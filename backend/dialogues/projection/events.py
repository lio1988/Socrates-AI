"""
Council Live View Foundation — versioned read-only CED event envelope.

Strict, frozen, versioned contract (audited + hardening round 1):

    schema            = ced_epistemic_event_v1   (wire name "schema";
                        accepted on BOTH read and write via validation alias)
    schema_version    = 1                        (envelope version)
    payload_schema    — MUST equal the registered payload model's name
    payload_version   — MUST equal the registered payload model's version
    event_id          — random uniqueness only; NEVER part of semantic identity
    idempotency_key   — deterministic identity of the canonical fact
    sequence          — assigned ONLY by the ledger at append; starts at 1
    session_id        — always required
    run_id            — typed stream contract: None on session-scoped events,
                        required non-sentinel string on run-scoped events
    event_type        — closed dotted taxonomy; canonically parsed to the
                        enum on validation (wire strings round-trip)
    actor_id / subject_id — optional; subject is the ANONYMOUS id pre-reveal
    phase / round_index   — closed PhaseLiteral / int ≥ 0; REQUIRED for the
                        matrix's phase-scoped event types
    emitted_at        — assigned ONLY by the ledger; MUST be timezone-aware
                        UTC (naive or non-UTC datetimes are rejected)
    causal_parent_id  — event_id of the causing event (optional)
    receipt_ref       — typed, resolvable ``ReceiptRef`` (receipt_kind +
                        request_id + receipt_digest) into the immutable
                        AtomicReceiptStore; REQUIRED where the contract matrix
                        says so (provider.completed)
    artifact_digest   — single digest for non-move artifacts (optional)
    raw_digest / validated_digest — REQUIRED inside move.validated payloads
    payload           — validated + normalized by the event's typed model

Semantic identity (audited idempotency rule): ``semantic_digest`` is computed
over canonical sorted UTF-8 JSON of the draft **excluding event_id** — and
drafts structurally exclude ``sequence`` and ``emitted_at``, so all three
volatile fields are outside the semantic identity by construction.

Deterministic keys (hardening round 1, finding 8): identity parts are encoded
as a canonical JSON array — never "|".join — so ("a|b","c") and ("a","b|c")
can no longer collide.

Nothing here executes or observes CED. The package imports nothing from
ced.py, providers, registry, or models — runtime-inert until the flag-gated
emission slice (guarded by a byte-identical FinalResponse test).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from .taxonomy import (
    FORBIDDEN_RUN_ID_SENTINELS,
    SESSION_SCOPED_TYPES,
    CedEventType,
    PhaseLiteral,
    run_stream_id,
    session_stream_id,
)

SCHEMA_NAME = "ced_epistemic_event_v1"
SCHEMA_VERSION = 1

RECEIPT_REF_SCHEMA = "ced_receipt_ref_v1"


class ReceiptRef(BaseModel):
    """
    Typed, RESOLVABLE reference to an immutable receipt (round 3, finding 3).

    The real AtomicReceiptStore is addressed by request_id (its file path
    derives from sha256(request_id) and the public lookup is
    ``load(request_id)``) — a bare content digest cannot locate a record.
    So the reference carries BOTH:

    - ``receipt_kind`` + ``request_id`` — locate the store/domain and load
      the record without scanning;
    - ``receipt_digest`` — verify that the loaded record is the exact
      immutable content this event refers to (content check happens at
      projection-integration time; the format is checkable here).
    """
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                              populate_by_name=True)

    schema_name:    str = Field(
        default=RECEIPT_REF_SCHEMA,
        validation_alias=AliasChoices("schema", "schema_name"),
        serialization_alias="schema",
    )
    receipt_kind:   Literal["provider", "ratification", "blocking_objection"]
    request_id:     str = Field(min_length=1, max_length=200)
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _check_schema(self) -> "ReceiptRef":
        if self.schema_name != RECEIPT_REF_SCHEMA:
            raise ValueError(
                f"unknown receipt-ref schema: {self.schema_name!r}"
            )
        return self


#: Which receipt_kind each receipt-bearing event must carry.
_RECEIPT_KIND_BY_EVENT: Dict[CedEventType, str] = {
    CedEventType.PROVIDER_COMPLETED:         "provider",
    CedEventType.PROVIDER_FAILED:            "provider",
    CedEventType.RATIFICATION_VOTE_RECORDED: "ratification",
    CedEventType.BLOCKING_OBJECTION_RAISED:  "blocking_objection",
}


def _utcnow() -> datetime:
    """Timezone-aware UTC now (matches models._utcnow semantics)."""
    return datetime.now(timezone.utc)


def sha256_hex(text: str) -> str:
    """Canonical SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_identity_digest(parts: List[Any]) -> str:
    """
    Collision-free deterministic digest of identity parts: canonical JSON
    array (type-preserving, no delimiter ambiguity), UTF-8, SHA-256.
    Parts must be JSON-serializable and finite.
    """
    encoded = json.dumps(
        parts, sort_keys=False, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )
    return sha256_hex(encoded)


def derive_idempotency_key(
    event_type: "CedEventType | str", *parts: Any
) -> str:
    """
    Low-level deterministic key over explicit parts (canonical JSON array).
    The CONTRACT key for events is ``derive_event_idempotency_key`` below —
    this helper remains only as a collision-free primitive.
    """
    et = CedEventType(event_type)
    return "idem_" + canonical_identity_digest([et.value, *parts])


def derive_event_idempotency_key(
    event_type: "CedEventType | str",
    *,
    session_id: str,
    run_id: Optional[str] = None,
    phase: Optional[str] = None,
    round_index: Optional[int] = None,
    payload: Dict[str, Any],
) -> str:
    """
    THE executable identity contract (round 2, finding 1): the idempotency
    key is derived from the event's CONTRACT_MATRIX identity fields —
    extracted from the envelope (session_id/run_id/phase/round_index) or the
    payload — as a canonical JSON array of [field_name, value] pairs
    (labeled, type-preserving, collision-free). A missing identity field is
    a contract violation. Every draft/sealed event is verified against this
    derivation — a caller-supplied wrong key is rejected.
    """
    et = CedEventType(event_type)
    from .contract_matrix import CONTRACT_MATRIX
    envelope_values: Dict[str, Any] = {
        "session_id": session_id,
        "run_id": run_id,
        "phase": phase,
        "round_index": round_index,
    }
    labeled_parts: list = []
    for field_name in CONTRACT_MATRIX[et].idempotency_identity:
        if field_name in envelope_values:
            value = envelope_values[field_name]
        else:
            value = payload.get(field_name)
        if value is None:
            raise ValueError(
                f"cannot derive idempotency key for {et.value}: identity "
                f"field {field_name!r} is missing"
            )
        labeled_parts.append([field_name, value])
    return "idem_" + canonical_identity_digest([et.value, labeled_parts])


def _contract_check(model: "CedEventDraft | CedEpistemicEvent") -> None:
    """Shared envelope contract checks (drafts AND sealed events)."""
    if model.schema_name != SCHEMA_NAME:
        raise ValueError(f"unknown schema name: {model.schema_name!r}")
    if model.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version {model.schema_version} "
            f"(this contract is v{SCHEMA_VERSION})"
        )
    if not model.session_id.strip():
        raise ValueError("session_id must be non-empty")
    if not model.idempotency_key.strip():
        raise ValueError("idempotency_key must be non-empty and deterministic")
    if model.causal_parent_id is not None and \
            model.causal_parent_id == model.event_id:
        raise ValueError("an event cannot be its own causal parent")

    # Typed stream contract (session/run sequencing — audited).
    if model.event_type in SESSION_SCOPED_TYPES:
        if model.run_id is not None:
            raise ValueError(
                f"{model.event_type.value} is session-scoped: run_id must be "
                "None (typed absence), never a value or sentinel"
            )
    else:
        if model.run_id is None or not model.run_id.strip():
            raise ValueError(
                f"{model.event_type.value} is run-scoped: run_id is required"
            )
        if model.run_id.strip().lower() in FORBIDDEN_RUN_ID_SENTINELS:
            raise ValueError(
                f"run_id {model.run_id!r} is a forbidden sentinel — the typed "
                "stream contract expresses absence as None on session-scoped "
                "events, never as a sentinel string"
            )

    # Matrix-driven envelope requirements (hardening round 1, finding 6).
    from .contract_matrix import CONTRACT_MATRIX
    contract = CONTRACT_MATRIX[model.event_type]
    for field_name in contract.required_envelope:
        if getattr(model, field_name, None) is None:
            raise ValueError(
                f"{model.event_type.value} requires envelope field "
                f"{field_name!r} (contract matrix)"
            )

    # Receipt rule (rounds 2–3, finding 5/R3-3): required / optional / none.
    # ("pending integration" is documentation status, not wire semantics.)
    if contract.receipt == "required":
        if model.receipt_ref is None:
            raise ValueError(
                f"{model.event_type.value} requires a receipt_ref — the "
                "immutable provider receipt is part of the contract"
            )
    elif contract.receipt == "none":
        if model.receipt_ref is not None:
            raise ValueError(
                f"{model.event_type.value} carries no receipt — a "
                "receipt_ref here is a contract violation"
            )
    if model.receipt_ref is not None:
        expected_kind = _RECEIPT_KIND_BY_EVENT.get(model.event_type)
        if expected_kind is None:
            raise ValueError(
                f"{model.event_type.value} is not a receipt-bearing event"
            )
        if model.receipt_ref.receipt_kind != expected_kind:
            raise ValueError(
                f"{model.event_type.value} requires receipt_kind "
                f"{expected_kind!r}, got {model.receipt_ref.receipt_kind!r}"
            )

    # Envelope-level pairing/version re-check + payload strict re-validation.
    from .payloads import PAYLOAD_MODELS
    payload_model = PAYLOAD_MODELS[model.event_type]
    if model.payload_schema != payload_model.PAYLOAD_SCHEMA:
        raise ValueError(
            f"wrong event/payload pairing: {model.event_type.value} requires "
            f"payload_schema {payload_model.PAYLOAD_SCHEMA!r}, "
            f"got {model.payload_schema!r}"
        )
    if model.payload_version != payload_model.PAYLOAD_VERSION:
        raise ValueError(
            f"payload_version mismatch for {model.payload_schema}: expected "
            f"{payload_model.PAYLOAD_VERSION}, got {model.payload_version}"
        )

    # Executable identity (round 2, finding 1): the supplied key must equal
    # the contract-derived key for this event's identity fields.
    expected_key = derive_event_idempotency_key(
        model.event_type,
        session_id=model.session_id,
        run_id=model.run_id,
        phase=model.phase,
        round_index=model.round_index,
        payload=model.payload,
    )
    if model.idempotency_key != expected_key:
        raise ValueError(
            f"idempotency_key does not match the contract-derived identity "
            f"for {model.event_type.value} "
            f"(identity fields: "
            f"{CONTRACT_MATRIX[model.event_type].idempotency_identity})"
        )

    # Canonical-JSON finiteness (rejects NaN/Infinity smuggled past typing).
    try:
        json.dumps(model.payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"payload must be finite JSON-serializable: {exc}")


class _EnvelopeBase(BaseModel):
    """Fields shared by drafts and sealed events."""
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, populate_by_name=True,
    )

    schema_name:      str = Field(
        default=SCHEMA_NAME,
        validation_alias=AliasChoices("schema", "schema_name"),
        serialization_alias="schema",
    )
    schema_version:   int = SCHEMA_VERSION
    payload_schema:   str
    payload_version:  int
    # Bounded, safe identifier format (round 2, finding 2).
    event_id:         str = Field(
        default_factory=lambda: "evt_" + uuid.uuid4().hex,
        pattern=r"^evt_[0-9A-Za-z_-]{3,64}$")
    session_id:       str
    run_id:           Optional[str] = None
    event_type:       CedEventType
    actor_id:         Optional[str] = None
    subject_id:       Optional[str] = None  # anonymous pre-reveal (blind events)
    phase:            Optional[PhaseLiteral] = None
    round_index:      Optional[int] = Field(default=None, ge=0)
    causal_parent_id: Optional[str] = Field(
        default=None, pattern=r"^evt_[0-9A-Za-z_-]{3,64}$")
    # Typed, resolvable receipt reference (round 3, finding 3): kind +
    # request_id locate the immutable AtomicReceiptStore record;
    # receipt_digest verifies the loaded content.
    receipt_ref:      Optional[ReceiptRef] = None
    artifact_digest:  Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$")
    idempotency_key:  str
    payload:          Dict[str, Any] = Field(default_factory=dict)

    @property
    def stream_id(self) -> str:
        """Derived, never caller-asserted: run stream, else session stream."""
        if self.run_id is not None:
            return run_stream_id(self.run_id)
        return session_stream_id(self.session_id)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, values: Any) -> Any:
        """
        Canonical parsing + payload normalization (wire round-trip support):
        - event_type strings are parsed to the enum HERE, so strict field
          validation receives the canonical enum on both construction and
          wire re-validation;
        - the payload is validated against its typed model and stored as the
          model's normalized JSON dump, so semantic digests are canonical.
        Pairing/version violations are rejected here (and re-checked in the
        after-validator).
        """
        if not isinstance(values, dict):
            return values
        raw_type = values.get("event_type")
        try:
            event_type = CedEventType(raw_type)
        except (ValueError, TypeError):
            return values  # let field validation report the unknown type
        values["event_type"] = event_type  # canonical enum on the field

        payload_schema = values.get("payload_schema")
        payload_version = values.get("payload_version")
        if payload_schema is None or payload_version is None:
            return values  # required-field errors will surface

        from .payloads import PAYLOAD_MODELS
        payload_model = PAYLOAD_MODELS[event_type]
        if payload_schema != payload_model.PAYLOAD_SCHEMA:
            raise ValueError(
                f"wrong event/payload pairing: {event_type.value} requires "
                f"payload_schema {payload_model.PAYLOAD_SCHEMA!r}, "
                f"got {payload_schema!r}"
            )
        if payload_version != payload_model.PAYLOAD_VERSION:
            raise ValueError(
                f"payload_version mismatch for {payload_schema}: expected "
                f"{payload_model.PAYLOAD_VERSION}, got {payload_version}"
            )
        raw_payload = values.get("payload") or {}
        if not isinstance(raw_payload, dict):
            raise ValueError("payload must be a mapping")
        validated = payload_model(**raw_payload)   # strict typed validation
        values["payload"] = validated.model_dump(mode="json")
        return values


class CedEventDraft(_EnvelopeBase):
    """
    An event as handed to the ledger by a (future) CED observer — everything
    EXCEPT sequence and emitted_at, which ONLY the ledger assigns at append.
    Frozen and strict; payload is normalized by its typed model.
    """

    @model_validator(mode="after")
    def _check_contract(self) -> "CedEventDraft":
        _contract_check(self)
        return self


class CedEpistemicEvent(_EnvelopeBase):
    """
    The sealed, immutable event as it exists on the ledger. Constructed ONLY
    by EventLedger.append(): sequence is monotonic gap-free per stream and
    STARTS AT 1; emitted_at is ledger-assigned, timezone-aware UTC, and
    advisory (ordering is by sequence, never by timestamp).

    Wire round-trip is part of the contract:
    ``CedEpistemicEvent.model_validate(sealed.wire_dict())`` and
    ``model_validate_json(...)`` reproduce an equal event.
    """
    sequence:   int = Field(ge=1)
    # strict=False on this one field so the ISO-8601 wire form re-parses;
    # UTC-awareness is enforced below regardless of input form.
    emitted_at: datetime = Field(strict=False)

    @model_validator(mode="after")
    def _check_contract(self) -> "CedEpistemicEvent":
        _contract_check(self)
        offset = self.emitted_at.utcoffset()
        if self.emitted_at.tzinfo is None or offset is None:
            raise ValueError(
                "emitted_at must be timezone-aware UTC (naive datetime "
                "rejected)"
            )
        if offset.total_seconds() != 0:
            raise ValueError(
                f"emitted_at must be UTC (offset {offset} rejected — the "
                "contract does not silently normalize non-UTC clocks)"
            )
        return self

    def wire_dict(self) -> Dict[str, Any]:
        """Serialization with the on-wire field name ``schema``."""
        return self.model_dump(by_alias=True, mode="json")


def semantic_digest(draft: CedEventDraft) -> str:
    """
    Canonical semantic identity of a draft: SHA-256 over sorted-key UTF-8
    JSON, EXCLUDING event_id (random) — and structurally excluding sequence
    and emitted_at, which do not exist on drafts. Used by the ledger to
    distinguish an idempotent duplicate (same digest) from a CONFLICT
    (same idempotency_key, different semantic content).
    """
    data = draft.model_dump(mode="json", exclude={"event_id"})
    canonical = json.dumps(
        data, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )
    return sha256_hex(canonical)


def build_draft(
    *,
    event_type: "CedEventType | str",
    session_id: str,
    payload: Dict[str, Any],
    run_id: Optional[str] = None,
    **envelope: Any,
) -> CedEventDraft:
    """
    Ergonomic constructor: fills payload_schema/payload_version from the
    registered payload model and derives the idempotency key from the
    CONTRACT identity fields itself (round 2, finding 1) — there is no
    public way to supply an arbitrary key, and the contract check rejects a
    wrong one on direct CedEventDraft construction anyway.
    """
    et = CedEventType(event_type)
    from .payloads import PAYLOAD_MODELS
    payload_model = PAYLOAD_MODELS[et]
    normalized = payload_model(**payload).model_dump(mode="json")
    idempotency_key = derive_event_idempotency_key(
        et,
        session_id=session_id,
        run_id=run_id,
        phase=envelope.get("phase"),
        round_index=envelope.get("round_index"),
        payload=normalized,
    )
    return CedEventDraft(
        event_type=et,
        session_id=session_id,
        run_id=run_id,
        payload_schema=payload_model.PAYLOAD_SCHEMA,
        payload_version=payload_model.PAYLOAD_VERSION,
        payload=normalized,
        idempotency_key=idempotency_key,
        **envelope,
    )

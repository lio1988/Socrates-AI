"""
Council Live View Foundation — versioned read-only CED event envelope.

Strict, frozen, versioned contract (audited):

    schema            = ced_epistemic_event_v1   (wire name "schema")
    schema_version    = 1                        (envelope version)
    payload_schema    — MUST equal the registered payload model's name
    payload_version   — MUST equal the registered payload model's version
    event_id          — random uniqueness only; NEVER part of semantic identity
    idempotency_key   — deterministic identity of the canonical fact
    sequence          — assigned ONLY by the ledger at append; starts at 1
    session_id        — always required
    run_id            — typed stream contract: None on session-scoped events,
                        required non-sentinel string on run-scoped events
    event_type        — closed dotted taxonomy (taxonomy.py)
    actor_id / subject_id — optional; subject is the ANONYMOUS id pre-reveal
    phase / round_index   — required for PHASE_REQUIRED_TYPES
    emitted_at        — assigned ONLY by the ledger; advisory display data
    causal_parent_id  — event_id of the causing event (optional)
    receipt_ref       — AtomicReceiptStore digest reference (optional)
    artifact_digest   — single digest for non-move artifacts (optional)
    raw_digest / validated_digest — REQUIRED inside move.validated payloads
    payload           — validated + normalized by the event's typed model

Semantic identity (audited idempotency rule): ``semantic_digest`` is computed
over canonical sorted UTF-8 JSON of the draft **excluding event_id** — and
drafts structurally exclude ``sequence`` and ``emitted_at``, so all three
volatile fields are outside the semantic identity by construction.

Nothing here executes or observes CED. The package imports nothing from
ced.py, providers, registry, or models — runtime-inert until the flag-gated
emission slice (guarded by a byte-identical FinalResponse test).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .taxonomy import (
    FORBIDDEN_RUN_ID_SENTINELS,
    PHASE_REQUIRED_TYPES,
    SESSION_SCOPED_TYPES,
    CedEventType,
    run_stream_id,
    session_stream_id,
)

SCHEMA_NAME = "ced_epistemic_event_v1"
SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    """Timezone-aware UTC now (matches models._utcnow semantics)."""
    return datetime.now(timezone.utc)


def sha256_hex(text: str) -> str:
    """Canonical SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_idempotency_key(
    event_type: "CedEventType | str", *parts: Any
) -> str:
    """
    Deterministic idempotency key: SHA-256 over the event type plus the stable
    identity parts of the canonical fact (§9.2 col 7 — e.g. run, phase, round,
    agent). Distinct from event_id: two emissions of the SAME canonical fact
    share the SAME idempotency key.
    """
    et = CedEventType(event_type)
    joined = "|".join([et.value, *[str(p) for p in parts]])
    return "idem_" + sha256_hex(joined)


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

    if model.event_type in PHASE_REQUIRED_TYPES:
        if model.phase is None or model.round_index is None:
            raise ValueError(
                f"{model.event_type.value} requires envelope phase and "
                "round_index"
            )

    # Envelope-level pairing/version re-check + payload strict re-validation.
    from .payloads import PAYLOAD_MODELS  # local import: no cycle at import time
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

    # Canonical-JSON finiteness (rejects NaN/Infinity smuggled past typing).
    try:
        json.dumps(model.payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"payload must be finite JSON-serializable: {exc}")


class _EnvelopeBase(BaseModel):
    """Fields shared by drafts and sealed events."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name:      str = Field(default=SCHEMA_NAME,
                                  serialization_alias="schema")
    schema_version:   int = SCHEMA_VERSION
    payload_schema:   str
    payload_version:  int
    event_id:         str = Field(
        default_factory=lambda: "evt_" + uuid.uuid4().hex)
    session_id:       str
    run_id:           Optional[str] = None
    event_type:       CedEventType
    actor_id:         Optional[str] = None
    subject_id:       Optional[str] = None  # anonymous pre-reveal (blind events)
    phase:            Optional[str] = None
    round_index:      Optional[int] = None
    causal_parent_id: Optional[str] = None
    receipt_ref:      Optional[str] = None
    artifact_digest:  Optional[str] = None
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
    def _normalize_payload(cls, values: Any) -> Any:
        """
        Validate the payload against its typed model and store the NORMALIZED
        dump, so semantic digests are canonical. Pairing/version violations
        are rejected here (and re-checked in the after-validator).
        """
        if not isinstance(values, dict):
            return values
        raw_type = values.get("event_type")
        try:
            event_type = CedEventType(raw_type)
        except (ValueError, TypeError):
            return values  # let field validation report the unknown type
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
    STARTS AT 1; emitted_at is ledger-assigned and advisory (ordering is by
    sequence, never by timestamp).
    """
    sequence:   int = Field(ge=1)
    emitted_at: datetime

    @model_validator(mode="after")
    def _check_contract(self) -> "CedEpistemicEvent":
        _contract_check(self)
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
    idempotency_key: Optional[str] = None,
    idempotency_parts: Optional[list] = None,
    **envelope: Any,
) -> CedEventDraft:
    """
    Ergonomic constructor: fills payload_schema/payload_version from the
    registered payload model (still fully validated afterwards). The caller
    must supply either an explicit idempotency_key or the deterministic
    identity parts.
    """
    et = CedEventType(event_type)
    from .payloads import PAYLOAD_MODELS
    payload_model = PAYLOAD_MODELS[et]
    if idempotency_key is None:
        if not idempotency_parts:
            raise ValueError(
                "provide idempotency_key or idempotency_parts — idempotency "
                "identity is never implicit"
            )
        idempotency_key = derive_idempotency_key(et, *idempotency_parts)
    return CedEventDraft(
        event_type=et,
        session_id=session_id,
        run_id=run_id,
        payload_schema=payload_model.PAYLOAD_SCHEMA,
        payload_version=payload_model.PAYLOAD_VERSION,
        payload=payload,
        idempotency_key=idempotency_key,
        **envelope,
    )

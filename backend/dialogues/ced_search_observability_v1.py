"""Immutable CED-side SearchState v1 observability contracts.

These views preserve typed decisions already owned by the governing Hybrid
state.  They do not infer outcomes and carry no authority back into CED.  The
module deliberately stays on the trusted CED side of the H8 boundary: the
runtime-inert ``socrates_zero`` package must not import the Hybrid core.

SearchState v0 remains embedded, unchanged, for compatibility and replay.  The
new semantic identity contains only canonical IDs and typed values; prose,
scores, confidence, consensus, markers and provider/model routing are absent.
"""

from __future__ import annotations

import hashlib
from typing import ClassVar, Dict, Iterable, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .hybrid_epistemic import (
    HYBRID_EPISTEMIC_SCHEMA_VERSION,
    ContradictionState,
    EvidenceSourceType,
    EvidenceStance,
    ObjectionScope,
    ObjectionState,
    ObjectionTargetProvenance,
    SupportState,
    VerificationClass,
    VerificationMethod,
    VerificationResult,
)
from .socrates_zero.contracts import (
    ContractValidationError,
    SearchState,
    canonical_json,
    stable_contract_id,
)


SEARCH_STATE_V1_SCHEMA_VERSION = "socrates.zero.search-state/v1"
SEARCH_STATE_V1_PROJECTION_VERSION = "ced-search-state-projection/v1"


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


class _FrozenObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    semantic_digest: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    def semantic_payload(self) -> Dict[str, object]:
        raise NotImplementedError

    @model_validator(mode="after")
    def validate_semantic_digest(self) -> "_FrozenObservation":
        expected = _digest(self.semantic_payload())
        if self.semantic_digest is not None and self.semantic_digest != expected:
            raise ContractValidationError(
                "semantic_digest does not match typed canonical content"
            )
        object.__setattr__(self, "semantic_digest", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            **self.semantic_payload(),
            "semantic_digest": self.semantic_digest,
        }


class CanonicalEvidenceView(_FrozenObservation):
    """Decision-relevant typing for one admissible canonical evidence record."""

    source_record_id: str
    claim_id: str
    stance: EvidenceStance
    source_type: EvidenceSourceType
    receipt_ref: Optional[str] = None

    _nonblank_fields = field_validator("source_record_id", "claim_id")(_nonblank)

    def semantic_payload(self) -> Dict[str, object]:
        return {
            "source_record_id": self.source_record_id,
            "claim_id": self.claim_id,
            "stance": self.stance.value,
            "source_type": self.source_type.value,
            "receipt_ref": self.receipt_ref,
        }


class CanonicalVerificationView(_FrozenObservation):
    """Typed outcome and provenance of one canonical verification record."""

    source_record_id: str
    claim_id: str
    objection_id: Optional[str] = None
    verification_class: VerificationClass
    method: Optional[VerificationMethod] = None
    result: VerificationResult
    evidence_ids: Tuple[str, ...] = ()

    _nonblank_fields = field_validator("source_record_id", "claim_id")(_nonblank)

    @model_validator(mode="after")
    def canonicalize_evidence_ids(self) -> "CanonicalVerificationView":
        ordered = tuple(sorted(self.evidence_ids))
        if any(not item.strip() for item in ordered):
            raise ContractValidationError("verification evidence IDs must not be blank")
        if len(set(ordered)) != len(ordered):
            raise ContractValidationError(
                f"verification {self.source_record_id!r} contains duplicate evidence IDs"
            )
        object.__setattr__(self, "evidence_ids", ordered)
        return self

    def semantic_payload(self) -> Dict[str, object]:
        return {
            "source_record_id": self.source_record_id,
            "claim_id": self.claim_id,
            "objection_id": self.objection_id,
            "verification_class": self.verification_class.value,
            "method": self.method.value if self.method is not None else None,
            "result": self.result.value,
            "evidence_ids": sorted(self.evidence_ids),
        }


class CanonicalClaimAssessmentView(_FrozenObservation):
    """The governing Hybrid assessment, copied without recomputing its rules."""

    claim_id: str
    support_state: SupportState
    basis_record_ids: Tuple[str, ...] = ()
    falsifying_record_ids: Tuple[str, ...] = ()
    unresolved_record_ids: Tuple[str, ...] = ()
    eligible_for_assembly: bool

    _claim_id_nonblank = field_validator("claim_id")(_nonblank)

    @model_validator(mode="after")
    def canonicalize_record_ids(self) -> "CanonicalClaimAssessmentView":
        for field_name in (
            "basis_record_ids",
            "falsifying_record_ids",
            "unresolved_record_ids",
        ):
            ordered = tuple(sorted(getattr(self, field_name)))
            if any(not item.strip() for item in ordered):
                raise ContractValidationError(
                    f"{field_name} must not contain blank record IDs"
                )
            if len(set(ordered)) != len(ordered):
                raise ContractValidationError(
                    f"assessment {self.claim_id!r} contains duplicate {field_name}"
                )
            object.__setattr__(self, field_name, ordered)
        return self

    def semantic_payload(self) -> Dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "support_state": self.support_state.value,
            "basis_record_ids": sorted(self.basis_record_ids),
            "falsifying_record_ids": sorted(self.falsifying_record_ids),
            "unresolved_record_ids": sorted(self.unresolved_record_ids),
            "eligible_for_assembly": self.eligible_for_assembly,
        }


class CanonicalObjectionView(_FrozenObservation):
    """Current canonical objection lifecycle state and its governing links."""

    source_record_id: str
    target_claim_id: str
    state: ObjectionState
    scope: ObjectionScope
    target_provenance: ObjectionTargetProvenance
    verification_id: Optional[str] = None

    _nonblank_fields = field_validator(
        "source_record_id", "target_claim_id"
    )(_nonblank)

    def semantic_payload(self) -> Dict[str, object]:
        return {
            "source_record_id": self.source_record_id,
            "target_claim_id": self.target_claim_id,
            "state": self.state.value,
            "scope": self.scope.value,
            "target_provenance": self.target_provenance.value,
            "verification_id": self.verification_id,
        }


class CanonicalContradictionView(_FrozenObservation):
    """Current canonical contradiction lifecycle state and source links."""

    source_record_id: str
    claim_id_a: str
    claim_id_b: str
    state: ContradictionState
    verification_id: Optional[str] = None

    _nonblank_fields = field_validator(
        "source_record_id", "claim_id_a", "claim_id_b"
    )(_nonblank)

    def semantic_payload(self) -> Dict[str, object]:
        return {
            "source_record_id": self.source_record_id,
            "claim_id_a": self.claim_id_a,
            "claim_id_b": self.claim_id_b,
            "state": self.state.value,
            "verification_id": self.verification_id,
        }


class SearchStateV1(BaseModel):
    """Opt-in typed observability envelope around the frozen v0 SearchState."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[
        SEARCH_STATE_V1_SCHEMA_VERSION
    ] = SEARCH_STATE_V1_SCHEMA_VERSION
    projection_version: Literal[
        SEARCH_STATE_V1_PROJECTION_VERSION
    ] = SEARCH_STATE_V1_PROJECTION_VERSION
    authority_schema_version: Literal[
        HYBRID_EPISTEMIC_SCHEMA_VERSION
    ] = HYBRID_EPISTEMIC_SCHEMA_VERSION
    state_id: Optional[str] = None
    base_state: SearchState
    evidence: Tuple[CanonicalEvidenceView, ...] = ()
    verifications: Tuple[CanonicalVerificationView, ...] = ()
    claim_assessments: Tuple[CanonicalClaimAssessmentView, ...] = ()
    objections: Tuple[CanonicalObjectionView, ...] = ()
    contradictions: Tuple[CanonicalContradictionView, ...] = ()

    _COLLECTION_KEYS: ClassVar[Dict[str, str]] = {
        "evidence": "source_record_id",
        "verifications": "source_record_id",
        "claim_assessments": "claim_id",
        "objections": "source_record_id",
        "contradictions": "source_record_id",
    }

    @staticmethod
    def _canonicalize(
        values: Iterable[_FrozenObservation], field_name: str, key_name: str
    ) -> Tuple[_FrozenObservation, ...]:
        ordered = tuple(sorted(values, key=lambda item: getattr(item, key_name)))
        seen: Dict[str, str] = {}
        for item in ordered:
            key = getattr(item, key_name)
            digest = item.semantic_digest or ""
            previous = seen.get(key)
            if previous is not None:
                detail = "conflicting content" if previous != digest else "duplicate"
                raise ContractValidationError(
                    f"{field_name} contains {detail} for {key!r}"
                )
            seen[key] = digest
        return ordered

    @model_validator(mode="after")
    def canonicalize_validate_and_identify(self) -> "SearchStateV1":
        for field_name, key_name in self._COLLECTION_KEYS.items():
            canonical = self._canonicalize(
                getattr(self, field_name), field_name, key_name
            )
            object.__setattr__(self, field_name, canonical)

        claim_ids = {item.claim_id for item in self.claim_assessments}
        evidence_ids = {item.source_record_id for item in self.evidence}
        verification_ids = {item.source_record_id for item in self.verifications}
        objection_ids = {item.source_record_id for item in self.objections}
        contradiction_ids = {item.source_record_id for item in self.contradictions}

        source_ids = evidence_ids | verification_ids | objection_ids | contradiction_ids
        expected_count = (
            len(evidence_ids)
            + len(verification_ids)
            + len(objection_ids)
            + len(contradiction_ids)
        )
        if len(source_ids) != expected_count:
            raise ContractValidationError(
                "canonical source record IDs must be unique across observation families"
            )

        for item in self.evidence:
            self._require_claim(item.claim_id, claim_ids, item.source_record_id)
        for item in self.verifications:
            self._require_claim(item.claim_id, claim_ids, item.source_record_id)
            if item.objection_id is not None and item.objection_id not in objection_ids:
                raise ContractValidationError(
                    f"verification {item.source_record_id!r} has dangling objection ID"
                )
            missing = set(item.evidence_ids) - evidence_ids
            if missing:
                raise ContractValidationError(
                    f"verification {item.source_record_id!r} has dangling evidence IDs"
                )
        for item in self.objections:
            if item.target_provenance is not ObjectionTargetProvenance.UNMAPPED:
                self._require_claim(
                    item.target_claim_id, claim_ids, item.source_record_id
                )
            if item.verification_id is not None \
                    and item.verification_id not in verification_ids:
                raise ContractValidationError(
                    f"objection {item.source_record_id!r} has dangling verification ID"
                )
        for item in self.contradictions:
            self._require_claim(item.claim_id_a, claim_ids, item.source_record_id)
            self._require_claim(item.claim_id_b, claim_ids, item.source_record_id)
            if item.verification_id is not None \
                    and item.verification_id not in verification_ids:
                raise ContractValidationError(
                    f"contradiction {item.source_record_id!r} has dangling verification ID"
                )

        allowed_basis = evidence_ids | verification_ids
        allowed_falsifying = verification_ids | objection_ids
        allowed_unresolved = (
            evidence_ids | verification_ids | objection_ids | contradiction_ids
        )
        for assessment in self.claim_assessments:
            self._require_records(
                assessment.basis_record_ids,
                allowed_basis,
                assessment.claim_id,
                "basis",
            )
            self._require_records(
                assessment.falsifying_record_ids,
                allowed_falsifying,
                assessment.claim_id,
                "falsifying",
            )
            self._require_records(
                assessment.unresolved_record_ids,
                allowed_unresolved,
                assessment.claim_id,
                "unresolved",
            )

        expected = stable_contract_id("szstatev1", self.identity_payload())
        if self.state_id is not None and self.state_id != expected:
            raise ContractValidationError("v1 state_id does not match semantic content")
        object.__setattr__(self, "state_id", expected)
        return self

    @staticmethod
    def _require_claim(claim_id: str, claim_ids: set[str], source_id: str) -> None:
        if claim_id not in claim_ids:
            raise ContractValidationError(
                f"canonical observation {source_id!r} has dangling claim ID {claim_id!r}"
            )

    @staticmethod
    def _require_records(
        record_ids: Tuple[str, ...],
        allowed: set[str],
        claim_id: str,
        kind: str,
    ) -> None:
        missing = set(record_ids) - allowed
        if missing:
            raise ContractValidationError(
                f"claim assessment {claim_id!r} has dangling {kind} record IDs"
            )

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "projection_version": self.projection_version,
            "authority_schema_version": self.authority_schema_version,
            "base_state_id": self.base_state.state_id,
            **{
                field_name: [
                    item.identity_payload() for item in getattr(self, field_name)
                ]
                for field_name in self._COLLECTION_KEYS
            },
        }


__all__ = [
    "SEARCH_STATE_V1_PROJECTION_VERSION",
    "SEARCH_STATE_V1_SCHEMA_VERSION",
    "CanonicalClaimAssessmentView",
    "CanonicalContradictionView",
    "CanonicalEvidenceView",
    "CanonicalObjectionView",
    "CanonicalVerificationView",
    "SearchStateV1",
]

"""Opt-in trusted projection into typed canonical SearchState v1 observations.

The v0 projector is invoked unchanged and its output is retained as the base
snapshot.  The additional views are direct, current-time copies of canonical
Hybrid records or of ``HybridEpistemicState.assess_all()`` results.  No field is
derived from prose and no status is decided here.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from .ced import CanonicalTaskSpec
from .ced_search_observability_v1 import (
    SEARCH_STATE_V1_PROJECTION_VERSION,
    CanonicalClaimAssessmentView,
    CanonicalContradictionView,
    CanonicalEvidenceView,
    CanonicalObjectionView,
    CanonicalVerificationView,
    SearchStateV1,
)
from .ced_search_projection import project_search_state
from .hybrid_epistemic import (
    HybridEpistemicState,
    validate_verification_record,
)
from .models import SessionState
from .socratic import AporiaRecord, CommitmentRecord
from .socrates_zero.contracts import (
    BudgetUsage,
    ContractValidationError,
    SearchBudget,
)


def _validate_index(
    records: Mapping[str, object], *, id_attribute: str, family: str
) -> None:
    """Reject a mutated ledger whose storage key no longer names its record."""
    record_ids = []
    for key, record in records.items():
        record_id = getattr(record, id_attribute, None)
        if key != record_id:
            raise ContractValidationError(
                f"{family} index key {key!r} does not match record ID {record_id!r}"
            )
        record_ids.append(record_id)
    if len(set(record_ids)) != len(record_ids):
        raise ContractValidationError(f"{family} index contains duplicate record IDs")


def _validate_hybrid_snapshot(hybrid: HybridEpistemicState) -> None:
    """Recheck the canonical snapshot rather than silently dropping corruption."""
    for records, id_attribute, family in (
        (hybrid.claims, "claim_id", "claim"),
        (hybrid.evidence, "evidence_id", "evidence"),
        (hybrid.verifications, "verification_id", "verification"),
        (hybrid.objections, "objection_id", "objection"),
        (hybrid.contradictions, "contradiction_id", "contradiction"),
    ):
        _validate_index(records, id_attribute=id_attribute, family=family)
    for record in hybrid.verifications.values():
        validate_verification_record(
            record,
            task_text=hybrid.task_text,
            evidence=hybrid.evidence,
        )


def project_search_state_v1(
    state: SessionState,
    task: Optional[CanonicalTaskSpec],
    *,
    budget: SearchBudget,
    budget_usage: Optional[BudgetUsage] = None,
    commitments: Sequence[CommitmentRecord] = (),
    aporia_records: Sequence[AporiaRecord] = (),
    hybrid_state: Optional[HybridEpistemicState] = None,
    depth: int = 0,
) -> SearchStateV1:
    """Project one present canonical snapshot without mutation or inference."""
    base_state = project_search_state(
        state,
        task,
        budget=budget,
        budget_usage=budget_usage,
        commitments=commitments,
        aporia_records=aporia_records,
        hybrid_state=hybrid_state,
        depth=depth,
    )
    if hybrid_state is None:
        return SearchStateV1(base_state=base_state)

    _validate_hybrid_snapshot(hybrid_state)
    assessments = hybrid_state.assess_all()
    if set(assessments) != set(hybrid_state.claims):
        raise ContractValidationError(
            "governing claim assessments do not cover the canonical claim index"
        )

    evidence = tuple(
        CanonicalEvidenceView(
            source_record_id=record.evidence_id,
            claim_id=record.claim_id,
            stance=record.stance,
            source_type=record.source_type,
            receipt_ref=record.receipt_ref,
        )
        for record in hybrid_state.evidence.values()
        if record.admissible
    )
    verifications = tuple(
        CanonicalVerificationView(
            source_record_id=record.verification_id,
            claim_id=record.claim_id,
            objection_id=record.objection_id,
            verification_class=record.verification_class,
            method=record.method,
            result=record.result,
            evidence_ids=tuple(record.evidence_ids),
        )
        for record in hybrid_state.verifications.values()
    )
    claim_assessments = tuple(
        CanonicalClaimAssessmentView(
            claim_id=assessment.claim_id,
            support_state=assessment.support_state,
            basis_record_ids=tuple(assessment.basis_record_ids),
            falsifying_record_ids=tuple(assessment.falsifying_record_ids),
            unresolved_record_ids=tuple(assessment.unresolved_record_ids),
            eligible_for_assembly=assessment.eligible_for_assembly,
        )
        for assessment in assessments.values()
    )
    objections = tuple(
        CanonicalObjectionView(
            source_record_id=record.objection_id,
            target_claim_id=record.target_claim_id,
            state=record.state,
            scope=record.scope,
            target_provenance=record.target_provenance,
            verification_id=record.verification_id,
        )
        for record in hybrid_state.objections.values()
    )
    contradictions = tuple(
        CanonicalContradictionView(
            source_record_id=record.contradiction_id,
            claim_id_a=record.claim_id_a,
            claim_id_b=record.claim_id_b,
            state=record.state,
            verification_id=record.verification_id,
        )
        for record in hybrid_state.contradictions.values()
    )
    return SearchStateV1(
        base_state=base_state,
        evidence=evidence,
        verifications=verifications,
        claim_assessments=claim_assessments,
        objections=objections,
        contradictions=contradictions,
    )


__all__ = ["SEARCH_STATE_V1_PROJECTION_VERSION", "project_search_state_v1"]


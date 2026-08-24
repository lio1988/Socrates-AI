"""Trusted CED-side projection into immutable SocratesZero search state.

This bridge lives on the governing side of the authority boundary because it
must read Hybrid records.  The search package receives only the resulting
frozen references and never imports or reaches the governing core directly.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Sequence, Tuple

from .ced import CanonicalTaskSpec
from .hybrid_epistemic import (
    UNMAPPED_TARGET,
    ContradictionState,
    HybridEpistemicState,
    ObjectionState,
)
from .models import AgentRole, DialogPhase, ProviderStatus, SessionState
from .socratic import AporiaRecord, CommitmentRecord, live_commitments
from .socrates_zero.contracts import (
    BudgetUsage,
    ContractValidationError,
    MoveHistoryRef,
    ObservationRef,
    RoleHistoryRef,
    SearchBudget,
    SearchState,
    SemanticArtifactRef,
    TerminalStatus,
    canonical_json,
)


SEARCH_STATE_PROJECTION_VERSION = "ced-search-state-projection/v0"

_PHASE_ORDER = {phase.value: index for index, phase in enumerate(DialogPhase)}
_UNRESOLVED_OBJECTION_STATES = {
    ObjectionState.RAISED,
    ObjectionState.PENDING_VERIFICATION,
    ObjectionState.INCONCLUSIVE,
}


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _artifact(artifact_id: str, value: object) -> SemanticArtifactRef:
    return SemanticArtifactRef(artifact_id=artifact_id, semantic_digest=_digest(value))


def _terminal_status(
    state: SessionState, budget: SearchBudget, usage: BudgetUsage
) -> TerminalStatus:
    if budget.violations(usage):
        return TerminalStatus.BUDGET_EXHAUSTED
    if state.phase is not DialogPhase.COMPLETE and state.final_response is None:
        return TerminalStatus.NON_TERMINAL
    final = state.final_response
    if final is None or final.synthesis is None or final.release_decision == "blocked":
        return TerminalStatus.BLOCKED
    return TerminalStatus.ANSWER_READY


def _validate_source(
    state: SessionState,
    task: Optional[CanonicalTaskSpec],
    commitments: Sequence[CommitmentRecord],
    aporia_records: Sequence[AporiaRecord],
    hybrid_state: Optional[HybridEpistemicState],
) -> None:
    if not state.question.strip():
        raise ContractValidationError("source state question must not be blank")
    if state.phase is not DialogPhase.COMPLETE and state.final_response is not None:
        raise ContractValidationError(
            "non-complete source state cannot contain a final response"
        )
    if state.phase is DialogPhase.COMPLETE:
        if task is not None:
            raise ContractValidationError("a complete source state cannot have an active task")
    elif task is None:
        raise ContractValidationError("a non-terminal source state requires an active task")
    if task is not None:
        if task.agent_id not in state.agent_states:
            raise ContractValidationError(
                f"active agent {task.agent_id!r} is absent from source state"
            )
        if task.round_number < 0 or task.slot_index < 0:
            raise ContractValidationError("active task indices must be non-negative")

    accepted_move_ids = {move.move_id for move in state.moves}
    if len(accepted_move_ids) != len(state.moves):
        raise ContractValidationError("source state contains duplicate accepted move IDs")
    commitment_ids = {record.commitment_id for record in commitments}
    if len(commitment_ids) != len(commitments):
        raise ContractValidationError("commitment ledger contains duplicate IDs")
    for record in commitments:
        if record.source_move_id not in accepted_move_ids:
            raise ContractValidationError(
                f"commitment {record.commitment_id!r} has unknown source move "
                f"{record.source_move_id!r}"
            )
        if record.target_commitment_id and record.target_commitment_id not in commitment_ids:
            raise ContractValidationError(
                f"commitment {record.commitment_id!r} has unknown target commitment"
            )
    for record in aporia_records:
        refs = {record.previous_commitment_id, record.conflicting_commitment_id}
        if not refs <= commitment_ids:
            raise ContractValidationError(
                f"aporia {record.aporia_id!r} references an unknown commitment"
            )

    if hybrid_state is None:
        return
    if hybrid_state.session_id != state.session_id:
        raise ContractValidationError("Hybrid session does not match source session")
    if hybrid_state.task_text != state.question:
        raise ContractValidationError("Hybrid task text does not match source task text")
    claim_ids = set(hybrid_state.claims)
    for claim in hybrid_state.claims.values():
        if claim.superseded_by and claim.superseded_by not in claim_ids:
            raise ContractValidationError(
                f"claim {claim.claim_id!r} has unknown superseding claim"
            )
    for evidence in hybrid_state.evidence.values():
        if evidence.claim_id not in claim_ids:
            raise ContractValidationError(
                f"evidence {evidence.evidence_id!r} has unknown claim target"
            )
    for objection in hybrid_state.objections.values():
        if objection.target_claim_id not in claim_ids | {UNMAPPED_TARGET}:
            raise ContractValidationError(
                f"objection {objection.objection_id!r} has unknown claim target"
            )
    for contradiction in hybrid_state.contradictions.values():
        if {contradiction.claim_id_a, contradiction.claim_id_b} - claim_ids:
            raise ContractValidationError(
                f"contradiction {contradiction.contradiction_id!r} has unknown claim target"
            )
    for verification in hybrid_state.verifications.values():
        if verification.claim_id not in claim_ids:
            raise ContractValidationError(
                f"verification {verification.verification_id!r} has unknown claim target"
            )
        if (verification.objection_id is not None
                and verification.objection_id not in hybrid_state.objections):
            raise ContractValidationError(
                f"verification {verification.verification_id!r} has unknown objection"
            )


def _role_history(state: SessionState) -> Tuple[RoleHistoryRef, ...]:
    refs = []
    for row in state.role_history:
        try:
            phase = DialogPhase(str(row["phase"]))
            role = AgentRole(str(row["role"]))
            round_index = int(row["round_index"])
            agent_id = str(row["agent_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractValidationError("source role history is malformed") from exc
        if agent_id not in state.agent_states or round_index < 0:
            raise ContractValidationError("source role history references invalid routing")
        refs.append(
            RoleHistoryRef(
                phase=phase.value,
                round_index=round_index,
                agent_id=agent_id,
                role=role.value,
            )
        )
    return tuple(
        sorted(
            refs,
            key=lambda ref: (
                ref.round_index,
                _PHASE_ORDER[ref.phase],
                ref.agent_id,
                ref.role,
            ),
        )
    )


def _move_history(state: SessionState) -> Tuple[MoveHistoryRef, ...]:
    log_by_move = {}
    for row in state.task_log:
        if row.move_id is None:
            continue
        if row.move_id in log_by_move:
            raise ContractValidationError(
                f"accepted move {row.move_id!r} has duplicate task-log entries"
            )
        log_by_move[row.move_id] = row

    refs = []
    for move in state.moves:
        row = log_by_move.get(move.move_id)
        if row is None:
            raise ContractValidationError(
                f"accepted move {move.move_id!r} has no task-log record"
            )
        if row.provider_status is not ProviderStatus.OK:
            raise ContractValidationError(
                f"accepted move {move.move_id!r} is not provider-OK in task log"
            )
        if (
            row.phase is not move.phase
            or row.agent_id != move.agent_id
            or row.assigned_role is not move.role
            or row.task_kind is not move.task_kind
            or row.slot_index != move.slot_index
            or row.attempt_index != move.attempt_index
        ):
            raise ContractValidationError(
                f"accepted move {move.move_id!r} conflicts with its task-log record"
            )
        semantic = {
            "content": move.content,
            "confidence": move.confidence,
            "epistemic_markers": [marker.value for marker in move.epistemic_markers],
        }
        refs.append(
            MoveHistoryRef(
                move_id=move.move_id,
                semantic_digest=_digest(semantic),
                phase=move.phase.value,
                round_index=row.round_index,
                agent_id=move.agent_id,
                role=move.role.value,
                task_kind=move.task_kind.value if move.task_kind else None,
                slot_index=move.slot_index,
                attempt_index=move.attempt_index,
            )
        )
    return tuple(
        sorted(
            refs,
            key=lambda ref: (
                ref.round_index,
                _PHASE_ORDER[ref.phase],
                ref.slot_index,
                ref.attempt_index,
                ref.move_id,
            ),
        )
    )


def _commitment_refs(
    commitments: Sequence[CommitmentRecord],
) -> Tuple[SemanticArtifactRef, ...]:
    return tuple(
        _artifact(
            record.commitment_id,
            {
                "claim": record.claim,
                "status": record.status.value,
                "target_commitment_id": record.target_commitment_id,
                "model_id": record.model_id,
                "authority": record.authority,
            },
        )
        for record in live_commitments(commitments)
        if record.is_authoritative and record.claim.strip()
    )


def _hybrid_projection(hybrid: Optional[HybridEpistemicState]):
    if hybrid is None:
        return (), (), (), (), (), None

    claims = tuple(
        _artifact(
            claim.claim_id,
            {
                "text": claim.text,
                "author_agent_id": claim.author_agent_id,
                "section": claim.section,
                "verification_class": claim.verification_class.value,
                "superseded_by": claim.superseded_by,
            },
        )
        for claim in sorted(hybrid.claims.values(), key=lambda item: item.claim_id)
        if claim.superseded_by is None
    )
    evidence = tuple(
        _artifact(
            record.evidence_id,
            {
                "claim_id": record.claim_id,
                "stance": record.stance.value,
                "source_type": record.source_type.value,
                "source_identity": record.source_identity,
                "content": record.content,
                "citation": record.citation,
                "receipt_ref": record.receipt_ref,
                "provenance": record.provenance,
            },
        )
        for record in sorted(
            hybrid.evidence.values(), key=lambda item: item.evidence_id
        )
        if record.admissible
    )
    contradictions = tuple(
        _artifact(
            record.contradiction_id,
            {
                "claim_id_a": record.claim_id_a,
                "claim_id_b": record.claim_id_b,
                "state": record.state.value,
                "verification_id": record.verification_id,
            },
        )
        for record in sorted(
            hybrid.contradictions.values(), key=lambda item: item.contradiction_id
        )
        if record.state is not ContradictionState.DISMISSED
    )
    objections = tuple(
        _artifact(
            record.objection_id,
            {
                "target_claim_id": record.target_claim_id,
                "text": record.text,
                "state": record.state.value,
                "scope": record.scope.value,
                "verification_id": record.verification_id,
                "target_provenance": record.target_provenance.value,
            },
        )
        for record in sorted(
            hybrid.objections.values(), key=lambda item: item.objection_id
        )
        if record.state in _UNRESOLVED_OBJECTION_STATES
    )
    verifications = tuple(
        ObservationRef(
            record_id=record.verification_id,
            semantic_digest=_digest(
                record.model_dump(
                    mode="json",
                    exclude={"verifier_provider_id", "verifier_model_id"},
                )
            ),
            provider_id=record.verifier_provider_id,
            model_id=record.verifier_model_id,
        )
        for record in sorted(
            hybrid.verifications.values(), key=lambda item: item.verification_id
        )
    )
    graph_payload = {
        "claims": [item.identity_payload() for item in claims],
        "evidence": [item.identity_payload() for item in evidence],
        "contradictions": [item.identity_payload() for item in contradictions],
        "unresolved_objections": [item.identity_payload() for item in objections],
        "verifications": [item.identity_payload() for item in verifications],
    }
    graph_ref = _artifact("hybrid_governing_state", graph_payload)
    return claims, evidence, contradictions, objections, verifications, graph_ref


def _aporia_refs(records: Sequence[AporiaRecord]) -> Tuple[SemanticArtifactRef, ...]:
    return tuple(
        _artifact(record.aporia_id, record.to_dict())
        for record in records
        if record.remaining_question.strip()
    )


def _move_artifacts(
    state: SessionState, phase: DialogPhase
) -> Tuple[SemanticArtifactRef, ...]:
    return tuple(
        _artifact(move.move_id, move.content)
        for move in state.moves_for_phase(phase)
    )


def project_search_state(
    state: SessionState,
    task: Optional[CanonicalTaskSpec],
    *,
    budget: SearchBudget,
    budget_usage: Optional[BudgetUsage] = None,
    commitments: Sequence[CommitmentRecord] = (),
    aporia_records: Sequence[AporiaRecord] = (),
    hybrid_state: Optional[HybridEpistemicState] = None,
    depth: int = 0,
) -> SearchState:
    """Project recorded public state; never mutate or infer missing records."""
    usage = budget_usage or BudgetUsage()
    _validate_source(state, task, commitments, aporia_records, hybrid_state)
    move_history = _move_history(state)
    hybrid_claims, evidence, contradictions, objections, verifications, graph = (
        _hybrid_projection(hybrid_state)
    )
    active_claims = _commitment_refs(commitments) + hybrid_claims
    unresolved = _aporia_refs(aporia_records) + objections
    terminal = _terminal_status(state, budget, usage)

    return SearchState(
        session_id=state.session_id,
        task_kind=task.task_kind.value if task is not None else "terminal",
        question=state.question,
        phase=task.phase.value if task is not None else state.phase.value,
        round_number=task.round_number if task is not None else state.round_number,
        active_agent_id=task.agent_id if task is not None else None,
        active_role=task.role.value if task is not None else None,
        active_slot_index=task.slot_index if task is not None else 0,
        active_attempt_index=0,
        active_claims=active_claims,
        evidence=evidence,
        contradictions=contradictions,
        unresolved_questions=unresolved,
        candidate_hypotheses=_move_artifacts(state, DialogPhase.RECONSTRUCTION),
        candidate_answers=_move_artifacts(state, DialogPhase.SYNTHESIS),
        role_history=_role_history(state),
        move_history=move_history,
        provider_receipts=(),
        verification_results=verifications,
        epistemic_graph_ref=graph,
        budget=budget,
        budget_usage=usage,
        depth=depth,
        terminal_status=terminal,
    )


__all__ = ["SEARCH_STATE_PROJECTION_VERSION", "project_search_state"]

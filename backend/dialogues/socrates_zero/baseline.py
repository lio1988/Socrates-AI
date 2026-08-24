"""Explicit adapter for the unchanged canonical fixed-rotation baseline."""

from __future__ import annotations

from typing import Optional, Tuple

from ..ced import CEDOrchestrator, CanonicalTaskSpec
from ..models import DialogPhase, SessionState, TaskKind
from .contracts import (
    ActionKind,
    ActionStatistics,
    ContractValidationError,
    LegalAction,
    SearchBudget,
    SearchConstitution,
    SearchReceipt,
    SearchResult,
    SearchState,
    SearchTerminationReason,
    TerminalStatus,
)


class FixedRotationBaselineAdapter:
    """Read-only view of decisions owned by ``CEDOrchestrator``.

    The adapter contains no rotation table and performs no scheduling.  It
    delegates to the extraction point consumed by canonical registry execution.
    """

    def __init__(self, orchestrator: CEDOrchestrator) -> None:
        self._orchestrator = orchestrator

    def task_specs(
        self,
        state: SessionState,
        phase: DialogPhase,
        round_index: Optional[int] = None,
    ) -> Tuple[CanonicalTaskSpec, ...]:
        return self._orchestrator.canonical_registry_task_specs(
            state, phase, round_index
        )


class FixedRotationBaselineStrategy:
    """Handcrafted baseline expressed through the search strategy contract.

    It observes CED's already-selected task kind and chooses the matching hard
    legal macro-action.  It never calls a generator, prior, value estimator, or
    provider and never executes the selected action.
    """

    name = "fixed_rotation_baseline"
    version = "v0"

    _ACTION_BY_TASK = {
        TaskKind.SOCRATIC_QUESTION.value: ActionKind.ASK_SOCRATIC_QUESTION,
        TaskKind.INITIAL_RESPONSE.value: ActionKind.PROPOSE_CLAIM,
        TaskKind.ELENCHUS_OBJECTION.value: ActionKind.RUN_ELENCHUS,
        TaskKind.REFLECTION_REVISION.value: ActionKind.REFLECT,
        TaskKind.RECONSTRUCTION_PROPOSAL.value: ActionKind.RECONSTRUCT,
        TaskKind.SYNTHESIS_DRAFT.value: ActionKind.SYNTHESIZE_FINAL,
        TaskKind.COUNCIL_RATIFICATION.value: ActionKind.RATIFY,
        TaskKind.RATIFICATION_INITIAL.value: ActionKind.RATIFY,
        TaskKind.RATIFICATION_REVISION.value: ActionKind.RATIFY,
        TaskKind.RATIFICATION_FINAL.value: ActionKind.RATIFY,
    }

    @classmethod
    def expected_action_kind(cls, state: SearchState) -> ActionKind:
        if state.terminal_status is not TerminalStatus.NON_TERMINAL:
            return ActionKind.STOP
        try:
            return cls._ACTION_BY_TASK[state.task_kind]
        except KeyError as exc:
            raise ContractValidationError(
                f"unsupported canonical baseline task kind {state.task_kind!r}"
            ) from exc

    async def search(
        self,
        initial_state: SearchState,
        *,
        constitution: SearchConstitution,
        action_generator,
        policy_prior,
        value_estimator,
        budget: SearchBudget,
    ) -> SearchResult:
        if budget != initial_state.budget:
            raise ContractValidationError(
                "baseline budget must equal the projected state's hard budget"
            )
        budget.enforce(initial_state.budget_usage)

        legal = tuple(constitution.legal_actions(initial_state))
        legal_ids = tuple(action.action_id for action in legal)
        if len(set(legal_ids)) != len(legal_ids):
            raise ContractValidationError("hard legal actions contain duplicate IDs")

        expected = self.expected_action_kind(initial_state)
        candidates = tuple(
            action
            for action in legal
            if action.kind is expected and action.target_id is None
        )
        if len(candidates) != 1:
            raise ContractValidationError(
                "canonical baseline action is absent or ambiguous in hard legal actions"
            )
        selected = candidates[0]
        constitution.validate_action(initial_state, selected)

        termination = (
            SearchTerminationReason.TERMINAL_STATE
            if expected is ActionKind.STOP
            else SearchTerminationReason.BASELINE_SELECTED
        )
        receipt = SearchReceipt(
            strategy_name=self.name,
            strategy_version=self.version,
            initial_state_id=initial_state.state_id,
            selected_action_id=selected.action_id,
            expanded_action_ids=tuple(sorted(legal_ids)),
            budget=budget,
            usage=initial_state.budget_usage,
            termination_reason=termination,
        )
        return SearchResult(
            initial_state_id=initial_state.state_id,
            selected_action=selected,
            estimated_value=0.0,
            action_statistics=(
                ActionStatistics(
                    action_id=selected.action_id,
                    prior=1.0,
                    visit_count=1,
                    mean_value=0.0,
                ),
            ),
            receipt=receipt,
        )


__all__ = [
    "FixedRotationBaselineAdapter",
    "FixedRotationBaselineStrategy",
]

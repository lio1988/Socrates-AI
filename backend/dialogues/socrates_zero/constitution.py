"""Deterministic hard legal-action surface for the canonical CED protocol."""

from __future__ import annotations

from typing import Sequence, Tuple

from ..models import DialogPhase, TaskKind
from .contracts import (
    ActionKind,
    ActionTargetKind,
    ContractValidationError,
    LegalAction,
    SearchState,
    TerminalStatus,
    canonical_json,
    validate_action_references,
)


LEGAL_ACTION_VOCABULARY_VERSION = "ced-legal-action-vocabulary/v0"
LEGAL_ACTION_GENERATOR_VERSION = "ced-deterministic-legal-action-generator/v0"


class CEDSearchConstitution:
    """Generate legality only; no ranking, quality judgment, or execution."""

    version = "ced-search-constitution/v0"
    action_vocabulary_version = LEGAL_ACTION_VOCABULARY_VERSION

    _PHASES_BY_TASK = {
        TaskKind.SOCRATIC_QUESTION.value: {
            DialogPhase.OPENING.value,
            DialogPhase.ELENCHUS.value,
        },
        TaskKind.INITIAL_RESPONSE.value: {DialogPhase.INITIAL_RESPONSE.value},
        TaskKind.ELENCHUS_OBJECTION.value: {DialogPhase.ELENCHUS.value},
        TaskKind.REFLECTION_REVISION.value: {DialogPhase.REFLECTION.value},
        TaskKind.RECONSTRUCTION_PROPOSAL.value: {
            DialogPhase.RECONSTRUCTION.value
        },
        TaskKind.SYNTHESIS_DRAFT.value: {DialogPhase.SYNTHESIS.value},
        TaskKind.COUNCIL_RATIFICATION.value: {DialogPhase.RATIFICATION.value},
        TaskKind.RATIFICATION_INITIAL.value: {DialogPhase.RATIFICATION.value},
        TaskKind.RATIFICATION_REVISION.value: {DialogPhase.RATIFICATION.value},
        TaskKind.RATIFICATION_FINAL.value: {DialogPhase.RATIFICATION.value},
    }

    def __init__(self, *, max_socratic_followups: int = 2) -> None:
        if max_socratic_followups < 0:
            raise ValueError("max_socratic_followups must be non-negative")
        self.max_socratic_followups = max_socratic_followups

    @staticmethod
    def action_order_key(action: LegalAction) -> Tuple[str, str, str, str, str]:
        """Canonical replay order: type, target type/id, parameters, capability."""
        return (
            action.kind.value,
            action.target_kind.value if action.target_kind else "",
            action.target_id or "",
            canonical_json(
                [parameter.model_dump(mode="json") for parameter in action.parameters]
            ),
            canonical_json(list(action.required_capabilities)),
        )

    @staticmethod
    def _moves(
        state: SearchState,
        task_kind: TaskKind,
        *,
        phase: DialogPhase | None = None,
        round_index: int | None = None,
    ):
        return tuple(
            move
            for move in state.move_history
            if move.task_kind == task_kind.value
            and (phase is None or move.phase == phase.value)
            and (round_index is None or move.round_index == round_index)
        )

    def _socratic_question_is_legal(self, state: SearchState) -> bool:
        if state.phase == DialogPhase.OPENING.value:
            return not self._moves(
                state,
                TaskKind.SOCRATIC_QUESTION,
                phase=DialogPhase.OPENING,
            )
        if state.phase != DialogPhase.ELENCHUS.value:
            return False
        if not self._moves(state, TaskKind.INITIAL_RESPONSE):
            return False
        followups = self._moves(
            state,
            TaskKind.SOCRATIC_QUESTION,
            phase=DialogPhase.ELENCHUS,
        )
        if len(followups) >= self.max_socratic_followups:
            return False
        return not any(
            move.round_index == state.round_number for move in followups
        )

    def _reflection_is_legal(self, state: SearchState) -> bool:
        return bool(
            self._moves(
                state,
                TaskKind.SOCRATIC_QUESTION,
                phase=DialogPhase.ELENCHUS,
                round_index=state.round_number,
            )
        )

    def _actions_for_nonterminal(self, state: SearchState) -> Tuple[LegalAction, ...]:
        allowed_phases = self._PHASES_BY_TASK.get(state.task_kind)
        if allowed_phases is None or state.phase not in allowed_phases:
            return ()

        actions = []
        if state.task_kind == TaskKind.SOCRATIC_QUESTION.value:
            if self._socratic_question_is_legal(state):
                actions.append(LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION))
        elif state.task_kind == TaskKind.INITIAL_RESPONSE.value:
            actions.append(LegalAction(kind=ActionKind.PROPOSE_CLAIM))
        elif state.task_kind == TaskKind.ELENCHUS_OBJECTION.value:
            if self._moves(state, TaskKind.INITIAL_RESPONSE):
                actions.append(LegalAction(kind=ActionKind.RUN_ELENCHUS))
                actions.extend(
                    LegalAction(
                        kind=ActionKind.CHALLENGE_CLAIM,
                        target_kind=ActionTargetKind.CLAIM,
                        target_id=claim_id,
                    )
                    for claim_id in state.target_ids(ActionTargetKind.CLAIM)
                )
        elif state.task_kind == TaskKind.REFLECTION_REVISION.value:
            if self._reflection_is_legal(state):
                actions.append(LegalAction(kind=ActionKind.REFLECT))
                actions.extend(
                    LegalAction(
                        kind=ActionKind.DEFEND_CLAIM,
                        target_kind=ActionTargetKind.CLAIM,
                        target_id=claim_id,
                    )
                    for claim_id in state.target_ids(ActionTargetKind.CLAIM)
                )
        elif state.task_kind == TaskKind.RECONSTRUCTION_PROPOSAL.value:
            already_reconstructed = self._moves(
                state, TaskKind.RECONSTRUCTION_PROPOSAL
            )
            if self._moves(state, TaskKind.INITIAL_RESPONSE) and not already_reconstructed:
                actions.append(LegalAction(kind=ActionKind.RECONSTRUCT))
        elif state.task_kind == TaskKind.SYNTHESIS_DRAFT.value:
            if self._moves(state, TaskKind.RECONSTRUCTION_PROPOSAL):
                actions.append(LegalAction(kind=ActionKind.SYNTHESIZE_FINAL))
        elif state.task_kind in {
            TaskKind.COUNCIL_RATIFICATION.value,
            TaskKind.RATIFICATION_INITIAL.value,
            TaskKind.RATIFICATION_REVISION.value,
            TaskKind.RATIFICATION_FINAL.value,
        }:
            if state.candidate_answers:
                actions.append(LegalAction(kind=ActionKind.RATIFY))
        return tuple(actions)

    def legal_actions(self, state: SearchState) -> Tuple[LegalAction, ...]:
        if state.terminal_status is not TerminalStatus.NON_TERMINAL:
            return (LegalAction(kind=ActionKind.STOP),)
        actions = self._actions_for_nonterminal(state)
        ordered = tuple(sorted(actions, key=self.action_order_key))
        if len({action.action_id for action in ordered}) != len(ordered):
            raise ContractValidationError("legal action generation produced duplicates")
        for action in ordered:
            validate_action_references(state, action)
        return ordered

    def validate_action(self, state: SearchState, action: LegalAction) -> None:
        legal = self.legal_actions(state)
        if action.action_id not in {candidate.action_id for candidate in legal}:
            raise ContractValidationError(
                f"action {action.action_id!r} is not legal in state {state.state_id!r}"
            )
        validate_action_references(state, action)


class DeterministicLegalActionGenerator:
    """Bounded, model-free adapter over a CED-owned hard legal set."""

    name = "deterministic_legal_actions"
    version = LEGAL_ACTION_GENERATOR_VERSION

    async def generate(
        self,
        state: SearchState,
        *,
        hard_legal_actions: Sequence[LegalAction],
        limit: int,
    ) -> Tuple[LegalAction, ...]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        ordered = tuple(
            sorted(hard_legal_actions, key=CEDSearchConstitution.action_order_key)
        )
        if len({action.action_id for action in ordered}) != len(ordered):
            raise ContractValidationError("hard legal actions contain duplicate IDs")
        for action in ordered:
            validate_action_references(state, action)
        return ordered[:limit]


__all__ = [
    "LEGAL_ACTION_GENERATOR_VERSION",
    "LEGAL_ACTION_VOCABULARY_VERSION",
    "CEDSearchConstitution",
    "DeterministicLegalActionGenerator",
]

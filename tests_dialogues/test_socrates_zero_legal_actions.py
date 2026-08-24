"""Deterministic CED constitutional legal actions for SocratesZero."""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
from backend.dialogues.socrates_zero import (
    ActionKind,
    ActionTargetKind,
    BudgetUsage,
    CEDSearchConstitution,
    ContractValidationError,
    DeterministicLegalActionGenerator,
    FixedRotationBaselineStrategy,
    MoveHistoryRef,
    SearchBudget,
    SearchState,
    SemanticArtifactRef,
    TerminalStatus,
    validate_action_references,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact(artifact_id: str) -> SemanticArtifactRef:
    return SemanticArtifactRef(
        artifact_id=artifact_id,
        semantic_digest=_digest(artifact_id),
    )


def _move(
    move_id: str,
    phase: DialogPhase,
    kind: TaskKind,
    *,
    round_index: int = 0,
) -> MoveHistoryRef:
    role = {
        TaskKind.SOCRATIC_QUESTION: AgentRole.SOCRATES,
        TaskKind.INITIAL_RESPONSE: AgentRole.SYNTHESIZER,
        TaskKind.ELENCHUS_OBJECTION: AgentRole.ELENCHUS_CRITIC,
        TaskKind.REFLECTION_REVISION: AgentRole.REFLECTOR,
        TaskKind.RECONSTRUCTION_PROPOSAL: AgentRole.MAIEUTIC_RECONSTRUCTOR,
        TaskKind.SYNTHESIS_DRAFT: AgentRole.SYNTHESIZER,
    }[kind]
    return MoveHistoryRef(
        move_id=move_id,
        semantic_digest=_digest(f"content:{move_id}"),
        phase=phase.value,
        round_index=round_index,
        agent_id=f"agent:{move_id}",
        role=role.value,
        task_kind=kind.value,
    )


def _budget() -> SearchBudget:
    return SearchBudget(
        max_nodes=8,
        max_expansions=4,
        max_model_calls=4,
        max_tool_calls=2,
        max_tokens=4000,
        max_cost_microusd=100_000,
        max_wall_time_ms=20_000,
        max_depth=3,
    )


def _state(kind: str, phase: DialogPhase, **overrides) -> SearchState:
    data = {
        "task_kind": kind,
        "question": "Which claim survives examination?",
        "phase": phase.value,
        "round_number": 0,
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=1),
    }
    data.update(overrides)
    return SearchState(**data)


def _kinds(state: SearchState):
    return tuple(action.kind for action in CEDSearchConstitution().legal_actions(state))


def test_opening_and_initial_response_have_only_their_real_macro_action():
    opening = _state(TaskKind.SOCRATIC_QUESTION.value, DialogPhase.OPENING)
    assert _kinds(opening) == (ActionKind.ASK_SOCRATIC_QUESTION,)

    initial = _state(
        TaskKind.INITIAL_RESPONSE.value,
        DialogPhase.INITIAL_RESPONSE,
        move_history=(
            _move("opening", DialogPhase.OPENING, TaskKind.SOCRATIC_QUESTION),
        ),
    )
    assert _kinds(initial) == (ActionKind.PROPOSE_CLAIM,)


def test_elenchus_actions_are_stable_targeted_valid_and_duplicate_free():
    state = _state(
        TaskKind.ELENCHUS_OBJECTION.value,
        DialogPhase.ELENCHUS,
        active_claims=(_artifact("claim_z"), _artifact("claim_a")),
        move_history=(
            _move("initial", DialogPhase.INITIAL_RESPONSE, TaskKind.INITIAL_RESPONSE),
        ),
    )
    constitution = CEDSearchConstitution()
    actions = constitution.legal_actions(state)

    assert tuple(action.action_id for action in actions) == tuple(
        sorted(
            (action.action_id for action in actions),
            key=lambda action_id: next(
                constitution.action_order_key(action)
                for action in actions
                if action.action_id == action_id
            ),
        )
    )
    assert {action.kind for action in actions} == {
        ActionKind.CHALLENGE_CLAIM,
        ActionKind.RUN_ELENCHUS,
    }
    targeted = [action for action in actions if action.target_id is not None]
    assert [action.target_id for action in targeted] == ["claim_a", "claim_z"]
    assert len({action.action_id for action in actions}) == len(actions)
    for action in actions:
        validate_action_references(state, action)
        constitution.validate_action(state, action)

    reordered = _state(
        TaskKind.ELENCHUS_OBJECTION.value,
        DialogPhase.ELENCHUS,
        active_claims=tuple(reversed(state.active_claims)),
        move_history=state.move_history,
    )
    assert constitution.legal_actions(reordered) == actions


def test_socratic_followup_limit_and_same_cycle_uniqueness_are_hard_gates():
    initial = _move("initial", DialogPhase.INITIAL_RESPONSE, TaskKind.INITIAL_RESPONSE)
    opening = _move("opening", DialogPhase.OPENING, TaskKind.SOCRATIC_QUESTION)
    allowed = _state(
        TaskKind.SOCRATIC_QUESTION.value,
        DialogPhase.ELENCHUS,
        round_number=1,
        move_history=(opening, initial),
    )
    assert _kinds(allowed) == (ActionKind.ASK_SOCRATIC_QUESTION,)

    same_cycle = _state(
        TaskKind.SOCRATIC_QUESTION.value,
        DialogPhase.ELENCHUS,
        round_number=1,
        move_history=(
            opening,
            initial,
            _move(
                "followup_current",
                DialogPhase.ELENCHUS,
                TaskKind.SOCRATIC_QUESTION,
                round_index=1,
            ),
        ),
    )
    assert CEDSearchConstitution().legal_actions(same_cycle) == ()

    exhausted = _state(
        TaskKind.SOCRATIC_QUESTION.value,
        DialogPhase.ELENCHUS,
        round_number=2,
        move_history=(
            opening,
            initial,
            _move("followup_0", DialogPhase.ELENCHUS, TaskKind.SOCRATIC_QUESTION),
            _move(
                "followup_1",
                DialogPhase.ELENCHUS,
                TaskKind.SOCRATIC_QUESTION,
                round_index=1,
            ),
        ),
    )
    assert CEDSearchConstitution(max_socratic_followups=2).legal_actions(exhausted) == ()


def test_reflection_requires_an_accepted_same_cycle_socratic_question():
    initial = _move("initial", DialogPhase.INITIAL_RESPONSE, TaskKind.INITIAL_RESPONSE)
    denied = _state(
        TaskKind.REFLECTION_REVISION.value,
        DialogPhase.REFLECTION,
        round_number=1,
        active_claims=(_artifact("claim_a"),),
        move_history=(initial,),
    )
    assert CEDSearchConstitution().legal_actions(denied) == ()

    allowed = _state(
        TaskKind.REFLECTION_REVISION.value,
        DialogPhase.REFLECTION,
        round_number=1,
        active_claims=denied.active_claims,
        move_history=(
            initial,
            _move(
                "followup",
                DialogPhase.ELENCHUS,
                TaskKind.SOCRATIC_QUESTION,
                round_index=1,
            ),
        ),
    )
    assert set(_kinds(allowed)) == {ActionKind.DEFEND_CLAIM, ActionKind.REFLECT}


def test_reconstruction_is_single_use_and_synthesis_requires_it():
    initial = _move("initial", DialogPhase.INITIAL_RESPONSE, TaskKind.INITIAL_RESPONSE)
    reconstruct = _state(
        TaskKind.RECONSTRUCTION_PROPOSAL.value,
        DialogPhase.RECONSTRUCTION,
        move_history=(initial,),
    )
    assert _kinds(reconstruct) == (ActionKind.RECONSTRUCT,)

    reconstructed_move = _move(
        "reconstructed",
        DialogPhase.RECONSTRUCTION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
    )
    repeated = _state(
        TaskKind.RECONSTRUCTION_PROPOSAL.value,
        DialogPhase.RECONSTRUCTION,
        move_history=(initial, reconstructed_move),
    )
    assert CEDSearchConstitution().legal_actions(repeated) == ()

    synthesis = _state(
        TaskKind.SYNTHESIS_DRAFT.value,
        DialogPhase.SYNTHESIS,
        move_history=(initial, reconstructed_move),
    )
    assert _kinds(synthesis) == (ActionKind.SYNTHESIZE_FINAL,)
    missing = _state(
        TaskKind.SYNTHESIS_DRAFT.value,
        DialogPhase.SYNTHESIS,
        move_history=(initial,),
    )
    assert CEDSearchConstitution().legal_actions(missing) == ()


def test_ratification_requires_a_candidate_answer_and_stop_is_terminal_only():
    denied = _state(TaskKind.COUNCIL_RATIFICATION.value, DialogPhase.RATIFICATION)
    assert CEDSearchConstitution().legal_actions(denied) == ()
    allowed = _state(
        TaskKind.COUNCIL_RATIFICATION.value,
        DialogPhase.RATIFICATION,
        candidate_answers=(_artifact("answer_a"),),
    )
    assert _kinds(allowed) == (ActionKind.RATIFY,)
    assert ActionKind.STOP not in _kinds(allowed)

    for status in (
        TerminalStatus.ANSWER_READY,
        TerminalStatus.BLOCKED,
        TerminalStatus.BUDGET_EXHAUSTED,
    ):
        terminal = _state(
            "terminal",
            DialogPhase.COMPLETE,
            terminal_status=status,
        )
        assert _kinds(terminal) == (ActionKind.STOP,)


@pytest.mark.parametrize(
    "kind,wrong_phase",
    [
        (TaskKind.SOCRATIC_QUESTION, DialogPhase.SYNTHESIS),
        (TaskKind.INITIAL_RESPONSE, DialogPhase.REFLECTION),
        (TaskKind.ELENCHUS_OBJECTION, DialogPhase.OPENING),
        (TaskKind.REFLECTION_REVISION, DialogPhase.ELENCHUS),
        (TaskKind.RECONSTRUCTION_PROPOSAL, DialogPhase.RATIFICATION),
        (TaskKind.SYNTHESIS_DRAFT, DialogPhase.RECONSTRUCTION),
        (TaskKind.COUNCIL_RATIFICATION, DialogPhase.SYNTHESIS),
    ],
)
def test_task_phase_mismatch_fails_closed_with_no_actions(kind, wrong_phase):
    state = _state(kind.value, wrong_phase)
    assert CEDSearchConstitution().legal_actions(state) == ()


def test_deterministic_generator_returns_only_the_bounded_hard_legal_subset():
    state = _state(
        TaskKind.ELENCHUS_OBJECTION.value,
        DialogPhase.ELENCHUS,
        active_claims=(_artifact("claim_b"), _artifact("claim_a")),
        move_history=(
            _move("initial", DialogPhase.INITIAL_RESPONSE, TaskKind.INITIAL_RESPONSE),
        ),
    )
    hard = CEDSearchConstitution().legal_actions(state)
    generator = DeterministicLegalActionGenerator()
    generated = asyncio.run(
        generator.generate(state, hard_legal_actions=tuple(reversed(hard)), limit=2)
    )
    assert generated == hard[:2]
    assert set(generated) <= set(hard)
    assert asyncio.run(
        generator.generate(state, hard_legal_actions=hard, limit=0)
    ) == ()


def _representative_states():
    opening = _move("opening", DialogPhase.OPENING, TaskKind.SOCRATIC_QUESTION)
    initial = _move("initial", DialogPhase.INITIAL_RESPONSE, TaskKind.INITIAL_RESPONSE)
    followup = _move("followup", DialogPhase.ELENCHUS, TaskKind.SOCRATIC_QUESTION)
    reconstruction = _move(
        "reconstruction",
        DialogPhase.RECONSTRUCTION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
    )
    claim = (_artifact("claim_a"),)
    return (
        _state(TaskKind.SOCRATIC_QUESTION.value, DialogPhase.OPENING),
        _state(
            TaskKind.INITIAL_RESPONSE.value,
            DialogPhase.INITIAL_RESPONSE,
            move_history=(opening,),
        ),
        _state(
            TaskKind.ELENCHUS_OBJECTION.value,
            DialogPhase.ELENCHUS,
            active_claims=claim,
            move_history=(opening, initial),
        ),
        _state(
            TaskKind.SOCRATIC_QUESTION.value,
            DialogPhase.ELENCHUS,
            active_claims=claim,
            move_history=(opening, initial),
        ),
        _state(
            TaskKind.REFLECTION_REVISION.value,
            DialogPhase.REFLECTION,
            active_claims=claim,
            move_history=(opening, initial, followup),
        ),
        _state(
            TaskKind.RECONSTRUCTION_PROPOSAL.value,
            DialogPhase.RECONSTRUCTION,
            move_history=(opening, initial, followup),
        ),
        _state(
            TaskKind.SYNTHESIS_DRAFT.value,
            DialogPhase.SYNTHESIS,
            move_history=(opening, initial, followup, reconstruction),
        ),
        _state(
            TaskKind.COUNCIL_RATIFICATION.value,
            DialogPhase.RATIFICATION,
            candidate_answers=(_artifact("answer_a"),),
        ),
    )


def test_fixed_baseline_action_is_always_in_the_hard_legal_set():
    constitution = CEDSearchConstitution()
    for state in _representative_states():
        legal = constitution.legal_actions(state)
        expected = FixedRotationBaselineStrategy.expected_action_kind(state)
        matching = [
            action
            for action in legal
            if action.kind is expected and action.target_id is None
        ]
        assert len(matching) == 1
        constitution.validate_action(state, matching[0])


def test_validate_action_rejects_a_structurally_valid_but_currently_illegal_move():
    state = _state(TaskKind.SOCRATIC_QUESTION.value, DialogPhase.OPENING)
    illegal = next(
        action
        for action in CEDSearchConstitution().legal_actions(
            _state(
                TaskKind.ELENCHUS_OBJECTION.value,
                DialogPhase.ELENCHUS,
                active_claims=(_artifact("claim_a"),),
                move_history=(
                    _move(
                        "initial",
                        DialogPhase.INITIAL_RESPONSE,
                        TaskKind.INITIAL_RESPONSE,
                    ),
                ),
            )
        )
        if action.kind is ActionKind.CHALLENGE_CLAIM
    )
    with pytest.raises(ContractValidationError, match="not legal"):
        CEDSearchConstitution().validate_action(state, illegal)

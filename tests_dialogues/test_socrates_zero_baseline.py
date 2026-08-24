"""Fixed-rotation baseline adapter over the canonical CED task planner."""

from __future__ import annotations

import asyncio

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import AgentMove, AgentRole, DialogPhase, TaskKind
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socrates_zero import (
    ActionKind,
    BudgetUsage,
    CEDSearchConstitution,
    ContractValidationError,
    FixedRotationBaselineAdapter,
    FixedRotationBaselineStrategy,
    LegalAction,
    SearchBudget,
    SearchState,
    SearchStrategy,
    TerminalStatus,
    project_search_state,
)


def _budget() -> SearchBudget:
    return SearchBudget(
        max_nodes=1,
        max_expansions=0,
        max_model_calls=0,
        max_tool_calls=0,
        max_tokens=0,
        max_cost_microusd=0,
        max_wall_time_ms=0,
        max_depth=0,
    )


def _search_state(task_kind: TaskKind, phase: DialogPhase) -> SearchState:
    return SearchState(
        task_kind=task_kind.value,
        question="What survives examination?",
        phase=phase.value,
        budget=_budget(),
        budget_usage=BudgetUsage(nodes=1),
    )


def _ced() -> CEDOrchestrator:
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(ScriptedMockProvider(f"seat{index}"))
    return CEDOrchestrator(
        [SocraticAgent(f"agent_{index}", provider) for index in range(4)],
        provider,
        registry=registry,
    )


class _StaticConstitution:
    def __init__(self, actions):
        self.actions = tuple(actions)

    def legal_actions(self, state):
        return self.actions

    def validate_action(self, state, action):
        if action not in self.actions:
            raise ContractValidationError("not legal")


class _Unused:
    async def generate(self, *args, **kwargs):
        raise AssertionError("fixed baseline must not call an action generator")

    async def priors(self, *args, **kwargs):
        raise AssertionError("fixed baseline must not call a policy prior")

    async def estimate(self, *args, **kwargs):
        raise AssertionError("fixed baseline must not call a value estimator")


@pytest.mark.parametrize(
    "phase,expected",
    [
        (DialogPhase.OPENING, ((AgentRole.SOCRATES, TaskKind.SOCRATIC_QUESTION),)),
        (
            DialogPhase.INITIAL_RESPONSE,
            (
                (AgentRole.ELENCHUS_CRITIC, TaskKind.INITIAL_RESPONSE),
                (AgentRole.EMPIRICIST, TaskKind.INITIAL_RESPONSE),
                (AgentRole.SYNTHESIZER, TaskKind.INITIAL_RESPONSE),
            ),
        ),
        (
            DialogPhase.ELENCHUS,
            (
                (AgentRole.ELENCHUS_CRITIC, TaskKind.ELENCHUS_OBJECTION),
                (AgentRole.EMPIRICIST, TaskKind.ELENCHUS_OBJECTION),
                (AgentRole.SOCRATES, TaskKind.SOCRATIC_QUESTION),
            ),
        ),
        (
            DialogPhase.RECONSTRUCTION,
            ((AgentRole.MAIEUTIC_RECONSTRUCTOR, TaskKind.RECONSTRUCTION_PROPOSAL),),
        ),
    ],
)
def test_adapter_delegates_to_canonical_rotation_without_mutating_state(phase, expected):
    ced = _ced()
    state = ced.create_session("What survives examination?", session_id="baseline")
    before = state.model_dump(mode="json")

    specs = FixedRotationBaselineAdapter(ced).task_specs(state, phase)
    assignment = ced.assign_roles_for_phase(state, phase, state.round_number)

    assert {(spec.agent_id, spec.role) for spec in specs} == set(assignment.items())
    assert tuple(sorted((spec.role, spec.task_kind) for spec in specs)) == tuple(
        sorted(expected)
    )
    assert [spec.slot_index for spec in specs] == list(range(len(specs)))
    assert state.model_dump(mode="json") == before


def test_reflection_specs_are_exactly_the_initial_responders():
    ced = _ced()
    state = ced.create_session("q", session_id="reflection-baseline")
    initial = ced.canonical_registry_task_specs(state, DialogPhase.INITIAL_RESPONSE)
    for spec in initial:
        state.moves.append(
            AgentMove(
                move_id=f"move_{spec.slot_index}",
                task_id=f"task_{spec.slot_index}",
                agent_id=spec.agent_id,
                role=spec.role,
                phase=DialogPhase.INITIAL_RESPONSE,
                content={"commitments": [f"claim {spec.slot_index}"]},
                task_kind=TaskKind.INITIAL_RESPONSE,
                slot_index=spec.slot_index,
            )
        )

    reflected = FixedRotationBaselineAdapter(ced).task_specs(
        state, DialogPhase.REFLECTION
    )
    assert {spec.agent_id for spec in reflected} == {
        move.agent_id for move in state.moves
    }
    assert {spec.role for spec in reflected} == {AgentRole.REFLECTOR}
    assert {spec.task_kind for spec in reflected} == {TaskKind.REFLECTION_REVISION}


def test_adapter_specs_equal_the_tasks_canonical_execution_dispatches():
    ced = _ced()
    state = ced.create_session("What survives examination?", session_id="dispatch")
    adapter = FixedRotationBaselineAdapter(ced)

    async def exercise():
        for phase in (
            DialogPhase.OPENING,
            DialogPhase.INITIAL_RESPONSE,
            DialogPhase.ELENCHUS,
            DialogPhase.REFLECTION,
            DialogPhase.RECONSTRUCTION,
            DialogPhase.SYNTHESIS,
        ):
            planned = adapter.task_specs(state, phase)
            before = len(state.task_log)
            result = await ced._run_registry_phase(state, phase, None)
            assert result.proceed
            dispatched = state.task_log[before:]
            assert tuple(
                (
                    row.agent_id,
                    row.assigned_role,
                    row.task_kind,
                    row.slot_index,
                    row.round_index,
                )
                for row in dispatched
            ) == tuple(
                (
                    spec.agent_id,
                    spec.role,
                    spec.task_kind,
                    spec.slot_index,
                    spec.round_number,
                )
                for spec in planned
            )

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "kind,phase,action_kind",
    [
        (TaskKind.SOCRATIC_QUESTION, DialogPhase.OPENING, ActionKind.ASK_SOCRATIC_QUESTION),
        (TaskKind.INITIAL_RESPONSE, DialogPhase.INITIAL_RESPONSE, ActionKind.PROPOSE_CLAIM),
        (TaskKind.ELENCHUS_OBJECTION, DialogPhase.ELENCHUS, ActionKind.RUN_ELENCHUS),
        (TaskKind.REFLECTION_REVISION, DialogPhase.REFLECTION, ActionKind.REFLECT),
        (
            TaskKind.RECONSTRUCTION_PROPOSAL,
            DialogPhase.RECONSTRUCTION,
            ActionKind.RECONSTRUCT,
        ),
        (TaskKind.SYNTHESIS_DRAFT, DialogPhase.SYNTHESIS, ActionKind.SYNTHESIZE_FINAL),
        (TaskKind.COUNCIL_RATIFICATION, DialogPhase.RATIFICATION, ActionKind.RATIFY),
    ],
)
def test_fixed_baseline_selects_the_matching_hard_legal_action(kind, phase, action_kind):
    state = _search_state(kind, phase)
    chosen = LegalAction(kind=action_kind)
    other = LegalAction(kind=ActionKind.STOP)
    strategy = FixedRotationBaselineStrategy()
    assert isinstance(strategy, SearchStrategy)

    result = asyncio.run(
        strategy.search(
            state,
            constitution=_StaticConstitution((other, chosen)),
            action_generator=_Unused(),
            policy_prior=_Unused(),
            value_estimator=_Unused(),
            budget=state.budget,
        )
    )

    assert result.selected_action == chosen
    assert result.receipt.initial_state_id == state.state_id
    assert result.receipt.selected_action_id == chosen.action_id
    assert result.receipt.expanded_action_ids == tuple(
        sorted((other.action_id, chosen.action_id))
    )


def test_fixed_baseline_fails_closed_when_canonical_action_is_not_legal():
    state = _search_state(TaskKind.REFLECTION_REVISION, DialogPhase.REFLECTION)
    with pytest.raises(ContractValidationError, match="canonical baseline action"):
        asyncio.run(
            FixedRotationBaselineStrategy().search(
                state,
                constitution=_StaticConstitution((LegalAction(kind=ActionKind.STOP),)),
                action_generator=_Unused(),
                policy_prior=_Unused(),
                value_estimator=_Unused(),
                budget=state.budget,
            )
        )


def test_terminal_baseline_selects_stop_only():
    state = _search_state(TaskKind.COUNCIL_RATIFICATION, DialogPhase.COMPLETE).model_copy(
        update={"terminal_status": TerminalStatus.ANSWER_READY}
    )
    state = SearchState(**state.model_dump(exclude={"state_id"}))
    stop = LegalAction(kind=ActionKind.STOP)
    result = asyncio.run(
        FixedRotationBaselineStrategy().search(
            state,
            constitution=_StaticConstitution((stop,)),
            action_generator=_Unused(),
            policy_prior=_Unused(),
            value_estimator=_Unused(),
            budget=state.budget,
        )
    )
    assert result.selected_action == stop


def test_every_real_fixed_rotation_decision_projects_to_a_hard_legal_action():
    ced = _ced()
    state = ced.create_session("What survives examination?", session_id="inside-rules")
    adapter = FixedRotationBaselineAdapter(ced)
    constitution = CEDSearchConstitution(
        max_socratic_followups=ced.max_socratic_followups
    )

    async def exercise():
        for phase in (
            DialogPhase.OPENING,
            DialogPhase.INITIAL_RESPONSE,
            DialogPhase.ELENCHUS,
            DialogPhase.REFLECTION,
            DialogPhase.RECONSTRUCTION,
            DialogPhase.SYNTHESIS,
        ):
            for spec in adapter.task_specs(state, phase):
                projected = project_search_state(
                    state,
                    spec,
                    budget=_budget(),
                    budget_usage=BudgetUsage(nodes=1),
                    commitments=ced.commitment_ledger(state),
                    aporia_records=ced.aporia_records(state),
                )
                legal = constitution.legal_actions(projected)
                expected = FixedRotationBaselineStrategy.expected_action_kind(projected)
                matching = [
                    action
                    for action in legal
                    if action.kind is expected and action.target_id is None
                ]
                assert len(matching) == 1, (phase, spec, legal)
                constitution.validate_action(projected, matching[0])
            result = await ced._run_registry_phase(state, phase, None)
            assert result.proceed

    asyncio.run(exercise())

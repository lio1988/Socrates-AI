"""Deterministic one-step Greedy strategy over the full hard-legal set."""

from __future__ import annotations

import asyncio
import hashlib
import math

import pytest

from backend.dialogues.socrates_zero import (
    GREEDY_STRATEGY_VERSION,
    ActionKind,
    ActionPrior,
    BudgetExceeded,
    BudgetUsage,
    CEDSearchConstitution,
    ContractValidationError,
    DeterministicLegalActionGenerator,
    GreedyStrategy,
    HeuristicPolicyPrior,
    HeuristicValueEstimator,
    LegalAction,
    MoveHistoryRef,
    SearchBudget,
    SearchState,
    SearchStrategy,
    SearchTerminationReason,
    SemanticArtifactRef,
)


def _budget(**updates) -> SearchBudget:
    data = {
        "max_nodes": 4,
        "max_expansions": 4,
        "max_model_calls": 0,
        "max_tool_calls": 0,
        "max_tokens": 0,
        "max_cost_microusd": 0,
        "max_wall_time_ms": 0,
        "max_depth": 1,
    }
    data.update(updates)
    return SearchBudget(**data)


def _state(**updates) -> SearchState:
    data = {
        "task_kind": "elenchus_objection",
        "question": "What survives examination?",
        "phase": "elenchus",
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=1),
    }
    data.update(updates)
    return SearchState(**data)


def _actions() -> tuple[LegalAction, ...]:
    return (
        LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
        LegalAction(kind=ActionKind.REFLECT),
        LegalAction(kind=ActionKind.RUN_ELENCHUS),
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _StaticConstitution:
    def __init__(self, actions) -> None:
        self.actions = tuple(actions)
        self.legal_calls = 0
        self.validated = []

    def legal_actions(self, state):
        self.legal_calls += 1
        return self.actions

    def validate_action(self, state, action):
        if action.action_id not in {candidate.action_id for candidate in self.actions}:
            raise ContractValidationError("not legal")
        self.validated.append(action.action_id)


class _RecordingGenerator:
    def __init__(self, outputs=None) -> None:
        self.outputs = outputs
        self.calls = []

    async def generate(self, state, *, hard_legal_actions, limit):
        hard = tuple(hard_legal_actions)
        self.calls.append((state.state_id, hard, limit))
        if self.outputs is not None:
            return self.outputs
        return tuple(reversed(hard))


class _StaticPolicy:
    def __init__(self, probabilities=None, outputs=None) -> None:
        self.probabilities = probabilities or {}
        self.outputs = outputs
        self.calls = []

    async def priors(self, state, legal_actions):
        actions = tuple(legal_actions)
        self.calls.append((state.state_id, actions))
        if self.outputs is not None:
            return self.outputs
        return tuple(
            ActionPrior(
                action_id=action.action_id,
                probability=self.probabilities[action.action_id],
            )
            for action in reversed(actions)
        )


class _StaticValue:
    def __init__(self, value=0.0) -> None:
        self.value = value
        self.calls = []

    async def estimate(self, state):
        self.calls.append(state.state_id)
        return self.value


class _Unused:
    async def generate(self, *args, **kwargs):
        raise AssertionError("generator must not be called")

    async def priors(self, *args, **kwargs):
        raise AssertionError("policy must not be called")


def _search(
    *,
    state,
    constitution,
    generator,
    policy,
    value,
    budget=None,
):
    return asyncio.run(
        GreedyStrategy().search(
            state,
            constitution=constitution,
            action_generator=generator,
            policy_prior=policy,
            value_estimator=value,
            budget=budget or state.budget,
        )
    )


def test_greedy_implements_canonical_strategy_contract_and_version():
    strategy = GreedyStrategy()

    assert isinstance(strategy, SearchStrategy)
    assert strategy.name == "greedy_strategy"
    assert strategy.version == GREEDY_STRATEGY_VERSION
    assert GREEDY_STRATEGY_VERSION == "greedy-strategy/v0"


def test_greedy_selects_highest_prior_over_every_hard_legal_action_without_q_fabrication():
    state = _state()
    before = state.model_dump(mode="json")
    actions = _actions()
    constitution = _StaticConstitution(tuple(reversed(actions)))
    generator = _RecordingGenerator()
    probabilities = {
        actions[0].action_id: 0.2,
        actions[1].action_id: 0.7,
        actions[2].action_id: 0.1,
    }
    policy = _StaticPolicy(probabilities)
    value = _StaticValue(-0.25)

    result = _search(
        state=state,
        constitution=constitution,
        generator=generator,
        policy=policy,
        value=value,
    )

    assert result.selected_action == actions[1]
    assert result.estimated_value == -0.25
    assert generator.calls == [(state.state_id, tuple(reversed(actions)), 3)]
    assert {action.action_id for action in policy.calls[0][1]} == {
        action.action_id for action in actions
    }
    assert set(constitution.validated) == {action.action_id for action in actions}
    assert value.calls == [state.state_id]
    assert tuple(stat.action_id for stat in result.action_statistics) == tuple(
        sorted(action.action_id for action in actions)
    )
    assert {stat.action_id: stat.prior for stat in result.action_statistics} == probabilities
    assert all(stat.visit_count == 0 for stat in result.action_statistics)
    assert all(stat.mean_value == 0.0 for stat in result.action_statistics)
    assert result.receipt.visited_state_ids == (state.state_id,)
    assert result.receipt.expanded_action_ids == ()
    assert result.receipt.usage == state.budget_usage
    assert result.receipt.termination_reason is SearchTerminationReason.COMPLETED
    assert state.model_dump(mode="json") == before


def test_equal_priors_use_action_id_tie_break_and_are_input_order_invariant():
    state = _state()
    actions = _actions()
    probabilities = {action.action_id: 1.0 / len(actions) for action in actions}

    first = _search(
        state=state,
        constitution=_StaticConstitution(actions),
        generator=_RecordingGenerator(outputs=tuple(reversed(actions))),
        policy=_StaticPolicy(probabilities),
        value=_StaticValue(),
    )
    second = _search(
        state=state,
        constitution=_StaticConstitution(tuple(reversed(actions))),
        generator=_RecordingGenerator(outputs=actions),
        policy=_StaticPolicy(
            outputs=tuple(
                ActionPrior(action_id=action.action_id, probability=1.0 / len(actions))
                for action in actions
            )
        ),
        value=_StaticValue(),
    )

    expected_id = min(action.action_id for action in actions)
    assert first.selected_action.action_id == expected_id
    assert second.selected_action.action_id == expected_id
    assert first == second
    assert first.receipt.receipt_id == second.receipt.receipt_id


def test_no_hard_legal_actions_returns_audited_no_selection_without_generation_or_policy():
    state = _state()
    value = _StaticValue(-0.2)

    result = _search(
        state=state,
        constitution=_StaticConstitution(()),
        generator=_Unused(),
        policy=_Unused(),
        value=value,
    )

    assert result.selected_action is None
    assert result.estimated_value == -0.2
    assert result.action_statistics == ()
    assert result.receipt.selected_action_id is None
    assert result.receipt.termination_reason is SearchTerminationReason.NO_LEGAL_ACTIONS
    assert value.calls == [state.state_id]


def test_terminal_stop_is_selected_but_never_executed():
    state = _state(
        phase="complete",
        terminal_status="answer_ready",
    )
    stop = LegalAction(kind=ActionKind.STOP)

    result = _search(
        state=state,
        constitution=_StaticConstitution((stop,)),
        generator=_RecordingGenerator(),
        policy=_StaticPolicy({stop.action_id: 1.0}),
        value=_StaticValue(),
    )

    assert result.selected_action == stop
    assert result.final_state_id is None
    assert result.receipt.final_state_id is None


def test_real_constitution_generator_policy_and_value_compose_without_runtime_wiring():
    state = _state(
        active_claims=(
            SemanticArtifactRef(
                artifact_id="claim_b",
                semantic_digest=_digest("claim_b"),
            ),
            SemanticArtifactRef(
                artifact_id="claim_a",
                semantic_digest=_digest("claim_a"),
            ),
        ),
        contradictions=(
            SemanticArtifactRef(
                artifact_id="contradiction_a",
                semantic_digest=_digest("contradiction_a"),
            ),
        ),
        move_history=(
            MoveHistoryRef(
                move_id="initial",
                semantic_digest=_digest("initial"),
                phase="initial_response",
                round_index=0,
                agent_id="agent_initial",
                role="synthesizer",
                task_kind="initial_response",
            ),
        ),
    )

    result = _search(
        state=state,
        constitution=CEDSearchConstitution(),
        generator=DeterministicLegalActionGenerator(),
        policy=HeuristicPolicyPrior(),
        value=HeuristicValueEstimator(),
    )

    assert result.selected_action.kind is ActionKind.CHALLENGE_CLAIM
    assert result.selected_action.target_id in {"claim_a", "claim_b"}
    assert result.estimated_value == -0.08
    assert math.fsum(stat.prior for stat in result.action_statistics) == pytest.approx(1.0)
    assert result.receipt.expanded_action_ids == ()


@pytest.mark.parametrize(
    "outputs,match",
    [
        ((LegalAction(kind=ActionKind.REFLECT),), "full hard-legal set"),
        (
            (
                LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
                LegalAction(kind=ActionKind.REFLECT),
                LegalAction(kind=ActionKind.RUN_ELENCHUS),
                LegalAction(kind=ActionKind.STOP),
            ),
            "outside the hard-legal set",
        ),
        (
            (
                LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
                LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
                LegalAction(kind=ActionKind.RUN_ELENCHUS),
            ),
            "duplicate",
        ),
        (("not-an-action",), "LegalAction"),
    ],
)
def test_generator_output_must_be_the_exact_unique_hard_legal_set(outputs, match):
    state = _state()
    actions = _actions()

    with pytest.raises(ContractValidationError, match=match):
        _search(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_RecordingGenerator(outputs=outputs),
            policy=_StaticPolicy(),
            value=_StaticValue(),
        )


@pytest.mark.parametrize("case", ["missing", "unknown", "duplicate", "sum", "nan", "type"])
def test_policy_output_must_be_a_finite_normalized_bijection(case):
    state = _state()
    actions = _actions()
    valid = [
        ActionPrior(action_id=actions[0].action_id, probability=0.2),
        ActionPrior(action_id=actions[1].action_id, probability=0.3),
        ActionPrior(action_id=actions[2].action_id, probability=0.5),
    ]
    if case == "missing":
        outputs = tuple(valid[:-1])
    elif case == "unknown":
        outputs = tuple(valid[:-1]) + (
            ActionPrior(action_id=LegalAction(kind=ActionKind.STOP).action_id, probability=0.5),
        )
    elif case == "duplicate":
        outputs = (valid[0], valid[0], valid[2])
    elif case == "sum":
        outputs = tuple(
            prior.model_copy(update={"probability": prior.probability / 2.0})
            for prior in valid
        )
    elif case == "nan":
        outputs = (
            valid[0].model_copy(update={"probability": math.nan}),
            valid[1],
            valid[2],
        )
    else:
        outputs = ({"action_id": actions[0].action_id, "probability": 1.0},)

    with pytest.raises(ContractValidationError):
        _search(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_RecordingGenerator(outputs=actions),
            policy=_StaticPolicy(outputs=outputs),
            value=_StaticValue(),
        )


def test_budget_must_match_state_and_current_usage_must_be_within_it():
    state = _state()
    actions = _actions()
    common = {
        "constitution": _StaticConstitution(actions),
        "generator": _RecordingGenerator(outputs=actions),
        "policy": _StaticPolicy({action.action_id: 1.0 / len(actions) for action in actions}),
        "value": _StaticValue(),
    }

    with pytest.raises(ContractValidationError, match="budget must equal"):
        _search(state=state, budget=_budget(max_nodes=5), **common)

    over = _state(
        budget=_budget(max_nodes=1),
        budget_usage=BudgetUsage(nodes=2),
        terminal_status="budget_exhausted",
    )
    with pytest.raises(BudgetExceeded):
        _search(state=over, **common)


@pytest.mark.parametrize(
    "state,match",
    [
        (_state(terminal_status="answer_ready"), "must be in complete phase"),
        (_state(phase="complete"), "cannot be non-terminal"),
        (_state().model_copy(update={"state_id": "forged"}), "valid SearchState"),
    ],
)
def test_structurally_invalid_state_fails_before_any_strategy_dependency(state, match):
    with pytest.raises(ContractValidationError, match=match):
        _search(
            state=state,
            constitution=_Unused(),
            generator=_Unused(),
            policy=_Unused(),
            value=_StaticValue(),
        )


@pytest.mark.parametrize(
    "value",
    [math.nan, math.inf, -math.inf, -1.01, 1.01, "0.5", True],
)
def test_root_value_must_be_finite_and_inside_canonical_range(value):
    state = _state()
    actions = _actions()

    with pytest.raises(ContractValidationError, match="value"):
        _search(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_RecordingGenerator(outputs=actions),
            policy=_StaticPolicy({action.action_id: 1.0 / len(actions) for action in actions}),
            value=_StaticValue(value),
        )

"""Budgeted one-ply Best-of-N over explicit successor SearchStates."""

from __future__ import annotations

import asyncio
import hashlib
import math

import pytest

from backend.dialogues.socrates_zero import (
    BEST_OF_N_CANDIDATE_COUNT_V0,
    BEST_OF_N_STRATEGY_VERSION,
    ActionKind,
    ActionPrior,
    ActionStatistics,
    ActionSuccessor,
    BestOfNStrategy,
    BudgetExceeded,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    ObservationRef,
    PolicyContextEntry,
    SearchBudget,
    SearchState,
    SearchStrategy,
    SearchTerminationReason,
    SuccessorStateEvaluator,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _budget(**updates) -> SearchBudget:
    data = {
        "max_nodes": 12,
        "max_expansions": 8,
        "max_model_calls": 8,
        "max_tool_calls": 0,
        "max_tokens": 8000,
        "max_cost_microusd": 80_000,
        "max_wall_time_ms": 8000,
        "max_depth": 1,
    }
    data.update(updates)
    return SearchBudget(**data)


def _state(**updates) -> SearchState:
    data = {
        "task_kind": "elenchus_objection",
        "question": "Which successor is most promising?",
        "phase": "elenchus",
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=1),
    }
    data.update(updates)
    return SearchState(**data)


def _actions() -> tuple[LegalAction, ...]:
    return (
        LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
        LegalAction(kind=ActionKind.PROPOSE_CLAIM),
        LegalAction(kind=ActionKind.RECONSTRUCT),
        LegalAction(kind=ActionKind.REFLECT),
        LegalAction(kind=ActionKind.RUN_ELENCHUS),
    )


class _StaticConstitution:
    def __init__(self, actions) -> None:
        self.actions = tuple(actions)
        self.validated = []

    def legal_actions(self, state):
        return self.actions

    def validate_action(self, state, action):
        if action.action_id not in {candidate.action_id for candidate in self.actions}:
            raise ContractValidationError("not legal")
        self.validated.append(action.action_id)


class _Generator:
    def __init__(self, outputs=None) -> None:
        self.outputs = outputs
        self.calls = []

    async def generate(self, state, *, hard_legal_actions, limit):
        hard = tuple(hard_legal_actions)
        self.calls.append((state.state_id, hard, limit))
        if self.outputs is not None:
            return self.outputs
        return hard[:limit]


class _Policy:
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


class _StateValue:
    def __init__(self, value_by_action, *, root_value=0.0) -> None:
        self.values = {
            _digest(action_id): value
            for action_id, value in value_by_action.items()
        }
        self.root_value = root_value
        self.calls = []

    async def estimate(self, state):
        self.calls.append(state.state_id)
        candidate = next(
            (
                entry
                for entry in state.policy_context
                if entry.name == "candidate_action"
            ),
            None,
        )
        if candidate is None:
            return self.root_value
        return self.values.get(candidate.semantic_digest, self.root_value)


class _Successors:
    def __init__(self, *, transform=None) -> None:
        self.transform = transform
        self.calls = []

    async def evaluate_successor(
        self,
        state,
        action,
        *,
        budget,
        aggregate_usage,
    ):
        self.calls.append((action.action_id, aggregate_usage))
        delta = BudgetUsage(
            nodes=1,
            expansions=1,
            model_calls=1,
            tokens=100,
            cost_microusd=1000,
            wall_time_ms=100,
            max_depth_observed=state.depth + 1,
        )
        data = state.model_dump(mode="python", exclude={"state_id"})
        data.update(
            {
                "parent_state_id": state.state_id,
                "policy_context": (
                    PolicyContextEntry(
                        name="candidate_action",
                        semantic_digest=_digest(action.action_id),
                    ),
                ),
                "provider_receipts": (
                    ObservationRef(
                        record_id=f"provider:{action.action_id}",
                        semantic_digest=_digest(f"observation:{action.action_id}"),
                    ),
                ),
                "budget_usage": state.budget_usage.plus(delta),
                "depth": state.depth + 1,
            }
        )
        successor_state = SearchState(**data)
        result = ActionSuccessor(
            action_id=action.action_id,
            state=successor_state,
            usage_delta=delta,
        )
        if self.transform is not None:
            return self.transform(result)
        return result


class _Unused:
    def legal_actions(self, *args, **kwargs):
        raise AssertionError("constitution must not be called")

    def validate_action(self, *args, **kwargs):
        raise AssertionError("constitution must not validate")

    async def generate(self, *args, **kwargs):
        raise AssertionError("generator must not be called")

    async def priors(self, *args, **kwargs):
        raise AssertionError("policy must not be called")

    async def evaluate_successor(self, *args, **kwargs):
        raise AssertionError("successor evaluator must not be called")


def _run(
    *,
    state,
    constitution,
    generator,
    policy,
    value,
    successors,
    budget=None,
):
    return asyncio.run(
        BestOfNStrategy(successors).search(
            state,
            constitution=constitution,
            action_generator=generator,
            policy_prior=policy,
            value_estimator=value,
            budget=budget or state.budget,
        )
    )


def test_successor_and_best_of_n_use_explicit_canonical_contracts_and_versions():
    state = _state()
    action = _actions()[0]
    delta = BudgetUsage(nodes=1, expansions=1, max_depth_observed=1)
    data = state.model_dump(mode="python", exclude={"state_id"})
    data.update(
        parent_state_id=state.state_id,
        depth=1,
        budget_usage=state.budget_usage.plus(delta),
    )
    evaluator = _Successors()
    successor = ActionSuccessor(
        action_id=action.action_id,
        state=SearchState(**data),
        usage_delta=delta,
    )
    strategy = BestOfNStrategy(evaluator)

    assert successor.action_id == action.action_id
    assert isinstance(evaluator, SuccessorStateEvaluator)
    assert isinstance(strategy, SearchStrategy)
    assert strategy.name == "best_of_n_strategy"
    assert strategy.version == BEST_OF_N_STRATEGY_VERSION
    assert BEST_OF_N_STRATEGY_VERSION == "best-of-n-strategy/v0"
    assert BEST_OF_N_CANDIDATE_COUNT_V0 == 4
    assert strategy.candidate_count == 4
    statistic = ActionStatistics(
        action_id=action.action_id,
        prior=1.0,
        visit_count=1,
        mean_value=0.0,
    )
    assert statistic.action_id == action.action_id


def test_best_of_n_selects_highest_successor_value_and_records_exact_aggregate_usage():
    state = _state()
    before = state.model_dump(mode="json")
    actions = _actions()
    candidates = actions[:4]
    probabilities = {
        candidates[0].action_id: 0.1,
        candidates[1].action_id: 0.2,
        candidates[2].action_id: 0.3,
        candidates[3].action_id: 0.4,
    }
    value_by_action = {
        candidates[0].action_id: -0.4,
        candidates[1].action_id: 0.2,
        candidates[2].action_id: 0.8,
        candidates[3].action_id: 0.1,
    }
    evaluator = _Successors()
    generator = _Generator()
    constitution = _StaticConstitution(actions)
    value = _StateValue(value_by_action)

    result = _run(
        state=state,
        constitution=constitution,
        generator=generator,
        policy=_Policy(probabilities),
        value=value,
        successors=evaluator,
    )

    assert generator.calls == [(state.state_id, actions, 4)]
    assert [call[0] for call in evaluator.calls] == sorted(
        action.action_id for action in candidates
    )
    assert [call[1].nodes for call in evaluator.calls] == [1, 2, 3, 4]
    assert [call[1].expansions for call in evaluator.calls] == [0, 1, 2, 3]
    assert result.selected_action == candidates[2]
    successor_by_action = dict(
        zip(
            result.receipt.expanded_action_ids,
            result.receipt.visited_state_ids[1:],
        )
    )
    assert result.final_state_id == successor_by_action[candidates[2].action_id]
    assert result.estimated_value == 0.8
    assert all(stat.visit_count == 1 for stat in result.action_statistics)
    assert {stat.action_id: stat.mean_value for stat in result.action_statistics} == value_by_action
    assert result.receipt.expanded_action_ids == tuple(
        sorted(action.action_id for action in candidates)
    )
    assert result.receipt.visited_state_ids[0] == state.state_id
    assert len(result.receipt.visited_state_ids[1:]) == len(result.action_statistics)
    assert result.receipt.provider_receipt_ids == tuple(
        sorted(f"provider:{action.action_id}" for action in candidates)
    )
    assert result.receipt.usage == BudgetUsage(
        nodes=5,
        expansions=4,
        model_calls=4,
        tokens=400,
        cost_microusd=4000,
        wall_time_ms=400,
        max_depth_observed=1,
    )
    assert result.receipt.termination_reason is SearchTerminationReason.COMPLETED
    assert state.model_dump(mode="json") == before


def test_equal_successor_values_use_prior_then_action_id_tie_breaks():
    state = _state()
    actions = _actions()[:3]

    def exercise(probabilities):
        value_by_action = {action.action_id: 0.5 for action in actions}
        evaluator = _Successors()
        return _run(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_Generator(),
            policy=_Policy(probabilities),
            value=_StateValue(value_by_action),
            successors=evaluator,
        )

    highest_prior = actions[1]
    first = exercise(
        {
            actions[0].action_id: 0.2,
            actions[1].action_id: 0.6,
            actions[2].action_id: 0.2,
        }
    )
    second = exercise({action.action_id: 1.0 / 3.0 for action in actions})

    assert first.selected_action == highest_prior
    assert second.selected_action.action_id == min(action.action_id for action in actions)


def test_result_is_deterministic_across_candidate_and_prior_input_order():
    state = _state()
    actions = _actions()[:4]
    probabilities = {action.action_id: 0.25 for action in actions}

    def exercise(action_order, policy_order):
        value_by_action = {action.action_id: 0.1 for action in actions}
        evaluator = _Successors()
        return _run(
            state=state,
            constitution=_StaticConstitution(tuple(reversed(actions))),
            generator=_Generator(outputs=action_order),
            policy=_Policy(
                outputs=tuple(
                    ActionPrior(action_id=action.action_id, probability=0.25)
                    for action in policy_order
                )
            ),
            value=_StateValue(value_by_action),
            successors=evaluator,
        )

    first = exercise(actions, actions)
    second = exercise(tuple(reversed(actions)), tuple(reversed(actions)))

    assert first == second
    assert first.receipt.receipt_id == second.receipt.receipt_id


def test_no_legal_action_and_no_remaining_candidate_budget_are_distinct():
    no_legal_state = _state()
    no_legal_value = _StateValue({}, root_value=-0.2)
    no_legal = _run(
        state=no_legal_state,
        constitution=_StaticConstitution(()),
        generator=_Unused(),
        policy=_Unused(),
        value=no_legal_value,
        successors=_Unused(),
    )
    assert no_legal.selected_action is None
    assert no_legal.estimated_value == -0.2
    assert no_legal.receipt.termination_reason is SearchTerminationReason.NO_LEGAL_ACTIONS

    exhausted_budget = _budget(max_nodes=1, max_expansions=0)
    exhausted_state = _state(
        budget=exhausted_budget,
        budget_usage=BudgetUsage(nodes=1),
    )
    exhausted_value = _StateValue({}, root_value=-0.1)
    exhausted = _run(
        state=exhausted_state,
        constitution=_StaticConstitution(_actions()),
        generator=_Unused(),
        policy=_Unused(),
        value=exhausted_value,
        successors=_Unused(),
    )
    assert exhausted.selected_action is None
    assert exhausted.estimated_value == -0.1
    assert exhausted.receipt.termination_reason is SearchTerminationReason.BUDGET_EXHAUSTED


def test_terminal_stop_uses_current_state_value_without_fabricating_a_successor():
    state = _state(phase="complete", terminal_status="abstained")
    stop = LegalAction(kind=ActionKind.STOP)
    value = _StateValue({}, root_value=0.0)

    result = _run(
        state=state,
        constitution=_StaticConstitution((stop,)),
        generator=_Unused(),
        policy=_Unused(),
        value=value,
        successors=_Unused(),
    )

    assert result.selected_action == stop
    assert result.final_state_id is None
    assert result.action_statistics == (
        ActionStatistics(
            action_id=stop.action_id,
            prior=1.0,
            visit_count=0,
            mean_value=0.0,
        ),
    )
    assert result.receipt.termination_reason is SearchTerminationReason.TERMINAL_STATE
    assert value.calls == [state.state_id]


def test_candidate_count_is_capped_by_remaining_nodes_and_expansions():
    budget = _budget(max_nodes=3, max_expansions=2)
    state = _state(budget=budget, budget_usage=BudgetUsage(nodes=1))
    actions = _actions()
    candidates = actions[:2]
    probabilities = {action.action_id: 0.5 for action in candidates}
    value_by_action = {action.action_id: 0.1 for action in candidates}
    evaluator = _Successors()
    generator = _Generator()

    result = _run(
        state=state,
        constitution=_StaticConstitution(actions),
        generator=generator,
        policy=_Policy(probabilities),
        value=_StateValue(value_by_action),
        successors=evaluator,
    )

    assert generator.calls == [(state.state_id, actions, 2)]
    assert len(evaluator.calls) == 2
    assert result.receipt.usage.nodes == 3
    assert result.receipt.usage.expansions == 2


@pytest.mark.parametrize("case", ["short", "outside", "duplicate", "type"])
def test_generated_candidates_must_be_exactly_n_unique_hard_legal_actions(case):
    state = _state()
    actions = _actions()
    if case == "short":
        outputs = actions[:3]
    elif case == "outside":
        outputs = actions[:3] + (LegalAction(kind=ActionKind.STOP),)
    elif case == "duplicate":
        outputs = actions[:3] + (actions[0],)
    else:
        outputs = ("not-an-action",) * 4

    with pytest.raises(ContractValidationError):
        _run(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_Generator(outputs=outputs),
            policy=_Unused(),
            value=_StateValue({}),
            successors=_Unused(),
        )


def test_policy_output_is_validated_before_successor_evaluation():
    state = _state()
    actions = _actions()
    candidates = actions[:4]
    malformed = tuple(
        ActionPrior(action_id=action.action_id, probability=0.1)
        for action in candidates
    )

    with pytest.raises(ContractValidationError, match="sum to 1"):
        _run(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_Generator(),
            policy=_Policy(outputs=malformed),
            value=_StateValue({}),
            successors=_Unused(),
        )


@pytest.mark.parametrize(
    "transform",
    [
        lambda outcome: outcome.model_copy(
            update={"action_id": LegalAction(kind=ActionKind.STOP).action_id}
        ),
        lambda outcome: outcome.model_copy(
            update={
                "state": outcome.state.model_copy(
                    update={"parent_state_id": "wrong-parent"}
                )
            }
        ),
        lambda outcome: outcome.model_copy(
            update={"state": outcome.state.model_copy(update={"depth": 2})}
        ),
        lambda outcome: outcome.model_copy(
            update={"usage_delta": BudgetUsage(expansions=1, max_depth_observed=1)}
        ),
        lambda outcome: outcome.model_copy(
            update={
                "usage_delta": outcome.usage_delta.model_copy(
                    update={"model_calls": 2}
                )
            }
        ),
        lambda outcome: "not-an-action-successor",
    ],
)
def test_successor_evaluator_output_fails_closed_on_broken_links_or_usage(transform):
    state = _state()
    actions = _actions()[:1]
    value_by_action = {actions[0].action_id: 0.2}
    evaluator = _Successors(transform=transform)

    with pytest.raises(ContractValidationError):
        _run(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_Generator(),
            policy=_Policy({actions[0].action_id: 1.0}),
            value=_StateValue(value_by_action),
            successors=evaluator,
        )


def test_aggregate_branch_usage_cannot_silently_exceed_nonstructural_budget():
    budget = _budget(max_model_calls=1)
    state = _state(budget=budget)
    actions = _actions()[:2]
    value_by_action = {action.action_id: 0.1 for action in actions}
    evaluator = _Successors()

    with pytest.raises(BudgetExceeded, match="model_calls"):
        _run(
            state=state,
            constitution=_StaticConstitution(actions),
            generator=_Generator(),
            policy=_Policy({action.action_id: 0.5 for action in actions}),
            value=_StateValue(value_by_action),
            successors=evaluator,
        )
    assert evaluator.calls[1][1].model_calls == 1


@pytest.mark.parametrize("unsafe_value", [math.nan, math.inf, -1.01, 1.01, "0.2"])
def test_each_successor_value_must_be_finite_numeric_and_bounded(unsafe_value):
    state = _state()
    action = _actions()[0]
    value_by_action = {action.action_id: unsafe_value}
    evaluator = _Successors()

    with pytest.raises(ContractValidationError, match="value"):
        _run(
            state=state,
            constitution=_StaticConstitution((action,)),
            generator=_Generator(),
            policy=_Policy({action.action_id: 1.0}),
            value=_StateValue(value_by_action),
            successors=evaluator,
        )

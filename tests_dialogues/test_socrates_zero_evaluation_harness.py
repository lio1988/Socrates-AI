"""Phase 5 matched-compute harness, isolation, and fairness tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from backend.dialogues.socrates_zero import (
    BEST_OF_N_STRATEGY_VERSION,
    CORE_MATCHED_SUCCESSOR_LIMIT,
    FIXED_ROTATION_REFERENCE_VERSION,
    FROZEN_EVALUATION_MATRIX,
    FROZEN_SEARCH_KERNEL_CASE_SET,
    GREEDY_STRATEGY_VERSION,
    HEURISTIC_POLICY_PRIOR_VERSION,
    HEURISTIC_VALUE_ESTIMATOR_VERSION,
    NEUTRAL_VALUE_ESTIMATOR_VERSION,
    PRIMARY_MATCHED_CONFIG_IDS,
    PUCT_STRATEGY_VERSION,
    SEARCH_KERNEL_CASE_SET_VERSION,
    SEARCH_KERNEL_CLAIM_SCOPE,
    SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION,
    SEARCH_KERNEL_HARNESS_VERSION,
    SEARCH_KERNEL_SUCCESSOR_VERSION,
    TRACE_FIXTURE_IDS,
    UNIFORM_POLICY_PRIOR_VERSION,
    BudgetUsage,
    ContractValidationError,
    EvaluationCase,
    EvaluationMetrics,
    EvaluationResourceUsage,
    EvaluationStatus,
    GreedyStrategy,
    TraceObservability,
    evaluate_case,
    evaluate_run,
    matched_budget_profile,
)


def _identity(*, strategy: str, policy: str, value: str, limit: int):
    return next(
        item
        for item in FROZEN_EVALUATION_MATRIX
        if item.strategy_id == strategy
        and item.policy_id == policy
        and item.value_id == value
        and item.budget_profile_id == matched_budget_profile(limit).profile_id
    )


def _case(name: str):
    return next(
        case for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases
        if case.case_name == name
    )


def _core_identity(strategy: str):
    return _identity(
        strategy=strategy,
        policy=HEURISTIC_POLICY_PRIOR_VERSION,
        value=HEURISTIC_VALUE_ESTIMATOR_VERSION,
        limit=CORE_MATCHED_SUCCESSOR_LIMIT,
    )


def _zero_usage() -> EvaluationResourceUsage:
    return EvaluationResourceUsage(
        successor_evaluations=0,
        policy_evaluations=0,
        value_evaluations=0,
        nodes=0,
        expansions=0,
        model_calls=0,
        tool_calls=0,
        tokens=0,
        cost_microusd=0,
        wall_time_ms=0,
        max_depth_observed=0,
    )


def _run(awaitable):
    return asyncio.run(awaitable)


def _plain(value: Any, seen: set[int] | None = None) -> Any:
    """Bounded view of the data graph supplied through the strategy API."""

    if seen is None:
        seen = set()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    marker = id(value)
    if marker in seen:
        return f"<{type(value).__name__}:seen>"
    seen.add(marker)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _plain(item, seen) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_plain(item, seen) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: _plain(item, seen)
            for key, item in vars(value).items()
            if not callable(item)
        }
    return f"<{type(value).__module__}.{type(value).__qualname__}>"


class _GroundTruthProbeStrategy:
    """Adversarial strategy that recursively inspects its supplied API graph."""

    def __init__(self, successor, forbidden: tuple[str, ...]) -> None:
        self.successor = successor
        self.forbidden = forbidden
        self.inspected = False

    async def search(self, initial_state, **kwargs):
        surface = repr(_plain((initial_state, kwargs, self.successor))).lower()
        assert all(value.lower() not in surface for value in self.forbidden)
        self.inspected = True
        return await GreedyStrategy().search(initial_state, **kwargs)


class _OverconsumeStrategy:
    """Ignores the declared cap and attempts one extra real observation."""

    def __init__(self, successor) -> None:
        self.successor = successor

    async def search(self, initial_state, **kwargs):
        constitution = kwargs["constitution"]
        budget = kwargs["budget"]
        actions = constitution.legal_actions(initial_state)
        aggregate = initial_state.budget_usage
        for index in range(budget.max_expansions + 1):
            observed = await self.successor.evaluate_successor(
                initial_state,
                actions[index % len(actions)],
                budget=budget,
                aggregate_usage=aggregate,
            )
            aggregate = aggregate.plus(observed.usage_delta)
        return await GreedyStrategy().search(initial_state, **kwargs)


def test_frozen_matrix_has_core_match_and_one_factor_ablations():
    assert len(FROZEN_EVALUATION_MATRIX) == 11
    assert len({item.evaluation_id for item in FROZEN_EVALUATION_MATRIX}) == 11
    assert len(PRIMARY_MATCHED_CONFIG_IDS) == 3
    assert {
        next(
            item.strategy_id for item in FROZEN_EVALUATION_MATRIX
            if item.evaluation_id == evaluation_id
        )
        for evaluation_id in PRIMARY_MATCHED_CONFIG_IDS
    } == {
        GREEDY_STRATEGY_VERSION,
        BEST_OF_N_STRATEGY_VERSION,
        PUCT_STRATEGY_VERSION,
    }

    # Policy ablations hold strategy, Value, budget, and cases constant.
    _identity(
        strategy=GREEDY_STRATEGY_VERSION,
        policy=UNIFORM_POLICY_PRIOR_VERSION,
        value=NEUTRAL_VALUE_ESTIMATOR_VERSION,
        limit=4,
    )
    _identity(
        strategy=GREEDY_STRATEGY_VERSION,
        policy=HEURISTIC_POLICY_PRIOR_VERSION,
        value=NEUTRAL_VALUE_ESTIMATOR_VERSION,
        limit=4,
    )
    _identity(
        strategy=PUCT_STRATEGY_VERSION,
        policy=UNIFORM_POLICY_PRIOR_VERSION,
        value=NEUTRAL_VALUE_ESTIMATOR_VERSION,
        limit=4,
    )
    _identity(
        strategy=PUCT_STRATEGY_VERSION,
        policy=HEURISTIC_POLICY_PRIOR_VERSION,
        value=NEUTRAL_VALUE_ESTIMATOR_VERSION,
        limit=4,
    )

    # Value ablations change only Value; budget ablations change only budget.
    for strategy in (
        GREEDY_STRATEGY_VERSION,
        BEST_OF_N_STRATEGY_VERSION,
        PUCT_STRATEGY_VERSION,
    ):
        _identity(
            strategy=strategy,
            policy=HEURISTIC_POLICY_PRIOR_VERSION,
            value=NEUTRAL_VALUE_ESTIMATOR_VERSION,
            limit=4,
        )
        _identity(
            strategy=strategy,
            policy=HEURISTIC_POLICY_PRIOR_VERSION,
            value=HEURISTIC_VALUE_ESTIMATOR_VERSION,
            limit=4,
        )
    for limit in (1, 2, 4, 8):
        _identity(
            strategy=PUCT_STRATEGY_VERSION,
            policy=HEURISTIC_POLICY_PRIOR_VERSION,
            value=HEURISTIC_VALUE_ESTIMATOR_VERSION,
            limit=limit,
        )


def test_every_identity_reports_the_complete_frozen_semantic_configuration():
    for identity in FROZEN_EVALUATION_MATRIX:
        assert identity.harness_id == SEARCH_KERNEL_HARNESS_VERSION
        assert identity.case_set_id == SEARCH_KERNEL_CASE_SET_VERSION
        assert identity.successor_evaluator_id == SEARCH_KERNEL_SUCCESSOR_VERSION
        assert identity.search_state_projection_id == (
            SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION
        )
        assert identity.legal_vocabulary_id
        assert identity.constitution_id
        assert identity.evaluation_id.startswith("szevaluation_")


def test_adversarial_strategy_cannot_reach_ground_truth_or_label_identity():
    case = _case("misleading_policy_01")
    holder = {}

    def factory(successor):
        probe = _GroundTruthProbeStrategy(
            successor,
            forbidden=(
                "ground_truth",
                "optimal_action",
                "outcome_value",
                case.case_name,
                case.category.value,
                case.case_id,
            ),
        )
        holder["probe"] = probe
        return probe

    result = _run(
        evaluate_case(
            case,
            _core_identity(GREEDY_STRATEGY_VERSION),
            strategy_factory=factory,
        )
    )

    assert holder["probe"].inspected is True
    assert result.status is EvaluationStatus.COMPLETED
    assert result.error_code is None


def test_adversarial_strategy_cannot_overconsume_successor_budget():
    case = _case("budget_exhaustion_01")
    holder = {}

    def factory(successor):
        strategy = _OverconsumeStrategy(successor)
        holder["strategy"] = strategy
        return strategy

    result = _run(
        evaluate_case(
            case,
            _core_identity(BEST_OF_N_STRATEGY_VERSION),
            strategy_factory=factory,
        )
    )

    successor = holder["strategy"].successor
    assert successor.attempt_count == CORE_MATCHED_SUCCESSOR_LIMIT + 1
    assert successor.completed_count == CORE_MATCHED_SUCCESSOR_LIMIT
    assert result.status is EvaluationStatus.STRATEGY_FAILURE
    assert result.error_code == "BUDGETEXCEEDED"
    assert result.resource_usage.successor_evaluations == CORE_MATCHED_SUCCESSOR_LIMIT
    assert result.budget_utilization == 1.0
    assert result.selected_action_id is None


def test_matched_best_of_n_and_puct_obey_identical_real_observation_cap():
    case = _case("budget_exhaustion_01")
    results = {
        strategy: _run(evaluate_case(case, _core_identity(strategy)))
        for strategy in (
            GREEDY_STRATEGY_VERSION,
            BEST_OF_N_STRATEGY_VERSION,
            PUCT_STRATEGY_VERSION,
        )
    }

    greedy = results[GREEDY_STRATEGY_VERSION].resource_usage
    best = results[BEST_OF_N_STRATEGY_VERSION].resource_usage
    puct = results[PUCT_STRATEGY_VERSION].resource_usage
    assert (greedy.successor_evaluations, greedy.nodes, greedy.expansions) == (0, 0, 0)
    assert (greedy.policy_evaluations, greedy.value_evaluations) == (1, 1)
    assert (best.successor_evaluations, best.nodes, best.expansions) == (4, 4, 4)
    assert (puct.successor_evaluations, puct.nodes, puct.expansions) == (4, 4, 4)
    assert (best.policy_evaluations, best.value_evaluations) == (1, 4)
    assert (puct.policy_evaluations, puct.value_evaluations) == (1, 4)
    for usage in (greedy, best, puct):
        assert (
            usage.model_calls,
            usage.tool_calls,
            usage.tokens,
            usage.cost_microusd,
            usage.wall_time_ms,
        ) == (0, 0, 0, 0, 0)


def test_manual_regret_and_policy_rank_are_exact():
    result = _run(
        evaluate_case(
            _case("misleading_policy_01"),
            _core_identity(GREEDY_STRATEGY_VERSION),
        )
    )

    assert result.selected_action_correct is False
    assert result.selected_outcome_value == -0.8
    assert result.optimal_outcome_value == 0.8
    assert result.regret == 1.6
    assert result.policy_rank == 1


def test_uniform_neutral_exact_ties_use_canonical_action_id():
    case = _case("exact_ties_01")
    for strategy in (GREEDY_STRATEGY_VERSION, PUCT_STRATEGY_VERSION):
        result = _run(
            evaluate_case(
                case,
                _identity(
                    strategy=strategy,
                    policy=UNIFORM_POLICY_PRIOR_VERSION,
                    value=NEUTRAL_VALUE_ESTIMATOR_VERSION,
                    limit=4,
                ),
            )
        )
        assert result.selected_action_id == case.ground_truth.canonical_optimal_action_id
        assert result.selected_action_correct is True
        assert result.regret == 0.0


def test_cross_strategy_order_is_independent_and_root_is_immutable():
    case = _case("misleading_policy_02")
    before = case.model_dump(mode="json")
    identities = tuple(
        _core_identity(strategy)
        for strategy in (
            GREEDY_STRATEGY_VERSION,
            BEST_OF_N_STRATEGY_VERSION,
            PUCT_STRATEGY_VERSION,
        )
    )

    async def execute(order):
        results = [await evaluate_case(case, identity) for identity in order]
        return {result.evaluation_id: result.model_dump(mode="json") for result in results}

    assert _run(execute(identities)) == _run(execute(tuple(reversed(identities))))
    assert case.model_dump(mode="json") == before


def test_same_config_and_case_set_replay_to_identical_semantic_run():
    identity = _core_identity(PUCT_STRATEGY_VERSION)

    first = _run(evaluate_run(identity))
    second = _run(evaluate_run(identity))

    assert first == second
    assert first.run_id == second.run_id
    assert len(first.per_case_results) == 20
    assert first.aggregate_metrics.cases_total == 20
    assert first.aggregate_metrics.cases_evaluable == 20
    assert first.aggregate_metrics.cases_failed == 0
    assert first.receipt_refs == second.receipt_refs


def test_not_evaluable_case_remains_visible_and_unscored():
    source = _case("policy_correct_01")
    data = source.model_dump(mode="python", exclude={"case_id"})
    data["compatible_budget_profile_ids"] = (matched_budget_profile(1).profile_id,)
    case = EvaluationCase(**data)

    result = _run(
        evaluate_case(case, _core_identity(GREEDY_STRATEGY_VERSION))
    )

    assert result.status is EvaluationStatus.NOT_EVALUABLE
    assert result.error_code == "INCOMPATIBLE_BUDGET"
    assert result.selected_action_correct is None
    assert result.regret is None
    assert result.resource_usage == _zero_usage()


def test_denominators_retain_failed_and_not_evaluable_counts():
    metrics = EvaluationMetrics(
        cases_total=2,
        cases_evaluable=0,
        cases_completed=0,
        cases_failed=1,
        cases_not_evaluable=1,
        correct_count=0,
        accuracy=None,
        total_regret=None,
        mean_regret=None,
        mean_budget_utilization=None,
        resource_usage=_zero_usage(),
    )

    assert metrics.cases_total == 2
    assert metrics.cases_failed == 1
    assert metrics.cases_not_evaluable == 1
    with pytest.raises((ValidationError, ContractValidationError), match="denominators"):
        EvaluationMetrics(
            **metrics.model_dump(
                mode="python",
                exclude={"cases_not_evaluable"},
            ),
            cases_not_evaluable=0,
        )


def test_trace_counterfactual_absence_and_fixed_baseline_are_explicit():
    traces = TraceObservability(
        traces_total=2,
        traces_evaluable=0,
        traces_missing_counterfactual=2,
        missing_fixture_ids=TRACE_FIXTURE_IDS,
    )

    assert traces.traces_evaluable == 0
    assert traces.traces_missing_counterfactual == 2
    assert len(traces.missing_fixture_ids) == 2
    assert FIXED_ROTATION_REFERENCE_VERSION == "ced-fixed-rotation-adapter/v0"
    assert SEARCH_KERNEL_CLAIM_SCOPE == "SEARCH_KERNEL_EVALUATION"


def test_evaluation_identity_rejects_unfrozen_strategy_policy_and_value():
    canonical = _core_identity(PUCT_STRATEGY_VERSION)
    for field, value in (
        ("strategy_id", "tuned-puct/v1"),
        ("policy_id", "learned-policy/v0"),
        ("value_id", "learned-value/v0"),
    ):
        data = canonical.model_dump(
            mode="python",
            exclude={"evaluation_id", field},
        )
        with pytest.raises((ValidationError, ContractValidationError), match="unfrozen"):
            type(canonical)(**data, **{field: value})

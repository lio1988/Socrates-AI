"""Frozen Phase 5 search-kernel evaluation contracts and budgets."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero import (
    MATCHED_SUCCESSOR_BUDGET_PROFILES,
    MATCHED_SUCCESSOR_BUDGET_VERSION,
    MATCHED_SUCCESSOR_OBSERVATION_LIMITS,
    SEARCH_KERNEL_CASE_SET_VERSION,
    SEARCH_KERNEL_CONSTITUTION_VERSION,
    SEARCH_KERNEL_EVALUATION_CONTRACT_VERSION,
    SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION,
    SEARCH_KERNEL_HARNESS_VERSION,
    SEARCH_KERNEL_SUCCESSOR_VERSION,
    BudgetUsage,
    ContractValidationError,
    EvaluationIdentity,
    EvaluationResourceUsage,
    MatchedBudgetProfile,
    SearchBudget,
    matched_budget_profile,
)


def test_phase5_semantic_versions_are_frozen_before_results():
    assert SEARCH_KERNEL_EVALUATION_CONTRACT_VERSION.endswith("/v0")
    assert SEARCH_KERNEL_HARNESS_VERSION == "socrateszero-search-kernel-eval-harness/v0"
    assert SEARCH_KERNEL_CASE_SET_VERSION == "socrateszero-search-kernel-case-set/v0"
    assert SEARCH_KERNEL_SUCCESSOR_VERSION == "socrateszero-search-kernel-successor/v0"
    assert SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION.endswith("/v0")
    assert SEARCH_KERNEL_CONSTITUTION_VERSION.endswith("/v0")


def test_frozen_profiles_are_exactly_one_two_four_and_eight_observations():
    assert MATCHED_SUCCESSOR_OBSERVATION_LIMITS == (1, 2, 4, 8)
    assert tuple(
        profile.max_successor_observations
        for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES
    ) == (1, 2, 4, 8)
    assert tuple(profile.profile_id for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES) == (
        "matched-successor-budget/v0/1",
        "matched-successor-budget/v0/2",
        "matched-successor-budget/v0/4",
        "matched-successor-budget/v0/8",
    )


@pytest.mark.parametrize("limit", MATCHED_SUCCESSOR_OBSERVATION_LIMITS)
def test_each_profile_encodes_one_root_and_exact_real_observation_cap(limit):
    profile = matched_budget_profile(limit)

    assert profile.schema_version == MATCHED_SUCCESSOR_BUDGET_VERSION
    assert profile.budget == SearchBudget(
        max_nodes=1 + limit,
        max_expansions=limit,
        max_model_calls=0,
        max_tool_calls=0,
        max_tokens=0,
        max_cost_microusd=0,
        max_wall_time_ms=0,
        max_depth=1,
    )


def test_budget_profile_rejects_post_hoc_semantic_drift():
    canonical = matched_budget_profile(4)
    with pytest.raises((ValidationError, ContractValidationError)):
        MatchedBudgetProfile(
            profile_id=canonical.profile_id,
            max_successor_observations=4,
            budget=canonical.budget.model_copy(update={"max_nodes": 6}),
        )
    with pytest.raises(ContractValidationError, match="unsupported frozen"):
        matched_budget_profile(3)


def test_resource_vector_reports_real_deltas_without_universal_compute_score():
    initial = BudgetUsage(nodes=1)
    final = BudgetUsage(nodes=5, expansions=4, max_depth_observed=1)

    usage = EvaluationResourceUsage.from_search_usage(
        initial=initial,
        final=final,
        successor_evaluations=4,
        policy_evaluations=1,
        value_evaluations=4,
    )

    assert usage == EvaluationResourceUsage(
        successor_evaluations=4,
        policy_evaluations=1,
        value_evaluations=4,
        nodes=4,
        expansions=4,
        model_calls=0,
        tool_calls=0,
        tokens=0,
        cost_microusd=0,
        wall_time_ms=0,
        max_depth_observed=1,
    )
    assert "compute_score" not in EvaluationResourceUsage.model_fields


def test_resource_vector_rejects_decreasing_counters():
    with pytest.raises(ContractValidationError, match="cannot decrease"):
        EvaluationResourceUsage.from_search_usage(
            initial=BudgetUsage(nodes=2),
            final=BudgetUsage(nodes=1),
            successor_evaluations=0,
            policy_evaluations=0,
            value_evaluations=0,
        )


def test_evaluation_configuration_identity_is_deterministic_and_complete():
    data = {
        "strategy_id": "puct-strategy/v0",
        "policy_id": "heuristic-policy-prior/v0",
        "value_id": "heuristic-value-estimator/v0",
        "budget_profile_id": matched_budget_profile(4).profile_id,
        "legal_vocabulary_id": "ced-legal-action-vocabulary/v0",
    }
    first = EvaluationIdentity(**data)
    second = EvaluationIdentity(**dict(reversed(tuple(data.items()))))

    assert first == second
    assert first.evaluation_id == second.evaluation_id
    assert first.successor_evaluator_id == SEARCH_KERNEL_SUCCESSOR_VERSION
    assert first.search_state_projection_id == SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION
    assert first.constitution_id == SEARCH_KERNEL_CONSTITUTION_VERSION


def test_evaluation_identity_rejects_unfrozen_budget_and_forged_hash():
    common = {
        "strategy_id": "puct-strategy/v0",
        "policy_id": "heuristic-policy-prior/v0",
        "value_id": "heuristic-value-estimator/v0",
        "legal_vocabulary_id": "ced-legal-action-vocabulary/v0",
    }
    with pytest.raises((ValidationError, ContractValidationError), match="unfrozen"):
        EvaluationIdentity(
            **common,
            budget_profile_id="matched-successor-budget/v0/3",
        )

    canonical = EvaluationIdentity(
        **common,
        budget_profile_id=matched_budget_profile(4).profile_id,
    )
    with pytest.raises((ValidationError, ContractValidationError), match="evaluation_id"):
        EvaluationIdentity(
            **common,
            budget_profile_id=matched_budget_profile(4).profile_id,
            evaluation_id="forged",
        )

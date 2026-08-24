"""Frozen balanced Phase 5 deterministic search-kernel cases."""

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero import (
    FROZEN_SEARCH_KERNEL_CASE_SET,
    MATCHED_SUCCESSOR_BUDGET_PROFILES,
    SEARCH_KERNEL_CASE_SET_VERSION,
    ActionOutcome,
    ContractValidationError,
    EvaluationCaseSet,
    EvaluationCategory,
    EvaluationGroundTruth,
)


def test_case_set_version_digest_count_and_category_balance_are_frozen():
    case_set = FROZEN_SEARCH_KERNEL_CASE_SET

    assert case_set.case_set_id == SEARCH_KERNEL_CASE_SET_VERSION
    assert case_set.case_set_digest.startswith("szevalcases_")
    assert len(case_set.cases) == 20
    assert Counter(case.category for case in case_set.cases) == {
        category: 2 for category in EvaluationCategory
    }
    assert tuple(case.case_name for case in case_set.cases) == tuple(
        sorted(case.case_name for case in case_set.cases)
    )


def test_every_case_has_exact_action_observation_truth_and_budget_alignment():
    frozen_profile_ids = {
        profile.profile_id for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES
    }
    for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases:
        action_ids = {action.action_id for action in case.hard_legal_actions}
        assert action_ids == {
            observation.action_id for observation in case.successor_observations
        }
        assert action_ids == {
            outcome.action_id for outcome in case.ground_truth.action_outcomes
        }
        assert set(case.compatible_budget_profile_ids) == frozen_profile_ids
        assert case.root_state.depth == 0
        assert case.root_state.budget_usage.nodes == 1


def test_ground_truth_derives_all_optima_and_canonical_tie_deterministically():
    truth = EvaluationGroundTruth(
        action_outcomes=(
            ActionOutcome(action_id="b", outcome_value=0.5),
            ActionOutcome(action_id="a", outcome_value=0.5),
            ActionOutcome(action_id="c", outcome_value=-0.2),
        )
    )

    assert truth.optimal_action_ids == ("a", "b")
    assert truth.canonical_optimal_action_id == "a"
    assert truth.outcome_for("c") == -0.2


def test_strategy_view_contains_no_ground_truth_labels_or_optimal_action():
    case = FROZEN_SEARCH_KERNEL_CASE_SET.cases[0]
    view = case.strategy_view()
    payload = view.model_dump(mode="json")
    serialized = repr(payload).lower()

    assert "ground_truth" not in payload
    assert "optimal_action" not in serialized
    assert "outcome_value" not in serialized
    assert set(payload) == {
        "case_id",
        "root_state",
        "hard_legal_actions",
        "successor_observations",
        "compatible_budget_profile_ids",
    }


def test_strategy_facing_state_and_actions_do_not_expose_case_or_category_names():
    for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases:
        view = case.strategy_view().model_dump(mode="json")
        strategy_surface = repr(
            {
                "root_state": view["root_state"],
                "hard_legal_actions": view["hard_legal_actions"],
                "successor_observations": view["successor_observations"],
            }
        ).lower()
        assert case.case_name.lower() not in strategy_surface
        assert case.category.value.lower() not in strategy_surface


def test_case_and_case_set_identity_replay_exactly():
    case_set = FROZEN_SEARCH_KERNEL_CASE_SET
    replay = EvaluationCaseSet.model_validate(case_set.model_dump(mode="python"))

    assert replay == case_set
    assert replay.case_set_digest == case_set.case_set_digest
    assert tuple(case.case_id for case in replay.cases) == tuple(
        case.case_id for case in case_set.cases
    )


def test_case_set_rejects_post_freeze_addition_removal_or_category_imbalance():
    case_set = FROZEN_SEARCH_KERNEL_CASE_SET
    with pytest.raises((ValidationError, ContractValidationError), match="20 cases"):
        EvaluationCaseSet(cases=case_set.cases[:-1])

    changed = case_set.cases[0].model_copy(
        update={"category": EvaluationCategory.EXACT_TIES, "case_id": None}
    )
    with pytest.raises((ValidationError, ContractValidationError), match="two cases"):
        EvaluationCaseSet(cases=(changed,) + case_set.cases[1:])


def test_exact_tie_cases_freeze_equal_numeric_outcomes():
    tie_cases = tuple(
        case
        for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases
        if case.category is EvaluationCategory.EXACT_TIES
    )
    assert len(tie_cases) == 2
    for case in tie_cases:
        assert len(case.ground_truth.optimal_action_ids) == len(
            case.hard_legal_actions
        )
        assert len(
            {item.outcome_value for item in case.ground_truth.action_outcomes}
        ) == 1


def test_selective_budget_cases_have_more_actions_than_matched_four_budget():
    selective = tuple(
        case
        for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases
        if case.category is EvaluationCategory.SELECTIVE_BUDGET_ADVANTAGE
    )
    assert len(selective) == 2
    assert all(len(case.hard_legal_actions) == 8 for case in selective)


def test_single_move_cases_have_exactly_one_action():
    single = tuple(
        case
        for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases
        if case.category is EvaluationCategory.SINGLE_LEGAL_MOVE
    )
    assert len(single) == 2
    assert all(len(case.hard_legal_actions) == 1 for case in single)

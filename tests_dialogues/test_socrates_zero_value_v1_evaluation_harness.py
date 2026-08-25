"""Metric, split, receipt, and deterministic replay tests for the v1 harness."""

from __future__ import annotations

import pytest

from backend.dialogues.ced_search_value_v1_evaluation import (
    ValueV1HardSafetyCounts,
    judge_pair,
    run_value_v1_evaluation,
)
from backend.dialogues.ced_search_value_v1_evaluation_cases import (
    FROZEN_VALUE_V1_EVALUATION_CASE_SET,
    VALUE_V1_EVAL_HARNESS_VERSION,
    ValueV1EvaluationSplit,
    ValueV1PairExpectation,
)
from backend.dialogues.socrates_zero import ContractValidationError


@pytest.mark.parametrize(
    "expectation,left,right,correct,inversion,ordered_tie,loss",
    [
        (ValueV1PairExpectation.LEFT_BETTER, 0.0, -0.1, True, False, False, 0.0),
        (ValueV1PairExpectation.LEFT_BETTER, -0.1, 0.0, False, True, False, 1.0),
        (ValueV1PairExpectation.LEFT_BETTER, 0.0, 0.0, False, False, True, 0.5),
        (ValueV1PairExpectation.RIGHT_BETTER, -0.1, 0.0, True, False, False, 0.0),
        (ValueV1PairExpectation.REQUIRED_TIE, -0.1, -0.1, True, False, False, 0.0),
        (ValueV1PairExpectation.REQUIRED_TIE, -0.1, 0.0, False, False, False, 1.0),
    ],
)
def test_hand_calculated_pair_judgments(
    expectation, left, right, correct, inversion, ordered_tie, loss
):
    result = judge_pair(expectation, left, right)
    assert result.correct is correct
    assert result.directional_error is inversion
    assert result.ordered_tie is ordered_tie
    assert result.ranking_loss == loss


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_pair_judgment_fails_closed_on_nonfinite_values(value):
    with pytest.raises(ContractValidationError, match="finite"):
        judge_pair(ValueV1PairExpectation.LEFT_BETTER, value, 0.0)


def test_development_run_uses_only_18_development_pairs_and_exact_denominators():
    run = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    expected_ids = {
        pair.pair_id
        for pair in FROZEN_VALUE_V1_EVALUATION_CASE_SET.for_split(
            ValueV1EvaluationSplit.DEVELOPMENT
        )
    }
    assert run.harness_id == VALUE_V1_EVAL_HARNESS_VERSION
    assert len(run.pair_results) == 18
    assert {item.pair_id for item in run.pair_results} == expected_ids
    assert all(
        item.split is ValueV1EvaluationSplit.DEVELOPMENT
        for item in run.pair_results
    )
    assert run.v0_metrics.total_pairs == run.v1_metrics.total_pairs == 18
    assert run.v0_metrics.ordered_pairs == run.v1_metrics.ordered_pairs == 5
    assert run.v0_metrics.required_tie_pairs \
        == run.v1_metrics.required_tie_pairs == 13
    assert run.v0_nonterminal_metrics.total_pairs \
        == run.v1_nonterminal_metrics.total_pairs == 16
    assert run.v0_terminal_metrics.total_pairs \
        == run.v1_terminal_metrics.total_pairs == 2


def test_development_receipt_source_and_hard_safety_gates_are_clean():
    run = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    assert run.hard_safety == ValueV1HardSafetyCounts()
    assert all(len(item.v1.left_receipt_hash) == 64 for item in run.pair_results)
    assert all(len(item.v1.right_receipt_hash) == 64 for item in run.pair_results)
    assert all(item.v0.left_receipt_hash.startswith("szvalueaudit_")
               for item in run.pair_results)


def test_development_run_replays_with_semantic_and_identity_equality():
    first = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    second = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    assert first == second
    assert first.run_id == second.run_id
    assert first.model_dump_json() == second.model_dump_json()


def test_development_metrics_are_structurally_complete_by_category():
    run = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    assert len(run.category_metrics) == 9
    assert all(item.v0.total_pairs == item.v1.total_pairs == 2
               for item in run.category_metrics)
    assert run.v1_metrics.directional_errors == 0
    assert run.v1_metrics.ordered_ties == 0
    assert run.v1_metrics.required_tie_accuracy == 1.0

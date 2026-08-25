"""Pre-holdout locks; these tests never execute the holdout evaluator."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.dialogues.ced_search_value_v1_artifact import (
    VALUE_V1_DEVELOPMENT_HOLDOUT_SPLIT_HASH,
    ValueV1PrimaryGateInputs,
    classify_primary_gate,
    primary_gate_for_holdout,
)
from backend.dialogues.ced_search_value_v1_contracts import (
    VALUE_V1_RULE_SEMANTIC_ID,
)
from backend.dialogues.ced_search_value_v1_evaluation import (
    ValueV1HardSafetyCounts,
    run_value_v1_evaluation,
)
from backend.dialogues.ced_search_value_v1_evaluation_cases import (
    ValueV1EvaluationSplit,
)
from backend.dialogues.socrates_zero import ContractValidationError
from scripts.run_socrates_zero_value_v1_evaluation import DEFAULT_OUTPUT


def _inputs(**updates) -> ValueV1PrimaryGateInputs:
    values = {
        "v0_ordered_accuracy": 0.50,
        "v1_ordered_accuracy": 0.80,
        "v0_nonterminal_accuracy": 0.50,
        "v1_nonterminal_accuracy": 0.80,
        "required_tie_accuracy": 1.0,
        "hard_safety": ValueV1HardSafetyCounts(),
    }
    values.update(updates)
    return ValueV1PrimaryGateInputs(**values)


def test_rule_split_and_runner_output_are_frozen_before_holdout():
    assert VALUE_V1_RULE_SEMANTIC_ID == (
        "szvaluev1rules_"
        "3d6d50dbb1a70a3d7d7d70c7b12835bc3f9a39cbcde74838022fc4ad3c6a1826"
    )
    assert VALUE_V1_DEVELOPMENT_HOLDOUT_SPLIT_HASH == (
        "f32a61ae9fd5ba1ca43d67f59f7adc455302947cfa89c12de59ad06f82bf3d3b"
    )
    assert DEFAULT_OUTPUT.name == "socrateszero_value_v1_primary_v0.json"
    assert DEFAULT_OUTPUT.parent.name == "artifacts"


def test_synthetic_primary_gate_passes_only_when_every_threshold_passes():
    decision = classify_primary_gate(_inputs())
    assert decision.passed is True
    assert decision.decision == "VALUE V1 HYPOTHESIS PASSED"
    assert decision.ordered_improvement == pytest.approx(0.30)
    assert decision.nonterminal_improvement == pytest.approx(0.30)
    assert decision.failed_gates == ()


@pytest.mark.parametrize(
    "updates,failed",
    [
        ({"v1_ordered_accuracy": 0.79}, "holdout_ordered_accuracy_below_80_percent"),
        ({"v0_ordered_accuracy": 0.61}, "holdout_improvement_below_20_points"),
        ({"v1_nonterminal_accuracy": 0.79}, "nonterminal_ordered_accuracy_below_80_percent"),
        ({"v0_nonterminal_accuracy": 0.61}, "nonterminal_improvement_below_20_points"),
        ({"required_tie_accuracy": 0.99}, "required_tie_accuracy_not_100_percent"),
        ({"v1_ordered_accuracy": None}, "missing_holdout_ordered_denominator"),
        (
            {"hard_safety": ValueV1HardSafetyCounts(receipt_mismatches=1)},
            "hard_safety_receipt_mismatches_nonzero",
        ),
    ],
)
def test_synthetic_primary_gate_has_no_soft_pass(updates, failed):
    decision = classify_primary_gate(_inputs(**updates))
    assert decision.passed is False
    assert decision.decision == "VALUE V1 HYPOTHESIS FALSIFIED"
    assert failed in decision.failed_gates


def test_primary_gate_refuses_development_run_as_holdout():
    development = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    with pytest.raises(ContractValidationError, match="holdout"):
        primary_gate_for_holdout(development)


def test_authoritative_output_does_not_exist_before_first_holdout_run():
    assert not Path(DEFAULT_OUTPUT).exists()

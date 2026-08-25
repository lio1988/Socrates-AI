"""Secondary classifier/config locks; no BestOfN strategy is executed here."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.dialogues.ced_search_value_v1_bestofn import classify_bestofn_gate
from backend.dialogues.socrates_zero import (
    BEST_OF_N_CANDIDATE_COUNT_V0,
    BEST_OF_N_STRATEGY_VERSION,
    UNIFORM_POLICY_PRIOR_VERSION,
)
from scripts.run_socrates_zero_value_v1_bestofn import DEFAULT_OUTPUT


def test_secondary_configuration_and_output_are_frozen_before_run():
    assert BEST_OF_N_STRATEGY_VERSION == "best-of-n-strategy/v0"
    assert UNIFORM_POLICY_PRIOR_VERSION == "uniform-policy-prior/v0"
    assert BEST_OF_N_CANDIDATE_COUNT_V0 == 4
    assert DEFAULT_OUTPUT.name == "socrateszero_value_v1_bestofn_v0.json"
    assert not Path(DEFAULT_OUTPUT).exists()


def test_secondary_gate_passes_at_exact_threshold_with_no_regressions():
    decision = classify_bestofn_gate(
        v0_selection_accuracy=0.50,
        v1_selection_accuracy=0.60,
    )
    assert decision.passed is True
    assert decision.improvement == pytest.approx(0.10)
    assert decision.failed_gates == ()


@pytest.mark.parametrize(
    "kwargs,failed",
    [
        (
            {"v0_selection_accuracy": 0.50, "v1_selection_accuracy": 0.59},
            "selection_improvement_below_10_points",
        ),
        (
            {
                "v0_selection_accuracy": 0.0,
                "v1_selection_accuracy": 1.0,
                "guardrail_regressions": 1,
            },
            "guardrail_regressions_nonzero",
        ),
        (
            {
                "v0_selection_accuracy": 0.0,
                "v1_selection_accuracy": 1.0,
                "budget_usage_regressions": 1,
            },
            "budget_usage_regressions_nonzero",
        ),
        (
            {
                "v0_selection_accuracy": 0.0,
                "v1_selection_accuracy": 1.0,
                "successor_accounting_regressions": 1,
            },
            "successor_accounting_regressions_nonzero",
        ),
        (
            {
                "v0_selection_accuracy": 0.0,
                "v1_selection_accuracy": 1.0,
                "new_failures": 1,
            },
            "new_failures_nonzero",
        ),
    ],
)
def test_secondary_gate_has_no_soft_pass(kwargs, failed):
    decision = classify_bestofn_gate(**kwargs)
    assert decision.passed is False
    assert failed in decision.failed_gates

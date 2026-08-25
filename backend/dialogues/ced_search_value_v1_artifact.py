"""Frozen primary-gate classification and artifact for Value-v1 Phase 7."""

from __future__ import annotations

import hashlib
from typing import Literal, Optional, Tuple

from pydantic import Field, model_validator

from .ced_search_value_v1_contracts import (
    HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
    VALUE_V1_RULE_SEMANTIC_ID,
)
from .ced_search_value_v1_evaluation import (
    ValueV1EvaluationRun,
    ValueV1HardSafetyCounts,
    ValueV1RankingMetrics,
    run_value_v1_evaluation,
)
from .ced_search_value_v1_evaluation_cases import (
    FROZEN_VALUE_V1_EVALUATION_CASE_SET,
    VALUE_V1_EVAL_HARNESS_VERSION,
    VALUE_V1_HOLDOUT_IMPROVEMENT_THRESHOLD,
    VALUE_V1_HOLDOUT_ORDERED_ACCURACY_THRESHOLD,
    VALUE_V1_NONTERMINAL_IMPROVEMENT_THRESHOLD,
    VALUE_V1_NONTERMINAL_ORDERED_ACCURACY_THRESHOLD,
    VALUE_V1_REQUIRED_TIE_ACCURACY_THRESHOLD,
    ValueV1EvaluationCategory,
    ValueV1EvaluationSplit,
    ValueV1PairExpectation,
)
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)
from .socrates_zero.evaluation import _FrozenEvaluationContract
from .socrates_zero.value import HEURISTIC_VALUE_ESTIMATOR_VERSION


VALUE_V1_PRIMARY_GATE_VERSION = "socrateszero-value-v1-primary-gate/v0"
VALUE_V1_PRIMARY_ARTIFACT_VERSION = (
    "socrateszero-value-v1-primary-artifact/v0"
)


def _split_hash() -> str:
    case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
    payload = {
        "case_set_id": case_set.case_set_id,
        "case_set_digest": case_set.case_set_digest,
        "pairs": [
            {"pair_id": pair.pair_id, "split": pair.split.value}
            for pair in case_set.pairs
        ],
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


VALUE_V1_DEVELOPMENT_HOLDOUT_SPLIT_HASH = _split_hash()


class ValueV1PrimaryGateInputs(_FrozenEvaluationContract):
    v0_ordered_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    v1_ordered_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    v0_nonterminal_accuracy: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    v1_nonterminal_accuracy: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    required_tie_accuracy: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    hard_safety: ValueV1HardSafetyCounts


class ValueV1PrimaryGateDecision(_FrozenEvaluationContract):
    gate_id: Literal[
        VALUE_V1_PRIMARY_GATE_VERSION
    ] = VALUE_V1_PRIMARY_GATE_VERSION
    passed: bool
    decision: Literal[
        "VALUE V1 HYPOTHESIS PASSED",
        "VALUE V1 HYPOTHESIS FALSIFIED",
    ]
    inputs: ValueV1PrimaryGateInputs
    ordered_improvement: Optional[float]
    nonterminal_improvement: Optional[float]
    failed_gates: Tuple[str, ...]


def classify_primary_gate(
    inputs: ValueV1PrimaryGateInputs,
) -> ValueV1PrimaryGateDecision:
    failed = []
    overall_delta = (
        inputs.v1_ordered_accuracy - inputs.v0_ordered_accuracy
        if inputs.v1_ordered_accuracy is not None
        and inputs.v0_ordered_accuracy is not None
        else None
    )
    nonterminal_delta = (
        inputs.v1_nonterminal_accuracy - inputs.v0_nonterminal_accuracy
        if inputs.v1_nonterminal_accuracy is not None
        and inputs.v0_nonterminal_accuracy is not None
        else None
    )
    if inputs.v1_ordered_accuracy is None:
        failed.append("missing_holdout_ordered_denominator")
    elif inputs.v1_ordered_accuracy < VALUE_V1_HOLDOUT_ORDERED_ACCURACY_THRESHOLD:
        failed.append("holdout_ordered_accuracy_below_80_percent")
    if overall_delta is None:
        failed.append("missing_holdout_v0_comparison")
    elif overall_delta < VALUE_V1_HOLDOUT_IMPROVEMENT_THRESHOLD:
        failed.append("holdout_improvement_below_20_points")
    if inputs.v1_nonterminal_accuracy is None:
        failed.append("missing_nonterminal_ordered_denominator")
    elif (
        inputs.v1_nonterminal_accuracy
        < VALUE_V1_NONTERMINAL_ORDERED_ACCURACY_THRESHOLD
    ):
        failed.append("nonterminal_ordered_accuracy_below_80_percent")
    if nonterminal_delta is None:
        failed.append("missing_nonterminal_v0_comparison")
    elif nonterminal_delta < VALUE_V1_NONTERMINAL_IMPROVEMENT_THRESHOLD:
        failed.append("nonterminal_improvement_below_20_points")
    if inputs.required_tie_accuracy is None:
        failed.append("missing_required_tie_denominator")
    elif inputs.required_tie_accuracy != VALUE_V1_REQUIRED_TIE_ACCURACY_THRESHOLD:
        failed.append("required_tie_accuracy_not_100_percent")
    for name, count in inputs.hard_safety.model_dump(mode="python").items():
        if count:
            failed.append(f"hard_safety_{name}_nonzero")
    passed = not failed
    return ValueV1PrimaryGateDecision(
        passed=passed,
        decision=(
            "VALUE V1 HYPOTHESIS PASSED"
            if passed
            else "VALUE V1 HYPOTHESIS FALSIFIED"
        ),
        inputs=inputs,
        ordered_improvement=overall_delta,
        nonterminal_improvement=nonterminal_delta,
        failed_gates=tuple(failed),
    )


_GUARDRAIL_CATEGORIES = {
    ValueV1EvaluationCategory.MISLEADING_LIFECYCLE_CLOSURE,
    ValueV1EvaluationCategory.DUPLICATE_DERIVED_SIGNAL,
    ValueV1EvaluationCategory.V0_V1_EQUIVALENCE,
    ValueV1EvaluationCategory.RESOLUTION_REMOVES_PENALTY,
    ValueV1EvaluationCategory.COUNT_INFLATION,
}


def _required_tie_accuracy(results) -> Optional[float]:
    guardrails = tuple(
        item for item in results
        if item.category in _GUARDRAIL_CATEGORIES
        and item.expectation is ValueV1PairExpectation.REQUIRED_TIE
    )
    if not guardrails:
        return None
    return sum(item.v1.judgment.correct for item in guardrails) / len(guardrails)


def primary_gate_for_holdout(
    holdout: ValueV1EvaluationRun,
) -> ValueV1PrimaryGateDecision:
    if holdout.split is not ValueV1EvaluationSplit.HOLDOUT:
        raise ContractValidationError("primary gate requires the holdout split")
    return classify_primary_gate(
        ValueV1PrimaryGateInputs(
            v0_ordered_accuracy=holdout.v0_metrics.ordered_accuracy,
            v1_ordered_accuracy=holdout.v1_metrics.ordered_accuracy,
            v0_nonterminal_accuracy=(
                holdout.v0_nonterminal_metrics.ordered_accuracy
            ),
            v1_nonterminal_accuracy=(
                holdout.v1_nonterminal_metrics.ordered_accuracy
            ),
            required_tie_accuracy=_required_tie_accuracy(holdout.pair_results),
            hard_safety=holdout.hard_safety,
        )
    )


class ValueV1PrimaryArtifact(_FrozenEvaluationContract):
    schema_version: Literal[
        VALUE_V1_PRIMARY_ARTIFACT_VERSION
    ] = VALUE_V1_PRIMARY_ARTIFACT_VERSION
    artifact_id: Optional[str] = None
    estimator_ids: Tuple[
        Literal[
            HEURISTIC_VALUE_ESTIMATOR_VERSION,
            HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
        ],
        ...,
    ] = (
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
    )
    case_set_id: str
    case_set_digest: str
    harness_id: Literal[
        VALUE_V1_EVAL_HARNESS_VERSION
    ] = VALUE_V1_EVAL_HARNESS_VERSION
    development_holdout_split_hash: str
    rule_semantic_id: Literal[
        VALUE_V1_RULE_SEMANTIC_ID
    ] = VALUE_V1_RULE_SEMANTIC_ID
    development_run: ValueV1EvaluationRun
    holdout_run: ValueV1EvaluationRun
    primary_decision: ValueV1PrimaryGateDecision

    @model_validator(mode="after")
    def validate_and_identify(self) -> "ValueV1PrimaryArtifact":
        case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
        if (
            self.case_set_id != case_set.case_set_id
            or self.case_set_digest != case_set.case_set_digest
        ):
            raise ContractValidationError("artifact case-set identity mismatch")
        if self.development_holdout_split_hash \
                != VALUE_V1_DEVELOPMENT_HOLDOUT_SPLIT_HASH:
            raise ContractValidationError("artifact split hash mismatch")
        if self.development_run.split is not ValueV1EvaluationSplit.DEVELOPMENT:
            raise ContractValidationError("artifact development run is misclassified")
        if self.holdout_run.split is not ValueV1EvaluationSplit.HOLDOUT:
            raise ContractValidationError("artifact holdout run is misclassified")
        if self.primary_decision != primary_gate_for_holdout(self.holdout_run):
            raise ContractValidationError("artifact primary decision mismatch")
        expected = stable_contract_id(
            "szvaluev1artifact",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id is not None and self.artifact_id != expected:
            raise ContractValidationError("artifact ID does not match semantics")
        object.__setattr__(self, "artifact_id", expected)
        return self


def build_primary_artifact() -> ValueV1PrimaryArtifact:
    development = run_value_v1_evaluation(ValueV1EvaluationSplit.DEVELOPMENT)
    holdout = run_value_v1_evaluation(ValueV1EvaluationSplit.HOLDOUT)
    case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
    return ValueV1PrimaryArtifact(
        case_set_id=case_set.case_set_id,
        case_set_digest=case_set.case_set_digest or "",
        development_holdout_split_hash=VALUE_V1_DEVELOPMENT_HOLDOUT_SPLIT_HASH,
        development_run=development,
        holdout_run=holdout,
        primary_decision=primary_gate_for_holdout(holdout),
    )


def render_primary_artifact(artifact: ValueV1PrimaryArtifact) -> str:
    return canonical_json(artifact.model_dump(mode="json")) + "\n"


__all__ = [
    "VALUE_V1_DEVELOPMENT_HOLDOUT_SPLIT_HASH",
    "VALUE_V1_PRIMARY_ARTIFACT_VERSION",
    "VALUE_V1_PRIMARY_GATE_VERSION",
    "ValueV1PrimaryArtifact",
    "ValueV1PrimaryGateDecision",
    "ValueV1PrimaryGateInputs",
    "build_primary_artifact",
    "classify_primary_gate",
    "primary_gate_for_holdout",
    "render_primary_artifact",
]

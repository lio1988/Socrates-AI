"""Deterministic direct-ranking harness for the frozen Value-v1 case set."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Literal, Optional, Tuple

from pydantic import Field, model_validator

from .ced_search_observability_v1 import (
    SEARCH_STATE_V1_PROJECTION_VERSION,
    SEARCH_STATE_V1_SCHEMA_VERSION,
    SearchStateV1,
)
from .ced_search_value_v1 import HeuristicValueEstimatorV1
from .ced_search_value_v1_contracts import (
    HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
    HEURISTIC_VALUE_RULES_V1,
    ValueV1Audit,
)
from .ced_search_value_v1_evaluation_cases import (
    FROZEN_VALUE_V1_EVALUATION_CASE_SET,
    VALUE_V1_EVAL_HARNESS_VERSION,
    ValueV1EvaluationCategory,
    ValueV1EvaluationPair,
    ValueV1EvaluationSplit,
    ValueV1PairExpectation,
    build_canonical_state,
)
from .socrates_zero.contracts import (
    ContractValidationError,
    TerminalStatus,
    canonical_json,
    stable_contract_id,
)
from .socrates_zero.evaluation import _FrozenEvaluationContract
from .socrates_zero.value import (
    HEURISTIC_VALUE_ESTIMATOR_VERSION,
    HeuristicValueEstimator,
)


VALUE_V1_PAIR_RESULT_VERSION = "socrateszero-value-v1-pair-result/v0"
VALUE_V1_EVALUATION_RUN_VERSION = "socrateszero-value-v1-evaluation-run/v0"

_ALLOWED_AUDIT_REASONS = set(HEURISTIC_VALUE_RULES_V1) | {
    "active_claim_supported_no_bonus",
    "terminal_neutral_firewall",
}
_ALLOWED_SUPPRESSION_FAMILIES = {
    "claim_assessment",
    "evidence",
    "verification",
    "objection",
    "contradiction",
}


class ValueV1PairJudgment(_FrozenEvaluationContract):
    correct: bool
    directional_error: bool
    ordered_tie: bool
    ranking_loss: float = Field(ge=0.0, le=2.0)


class ValueV1EstimatorPairOutcome(_FrozenEvaluationContract):
    estimator_id: str
    left_value: float = Field(ge=-1.0, le=1.0)
    right_value: float = Field(ge=-1.0, le=1.0)
    judgment: ValueV1PairJudgment
    left_receipt_hash: str
    right_receipt_hash: str

    @model_validator(mode="after")
    def validate_finite(self) -> "ValueV1EstimatorPairOutcome":
        if not math.isfinite(self.left_value) or not math.isfinite(self.right_value):
            raise ContractValidationError("pair outcome values must be finite")
        return self


class ValueV1HardSafetyCounts(_FrozenEvaluationContract):
    forbidden_inputs: int = Field(default=0, ge=0)
    positive_components: int = Field(default=0, ge=0)
    mutations: int = Field(default=0, ge=0)
    missing_source_records: int = Field(default=0, ge=0)
    receipt_mismatches: int = Field(default=0, ge=0)

    def plus(self, other: "ValueV1HardSafetyCounts") -> "ValueV1HardSafetyCounts":
        return ValueV1HardSafetyCounts(
            forbidden_inputs=self.forbidden_inputs + other.forbidden_inputs,
            positive_components=self.positive_components + other.positive_components,
            mutations=self.mutations + other.mutations,
            missing_source_records=(
                self.missing_source_records + other.missing_source_records
            ),
            receipt_mismatches=self.receipt_mismatches + other.receipt_mismatches,
        )


class ValueV1PairResult(_FrozenEvaluationContract):
    schema_version: Literal[
        VALUE_V1_PAIR_RESULT_VERSION
    ] = VALUE_V1_PAIR_RESULT_VERSION
    result_id: Optional[str] = None
    pair_id: str
    pair_name: str
    category: ValueV1EvaluationCategory
    split: ValueV1EvaluationSplit
    expectation: ValueV1PairExpectation
    nonterminal_pair: bool
    v0: ValueV1EstimatorPairOutcome
    v1: ValueV1EstimatorPairOutcome
    hard_safety: ValueV1HardSafetyCounts

    @model_validator(mode="after")
    def identify(self) -> "ValueV1PairResult":
        expected = stable_contract_id(
            "szvaluev1pairresult",
            self.model_dump(mode="json", exclude={"result_id"}),
        )
        if self.result_id is not None and self.result_id != expected:
            raise ContractValidationError("pair result ID does not match semantics")
        object.__setattr__(self, "result_id", expected)
        return self


class ValueV1RankingMetrics(_FrozenEvaluationContract):
    total_pairs: int = Field(ge=0)
    ordered_pairs: int = Field(ge=0)
    ordered_correct: int = Field(ge=0)
    ordered_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    required_tie_pairs: int = Field(ge=0)
    required_tie_correct: int = Field(ge=0)
    required_tie_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    directional_errors: int = Field(ge=0)
    ordered_ties: int = Field(ge=0)
    ranking_loss: float = Field(ge=0.0)
    mean_ranking_loss: Optional[float] = Field(default=None, ge=0.0, le=2.0)


class ValueV1CategoryMetrics(_FrozenEvaluationContract):
    category: ValueV1EvaluationCategory
    v0: ValueV1RankingMetrics
    v1: ValueV1RankingMetrics


class ValueV1EvaluationRun(_FrozenEvaluationContract):
    schema_version: Literal[
        VALUE_V1_EVALUATION_RUN_VERSION
    ] = VALUE_V1_EVALUATION_RUN_VERSION
    run_id: Optional[str] = None
    harness_id: Literal[
        VALUE_V1_EVAL_HARNESS_VERSION
    ] = VALUE_V1_EVAL_HARNESS_VERSION
    case_set_id: str
    case_set_digest: str
    split: ValueV1EvaluationSplit
    v0_estimator_id: Literal[
        HEURISTIC_VALUE_ESTIMATOR_VERSION
    ] = HEURISTIC_VALUE_ESTIMATOR_VERSION
    v1_estimator_id: Literal[
        HEURISTIC_VALUE_ESTIMATOR_V1_VERSION
    ] = HEURISTIC_VALUE_ESTIMATOR_V1_VERSION
    pair_results: Tuple[ValueV1PairResult, ...]
    v0_metrics: ValueV1RankingMetrics
    v1_metrics: ValueV1RankingMetrics
    v0_nonterminal_metrics: ValueV1RankingMetrics
    v1_nonterminal_metrics: ValueV1RankingMetrics
    v0_terminal_metrics: ValueV1RankingMetrics
    v1_terminal_metrics: ValueV1RankingMetrics
    category_metrics: Tuple[ValueV1CategoryMetrics, ...]
    hard_safety: ValueV1HardSafetyCounts

    @model_validator(mode="after")
    def identify(self) -> "ValueV1EvaluationRun":
        expected_count = (
            18 if self.split is ValueV1EvaluationSplit.DEVELOPMENT else 27
        )
        if len(self.pair_results) != expected_count:
            raise ContractValidationError(
                f"{self.split.value} run requires {expected_count} pair results"
            )
        if any(item.split is not self.split for item in self.pair_results):
            raise ContractValidationError("evaluation run mixes frozen splits")
        expected = stable_contract_id(
            "szvaluev1run",
            self.model_dump(mode="json", exclude={"run_id"}),
        )
        if self.run_id is not None and self.run_id != expected:
            raise ContractValidationError("evaluation run ID does not match semantics")
        object.__setattr__(self, "run_id", expected)
        return self


def judge_pair(
    expectation: ValueV1PairExpectation,
    left_value: float,
    right_value: float,
    *,
    ranking_regret_weight: float = 1.0,
) -> ValueV1PairJudgment:
    """Apply evaluator-only ground truth after both Value calls have returned."""

    if not all(
        math.isfinite(item)
        for item in (left_value, right_value, ranking_regret_weight)
    ):
        raise ContractValidationError("pair judgment requires finite numbers")
    if not 0.0 < ranking_regret_weight <= 2.0:
        raise ContractValidationError("ranking regret weight must be in (0, 2]")

    if expectation is ValueV1PairExpectation.REQUIRED_TIE:
        correct = left_value == right_value
        return ValueV1PairJudgment(
            correct=correct,
            directional_error=False,
            ordered_tie=False,
            ranking_loss=0.0 if correct else ranking_regret_weight,
        )

    ordered_tie = left_value == right_value
    correct = (
        left_value > right_value
        if expectation is ValueV1PairExpectation.LEFT_BETTER
        else right_value > left_value
    )
    directional_error = not correct and not ordered_tie
    loss = (
        0.0
        if correct
        else ranking_regret_weight / 2.0
        if ordered_tie
        else ranking_regret_weight
    )
    return ValueV1PairJudgment(
        correct=correct,
        directional_error=directional_error,
        ordered_tie=ordered_tie,
        ranking_loss=loss,
    )


def _metrics(
    results: Iterable[ValueV1PairResult], *, estimator: Literal["v0", "v1"]
) -> ValueV1RankingMetrics:
    selected = tuple(results)
    outcomes = tuple(getattr(item, estimator) for item in selected)
    ordered = tuple(
        (item, outcome)
        for item, outcome in zip(selected, outcomes)
        if item.expectation is not ValueV1PairExpectation.REQUIRED_TIE
    )
    ties = tuple(
        (item, outcome)
        for item, outcome in zip(selected, outcomes)
        if item.expectation is ValueV1PairExpectation.REQUIRED_TIE
    )
    ordered_correct = sum(outcome.judgment.correct for _, outcome in ordered)
    tie_correct = sum(outcome.judgment.correct for _, outcome in ties)
    total_loss = math.fsum(outcome.judgment.ranking_loss for outcome in outcomes)
    return ValueV1RankingMetrics(
        total_pairs=len(selected),
        ordered_pairs=len(ordered),
        ordered_correct=ordered_correct,
        ordered_accuracy=(ordered_correct / len(ordered) if ordered else None),
        required_tie_pairs=len(ties),
        required_tie_correct=tie_correct,
        required_tie_accuracy=(tie_correct / len(ties) if ties else None),
        directional_errors=sum(
            outcome.judgment.directional_error for _, outcome in ordered
        ),
        ordered_ties=sum(outcome.judgment.ordered_tie for _, outcome in ordered),
        ranking_loss=total_loss,
        mean_ranking_loss=(total_loss / len(outcomes) if outcomes else None),
    )


def _hybrid_snapshot(hybrid) -> str:
    return canonical_json(
        {
            family: [
                item.model_dump(mode="json")
                for _, item in sorted(getattr(hybrid, family).items())
            ]
            for family in (
                "claims",
                "evidence",
                "verifications",
                "objections",
                "contradictions",
                "revisions",
            )
        }
        | {"transitions": hybrid.transitions}
    )


def _source_snapshot(built) -> Tuple[str, str, str, str]:
    return (
        canonical_json(built.session_state.model_dump(mode="json")),
        canonical_json([item.to_dict() for item in built.commitments]),
        canonical_json([item.to_dict() for item in built.aporia_records]),
        _hybrid_snapshot(built.hybrid_state),
    )


def _audit_safety(state: SearchStateV1, audit: ValueV1Audit):
    forbidden = 0
    positive = sum(item.contribution > 0.0 for item in audit.components)
    missing = 0
    mismatch = 0

    if audit.reason_code is not None and audit.reason_code not in _ALLOWED_AUDIT_REASONS:
        forbidden += 1
    forbidden += sum(
        item.reason_code not in HEURISTIC_VALUE_RULES_V1
        for item in audit.components
    )
    forbidden += sum(
        item.family not in _ALLOWED_SUPPRESSION_FAMILIES
        for item in audit.suppressed_sources
    )

    source_index = {}
    for family, collection in (
        ("evidence", state.evidence),
        ("verification", state.verifications),
        ("objection", state.objections),
        ("contradiction", state.contradictions),
    ):
        for item in collection:
            source_index[(family, item.source_record_id)] = item.semantic_digest
    assessment_index = {
        item.claim_id: item.semantic_digest for item in state.claim_assessments
    }
    for item in audit.suppressed_sources:
        expected_digest = (
            assessment_index.get(item.source_record_id)
            if item.family == "claim_assessment"
            else source_index.get((item.family, item.source_record_id))
        )
        if expected_digest is None:
            missing += 1
        elif expected_digest != item.semantic_digest:
            mismatch += 1

    allowed_refs = {
        item.source_record_id
        for collection in (
            state.evidence,
            state.verifications,
            state.objections,
            state.contradictions,
        )
        for item in collection
    } | {
        item.claim_id for item in state.claim_assessments
    } | {
        f"claim-assessment:{item.semantic_digest}"
        for item in state.claim_assessments
    } | {
        item.artifact_id for item in state.base_state.unresolved_questions
    }
    missing += sum(
        reference not in allowed_refs
        for component in audit.components
        for reference in component.canonical_refs
    )

    if (
        audit.estimator_id != HEURISTIC_VALUE_ESTIMATOR_V1_VERSION
        or audit.search_state_version != SEARCH_STATE_V1_SCHEMA_VERSION
        or audit.projection_version != SEARCH_STATE_V1_PROJECTION_VERSION
        or audit.state_id != state.state_id
        or audit.base_state_id != state.base_state.state_id
    ):
        mismatch += 1
    expected_hash = hashlib.sha256(
        canonical_json(audit.identity_payload()).encode("utf-8")
    ).hexdigest()
    if audit.receipt_hash != expected_hash:
        mismatch += 1
    if audit.source_claim_id is not None:
        expected_digest = assessment_index.get(audit.source_claim_id)
        if expected_digest is None:
            missing += 1
        else:
            if audit.source_claim_assessment_digest != expected_digest:
                mismatch += 1
            if audit.source_claim_assessment_id != f"claim-assessment:{expected_digest}":
                mismatch += 1

    return forbidden, positive, missing, mismatch


@dataclass(frozen=True)
class _SideEvaluation:
    v0_value: float
    v0_receipt: str
    v1_value: float
    v1_receipt: str
    hard_safety: ValueV1HardSafetyCounts


def _evaluate_side(blueprint) -> _SideEvaluation:
    built = build_canonical_state(blueprint)
    source_before = _source_snapshot(built)
    projected_before = built.projected.model_dump(mode="json")
    v0_audit = HeuristicValueEstimator().evaluate(built.projected.base_state)
    v1_audit = HeuristicValueEstimatorV1().evaluate(built.projected)
    mutations = int(source_before != _source_snapshot(built)) + int(
        projected_before != built.projected.model_dump(mode="json")
    )
    forbidden, positive, missing, mismatch = _audit_safety(
        built.projected, v1_audit
    )
    return _SideEvaluation(
        v0_value=v0_audit.bounded_value,
        v0_receipt=v0_audit.audit_id,
        v1_value=v1_audit.bounded_value,
        v1_receipt=v1_audit.receipt_hash,
        hard_safety=ValueV1HardSafetyCounts(
            forbidden_inputs=forbidden,
            positive_components=positive,
            mutations=mutations,
            missing_source_records=missing,
            receipt_mismatches=mismatch,
        ),
    )


def _evaluate_pair(pair: ValueV1EvaluationPair) -> ValueV1PairResult:
    # The label is not passed into either side evaluation.  It is applied only
    # after the two isolated estimator calls have returned.
    left = _evaluate_side(pair.left)
    right = _evaluate_side(pair.right)
    v0_judgment = judge_pair(
        pair.expectation,
        left.v0_value,
        right.v0_value,
        ranking_regret_weight=pair.ranking_regret_weight,
    )
    v1_judgment = judge_pair(
        pair.expectation,
        left.v1_value,
        right.v1_value,
        ranking_regret_weight=pair.ranking_regret_weight,
    )
    left_state = build_canonical_state(pair.left).projected
    right_state = build_canonical_state(pair.right).projected
    nonterminal = (
        left_state.base_state.terminal_status is TerminalStatus.NON_TERMINAL
        and right_state.base_state.terminal_status is TerminalStatus.NON_TERMINAL
    )
    return ValueV1PairResult(
        pair_id=pair.pair_id or "",
        pair_name=pair.pair_name,
        category=pair.category,
        split=pair.split,
        expectation=pair.expectation,
        nonterminal_pair=nonterminal,
        v0=ValueV1EstimatorPairOutcome(
            estimator_id=HEURISTIC_VALUE_ESTIMATOR_VERSION,
            left_value=left.v0_value,
            right_value=right.v0_value,
            judgment=v0_judgment,
            left_receipt_hash=left.v0_receipt,
            right_receipt_hash=right.v0_receipt,
        ),
        v1=ValueV1EstimatorPairOutcome(
            estimator_id=HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
            left_value=left.v1_value,
            right_value=right.v1_value,
            judgment=v1_judgment,
            left_receipt_hash=left.v1_receipt,
            right_receipt_hash=right.v1_receipt,
        ),
        hard_safety=left.hard_safety.plus(right.hard_safety),
    )


def run_value_v1_evaluation(
    split: ValueV1EvaluationSplit,
) -> ValueV1EvaluationRun:
    """Run one explicitly selected frozen split, offline and deterministically."""

    case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
    pairs = case_set.for_split(split)
    results = tuple(_evaluate_pair(pair) for pair in pairs)
    nonterminal = tuple(item for item in results if item.nonterminal_pair)
    terminal = tuple(item for item in results if not item.nonterminal_pair)
    categories = tuple(
        ValueV1CategoryMetrics(
            category=category,
            v0=_metrics(
                (item for item in results if item.category is category),
                estimator="v0",
            ),
            v1=_metrics(
                (item for item in results if item.category is category),
                estimator="v1",
            ),
        )
        for category in ValueV1EvaluationCategory
    )
    hard_safety = ValueV1HardSafetyCounts()
    for result in results:
        hard_safety = hard_safety.plus(result.hard_safety)
    return ValueV1EvaluationRun(
        case_set_id=case_set.case_set_id,
        case_set_digest=case_set.case_set_digest or "",
        split=split,
        pair_results=results,
        v0_metrics=_metrics(results, estimator="v0"),
        v1_metrics=_metrics(results, estimator="v1"),
        v0_nonterminal_metrics=_metrics(nonterminal, estimator="v0"),
        v1_nonterminal_metrics=_metrics(nonterminal, estimator="v1"),
        v0_terminal_metrics=_metrics(terminal, estimator="v0"),
        v1_terminal_metrics=_metrics(terminal, estimator="v1"),
        category_metrics=categories,
        hard_safety=hard_safety,
    )


__all__ = [
    "VALUE_V1_EVALUATION_RUN_VERSION",
    "VALUE_V1_PAIR_RESULT_VERSION",
    "ValueV1CategoryMetrics",
    "ValueV1EvaluationRun",
    "ValueV1EstimatorPairOutcome",
    "ValueV1HardSafetyCounts",
    "ValueV1PairJudgment",
    "ValueV1PairResult",
    "ValueV1RankingMetrics",
    "judge_pair",
    "run_value_v1_evaluation",
]

"""Frozen one-factor BestOfN comparison unlocked by the passing primary gate."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple

from pydantic import Field, model_validator

from .ced_search_observability_v1 import SearchStateV1
from .ced_search_value_v1 import HeuristicValueEstimatorV1
from .ced_search_value_v1_artifact import ValueV1PrimaryArtifact
from .ced_search_value_v1_bestofn_cases import (
    FROZEN_VALUE_V1_BESTOFN_CASE_SET,
    VALUE_V1_BESTOFN_HARNESS_VERSION,
    ValueV1BestOfNCase,
    ValueV1BestOfNCaseMode,
)
from .ced_search_value_v1_contracts import HEURISTIC_VALUE_ESTIMATOR_V1_VERSION
from .ced_search_value_v1_evaluation_cases import (
    VALUE_V1_SECONDARY_IMPROVEMENT_THRESHOLD,
    build_canonical_state,
)
from .socrates_zero.constitution import (
    CEDSearchConstitution,
    DeterministicLegalActionGenerator,
    LEGAL_ACTION_GENERATOR_VERSION,
    LEGAL_ACTION_VOCABULARY_VERSION,
)
from .socrates_zero.contracts import (
    ActionSuccessor,
    BudgetUsage,
    ContractValidationError,
    SearchState,
    canonical_json,
    stable_contract_id,
)
from .socrates_zero.evaluation import _FrozenEvaluationContract
from .socrates_zero.policy import UNIFORM_POLICY_PRIOR_VERSION, UniformPolicyPrior
from .socrates_zero.strategy import (
    BEST_OF_N_CANDIDATE_COUNT_V0,
    BEST_OF_N_STRATEGY_VERSION,
    BestOfNStrategy,
)
from .socrates_zero.value import (
    HEURISTIC_VALUE_ESTIMATOR_VERSION,
    HeuristicValueEstimator,
)


VALUE_V1_BESTOFN_RESULT_VERSION = "socrateszero-value-v1-bestofn-result/v0"
VALUE_V1_BESTOFN_ARTIFACT_VERSION = "socrateszero-value-v1-bestofn-artifact/v0"

_PRIMARY_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "branches"
    / "feature-socrates-zero-heuristic-value-v1"
    / "artifacts"
    / "socrateszero_value_v1_primary_v0.json"
)


class ValueV1BestOfNArmResult(_FrozenEvaluationContract):
    estimator_id: str
    selected_action_id: str
    selected_correct: Optional[bool]
    action_values: Tuple[Tuple[str, float], ...]
    value_receipt_hashes: Tuple[Tuple[str, str], ...]
    usage: BudgetUsage
    visited_state_ids: Tuple[str, ...]
    expanded_action_ids: Tuple[str, ...]


class ValueV1BestOfNCaseResult(_FrozenEvaluationContract):
    result_id: Optional[str] = None
    case_id: str
    case_name: str
    mode: ValueV1BestOfNCaseMode
    optimal_action_id: Optional[str]
    v0: ValueV1BestOfNArmResult
    v1: ValueV1BestOfNArmResult
    guardrail_regression: bool
    budget_usage_regression: bool
    successor_accounting_regression: bool
    new_failure: bool = False

    @model_validator(mode="after")
    def identify(self) -> "ValueV1BestOfNCaseResult":
        expected = stable_contract_id(
            "szvaluev1bestofnresult",
            self.model_dump(mode="json", exclude={"result_id"}),
        )
        if self.result_id is not None and self.result_id != expected:
            raise ContractValidationError("secondary result ID mismatch")
        object.__setattr__(self, "result_id", expected)
        return self


class ValueV1BestOfNDecision(_FrozenEvaluationContract):
    passed: bool
    decision: Literal[
        "VALUE V1 BESTOFN GATE PASSED",
        "VALUE V1 BESTOFN GATE FAILED",
    ]
    v0_selection_accuracy: float = Field(ge=0.0, le=1.0)
    v1_selection_accuracy: float = Field(ge=0.0, le=1.0)
    improvement: float = Field(ge=-1.0, le=1.0)
    guardrail_regressions: int = Field(ge=0)
    budget_usage_regressions: int = Field(ge=0)
    successor_accounting_regressions: int = Field(ge=0)
    new_failures: int = Field(ge=0)
    failed_gates: Tuple[str, ...]


def classify_bestofn_gate(
    *,
    v0_selection_accuracy: float,
    v1_selection_accuracy: float,
    guardrail_regressions: int = 0,
    budget_usage_regressions: int = 0,
    successor_accounting_regressions: int = 0,
    new_failures: int = 0,
) -> ValueV1BestOfNDecision:
    improvement = v1_selection_accuracy - v0_selection_accuracy
    failed = []
    if improvement + 1e-12 < VALUE_V1_SECONDARY_IMPROVEMENT_THRESHOLD:
        failed.append("selection_improvement_below_10_points")
    for name, count in (
        ("guardrail_regressions", guardrail_regressions),
        ("budget_usage_regressions", budget_usage_regressions),
        ("successor_accounting_regressions", successor_accounting_regressions),
        ("new_failures", new_failures),
    ):
        if count:
            failed.append(f"{name}_nonzero")
    passed = not failed
    return ValueV1BestOfNDecision(
        passed=passed,
        decision=(
            "VALUE V1 BESTOFN GATE PASSED"
            if passed
            else "VALUE V1 BESTOFN GATE FAILED"
        ),
        v0_selection_accuracy=v0_selection_accuracy,
        v1_selection_accuracy=v1_selection_accuracy,
        improvement=improvement,
        guardrail_regressions=guardrail_regressions,
        budget_usage_regressions=budget_usage_regressions,
        successor_accounting_regressions=successor_accounting_regressions,
        new_failures=new_failures,
        failed_gates=tuple(failed),
    )


@dataclass(frozen=True)
class _BuiltSearchCase:
    root: SearchState
    actions: Tuple[object, ...]
    successors: Tuple[SearchStateV1, ...]
    optimal_action_id: Optional[str]


def _navigation_successor(
    envelope: SearchStateV1,
    *,
    root: SearchState,
    delta: BudgetUsage,
) -> SearchStateV1:
    payload = envelope.base_state.model_dump(mode="python", exclude={"state_id"})
    payload.update(
        parent_state_id=root.state_id,
        budget=root.budget,
        budget_usage=root.budget_usage.plus(delta),
        depth=root.depth + 1,
    )
    base = SearchState(**payload)
    return SearchStateV1(
        base_state=base,
        evidence=envelope.evidence,
        verifications=envelope.verifications,
        claim_assessments=envelope.claim_assessments,
        objections=envelope.objections,
        contradictions=envelope.contradictions,
    )


def _build_search_case(case: ValueV1BestOfNCase) -> _BuiltSearchCase:
    root = build_canonical_state(case.root).projected.base_state
    constitution = CEDSearchConstitution()
    actions = constitution.legal_actions(root)
    if len(actions) != BEST_OF_N_CANDIDATE_COUNT_V0:
        raise ContractValidationError("secondary root must expose N=4 actions")
    delta = BudgetUsage(nodes=1, expansions=1, max_depth_observed=1)
    successors = tuple(
        _navigation_successor(
            build_canonical_state(blueprint).projected,
            root=root,
            delta=delta,
        )
        for blueprint in case.candidates
    )
    optimal = (
        actions[case.optimal_candidate_slot].action_id
        if case.optimal_candidate_slot is not None
        else None
    )
    return _BuiltSearchCase(
        root=root,
        actions=actions,
        successors=successors,
        optimal_action_id=optimal,
    )


class _SuccessorEvaluator:
    def __init__(self, actions, successors) -> None:
        self._by_action = {
            action.action_id: successor
            for action, successor in zip(actions, successors)
        }

    async def evaluate_successor(
        self, state, action, *, budget, aggregate_usage
    ) -> ActionSuccessor:
        successor = self._by_action[action.action_id]
        return ActionSuccessor(
            action_id=action.action_id,
            state=successor.base_state,
            usage_delta=BudgetUsage(
                nodes=1,
                expansions=1,
                max_depth_observed=successor.base_state.depth,
            ),
        )


class _RecordingValueV0:
    version = HEURISTIC_VALUE_ESTIMATOR_VERSION

    def __init__(self) -> None:
        self.receipts: Dict[str, str] = {}

    async def estimate(self, state: SearchState) -> float:
        audit = HeuristicValueEstimator().evaluate(state)
        self.receipts[state.state_id or ""] = audit.audit_id
        return audit.bounded_value


class _CanonicalValueV1Adapter:
    """Navigation-only adapter; semantic evaluation still requires v1."""

    version = HEURISTIC_VALUE_ESTIMATOR_V1_VERSION

    def __init__(self, successors: Tuple[SearchStateV1, ...]) -> None:
        self._by_base_id = {
            item.base_state.state_id: item for item in successors
        }
        self.receipts: Dict[str, str] = {}

    async def estimate(self, state: SearchState) -> float:
        envelope = self._by_base_id.get(state.state_id)
        if envelope is None or envelope.base_state != state:
            raise ContractValidationError(
                "Value-v1 adapter has no exact canonical successor envelope"
            )
        audit = HeuristicValueEstimatorV1().evaluate(envelope)
        self.receipts[state.state_id or ""] = audit.receipt_hash
        return audit.bounded_value


def _run_arm(built: _BuiltSearchCase, *, use_v1: bool):
    successor_evaluator = _SuccessorEvaluator(built.actions, built.successors)
    value = (
        _CanonicalValueV1Adapter(built.successors)
        if use_v1
        else _RecordingValueV0()
    )
    result = asyncio.run(
        BestOfNStrategy(successor_evaluator).search(
            built.root,
            constitution=CEDSearchConstitution(),
            action_generator=DeterministicLegalActionGenerator(),
            policy_prior=UniformPolicyPrior(),
            value_estimator=value,
            budget=built.root.budget,
        )
    )
    receipts_by_action = []
    state_by_action = dict(
        zip(result.receipt.expanded_action_ids, result.receipt.visited_state_ids[1:])
    )
    for action_id in result.receipt.expanded_action_ids:
        receipts_by_action.append((action_id, value.receipts[state_by_action[action_id]]))
    return result, tuple(receipts_by_action)


def _arm_result(
    result,
    receipts,
    *,
    estimator_id: str,
    optimal_action_id: Optional[str],
) -> ValueV1BestOfNArmResult:
    return ValueV1BestOfNArmResult(
        estimator_id=estimator_id,
        selected_action_id=result.selected_action.action_id,
        selected_correct=(
            result.selected_action.action_id == optimal_action_id
            if optimal_action_id is not None
            else None
        ),
        action_values=tuple(
            sorted(
                (item.action_id, item.mean_value)
                for item in result.action_statistics
            )
        ),
        value_receipt_hashes=tuple(sorted(receipts)),
        usage=result.receipt.usage,
        visited_state_ids=result.receipt.visited_state_ids,
        expanded_action_ids=result.receipt.expanded_action_ids,
    )


def _run_case(case: ValueV1BestOfNCase) -> ValueV1BestOfNCaseResult:
    built = _build_search_case(case)
    v0_result, v0_receipts = _run_arm(built, use_v1=False)
    v1_result, v1_receipts = _run_arm(built, use_v1=True)
    v0 = _arm_result(
        v0_result,
        v0_receipts,
        estimator_id=HEURISTIC_VALUE_ESTIMATOR_VERSION,
        optimal_action_id=built.optimal_action_id,
    )
    v1 = _arm_result(
        v1_result,
        v1_receipts,
        estimator_id=HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
        optimal_action_id=built.optimal_action_id,
    )
    guardrail_regression = False
    if case.mode is ValueV1BestOfNCaseMode.GUARDRAIL_TIE:
        guardrail_regression = len({value for _, value in v1.action_values}) != 1
    expected_usage = BudgetUsage(nodes=5, expansions=4, max_depth_observed=1)
    accounting_regression = (
        len(v0.expanded_action_ids) != 4
        or len(v1.expanded_action_ids) != 4
        or len(v0.visited_state_ids) != 5
        or len(v1.visited_state_ids) != 5
        or v0.expanded_action_ids != v1.expanded_action_ids
    )
    return ValueV1BestOfNCaseResult(
        case_id=case.case_id or "",
        case_name=case.case_name,
        mode=case.mode,
        optimal_action_id=built.optimal_action_id,
        v0=v0,
        v1=v1,
        guardrail_regression=guardrail_regression,
        budget_usage_regression=(
            v0.usage != v1.usage
            or v0.usage != expected_usage
        ),
        successor_accounting_regression=accounting_regression,
    )


class ValueV1BestOfNArtifact(_FrozenEvaluationContract):
    schema_version: Literal[
        VALUE_V1_BESTOFN_ARTIFACT_VERSION
    ] = VALUE_V1_BESTOFN_ARTIFACT_VERSION
    artifact_id: Optional[str] = None
    primary_artifact_id: str
    case_set_id: str
    case_set_digest: str
    harness_id: Literal[
        VALUE_V1_BESTOFN_HARNESS_VERSION
    ] = VALUE_V1_BESTOFN_HARNESS_VERSION
    strategy_id: Literal[BEST_OF_N_STRATEGY_VERSION] = BEST_OF_N_STRATEGY_VERSION
    policy_id: Literal[UNIFORM_POLICY_PRIOR_VERSION] = UNIFORM_POLICY_PRIOR_VERSION
    legal_vocabulary_id: Literal[
        LEGAL_ACTION_VOCABULARY_VERSION
    ] = LEGAL_ACTION_VOCABULARY_VERSION
    action_generator_id: Literal[
        LEGAL_ACTION_GENERATOR_VERSION
    ] = LEGAL_ACTION_GENERATOR_VERSION
    candidate_count: Literal[4] = BEST_OF_N_CANDIDATE_COUNT_V0
    safe_depth: Literal[1] = 1
    matched_successor_budget: Literal[4] = 4
    case_results: Tuple[ValueV1BestOfNCaseResult, ...]
    decision: ValueV1BestOfNDecision

    @model_validator(mode="after")
    def validate_and_identify(self) -> "ValueV1BestOfNArtifact":
        case_set = FROZEN_VALUE_V1_BESTOFN_CASE_SET
        if (
            self.case_set_id != case_set.case_set_id
            or self.case_set_digest != case_set.case_set_digest
        ):
            raise ContractValidationError("secondary artifact case-set mismatch")
        if len(self.case_results) != len(case_set.cases):
            raise ContractValidationError("secondary artifact result denominator mismatch")
        expected = stable_contract_id(
            "szvaluev1bestofnartifact",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id is not None and self.artifact_id != expected:
            raise ContractValidationError("secondary artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected)
        return self


def _load_passing_primary() -> ValueV1PrimaryArtifact:
    primary = ValueV1PrimaryArtifact.model_validate_json(
        _PRIMARY_ARTIFACT_PATH.read_bytes()
    )
    if not primary.primary_decision.passed:
        raise ContractValidationError("secondary gate is locked by primary failure")
    return primary


def build_bestofn_artifact() -> ValueV1BestOfNArtifact:
    primary = _load_passing_primary()
    case_set = FROZEN_VALUE_V1_BESTOFN_CASE_SET
    results = tuple(_run_case(case) for case in case_set.cases)
    ordered = tuple(
        item for item in results
        if item.mode is ValueV1BestOfNCaseMode.ORDERED_SELECTION
    )
    v0_accuracy = sum(item.v0.selected_correct is True for item in ordered) / len(ordered)
    v1_accuracy = sum(item.v1.selected_correct is True for item in ordered) / len(ordered)
    decision = classify_bestofn_gate(
        v0_selection_accuracy=v0_accuracy,
        v1_selection_accuracy=v1_accuracy,
        guardrail_regressions=sum(item.guardrail_regression for item in results),
        budget_usage_regressions=sum(item.budget_usage_regression for item in results),
        successor_accounting_regressions=sum(
            item.successor_accounting_regression for item in results
        ),
        new_failures=sum(item.new_failure for item in results),
    )
    return ValueV1BestOfNArtifact(
        primary_artifact_id=primary.artifact_id or "",
        case_set_id=case_set.case_set_id,
        case_set_digest=case_set.case_set_digest or "",
        case_results=results,
        decision=decision,
    )


def render_bestofn_artifact(artifact: ValueV1BestOfNArtifact) -> str:
    return canonical_json(artifact.model_dump(mode="json")) + "\n"


__all__ = [
    "VALUE_V1_BESTOFN_ARTIFACT_VERSION",
    "VALUE_V1_BESTOFN_RESULT_VERSION",
    "ValueV1BestOfNArtifact",
    "ValueV1BestOfNDecision",
    "build_bestofn_artifact",
    "classify_bestofn_gate",
    "render_bestofn_artifact",
]

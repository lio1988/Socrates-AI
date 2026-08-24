"""Offline deterministic matched-compute search-kernel evaluation harness.

This module evaluates frozen Greedy, Best-of-N, and one-real-ply PUCT only.  It
does not run the fixed CED orchestration, dispatch providers, fabricate trace
counterfactuals, tune search, or grant a benchmark selection runtime authority.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Callable, Iterable, Literal, Optional, Tuple

from pydantic import Field, model_validator

from .constitution import (
    LEGAL_ACTION_VOCABULARY_VERSION,
    DeterministicLegalActionGenerator,
)
from .contracts import (
    ActionSuccessor,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    PolicyContextEntry,
    SearchBudget,
    SearchResult,
    SearchState,
    SearchTerminationReason,
    SemanticArtifactRef,
    stable_contract_id,
)
from .evaluation import (
    FIXED_ROTATION_REFERENCE_VERSION,
    SEARCH_KERNEL_CASE_SET_VERSION,
    SEARCH_KERNEL_HARNESS_VERSION,
    SEARCH_KERNEL_SUCCESSOR_VERSION,
    EvaluationCategory,
    EvaluationIdentity,
    EvaluationResourceUsage,
    EvaluationStatus,
    MatchedBudgetProfile,
    _FrozenEvaluationContract,
    matched_budget_profile,
)
from .evaluation_cases import (
    FROZEN_SEARCH_KERNEL_CASE_SET,
    EvaluationCase,
    EvaluationCaseSet,
    StrategyCaseView,
    SuccessorObservationBlueprint,
)
from .policy import (
    HEURISTIC_POLICY_PRIOR_VERSION,
    UNIFORM_POLICY_PRIOR_VERSION,
    HeuristicPolicyPrior,
    UniformPolicyPrior,
)
from .puct import PUCT_STRATEGY_VERSION, PUCTStrategy
from .strategy import (
    BEST_OF_N_STRATEGY_VERSION,
    GREEDY_STRATEGY_VERSION,
    BestOfNStrategy,
    GreedyStrategy,
)
from .value import (
    HEURISTIC_VALUE_ESTIMATOR_VERSION,
    NEUTRAL_VALUE_ESTIMATOR_VERSION,
    HeuristicValueEstimator,
    NeutralValueEstimator,
)


SEARCH_KERNEL_RESULT_VERSION = "socrateszero-search-kernel-result/v0"
SEARCH_KERNEL_BENCHMARK_ARTIFACT_VERSION = (
    "socrateszero-search-kernel-benchmark-artifact/v0"
)
SEARCH_KERNEL_CLAIM_SCOPE = "SEARCH_KERNEL_EVALUATION"

CORE_MATCHED_SUCCESSOR_LIMIT = 4
TRACE_FIXTURE_IDS = (
    "current_canonical_repeat_003",
    "historical_challenger_live_001",
)


def _identity(
    strategy_id: str,
    policy_id: str,
    value_id: str,
    successor_limit: int,
) -> EvaluationIdentity:
    return EvaluationIdentity(
        strategy_id=strategy_id,
        policy_id=policy_id,
        value_id=value_id,
        budget_profile_id=matched_budget_profile(successor_limit).profile_id,
        legal_vocabulary_id=LEGAL_ACTION_VOCABULARY_VERSION,
    )


# Frozen before the first comparative run.  The matrix changes one factor at a
# time for Policy/Value ablations and includes PUCT budgets 1/2/4/8.
FROZEN_EVALUATION_MATRIX: Tuple[EvaluationIdentity, ...] = (
    _identity(
        GREEDY_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        BEST_OF_N_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        PUCT_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        1,
    ),
    _identity(
        PUCT_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        2,
    ),
    _identity(
        PUCT_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        PUCT_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        HEURISTIC_VALUE_ESTIMATOR_VERSION,
        8,
    ),
    _identity(
        GREEDY_STRATEGY_VERSION,
        UNIFORM_POLICY_PRIOR_VERSION,
        NEUTRAL_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        GREEDY_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        NEUTRAL_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        BEST_OF_N_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        NEUTRAL_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        PUCT_STRATEGY_VERSION,
        UNIFORM_POLICY_PRIOR_VERSION,
        NEUTRAL_VALUE_ESTIMATOR_VERSION,
        4,
    ),
    _identity(
        PUCT_STRATEGY_VERSION,
        HEURISTIC_POLICY_PRIOR_VERSION,
        NEUTRAL_VALUE_ESTIMATOR_VERSION,
        4,
    ),
)


PRIMARY_MATCHED_CONFIG_IDS = tuple(
    identity.evaluation_id
    for identity in FROZEN_EVALUATION_MATRIX
    if identity.budget_profile_id == matched_budget_profile(4).profile_id
    and identity.policy_id == HEURISTIC_POLICY_PRIOR_VERSION
    and identity.value_id == HEURISTIC_VALUE_ESTIMATOR_VERSION
    and identity.strategy_id
    in {
        GREEDY_STRATEGY_VERSION,
        BEST_OF_N_STRATEGY_VERSION,
        PUCT_STRATEGY_VERSION,
    }
)


PRIMARY_PARETO_CONFIG_IDS = tuple(
    identity.evaluation_id
    for identity in FROZEN_EVALUATION_MATRIX
    if identity.policy_id == HEURISTIC_POLICY_PRIOR_VERSION
    and identity.value_id == HEURISTIC_VALUE_ESTIMATOR_VERSION
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SearchKernelCaseResult(_FrozenEvaluationContract):
    schema_version: Literal[SEARCH_KERNEL_RESULT_VERSION] = SEARCH_KERNEL_RESULT_VERSION
    result_id: Optional[str] = None
    evaluation_id: str
    case_id: str
    case_name: str
    category: EvaluationCategory
    status: EvaluationStatus
    selected_action_correct: Optional[bool] = None
    selected_action_id: Optional[str] = None
    optimal_action_ids: Tuple[str, ...] = ()
    canonical_optimal_action_id: Optional[str] = None
    selected_outcome_value: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    optimal_outcome_value: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    regret: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    policy_rank: Optional[int] = Field(default=None, ge=1)
    resource_usage: EvaluationResourceUsage
    # Values above 1.0 are retained for rejected adversarial runs rather than
    # clipped, so an attempted/actual overrun cannot be hidden in the artifact.
    budget_utilization: float = Field(ge=0.0)
    termination_reason: Optional[SearchTerminationReason] = None
    search_receipt_id: Optional[str] = None
    puct_receipt_id: Optional[str] = None
    error_code: Optional[str] = None

    @model_validator(mode="after")
    def validate_and_identify(self) -> "SearchKernelCaseResult":
        evaluable = self.status in {
            EvaluationStatus.COMPLETED,
            EvaluationStatus.BUDGET_EXHAUSTED,
        }
        scored = (
            self.selected_action_correct,
            self.selected_action_id,
            self.selected_outcome_value,
            self.optimal_outcome_value,
            self.regret,
            self.policy_rank,
            self.search_receipt_id,
        )
        if evaluable and any(value is None for value in scored):
            raise ContractValidationError("evaluable case result is incompletely scored")
        if not evaluable and any(value is not None for value in scored):
            raise ContractValidationError("failed or missing case cannot carry a score")
        if evaluable and (
            not self.optimal_action_ids
            or self.canonical_optimal_action_id not in self.optimal_action_ids
        ):
            raise ContractValidationError("evaluable case result lacks canonical optimum")
        if not evaluable and (
            self.optimal_action_ids or self.canonical_optimal_action_id is not None
        ):
            raise ContractValidationError("unscored case cannot carry optimal labels")
        if evaluable and self.error_code is not None:
            raise ContractValidationError("evaluable case cannot carry an error code")
        if not evaluable and not self.error_code:
            raise ContractValidationError("failed or missing case needs an error code")
        if not math.isclose(
            self.budget_utilization,
            self.resource_usage.successor_evaluations
            / max(1, _budget_limit_from_id(self.evaluation_id)),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ContractValidationError("budget utilization differs from real calls")
        payload = self.model_dump(mode="json", exclude={"result_id"})
        expected = stable_contract_id("szevalresult", payload)
        if self.result_id is not None and self.result_id != expected:
            raise ContractValidationError("result_id does not match case result")
        object.__setattr__(self, "result_id", expected)
        return self


class EvaluationMetrics(_FrozenEvaluationContract):
    category: Optional[EvaluationCategory] = None
    cases_total: int = Field(ge=0)
    cases_evaluable: int = Field(ge=0)
    cases_completed: int = Field(ge=0)
    cases_failed: int = Field(ge=0)
    cases_not_evaluable: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    total_regret: Optional[float] = Field(default=None, ge=0.0)
    mean_regret: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    mean_budget_utilization: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    resource_usage: EvaluationResourceUsage

    @model_validator(mode="after")
    def validate_denominators(self) -> "EvaluationMetrics":
        if self.cases_evaluable + self.cases_failed + self.cases_not_evaluable != self.cases_total:
            raise ContractValidationError("evaluation denominators do not sum to total")
        if self.cases_completed != self.cases_evaluable:
            raise ContractValidationError("every evaluable deterministic case must complete")
        if self.correct_count > self.cases_evaluable:
            raise ContractValidationError("correct count exceeds evaluable denominator")
        expected_accuracy = (
            self.correct_count / self.cases_evaluable
            if self.cases_evaluable
            else None
        )
        if self.accuracy != expected_accuracy:
            raise ContractValidationError("accuracy denominator is inconsistent")
        return self


class SearchKernelEvaluationRun(_FrozenEvaluationContract):
    schema_version: Literal[SEARCH_KERNEL_RESULT_VERSION] = SEARCH_KERNEL_RESULT_VERSION
    run_id: Optional[str] = None
    claim_scope: Literal[SEARCH_KERNEL_CLAIM_SCOPE] = SEARCH_KERNEL_CLAIM_SCOPE
    identity: EvaluationIdentity
    case_set_digest: str
    aggregate_metrics: EvaluationMetrics
    category_metrics: Tuple[EvaluationMetrics, ...]
    per_case_results: Tuple[SearchKernelCaseResult, ...]
    receipt_refs: Tuple[str, ...]
    fixed_rotation_reference_id: Literal[
        FIXED_ROTATION_REFERENCE_VERSION
    ] = FIXED_ROTATION_REFERENCE_VERSION

    @model_validator(mode="after")
    def validate_and_identify(self) -> "SearchKernelEvaluationRun":
        results = tuple(sorted(self.per_case_results, key=lambda item: item.case_name))
        expected_case_ids = {
            case.case_id for case in FROZEN_SEARCH_KERNEL_CASE_SET.cases
        }
        if self.case_set_digest != FROZEN_SEARCH_KERNEL_CASE_SET.case_set_digest:
            raise ContractValidationError("run uses an unknown case-set digest")
        if {item.case_id for item in results} != expected_case_ids:
            raise ContractValidationError("run must retain every frozen case exactly once")
        if len({item.case_id for item in results}) != len(results):
            raise ContractValidationError("run case result IDs must be unique")
        if any(item.evaluation_id != self.identity.evaluation_id for item in results):
            raise ContractValidationError("case result belongs to another evaluation")
        if self.aggregate_metrics != _metrics(results):
            raise ContractValidationError("aggregate metrics differ from case results")
        expected_categories = tuple(
            _metrics(
                tuple(item for item in results if item.category is category),
                category=category,
            )
            for category in EvaluationCategory
        )
        if self.category_metrics != expected_categories:
            raise ContractValidationError("category metrics differ from case results")
        expected_receipts = tuple(
            sorted(
                {
                    receipt
                    for item in results
                    for receipt in (item.search_receipt_id, item.puct_receipt_id)
                    if receipt is not None
                }
            )
        )
        if self.receipt_refs != expected_receipts:
            raise ContractValidationError("run receipt references are incomplete")
        object.__setattr__(self, "per_case_results", results)
        payload = self.model_dump(mode="json", exclude={"run_id"})
        expected = stable_contract_id("szevalrun", payload)
        if self.run_id is not None and self.run_id != expected:
            raise ContractValidationError("run_id does not match run semantics")
        object.__setattr__(self, "run_id", expected)
        return self


class TraceObservability(_FrozenEvaluationContract):
    traces_total: int = Field(ge=0)
    traces_evaluable: int = Field(ge=0)
    traces_missing_counterfactual: int = Field(ge=0)
    missing_fixture_ids: Tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_counts(self) -> "TraceObservability":
        if self.traces_evaluable + self.traces_missing_counterfactual != self.traces_total:
            raise ContractValidationError("trace observability denominators differ")
        if len(self.missing_fixture_ids) != self.traces_missing_counterfactual:
            raise ContractValidationError("missing trace IDs differ from count")
        return self


class SearchKernelBenchmarkArtifact(_FrozenEvaluationContract):
    schema_version: Literal[
        SEARCH_KERNEL_BENCHMARK_ARTIFACT_VERSION
    ] = SEARCH_KERNEL_BENCHMARK_ARTIFACT_VERSION
    artifact_id: Optional[str] = None
    claim_scope: Literal[SEARCH_KERNEL_CLAIM_SCOPE] = SEARCH_KERNEL_CLAIM_SCOPE
    harness_id: Literal[SEARCH_KERNEL_HARNESS_VERSION] = SEARCH_KERNEL_HARNESS_VERSION
    case_set_id: Literal[SEARCH_KERNEL_CASE_SET_VERSION] = SEARCH_KERNEL_CASE_SET_VERSION
    case_set_digest: str
    runs: Tuple[SearchKernelEvaluationRun, ...]
    primary_matched_run_ids: Tuple[str, ...]
    pareto_frontier_run_ids: Tuple[str, ...]
    trace_observability: TraceObservability
    disclaimer: str

    @model_validator(mode="after")
    def validate_and_identify(self) -> "SearchKernelBenchmarkArtifact":
        runs = tuple(sorted(self.runs, key=lambda item: item.identity.evaluation_id))
        if len({run.identity.evaluation_id for run in runs}) != len(runs):
            raise ContractValidationError("benchmark configurations must be unique")
        expected_evaluations = {
            identity.evaluation_id for identity in FROZEN_EVALUATION_MATRIX
        }
        if {run.identity.evaluation_id for run in runs} != expected_evaluations:
            raise ContractValidationError("benchmark must contain the entire frozen matrix")
        if self.case_set_digest != FROZEN_SEARCH_KERNEL_CASE_SET.case_set_digest:
            raise ContractValidationError("benchmark uses an unknown case-set digest")
        if any(run.case_set_digest != self.case_set_digest for run in runs):
            raise ContractValidationError("benchmark runs use different case sets")
        run_by_eval = {run.identity.evaluation_id: run for run in runs}
        expected_primary = tuple(
            run_by_eval[evaluation_id].run_id
            for evaluation_id in PRIMARY_MATCHED_CONFIG_IDS
        )
        if self.primary_matched_run_ids != expected_primary:
            raise ContractValidationError("primary matched comparison is incomplete")
        expected_frontier = pareto_frontier(
            tuple(
                run_by_eval[evaluation_id]
                for evaluation_id in PRIMARY_PARETO_CONFIG_IDS
            )
        )
        if self.pareto_frontier_run_ids != tuple(run.run_id for run in expected_frontier):
            raise ContractValidationError("Pareto frontier differs from run metrics")
        object.__setattr__(self, "runs", runs)
        payload = self.model_dump(mode="json", exclude={"artifact_id"})
        expected = stable_contract_id("szevalartifact", payload)
        if self.artifact_id is not None and self.artifact_id != expected:
            raise ContractValidationError("artifact_id does not match benchmark")
        object.__setattr__(self, "artifact_id", expected)
        return self


class _CaseConstitution:
    version = "socrateszero-search-kernel-constitution/v0"

    def __init__(self, root: SearchState, actions: Tuple[LegalAction, ...]) -> None:
        self._root_id = root.state_id
        self._actions = tuple(actions)

    def legal_actions(self, state: SearchState) -> Tuple[LegalAction, ...]:
        if state.state_id != self._root_id:
            raise ContractValidationError("evaluation Constitution is root-only")
        return self._actions

    def validate_action(self, state: SearchState, action: LegalAction) -> None:
        if state.state_id != self._root_id:
            raise ContractValidationError("evaluation Constitution is root-only")
        if action.action_id not in {item.action_id for item in self._actions}:
            raise ContractValidationError("action is outside frozen hard-legal set")


class _CountingPolicy:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name
        self.version = inner.version
        self.call_count = 0
        self.outputs = []

    async def priors(self, state, legal_actions):
        self.call_count += 1
        result = await self.inner.priors(state, legal_actions)
        self.outputs.append(result)
        return result


class _CountingValue:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name
        self.version = inner.version
        self.call_count = 0

    async def estimate(self, state):
        self.call_count += 1
        return await self.inner.estimate(state)


class DeterministicEvaluationSuccessor:
    """Root-only observed-state fixture with no objective outcome labels."""

    name = "search_kernel_evaluation_successor"
    version = SEARCH_KERNEL_SUCCESSOR_VERSION

    def __init__(self, root: SearchState, view: StrategyCaseView) -> None:
        self._root = root
        self._observations = {
            item.action_id: item for item in view.successor_observations
        }
        self.attempt_count = 0
        self.completed_count = 0
        self.input_state_ids = []
        self.aggregate_usage_inputs = []

    async def evaluate_successor(
        self,
        state: SearchState,
        action: LegalAction,
        *,
        budget: SearchBudget,
        aggregate_usage: BudgetUsage,
    ) -> ActionSuccessor:
        self.attempt_count += 1
        self.input_state_ids.append(state.state_id)
        self.aggregate_usage_inputs.append(aggregate_usage)
        if state.state_id != self._root.state_id or state.depth != 0:
            raise ContractValidationError("evaluation successor is root-only")
        if budget != self._root.budget:
            raise ContractValidationError("evaluation successor budget differs")
        expected_aggregate = self._root.budget_usage.plus(
            BudgetUsage(
                nodes=self.completed_count,
                expansions=self.completed_count,
                max_depth_observed=1 if self.completed_count else 0,
            )
        )
        if aggregate_usage != expected_aggregate:
            raise ContractValidationError(
                "evaluation successor received dishonest aggregate usage"
            )
        try:
            blueprint = self._observations[action.action_id]
        except KeyError as exc:
            raise ContractValidationError("evaluation successor action is unknown") from exc
        delta = BudgetUsage(nodes=1, expansions=1, max_depth_observed=1)
        budget.enforce(expected_aggregate.plus(delta))
        data = state.model_dump(mode="python", exclude={"state_id"})
        opaque_prefix = _digest(f"{self._root.state_id}:{action.action_id}")
        data.update(
            parent_state_id=state.state_id,
            contradictions=tuple(
                _artifact(f"eval_contradiction_{opaque_prefix}", index)
                for index in range(blueprint.contradiction_count)
            ),
            unresolved_questions=tuple(
                _artifact(f"eval_question_{opaque_prefix}", index)
                for index in range(blueprint.unresolved_question_count)
            ),
            policy_context=(
                PolicyContextEntry(
                    name="evaluation_transition",
                    semantic_digest=_digest(action.action_id),
                ),
            ),
            budget_usage=state.budget_usage.plus(delta),
            depth=1,
        )
        successor = ActionSuccessor(
            action_id=action.action_id,
            state=SearchState(**data),
            usage_delta=delta,
        )
        self.completed_count += 1
        return successor


def _artifact(prefix: str, index: int) -> SemanticArtifactRef:
    artifact_id = f"{prefix}_{index}"
    return SemanticArtifactRef(
        artifact_id=artifact_id,
        semantic_digest=_digest(artifact_id),
    )


def _policy(policy_id: str):
    if policy_id == HEURISTIC_POLICY_PRIOR_VERSION:
        return HeuristicPolicyPrior()
    if policy_id == UNIFORM_POLICY_PRIOR_VERSION:
        return UniformPolicyPrior()
    raise ContractValidationError(f"unfrozen Policy {policy_id!r}")


def _value(value_id: str):
    if value_id == HEURISTIC_VALUE_ESTIMATOR_VERSION:
        return HeuristicValueEstimator()
    if value_id == NEUTRAL_VALUE_ESTIMATOR_VERSION:
        return NeutralValueEstimator()
    raise ContractValidationError(f"unfrozen Value {value_id!r}")


def _strategy(strategy_id: str, successor):
    if strategy_id == GREEDY_STRATEGY_VERSION:
        return GreedyStrategy()
    if strategy_id == BEST_OF_N_STRATEGY_VERSION:
        return BestOfNStrategy(successor)
    if strategy_id == PUCT_STRATEGY_VERSION:
        return PUCTStrategy(successor)
    raise ContractValidationError(f"unfrozen strategy {strategy_id!r}")


def _profile_for(identity: EvaluationIdentity) -> MatchedBudgetProfile:
    return next(
        profile
        for profile in (
            matched_budget_profile(1),
            matched_budget_profile(2),
            matched_budget_profile(4),
            matched_budget_profile(8),
        )
        if profile.profile_id == identity.budget_profile_id
    )


def _materialize_root(case: EvaluationCase, profile: MatchedBudgetProfile) -> SearchState:
    data = case.root_state.model_dump(mode="python", exclude={"state_id"})
    data.update(budget=profile.budget, budget_usage=BudgetUsage(nodes=1))
    return SearchState(**data)


def _budget_limit_from_id(evaluation_id: str) -> int:
    try:
        identity = next(
            item for item in FROZEN_EVALUATION_MATRIX if item.evaluation_id == evaluation_id
        )
    except StopIteration as exc:
        raise ContractValidationError("case result uses unknown evaluation ID") from exc
    return _profile_for(identity).max_successor_observations


async def _full_policy_rank(
    policy_id: str,
    root: SearchState,
    actions: Tuple[LegalAction, ...],
    selected_action_id: str,
) -> int:
    priors = await _policy(policy_id).priors(root, actions)
    ordered = sorted(priors, key=lambda item: (-item.probability, item.action_id))
    return next(
        index
        for index, item in enumerate(ordered, start=1)
        if item.action_id == selected_action_id
    )


async def evaluate_case(
    case: EvaluationCase,
    identity: EvaluationIdentity,
    *,
    strategy_factory: Optional[Callable[[DeterministicEvaluationSuccessor], object]] = None,
) -> SearchKernelCaseResult:
    """Evaluate one case while keeping ground truth outside strategy inputs."""

    if identity.evaluation_id not in {
        item.evaluation_id for item in FROZEN_EVALUATION_MATRIX
    }:
        raise ContractValidationError("configuration is outside frozen matrix")
    profile = _profile_for(identity)
    if profile.profile_id not in case.compatible_budget_profile_ids:
        return _unscored_result(
            case,
            identity,
            profile,
            EvaluationStatus.NOT_EVALUABLE,
            "INCOMPATIBLE_BUDGET",
        )
    view = case.strategy_view()
    root = _materialize_root(case, profile)
    before = root.model_dump(mode="json")
    successor = DeterministicEvaluationSuccessor(root, view)
    policy = _CountingPolicy(_policy(identity.policy_id))
    value = _CountingValue(_value(identity.value_id))
    constitution = _CaseConstitution(root, view.hard_legal_actions)
    strategy = (
        strategy_factory(successor)
        if strategy_factory is not None
        else _strategy(identity.strategy_id, successor)
    )
    puct_receipt_id = None
    try:
        if identity.strategy_id == PUCT_STRATEGY_VERSION and isinstance(
            strategy, PUCTStrategy
        ):
            evaluation = await strategy.evaluate(
                root,
                constitution=constitution,
                action_generator=DeterministicLegalActionGenerator(),
                policy_prior=policy,
                value_estimator=value,
                budget=profile.budget,
            )
            result = evaluation.result
            puct_receipt_id = evaluation.puct_receipt.receipt_id
        else:
            result = await strategy.search(
                root,
                constitution=constitution,
                action_generator=DeterministicLegalActionGenerator(),
                policy_prior=policy,
                value_estimator=value,
                budget=profile.budget,
            )
        _validate_run_result(
            result=result,
            identity=identity,
            profile=profile,
            root=root,
            legal_actions=view.hard_legal_actions,
            successor=successor,
        )
        if root.model_dump(mode="json") != before:
            raise ContractValidationError("strategy mutated evaluation root")
        selected_id = result.selected_action.action_id if result.selected_action else None
        if selected_id is None:
            raise ContractValidationError("evaluable fixture returned no action")
        selected_outcome = case.ground_truth.outcome_for(selected_id)
        optimal_outcome = max(
            item.outcome_value for item in case.ground_truth.action_outcomes
        )
        regret = round(optimal_outcome - selected_outcome, 12)
        usage = EvaluationResourceUsage.from_search_usage(
            initial=root.budget_usage,
            final=result.receipt.usage,
            successor_evaluations=successor.completed_count,
            policy_evaluations=policy.call_count,
            value_evaluations=value.call_count,
        )
        status = (
            EvaluationStatus.BUDGET_EXHAUSTED
            if result.receipt.termination_reason
            is SearchTerminationReason.BUDGET_EXHAUSTED
            else EvaluationStatus.COMPLETED
        )
        return SearchKernelCaseResult(
            evaluation_id=identity.evaluation_id,
            case_id=case.case_id,
            case_name=case.case_name,
            category=case.category,
            status=status,
            selected_action_correct=(selected_id in case.ground_truth.optimal_action_ids),
            selected_action_id=selected_id,
            optimal_action_ids=case.ground_truth.optimal_action_ids,
            canonical_optimal_action_id=case.ground_truth.canonical_optimal_action_id,
            selected_outcome_value=selected_outcome,
            optimal_outcome_value=optimal_outcome,
            regret=regret,
            policy_rank=await _full_policy_rank(
                identity.policy_id,
                root,
                view.hard_legal_actions,
                selected_id,
            ),
            resource_usage=usage,
            budget_utilization=(
                successor.completed_count / profile.max_successor_observations
            ),
            termination_reason=result.receipt.termination_reason,
            search_receipt_id=result.receipt.receipt_id,
            puct_receipt_id=puct_receipt_id,
        )
    except Exception as exc:
        if root.model_dump(mode="json") != before:
            error_code = "ROOT_MUTATION"
        else:
            error_code = exc.__class__.__name__.upper()
        usage = EvaluationResourceUsage(
            successor_evaluations=successor.completed_count,
            policy_evaluations=policy.call_count,
            value_evaluations=value.call_count,
            nodes=successor.completed_count,
            expansions=successor.completed_count,
            model_calls=0,
            tool_calls=0,
            tokens=0,
            cost_microusd=0,
            wall_time_ms=0,
            max_depth_observed=1 if successor.completed_count else 0,
        )
        return SearchKernelCaseResult(
            evaluation_id=identity.evaluation_id,
            case_id=case.case_id,
            case_name=case.case_name,
            category=case.category,
            status=EvaluationStatus.STRATEGY_FAILURE,
            resource_usage=usage,
            budget_utilization=(
                successor.completed_count / profile.max_successor_observations
            ),
            error_code=error_code,
        )


def _unscored_result(
    case: EvaluationCase,
    identity: EvaluationIdentity,
    profile: MatchedBudgetProfile,
    status: EvaluationStatus,
    error_code: str,
) -> SearchKernelCaseResult:
    return SearchKernelCaseResult(
        evaluation_id=identity.evaluation_id,
        case_id=case.case_id,
        case_name=case.case_name,
        category=case.category,
        status=status,
        resource_usage=_zero_usage(),
        budget_utilization=0.0 / profile.max_successor_observations,
        error_code=error_code,
    )


def _validate_run_result(
    *,
    result: SearchResult,
    identity: EvaluationIdentity,
    profile: MatchedBudgetProfile,
    root: SearchState,
    legal_actions: Tuple[LegalAction, ...],
    successor: DeterministicEvaluationSuccessor,
) -> None:
    if not isinstance(result, SearchResult):
        raise ContractValidationError("strategy did not return SearchResult")
    if result.initial_state_id != root.state_id:
        raise ContractValidationError("strategy result root differs")
    if result.receipt.strategy_version != identity.strategy_id:
        raise ContractValidationError("strategy receipt version differs from config")
    if result.receipt.budget != profile.budget:
        raise ContractValidationError("strategy receipt budget differs from profile")
    # Harness rejects even receipts that label an overrun as budget exhaustion.
    profile.budget.enforce(result.receipt.usage)
    if successor.attempt_count > profile.max_successor_observations:
        raise ContractValidationError("strategy attempted excess successor work")
    if successor.completed_count > profile.max_successor_observations:
        raise ContractValidationError("strategy completed excess successor work")
    usage = EvaluationResourceUsage.from_search_usage(
        initial=root.budget_usage,
        final=result.receipt.usage,
        successor_evaluations=successor.completed_count,
        policy_evaluations=0,
        value_evaluations=0,
    )
    if usage.nodes != successor.completed_count or usage.expansions != successor.completed_count:
        raise ContractValidationError("receipt work differs from observed successor calls")
    if any(state_id != root.state_id for state_id in successor.input_state_ids):
        raise ContractValidationError("successor evaluator received a descendant")
    legal_ids = {action.action_id for action in legal_actions}
    if result.selected_action is not None and result.selected_action.action_id not in legal_ids:
        raise ContractValidationError("strategy selected an illegal action")


async def evaluate_run(
    identity: EvaluationIdentity,
    *,
    case_set: EvaluationCaseSet = FROZEN_SEARCH_KERNEL_CASE_SET,
) -> SearchKernelEvaluationRun:
    results = tuple(
        [await evaluate_case(case, identity) for case in case_set.cases]
    )
    aggregate = _metrics(results)
    categories = tuple(
        _metrics(
            tuple(item for item in results if item.category is category),
            category=category,
        )
        for category in EvaluationCategory
    )
    receipts = tuple(
        sorted(
            {
                receipt
                for item in results
                for receipt in (item.search_receipt_id, item.puct_receipt_id)
                if receipt is not None
            }
        )
    )
    return SearchKernelEvaluationRun(
        identity=identity,
        case_set_digest=case_set.case_set_digest,
        aggregate_metrics=aggregate,
        category_metrics=categories,
        per_case_results=results,
        receipt_refs=receipts,
    )


async def evaluate_frozen_matrix() -> SearchKernelBenchmarkArtifact:
    runs = tuple([await evaluate_run(identity) for identity in FROZEN_EVALUATION_MATRIX])
    run_by_eval = {run.identity.evaluation_id: run for run in runs}
    primary = tuple(
        run_by_eval[evaluation_id].run_id
        for evaluation_id in PRIMARY_MATCHED_CONFIG_IDS
    )
    frontier = pareto_frontier(
        tuple(run_by_eval[evaluation_id] for evaluation_id in PRIMARY_PARETO_CONFIG_IDS)
    )
    return SearchKernelBenchmarkArtifact(
        case_set_digest=FROZEN_SEARCH_KERNEL_CASE_SET.case_set_digest,
        runs=runs,
        primary_matched_run_ids=primary,
        pareto_frontier_run_ids=tuple(run.run_id for run in frontier),
        trace_observability=TraceObservability(
            traces_total=2,
            traces_evaluable=0,
            traces_missing_counterfactual=2,
            missing_fixture_ids=TRACE_FIXTURE_IDS,
        ),
        disclaimer=(
            "Deterministic SEARCH-KERNEL EVALUATION over frozen one-ply fixtures. "
            "It is not end-to-end evidence that SocratesZero improves CED dialogue."
        ),
    )


def run_frozen_matrix() -> SearchKernelBenchmarkArtifact:
    return asyncio.run(evaluate_frozen_matrix())


def _metrics(
    results: Tuple[SearchKernelCaseResult, ...],
    *,
    category: Optional[EvaluationCategory] = None,
) -> EvaluationMetrics:
    evaluable = tuple(
        item
        for item in results
        if item.status in {EvaluationStatus.COMPLETED, EvaluationStatus.BUDGET_EXHAUSTED}
    )
    failed = tuple(
        item
        for item in results
        if item.status in {EvaluationStatus.STRATEGY_FAILURE, EvaluationStatus.INVALID_FIXTURE}
    )
    not_evaluable = tuple(
        item
        for item in results
        if item.status in {EvaluationStatus.NOT_EVALUABLE, EvaluationStatus.MISSING_COUNTERFACTUAL}
    )
    regrets = tuple(item.regret for item in evaluable if item.regret is not None)
    correct = sum(1 for item in evaluable if item.selected_action_correct)
    return EvaluationMetrics(
        category=category,
        cases_total=len(results),
        cases_evaluable=len(evaluable),
        cases_completed=len(evaluable),
        cases_failed=len(failed),
        cases_not_evaluable=len(not_evaluable),
        correct_count=correct,
        accuracy=(correct / len(evaluable) if evaluable else None),
        total_regret=(math.fsum(regrets) if regrets else None),
        mean_regret=(math.fsum(regrets) / len(regrets) if regrets else None),
        mean_budget_utilization=(
            math.fsum(item.budget_utilization for item in evaluable) / len(evaluable)
            if evaluable
            else None
        ),
        resource_usage=_sum_usage(item.resource_usage for item in results),
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


def _sum_usage(values: Iterable[EvaluationResourceUsage]) -> EvaluationResourceUsage:
    items = tuple(values)
    additive = (
        "successor_evaluations",
        "policy_evaluations",
        "value_evaluations",
        "nodes",
        "expansions",
        "model_calls",
        "tool_calls",
        "tokens",
        "cost_microusd",
        "wall_time_ms",
    )
    return EvaluationResourceUsage(
        **{
            name: sum(getattr(item, name) for item in items)
            for name in additive
        },
        max_depth_observed=max(
            (item.max_depth_observed for item in items), default=0
        ),
    )


def pareto_frontier(
    runs: Tuple[SearchKernelEvaluationRun, ...],
) -> Tuple[SearchKernelEvaluationRun, ...]:
    """Return non-dominated quality/resource points without scalar weighting."""

    def dominates(left: SearchKernelEvaluationRun, right: SearchKernelEvaluationRun) -> bool:
        l = left.aggregate_metrics
        r = right.aggregate_metrics
        if l.accuracy is None or r.accuracy is None:
            return False
        l_regret = l.mean_regret if l.mean_regret is not None else math.inf
        r_regret = r.mean_regret if r.mean_regret is not None else math.inf
        l_usage = l.resource_usage
        r_usage = r.resource_usage
        comparisons = (
            l.accuracy >= r.accuracy,
            l_regret <= r_regret,
            l_usage.successor_evaluations <= r_usage.successor_evaluations,
            l_usage.nodes <= r_usage.nodes,
            l_usage.expansions <= r_usage.expansions,
        )
        strict = (
            l.accuracy > r.accuracy
            or l_regret < r_regret
            or l_usage.successor_evaluations < r_usage.successor_evaluations
            or l_usage.nodes < r_usage.nodes
            or l_usage.expansions < r_usage.expansions
        )
        return all(comparisons) and strict

    frontier = tuple(
        run
        for run in runs
        if not any(other is not run and dominates(other, run) for other in runs)
    )
    return tuple(sorted(frontier, key=lambda item: item.identity.evaluation_id))


__all__ = [
    "CORE_MATCHED_SUCCESSOR_LIMIT",
    "FROZEN_EVALUATION_MATRIX",
    "PRIMARY_MATCHED_CONFIG_IDS",
    "PRIMARY_PARETO_CONFIG_IDS",
    "SEARCH_KERNEL_BENCHMARK_ARTIFACT_VERSION",
    "SEARCH_KERNEL_CLAIM_SCOPE",
    "SEARCH_KERNEL_RESULT_VERSION",
    "TRACE_FIXTURE_IDS",
    "DeterministicEvaluationSuccessor",
    "EvaluationMetrics",
    "SearchKernelBenchmarkArtifact",
    "SearchKernelCaseResult",
    "SearchKernelEvaluationRun",
    "TraceObservability",
    "evaluate_case",
    "evaluate_frozen_matrix",
    "evaluate_run",
    "pareto_frontier",
    "run_frozen_matrix",
]

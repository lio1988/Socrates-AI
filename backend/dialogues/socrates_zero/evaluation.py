"""Frozen offline search-kernel evaluation contracts for SocratesZero.

Phase 5 measures already-frozen strategies.  It does not change search math,
execute a CED action, call a provider, or claim end-to-end dialogue quality.
Resource categories remain separate; no synthetic universal compute unit is
defined.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import (
    BudgetUsage,
    ContractValidationError,
    SearchBudget,
    stable_contract_id,
)
from .policy import (
    HEURISTIC_POLICY_PRIOR_VERSION,
    UNIFORM_POLICY_PRIOR_VERSION,
)
from .puct import PUCT_STRATEGY_VERSION
from .strategy import BEST_OF_N_STRATEGY_VERSION, GREEDY_STRATEGY_VERSION
from .value import (
    HEURISTIC_VALUE_ESTIMATOR_VERSION,
    NEUTRAL_VALUE_ESTIMATOR_VERSION,
)


SEARCH_KERNEL_EVALUATION_CONTRACT_VERSION = (
    "socrateszero-search-kernel-evaluation-contracts/v0"
)
SEARCH_KERNEL_HARNESS_VERSION = "socrateszero-search-kernel-eval-harness/v0"
SEARCH_KERNEL_CASE_SET_VERSION = "socrateszero-search-kernel-case-set/v0"
SEARCH_KERNEL_SUCCESSOR_VERSION = "socrateszero-search-kernel-successor/v0"
SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION = (
    "socrateszero-search-kernel-fixture-projection/v0"
)
SEARCH_KERNEL_CONSTITUTION_VERSION = "socrateszero-search-kernel-constitution/v0"
FIXED_ROTATION_REFERENCE_VERSION = "ced-fixed-rotation-adapter/v0"

MATCHED_SUCCESSOR_BUDGET_VERSION = "matched-successor-budget/v0"
MATCHED_SUCCESSOR_OBSERVATION_LIMITS = (1, 2, 4, 8)


class _FrozenEvaluationContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvaluationCategory(str, Enum):
    POLICY_CORRECT = "policy_correct"
    MISLEADING_POLICY = "misleading_policy"
    BEST_OF_N_SUFFICIENT = "best_of_n_sufficient"
    SELECTIVE_BUDGET_ADVANTAGE = "selective_budget_advantage"
    FLAT_VALUE = "flat_value"
    HEURISTIC_VALUE_INFORMATIVE = "heuristic_value_informative"
    VALUE_UNINFORMATIVE = "value_uninformative"
    BUDGET_EXHAUSTION = "budget_exhaustion"
    SINGLE_LEGAL_MOVE = "single_legal_move"
    EXACT_TIES = "exact_ties"


class EvaluationStatus(str, Enum):
    COMPLETED = "completed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_EVALUABLE = "not_evaluable"
    MISSING_COUNTERFACTUAL = "missing_counterfactual"
    INVALID_FIXTURE = "invalid_fixture"
    STRATEGY_FAILURE = "strategy_failure"


class MatchedBudgetProfile(_FrozenEvaluationContract):
    """One exact maximum of real one-ply successor observations.

    The deterministic fixture performs no provider/tool call and consumes no
    tokens, money, or measured wall-clock time.  One real observation consumes
    exactly one node and one expansion; the root is the initial node.
    """

    schema_version: Literal[
        MATCHED_SUCCESSOR_BUDGET_VERSION
    ] = MATCHED_SUCCESSOR_BUDGET_VERSION
    profile_id: str
    max_successor_observations: int = Field(ge=1)
    budget: SearchBudget

    @model_validator(mode="after")
    def validate_frozen_profile(self) -> "MatchedBudgetProfile":
        expected_id = (
            f"{MATCHED_SUCCESSOR_BUDGET_VERSION}/"
            f"{self.max_successor_observations}"
        )
        if self.profile_id != expected_id:
            raise ContractValidationError(
                "matched budget profile ID does not match observation limit"
            )
        expected_budget = SearchBudget(
            max_nodes=1 + self.max_successor_observations,
            max_expansions=self.max_successor_observations,
            max_model_calls=0,
            max_tool_calls=0,
            max_tokens=0,
            max_cost_microusd=0,
            max_wall_time_ms=0,
            max_depth=1,
        )
        if self.budget != expected_budget:
            raise ContractValidationError(
                "matched budget must encode one root plus exact observation cap"
            )
        return self


def _matched_profile(limit: int) -> MatchedBudgetProfile:
    return MatchedBudgetProfile(
        profile_id=f"{MATCHED_SUCCESSOR_BUDGET_VERSION}/{limit}",
        max_successor_observations=limit,
        budget=SearchBudget(
            max_nodes=1 + limit,
            max_expansions=limit,
            max_model_calls=0,
            max_tool_calls=0,
            max_tokens=0,
            max_cost_microusd=0,
            max_wall_time_ms=0,
            max_depth=1,
        ),
    )


MATCHED_SUCCESSOR_BUDGET_PROFILES: Tuple[MatchedBudgetProfile, ...] = tuple(
    _matched_profile(limit) for limit in MATCHED_SUCCESSOR_OBSERVATION_LIMITS
)


def matched_budget_profile(limit: int) -> MatchedBudgetProfile:
    try:
        return next(
            profile
            for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES
            if profile.max_successor_observations == limit
        )
    except StopIteration as exc:
        raise ContractValidationError(
            f"unsupported frozen successor-observation budget {limit}"
        ) from exc


class EvaluationResourceUsage(_FrozenEvaluationContract):
    """Actual resource vector for one strategy/case run, never a scalar score."""

    successor_evaluations: int = Field(ge=0)
    policy_evaluations: int = Field(ge=0)
    value_evaluations: int = Field(ge=0)
    nodes: int = Field(ge=0)
    expansions: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    tokens: int = Field(ge=0)
    cost_microusd: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    max_depth_observed: int = Field(ge=0)

    @classmethod
    def from_search_usage(
        cls,
        *,
        initial: BudgetUsage,
        final: BudgetUsage,
        successor_evaluations: int,
        policy_evaluations: int,
        value_evaluations: int,
    ) -> "EvaluationResourceUsage":
        additive_fields = (
            "nodes",
            "expansions",
            "model_calls",
            "tool_calls",
            "tokens",
            "cost_microusd",
            "wall_time_ms",
        )
        deltas = {
            name: getattr(final, name) - getattr(initial, name)
            for name in additive_fields
        }
        if any(value < 0 for value in deltas.values()):
            raise ContractValidationError("search usage counters cannot decrease")
        return cls(
            successor_evaluations=successor_evaluations,
            policy_evaluations=policy_evaluations,
            value_evaluations=value_evaluations,
            **deltas,
            max_depth_observed=max(
                0, final.max_depth_observed - initial.max_depth_observed
            ),
        )


class EvaluationIdentity(_FrozenEvaluationContract):
    """Versioned semantic identity shared by future run artifacts."""

    evaluation_id: Optional[str] = None
    harness_id: Literal[SEARCH_KERNEL_HARNESS_VERSION] = SEARCH_KERNEL_HARNESS_VERSION
    case_set_id: Literal[
        SEARCH_KERNEL_CASE_SET_VERSION
    ] = SEARCH_KERNEL_CASE_SET_VERSION
    strategy_id: str
    policy_id: str
    value_id: str
    budget_profile_id: str
    successor_evaluator_id: Literal[
        SEARCH_KERNEL_SUCCESSOR_VERSION
    ] = SEARCH_KERNEL_SUCCESSOR_VERSION
    search_state_projection_id: Literal[
        SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION
    ] = SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION
    constitution_id: Literal[
        SEARCH_KERNEL_CONSTITUTION_VERSION
    ] = SEARCH_KERNEL_CONSTITUTION_VERSION
    legal_vocabulary_id: str

    @model_validator(mode="after")
    def validate_and_identify(self) -> "EvaluationIdentity":
        if not all(
            value.strip()
            for value in (
                self.strategy_id,
                self.policy_id,
                self.value_id,
                self.budget_profile_id,
                self.legal_vocabulary_id,
            )
        ):
            raise ContractValidationError("evaluation identity fields cannot be blank")
        if self.strategy_id not in {
            GREEDY_STRATEGY_VERSION,
            BEST_OF_N_STRATEGY_VERSION,
            PUCT_STRATEGY_VERSION,
        }:
            raise ContractValidationError("evaluation uses an unfrozen strategy")
        if self.policy_id not in {
            UNIFORM_POLICY_PRIOR_VERSION,
            HEURISTIC_POLICY_PRIOR_VERSION,
        }:
            raise ContractValidationError("evaluation uses an unfrozen Policy")
        if self.value_id not in {
            NEUTRAL_VALUE_ESTIMATOR_VERSION,
            HEURISTIC_VALUE_ESTIMATOR_VERSION,
        }:
            raise ContractValidationError("evaluation uses an unfrozen Value")
        if self.budget_profile_id not in {
            profile.profile_id for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES
        }:
            raise ContractValidationError("evaluation uses an unfrozen budget profile")
        payload = self.model_dump(mode="json", exclude={"evaluation_id"})
        expected = stable_contract_id("szevaluation", payload)
        if self.evaluation_id is not None and self.evaluation_id != expected:
            raise ContractValidationError("evaluation_id does not match configuration")
        object.__setattr__(self, "evaluation_id", expected)
        return self


__all__ = [
    "FIXED_ROTATION_REFERENCE_VERSION",
    "MATCHED_SUCCESSOR_BUDGET_PROFILES",
    "MATCHED_SUCCESSOR_BUDGET_VERSION",
    "MATCHED_SUCCESSOR_OBSERVATION_LIMITS",
    "SEARCH_KERNEL_CASE_SET_VERSION",
    "SEARCH_KERNEL_CONSTITUTION_VERSION",
    "SEARCH_KERNEL_EVALUATION_CONTRACT_VERSION",
    "SEARCH_KERNEL_FIXTURE_PROJECTION_VERSION",
    "SEARCH_KERNEL_HARNESS_VERSION",
    "SEARCH_KERNEL_SUCCESSOR_VERSION",
    "EvaluationCategory",
    "EvaluationIdentity",
    "EvaluationResourceUsage",
    "EvaluationStatus",
    "MatchedBudgetProfile",
    "matched_budget_profile",
]

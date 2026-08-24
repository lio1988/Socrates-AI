"""Frozen balanced deterministic case set for search-kernel evaluation v0.

The case object contains evaluator-side ground truth, but strategies never
receive that object.  ``strategy_view()`` exposes only the root, hard-legal
actions, observation blueprints, and precommitted compatible budgets.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Dict, Literal, Optional, Tuple

from pydantic import Field, model_validator

from .contracts import (
    ActionKind,
    ActionParameter,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    SearchState,
    SemanticArtifactRef,
    stable_contract_id,
)
from .evaluation import (
    MATCHED_SUCCESSOR_BUDGET_PROFILES,
    SEARCH_KERNEL_CASE_SET_VERSION,
    EvaluationCategory,
    _FrozenEvaluationContract,
    matched_budget_profile,
)


SEARCH_KERNEL_CASE_SCHEMA_VERSION = "socrateszero-search-kernel-case/v0"
SEARCH_KERNEL_CASE_SET_DIGEST_PREFIX = "szevalcases"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ActionOutcome(_FrozenEvaluationContract):
    action_id: str
    outcome_value: float = Field(ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def validate_value(self) -> "ActionOutcome":
        if not self.action_id.strip():
            raise ContractValidationError("ground-truth action ID cannot be blank")
        if not math.isfinite(self.outcome_value):
            raise ContractValidationError("ground-truth outcome must be finite")
        return self


class EvaluationGroundTruth(_FrozenEvaluationContract):
    """Evaluator-only labels; never part of the strategy-facing view."""

    action_outcomes: Tuple[ActionOutcome, ...]
    optimal_action_ids: Tuple[str, ...] = ()
    canonical_optimal_action_id: Optional[str] = None

    @model_validator(mode="after")
    def canonicalize_and_validate(self) -> "EvaluationGroundTruth":
        outcomes = tuple(sorted(self.action_outcomes, key=lambda item: item.action_id))
        if not outcomes:
            raise ContractValidationError("evaluation ground truth cannot be empty")
        if len({item.action_id for item in outcomes}) != len(outcomes):
            raise ContractValidationError("ground-truth action IDs must be unique")
        best = max(item.outcome_value for item in outcomes)
        optimal = tuple(
            item.action_id for item in outcomes if item.outcome_value == best
        )
        canonical = min(optimal)
        if self.optimal_action_ids and tuple(sorted(self.optimal_action_ids)) != optimal:
            raise ContractValidationError("optimal action IDs differ from outcome values")
        if (
            self.canonical_optimal_action_id is not None
            and self.canonical_optimal_action_id != canonical
        ):
            raise ContractValidationError("canonical optimal action ID is incorrect")
        object.__setattr__(self, "action_outcomes", outcomes)
        object.__setattr__(self, "optimal_action_ids", optimal)
        object.__setattr__(self, "canonical_optimal_action_id", canonical)
        return self

    def outcome_for(self, action_id: str) -> float:
        try:
            return next(
                item.outcome_value
                for item in self.action_outcomes
                if item.action_id == action_id
            )
        except StopIteration as exc:
            raise ContractValidationError(
                f"no ground-truth outcome for action {action_id!r}"
            ) from exc


class SuccessorObservationBlueprint(_FrozenEvaluationContract):
    """Observable transition facts without evaluator-side outcome labels."""

    action_id: str
    contradiction_count: int = Field(default=0, ge=0, le=3)
    unresolved_question_count: int = Field(default=0, ge=0, le=4)

    @model_validator(mode="after")
    def validate_action_id(self) -> "SuccessorObservationBlueprint":
        if not self.action_id.strip():
            raise ContractValidationError("successor blueprint action ID cannot be blank")
        return self


class StrategyCaseView(_FrozenEvaluationContract):
    """Complete fixture input available to the harness, with no ground truth."""

    case_id: str
    root_state: SearchState
    hard_legal_actions: Tuple[LegalAction, ...]
    successor_observations: Tuple[SuccessorObservationBlueprint, ...]
    compatible_budget_profile_ids: Tuple[str, ...]


class EvaluationCase(_FrozenEvaluationContract):
    schema_version: Literal[
        SEARCH_KERNEL_CASE_SCHEMA_VERSION
    ] = SEARCH_KERNEL_CASE_SCHEMA_VERSION
    case_id: Optional[str] = None
    case_name: str
    category: EvaluationCategory
    root_state: SearchState
    hard_legal_actions: Tuple[LegalAction, ...]
    successor_observations: Tuple[SuccessorObservationBlueprint, ...]
    compatible_budget_profile_ids: Tuple[str, ...]
    ground_truth: EvaluationGroundTruth

    @model_validator(mode="after")
    def validate_and_identify(self) -> "EvaluationCase":
        if not self.case_name.strip():
            raise ContractValidationError("evaluation case name cannot be blank")
        if self.root_state.depth != 0 or self.root_state.budget_usage != BudgetUsage(nodes=1):
            raise ContractValidationError("evaluation root must contain only its root node")
        actions = tuple(sorted(self.hard_legal_actions, key=lambda item: item.action_id))
        action_ids = tuple(action.action_id for action in actions)
        if not actions or len(set(action_ids)) != len(action_ids):
            raise ContractValidationError("case hard-legal actions must be nonempty and unique")
        observations = tuple(
            sorted(self.successor_observations, key=lambda item: item.action_id)
        )
        observation_ids = tuple(item.action_id for item in observations)
        truth_ids = tuple(item.action_id for item in self.ground_truth.action_outcomes)
        if observation_ids != action_ids or truth_ids != action_ids:
            raise ContractValidationError(
                "legal actions, successor observations, and ground truth must align"
            )
        frozen_profiles = {
            profile.profile_id for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES
        }
        profiles = tuple(sorted(set(self.compatible_budget_profile_ids)))
        if not profiles or set(profiles) - frozen_profiles:
            raise ContractValidationError("case names an unfrozen budget profile")
        object.__setattr__(self, "hard_legal_actions", actions)
        object.__setattr__(self, "successor_observations", observations)
        object.__setattr__(self, "compatible_budget_profile_ids", profiles)
        payload = self.model_dump(mode="json", exclude={"case_id"})
        expected = stable_contract_id("szevalcase", payload)
        if self.case_id is not None and self.case_id != expected:
            raise ContractValidationError("case_id does not match case semantics")
        object.__setattr__(self, "case_id", expected)
        return self

    def strategy_view(self) -> StrategyCaseView:
        return StrategyCaseView(
            case_id=self.case_id,
            root_state=self.root_state,
            hard_legal_actions=self.hard_legal_actions,
            successor_observations=self.successor_observations,
            compatible_budget_profile_ids=self.compatible_budget_profile_ids,
        )


class EvaluationCaseSet(_FrozenEvaluationContract):
    case_set_id: Literal[SEARCH_KERNEL_CASE_SET_VERSION] = SEARCH_KERNEL_CASE_SET_VERSION
    case_set_digest: Optional[str] = None
    cases: Tuple[EvaluationCase, ...]

    @model_validator(mode="after")
    def validate_balance_and_identify(self) -> "EvaluationCaseSet":
        if len(self.cases) != 20:
            raise ContractValidationError("v0 case set must contain exactly 20 cases")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ContractValidationError("evaluation case IDs must be unique")
        if len({case.case_name for case in self.cases}) != len(self.cases):
            raise ContractValidationError("evaluation case names must be unique")
        counts = Counter(case.category for case in self.cases)
        if set(counts) != set(EvaluationCategory) or any(
            counts[category] != 2 for category in EvaluationCategory
        ):
            raise ContractValidationError(
                "v0 case set requires exactly two cases in every category"
            )
        ordered = tuple(sorted(self.cases, key=lambda item: item.case_name))
        object.__setattr__(self, "cases", ordered)
        expected = stable_contract_id(
            SEARCH_KERNEL_CASE_SET_DIGEST_PREFIX,
            {
                "case_set_id": self.case_set_id,
                "case_ids": [case.case_id for case in ordered],
            },
        )
        if self.case_set_digest is not None and self.case_set_digest != expected:
            raise ContractValidationError("case-set digest does not match cases")
        object.__setattr__(self, "case_set_digest", expected)
        return self


def _artifact(prefix: str, index: int) -> SemanticArtifactRef:
    artifact_id = f"{prefix}_{index}"
    return SemanticArtifactRef(
        artifact_id=artifact_id,
        semantic_digest=_digest(artifact_id),
    )


def _root(*, contradictions: int = 0, questions: int = 0) -> SearchState:
    return SearchState(
        task_kind="search_kernel_evaluation",
        question="Frozen deterministic search-kernel fixture.",
        phase="evaluation",
        active_claims=(_artifact("root_claim", 0),),
        contradictions=tuple(
            _artifact("root_contradiction", index) for index in range(contradictions)
        ),
        unresolved_questions=tuple(
            _artifact("root_question", index) for index in range(questions)
        ),
        budget=matched_budget_profile(8).budget,
        budget_usage=BudgetUsage(nodes=1),
    )


def _action(kind: ActionKind, label: str) -> LegalAction:
    return LegalAction(
        kind=kind,
        parameters=(ActionParameter(name="fixture_action", value=label),),
    )


def _case(
    name: str,
    category: EvaluationCategory,
    *,
    actions: Tuple[LegalAction, ...],
    outcomes: Tuple[float, ...],
    observation_penalties: Tuple[Tuple[int, int], ...],
    root_contradictions: int = 0,
    root_questions: int = 0,
) -> EvaluationCase:
    if not (len(actions) == len(outcomes) == len(observation_penalties)):
        raise ValueError("case fixture vectors must have equal length")
    return EvaluationCase(
        case_name=name,
        category=category,
        root_state=_root(
            contradictions=root_contradictions,
            questions=root_questions,
        ),
        hard_legal_actions=actions,
        successor_observations=tuple(
            SuccessorObservationBlueprint(
                action_id=action.action_id,
                contradiction_count=penalty[0],
                unresolved_question_count=penalty[1],
            )
            for action, penalty in zip(actions, observation_penalties)
        ),
        compatible_budget_profile_ids=tuple(
            profile.profile_id for profile in MATCHED_SUCCESSOR_BUDGET_PROFILES
        ),
        ground_truth=EvaluationGroundTruth(
            action_outcomes=tuple(
                ActionOutcome(action_id=action.action_id, outcome_value=value)
                for action, value in zip(actions, outcomes)
            )
        ),
    )


def _pair(_case_name: str, kinds: Tuple[ActionKind, ...]) -> Tuple[LegalAction, ...]:
    # Strategy-facing actions deliberately carry no case/category label.  The
    # case name is accepted only to keep fixture declarations readable here.
    return tuple(_action(kind, f"branch_{index}") for index, kind in enumerate(kinds))


_EIGHT_KINDS = (
    ActionKind.ASK_SOCRATIC_QUESTION,
    ActionKind.EXPLORE_ALTERNATIVE_HYPOTHESIS,
    ActionKind.PROPOSE_CLAIM,
    ActionKind.RECONSTRUCT,
    ActionKind.REFLECT,
    ActionKind.RUN_ELENCHUS,
    ActionKind.SEEK_EVIDENCE,
    ActionKind.SYNTHESIZE_PARTIAL,
)


def _build_cases() -> Tuple[EvaluationCase, ...]:
    cases = []

    actions = _pair("policy_correct_01", (ActionKind.RUN_ELENCHUS, ActionKind.REFLECT))
    cases.append(_case(
        "policy_correct_01", EvaluationCategory.POLICY_CORRECT,
        actions=actions, outcomes=(0.8, 0.2), observation_penalties=((0, 0), (1, 0)),
        root_contradictions=1,
    ))
    actions = _pair("policy_correct_02", (ActionKind.ASK_SOCRATIC_QUESTION, ActionKind.RECONSTRUCT))
    cases.append(_case(
        "policy_correct_02", EvaluationCategory.POLICY_CORRECT,
        actions=actions, outcomes=(0.7, 0.1), observation_penalties=((0, 0), (0, 1)),
        root_questions=1,
    ))

    actions = _pair("misleading_policy_01", (ActionKind.RUN_ELENCHUS, ActionKind.REFLECT))
    cases.append(_case(
        "misleading_policy_01", EvaluationCategory.MISLEADING_POLICY,
        actions=actions, outcomes=(-0.8, 0.8), observation_penalties=((2, 0), (0, 0)),
        root_contradictions=1,
    ))
    actions = _pair("misleading_policy_02", (ActionKind.ASK_SOCRATIC_QUESTION, ActionKind.RECONSTRUCT))
    cases.append(_case(
        "misleading_policy_02", EvaluationCategory.MISLEADING_POLICY,
        actions=actions, outcomes=(-0.6, 0.6), observation_penalties=((0, 2), (0, 0)),
        root_questions=1,
    ))

    for index, kinds in enumerate((
        (ActionKind.ASK_SOCRATIC_QUESTION, ActionKind.RUN_ELENCHUS, ActionKind.REFLECT, ActionKind.RECONSTRUCT),
        (ActionKind.PROPOSE_CLAIM, ActionKind.SEEK_EVIDENCE, ActionKind.RUN_ELENCHUS, ActionKind.SYNTHESIZE_PARTIAL),
    ), start=1):
        name = f"best_of_n_sufficient_{index:02d}"
        actions = _pair(name, kinds)
        cases.append(_case(
            name, EvaluationCategory.BEST_OF_N_SUFFICIENT,
            actions=actions,
            outcomes=(-0.3, 0.9, 0.2, -0.1) if index == 1 else (0.1, 0.8, -0.4, 0.0),
            observation_penalties=((1, 0), (0, 0), (0, 1), (1, 1)) if index == 1 else ((0, 1), (0, 0), (2, 0), (1, 0)),
            root_contradictions=1,
            root_questions=1,
        ))

    actions = _pair("selective_budget_advantage_01", _EIGHT_KINDS)
    cases.append(_case(
        "selective_budget_advantage_01", EvaluationCategory.SELECTIVE_BUDGET_ADVANTAGE,
        actions=actions,
        outcomes=(0.1, -0.2, 0.0, 0.2, 0.4, 0.9, -0.3, -0.1),
        observation_penalties=((0, 1), (1, 0), (1, 1), (0, 1), (0, 0), (0, 0), (2, 0), (1, 1)),
        root_contradictions=1,
        root_questions=1,
    ))
    actions = _pair("selective_budget_advantage_02", _EIGHT_KINDS)
    cases.append(_case(
        "selective_budget_advantage_02", EvaluationCategory.SELECTIVE_BUDGET_ADVANTAGE,
        actions=actions,
        outcomes=(-0.1, 0.0, 0.85, 0.2, 0.3, -0.4, 0.1, -0.2),
        observation_penalties=((0, 1), (1, 0), (0, 0), (0, 1), (0, 0), (2, 0), (1, 0), (1, 1)),
        root_contradictions=1,
        root_questions=1,
    ))

    for index, best_low_prior in enumerate((False, True), start=1):
        name = f"flat_value_{index:02d}"
        actions = _pair(name, (ActionKind.RUN_ELENCHUS, ActionKind.REFLECT, ActionKind.RECONSTRUCT))
        outcomes = (0.8, 0.2, 0.0) if not best_low_prior else (-0.2, 0.1, 0.8)
        cases.append(_case(
            name, EvaluationCategory.FLAT_VALUE,
            actions=actions, outcomes=outcomes,
            observation_penalties=((0, 0), (0, 0), (0, 0)),
            root_contradictions=1,
        ))

    for index in (1, 2):
        name = f"heuristic_value_informative_{index:02d}"
        actions = _pair(name, (ActionKind.ASK_SOCRATIC_QUESTION, ActionKind.PROPOSE_CLAIM, ActionKind.REFLECT, ActionKind.RUN_ELENCHUS))
        cases.append(_case(
            name, EvaluationCategory.HEURISTIC_VALUE_INFORMATIVE,
            actions=actions,
            outcomes=(0.1, 0.9, -0.3, -0.7) if index == 1 else (-0.4, 0.8, 0.2, -0.6),
            observation_penalties=((0, 1), (0, 0), (1, 0), (2, 0)) if index == 1 else ((1, 0), (0, 0), (0, 1), (2, 0)),
            root_questions=1,
        ))

    for index in (1, 2):
        name = f"value_uninformative_{index:02d}"
        actions = _pair(name, (ActionKind.ASK_SOCRATIC_QUESTION, ActionKind.PROPOSE_CLAIM, ActionKind.REFLECT, ActionKind.RUN_ELENCHUS))
        cases.append(_case(
            name, EvaluationCategory.VALUE_UNINFORMATIVE,
            actions=actions,
            outcomes=(-0.5, 0.7, 0.1, 0.0) if index == 1 else (0.2, -0.3, 0.8, 0.1),
            observation_penalties=((0, 0), (0, 0), (0, 0), (0, 0)),
            root_contradictions=index - 1,
            root_questions=2 - index,
        ))

    for index in (1, 2):
        name = f"budget_exhaustion_{index:02d}"
        actions = _pair(name, _EIGHT_KINDS)
        cases.append(_case(
            name, EvaluationCategory.BUDGET_EXHAUSTION,
            actions=actions,
            outcomes=(0.8, 0.4, 0.2, 0.0, -0.1, -0.2, -0.3, -0.4) if index == 1 else (-0.3, -0.2, -0.1, 0.0, 0.2, 0.4, 0.6, 0.8),
            observation_penalties=((0, 0), (0, 1), (1, 0), (1, 1), (0, 0), (2, 0), (0, 2), (1, 1)),
            root_contradictions=1,
            root_questions=1,
        ))

    for index, kind in enumerate((ActionKind.RUN_ELENCHUS, ActionKind.RECONSTRUCT), start=1):
        name = f"single_legal_move_{index:02d}"
        actions = _pair(name, (kind,))
        cases.append(_case(
            name, EvaluationCategory.SINGLE_LEGAL_MOVE,
            actions=actions, outcomes=(0.5,), observation_penalties=((0, 0),),
            root_contradictions=index - 1,
        ))

    for index in (1, 2):
        name = f"exact_ties_{index:02d}"
        actions = _pair(name, (ActionKind.PROPOSE_CLAIM, ActionKind.RECONSTRUCT, ActionKind.SEEK_EVIDENCE))
        cases.append(_case(
            name, EvaluationCategory.EXACT_TIES,
            actions=actions, outcomes=(0.25, 0.25, 0.25),
            observation_penalties=((0, 0), (0, 0), (0, 0)),
        ))

    return tuple(cases)


FROZEN_SEARCH_KERNEL_CASE_SET = EvaluationCaseSet(cases=_build_cases())


__all__ = [
    "FROZEN_SEARCH_KERNEL_CASE_SET",
    "SEARCH_KERNEL_CASE_SCHEMA_VERSION",
    "SEARCH_KERNEL_CASE_SET_DIGEST_PREFIX",
    "ActionOutcome",
    "EvaluationCase",
    "EvaluationCaseSet",
    "EvaluationGroundTruth",
    "StrategyCaseView",
    "SuccessorObservationBlueprint",
]

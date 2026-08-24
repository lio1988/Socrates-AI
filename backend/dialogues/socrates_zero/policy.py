"""Deterministic, model-free priors over an already-legal action set.

Policy ranks supplied legal actions.  It does not generate actions, decide
legality, call a provider, estimate state value, or execute a selection.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Sequence, Tuple

from .constitution import CEDSearchConstitution
from .contracts import (
    ActionKind,
    ActionPrior,
    ActionTargetKind,
    ContractValidationError,
    LegalAction,
    SearchState,
    validate_action_references,
)


HEURISTIC_POLICY_PRIOR_VERSION = "heuristic-policy-prior/v0"
UNIFORM_POLICY_PRIOR_VERSION = "uniform-policy-prior/v0"
HEURISTIC_POLICY_MIN_PROBABILITY = 1e-6
_NORMALIZATION_TOLERANCE = 1e-12


@dataclass(frozen=True)
class PolicyAdjustment:
    """One public, structured reason why an action's raw weight changed."""

    reason_code: str
    delta: float


@dataclass(frozen=True)
class PolicyActionAudit:
    """Inspectable v0 score attribution; never authority-bearing reasoning."""

    action_id: str
    action_kind: ActionKind
    base_weight: float
    adjustments: Tuple[PolicyAdjustment, ...]
    final_weight: float
    normalized_probability: float


def _canonical_actions(
    state: SearchState,
    legal_actions: Sequence[LegalAction],
) -> Tuple[LegalAction, ...]:
    """Validate supplied actions without re-deciding their constitutional status."""
    actions = tuple(legal_actions)
    if any(not isinstance(action, LegalAction) for action in actions):
        raise ContractValidationError("policy input must contain only LegalAction values")
    action_ids = tuple(action.action_id for action in actions)
    if len(set(action_ids)) != len(action_ids):
        raise ContractValidationError("policy input contains duplicate action IDs")
    ordered = tuple(
        sorted(actions, key=CEDSearchConstitution.action_order_key)
    )
    for action in ordered:
        validate_action_references(state, action)
    return ordered


def _normalize_weights(
    weights: Sequence[float],
    *,
    minimum_probability: float,
) -> Tuple[float, ...]:
    """Normalize in canonical order while reserving exploration probability."""
    values = tuple(weights)
    if not values:
        return ()
    if len(values) == 1:
        value = values[0]
        if not math.isfinite(value):
            raise ContractValidationError("policy raw weight must be finite")
        if value <= 0.0:
            raise ContractValidationError("policy raw weight must be positive")
        return (1.0,)
    if not math.isfinite(minimum_probability) or minimum_probability < 0.0:
        raise ContractValidationError("policy minimum probability must be finite and non-negative")
    reserved = len(values) * minimum_probability
    if reserved >= 1.0:
        raise ContractValidationError("policy minimum probability leaves no mass to normalize")
    if any(not math.isfinite(value) for value in values):
        raise ContractValidationError("policy raw weight must be finite")
    if any(value <= 0.0 for value in values):
        raise ContractValidationError("policy raw weight must be positive")
    total = math.fsum(values)
    if not math.isfinite(total) or total <= 0.0:
        raise ContractValidationError("policy normalization total must be finite and positive")

    distributable = 1.0 - reserved
    probabilities = [
        minimum_probability + distributable * (value / total)
        for value in values
    ]
    probabilities[-1] += 1.0 - math.fsum(probabilities)
    if any(not math.isfinite(value) for value in probabilities):
        raise ContractValidationError("normalized policy probability must be finite")
    if any(value < minimum_probability for value in probabilities):
        raise ContractValidationError("normalized policy violated its exploration floor")
    if not math.isclose(
        math.fsum(probabilities),
        1.0,
        rel_tol=0.0,
        abs_tol=_NORMALIZATION_TOLERANCE,
    ):
        raise ContractValidationError("policy probabilities failed normalization")
    return tuple(probabilities)


class UniformPolicyPrior:
    """Reference policy assigning identical mass to every supplied action."""

    name = "uniform_policy_prior"
    version = UNIFORM_POLICY_PRIOR_VERSION

    def evaluate(
        self,
        state: SearchState,
        legal_actions: Sequence[LegalAction],
    ) -> Tuple[PolicyActionAudit, ...]:
        actions = _canonical_actions(state, legal_actions)
        probabilities = _normalize_weights(
            (1.0,) * len(actions), minimum_probability=0.0
        )
        return tuple(
            PolicyActionAudit(
                action_id=action.action_id,
                action_kind=action.kind,
                base_weight=1.0,
                adjustments=(),
                final_weight=1.0,
                normalized_probability=probability,
            )
            for action, probability in zip(actions, probabilities)
        )

    async def priors(
        self,
        state: SearchState,
        legal_actions: Sequence[LegalAction],
    ) -> Tuple[ActionPrior, ...]:
        return tuple(
            ActionPrior(
                action_id=audit.action_id,
                probability=audit.normalized_probability,
            )
            for audit in self.evaluate(state, legal_actions)
        )


class HeuristicPolicyPrior:
    """Small transparent v0 preference model over canonical legal actions."""

    name = "heuristic_policy_prior"
    version = HEURISTIC_POLICY_PRIOR_VERSION
    minimum_probability = HEURISTIC_POLICY_MIN_PROBABILITY
    base_weight = 1.0

    contradiction_adjustments: Mapping[ActionKind, float] = MappingProxyType(
        {
            ActionKind.RUN_ELENCHUS: 1.0,
            ActionKind.CHALLENGE_CLAIM: 0.75,
        }
    )
    unresolved_question_adjustments: Mapping[ActionKind, float] = MappingProxyType(
        {
            ActionKind.ASK_SOCRATIC_QUESTION: 0.75,
            ActionKind.RUN_ELENCHUS: 0.5,
            ActionKind.CHALLENGE_CLAIM: 0.5,
            ActionKind.REFLECT: 0.5,
        }
    )
    canonical_claim_target_adjustments: Mapping[ActionKind, float] = MappingProxyType(
        {
            ActionKind.CHALLENGE_CLAIM: 0.25,
            ActionKind.DEFEND_CLAIM: 0.25,
        }
    )

    @staticmethod
    def _append_adjustment(
        adjustments: list[PolicyAdjustment],
        *,
        reason_code: str,
        action: LegalAction,
        weights: Mapping[ActionKind, float],
    ) -> None:
        delta = weights.get(action.kind)
        if delta is not None:
            adjustments.append(PolicyAdjustment(reason_code, delta))

    def _adjustments(
        self,
        state: SearchState,
        action: LegalAction,
    ) -> Tuple[PolicyAdjustment, ...]:
        adjustments: list[PolicyAdjustment] = []
        if state.contradictions:
            self._append_adjustment(
                adjustments,
                reason_code="unresolved_contradiction",
                action=action,
                weights=self.contradiction_adjustments,
            )
        if state.unresolved_questions:
            self._append_adjustment(
                adjustments,
                reason_code="unresolved_question",
                action=action,
                weights=self.unresolved_question_adjustments,
            )
        if (
            action.target_kind is ActionTargetKind.CLAIM
            and action.target_id in state.target_ids(ActionTargetKind.CLAIM)
        ):
            self._append_adjustment(
                adjustments,
                reason_code="canonical_claim_target",
                action=action,
                weights=self.canonical_claim_target_adjustments,
            )
        return tuple(adjustments)

    def evaluate(
        self,
        state: SearchState,
        legal_actions: Sequence[LegalAction],
    ) -> Tuple[PolicyActionAudit, ...]:
        actions = _canonical_actions(state, legal_actions)
        scored = []
        for action in actions:
            adjustments = self._adjustments(state, action)
            deltas = tuple(adjustment.delta for adjustment in adjustments)
            if not math.isfinite(self.base_weight):
                raise ContractValidationError("policy base weight must be finite")
            if any(not math.isfinite(delta) for delta in deltas):
                raise ContractValidationError("policy adjustment must be finite")
            final_weight = self.base_weight + math.fsum(deltas)
            if not math.isfinite(final_weight):
                raise ContractValidationError("policy raw weight must be finite")
            if final_weight <= 0.0:
                raise ContractValidationError("policy raw weight must be positive")
            scored.append((action, adjustments, final_weight))

        probabilities = _normalize_weights(
            tuple(item[2] for item in scored),
            minimum_probability=self.minimum_probability,
        )
        return tuple(
            PolicyActionAudit(
                action_id=action.action_id,
                action_kind=action.kind,
                base_weight=self.base_weight,
                adjustments=adjustments,
                final_weight=final_weight,
                normalized_probability=probability,
            )
            for (action, adjustments, final_weight), probability in zip(
                scored, probabilities
            )
        )

    async def priors(
        self,
        state: SearchState,
        legal_actions: Sequence[LegalAction],
    ) -> Tuple[ActionPrior, ...]:
        return tuple(
            ActionPrior(
                action_id=audit.action_id,
                probability=audit.normalized_probability,
            )
            for audit in self.evaluate(state, legal_actions)
        )


__all__ = [
    "HEURISTIC_POLICY_MIN_PROBABILITY",
    "HEURISTIC_POLICY_PRIOR_VERSION",
    "UNIFORM_POLICY_PRIOR_VERSION",
    "HeuristicPolicyPrior",
    "PolicyActionAudit",
    "PolicyAdjustment",
    "UniformPolicyPrior",
]

"""Deterministic, model-free, leakage-safe state-value baselines.

Value consumes one current SearchState.  It does not inspect future episode
data, rank actions, decide legality, call providers, or execute protocol steps.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Tuple

from pydantic import ValidationError

from .contracts import (
    ContractValidationError,
    SearchState,
    TerminalStatus,
    stable_contract_id,
)


NEUTRAL_VALUE_ESTIMATOR_VERSION = "neutral-value-estimator/v0"
HEURISTIC_VALUE_ESTIMATOR_VERSION = "heuristic-value-estimator/v0"
VALUE_MIN = -1.0
VALUE_MAX = 1.0

HEURISTIC_VALUE_RULES_V0: Mapping[str, float] = MappingProxyType(
    {
        "unresolved_contradiction_per_record": -0.08,
        "unresolved_contradiction_floor": -0.24,
        "unresolved_question_per_record": -0.05,
        "unresolved_question_floor": -0.20,
        "terminal_blocked": -0.20,
        "terminal_budget_exhausted": -0.10,
    }
)


@dataclass(frozen=True)
class ValueComponent:
    """One structured, public contribution to heuristic Value."""

    reason_code: str
    contribution: float
    canonical_refs: Tuple[str, ...] = ()

    def identity_payload(self) -> dict[str, object]:
        return {
            "reason_code": self.reason_code,
            "contribution": self.contribution,
            "canonical_refs": list(self.canonical_refs),
        }


@dataclass(frozen=True)
class ValueAudit:
    """Deterministic attribution record suitable for a future receipt link."""

    audit_id: str
    estimator_name: str
    estimator_version: str
    state_id: str
    base_value: float
    components: Tuple[ValueComponent, ...]
    raw_value: float
    bounded_value: float


def _validated_state(state: SearchState) -> SearchState:
    if not isinstance(state, SearchState):
        raise ContractValidationError("value estimator requires a SearchState")
    try:
        validated = SearchState.model_validate(state.model_dump(mode="python"))
    except (ValidationError, ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            "value estimator requires a valid SearchState"
        ) from exc

    complete = validated.phase == "complete"
    status = validated.terminal_status
    if status in {
        TerminalStatus.ANSWER_READY,
        TerminalStatus.ABSTAINED,
        TerminalStatus.BLOCKED,
    } and not complete:
        raise ContractValidationError(
            f"{status.value} terminal state must be in complete phase"
        )
    if complete and status is TerminalStatus.NON_TERMINAL:
        raise ContractValidationError("complete state cannot be non-terminal")
    return validated


def _bounded(value: float) -> float:
    if not math.isfinite(value):
        raise ContractValidationError("heuristic value must be finite")
    return max(VALUE_MIN, min(VALUE_MAX, value))


def _make_audit(
    *,
    estimator_name: str,
    estimator_version: str,
    state: SearchState,
    base_value: float,
    components: Tuple[ValueComponent, ...],
) -> ValueAudit:
    contributions = tuple(component.contribution for component in components)
    if not math.isfinite(base_value):
        raise ContractValidationError("value base must be finite")
    if any(not math.isfinite(value) for value in contributions):
        raise ContractValidationError("value component contribution must be finite")
    raw_value = math.fsum((base_value, *contributions))
    bounded_value = _bounded(raw_value)
    payload = {
        "estimator_name": estimator_name,
        "estimator_version": estimator_version,
        "state_id": state.state_id,
        "base_value": base_value,
        "components": [component.identity_payload() for component in components],
        "raw_value": raw_value,
        "bounded_value": bounded_value,
    }
    return ValueAudit(
        audit_id=stable_contract_id("szvalueaudit", payload),
        estimator_name=estimator_name,
        estimator_version=estimator_version,
        state_id=state.state_id,
        base_value=base_value,
        components=components,
        raw_value=raw_value,
        bounded_value=bounded_value,
    )


class NeutralValueEstimator:
    """Scientific control returning neutral Value for every valid state."""

    name = "neutral_value_estimator"
    version = NEUTRAL_VALUE_ESTIMATOR_VERSION

    def evaluate(self, state: SearchState) -> ValueAudit:
        validated = _validated_state(state)
        return _make_audit(
            estimator_name=self.name,
            estimator_version=self.version,
            state=validated,
            base_value=0.0,
            components=(),
        )

    async def estimate(self, state: SearchState) -> float:
        return self.evaluate(state).bounded_value


class HeuristicValueEstimator:
    """Conservative v0 penalty model over explicit unresolved state only."""

    name = "heuristic_value_estimator"
    version = HEURISTIC_VALUE_ESTIMATOR_VERSION
    base_value = 0.0

    unresolved_contradiction_per_record = HEURISTIC_VALUE_RULES_V0[
        "unresolved_contradiction_per_record"
    ]
    unresolved_contradiction_floor = HEURISTIC_VALUE_RULES_V0[
        "unresolved_contradiction_floor"
    ]
    unresolved_question_per_record = HEURISTIC_VALUE_RULES_V0[
        "unresolved_question_per_record"
    ]
    unresolved_question_floor = HEURISTIC_VALUE_RULES_V0[
        "unresolved_question_floor"
    ]
    terminal_blocked = HEURISTIC_VALUE_RULES_V0["terminal_blocked"]
    terminal_budget_exhausted = HEURISTIC_VALUE_RULES_V0[
        "terminal_budget_exhausted"
    ]

    @staticmethod
    def _capped_penalty(
        count: int,
        *,
        per_record: float,
        floor: float,
    ) -> float:
        if not math.isfinite(per_record) or not math.isfinite(floor):
            raise ContractValidationError("heuristic value coefficient must be finite")
        if per_record > 0.0 or floor > 0.0:
            raise ContractValidationError(
                "heuristic v0 penalty coefficients must be non-positive"
            )
        return max(floor, per_record * count)

    def _components(self, state: SearchState) -> Tuple[ValueComponent, ...]:
        components = []
        if state.contradictions:
            components.append(
                ValueComponent(
                    reason_code="unresolved_contradiction",
                    contribution=self._capped_penalty(
                        len(state.contradictions),
                        per_record=self.unresolved_contradiction_per_record,
                        floor=self.unresolved_contradiction_floor,
                    ),
                    canonical_refs=tuple(
                        item.artifact_id for item in state.contradictions
                    ),
                )
            )
        if state.unresolved_questions:
            components.append(
                ValueComponent(
                    reason_code="unresolved_question",
                    contribution=self._capped_penalty(
                        len(state.unresolved_questions),
                        per_record=self.unresolved_question_per_record,
                        floor=self.unresolved_question_floor,
                    ),
                    canonical_refs=tuple(
                        item.artifact_id for item in state.unresolved_questions
                    ),
                )
            )

        if state.terminal_status is TerminalStatus.ANSWER_READY:
            components.append(
                ValueComponent("answer_ready_is_not_verification", 0.0)
            )
        elif state.terminal_status is TerminalStatus.ABSTAINED:
            components.append(ValueComponent("epistemic_abstention", 0.0))
        elif state.terminal_status is TerminalStatus.BLOCKED:
            components.append(
                ValueComponent("terminal_blocked", self.terminal_blocked)
            )
        elif state.terminal_status is TerminalStatus.BUDGET_EXHAUSTED:
            components.append(
                ValueComponent(
                    "terminal_budget_exhausted",
                    self.terminal_budget_exhausted,
                )
            )
        return tuple(components)

    def evaluate(self, state: SearchState) -> ValueAudit:
        validated = _validated_state(state)
        components = self._components(validated)
        if any(component.contribution > 0.0 for component in components):
            raise ContractValidationError(
                "heuristic v0 components must not manufacture positive support"
            )
        return _make_audit(
            estimator_name=self.name,
            estimator_version=self.version,
            state=validated,
            base_value=self.base_value,
            components=components,
        )

    async def estimate(self, state: SearchState) -> float:
        return self.evaluate(state).bounded_value


__all__ = [
    "HEURISTIC_VALUE_ESTIMATOR_VERSION",
    "HEURISTIC_VALUE_RULES_V0",
    "NEUTRAL_VALUE_ESTIMATOR_VERSION",
    "VALUE_MAX",
    "VALUE_MIN",
    "HeuristicValueEstimator",
    "NeutralValueEstimator",
    "ValueAudit",
    "ValueComponent",
]

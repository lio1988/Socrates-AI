"""Deterministic penalty-only Value v1 over canonical SearchState v1.

The estimator reads a current immutable projection, emits an advisory audit,
and owns no CED, Hybrid, verification, lifecycle, legality, or release authority.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import math
from typing import Dict, Iterable, Mapping, Optional, Set, Tuple

from pydantic import ValidationError

from .ced_search_observability_v1 import (
    SEARCH_STATE_V1_PROJECTION_VERSION,
    SEARCH_STATE_V1_SCHEMA_VERSION,
    CanonicalClaimAssessmentView,
    SearchStateV1,
)
from .ced_search_value_v1_contracts import (
    HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
    HEURISTIC_VALUE_RULES_V1,
    SUPPORT_STATE_REASON_V1,
    SuppressedValueV1Source,
    VALUE_V1_BASE,
    VALUE_V1_MAX,
    VALUE_V1_MIN,
    ValueV1Audit,
    ValueV1Component,
)
from .hybrid_epistemic import SupportState
from .socrates_zero.contracts import (
    ContractValidationError,
    TerminalStatus,
    canonical_json,
)


_TERMINAL_REASON = {
    TerminalStatus.BLOCKED: "terminal_blocked",
    TerminalStatus.BUDGET_EXHAUSTED: "terminal_budget_exhausted",
}


def _validated_state(state: SearchStateV1) -> SearchStateV1:
    if not isinstance(state, SearchStateV1):
        raise ContractValidationError(
            "heuristic Value v1 requires canonical SearchState v1"
        )
    try:
        validated = SearchStateV1.model_validate(state.model_dump(mode="python"))
    except (ValidationError, ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            "heuristic Value v1 requires a valid SearchState v1"
        ) from exc

    base = validated.base_state
    complete = base.phase == "complete"
    if base.terminal_status in {
        TerminalStatus.ANSWER_READY,
        TerminalStatus.ABSTAINED,
        TerminalStatus.BLOCKED,
    } and not complete:
        raise ContractValidationError(
            f"{base.terminal_status.value} terminal state must be complete"
        )
    if complete and base.terminal_status is TerminalStatus.NON_TERMINAL:
        raise ContractValidationError("complete state cannot be non-terminal")
    if validated.state_id is None or base.state_id is None:
        raise ContractValidationError("canonical state identities are required")
    return validated


def _assessment_id(assessment: CanonicalClaimAssessmentView) -> str:
    if assessment.semantic_digest is None:
        raise ContractValidationError("claim assessment digest is required")
    return f"claim-assessment:{assessment.semantic_digest}"


def _source_index(
    state: SearchStateV1,
) -> Dict[str, Tuple[str, str, Set[str]]]:
    index: Dict[str, Tuple[str, str, Set[str]]] = {}
    for family, collection in (
        ("evidence", state.evidence),
        ("verification", state.verifications),
        ("objection", state.objections),
        ("contradiction", state.contradictions),
    ):
        for item in collection:
            digest = item.semantic_digest
            if digest is None:
                raise ContractValidationError(
                    f"{family} source semantic digest is required"
                )
            if family in {"evidence", "verification"}:
                owners = {item.claim_id}
            elif family == "objection":
                owners = {item.target_claim_id}
            else:
                owners = {item.claim_id_a, item.claim_id_b}
            index[item.source_record_id] = (family, digest, owners)
    return index


def _validate_assessment_sources(
    state: SearchStateV1,
    index: Mapping[str, Tuple[str, str, Set[str]]],
) -> None:
    active_ids = {item.artifact_id for item in state.base_state.active_claims}
    for assessment in state.claim_assessments:
        references = (
            assessment.basis_record_ids
            + assessment.falsifying_record_ids
            + assessment.unresolved_record_ids
        )
        if len(references) != len(set(references)):
            raise ContractValidationError(
                "claim assessment repeats a governing source representation"
            )
        for source_id in references:
            source = index.get(source_id)
            if source is None or assessment.claim_id not in source[2]:
                raise ContractValidationError(
                    "claim assessment source ownership does not match claim"
                )
        if assessment.claim_id in active_ids:
            if (
                assessment.support_state is SupportState.FALSIFIED
                and assessment.eligible_for_assembly
            ):
                raise ContractValidationError(
                    "active falsified claim cannot be eligible for assembly"
                )
            if (
                assessment.support_state is not SupportState.FALSIFIED
                and not assessment.eligible_for_assembly
            ):
                raise ContractValidationError(
                    "active non-falsified claim must remain eligible for assembly"
                )


def _suppressed_for_claim(
    state: SearchStateV1,
    *,
    claim_id: str,
    represented_by_reason: str,
) -> Tuple[SuppressedValueV1Source, ...]:
    suppressed = []
    for family, collection in (
        ("evidence", state.evidence),
        ("verification", state.verifications),
        ("objection", state.objections),
        ("contradiction", state.contradictions),
    ):
        for item in collection:
            related = (
                item.claim_id == claim_id
                if family in {"evidence", "verification"}
                else item.target_claim_id == claim_id
                if family == "objection"
                else claim_id in {item.claim_id_a, item.claim_id_b}
            )
            if related:
                suppressed.append(
                    SuppressedValueV1Source(
                        family=family,
                        source_record_id=item.source_record_id,
                        semantic_digest=item.semantic_digest or "",
                        represented_by_reason=represented_by_reason,
                    )
                )
    return tuple(
        sorted(
            suppressed,
            key=lambda item: (
                item.family,
                item.source_record_id,
                item.semantic_digest,
            ),
        )
    )


def _all_terminal_suppressed(
    state: SearchStateV1, *, represented_by_reason: str
) -> Tuple[SuppressedValueV1Source, ...]:
    suppressed = [
        SuppressedValueV1Source(
            family="claim_assessment",
            source_record_id=item.claim_id,
            semantic_digest=item.semantic_digest or "",
            represented_by_reason=represented_by_reason,
        )
        for item in state.claim_assessments
    ]
    for family, collection in (
        ("evidence", state.evidence),
        ("verification", state.verifications),
        ("objection", state.objections),
        ("contradiction", state.contradictions),
    ):
        suppressed.extend(
            SuppressedValueV1Source(
                family=family,
                source_record_id=item.source_record_id,
                semantic_digest=item.semantic_digest or "",
                represented_by_reason=represented_by_reason,
            )
            for item in collection
        )
    return tuple(
        sorted(
            suppressed,
            key=lambda item: (
                item.family,
                item.source_record_id,
                item.semantic_digest,
            ),
        )
    )


class HeuristicValueEstimatorV1:
    """One-factor current-readiness experiment over canonical observations."""

    name = "heuristic_value_estimator"
    version = HEURISTIC_VALUE_ESTIMATOR_V1_VERSION
    base_value = VALUE_V1_BASE
    rules: Mapping[str, float] = HEURISTIC_VALUE_RULES_V1

    def _validated_rules(self) -> Mapping[str, float]:
        if set(self.rules) != set(HEURISTIC_VALUE_RULES_V1):
            raise ContractValidationError(
                "heuristic Value v1 rule families differ from frozen semantics"
            )
        for reason, value in self.rules.items():
            if not math.isfinite(value):
                raise ContractValidationError(
                    f"heuristic Value v1 rule {reason} must be finite"
                )
            if value > 0.0:
                raise ContractValidationError(
                    "heuristic Value v1 cannot contain a positive component"
                )
        return self.rules

    def _worst_active_assessment(
        self,
        state: SearchStateV1,
        rules: Mapping[str, float],
    ) -> Optional[CanonicalClaimAssessmentView]:
        active_ids = {item.artifact_id for item in state.base_state.active_claims}
        active = tuple(
            item for item in state.claim_assessments if item.claim_id in active_ids
        )
        if not active:
            return None

        def selection_key(item: CanonicalClaimAssessmentView):
            reason = SUPPORT_STATE_REASON_V1[item.support_state]
            contribution = rules[reason] if reason is not None else 0.0
            return contribution, item.claim_id

        return min(active, key=selection_key)

    @staticmethod
    def _bounded(value: float) -> float:
        if not math.isfinite(value):
            raise ContractValidationError("heuristic Value v1 must be finite")
        return max(VALUE_V1_MIN, min(VALUE_V1_MAX, value))

    def evaluate(self, state: SearchStateV1) -> ValueV1Audit:
        validated = _validated_state(state)
        rules = self._validated_rules()
        source_index = _source_index(validated)
        _validate_assessment_sources(validated, source_index)

        components = []
        selected = None
        source_assessment_id = None
        source_claim_id = None
        source_digest = None
        reason_code = None
        suppressed: Tuple[SuppressedValueV1Source, ...] = ()
        terminal = validated.base_state.terminal_status is not TerminalStatus.NON_TERMINAL

        if terminal:
            terminal_reason = _TERMINAL_REASON.get(
                validated.base_state.terminal_status
            )
            represented_reason = terminal_reason or "terminal_neutral_firewall"
            suppressed = _all_terminal_suppressed(
                validated, represented_by_reason=represented_reason
            )
            reason_code = terminal_reason
            if terminal_reason is not None:
                components.append(
                    ValueV1Component(
                        reason_code=terminal_reason,
                        contribution=rules[terminal_reason],
                    )
                )
        else:
            selected = self._worst_active_assessment(validated, rules)
            if selected is not None:
                source_assessment_id = _assessment_id(selected)
                source_claim_id = selected.claim_id
                source_digest = selected.semantic_digest
                claim_reason = SUPPORT_STATE_REASON_V1[selected.support_state]
                represented_reason = (
                    claim_reason or "active_claim_supported_no_bonus"
                )
                reason_code = represented_reason
                suppressed = _suppressed_for_claim(
                    validated,
                    claim_id=selected.claim_id,
                    represented_by_reason=represented_reason,
                )
                if claim_reason is not None:
                    refs = tuple(
                        sorted(
                            {
                                source_assessment_id,
                                selected.claim_id,
                                *selected.basis_record_ids,
                                *selected.falsifying_record_ids,
                                *selected.unresolved_record_ids,
                            }
                        )
                    )
                    components.append(
                        ValueV1Component(
                            reason_code=claim_reason,
                            contribution=rules[claim_reason],
                            canonical_refs=refs,
                        )
                    )

            objection_ids = {
                item.source_record_id for item in validated.objections
            }
            remainder_ids = tuple(
                sorted(
                    item.artifact_id
                    for item in validated.base_state.unresolved_questions
                    if item.artifact_id not in objection_ids
                )
            )
            if remainder_ids:
                components.append(
                    ValueV1Component(
                        reason_code="socratic_remainder_open",
                        contribution=rules["socratic_remainder_open"],
                        canonical_refs=remainder_ids,
                    )
                )
                if reason_code is None:
                    reason_code = "socratic_remainder_open"

        if any(component.contribution > 0.0 for component in components):
            raise ContractValidationError(
                "heuristic Value v1 cannot manufacture positive support"
            )
        raw_value = math.fsum(
            (self.base_value, *(item.contribution for item in components))
        )
        bounded_value = self._bounded(raw_value)
        audit = ValueV1Audit(
            receipt_hash="",
            estimator_id=self.version,
            search_state_version=SEARCH_STATE_V1_SCHEMA_VERSION,
            projection_version=SEARCH_STATE_V1_PROJECTION_VERSION,
            state_id=validated.state_id or "",
            base_state_id=validated.base_state.state_id or "",
            base_value=self.base_value,
            selected_worst_support_state=(
                selected.support_state if selected is not None else None
            ),
            source_claim_assessment_id=source_assessment_id,
            source_claim_id=source_claim_id,
            source_claim_assessment_digest=source_digest,
            reason_code=reason_code,
            components=tuple(components),
            suppressed_sources=suppressed,
            terminal_suppression_status=terminal,
            raw_value=raw_value,
            bounded_value=bounded_value,
        )
        receipt_hash = hashlib.sha256(
            canonical_json(audit.identity_payload()).encode("utf-8")
        ).hexdigest()
        return replace(audit, receipt_hash=receipt_hash)

    async def estimate(self, state: SearchStateV1) -> float:
        return self.evaluate(state).bounded_value


__all__ = ["HeuristicValueEstimatorV1"]

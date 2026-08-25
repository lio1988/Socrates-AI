"""Frozen contracts for the deterministic canonical Value-v1 experiment.

This module declares semantic constants and structured audit records only.  It
does not implement an estimator, inspect evaluator labels, or alter canonical
CED/Hybrid state.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .ced_search_observability_v1 import (
    SEARCH_STATE_V1_PROJECTION_VERSION,
    SEARCH_STATE_V1_SCHEMA_VERSION,
)
from .hybrid_epistemic import SupportState


HEURISTIC_VALUE_ESTIMATOR_V1_VERSION = "heuristic-value-estimator/v1"
VALUE_V1_BASE = 0.0
VALUE_V1_MIN = -1.0
VALUE_V1_MAX = 1.0

HEURISTIC_VALUE_RULES_V1: Mapping[str, float] = MappingProxyType(
    {
        "active_claim_falsified": -0.20,
        "active_claim_external_evidence_required": -0.12,
        "active_claim_unresolved": -0.08,
        "active_claim_unsupported": -0.05,
        "socratic_remainder_open": -0.05,
        "terminal_blocked": -0.20,
        "terminal_budget_exhausted": -0.10,
    }
)

SUPPORT_STATE_REASON_V1: Mapping[SupportState, Optional[str]] = MappingProxyType(
    {
        SupportState.FALSIFIED: "active_claim_falsified",
        SupportState.EXTERNAL_EVIDENCE_REQUIRED:
            "active_claim_external_evidence_required",
        SupportState.UNRESOLVED: "active_claim_unresolved",
        SupportState.UNSUPPORTED: "active_claim_unsupported",
        SupportState.SUPPORTED: None,
    }
)


@dataclass(frozen=True)
class ValueV1Component:
    """One approved, public, non-positive Value-v1 contribution."""

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
class SuppressedValueV1Source:
    """Canonical source represented by a governing non-duplicated signal."""

    family: str
    source_record_id: str
    semantic_digest: str
    represented_by_reason: str

    def identity_payload(self) -> dict[str, str]:
        return {
            "family": self.family,
            "source_record_id": self.source_record_id,
            "semantic_digest": self.semantic_digest,
            "represented_by_reason": self.represented_by_reason,
        }


@dataclass(frozen=True)
class ValueV1Audit:
    """Deterministic public receipt; it contains no prose reasoning."""

    receipt_hash: str
    estimator_id: str
    search_state_version: str
    projection_version: str
    state_id: str
    base_state_id: str
    base_value: float
    selected_worst_support_state: Optional[SupportState]
    source_claim_assessment_id: Optional[str]
    source_claim_id: Optional[str]
    source_claim_assessment_digest: Optional[str]
    reason_code: Optional[str]
    components: Tuple[ValueV1Component, ...]
    suppressed_sources: Tuple[SuppressedValueV1Source, ...]
    terminal_suppression_status: bool
    raw_value: float
    bounded_value: float

    def identity_payload(self) -> dict[str, object]:
        return {
            "estimator_id": self.estimator_id,
            "search_state_version": self.search_state_version,
            "projection_version": self.projection_version,
            "state_id": self.state_id,
            "base_state_id": self.base_state_id,
            "base_value": self.base_value,
            "selected_worst_support_state": (
                self.selected_worst_support_state.value
                if self.selected_worst_support_state is not None
                else None
            ),
            "source_claim_assessment_id": self.source_claim_assessment_id,
            "source_claim_id": self.source_claim_id,
            "source_claim_assessment_digest": self.source_claim_assessment_digest,
            "reason_code": self.reason_code,
            "components": [item.identity_payload() for item in self.components],
            "suppressed_sources": [
                item.identity_payload() for item in self.suppressed_sources
            ],
            "terminal_suppression_status": self.terminal_suppression_status,
            "raw_value": self.raw_value,
            "bounded_value": self.bounded_value,
        }


__all__ = [
    "HEURISTIC_VALUE_ESTIMATOR_V1_VERSION",
    "HEURISTIC_VALUE_RULES_V1",
    "SEARCH_STATE_V1_PROJECTION_VERSION",
    "SEARCH_STATE_V1_SCHEMA_VERSION",
    "SUPPORT_STATE_REASON_V1",
    "SuppressedValueV1Source",
    "VALUE_V1_BASE",
    "VALUE_V1_MAX",
    "VALUE_V1_MIN",
    "ValueV1Audit",
    "ValueV1Component",
]

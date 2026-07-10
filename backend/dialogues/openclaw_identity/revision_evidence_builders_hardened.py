"""Public hardening wrapper for instrument-bound revision evidence builders.

The underlying builders enforce causal attribution and exact schemas. This
wrapper adds numeric finiteness and required-label checks before delegating, so
NaN/Infinity or empty pattern identifiers can never produce trusted evidence.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from .revision_evidence_builders import (
    AGENT_LESSON_AB_REPORT_VERSION,
    IDENTITY_FAILURE_REPORT_VERSION,
    IDENTITY_RESOLUTION_REPORT_VERSION,
    SOUL_ATTESTATION_VERSION,
    build_agent_lesson_ab_evidence as _build_agent_lesson_ab_evidence,
    build_identity_failure_evidence as _build_identity_failure_evidence,
    build_identity_resolution_evidence as _build_identity_resolution_evidence,
    build_soul_attestation_evidence as _build_soul_attestation_evidence,
)


def _mapping(report: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(report, Mapping):
        raise ValueError("instrument report must be a mapping")
    return report


def _nonempty_label(report: Mapping[str, Any], field: str) -> None:
    value = str(report.get(field, "")).strip()
    if not value:
        raise ValueError(f"instrument report {field} must be non-empty")
    if len(value) > 128:
        raise ValueError(f"instrument report {field} exceeds 128 characters")


def _finite_number(report: Mapping[str, Any], field: str) -> None:
    value = report.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError(f"{field} must be finite")


def build_identity_failure_evidence(
    report: Mapping[str, Any],
    *,
    min_occurrences: int = 2,
):
    report = _mapping(report)
    _nonempty_label(report, "pattern_key")
    _nonempty_label(report, "agent_id")
    return _build_identity_failure_evidence(
        report, min_occurrences=min_occurrences)


def build_identity_resolution_evidence(
    report: Mapping[str, Any],
    *,
    min_window: int = 2,
):
    report = _mapping(report)
    _nonempty_label(report, "pattern_key")
    _nonempty_label(report, "agent_id")
    return _build_identity_resolution_evidence(
        report, min_window=min_window)


def build_agent_lesson_ab_evidence(
    report: Mapping[str, Any],
    *,
    action: str,
):
    report = _mapping(report)
    for field in ("mean_score_delta", "harm_rate", "max_harm_rate"):
        _finite_number(report, field)
    _nonempty_label(report, "target_agent_id")
    return _build_agent_lesson_ab_evidence(report, action=action)


def build_soul_attestation_evidence(report: Mapping[str, Any]):
    report = _mapping(report)
    _nonempty_label(report, "agent_id")
    return _build_soul_attestation_evidence(report)


__all__ = [
    "AGENT_LESSON_AB_REPORT_VERSION",
    "IDENTITY_FAILURE_REPORT_VERSION",
    "IDENTITY_RESOLUTION_REPORT_VERSION",
    "SOUL_ATTESTATION_VERSION",
    "build_agent_lesson_ab_evidence",
    "build_identity_failure_evidence",
    "build_identity_resolution_evidence",
    "build_soul_attestation_evidence",
]

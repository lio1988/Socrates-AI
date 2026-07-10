"""
OpenClaw Agent Identity — instrument-fed gate evidence (Goal 13.1).

Version gates consume evidence derived mechanically from existing instruments:
  - trace windows + failure detectors -> failure-count deltas
  - verified Shadow Apprentice records -> shadow section wins
  - Promotion Arena reports -> informational metrics

Honesty rules:
  - a metric no instrument can compute remains absent
  - before/after deltas require two non-empty windows
  - shadow promotion evidence requires a capture-time shadow marker, no explicit
    run failure, and a ratified council target; unratified/failed records remain
    available for analysis but cannot make promotion easier

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from backend.dialogues.openclaw_memory import detect_trace_failures

from .identity_profile import AgentIdentityProfile

_DELTA_KEY = "{lesson_type}_failures_delta"


def _failure_counts(traces: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for trace in traces:
        for observation in detect_trace_failures(trace):
            lesson_type = observation["lesson_type"]
            counts[lesson_type] = counts.get(lesson_type, 0) + 1
    return counts


def evidence_from_trace_windows(
    traces_before: Sequence[Dict[str, Any]],
    traces_after: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Failure-count deltas: after minus before; negative is improvement."""
    if not traces_before or not traces_after:
        return {}
    before = _failure_counts(traces_before)
    after = _failure_counts(traces_after)
    evidence: Dict[str, Any] = {}
    for lesson_type in sorted(set(before) | set(after)):
        evidence[_DELTA_KEY.format(lesson_type=lesson_type)] = (
            after.get(lesson_type, 0) - before.get(lesson_type, 0))
    return evidence


def evidence_from_shadow_profile(
    shadow_profile: AgentIdentityProfile,
) -> Dict[str, Any]:
    """Caller-declared shadow evidence; prefer marker-verified trace evidence."""
    return {
        "shadow_blind_spots_wins": shadow_profile.section_wins.get(
            "blind_spots", 0),
        "shadow_sessions_analyzed": shadow_profile.sessions_analyzed,
    }


def _is_ratified(trace: Dict[str, Any]) -> bool:
    ratification = trace.get("ratification") or {}
    return ratification.get("ratified") is True


def _is_explicit_success(trace: Dict[str, Any]) -> bool:
    # Legacy TraceCapturer shadow records did not carry ``ok``. Absence is
    # accepted for backward compatibility; an explicit False is never eligible.
    return trace.get("ok", True) is True


def evidence_from_shadow_traces(
    agent_id: str,
    traces: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Derive promotion evidence from mechanically eligible shadow records.

    Eligibility requires:
      - ``shadow_run is True`` at capture time
      - the run is not explicitly failed
      - the council target was ratified

    Diagnostics include every excluded marked record so a human can audit why a
    run did not count. Gate metrics are absent when no eligible record exists.
    """
    marked = [trace for trace in traces if trace.get("shadow_run") is True]
    if not marked:
        return {}

    failed = [trace for trace in marked if not _is_explicit_success(trace)]
    unratified = [
        trace for trace in marked
        if _is_explicit_success(trace) and not _is_ratified(trace)
    ]
    eligible = [
        trace for trace in marked
        if _is_explicit_success(trace) and _is_ratified(trace)
    ]

    diagnostics: Dict[str, Any] = {
        "shadow_records_marked": len(marked),
        "shadow_records_eligible": len(eligible),
        "shadow_records_excluded_failed": len(failed),
        "shadow_records_excluded_unratified": len(unratified),
        "shadow_excluded_session_ids": sorted(
            str(trace.get("session_id", ""))
            for trace in failed + unratified
        ),
    }
    if not eligible:
        return diagnostics

    from .identity_profile import build_identity_profile

    profile = build_identity_profile(agent_id, eligible)
    diagnostics.update({
        "shadow_blind_spots_wins": profile.section_wins.get(
            "blind_spots", 0),
        "shadow_sessions_analyzed": profile.sessions_analyzed,
        "shadow_session_ids": sorted(
            str(trace.get("session_id", "")) for trace in eligible),
    })
    return diagnostics


def evidence_from_arena(report: Dict[str, Any]) -> Dict[str, Any]:
    """Informational metrics from a Promotion Arena report."""
    return {
        "arena_win_rate": float(report.get("win_rate", 0.0)),
        "arena_decided": int(report.get("decided", 0)),
        "arena_promote_recommended": 1 if report.get("promote") else 0,
    }


def collect_gate_evidence(
    *,
    traces_before: Optional[Sequence[Dict[str, Any]]] = None,
    traces_after: Optional[Sequence[Dict[str, Any]]] = None,
    shadow_profile: Optional[AgentIdentityProfile] = None,
    shadow_traces: Optional[Sequence[Dict[str, Any]]] = None,
    shadow_agent_id: Optional[str] = None,
    arena_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge available instruments; marker-verified traces override profile data."""
    if (shadow_traces is None) != (shadow_agent_id is None):
        raise ValueError("shadow_traces and shadow_agent_id go together")

    evidence: Dict[str, Any] = {}
    if traces_before is not None and traces_after is not None:
        evidence.update(evidence_from_trace_windows(
            traces_before, traces_after))
    if shadow_profile is not None:
        evidence.update(evidence_from_shadow_profile(shadow_profile))
    if shadow_traces is not None and shadow_agent_id is not None:
        verified = evidence_from_shadow_traces(shadow_agent_id, shadow_traces)
        # Remove caller-declared shadow gate metrics before applying the verified
        # path. If no eligible trace exists, the gate metric must remain absent.
        evidence.pop("shadow_blind_spots_wins", None)
        evidence.pop("shadow_sessions_analyzed", None)
        evidence.update(verified)
    if arena_report is not None:
        evidence.update(evidence_from_arena(arena_report))
    return evidence

"""
OpenClaw Agent Identity — instrument-fed gate evidence (Goal 13.1).

Version gates consume evidence derived mechanically from existing instruments:
  - matched trace windows + failure detectors -> failure-count deltas
  - verified Shadow Apprentice records -> shadow section wins
  - Promotion Arena reports -> informational metrics

Honesty rules:
  - a metric no instrument can compute remains absent
  - before/after failure deltas require equal-size windows and, when every trace
    carries a question, the same question multiset
  - shadow promotion evidence requires a capture-time marker, no explicit run
    failure, and a ratified council target

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

from collections import Counter
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


def _complete_question_multiset(
    traces: Sequence[Dict[str, Any]],
) -> Optional[Counter]:
    questions = [str(trace.get("question", "")).strip() for trace in traces]
    if any(not question for question in questions):
        return None
    return Counter(questions)


def evidence_from_trace_windows(
    traces_before: Sequence[Dict[str, Any]],
    traces_after: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Failure-count deltas over matched windows only.

    A smaller after-window is not evidence of improvement. When both windows
    contain complete trace questions, their question multisets must also match;
    otherwise task-difficulty drift could masquerade as agent improvement.

    Legacy synthetic traces without questions remain supported only when window
    sizes match. Invalid windows emit diagnostics but no gate metric.
    """
    if not traces_before or not traces_after:
        return {}
    if len(traces_before) != len(traces_after):
        return {
            "trace_window_match": False,
            "trace_window_mismatch_reason": "different_window_sizes",
            "trace_window_before_count": len(traces_before),
            "trace_window_after_count": len(traces_after),
        }

    before_questions = _complete_question_multiset(traces_before)
    after_questions = _complete_question_multiset(traces_after)
    if (
        before_questions is not None
        and after_questions is not None
        and before_questions != after_questions
    ):
        return {
            "trace_window_match": False,
            "trace_window_mismatch_reason": "different_question_multisets",
            "trace_window_before_count": len(traces_before),
            "trace_window_after_count": len(traces_after),
        }

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

    Eligibility requires ``shadow_run is True``, no explicit failure, and a
    ratified council target. Diagnostics explain every excluded marked record.
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
        evidence.pop("shadow_blind_spots_wins", None)
        evidence.pop("shadow_sessions_analyzed", None)
        evidence.update(verified)
    if arena_report is not None:
        evidence.update(evidence_from_arena(arena_report))
    return evidence

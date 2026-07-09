"""
OpenClaw Agent Identity — instrument-fed gate evidence (Goal 13.1).

Version gates consume an evidence dict. In v0 the operator assembled that
dict by hand; this module derives it mechanically from instruments that
already exist on this branch:

  - Goal 5 traces + Goal 6 failure detectors → failure-count deltas between
    a BEFORE and an AFTER window (gates v0.1→v0.2, v0.2→v0.3)
  - a profile built from declared SHADOW-run traces → shadow section wins
    (gate v0.3→v0.4)
  - a Promotion Arena report → informational arena metrics (future gates)

Honesty rules, mechanically kept:
  - A metric no instrument can compute is simply ABSENT — and an absent
    metric fails its gate honestly (evaluate_gate). Today no detector
    observes unsupported claims from traces alone, so
    ``unsupported_claim_failures_delta`` is never emitted; that gate cannot
    pass until a real instrument exists. This is by design.
  - Deltas need both windows non-empty: comparing something to nothing is
    not evidence of improvement.
  - Shadow semantics are DECLARED by the caller (the trace format does not
    yet mark shadow runs): pass only shadow-run traces as the shadow
    profile. The function cannot verify the declaration — the approver can,
    because session ids travel with the profile.

Pure, deterministic, offline. No provider calls, no network, no keys.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from backend.dialogues.openclaw_memory import detect_trace_failures

from .identity_profile import AgentIdentityProfile

#: evidence key template shared with promotion_policy gate metrics.
_DELTA_KEY = "{lesson_type}_failures_delta"


def _failure_counts(traces: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for trace in traces:
        for obs in detect_trace_failures(trace):
            lt = obs["lesson_type"]
            counts[lt] = counts.get(lt, 0) + 1
    return counts


def evidence_from_trace_windows(
    traces_before: Sequence[Dict[str, Any]],
    traces_after: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Failure-count deltas per lesson type: after − before (negative = the
    failures went DOWN, which is what the reduction gates require). Emits a
    delta only for lesson types observed in at least one window; emits
    nothing at all when either window is empty."""
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
    """Shadow-mode evidence from a profile the CALLER built over declared
    shadow-run traces. Session ids stay auditable inside the profile.

    Prefer :func:`evidence_from_shadow_traces` when traces carry the
    capture-time ``shadow_run`` marker — there the shadow claim is verified
    mechanically instead of trusted."""
    return {
        "shadow_blind_spots_wins": shadow_profile.section_wins.get(
            "blind_spots", 0),
        "shadow_sessions_analyzed": shadow_profile.sessions_analyzed,
    }


def evidence_from_shadow_traces(
    agent_id: str,
    traces: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Shadow-mode evidence VERIFIED by the capture-time marker.

    Filters to traces whose ``shadow_run`` field is exactly True (set by
    ``TraceCapturer(shadow_run=True)`` when the session ran) — an unmarked
    trace is never counted as shadow, no matter what the caller believes.
    The counted session ids travel with the evidence so the approver can
    audit precisely which shadow runs backed a promotion. Empty when no
    marked traces exist (the gate then fails honestly)."""
    shadow = [t for t in traces if t.get("shadow_run") is True]
    if not shadow:
        return {}
    from .identity_profile import build_identity_profile
    profile = build_identity_profile(agent_id, shadow)
    return {
        "shadow_blind_spots_wins": profile.section_wins.get("blind_spots", 0),
        "shadow_sessions_analyzed": profile.sessions_analyzed,
        "shadow_session_ids": sorted(
            str(t.get("session_id", "")) for t in shadow),
    }


def evidence_from_arena(report: Dict[str, Any]) -> Dict[str, Any]:
    """Informational metrics from a Promotion Arena report (arena_v0 schema).
    No current version gate consumes these; they travel with the evidence so
    the approver sees the whole picture."""
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
    """Merge every available instrument into one gate-evidence dict.

    Only computable metrics appear; whatever no instrument produced stays
    absent and its gate fails honestly. The key spaces of the sources are
    disjoint by construction — except the two shadow sources, where the
    marker-VERIFIED ``shadow_traces`` path wins over the caller-declared
    ``shadow_profile`` path (it is applied last on purpose)."""
    if (shadow_traces is None) != (shadow_agent_id is None):
        raise ValueError("shadow_traces and shadow_agent_id go together")
    evidence: Dict[str, Any] = {}
    if traces_before is not None and traces_after is not None:
        evidence.update(evidence_from_trace_windows(traces_before, traces_after))
    if shadow_profile is not None:
        evidence.update(evidence_from_shadow_profile(shadow_profile))
    if shadow_traces is not None and shadow_agent_id is not None:
        evidence.update(evidence_from_shadow_traces(shadow_agent_id, shadow_traces))
    if arena_report is not None:
        evidence.update(evidence_from_arena(arena_report))
    return evidence

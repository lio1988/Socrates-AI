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
    shadow-run traces. Session ids stay auditable inside the profile."""
    return {
        "shadow_blind_spots_wins": shadow_profile.section_wins.get(
            "blind_spots", 0),
        "shadow_sessions_analyzed": shadow_profile.sessions_analyzed,
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
    arena_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge every available instrument into one gate-evidence dict.

    Only computable metrics appear; whatever no instrument produced stays
    absent and its gate fails honestly. The key spaces of the sources are
    disjoint by construction, so merging never overwrites."""
    evidence: Dict[str, Any] = {}
    if traces_before is not None and traces_after is not None:
        evidence.update(evidence_from_trace_windows(traces_before, traces_after))
    if shadow_profile is not None:
        evidence.update(evidence_from_shadow_profile(shadow_profile))
    if arena_report is not None:
        evidence.update(evidence_from_arena(arena_report))
    return evidence

"""
OpenClaw Agent Identity — the Soul Card (readable identity summary).

A Soul Card is a human-readable rendering of an AgentIdentityProfile. It is
DESCRIPTIVE AND AUDITABLE, NOT AUTHORITY: printing a card changes nothing at
runtime, grants no permissions, and is never shown to agents as context.

Every line is traceable to profile evidence or an approved append-only
self-revision. No raw hidden scorecards, no secrets.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .identity_profile import AgentIdentityProfile
from .promotion_policy import (
    IDENTITY_LADDER,
    STAGE_NAMES,
    VERSION_GATES,
    next_gate_for,
)

GUIDING_SENTENCE = (
    "The agent does not become powerful because it claims identity. "
    "The agent earns identity through evidence.")

CARD_HEADER = "SOUL CARD (descriptive, not authority)"


def _best_and_weak(profile: AgentIdentityProfile
                   ) -> Tuple[Optional[str], Optional[str]]:
    contested = {name: strength
                 for name, strength in profile.role_strengths.items()
                 if profile.section_opportunities.get(name, 0) > 0}
    if not contested:
        return None, None
    best = min(contested, key=lambda n: (-contested[n], n))
    weak = min(contested, key=lambda n: (contested[n], n))
    return best, weak


def _role_line(profile: AgentIdentityProfile, name: Optional[str]) -> str:
    if name is None:
        return "insufficient evidence"
    return (f"{name} ({profile.role_strengths[name]:.2f} win rate, "
            f"{profile.section_wins.get(name, 0)}/"
            f"{profile.section_opportunities.get(name, 0)})")


def render_soul_card(profile: AgentIdentityProfile) -> str:
    """Render the readable, auditable identity summary of one agent seat."""
    stage_idx = (STAGE_NAMES.index(profile.promotion_status)
                 if profile.promotion_status in STAGE_NAMES else 0)
    stage_desc = IDENTITY_LADDER[stage_idx]["description"]
    best, weak = _best_and_weak(profile)

    gate = next((g for g in VERSION_GATES if g.gate_id == profile.next_gate),
                None) or next_gate_for(profile.identity_version)
    gate_line = (f"{gate.gate_id} - {gate.description}" if gate
                 else "none (end of the current gate chain)")

    flaws = ("\n".join(f"  - {f}" for f in profile.known_failures)
             if profile.known_failures else "  - none recorded")
    principles = ("\n".join(f"  - {p}" for p in profile.soul_principles)
                  if profile.soul_principles else "  - none approved")
    lessons = (", ".join(profile.stable_lessons)
               if profile.stable_lessons else "none recorded")

    lines = [
        CARD_HEADER,
        "=" * len(CARD_HEADER),
        f"Agent: {profile.agent_id}",
        f"Identity version: {profile.identity_version}",
        f"Rank: {profile.promotion_status} "
        f"(stage {stage_idx} of {len(IDENTITY_LADDER) - 1}) - {stage_desc}",
        f"Best role: {_role_line(profile, best)}",
        f"Weak role: {_role_line(profile, weak)}",
        "Known flaws:",
        flaws,
        "Approved soul principles:",
        principles,
        f"Stable lessons: {lessons}",
        f"Sessions analyzed: {profile.sessions_analyzed} "
        f"(ratified: {profile.ratified_sessions})",
        f"Promotions recorded: {len(profile.version_history)}",
        f"Self-revisions recorded: {len(profile.revision_history)}",
        f"Next promotion gate: {gate_line}",
        "-" * len(CARD_HEADER),
        GUIDING_SENTENCE,
    ]
    return "\n".join(lines)

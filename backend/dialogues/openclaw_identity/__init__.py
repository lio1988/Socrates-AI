"""
OpenClaw Agent Identity — the Self-Improving Agent Identity Layer (v0).

Canonical docs:
  docs/openclaw_memory_lessons/SELF_IMPROVING_AGENT_IDENTITY.md
    (OPENCLAW_MEMORY_LESSONS_AGENT_IDENTITY)
  docs/openclaw_memory_lessons/AGENT_SOUL_CARD.md
    (OPENCLAW_MEMORY_LESSONS_AGENT_SOUL_CARD)

"Soul" here is not mystical and not autonomy: it is an auditable, versioned
identity profile per agent seat, derived from evidence (session traces,
Memory Lessons, arena/tree outcomes) and advanced ONLY through human-approved,
evidence-backed gates.

Constitution:
  CED governs. Evidence Harness measures. OpenClaw remembers. Agents execute.
  Identity is earned through verified performance.

This package is SYSTEM-owned and runtime-inert: the CED core never imports it
(test-locked), profiles are never injected into agent contexts, and nothing
here grants any agent authority. Pure, deterministic, offline.
"""

from .identity_profile import (
    SECTION_NAMES,
    AgentIdentityProfile,
    build_identity_profile,
    from_record,
)
from .identity_registry import (
    IdentityRegistry,
)
from .evidence_collection import (
    collect_gate_evidence,
    evidence_from_arena,
    evidence_from_shadow_profile,
    evidence_from_shadow_traces,
    evidence_from_trace_windows,
)
from .promotion_policy import (
    IDENTITY_LADDER,
    STAGE_NAMES,
    VERSION_GATES,
    GateResult,
    VersionGate,
    advance_stage,
    evaluate_gate,
    next_gate_for,
    record_promotion,
)
from .soul_card import (
    CARD_HEADER,
    GUIDING_SENTENCE,
    render_soul_card,
)

__all__ = [
    "SECTION_NAMES",
    "AgentIdentityProfile",
    "build_identity_profile",
    "from_record",
    "IdentityRegistry",
    "collect_gate_evidence",
    "evidence_from_arena",
    "evidence_from_shadow_profile",
    "evidence_from_shadow_traces",
    "evidence_from_trace_windows",
    "IDENTITY_LADDER",
    "STAGE_NAMES",
    "VERSION_GATES",
    "GateResult",
    "VersionGate",
    "advance_stage",
    "evaluate_gate",
    "next_gate_for",
    "record_promotion",
    "CARD_HEADER",
    "GUIDING_SENTENCE",
    "render_soul_card",
]

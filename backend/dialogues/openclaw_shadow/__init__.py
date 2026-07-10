"""
OpenClaw Shadow Apprentice Mode (Goal 11, Stage 1).

    The local agent should learn beside the council before it influences
    the council.

Runtime-inert toward the council: the CED core never imports this package
(test-locked), the apprentice runs only AFTER a session's final answer
exists, and nothing here writes into council state. Shadow records carry
the Goal 13.2 capture-time marker so the identity evidence pipeline
(evidence_from_shadow_traces -> gate v0.3 -> v0.4) consumes them unchanged.

Stage 2+ (contributing low-risk sections, entering synthesis) requires the
Promotion Arena gate and explicit human approval — see FUTURE_GOALS Goal 11
and the identity ladder.

No keys, no network beyond the adapters it is given.
"""

from .shadow_apprentice import (
    SHADOW_SCHEMA_VERSION,
    ShadowApprentice,
)

__all__ = [
    "SHADOW_SCHEMA_VERSION",
    "ShadowApprentice",
]

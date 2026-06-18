"""
Epistemic State Machine
=======================

Every Claim in Socrates AI lives inside an explicit lifecycle. This module
defines the allowed states and — crucially — the *legal transitions* between
them. The directive's non-negotiable rule is enforced here in code:

    "No claim may jump directly from HYPOTHESIS to KNOWLEDGE."

A claim must survive challenge and evidence integration first. The state graph
below makes illegal shortcuts impossible, not merely discouraged.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class EpistemicState(str, Enum):
    UNKNOWN = "UNKNOWN"
    HYPOTHESIS = "HYPOTHESIS"
    SUPPORTED = "SUPPORTED"
    CHALLENGED = "CHALLENGED"
    REVISED = "REVISED"
    VERIFIED = "VERIFIED"
    KNOWLEDGE = "KNOWLEDGE"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    OBSOLETE = "OBSOLETE"
    ARCHIVED = "ARCHIVED"


# Allowed transitions. A claim may only move along these edges.
# This is the single source of truth for what the lifecycle permits.
ALLOWED_TRANSITIONS: Dict[EpistemicState, Set[EpistemicState]] = {
    EpistemicState.UNKNOWN: {EpistemicState.HYPOTHESIS},
    EpistemicState.HYPOTHESIS: {
        EpistemicState.CHALLENGED,
        EpistemicState.SUPPORTED,
        EpistemicState.REJECTED,
    },
    EpistemicState.SUPPORTED: {
        EpistemicState.CHALLENGED,
        EpistemicState.VERIFIED,
        EpistemicState.DISPUTED,
    },
    EpistemicState.CHALLENGED: {
        EpistemicState.REVISED,
        EpistemicState.SUPPORTED,
        EpistemicState.DISPUTED,
        EpistemicState.REJECTED,
    },
    EpistemicState.REVISED: {
        EpistemicState.CHALLENGED,
        EpistemicState.SUPPORTED,
        EpistemicState.VERIFIED,
    },
    EpistemicState.VERIFIED: {
        EpistemicState.KNOWLEDGE,
        EpistemicState.CHALLENGED,
        EpistemicState.DISPUTED,
    },
    EpistemicState.KNOWLEDGE: {
        EpistemicState.DISPUTED,
        EpistemicState.OBSOLETE,
    },
    EpistemicState.DISPUTED: {
        EpistemicState.REVISED,
        EpistemicState.OBSOLETE,
        EpistemicState.REJECTED,
    },
    EpistemicState.REJECTED: {EpistemicState.ARCHIVED},
    EpistemicState.OBSOLETE: {EpistemicState.ARCHIVED, EpistemicState.REVISED},
    EpistemicState.ARCHIVED: set(),  # terminal
}

# States in which a claim is considered "live" and may participate in reasoning.
ACTIVE_STATES: Set[EpistemicState] = {
    EpistemicState.HYPOTHESIS,
    EpistemicState.SUPPORTED,
    EpistemicState.CHALLENGED,
    EpistemicState.REVISED,
    EpistemicState.VERIFIED,
    EpistemicState.KNOWLEDGE,
    EpistemicState.DISPUTED,
}

# A claim must pass through challenge before it can be promoted.
# We track this with a flag on the Claim, but the state graph already guarantees
# that VERIFIED is only reachable via SUPPORTED or REVISED, both of which are
# only reachable after CHALLENGED (except the SUPPORTED-direct path, which the
# Claim object additionally guards — see claim.py).


class IllegalTransition(Exception):
    """Raised when a state transition is not permitted by the lifecycle."""


def can_transition(src: EpistemicState, dst: EpistemicState) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, set())


def assert_transition(src: EpistemicState, dst: EpistemicState) -> None:
    if not can_transition(src, dst):
        raise IllegalTransition(
            f"Illegal epistemic transition: {src.value} -> {dst.value}. "
            f"Allowed from {src.value}: "
            f"{sorted(s.value for s in ALLOWED_TRANSITIONS.get(src, set()))}"
        )


def is_terminal(state: EpistemicState) -> bool:
    return len(ALLOWED_TRANSITIONS.get(state, set())) == 0

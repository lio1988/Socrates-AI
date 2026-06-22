"""
Deterministic Role Assignment (V1)

Given a list of agent IDs and a session_id, assigns one primary AgentRole to
each agent such that:

  1. The mapping is fully deterministic — same inputs, same output, always.
  2. The Socrates role rotates across sessions so no agent holds it permanently.
  3. Exactly one agent is assigned SOCRATES per session.
  4. With N agents the four base roles tile cyclically; for N=4 every base role
     is assigned exactly once.

The rotation offset is derived from SHA-256(session_id) mod N, which means
every session gets a different starting position without any shared mutable state.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List

from .models import AgentRole


# The four primary roles that fill the rotation table.
# Dynamic roles (REFLECTOR, MAIEUTIC_RECONSTRUCTOR, FINAL_EVALUATOR) are
# assigned by the CED orchestrator at runtime, not here.
_PRIMARY_ROLES: List[AgentRole] = [
    AgentRole.SOCRATES,
    AgentRole.ELENCHUS_CRITIC,
    AgentRole.EMPIRICIST,
    AgentRole.SYNTHESIZER,
]


def stable_hash(text: str) -> int:
    """
    Deterministic, run-independent hash (SHA-256 based).

    Python's built-in hash() is randomized per process for strings, so it MUST
    NOT be used for reproducible role rotation. This is the canonical hash used
    by both the primary-role assignment and the CED per-phase role scheduler.
    """
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def _rotation_offset(session_id: str, modulus: int) -> int:
    """Derive a deterministic offset from session_id via SHA-256."""
    return stable_hash(session_id) % modulus


def assign_primary_roles(
    agent_ids: List[str],
    session_id: str,
) -> Dict[str, AgentRole]:
    """
    Assign one primary role to each agent for the session.

    Guarantees:
    - Exactly one agent is assigned SOCRATES, regardless of N.
    - The Socrates slot rotates across sessions (different session_id → different holder).
    - Result is independent of insertion order (agents are sorted first).

    Algorithm:
    - Build a role list of length N where position 0 is always SOCRATES and the
      remaining positions cycle through the non-Socrates primary roles.
    - Apply a rotation offset derived from SHA-256(session_id) mod N.
    - Because the role list has exactly one SOCRATES and the rotation is a permutation
      of N positions, exactly one agent always gets SOCRATES.

    Returns: {agent_id: AgentRole}

    Raises:
        ValueError: if fewer than 2 agents are provided.
    """
    n = len(agent_ids)
    if n < 2:
        raise ValueError(
            f"Socratic Council requires at least 2 agents; got {n}."
        )

    offset = _rotation_offset(session_id, n)   # in [0, n-1]
    sorted_ids = sorted(agent_ids)             # canonical order

    # Build an N-slot role list: slot 0 = SOCRATES, rest cycle through non-Socrates roles.
    # This guarantees exactly one SOCRATES in the list regardless of N.
    non_socrates = [r for r in _PRIMARY_ROLES if r != AgentRole.SOCRATES]
    full_roles = [AgentRole.SOCRATES] + [
        non_socrates[i % len(non_socrates)] for i in range(n - 1)
    ]

    assignment: Dict[str, AgentRole] = {}
    for position, agent_id in enumerate(sorted_ids):
        role_index = (position + offset) % n   # rotation within [0, n-1]
        assignment[agent_id] = full_roles[role_index]

    return assignment


def socrates_for_session(agent_ids: List[str], session_id: str) -> str:
    """Return the agent_id that will be assigned SOCRATES for this session."""
    roles = assign_primary_roles(agent_ids, session_id)
    return next(aid for aid, role in roles.items() if role == AgentRole.SOCRATES)

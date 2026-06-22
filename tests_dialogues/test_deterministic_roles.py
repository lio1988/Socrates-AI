"""
Deterministic Role Assignment tests.

Invariants under test:
  1. Same session_id → same role map (determinism).
  2. Different session_ids → at least one agent changes role (rotation).
  3. Exactly one SOCRATES per session, regardless of N.
  4. Every agent gets a role.
  5. Minimum-2-agent constraint is enforced.
  6. All four primary roles appear across enough distinct sessions.
"""

import pytest

from backend.dialogues.models import AgentRole
from backend.dialogues.role_assignment import assign_primary_roles, socrates_for_session

AGENTS_4 = ["alpha", "beta", "gamma", "delta"]
AGENTS_2 = ["x", "y"]
AGENTS_6 = ["a", "b", "c", "d", "e", "f"]


# ── Determinism ───────────────────────────────────────────────────────────────

def test_same_inputs_produce_same_role_map():
    r1 = assign_primary_roles(AGENTS_4, "session-determinism-test")
    r2 = assign_primary_roles(AGENTS_4, "session-determinism-test")
    assert r1 == r2


def test_agent_order_does_not_affect_result():
    """Role assignment is based on sorted agent IDs, so insertion order is irrelevant."""
    shuffled = list(reversed(AGENTS_4))
    r1 = assign_primary_roles(AGENTS_4, "order-test")
    r2 = assign_primary_roles(shuffled, "order-test")
    assert r1 == r2


# ── Rotation ──────────────────────────────────────────────────────────────────

def test_different_sessions_vary_assignment():
    """Different session_ids must produce different role distributions."""
    maps = [assign_primary_roles(AGENTS_4, f"sess-{i}") for i in range(20)]
    # Not all maps should be identical — rotation is expected
    unique_maps = {frozenset(m.items()) for m in maps}
    assert len(unique_maps) > 1, "Role assignment never changed across 20 sessions."


def test_socrates_role_rotates_across_sessions():
    """SOCRATES must be assigned to different agents in different sessions."""
    socrates_holders = {
        socrates_for_session(AGENTS_4, f"rotation-{i}") for i in range(50)
    }
    # With 4 agents rotating, all 4 should eventually hold SOCRATES
    assert len(socrates_holders) == 4, (
        f"SOCRATES never rotated to all agents; only held by: {socrates_holders}"
    )


# ── Structural invariants ─────────────────────────────────────────────────────

def test_exactly_one_socrates_per_session():
    for i in range(30):
        roles = assign_primary_roles(AGENTS_4, f"one-socrates-{i}")
        count = sum(1 for r in roles.values() if r == AgentRole.SOCRATES)
        assert count == 1, (
            f"Session one-socrates-{i}: expected 1 SOCRATES, got {count}."
        )


def test_every_agent_receives_a_role():
    roles = assign_primary_roles(AGENTS_4, "coverage-test")
    assert set(roles.keys()) == set(AGENTS_4)
    for agent_id, role in roles.items():
        assert isinstance(role, AgentRole), (
            f"Agent {agent_id} got non-AgentRole value: {role!r}"
        )


def test_minimum_agent_constraint():
    with pytest.raises(ValueError, match="at least 2"):
        assign_primary_roles(["lone_agent"], "session-x")


def test_empty_agent_list_raises():
    with pytest.raises((ValueError, ZeroDivisionError)):
        assign_primary_roles([], "session-empty")


# ── Coverage of primary roles ─────────────────────────────────────────────────

def test_all_four_primary_roles_appear_across_sessions():
    """The four primary roles must all appear across a reasonable set of sessions."""
    seen: set[AgentRole] = set()
    for i in range(40):
        roles = assign_primary_roles(AGENTS_4, f"all-roles-{i}")
        seen |= set(roles.values())

    for role in (
        AgentRole.SOCRATES,
        AgentRole.ELENCHUS_CRITIC,
        AgentRole.EMPIRICIST,
        AgentRole.SYNTHESIZER,
    ):
        assert role in seen, f"{role.value} never appeared in any session."


def test_two_agent_assignment_still_has_one_socrates():
    for i in range(10):
        roles = assign_primary_roles(AGENTS_2, f"two-agent-{i}")
        count = sum(1 for r in roles.values() if r == AgentRole.SOCRATES)
        assert count == 1


def test_six_agent_assignment():
    roles = assign_primary_roles(AGENTS_6, "six-agents")
    assert set(roles.keys()) == set(AGENTS_6)
    count = sum(1 for r in roles.values() if r == AgentRole.SOCRATES)
    assert count == 1

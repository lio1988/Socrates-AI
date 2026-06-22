"""
Deterministic Dynamic Role Rotation tests (Phase 3).

Invariants under test:
  1. Socrates rotates deterministically across sessions.
  2. Socrates rotates across rounds when multiple Socratic rounds exist.
  3. Same session_id → identical role assignments (determinism).
  4. Different session_ids → deterministic but different assignments.
  5. No agent assigns its own role (CED owns assignment).
  6. No provider influences role assignment.
  7. role_history is recorded in SessionState.
  8. High-impact roles (Socrates / Synthesizer / Final Evaluator) are not
     monopolized by the same agent when enough agents are available.
"""

import pytest
from unittest.mock import patch

from backend.dialogues.models import AgentRole, DialogPhase
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


def _make_ced(n: int = 4) -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


def _socrates_of(ced: CEDOrchestrator, session_id: str, round_index: int = 0) -> str:
    state = ced.create_session("Q?", session_id=session_id)
    assignment = ced.assign_roles_for_phase(state, DialogPhase.OPENING, round_index)
    return next(aid for aid, r in assignment.items() if r == AgentRole.SOCRATES)


def _role_holder(ced, state, phase, role) -> str:
    assignment = ced.assign_roles_for_phase(state, phase)
    return next(aid for aid, r in assignment.items() if r == role)


# ── 1. Socrates rotates across sessions ───────────────────────────────────────

def test_socrates_rotates_across_sessions():
    ced = _make_ced(4)
    holders = {_socrates_of(ced, f"sess-{i}") for i in range(60)}
    assert len(holders) == 4, (
        f"Socrates did not rotate to all agents across sessions; saw {holders}."
    )


# ── 2. Socrates rotates across rounds ─────────────────────────────────────────

def test_socrates_rotates_across_rounds():
    ced = _make_ced(4)
    state = ced.create_session("Q?", session_id="multi-round")
    holders = [
        next(
            aid for aid, r in
            ced.assign_roles_for_phase(state, DialogPhase.OPENING, round_index=k).items()
            if r == AgentRole.SOCRATES
        )
        for k in range(4)
    ]
    assert len(set(holders)) == 4, (
        f"Socrates must rotate across rounds; got {holders}."
    )


# ── 3. Determinism: same session → same assignment ───────────────────────────

def test_same_session_same_assignment():
    ced = _make_ced(4)
    state = ced.create_session("Q?", session_id="determinism")
    for phase in DialogPhase:
        a1 = ced.assign_roles_for_phase(state, phase)
        a2 = ced.assign_roles_for_phase(state, phase)
        assert a1 == a2, f"Non-deterministic assignment for phase {phase.value}."


def test_full_plan_is_reproducible():
    ced = _make_ced(4)
    ced.create_session("Q?", session_id="plan-repro")
    p1 = ced.get_phase_role_plan("plan-repro")
    p2 = ced.get_phase_role_plan("plan-repro")
    assert p1 == p2


# ── 4. Different sessions → deterministic but different ───────────────────────

def test_different_sessions_differ():
    ced = _make_ced(4)
    plans = []
    for i in range(20):
        ced.create_session("Q?", session_id=f"diff-{i}")
        plan = ced.get_phase_role_plan(f"diff-{i}")
        plans.append(tuple((ph.value, tuple(sorted(m.items()))) for ph, m in plan))
    assert len(set(plans)) > 1, "Assignments never differed across sessions."


# ── 5. No agent assigns its own role ──────────────────────────────────────────

def test_role_assignment_is_ced_owned_not_agent_owned():
    """Agents expose no role-assignment capability; the CED owns it entirely."""
    ced = _make_ced(4)
    for agent in ced.agents:
        assert not hasattr(agent, "assign_roles_for_phase")
        assert not hasattr(agent, "choose_role")
    assert hasattr(ced, "assign_roles_for_phase")


def test_assignment_independent_of_agent_internal_state():
    """
    Assignment depends only on session_id/phase/round/agent_ids — not on any
    agent's internal attributes. Mutating an agent must not change assignment.
    """
    ced = _make_ced(4)
    state = ced.create_session("Q?", session_id="agent-state-indep")
    before = ced.assign_roles_for_phase(state, DialogPhase.OPENING)

    # Poke agent internals — should have zero effect on role assignment.
    for agent in ced.agents:
        agent._scratch = "mutated"  # type: ignore[attr-defined]
    after = ced.assign_roles_for_phase(state, DialogPhase.OPENING)
    assert before == after


# ── 6. No provider influences role assignment ─────────────────────────────────

def test_provider_never_called_during_role_assignment():
    ced = _make_ced(4)
    state = ced.create_session("Q?", session_id="no-provider")

    with patch.object(
        FakeProvider, "complete",
        side_effect=AssertionError("provider must not influence role assignment"),
    ):
        for phase in DialogPhase:
            ced.assign_roles_for_phase(state, phase)
        ced.get_phase_role_plan("no-provider")  # also must not call the provider


# ── 7. role_history recorded in SessionState ──────────────────────────────────

def test_role_history_recorded_during_session():
    ced = _make_ced(4)
    ced.run_session("Is knowledge justified true belief?", session_id="hist")
    state = ced.get_session("hist")

    assert state.role_history, "role_history must be populated after a run."
    sample = state.role_history[0]
    assert set(sample.keys()) == {"phase", "round_index", "agent_id", "role"}

    phases_recorded = {r["phase"] for r in state.role_history}
    for expected in (
        DialogPhase.OPENING.value,
        DialogPhase.INITIAL_RESPONSE.value,
        DialogPhase.ELENCHUS.value,
        DialogPhase.REFLECTION.value,
        DialogPhase.RECONSTRUCTION.value,
        DialogPhase.SYNTHESIS.value,
        DialogPhase.RATIFICATION.value,
    ):
        assert expected in phases_recorded, f"Missing role_history for {expected}."


def test_role_history_opening_matches_scheduler():
    ced = _make_ced(4)
    ced.run_session("Q?", session_id="hist-match")
    state = ced.get_session("hist-match")

    recorded_socrates = next(
        r["agent_id"] for r in state.role_history
        if r["phase"] == DialogPhase.OPENING.value
        and r["role"] == AgentRole.SOCRATES.value
    )
    scheduled_socrates = _role_holder(ced, state, DialogPhase.OPENING, AgentRole.SOCRATES)
    assert recorded_socrates == scheduled_socrates


# ── 8. High-impact roles are not monopolized ──────────────────────────────────

def test_high_impact_roles_distinct_within_session():
    """With 4 agents, Socrates / Synthesizer / Final Evaluator land on 3 agents."""
    ced = _make_ced(4)
    state = ced.create_session("Q?", session_id="no-monopoly")

    socrates = _role_holder(ced, state, DialogPhase.OPENING, AgentRole.SOCRATES)
    synthesizer = _role_holder(ced, state, DialogPhase.INITIAL_RESPONSE, AgentRole.SYNTHESIZER)
    evaluator = _role_holder(ced, state, DialogPhase.RATIFICATION, AgentRole.FINAL_EVALUATOR)

    assert len({socrates, synthesizer, evaluator}) == 3, (
        f"High-impact roles collided: socrates={socrates}, "
        f"synthesizer={synthesizer}, evaluator={evaluator}."
    )


def test_socrates_and_final_evaluator_differ_across_many_sessions():
    """The Final Evaluator is never forced to be the opening Socrates (n=4)."""
    ced = _make_ced(4)
    for i in range(40):
        state = ced.create_session("Q?", session_id=f"sep-{i}")
        socrates = _role_holder(ced, state, DialogPhase.OPENING, AgentRole.SOCRATES)
        evaluator = _role_holder(ced, state, DialogPhase.RATIFICATION, AgentRole.FINAL_EVALUATOR)
        assert socrates != evaluator, (
            f"Session sep-{i}: Final Evaluator monopolized by Socrates agent."
        )


def test_final_evaluator_distributes_across_sessions():
    ced = _make_ced(4)
    evaluators = set()
    for i in range(60):
        state = ced.create_session("Q?", session_id=f"eval-dist-{i}")
        evaluators.add(_role_holder(ced, state, DialogPhase.RATIFICATION, AgentRole.FINAL_EVALUATOR))
    assert len(evaluators) == 4, (
        f"Final Evaluator did not distribute across agents; saw {evaluators}."
    )

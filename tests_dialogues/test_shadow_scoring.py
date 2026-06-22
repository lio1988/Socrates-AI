"""
Shadow Scoring tests (Phase 4 — multi-dimensional, move-level).

Invariants under test:
  1. No agent scores its own output (hard constraint).
  2. Every synthesis move is scored by every other agent.
  3. Scores are multi-dimensional and on the 0–10 scale.
  4. Score data never leaks into any AgentTask.context.
  5. Micro scores are CED-owned (on SessionState), not on AgentState.
"""

import pytest
from unittest.mock import patch

from backend.dialogues.models import AgentRole, DialogPhase, MicroScore
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


def _make_ced(n: int = 4) -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


def _run_to_synthesis(ced: CEDOrchestrator, sid: str, question: str) -> None:
    ced.create_session(question, session_id=sid)
    ced.run_opening_phase(sid)
    ced.run_initial_response_phase(sid)
    ced.run_elenchus_phase(sid)
    ced.run_reflection_phase(sid)
    ced.run_reconstruction_phase(sid)
    ced.run_synthesis_phase(sid)


# ── No self-scoring ───────────────────────────────────────────────────────────

def test_no_agent_scores_its_own_output():
    ced = _make_ced()
    _run_to_synthesis(ced, "shadow-no-self", "Is consciousness reducible to physics?")
    micro = ced.compute_shadow_scores("shadow-no-self", DialogPhase.SYNTHESIS)

    assert micro
    for ms in micro:
        assert ms.author_agent_id != ms.voter_agent_id, (
            f"Self-scoring violation: {ms.voter_agent_id} scored its own move "
            f"{ms.output_id}."
        )


def test_no_self_scoring_with_two_agents():
    ced = _make_ced(n=2)
    _run_to_synthesis(ced, "shadow-two", "What is time?")
    micro = ced.compute_shadow_scores("shadow-two")
    for ms in micro:
        assert ms.author_agent_id != ms.voter_agent_id


# ── Coverage ──────────────────────────────────────────────────────────────────

def test_each_move_scored_by_all_other_agents():
    ced = _make_ced(4)
    _run_to_synthesis(ced, "shadow-coverage", "Does free will exist?")
    micro = ced.compute_shadow_scores("shadow-coverage")
    state = ced.get_session("shadow-coverage")

    for move in state.moves_for_phase(DialogPhase.SYNTHESIS):
        voters = {ms.voter_agent_id for ms in micro if ms.output_id == move.move_id}
        expected = {a.agent_id for a in ced.agents if a.agent_id != move.agent_id}
        assert voters == expected, (
            f"Move {move.move_id} by {move.agent_id} scored by {voters}, "
            f"expected {expected}."
        )


# ── Multi-dimensional, 0–10 scale ────────────────────────────────────────────

def test_scores_are_multidimensional_and_0_to_10():
    ced = _make_ced()
    _run_to_synthesis(ced, "shadow-scale", "Is logic universal?")
    micro = ced.compute_shadow_scores("shadow-scale")

    for ms in micro:
        assert 0.0 <= ms.overall_score <= 10.0
        bd = ms.score_breakdown
        for dim in (
            bd.epistemic_value, bd.logical_rigor, bd.factual_grounding,
            bd.constructive_impact, bd.intellectual_honesty,
            bd.clarity_precision, bd.grounded_creativity,
        ):
            assert 0.0 <= dim <= 10.0
        # overall matches the weighted breakdown (auto-filled)
        assert ms.overall_score == pytest.approx(bd.weighted_overall())
        assert 0.0 <= ms.confidence <= 1.0


# ── Scores never leak into agent context ─────────────────────────────────────

def test_shadow_scores_not_exposed_in_agent_context():
    ced = _make_ced()
    ced.create_session("What is knowledge?", session_id="shadow-leak")

    captured_tasks = []
    original_execute = SocraticAgent.execute

    def capturing_execute(self, task):
        captured_tasks.append(task)
        return original_execute(self, task)

    with patch.object(SocraticAgent, "execute", capturing_execute):
        ced.run_opening_phase("shadow-leak")
        ced.run_initial_response_phase("shadow-leak")
        ced.run_elenchus_phase("shadow-leak")
        ced.run_reflection_phase("shadow-leak")
        ced.run_reconstruction_phase("shadow-leak")
        ced.run_synthesis_phase("shadow-leak")

    ced.compute_shadow_scores("shadow-leak")

    score_keywords = {
        "score_breakdown", "overall_score", "voter_agent_id",
        "micro_score", "leaderboard", "epistemic_value",
    }
    for task in captured_tasks:
        ctx_str = str(task.context).lower()
        for kw in score_keywords:
            assert kw not in ctx_str, (
                f"Score keyword '{kw}' leaked into AgentTask.context "
                f"of '{task.agent_id}' in phase '{task.phase.value}'."
            )


# ── Micro scores are CED-owned ────────────────────────────────────────────────

def test_micro_scores_stored_on_session_not_agent_state():
    ced = _make_ced()
    _run_to_synthesis(ced, "shadow-own", "Can ethics be objective?")
    micro = ced.compute_shadow_scores("shadow-own")

    state = ced.get_session("shadow-own")
    assert state.micro_scores == micro
    assert len(state.micro_scores) > 0

    # AgentState must not carry raw scores / scorecards / leaderboard.
    for ast in state.agent_states.values():
        for forbidden in ("micro_scores", "draft_scorecards", "section_scores",
                          "leaderboard", "scorecard"):
            assert not hasattr(ast, forbidden), (
                f"AgentState leaked scoring field '{forbidden}'."
            )

"""
PERMANENT CED INVARIANT — peer scoring, not CED scoring.

CED governs the protocol (assign roles, route scoring tasks, validate, prevent
self-scoring, aggregate mechanically, audit). CED MUST NOT act as a semantic
judge: every qualitative score is attributed to a peer voter, and a failed/
invalid peer score stays MISSING — CED never fabricates a stand-in score.
"""

import asyncio
from unittest.mock import patch

import pytest

from backend.dialogues.models import (
    DialogPhase, LeaderboardStatus, SyncGateStatus, ShadowScoringMode,
)
from backend.dialogues.ced import CEDOrchestrator, SCORED_PHASES, PHASE_RUBRICS
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent

Q = "Is knowledge merely justified true belief?"


def _make_ced(n=4, provider=None, mode=ShadowScoringMode.ALL_PHASES):
    provider = provider or FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider, shadow_scoring_mode=mode)


class _BrokenMoveScoreProvider(FakeProvider):
    """Returns malformed (empty) MOVE scores; everything else stays valid."""
    def complete(self, system_prompt, user_prompt, output_schema, agent_id="", temperature=0.7):
        if output_schema.get("_role") == "__move_score__":
            return {}   # no score_breakdown → invalid peer score
        return super().complete(system_prompt, user_prompt, output_schema, agent_id, temperature)


def _run(ced, sid):
    ced.run_session(Q, session_id=sid)
    return ced.get_session(sid)


# 1 + 2 + 3 + 11 — every score is attributed to a peer voter (voter != author) ─

def test_every_microscore_has_author_and_voter():
    st = _run(_make_ced(), "inv-1")
    assert st.micro_scores
    agent_ids = {a.agent_id for a in [SocraticAgent(f"agent_{i}", None) for i in range(4)]}
    for ms in st.micro_scores:
        assert ms.author_agent_id and ms.voter_agent_id
        assert ms.author_agent_id != ms.voter_agent_id          # no self-scoring
        assert ms.voter_agent_id in agent_ids                   # attributed to a peer


def test_no_self_scoring_in_any_phase():
    st = _run(_make_ced(), "inv-2")
    for ms in st.micro_scores:
        assert ms.voter_agent_id != ms.author_agent_id


def test_scores_attributed_to_peers_not_ced():
    st = _run(_make_ced(), "inv-3")
    voters = {ms.voter_agent_id for ms in st.micro_scores}
    # voters are agents, never "ced"/"CED"/system
    assert voters and all(v.startswith("agent_") for v in voters)


# 4 + 12 — CED fabricates NO scores when peer scoring fails ───────────────────

def test_ced_does_not_fabricate_when_peer_scoring_fails():
    ced = _make_ced(provider=_BrokenMoveScoreProvider())
    st = _run(ced, "inv-4")
    # No move-level scores were fabricated by CED.
    assert st.micro_scores == []
    # Failures are recorded as metadata, not as zero scores.
    assert st.failed_score_tasks
    # Leaderboard reports the failure honestly, with no fabricated averages.
    assert st.epistemic_leaderboard.leaderboard_status == LeaderboardStatus.FAILED
    assert st.epistemic_leaderboard.average_scores_by_agent == {}


# 5 — all peer scoring fails → failure status, never silent fake completion ───

def test_all_peer_scoring_failed_status():
    ced = _make_ced(provider=_BrokenMoveScoreProvider())
    st = _run(ced, "inv-5")
    assert st.shadow_harvest.status == SyncGateStatus.FAILED
    assert st.epistemic_leaderboard.leaderboard_status == LeaderboardStatus.FAILED
    # pipeline still completes (assembly/ratification unaffected) — no crash
    assert st.final_response is not None


# 6 — leaderboard derived ONLY from valid peer MicroScores ───────────────────

def test_leaderboard_built_only_from_valid_peer_scores():
    st = _run(_make_ced(), "inv-6")
    lb = st.epistemic_leaderboard
    # Recompute averages purely from the recorded peer MicroScores.
    from collections import defaultdict
    sums, counts = defaultdict(float), defaultdict(int)
    for ms in st.micro_scores:
        sums[ms.author_agent_id] += float(ms.overall_score)
        counts[ms.author_agent_id] += 1
    expected = {a: round(sums[a] / counts[a], 4) for a in sums}
    assert lb.average_scores_by_agent == expected


# 7 — Socratic opening questions are peer-scored ─────────────────────────────

def test_socratic_question_is_peer_scored():
    st = _run(_make_ced(), "inv-7")
    opening = [ms for ms in st.micro_scores if ms.phase == DialogPhase.OPENING]
    assert opening
    for ms in opening:
        assert ms.voter_agent_id != ms.author_agent_id
        assert ms.rubric_name == PHASE_RUBRICS[DialogPhase.OPENING][0]   # question_quality


# 8 — scores across all configured phases ────────────────────────────────────

def test_scores_span_all_configured_phases():
    st = _run(_make_ced(mode=ShadowScoringMode.ALL_PHASES), "inv-8")
    assert {ms.phase for ms in st.micro_scores} == set(SCORED_PHASES)
    # each carries a phase-specific rubric identity
    for ph in SCORED_PHASES:
        rub = {ms.rubric_name for ms in st.micro_scores if ms.phase == ph}
        assert rub == {PHASE_RUBRICS[ph][0]}


# 9 — off → no fake scores, disabled status ──────────────────────────────────

def test_off_produces_no_scores_and_disabled_status():
    st = _run(_make_ced(mode=ShadowScoringMode.OFF), "inv-9")
    assert st.micro_scores == []
    assert st.epistemic_leaderboard.leaderboard_status == LeaderboardStatus.DISABLED


# 10 — minimal awareness: scoring internals never reach agents ───────────────

def test_minimal_awareness_scores_not_in_agentstate_or_task():
    ced = _make_ced()
    captured = []
    original = SocraticAgent.execute

    def cap(self, task):
        captured.append(task)
        return original(self, task)

    with patch.object(SocraticAgent, "execute", cap):
        ced.run_session(Q, session_id="inv-10")

    state = ced.get_session("inv-10")
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in ("micro_scores", "socratic_leaderboard", "task_log",
                          "failed_score_tasks", "provider_status_summary",
                          "score_breakdown", "coverage_ratio"):
            assert forbidden not in dumped
    for task in captured:
        blob = str(task.context).lower()
        for kw in ("leaderboard", "score_breakdown", "overall_score",
                   "coverage_ratio", "task_log", "voter_agent_id"):
            assert kw not in blob


# 12 — there is no CED-only semantic scoring path (behavioural proof) ────────

def test_no_ced_only_scoring_path():
    # A provider that returns no breakdown for ANY score request yields ZERO
    # scores — CED has no path that invents a score without a peer breakdown.
    class _NoScores(FakeProvider):
        def complete(self, system_prompt, user_prompt, output_schema, agent_id="", temperature=0.7):
            if output_schema.get("_role") in ("__move_score__", "__section_score__"):
                return {"penalty_flags": [], "provider_status": "ok"}   # no score_breakdown
            return super().complete(system_prompt, user_prompt, output_schema, agent_id, temperature)

    ced = _make_ced(provider=_NoScores())
    st = _run(ced, "inv-12")
    assert st.micro_scores == []
    section_scores = [s for c in st.draft_scorecards for s in c.section_scores]
    assert section_scores == []          # not one fabricated score anywhere

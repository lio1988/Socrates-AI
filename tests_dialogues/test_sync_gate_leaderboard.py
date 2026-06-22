"""
Phase 7 — Epistemic Sync Gate + CED-owned leaderboard + FinalResponse contract.

Covers: bounded harvest (complete/partial/timeout/unavailable), leaderboard
aggregation + status + warning, Minimal Awareness (no scores/leaderboard on
AgentState), and the separated FinalResponse contract.
"""

import asyncio
import json
import types

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, DialogPhase, MicroScore, ScoreBreakdown,
    ShadowScoreHarvest, EpistemicLeaderboard, AssembledAnswer,
    SyncGateStatus, LeaderboardStatus, ProviderStatus,
    LEADERBOARD_INTERPRETATION_WARNING,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


EPI_Q = "Is knowledge merely justified true belief?"


def _make_ced(n: int = 4) -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


def _run_to_synthesis(ced: CEDOrchestrator, sid: str, q: str = EPI_Q):
    state = ced.create_session(q, session_id=sid)
    for fn in [ced.run_opening_phase, ced.run_initial_response_phase,
               ced.run_elenchus_phase, ced.run_reflection_phase,
               ced.run_reconstruction_phase, ced.run_synthesis_phase]:
        fn(sid)
    return state


def _bd(v: float) -> ScoreBreakdown:
    return ScoreBreakdown(
        epistemic_value=v, logical_rigor=v, factual_grounding=v,
        constructive_impact=v, intellectual_honesty=v,
        clarity_precision=v, grounded_creativity=v,
    )


# ── Sync gate: complete ───────────────────────────────────────────────────────

def test_harvest_complete_when_all_finish():
    ced = _make_ced(4)
    state = _run_to_synthesis(ced, "sg-complete")
    harvest = asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=4.0))

    assert harvest.status == SyncGateStatus.COMPLETE
    assert harvest.scores_expected == 4 * 3   # 4 synthesis moves × 3 voters
    assert harvest.scores_collected == harvest.scores_expected
    assert harvest.coverage_ratio == pytest.approx(1.0)
    assert harvest.timed_out_tasks == []
    assert state.micro_scores  # collected onto session state


# ── Sync gate: partial (some time out) ───────────────────────────────────────

def _patch_slow_for(ced, slow_agent_id, delay=5.0):
    """Make scoring tasks issued by `slow_agent_id` hang (to be timed out)."""
    async def slow(self, state, move, scorer, phase):
        if scorer.agent_id == slow_agent_id:
            await asyncio.sleep(delay)
        return self._score_one_move(state, move, scorer, phase)
    ced._score_move_async = types.MethodType(slow, ced)


def test_harvest_partial_when_some_time_out():
    ced = _make_ced(4)
    state = _run_to_synthesis(ced, "sg-partial")
    _patch_slow_for(ced, "agent_1")

    harvest = asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=0.1))

    assert harvest.status == SyncGateStatus.PARTIAL
    assert 0 < harvest.scores_collected < harvest.scores_expected
    assert 0.0 < harvest.coverage_ratio < 1.0
    assert harvest.timed_out_tasks, "timed-out tasks must be recorded"
    # every timed-out task id is for the slow agent
    assert all(t.endswith(":agent_1") for t in harvest.timed_out_tasks)


# ── Sync gate: timeout (all time out) ────────────────────────────────────────

def test_harvest_timeout_when_all_time_out():
    ced = _make_ced(4)
    state = _run_to_synthesis(ced, "sg-timeout")

    async def all_slow(self, state, move, scorer, phase):
        await asyncio.sleep(5.0)
        return self._score_one_move(state, move, scorer, phase)
    ced._score_move_async = types.MethodType(all_slow, ced)

    harvest = asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=0.1))
    assert harvest.status == SyncGateStatus.TIMEOUT
    assert harvest.scores_collected == 0
    assert len(harvest.timed_out_tasks) == harvest.scores_expected


# ── Sync gate: unavailable (no scores possible) ──────────────────────────────

def test_harvest_unavailable_when_no_moves():
    ced = _make_ced(4)
    state = ced.create_session(EPI_Q, session_id="sg-unavail")  # no synthesis moves
    harvest = asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=1.0))
    assert harvest.status == SyncGateStatus.UNAVAILABLE
    assert harvest.scores_expected == 0
    assert harvest.scores_collected == 0


def test_scoring_failure_does_not_crash_and_is_recorded():
    ced = _make_ced(4)
    state = _run_to_synthesis(ced, "sg-fail")

    async def boom(self, state, move, scorer, phase):
        if scorer.agent_id == "agent_2":
            raise RuntimeError("provider exploded")
        return self._score_one_move(state, move, scorer, phase)
    ced._score_move_async = types.MethodType(boom, ced)

    harvest = asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=2.0))
    assert harvest.failed_tasks, "failed tasks recorded, not crashed"
    assert harvest.status == SyncGateStatus.PARTIAL


def test_no_fake_microscore_created_for_timeout_or_failure():
    """
    Timeouts and failures are recorded ONLY as harvest metadata — never as
    fabricated MicroScore records. Collected scores are exactly the successes.
    """
    ced = _make_ced(4)
    state = _run_to_synthesis(ced, "sg-nofake")

    async def mixed(self, state, move, scorer, phase):
        if scorer.agent_id == "agent_1":          # will time out
            await asyncio.sleep(5.0)
        if scorer.agent_id == "agent_2":          # will fail
            raise RuntimeError("provider down")
        return self._score_one_move(state, move, scorer, phase)
    ced._score_move_async = types.MethodType(mixed, ced)

    harvest = asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=0.1))

    # Both failure modes were recorded as metadata.
    assert harvest.timed_out_tasks and harvest.failed_tasks
    # No placeholder/fake score was fabricated for them.
    assert all(ms.provider_status != ProviderStatus.TIMEOUT for ms in state.micro_scores)
    # Collected == successes only (voters agent_0 + agent_3); timed-out/failed excluded.
    successes = sum(
        1 for _move, scorer in ced._move_score_pairs(state, DialogPhase.SYNTHESIS)
        if scorer.agent_id in ("agent_0", "agent_3")
    )
    assert harvest.scores_collected == len(state.micro_scores) == successes
    assert harvest.scores_collected < harvest.scores_expected


# ── Final response still produced after a timeout ────────────────────────────

def test_final_response_still_produced_after_timeout():
    ced = _make_ced(4)
    state = _run_to_synthesis(ced, "sg-final")
    _patch_slow_for(ced, "agent_1")
    asyncio.run(ced.harvest_shadow_scores(state, timeout_seconds=0.1))  # partial

    ced.score_section_drafts("sg-final")
    ced.assemble_sections("sg-final")
    final = ced.run_ratification_phase("sg-final")

    assert final is not None
    assert final.socratic_leaderboard is not None
    assert final.socratic_leaderboard.leaderboard_status == LeaderboardStatus.PARTIAL
    assert final.synthesis is not None


# ── Leaderboard aggregation ──────────────────────────────────────────────────

def test_leaderboard_average_and_cumulative():
    ced = _make_ced(4)
    state = ced.create_session(EPI_Q, session_id="lb-agg")
    # agent_0 scored 8.0 and 6.0 (avg 7.0, cum 14.0); agent_1 scored 9.0 (avg 9.0).
    state.micro_scores = [
        MicroScore(session_id="lb-agg", output_id="m0", phase=DialogPhase.SYNTHESIS,
                   author_agent_id="agent_0", voter_agent_id="agent_1", score_breakdown=_bd(8.0)),
        MicroScore(session_id="lb-agg", output_id="m0", phase=DialogPhase.SYNTHESIS,
                   author_agent_id="agent_0", voter_agent_id="agent_2", score_breakdown=_bd(6.0)),
        MicroScore(session_id="lb-agg", output_id="m1", phase=DialogPhase.SYNTHESIS,
                   author_agent_id="agent_1", voter_agent_id="agent_0", score_breakdown=_bd(9.0)),
    ]
    harvest = ShadowScoreHarvest(session_id="lb-agg", scores_expected=3,
                                 scores_collected=3, coverage_ratio=1.0,
                                 status=SyncGateStatus.COMPLETE)
    lb = ced.build_epistemic_leaderboard(state, harvest)

    assert lb.average_scores_by_agent["agent_0"] == pytest.approx(7.0)
    assert lb.cumulative_scores_by_agent["agent_0"] == pytest.approx(14.0)
    assert lb.average_scores_by_agent["agent_1"] == pytest.approx(9.0)
    assert lb.top_contributors[0] == "agent_1"   # highest average first
    assert lb.leaderboard_status == LeaderboardStatus.COMPLETE
    assert lb.interpretation_warning == LEADERBOARD_INTERPRETATION_WARNING


def test_leaderboard_status_partial():
    ced = _make_ced(4)
    state = ced.create_session(EPI_Q, session_id="lb-part")
    state.micro_scores = [
        MicroScore(session_id="lb-part", output_id="m0", phase=DialogPhase.SYNTHESIS,
                   author_agent_id="agent_0", voter_agent_id="agent_1", score_breakdown=_bd(7.0)),
    ]
    harvest = ShadowScoreHarvest(session_id="lb-part", scores_expected=4,
                                 scores_collected=1, coverage_ratio=0.25,
                                 status=SyncGateStatus.PARTIAL)
    lb = ced.build_epistemic_leaderboard(state, harvest)
    assert lb.leaderboard_status == LeaderboardStatus.PARTIAL
    assert lb.notable_events  # records the partial coverage


def test_leaderboard_status_unavailable():
    ced = _make_ced(4)
    state = ced.create_session(EPI_Q, session_id="lb-unavail")
    harvest = ShadowScoreHarvest(session_id="lb-unavail", scores_expected=0,
                                 scores_collected=0, coverage_ratio=0.0,
                                 status=SyncGateStatus.UNAVAILABLE)
    lb = ced.build_epistemic_leaderboard(state, harvest)
    assert lb.leaderboard_status == LeaderboardStatus.UNAVAILABLE


def test_leaderboard_status_complete_on_full_run():
    ced = _make_ced(4)
    final = ced.run_session(EPI_Q, session_id="lb-full")
    lb = final.socratic_leaderboard
    assert lb.leaderboard_status == LeaderboardStatus.COMPLETE
    assert lb.coverage_ratio == pytest.approx(1.0)
    assert set(lb.average_scores_by_agent) == {f"agent_{i}" for i in range(4)}
    for v in lb.average_scores_by_agent.values():
        assert 0.0 <= v <= 10.0
    assert lb.interpretation_warning == LEADERBOARD_INTERPRETATION_WARNING


# ── Minimal Awareness ─────────────────────────────────────────────────────────

_FORBIDDEN_AGENTSTATE_FIELDS = [
    "micro_scores", "section_scores", "draft_scorecards", "socratic_leaderboard",
    "epistemic_leaderboard", "score_breakdown", "ranking", "score_coverage",
    "scores_by_phase", "leaderboard",
]


def test_agentstate_has_no_scores_or_leaderboard():
    ced = _make_ced(4)
    ced.run_session(EPI_Q, session_id="ma")
    state = ced.get_session("ma")
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in _FORBIDDEN_AGENTSTATE_FIELDS:
            assert forbidden not in dumped, f"AgentState leaked '{forbidden}'"


def test_leaderboard_lives_on_session_not_agentstate():
    ced = _make_ced(4)
    ced.run_session(EPI_Q, session_id="ma2")
    state = ced.get_session("ma2")
    assert state.epistemic_leaderboard is not None         # CED-owned
    for ast in state.agent_states.values():
        assert not hasattr(ast, "epistemic_leaderboard")
        assert not hasattr(ast, "micro_scores")


# ── FinalResponse contract ───────────────────────────────────────────────────

def test_final_response_separates_synthesis_from_leaderboard():
    ced = _make_ced(4)
    final = ced.run_session(EPI_Q, session_id="fr-sep")
    assert isinstance(final.synthesis, AssembledAnswer)
    assert isinstance(final.socratic_leaderboard, EpistemicLeaderboard)
    assert final.ratification_status in {"ratified", "blocked", "unresolved"}


def test_final_response_has_audit_summary():
    ced = _make_ced(4)
    final = ced.run_session(EPI_Q, session_id="fr-audit")
    audit = final.audit_summary
    for key in ("phases_completed", "final_evaluator", "role_history_summary",
                "score_coverage", "leaderboard_status"):
        assert key in audit
    assert audit["score_coverage"]["sync_gate_status"] in {s.value for s in SyncGateStatus}


def test_final_response_does_not_expose_raw_micro_scores():
    ced = _make_ced(4)
    final = ced.run_session(EPI_Q, session_id="fr-raw")
    blob = json.dumps(final.model_dump(), default=str)
    # raw MicroScore / SectionScore-only fields must not appear anywhere
    assert "score_breakdown" not in blob
    assert "grounded_creativity" not in blob


def test_existing_ratification_still_works():
    ced = _make_ced(4)
    final = ced.run_session(EPI_Q, session_id="fr-rat")
    assert final.ratified is True
    assert final.ratification_status == "ratified"
    assert final.answer  # backward-compatible field still populated

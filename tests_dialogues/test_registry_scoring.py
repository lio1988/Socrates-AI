"""
Phase 8C.2 — registry-backed peer scoring.

In registry mode, move-level shadow scoring AND section-level scoring are routed
through CouncilProviderRegistry providers (not self.agents/FakeProvider). CED
validates + aggregates; providers judge. Failed/invalid/timeout scores stay
MISSING — never fabricated. voter != author; every score attributed to a provider.
"""

import asyncio
from unittest.mock import patch

import pytest

from backend.dialogues.models import (
    DialogPhase, ShadowScoringMode, LeaderboardStatus, SyncGateStatus,
    TaskKind, ProviderResponse, ProviderStatus,
)
from backend.dialogues.ced import CEDOrchestrator, SCORED_PHASES, PHASE_RUBRICS
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)

Q = "Is knowledge merely justified true belief?"


def _build(provs, **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pr in provs:
        reg.register(pr)
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _run(provs, sid, **kw):
    ced = _build(provs, **kw)
    final = asyncio.run(ced.run_registry_session(Q, session_id=sid))
    return ced, ced.get_session(sid), final


def _scripts(n=3, **kw):
    return [ScriptedMockProvider(f"p_{i}", **kw) for i in range(n)]


# ── Failure-at-scoring providers (valid deliberation, fail only at scoring) ───

class _ScoreTimeout(ScriptedMockProvider):
    async def generate_agent_move(self, task, agent_state):
        if task.task_kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE):
            return ProviderResponse(provider_id=self.provider_id, agent_id=task.agent_id,
                                    status=ProviderStatus.TIMEOUT, error_message="score timeout")
        return await super().generate_agent_move(task, agent_state)


class _ScoreInvalidJSON(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE):
            return "<<< not json >>>"
        return await super()._produce_raw_text(task, agent_state)


class _ScoreSchemaError(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE):
            import json
            return json.dumps({"content": "not-a-dict"})   # fails AgentMove schema
        return await super()._produce_raw_text(task, agent_state)


# 1 + 2 + 5 — scoring routed through registry providers ───────────────────────

def test_shadow_scoring_uses_registry_providers():
    _ced, st, _f = _run(_scripts(3), "rs-1")
    assert st.micro_scores
    provider_ids = {"p_0", "p_1", "p_2"}
    assert all(m.provider_id in provider_ids for m in st.micro_scores)
    assert all(m.voter_agent_id in provider_ids for m in st.micro_scores)   # voters are providers


def test_no_self_agents_voters_in_registry_scoring():
    _ced, st, _f = _run(_scripts(3), "rs-2")
    agent_ids = {"agent_0", "agent_1", "agent_2", "agent_3"}
    # voters are NEVER the council agents (self.agents) in registry mode
    assert not ({m.voter_agent_id for m in st.micro_scores} & agent_ids)


# 3 + 4 — author/voter present, voter != author ──────────────────────────────

def test_every_microscore_has_author_and_voter_distinct():
    _ced, st, _f = _run(_scripts(3), "rs-3")
    for m in st.micro_scores:
        assert m.author_agent_id and m.voter_agent_id
        assert m.voter_agent_id != m.author_agent_id


def test_no_provider_scores_its_own_move():
    _ced, st, _f = _run(_scripts(3), "rs-4")
    producer = {m.move_id: m.provider_id for m in st.moves}
    for ms in st.micro_scores:
        assert ms.provider_id != producer.get(ms.output_id)


# 6 + 7 — all scorers fail → no fabricated scores, honest failed status ───────

def test_all_scorers_fail_no_fabrication():
    _ced, st, final = _run([_ScoreTimeout(f"f_{i}") for i in range(3)], "rs-allfail")
    assert st.micro_scores == []
    assert st.failed_score_tasks
    assert final.socratic_leaderboard.leaderboard_status in (
        LeaderboardStatus.FAILED, LeaderboardStatus.UNAVAILABLE)
    assert st.shadow_harvest.status in (SyncGateStatus.TIMEOUT, SyncGateStatus.FAILED)
    assert final.audit_summary["scoring"]["scores_collected"] == 0


# 8 — one scorer fails, others succeed → partial, only valid scores ──────────

def test_partial_scoring_uses_only_valid_scores():
    _ced, st, final = _run([ScriptedMockProvider("p_ok1"), ScriptedMockProvider("p_ok2"),
                            _ScoreTimeout("p_bad")], "rs-partial")
    assert st.micro_scores                       # some valid
    assert st.failed_score_tasks                 # some failed
    assert all(m.provider_id != "p_bad" for m in st.micro_scores)   # bad scores excluded
    assert st.shadow_harvest.status == SyncGateStatus.PARTIAL
    assert final.socratic_leaderboard.leaderboard_status == LeaderboardStatus.PARTIAL


# 9-13 — shadow_scoring_mode through registry ────────────────────────────────

def test_mode_all_phases_scores_all_phases():
    _ced, st, _f = _run(_scripts(3), "rs-all", shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    assert {m.phase for m in st.micro_scores} == set(SCORED_PHASES)


def test_mode_synthesis_only():
    _ced, st, _f = _run(_scripts(3), "rs-syn", shadow_scoring_mode=ShadowScoringMode.SYNTHESIS_ONLY)
    assert {m.phase for m in st.micro_scores} == {DialogPhase.SYNTHESIS}


def test_mode_sampled_deterministic():
    _ced, st, _f = _run(_scripts(3), "rs-sam", shadow_scoring_mode=ShadowScoringMode.SAMPLED)
    assert {m.phase for m in st.micro_scores} == {DialogPhase.OPENING, DialogPhase.SYNTHESIS}


def test_mode_off_no_scores_disabled():
    _ced, st, final = _run(_scripts(3), "rs-off", shadow_scoring_mode=ShadowScoringMode.OFF)
    assert st.micro_scores == []
    assert final.socratic_leaderboard.leaderboard_status == LeaderboardStatus.DISABLED
    assert st.shadow_harvest.status == SyncGateStatus.DISABLED


def test_socratic_opening_scored_with_rubric():
    _ced, st, _f = _run(_scripts(3), "rs-open")
    opening = [m for m in st.micro_scores if m.phase == DialogPhase.OPENING]
    assert opening
    assert all(m.rubric_name == PHASE_RUBRICS[DialogPhase.OPENING][0] for m in opening)


# 14 — section scoring through registry ──────────────────────────────────────

def test_section_scoring_uses_registry_providers():
    _ced, st, _f = _run(_scripts(3), "rs-sec")
    section_scores = [s for c in st.draft_scorecards for s in c.section_scores]
    assert section_scores
    assert all(s.provider_id in {"p_0", "p_1", "p_2"} for s in section_scores)
    assert all(s.voter_agent_id != s.author_agent_id for s in section_scores)


# 15-17 — scoring failures stay missing, audited, never zero ──────────────────

@pytest.mark.parametrize("cls,sid", [
    (_ScoreInvalidJSON, "rs-badjson"),
    (_ScoreSchemaError, "rs-badschema"),
    (_ScoreTimeout, "rs-totimeout"),
])
def test_scoring_failure_missing_not_zero(cls, sid):
    # 2 good + 1 failing scorer → failures recorded, no zero scores injected
    _ced, st, final = _run([ScriptedMockProvider("p_ok1"), ScriptedMockProvider("p_ok2"),
                            cls("p_fail")], sid)
    assert st.failed_score_tasks
    assert all(m.provider_id != "p_fail" for m in st.micro_scores)
    # no fabricated zero: every recorded score has a real (non-zero-only) breakdown
    assert all(m.overall_score is not None for m in st.micro_scores)


# 18 — determinism ───────────────────────────────────────────────────────────

def test_registry_scoring_deterministic():
    def sig(sid):
        ced, st, final = _run(_scripts(3), sid)
        return {
            "move_ids": [m.move_id for m in st.moves],
            "score_task_ids": sorted(e.task_id for e in st.task_log
                                     if e.task_kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE)),
            "micro": sorted((m.output_id, m.voter_agent_id, round(m.overall_score, 4))
                            for m in st.micro_scores),
            "scores_by_phase": final.audit_summary["scoring"]["scores_by_phase"],
            "leaderboard": final.socratic_leaderboard.average_scores_by_agent,
            "winners": {x.section_name.value: x.selected_author_agent_id
                        for x in final.synthesis.sections},
            "expected": final.audit_summary["scoring"]["scores_expected"],
        }
    assert sig("rs-det") == sig("rs-det")


# 19 — async latency does not change score identity / winners ────────────────

def test_latency_does_not_change_scoring():
    def run(delays, sid):
        provs = [ScriptedMockProvider(f"p_{i}", delay_seconds=d) for i, d in enumerate(delays)]
        ced = _build(provs)
        final = asyncio.run(ced.run_registry_session(Q, session_id=sid, timeout_seconds=5.0))
        st = ced.get_session(sid)
        return (
            [m.move_id for m in st.moves],
            sorted(e.task_id for e in st.task_log if e.task_kind == TaskKind.MOVE_SCORE),
            {x.section_name.value: x.selected_author_agent_id for x in final.synthesis.sections},
        )
    a = run([0.05, 0.0, 0.0], "rs-lat")
    b = run([0.0, 0.0, 0.0], "rs-lat")
    assert a == b


# 20 — minimal awareness in scoring tasks ────────────────────────────────────

def test_scoring_task_minimal_awareness():
    ced = _build(_scripts(3))
    reg = ced.registry
    orig = reg.run_adapter
    captured = []

    async def cap(adapter, task, agent_state, timeout_seconds=None):
        if task.task_kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE):
            captured.append(task)
        return await orig(adapter, task, agent_state, timeout_seconds)

    with patch.object(reg, "run_adapter", cap):
        asyncio.run(ced.run_registry_session(Q, session_id="rs-ma"))

    assert captured
    for task in captured:
        blob = (str(task.context) + " " + str(task.output_schema)).lower()
        for kw in ("leaderboard", "overall_score", "average_scores", "coverage_ratio",
                   "task_log", "provider_status_summary", "audit"):
            assert kw not in blob
    state = ced.get_session("rs-ma")
    for ast in state.agent_states.values():
        d = ast.model_dump()
        for kw in ("micro_scores", "draft_scorecards", "leaderboard", "failed_score_tasks"):
            assert kw not in d

"""
Phase 16 — autonomy & self-healing: the inquiry cycle (the system studies its
own open questions), real quarantine exclusion (with quorum protection), and
the diversity guard (content-similarity herding detector). Offline, no live.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, DialogPhase, ProviderStatus, SessionState, TaskLogEntry,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider
from backend.dialogues.self_improvement import EpistemicLessonStore, SeatHealthTracker
from backend.dialogues.living_system import OpenQuestionLedger, run_inquiry_cycle

Q = "Is knowledge merely justified true belief?"


def _ced(seat_ids=("m_a", "m_b"), **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pid in seat_ids:
        reg.register(ScriptedMockProvider(pid))
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _quarantined_health(seat="m_bad", n=6):
    health = SeatHealthTracker()
    st = SessionState(session_id="s", question="q")
    for _ in range(n):
        st.task_log.append(TaskLogEntry(task_id="t", move_id=None, session_id="s",
                                        phase=DialogPhase.SYNTHESIS, agent_id="a",
                                        assigned_role=AgentRole.SYNTHESIZER,
                                        provider_id=seat, provider_status=ProviderStatus.TIMEOUT))
    health.ingest_session(st)
    return health


# ── autonomous inquiry cycle ──────────────────────────────────────────────────

def test_inquiry_cycle_studies_and_resolves_open_questions():
    store, ledger = EpistemicLessonStore(), OpenQuestionLedger()
    ced = _ced(lesson_store=store, open_questions=ledger)
    ledger.add("What is the nature of collective intelligence?", "quorum_failure", "old")
    rep = asyncio.run(run_inquiry_cycle(ced, max_inquiries=1))
    assert rep["inquiries_run"] == 1
    assert rep["results"][0]["ratified"] is True
    assert rep["resolved_total"] == 1                  # the open question got answered
    assert len(store) == 1                             # and taught a lesson


def test_inquiry_cycle_without_ledger_is_a_noop():
    ced = _ced()
    rep = asyncio.run(run_inquiry_cycle(ced))
    assert rep["inquiries_run"] == 0


def test_inquiry_cycle_session_ids_do_not_collide():
    store, ledger = EpistemicLessonStore(), OpenQuestionLedger()
    ced = _ced(lesson_store=store, open_questions=ledger)
    ledger.add("First open question about knowledge?", "blind_spot", "s1")
    r1 = asyncio.run(run_inquiry_cycle(ced, max_inquiries=1))
    ledger.add("Second open question about wisdom?", "blind_spot", "s2")
    r2 = asyncio.run(run_inquiry_cycle(ced, max_inquiries=1))
    assert r1["results"][0]["session_id"] != r2["results"][0]["session_id"]


# ── self-healing: quarantine actually excludes (all paths) ────────────────────

def test_quarantined_seat_excluded_from_every_path():
    ced = _ced(seat_ids=("m_a", "m_b", "m_bad"), seat_health=_quarantined_health())
    final = asyncio.run(ced.run_registry_session(Q, session_id="heal"))
    assert final.ratified is True
    assert final.audit_summary["quarantine_excluded"] == ["m_bad"]
    used = {e.provider_id for e in ced.get_session("heal").task_log if e.provider_id}
    assert "m_bad" not in used                          # deliberation+scoring+ratification


def test_quorum_protection_keeps_shaky_seat_when_needed():
    # 2 seats, 1 quarantined → excluding would kill quorum → keep it (honest)
    ced = _ced(seat_ids=("m_a", "m_bad"), seat_health=_quarantined_health())
    assert ced._quarantine_exclusions() == []
    final = asyncio.run(ced.run_registry_session(Q, session_id="keep"))
    assert final.ratified is True


def test_roster_reflects_actual_room():
    ced = _ced(seat_ids=("m_a", "m_b", "m_bad"), seat_health=_quarantined_health())
    seats = {r["seat"] for r in ced._council_roster()}
    assert seats == {"m_a", "m_b"}                      # excluded seat not "in the room"


# ── diversity guard (content-similarity herding detector) ─────────────────────

def _state_with_contents(ced, contents, conf=0.6, sid="div"):
    st = SessionState(session_id=sid, question=Q)
    ced._sessions[sid] = st
    for i, c in enumerate(contents):
        st.moves.append(AgentMove(task_id="t", agent_id=f"a{i}", role=AgentRole.SYNTHESIZER,
                                  phase=DialogPhase.INITIAL_RESPONSE,
                                  content=c, confidence=conf))
    return st


def test_identical_responses_trigger_diversity_alert():
    ced = _ced()
    st = _state_with_contents(ced, [{"thesis": "knowledge is collective and social"}] * 2)
    ad = ced._adaptive_dialectic(st)
    assert ad["response_diversity"] == 0.0 and ad["low_diversity_triggered"] is True
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "low_diversity_alert" in ctx
    assert "shared assumption" in ctx["low_diversity_alert"]


def test_diverse_responses_do_not_trigger():
    ced = _ced()
    st = _state_with_contents(ced, [
        {"thesis": "knowledge emerges from individual rational reflection"},
        {"thesis": "epistemic communities validate testimony socially together"},
    ])
    ad = ced._adaptive_dialectic(st)
    assert ad["response_diversity"] > ced.LOW_DIVERSITY_FLOOR
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "low_diversity_alert" not in ctx


def test_devils_advocate_takes_precedence_over_diversity_alert():
    ced = _ced()
    st = _state_with_contents(ced, [{"thesis": "same answer here"}] * 2, conf=0.9)
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "devils_advocate_mandate" in ctx             # confidence trigger wins
    assert "low_diversity_alert" not in ctx             # one mandate at a time


def test_diversity_is_audited():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="divaudit"))
    ad = final.audit_summary["adaptive_dialectic"]
    assert "response_diversity" in ad and "low_diversity_triggered" in ad
    assert ad["low_diversity_triggered"] is False       # mock responses differ by role

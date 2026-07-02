"""
Phase 13 — Self-Improvement Layer (A: seat health, B: epistemic lessons).

Proves the system gets better with use — mechanically and invariant-safely:
seat telemetry is content-blind; lessons are PUBLIC artifacts from RATIFIED
sessions only; defaults-off changes nothing; telemetry can never break a session.
All offline, no live calls.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentRole, DialogPhase, ProviderStatus, SessionState, TaskLogEntry,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider
from backend.dialogues.self_improvement import (
    SeatHealthTracker, SeatStats, EpistemicLessonStore, Lesson, extract_lesson,
    QUARANTINE_MIN_TASKS, QUARANTINE_FAILURE_RATE,
)

Q = "Is knowledge merely justified true belief?"


def _ced(**kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    reg.register(ScriptedMockProvider("m_a"))
    reg.register(ScriptedMockProvider("m_b"))
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _log_entry(seat: str, status: ProviderStatus, ok: bool) -> TaskLogEntry:
    return TaskLogEntry(task_id="t", move_id=("m" if ok else None), session_id="s",
                        phase=DialogPhase.SYNTHESIS, agent_id="a",
                        assigned_role=AgentRole.SYNTHESIZER,
                        provider_id=seat, provider_status=status)


def _state_with_failures(seat="bad_seat", n_fail=6, n_ok=0) -> SessionState:
    st = SessionState(session_id="s", question=Q)
    for _ in range(n_fail):
        st.task_log.append(_log_entry(seat, ProviderStatus.TIMEOUT, ok=False))
    for _ in range(n_ok):
        st.task_log.append(_log_entry(seat, ProviderStatus.OK, ok=True))
    return st


# ── A. SeatHealthTracker ──────────────────────────────────────────────────────

def test_seat_health_ingests_and_computes_failure_rate():
    h = SeatHealthTracker()
    h.ingest_session(_state_with_failures("s1", n_fail=3, n_ok=1))
    s = h.stats()["s1"]
    assert s.tasks == 4 and s.ok == 1
    assert s.failure_rate == pytest.approx(0.75)
    assert s.by_status["timeout"] == 3


def test_quarantine_is_deterministic_and_evidence_gated():
    h = SeatHealthTracker()
    # too few tasks → NOT quarantined even at 100% failure (insufficient evidence)
    h.ingest_session(_state_with_failures("few", n_fail=QUARANTINE_MIN_TASKS - 1))
    assert "few" not in h.quarantined()
    # enough tasks + chronic failure → quarantined
    h.ingest_session(_state_with_failures("bad", n_fail=QUARANTINE_MIN_TASKS))
    assert "bad" in h.quarantined()
    # healthy seat never quarantined
    h.ingest_session(_state_with_failures("good", n_fail=0, n_ok=10))
    assert "good" not in h.quarantined()


def test_rank_seats_prefers_reliable_then_unknown_first():
    h = SeatHealthTracker()
    h.ingest_session(_state_with_failures("flaky", n_fail=5, n_ok=5))
    h.ingest_session(_state_with_failures("solid", n_fail=0, n_ok=10))
    ranked = h.rank_seats(["flaky", "solid", "brand_new"])
    assert ranked[0] == "brand_new"          # unknown deserves a chance
    assert ranked[1] == "solid"              # then most reliable
    assert ranked[2] == "flaky"


def test_recommendations_name_the_observed_failure_mode():
    h = SeatHealthTracker()
    h.ingest_session(_state_with_failures("slow", n_fail=6, n_ok=2))   # timeouts
    recs = " | ".join(h.recommendations())
    assert "CED_LIVE_TIMEOUT" in recs and "slow" in recs
    assert "QUARANTINE" in recs


def test_seat_health_persistence_round_trip(tmp_path):
    h = SeatHealthTracker()
    h.ingest_session(_state_with_failures("s1", n_fail=2, n_ok=8))
    path = str(tmp_path / "health.json")
    h.save(path)
    loaded = SeatHealthTracker.load(path)
    assert loaded.stats()["s1"].tasks == 10 and loaded.stats()["s1"].ok == 8
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "WRONG"}', encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        SeatHealthTracker.load(str(bad))


# ── B. EpistemicLessonStore ───────────────────────────────────────────────────

def _ratified_session(store=None, sid="ls1", question=Q):
    ced = _ced(lesson_store=store)
    final = asyncio.run(ced.run_registry_session(question, session_id=sid))
    return ced, ced.get_session(sid), final


def test_lesson_extracted_only_from_ratified():
    _, state, final = _ratified_session()
    lesson = extract_lesson(state, final)
    assert lesson is not None
    assert lesson.core_answer and lesson.final_verdict
    # a non-ratified outcome yields NO lesson (the store never learns from those)
    final.ratified = False
    assert extract_lesson(state, final) is None


def test_lessons_are_public_only():
    store = EpistemicLessonStore()
    _ratified_session(store)
    pub = store.relevant(Q, k=1)[0]
    assert set(pub) == {"question", "final_verdict", "core_answer",
                        "caveats", "decisive_objections"}
    blob = str(pub).lower()
    for forbidden in ("score", "leaderboard", "provider_id", "task_log", "m_a", "m_b"):
        assert forbidden not in blob


def test_relevance_is_keyword_overlap_and_bounded():
    store = EpistemicLessonStore(lessons=[
        Lesson(question="Is knowledge justified true belief?", final_verdict="v",
               core_answer="Gettier cases block sufficiency"),
        Lesson(question="Should tomatoes be refrigerated?", final_verdict="v",
               core_answer="cold damages flavor compounds"),
    ])
    hits = store.relevant("What is knowledge and is belief enough?", k=3)
    assert len(hits) == 1                                  # tomato lesson irrelevant
    assert "Gettier" in hits[0]["core_answer"]
    assert store.relevant("ξζψ", k=3) == []                # no keywords → nothing


def test_lesson_store_persistence_round_trip(tmp_path):
    store = EpistemicLessonStore()
    _ratified_session(store)
    path = str(tmp_path / "lessons.json")
    store.save(path)
    loaded = EpistemicLessonStore.load(path)
    assert len(loaded) == 1
    assert loaded.relevant(Q, k=1)


# ── CED integration: the loop closes ─────────────────────────────────────────

def test_session_records_lesson_and_next_session_receives_it():
    store = EpistemicLessonStore()
    _, _, f1 = _ratified_session(store, sid="loop1")
    assert f1.audit_summary.get("lesson_recorded") is True

    ced = _ced(lesson_store=store)
    asyncio.run(ced.run_registry_session(
        "Is justified true belief enough for knowledge?", session_id="loop2"))
    st2 = ced.get_session("loop2")
    ctx = ced._registry_phase_context(st2, DialogPhase.INITIAL_RESPONSE, "agent_0")
    lessons = ctx.get("lessons_from_prior_dialogues", [])
    assert lessons and any("justified true belief" in l["question"] for l in lessons)


def test_defaults_off_changes_nothing():
    ced = _ced()                                            # no stores
    final = asyncio.run(ced.run_registry_session(Q, session_id="noop"))
    assert final.ratified is True
    assert "lesson_recorded" not in final.audit_summary
    st = ced.get_session("noop")
    ctx = ced._registry_phase_context(st, DialogPhase.SYNTHESIS, "agent_0")
    assert "lessons_from_prior_dialogues" not in ctx


def test_telemetry_failure_never_breaks_a_session():
    class ExplodingStore:
        def relevant(self, *a, **k):
            return []
        def ingest(self, *a, **k):
            raise RuntimeError("disk full")

    ced = _ced(lesson_store=ExplodingStore())
    final = asyncio.run(ced.run_registry_session(Q, session_id="boom"))
    assert final.ratified is True                            # session survived
    assert final.audit_summary.get("self_improvement_error") is True

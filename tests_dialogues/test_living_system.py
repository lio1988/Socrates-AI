"""
Phase 15 — The Living System: curiosity (open questions), memory consolidation
("sleep"), homeostasis (vitals). All mechanical/AI-with-honest-fallback,
invariant-safe, offline. No live calls.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentRole, DialogPhase, ProviderResponse, ProviderStatus, TaskKind,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, TimeoutScriptedProvider,
    parse_and_validate_move,
)
from backend.dialogues.reasoning_prompts import LESSON_CONSOLIDATION_DIRECTIVE
from backend.dialogues.self_improvement import EpistemicLessonStore, Lesson, SeatHealthTracker
from backend.dialogues.living_system import (
    OpenQuestionLedger, consolidate_lessons, compute_vitals, find_clusters,
)

Q = "Is knowledge merely justified true belief?"


def _ced(providers=None, **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pr in providers or [ScriptedMockProvider("m_a"), ScriptedMockProvider("m_b")]:
        reg.register(pr)
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _related_lessons(n=3):
    return [Lesson(question=f"Is knowledge justified true belief (variant {i})?",
                   final_verdict=f"v{i}",
                   core_answer="Gettier cases show justified true belief is insufficient "
                               "for knowledge without anti-luck conditions")
            for i in range(n)]


# ── curiosity: the OpenQuestionLedger ─────────────────────────────────────────

def test_quorum_failure_becomes_the_loudest_open_question():
    ledger = OpenQuestionLedger()
    ced = _ced([ScriptedMockProvider("ok"), TimeoutScriptedProvider()],
               open_questions=ledger)
    final = asyncio.run(ced.run_registry_session("What is consciousness?", session_id="qf"))
    assert final.ratified is False
    agenda = ledger.propose_inquiries(3)
    assert agenda[0]["question"] == "What is consciousness?"
    assert agenda[0]["source"] == "quorum_failure"


def test_ratified_session_harvests_blind_spot_and_resolves_open_question():
    ledger = OpenQuestionLedger()
    ledger.add(Q, "quorum_failure", "old_session")            # previously failed
    ced = _ced(open_questions=ledger)
    final = asyncio.run(ced.run_registry_session(Q, session_id="ok1"))
    assert final.ratified is True
    # the old open question about the SAME question is now resolved
    resolved = [q for q in ledger._questions if q.status == "resolved"]
    assert any(q.resolved_by_session == "ok1" for q in resolved)
    # and the new blind spot became a new open question
    assert any(q.source == "blind_spot" for q in ledger.open_questions())


def test_ledger_dedupes_and_prioritizes():
    ledger = OpenQuestionLedger()
    assert ledger.add("What is X?", "blind_spot", "s1") is True
    assert ledger.add("What is X?", "caveat", "s2") is False   # dedupe
    ledger.add("Why did Y fail?", "quorum_failure", "s3")
    agenda = ledger.propose_inquiries(2)
    assert agenda[0]["source"] == "quorum_failure"             # priority first


def test_ledger_persistence_round_trip(tmp_path):
    ledger = OpenQuestionLedger()
    ledger.add("open one", "blind_spot", "s1")
    path = str(tmp_path / "oq.json")
    ledger.save(path)
    loaded = OpenQuestionLedger.load(path)
    assert len(loaded.open_questions()) == 1
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "WRONG"}', encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        OpenQuestionLedger.load(str(bad))


# ── memory consolidation ("sleep") ────────────────────────────────────────────

def test_find_clusters_groups_related_lessons_only():
    lessons = _related_lessons(3) + [Lesson(question="Should tomatoes be refrigerated?",
                                            final_verdict="v", core_answer="cold ruins flavor")]
    clusters = find_clusters(lessons)
    assert len(clusters) == 1 and sorted(clusters[0]) == [0, 1, 2]


def test_consolidation_with_ai_authors_deeper_lesson():
    store = EpistemicLessonStore(lessons=_related_lessons(3))
    ced = _ced(lesson_store=store, ai_learning=True)
    rep = asyncio.run(consolidate_lessons(ced))
    assert rep["mode"] == "council" and rep["lessons_after"] == 1
    merged = store.lessons()[-1]
    assert merged.distilled_by == "consolidation_council"
    assert merged.insight and merged.transferable_principle
    assert merged.question.startswith("[consolidated ×3]")


def test_consolidation_mechanical_fallback_on_ai_failure():
    class ConsolidationFails(ScriptedMockProvider):
        async def generate_agent_move(self, task, agent_state):
            if task.task_kind == TaskKind.LESSON_CONSOLIDATION:
                return ProviderResponse(provider_id=self.provider_id, agent_id=task.agent_id,
                                        status=ProviderStatus.TIMEOUT, error_message="slow")
            return await super().generate_agent_move(task, agent_state)

    store = EpistemicLessonStore(lessons=_related_lessons(3))
    ced = _ced([ConsolidationFails("f_a"), ConsolidationFails("f_b")],
               lesson_store=store, ai_learning=True)
    rep = asyncio.run(consolidate_lessons(ced))
    assert rep["mode"] == "mechanical" and rep["lessons_after"] == 1
    assert store.lessons()[-1].distilled_by == "consolidation_mechanical"


def test_consolidation_needs_enough_evidence():
    store = EpistemicLessonStore(lessons=_related_lessons(2))   # below MIN_CLUSTER
    ced = _ced(lesson_store=store)
    rep = asyncio.run(consolidate_lessons(ced))
    assert rep["clusters_found"] == 0 and len(store.lessons()) == 2


def test_consolidation_directive_example_passes_validator():
    from backend.dialogues.models import AgentTask
    example = LESSON_CONSOLIDATION_DIRECTIVE[LESSON_CONSOLIDATION_DIRECTIVE.index('{"content"'):]
    task = AgentTask(session_id="s", agent_id="a", role=AgentRole.SYNTHESIZER,
                     phase=DialogPhase.COMPLETE, question="q",
                     task_kind=TaskKind.LESSON_CONSOLIDATION)
    move, status, err = parse_and_validate_move(example, task, meta={})
    assert status.value == "ok", err


# ── homeostasis: vitals ───────────────────────────────────────────────────────

def test_vitals_thriving_and_degrading():
    good = [{"ratified": True, "quorum_failed": False, "initial_mean_confidence": 0.7}] * 5
    v = compute_vitals(good)
    assert v["health_status"] == "thriving" and v["ratification_rate"] == 1.0

    bad = [{"ratified": False, "quorum_failed": True, "initial_mean_confidence": None}] * 5
    v2 = compute_vitals(bad)
    assert v2["health_status"] == "degrading"
    assert any("quorum" in r for r in v2["recommendations"])


def test_vitals_flag_quarantined_seats():
    health = SeatHealthTracker()
    from backend.dialogues.models import SessionState, TaskLogEntry
    st = SessionState(session_id="s", question="q")
    for _ in range(6):
        st.task_log.append(TaskLogEntry(task_id="t", move_id=None, session_id="s",
                                        phase=DialogPhase.SYNTHESIS, agent_id="a",
                                        assigned_role=AgentRole.SYNTHESIZER,
                                        provider_id="bad", provider_status=ProviderStatus.TIMEOUT))
    health.ingest_session(st)
    v = compute_vitals([{"ratified": True, "quorum_failed": False}], seat_health=health)
    assert v["health_status"] == "degrading"
    assert "bad" in str(v["recommendations"])


def test_ced_vitals_end_to_end():
    store, ledger = EpistemicLessonStore(), OpenQuestionLedger()
    ced = _ced(lesson_store=store, open_questions=ledger)
    asyncio.run(ced.run_registry_session(Q, session_id="v1"))
    v = ced.vitals()
    assert v["sessions_observed"] == 1 and v["health_status"] == "thriving"
    assert v["lessons_total"] == 1
    assert v["open_questions"] >= 1                            # blind spot harvested


def test_outcomes_recorded_on_fallback_too():
    ced = _ced([ScriptedMockProvider("ok"), TimeoutScriptedProvider()])
    asyncio.run(ced.run_registry_session(Q, session_id="fb"))
    v = ced.vitals()
    assert v["sessions_observed"] == 1 and v["quorum_failure_rate"] == 1.0

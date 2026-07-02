"""
Phase 13D — AI-in-the-loop learning (offline; mock council authors the lessons).

Proves: lessons can be AUTHORED by a council agent (through the same registry
adapters), the council reviews its own process, future sessions receive both,
AI failure falls back honestly to the mechanical extractor, defaults stay off,
and seat telemetry now learns from FAILED sessions too. No live calls.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentRole, DialogPhase, ProviderStatus, ProviderResponse, TaskKind,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, TimeoutScriptedProvider,
    parse_and_validate_move,
)
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt,
    LESSON_DISTILLATION_DIRECTIVE, PROCESS_REVIEW_DIRECTIVE,
)
from backend.dialogues.self_improvement import (
    EpistemicLessonStore, SeatHealthTracker, ProcessLesson,
)

Q = "Is knowledge merely justified true belief?"


def _ced(providers=None, **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pr in providers or [ScriptedMockProvider("m_a"), ScriptedMockProvider("m_b")]:
        reg.register(pr)
    return CEDOrchestrator(agents, p, registry=reg, **kw)


# ── AI-authored lessons ───────────────────────────────────────────────────────

def test_council_authors_the_lesson_when_ai_learning_on():
    store = EpistemicLessonStore()
    ced = _ced(lesson_store=store, ai_learning=True)
    final = asyncio.run(ced.run_registry_session(Q, session_id="ai1"))
    assert final.audit_summary["lesson_recorded"] is True
    assert final.audit_summary["lesson_distilled_by"] == "council"
    pub = store.relevant(Q, k=1)[0]
    assert pub["insight"] and pub["transferable_principle"] and pub["pitfalls"]


def test_process_review_recorded_and_injected_next_session():
    store = EpistemicLessonStore()
    ced = _ced(lesson_store=store, ai_learning=True)
    f1 = asyncio.run(ced.run_registry_session(Q, session_id="pr1"))
    assert f1.audit_summary["process_lesson_recorded"] is True
    assert store.process_guidance(1)[0]["advice_for_next_dialogue"]

    asyncio.run(ced.run_registry_session("Is JTB sufficient?", session_id="pr2"))
    st2 = ced.get_session("pr2")
    ctx = ced._registry_phase_context(st2, DialogPhase.INITIAL_RESPONSE, "agent_0")
    assert "process_lessons_from_past_dialogues" in ctx
    guidance = ctx["process_lessons_from_past_dialogues"][0]
    assert set(guidance) == {"what_worked", "what_failed", "advice_for_next_dialogue"}


def test_ai_failure_falls_back_to_mechanical_lesson():
    class DistillationFails(ScriptedMockProvider):
        async def generate_agent_move(self, task, agent_state):
            if task.task_kind in (TaskKind.LESSON_DISTILLATION, TaskKind.PROCESS_REVIEW):
                return ProviderResponse(provider_id=self.provider_id, agent_id=task.agent_id,
                                        status=ProviderStatus.TIMEOUT, error_message="slow")
            return await super().generate_agent_move(task, agent_state)

    store = EpistemicLessonStore()
    ced = _ced([DistillationFails("f_a"), DistillationFails("f_b")],
               lesson_store=store, ai_learning=True)
    final = asyncio.run(ced.run_registry_session(Q, session_id="fb1"))
    assert final.ratified is True
    assert final.audit_summary["lesson_recorded"] is True
    assert final.audit_summary["lesson_distilled_by"] == "mechanical"  # honest fallback
    assert "process_lesson_recorded" not in final.audit_summary        # none fabricated
    pub = store.relevant(Q, k=1)[0]
    assert "insight" not in pub                                        # mechanical lesson


def test_ai_learning_default_off():
    store = EpistemicLessonStore()
    ced = _ced(lesson_store=store)                                     # ai_learning=False
    final = asyncio.run(ced.run_registry_session(Q, session_id="off1"))
    assert final.audit_summary["lesson_distilled_by"] == "mechanical"
    assert "process_lesson_recorded" not in final.audit_summary
    assert not store.process_guidance(2)


# ── directives + mock payload validity ────────────────────────────────────────

def test_directives_specify_exact_fields():
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.COMPLETE,
                                      TaskKind.LESSON_DISTILLATION)
    for f in ('"insight"', '"transferable_principle"', '"pitfalls"'):
        assert f in p
    p2 = build_reasoning_system_prompt(AgentRole.REFLECTOR, DialogPhase.COMPLETE,
                                       TaskKind.PROCESS_REVIEW)
    for f in ('"what_worked"', '"what_failed"', '"advice_for_next_dialogue"'):
        assert f in p2


def test_directive_examples_pass_our_validator():
    from backend.dialogues.models import AgentTask
    for directive, kind in ((LESSON_DISTILLATION_DIRECTIVE, TaskKind.LESSON_DISTILLATION),
                            (PROCESS_REVIEW_DIRECTIVE, TaskKind.PROCESS_REVIEW)):
        example = directive[directive.index('{"content"'):]
        task = AgentTask(session_id="s", agent_id="a", role=AgentRole.SYNTHESIZER,
                         phase=DialogPhase.COMPLETE, question="q", task_kind=kind)
        move, status, err = parse_and_validate_move(example, task, meta={})
        assert status.value == "ok", (kind, err)


# ── persistence with process lessons ──────────────────────────────────────────

def test_store_round_trip_includes_process_lessons(tmp_path):
    store = EpistemicLessonStore()
    store.add_process(ProcessLesson(what_worked="w", what_failed="f",
                                    advice_for_next_dialogue="a", session_id="s"))
    path = str(tmp_path / "l.json")
    store.save(path)
    loaded = EpistemicLessonStore.load(path)
    assert loaded.process_guidance(1)[0]["advice_for_next_dialogue"] == "a"


# ── seat telemetry learns from FAILED sessions ────────────────────────────────

def test_seat_health_learns_from_quorum_failure():
    health = SeatHealthTracker()
    ced = _ced([ScriptedMockProvider("ok_seat"), TimeoutScriptedProvider()],
               seat_health=health)
    final = asyncio.run(ced.run_registry_session(Q, session_id="qf1"))
    assert final.ratified is False                                     # quorum failed
    stats = health.stats()
    assert stats["mock_scripted_timeout"].failure_rate == 1.0          # the culprit found
    assert stats["ok_seat"].failure_rate == 0.0

"""
Phase 14 — mad-scientist features, disciplined: Confidence-Adaptive Dialectic,
AI lesson retrieval (semantic relevance seam), per-topic seat skill profiles.

All triggers are mechanical (CED-owned metadata), all AI paths have honest
keyword fallbacks, topic skill stays hidden from agents. Offline, no live calls.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, DialogPhase, ProviderResponse, ProviderStatus,
    SessionState, TaskKind,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, parse_and_validate_move,
)
from backend.dialogues.reasoning_prompts import LESSON_RELEVANCE_DIRECTIVE
from backend.dialogues.self_improvement import (
    EpistemicLessonStore, Lesson, TopicSkillTracker, rank_lessons_with_council,
)

Q = "Is knowledge merely justified true belief?"


def _ced(providers=None, **kw):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for pr in providers or [ScriptedMockProvider("m_a"), ScriptedMockProvider("m_b")]:
        reg.register(pr)
    return CEDOrchestrator(agents, p, registry=reg, **kw)


def _state_with_confidences(ced, confs, sid="cad"):
    st = SessionState(session_id=sid, question=Q)
    ced._sessions[sid] = st
    for i, c in enumerate(confs):
        st.moves.append(AgentMove(task_id="t", agent_id=f"a{i}", role=AgentRole.SYNTHESIZER,
                                  phase=DialogPhase.INITIAL_RESPONSE,
                                  content={"x": 1}, confidence=c))
    return st


# ── Confidence-Adaptive Dialectic ─────────────────────────────────────────────

def test_high_consensus_confidence_triggers_devils_advocate():
    ced = _ced()
    st = _state_with_confidences(ced, [0.92, 0.88])
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "devils_advocate_mandate" in ctx
    assert "AGAINST the emerging consensus" in ctx["devils_advocate_mandate"]
    # honesty clause: no fake objections if the consensus survives
    assert "do not manufacture" in ctx["devils_advocate_mandate"]


def test_low_confidence_triggers_uncertainty_mapping():
    ced = _ced()
    st = _state_with_confidences(ced, [0.30, 0.40])
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "uncertainty_mapping_mandate" in ctx
    assert "devils_advocate_mandate" not in ctx


def test_normal_confidence_triggers_nothing():
    ced = _ced()
    st = _state_with_confidences(ced, [0.6, 0.7])
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "devils_advocate_mandate" not in ctx
    assert "uncertainty_mapping_mandate" not in ctx


def test_adaptive_state_is_audited():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="aud"))
    ad = final.audit_summary["adaptive_dialectic"]
    assert {"initial_mean_confidence", "devils_advocate_triggered",
            "uncertainty_mode_triggered"} <= set(ad)   # Phase 16 adds diversity keys
    assert isinstance(ad["initial_mean_confidence"], float)


# ── AI lesson retrieval (semantic relevance seam) ─────────────────────────────

def _seeded_store():
    store = EpistemicLessonStore(lessons=[
        Lesson(question="Is knowledge justified true belief?", final_verdict="v1",
               core_answer="Gettier cases block sufficiency of belief and knowledge"),
        Lesson(question="Is belief in knowledge justified by evidence?", final_verdict="v2",
               core_answer="justified knowledge belief requires evidence"),
    ])
    return store


def test_council_ranker_selects_and_reports_mode():
    ced = _ced(lesson_store=_seeded_store(), ai_learning=True)
    lessons, mode = asyncio.run(rank_lessons_with_council(ced, Q, k=3))
    assert mode == "council"
    assert 1 <= len(lessons) <= 2                    # mock picks first min(2, n) indices


def test_ranker_falls_back_to_keyword_on_failure():
    class RelevanceFails(ScriptedMockProvider):
        async def generate_agent_move(self, task, agent_state):
            if task.task_kind == TaskKind.LESSON_RELEVANCE:
                return ProviderResponse(provider_id=self.provider_id, agent_id=task.agent_id,
                                        status=ProviderStatus.TIMEOUT, error_message="slow")
            return await super().generate_agent_move(task, agent_state)

    ced = _ced([RelevanceFails("f_a"), RelevanceFails("f_b")],
               lesson_store=_seeded_store(), ai_learning=True)
    lessons, mode = asyncio.run(rank_lessons_with_council(ced, Q, k=3))
    assert mode == "keyword" and lessons             # honest fallback still delivers


def test_session_audit_records_retrieval_mode():
    ced = _ced(lesson_store=_seeded_store(), ai_learning=True)
    final = asyncio.run(ced.run_registry_session(Q, session_id="ret"))
    assert final.audit_summary["lesson_retrieval"] == "council"
    ced2 = _ced(lesson_store=_seeded_store())        # ai_learning off
    final2 = asyncio.run(ced2.run_registry_session(Q, session_id="ret2"))
    assert final2.audit_summary["lesson_retrieval"] == "keyword"


def test_relevance_directive_example_passes_validator():
    from backend.dialogues.models import AgentTask
    example = LESSON_RELEVANCE_DIRECTIVE[LESSON_RELEVANCE_DIRECTIVE.index('{"content"'):]
    task = AgentTask(session_id="s", agent_id="a", role=AgentRole.EMPIRICIST,
                     phase=DialogPhase.OPENING, question="q",
                     task_kind=TaskKind.LESSON_RELEVANCE)
    move, status, err = parse_and_validate_move(example, task, meta={})
    assert status.value == "ok", err


# ── per-topic seat skill profiles ─────────────────────────────────────────────

def test_topic_skill_aggregates_by_seat_and_topic():
    skill = TopicSkillTracker()
    ced = _ced(topic_skill=skill)
    final = asyncio.run(ced.run_registry_session(Q, session_id="ts"))
    assert final.ratified is True
    best = skill.best_seats("epistemology")
    assert set(best) == {"m_a", "m_b"}               # both seats profiled
    prof = skill.profile(best[0])
    assert 0.0 < prof["epistemology"] <= 10.0        # peer-scored average


def test_topic_skill_hidden_from_agents():
    skill = TopicSkillTracker()
    ced = _ced(topic_skill=skill)
    asyncio.run(ced.run_registry_session(Q, session_id="tsh"))
    st = ced.get_session("tsh")
    for phase in (DialogPhase.ELENCHUS, DialogPhase.SYNTHESIS):
        blob = str(ced._registry_phase_context(st, phase, "agent_0")).lower()
        assert "topic_skill" not in blob and "best_seats" not in blob


def test_topic_skill_persistence_round_trip(tmp_path):
    skill = TopicSkillTracker()
    ced = _ced(topic_skill=skill)
    asyncio.run(ced.run_registry_session(Q, session_id="tsp"))
    path = str(tmp_path / "skill.json")
    skill.save(path)
    loaded = TopicSkillTracker.load(path)
    assert loaded.best_seats("epistemology") == skill.best_seats("epistemology")
    assert "not proof of truth" in loaded.report()["interpretation_warning"]

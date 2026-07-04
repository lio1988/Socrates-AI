"""
Phase 24 — cross-section coherence of the blind-assembled answer.

The gap: the five sections are assembled INDEPENDENTLY (each section's winner
picked on its own), so the final answer can stitch sections from different drafts
that argue past each other — a "Frankenstein" answer — with nothing checking
coherence. Two fixes:
  (A) a mechanical fragmentation metric (how many distinct drafts the resolved
      sections came from) — CED-owned audit, hidden from agents;
  (B) a coherence directive in the RATIFICATION prompt telling the ratifier the
      answer was assembled section-by-section and to block on contradictions —
      generic (no session-specific leak, no scores, no identities).
Offline, mock only.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentRole, AssembledAnswer, AssembledSection, DialogPhase, SectionName,
    SessionState, TaskKind,
)
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, RATIFICATION_COHERENCE_NOTE,
)
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"


def _assembled(distinct_sources):
    """Build a 5-section AssembledAnswer drawn from `distinct_sources` drafts."""
    secs = [AssembledSection(section_name=n, selected_draft_id=f"d{i % distinct_sources}",
                             selected_author_agent_id="a", content="c", average_score=8.0)
            for i, n in enumerate(SectionName)]
    return AssembledAnswer(session_id="x", sections=secs)


def _ced():
    ced, _ = build_council(env={}, council_size=2)
    return ced


# ── (A) fragmentation metric ──────────────────────────────────────────────────

def test_single_source_is_coherent():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)
    st.assembled_answer = _assembled(1)
    m = ced._assembly_coherence(st)
    assert m["distinct_source_drafts"] == 1 and m["single_source"] is True
    assert m["fragmentation"] == pytest.approx(0.2)          # 1/5


def test_full_fragmentation_flagged():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)
    st.assembled_answer = _assembled(5)
    m = ced._assembly_coherence(st)
    assert m["distinct_source_drafts"] == 5 and m["single_source"] is False
    assert m["fragmentation"] == pytest.approx(1.0)


def test_unresolved_sections_excluded_from_metric():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)
    secs = list(_assembled(2).sections)
    secs[0] = AssembledSection(section_name=SectionName.CORE_ANSWER, selected_draft_id="",
                               selected_author_agent_id="", content="", average_score=0.0,
                               unresolved=True)
    st.assembled_answer = AssembledAnswer(session_id="x", sections=secs)
    m = ced._assembly_coherence(st)
    assert m["resolved_sections"] == 4                       # the unresolved one dropped


def test_no_assembly_is_safe():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)                 # assembled_answer is None
    m = ced._assembly_coherence(st)
    assert m == {"resolved_sections": 0, "distinct_source_drafts": 0,
                 "fragmentation": 0.0, "single_source": True}


def test_full_session_audits_coherence():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="ac"))
    m = final.audit_summary["assembly_coherence"]
    assert {"resolved_sections", "distinct_source_drafts", "fragmentation",
            "single_source"} <= set(m)                   # Phase 25 adds cohesion keys
    assert m["resolved_sections"] >= 1


def test_metric_hidden_from_agents():
    ced = _ced()
    asyncio.run(ced.run_registry_session(Q, session_id="ach"))
    st = ced.get_session("ach")
    for phase in (DialogPhase.ELENCHUS, DialogPhase.SYNTHESIS):
        blob = str(ced._registry_phase_context(st, phase, "agent_0")).lower()
        assert "fragmentation" not in blob and "assembly_coherence" not in blob


# ── (B) ratifier coherence directive ─────────────────────────────────────────

def test_coherence_note_only_in_ratification_prompt():
    pr = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION,
                                       TaskKind.COUNCIL_RATIFICATION, model="claude-opus-4-8")
    assert RATIFICATION_COHERENCE_NOTE.splitlines()[0] in pr
    for kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE, TaskKind.SYNTHESIS_DRAFT,
                 TaskKind.ELENCHUS_OBJECTION):
        p = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION,
                                          kind, model="claude-opus-4-8")
        assert RATIFICATION_COHERENCE_NOTE.splitlines()[0] not in p, kind


def test_coherence_note_leaks_no_scores_or_identities():
    low = RATIFICATION_COHERENCE_NOTE.lower()
    for forbidden in ("score", "confidence", "provider", "seat", "draft_id",
                      "leaderboard", "peer"):
        assert forbidden not in low, forbidden


def test_coherence_note_directs_a_blocking_objection():
    assert "blocking_objection" in RATIFICATION_COHERENCE_NOTE
    assert "target_section" in RATIFICATION_COHERENCE_NOTE
    # it must reference the actual section names it can flag
    assert "core_answer" in RATIFICATION_COHERENCE_NOTE
    assert "crucial_stress_test" in RATIFICATION_COHERENCE_NOTE

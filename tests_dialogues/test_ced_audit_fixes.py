"""
CED audit fixes — lock in three guarantees:

  #1 deterministic, reproducible pipeline (deterministic move_id → reproducible
     shadow scores, leaderboard, and section winners; ids unique)
  #3 clean move content (no stray `confidence` key; it lives on move.confidence)
  #2 every deliberation phase is shadow-scored (incl. the Socratic opening),
     and the leaderboard credits all phases
"""

import pytest

from backend.dialogues import build_demo_orchestrator
from backend.dialogues.ced import SCORED_PHASES
from backend.dialogues.models import DialogPhase

Q = "Is knowledge merely justified true belief?"


def _run(session_id="ced-fix"):
    ced = build_demo_orchestrator(4)
    final = ced.run_session(Q, session_id=session_id)
    return ced, ced.get_session(session_id), final


# ── #1 Deterministic / reproducible pipeline ─────────────────────────────────

def test_move_ids_are_deterministic_and_unique():
    _c1, s1, _ = _run("det-a")
    _c2, s2, _ = _run("det-b")   # same question, different session id
    ids1 = [m.move_id for m in s1.moves]
    assert len(set(ids1)) == len(ids1), "move ids must be unique"
    # same session id → identical ids (full reproducibility)
    _c3, s3, _ = _run("det-a")
    assert [m.move_id for m in s3.moves] == ids1
    # ids are not random UUID hex of the old style — they are hash-derived but stable
    assert all(m.move_id.startswith("move_") for m in s1.moves)


def test_section_winners_and_leaderboard_reproducible():
    _c1, s1, _ = _run("repro-1")
    _c2, s2, _ = _run("repro-1")
    w1 = {x.section_name: x.selected_author_agent_id for x in s1.assembled_answer.sections}
    w2 = {x.section_name: x.selected_author_agent_id for x in s2.assembled_answer.sections}
    assert w1 == w2
    assert s1.epistemic_leaderboard.average_scores_by_agent == \
           s2.epistemic_leaderboard.average_scores_by_agent


def test_different_sessions_can_differ_but_stay_deterministic():
    _c1, s1, _ = _run("sess-x")
    _c2, s2, _ = _run("sess-y")
    # determinism is per-session; both are individually reproducible (checked above)
    assert [m.move_id for m in s1.moves] != [m.move_id for m in s2.moves] or \
           s1.session_id == s2.session_id


# ── #3 Clean content ──────────────────────────────────────────────────────────

def test_synthesis_content_has_no_stray_confidence():
    _c, st, _ = _run("clean")
    for m in st.moves_for_phase(DialogPhase.SYNTHESIS):
        assert set(m.content.keys()) == {
            "core_answer", "crucial_stress_test", "blind_spots", "nuance", "final_verdict",
        }
        assert 0.0 <= m.confidence <= 1.0    # confidence still carried on the move


def test_no_move_content_carries_confidence_key():
    _c, st, _ = _run("clean2")
    for m in st.moves:
        assert "confidence" not in m.content


# ── #2 Every phase scored (incl. the Socratic opening) ───────────────────────

def test_all_deliberation_phases_are_scored():
    _c, st, _ = _run("allphase")
    scored_phases = {ms.phase for ms in st.micro_scores}
    assert scored_phases == set(SCORED_PHASES)
    # ratification is NOT peer-scored
    assert DialogPhase.RATIFICATION not in scored_phases


def test_socratic_opening_question_gets_scored():
    _c, st, _ = _run("opening-scored")
    opening = [ms for ms in st.micro_scores if ms.phase == DialogPhase.OPENING]
    assert opening, "the Socratic opening question must receive shadow scores"
    for ms in opening:
        assert ms.author_agent_id != ms.voter_agent_id   # still no self-scoring
        assert 0.0 <= ms.overall_score <= 10.0


def test_leaderboard_credits_every_scored_phase():
    _c, st, final = _run("lb-phases")
    lb = st.epistemic_leaderboard
    assert set(lb.scores_by_phase.keys()) == {p.value for p in SCORED_PHASES}
    assert lb.leaderboard_status.value == "complete"
    # coverage now spans all phases, not just synthesis
    assert final.audit_summary["score_coverage"]["scores_expected"] > 4 * 3


def test_no_self_scoring_preserved_across_all_phases():
    _c, st, _ = _run("noself-all")
    for ms in st.micro_scores:
        assert ms.author_agent_id != ms.voter_agent_id

"""
Blind Section Assembly tests (Phase 4 — 5 independent sections).

Invariants under test:
  1. Each of the five sections is assembled independently.
  2. Per section, the draft with the highest average overall_score wins.
  3. Tie-breakers apply in order: avg → lower variance → higher count → draft_id.
  4. Different drafts can win different sections.
  5. Assembly is mechanical and deterministic.
"""

import pytest

from backend.dialogues.models import (
    AgentRole, DialogPhase, SECTION_ORDER, SectionName,
    ScoreBreakdown, SectionScore, DraftScorecard, SectionDraft,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


def _make_ced(n: int = 4) -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


def _run_to_scored(ced: CEDOrchestrator, sid: str, question: str):
    ced.create_session(question, session_id=sid)
    for fn in [
        ced.run_opening_phase, ced.run_initial_response_phase,
        ced.run_elenchus_phase, ced.run_reflection_phase,
        ced.run_reconstruction_phase, ced.run_synthesis_phase,
    ]:
        fn(sid)
    ced.compute_shadow_scores(sid)
    ced.score_section_drafts(sid)


# ── Synthetic-scorecard helpers (full control over scores) ───────────────────

def _bd(v: float = 7.0) -> ScoreBreakdown:
    return ScoreBreakdown(
        epistemic_value=v, logical_rigor=v, factual_grounding=v,
        constructive_impact=v, intellectual_honesty=v,
        clarity_precision=v, grounded_creativity=v,
    )


def _draft(did: str, author: str) -> SectionDraft:
    return SectionDraft(
        draft_id=did, session_id="s", author_agent_id=author, move_id=did,
        core_answer=f"{did}-core", crucial_stress_test=f"{did}-stress",
        blind_spots=f"{did}-blind", nuance=f"{did}-nuance",
        final_verdict=f"{did}-verdict",
    )


def _cards_for_section(section: SectionName, per_draft: dict, drafts: dict):
    """Build DraftScorecards: per_draft maps draft_id -> list of overall scores."""
    cards = []
    for did, values in per_draft.items():
        author = drafts[did].author_agent_id
        for i, v in enumerate(values):
            voter = f"voter_{did}_{i}"
            ss = SectionScore(
                session_id="s", section_name=section, draft_id=did,
                author_agent_id=author, voter_agent_id=voter,
                score_breakdown=_bd(), overall_score=v,
            )
            cards.append(DraftScorecard(
                session_id="s", draft_id=did, author_agent_id=author,
                voter_agent_id=voter, section_scores=[ss],
            ))
    return cards


def _assemble_one_section(section: SectionName, per_draft: dict):
    """Set up a synthetic session and assemble; return the AssembledSection."""
    ced = _make_ced()
    state = ced.create_session("Q?", session_id="synthetic")
    drafts = {did: _draft(did, f"author_{did}") for did in per_draft}
    state.section_drafts = list(drafts.values())
    state.draft_scorecards = _cards_for_section(section, per_draft, drafts)
    assembled = ced.assemble_sections("synthetic")
    return assembled.section(section)


# ── Highest average per section ──────────────────────────────────────────────

def test_selects_highest_average_per_section():
    sec = _assemble_one_section(
        SectionName.CORE_ANSWER,
        {"draft_a": [8.0, 8.0], "draft_b": [6.0, 6.0]},
    )
    assert sec.selected_draft_id == "draft_a"
    assert sec.average_score == pytest.approx(8.0)
    assert sec.content == "draft_a-core"


# ── Tie-breaker: lower variance ──────────────────────────────────────────────

def test_tiebreak_lower_variance_wins():
    # Same average (7.0), draft_a has zero variance, draft_b has high variance.
    sec = _assemble_one_section(
        SectionName.NUANCE,
        {"draft_a": [7.0, 7.0], "draft_b": [4.0, 10.0]},
    )
    assert sec.selected_draft_id == "draft_a"
    assert sec.variance == pytest.approx(0.0)


# ── Tie-breaker: higher score_count ──────────────────────────────────────────

def test_tiebreak_higher_count_wins():
    # Same average (7.0) and variance (0.0); draft_a has more scores.
    sec = _assemble_one_section(
        SectionName.BLIND_SPOTS,
        {"draft_a": [7.0, 7.0, 7.0], "draft_b": [7.0, 7.0]},
    )
    assert sec.selected_draft_id == "draft_a"
    assert sec.score_count == 3


# ── Tie-breaker: deterministic draft_id order ────────────────────────────────

def test_tiebreak_draft_id_order_is_final():
    # Identical avg, variance and count → lowest draft_id wins.
    sec = _assemble_one_section(
        SectionName.FINAL_VERDICT,
        {"draft_b": [7.0, 7.0], "draft_a": [7.0, 7.0]},
    )
    assert sec.selected_draft_id == "draft_a"


# ── Five independent sections ────────────────────────────────────────────────

def test_assembles_exactly_five_sections_in_order():
    ced = _make_ced()
    _run_to_scored(ced, "five", "Is mathematics discovered or invented?")
    assembled = ced.assemble_sections("five")

    assert [s.section_name for s in assembled.sections] == SECTION_ORDER
    assert len(assembled.sections) == 5


def test_different_drafts_can_win_different_sections():
    ced = _make_ced()
    state = ced.create_session("Q?", session_id="indep")
    drafts = {d: _draft(d, f"author_{d}") for d in ("draft_a", "draft_b")}
    state.section_drafts = list(drafts.values())

    # draft_a wins CORE_ANSWER, draft_b wins NUANCE.
    cards = []
    cards += _cards_for_section(SectionName.CORE_ANSWER,
                                {"draft_a": [9.0, 9.0], "draft_b": [5.0, 5.0]}, drafts)
    cards += _cards_for_section(SectionName.NUANCE,
                                {"draft_a": [5.0, 5.0], "draft_b": [9.0, 9.0]}, drafts)
    state.draft_scorecards = cards

    assembled = ced.assemble_sections("indep")
    assert assembled.section(SectionName.CORE_ANSWER).selected_draft_id == "draft_a"
    assert assembled.section(SectionName.NUANCE).selected_draft_id == "draft_b"


# ── Determinism + storage + label ────────────────────────────────────────────

def test_assembly_is_deterministic():
    ced = _make_ced()
    _run_to_scored(ced, "det", "Does free will exist?")
    a1 = ced.assemble_sections("det")
    a2 = ced.assemble_sections("det")
    assert [(s.section_name, s.selected_draft_id) for s in a1.sections] == \
           [(s.section_name, s.selected_draft_id) for s in a2.sections]


def test_assembled_answer_stored_on_session():
    ced = _make_ced()
    _run_to_scored(ced, "store", "Is logic empirical?")
    assembled = ced.assemble_sections("store")
    assert ced.get_session("store").assembled_answer is assembled


def test_assembly_method_label():
    ced = _make_ced()
    _run_to_scored(ced, "label", "What is mind?")
    assembled = ced.assemble_sections("label")
    assert assembled.assembly_method == "blind_section_highest_average"


def test_section_with_no_scores_is_unresolved():
    # Only CORE_ANSWER scored; the other four sections have no scores.
    sec = _assemble_one_section(SectionName.CORE_ANSWER, {"draft_a": [7.0]})
    ced = _make_ced()
    state = ced.create_session("Q?", session_id="partial")
    drafts = {"draft_a": _draft("draft_a", "author_draft_a")}
    state.section_drafts = list(drafts.values())
    state.draft_scorecards = _cards_for_section(
        SectionName.CORE_ANSWER, {"draft_a": [7.0]}, drafts)
    assembled = ced.assemble_sections("partial")

    assert assembled.section(SectionName.CORE_ANSWER).unresolved is False
    assert assembled.section(SectionName.NUANCE).unresolved is True

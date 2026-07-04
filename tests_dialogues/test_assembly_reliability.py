"""
Phase 26 — per-section corroboration reliability.

The gap: a section could WIN on a single peer score (one reviewer's opinion) or
none at all (fallback), and nothing distinguished it from a section corroborated
by several concordant scores — the session-level coverage_ratio is global, not
per section. `_assembly_reliability` surfaces, per section, how many peer scores
its winning draft got, and flags the thinly-corroborated ones. A mechanical
count (never a judgement), CED-owned audit, hidden from agents. Offline.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AssembledAnswer, AssembledSection, DialogPhase, SectionName, SessionState,
)
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"

# metric-specific field names — safe to assert absence of (won't appear in the
# mock's philosophy prose the way generic words like "reliability" do).
METRIC_TOKENS = ("assembly_reliability", "thinly_corroborated", "min_corroboration",
                 "mean_corroboration", "well_corroborated", "thin_sections")


def _ced():
    ced, _ = build_council(env={}, council_size=2)
    return ced


def _assembled(counts):
    """5 sections with the given per-section winner score_counts (0 → unresolved)."""
    secs = []
    for i, n in enumerate(SectionName):
        c = counts[i]
        secs.append(AssembledSection(
            section_name=n, selected_draft_id=("d" if c > 0 else ""),
            selected_author_agent_id="a", content="c", average_score=8.0,
            score_count=c, unresolved=(c == 0)))
    return AssembledAnswer(session_id="x", sections=secs)


# ── the metric ────────────────────────────────────────────────────────────────

def test_thin_sections_identified():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)
    st.assembled_answer = _assembled([3, 2, 1, 0, 2])   # blind=1 thin; nuance=0 unresolved
    r = ced._assembly_reliability(st)
    assert r["resolved_sections"] == 4                   # the unresolved one excluded
    assert r["thin_sections"] == ["blind_spots"]         # only the count-1 resolved one
    assert r["thinly_corroborated_sections"] == 1
    assert r["min_corroboration"] == 1
    assert r["mean_corroboration"] == pytest.approx((3 + 2 + 1 + 2) / 4)
    assert r["well_corroborated"] is False


def test_all_well_corroborated():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)
    st.assembled_answer = _assembled([2, 3, 2, 4, 2])
    r = ced._assembly_reliability(st)
    assert r["well_corroborated"] is True and r["thin_sections"] == []
    assert r["min_corroboration"] == 2


def test_threshold_boundary():
    ced = _ced()
    st = SessionState(session_id="x", question=Q)
    st.assembled_answer = _assembled([2, 2, 2, 2, 2])   # exactly at WELL_CORROBORATED_MIN
    assert ced._assembly_reliability(st)["well_corroborated"] is True
    st.assembled_answer = _assembled([1, 1, 1, 1, 1])   # one voter each
    assert ced._assembly_reliability(st)["thinly_corroborated_sections"] == 5


def test_no_assembly_is_safe():
    r = _ced()._assembly_reliability(SessionState(session_id="e", question=Q))
    assert r == {"resolved_sections": 0, "min_corroboration": 0,
                 "mean_corroboration": 0.0, "thinly_corroborated_sections": 0,
                 "thin_sections": [], "well_corroborated": True}


# ── integration: honest revelation + hidden from agents ───────────────────────

def test_full_session_audits_reliability():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="r1"))
    r = final.audit_summary["assembly_reliability"]
    assert {"resolved_sections", "min_corroboration", "mean_corroboration",
            "thinly_corroborated_sections", "thin_sections", "well_corroborated"} == set(r)


def test_two_seat_council_is_honestly_thin():
    # with only 2 seats each draft is scored by exactly ONE peer → every section
    # rests on a single score. The metric reveals this instead of hiding it.
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="r2"))
    r = final.audit_summary["assembly_reliability"]
    assert r["mean_corroboration"] == pytest.approx(1.0)
    assert r["well_corroborated"] is False               # honest: thin by construction


def test_metric_hidden_from_agents():
    ced = _ced()
    asyncio.run(ced.run_registry_session(Q, session_id="r3"))
    st = ced.get_session("r3")
    for phase in (DialogPhase.OPENING, DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS,
                  DialogPhase.REFLECTION, DialogPhase.RECONSTRUCTION, DialogPhase.SYNTHESIS):
        blob = str(ced._registry_phase_context(st, phase, "agent_0")).lower()
        for tok in METRIC_TOKENS:
            assert tok not in blob, (phase.value, tok)


def test_scoring_task_context_has_no_reliability():
    ced = _ced()
    asyncio.run(ced.run_registry_session(Q, session_id="r4"))
    st = ced.get_session("r4")
    move = st.moves[0]
    mtask = ced._build_move_score_task(st, move, "voter_x", move.phase, 0)
    assert set(mtask.context) == {"output_to_score", "rubric_name", "rubric_focus"}

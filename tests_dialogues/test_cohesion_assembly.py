"""
Phase 25 — coherence-aware assembly (the smart part of cross-section coherence).

Beyond flagging fragmentation (Phase 24), the assembly itself can now prefer
coherence: when two drafts are within `cohesion_margin` (0–10 scale) on a
section, CED takes the section from the globally STRONGER draft (mean section
score across all sections) — anchoring the answer to one coherent source and
"borrowing" a section from another draft ONLY when it wins decisively (beyond
the margin). A bounded, mechanical quality↔coherence trade; default off.

Invariants: margin 0 (default) is byte-for-byte the old score-winner pick;
selection stays mechanical (scores + a deterministic global-strength tie-break,
never semantics); never picks a draft weaker than the winner by more than the
margin; audited. Offline, mock only.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    DraftScorecard, ScoreBreakdown, SectionDraft, SectionName, SectionScore,
    SessionState,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"


def _bd(v):
    return ScoreBreakdown(epistemic_value=v, logical_rigor=v, factual_grounding=v,
                          constructive_impact=v, intellectual_honesty=v,
                          clarity_precision=v, grounded_creativity=v)


def _state(core_b=8.3, other_b=5.0, core_a=8.0, other_a=8.0):
    """dA strong+coherent everywhere; dB spikes on core_answer only."""
    st = SessionState(session_id="s", question=Q)
    st.section_drafts = [
        SectionDraft(draft_id="dA", session_id="s", author_agent_id="a0", move_id="mA",
                     core_answer="A-core", crucial_stress_test="A", blind_spots="A",
                     nuance="A", final_verdict="A"),
        SectionDraft(draft_id="dB", session_id="s", author_agent_id="a1", move_id="mB",
                     core_answer="B-core", crucial_stress_test="B", blind_spots="B",
                     nuance="B", final_verdict="B")]
    vals = {SectionName.CORE_ANSWER: {"dA": core_a, "dB": core_b}}
    for sec in SectionName:
        vals.setdefault(sec, {"dA": other_a, "dB": other_b})
    cards = {}
    for sec, dd in vals.items():
        for did, v in dd.items():
            author = "a0" if did == "dA" else "a1"
            cards.setdefault(did, DraftScorecard(session_id="s", draft_id=did,
                             author_agent_id=author, voter_agent_id="v", section_scores=[]))
            cards[did].section_scores.append(SectionScore(
                session_id="s", section_name=sec, draft_id=did, author_agent_id=author,
                voter_agent_id="v", score_breakdown=_bd(v), overall_score=v))
    st.draft_scorecards = list(cards.values())
    return st


def _ced(margin=0.0):
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", p) for i in range(2)], p,
                          cohesion_margin=margin)
    ced._sessions["s"] = _state()
    return ced


def _sources(ced):
    a = ced.assemble_sections("s")
    return {s.section_name.value: s.selected_draft_id for s in a.sections}


# ── the core mechanic ─────────────────────────────────────────────────────────

def test_default_margin_zero_is_fragmented_like_before():
    src = _sources(_ced(0.0))
    assert src["core_answer"] == "dB"                    # raw score-winner (8.3)
    assert src["final_verdict"] == "dA"                  # → 2 sources, fragmented


def test_cohesion_anchors_to_the_strong_draft():
    ced = _ced(0.5)
    src = _sources(ced)
    assert set(src.values()) == {"dA"}                   # all five from the anchor
    m = ced._assembly_coherence(ced._sessions["s"])
    assert m["single_source"] is True and m["cohesion_overrides"] == 1


def test_margin_smaller_than_gap_keeps_quality_winner():
    # core gap is 0.3; a 0.1 margin must NOT override (quality wins beyond margin)
    src = _sources(_ced(0.1))
    assert src["core_answer"] == "dB"


def test_cohesion_never_exceeds_the_margin_tradeoff():
    ced = _ced(0.5)
    a = ced.assemble_sections("s")
    core = next(s for s in a.sections if s.section_name == SectionName.CORE_ANSWER)
    # took dA's 8.0 over dB's 8.3 — exactly a 0.3 trade, within the 0.5 margin
    assert core.average_score == pytest.approx(8.0)


def test_global_strength_is_order_independent():
    ced = _ced(0.5)
    strengths = ced._cohesion_strengths(ced._sessions["s"])
    assert strengths["dA"] > strengths["dB"]             # A strong everywhere
    assert strengths["dA"] == pytest.approx(8.0)


def test_negative_margin_raises():
    p = FakeProvider()
    with pytest.raises(ValueError, match="cohesion_margin"):
        CEDOrchestrator([SocraticAgent(f"a{i}", p) for i in range(2)], p,
                        cohesion_margin=-0.5)


# ── integration + audit + invariant (no full silencing / still mechanical) ────

def test_full_session_ratifies_with_cohesion_on():
    ced, _ = build_council(env={}, council_size=2, cohesion_margin=1.0)
    final = asyncio.run(ced.run_registry_session(Q, session_id="c1"))
    assert final.ratified is True
    ac = final.audit_summary["assembly_coherence"]
    assert ac["cohesion_margin"] == 1.0 and "cohesion_overrides" in ac


def test_build_council_defaults_margin_zero():
    ced, _ = build_council(env={}, council_size=2)
    assert ced.cohesion_margin == 0.0
    ced2, _ = build_council(env={}, council_size=2, cohesion_margin=0.75)
    assert ced2.cohesion_margin == 0.75


def test_uniform_full_session_unchanged_by_default():
    # a default-margin session behaves exactly like the pre-Phase-25 assembly
    ced0, _ = build_council(env={}, council_size=2)
    f0 = asyncio.run(ced0.run_registry_session(Q, session_id="z"))
    assert f0.audit_summary["assembly_coherence"]["cohesion_overrides"] == 0

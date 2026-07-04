"""
Phase 23 — confidence-weighted peer-score aggregation.

The gap: section winners were picked by a PLAIN mean of peer scores, ignoring
the confidence each voter self-reported in that very score. Now the aggregation
can weight by that confidence — a mechanical weighted average (still no semantic
CED judgement; a low-confidence vote still counts, just less).

Invariants: default "uniform" is byte-for-byte the old behavior; weighting is
opt-in; a low-confidence vote is never fully silenced; all-zero confidence falls
back to the plain mean (no division by zero); the effect is audited, not hidden.
Offline, mock only.
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


def _flip_state():
    """dA: 9@0.1 + 5@0.9 → uniform 7.0, confidence 5.4 ; dB: 6@1.0 ×2 → 6.0 both."""
    st = SessionState(session_id="s", question=Q)
    st.section_drafts = [
        SectionDraft(draft_id="dA", session_id="s", author_agent_id="a0", move_id="mA",
                     core_answer="A core", crucial_stress_test="x", blind_spots="x",
                     nuance="x", final_verdict="x"),
        SectionDraft(draft_id="dB", session_id="s", author_agent_id="a1", move_id="mB",
                     core_answer="B core", crucial_stress_test="x", blind_spots="x",
                     nuance="x", final_verdict="x")]
    rows = [("dA", "a0", 9.0, 0.1, "v1"), ("dA", "a0", 5.0, 0.9, "v2"),
            ("dB", "a1", 6.0, 1.0, "v1"), ("dB", "a1", 6.0, 1.0, "v2")]
    cards = {}
    for did, author, score, conf, voter in rows:
        cards.setdefault((did, voter), DraftScorecard(
            session_id="s", draft_id=did, author_agent_id=author,
            voter_agent_id=voter, section_scores=[]))
        cards[(did, voter)].section_scores.append(SectionScore(
            session_id="s", section_name=SectionName.CORE_ANSWER, draft_id=did,
            author_agent_id=author, voter_agent_id=voter, score_breakdown=_bd(score),
            overall_score=score, confidence=conf))
    st.draft_scorecards = list(cards.values())
    return st


def _ced(mode="uniform"):
    p = FakeProvider()
    return CEDOrchestrator([SocraticAgent(f"a{i}", p) for i in range(2)], p,
                           score_weighting=mode)


# ── the core mechanic ─────────────────────────────────────────────────────────

def test_default_is_uniform():
    assert _ced().score_weighting == "uniform"


def test_uniform_picks_higher_plain_mean():
    r = _ced("uniform")._section_ranking(_flip_state(), SectionName.CORE_ANSWER)
    assert r[0]["draft_id"] == "dA"
    assert r[0]["average_score"] == pytest.approx(7.0)


def test_confidence_weighting_flips_the_winner():
    r = _ced("confidence")._section_ranking(_flip_state(), SectionName.CORE_ANSWER)
    assert r[0]["draft_id"] == "dB"                       # 6.0 beats weighted 5.4
    dA = next(s for s in r if s["draft_id"] == "dA")
    assert dA["average_score"] == pytest.approx(5.4)       # (9*.1 + 5*.9)/1.0


def test_equal_confidence_matches_uniform():
    st = _flip_state()
    for card in st.draft_scorecards:
        for ss in card.section_scores:
            ss.confidence = 0.7                            # all equal
    u = _ced("uniform")._section_ranking(st, SectionName.CORE_ANSWER)
    c = _ced("confidence")._section_ranking(st, SectionName.CORE_ANSWER)
    assert [x["draft_id"] for x in u] == [x["draft_id"] for x in c]
    assert u[0]["average_score"] == pytest.approx(c[0]["average_score"])


def test_low_confidence_vote_is_not_silenced():
    # a single 0.01-confidence vote still shifts the mean (weight>0, not dropped)
    st = SessionState(session_id="s", question=Q)
    st.section_drafts = [SectionDraft(draft_id="d1", session_id="s", author_agent_id="a0",
                                      move_id="m1", core_answer="c", crucial_stress_test="x",
                                      blind_spots="x", nuance="x", final_verdict="x")]
    st.draft_scorecards = [DraftScorecard(session_id="s", draft_id="d1", author_agent_id="a0",
        voter_agent_id="v", section_scores=[
            SectionScore(session_id="s", section_name=SectionName.CORE_ANSWER, draft_id="d1",
                         author_agent_id="a0", voter_agent_id="v", score_breakdown=_bd(2.0),
                         overall_score=2.0, confidence=0.01)])]
    r = _ced("confidence")._section_ranking(st, SectionName.CORE_ANSWER)
    assert r[0]["average_score"] == pytest.approx(2.0)     # counted, not discarded


def test_all_zero_confidence_falls_back_to_plain_mean():
    st = _flip_state()
    for card in st.draft_scorecards:
        for ss in card.section_scores:
            ss.confidence = 0.0
    r = _ced("confidence")._section_ranking(st, SectionName.CORE_ANSWER)
    assert r[0]["draft_id"] == "dA" and r[0]["average_score"] == pytest.approx(7.0)


def test_invalid_mode_raises():
    p = FakeProvider()
    with pytest.raises(ValueError, match="score_weighting"):
        CEDOrchestrator([SocraticAgent(f"a{i}", p) for i in range(2)], p,
                        score_weighting="magic")


# ── audit + integration ───────────────────────────────────────────────────────

def test_weighting_audit_reports_mode_and_flips():
    ced = _ced("confidence")
    ced._sessions["s"] = _flip_state()
    audit = ced._weighting_audit(ced._sessions["s"])
    assert audit["mode"] == "confidence" and audit["sections_reweighted"] == 1
    assert _ced("uniform")._weighting_audit(_flip_state()) == {
        "mode": "uniform", "sections_reweighted": 0}


def test_full_session_audits_weighting():
    ced, _ = build_council(env={}, council_size=2, score_weighting="confidence")
    final = asyncio.run(ced.run_registry_session(Q, session_id="w1"))
    sw = final.audit_summary["score_weighting"]
    assert sw["mode"] == "confidence" and "sections_reweighted" in sw
    assert final.ratified is True                          # still produces an answer


def test_build_council_defaults_uniform_and_passes_through():
    ced_u, _ = build_council(env={}, council_size=2)
    assert ced_u.score_weighting == "uniform"
    ced_c, _ = build_council(env={}, council_size=2, score_weighting="confidence")
    assert ced_c.score_weighting == "confidence"

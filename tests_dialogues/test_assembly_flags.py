"""
Phase 27 — penalty-flag aggregation.

The gap: voters can flag a section for real epistemic problems (unsupported_claim,
logical_gap, overconfidence, missed_uncertainty, …). Those flags were parsed and
stored but NEVER read — a section could WIN on score and ship with unresolved
flags, silently. `_assembly_flags` aggregates the flags voters raised on the
WINNING content of each assembled section, distinguishing substantive from
stylistic (vague / rhetorical_fluff). A mechanical count of the council's own
flags — CED-owned audit, hidden from agents. Offline.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AssembledAnswer, AssembledSection, DialogPhase, DraftScorecard, PenaltyFlag,
    ScoreBreakdown, SectionName, SectionScore, SessionState,
)
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"
METRIC_TOKENS = ("assembly_flags", "flags_by_section", "serious_flag_count",
                 "flagged_sections", "penalty_flag")


def _bd(v):
    return ScoreBreakdown(epistemic_value=v, logical_rigor=v, factual_grounding=v,
                          constructive_impact=v, intellectual_honesty=v,
                          clarity_precision=v, grounded_creativity=v)


def _ced():
    ced, _ = build_council(env={}, council_size=2)
    return ced


def _state_with_flags(winner_flags, loser_flags=None):
    """core_answer winner is 'dW'; attach flags to winner and (ignored) loser."""
    st = SessionState(session_id="x", question=Q)
    st.assembled_answer = AssembledAnswer(session_id="x", sections=[
        AssembledSection(section_name=n, selected_draft_id="dW",
                         selected_author_agent_id="a", content="c",
                         average_score=8.0, score_count=2) for n in SectionName])
    scores = []
    for i, flags in enumerate(winner_flags):
        scores.append(SectionScore(session_id="x", section_name=SectionName.CORE_ANSWER,
                                   draft_id="dW", author_agent_id="a0",
                                   voter_agent_id=f"v{i}", score_breakdown=_bd(8.0),
                                   overall_score=8.0, penalty_flags=flags))
    for i, flags in enumerate(loser_flags or []):
        scores.append(SectionScore(session_id="x", section_name=SectionName.CORE_ANSWER,
                                   draft_id="dLOSER", author_agent_id="a1",
                                   voter_agent_id=f"L{i}", score_breakdown=_bd(3.0),
                                   overall_score=3.0, penalty_flags=flags))
    st.draft_scorecards = [DraftScorecard(session_id="x", draft_id="dW",
                           author_agent_id="a0", voter_agent_id="v0", section_scores=scores)]
    return st


# ── aggregation semantics ─────────────────────────────────────────────────────

def test_flags_on_the_winner_are_aggregated():
    st = _state_with_flags([[PenaltyFlag.UNSUPPORTED_CLAIM],
                            [PenaltyFlag.UNSUPPORTED_CLAIM, PenaltyFlag.LOGICAL_GAP]])
    r = _ced()._assembly_flags(st)
    assert r["flags_by_section"]["core_answer"] == {"unsupported_claim": 2, "logical_gap": 1}
    assert r["serious_flag_count"] == 3 and r["clean"] is False
    assert r["flagged_sections"] == ["core_answer"]


def test_flags_on_losing_drafts_are_ignored():
    st = _state_with_flags([[PenaltyFlag.OVERCONFIDENCE]],
                           loser_flags=[[PenaltyFlag.LOGICAL_GAP, PenaltyFlag.UNSUPPORTED_CLAIM]])
    r = _ced()._assembly_flags(st)
    # only the winner's overconfidence counts; the loser's flags never shipped
    assert r["flags_by_section"]["core_answer"] == {"overconfidence": 1}
    assert r["serious_flag_count"] == 1


def test_stylistic_flags_excluded_from_serious_count():
    st = _state_with_flags([[PenaltyFlag.VAGUE, PenaltyFlag.RHETORICAL_FLUFF]])
    r = _ced()._assembly_flags(st)
    assert r["flags_by_section"]["core_answer"] == {"vague": 1, "rhetorical_fluff": 1}
    assert r["serious_flag_count"] == 0 and r["clean"] is True   # stylistic only → clean


def test_no_flags_is_clean():
    st = _state_with_flags([[], []])
    r = _ced()._assembly_flags(st)
    assert r == {"flagged_sections": [], "flags_by_section": {},
                 "serious_flag_count": 0, "clean": True}


def test_no_assembly_is_safe():
    r = _ced()._assembly_flags(SessionState(session_id="e", question=Q))
    assert r["clean"] is True and r["flagged_sections"] == []


# ── integration: reveals real inert flags + hidden ───────────────────────────

def test_full_session_audits_flags_and_surfaces_the_inert_ones():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="r1"))
    af = final.audit_summary["assembly_flags"]
    assert set(af) == {"flagged_sections", "flags_by_section",
                       "serious_flag_count", "clean"}
    # the mock raises missed_uncertainty flags that used to be silently ignored
    all_flags = {f for counts in af["flags_by_section"].values() for f in counts}
    assert "missed_uncertainty" in all_flags
    assert af["clean"] is False


def test_flags_hidden_from_agents():
    ced = _ced()
    asyncio.run(ced.run_registry_session(Q, session_id="r2"))
    st = ced.get_session("r2")
    for phase in (DialogPhase.OPENING, DialogPhase.ELENCHUS, DialogPhase.SYNTHESIS):
        blob = str(ced._registry_phase_context(st, phase, "agent_0")).lower()
        for tok in METRIC_TOKENS:
            assert tok not in blob, (phase.value, tok)


def test_stylistic_set_matches_enum_values():
    from backend.dialogues.ced import CEDOrchestrator
    assert CEDOrchestrator.STYLISTIC_FLAG_VALUES == {"vague", "rhetorical_fluff"}
    assert CEDOrchestrator.STYLISTIC_FLAG_VALUES <= {f.value for f in PenaltyFlag}

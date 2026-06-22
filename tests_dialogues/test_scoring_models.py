"""
Phase 4 scoring-model validation tests.

Covers: ScoreBreakdown range + weights, MicroScore / SectionScore / DraftScorecard
validation, self-scoring rejection, and 0–10 scale enforcement.
"""

import pytest
from pydantic import ValidationError

from backend.dialogues.models import (
    ScoreBreakdown, SCORE_WEIGHTS, MicroScore, SectionScore, DraftScorecard,
    PenaltyFlag, ProviderStatus, SectionName, DialogPhase,
)


def _bd(v: float = 7.0) -> ScoreBreakdown:
    return ScoreBreakdown(
        epistemic_value=v, logical_rigor=v, factual_grounding=v,
        constructive_impact=v, intellectual_honesty=v,
        clarity_precision=v, grounded_creativity=v,
    )


# ── ScoreBreakdown ────────────────────────────────────────────────────────────

def test_weights_sum_to_one():
    assert sum(SCORE_WEIGHTS.values()) == pytest.approx(1.0)


def test_weighted_overall_is_correct():
    bd = ScoreBreakdown(
        epistemic_value=10, logical_rigor=8, factual_grounding=6,
        constructive_impact=4, intellectual_honesty=2,
        clarity_precision=0, grounded_creativity=10,
    )
    expected = (10*0.30 + 8*0.20 + 6*0.15 + 4*0.10 + 2*0.10 + 0*0.10 + 10*0.05)
    assert bd.weighted_overall() == pytest.approx(expected)


def test_uniform_breakdown_overall_equals_value():
    assert _bd(7.0).weighted_overall() == pytest.approx(7.0)


@pytest.mark.parametrize("bad", [-0.1, -1, 10.1, 11])
def test_score_dimension_out_of_range_rejected(bad):
    with pytest.raises(ValidationError):
        ScoreBreakdown(
            epistemic_value=bad, logical_rigor=7, factual_grounding=7,
            constructive_impact=7, intellectual_honesty=7,
            clarity_precision=7, grounded_creativity=7,
        )


# ── MicroScore ────────────────────────────────────────────────────────────────

def _micro(author="a0", voter="a1", **kw):
    return MicroScore(
        session_id="s", output_id="m1", phase=DialogPhase.SYNTHESIS,
        author_agent_id=author, voter_agent_id=voter, score_breakdown=_bd(),
        **kw,
    )


def test_micro_self_scoring_rejected():
    with pytest.raises(ValidationError):
        _micro(author="a0", voter="a0")


def test_micro_overall_autofilled_on_0_to_10_scale():
    ms = _micro()
    assert ms.overall_score == pytest.approx(_bd().weighted_overall())
    assert 0.0 <= ms.overall_score <= 10.0


def test_micro_overall_explicit_value_preserved():
    ms = _micro(overall_score=9.5)
    assert ms.overall_score == 9.5


@pytest.mark.parametrize("bad_conf", [-0.01, 1.01, 2.0])
def test_micro_confidence_range_rejected(bad_conf):
    with pytest.raises(ValidationError):
        _micro(confidence=bad_conf)


def test_micro_penalty_flags_validated():
    ms = _micro(penalty_flags=[PenaltyFlag.OVERCONFIDENCE, PenaltyFlag.VAGUE])
    assert PenaltyFlag.OVERCONFIDENCE in ms.penalty_flags
    with pytest.raises(ValidationError):
        _micro(penalty_flags=["not_a_real_flag"])


def test_micro_provider_status_validated():
    ms = _micro(provider_status=ProviderStatus.FALLBACK)
    assert ms.provider_status == ProviderStatus.FALLBACK
    with pytest.raises(ValidationError):
        _micro(provider_status="exploded")


def test_micro_overall_above_10_rejected():
    with pytest.raises(ValidationError):
        _micro(overall_score=10.5)


# ── SectionScore ──────────────────────────────────────────────────────────────

def _section(author="a0", voter="a1", **kw):
    return SectionScore(
        session_id="s", section_name=SectionName.CORE_ANSWER, draft_id="d1",
        author_agent_id=author, voter_agent_id=voter, score_breakdown=_bd(),
        **kw,
    )


def test_section_self_scoring_rejected():
    with pytest.raises(ValidationError):
        _section(author="a0", voter="a0")


def test_section_overall_autofilled():
    assert _section().overall_score == pytest.approx(_bd().weighted_overall())


def test_section_uses_0_to_10_scale():
    ss = _section(overall_score=8.4)
    assert 0.0 <= ss.overall_score <= 10.0
    with pytest.raises(ValidationError):
        _section(overall_score=12)


# ── DraftScorecard ────────────────────────────────────────────────────────────

def test_draft_scorecard_self_scoring_rejected():
    with pytest.raises(ValidationError):
        DraftScorecard(
            session_id="s", draft_id="d1",
            author_agent_id="a0", voter_agent_id="a0",
        )


def test_draft_scorecard_records_missing_sections():
    card = DraftScorecard(
        session_id="s", draft_id="d1",
        author_agent_id="a0", voter_agent_id="a1",
        section_scores=[_section(author="a0", voter="a1")],
        missing_sections=[SectionName.NUANCE, SectionName.FINAL_VERDICT],
    )
    assert card.score_for_section(SectionName.CORE_ANSWER) is not None
    assert SectionName.NUANCE in card.missing_sections
    assert card.score_for_section(SectionName.NUANCE) is None


def test_draft_scorecard_can_hold_all_five_sections():
    scores = [
        SectionScore(
            session_id="s", section_name=name, draft_id="d1",
            author_agent_id="a0", voter_agent_id="a1", score_breakdown=_bd(),
        )
        for name in SectionName
    ]
    card = DraftScorecard(
        session_id="s", draft_id="d1",
        author_agent_id="a0", voter_agent_id="a1",
        section_scores=scores,
    )
    assert len(card.section_scores) == 5
    for name in SectionName:
        assert card.score_for_section(name) is not None

"""CED Graph v10.2 Elenchus explanation and provider transparency tests."""

import asyncio

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.orchestrator.session import EnhancedDialogSession, session_manager
from backend.orchestrator import dialog_pipeline_ced
from backend.reasoning.elenchus_explanation import (
    OUTCOME_NOT_REFUTED_YET,
    OUTCOME_WRONG_TARGET,
    explain_elenchus_result,
    is_epistemic_claim,
    is_meta_instruction,
)


class _FakeManager:
    async def _call_model(self, model_id, prompt):
        if "challenge this exact claim" in prompt.lower():
            return (
                '{"challenged_assumptions":["assumes insider selling means overpricing"],'
                '"logic_gaps":["evidence does not separate liquidity from overpricing"],'
                '"evidence_issues":["needs source-backed valuation evidence"],'
                '"conclusion_issues":[],"falsification_successful":false}'
            )
        return "FINAL: Retail buyers may be disadvantaged because insiders have better information and different incentives."


def _make_session(sid):
    cfg = DialogConfig(
        topic="Is a SpaceX IPO price fair to retail buyers?",
        rounds=2,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    s = EnhancedDialogSession(sid, cfg, {"claude": "x", "chatgpt": "y"})
    s.manager = _FakeManager()
    s.enforced_rounds = 2
    session_manager._sessions[sid] = s
    return s


def test_meta_instruction_is_not_epistemic_claim():
    text = "Deliver a sharp Socratic follow-up that exposes the contradiction."
    assert is_meta_instruction(text) is True
    assert is_epistemic_claim(text) is False


def test_elenchus_wrong_target_for_meta_instruction():
    exp = explain_elenchus_result("claim_x", "Deliver a sharp Socratic follow-up.", {})
    assert exp.outcome == OUTCOME_WRONG_TARGET
    assert exp.target_is_epistemic_claim is False
    assert "instruction" in exp.reason.lower()


def test_not_refuted_yet_has_reason_and_next_question():
    exp = explain_elenchus_result(
        "claim_1",
        "Retail buyers may be disadvantaged because insiders have better information.",
        {"falsification_successful": False},
    )
    assert exp.outcome == OUTCOME_NOT_REFUTED_YET
    assert exp.reason
    assert exp.remaining_uncertainty
    assert exp.next_socratic_question


def test_live_elenchus_turn_exposes_target_reason_and_provider_status():
    s = _make_session("test_v10_2_live")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))
    turns = [t for t in s.history if t.is_elenchus]
    assert turns
    last = turns[-1]
    assert "Target claim:" in last.content
    assert "Reason:" in last.content
    assert "Remaining uncertainty:" in last.content
    assert "Next Socratic question:" in last.content
    assert last.provider_status is not None
    assert last.provider_status.provider_name in {"claude", "chatgpt"}
    assert "API_KEY" not in str(last.provider_status.dict())


def test_elenchus_history_stores_explanation_fields_and_provider_status():
    s = _make_session("test_v10_2_history")
    asyncio.run(dialog_pipeline_ced._run_dialog_pipeline(s.session_id))
    assert s.elenchus_history
    e = s.elenchus_history[-1]
    assert e.target_claim_id
    assert e.target_claim_text
    assert e.reason
    assert e.remaining_uncertainty
    assert e.next_socratic_question
    assert e.provider_status is not None
    assert e.provider_status.real_api_call is True

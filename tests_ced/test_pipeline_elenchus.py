"""Proves the dialog pipeline performs and stores Elenchus on every completed
dialog (Rule 3). Runs fully offline with a deterministic fake manager — no API
keys, no network, no secrets in output."""

import asyncio

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.orchestrator.session import EnhancedDialogSession, session_manager
from backend.orchestrator import dialog_pipeline


class _FakeManager:
    """Deterministic stand-in for DialogManager. No network, no API keys."""

    async def _call_model(self, model_id, prompt):
        if "falsify" in prompt.lower():
            # A parseable, structured Elenchus response.
            return (
                '{"challenged_assumptions":["assumes the premise holds"],'
                '"logic_gaps":["does not follow"],"evidence_issues":[],'
                '"conclusion_issues":[],"falsification_successful":false}'
            )
        return "INITIAL: a\nCRITICISM: b\nREVISION: c\nFINAL: A reasoned position."


def _make_session(sid, rounds=2):
    cfg = DialogConfig(
        topic="Is knowledge justified true belief?",
        rounds=rounds,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    s = EnhancedDialogSession(sid, cfg, {"claude": "x", "chatgpt": "y"})
    s.manager = _FakeManager()
    s.enforced_rounds = rounds
    session_manager._sessions[sid] = s
    return s


def test_elenchus_recorded_after_dialog():
    s = _make_session("test_elenchus_1")
    asyncio.run(dialog_pipeline._run_dialog_pipeline(s.session_id))
    assert len(s.elenchus_history) > 0, "Elenchus must be performed and stored"


def test_no_rule3_violation_on_normal_completion():
    s = _make_session("test_elenchus_2")
    asyncio.run(dialog_pipeline._run_dialog_pipeline(s.session_id))
    rule3 = [v for v in s.constitution_violations if "Rule 3" in v]
    assert not rule3, f"Unexpected Rule 3 violation(s): {rule3}"


def test_elenchus_endpoint_rule_satisfied_after_dialog():
    # Mirrors the /dialog/{id}/elenchus endpoint's rule_satisfied = count > 0.
    s = _make_session("test_elenchus_3")
    asyncio.run(dialog_pipeline._run_dialog_pipeline(s.session_id))
    count = len(s.elenchus_history)
    rule_satisfied = count > 0
    assert rule_satisfied is True


def test_elenchus_records_even_when_model_returns_nothing():
    # Challenger returns empty -> structural Elenchus still recorded.
    class _SilentManager:
        async def _call_model(self, model_id, prompt):
            return "" if "falsify" in prompt.lower() else "FINAL: ok"

    s = _make_session("test_elenchus_4")
    s.manager = _SilentManager()
    asyncio.run(dialog_pipeline._run_dialog_pipeline(s.session_id))
    assert len(s.elenchus_history) > 0

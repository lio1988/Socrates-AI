"""
PART 3 — configurable shadow_scoring_mode.
"""

import pytest

from backend.dialogues.models import DialogPhase, ShadowScoringMode, LeaderboardStatus
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator

Q = "Is knowledge merely justified true belief?"


def _run(mode, sid):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    ced = CEDOrchestrator(agents, p, shadow_scoring_mode=mode)
    final = ced.run_session(Q, session_id=sid)
    return final, ced.get_session(sid)


def test_all_phases_scores_every_phase():
    final, st = _run(ShadowScoringMode.ALL_PHASES, "m-all")
    phases = {ms.phase for ms in st.micro_scores}
    assert DialogPhase.OPENING in phases and DialogPhase.SYNTHESIS in phases
    assert len(phases) == 6
    assert final.socratic_leaderboard.leaderboard_status == LeaderboardStatus.COMPLETE


def test_synthesis_only():
    final, st = _run(ShadowScoringMode.SYNTHESIS_ONLY, "m-syn")
    assert {ms.phase for ms in st.micro_scores} == {DialogPhase.SYNTHESIS}
    assert final.socratic_leaderboard.leaderboard_status == LeaderboardStatus.COMPLETE


def test_sampled_scores_opening_and_synthesis():
    final, st = _run(ShadowScoringMode.SAMPLED, "m-sam")
    assert {ms.phase for ms in st.micro_scores} == {DialogPhase.OPENING, DialogPhase.SYNTHESIS}
    assert final.socratic_leaderboard.leaderboard_status == LeaderboardStatus.COMPLETE


def test_off_disables_scoring_cleanly():
    final, st = _run(ShadowScoringMode.OFF, "m-off")
    assert st.micro_scores == []
    lb = final.socratic_leaderboard
    assert lb.leaderboard_status == LeaderboardStatus.DISABLED
    assert any("disabled" in e.lower() for e in lb.notable_events)
    # off is a clean state, not a failure / not ratification-blocking
    assert isinstance(final.ratified, bool)
    assert final.audit_summary["score_coverage"]["sync_gate_status"] == "disabled"


def test_off_does_not_crash_pipeline():
    final, _ = _run(ShadowScoringMode.OFF, "m-off2")
    assert final.synthesis is not None     # assembly still works without leaderboard
    assert final.answer

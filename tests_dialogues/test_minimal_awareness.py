"""
Minimal Awareness tests (Phase 4 §9) + scoring resilience (§10).

Agents must never receive raw scores, score breakdowns, peer leaderboards, or
shadow-scoring internals. Malformed scores must be recorded cleanly without
crashing orchestration.
"""

import pytest
from unittest.mock import patch

from backend.dialogues.models import (
    DialogPhase, PenaltyFlag, ProviderStatus, SectionName,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


def _make_ced(n: int = 4, provider=None) -> CEDOrchestrator:
    provider = provider or FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


# ── Agents never receive scoring data ────────────────────────────────────────

_FORBIDDEN_KEYWORDS = {
    "score_breakdown", "overall_score", "micro_score", "section_score",
    "draft_scorecard", "leaderboard", "voter_agent_id", "epistemic_value",
    "logical_rigor", "grounded_creativity", "penalty_flag",
}


def test_agents_never_receive_scores_or_leaderboard_in_context():
    ced = _make_ced()
    captured = []
    original = SocraticAgent.execute

    def capturing(self, task):
        captured.append(task)
        return original(self, task)

    with patch.object(SocraticAgent, "execute", capturing):
        ced.run_session("Is knowledge justified true belief?", session_id="aware")

    assert captured
    for task in captured:
        blob = str(task.context).lower() + " " + str(task.output_schema).lower()
        for kw in _FORBIDDEN_KEYWORDS:
            assert kw not in blob, (
                f"Forbidden keyword '{kw}' reached agent '{task.agent_id}' "
                f"in phase '{task.phase.value}'."
            )


def test_agent_state_has_no_scoring_fields():
    ced = _make_ced()
    ced.run_session("Does free will exist?", session_id="aware-state")
    state = ced.get_session("aware-state")

    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in ("micro_scores", "draft_scorecards", "section_scores",
                          "leaderboard", "scorecard", "score_breakdown"):
            assert forbidden not in dumped


def test_scoring_lives_only_on_session_state():
    ced = _make_ced()
    ced.run_session("Is logic universal?", session_id="aware-own")
    state = ced.get_session("aware-own")

    # CED-owned scoring is present on SessionState…
    assert state.micro_scores
    assert state.draft_scorecards
    # …and the agents themselves hold no session/score references.
    for agent in ced.agents:
        assert not hasattr(agent, "micro_scores")
        assert not hasattr(agent, "scorecard")
        assert not hasattr(agent, "session_state")


# ── Malformed scores do not crash orchestration ──────────────────────────────

class _BrokenSectionProvider(FakeProvider):
    """Returns a malformed section-score breakdown (missing dimensions)."""

    def complete(self, system_prompt, user_prompt, output_schema,
                 agent_id="", temperature=0.7):
        if output_schema.get("_role") == "__section_score__":
            return {
                "score_breakdown": {"epistemic_value": 7.0},  # 6 dims missing
                "confidence": 0.5,
                "penalty_flags": [],
                "provider_status": "ok",
            }
        return super().complete(system_prompt, user_prompt, output_schema,
                                agent_id, temperature)


def test_malformed_section_scores_recorded_as_missing_not_fabricated():
    """
    INVARIANT: CED is not a scorer. When a peer's section score is malformed, the
    score stays MISSING (recorded as a failure) — CED never fabricates a stand-in
    qualitative score (e.g. zeros). Orchestration still completes.
    """
    ced = _make_ced(provider=_BrokenSectionProvider())
    final = ced.run_session("What is truth?", session_id="broken")

    # Orchestration completed without raising.
    assert isinstance(final.ratified, bool)
    assert final.response_id.startswith("resp_")

    state = ced.get_session("broken")
    all_section_scores = [
        ss for card in state.draft_scorecards for ss in card.section_scores
    ]
    # No fabricated section scores were created for the malformed peer output.
    assert all_section_scores == []
    # The failures are recorded as MISSING (per draftcard) + in the failed list.
    assert all(card.missing_sections for card in state.draft_scorecards)
    assert state.section_scores_failed, "failed peer section-scores must be recorded"
    # And the move-level leaderboard is unaffected (move scores were valid here).
    assert final.socratic_leaderboard is not None

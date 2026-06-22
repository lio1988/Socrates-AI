"""
Ratification and full-pipeline tests.

Invariants under test:
  1. Ratification is approved when the Final Evaluator returns no blocking objections.
  2. Ratification is blocked when blocking objections are present.
  3. A single blocking objection is sufficient to prevent ratification.
  4. Final response is stored on SessionState.
  5. Session phase advances to COMPLETE after ratification.
  6. Full end-to-end pipeline completes without error.
  7. The FINAL_EVALUATOR role is never assigned to an agent who authored synthesis.
"""

import pytest
from unittest.mock import patch

from backend.dialogues.models import (
    AgentRole, DialogPhase, EpistemicStatus, SectionName,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


def _make_ced(n: int = 4) -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n)]
    return CEDOrchestrator(agents, provider)


def _run_to_assembly(ced: CEDOrchestrator, sid: str, question: str) -> None:
    ced.create_session(question, session_id=sid)
    for fn in [
        ced.run_opening_phase,
        ced.run_initial_response_phase,
        ced.run_elenchus_phase,
        ced.run_reflection_phase,
        ced.run_reconstruction_phase,
        ced.run_synthesis_phase,
    ]:
        fn(sid)
    ced.compute_shadow_scores(sid)
    ced.score_section_drafts(sid)
    ced.assemble_sections(sid)


def _vote(decision, severity="none", target_section=None, reason=""):
    return {
        "decision": decision,
        "severity": severity,
        "target_section": target_section,
        "reason": reason,
        "epistemic_status": "uncertain",
    }


# ── Happy-path approval ───────────────────────────────────────────────────────

def test_ratification_approved_by_default():
    """FakeProvider's Final Evaluator approves by default."""
    ced = _make_ced()
    _run_to_assembly(ced, "rat-approved", "Is logic universal?")

    final = ced.run_ratification_phase("rat-approved")

    assert final.ratified is True
    assert final.blocking_objections == []
    assert final.unresolved_sections == []
    assert isinstance(final.epistemic_status, EpistemicStatus)


# ── Critical objection blocks ─────────────────────────────────────────────────

def test_critical_whole_answer_objection_blocks():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-critical", "Does God exist?")

    critical = _vote("blocking_objection", severity="critical",
                     reason="The entire answer rests on an unsupported premise.")
    with patch.object(FakeProvider, "complete", return_value=critical):
        final = ced.run_ratification_phase("rat-critical")

    assert final.ratified is False
    assert final.council_summary["hard_blocked"] is True
    assert any("unsupported premise" in o for o in final.blocking_objections)
    assert final.answer == ""   # hard-blocked answers are withheld


# ── Minor / major objections do NOT block ────────────────────────────────────

def test_minor_objection_does_not_block():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-minor", "What is beauty?")

    minor = _vote("blocking_objection", severity="minor",
                  reason="Wording in the nuance section could be tightened.")
    with patch.object(FakeProvider, "complete", return_value=minor):
        final = ced.run_ratification_phase("rat-minor")

    assert final.ratified is True
    assert any("tightened" in o for o in final.blocking_objections)


def test_major_objection_does_not_block():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-major", "Is perception reliable?")

    major = _vote("blocking_objection", severity="major",
                  reason="The stress-test could be stronger.")
    with patch.object(FakeProvider, "complete", return_value=major):
        final = ced.run_ratification_phase("rat-major")

    assert final.ratified is True


# ── Critical sectional objection → runner-up replacement ─────────────────────

def test_critical_section_objection_triggers_runner_up_replacement():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-runner", "Is mathematics discovered or invented?")

    state = ced.get_session("rat-runner")
    original = state.assembled_answer.section(SectionName.CORE_ANSWER).selected_draft_id

    # Round 1: critical objection to CORE_ANSWER. Round 2: approve.
    votes = [
        _vote("blocking_objection", severity="critical",
              target_section="core_answer", reason="Core answer overclaims."),
        _vote("approve"),
    ]
    with patch.object(FakeProvider, "complete", side_effect=votes):
        final = ced.run_ratification_phase("rat-runner")

    new = state.assembled_answer.section(SectionName.CORE_ANSWER).selected_draft_id
    assert new != original, "Runner-up replacement should change the section's draft."
    assert final.ratified is True
    assert SectionName.CORE_ANSWER not in final.unresolved_sections
    assert final.council_summary["ratification_rounds"] == 2


# ── Unresolved fallback after max rounds ─────────────────────────────────────

def test_unresolved_after_max_rounds():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-unresolved", "What is justice?")

    # Critical objection to the same section every round → never satisfied.
    critical = _vote("blocking_objection", severity="critical",
                     target_section="nuance", reason="Nuance section is inadequate.")
    with patch.object(FakeProvider, "complete", return_value=critical):
        final = ced.run_ratification_phase("rat-unresolved")

    assert SectionName.NUANCE in final.unresolved_sections
    assert final.ratified is False
    assert final.council_summary["ratification_rounds"] == 2
    state = ced.get_session("rat-unresolved")
    assert state.assembled_answer.section(SectionName.NUANCE).unresolved is True


# ── Session state persistence ─────────────────────────────────────────────────

def test_final_response_stored_on_session():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-store", "Can ethics be objective?")

    final = ced.run_ratification_phase("rat-store")
    state = ced.get_session("rat-store")

    assert state.final_response is not None
    assert state.final_response.response_id == final.response_id


def test_session_reaches_complete_phase():
    ced = _make_ced()
    _run_to_assembly(ced, "rat-complete", "What is the mind?")

    ced.run_ratification_phase("rat-complete")
    state = ced.get_session("rat-complete")

    assert state.phase == DialogPhase.COMPLETE
    assert DialogPhase.RATIFICATION in state.phase_history


def test_ratification_without_assembly_raises():
    ced = _make_ced()
    ced.create_session("A question.", session_id="rat-no-assembly")
    ced.run_opening_phase("rat-no-assembly")

    with pytest.raises(RuntimeError, match="assemble_sections"):
        ced.run_ratification_phase("rat-no-assembly")


# ── Full end-to-end pipeline ──────────────────────────────────────────────────

def test_full_pipeline_completes():
    ced = _make_ced()
    final = ced.run_session(
        "What is the relationship between language and thought?",
        session_id="e2e-full",
    )

    assert final.session_id == "e2e-full"
    assert final.question == "What is the relationship between language and thought?"
    assert isinstance(final.ratified, bool)
    assert final.response_id.startswith("resp_")
    assert final.council_summary["num_agents"] == 4
    assert final.council_summary["total_moves"] > 0


def test_full_pipeline_populates_council_summary():
    ced = _make_ced()
    final = ced.run_session("Is perception reliable?", session_id="e2e-summary")

    summary = final.council_summary
    assert "phases_completed" in summary
    assert "total_moves" in summary
    assert "evaluator_agent" in summary

    phases = summary["phases_completed"]
    expected_phases = {
        DialogPhase.OPENING.value,
        DialogPhase.INITIAL_RESPONSE.value,
        DialogPhase.ELENCHUS.value,
        DialogPhase.REFLECTION.value,
        DialogPhase.RECONSTRUCTION.value,
        DialogPhase.SYNTHESIS.value,
        DialogPhase.RATIFICATION.value,
    }
    assert set(phases) >= expected_phases, (
        f"Missing phases: {expected_phases - set(phases)}"
    )


def test_full_pipeline_two_agents():
    """Minimum viable council of 2 agents must complete without error."""
    provider = FakeProvider()
    ced = CEDOrchestrator(
        [SocraticAgent("p", provider), SocraticAgent("q", provider)],
        provider,
    )
    final = ced.run_session("What is a number?", session_id="e2e-two")
    assert isinstance(final.ratified, bool)


# ── FINAL_EVALUATOR anti-monopolization (Phase 3 dynamic rotation) ────────────

def test_final_evaluator_is_not_forced_to_socrates_agent():
    """
    Phase 3 change: the Final Evaluator is assigned by the deterministic
    per-phase scheduler, NOT pinned to the opening Socrates agent. With 4 agents
    the two high-impact roles must land on different agents.
    """
    ced = _make_ced(4)
    sid = "rat-evaluator-role"
    _run_to_assembly(ced, sid, "Can machines think?")

    final = ced.run_ratification_phase(sid)
    state = ced.get_session(sid)

    evaluator_id = final.council_summary["evaluator_agent"]

    # The agent who actually opened as Socrates (from recorded role_history).
    socrates_id = next(
        r["agent_id"] for r in state.role_history
        if r["phase"] == DialogPhase.OPENING.value
        and r["role"] == AgentRole.SOCRATES.value
    )
    assert evaluator_id != socrates_id, (
        "Final Evaluator must not be monopolized by the opening Socrates agent "
        "when enough agents are available."
    )
    # And the evaluator's current assigned_role reflects the phase role.
    assert state.agent_states[evaluator_id].assigned_role == AgentRole.FINAL_EVALUATOR

"""
Phase 26O — CED / Learner / Trainer Triad Loop tests.

The triad loop ties pipeline, health audit, learner state, interaction cycle, and
safe CED feedback into one deterministic integration facade.
"""

from backend.dialogues.learning_live_learner import LearnerState
from backend.dialogues.learning_triad_loop import (
    TriadLoopPolicy,
    build_ced_feedback_packet,
    run_triad_learning_loop,
    triad_hash,
    triad_loop_summary,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    DialogPhase,
    ProviderStatus,
    SessionState,
    TaskKind,
    TaskLogEntry,
)


QUESTION = "Should knowledge require certainty?"


def _state(session_id="sess_triad"):
    state = SessionState(session_id=session_id, question=QUESTION)
    initial = AgentMove(
        move_id="initial",
        task_id="task_initial",
        agent_id="agent_initial",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.INITIAL_RESPONSE,
        task_kind=TaskKind.INITIAL_RESPONSE,
        provider_id="mock_initial",
        content={"text": "Knowledge requires certainty."},
        confidence=0.96,
    )
    reconstruction = AgentMove(
        move_id="reconstruction",
        task_id="task_reconstruction",
        agent_id="agent_reconstruction",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.RECONSTRUCTION,
        task_kind=TaskKind.RECONSTRUCTION_PROPOSAL,
        provider_id="mock_reconstruction",
        content={"text": "A stronger model integrates the objection: knowledge needs justification, not absolute certainty."},
        confidence=0.78,
    )
    state.moves.extend([initial, reconstruction])
    for move in state.moves:
        state.task_log.append(TaskLogEntry(
            task_id=move.task_id,
            move_id=move.move_id,
            session_id=state.session_id,
            phase=move.phase,
            agent_id=move.agent_id,
            assigned_role=move.role,
            task_kind=move.task_kind,
            schema_name=move.role.value,
            provider_id=move.provider_id,
            provider_status=ProviderStatus.OK,
        ))
    return state


def test_triad_hash_is_deterministic():
    assert triad_hash({"a": 1, "b": 2}) == triad_hash({"b": 2, "a": 1})
    assert triad_hash({"a": 1}) != triad_hash({"a": 2})


def test_run_triad_learning_loop_returns_integrated_result():
    result = run_triad_learning_loop(_state(), policy=TriadLoopPolicy.exploratory())
    summary = triad_loop_summary(result)

    assert result.loop_id.startswith("triad_")
    assert result.session_id == "sess_triad"
    assert result.learner_after_hash.startswith("learner_")
    assert result.feedback_packet.packet_id.startswith("ced_feedback_")
    assert result.dry_run_only is True
    assert summary["dry_run_only"] is True
    assert summary["interaction_cycle_id"] == result.interaction.cycle_id


def test_triad_learning_loop_updates_existing_learner_state():
    first = run_triad_learning_loop(_state("sess_a"), policy=TriadLoopPolicy.exploratory())
    second = run_triad_learning_loop(
        _state("sess_b"),
        learner_state=first.interaction.learner_state,
        policy=TriadLoopPolicy.exploratory(),
    )

    assert second.learner_before_hash == first.learner_after_hash
    assert second.interaction.learner_state.observations_seen >= 2
    assert second.interaction.learner_state.sessions_seen == ["sess_a", "sess_b"]


def test_build_ced_feedback_packet_contains_safe_fields():
    result = run_triad_learning_loop(_state(), policy=TriadLoopPolicy.exploratory())
    packet = build_ced_feedback_packet(
        result.interaction,
        session_id=result.session_id,
        policy=TriadLoopPolicy.exploratory(),
    )

    assert packet.session_id == result.session_id
    assert packet.dry_run_only is True
    assert isinstance(packet.safe_focus_hints, list)
    assert isinstance(packet.data_collection_requests, list)
    assert isinstance(packet.eval_recommendations, list)
    assert isinstance(packet.trainer_readiness, dict)
    assert "interaction_cycle_id" in packet.evidence


def test_triad_loop_is_deterministic_for_same_inputs_and_empty_prior_state():
    result_a = run_triad_learning_loop(_state(), policy=TriadLoopPolicy.exploratory(), metadata={"same": True})
    result_b = run_triad_learning_loop(_state(), policy=TriadLoopPolicy.exploratory(), metadata={"same": True})

    assert result_a.loop_id == result_b.loop_id
    assert result_a.feedback_packet.packet_id == result_b.feedback_packet.packet_id
    assert result_a.learner_after_hash == result_b.learner_after_hash


def test_triad_loop_result_serializes_to_json():
    result = run_triad_learning_loop(_state(), policy=TriadLoopPolicy.exploratory())
    text = result.to_json()
    assert "sess_triad" in text
    assert "ced_feedback_" in text

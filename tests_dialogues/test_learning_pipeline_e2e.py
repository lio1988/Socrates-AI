"""
Phase 26K — End-to-end learning pipeline tests.

These tests verify the full offline learning chain from SessionState to dry-run
plan. No providers are called and no training is executed.
"""

import pytest

from backend.dialogues.learning_pipeline import (
    LearningPipelinePolicy,
    learning_pipeline_summary,
    run_learning_pipeline_from_state,
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


def _state_with_process_progression():
    state = SessionState(session_id="sess_e2e", question=QUESTION)

    initial = AgentMove(
        move_id="initial",
        task_id="task_initial",
        agent_id="agent_initial",
        role=AgentRole.THESIS_BUILDER,
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


def test_run_learning_pipeline_from_state_completes_without_training():
    state = _state_with_process_progression()
    result = run_learning_pipeline_from_state(
        state,
        policy=LearningPipelinePolicy.exploratory(),
        metadata={"test": "e2e"},
    )

    summary = learning_pipeline_summary(result)
    assert summary["pipeline_version"] == "phase_26k"
    assert summary["no_training_executed"] is True
    assert result.dataset.traces
    assert result.export_pack.artifacts
    assert result.quality_report.total_records > 0
    assert result.dry_run_plan.metadata["test"] == "e2e"
    assert "quality" in summary
    assert "plan" in summary


def test_pipeline_policy_rejects_unknown_policy_name():
    state = _state_with_process_progression()
    policy = LearningPipelinePolicy.exploratory()
    policy.preference_policy = "unknown"

    with pytest.raises(ValueError, match="unknown preference policy"):
        run_learning_pipeline_from_state(state, policy=policy)

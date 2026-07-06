"""
Phase 26L — Learning Health Audit tests.

The health audit converts a full pipeline result into a PASS/WARN/FAIL dashboard.
It is diagnostic only and never trains.
"""

from backend.dialogues.learning_health_audit import (
    HealthStatus,
    LearningHealthPolicy,
    audit_learning_pipeline_result,
    learning_health_summary,
)
from backend.dialogues.learning_pipeline import LearningPipelinePolicy, run_learning_pipeline_from_state
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    DialogPhase,
    ProviderStatus,
    SessionState,
    TaskKind,
    TaskLogEntry,
)
from backend.dialogues.learning_quality_gates import QualityVerdict


QUESTION = "Should knowledge require certainty?"


def _state():
    state = SessionState(session_id="sess_health", question=QUESTION)
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


def _result():
    return run_learning_pipeline_from_state(_state(), policy=LearningPipelinePolicy.exploratory())


def test_health_audit_returns_dashboard_for_pipeline_result():
    audit = audit_learning_pipeline_result(_result(), policy=LearningHealthPolicy.exploratory())
    summary = learning_health_summary(audit)

    assert audit.audit_version == "phase_26l"
    assert audit.stages
    assert summary["overall_status"] in {"pass", "warn", "fail"}
    assert "collector" in summary["pass_stages"] or "collector" in summary["warn_stages"] or "collector" in summary["fail_stages"]


def test_health_audit_fails_when_collector_has_no_traces():
    state = SessionState(session_id="empty", question="Empty?")
    result = run_learning_pipeline_from_state(state, policy=LearningPipelinePolicy.exploratory())
    audit = audit_learning_pipeline_result(result, policy=LearningHealthPolicy.exploratory())

    assert audit.overall_status == HealthStatus.FAIL
    assert any("collector" in failure for failure in audit.failures)


def test_health_audit_warns_on_quality_warn():
    result = _result()
    result.quality_report.verdict = QualityVerdict.WARN
    result.quality_report.issues = []
    audit = audit_learning_pipeline_result(result, policy=LearningHealthPolicy.exploratory())

    assert audit.overall_status in {HealthStatus.WARN, HealthStatus.FAIL}
    assert any(stage.stage.value == "quality_gates" and stage.status == HealthStatus.WARN for stage in audit.stages)


def test_health_audit_fails_when_no_training_flag_missing():
    result = _result()
    result.summary["no_training_executed"] = False
    audit = audit_learning_pipeline_result(result, policy=LearningHealthPolicy.exploratory())

    assert audit.overall_status == HealthStatus.FAIL
    assert any(stage.stage.value == "safety_invariants" and stage.status == HealthStatus.FAIL for stage in audit.stages)


def test_health_audit_summary_lists_failed_and_warned_stages():
    result = _result()
    result.summary["no_training_executed"] = False
    audit = audit_learning_pipeline_result(result, policy=LearningHealthPolicy.exploratory())
    summary = learning_health_summary(audit)

    assert "safety_invariants" in summary["fail_stages"]
    assert summary["audit_version"] == "phase_26l"

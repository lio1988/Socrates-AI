"""
Phase 26N — Learner / Trainer / CED Interaction Control Plane tests.

The control plane lets CED, Learner, and Trainer communicate through typed,
deterministic, safety-gated messages. It never mutates CED or trains.
"""

from backend.dialogues.learning_health_audit import LearningHealthPolicy, audit_learning_pipeline_result
from backend.dialogues.learning_interaction_control import (
    AdvisoryStatus,
    ControlActor,
    ControlMessageKind,
    build_trainer_capability_report,
    interaction_cycle_summary,
    interaction_hash,
    run_interaction_cycle,
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


QUESTION = "Should knowledge require certainty?"


def _state(session_id="sess_interaction"):
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


def _pipeline_and_health(session_id="sess_interaction"):
    pipeline = run_learning_pipeline_from_state(
        _state(session_id),
        policy=LearningPipelinePolicy.exploratory(),
    )
    health = audit_learning_pipeline_result(pipeline, policy=LearningHealthPolicy.exploratory())
    return pipeline, health


def test_interaction_hash_is_deterministic():
    assert interaction_hash({"a": 1, "b": 2}) == interaction_hash({"b": 2, "a": 1})
    assert interaction_hash({"a": 1}) != interaction_hash({"a": 2})


def test_trainer_capability_report_reads_dry_run_plan():
    pipeline, _ = _pipeline_and_health()
    report = build_trainer_capability_report(pipeline)
    assert report.no_training_executed is True
    assert isinstance(report.ready_families, list)
    assert isinstance(report.blocked_families, list)


def test_interaction_cycle_creates_typed_messages_and_advisories():
    pipeline, health = _pipeline_and_health()
    cycle = run_interaction_cycle(pipeline, health, metadata={"test": "interaction"})

    assert cycle.no_training_executed is True
    assert cycle.messages
    assert cycle.ced_advisories
    assert any(m.sender == ControlActor.CED and m.recipient == ControlActor.LEARNER for m in cycle.messages)
    assert any(m.sender == ControlActor.LEARNER and m.recipient == ControlActor.TRAINER for m in cycle.messages)
    assert any(m.sender == ControlActor.TRAINER and m.recipient == ControlActor.LEARNER for m in cycle.messages)
    assert any(m.recipient == ControlActor.CED for m in cycle.messages)
    assert any(a.status == AdvisoryStatus.BLOCKED for a in cycle.ced_advisories)


def test_interaction_cycle_is_deterministic_for_same_inputs():
    pipeline, health = _pipeline_and_health()
    cycle_a = run_interaction_cycle(pipeline, health, metadata={"same": True})
    cycle_b = run_interaction_cycle(pipeline, health, metadata={"same": True})

    assert cycle_a.cycle_id == cycle_b.cycle_id
    assert [m.message_id for m in cycle_a.messages] == [m.message_id for m in cycle_b.messages]
    assert [a.advisory_id for a in cycle_a.ced_advisories] == [a.advisory_id for a in cycle_b.ced_advisories]


def test_interaction_cycle_summary_lists_blocked_actions():
    pipeline, health = _pipeline_and_health()
    cycle = run_interaction_cycle(pipeline, health)
    summary = interaction_cycle_summary(cycle)

    assert summary["no_training_executed"] is True
    assert "automatic_ced_core_change" in summary["blocked_actions"]
    assert "automatic_weight_update" in summary["blocked_actions"]
    assert "real_training_without_explicit_human_task" in summary["blocked_actions"]
    assert summary["message_count"] >= 3


def test_human_approval_required_for_ready_trainer_advisory_when_ready_jobs_exist():
    pipeline, health = _pipeline_and_health()
    for job in pipeline.dry_run_plan.jobs:
        job.readiness = job.readiness.READY
    cycle = run_interaction_cycle(pipeline, health)

    assert any(a.status == AdvisoryStatus.HUMAN_APPROVAL_REQUIRED for a in cycle.ced_advisories)
    assert any(m.kind == ControlMessageKind.CED_ADVISORY and m.requires_human_approval for m in cycle.messages)

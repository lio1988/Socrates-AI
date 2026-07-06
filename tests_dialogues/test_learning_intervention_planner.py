"""
Phase 26P — Learning Intervention Planner tests.

The planner converts triad feedback into ranked, non-executing intervention
proposals with priorities, evidence, and review flags.
"""

from backend.dialogues.learning_intervention_planner import (
    InterventionKind,
    InterventionPlanPolicy,
    InterventionPriority,
    build_intervention_plan,
    intervention_hash,
    intervention_plan_summary,
    interventions_from_feedback,
)
from backend.dialogues.learning_triad_loop import TriadLoopPolicy, run_triad_learning_loop
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


def _state(session_id="sess_intervention"):
    state = SessionState(session_id=session_id, question=QUESTION)
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


def _triad():
    return run_triad_learning_loop(_state(), policy=TriadLoopPolicy.exploratory())


def test_intervention_hash_is_deterministic():
    assert intervention_hash({"a": 1, "b": 2}) == intervention_hash({"b": 2, "a": 1})
    assert intervention_hash({"a": 1}) != intervention_hash({"a": 2})


def test_interventions_from_feedback_are_non_executable_and_ranked():
    triad = _triad()
    interventions = interventions_from_feedback(
        triad.feedback_packet,
        health_status=triad.health.overall_status.value,
        policy=InterventionPlanPolicy.conservative(),
    )
    assert interventions
    assert all(i.executable is False for i in interventions)
    priority_values = [i.priority for i in interventions]
    assert priority_values == sorted(priority_values, key=lambda p: {"critical": 0, "high": 1, "medium": 2, "low": 3}[p.value])


def test_build_intervention_plan_returns_summary():
    plan = build_intervention_plan(_triad(), policy=InterventionPlanPolicy.conservative())
    summary = intervention_plan_summary(plan)

    assert plan.plan_id.startswith("intervention_plan_")
    assert plan.dry_run_only is True
    assert summary["plan_id"] == plan.plan_id
    assert summary["intervention_count"] == len(plan.interventions)
    assert "top_actions" in summary


def test_failed_health_status_creates_critical_quality_intervention():
    triad = _triad()
    triad.health.overall_status = triad.health.overall_status.FAIL
    plan = build_intervention_plan(triad, policy=InterventionPlanPolicy.conservative())

    assert any(i.kind == InterventionKind.REVIEW_QUALITY for i in plan.interventions)
    assert any(i.priority == InterventionPriority.CRITICAL for i in plan.interventions)


def test_compact_policy_limits_low_priority_items():
    triad = _triad()
    plan = build_intervention_plan(triad, policy=InterventionPlanPolicy.compact())

    assert len(plan.interventions) <= InterventionPlanPolicy.compact().max_interventions
    assert all(i.priority != InterventionPriority.LOW for i in plan.interventions)


def test_readiness_items_can_require_human_review():
    triad = _triad()
    triad.feedback_packet.trainer_readiness["ready_families"] = ["dpo"]
    plan = build_intervention_plan(triad, policy=InterventionPlanPolicy.conservative())

    assert any(i.requires_human_review for i in plan.interventions)
    assert any(i.kind == InterventionKind.INSPECT_READINESS for i in plan.interventions)


def test_intervention_plan_serializes_to_json():
    plan = build_intervention_plan(_triad())
    text = plan.to_json()
    assert "intervention_plan_" in text
    assert "dry_run_only" in text

from backend.dialogues.learning_health_audit import LearningHealthPolicy, audit_learning_pipeline_result
from backend.dialogues.learning_live_learner import (
    LearnerSignal,
    LearnerState,
    deterministic_live_learn,
    derive_lessons_from_pipeline,
    learner_state_summary,
    observe_learning_pipeline,
    stable_learner_hash,
    update_learner_state,
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


def _state(session_id="sess_learner"):
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


def _pipeline_and_audit(session_id="sess_learner"):
    pipeline = run_learning_pipeline_from_state(
        _state(session_id),
        policy=LearningPipelinePolicy.exploratory(),
    )
    audit = audit_learning_pipeline_result(pipeline, policy=LearningHealthPolicy.exploratory())
    return pipeline, audit


def test_stable_learner_hash_is_order_insensitive_for_dicts():
    assert stable_learner_hash({"a": 1, "b": 2}) == stable_learner_hash({"b": 2, "a": 1})
    assert stable_learner_hash({"a": 1}) != stable_learner_hash({"a": 2})


def test_derive_lessons_from_pipeline_includes_safety_signal():
    pipeline, audit = _pipeline_and_audit()
    lessons = derive_lessons_from_pipeline(pipeline, audit)
    assert lessons
    assert any(lesson.signal == LearnerSignal.SAFETY for lesson in lessons)
    assert all(lesson.lesson_id.startswith("lesson_") for lesson in lessons)


def test_observe_learning_pipeline_is_deterministic_for_same_inputs():
    pipeline, audit = _pipeline_and_audit()
    obs_a = observe_learning_pipeline(pipeline, audit, metadata={"run": "same"})
    obs_b = observe_learning_pipeline(pipeline, audit, metadata={"run": "same"})
    assert obs_a.observation_id == obs_b.observation_id
    assert [l.lesson_id for l in obs_a.derived_lessons] == [l.lesson_id for l in obs_b.derived_lessons]


def test_update_learner_state_accumulates_lessons_and_is_idempotent_for_same_observation():
    pipeline, audit = _pipeline_and_audit()
    observation = observe_learning_pipeline(pipeline, audit)

    state = update_learner_state(None, observation)
    again = update_learner_state(state, observation)

    assert state.observations_seen == 1
    assert again.observations_seen == 1
    assert state.last_observation_id == observation.observation_id
    assert state.lessons
    assert state.safety_flags


def test_deterministic_live_learn_updates_state_across_sessions():
    pipeline_a, audit_a = _pipeline_and_audit("sess_a")
    pipeline_b, audit_b = _pipeline_and_audit("sess_b")

    state = deterministic_live_learn(pipeline_a, audit_a)
    state = deterministic_live_learn(pipeline_b, audit_b, state=state)
    summary = learner_state_summary(state)

    assert summary["observations_seen"] == 2
    assert summary["sessions_seen"] == ["sess_a", "sess_b"]
    assert summary["lesson_count"] >= 1
    assert "safety_invariants" in summary["strengths"] or summary["safety_flags"]


def test_learner_state_serializes_to_json():
    state = LearnerState()
    text = state.to_json()
    assert "deterministic_live_learner" in text

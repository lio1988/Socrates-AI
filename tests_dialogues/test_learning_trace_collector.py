"""
Phase 26D — Learning trace collector tests.

The collector is post-run and opt-in: it reads SessionState and registry metadata,
builds sanitized LearningDataset records, and never calls providers or mutates CED
execution semantics.
"""

from backend.dialogues.learning_foundation import LearningSignalKind
from backend.dialogues.learning_trace_collector import (
    collect_learning_dataset,
    collect_ratification_traces,
    collect_score_traces,
    collect_task_traces,
    infer_provider_family,
    learning_export_summary,
    provider_catalog,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    CouncilRatification,
    CouncilRatificationStatus,
    CouncilVerdict,
    DialogPhase,
    MicroScore,
    ObjectionSeverity,
    ProviderStatus,
    RatificationVerdict,
    ScoreBreakdown,
    SectionName,
    SessionState,
    TaskKind,
    TaskLogEntry,
)
from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider


def _state_with_one_move():
    state = SessionState(session_id="sess_trace", question="What makes belief knowledge?")
    move = AgentMove(
        move_id="move_good",
        task_id="task_good",
        agent_id="agent_0",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.SYNTHESIS,
        content={
            "text": "Knowledge requires justification and truth, but the account is contested.",
            "hidden_audit": "must not leak",
        },
        confidence=0.82,
        provider_id="mock_seat0",
        task_kind=TaskKind.SYNTHESIS_DRAFT,
    )
    state.moves.append(move)
    state.task_log.append(TaskLogEntry(
        task_id="task_good",
        move_id="move_good",
        session_id="sess_trace",
        phase=DialogPhase.SYNTHESIS,
        agent_id="agent_0",
        assigned_role=AgentRole.SYNTHESIZER,
        task_kind=TaskKind.SYNTHESIS_DRAFT,
        schema_name="synthesizer",
        context_hash="abc123",
        provider_id="mock_seat0",
        provider_status=ProviderStatus.OK,
        debug_context={"hidden_audit": "private", "public_hint": "safe"},
    ))
    return state


def _registry():
    reg = CouncilProviderRegistry()
    reg.register(ScriptedMockProvider("mock_seat0"))
    return reg


def test_infer_provider_family_and_catalog_are_metadata_only():
    assert infer_provider_family(provider_id="nvidia_seat0") == "nvidia"
    assert infer_provider_family(provider_name="Anthropic Live", model="claude-opus-4-8") == "anthropic"
    assert infer_provider_family(provider_id="mock_seat0") == "mock"

    catalog = provider_catalog(_registry())
    assert catalog["mock_seat0"].provider_family == "mock"
    assert catalog["mock_seat0"].model == "mock"


def test_collect_task_traces_turns_successful_moves_into_eligible_sanitized_traces():
    state = _state_with_one_move()
    traces = collect_task_traces(state, registry=_registry())

    assert len(traces) == 1
    trace = traces[0]
    assert trace.signal_kind == LearningSignalKind.PROVIDER_MOVE
    assert trace.ok
    assert trace.provider_family == "mock"
    assert trace.metadata["source"] == "task_log"
    assert trace.metadata["context_hash"] == "abc123"
    assert "hidden_audit" not in trace.content
    assert trace.eligibility and trace.eligibility.eligible


def test_failed_task_log_entries_are_trace_only_not_training_eligible():
    state = _state_with_one_move()
    state.task_log.append(TaskLogEntry(
        task_id="task_bad",
        move_id=None,
        session_id="sess_trace",
        phase=DialogPhase.ELENCHUS,
        agent_id="agent_1",
        assigned_role=AgentRole.ELENCHUS_CRITIC,
        task_kind=TaskKind.ELENCHUS_OBJECTION,
        provider_id="mock_seat1",
        provider_status=ProviderStatus.TIMEOUT,
    ))

    ds = collect_learning_dataset(state, registry=_registry(), include_scores=False, include_ratification=False)
    failed = [t for t in ds.traces if t.task_id == "task_bad"][0]
    assert failed.status == ProviderStatus.TIMEOUT.value
    assert failed.eligibility and not failed.eligibility.eligible
    assert all(t.task_id != "task_bad" for t in ds.eligible_traces())


def test_ratification_verdicts_are_collected_as_trace_only_signals():
    state = _state_with_one_move()
    state.council_ratification = CouncilRatification(
        session_id=state.session_id,
        status=CouncilRatificationStatus.RATIFIED,
        verdicts=[RatificationVerdict(
            session_id=state.session_id,
            agent_id="mock_seat0",
            provider_id="mock_seat0",
            verdict=CouncilVerdict.ACCEPT,
            rationale="The synthesis is acceptable with proper uncertainty.",
            confidence=0.8,
            severity=ObjectionSeverity.NONE,
            provider_status=ProviderStatus.OK,
            task_id="rat_task_0",
            move_id="rat_move_0",
        )],
        valid_verdicts=1,
        quorum=1,
    )

    traces = collect_ratification_traces(state, registry=_registry())
    assert len(traces) == 1
    trace = traces[0]
    assert trace.signal_kind == LearningSignalKind.RATIFICATION
    assert trace.task_kind == TaskKind.COUNCIL_RATIFICATION.value
    assert trace.eligibility and not trace.eligibility.eligible
    assert "verdict" in trace.content


def test_score_traces_are_collected_but_remain_trace_only():
    state = _state_with_one_move()
    state.micro_scores.append(MicroScore(
        session_id=state.session_id,
        output_id="move_good",
        phase=DialogPhase.SYNTHESIS,
        rubric_name="synthesis_quality",
        author_agent_id="agent_0",
        voter_agent_id="mock_seat0",
        provider_id="mock_seat0",
        score_breakdown=ScoreBreakdown(
            epistemic_value=8,
            logical_rigor=8,
            factual_grounding=7,
            constructive_impact=7,
            intellectual_honesty=9,
            clarity_precision=8,
            grounded_creativity=6,
        ),
        confidence=0.7,
        justification="Good calibration.",
    ))

    traces = collect_score_traces(state, registry=_registry())
    assert len(traces) == 1
    trace = traces[0]
    assert trace.signal_kind == LearningSignalKind.PEER_SCORE
    assert trace.task_kind == TaskKind.MOVE_SCORE.value
    assert trace.content["overall_score"] is not None
    assert trace.eligibility and not trace.eligibility.eligible


def test_collect_learning_dataset_and_summary_counts_signals():
    state = _state_with_one_move()
    ds = collect_learning_dataset(state, registry=_registry(), include_scores=True, include_ratification=True)
    summary = learning_export_summary(ds)

    assert summary["trace_count"] >= 1
    assert summary["eligible_trace_count"] == 1
    assert summary["signals"][LearningSignalKind.PROVIDER_MOVE.value] == 1
    assert ds.trace_jsonl(eligible_only=True)

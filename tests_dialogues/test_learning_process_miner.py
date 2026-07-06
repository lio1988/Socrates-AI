"""
Phase 26F — Process Reward Miner tests.

The process miner converts CED phase traces into process SFT and process preference
examples without touching CED runtime behavior.
"""

from backend.dialogues.learning_foundation import (
    LearningDataset,
    LearningTrace,
    LearningUse,
    TrainingEligibility,
)
from backend.dialogues.learning_process_miner import (
    ProcessMiningPolicy,
    ProcessSignal,
    mine_process_examples,
    mine_process_transitions,
    process_reward_summary,
    score_process_step,
)
from backend.dialogues.models import ProviderStatus, TaskKind


QUESTION = "Should knowledge require certainty?"


def _trace(trace_id, *, phase, task_kind, text, confidence=0.72, eligible=True,
           provider="p", winner_sections=None):
    t = LearningTrace(
        trace_id=trace_id,
        session_id="sess_proc",
        task_id=f"task_{trace_id}",
        question=QUESTION,
        provider_id=provider,
        provider_family="mock",
        model="mock",
        agent_id=f"agent_{provider}",
        role="synthesizer",
        phase=phase,
        task_kind=task_kind,
        status=ProviderStatus.OK.value,
        content={"text": text},
        confidence=confidence,
        winner_sections=winner_sections or [],
    )
    t.eligibility = (
        TrainingEligibility.accept(LearningUse.SUPERVISED_DISTILLATION)
        if eligible
        else TrainingEligibility.reject("test rejection")
    )
    return t


def test_score_process_step_rewards_real_socratic_objection():
    trace = _trace(
        "objection",
        phase="elenchus",
        task_kind=TaskKind.ELENCHUS_OBJECTION.value,
        text="This argument hides an assumption and lacks evidence for certainty.",
    )
    scored = score_process_step(trace)
    assert scored.score > 0
    assert ProcessSignal.OBJECTION.value in scored.signals


def test_score_process_step_rewards_reflection_that_revises():
    trace = _trace(
        "reflection",
        phase="reflection",
        task_kind=TaskKind.REFLECTION_REVISION.value,
        text="I revise my earlier claim because the objection shows uncertainty remains.",
    )
    scored = score_process_step(trace)
    assert scored.score > 0
    assert ProcessSignal.REFLECTION.value in scored.signals


def test_mine_process_transitions_finds_forward_improvement():
    before = _trace(
        "initial",
        phase="initial_response",
        task_kind=TaskKind.INITIAL_RESPONSE.value,
        text="Knowledge requires certainty.",
        confidence=0.95,
    )
    after = _trace(
        "reflection",
        phase="reflection",
        task_kind=TaskKind.REFLECTION_REVISION.value,
        text="I revise the claim because the objection shows certainty is too strong.",
        confidence=0.72,
        winner_sections=["nuance"],
    )
    ds = LearningDataset(traces=[before, after])

    report = mine_process_transitions(ds, policy=ProcessMiningPolicy.balanced())
    assert report.transition_count >= 1
    transition = report.transitions[0]
    assert transition.before_trace_id == "initial"
    assert transition.after_trace_id == "reflection"
    assert transition.gain > 0


def test_mine_process_examples_creates_sft_and_preference_outputs():
    before = _trace(
        "initial",
        phase="initial_response",
        task_kind=TaskKind.INITIAL_RESPONSE.value,
        text="Knowledge requires certainty.",
        confidence=0.96,
    )
    after = _trace(
        "reconstruction",
        phase="reconstruction",
        task_kind=TaskKind.RECONSTRUCTION_PROPOSAL.value,
        text="A stronger model integrates the objection: knowledge needs justification, not absolute certainty.",
        confidence=0.75,
        winner_sections=["core_answer", "nuance"],
    )
    ds = LearningDataset(traces=[before, after])

    report = mine_process_examples(ds, policy=ProcessMiningPolicy.balanced(), attach_preferences=True)
    assert report.sft_count >= 1
    assert report.preference_count >= 1
    assert len(ds.preferences) >= 1
    assert "Produce the improved next process move" in report.sft_examples[0].prompt
    assert "stronger model" in report.sft_examples[0].response.lower()


def test_non_forward_transition_is_skipped():
    reflection = _trace(
        "reflection",
        phase="reflection",
        task_kind=TaskKind.REFLECTION_REVISION.value,
        text="I revise because of the objection.",
    )
    initial = _trace(
        "initial",
        phase="initial_response",
        task_kind=TaskKind.INITIAL_RESPONSE.value,
        text="Knowledge requires certainty.",
    )
    ds = LearningDataset(traces=[reflection, initial])

    report = mine_process_transitions(ds)
    assert all(t.before_phase != "reflection" or t.after_phase != "initial_response" for t in report.transitions)


def test_process_miner_requires_after_eligible_by_default():
    before = _trace(
        "initial",
        phase="initial_response",
        task_kind=TaskKind.INITIAL_RESPONSE.value,
        text="Knowledge requires certainty.",
    )
    after = _trace(
        "bad_after",
        phase="reflection",
        task_kind=TaskKind.REFLECTION_REVISION.value,
        text="I revise because of the objection.",
        eligible=False,
    )
    ds = LearningDataset(traces=[before, after])

    report = mine_process_transitions(ds, policy=ProcessMiningPolicy.aggressive())
    assert report.transition_count == 0
    assert any("after trace not eligible" in s["reason"] for s in report.skipped)


def test_process_reward_summary_counts_outputs():
    before = _trace(
        "initial",
        phase="initial_response",
        task_kind=TaskKind.INITIAL_RESPONSE.value,
        text="Knowledge requires certainty.",
        confidence=0.95,
    )
    after = _trace(
        "synthesis",
        phase="synthesis",
        task_kind=TaskKind.SYNTHESIS_DRAFT.value,
        text="The final view preserves uncertainty and avoids absolute certainty.",
        winner_sections=["core_answer", "final_verdict"],
    )
    ds = LearningDataset(traces=[before, after])
    report = mine_process_examples(ds, policy=ProcessMiningPolicy.balanced())
    summary = process_reward_summary(report)

    assert summary["traces_seen"] == 2
    assert summary["process_traces_seen"] == 2
    assert "transition_count" in summary
    assert "sft_count" in summary

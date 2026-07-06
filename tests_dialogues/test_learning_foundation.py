"""
Phase 26C — CED Learning Foundation tests.

These tests verify dataset safety and training-readiness rules only. They do not
train models, call providers, or require API keys.
"""

import json

import pytest

from backend.dialogues.learning_foundation import (
    EvalExample,
    EvalVerifierType,
    LearningDataset,
    LearningTrace,
    PreferenceExample,
    SocratesConstitution,
    assess_training_eligibility,
    build_preference_example,
    sanitize_public_payload,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    AgentTask,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    TaskKind,
)


def _task(kind=TaskKind.SYNTHESIS_DRAFT):
    return AgentTask(
        session_id="sess_learning",
        agent_id="agent_0",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.SYNTHESIS,
        question="What makes a belief knowledge?",
        task_kind=kind,
        output_schema={"type": "object"},
    )


def _ok_response(task, *, content=None, confidence=0.8, provider_id="provider_a", raw="raw secret sk-testsecret123456"):
    move = AgentMove(
        task_id=task.task_id,
        agent_id=task.agent_id,
        role=task.role,
        phase=task.phase,
        content=content or {"text": "A calibrated answer."},
        confidence=confidence,
    )
    return ProviderResponse(
        provider_id=provider_id,
        agent_id=task.agent_id,
        status=ProviderStatus.OK,
        raw_text=raw,
        parsed_move=move,
    )


def test_sanitize_public_payload_removes_hidden_fields_and_redacts_keys():
    payload = {
        "answer": "ok",
        "hidden_audit": {"scoreboard": "private"},
        "nested": {
            "api_key": "sk-abc123456789",
            "safe": "token-like nvapi-secret123456 should redact",
        },
    }
    clean = sanitize_public_payload(payload)
    assert "hidden_audit" not in clean
    assert "api_key" not in clean["nested"]
    assert "***REDACTED***" in clean["nested"]["safe"]


def test_learning_trace_from_valid_response_is_eligible_and_public_safe():
    task = _task()
    resp = _ok_response(task, content={
        "text": "A good synthesis.",
        "hidden_audit": "must not leak",
        "nested": {"secret": "nope", "visible": "yes"},
    })
    trace = LearningTrace.from_provider_response(
        task,
        resp,
        provider_family="nvidia",
        model="nvidia/test-model",
        include_raw_text=True,
        metadata={"provider_mapping": "hidden", "safe_tag": "learning"},
    )

    assert trace.ok
    assert trace.eligibility and trace.eligibility.eligible
    assert trace.content["text"] == "A good synthesis."
    assert "hidden_audit" not in trace.content
    assert "secret" not in trace.content["nested"]
    assert trace.raw_text and "***REDACTED***" in trace.raw_text

    public = trace.public_payload()
    assert "raw_text" not in public
    assert public["metadata"] == {"safe_tag": "learning"}


def test_failed_provider_output_is_trace_only_not_training_data():
    task = _task()
    resp = ProviderResponse(
        provider_id="provider_bad",
        agent_id=task.agent_id,
        status=ProviderStatus.INVALID_JSON,
        raw_text="<<< bad >>>",
    )
    trace = LearningTrace.from_provider_response(task, resp)
    assert not trace.ok
    assert trace.eligibility and not trace.eligibility.eligible

    ds = LearningDataset(traces=[trace])
    assert ds.eligible_traces() == []
    assert ds.trace_jsonl(eligible_only=True) == ""


def test_scoring_and_ratification_tasks_are_trace_only_by_default():
    task = _task(TaskKind.MOVE_SCORE)
    trace = LearningTrace.from_provider_response(task, _ok_response(task))
    elig = assess_training_eligibility(trace, SocratesConstitution.default())
    assert not elig.eligible
    assert any("trace-only" in reason for reason in elig.reasons)


def test_low_confidence_valid_move_is_not_training_eligible():
    task = _task()
    trace = LearningTrace.from_provider_response(task, _ok_response(task, confidence=0.2))
    assert trace.eligibility and not trace.eligibility.eligible
    assert "below minimum" in trace.eligibility.reasons[0]


def test_preference_example_requires_valid_chosen_and_valid_rejected_move():
    task = _task()
    chosen = LearningTrace.from_provider_response(
        task,
        _ok_response(task, content={"text": "Chosen: qualified and evidence-aware."}, provider_id="p_chosen"),
    )
    rejected = LearningTrace.from_provider_response(
        task,
        _ok_response(task, content={"text": "Rejected: overconfident and vague."}, provider_id="p_rejected"),
    )

    pref = build_preference_example(
        chosen,
        rejected,
        rationale="Chosen is better calibrated and preserves uncertainty.",
    )
    assert isinstance(pref, PreferenceExample)
    rec = pref.to_dpo_record()
    assert rec["prompt"] == task.question
    assert "Chosen" in rec["chosen"]
    assert "Rejected" in rec["rejected"]
    assert rec["metadata"]["chosen_provider"] == "p_chosen"


def test_preference_example_rejects_failed_negative_as_training_pair():
    task = _task()
    chosen = LearningTrace.from_provider_response(task, _ok_response(task, content={"text": "Valid."}))
    failed = LearningTrace.from_provider_response(task, ProviderResponse(
        provider_id="provider_bad",
        agent_id=task.agent_id,
        status=ProviderStatus.TIMEOUT,
    ))
    with pytest.raises(ValueError, match="provider failures are trace-only"):
        build_preference_example(chosen, failed, rationale="Failed provider is not a DPO negative.")


def test_eval_example_requires_verification_signal():
    with pytest.raises(ValueError, match="expected_answer"):
        EvalExample(question="2+2?", verifier_type=EvalVerifierType.EXACT)

    ev = EvalExample(
        question="2+2?",
        verifier_type=EvalVerifierType.EXACT,
        expected_answer="4",
        tags=["math", "smoke"],
    )
    assert ev.to_jsonl_record()["expected_answer"] == "4"


def test_learning_dataset_exports_trace_dpo_and_eval_jsonl():
    task = _task()
    chosen = LearningTrace.from_provider_response(
        task,
        _ok_response(task, content={"text": "Good answer."}, provider_id="p1"),
    )
    rejected = LearningTrace.from_provider_response(
        task,
        _ok_response(task, content={"text": "Weak answer."}, provider_id="p2"),
    )
    pref = build_preference_example(chosen, rejected, rationale="Good answer is more calibrated.")
    ev = EvalExample(question="Capital of France?", verifier_type=EvalVerifierType.EXACT,
                     accepted_answers=["Paris"])
    ds = LearningDataset(traces=[chosen, rejected], preferences=[pref], evals=[ev])

    trace_lines = [json.loads(line) for line in ds.trace_jsonl(eligible_only=True).splitlines()]
    dpo_lines = [json.loads(line) for line in ds.dpo_jsonl().splitlines()]
    eval_lines = [json.loads(line) for line in ds.eval_jsonl().splitlines()]

    assert len(trace_lines) == 2
    assert "raw_text" not in trace_lines[0]
    assert dpo_lines[0]["chosen"] == "Good answer."
    assert eval_lines[0]["accepted_answers"] == ["Paris"]


def test_default_constitution_contains_core_ced_learning_principles():
    constitution = SocratesConstitution.default()
    block = constitution.principle_block()
    assert "evidence_over_agreement" in block
    assert "no_overclaiming" in block
    assert "failed_outputs_are_not_training_targets" in block
    assert "hidden_audit_is_not_training_prompt" in block

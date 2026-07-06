"""
Phase 26S — Evidence Claim Gates tests.

Claim gates evaluate explicit scientific claims against evidence harness reports.
"""

from backend.dialogues.learning_evidence_claim_gates import (
    EvidenceClaim,
    EvidenceClaimKind,
    EvidenceClaimPolicy,
    EvidenceClaimVerdict,
    claim_gate_hash,
    evaluate_evidence_claim,
    evidence_claim_gate_summary,
    make_default_ced_vs_baseline_claims,
    run_evidence_claim_gates,
)
from backend.dialogues.learning_evidence_harness import CandidateSystemKind, CandidateSystemOutput, run_evidence_harness
from backend.dialogues.learning_ground_truth_checks import GroundTruthTask, GroundTruthTaskKind


def _tasks(count=12):
    return [
        GroundTruthTask(task_id=f"t{i}", kind=GroundTruthTaskKind.EXACT_TEXT, prompt=f"Task {i}", gold_answer="yes")
        for i in range(count)
    ]


def _outputs(ced_correct=10, baseline_correct=7, count=12):
    outputs = []
    for i in range(count):
        outputs.append(CandidateSystemOutput(
            system_id="ced",
            system_kind=CandidateSystemKind.CED,
            task_id=f"t{i}",
            answer="yes" if i < ced_correct else "no",
            confidence=0.9 if i < ced_correct else 0.2,
        ))
        outputs.append(CandidateSystemOutput(
            system_id="baseline",
            system_kind=CandidateSystemKind.BASELINE,
            task_id=f"t{i}",
            answer="yes" if i < baseline_correct else "no",
            confidence=0.7 if i < baseline_correct else 0.6,
        ))
    return outputs


def _report(ced_correct=10, baseline_correct=7, count=12):
    return run_evidence_harness(_tasks(count), _outputs(ced_correct, baseline_correct, count))


def test_claim_gate_hash_is_deterministic():
    assert claim_gate_hash({"a": 1, "b": 2}) == claim_gate_hash({"b": 2, "a": 1})
    assert claim_gate_hash({"a": 1}) != claim_gate_hash({"a": 2})


def test_system_beats_baseline_supported_when_margins_pass():
    policy = EvidenceClaimPolicy(min_task_count=10, min_coverage=0.8, min_accuracy_margin=0.05, min_score_ratio_margin=0.05)
    claim = EvidenceClaim(
        claim_id="ced_beats",
        kind=EvidenceClaimKind.SYSTEM_BEATS_BASELINE,
        target_system_id="ced",
        baseline_system_id="baseline",
        statement="CED beats baseline.",
        policy=policy,
    )
    result = evaluate_evidence_claim(claim, _report())
    assert result.verdict == EvidenceClaimVerdict.SUPPORTED
    assert result.metrics["accuracy_margin"] > 0


def test_system_beats_baseline_not_supported_when_margin_is_small():
    policy = EvidenceClaimPolicy(min_task_count=10, min_coverage=0.8, min_accuracy_margin=0.20, min_score_ratio_margin=0.20)
    claim = EvidenceClaim(
        claim_id="ced_beats",
        kind=EvidenceClaimKind.SYSTEM_BEATS_BASELINE,
        target_system_id="ced",
        baseline_system_id="baseline",
        statement="CED beats baseline.",
        policy=policy,
    )
    result = evaluate_evidence_claim(claim, _report(ced_correct=9, baseline_correct=8))
    assert result.verdict == EvidenceClaimVerdict.NOT_SUPPORTED
    assert any("accuracy_margin" in reason for reason in result.reasons)


def test_claim_is_insufficient_when_sample_too_small():
    policy = EvidenceClaimPolicy(min_task_count=10, min_coverage=0.8)
    claim = EvidenceClaim(
        claim_id="ced_threshold",
        kind=EvidenceClaimKind.SYSTEM_MEETS_THRESHOLD,
        target_system_id="ced",
        statement="CED meets threshold.",
        policy=policy,
    )
    result = evaluate_evidence_claim(claim, _report(ced_correct=2, baseline_correct=1, count=3))
    assert result.verdict == EvidenceClaimVerdict.INSUFFICIENT
    assert any("task_count" in reason for reason in result.reasons)


def test_system_meets_threshold_supported_and_not_supported():
    policy = EvidenceClaimPolicy.small_sample()
    policy.min_accuracy = 0.7
    policy.min_score_ratio = 0.7
    supported_claim = EvidenceClaim(
        claim_id="threshold_good",
        kind=EvidenceClaimKind.SYSTEM_MEETS_THRESHOLD,
        target_system_id="ced",
        statement="CED passes threshold.",
        policy=policy,
    )
    not_supported_claim = EvidenceClaim(
        claim_id="threshold_bad",
        kind=EvidenceClaimKind.SYSTEM_MEETS_THRESHOLD,
        target_system_id="baseline",
        statement="Baseline passes threshold.",
        policy=policy,
    )
    report = _report(ced_correct=10, baseline_correct=5, count=12)
    assert evaluate_evidence_claim(supported_claim, report).verdict == EvidenceClaimVerdict.SUPPORTED
    assert evaluate_evidence_claim(not_supported_claim, report).verdict == EvidenceClaimVerdict.NOT_SUPPORTED


def test_coverage_claim_detects_missing_answers():
    tasks = _tasks(4)
    outputs = [CandidateSystemOutput(system_id="ced", task_id="t0", answer="yes")]
    report = run_evidence_harness(tasks, outputs)
    claim = EvidenceClaim(
        claim_id="coverage",
        kind=EvidenceClaimKind.SYSTEM_HAS_COVERAGE,
        target_system_id="ced",
        statement="CED has coverage.",
        policy=EvidenceClaimPolicy(min_task_count=1, min_coverage=0.8),
    )
    result = evaluate_evidence_claim(claim, report)
    assert result.verdict == EvidenceClaimVerdict.NOT_SUPPORTED
    assert result.metrics["coverage"] == 0.25


def test_confidence_claim_supported_when_gap_is_large():
    policy = EvidenceClaimPolicy.small_sample()
    policy.min_confidence_gap = 0.1
    claim = EvidenceClaim(
        claim_id="confidence",
        kind=EvidenceClaimKind.CONFIDENCE_IS_USEFUL,
        target_system_id="ced",
        statement="Confidence separates pass/fail.",
        policy=policy,
    )
    result = evaluate_evidence_claim(claim, _report(ced_correct=10, baseline_correct=7, count=12))
    assert result.verdict == EvidenceClaimVerdict.SUPPORTED
    assert result.metrics["confidence_gap"] >= 0.1


def test_default_ced_vs_baseline_claims_and_gate_report():
    policy = EvidenceClaimPolicy.small_sample()
    claims = make_default_ced_vs_baseline_claims(policy=policy)
    report = _report()
    gate_report = run_evidence_claim_gates(claims, report)
    summary = evidence_claim_gate_summary(gate_report, report)
    assert gate_report.report_id.startswith("claim_gate_")
    assert gate_report.claim_count == 4
    assert summary["claim_count"] == 4
    assert "harness" in summary


def test_gate_report_serializes_to_json():
    policy = EvidenceClaimPolicy.small_sample()
    gate_report = run_evidence_claim_gates(make_default_ced_vs_baseline_claims(policy=policy), _report())
    text = gate_report.to_json()
    assert "claim_gate_" in text

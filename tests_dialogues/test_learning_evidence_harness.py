"""
Phase 26R — Evidence Harness tests.

The harness compares candidate systems against the same ground-truth task set.
It is deterministic and side-effect free.
"""

from backend.dialogues.learning_evidence_harness import (
    CandidateSystemKind,
    CandidateSystemOutput,
    build_leaderboard,
    evaluate_system,
    evidence_hash,
    evidence_harness_summary,
    run_evidence_harness,
)
from backend.dialogues.learning_ground_truth_checks import (
    GroundTruthTask,
    GroundTruthTaskKind,
)


def _tasks():
    return [
        GroundTruthTask(task_id="t1", kind=GroundTruthTaskKind.EXACT_TEXT, prompt="Capital of Greece?", gold_answer="Athens"),
        GroundTruthTask(task_id="t2", kind=GroundTruthTaskKind.NUMERIC_EXACT, prompt="2+2", numeric_answer=4.0),
        GroundTruthTask(task_id="t3", kind=GroundTruthTaskKind.CODE_CHECK_RECORD, prompt="Recorded tests pass?"),
    ]


def _outputs():
    return [
        CandidateSystemOutput(system_id="ced", system_kind=CandidateSystemKind.CED, task_id="t1", answer="Athens", confidence=0.9),
        CandidateSystemOutput(system_id="ced", system_kind=CandidateSystemKind.CED, task_id="t2", answer="4", confidence=0.8),
        CandidateSystemOutput(system_id="ced", system_kind=CandidateSystemKind.CED, task_id="t3", answer="code", confidence=0.7, recorded_code_passed=True),
        CandidateSystemOutput(system_id="base", system_kind=CandidateSystemKind.BASELINE, task_id="t1", answer="Rome", confidence=0.95),
        CandidateSystemOutput(system_id="base", system_kind=CandidateSystemKind.BASELINE, task_id="t2", answer="4", confidence=0.6),
        CandidateSystemOutput(system_id="base", system_kind=CandidateSystemKind.BASELINE, task_id="t3", answer="code", confidence=0.5, recorded_code_passed=False),
    ]


def test_evidence_hash_is_deterministic():
    assert evidence_hash({"a": 1, "b": 2}) == evidence_hash({"b": 2, "a": 1})
    assert evidence_hash({"a": 1}) != evidence_hash({"a": 2})


def test_candidate_system_output_converts_to_ground_truth_candidate():
    output = CandidateSystemOutput(system_id="ced", system_kind=CandidateSystemKind.CED, task_id="t1", answer="Athens", confidence=0.9)
    candidate = output.as_candidate_output()
    assert candidate.task_id == "t1"
    assert candidate.answer == "Athens"
    assert candidate.metadata["system_id"] == "ced"
    assert candidate.metadata["confidence"] == 0.9


def test_evaluate_system_reports_accuracy_coverage_and_confidence():
    result = evaluate_system(_tasks(), _outputs(), system_id="ced", system_kind=CandidateSystemKind.CED)
    assert result.system_id == "ced"
    assert result.report.accuracy == 1.0
    assert result.coverage == 1.0
    assert result.score_ratio == 1.0
    assert result.confidence_mean is not None
    assert result.confidence_on_pass is not None
    assert result.confidence_on_fail is None


def test_run_evidence_harness_builds_leaderboard():
    report = run_evidence_harness(_tasks(), _outputs())
    summary = evidence_harness_summary(report)
    assert report.harness_id.startswith("evidence_")
    assert report.best_system_id == "ced"
    assert report.leaderboard[0].system_id == "ced"
    assert report.leaderboard[0].accuracy == 1.0
    assert summary["best_system_id"] == "ced"
    assert "ced" in summary["system_summaries"]


def test_missing_answers_reduce_coverage_and_create_unscored_results():
    outputs = [CandidateSystemOutput(system_id="partial", task_id="t1", answer="Athens")]
    result = evaluate_system(_tasks(), outputs, system_id="partial")
    assert result.coverage == 1 / 3
    assert result.report.unscored_count == 2


def test_leaderboard_tiebreaks_by_accuracy_score_coverage_then_id():
    tasks = _tasks()[:2]
    outputs = [
        CandidateSystemOutput(system_id="a", task_id="t1", answer="Athens"),
        CandidateSystemOutput(system_id="b", task_id="t1", answer="Athens"),
        CandidateSystemOutput(system_id="b", task_id="t2", answer="4"),
    ]
    a = evaluate_system(tasks, outputs, system_id="a")
    b = evaluate_system(tasks, outputs, system_id="b")
    leaderboard = build_leaderboard([a, b])
    assert leaderboard[0].system_id == "b"
    assert leaderboard[0].coverage == 1.0


def test_confidence_gap_positive_when_correct_answers_are_more_confident():
    tasks = _tasks()[:2]
    outputs = [
        CandidateSystemOutput(system_id="sys", task_id="t1", answer="Athens", confidence=0.9),
        CandidateSystemOutput(system_id="sys", task_id="t2", answer="5", confidence=0.2),
    ]
    result = evaluate_system(tasks, outputs, system_id="sys")
    assert result.confidence_on_pass == 0.9
    assert result.confidence_on_fail == 0.2
    assert result.confidence_gap == 0.7


def test_report_serializes_to_json():
    report = run_evidence_harness(_tasks(), _outputs())
    text = report.to_json()
    assert "evidence_" in text
    assert "leaderboard" in text

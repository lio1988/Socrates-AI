"""
Phase 26Q — Ground Truth Checks tests.

These tests verify deterministic, non-model-based checks: exact text, numeric,
multiple choice, regex, recorded code-check outcomes, and human rubric scores.
"""

from backend.dialogues.learning_ground_truth_checks import (
    CandidateOutput,
    GroundTruthTask,
    GroundTruthTaskKind,
    GroundTruthVerdict,
    HumanRubricCriterion,
    HumanRubricScore,
    ground_truth_hash,
    ground_truth_summary,
    normalize_text,
    run_ground_truth_suite,
    score_ground_truth_task,
)


def test_ground_truth_hash_is_deterministic():
    assert ground_truth_hash({"a": 1, "b": 2}) == ground_truth_hash({"b": 2, "a": 1})
    assert ground_truth_hash({"a": 1}) != ground_truth_hash({"a": 2})


def test_normalize_text_lowercases_and_collapses_spaces():
    assert normalize_text("  Hello   WORLD  ") == "hello world"


def test_exact_text_passes_and_fails():
    task = GroundTruthTask(task_id="t1", kind=GroundTruthTaskKind.EXACT_TEXT, prompt="Capital?", gold_answer="Athens")
    assert score_ground_truth_task(task, CandidateOutput(task_id="t1", answer=" athens ")).verdict == GroundTruthVerdict.PASS
    assert score_ground_truth_task(task, CandidateOutput(task_id="t1", answer="Rome")).verdict == GroundTruthVerdict.FAIL


def test_numeric_exact_uses_tolerance():
    task = GroundTruthTask(task_id="m1", kind=GroundTruthTaskKind.NUMERIC_EXACT, prompt="2+2", numeric_answer=4.0, numeric_tolerance=0.01)
    passed = score_ground_truth_task(task, CandidateOutput(task_id="m1", answer="4.005"))
    failed = score_ground_truth_task(task, CandidateOutput(task_id="m1", answer="4.2"))
    assert passed.verdict == GroundTruthVerdict.PASS
    assert failed.verdict == GroundTruthVerdict.FAIL


def test_multiple_choice_requires_valid_expected_choice():
    task = GroundTruthTask(
        task_id="mc1",
        kind=GroundTruthTaskKind.MULTIPLE_CHOICE,
        prompt="Pick one",
        gold_answer="B",
        choices=["A", "B", "C"],
    )
    assert score_ground_truth_task(task, CandidateOutput(task_id="mc1", answer="b")).verdict == GroundTruthVerdict.PASS
    assert score_ground_truth_task(task, CandidateOutput(task_id="mc1", answer="c")).verdict == GroundTruthVerdict.FAIL


def test_regex_match():
    task = GroundTruthTask(task_id="r1", kind=GroundTruthTaskKind.REGEX_MATCH, prompt="Mention Athens", regex_pattern=r"\bAthens\b")
    assert score_ground_truth_task(task, CandidateOutput(task_id="r1", answer="The answer is Athens.")).verdict == GroundTruthVerdict.PASS
    assert score_ground_truth_task(task, CandidateOutput(task_id="r1", answer="The answer is Rome.")).verdict == GroundTruthVerdict.FAIL


def test_code_check_record_never_executes_code_and_uses_recorded_outcome():
    task = GroundTruthTask(task_id="code1", kind=GroundTruthTaskKind.CODE_CHECK_RECORD, prompt="Function should pass tests")
    unscored = score_ground_truth_task(task, CandidateOutput(task_id="code1", answer="def f(): pass"))
    passed = score_ground_truth_task(task, CandidateOutput(task_id="code1", answer="def f(): pass", recorded_code_passed=True))
    failed = score_ground_truth_task(task, CandidateOutput(task_id="code1", answer="def f(): pass", recorded_code_passed=False))
    assert unscored.verdict == GroundTruthVerdict.UNSCORED
    assert passed.verdict == GroundTruthVerdict.PASS
    assert failed.verdict == GroundTruthVerdict.FAIL


def test_human_rubric_needs_human_without_scores_then_scores_when_present():
    task = GroundTruthTask(
        task_id="h1",
        kind=GroundTruthTaskKind.HUMAN_RUBRIC,
        prompt="Essay",
        rubric=[HumanRubricCriterion(name="clarity", description="Clear answer", max_score=2.0)],
    )
    needs = score_ground_truth_task(task, CandidateOutput(task_id="h1", answer="Essay text"))
    scored = score_ground_truth_task(
        task,
        CandidateOutput(task_id="h1", answer="Essay text", human_scores=[HumanRubricScore(criterion="clarity", score=2.0, max_score=2.0)]),
    )
    assert needs.verdict == GroundTruthVerdict.NEEDS_HUMAN
    assert scored.verdict == GroundTruthVerdict.PASS
    assert scored.score == 2.0


def test_task_id_mismatch_fails():
    task = GroundTruthTask(task_id="x", kind=GroundTruthTaskKind.EXACT_TEXT, prompt="", gold_answer="yes")
    result = score_ground_truth_task(task, CandidateOutput(task_id="y", answer="yes"))
    assert result.verdict == GroundTruthVerdict.FAIL
    assert "does not match" in result.explanation


def test_run_ground_truth_suite_aggregates_results():
    tasks = [
        GroundTruthTask(task_id="a", kind=GroundTruthTaskKind.EXACT_TEXT, prompt="", gold_answer="yes"),
        GroundTruthTask(task_id="b", kind=GroundTruthTaskKind.NUMERIC_EXACT, prompt="", numeric_answer=10.0, numeric_tolerance=0.0),
        GroundTruthTask(task_id="c", kind=GroundTruthTaskKind.HUMAN_RUBRIC, prompt="", rubric=[]),
    ]
    candidates = [
        CandidateOutput(task_id="a", answer="yes"),
        CandidateOutput(task_id="b", answer="11"),
    ]
    report = run_ground_truth_suite(tasks, candidates)
    summary = ground_truth_summary(report)
    assert report.report_id.startswith("gt_report_")
    assert report.pass_count == 1
    assert report.fail_count == 1
    assert report.unscored_count == 1
    assert summary["accuracy"] == 0.5
    assert "b" in summary["failed_tasks"]
    assert "c" in summary["unscored_tasks"]


def test_report_serializes_to_json():
    report = run_ground_truth_suite([], [])
    text = report.to_json()
    assert "gt_report_" in text

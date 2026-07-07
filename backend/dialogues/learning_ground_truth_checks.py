"""
Phase 26Q — Ground Truth Checks.

This module adds deterministic checks that sit outside model self-judgment:
exact answers, numeric checks, multiple choice, recorded code-check outcomes,
and human rubric placeholders.

It is side-effect free: no provider calls, no file writes, no code execution.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import sanitize_public_payload


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def ground_truth_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


class GroundTruthTaskKind(str, Enum):
    EXACT_TEXT = "exact_text"
    NUMERIC_EXACT = "numeric_exact"
    MULTIPLE_CHOICE = "multiple_choice"
    REGEX_MATCH = "regex_match"
    CODE_CHECK_RECORD = "code_check_record"
    HUMAN_RUBRIC = "human_rubric"


class GroundTruthVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_HUMAN = "needs_human"
    UNSCORED = "unscored"


class HumanRubricCriterion(BaseModel):
    name: str
    description: str
    max_score: float = 1.0


class HumanRubricScore(BaseModel):
    criterion: str
    score: float
    max_score: float = 1.0
    notes: str = ""


class GroundTruthTask(BaseModel):
    task_id: str
    kind: GroundTruthTaskKind
    prompt: str
    gold_answer: Optional[str] = None
    numeric_answer: Optional[float] = None
    numeric_tolerance: float = 0.0
    choices: List[str] = Field(default_factory=list)
    regex_pattern: Optional[str] = None
    rubric: List[HumanRubricCriterion] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CandidateOutput(BaseModel):
    task_id: str
    answer: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recorded_code_passed: Optional[bool] = None
    human_scores: List[HumanRubricScore] = Field(default_factory=list)


class GroundTruthResult(BaseModel):
    task_id: str
    kind: GroundTruthTaskKind
    verdict: GroundTruthVerdict
    score: float = 0.0
    max_score: float = 1.0
    explanation: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkReport(BaseModel):
    report_id: str
    result_count: int
    pass_count: int
    fail_count: int
    needs_human_count: int
    unscored_count: int
    total_score: float
    max_score: float
    accuracy: float
    results: List[GroundTruthResult] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _as_float(text: str) -> Optional[float]:
    try:
        return float(text.strip())
    except (TypeError, ValueError):
        return None


def score_exact_text(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    expected = normalize_text(task.gold_answer or "")
    actual = normalize_text(candidate.answer)
    passed = expected == actual and expected != ""
    return GroundTruthResult(
        task_id=task.task_id,
        kind=task.kind,
        verdict=GroundTruthVerdict.PASS if passed else GroundTruthVerdict.FAIL,
        score=1.0 if passed else 0.0,
        explanation="Exact text matched." if passed else "Exact text did not match.",
        evidence={"expected": expected, "actual": actual},
    )


def score_numeric_exact(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    actual = _as_float(candidate.answer)
    expected = task.numeric_answer
    if actual is None or expected is None:
        return GroundTruthResult(
            task_id=task.task_id,
            kind=task.kind,
            verdict=GroundTruthVerdict.FAIL,
            explanation="Numeric answer could not be parsed or expected value is missing.",
            evidence={"expected": expected, "actual": candidate.answer},
        )
    diff = abs(actual - expected)
    passed = diff <= task.numeric_tolerance
    return GroundTruthResult(
        task_id=task.task_id,
        kind=task.kind,
        verdict=GroundTruthVerdict.PASS if passed else GroundTruthVerdict.FAIL,
        score=1.0 if passed else 0.0,
        explanation="Numeric answer within tolerance." if passed else "Numeric answer outside tolerance.",
        evidence={"expected": expected, "actual": actual, "difference": diff, "tolerance": task.numeric_tolerance},
    )


def score_multiple_choice(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    expected = normalize_text(task.gold_answer or "")
    actual = normalize_text(candidate.answer)
    valid = {normalize_text(choice) for choice in task.choices}
    passed = actual == expected and actual in valid
    return GroundTruthResult(
        task_id=task.task_id,
        kind=task.kind,
        verdict=GroundTruthVerdict.PASS if passed else GroundTruthVerdict.FAIL,
        score=1.0 if passed else 0.0,
        explanation="Multiple-choice answer matched." if passed else "Multiple-choice answer did not match.",
        evidence={"expected": expected, "actual": actual, "choices": sorted(valid)},
    )


def score_regex_match(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    pattern = task.regex_pattern or ""
    matched = bool(pattern and re.search(pattern, candidate.answer, flags=re.IGNORECASE | re.MULTILINE))
    return GroundTruthResult(
        task_id=task.task_id,
        kind=task.kind,
        verdict=GroundTruthVerdict.PASS if matched else GroundTruthVerdict.FAIL,
        score=1.0 if matched else 0.0,
        explanation="Regex matched." if matched else "Regex did not match.",
        evidence={"pattern": pattern, "answer": candidate.answer},
    )


def score_code_check_record(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    if candidate.recorded_code_passed is None:
        return GroundTruthResult(
            task_id=task.task_id,
            kind=task.kind,
            verdict=GroundTruthVerdict.UNSCORED,
            explanation="No recorded code-check outcome was supplied.",
            evidence={"recorded_code_passed": None},
        )
    return GroundTruthResult(
        task_id=task.task_id,
        kind=task.kind,
        verdict=GroundTruthVerdict.PASS if candidate.recorded_code_passed else GroundTruthVerdict.FAIL,
        score=1.0 if candidate.recorded_code_passed else 0.0,
        explanation="Recorded code-check passed." if candidate.recorded_code_passed else "Recorded code-check failed.",
        evidence={"recorded_code_passed": candidate.recorded_code_passed},
    )


def score_human_rubric(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    if not candidate.human_scores:
        return GroundTruthResult(
            task_id=task.task_id,
            kind=task.kind,
            verdict=GroundTruthVerdict.NEEDS_HUMAN,
            explanation="Human rubric task requires supplied human scores.",
            evidence={"criteria": [c.model_dump(mode="json") for c in task.rubric]},
        )
    total = sum(max(0.0, score.score) for score in candidate.human_scores)
    maximum = sum(max(0.0, score.max_score) for score in candidate.human_scores) or 1.0
    ratio = max(0.0, min(1.0, total / maximum))
    return GroundTruthResult(
        task_id=task.task_id,
        kind=task.kind,
        verdict=GroundTruthVerdict.PASS if ratio >= 0.7 else GroundTruthVerdict.FAIL,
        score=total,
        max_score=maximum,
        explanation="Human rubric scores supplied.",
        evidence={"scores": [s.model_dump(mode="json") for s in candidate.human_scores], "ratio": ratio},
    )


SCORERS = {
    GroundTruthTaskKind.EXACT_TEXT: score_exact_text,
    GroundTruthTaskKind.NUMERIC_EXACT: score_numeric_exact,
    GroundTruthTaskKind.MULTIPLE_CHOICE: score_multiple_choice,
    GroundTruthTaskKind.REGEX_MATCH: score_regex_match,
    GroundTruthTaskKind.CODE_CHECK_RECORD: score_code_check_record,
    GroundTruthTaskKind.HUMAN_RUBRIC: score_human_rubric,
}


def score_ground_truth_task(task: GroundTruthTask, candidate: CandidateOutput) -> GroundTruthResult:
    if task.task_id != candidate.task_id:
        return GroundTruthResult(
            task_id=task.task_id,
            kind=task.kind,
            verdict=GroundTruthVerdict.FAIL,
            explanation="Candidate task_id does not match ground-truth task_id.",
            evidence={"task_id": task.task_id, "candidate_task_id": candidate.task_id},
        )
    return SCORERS[task.kind](task, candidate)


def run_ground_truth_suite(tasks: List[GroundTruthTask], candidates: List[CandidateOutput]) -> BenchmarkReport:
    candidate_by_id = {candidate.task_id: candidate for candidate in candidates}
    results: List[GroundTruthResult] = []
    for task in sorted(tasks, key=lambda t: t.task_id):
        candidate = candidate_by_id.get(task.task_id)
        if not candidate:
            results.append(GroundTruthResult(
                task_id=task.task_id,
                kind=task.kind,
                verdict=GroundTruthVerdict.UNSCORED,
                explanation="No candidate output was supplied for this task.",
            ))
        else:
            results.append(score_ground_truth_task(task, candidate))

    pass_count = sum(1 for r in results if r.verdict == GroundTruthVerdict.PASS)
    fail_count = sum(1 for r in results if r.verdict == GroundTruthVerdict.FAIL)
    needs_human_count = sum(1 for r in results if r.verdict == GroundTruthVerdict.NEEDS_HUMAN)
    unscored_count = sum(1 for r in results if r.verdict == GroundTruthVerdict.UNSCORED)
    total_score = sum(r.score for r in results)
    max_score = sum(r.max_score for r in results) or 1.0
    scored_count = pass_count + fail_count
    accuracy = pass_count / scored_count if scored_count else 0.0
    payload = {
        "results": [r.model_dump(mode="json") for r in results],
        "pass_count": pass_count,
        "fail_count": fail_count,
        "needs_human_count": needs_human_count,
        "unscored_count": unscored_count,
        "total_score": total_score,
        "max_score": max_score,
        "accuracy": accuracy,
    }
    report = BenchmarkReport(
        report_id=ground_truth_hash(payload, prefix="gt_report_"),
        result_count=len(results),
        pass_count=pass_count,
        fail_count=fail_count,
        needs_human_count=needs_human_count,
        unscored_count=unscored_count,
        total_score=total_score,
        max_score=max_score,
        accuracy=accuracy,
        results=results,
    )
    report.summary = ground_truth_summary(report)
    return report


def ground_truth_summary(report: BenchmarkReport) -> Dict[str, Any]:
    return sanitize_public_payload({
        "report_id": report.report_id,
        "result_count": report.result_count,
        "pass_count": report.pass_count,
        "fail_count": report.fail_count,
        "needs_human_count": report.needs_human_count,
        "unscored_count": report.unscored_count,
        "accuracy": report.accuracy,
        "score_ratio": report.total_score / report.max_score if report.max_score else 0.0,
        "failed_tasks": [r.task_id for r in report.results if r.verdict == GroundTruthVerdict.FAIL],
        "needs_human_tasks": [r.task_id for r in report.results if r.verdict == GroundTruthVerdict.NEEDS_HUMAN],
        "unscored_tasks": [r.task_id for r in report.results if r.verdict == GroundTruthVerdict.UNSCORED],
    })

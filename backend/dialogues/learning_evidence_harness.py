"""
Phase 26R — Evidence Harness.

This module compares candidate systems against the same ground-truth task set.
It is deterministic and side-effect free: no provider calls, no file writes, and
no code execution.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import sanitize_public_payload
from .learning_ground_truth_checks import (
    BenchmarkReport,
    CandidateOutput,
    GroundTruthResult,
    GroundTruthTask,
    GroundTruthVerdict,
    HumanRubricScore,
    ground_truth_summary,
    run_ground_truth_suite,
)


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def evidence_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


class CandidateSystemKind(str, Enum):
    CED = "ced"
    BASELINE = "baseline"
    SINGLE_MODEL = "single_model"
    HUMAN = "human"
    OTHER = "other"


class CandidateSystemOutput(BaseModel):
    system_id: str
    system_kind: CandidateSystemKind = CandidateSystemKind.OTHER
    task_id: str
    answer: str
    confidence: Optional[float] = None
    recorded_code_passed: Optional[bool] = None
    human_scores: List[HumanRubricScore] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def as_candidate_output(self) -> CandidateOutput:
        return CandidateOutput(
            task_id=self.task_id,
            answer=self.answer,
            metadata=sanitize_public_payload({
                "system_id": self.system_id,
                "system_kind": self.system_kind.value,
                "confidence": self.confidence,
                **self.metadata,
            }),
            recorded_code_passed=self.recorded_code_passed,
            human_scores=self.human_scores,
        )


class SystemEvidenceResult(BaseModel):
    system_id: str
    system_kind: CandidateSystemKind
    report: BenchmarkReport
    task_count: int
    answered_count: int
    coverage: float
    score_ratio: float
    confidence_mean: Optional[float] = None
    confidence_on_pass: Optional[float] = None
    confidence_on_fail: Optional[float] = None
    confidence_gap: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceLeaderboardRow(BaseModel):
    rank: int
    system_id: str
    system_kind: str
    accuracy: float
    score_ratio: float
    coverage: float
    pass_count: int
    fail_count: int
    needs_human_count: int
    unscored_count: int


class EvidenceHarnessReport(BaseModel):
    harness_id: str
    task_count: int
    system_count: int
    systems: List[SystemEvidenceResult] = Field(default_factory=list)
    leaderboard: List[EvidenceLeaderboardRow] = Field(default_factory=list)
    best_system_id: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _confidence_stats(outputs: List[CandidateSystemOutput], results: List[GroundTruthResult]) -> Dict[str, Optional[float]]:
    confidence_by_task = {out.task_id: out.confidence for out in outputs if out.confidence is not None}
    all_conf = [float(c) for c in confidence_by_task.values()]
    pass_conf: List[float] = []
    fail_conf: List[float] = []
    for result in results:
        conf = confidence_by_task.get(result.task_id)
        if conf is None:
            continue
        if result.verdict == GroundTruthVerdict.PASS:
            pass_conf.append(float(conf))
        elif result.verdict == GroundTruthVerdict.FAIL:
            fail_conf.append(float(conf))
    pass_mean = _mean(pass_conf)
    fail_mean = _mean(fail_conf)
    return {
        "confidence_mean": _mean(all_conf),
        "confidence_on_pass": pass_mean,
        "confidence_on_fail": fail_mean,
        "confidence_gap": None if pass_mean is None or fail_mean is None else pass_mean - fail_mean,
    }


def evaluate_system(
    tasks: List[GroundTruthTask],
    outputs: List[CandidateSystemOutput],
    *,
    system_id: str,
    system_kind: CandidateSystemKind = CandidateSystemKind.OTHER,
    metadata: Optional[Dict[str, Any]] = None,
) -> SystemEvidenceResult:
    selected = [out for out in outputs if out.system_id == system_id]
    report = run_ground_truth_suite(tasks, [out.as_candidate_output() for out in selected])
    answered_ids = {out.task_id for out in selected}
    task_ids = {task.task_id for task in tasks}
    answered_count = len(answered_ids & task_ids)
    coverage = answered_count / len(task_ids) if task_ids else 0.0
    score_ratio = report.total_score / report.max_score if report.max_score else 0.0
    stats = _confidence_stats(selected, report.results)
    return SystemEvidenceResult(
        system_id=system_id,
        system_kind=system_kind,
        report=report,
        task_count=len(tasks),
        answered_count=answered_count,
        coverage=coverage,
        score_ratio=score_ratio,
        confidence_mean=stats["confidence_mean"],
        confidence_on_pass=stats["confidence_on_pass"],
        confidence_on_fail=stats["confidence_on_fail"],
        confidence_gap=stats["confidence_gap"],
        metadata=sanitize_public_payload(metadata or {}),
    )


def build_leaderboard(systems: List[SystemEvidenceResult]) -> List[EvidenceLeaderboardRow]:
    ordered = sorted(
        systems,
        key=lambda item: (
            -item.report.accuracy,
            -item.score_ratio,
            -item.coverage,
            item.system_id,
        ),
    )
    return [
        EvidenceLeaderboardRow(
            rank=index + 1,
            system_id=system.system_id,
            system_kind=system.system_kind.value,
            accuracy=system.report.accuracy,
            score_ratio=system.score_ratio,
            coverage=system.coverage,
            pass_count=system.report.pass_count,
            fail_count=system.report.fail_count,
            needs_human_count=system.report.needs_human_count,
            unscored_count=system.report.unscored_count,
        )
        for index, system in enumerate(ordered)
    ]


def run_evidence_harness(
    tasks: List[GroundTruthTask],
    outputs: List[CandidateSystemOutput],
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> EvidenceHarnessReport:
    systems_seen: Dict[str, CandidateSystemKind] = {}
    for output in outputs:
        systems_seen.setdefault(output.system_id, output.system_kind)
    system_results = [
        evaluate_system(tasks, outputs, system_id=system_id, system_kind=kind, metadata=metadata)
        for system_id, kind in sorted(systems_seen.items())
    ]
    leaderboard = build_leaderboard(system_results)
    payload = {
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "systems": [system.model_dump(mode="json") for system in system_results],
        "leaderboard": [row.model_dump(mode="json") for row in leaderboard],
        "metadata": sanitize_public_payload(metadata or {}),
    }
    report = EvidenceHarnessReport(
        harness_id=evidence_hash(payload, prefix="evidence_"),
        task_count=len(tasks),
        system_count=len(system_results),
        systems=system_results,
        leaderboard=leaderboard,
        best_system_id=leaderboard[0].system_id if leaderboard else None,
    )
    report.summary = evidence_harness_summary(report)
    return report


def evidence_harness_summary(report: EvidenceHarnessReport) -> Dict[str, Any]:
    return sanitize_public_payload({
        "harness_id": report.harness_id,
        "task_count": report.task_count,
        "system_count": report.system_count,
        "best_system_id": report.best_system_id,
        "leaderboard": [row.model_dump(mode="json") for row in report.leaderboard],
        "system_summaries": {
            system.system_id: {
                "system_kind": system.system_kind.value,
                "coverage": system.coverage,
                "score_ratio": system.score_ratio,
                "confidence_mean": system.confidence_mean,
                "confidence_gap": system.confidence_gap,
                "ground_truth": ground_truth_summary(system.report),
            }
            for system in report.systems
        },
    })

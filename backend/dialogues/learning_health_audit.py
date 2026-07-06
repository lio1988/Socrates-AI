"""
Phase 26L — Learning Health Audit.

This module turns a LearningPipelineResult into a compact PASS/WARN/FAIL dashboard
for humans. It is a diagnostic layer over the parallel learning stack.

It does not call providers, train models, write files, mutate CED state, or modify
CED core behavior.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_foundation import sanitize_public_payload
from .learning_pipeline import LearningPipelineResult
from .learning_quality_gates import QualityVerdict
from .learning_training_planner import TrainingReadiness


class HealthStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class LearningStage(str, Enum):
    COLLECTOR = "collector"
    PREFERENCE_MINER = "preference_miner"
    PROCESS_MINER = "process_miner"
    EXPORT_PACK = "export_pack"
    QUALITY_GATES = "quality_gates"
    DRY_RUN_PLANNER = "dry_run_planner"
    SAFETY_INVARIANTS = "safety_invariants"


class LearningHealthPolicy(BaseModel):
    min_traces: int = 1
    min_export_artifacts: int = 1
    min_total_export_records: int = 1
    min_ready_or_inspect_jobs: int = 1
    require_no_training_executed: bool = True
    warn_if_no_preferences: bool = True
    warn_if_no_process_examples: bool = True
    fail_on_quality_fail: bool = True

    @classmethod
    def strict(cls) -> "LearningHealthPolicy":
        return cls()

    @classmethod
    def exploratory(cls) -> "LearningHealthPolicy":
        return cls(
            warn_if_no_preferences=True,
            warn_if_no_process_examples=True,
            fail_on_quality_fail=True,
        )


class LearningStageHealth(BaseModel):
    stage: LearningStage
    status: HealthStatus
    message: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)


class LearningHealthAudit(BaseModel):
    audit_version: str = "phase_26l"
    overall_status: HealthStatus
    stages: List[LearningStageHealth] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


def _stage(status: HealthStatus, stage: LearningStage, message: str, *, metrics: Optional[Dict[str, Any]] = None,
           recommendations: Optional[List[str]] = None) -> LearningStageHealth:
    return LearningStageHealth(
        stage=stage,
        status=status,
        message=message,
        metrics=sanitize_public_payload(metrics or {}),
        recommendations=recommendations or [],
    )


def _status_from_counts(count: int, minimum: int, warn_message: str, fail_message: str) -> HealthStatus:
    if count < minimum:
        return HealthStatus.FAIL
    if count == 0:
        return HealthStatus.WARN
    return HealthStatus.PASS


def audit_learning_pipeline_result(
    result: LearningPipelineResult,
    *,
    policy: Optional[LearningHealthPolicy] = None,
) -> LearningHealthAudit:
    policy = policy or LearningHealthPolicy.strict()
    stages: List[LearningStageHealth] = []

    trace_count = len(result.dataset.traces)
    eligible_count = len(result.dataset.eligible_traces())
    if trace_count < policy.min_traces:
        stages.append(_stage(
            HealthStatus.FAIL,
            LearningStage.COLLECTOR,
            f"collector produced {trace_count} traces; minimum is {policy.min_traces}",
            metrics={"trace_count": trace_count, "eligible_trace_count": eligible_count},
            recommendations=["Run CED sessions with valid provider moves before exporting learning data."],
        ))
    elif eligible_count == 0:
        stages.append(_stage(
            HealthStatus.WARN,
            LearningStage.COLLECTOR,
            "collector produced traces but none are training-eligible",
            metrics={"trace_count": trace_count, "eligible_trace_count": eligible_count},
            recommendations=["Inspect SocratesConstitution eligibility thresholds and provider statuses."],
        ))
    else:
        stages.append(_stage(
            HealthStatus.PASS,
            LearningStage.COLLECTOR,
            "collector produced usable traces",
            metrics={"trace_count": trace_count, "eligible_trace_count": eligible_count},
        ))

    pref_count = result.preference_report.preference_count
    pref_status = HealthStatus.PASS if pref_count else (HealthStatus.WARN if policy.warn_if_no_preferences else HealthStatus.PASS)
    stages.append(_stage(
        pref_status,
        LearningStage.PREFERENCE_MINER,
        "preference miner produced answer-level preferences" if pref_count else "preference miner produced no answer-level preferences",
        metrics={
            "preference_count": pref_count,
            "candidate_count": len(result.preference_report.candidates),
            "skipped_count": len(result.preference_report.skipped),
        },
        recommendations=[] if pref_count else ["Collect more competing valid provider moves or lower mining policy only for diagnostics."],
    ))

    process_count = result.process_report.sft_count + result.process_report.preference_count
    proc_status = HealthStatus.PASS if process_count else (HealthStatus.WARN if policy.warn_if_no_process_examples else HealthStatus.PASS)
    stages.append(_stage(
        proc_status,
        LearningStage.PROCESS_MINER,
        "process miner produced process-learning examples" if process_count else "process miner produced no process-learning examples",
        metrics={
            "transition_count": result.process_report.transition_count,
            "process_sft_count": result.process_report.sft_count,
            "process_preference_count": result.process_report.preference_count,
            "skipped_count": len(result.process_report.skipped),
        },
        recommendations=[] if process_count else ["Run sessions that include forward phase progression from initial answer to reconstruction/synthesis."],
    ))

    artifact_count = result.export_pack.manifest.artifact_count
    total_records = result.export_pack.manifest.total_records
    if artifact_count < policy.min_export_artifacts or total_records < policy.min_total_export_records:
        export_status = HealthStatus.FAIL
        export_msg = "export pack is missing required artifacts or records"
    else:
        export_status = HealthStatus.PASS
        export_msg = "export pack contains alignment artifacts"
    stages.append(_stage(
        export_status,
        LearningStage.EXPORT_PACK,
        export_msg,
        metrics={
            "artifact_count": artifact_count,
            "total_records": total_records,
            "counts": result.export_pack.manifest.counts,
            "warnings": result.export_pack.manifest.warnings,
        },
        recommendations=[] if export_status == HealthStatus.PASS else ["Check miner outputs and exporter warnings before training planning."],
    ))

    q_verdict = result.quality_report.verdict
    if q_verdict == QualityVerdict.FAIL and policy.fail_on_quality_fail:
        q_status = HealthStatus.FAIL
    elif q_verdict == QualityVerdict.WARN:
        q_status = HealthStatus.WARN
    else:
        q_status = HealthStatus.PASS
    stages.append(_stage(
        q_status,
        LearningStage.QUALITY_GATES,
        f"quality gates verdict is {q_verdict.value}",
        metrics={
            "error_count": result.quality_report.error_count,
            "warning_count": result.quality_report.warning_count,
            "total_records": result.quality_report.total_records,
        },
        recommendations=[] if q_status == HealthStatus.PASS else ["Resolve quality gate issues before any real trainer adapter is enabled."],
    ))

    ready_or_inspect = sum(
        1 for job in result.dry_run_plan.jobs
        if job.readiness in {TrainingReadiness.READY, TrainingReadiness.INSPECT_ONLY}
    )
    blocked = sum(1 for job in result.dry_run_plan.jobs if job.readiness == TrainingReadiness.BLOCKED)
    if ready_or_inspect < policy.min_ready_or_inspect_jobs:
        plan_status = HealthStatus.FAIL
        plan_msg = "dry-run planner found no usable training families"
    elif blocked:
        plan_status = HealthStatus.WARN
        plan_msg = "dry-run planner found some blocked training families"
    else:
        plan_status = HealthStatus.PASS
        plan_msg = "dry-run planner found usable training families"
    stages.append(_stage(
        plan_status,
        LearningStage.DRY_RUN_PLANNER,
        plan_msg,
        metrics={
            "global_readiness": result.dry_run_plan.global_readiness.value,
            "ready_or_inspect_jobs": ready_or_inspect,
            "blocked_jobs": blocked,
            "job_count": len(result.dry_run_plan.jobs),
        },
        recommendations=[] if plan_status != HealthStatus.FAIL else ["Add missing dataset formats or relax only exploratory thresholds."],
    ))

    no_training = bool(result.summary.get("no_training_executed", True))
    safety_status = HealthStatus.PASS if no_training or not policy.require_no_training_executed else HealthStatus.FAIL
    stages.append(_stage(
        safety_status,
        LearningStage.SAFETY_INVARIANTS,
        "pipeline confirms no training executed" if no_training else "pipeline did not confirm no_training_executed",
        metrics={"no_training_executed": no_training},
        recommendations=[] if safety_status == HealthStatus.PASS else ["Do not proceed until all learning pipeline outputs explicitly confirm dry-run behavior."],
    ))

    failures = [f"{s.stage.value}: {s.message}" for s in stages if s.status == HealthStatus.FAIL]
    warnings = [f"{s.stage.value}: {s.message}" for s in stages if s.status == HealthStatus.WARN]
    if failures:
        overall = HealthStatus.FAIL
    elif warnings:
        overall = HealthStatus.WARN
    else:
        overall = HealthStatus.PASS

    audit = LearningHealthAudit(
        overall_status=overall,
        stages=stages,
        warnings=warnings,
        failures=failures,
    )
    audit.summary = learning_health_summary(audit)
    return audit


def learning_health_summary(audit: LearningHealthAudit) -> Dict[str, Any]:
    return sanitize_public_payload({
        "audit_version": audit.audit_version,
        "overall_status": audit.overall_status.value,
        "stage_count": len(audit.stages),
        "pass_stages": [s.stage.value for s in audit.stages if s.status == HealthStatus.PASS],
        "warn_stages": [s.stage.value for s in audit.stages if s.status == HealthStatus.WARN],
        "fail_stages": [s.stage.value for s in audit.stages if s.status == HealthStatus.FAIL],
        "warnings": audit.warnings,
        "failures": audit.failures,
    })

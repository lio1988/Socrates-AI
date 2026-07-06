"""
Phase 26I — Training Dry-Run Planner.

This is a planning layer, not a trainer. It reads an AlignmentExportPack plus a
DatasetQualityReport and decides which future training families are ready,
blocked, or only suitable for inspection.

It never trains, fine-tunes, calls providers, writes files, or changes CED core.
The goal is to prevent accidental "train on whatever we have" behavior.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_alignment_exporter import AlignmentExportPack, AlignmentFormat
from .learning_foundation import sanitize_public_payload
from .learning_quality_gates import DatasetQualityReport, QualityVerdict


class TrainingFamily(str, Enum):
    TRACE_SFT = "trace_sft"
    DPO = "dpo"
    NEMO_DPO = "nemo_dpo"
    REWARD_MODEL = "reward_model"
    PROCESS_SFT = "process_sft"
    PROCESS_REWARD = "process_reward"


class TrainingReadiness(str, Enum):
    READY = "ready"
    INSPECT_ONLY = "inspect_only"
    BLOCKED = "blocked"


class DryRunMode(str, Enum):
    NO_TRAINING = "no_training"
    COMMAND_PLAN_ONLY = "command_plan_only"


class TrainingPlannerPolicy(BaseModel):
    min_trace_sft_records: int = 1
    min_dpo_records: int = 1
    min_reward_pair_records: int = 1
    min_process_sft_records: int = 1
    allow_warn_quality_for_inspection: bool = True
    allow_warn_quality_for_training: bool = False
    default_model_family: str = "local_or_nemo_placeholder"
    default_epochs: int = 1
    default_learning_rate: str = "1e-5"
    dry_run_mode: DryRunMode = DryRunMode.NO_TRAINING

    @classmethod
    def conservative(cls) -> "TrainingPlannerPolicy":
        return cls()

    @classmethod
    def exploratory(cls) -> "TrainingPlannerPolicy":
        return cls(
            min_trace_sft_records=1,
            min_dpo_records=1,
            min_reward_pair_records=1,
            min_process_sft_records=1,
            allow_warn_quality_for_inspection=True,
            allow_warn_quality_for_training=False,
        )


class TrainingJobPlan(BaseModel):
    family: TrainingFamily
    readiness: TrainingReadiness
    record_count: int = 0
    required_records: int = 0
    artifact_names: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    dry_run_config: Dict[str, Any] = Field(default_factory=dict)
    command_preview: Optional[str] = None


class TrainingDryRunPlan(BaseModel):
    planner_version: str = "phase_26i"
    quality_verdict: str
    global_readiness: TrainingReadiness
    jobs: List[TrainingJobPlan] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


FAMILY_FORMATS: Dict[TrainingFamily, List[AlignmentFormat]] = {
    TrainingFamily.TRACE_SFT: [AlignmentFormat.TRACE_SFT],
    TrainingFamily.DPO: [AlignmentFormat.DPO],
    TrainingFamily.NEMO_DPO: [AlignmentFormat.NEMO_DPO],
    TrainingFamily.REWARD_MODEL: [AlignmentFormat.REWARD_PAIR],
    TrainingFamily.PROCESS_SFT: [AlignmentFormat.PROCESS_SFT],
    TrainingFamily.PROCESS_REWARD: [AlignmentFormat.REWARD_PAIR, AlignmentFormat.PROCESS_SFT],
}


REQUIRED_COUNTS = {
    TrainingFamily.TRACE_SFT: "min_trace_sft_records",
    TrainingFamily.DPO: "min_dpo_records",
    TrainingFamily.NEMO_DPO: "min_dpo_records",
    TrainingFamily.REWARD_MODEL: "min_reward_pair_records",
    TrainingFamily.PROCESS_SFT: "min_process_sft_records",
    TrainingFamily.PROCESS_REWARD: "min_process_sft_records",
}


def _artifact_names(pack: AlignmentExportPack, formats: List[AlignmentFormat]) -> List[str]:
    return [a.name for a in pack.artifacts if a.format in formats]


def _count_for_formats(pack: AlignmentExportPack, formats: List[AlignmentFormat]) -> int:
    return sum(a.record_count for a in pack.artifacts if a.format in formats)


def _quality_blocks_training(report: DatasetQualityReport, policy: TrainingPlannerPolicy) -> bool:
    if report.verdict == QualityVerdict.FAIL:
        return True
    if report.verdict == QualityVerdict.WARN and not policy.allow_warn_quality_for_training:
        return True
    return False


def _quality_allows_inspection(report: DatasetQualityReport, policy: TrainingPlannerPolicy) -> bool:
    if report.verdict == QualityVerdict.PASS:
        return True
    if report.verdict == QualityVerdict.WARN and policy.allow_warn_quality_for_inspection:
        return True
    return False


def _command_preview(family: TrainingFamily, artifact_names: List[str], config: Dict[str, Any]) -> str:
    # This is intentionally non-executable pseudo-command text. It prevents users
    # from accidentally launching training from a generated plan.
    artifact_list = ",".join(artifact_names) if artifact_names else "<missing-artifact>"
    return (
        f"DRY RUN ONLY: prepare {family.value} using [{artifact_list}] "
        f"with model_family={config.get('model_family')} epochs={config.get('epochs')} "
        f"lr={config.get('learning_rate')}"
    )


def plan_family(
    family: TrainingFamily,
    pack: AlignmentExportPack,
    quality_report: DatasetQualityReport,
    policy: TrainingPlannerPolicy,
) -> TrainingJobPlan:
    formats = FAMILY_FORMATS[family]
    count = _count_for_formats(pack, formats)
    names = _artifact_names(pack, formats)
    required = int(getattr(policy, REQUIRED_COUNTS[family]))
    reasons: List[str] = []

    if count < required:
        readiness = TrainingReadiness.BLOCKED
        reasons.append(f"record count {count} below required {required}")
    elif _quality_blocks_training(quality_report, policy):
        if _quality_allows_inspection(quality_report, policy):
            readiness = TrainingReadiness.INSPECT_ONLY
            reasons.append(f"quality verdict {quality_report.verdict.value}; training blocked but inspection allowed")
        else:
            readiness = TrainingReadiness.BLOCKED
            reasons.append(f"quality verdict {quality_report.verdict.value} blocks training")
    else:
        readiness = TrainingReadiness.READY
        reasons.append("quality gates and record counts allow dry-run planning")

    config = sanitize_public_payload({
        "dry_run": True,
        "mode": policy.dry_run_mode.value,
        "family": family.value,
        "model_family": policy.default_model_family,
        "epochs": policy.default_epochs,
        "learning_rate": policy.default_learning_rate,
        "artifacts": names,
        "record_count": count,
        "required_records": required,
        "no_training_executed": True,
    })

    return TrainingJobPlan(
        family=family,
        readiness=readiness,
        record_count=count,
        required_records=required,
        artifact_names=names,
        reasons=reasons,
        dry_run_config=config,
        command_preview=_command_preview(family, names, config),
    )


def build_training_dry_run_plan(
    pack: AlignmentExportPack,
    quality_report: DatasetQualityReport,
    *,
    policy: Optional[TrainingPlannerPolicy] = None,
    families: Optional[List[TrainingFamily]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TrainingDryRunPlan:
    policy = policy or TrainingPlannerPolicy.conservative()
    families = families or list(TrainingFamily)
    jobs = [plan_family(f, pack, quality_report, policy) for f in families]

    blocked_reasons: List[str] = []
    warnings: List[str] = []
    if quality_report.verdict == QualityVerdict.FAIL:
        blocked_reasons.append("quality report verdict is FAIL")
    elif quality_report.verdict == QualityVerdict.WARN:
        warnings.append("quality report verdict is WARN; training remains blocked by default")

    ready_count = sum(1 for j in jobs if j.readiness == TrainingReadiness.READY)
    inspect_count = sum(1 for j in jobs if j.readiness == TrainingReadiness.INSPECT_ONLY)
    if ready_count:
        global_readiness = TrainingReadiness.READY
    elif inspect_count:
        global_readiness = TrainingReadiness.INSPECT_ONLY
    else:
        global_readiness = TrainingReadiness.BLOCKED

    for job in jobs:
        if job.readiness == TrainingReadiness.BLOCKED:
            blocked_reasons.extend([f"{job.family.value}: {r}" for r in job.reasons])

    return TrainingDryRunPlan(
        quality_verdict=quality_report.verdict.value,
        global_readiness=global_readiness,
        jobs=jobs,
        blocked_reasons=blocked_reasons,
        warnings=warnings,
        metadata=sanitize_public_payload({
            "manifest_id": pack.manifest.manifest_id,
            "artifact_count": pack.manifest.artifact_count,
            "total_records": pack.manifest.total_records,
            "policy": policy.model_dump(mode="json"),
            **(metadata or {}),
        }),
    )


def dry_run_plan_summary(plan: TrainingDryRunPlan) -> Dict[str, Any]:
    return sanitize_public_payload({
        "quality_verdict": plan.quality_verdict,
        "global_readiness": plan.global_readiness.value,
        "job_count": len(plan.jobs),
        "ready_jobs": [j.family.value for j in plan.jobs if j.readiness == TrainingReadiness.READY],
        "inspect_only_jobs": [j.family.value for j in plan.jobs if j.readiness == TrainingReadiness.INSPECT_ONLY],
        "blocked_jobs": [j.family.value for j in plan.jobs if j.readiness == TrainingReadiness.BLOCKED],
        "blocked_reasons": plan.blocked_reasons[:20],
        "warnings": plan.warnings,
    })

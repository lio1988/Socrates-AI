"""
Phase 26K — End-to-End Learning Pipeline Runner.

This module is a stabilization layer, not a new training feature. It wires the
parallel learning stack together in one in-memory call:

  SessionState
    -> collect traces
    -> mine answer preferences
    -> mine process examples
    -> export alignment artifacts
    -> evaluate quality gates
    -> build dry-run training plan

It does not call providers, train models, write files, mutate CED state, or modify
CED core behavior.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .learning_alignment_exporter import AlignmentExportPack, alignment_export_summary, build_alignment_export_pack
from .learning_foundation import LearningDataset, SocratesConstitution, sanitize_public_payload
from .learning_preference_miner import (
    PreferenceMiningPolicy,
    PreferenceMiningReport,
    mine_preferences,
    smart_learning_summary,
)
from .learning_process_miner import (
    ProcessMiningPolicy,
    ProcessMiningReport,
    mine_process_examples,
    process_reward_summary,
)
from .learning_quality_gates import (
    DatasetQualityReport,
    QualityGatePolicy,
    evaluate_quality_gates,
    quality_gate_summary,
)
from .learning_trace_collector import collect_learning_dataset, learning_export_summary
from .learning_training_planner import (
    TrainingDryRunPlan,
    TrainingPlannerPolicy,
    build_training_dry_run_plan,
    dry_run_plan_summary,
)
from .models import SessionState
from .provider_registry import CouncilProviderRegistry


class LearningPipelinePolicy(BaseModel):
    """Policy bundle for the full offline learning pipeline."""

    preference_policy: str = "conservative"
    process_policy: str = "conservative"
    quality_policy: str = "strict"
    planner_policy: str = "conservative"
    validation_ratio: float = 0.10
    test_ratio: float = 0.0
    split_seed: str = "ced_alignment_v1"
    attach_preferences: bool = True
    attach_process_preferences: bool = True

    @classmethod
    def conservative(cls) -> "LearningPipelinePolicy":
        return cls()

    @classmethod
    def exploratory(cls) -> "LearningPipelinePolicy":
        return cls(
            preference_policy="balanced",
            process_policy="balanced",
            quality_policy="exploratory",
            planner_policy="exploratory",
            validation_ratio=0.0,
            test_ratio=0.0,
        )


class LearningPipelineResult(BaseModel):
    pipeline_version: str = "phase_26k"
    dataset: LearningDataset
    preference_report: PreferenceMiningReport
    process_report: ProcessMiningReport
    export_pack: AlignmentExportPack
    quality_report: DatasetQualityReport
    dry_run_plan: TrainingDryRunPlan
    summary: Dict[str, Any] = Field(default_factory=dict)

    def compact_summary(self) -> Dict[str, Any]:
        return sanitize_public_payload({
            "pipeline_version": self.pipeline_version,
            "learning": learning_export_summary(self.dataset),
            "preferences": smart_learning_summary(self.preference_report),
            "process": process_reward_summary(self.process_report),
            "export": alignment_export_summary(self.export_pack),
            "quality": quality_gate_summary(self.quality_report),
            "plan": dry_run_plan_summary(self.dry_run_plan),
            "no_training_executed": True,
        })


def _preference_policy(name: str) -> PreferenceMiningPolicy:
    if name == "conservative":
        return PreferenceMiningPolicy.conservative()
    if name == "balanced":
        return PreferenceMiningPolicy.balanced()
    if name == "aggressive":
        return PreferenceMiningPolicy.aggressive()
    raise ValueError(f"unknown preference policy: {name}")


def _process_policy(name: str) -> ProcessMiningPolicy:
    if name == "conservative":
        return ProcessMiningPolicy.conservative()
    if name == "balanced":
        return ProcessMiningPolicy.balanced()
    if name == "aggressive":
        return ProcessMiningPolicy.aggressive()
    raise ValueError(f"unknown process policy: {name}")


def _quality_policy(name: str) -> QualityGatePolicy:
    if name == "strict":
        return QualityGatePolicy.strict()
    if name == "exploratory":
        return QualityGatePolicy.exploratory()
    raise ValueError(f"unknown quality policy: {name}")


def _planner_policy(name: str) -> TrainingPlannerPolicy:
    if name == "conservative":
        return TrainingPlannerPolicy.conservative()
    if name == "exploratory":
        return TrainingPlannerPolicy.exploratory()
    raise ValueError(f"unknown planner policy: {name}")


def run_learning_pipeline_from_state(
    state: SessionState,
    *,
    registry: Optional[CouncilProviderRegistry] = None,
    constitution: Optional[SocratesConstitution] = None,
    policy: Optional[LearningPipelinePolicy] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningPipelineResult:
    """Run the complete offline learning pipeline from an existing SessionState."""
    policy = policy or LearningPipelinePolicy.conservative()

    dataset = collect_learning_dataset(
        state,
        registry=registry,
        constitution=constitution,
        include_scores=True,
        include_ratification=True,
        include_raw_text=False,
    )

    preference_report = mine_preferences(
        dataset,
        policy=_preference_policy(policy.preference_policy),
        attach=policy.attach_preferences,
    )
    process_report = mine_process_examples(
        dataset,
        policy=_process_policy(policy.process_policy),
        attach_preferences=policy.attach_process_preferences,
    )

    export_pack = build_alignment_export_pack(
        dataset,
        process_report=process_report,
        validation_ratio=policy.validation_ratio,
        test_ratio=policy.test_ratio,
        seed=policy.split_seed,
        metadata={
            "runner": "phase_26k_learning_pipeline",
            "session_id": state.session_id,
            **(metadata or {}),
        },
    )
    quality_report = evaluate_quality_gates(export_pack, policy=_quality_policy(policy.quality_policy))
    dry_run_plan = build_training_dry_run_plan(
        export_pack,
        quality_report,
        policy=_planner_policy(policy.planner_policy),
        metadata={
            "runner": "phase_26k_learning_pipeline",
            "session_id": state.session_id,
            **(metadata or {}),
        },
    )

    result = LearningPipelineResult(
        dataset=dataset,
        preference_report=preference_report,
        process_report=process_report,
        export_pack=export_pack,
        quality_report=quality_report,
        dry_run_plan=dry_run_plan,
    )
    result.summary = result.compact_summary()
    return result


def learning_pipeline_summary(result: LearningPipelineResult) -> Dict[str, Any]:
    return result.compact_summary()

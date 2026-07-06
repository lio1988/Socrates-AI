"""
Phase 26I — Training Dry-Run Planner tests.

The planner decides which future training families are ready/blocked/inspect-only
from an AlignmentExportPack + DatasetQualityReport. It never trains.
"""

from backend.dialogues.learning_alignment_exporter import build_alignment_export_pack
from backend.dialogues.learning_foundation import (
    LearningDataset,
    LearningTrace,
    LearningUse,
    TrainingEligibility,
    build_preference_example,
)
from backend.dialogues.learning_quality_gates import (
    DatasetQualityReport,
    QualityGatePolicy,
    QualityVerdict,
    evaluate_quality_gates,
)
from backend.dialogues.learning_training_planner import (
    TrainingFamily,
    TrainingPlannerPolicy,
    TrainingReadiness,
    build_training_dry_run_plan,
    dry_run_plan_summary,
    plan_family,
)
from backend.dialogues.models import ProviderStatus, TaskKind


QUESTION = "What makes a belief knowledge?"


def _trace(trace_id, text):
    t = LearningTrace(
        trace_id=trace_id,
        session_id="sess_train_plan",
        task_id=f"task_{trace_id}",
        question=QUESTION,
        provider_id="mock_provider",
        provider_family="mock",
        model="mock",
        agent_id="agent_0",
        role="synthesizer",
        phase="synthesis",
        task_kind=TaskKind.SYNTHESIS_DRAFT.value,
        status=ProviderStatus.OK.value,
        content={"text": text},
        confidence=0.8,
    )
    t.eligibility = TrainingEligibility.accept(LearningUse.SUPERVISED_DISTILLATION)
    return t


def _pack_with_dpo():
    chosen = _trace("chosen", "Knowledge is justified true belief with caveats.")
    rejected = _trace("rejected", "Knowledge is certainty.")
    ds = LearningDataset(traces=[chosen, rejected])
    ds.add_preference(build_preference_example(chosen, rejected, rationale="Chosen is more calibrated."))
    return build_alignment_export_pack(ds, validation_ratio=0.0, test_ratio=0.0)


def test_plan_family_ready_when_quality_passes_and_records_exist():
    pack = _pack_with_dpo()
    quality = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    quality.verdict = QualityVerdict.PASS

    job = plan_family(TrainingFamily.DPO, pack, quality, TrainingPlannerPolicy.exploratory())
    assert job.readiness == TrainingReadiness.READY
    assert job.record_count >= 1
    assert job.dry_run_config["dry_run"] is True
    assert job.dry_run_config["no_training_executed"] is True
    assert "DRY RUN ONLY" in job.command_preview


def test_warn_quality_blocks_training_but_allows_inspection_by_default():
    pack = _pack_with_dpo()
    quality = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    quality.verdict = QualityVerdict.WARN

    job = plan_family(TrainingFamily.DPO, pack, quality, TrainingPlannerPolicy.exploratory())
    assert job.readiness == TrainingReadiness.INSPECT_ONLY
    assert any("inspection allowed" in r for r in job.reasons)


def test_fail_quality_blocks_all_training_jobs():
    pack = _pack_with_dpo()
    quality = DatasetQualityReport(
        verdict=QualityVerdict.FAIL,
        policy={},
        total_records=pack.manifest.total_records,
        artifact_count=pack.manifest.artifact_count,
    )

    plan = build_training_dry_run_plan(pack, quality, policy=TrainingPlannerPolicy.exploratory())
    assert plan.global_readiness == TrainingReadiness.BLOCKED
    assert all(job.readiness == TrainingReadiness.BLOCKED for job in plan.jobs)
    assert any("quality report verdict is FAIL" in r for r in plan.blocked_reasons)


def test_missing_records_block_specific_family():
    pack = _pack_with_dpo()
    quality = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    quality.verdict = QualityVerdict.PASS

    job = plan_family(TrainingFamily.PROCESS_SFT, pack, quality, TrainingPlannerPolicy.exploratory())
    assert job.readiness == TrainingReadiness.BLOCKED
    assert job.record_count == 0
    assert any("below required" in r for r in job.reasons)


def test_build_training_dry_run_plan_can_scope_families():
    pack = _pack_with_dpo()
    quality = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    quality.verdict = QualityVerdict.PASS

    plan = build_training_dry_run_plan(
        pack,
        quality,
        policy=TrainingPlannerPolicy.exploratory(),
        families=[TrainingFamily.TRACE_SFT, TrainingFamily.DPO],
        metadata={"experiment": "unit"},
    )
    assert len(plan.jobs) == 2
    assert plan.metadata["experiment"] == "unit"
    assert plan.global_readiness == TrainingReadiness.READY


def test_dry_run_plan_summary_lists_ready_and_blocked_jobs():
    pack = _pack_with_dpo()
    quality = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    quality.verdict = QualityVerdict.PASS

    plan = build_training_dry_run_plan(pack, quality, policy=TrainingPlannerPolicy.exploratory())
    summary = dry_run_plan_summary(plan)
    assert summary["quality_verdict"] == QualityVerdict.PASS.value
    assert "job_count" in summary
    assert "ready_jobs" in summary
    assert "blocked_jobs" in summary

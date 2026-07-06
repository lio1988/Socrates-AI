"""
Phase 26J — Local Dry-Run CLI tests.

These tests verify that the CLI/helper layer can load exported artifacts, run
quality gates + planner, and never imply that training was executed.
"""

import json

import pytest

from backend.dialogues.learning_alignment_exporter import build_alignment_export_pack
from backend.dialogues.learning_dry_run_cli import (
    infer_alignment_format,
    infer_dataset_split,
    load_alignment_pack_from_directory,
    load_alignment_pack_from_mapping,
    run_local_dry_run,
    run_local_dry_run_from_directory,
)
from backend.dialogues.learning_foundation import (
    LearningDataset,
    LearningTrace,
    LearningUse,
    TrainingEligibility,
    build_preference_example,
)
from backend.dialogues.models import ProviderStatus, TaskKind


QUESTION = "What makes a belief knowledge?"


def _trace(trace_id, text):
    trace = LearningTrace(
        trace_id=trace_id,
        session_id="sess_cli",
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
    trace.eligibility = TrainingEligibility.accept(LearningUse.SUPERVISED_DISTILLATION)
    return trace


def _pack_files():
    chosen = _trace("chosen", "Knowledge is justified true belief with caveats.")
    rejected = _trace("rejected", "Knowledge is certainty.")
    ds = LearningDataset(traces=[chosen, rejected])
    ds.add_preference(build_preference_example(chosen, rejected, rationale="Chosen is better calibrated."))
    pack = build_alignment_export_pack(ds, validation_ratio=0.0, test_ratio=0.0)
    return pack.as_files()


def test_infer_alignment_format_and_split_from_filename():
    assert infer_alignment_format("dpo.train.jsonl").value == "dpo"
    assert infer_alignment_format("nemo_dpo.train.jsonl").value == "nemo_dpo"
    assert infer_alignment_format("reward_pairs.validation.jsonl").value == "reward_pair"
    assert infer_dataset_split("dpo.train.jsonl").value == "train"
    assert infer_dataset_split("trace_sft.jsonl") is None


def test_infer_alignment_format_rejects_unknown_filename():
    with pytest.raises(ValueError, match="cannot infer"):
        infer_alignment_format("unknown.train.jsonl")


def test_load_alignment_pack_from_mapping_requires_manifest():
    with pytest.raises(ValueError, match="manifest.json"):
        load_alignment_pack_from_mapping({"dpo.train.jsonl": "{}\n"})


def test_load_alignment_pack_from_mapping_round_trips_export_files():
    files = _pack_files()
    pack = load_alignment_pack_from_mapping(files)
    assert pack.manifest.artifact_count >= 1
    assert pack.artifacts
    assert any(a.name == "dpo.train.jsonl" for a in pack.artifacts)


def test_run_local_dry_run_returns_quality_and_plan_without_training():
    pack = load_alignment_pack_from_mapping(_pack_files())
    result = run_local_dry_run(pack, quality_policy="exploratory", planner_policy="exploratory")
    assert result["no_training_executed"] is True
    assert "quality" in result
    assert "plan" in result
    assert result["plan_json"]["planner_version"] == "phase_26i"
    assert all(job["dry_run_config"]["no_training_executed"] for job in result["plan_json"]["jobs"])


def test_run_local_dry_run_from_directory(tmp_path):
    for name, text in _pack_files().items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    result = run_local_dry_run_from_directory(tmp_path, quality_policy="exploratory", planner_policy="exploratory")
    assert result["no_training_executed"] is True
    assert result["export"]["artifact_count"] >= 1


def test_load_alignment_pack_from_directory_rejects_missing_directory(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        load_alignment_pack_from_directory(tmp_path / "missing")

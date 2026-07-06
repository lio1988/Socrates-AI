"""
Phase 26G — Alignment export pack tests.

The exporter creates clean in-memory JSONL artifacts with dedupe, stable splits,
hashes, and a manifest. It does not train models or touch CED runtime.
"""

import json

from backend.dialogues.learning_alignment_exporter import (
    AlignmentFormat,
    DatasetSplit,
    alignment_export_summary,
    build_alignment_export_pack,
    dedupe_records,
    deterministic_split,
    dpo_records,
    nemo_dpo_records,
    reward_pair_records,
    stable_hash,
    trace_sft_records,
)
from backend.dialogues.learning_foundation import (
    LearningDataset,
    LearningTrace,
    LearningUse,
    TrainingEligibility,
    build_preference_example,
)
from backend.dialogues.learning_process_miner import ProcessMiningReport, ProcessSFTExample
from backend.dialogues.models import ProviderStatus, TaskKind


QUESTION = "What makes a belief knowledge?"


def _trace(trace_id, text, *, eligible=True):
    t = LearningTrace(
        trace_id=trace_id,
        session_id="sess_export",
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
    t.eligibility = (
        TrainingEligibility.accept(LearningUse.SUPERVISED_DISTILLATION)
        if eligible
        else TrainingEligibility.reject("not eligible")
    )
    return t


def test_stable_hash_is_deterministic_and_order_insensitive_for_dicts():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_dedupe_records_preserves_first_record():
    records = [
        {"prompt": "p", "response": "r", "metadata": {"n": 1}},
        {"prompt": "p", "response": "r", "metadata": {"n": 2}},
        {"prompt": "p", "response": "r2", "metadata": {"n": 3}},
    ]
    deduped = dedupe_records(records, key_fields=["prompt", "response"])
    assert len(deduped) == 2
    assert deduped[0]["metadata"]["n"] == 1
    assert deduped[0]["record_id"].startswith("rec_")


def test_deterministic_split_is_stable_and_adds_split_field():
    records = [{"record_id": f"rec_{i}", "value": i} for i in range(20)]
    split_a = deterministic_split(records, validation_ratio=0.2, test_ratio=0.1, seed="same")
    split_b = deterministic_split(records, validation_ratio=0.2, test_ratio=0.1, seed="same")
    assert split_a == split_b
    assert sum(len(part) for part in split_a) == 20
    assert all("split" in row for part in split_a for row in part)


def test_trace_sft_records_use_only_eligible_traces():
    ds = LearningDataset(traces=[
        _trace("good", "Good answer", eligible=True),
        _trace("bad", "Bad answer", eligible=False),
    ])
    records = trace_sft_records(ds)
    assert len(records) == 1
    assert records[0]["response"] == "Good answer"
    assert records[0]["metadata"]["format"] == AlignmentFormat.TRACE_SFT.value


def test_dpo_nemo_and_reward_records_from_preferences():
    chosen = _trace("chosen", "Chosen answer")
    rejected = _trace("rejected", "Rejected answer")
    pref = build_preference_example(chosen, rejected, rationale="Chosen is better calibrated.")

    dpo = dpo_records([pref])
    nemo = nemo_dpo_records([pref])
    reward = reward_pair_records([pref])

    assert dpo[0]["chosen"] == "Chosen answer"
    assert nemo[0]["prompt"][0]["role"] == "user"
    assert nemo[0]["chosen"][0]["role"] == "assistant"
    assert reward[0]["preferred"] == "candidate_a"
    assert reward[0]["label"] == 1


def test_build_alignment_export_pack_creates_manifest_and_files():
    chosen = _trace("chosen", "Chosen answer")
    rejected = _trace("rejected", "Rejected answer")
    ds = LearningDataset(traces=[chosen, rejected])
    ds.add_preference(build_preference_example(chosen, rejected, rationale="Chosen is better."))

    process_report = ProcessMiningReport(
        policy_mode="balanced",
        sft_examples=[ProcessSFTExample(
            process_id="proc_1",
            prompt="Improve this step",
            response="Improved step",
            phase="reflection",
            task_kind=TaskKind.REFLECTION_REVISION.value,
            rationale="It repaired the earlier flaw.",
            source_trace_id="chosen",
        )],
    )

    pack = build_alignment_export_pack(
        ds,
        process_report=process_report,
        validation_ratio=0.0,
        test_ratio=0.0,
        seed="unit",
        metadata={"run": "test"},
    )

    files = pack.as_files()
    assert "manifest.json" in files
    assert pack.manifest.artifact_count >= 5
    assert pack.manifest.counts[AlignmentFormat.DPO.value] == 1
    assert pack.manifest.counts[AlignmentFormat.PROCESS_SFT.value] == 1
    assert all(a.content_sha256 for a in pack.artifacts)
    assert any(a.name == "dpo.train.jsonl" for a in pack.artifacts)

    manifest = json.loads(files["manifest.json"])
    assert manifest["metadata"]["run"] == "test"


def test_alignment_export_summary_lists_artifacts():
    ds = LearningDataset(traces=[_trace("only", "Only answer")])
    pack = build_alignment_export_pack(ds, validation_ratio=0.0, test_ratio=0.0)
    summary = alignment_export_summary(pack)
    assert summary["artifact_count"] >= 1
    assert summary["total_records"] >= 1
    assert isinstance(summary["artifacts"], list)
    assert summary["artifacts"][0]["split"] == DatasetSplit.TRAIN.value

"""
Phase 26H — Dataset Quality Gates tests.

Quality gates inspect alignment export packs before any training. They are pure,
in-memory checks with no provider calls, no file IO, and no CED core changes.
"""

import json

from backend.dialogues.learning_alignment_exporter import (
    AlignmentFormat,
    DatasetSplit,
    ExportedArtifact,
    build_alignment_export_pack,
)
from backend.dialogues.learning_foundation import (
    LearningDataset,
    LearningTrace,
    LearningUse,
    TrainingEligibility,
    build_preference_example,
)
from backend.dialogues.learning_quality_gates import (
    QualityGatePolicy,
    QualityVerdict,
    evaluate_quality_gates,
    jaccard_similarity,
    quality_gate_summary,
)
from backend.dialogues.models import ProviderStatus, TaskKind


QUESTION = "What makes a belief knowledge?"


def _trace(trace_id, text, *, eligible=True):
    trace = LearningTrace(
        trace_id=trace_id,
        session_id="sess_quality",
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
    trace.eligibility = (
        TrainingEligibility.accept(LearningUse.SUPERVISED_DISTILLATION)
        if eligible else TrainingEligibility.reject("not eligible")
    )
    return trace


def _pack_with_preference():
    chosen = _trace("chosen", "Knowledge is justified true belief with careful caveats.")
    rejected = _trace("rejected", "Knowledge is just certainty.")
    ds = LearningDataset(traces=[chosen, rejected])
    ds.add_preference(build_preference_example(chosen, rejected, rationale="Chosen is better calibrated."))
    return build_alignment_export_pack(ds, validation_ratio=0.0, test_ratio=0.0)


def test_jaccard_similarity_detects_identical_and_different_text():
    assert jaccard_similarity("same words", "same words") == 1.0
    assert jaccard_similarity("alpha beta", "gamma delta") == 0.0
    assert 0.0 < jaccard_similarity("alpha beta", "alpha gamma") < 1.0


def test_quality_gates_pass_clean_pack_with_exploratory_policy():
    pack = _pack_with_preference()
    report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    assert report.verdict in {QualityVerdict.PASS, QualityVerdict.WARN}
    assert report.total_records > 0
    summary = quality_gate_summary(report)
    assert summary["total_records"] == report.total_records


def test_quality_gates_fail_hash_mismatch():
    pack = _pack_with_preference()
    artifact = pack.artifacts[0]
    artifact.jsonl = artifact.jsonl + "\n"

    report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    assert report.verdict == QualityVerdict.FAIL
    assert any(i.gate == "artifact_hash" for i in report.issues)


def test_quality_gates_fail_bad_jsonl_line():
    pack = _pack_with_preference()
    bad = ExportedArtifact(
        name="bad.train.jsonl",
        format=AlignmentFormat.DPO,
        split=DatasetSplit.TRAIN,
        record_count=1,
        content_sha256="bad-hash",
        jsonl="{not valid json}\n",
    )
    pack.artifacts = [bad]

    report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    assert report.verdict == QualityVerdict.FAIL
    assert any(i.gate == "jsonl_parse" for i in report.issues)


def test_quality_gates_fail_empty_required_field():
    record = {"record_id": "r1", "prompt": "Question", "chosen": "", "rejected": "Weak"}
    text = json.dumps(record) + "\n"
    import hashlib
    artifact = ExportedArtifact(
        name="dpo.train.jsonl",
        format=AlignmentFormat.DPO,
        split=DatasetSplit.TRAIN,
        record_count=1,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        jsonl=text,
    )
    pack = _pack_with_preference()
    pack.artifacts = [artifact]
    pack.manifest.counts = {AlignmentFormat.DPO.value: 1}

    report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    assert report.verdict == QualityVerdict.FAIL
    assert any(i.gate == "empty_required_field" for i in report.issues)


def test_quality_gates_warn_near_identical_chosen_rejected():
    record = {
        "record_id": "near_same",
        "prompt": "Question",
        "chosen": "alpha beta gamma",
        "rejected": "alpha beta gamma",
    }
    text = json.dumps(record) + "\n"
    import hashlib
    artifact = ExportedArtifact(
        name="dpo.train.jsonl",
        format=AlignmentFormat.DPO,
        split=DatasetSplit.TRAIN,
        record_count=1,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        jsonl=text,
    )
    pack = _pack_with_preference()
    pack.artifacts = [artifact]
    pack.manifest.counts = {AlignmentFormat.DPO.value: 1}

    report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    assert report.verdict == QualityVerdict.WARN
    assert any(i.gate == "chosen_rejected_similarity" for i in report.issues)


def test_quality_gates_detect_split_leakage():
    rec = {"record_id": "r", "prompt": "Q", "chosen": "A", "rejected": "B"}
    text = json.dumps(rec) + "\n"
    import hashlib
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    train = ExportedArtifact(
        name="dpo.train.jsonl",
        format=AlignmentFormat.DPO,
        split=DatasetSplit.TRAIN,
        record_count=1,
        content_sha256=sha,
        jsonl=text,
    )
    val = ExportedArtifact(
        name="dpo.validation.jsonl",
        format=AlignmentFormat.DPO,
        split=DatasetSplit.VALIDATION,
        record_count=1,
        content_sha256=sha,
        jsonl=text,
    )
    pack = _pack_with_preference()
    pack.artifacts = [train, val]
    pack.manifest.counts = {AlignmentFormat.DPO.value: 2}

    report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
    assert report.verdict == QualityVerdict.FAIL
    assert any(i.gate == "split_leakage" for i in report.issues)


def test_quality_gates_can_fail_min_total_records():
    pack = _pack_with_preference()
    report = evaluate_quality_gates(pack, policy=QualityGatePolicy(min_total_records=10_000))
    assert report.verdict in {QualityVerdict.FAIL, QualityVerdict.WARN}
    assert any(i.gate == "min_total_records" for i in report.issues)

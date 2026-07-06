"""
Phase 26G — Alignment Export Pack.

This module is the first practical "LLM learning trick" layer: export discipline.
It turns the parallel learning objects into clean, deduplicated, split, manifest-
backed JSONL files for future DPO / SFT / reward-model / process-reward / NeMo-
style workflows.

It still does not train or fine-tune anything, and it does not touch CED core.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from .learning_foundation import (
    LearningDataset,
    PreferenceExample,
    render_trace_answer,
    sanitize_public_payload,
)
from .learning_process_miner import ProcessMiningReport, ProcessSFTExample


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


def jsonl_lines(records: Iterable[Dict[str, Any]]) -> str:
    lines = [json.dumps(sanitize_public_payload(r), ensure_ascii=False, sort_keys=True) for r in records]
    return "\n".join(lines) + ("\n" if lines else "")


class AlignmentFormat(str, Enum):
    TRACE_SFT = "trace_sft"
    DPO = "dpo"
    NEMO_DPO = "nemo_dpo"
    REWARD_PAIR = "reward_pair"
    PROCESS_SFT = "process_sft"
    MANIFEST = "manifest"


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class ExportedArtifact(BaseModel):
    name: str
    format: AlignmentFormat
    split: Optional[DatasetSplit] = None
    record_count: int = 0
    content_sha256: str
    jsonl: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlignmentDatasetManifest(BaseModel):
    manifest_id: str = Field(default_factory=lambda: stable_hash({"created_at": _utcnow().isoformat()}, prefix="manifest_"))
    created_at: datetime = Field(default_factory=_utcnow)
    source: str = "ced_alignment_export_pack"
    constitution_version: str
    policy_versions: Dict[str, Any] = Field(default_factory=dict)
    artifact_count: int = 0
    total_records: int = 0
    artifact_hashes: Dict[str, str] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


class AlignmentExportPack(BaseModel):
    manifest: AlignmentDatasetManifest
    artifacts: List[ExportedArtifact] = Field(default_factory=list)

    def artifact(self, name: str) -> Optional[ExportedArtifact]:
        return next((a for a in self.artifacts if a.name == name), None)

    def as_files(self) -> Dict[str, str]:
        out = {a.name: a.jsonl for a in self.artifacts}
        out["manifest.json"] = self.manifest.to_json() + "\n"
        return out


# ── record preparation ───────────────────────────────────────────────────────

def dedupe_records(records: Sequence[Dict[str, Any]], *, key_fields: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Deterministically remove duplicate records while preserving first order."""
    seen = set()
    out: List[Dict[str, Any]] = []
    for record in records:
        clean = sanitize_public_payload(record)
        if key_fields:
            key_payload = {k: clean.get(k) for k in key_fields}
        else:
            key_payload = clean
        key = stable_hash(key_payload)
        if key in seen:
            continue
        seen.add(key)
        clean.setdefault("record_id", stable_hash(clean, prefix="rec_"))
        out.append(clean)
    return out


def deterministic_split(
    records: Sequence[Dict[str, Any]],
    *,
    validation_ratio: float = 0.10,
    test_ratio: float = 0.0,
    seed: str = "ced_alignment_v1",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Hash-based stable train/validation/test split."""
    val_ratio = max(0.0, min(0.5, validation_ratio))
    tst_ratio = max(0.0, min(0.5, test_ratio))
    if val_ratio + tst_ratio > 0.8:
        raise ValueError("validation_ratio + test_ratio is too large")

    train: List[Dict[str, Any]] = []
    validation: List[Dict[str, Any]] = []
    test: List[Dict[str, Any]] = []
    for record in records:
        key = stable_hash({"seed": seed, "record": record.get("record_id") or record})
        bucket = int(key[:8], 16) / 0xFFFFFFFF
        if bucket < tst_ratio:
            split = DatasetSplit.TEST.value
            target = test
        elif bucket < tst_ratio + val_ratio:
            split = DatasetSplit.VALIDATION.value
            target = validation
        else:
            split = DatasetSplit.TRAIN.value
            target = train
        item = dict(record)
        item["split"] = split
        target.append(item)
    return train, validation, test


def _artifact(name: str, fmt: AlignmentFormat, records: Sequence[Dict[str, Any]], *, split: Optional[DatasetSplit] = None,
              metadata: Optional[Dict[str, Any]] = None) -> ExportedArtifact:
    text = jsonl_lines(records)
    return ExportedArtifact(
        name=name,
        format=fmt,
        split=split,
        record_count=len(records),
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        jsonl=text,
        metadata=sanitize_public_payload(metadata or {}),
    )


# ── exporters ────────────────────────────────────────────────────────────────

def trace_sft_records(dataset: LearningDataset) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for trace in dataset.eligible_traces():
        response = render_trace_answer(trace).strip()
        if not response:
            continue
        records.append({
            "record_id": stable_hash({"trace_id": trace.trace_id, "format": "trace_sft"}, prefix="sft_"),
            "prompt": trace.question,
            "response": response,
            "metadata": {
                "format": AlignmentFormat.TRACE_SFT.value,
                "trace_id": trace.trace_id,
                "task_id": trace.task_id,
                "task_kind": trace.task_kind,
                "phase": trace.phase,
                "provider_family": trace.provider_family,
                "model": trace.model,
                "confidence": trace.confidence,
                "constitution_version": dataset.constitution.version,
            },
        })
    return dedupe_records(records, key_fields=["prompt", "response"])


def dpo_records(preferences: Sequence[PreferenceExample]) -> List[Dict[str, Any]]:
    records = []
    for pref in preferences:
        rec = pref.to_dpo_record()
        rec["record_id"] = stable_hash({
            "prompt": rec.get("prompt"),
            "chosen": rec.get("chosen"),
            "rejected": rec.get("rejected"),
        }, prefix="dpo_")
        rec.setdefault("metadata", {})["format"] = AlignmentFormat.DPO.value
        records.append(rec)
    return dedupe_records(records, key_fields=["prompt", "chosen", "rejected"])


def nemo_dpo_records(preferences: Sequence[PreferenceExample]) -> List[Dict[str, Any]]:
    """NeMo-style conversation preference shape, kept generic/offline-safe."""
    records = []
    for pref in preferences:
        records.append({
            "record_id": stable_hash({"pref": pref.preference_id, "format": "nemo_dpo"}, prefix="nemo_"),
            "prompt": [{"role": "user", "content": pref.prompt}],
            "chosen": [{"role": "assistant", "content": pref.chosen}],
            "rejected": [{"role": "assistant", "content": pref.rejected}],
            "metadata": {
                "format": AlignmentFormat.NEMO_DPO.value,
                "preference_id": pref.preference_id,
                "chosen_trace_id": pref.chosen_trace_id,
                "rejected_trace_id": pref.rejected_trace_id,
                "rationale": pref.rationale,
                **sanitize_public_payload(pref.metadata),
            },
        })
    return dedupe_records(records, key_fields=["prompt", "chosen", "rejected"])


def reward_pair_records(preferences: Sequence[PreferenceExample]) -> List[Dict[str, Any]]:
    """Pairwise reward-model records: chosen label=1, rejected label=0."""
    records = []
    for pref in preferences:
        records.append({
            "record_id": stable_hash({"pref": pref.preference_id, "format": "reward_pair"}, prefix="rm_"),
            "input": pref.prompt,
            "candidate_a": pref.chosen,
            "candidate_b": pref.rejected,
            "preferred": "candidate_a",
            "label": 1,
            "metadata": {
                "format": AlignmentFormat.REWARD_PAIR.value,
                "preference_id": pref.preference_id,
                "chosen_trace_id": pref.chosen_trace_id,
                "rejected_trace_id": pref.rejected_trace_id,
                "rationale": pref.rationale,
                **sanitize_public_payload(pref.metadata),
            },
        })
    return dedupe_records(records, key_fields=["input", "candidate_a", "candidate_b"])


def process_sft_records(process_report: Optional[ProcessMiningReport]) -> List[Dict[str, Any]]:
    if process_report is None:
        return []
    records: List[Dict[str, Any]] = []
    for ex in process_report.sft_examples:
        rec = ex.to_jsonl_record()
        rec["record_id"] = stable_hash({"process_id": ex.process_id, "format": "process_sft"}, prefix="proc_sft_")
        rec.setdefault("metadata", {})["format"] = AlignmentFormat.PROCESS_SFT.value
        records.append(rec)
    return dedupe_records(records, key_fields=["prompt", "response"])


# ── pack builder ─────────────────────────────────────────────────────────────

def _split_artifacts(base_name: str, fmt: AlignmentFormat, records: Sequence[Dict[str, Any]], *, validation_ratio: float,
                     test_ratio: float, seed: str) -> List[ExportedArtifact]:
    train, validation, test = deterministic_split(records, validation_ratio=validation_ratio, test_ratio=test_ratio, seed=seed)
    artifacts = [_artifact(f"{base_name}.train.jsonl", fmt, train, split=DatasetSplit.TRAIN)]
    if validation:
        artifacts.append(_artifact(f"{base_name}.validation.jsonl", fmt, validation, split=DatasetSplit.VALIDATION))
    if test:
        artifacts.append(_artifact(f"{base_name}.test.jsonl", fmt, test, split=DatasetSplit.TEST))
    return artifacts


def build_alignment_export_pack(
    dataset: LearningDataset,
    *,
    process_report: Optional[ProcessMiningReport] = None,
    validation_ratio: float = 0.10,
    test_ratio: float = 0.0,
    seed: str = "ced_alignment_v1",
    metadata: Optional[Dict[str, Any]] = None,
) -> AlignmentExportPack:
    """
    Build a manifest-backed artifact pack from the current learning dataset.

    The pack is in-memory by design. A caller may write `pack.as_files()` to disk,
    upload to storage, or feed each JSONL string into a training pipeline later.
    """
    prefs: List[PreferenceExample] = list(dataset.preferences)
    if process_report is not None:
        prefs.extend(process_report.preferences)

    record_groups: List[Tuple[str, AlignmentFormat, List[Dict[str, Any]]]] = [
        ("trace_sft", AlignmentFormat.TRACE_SFT, trace_sft_records(dataset)),
        ("dpo", AlignmentFormat.DPO, dpo_records(prefs)),
        ("nemo_dpo", AlignmentFormat.NEMO_DPO, nemo_dpo_records(prefs)),
        ("reward_pairs", AlignmentFormat.REWARD_PAIR, reward_pair_records(prefs)),
        ("process_sft", AlignmentFormat.PROCESS_SFT, process_sft_records(process_report)),
    ]

    artifacts: List[ExportedArtifact] = []
    warnings: List[str] = []
    counts: Dict[str, int] = {}
    for base_name, fmt, records in record_groups:
        counts[fmt.value] = len(records)
        if not records:
            warnings.append(f"no records for {fmt.value}")
            continue
        artifacts.extend(_split_artifacts(base_name, fmt, records,
                                          validation_ratio=validation_ratio,
                                          test_ratio=test_ratio,
                                          seed=f"{seed}:{fmt.value}"))

    artifact_hashes = {a.name: a.content_sha256 for a in artifacts}
    manifest = AlignmentDatasetManifest(
        constitution_version=dataset.constitution.version,
        policy_versions={
            "export_pack": "phase_26g",
            "split_seed": seed,
            "validation_ratio": validation_ratio,
            "test_ratio": test_ratio,
            "process_report_policy": getattr(process_report, "policy_mode", None),
        },
        artifact_count=len(artifacts),
        total_records=sum(a.record_count for a in artifacts),
        artifact_hashes=artifact_hashes,
        counts=counts,
        warnings=warnings,
        metadata=sanitize_public_payload(metadata or {}),
    )
    return AlignmentExportPack(manifest=manifest, artifacts=artifacts)


def alignment_export_summary(pack: AlignmentExportPack) -> Dict[str, Any]:
    return sanitize_public_payload({
        "manifest_id": pack.manifest.manifest_id,
        "artifact_count": pack.manifest.artifact_count,
        "total_records": pack.manifest.total_records,
        "counts": pack.manifest.counts,
        "warnings": pack.manifest.warnings,
        "artifacts": [
            {"name": a.name, "format": a.format.value, "split": a.split.value if a.split else None,
             "record_count": a.record_count, "sha256": a.content_sha256}
            for a in pack.artifacts
        ],
    })

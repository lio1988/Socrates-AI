"""
Phase 26H — Dataset Quality Gates.

Quality gates are the safety layer between alignment exports and real training.
They inspect an AlignmentExportPack and produce a deterministic verdict:

  - PASS: safe enough for downstream experiments;
  - WARN: usable for inspection, but not trusted training;
  - FAIL: should not be used for training.

This module remains parallel to CED core: no provider calls, no training, no file IO,
no mutation of CED state, no changes to prompts/routing/scoring/ratification.
"""

from __future__ import annotations

import json
import math
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field

from .learning_alignment_exporter import AlignmentExportPack, AlignmentFormat, ExportedArtifact, stable_hash
from .learning_foundation import sanitize_public_payload


class QualitySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class QualityVerdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class QualityGatePolicy(BaseModel):
    min_total_records: int = 1
    min_dpo_records_for_training: int = 1
    min_process_sft_records_for_process_training: int = 1
    max_duplicate_ratio: float = 0.05
    max_split_leakage_pairs: int = 0
    max_empty_field_ratio: float = 0.0
    max_chosen_rejected_similarity: float = 0.98
    min_prompt_chars: int = 3
    max_prompt_chars: int = 24000
    min_response_chars: int = 1
    max_response_chars: int = 48000
    require_manifest_hashes: bool = True
    require_train_split: bool = True

    @classmethod
    def strict(cls) -> "QualityGatePolicy":
        return cls()

    @classmethod
    def exploratory(cls) -> "QualityGatePolicy":
        return cls(
            min_total_records=1,
            min_dpo_records_for_training=0,
            min_process_sft_records_for_process_training=0,
            max_duplicate_ratio=0.20,
            max_empty_field_ratio=0.05,
            max_chosen_rejected_similarity=0.995,
        )


class QualityIssue(BaseModel):
    gate: str
    severity: QualitySeverity
    message: str
    artifact: Optional[str] = None
    record_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArtifactQualitySummary(BaseModel):
    name: str
    format: str
    split: Optional[str] = None
    record_count: int = 0
    duplicate_count: int = 0
    empty_field_count: int = 0
    length_violation_count: int = 0
    near_identical_pair_count: int = 0
    content_hash_ok: bool = True


class DatasetQualityReport(BaseModel):
    verdict: QualityVerdict
    policy: Dict[str, Any]
    total_records: int = 0
    artifact_count: int = 0
    summaries: List[ArtifactQualitySummary] = Field(default_factory=list)
    issues: List[QualityIssue] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == QualitySeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == QualitySeverity.WARNING)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


# ── parsing / helpers ────────────────────────────────────────────────────────

def _records(artifact: ExportedArtifact) -> List[Dict[str, Any]]:
    if not artifact.jsonl.strip():
        return []
    records: List[Dict[str, Any]] = []
    for line_no, line in enumerate(artifact.jsonl.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            records.append({"__parse_error__": str(exc), "__line_no__": line_no})
            continue
        records.append(value)
    return records


def _text_fields(record: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key in ["prompt", "response", "chosen", "rejected", "input", "candidate_a", "candidate_b"]:
        value = record.get(key)
        if isinstance(value, str):
            out[key] = value
        elif isinstance(value, list):
            # Conversation-style records, e.g. NeMo DPO.
            content = []
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("content"), str):
                    content.append(item["content"])
            if content:
                out[key] = "\n".join(content)
    return out


def _field_signature(record: Dict[str, Any], keys: Sequence[str]) -> str:
    return stable_hash({k: record.get(k) for k in keys})


def _token_set(text: str) -> Set[str]:
    return {t for t in text.lower().replace("\n", " ").split(" ") if t.strip()}


def jaccard_similarity(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _content_hash_ok(artifact: ExportedArtifact) -> bool:
    import hashlib
    return hashlib.sha256(artifact.jsonl.encode("utf-8")).hexdigest() == artifact.content_sha256


def _add(issues: List[QualityIssue], gate: str, severity: QualitySeverity, message: str,
         artifact: Optional[str] = None, record_id: Optional[str] = None, **metadata: Any) -> None:
    issues.append(QualityIssue(
        gate=gate,
        severity=severity,
        message=message,
        artifact=artifact,
        record_id=record_id,
        metadata=sanitize_public_payload(metadata),
    ))


# ── gates ────────────────────────────────────────────────────────────────────

def check_artifact_integrity(pack: AlignmentExportPack, policy: QualityGatePolicy) -> Tuple[List[ArtifactQualitySummary], List[QualityIssue]]:
    summaries: List[ArtifactQualitySummary] = []
    issues: List[QualityIssue] = []

    for artifact in pack.artifacts:
        records = _records(artifact)
        summary = ArtifactQualitySummary(
            name=artifact.name,
            format=artifact.format.value,
            split=artifact.split.value if artifact.split else None,
            record_count=len(records),
            content_hash_ok=_content_hash_ok(artifact),
        )
        if any("__parse_error__" in r for r in records):
            for r in records:
                if "__parse_error__" in r:
                    _add(issues, "jsonl_parse", QualitySeverity.ERROR,
                         f"JSONL parse error at line {r['__line_no__']}: {r['__parse_error__']}", artifact.name)
        if policy.require_manifest_hashes and not summary.content_hash_ok:
            _add(issues, "artifact_hash", QualitySeverity.ERROR,
                 "artifact content SHA-256 does not match manifest/export metadata", artifact.name)
        if artifact.record_count != len(records):
            _add(issues, "record_count", QualitySeverity.ERROR,
                 f"artifact declares {artifact.record_count} records but JSONL contains {len(records)}", artifact.name)
        summaries.append(summary)
    return summaries, issues


def check_record_shapes(pack: AlignmentExportPack, policy: QualityGatePolicy,
                        summaries: List[ArtifactQualitySummary]) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    by_name = {s.name: s for s in summaries}

    for artifact in pack.artifacts:
        summary = by_name[artifact.name]
        records = [r for r in _records(artifact) if "__parse_error__" not in r]
        seen = set()
        for record in records:
            record_id = str(record.get("record_id") or stable_hash(record, prefix="rec_"))
            sig = stable_hash(record)
            if sig in seen:
                summary.duplicate_count += 1
            seen.add(sig)

            fields = _text_fields(record)
            required: List[str]
            if artifact.format in {AlignmentFormat.DPO, AlignmentFormat.NEMO_DPO}:
                required = ["prompt", "chosen", "rejected"]
            elif artifact.format == AlignmentFormat.REWARD_PAIR:
                required = ["input", "candidate_a", "candidate_b"]
            elif artifact.format in {AlignmentFormat.TRACE_SFT, AlignmentFormat.PROCESS_SFT}:
                required = ["prompt", "response"]
            else:
                required = []

            for field in required:
                if field not in fields or not fields[field].strip():
                    summary.empty_field_count += 1
                    _add(issues, "empty_required_field", QualitySeverity.ERROR,
                         f"missing or empty required field: {field}", artifact.name, record_id)

            for field, text in fields.items():
                if field in {"prompt", "input"}:
                    if not (policy.min_prompt_chars <= len(text) <= policy.max_prompt_chars):
                        summary.length_violation_count += 1
                        _add(issues, "prompt_length", QualitySeverity.WARNING,
                             f"{field} length {len(text)} outside bounds", artifact.name, record_id,
                             field=field, length=len(text))
                elif field in {"response", "chosen", "rejected", "candidate_a", "candidate_b"}:
                    if not (policy.min_response_chars <= len(text) <= policy.max_response_chars):
                        summary.length_violation_count += 1
                        _add(issues, "response_length", QualitySeverity.WARNING,
                             f"{field} length {len(text)} outside bounds", artifact.name, record_id,
                             field=field, length=len(text))

            if artifact.format in {AlignmentFormat.DPO, AlignmentFormat.NEMO_DPO} and {"chosen", "rejected"} <= set(fields):
                sim = jaccard_similarity(fields["chosen"], fields["rejected"])
                if sim >= policy.max_chosen_rejected_similarity:
                    summary.near_identical_pair_count += 1
                    _add(issues, "chosen_rejected_similarity", QualitySeverity.WARNING,
                         f"chosen/rejected similarity {sim:.3f} is too high", artifact.name, record_id,
                         similarity=sim)
    return issues


def check_split_leakage(pack: AlignmentExportPack, policy: QualityGatePolicy) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    by_signature: Dict[str, Set[str]] = {}
    for artifact in pack.artifacts:
        split = artifact.split.value if artifact.split else "none"
        for record in _records(artifact):
            if "__parse_error__" in record:
                continue
            fields = _text_fields(record)
            if artifact.format in {AlignmentFormat.DPO, AlignmentFormat.NEMO_DPO}:
                sig = _field_signature(record, ["prompt", "chosen", "rejected"])
            elif artifact.format == AlignmentFormat.REWARD_PAIR:
                sig = _field_signature(record, ["input", "candidate_a", "candidate_b"])
            else:
                sig = stable_hash(fields or record)
            by_signature.setdefault(sig, set()).add(split)

    leakage = {sig: splits for sig, splits in by_signature.items() if len(splits - {"none"}) > 1}
    if len(leakage) > policy.max_split_leakage_pairs:
        _add(issues, "split_leakage", QualitySeverity.ERROR,
             f"detected {len(leakage)} duplicate record signature(s) across splits", None,
             leakage_count=len(leakage))
    return issues


def check_dataset_volume(pack: AlignmentExportPack, policy: QualityGatePolicy) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    total = sum(a.record_count for a in pack.artifacts)
    if total < policy.min_total_records:
        _add(issues, "min_total_records", QualitySeverity.ERROR,
             f"total records {total} below minimum {policy.min_total_records}")

    counts = pack.manifest.counts or {}
    dpo_count = counts.get(AlignmentFormat.DPO.value, 0)
    process_count = counts.get(AlignmentFormat.PROCESS_SFT.value, 0)
    if dpo_count < policy.min_dpo_records_for_training:
        _add(issues, "min_dpo_records", QualitySeverity.WARNING,
             f"DPO records {dpo_count} below training target {policy.min_dpo_records_for_training}")
    if process_count < policy.min_process_sft_records_for_process_training:
        _add(issues, "min_process_sft_records", QualitySeverity.WARNING,
             f"process SFT records {process_count} below training target {policy.min_process_sft_records_for_process_training}")

    if policy.require_train_split and not any(a.split and a.split.value == "train" for a in pack.artifacts):
        _add(issues, "train_split", QualitySeverity.ERROR, "no train split artifact found")
    return issues


def evaluate_quality_gates(pack: AlignmentExportPack, *, policy: Optional[QualityGatePolicy] = None) -> DatasetQualityReport:
    policy = policy or QualityGatePolicy.strict()
    summaries, issues = check_artifact_integrity(pack, policy)
    issues.extend(check_record_shapes(pack, policy, summaries))
    issues.extend(check_split_leakage(pack, policy))
    issues.extend(check_dataset_volume(pack, policy))

    total_records = sum(s.record_count for s in summaries)
    duplicate_count = sum(s.duplicate_count for s in summaries)
    empty_count = sum(s.empty_field_count for s in summaries)
    duplicate_ratio = duplicate_count / total_records if total_records else 0.0
    empty_ratio = empty_count / total_records if total_records else 0.0

    if duplicate_ratio > policy.max_duplicate_ratio:
        _add(issues, "duplicate_ratio", QualitySeverity.WARNING,
             f"duplicate ratio {duplicate_ratio:.3f} exceeds {policy.max_duplicate_ratio:.3f}",
             duplicate_ratio=duplicate_ratio)
    if empty_ratio > policy.max_empty_field_ratio:
        _add(issues, "empty_field_ratio", QualitySeverity.ERROR,
             f"empty field ratio {empty_ratio:.3f} exceeds {policy.max_empty_field_ratio:.3f}",
             empty_ratio=empty_ratio)

    error_count = sum(1 for i in issues if i.severity == QualitySeverity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == QualitySeverity.WARNING)
    if error_count:
        verdict = QualityVerdict.FAIL
    elif warning_count:
        verdict = QualityVerdict.WARN
    else:
        verdict = QualityVerdict.PASS

    return DatasetQualityReport(
        verdict=verdict,
        policy=policy.model_dump(mode="json"),
        total_records=total_records,
        artifact_count=len(pack.artifacts),
        summaries=summaries,
        issues=issues,
        metrics={
            "duplicate_count": duplicate_count,
            "duplicate_ratio": duplicate_ratio,
            "empty_field_count": empty_count,
            "empty_field_ratio": empty_ratio,
            "error_count": error_count,
            "warning_count": warning_count,
        },
    )


def quality_gate_summary(report: DatasetQualityReport) -> Dict[str, Any]:
    return sanitize_public_payload({
        "verdict": report.verdict.value,
        "total_records": report.total_records,
        "artifact_count": report.artifact_count,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "metrics": report.metrics,
        "issues": [
            {
                "gate": i.gate,
                "severity": i.severity.value,
                "message": i.message,
                "artifact": i.artifact,
                "record_id": i.record_id,
            }
            for i in report.issues[:20]
        ],
    })

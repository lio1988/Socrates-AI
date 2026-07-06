"""
Phase 26J — Local Dry-Run CLI helpers.

This module makes the parallel learning stack runnable as a local dry-run over
exported artifacts. It is intentionally safe:

  - no training;
  - no fine-tuning;
  - no provider calls;
  - no CED state mutation;
  - no changes to prompts/routing/scoring/ratification.

It can load an in-memory or on-disk AlignmentExportPack, evaluate quality gates,
and build a TrainingDryRunPlan. The CLI prints JSON summaries only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .learning_alignment_exporter import (
    AlignmentDatasetManifest,
    AlignmentExportPack,
    AlignmentFormat,
    DatasetSplit,
    ExportedArtifact,
    alignment_export_summary,
)
from .learning_quality_gates import (
    QualityGatePolicy,
    evaluate_quality_gates,
    quality_gate_summary,
)
from .learning_training_planner import (
    TrainingDryRunPlan,
    TrainingPlannerPolicy,
    build_training_dry_run_plan,
    dry_run_plan_summary,
)
from .learning_foundation import sanitize_public_payload


FORMAT_BY_PREFIX = {
    "trace_sft": AlignmentFormat.TRACE_SFT,
    "dpo": AlignmentFormat.DPO,
    "nemo_dpo": AlignmentFormat.NEMO_DPO,
    "reward_pairs": AlignmentFormat.REWARD_PAIR,
    "process_sft": AlignmentFormat.PROCESS_SFT,
}


def infer_alignment_format(filename: str) -> AlignmentFormat:
    stem = filename.removesuffix(".jsonl")
    for prefix, fmt in sorted(FORMAT_BY_PREFIX.items(), key=lambda item: len(item[0]), reverse=True):
        if stem == prefix or stem.startswith(prefix + "."):
            return fmt
    raise ValueError(f"cannot infer alignment format from filename: {filename}")


def infer_dataset_split(filename: str) -> Optional[DatasetSplit]:
    parts = filename.removesuffix(".jsonl").split(".")
    if len(parts) < 2:
        return None
    maybe = parts[-1]
    for split in DatasetSplit:
        if split.value == maybe:
            return split
    return None


def _count_jsonl_records(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def load_alignment_pack_from_mapping(files: Mapping[str, str]) -> AlignmentExportPack:
    """
    Build an AlignmentExportPack from a mapping of filename -> text content.

    Required: manifest.json. Artifact formats and splits are inferred from JSONL
    filenames. Hashes are loaded from the manifest when present; otherwise the
    ExportedArtifact hash will intentionally mismatch and quality gates will fail.
    """
    if "manifest.json" not in files:
        raise ValueError("manifest.json is required")
    manifest = AlignmentDatasetManifest.model_validate(json.loads(files["manifest.json"]))
    artifacts: List[ExportedArtifact] = []
    hashes = manifest.artifact_hashes or {}

    for name, text in sorted(files.items()):
        if name == "manifest.json" or not name.endswith(".jsonl"):
            continue
        artifacts.append(ExportedArtifact(
            name=name,
            format=infer_alignment_format(name),
            split=infer_dataset_split(name),
            record_count=_count_jsonl_records(text),
            content_sha256=hashes.get(name, "missing-from-manifest"),
            jsonl=text,
            metadata={"loaded_by": "phase_26j_mapping_loader"},
        ))
    return AlignmentExportPack(manifest=manifest, artifacts=artifacts)


def load_alignment_pack_from_directory(directory: str | Path) -> AlignmentExportPack:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"artifact directory does not exist or is not a directory: {root}")
    files: Dict[str, str] = {}
    for path in root.iterdir():
        if path.is_file() and (path.name == "manifest.json" or path.name.endswith(".jsonl")):
            files[path.name] = path.read_text(encoding="utf-8")
    return load_alignment_pack_from_mapping(files)


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


def run_local_dry_run(
    pack: AlignmentExportPack,
    *,
    quality_policy: str = "strict",
    planner_policy: str = "conservative",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    quality = evaluate_quality_gates(pack, policy=_quality_policy(quality_policy))
    plan = build_training_dry_run_plan(
        pack,
        quality,
        policy=_planner_policy(planner_policy),
        metadata={"runner": "phase_26j_local_dry_run", **(metadata or {})},
    )
    return sanitize_public_payload({
        "export": alignment_export_summary(pack),
        "quality": quality_gate_summary(quality),
        "plan": dry_run_plan_summary(plan),
        "plan_json": json.loads(plan.to_json()),
        "no_training_executed": True,
    })


def run_local_dry_run_from_directory(
    directory: str | Path,
    *,
    quality_policy: str = "strict",
    planner_policy: str = "conservative",
) -> Dict[str, Any]:
    pack = load_alignment_pack_from_directory(directory)
    return run_local_dry_run(
        pack,
        quality_policy=quality_policy,
        planner_policy=planner_policy,
        metadata={"artifact_directory": str(directory)},
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.dialogues.learning_dry_run_cli",
        description="Run local dry-run quality gates and training planner over alignment export artifacts.",
    )
    parser.add_argument("artifact_dir", help="Directory containing manifest.json and *.jsonl artifacts")
    parser.add_argument("--quality-policy", choices=["strict", "exploratory"], default="strict")
    parser.add_argument("--planner-policy", choices=["conservative", "exploratory"], default="conservative")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_local_dry_run_from_directory(
        args.artifact_dir,
        quality_policy=args.quality_policy,
        planner_policy=args.planner_policy,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

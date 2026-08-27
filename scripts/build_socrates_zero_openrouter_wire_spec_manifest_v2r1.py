"""Build and independently revalidate OpenRouter wire specification manifest v2r1."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Optional, Sequence

if __package__ in (None, ""):
    _repository_root = Path(__file__).resolve().parents[1]
    if str(_repository_root) not in sys.path:
        sys.path.insert(0, str(_repository_root))

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v2r1 import (
    FROZEN_MANIFEST_V2R1,
    MANIFEST_RELATIVE_PATH_V2R1,
    REVALIDATION_RELATIVE_PATH_V2R1,
    VALIDATION_RELATIVE_PATH_V2R1,
    ManifestV2R1,
    RevalidationV2R1,
    ValidationV2R1,
    build_validation_v2r1,
    render_contract_v2r1,
    sha256_bytes_v2r1,
)


def _safe_path(root: Path, relative_path: str) -> Path:
    rel = PurePosixPath(relative_path)
    if rel.is_absolute() or ".." in rel.parts or "\\" in relative_path:
        raise ContractValidationError("artifact path is not canonical repo-relative")
    path = (root / Path(*rel.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ContractValidationError("artifact path escaped repository root") from exc
    return path


def _write_once(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise ContractValidationError(f"artifact already exists: {path.name}") from exc
    return hashlib.sha256(data).hexdigest()


def build_manifest_and_validation_v2r1(repository_root: Path) -> tuple[ManifestV2R1, ValidationV2R1, str, str]:
    root = repository_root.resolve(strict=True)
    manifest = FROZEN_MANIFEST_V2R1
    validation = build_validation_v2r1(root, manifest)
    manifest_bytes = render_contract_v2r1(manifest)
    validation_bytes = render_contract_v2r1(validation)
    manifest_path = _safe_path(root, MANIFEST_RELATIVE_PATH_V2R1)
    validation_path = _safe_path(root, VALIDATION_RELATIVE_PATH_V2R1)
    manifest_sha = _write_once(manifest_path, manifest_bytes)
    try:
        validation_sha = _write_once(validation_path, validation_bytes)
    except Exception:
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest, validation, manifest_sha, validation_sha


def revalidate_manifest_evidence_v2r1(repository_root: Path) -> RevalidationV2R1:
    root = repository_root.resolve(strict=True)
    manifest_path = _safe_path(root, MANIFEST_RELATIVE_PATH_V2R1)
    validation_path = _safe_path(root, VALIDATION_RELATIVE_PATH_V2R1)
    revalidation_path = _safe_path(root, REVALIDATION_RELATIVE_PATH_V2R1)
    if not manifest_path.is_file() or not validation_path.is_file():
        raise ContractValidationError("manifest/validation artifacts are missing")
    persisted_manifest_bytes = manifest_path.read_bytes()
    persisted_validation_bytes = validation_path.read_bytes()
    persisted_manifest = ManifestV2R1.model_validate_json(persisted_manifest_bytes)
    persisted_validation = ValidationV2R1.model_validate_json(persisted_validation_bytes)
    recomputed_manifest = FROZEN_MANIFEST_V2R1
    recomputed_validation = build_validation_v2r1(root, recomputed_manifest)
    recomputed_manifest_bytes = render_contract_v2r1(recomputed_manifest)
    recomputed_validation_bytes = render_contract_v2r1(recomputed_validation)
    if persisted_manifest != recomputed_manifest:
        raise ContractValidationError("persisted manifest semantic content diverged")
    if persisted_validation != recomputed_validation:
        raise ContractValidationError("persisted validation semantic content diverged")
    if persisted_manifest_bytes != recomputed_manifest_bytes:
        raise ContractValidationError("persisted manifest bytes diverged")
    if persisted_validation_bytes != recomputed_validation_bytes:
        raise ContractValidationError("persisted validation bytes diverged")
    result = RevalidationV2R1(
        source_manifest_id=persisted_manifest.manifest_id or "",
        source_manifest_sha256=sha256_bytes_v2r1(persisted_manifest_bytes),
        source_validation_id=persisted_validation.validation_id or "",
        source_validation_sha256=sha256_bytes_v2r1(persisted_validation_bytes),
        recomputed_manifest_id=recomputed_manifest.manifest_id or "",
        recomputed_validation_id=recomputed_validation.validation_id or "",
    )
    _write_once(revalidation_path, render_contract_v2r1(result))
    return result


def _parse(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--revalidate", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse(argv)
    try:
        if args.revalidate:
            result = revalidate_manifest_evidence_v2r1(args.root)
            payload = {
                "mode": "revalidate",
                "revalidation_id": result.revalidation_id,
                "status": "PASS",
            }
        else:
            manifest, validation, manifest_sha, validation_sha = build_manifest_and_validation_v2r1(args.root)
            payload = {
                "mode": "build",
                "manifest_id": manifest.manifest_id,
                "manifest_sha256": manifest_sha,
                "validation_id": validation.validation_id,
                "validation_sha256": validation_sha,
                "hypothesis_status": validation.hypothesis_status.value,
                "failure_reasons": list(validation.failure_reasons),
            }
    except (ContractValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": type(exc).__name__, "message": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

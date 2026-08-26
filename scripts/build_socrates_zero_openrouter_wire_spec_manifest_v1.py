"""Build and offline-revalidate OpenRouter wire specification manifest v1."""

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

from backend.dialogues.socrates_zero.contracts import ContractValidationError, canonical_json
from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v1 import (
    OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1,
    OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1,
    OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1,
    PREDECESSOR_MANIFEST_V0_FILE_SHA256,
    SEALED_ROUTE_CONTROLS_V1_SHA256,
    OpenRouterWireManifestRevalidationV1,
    OpenRouterWireManifestValidationV1,
    OpenRouterWireSpecificationManifestV1,
    build_openrouter_wire_manifest_validation_v1,
    build_openrouter_wire_specification_manifest_v1,
    render_contract_v1,
    sha256_bytes_v1,
)
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1,
    OpenRouterWireRetrievalLogV1,
)


PREDECESSOR_MANIFEST_V0_RELATIVE_PATH = (
    "docs/branches/feature-socrates-zero-openrouter-spec-evidence-gate-v0/"
    "evidence/openrouter_official_specification_evidence_v0.json"
)
SEALED_ROUTE_CONTROLS_V1_RELATIVE_PATH = (
    "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/"
    "artifacts/socrateszero_openrouter_route_controls_v1.json"
)


def _safe_path(root: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ContractValidationError("manifest output path is unsafe")
    destination = root.joinpath(*relative.parts)
    resolved_root = root.resolve(strict=True)
    resolved_parent = destination.parent.resolve(strict=False)
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise ContractValidationError("manifest output path escapes repository root")
    return destination


def _write_once(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ContractValidationError("write-once manifest destination already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()


def _verify_file_hash(root: Path, relative_path: str, expected: str) -> None:
    path = _safe_path(root, relative_path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ContractValidationError(f"sealed predecessor hash mismatch: {relative_path}")


def _load_retrieval_log(root: Path) -> tuple[OpenRouterWireRetrievalLogV1, bytes]:
    path = _safe_path(root, OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1)
    if not path.is_file():
        raise ContractValidationError("retrieval log is missing")
    rendered = path.read_bytes()
    return OpenRouterWireRetrievalLogV1.model_validate_json(rendered), rendered


def build_manifest_and_validation(root: Path) -> tuple[
    OpenRouterWireSpecificationManifestV1,
    OpenRouterWireManifestValidationV1,
    str,
    str,
]:
    repository_root = root.resolve(strict=True)
    _verify_file_hash(
        repository_root,
        PREDECESSOR_MANIFEST_V0_RELATIVE_PATH,
        PREDECESSOR_MANIFEST_V0_FILE_SHA256,
    )
    _verify_file_hash(
        repository_root,
        SEALED_ROUTE_CONTROLS_V1_RELATIVE_PATH,
        SEALED_ROUTE_CONTROLS_V1_SHA256,
    )
    retrieval_log, retrieval_bytes = _load_retrieval_log(repository_root)
    retrieval_sha = sha256_bytes_v1(retrieval_bytes)
    manifest = build_openrouter_wire_specification_manifest_v1(
        retrieval_log=retrieval_log,
        retrieval_log_sha256=retrieval_sha,
    )
    manifest_bytes = render_contract_v1(manifest)
    manifest_sha = sha256_bytes_v1(manifest_bytes)
    validation = build_openrouter_wire_manifest_validation_v1(
        manifest=manifest,
        manifest_sha256=manifest_sha,
        retrieval_log=retrieval_log,
    )
    validation_bytes = render_contract_v1(validation)
    validation_sha = sha256_bytes_v1(validation_bytes)

    manifest_path = _safe_path(repository_root, OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1)
    validation_path = _safe_path(repository_root, OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1)
    if manifest_path.exists() or validation_path.exists():
        raise ContractValidationError("authoritative manifest evidence already exists")
    _write_once(manifest_path, manifest_bytes)
    _write_once(validation_path, validation_bytes)
    return manifest, validation, manifest_sha, validation_sha


def revalidate_manifest_evidence(root: Path) -> OpenRouterWireManifestRevalidationV1:
    repository_root = root.resolve(strict=True)
    manifest_path = _safe_path(repository_root, OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1)
    validation_path = _safe_path(repository_root, OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1)
    revalidation_path = _safe_path(repository_root, OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1)
    if revalidation_path.exists():
        raise ContractValidationError("write-once revalidation destination already exists")
    manifest_bytes = manifest_path.read_bytes()
    validation_bytes = validation_path.read_bytes()
    source_manifest = OpenRouterWireSpecificationManifestV1.model_validate_json(
        manifest_bytes
    )
    source_validation = OpenRouterWireManifestValidationV1.model_validate_json(
        validation_bytes
    )
    retrieval_log, retrieval_bytes = _load_retrieval_log(repository_root)
    recomputed_manifest = build_openrouter_wire_specification_manifest_v1(
        retrieval_log=retrieval_log,
        retrieval_log_sha256=sha256_bytes_v1(retrieval_bytes),
    )
    recomputed_manifest_bytes = render_contract_v1(recomputed_manifest)
    recomputed_validation = build_openrouter_wire_manifest_validation_v1(
        manifest=recomputed_manifest,
        manifest_sha256=sha256_bytes_v1(recomputed_manifest_bytes),
        retrieval_log=retrieval_log,
    )
    recomputed_validation_bytes = render_contract_v1(recomputed_validation)
    if source_manifest != recomputed_manifest or source_validation != recomputed_validation:
        raise ContractValidationError("offline manifest semantic revalidation diverged")
    if manifest_bytes != recomputed_manifest_bytes or validation_bytes != recomputed_validation_bytes:
        raise ContractValidationError("offline manifest byte revalidation diverged")
    revalidation = OpenRouterWireManifestRevalidationV1(
        source_manifest_id=source_manifest.manifest_id or "",
        source_manifest_sha256=sha256_bytes_v1(manifest_bytes),
        recomputed_manifest_id=recomputed_manifest.manifest_id or "",
        recomputed_manifest_sha256=sha256_bytes_v1(recomputed_manifest_bytes),
        source_validation_id=source_validation.validation_id or "",
        source_validation_sha256=sha256_bytes_v1(validation_bytes),
        recomputed_validation_id=recomputed_validation.validation_id or "",
        recomputed_validation_sha256=sha256_bytes_v1(recomputed_validation_bytes),
    )
    _write_once(revalidation_path, render_contract_v1(revalidation))
    return revalidation


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "revalidate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        if args.mode == "build":
            manifest, validation, manifest_sha, validation_sha = (
                build_manifest_and_validation(args.root)
            )
            summary = {
                "manifest_id": manifest.manifest_id,
                "manifest_sha256": manifest_sha,
                "validation_id": validation.validation_id,
                "validation_sha256": validation_sha,
                "hypothesis_status": validation.hypothesis_status.value,
                "failure_reasons": validation.metrics.failure_reasons,
            }
        else:
            revalidation = revalidate_manifest_evidence(args.root)
            summary = {
                "revalidation_id": revalidation.revalidation_id,
                "semantic_equality": revalidation.semantic_equality,
                "manifest_byte_identity": revalidation.manifest_byte_identity,
                "validation_byte_identity": revalidation.validation_byte_identity,
            }
    except (ContractValidationError, OSError, ValueError) as exc:
        sys.stderr.write(f"manifest operation failed: {type(exc).__name__}\n")
        return 2
    sys.stdout.write(canonical_json(summary) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

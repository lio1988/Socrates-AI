"""Run one local-network recovery of the sealed six-source plan.

The original Phase 8.5D-S retrieval and artifacts remain immutable. This
wrapper reuses the frozen v1 source plan and retriever but publishes a distinct
retrieval log and recovery receipt. It never overwrites the sealed v1 log and
never performs a second retrieval after the v1r1 log exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Optional, Sequence

if __package__ in (None, ""):
    _repository_root = Path(__file__).resolve().parents[1]
    if str(_repository_root) not in sys.path:
        sys.path.insert(0, str(_repository_root))

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_wire_spec_recovery_v1r1 import (
    OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1,
    OPENROUTER_WIRE_RETRIEVAL_RECOVERY_RECEIPT_RELATIVE_PATH_V1R1,
    OpenRouterWireRetrievalRecoveryReceiptV1R1,
    OpenRouterWireRetrievalRecoveryStatusV1R1,
    build_openrouter_wire_retrieval_recovery_receipt_v1r1,
    render_openrouter_wire_retrieval_recovery_receipt_v1r1,
    sha256_file_v1r1,
    verify_openrouter_wire_retrieval_recovery_receipt_v1r1,
    verify_sealed_recovery_predecessors_v1r1,
)
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    OpenRouterWireRetrievalLogV1,
)
from scripts import acquire_socrates_zero_openrouter_wire_spec_sources_v1 as v1


def _within_root(root: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in relative_path:
        raise ContractValidationError("recovery output path is not repo-relative")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractValidationError("recovery output escaped repository root") from exc
    return candidate


def _write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _load_retrieval_log(path: Path) -> OpenRouterWireRetrievalLogV1:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError("persisted recovery retrieval log is invalid") from exc
    return OpenRouterWireRetrievalLogV1.model_validate(payload)


def _load_receipt(path: Path) -> OpenRouterWireRetrievalRecoveryReceiptV1R1:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError("persisted recovery receipt is invalid") from exc
    return OpenRouterWireRetrievalRecoveryReceiptV1R1.model_validate(payload)


def _finalize_existing(
    root: Path,
    log_path: Path,
    receipt_path: Path,
) -> OpenRouterWireRetrievalRecoveryReceiptV1R1:
    retrieval_log = _load_retrieval_log(log_path)
    receipt = build_openrouter_wire_retrieval_recovery_receipt_v1r1(
        retrieval_log=retrieval_log,
        retrieval_log_file_sha256=sha256_file_v1r1(log_path),
        retrieval_log_file_bytes=log_path.stat().st_size,
    )
    rendered = render_openrouter_wire_retrieval_recovery_receipt_v1r1(receipt)
    if receipt_path.exists():
        persisted = _load_receipt(receipt_path)
        verify_openrouter_wire_retrieval_recovery_receipt_v1r1(
            receipt=persisted,
            retrieval_log=retrieval_log,
            retrieval_log_file_sha256=sha256_file_v1r1(log_path),
            retrieval_log_file_bytes=log_path.stat().st_size,
        )
        if receipt_path.read_bytes() != rendered:
            raise ContractValidationError("persisted recovery receipt bytes diverge")
        return persisted
    _write_once(receipt_path, rendered)
    return receipt


def execute_openrouter_wire_source_retrieval_recovery_v1r1(
    repository_root: Path,
) -> OpenRouterWireRetrievalRecoveryReceiptV1R1:
    root = repository_root.resolve(strict=True)
    verify_sealed_recovery_predecessors_v1r1(root)
    log_path = _within_root(root, OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1)
    receipt_path = _within_root(
        root, OPENROUTER_WIRE_RETRIEVAL_RECOVERY_RECEIPT_RELATIVE_PATH_V1R1
    )

    if log_path.exists():
        return _finalize_existing(root, log_path, receipt_path)
    if receipt_path.exists():
        raise ContractValidationError("recovery receipt exists without retrieval log")

    original_log_path = v1.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1
    try:
        v1.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1 = (
            OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1
        )
        retrieval_log = v1.acquire_openrouter_wire_spec_sources_v1(root)
    finally:
        v1.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1 = original_log_path

    if not log_path.is_file():
        raise ContractValidationError("recovery retrieval did not publish its log")
    reparsed = _load_retrieval_log(log_path)
    if reparsed != retrieval_log:
        raise ContractValidationError("published recovery retrieval log diverges")
    return _finalize_existing(root, log_path, receipt_path)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or offline-finalize one versioned recovery of the frozen "
            "OpenRouter six-source retrieval plan."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root on the frozen recovery branch.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        receipt = execute_openrouter_wire_source_retrieval_recovery_v1r1(args.root)
    except (ContractValidationError, OSError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "socrateszero-openrouter-wire-retrieval-recovery-cli/v1r1",
                    "status": "FAILED_CLOSED",
                    "error": type(exc).__name__,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    print(json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True))
    return (
        0
        if receipt.recovery_status
        is OpenRouterWireRetrievalRecoveryStatusV1R1.COMPLETE
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())

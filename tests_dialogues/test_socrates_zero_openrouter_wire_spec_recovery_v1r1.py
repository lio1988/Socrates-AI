from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_wire_spec_recovery_v1r1 import (
    FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1,
    OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1,
    OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BASE_HEAD_V1R1,
    OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BRANCH_V1R1,
    OpenRouterWireRetrievalRecoveryReceiptV1R1,
    OpenRouterWireRetrievalRecoveryStatusV1R1,
    build_openrouter_wire_retrieval_recovery_receipt_v1r1,
    render_openrouter_wire_retrieval_recovery_receipt_v1r1,
    verify_openrouter_wire_retrieval_recovery_receipt_v1r1,
    verify_sealed_recovery_predecessors_v1r1,
)
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
    OpenRouterWireRetrievalLogV1,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OLD_LOG = (
    REPOSITORY_ROOT
    / "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/openrouter_wire_retrieval_log_v1.json"
)


def _old_log() -> OpenRouterWireRetrievalLogV1:
    return OpenRouterWireRetrievalLogV1.model_validate(
        json.loads(OLD_LOG.read_text(encoding="utf-8"))
    )


def test_recovery_is_new_lineage_over_exact_six_source_plan() -> None:
    assert OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BRANCH_V1R1.endswith("v1r1")
    assert OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BASE_HEAD_V1R1 == (
        "a37e6c0068e3132ca49128295a5ef8453f91592c"
    )
    assert len(FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records) == 6
    assert OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1.endswith(
        "openrouter_wire_retrieval_log_v1r1.json"
    )
    assert "openrouter_wire_retrieval_log_v1.json" not in (
        OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1
    )


def test_all_sealed_predecessor_files_match_snapshot() -> None:
    assert verify_sealed_recovery_predecessors_v1r1(REPOSITORY_ROOT) == (
        FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1
    )


def test_incomplete_receipt_is_deterministic_and_does_not_promote() -> None:
    log = _old_log()
    rendered_log = OLD_LOG.read_bytes()
    receipt = build_openrouter_wire_retrieval_recovery_receipt_v1r1(
        retrieval_log=log,
        retrieval_log_file_sha256=hashlib.sha256(rendered_log).hexdigest(),
        retrieval_log_file_bytes=len(rendered_log),
    )
    assert receipt.recovery_status is OpenRouterWireRetrievalRecoveryStatusV1R1.INCOMPLETE
    assert receipt.retained_source_count == 0
    assert receipt.failed_source_count == 6
    assert receipt.next_decision == "RETURN_TO_ARCHITECTURE_DECISION"
    assert receipt.seventh_or_substitute_source_used is False
    assert receipt.authenticated_api_calls == 0
    assert receipt.credential_accesses == 0
    assert receipt.provider_inference_calls == 0
    assert receipt.model_executions == 0
    assert receipt.paid_requests == 0
    assert receipt.ced_runtime_tool_calls == 0
    reparsed = OpenRouterWireRetrievalRecoveryReceiptV1R1.model_validate_json(
        render_openrouter_wire_retrieval_recovery_receipt_v1r1(receipt)
    )
    assert reparsed == receipt


def test_receipt_counts_and_decision_are_not_caller_controlled() -> None:
    log = _old_log()
    raw = OLD_LOG.read_bytes()
    receipt = build_openrouter_wire_retrieval_recovery_receipt_v1r1(
        retrieval_log=log,
        retrieval_log_file_sha256=hashlib.sha256(raw).hexdigest(),
        retrieval_log_file_bytes=len(raw),
    )
    payload = receipt.model_dump(mode="json")
    payload["retained_source_count"] = 6
    payload["failed_source_count"] = 0
    payload["recovery_status"] = "COMPLETE"
    payload["next_decision"] = "BUILD_MANIFEST_FROM_RECOVERY_EVIDENCE"
    payload["recovery_receipt_id"] = None
    with pytest.raises((ContractValidationError, ValueError)):
        OpenRouterWireRetrievalRecoveryReceiptV1R1.model_validate(payload)


def test_sealed_lock_tamper_is_rejected(tmp_path: Path) -> None:
    for lock in FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1:
        target = tmp_path / lock.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        source = REPOSITORY_ROOT / lock.relative_path
        target.write_bytes(source.read_bytes())
    first = FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1[0]
    (tmp_path / first.relative_path).write_bytes(b"tampered\n")
    with pytest.raises(ContractValidationError):
        verify_sealed_recovery_predecessors_v1r1(tmp_path)


def _copy_sealed_recovery_root(destination: Path) -> None:
    for lock in FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1:
        target = destination / lock.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPOSITORY_ROOT / lock.relative_path).read_bytes())


def test_recovery_wrapper_uses_new_log_path_once_and_then_finalizes_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.dialogues.socrates_zero.openrouter_wire_spec_recovery_v1r1 import (
        OPENROUTER_WIRE_RETRIEVAL_RECOVERY_RECEIPT_RELATIVE_PATH_V1R1,
    )
    from scripts import (
        acquire_socrates_zero_openrouter_wire_spec_sources_v1 as v1_script,
    )
    from scripts.acquire_socrates_zero_openrouter_wire_spec_sources_v1r1 import (
        execute_openrouter_wire_source_retrieval_recovery_v1r1,
    )

    _copy_sealed_recovery_root(tmp_path)
    old_path = v1_script.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1
    calls: list[str] = []
    old_log = _old_log()
    old_bytes = OLD_LOG.read_bytes()

    def fake_acquire(root: Path) -> OpenRouterWireRetrievalLogV1:
        calls.append(v1_script.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1)
        target = root / v1_script.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(old_bytes)
        return old_log

    monkeypatch.setattr(v1_script, "acquire_openrouter_wire_spec_sources_v1", fake_acquire)
    receipt = execute_openrouter_wire_source_retrieval_recovery_v1r1(tmp_path)
    assert calls == [OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1]
    assert v1_script.OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1 == old_path
    assert receipt.recovery_status is OpenRouterWireRetrievalRecoveryStatusV1R1.INCOMPLETE
    receipt_path = tmp_path / OPENROUTER_WIRE_RETRIEVAL_RECOVERY_RECEIPT_RELATIVE_PATH_V1R1
    assert receipt_path.is_file()

    again = execute_openrouter_wire_source_retrieval_recovery_v1r1(tmp_path)
    assert again == receipt
    assert calls == [OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1]

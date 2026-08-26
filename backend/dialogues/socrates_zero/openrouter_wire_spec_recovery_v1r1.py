"""Versioned recovery receipt for the frozen OpenRouter wire-source plan.

This module is offline and import-inert.  It does not retrieve documents.  It
binds one new retrieval execution to the already sealed six-source plan and to
the falsified Phase 8.5D-S evidence lineage.  The recovery changes only the
execution environment; source membership, extraction rules, resource limits,
and all authority boundaries remain frozen.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_wire_spec_source_v1 import (
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
    OpenRouterWireRetrievalLogV1,
    OpenRouterWireRetrievalStatusV1,
)


OPENROUTER_WIRE_RETRIEVAL_RECOVERY_SCHEMA_V1R1 = (
    "socrateszero-openrouter-wire-retrieval-recovery/v1r1"
)
OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCK_SCHEMA_V1R1 = (
    "socrateszero-openrouter-wire-retrieval-recovery-file-lock/v1r1"
)
OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BRANCH_V1R1 = (
    "feature/socrates-zero-openrouter-wire-source-retrieval-v1r1"
)
OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BASE_HEAD_V1R1 = (
    "a37e6c0068e3132ca49128295a5ef8453f91592c"
)
OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/openrouter_wire_retrieval_log_v1r1.json"
)
OPENROUTER_WIRE_RETRIEVAL_RECOVERY_RECEIPT_RELATIVE_PATH_V1R1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-source-retrieval-v1r1/"
    "evidence/openrouter_wire_retrieval_recovery_receipt_v1r1.json"
)
OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1R1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/sources"
)
OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1R1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/openrouter_wire_source_plan_v1.json"
)
OPENROUTER_WIRE_SOURCE_PLAN_FILE_SHA256_V1R1 = (
    "cfaec71b93a88114e9378fe297d8cd5ec9645e6c747877eadd622003de9760a5"
)
OPENROUTER_WIRE_SOURCE_PLAN_FILE_BYTES_V1R1 = 9030
OPENROUTER_WIRE_RETRIEVAL_RECOVERY_ENVIRONMENT_V1R1 = (
    "WINDOWS_LOCAL_PUBLIC_DOCUMENT_RETRIEVAL"
)


class _FrozenRecoveryContractV1R1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterWireRetrievalRecoveryStatusV1R1(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class OpenRouterWireRetrievalRecoveryFileLockV1R1(_FrozenRecoveryContractV1R1):
    schema_version: Literal[
        OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCK_SCHEMA_V1R1
    ] = OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCK_SCHEMA_V1R1
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_path(self) -> "OpenRouterWireRetrievalRecoveryFileLockV1R1":
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not self.relative_path.strip()
            or "\\" in self.relative_path
        ):
            raise ContractValidationError("sealed recovery path is not repo-relative")
        return self


FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1: Tuple[
    OpenRouterWireRetrievalRecoveryFileLockV1R1, ...
] = (
    OpenRouterWireRetrievalRecoveryFileLockV1R1(
        relative_path=OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1R1,
        sha256=OPENROUTER_WIRE_SOURCE_PLAN_FILE_SHA256_V1R1,
        byte_length=OPENROUTER_WIRE_SOURCE_PLAN_FILE_BYTES_V1R1,
    ),
    OpenRouterWireRetrievalRecoveryFileLockV1R1(
        relative_path=(
            "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
            "evidence/openrouter_wire_retrieval_log_v1.json"
        ),
        sha256="8e9a6ecfe41c444323cf01c0e8d6d11ad1fd1e09d5400c14b5bf4c63278d5fd3",
        byte_length=4828,
    ),
    OpenRouterWireRetrievalRecoveryFileLockV1R1(
        relative_path=(
            "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
            "evidence/openrouter_official_wire_specification_manifest_v1.json"
        ),
        sha256="cafd9364db1357b9aa676a7b45baeac2ef8a9f1b4288044fbaed95fcb3d4397b",
        byte_length=13739,
    ),
    OpenRouterWireRetrievalRecoveryFileLockV1R1(
        relative_path=(
            "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
            "artifacts/openrouter_wire_specification_manifest_validation_v1.json"
        ),
        sha256="26c4616bb6b07ca3e5d2d0a1385c2d10aa8e9d523f90ca2c87d9872dc2ee4bc7",
        byte_length=1824,
    ),
    OpenRouterWireRetrievalRecoveryFileLockV1R1(
        relative_path=(
            "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
            "artifacts/openrouter_wire_specification_manifest_revalidation_v1.json"
        ),
        sha256="c389c1816b364e787ba5270b121fdeb820a7426182f6d1d69e6a51aa796f187b",
        byte_length=1361,
    ),
    OpenRouterWireRetrievalRecoveryFileLockV1R1(
        relative_path="docs/SOCRATES_ZERO_OPENROUTER_WIRE_SPECIFICATION_MANIFEST_V1.md",
        sha256="b2fa8c5ffa8a5ceef1f127d3f7fa1a01800cc121c6d6d35f94e6c8b485e4121d",
        byte_length=13420,
    ),
)


class OpenRouterWireRetrievalRecoveryReceiptV1R1(_FrozenRecoveryContractV1R1):
    schema_version: Literal[
        OPENROUTER_WIRE_RETRIEVAL_RECOVERY_SCHEMA_V1R1
    ] = OPENROUTER_WIRE_RETRIEVAL_RECOVERY_SCHEMA_V1R1
    recovery_receipt_id: Optional[str] = None
    branch: Literal[
        OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BRANCH_V1R1
    ] = OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BRANCH_V1R1
    base_head: Literal[
        OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BASE_HEAD_V1R1
    ] = OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BASE_HEAD_V1R1
    execution_environment: Literal[
        OPENROUTER_WIRE_RETRIEVAL_RECOVERY_ENVIRONMENT_V1R1
    ] = OPENROUTER_WIRE_RETRIEVAL_RECOVERY_ENVIRONMENT_V1R1
    predecessor_hypothesis_status: Literal["FALSIFIED"] = "FALSIFIED"
    predecessor_failure_cause: Literal[
        "SIX_NETWORK_ERRORS_BEFORE_OFFICIAL_SOURCE_BYTES"
    ] = "SIX_NETWORK_ERRORS_BEFORE_OFFICIAL_SOURCE_BYTES"
    source_plan_id: Literal[
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    ] = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    source_plan_file_sha256: Literal[
        OPENROUTER_WIRE_SOURCE_PLAN_FILE_SHA256_V1R1
    ] = OPENROUTER_WIRE_SOURCE_PLAN_FILE_SHA256_V1R1
    source_plan_file_bytes: Literal[
        OPENROUTER_WIRE_SOURCE_PLAN_FILE_BYTES_V1R1
    ] = OPENROUTER_WIRE_SOURCE_PLAN_FILE_BYTES_V1R1
    source_count: Literal[6] = 6
    seventh_or_substitute_source_used: Literal[False] = False
    retrieval_log_path: Literal[
        OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1
    ] = OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1
    retrieval_log_id: str
    retrieval_log_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_log_file_bytes: int = Field(ge=1)
    retrieval_event_ids: Tuple[str, ...]
    retained_snapshot_ids: Tuple[str, ...]
    retained_source_directory: Literal[
        OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1R1
    ] = OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1R1
    retained_source_count: int = Field(ge=0, le=6)
    failed_source_count: int = Field(ge=0, le=6)
    official_public_document_fetches: Literal[6] = 6
    official_public_page_inspections: Literal[0] = 0
    retry_count: Literal[0] = 0
    authenticated_api_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    paid_requests: Literal[0] = 0
    ced_runtime_tool_calls: Literal[0] = 0
    sealed_predecessor_file_locks: Tuple[
        OpenRouterWireRetrievalRecoveryFileLockV1R1, ...
    ] = FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1
    recovery_status: OpenRouterWireRetrievalRecoveryStatusV1R1
    next_decision: Literal[
        "BUILD_MANIFEST_FROM_RECOVERY_EVIDENCE",
        "RETURN_TO_ARCHITECTURE_DECISION",
    ]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRetrievalRecoveryReceiptV1R1":
        if len(self.retrieval_event_ids) != self.source_count:
            raise ContractValidationError("recovery event IDs do not cover the source plan")
        if len(set(self.retrieval_event_ids)) != len(self.retrieval_event_ids):
            raise ContractValidationError("recovery event IDs are duplicated")
        if len(self.retained_snapshot_ids) != self.retained_source_count:
            raise ContractValidationError("recovery snapshot IDs do not match retained count")
        if len(set(self.retained_snapshot_ids)) != len(self.retained_snapshot_ids):
            raise ContractValidationError("recovery snapshot IDs are duplicated")
        if self.retained_source_count + self.failed_source_count != self.source_count:
            raise ContractValidationError("recovery counts do not cover the source plan")
        expected_status = (
            OpenRouterWireRetrievalRecoveryStatusV1R1.COMPLETE
            if self.retained_source_count == self.source_count
            else OpenRouterWireRetrievalRecoveryStatusV1R1.INCOMPLETE
        )
        expected_decision = (
            "BUILD_MANIFEST_FROM_RECOVERY_EVIDENCE"
            if expected_status is OpenRouterWireRetrievalRecoveryStatusV1R1.COMPLETE
            else "RETURN_TO_ARCHITECTURE_DECISION"
        )
        if self.recovery_status is not expected_status:
            raise ContractValidationError("recovery status is not count-derived")
        if self.next_decision != expected_decision:
            raise ContractValidationError("recovery decision is not status-derived")
        if self.sealed_predecessor_file_locks != (
            FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1
        ):
            raise ContractValidationError("sealed predecessor lock set changed")
        expected = stable_contract_id(
            "szorwireretrievalrecoveryv1r1",
            self.model_dump(mode="json", exclude={"recovery_receipt_id"}),
        )
        if self.recovery_receipt_id not in (None, expected):
            raise ContractValidationError("recovery receipt ID mismatch")
        object.__setattr__(self, "recovery_receipt_id", expected)
        return self


def sha256_file_v1r1(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sealed_recovery_predecessors_v1r1(
    repository_root: Path,
) -> Tuple[OpenRouterWireRetrievalRecoveryFileLockV1R1, ...]:
    root = repository_root.resolve(strict=True)
    observed: list[OpenRouterWireRetrievalRecoveryFileLockV1R1] = []
    for lock in FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1:
        candidate = (root / PurePosixPath(lock.relative_path)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ContractValidationError("sealed file escaped repository root") from exc
        if not candidate.is_file():
            raise ContractValidationError(
                f"sealed predecessor file is missing: {lock.relative_path}"
            )
        observed_lock = OpenRouterWireRetrievalRecoveryFileLockV1R1(
            relative_path=lock.relative_path,
            sha256=sha256_file_v1r1(candidate),
            byte_length=candidate.stat().st_size,
        )
        if observed_lock != lock:
            raise ContractValidationError(
                f"sealed predecessor file changed: {lock.relative_path}"
            )
        observed.append(observed_lock)
    return tuple(observed)


def build_openrouter_wire_retrieval_recovery_receipt_v1r1(
    *,
    retrieval_log: OpenRouterWireRetrievalLogV1,
    retrieval_log_file_sha256: str,
    retrieval_log_file_bytes: int,
) -> OpenRouterWireRetrievalRecoveryReceiptV1R1:
    retained = sum(
        event.status is OpenRouterWireRetrievalStatusV1.RETAINED
        for event in retrieval_log.events
    )
    failed = len(retrieval_log.events) - retained
    status = (
        OpenRouterWireRetrievalRecoveryStatusV1R1.COMPLETE
        if retained == 6
        else OpenRouterWireRetrievalRecoveryStatusV1R1.INCOMPLETE
    )
    return OpenRouterWireRetrievalRecoveryReceiptV1R1(
        retrieval_log_id=retrieval_log.retrieval_log_id or "",
        retrieval_log_file_sha256=retrieval_log_file_sha256,
        retrieval_log_file_bytes=retrieval_log_file_bytes,
        retrieval_event_ids=tuple(event.event_id or "" for event in retrieval_log.events),
        retained_snapshot_ids=tuple(snapshot.snapshot_id or "" for snapshot in retrieval_log.snapshots),
        retained_source_count=retained,
        failed_source_count=failed,
        recovery_status=status,
        next_decision=(
            "BUILD_MANIFEST_FROM_RECOVERY_EVIDENCE"
            if status is OpenRouterWireRetrievalRecoveryStatusV1R1.COMPLETE
            else "RETURN_TO_ARCHITECTURE_DECISION"
        ),
    )


def verify_openrouter_wire_retrieval_recovery_receipt_v1r1(
    *,
    receipt: OpenRouterWireRetrievalRecoveryReceiptV1R1,
    retrieval_log: OpenRouterWireRetrievalLogV1,
    retrieval_log_file_sha256: str,
    retrieval_log_file_bytes: int,
) -> OpenRouterWireRetrievalRecoveryReceiptV1R1:
    expected = build_openrouter_wire_retrieval_recovery_receipt_v1r1(
        retrieval_log=retrieval_log,
        retrieval_log_file_sha256=retrieval_log_file_sha256,
        retrieval_log_file_bytes=retrieval_log_file_bytes,
    )
    if receipt != expected:
        raise ContractValidationError("recovery receipt does not match retrieval evidence")
    return receipt


def render_openrouter_wire_retrieval_recovery_receipt_v1r1(
    receipt: OpenRouterWireRetrievalRecoveryReceiptV1R1,
) -> bytes:
    return (canonical_json(receipt.model_dump(mode="json")) + "\n").encode("utf-8")


__all__ = [
    "FROZEN_OPENROUTER_WIRE_RETRIEVAL_RECOVERY_FILE_LOCKS_V1R1",
    "OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1R1",
    "OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1R1",
    "OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BASE_HEAD_V1R1",
    "OPENROUTER_WIRE_RETRIEVAL_RECOVERY_BRANCH_V1R1",
    "OPENROUTER_WIRE_RETRIEVAL_RECOVERY_RECEIPT_RELATIVE_PATH_V1R1",
    "OpenRouterWireRetrievalRecoveryFileLockV1R1",
    "OpenRouterWireRetrievalRecoveryReceiptV1R1",
    "OpenRouterWireRetrievalRecoveryStatusV1R1",
    "build_openrouter_wire_retrieval_recovery_receipt_v1r1",
    "render_openrouter_wire_retrieval_recovery_receipt_v1r1",
    "sha256_file_v1r1",
    "verify_openrouter_wire_retrieval_recovery_receipt_v1r1",
    "verify_sealed_recovery_predecessors_v1r1",
]

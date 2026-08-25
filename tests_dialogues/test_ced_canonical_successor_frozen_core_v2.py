"""Pre-result locks for the Phase 8 v2 frozen implementation lineage."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from backend.dialogues.ced_canonical_successor_frozen_core_v2 import (
    CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_SCHEMA_VERSION,
    FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2,
    SEALED_PHASE8_ARTIFACT_ID,
    SEALED_PHASE8_ARTIFACT_SHA256,
    CanonicalSuccessorCoreBlobLockV2,
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SEALED_ARTIFACT = (
    REPOSITORY_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-canonical-successor-env-v0"
    / "artifacts"
    / "socrateszero_canonical_successor_parity_v1.json"
)


def test_core_blob_lock_freezes_complete_audited_lineage() -> None:
    lock = FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2
    paths = {item.path for item in lock.core_blobs}

    assert lock.schema_version == CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_SCHEMA_VERSION
    assert len(lock.core_blobs) == 34
    assert lock.lock_id == f"cedcorebloblockv2_{lock.fingerprint}"
    assert {
        "backend/dialogues/ced.py",
        "backend/dialogues/ced_canonical_successor.py",
        "backend/dialogues/ced_canonical_successor_contracts.py",
        "backend/dialogues/ced_canonical_successor_manifest.py",
        "backend/dialogues/ced_canonical_successor_cases_v1.py",
        "backend/dialogues/ced_search_projection.py",
        "backend/dialogues/ced_search_projection_v1.py",
        "backend/dialogues/ced_search_observability_v1.py",
        "backend/dialogues/ced_search_value_v1.py",
        "backend/dialogues/ced_search_value_v1_contracts.py",
        "backend/dialogues/hybrid_authority.py",
        "backend/dialogues/hybrid_epistemic.py",
        "backend/dialogues/hybrid_shadow.py",
        "backend/dialogues/hybrid_support.py",
        "backend/dialogues/socrates_zero/baseline.py",
        "backend/dialogues/socrates_zero/contracts.py",
        "backend/dialogues/socrates_zero/constitution.py",
        "backend/dialogues/socrates_zero/policy.py",
        "backend/dialogues/socrates_zero/puct.py",
        "backend/dialogues/socrates_zero/strategy.py",
        "backend/dialogues/socrates_zero/value.py",
    } <= paths


def test_every_frozen_repository_blob_is_still_byte_exact() -> None:
    lock = FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2

    for entry in lock.core_blobs:
        actual = subprocess.run(
            ["git", "hash-object", "--", entry.path],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == entry.git_blob_id, entry.path

    predecessor = lock.predecessor
    for path, expected in (
        (predecessor.evaluator_path, predecessor.evaluator_git_blob_id),
        (predecessor.artifact_path, predecessor.artifact_git_blob_id),
    ):
        actual = subprocess.run(
            ["git", "hash-object", "--", path],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == expected, path


def test_core_blob_lock_rejects_blob_tampering() -> None:
    lock = FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2
    payload = lock.model_dump(mode="python")
    payload["core_blobs"][0]["git_blob_id"] = "f" * 40

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        CanonicalSuccessorCoreBlobLockV2.model_validate(payload)


def test_sealed_predecessor_bytes_and_identity_remain_exact() -> None:
    lock = FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2
    predecessor = lock.predecessor
    payload = SEALED_ARTIFACT.read_bytes()

    assert predecessor.artifact_id == SEALED_PHASE8_ARTIFACT_ID
    assert predecessor.artifact_status == "FALSIFIED"
    assert hashlib.sha256(payload).hexdigest() == SEALED_PHASE8_ARTIFACT_SHA256
    assert predecessor.artifact_sha256 == SEALED_PHASE8_ARTIFACT_SHA256
    assert SEALED_PHASE8_ARTIFACT_ID.encode("utf-8") in payload
    assert b'"hypothesis_status":"FALSIFIED"' in payload


def test_historical_hash_set_is_exact_and_unique() -> None:
    entries = FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2.historical_artifacts
    actual = {item.name: item.sha256 for item in entries}

    assert actual == {
        "phase5_matched_compute_normalized": (
            "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"
        ),
        "phase7_value_v1_bestofn": (
            "86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637"
        ),
        "phase7_value_v1_primary": (
            "d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca"
        ),
        "phase8_falsified_successor_parity_v1": SEALED_PHASE8_ARTIFACT_SHA256,
    }

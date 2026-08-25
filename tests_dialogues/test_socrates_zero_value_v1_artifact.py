"""Immutable authoritative primary artifact and deterministic replay lock."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.dialogues.ced_search_value_v1_artifact import (
    ValueV1PrimaryArtifact,
    build_primary_artifact,
    render_primary_artifact,
)


_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_PATH = (
    _ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-heuristic-value-v1"
    / "artifacts"
    / "socrateszero_value_v1_primary_v0.json"
)
_ARTIFACT_ID = (
    "szvaluev1artifact_"
    "803646dbfff5a0449309bf4690ddcc8b6e374fe80ab5826d5fc56c749dc27e49"
)
_ARTIFACT_SHA256 = (
    "d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca"
)
_PHASE5_SHA256 = (
    "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"
)


def _load() -> ValueV1PrimaryArtifact:
    raw = _ARTIFACT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _ARTIFACT_SHA256
    return ValueV1PrimaryArtifact.model_validate_json(raw)


def test_first_authoritative_artifact_identity_and_sha_are_locked():
    artifact = _load()
    assert artifact.artifact_id == _ARTIFACT_ID
    assert artifact.primary_decision.passed is True
    assert artifact.primary_decision.decision == "VALUE V1 HYPOTHESIS PASSED"


def test_authoritative_artifact_replays_semantically_and_byte_identically():
    committed = _load()
    replay = build_primary_artifact()
    assert replay == committed
    assert replay.artifact_id == committed.artifact_id
    assert render_primary_artifact(replay).encode("utf-8") \
        == _ARTIFACT_PATH.read_bytes()


def test_primary_holdout_metrics_and_safety_counts_are_exact():
    holdout = _load().holdout_run
    assert holdout.v0_metrics.ordered_correct == 2
    assert holdout.v0_metrics.ordered_pairs == 7
    assert holdout.v0_metrics.ordered_accuracy == 2 / 7
    assert holdout.v1_metrics.ordered_correct == 7
    assert holdout.v1_metrics.ordered_pairs == 7
    assert holdout.v1_metrics.ordered_accuracy == 1.0
    assert holdout.v1_nonterminal_metrics.ordered_accuracy == 1.0
    assert holdout.v1_metrics.required_tie_accuracy == 1.0
    assert holdout.v1_metrics.directional_errors == 0
    assert holdout.v1_metrics.ordered_ties == 0
    assert holdout.v1_metrics.ranking_loss == 0.0
    assert sum(holdout.hard_safety.model_dump(mode="python").values()) == 0


def test_phase5_artifact_remains_sealed_after_primary_holdout():
    path = (
        _ROOT
        / "docs"
        / "branches"
        / "feature-socrates-zero-search-v0"
        / "artifacts"
        / "socrateszero_search_kernel_benchmark_v0.json"
    )
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == _PHASE5_SHA256

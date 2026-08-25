"""Immutable secondary BestOfN artifact and deterministic replay lock."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.dialogues.ced_search_value_v1_bestofn import (
    ValueV1BestOfNArtifact,
    build_bestofn_artifact,
    render_bestofn_artifact,
)


_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_PATH = (
    _ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-heuristic-value-v1"
    / "artifacts"
    / "socrateszero_value_v1_bestofn_v0.json"
)
_ARTIFACT_ID = (
    "szvaluev1bestofnartifact_"
    "c154689cd122f5f7dd68da5d7b31c34b26d049233e6425d3758f56491b11522d"
)
_ARTIFACT_SHA256 = (
    "86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637"
)


def _load() -> ValueV1BestOfNArtifact:
    raw = _ARTIFACT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _ARTIFACT_SHA256
    return ValueV1BestOfNArtifact.model_validate_json(raw)


def test_secondary_artifact_identity_decision_and_sha_are_locked():
    artifact = _load()
    assert artifact.artifact_id == _ARTIFACT_ID
    assert artifact.decision.passed is True
    assert artifact.decision.decision == "VALUE V1 BESTOFN GATE PASSED"


def test_secondary_artifact_replays_semantically_and_byte_identically():
    committed = _load()
    replay = build_bestofn_artifact()
    assert replay == committed
    assert replay.artifact_id == committed.artifact_id
    assert render_bestofn_artifact(replay).encode("utf-8") \
        == _ARTIFACT_PATH.read_bytes()


def test_secondary_metrics_and_resource_guardrails_are_exact():
    artifact = _load()
    decision = artifact.decision
    assert decision.v0_selection_accuracy == 2 / 7
    assert decision.v1_selection_accuracy == 1.0
    assert decision.improvement == 5 / 7
    assert decision.guardrail_regressions == 0
    assert decision.budget_usage_regressions == 0
    assert decision.successor_accounting_regressions == 0
    assert decision.new_failures == 0
    assert all(
        result.v0.usage == result.v1.usage
        for result in artifact.case_results
    )
    assert all(result.v0.usage.nodes == 5 for result in artifact.case_results)
    assert all(result.v0.usage.expansions == 4 for result in artifact.case_results)
    assert all(result.v0.usage.model_calls == 0 for result in artifact.case_results)

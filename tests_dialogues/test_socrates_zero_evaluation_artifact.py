"""Locks the first frozen Phase 5 machine-readable benchmark result."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.dialogues.socrates_zero import (
    BEST_OF_N_STRATEGY_VERSION,
    GREEDY_STRATEGY_VERSION,
    PUCT_STRATEGY_VERSION,
    SearchKernelBenchmarkArtifact,
    run_frozen_matrix,
)


_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_PATH = (
    _ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-search-v0"
    / "artifacts"
    / "socrateszero_search_kernel_benchmark_v0.json"
)
_ARTIFACT_ID = (
    "szevalartifact_"
    "dc795fdef6b64e56b808b990fedd764def7c6e1858d178d29c26aa3280ede710"
)
_ARTIFACT_SHA256 = (
    "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"
)


def _load() -> SearchKernelBenchmarkArtifact:
    raw = _ARTIFACT_PATH.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == _ARTIFACT_SHA256
    return SearchKernelBenchmarkArtifact.model_validate_json(raw)


def test_committed_artifact_replays_from_frozen_harness_byte_semantics():
    committed = _load()
    replay = run_frozen_matrix()

    assert committed.artifact_id == _ARTIFACT_ID
    assert replay == committed
    assert replay.artifact_id == committed.artifact_id
    assert len(committed.runs) == 11
    assert all(len(run.per_case_results) == 20 for run in committed.runs)


def test_primary_matched_compute_result_is_frozen_without_hidden_failures():
    artifact = _load()
    primary = {
        run.identity.strategy_id: run
        for run in artifact.runs
        if run.run_id in artifact.primary_matched_run_ids
    }

    expected = {
        GREEDY_STRATEGY_VERSION: (9, 11.55, 0, 20, 20),
        BEST_OF_N_STRATEGY_VERSION: (15, 4.8, 62, 20, 62),
        PUCT_STRATEGY_VERSION: (15, 4.55, 80, 20, 80),
    }
    for strategy_id, run in primary.items():
        metrics = run.aggregate_metrics
        usage = metrics.resource_usage
        assert (
            metrics.correct_count,
            metrics.total_regret,
            usage.successor_evaluations,
            usage.policy_evaluations,
            usage.value_evaluations,
        ) == expected[strategy_id]
        assert metrics.cases_total == 20
        assert metrics.cases_evaluable == 20
        assert metrics.cases_completed == 20
        assert metrics.cases_failed == 0
        assert metrics.cases_not_evaluable == 0
        assert (usage.nodes, usage.expansions) == (
            usage.successor_evaluations,
            usage.successor_evaluations,
        )
        assert (
            usage.model_calls,
            usage.tool_calls,
            usage.tokens,
            usage.cost_microusd,
            usage.wall_time_ms,
        ) == (0, 0, 0, 0, 0)


def test_trace_observability_does_not_fabricate_counterfactuals():
    traces = _load().trace_observability

    assert traces.traces_total == 2
    assert traces.traces_evaluable == 0
    assert traces.traces_missing_counterfactual == 2
    assert len(traces.missing_fixture_ids) == 2

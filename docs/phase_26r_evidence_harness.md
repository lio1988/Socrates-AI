# Phase 26R — Evidence Harness

Phase 26R compares multiple candidate systems against the same ground-truth task set.

It builds on Phase 26Q ground-truth checks.

## Added

### `backend/dialogues/learning_evidence_harness.py`

Types:

- `CandidateSystemKind`
- `CandidateSystemOutput`
- `SystemEvidenceResult`
- `EvidenceLeaderboardRow`
- `EvidenceHarnessReport`

Helpers:

- `evidence_hash(...)`
- `evaluate_system(...)`
- `build_leaderboard(...)`
- `run_evidence_harness(...)`
- `evidence_harness_summary(...)`

### `tests_dialogues/test_learning_evidence_harness.py`

Tests cover:

- deterministic ids
- conversion to ground-truth candidates
- per-system scoring
- coverage
- missing answers
- leaderboard ranking
- confidence diagnostics
- JSON output

## Purpose

The harness lets us compare:

- CED output
- baseline output
- single-model output
- human output
- other supplied outputs

against the same task set.

## Metrics

For each system it reports:

- accuracy
- score ratio
- coverage
- pass/fail/unscored counts
- confidence mean
- confidence on pass
- confidence on fail
- confidence gap

## Boundary

This module is side-effect free:

- no provider calls
- no file writes
- no code execution
- no CED mutation

It only scores supplied candidate outputs against supplied ground-truth tasks.

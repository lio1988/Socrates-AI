# Phase 26Q — Ground Truth Checks

Phase 26Q adds deterministic checks outside model self-judgment.

## Added

### `backend/dialogues/learning_ground_truth_checks.py`

Supported task kinds:

- `exact_text`
- `numeric_exact`
- `multiple_choice`
- `regex_match`
- `code_check_record`
- `human_rubric`

Main types:

- `GroundTruthTask`
- `CandidateOutput`
- `GroundTruthResult`
- `BenchmarkReport`

Main helpers:

- `score_ground_truth_task(...)`
- `run_ground_truth_suite(...)`
- `ground_truth_summary(...)`

### `tests_dialogues/test_learning_ground_truth_checks.py`

Tests cover:

- exact text checks
- numeric checks with tolerance
- multiple choice checks
- regex checks
- recorded code-check outcomes
- human rubric placeholders
- aggregate report summaries

## Purpose

This layer helps break circular scoring by adding checks that do not depend on agent self-judgment.

## Boundary

This module is side-effect free:

- no provider calls
- no file writes
- no code execution
- no CED mutation

For code-related tasks it only consumes a recorded pass/fail outcome supplied by a separate trusted test runner.

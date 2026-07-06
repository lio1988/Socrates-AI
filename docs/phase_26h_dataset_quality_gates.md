# Phase 26H — Dataset Quality Gates

Phase 26H adds the safety layer between alignment exports and real training.

The export pack from Phase 26G can produce DPO/SFT/reward/process JSONL files, but before any DPO/RLHF/RLAIF/NeMo training we need automatic quality checks.

## Core idea

```text
alignment export pack → quality gates → PASS / WARN / FAIL → training decision later
```

This phase still does **not** train anything.

## What was added

### `backend/dialogues/learning_quality_gates.py`

Main types:

- `QualitySeverity`
- `QualityVerdict`
- `QualityGatePolicy`
- `QualityIssue`
- `ArtifactQualitySummary`
- `DatasetQualityReport`

Main helpers:

- `jaccard_similarity(...)`
- `check_artifact_integrity(...)`
- `check_record_shapes(...)`
- `check_split_leakage(...)`
- `check_dataset_volume(...)`
- `evaluate_quality_gates(...)`
- `quality_gate_summary(...)`

### `tests_dialogues/test_learning_quality_gates.py`

Offline tests cover:

- clean pack evaluation
- artifact hash mismatch
- invalid JSONL line
- empty required fields
- near-identical chosen/rejected pairs
- train/validation leakage
- minimum dataset volume checks

## Verdicts

### PASS

No blocking errors or warnings. The dataset is clean enough for downstream experiments.

### WARN

No blocking errors, but there are issues that should be reviewed before real training. Examples:

- too few DPO examples
- too few process SFT examples
- chosen/rejected pair is almost identical
- prompt/response length outside preferred bounds

### FAIL

The dataset should not be used for training. Examples:

- broken JSONL
- SHA-256 artifact mismatch
- missing required fields
- train/validation leakage
- total records below the required minimum

## Checks

### Artifact integrity

Verifies:

- JSONL parses
- artifact record count matches actual JSONL rows
- artifact SHA-256 matches the exported content

### Record shape

Checks required fields by format:

- DPO / NeMo-DPO: `prompt`, `chosen`, `rejected`
- Reward pairs: `input`, `candidate_a`, `candidate_b`
- Trace/process SFT: `prompt`, `response`

Also checks prompt and response length bounds.

### Chosen/rejected similarity

For preference data, the gate computes a token-set Jaccard similarity. If chosen and rejected are almost identical, it warns because such pairs are weak DPO/RLHF training data.

### Split leakage

Detects duplicate record signatures across train/validation/test. Leakage here can make evaluation metrics look better than they really are.

### Dataset volume

Checks minimum total records and minimum useful records per training family. Defaults are intentionally small for early development, but policies can be made stricter later.

## Usage

```python
from backend.dialogues.learning_alignment_exporter import build_alignment_export_pack
from backend.dialogues.learning_quality_gates import evaluate_quality_gates, quality_gate_summary

pack = build_alignment_export_pack(dataset, process_report=process_report)
report = evaluate_quality_gates(pack)

print(report.verdict)
print(quality_gate_summary(report))
```

## Policies

Strict policy:

```python
report = evaluate_quality_gates(pack, policy=QualityGatePolicy.strict())
```

Exploratory policy:

```python
report = evaluate_quality_gates(pack, policy=QualityGatePolicy.exploratory())
```

Use exploratory for early smoke tests. Use strict before any serious training run.

## Parallel-learning invariant

This phase does not:

- train models
- fine-tune models
- call providers
- write files
- mutate CED state
- change `ced.py`
- change prompts
- change routing
- change scoring
- change ratification

It only inspects exported artifacts in memory and returns a quality verdict.

## Recommended next phase

### Phase 26I — Training Dry-Run Planner

Before real training, add a planner that reads the quality report and estimates:

- which dataset families are ready
- which training job types are blocked
- what data is missing
- whether to run SFT, DPO, reward model, or process reward first
- safe dry-run config with no real training by default

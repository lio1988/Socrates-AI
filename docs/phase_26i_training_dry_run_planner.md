# Phase 26I — Training Dry-Run Planner

Phase 26I adds a planner between dataset quality gates and any future training.

It does **not** train, fine-tune, call providers, write files, or change CED core.
It reads:

```text
AlignmentExportPack + DatasetQualityReport
```

and produces:

```text
TrainingDryRunPlan
```

The goal is to prevent accidental “train on whatever data exists” behavior.

## What was added

### `backend/dialogues/learning_training_planner.py`

Main types:

- `TrainingFamily`
- `TrainingReadiness`
- `DryRunMode`
- `TrainingPlannerPolicy`
- `TrainingJobPlan`
- `TrainingDryRunPlan`

Main helpers:

- `plan_family(...)`
- `build_training_dry_run_plan(...)`
- `dry_run_plan_summary(...)`

### `tests_dialogues/test_learning_training_planner.py`

Offline tests cover:

- READY job when quality passes and records exist
- WARN quality blocks training but allows inspection by default
- FAIL quality blocks all jobs
- missing records block a specific family
- scoped family planning
- summary output

## Training families

The planner knows these future training families:

- `trace_sft`
- `dpo`
- `nemo_dpo`
- `reward_model`
- `process_sft`
- `process_reward`

## Readiness states

### READY

The dataset quality report allows training and the required records exist.

### INSPECT_ONLY

The data may be inspected, but training remains blocked. This is the default behavior for `WARN` quality reports.

### BLOCKED

Training should not proceed. Examples:

- quality verdict is `FAIL`
- record count is below required minimum
- required artifacts are missing

## Why this matters

After Phase 26H, the system can say:

```text
PASS / WARN / FAIL
```

Phase 26I adds:

```text
Which training families are ready?
Which are blocked?
Which can only be inspected?
What dry-run config would be safe later?
```

## Usage

```python
from backend.dialogues.learning_alignment_exporter import build_alignment_export_pack
from backend.dialogues.learning_quality_gates import evaluate_quality_gates
from backend.dialogues.learning_training_planner import build_training_dry_run_plan

pack = build_alignment_export_pack(dataset, process_report=process_report)
quality = evaluate_quality_gates(pack)
plan = build_training_dry_run_plan(pack, quality)

print(plan.global_readiness)
print(plan.to_json())
```

## Dry-run only

Every job plan contains:

```python
{
    "dry_run": True,
    "no_training_executed": True,
    "family": "dpo",
    "artifacts": [...],
    "record_count": 123,
}
```

The command preview is intentionally non-executable:

```text
DRY RUN ONLY: prepare dpo using [...] with model_family=...
```

This prevents the planner from accidentally launching real training.

## Parallel-learning invariant

This phase does not:

- train models
- fine-tune models
- call providers
- write files
- mutate CED state
- modify `ced.py`
- change prompts
- change routing
- change scoring
- change ratification

It only plans.

## Recommended next phase

### Phase 26J — Local Dry-Run CLI

Add a CLI that can run the full offline learning pipeline on saved artifacts:

```text
collect → mine → process mine → export → quality gates → dry-run plan
```

The CLI should still default to no training and no provider calls.

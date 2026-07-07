# Phase 26L — Learning Health Audit

Phase 26L adds a human-readable health dashboard for the parallel learning stack.

It takes a `LearningPipelineResult` from Phase 26K and evaluates each stage:

```text
collector
preference miner
process miner
export pack
quality gates
dry-run planner
safety invariants
```

Each stage receives:

```text
PASS / WARN / FAIL
```

This phase does **not** train anything.

## What was added

### `backend/dialogues/learning_health_audit.py`

Main types:

- `HealthStatus`
- `LearningStage`
- `LearningHealthPolicy`
- `LearningStageHealth`
- `LearningHealthAudit`

Main helpers:

- `audit_learning_pipeline_result(...)`
- `learning_health_summary(...)`

### `tests_dialogues/test_learning_health_audit.py`

Offline tests cover:

- dashboard creation from a pipeline result
- collector failure when no traces exist
- quality WARN propagation
- safety invariant failure when `no_training_executed=False`
- compact summary generation

## Why this improves the base

Phase 26K made the whole pipeline runnable.

Phase 26L makes the result understandable.

Instead of only seeing raw JSON, we can now see:

```json
{
  "overall_status": "warn",
  "pass_stages": ["collector", "export_pack"],
  "warn_stages": ["preference_miner", "process_miner"],
  "fail_stages": []
}
```

This tells us exactly what to fix next.

## Usage

```python
from backend.dialogues.learning_pipeline import run_learning_pipeline_from_state, LearningPipelinePolicy
from backend.dialogues.learning_health_audit import audit_learning_pipeline_result

result = run_learning_pipeline_from_state(
    state,
    registry=ced.registry,
    policy=LearningPipelinePolicy.exploratory(),
)

audit = audit_learning_pipeline_result(result)
print(audit.summary)
```

## Stage meanings

### Collector

Checks that traces exist and at least some are training-eligible.

### Preference miner

Checks whether answer-level chosen/rejected preference pairs were produced.

### Process miner

Checks whether process SFT or process preference examples were produced.

### Export pack

Checks whether alignment artifacts and records exist.

### Quality gates

Propagates PASS/WARN/FAIL from dataset quality gates.

### Dry-run planner

Checks whether any training family is READY or INSPECT_ONLY.

### Safety invariants

Checks that the pipeline still reports:

```text
no_training_executed = true
```

## Safety invariant

This phase does not:

- call providers
- train models
- fine-tune models
- write files
- mutate `SessionState`
- modify `ced.py`
- modify `backend/dialogues/__init__.py`
- change prompts
- change routing
- change scoring
- change ratification

It only audits a pipeline result in memory.

## Recommended next phase

### Phase 26M — Learning Dataset Runbook

Before real trainer adapters, create a runbook/checklist for local use:

```text
run CED sessions
run learning pipeline
run health audit
inspect WARN/FAIL stages
only then consider trainer adapter dry-run
```

This should remain documentation/tooling first, not real training.

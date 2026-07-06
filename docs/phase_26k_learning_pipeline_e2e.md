# Phase 26K — End-to-End Learning Pipeline Runner

Phase 26K is a stabilization layer for the parallel learning stack.

It wires the existing learning modules together in one in-memory call:

```text
SessionState
→ collect traces
→ mine answer preferences
→ mine process examples
→ export alignment artifacts
→ run quality gates
→ build training dry-run plan
```

It does **not** train anything.

## What was added

### `backend/dialogues/learning_pipeline.py`

Main types:

- `LearningPipelinePolicy`
- `LearningPipelineResult`

Main helpers:

- `run_learning_pipeline_from_state(...)`
- `learning_pipeline_summary(...)`

### `tests_dialogues/test_learning_pipeline_e2e.py`

Offline tests cover:

- full SessionState → dry-run plan pipeline
- no training executed
- export pack creation
- quality report creation
- dry-run planner creation
- policy validation

## Why this improves the base

Before Phase 26K, each learning piece had its own tests:

- collector
- preference miner
- process miner
- alignment exporter
- quality gates
- planner
- local CLI

Phase 26K verifies that they also work together as one pipeline.

## Usage

```python
from backend.dialogues.learning_pipeline import (
    LearningPipelinePolicy,
    run_learning_pipeline_from_state,
)

state = ced.get_session(final.session_id)
result = run_learning_pipeline_from_state(
    state,
    registry=ced.registry,
    policy=LearningPipelinePolicy.exploratory(),
)

print(result.summary)
```

## Safety invariant

This phase does not:

- call providers
- train models
- fine-tune models
- write files
- mutate `SessionState`
- modify `ced.py`
- change prompts
- change routing
- change scoring
- change ratification

It only coordinates the already-parallel learning stack.

## Design note

This phase intentionally does **not** export from `backend.dialogues.__init__`.

Reason: `__init__.py` is already becoming too broad. Future cleanup should move the learning modules under a dedicated package:

```text
backend/dialogues/learning/
```

Phase 26K can be imported directly:

```python
from backend.dialogues.learning_pipeline import run_learning_pipeline_from_state
```

## Recommended next phase

### Phase 26L — Learning Package Refactor Plan

Before adding real trainer adapters, move the learning modules into a dedicated package and keep backwards compatibility shims if needed.

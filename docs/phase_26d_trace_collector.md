# Phase 26D — Learning Trace Collector Integration

Phase 26D connects the Phase 26C learning foundation to completed CED sessions in a safe, opt-in, post-run way.

This phase does **not** change CED execution. It does not alter prompts, scoring, ratification, provider routing, assembly, or runtime semantics. It reads CED-owned `SessionState` after a run and builds a sanitized `LearningDataset`.

## What was added

### `backend/dialogues/learning_trace_collector.py`

Main helpers:

- `collect_learning_dataset(...)`
- `collect_task_traces(...)`
- `collect_ratification_traces(...)`
- `collect_score_traces(...)`
- `provider_catalog(...)`
- `infer_provider_family(...)`
- `learning_export_summary(...)`

### `tests_dialogues/test_learning_trace_collector.py`

Offline tests verify:

- provider-family inference
- registry metadata cataloging without provider calls
- successful task-log entries become sanitized traces
- failed task-log entries are trace-only
- ratification verdicts are collected as trace-only signals
- peer-score traces are collected as trace-only reward-model signals
- dataset summary and eligible JSONL export work

## Usage

```python
from backend.dialogues.live_providers import build_council
from backend.dialogues.learning_trace_collector import (
    collect_learning_dataset,
    learning_export_summary,
)

ced, mode = build_council()
final = await ced.run_registry_session("What makes a belief knowledge?")

state = ced.get_session(final.session_id)
dataset = collect_learning_dataset(state, registry=ced.registry)
summary = learning_export_summary(dataset)

print(summary)
print(dataset.trace_jsonl(eligible_only=True))
```

## Safety model

The collector is post-run and opt-in:

```text
CED run finishes → SessionState exists → collector reads state → LearningDataset export
```

It does not:

- call providers
- train models
- fine-tune models
- change CED routing
- change scoring
- change ratification
- insert hidden audit into agent context

## What gets collected

### Provider move traces

From `state.task_log` + linked `state.moves`:

- phase
- role
- task kind
- provider id
- inferred provider family/model
- validated move content
- confidence
- final-answer metadata if available
- winner sections if the move contributed to final assembly

Successful trainable moves may become eligible for supervised distillation.

### Failed task traces

Failed task-log entries are collected, but remain trace-only. They are useful for reliability analytics, failure clustering, and future provider routing, but not as chosen training targets.

### Ratification traces

Council ratification verdicts are collected as `LearningSignalKind.RATIFICATION`. By default they are trace-only because they are governance/evaluation signals, not ordinary assistant-answer targets.

### Score traces

Move-level and section-level peer scores are collected as `LearningSignalKind.PEER_SCORE`. By default they are trace-only. Later phases can use them for reward-model or process-reward-model experiments under a separate explicit policy.

## JSONL exports

```python
eligible_trace_jsonl = dataset.trace_jsonl(eligible_only=True)
all_trace_jsonl = dataset.trace_jsonl(eligible_only=False)
dpo_jsonl = dataset.dpo_jsonl()
eval_jsonl = dataset.eval_jsonl()
```

Phase 26D mainly fills trace exports. Preference and eval exports remain available from Phase 26C and will be populated by later preference-mining/eval-authoring phases.

## Why this is parallel learning, not core mutation

Phase 26D does not change `CEDOrchestrator` behavior. The intended integration pattern is:

```python
final = await ced.run_registry_session(question)
state = ced.get_session(final.session_id)
dataset = collect_learning_dataset(state, registry=ced.registry)
```

That means the CED core remains the deterministic protocol authority. The learning layer is an observer/exporter sitting beside it.

## Recommended next phases

### Phase 26E — Optional Run Wrapper

Add a small helper like `run_registry_session_with_learning(...)` that calls the normal CED run, then invokes the collector. This should remain opt-in and should not mutate CED internals.

### Phase 26F — Preference Mining

Mine chosen/rejected examples from:

- ratified final sections
- peer-score gaps
- external eval pass/fail
- explicit human feedback

### Phase 27 — Alignment Exporters

Add dedicated output formats for:

- DPO
- RLHF ranking
- RLAIF
- reward models
- process reward models
- NeMo-compatible datasets

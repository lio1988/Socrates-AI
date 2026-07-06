# Phase 26E — Smart Learning Preference Miner

Phase 26E makes the parallel learning layer useful without touching the CED core.
It takes the sanitized `LearningDataset` from Phase 26D and mines auditable
chosen/rejected preference pairs for future DPO, RLHF, RLAIF, reward-model,
process-reward, and distillation workflows.

It still does **not** train anything.

## Core principle

```text
CED core stays deterministic → collector exports traces → miner creates preference data
```

The miner is a data engine, not a reasoning authority.

## What was added

### `backend/dialogues/learning_preference_miner.py`

Main types:

- `PreferenceSignal`
- `PreferenceMiningMode`
- `PreferenceMiningPolicy`
- `TracePreferenceScore`
- `MinedPreferenceCandidate`
- `PreferenceMiningReport`

Main helpers:

- `score_trace_for_preference(...)`
- `mine_preference_candidates(...)`
- `mine_preferences(...)`
- `smart_learning_summary(...)`

### `tests_dialogues/test_learning_preference_miner.py`

Offline tests cover:

- signal scoring
- DPO pair generation
- failed-provider outputs excluded as DPO negatives
- conservative/aggressive thresholds
- ignoring non-provider-move traces as pair sources
- summary generation

## Signals used by the miner

### 1. External eval signal

Strongest signal. If a trace has `external_eval_result={"passed": True}`, it gets a major positive signal. If it failed, it gets a major negative signal.

### 2. Assembly winner signal

If a synthesis trace contributed selected final sections, it receives positive signal. If it contributed failed/unresolved sections, it receives negative signal.

### 3. Peer-score signal

If a trace has peer-score summary metadata such as:

```python
{"average": 8.2}
```

then the miner treats it as a quality signal.

### 4. Confidence signal

Confidence is intentionally weak. High confidence is not truth. The miner uses confidence only as a small tie-breaker so it does not create overconfident training data.

### 5. Ratification signal

A ratified final answer adds a weak positive signal. Repair-required/quorum-failed statuses add negative signal.

### 6. Eligibility signal

Training eligibility from the Socrates Constitution is mandatory for chosen examples.

## Why failed outputs are not DPO negatives

A failed provider output is not a bad answer; it is a broken generation event. If we use it as a rejected DPO sample, future models may learn strange formatting artifacts instead of learning better reasoning.

So the miner requires:

```text
chosen = valid + training eligible
rejected = valid move
failed/timeout/invalid JSON = trace-only, not DPO negative
```

## Usage

```python
from backend.dialogues.learning_trace_collector import collect_learning_dataset
from backend.dialogues.learning_preference_miner import mine_preferences, smart_learning_summary

final = await ced.run_registry_session(question)
state = ced.get_session(final.session_id)

dataset = collect_learning_dataset(state, registry=ced.registry)
report = mine_preferences(dataset, attach=True)

print(smart_learning_summary(report))
print(dataset.dpo_jsonl())
```

## Mining policies

### Conservative

Best for real training export.

```python
policy = PreferenceMiningPolicy.conservative()
```

Requires clearer margins and fewer pairs per prompt.

### Balanced

Good for experimentation.

```python
policy = PreferenceMiningPolicy.balanced()
```

### Aggressive

Good for diagnostics, not yet for training.

```python
policy = PreferenceMiningPolicy.aggressive()
```

## What makes the collector/miner smarter now

Before Phase 26E, the learning layer could collect traces but did not know how to turn them into alignment data.

Now it can say:

```text
This answer won sections, passed eval, had stronger peer scores, and was eligible.
This other answer was valid but weaker.
Therefore: chosen/rejected pair with rationale.
```

That is the exact bridge needed before DPO/RLHF/RLAIF.

## Next phase

### Phase 26F — Process Reward Miner

Mine examples where the *process* improved:

- weak initial answer → strong reflection
- objection found real flaw
- reconstruction repaired the flaw
- synthesis preserved the correction

This is especially important for Socrates AI because the project is process-based, not answer-only.

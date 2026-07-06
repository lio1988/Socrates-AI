# Phase 26M — Deterministic Live Learner

Phase 26M formalizes the architecture distinction:

```text
CED = orchestrator / protocol governor
Live Learner = student / observer
```

CED runs and governs the dialogue. The learner watches the sanitized dialogue flow
and learning pipeline outputs, then updates a deterministic learner ledger.

This phase does **not** train anything.

## What was added

### `backend/dialogues/learning_live_learner.py`

Main types:

- `LearnerSignal`
- `LearnerLesson`
- `LearnerObservation`
- `LearnerState`

Main helpers:

- `stable_learner_hash(...)`
- `derive_lessons_from_pipeline(...)`
- `observe_learning_pipeline(...)`
- `update_learner_state(...)`
- `deterministic_live_learn(...)`
- `learner_state_summary(...)`

### `tests_dialogues/test_learning_live_learner.py`

Offline tests cover:

- deterministic hashes
- lesson derivation from pipeline + health audit
- deterministic observation IDs
- idempotent state update for the same observation
- state accumulation across sessions
- JSON serialization

## Core idea

After each completed CED session:

```python
pipeline = run_learning_pipeline_from_state(state, registry=ced.registry)
audit = audit_learning_pipeline_result(pipeline)
learner_state = deterministic_live_learn(pipeline, audit, state=learner_state)
```

The learner records:

- strengths
- weaknesses
- data needs
- next focus items
- safety confirmations
- observed lessons

## Deterministic live learning

The learner is deterministic because:

```text
same previous LearnerState
+ same LearningPipelineResult
+ same LearningHealthAudit
= same next LearnerState
```

It is live because it can be invoked after every session.

It is not a neural trainer. It is a structured learning ledger.

## What the learner learns

### Strengths

Examples:

- collector produced valid traces
- preference miner produced answer-level pairs
- process miner produced process examples
- quality gates passed
- dry-run planner has READY or INSPECT_ONLY jobs

### Weaknesses

Examples:

- traces exist but none are eligible
- quality gates failed or warned
- observation did not confirm dry-run-only behavior

### Data needs

Examples:

- more competing valid provider moves are needed
- more forward phase progression is needed

### Next focus

Examples:

- resolve blocked training families
- improve provider move validity
- improve confidence calibration

### Safety

The learner records that observation happened without:

- training
- provider calls
- CED mutation

## Safety invariant

This phase does not:

- call providers
- train models
- fine-tune models
- write files
- mutate `SessionState`
- mutate CED state
- modify `ced.py`
- modify `backend/dialogues/__init__.py`
- change prompts
- change routing
- change scoring
- change ratification

It only updates an in-memory learner ledger.

## Why this is the “student”

The CED system should not become semantic authority. It should govern the dialogue.

The learner is different:

```text
CED decides how the council runs.
Learner observes what happened.
Learner remembers what worked and what failed.
Learner proposes what to focus on next.
```

This preserves the original principle:

```text
Agents judge epistemic quality.
CED governs the protocol.
Learner studies the history.
```

## Recommended next phase

### Phase 26N — Learner Persistence Adapter

Add optional save/load for `LearnerState`:

- JSON file adapter
- no automatic writes by default
- explicit user-controlled persistence
- deterministic state hash
- no database requirement
- no CED mutation

This would let the learner actually continue across local runs without becoming a hidden background process.

# Phase 26N — Learner / Trainer / CED Interaction Control Plane

Phase 26N defines how CED, the Live Learner, and the future Trainer interact without
collapsing into one unsafe component.

## Core distinction

```text
CED      = orchestrator / protocol governor
Learner  = student / observer / memory ledger
Trainer  = future capability / readiness reporter / dry-run planner
```

The goal is mutual improvement without unsafe automatic mutation.

## What was added

### `backend/dialogues/learning_interaction_control.py`

Main types:

- `ControlActor`
- `ControlMessageKind`
- `AdvisoryScope`
- `AdvisoryStatus`
- `ControlMessage`
- `CEDAdvisory`
- `TrainerCapabilityReport`
- `InteractionControlPolicy`
- `InteractionCycle`

Main helpers:

- `interaction_hash(...)`
- `build_trainer_capability_report(...)`
- `build_ced_advisories(...)`
- `run_interaction_cycle(...)`
- `interaction_cycle_summary(...)`

### `tests_dialogues/test_learning_interaction_control.py`

Offline tests cover:

- deterministic interaction hashes
- trainer capability report from dry-run plan
- typed CED ↔ Learner ↔ Trainer messages
- safe advisories to CED
- deterministic interaction cycle IDs
- blocked unsafe actions
- human approval requirement for trainer escalation

## Interaction loop

```text
1. CED completes a dialogue session.
2. Learning pipeline turns SessionState into learning artifacts and dry-run plan.
3. Health audit evaluates the pipeline.
4. Learner observes pipeline + audit and updates LearnerState.
5. Trainer reports readiness from dry-run plan.
6. Learner sends safe advisories back toward CED.
7. Control plane blocks unsafe escalation.
```

## Message flow

```text
CED → Learner
  observation: here is a completed sanitized dialogue/pipeline result

Learner → Trainer
  lesson_update: here are strengths, weaknesses, data needs, next focus

Trainer → Learner
  trainer_readiness: READY / INSPECT_ONLY / BLOCKED training families

Learner → CED
  ced_advisory: safe diagnostic guidance only

Control Plane → All
  safety_block: no automatic core/prompt/weight/training mutation
```

## What CED is allowed to receive

CED may receive only safe advisories such as:

- collect better diagnostic data
- prefer external eval for weak areas
- inspect blocked learning families
- use next-focus items as optional diagnostic hints

CED must not automatically receive:

- prompt rewrites
- scoring changes
- core protocol edits
- model weight updates
- training execution commands

## What the Learner is allowed to do

The Learner may:

- observe sanitized pipeline results
- observe health audits
- update deterministic learner state
- record strengths, weaknesses, data needs, next focus
- produce CED advisories

The Learner may not:

- train models
- call providers
- modify CED state
- modify prompts
- modify scoring
- modify ratification

## What the Trainer is allowed to do here

The Trainer may:

- report READY / INSPECT_ONLY / BLOCKED families
- expose dry-run-only capability
- explain which artifacts are missing

The Trainer may not:

- train models
- mutate weights
- bypass quality gates
- run without human approval

## Safety invariant

This phase does not:

- call providers
- train models
- fine-tune models
- write files
- mutate CED state
- modify `ced.py`
- modify `backend/dialogues/__init__.py`
- change prompts
- change routing
- change scoring
- change ratification

It only builds deterministic messages and advisories.

## Why this is the right triangle

```text
CED governs the dialogue.
Learner studies the history.
Trainer reports what could be trained later.
Control plane prevents unsafe automatic mutation.
```

This creates mutual improvement without confusing roles.

## Example usage

```python
pipeline = run_learning_pipeline_from_state(state, registry=ced.registry)
audit = audit_learning_pipeline_result(pipeline)

cycle = run_interaction_cycle(
    pipeline,
    audit,
    learner_state=learner_state,
)

learner_state = cycle.learner_state
print(interaction_cycle_summary(cycle))
```

## Recommended next phase

### Phase 26O — Explicit Persistence Adapter

Add optional persistence for:

- `LearnerState`
- `InteractionCycle`
- audit summaries

Rules:

- no automatic writes
- explicit user command only
- deterministic hash in saved files
- no hidden background process
- no CED mutation

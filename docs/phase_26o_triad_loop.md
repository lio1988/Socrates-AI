# Phase 26O — CED / Learner / Trainer Triad Loop

Phase 26O ties the learning architecture together.

Before this phase, the project had separate pieces:

- learning pipeline
- health audit
- live learner ledger
- interaction control plane

Phase 26O adds one integration facade:

```text
CED SessionState
→ LearningPipelineResult
→ LearningHealthAudit
→ updated LearnerState
→ InteractionCycle
→ CEDFeedbackPacket
```

## What was added

### `backend/dialogues/learning_triad_loop.py`

Main types:

- `TriadLoopPolicy`
- `CEDFeedbackPacket`
- `TriadLoopResult`

Main helpers:

- `triad_hash(...)`
- `build_ced_feedback_packet(...)`
- `run_triad_learning_loop(...)`
- `triad_loop_summary(...)`

### `tests_dialogues/test_learning_triad_loop.py`

Offline tests cover:

- deterministic hashes
- integrated SessionState to triad result
- learner state update across sessions
- safe CED feedback packet generation
- deterministic loop ID for same inputs
- JSON serialization

## Usage

```python
from backend.dialogues.learning_triad_loop import (
    TriadLoopPolicy,
    run_triad_learning_loop,
)

result = run_triad_learning_loop(
    state,
    registry=ced.registry,
    learner_state=learner_state,
    policy=TriadLoopPolicy.exploratory(),
)

learner_state = result.interaction.learner_state
ced_feedback = result.feedback_packet
```

## CEDFeedbackPacket

The feedback packet is the safe object CED can inspect after a session.

It contains:

- focus hints
- data collection requests
- eval recommendations
- readiness summary
- blocked actions
- human review items
- evidence pointing back to learner and interaction summaries

It is a feedback object, not an automatic command object.

## Why this ties the system better

The system now has a clear rhythm:

```text
CED runs the dialogue.
Learner studies the completed flow.
Readiness is summarized from dry-run planning.
Control plane turns this into typed advisories.
Triad loop returns one feedback packet for CED inspection.
```

This creates mutual improvement without role confusion.

## Determinism

Same inputs produce the same loop identifiers:

```text
same SessionState
+ same prior LearnerState
+ same policies
= same TriadLoopResult identifiers
```

## Boundary

This phase is coordination-only. It does not:

- call providers
- write files
- edit CED state
- modify `ced.py`
- modify `backend/dialogues/__init__.py`
- change prompts
- change routing
- change scoring
- change ratification

It only coordinates existing safe components.

## Recommended next phase

### Phase 26P — Explicit Persistence Adapter

The triad loop is now useful in memory. The next step is optional persistence:

- save/load `LearnerState`
- save/load `TriadLoopResult` summary
- deterministic file hash
- explicit user command only
- no automatic background process

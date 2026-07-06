# Phase 26F — Process Reward Miner

Phase 26F adds process-reward mining on top of the parallel learning layer.

The previous miner, Phase 26E, creates chosen/rejected pairs for better answers.
Phase 26F asks a deeper Socrates-specific question:

```text
Which reasoning step improved the dialogue?
```

This matters because Socrates AI / CED is not an answer-only system. Its advantage
comes from process: Socratic questions, objections, reflection, reconstruction, and
synthesis.

## What was added

### `backend/dialogues/learning_process_miner.py`

Main types:

- `ProcessSignal`
- `ProcessMiningMode`
- `ProcessMiningPolicy`
- `ProcessStepScore`
- `ProcessTransition`
- `ProcessSFTExample`
- `ProcessMiningReport`

Main helpers:

- `score_process_step(...)`
- `mine_process_transitions(...)`
- `mine_process_examples(...)`
- `process_reward_summary(...)`

### `tests_dialogues/test_learning_process_miner.py`

Offline tests cover:

- Socratic objection scoring
- reflection scoring
- forward process-transition mining
- SFT + preference output generation
- non-forward transition skipping
- after-trace eligibility guardrail
- process summary output

## Parallel-learning invariant

Phase 26F does not change the CED core.

It does not:

- modify `ced.py`
- call providers
- train models
- fine-tune models
- change prompts
- change routing
- change scoring
- change ratification
- mutate `SessionState`

It reads a `LearningDataset` and produces process-learning artifacts.

## Input flow

```python
final = await ced.run_registry_session(question)
state = ced.get_session(final.session_id)

dataset = collect_learning_dataset(state, registry=ced.registry)
preference_report = mine_preferences(dataset, attach=True)
process_report = mine_process_examples(dataset, attach_preferences=True)
```

## Output types

### 1. Process SFT examples

These teach useful process moves directly.

Example shape:

```json
{
  "prompt": "Question: ... Earlier phase output: ... Produce the improved next process move...",
  "response": "A stronger reconstruction...",
  "phase": "reconstruction",
  "task_kind": "reconstruction_proposal"
}
```

### 2. Process preference examples

These are chosen/rejected pairs where the chosen output is a later, stronger
process move and the rejected output is an earlier weaker valid move.

These can feed:

- DPO
- RLAIF
- process reward models
- critique/revision preference training

## Signals

### Socratic question signal

Rewards opening questions that expose assumptions, clarify premises, or force a
better formulation.

### Objection signal

Rewards elenchus moves that target assumptions, contradictions, missing evidence,
falsifiability, weaknesses, or blind spots.

### Reflection signal

Rewards revisions that concede, update, or respond honestly to critique.

### Reconstruction signal

Rewards proposals that repair, integrate, or produce a stronger model.

### Synthesis signal

Rewards drafts that contributed selected final sections.

### Calibration signal

Rewards moderate calibrated confidence and penalizes extreme confidence when not
supported by external eval.

## Guardrails

- Transitions must move forward in the CED phase order.
- The after-step must be training-eligible by default.
- The before-step must be a valid provider move by default.
- Identical rendered outputs are skipped.
- Gains must exceed the policy threshold.

## Why this is important

A normal preference miner can teach:

```text
answer A is better than answer B
```

The process miner can teach:

```text
this objection improved the answer
this reflection fixed overclaiming
this reconstruction integrated the critique
this synthesis preserved the correction
```

That is much closer to the real promise of CED.

## Recommended next phase

### Phase 26G — Alignment Export Pack

Create dedicated exporters for:

- DPO answer preferences
- DPO process preferences
- process SFT
- reward-model pairwise data
- NeMo-compatible alignment files
- dataset manifest with provenance and policy metadata

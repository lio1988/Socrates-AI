# Phase 26C — CED Learning Foundation

This phase creates the safe data foundation needed before adding company-grade LLM
learning techniques such as RLHF, DPO, RLAIF, reward models, process-reward
learning, distillation, NVIDIA NeMo alignment, or local fine-tuning.

It does **not** train or fine-tune anything yet. It creates the substrate that
future learning loops can trust.

## Why this phase exists

A CED learning loop must not learn from its own failures blindly. The safe order is:

```text
trace → sanitize → assess eligibility → create preference/eval examples → export JSONL → train later
```

This phase keeps CED's key invariant intact:

> Evidence beats agreement. Failed providers never fabricate knowledge.

## What was added

### `backend/dialogues/learning_foundation.py`

Core types:

- `SocratesConstitution`
- `SocratesPrinciple`
- `TrainingEligibility`
- `LearningTrace`
- `PreferenceExample`
- `EvalExample`
- `LearningDataset`

Core helpers:

- `sanitize_public_payload(...)`
- `assess_training_eligibility(...)`
- `build_preference_example(...)`
- `jsonl(...)`

### `tests_dialogues/test_learning_foundation.py`

Offline tests for:

- secret/hidden-audit sanitization
- valid provider responses becoming eligible traces
- failed provider outputs staying trace-only
- scoring/ratification tasks staying trace-only by default
- low-confidence outputs being excluded
- valid chosen/rejected preference pairs
- rejecting failed-provider outputs as DPO negatives
- eval example validation
- JSONL export safety
- default Socrates Constitution principles

## Socrates Constitution

The default learning constitution includes these principles:

1. `evidence_over_agreement`
   - model agreement is not proof
   - prevents consensus laundering and herding

2. `no_overclaiming`
   - hypotheses must not be exported as established facts
   - preserves epistemic calibration

3. `failed_outputs_are_not_training_targets`
   - invalid JSON, schema errors, missing keys, timeouts, refusals, and failed providers can be logged but never used as chosen training targets

4. `hidden_audit_is_not_training_prompt`
   - provider mappings, hidden scores, keys, raw prompts, and task logs must not enter public learning examples

5. `process_matters`
   - future reward models should learn good Socratic process, not only polished final answers

## LearningTrace

A `LearningTrace` is a sanitized record of a provider move:

```python
trace = LearningTrace.from_provider_response(
    task,
    response,
    provider_family="nvidia",
    model="nvidia/llama-3.1-nemotron-70b-instruct",
)
```

It stores:

- question
- provider family/model
- role/phase/task kind
- provider status
- validated content
- confidence
- epistemic markers
- optional peer scores / ratification / human feedback / external eval result
- eligibility result

It does **not** put raw hidden audit into public exports.

## Training eligibility

By default, a trace is training-eligible only if:

- provider status is `OK`
- parsed/validated content exists
- task kind is trainable
- confidence is above the policy threshold
- external eval did not fail
- ratification did not block/reject it

Trace-only by default:

- move scoring
- section scoring
- council ratification
- lesson relevance
- lesson consolidation
- process review

These can still be used later for reward-model or process-model research, but not
as ordinary assistant answer targets without a separate policy.

## Preference examples

`build_preference_example(...)` creates DPO/RLHF/RLAIF-ready chosen-vs-rejected records.

```python
pref = build_preference_example(
    chosen_trace,
    rejected_trace,
    rationale="Chosen is better calibrated and evidence-aware.",
)
```

Guardrails:

- chosen must be training-eligible
- rejected must be a valid move
- failed providers are not used as DPO negatives
- both traces must come from the same question
- rationale is required

## Eval examples

`EvalExample` stores external benchmark items:

```python
ev = EvalExample(
    question="2+2?",
    verifier_type=EvalVerifierType.EXACT,
    expected_answer="4",
)
```

Supported verifier types:

- exact
- numeric
- set match
- rubric
- human
- external program

## JSONL exports

```python
ds = LearningDataset()
ds.add_trace(trace)
ds.add_preference(pref)
ds.add_eval(ev)

trace_jsonl = ds.trace_jsonl(eligible_only=True)
dpo_jsonl = ds.dpo_jsonl()
eval_jsonl = ds.eval_jsonl()
```

These are the files future phases can feed into:

- DPO
- RLHF/RLAIF preference pipelines
- reward model training
- supervised distillation
- external eval harnesses
- NVIDIA NeMo alignment workflows

## Recommended next phases

### Phase 26D — Trace Collector Integration

Wire `LearningTrace.from_provider_response(...)` into the CED task/result path so
every real council run can optionally emit a learning bundle.

### Phase 26E — Preference Mining

Use peer scores, ratification, external evals, and human feedback to automatically
select high-confidence chosen/rejected pairs.

### Phase 27 — Alignment Exporters

Add dedicated exporters for:

- DPO JSONL
- RLHF ranking JSONL
- reward model pairwise data
- supervised distillation data
- NeMo-compatible alignment datasets

### Phase 28 — Process Reward Model

Train/evaluate a model that rewards good Socratic process: useful objections,
better reconstruction, calibrated synthesis, and avoidance of herding.

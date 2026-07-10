# Deliberation Tree → Governed Agent Evidence

Status: additive v1 foundation. Runtime-inert toward CED.

## Purpose

The Deliberation Tree already improves a session by asking an agent to revise a selected parent draft and then scoring the child through the normal anonymous, no-self-scoring path. The Teacher Loop already distils successful tree trajectories into preference data.

This layer adds the missing personal-evidence bridge:

```text
completed CED tree session
→ strict parent/child matched comparison
→ per-agent immutable observation
→ repeated regression or matched resolution evidence
→ bounded self-review
→ governed proposal
```

It does **not** train a model, write Identity, link Memory, change prompts, promote an agent, grant council authority, or mutate `SessionState`.

## Modules

```text
backend/dialogues/openclaw_identity/
  tree_revision_schema.py       exact hash-bound observation schema
  tree_revision_observation.py  read-only extractor from completed sessions
  tree_revision_evidence.py     bridge to existing governed Identity evidence
```

The implementation deliberately reuses the existing hardened builders for:

- `identity:add_known_failure`
- `identity:resolve_known_failure`

It does not introduce another evidence registry or another self-revision lifecycle.

## Observation contract

Schema version:

```text
openclaw_tree_revision_observation_v1
```

Each observation binds:

- session and benchmark/comparison key;
- question SHA-256;
- exact revising agent and provider;
- parent and child draft IDs;
- recomputed parent/child means and margin;
- matched judge IDs and sections;
- matched score count;
- tree exploration and expansion budget;
- digest of the exact score pairs;
- source trace and full observation digest.

Unknown fields, non-finite values, secret-shaped text, malformed IDs and digest mismatches fail closed.

## Why matched score pairs

A parent and child are compared only where **the same eligible judge scored the same section in both drafts**:

```text
(judge_id, section_name)
```

The margin is recomputed from those intersections. The extractor never trusts the cached `child_score` stored in the tree audit.

This avoids attributing improvement to an agent when the apparent difference came from:

- a different judge panel;
- missing sections;
- failed scorecards;
- self-scoring;
- incomparable scoring coverage.

A run with no common valid judge-section pairs emits no observation. In very small councils, especially some two-seat configurations, this can happen naturally and is an honest lack of evidence rather than a zero score.

## Attribution checks

A successful tree child must be connected to both:

- an `AgentMove` with `task_kind=tree_revision` and `phase=synthesis`;
- a matching CED task-log entry.

Agent ID and provider ID must agree across the child draft, move and task log. Missing or conflicting provenance fails closed.

## Outcomes

Given a configured positive `effect_margin`:

```text
margin >= effect_margin   → improved
margin <= -effect_margin  → regressed
otherwise                 → neutral
```

These labels are observations only. A single revision never changes Identity.

## Failure evidence

`build_tree_revision_failure_evidence(...)` requires:

- at least two concrete regressions;
- one target agent;
- distinct session IDs;
- distinct source traces;
- immutable observation digests;
- a named non-self verifier through the existing evidence builder.

It produces evidence supporting only:

```text
identity:add_known_failure
```

Example weakness:

```text
Tree revisions repeatedly reduce matched peer score on evidence-preserving synthesis tasks.
```

The weakness wording and pattern key remain curator/instrument inputs. The tree does not invent a psychological explanation for the agent.

## Resolution evidence

`build_tree_revision_resolution_evidence(...)` requires equal before/after windows:

```text
before: concrete regressions
 after: concrete improvements
```

Every before item must match an after item by `comparison_key`, with identical:

- judge IDs;
- matched sections;
- score count;
- exploration constant;
- expansion budget.

Sessions must be unique and the windows may not overlap.

It produces the existing dual support:

```text
identity:add_known_failure
identity:resolve_known_failure
```

The resulting record can support a governed resolution proposal and a `reverted` outcome for the original weakness when the lifecycle requirements are otherwise satisfied.

## Deliberate non-authority

Tree evidence is not permission.

```text
Tree observation
→ verified evidence
→ bounded self-review
→ agent proposal
→ independent evaluation
→ named non-self decision
→ recoverable application
→ probation
→ confirmation or canonical inverse
```

The bridge never performs any later step automatically.

Positive tree trajectories remain useful for `TrainingCorpus` distillation, but they do not automatically link a Memory lesson. A lesson must still be stable/verified and prove a causal single-agent effect through the dedicated Lesson A/B path.

## Relationship to future epistemic events

This v1 reads the current completed `SessionState`, tree audit and real scorecards. When the Canonical Epistemic Event Ledger is introduced, the same observation schema can become a projection from authoritative tree events without changing the governed evidence contract.

## Tests

`tests_dialogues/test_openclaw_tree_revision_evidence.py` covers:

- real matched-score recomputation;
- refusal to trust cached audit scores;
- exact schema and digest tamper detection;
- no-self-scoring;
- missing move/task provenance;
- no-common-judge no-op;
- repeated-regression evidence;
- matched resolution windows;
- changed judges, benchmark keys and tree budget refusal;
- secret-shaped input rejection;
- deterministic summaries.

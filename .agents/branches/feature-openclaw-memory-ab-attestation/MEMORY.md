# Durable Memory — `feature/openclaw-memory-ab-attestation`

Only durable, evidence-backed branch decisions belong here.

## Branch purpose

PR #62 is the third governed attestation bridge. It connects matched single-agent Lesson A/B experiment results to immutable personal Memory evidence without directly mutating Memory or Identity.

The branch must preserve this separation:

```text
experiment result != evidence registration != proposal != approval != application
```

## Stacked history

PR #62 was intentionally stacked on PR #61 / `feature/openclaw-attestation-bridges`.

PR #61 later merged into `main` as the governed Identity failure/resolution, Soul review, and curator-reporting bridge.

PR #62 still owns only the single-agent Lesson A/B Memory bridge. It must not reintroduce preliminary or duplicate PR #61 scope.

A clean post-stack state should ultimately show only PR #62-owned changes against the merged `main`, but synchronization must be inspected before retargeting.

## Exact G4 envelope

Personal Memory evidence accepts only:

```text
openclaw_agent_lesson_ab_attestation_v1
```

The envelope binds:

- one exact nested `openclaw_agent_lesson_ab_v1` report;
- one exact `openclaw_agent_lesson_ab_experiment_v1` manifest;
- the complete current curated `MemoryLesson` record via SHA-256;
- the exact governed target Identity state via SHA-256;
- the complete canonical manifest via SHA-256.

Ordinary whole-council `lesson_ab_v2` reports may support global lesson curation but cannot justify one agent’s personal Memory change.

Bare personal reports without the full envelope and retained manifest are refused.

## Lesson fingerprint

`memory_lesson_fingerprint()` binds evidence to the complete canonical `MemoryLesson.to_record()` value, including:

- lesson ID and name;
- lifecycle status;
- lesson type and source;
- use conditions;
- problem, bad, and good patterns;
- exact lesson text;
- risk text.

Changing content or status under the same `LESSON-*` ID invalidates old evidence for new lifecycle actions.

## Identity fingerprint

The attestation is bound to the exact governed target Identity state.

The fingerprint must represent durable governed identity state, including relevant version/stage, known failures, linked lessons, Soul principles, gates, and append-only governed histories, while excluding refreshable observational counters where the canonical helper defines that boundary.

A later governed Identity state cannot inherit evidence produced for an earlier state.

## Experiment causality

The retained manifest must prove a matched single-agent experiment:

- exact target agent and lesson match;
- treatment scope is `single_agent`;
- question hashes are unique;
- random seeds and arm order align with each question;
- claimed counterbalancing is real;
- control and treatment share one base configuration;
- control has no lesson injection;
- treatment injects exactly one bound lesson into only the target agent;
- provider IDs are non-empty and distinct;
- judge set is bound and self-judging is false;
- token/timeout budgets are positive and common;
- retry limit is non-negative;
- tested count does not exceed retained questions;
- all content is finite canonical JSON and secret-safe.

## Named non-self attestation

The CLI verifier must match the verifier recorded in the nested report.

The target agent may not verify itself, including through capitalization changes or equivalent normalized identity.

Anonymous verification is insufficient.

## Link evidence semantics

A clean helped report may support:

```text
memory:link_stable_lesson
outcome: confirmed
```

A new link additionally requires:

- exact lesson and Identity bindings match current governed state;
- lesson currently has eligible `stable` or `verified` status;
- minimum tested threshold is met;
- mean score delta is positive and finite;
- harm remains within the configured bound;
- no ratification, unresolved, catastrophic, or configuration regressions exist.

The evidence record does not perform the link.

## Unlink evidence semantics

A concrete harmful post-link result may support:

```text
memory:link_stable_lesson
memory:unlink_stable_lesson
outcome: reverted
```

For a new unlink evidence reference, the exact lesson must currently be linked in the exact governed profile bound by the envelope.

The current lesson fingerprint map must include all current curated lessons, including deprecated lessons that may still need governed removal. Do not build it from stable lessons only.

## Current-state lifecycle binding

Personal Memory evidence is rechecked at:

```text
submit -> evaluate -> decide -> transactional apply
```

The lifecycle fails closed when:

- evidence lacks the single-agent marker;
- the G4 state-binding marker is missing or malformed;
- current governed Identity no longer matches;
- current lesson fingerprint is missing or stale;
- the wrong agent or lesson is referenced;
- the lifecycle caller omits required current catalogue context.

Application binding must be checked before creating or mutating the write-ahead journal or Identity file.

## Recovery boundary

Once a transaction is validly `prepared`, recovery completes the exact preflighted hash-bound intent stored in the journal.

Recovery is not:

- a new experiment evaluation;
- a new approval;
- permission to edit the lesson catalogue, Identity, evidence, lifecycle, or journal during recovery.

## Immutability and replay

- Exact replay of identical evidence may be idempotent.
- Reusing the same evidence reference with changed report, lesson, Identity, manifest, fingerprint, or semantics is refused.
- Existing exact evidence may remain readable after later governed state changes, but it cannot authorize a new action against stale state.
- Local attestation files are bounded UTF-8 JSON objects; URLs and malformed/non-object/oversized inputs fail closed.

## Authority boundary

The G4 bridge creates immutable evidence only.

It does not:

- edit lessons;
- link or unlink Memory;
- create, evaluate, approve, apply, confirm, or revert proposals;
- alter prompts, tools, roles, permissions, providers, council weight, or CED authority;
- invoke models or networks.

## Supported production surface

Production/operator code should use the governed facade and recoverable transaction coordinator.

Raw low-level registry operations may remain for compatibility and isolated tests, but they are not the supported activation path for G4 Memory changes.

## Remote-state discipline

The GitHub PR head is the remote source of truth.

Any later local merge commit, unstaged fix, uncommitted worktree change, or agent-reported RED→GREEN pass is not part of PR #62 until it is intentionally committed and pushed to `feature/openclaw-memory-ab-attestation`.

Do not claim local-only fixes are present on the remote branch.

## Validation truth

Focused tests do not establish merge readiness by themselves.

Validation requires synchronized branch state plus:

- compile/import checks;
- PR-owned focused tests;
- affected PR #61 and governed-lifecycle regressions;
- complete `tests_dialogues`;
- full repository suite;
- independent adversarial review of strict parsing, current-state binding, immutability, idempotency, and transaction preflight.

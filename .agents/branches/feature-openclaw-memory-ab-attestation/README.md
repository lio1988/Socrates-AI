# Branch: `feature/openclaw-memory-ab-attestation`

PR: `#62 — Add bound single-agent Lesson A/B Memory attestation`  
Original stacked base: `feature/openclaw-attestation-bridges` / PR #61  
Branch purpose: add a strict, state-bound evidence bridge from matched single-agent Lesson A/B experiments into the existing governed Memory self-revision lifecycle, without directly mutating Memory or Identity.

## Mandatory reading order

Before editing this branch, read:

1. [`AGENTS.md`](../../../AGENTS.md) — repository-wide agent contract;
2. [`.agents/user/ME.md`](../../user/ME.md) — project-owner collaboration profile and durable product intent;
3. [`PRESENT.md`](PRESENT.md) — current remote and PR truth;
4. [`MEMORY.md`](MEMORY.md) — durable architecture decisions;
5. [`PLANS.md`](PLANS.md) — ordered work and gates;
6. [`CLAUDE.md`](../../../CLAUDE.md) when using Claude Code;
7. [`CURSOR.md`](../../../CURSOR.md) when using Cursor;
8. [`docs/openclaw_memory_lessons/AGENT_LESSON_AB_ATTESTATION.md`](../../../docs/openclaw_memory_lessons/AGENT_LESSON_AB_ATTESTATION.md);
9. [`docs/openclaw_memory_lessons/G4_MEMORY_LIFECYCLE_BINDING.md`](../../../docs/openclaw_memory_lessons/G4_MEMORY_LIFECYCLE_BINDING.md);
10. the G4 section of [`docs/openclaw_memory_lessons/OPERATOR_GUIDE.md`](../../../docs/openclaw_memory_lessons/OPERATOR_GUIDE.md);
11. `scripts/openclaw_attest_lesson_ab.py`;
12. `backend/dialogues/openclaw_identity/memory_evidence_binding.py`;
13. the governed registry, facade, and transaction-coordinator changes;
14. all five PR-owned test files and affected PR #61 regression tests.

`ME.md` explains how to collaborate with the user. It does not prove code state, tests, runtime behavior, or merge readiness. Do not infer or store additional personal information.

Do not begin from a chat summary, an old PR body, or a local-only agent report when the remote branch can be inspected directly.

## Current stack warning

PR #61 has merged into `main`, but PR #62 still targets the historical feature branch `feature/openclaw-attestation-bridges`.

The branch has diverged from both that feature branch and current `main`.

Therefore the next agent must not blindly:

- merge the old base branch;
- rebase onto `main`;
- retarget PR #62;
- force-push;
- assume the PR currently contains only its intended fifteen-file diff.

First inspect exact commits, conflicts, and the intended post-#61 diff. Then choose and record a safe synchronization strategy.

## Branch scope

The branch owns the G4 personal Memory evidence bridge:

```text
single-agent matched A/B experiment
    -> exact retained experiment manifest
    -> exact lesson fingerprint
    -> exact governed Identity fingerprint
    -> named non-self attestation
    -> immutable action-specific Memory evidence
    -> current-state binding checks
    -> existing governed self-revision lifecycle
```

The intended branch-owned implementation areas are:

```text
backend/dialogues/openclaw_memory/
    lesson fingerprint helpers

backend/dialogues/openclaw_identity/
    Memory evidence binding
    governed evaluate/decide/apply plumbing

scripts/
    strict offline attestation command

docs/openclaw_memory_lessons/
    exact G4 envelope, lifecycle, and operator contract

tests_dialogues/
    attestation, provenance, manifest, fingerprint, and lifecycle tests
```

## Permanent authority boundary

The attestation command writes immutable evidence only.

It must never:

- edit `MEMORY_LESSONS.md`;
- link or unlink a lesson directly;
- mutate an `AgentIdentityProfile`;
- create a self-revision proposal;
- evaluate or approve a proposal;
- apply, confirm, promote, or roll back a lifecycle;
- alter prompts, tools, roles, permissions, provider access, council weight, or CED authority;
- call an AI provider or network service;
- use self-attestation or self-judging.

The complete governed path remains:

```text
experiment
    -> attested evidence
    -> bounded self-review
    -> agent-authored proposal
    -> independent evaluation
    -> named non-self approval
    -> recoverable transactional application
    -> probation
    -> confirmation or governed unlink rollback
```

## Evidence contract

Only the exact envelope is accepted:

```text
openclaw_agent_lesson_ab_attestation_v1
```

It contains:

- exact nested `openclaw_agent_lesson_ab_v1` report;
- exact `openclaw_agent_lesson_ab_experiment_v1` manifest;
- SHA-256 of the complete current curated lesson record;
- SHA-256 of the exact governed target Identity state;
- SHA-256 of the canonical complete experiment manifest.

Bare personal reports and ordinary whole-council `lesson_ab_v2` reports are insufficient for personal Memory.

## Experiment requirements

The retained experiment must prove:

- same target agent and lesson across envelope, report, and manifest;
- `treatment_scope="single_agent"`;
- unique question hashes;
- aligned seeds and arm order for every question;
- real counterbalancing when claimed;
- identical base configuration in control and treatment;
- clean control with no lesson injection;
- treatment injecting exactly the bound lesson into only the target agent;
- non-empty distinct provider IDs;
- bound judge set with self-judging forbidden;
- common positive token/timeout budget and non-negative retry limit;
- tested count within the retained question set;
- canonical finite JSON with no secret-shaped values.

## Link and unlink semantics

A valid helped result may produce evidence supporting:

```text
memory:link_stable_lesson
outcome: confirmed
```

A valid harmful post-link result may produce evidence supporting:

```text
memory:link_stable_lesson
memory:unlink_stable_lesson
outcome: reverted
```

Evidence support is not automatic action. Linking or unlinking still requires the existing governed lifecycle.

## Current-state binding

Personal Memory evidence must be rebound at every supported lifecycle boundary:

```text
submit -> evaluate -> decide -> transactional apply
```

The lifecycle must fail closed when:

- the evidence is not a single-agent Lesson A/B record;
- the binding marker is absent or malformed;
- the governed Identity changed;
- the lesson record changed under the same lesson ID;
- the current lesson fingerprint map is absent or stale;
- a new unlink targets a lesson not linked in the bound profile;
- an application preflight fails before journal or Identity mutation.

Recovery may complete only the exact already-preflighted intent stored in the transaction journal. Recovery is not a new approval or new experiment evaluation.

## What this branch must not do accidentally

Do not:

- weaken strict exact-field schemas;
- accept whole-council reports as personal evidence;
- accept bare unbound personal reports;
- bind only the lesson ID instead of the full lesson record;
- bind only a refreshable observational Identity view instead of governed state;
- build unlink fingerprint maps from stable lessons only;
- allow self-attestation through case changes;
- trust caller-provided `passed=True` decisions or replacement profiles;
- persist partial state after a failed application preflight;
- treat exact idempotent replay as permission for conflicting reuse;
- assume local unpushed fixes exist on the GitHub branch;
- retarget or merge before synchronization and full validation.

## Status vocabulary

Use only these meanings:

- `specified` — documented contract exists;
- `implemented` — source and tests exist on the inspected branch;
- `validated_focused_only` — only a focused subset passed;
- `validated` — all required focused, regression, `tests_dialogues`, and full repository suites passed on the synchronized branch;
- `runtime_available` — supported operator code can execute the feature;
- `shipped` — merged into `main`;
- `blocked` — a named defect, conflict, or dependency prevents progress.

## Required validation before retarget or merge

At minimum:

1. inspect branch divergence and preserve only the intended post-#61 diff;
2. audit the complete CLI parser and file boundary;
3. run compile/import checks;
4. run all five PR-owned focused test files;
5. run affected attestation, evidence builder, self-review, lifecycle, transaction, and recovery regressions;
6. run `tests_dialogues`;
7. run the full repository suite in the canonical environment;
8. scan for secrets and `.env` changes;
9. independently review fail-closed, idempotency, current-state binding, and transaction preflight behavior;
10. update `PRESENT.md`, `MEMORY.md`, and `PLANS.md` with exact results;
11. only then retarget cleanly to `main`, update the PR body, and decide readiness.

## Handoff rule

Every agent leaving this branch must update `PRESENT.md` with the exact remote/local relationship, head SHA, base, tests actually run, remaining defects, and one next action. Durable decisions belong in `MEMORY.md`; unfinished steps belong in `PLANS.md`.

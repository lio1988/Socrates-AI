# Socrates AI — Agent Working Contract

This file is the repository-level entry point for coding agents.

## Mandatory startup sequence

Before editing any file:

1. Confirm the current Git branch, head commit, worktree state, remotes, and PR target.
2. Locate the matching branch workspace under `.agents/branches/`.
3. Read, in this exact order:
   - the branch `README.md`;
   - `PRESENT.md`;
   - `MEMORY.md`;
   - `PLANS.md`.
4. Read every canonical document linked from the branch README.
5. Compare the stated branch status with the actual source, tests, commits, PR metadata, and base branch.
6. Correct stale handoff documentation before relying on it.

For branch `feature/openclaw-memory-ab-attestation`, the required workspace is:

```text
.agents/branches/feature-openclaw-memory-ab-attestation/
```

## Source-of-truth hierarchy

When sources disagree, use this order:

1. actual code and validated schemas;
2. passing tests and immutable records;
3. current Git branch, commits, base, and PR metadata;
4. canonical architecture and operator documents;
5. branch `PRESENT.md`;
6. branch `MEMORY.md`;
7. branch `PLANS.md`;
8. historical prose, chat summaries, and old phase notes.

Do not treat a plan, README statement, PR body, previous agent report, or local-only change as proof that behavior exists on the remote branch.

## Required branch handoff files

Every substantial branch must maintain:

```text
.agents/branches/<sanitized-branch-name>/
    README.md
    MEMORY.md
    PLANS.md
    PRESENT.md
```

The branch README title must contain the exact Git branch name.

### `README.md`

Defines branch identity, scope, canonical reading order, permanent invariants, acceptance gates, and forbidden scope expansion.

### `MEMORY.md`

Contains durable, evidence-backed decisions future agents must preserve. It must not contain guesses, temporary debugging notes, hidden chain-of-thought, secrets, or unverified claims.

### `PLANS.md`

Contains ordered future work, dependencies, acceptance criteria, validation commands, rollback rules, and explicit non-goals. Planned work must never be described as implemented.

### `PRESENT.md`

Contains current factual state: branch, PR, base/head, divergence, changed files, implemented behavior, missing behavior, tests actually run, known risks, and the exact next action. Update it whenever a material commit changes the branch state.

## Update discipline

For every material change:

1. inspect the diff and base relationship;
2. add or update tests with the behavior;
3. run the narrowest relevant tests first;
4. run broader regression suites before claiming validation;
5. update `PRESENT.md` and `PLANS.md` in the same change or immediately after;
6. record only durable decisions in `MEMORY.md`;
7. keep the branch README aligned with scope and invariants.

Never mark work as:

- `implemented` when only documentation exists;
- `validated` when only compilation or a focused subset passed;
- `runtime-wired` when code is not reached by the supported path;
- `shipped` before merge to the intended target branch.

## Socrates AI permanent invariants

Preserve all of the following:

- Agents judge epistemic quality; CED governs the protocol.
- No self-attestation, self-scoring, self-certification, or self-approval.
- Missing, timed-out, malformed, stale, unbound, or unavailable evidence remains invalid or missing.
- Immutable records are append-only; exact replay may be idempotent, while conflicting reuse is refused.
- Lasting Memory, Identity, Soul, prompt, or governance changes require governed evidence, independent non-self review, recoverable application, probation, and confirmation or rollback.
- Evidence registration is not proposal creation, approval, application, confirmation, promotion, or rollback.
- A receipt or digest proves binding and recording under a contract; it does not prove the semantic claim is true.
- Raw Memory, Identity, Soul, private scratchpads, hidden chain-of-thought, provider secrets, and credentials are never exposed or stored as authority-bearing evidence.
- No branch may silently grant tools, roles, permissions, provider access, council weight, prompt mutation, or CED authority.
- Provider/model execution and prompt lineage must remain externally verifiable and fail closed where exactness is required.

## Personal Memory evidence invariant

Personal agent Memory may not inherit evidence from a whole-council lesson experiment.

The supported G4 chain is:

```text
single-agent matched A/B experiment
    -> retained self-verifying experiment manifest
    -> exact lesson fingerprint
    -> exact governed Identity fingerprint
    -> named non-self attestation
    -> immutable Memory evidence
    -> bounded self-review
    -> agent-authored proposal
    -> independent evaluation
    -> named non-self decision
    -> recoverable application
    -> probation
    -> confirmation or governed unlink rollback
```

The attestation command creates immutable evidence only. It must not edit the lesson catalogue, link or unlink Memory, create or approve a proposal, apply Identity changes, alter prompts, invoke providers, or grant authority.

Personal Memory evidence must be rebound to current governed state at every supported lifecycle boundary:

```text
submit -> evaluate -> decide -> transactional apply
```

Stale lesson content, stale governed Identity, missing fingerprint maps, unbound reports, whole-council reports, self-judging, self-attestation, and conflicting evidence references must fail closed.

## Stacked PR safety

When a PR is stacked:

- verify whether its base PR has merged;
- inspect the live base branch, merge base, and divergence;
- do not retarget, rebase, merge, or force-push blindly;
- preserve only the intended branch-owned diff;
- rerun all affected tests after synchronization;
- update the PR body and branch handoff to the new base/head truth.

## Safety and repository hygiene

- Never commit `.env`, API keys, credentials, tokens, or secret-shaped values.
- Do not modify unrelated files or branches.
- Do not force-push or rewrite history unless explicitly authorized and the recovery target is verified.
- Do not merge merely because focused tests pass.
- Preserve deterministic behavior, strict schemas, fail-closed boundaries, atomic persistence, and immutable evidence semantics.
- Prefer additive, reviewable changes and explicit migration steps.
- When uncertain, inspect code and tests rather than inventing architecture.

## Completion report

Before handing work to another agent or the user, report:

- branch and exact head commit;
- PR base and target state;
- files changed;
- behavior implemented versus still planned;
- tests actually executed and exact results;
- unresolved risks or review findings;
- whether the PR is draft, ready, mergeable, retargeted, or merged;
- the single next recommended action.

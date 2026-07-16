# Socrates AI — Agent Working Contract

This file is the repository-level entry point for coding agents.

## Mandatory startup sequence

Before editing any file:

1. Confirm the current Git branch and repository state.
2. Locate the matching branch workspace under `.agents/branches/`.
3. Read, in this exact order:
   - the branch `README.md`;
   - `PRESENT.md`;
   - `MEMORY.md`;
   - `PLANS.md`.
4. Read every canonical document linked from the branch README.
5. Compare the stated branch status with the actual source, tests, commits, and PR.
6. Correct stale handoff documentation before relying on it.

For branch `agent/prompt-architecture-v2-foundation`, the required workspace is:

```text
.agents/branches/agent-prompt-architecture-v2-foundation/
```

## Source-of-truth hierarchy

When sources disagree, use this order:

1. actual code and validated schemas;
2. passing tests and immutable receipts;
3. current branch and PR metadata;
4. canonical architecture documents;
5. branch `PRESENT.md`;
6. branch `MEMORY.md`;
7. branch `PLANS.md`;
8. historical prose and old phase notes.

Do not treat a plan, README statement, prompt proposal, or prior agent message as proof that runtime behavior exists.

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

Contains durable, evidence-backed decisions that future agents must preserve. It must not contain guesses, temporary debugging notes, hidden chain-of-thought, secrets, or unverified claims.

### `PLANS.md`

Contains ordered future work, dependencies, acceptance criteria, validation commands, rollback rules, and explicit non-goals. Planned work must never be described as implemented.

### `PRESENT.md`

Contains the current factual state: branch, PR, baseline/head, changed files, implemented behavior, missing behavior, tests actually run, known risks, and the exact next action. Update it whenever a material commit changes the branch state.

## Update discipline

For every material change:

1. inspect the diff;
2. add or update tests with the behavior;
3. run the narrowest relevant test first;
4. run broader regression suites before claiming validation;
5. update `PRESENT.md` and `PLANS.md` in the same change or immediately after;
6. record only durable decisions in `MEMORY.md`;
7. keep the branch README aligned with scope and invariants.

Never mark work as:

- `implemented` when only documentation exists;
- `validated` when only compilation or a focused subset passed;
- `runtime-wired` when code is not reached by the canonical path;
- `shipped` before merge to the target branch.

## Socrates AI permanent invariants

Preserve all of the following:

- Agents judge epistemic quality; CED governs the protocol.
- `CEDOrchestrator` remains the sole execution and protocol authority.
- Persistent model/agent identity is separate from temporary role and current task.
- Roles remain deterministic, temporary CED assignments; no model permanently owns a role.
- No self-scoring, self-certification, or self-approval.
- Missing, timed-out, malformed, or unavailable evidence remains missing.
- Blind evaluators do not receive author identity, provider reputation, hidden scores, rankings, or role-fit hypotheses.
- No raw Memory, Identity, Soul, trace, leaderboard, private scratchpad, or hidden chain-of-thought is injected into prompts.
- Lasting Memory, Identity, Soul, prompt, or governance changes require governed evidence, independent non-self review, recoverable application, probation, and confirmation or rollback.
- The requested model ID is not proof of the model or provider route actually returned.
- Exact-model execution must fail closed on unavailable or substituted models; silent fallback or automatic model substitution is forbidden.
- Provider/model/prompt/identity lineage is adapter/CED-owned and externally auditable.
- Tools, external consultation, and Micro-Socratic checks never gain governance authority.

## Micro-Socratic end-state requirement

The canonical target is a real, default-on Micro-Socratic stage for every accepted canonical agent output:

```text
agent draft
    -> exactly one governed Micro-Socratic Kernel check
    -> optional governed observation or bounded revision
    -> final AgentMove
```

The Kernel is not merely text inside the system prompt. It is an external runtime service call with a strict schema and receipt.

It may recommend but may not certify, approve, execute tools, launch consultation by itself, recurse, silently replace the answer, mutate persistent state, or store hidden chain-of-thought.

Compatibility, deterministic mock, and explicit rollback paths may disable runtime invocation only through a documented policy gate. Do not silently bypass a required Kernel failure in production.

## Safety and repository hygiene

- Never commit `.env`, API keys, credentials, tokens, or secret-shaped values.
- Do not modify unrelated files or branches.
- Do not force-push or rewrite history unless the user explicitly authorizes it and the recovery target is verified.
- Do not merge merely because focused tests pass.
- Preserve deterministic behavior and immutable evidence semantics.
- Prefer additive, reviewable changes and explicit migration gates.
- When uncertain, inspect code and tests rather than inventing architecture.

## Completion report

Before handing work to another agent or the user, report:

- branch and exact head commit;
- files changed;
- behavior implemented versus still planned;
- tests actually executed and their exact results;
- unresolved risks or review findings;
- whether the PR is draft, ready, mergeable, or merged;
- the single next recommended action.

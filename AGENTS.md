# Socrates AI Repository Agent Contract

Shared instructions for Codex, Claude Code, Cursor, and other coding agents.

**Goal:** make the smallest correct, test-backed, auditable change while preserving
Socrates AI's epistemic, deterministic, security, and governance invariants.

## 1. Read before writing

Before editing:

1. inspect branch, HEAD, worktree, and existing diff;
2. read the complete relevant implementation, tests, imports, call sites, schemas,
   persisted artifacts, and nearby docs;
3. state scope, assumptions, trade-offs, and a concrete success criterion;
4. distinguish shipped behavior from open PRs, branches, prototypes, and plans;
5. search the repository before claiming an API, field, command, status, file, or
   capability exists.

Do not guess silently. Prefer verified repository facts over memory.

Authority: `README.md` is the canonical overview; `backend/dialogues/README.md` is
the detailed technical reference; focused files under `docs/` govern their contracts.

## 2. Canonical architecture

The governed engine lives under `backend/dialogues/`.

- `CEDOrchestrator` is the sole execution and reasoning-protocol authority.
- Agents receive structured tasks and return structured moves.
- Provider adapters call models but do not decide protocol state.
- Peers supply qualitative judgments; CED validates and aggregates mechanically.
- Council Ratification is council-wide governance, not a permanent chairman.

Treat `socrates_ai.py`, `backend/orchestrator/`, and historical frontends as legacy
prototypes and pattern donors, not canonical production authority.

## 3. Permanent invariants

A change is invalid if CED can:

- fabricate a score or replace missing evidence with zero;
- hide or silently drop failed, timed-out, malformed, or unavailable providers;
- allow self-scoring, self-attestation, self-approval, or self-consultation to count
  as approval;
- expose hidden scores, rankings, scorer identities, provider mappings, or audit
  internals to deliberating agents;
- treat agreement, popularity, or model rank as truth;
- grant one permanent model final authority;
- override a structurally valid critical blocking objection;
- mutate Memory, Identity, Soul, prompts, profiles, or governance outside the
  governed evidence and attestation lifecycle.

Unavailable evidence stays unavailable. Report honest states such as `missing`,
`partial`, `timeout`, `failed`, `disabled`, and `quorum_failed`.

Keep producer, evaluator, approver, and applier separation where required. Preserve
the applicable path from verified observation through immutable evidence,
independent review, recoverable application, probation, confirmation, or rollback.

Runtime-inert foundations remain inert unless integration is explicitly requested
and covered by dedicated tests.

## 4. Determinism and providers

- Role assignment must not depend on provider latency or completion order.
- Keep canonical identifiers, hashing, serialization, and ordering stable.
- Do not add wall-clock time, unordered iteration, random completion order, ambient
  global state, or hidden nondeterminism without an explicit audited contract.
- Exact reruns may be idempotent; conflicting immutable identity or receipt reuse
  must fail closed.
- Test ordering, repetition, and timing variations when they could expose drift.

Provider integrations must:

- pin the exact requested model ID where identity matters;
- forbid silent substitution, automatic selection, and silent fallback;
- fail closed when the required model is unavailable;
- verify and record the model actually returned;
- preserve bounded timeouts, retries, and call budgets;
- retain immutable receipts on governed or reproducibility-sensitive paths;
- pin or allowlist the upstream route for strict reproducibility when supported;
- record retries and repair attempts explicitly.

Provider failure is protocol data, not an inconvenience to conceal.

## 5. Change discipline

Prefer the simplest sufficient solution and a surgical diff.

- Modify only files required by the task.
- Avoid unrelated refactors, formatting, renames, upgrades, and cleanup.
- Reuse abstractions only after confirming semantic fit.
- Do not build a generic framework for one concrete need.
- Do not add configuration for hypothetical variants.
- Avoid new dependencies when existing code or the standard library is sufficient.
- Explain necessity, security, maintenance, and lockfile impact for any dependency.
- Preserve public schemas and persisted artifacts unless a versioned migration is
  explicitly required.
- Prefer additive, versioned evolution over in-place semantic mutation.

If the change spreads into unrelated subsystems, stop and reassess.

## 6. Debugging and root cause

For a bug:

1. read the entire error, traceback, logs, and surrounding context;
2. reproduce the failure before editing;
3. add or identify a focused test that fails for the correct reason;
4. separate observations from hypotheses and test one hypothesis at a time;
5. implement the smallest root-cause fix;
6. rerun the focused test, surrounding tests, then the full relevant suite.

Do not mask symptoms with broad exception handling, default values, retries, or null
checks without explaining why the invalid state arose. Do not change multiple
independent variables at once unless the contract requires an atomic change.

Test meaningful behavior and invariants, not incidental implementation details. If
correct behavior is unusually hard to test, reconsider the design boundary.

Never weaken, delete, skip, xfail, or over-mock a valid test merely to get green.
Do not change expected values until evidence shows the previous contract was wrong.

## 7. Validation

Run narrow tests first, then broaden.

```bash
python -m pytest tests_dialogues -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues -q
```

Useful deterministic smoke paths:

```bash
python -m backend.dialogues.demo
python -m backend.dialogues "Is mathematics discovered or invented?"
```

New behavior needs success and important failure/boundary coverage. Governance
changes need negative tests proving bypasses remain impossible.

Report exact commands and results. Never claim tests passed unless they ran
successfully in the current worktree and environment.

Do not run live-provider tests, spend API credits, or require network access without
explicit authorization and satisfied repository gates. Offline deterministic
execution is the default.

## 8. Security and evidence

- Never read, print, modify, stage, or commit `.env` unless explicitly authorized
  for a local-only change that remains uncommitted.
- Never put secrets, keys, authorization headers, or private prompts in source,
  frontend code, tests, fixtures, receipts, logs, screenshots, or docs.
- Do not persist hidden chain-of-thought or private scratchpads as authority.
- Do not transfer raw private scratchpads between agents or consultations.
- Sanitize upstream payloads from exceptions and receipts when needed.
- Treat immutable evidence and receipts as append-only; refuse conflicting writes.

## 9. Git safety

Inspect full status and diff before staging.

- Never stage unrelated user changes; prefer explicit paths in mixed worktrees.
- Do not amend, rebase, reset, force-push, delete branches, or rewrite history
  without explicit authorization.
- Do not commit, push, open or modify a PR, merge, or change GitHub state without
  explicit authorization for that action.
- Commit or push permission does not imply merge permission.
- Preserve the user's branch and uncommitted work.
- Confirm the remote points to the commit claimed as pushed.

## 10. Completion and stop conditions

Report exact files and behavior changed, architectural compatibility, tests actually
run, remaining risks, and branch/commit/PR state only when applicable.

Stop instead of guessing when a request violates a permanent invariant,
authoritative schemas conflict, required permissions are unavailable, unrelated work
cannot be isolated, or tests reveal a wider contract change than requested.

A partial honest result is better than a broad unverified rewrite.

> Read the real system. Preserve the invariants. Make the smallest correct change.
> Prove it with evidence. Never hide failure.

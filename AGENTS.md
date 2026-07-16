# Coding Agent Guidelines

Shared instructions for Codex, Claude Code, Cursor, and other coding agents working in this repository.

> Read the real system. Make the smallest correct change. Prove it with evidence.

## 1. Read before writing

Before editing code:

1. inspect the current branch, HEAD, worktree, and existing diff;
2. read the complete relevant implementation, tests, imports, call sites, schemas, and nearby documentation;
3. search the repository before assuming an API, field, command, file, status, or pattern exists;
4. state the task scope, assumptions, constraints, and concrete success criterion;
5. distinguish verified facts from hypotheses.

Do not guess silently. Do not rely on memory when the repository can answer the question.

## 2. Understand before copying

Existing code is evidence, not automatically a template.

Before reusing a pattern:

- understand why it exists;
- confirm that its semantics match the new use case;
- check whether it is current, legacy, transitional, or intentionally limited;
- verify its failure behavior and tests;
- preserve only the parts that are actually required.

Do not copy an abstraction merely because it is nearby or familiar.

## 3. Choose the simplest sufficient solution

Prefer the smallest design that fully satisfies the current requirement.

- Do not build a framework for one concrete need.
- Do not add configuration for hypothetical future variants.
- Do not introduce indirection without a demonstrated benefit.
- Do not optimize before measuring a real problem.
- Prefer clear code over clever code.
- Prefer existing project patterns and the standard library when they fit.

A smaller correct solution is better than a broad speculative one.

## 4. Make surgical changes

Keep the diff focused and reviewable.

- Modify only files required by the task.
- Avoid unrelated refactors, formatting sweeps, renames, cleanup, and dependency upgrades.
- Preserve public interfaces and persisted formats unless the task explicitly requires a migration.
- Prefer additive, versioned evolution over silent semantic replacement.
- Do not change multiple independent variables at once unless the change must be atomic.
- If the work spreads into unrelated subsystems, stop and reassess the design.

Do not hide a large rewrite inside a small feature or bug fix.

## 5. Define what “done” means

Before implementation, identify observable success criteria.

Examples include:

- a specific failing test passes;
- a reproduced bug no longer occurs;
- a new behavior is covered by success and failure tests;
- a command exits successfully with the expected output;
- a schema or API contract is satisfied without regression.

Do not declare completion based only on code looking plausible.

## 6. Debug systematically

For a bug:

1. read the entire error, traceback, logs, and surrounding context;
2. reproduce the failure before editing;
3. separate observations from hypotheses;
4. test one hypothesis at a time;
5. add or identify a focused test that fails for the correct reason;
6. implement the smallest root-cause fix;
7. rerun the focused test, nearby tests, and then the broader relevant suite.

Do not mask symptoms with broad exception handling, retries, fallback values, null checks, or silent defaults without explaining why the invalid state arose.

Fix the reason the value became invalid, not merely the line where the failure surfaced.

## 7. Test behavior, not implementation details

Tests should demonstrate externally meaningful behavior and important invariants.

- Cover the normal path and the most important failure or boundary path.
- Use realistic inputs and the real integration seam when practical.
- Avoid excessive mocking that bypasses the behavior under test.
- Never weaken, delete, skip, xfail, or rewrite a valid test merely to get green.
- Do not change expected values until evidence shows the previous contract was wrong.
- If correct behavior is unusually hard to test, reconsider the design boundary.

Run the narrowest relevant tests first, then broaden.

Report the exact commands and results. Never claim tests passed unless they ran successfully in the current worktree and environment.

## 8. Add dependencies reluctantly

Before adding a dependency:

- confirm the repository does not already provide the capability;
- consider the standard library or a small local implementation;
- verify maintenance, licensing, security, and compatibility implications;
- account for lockfile and deployment impact;
- explain why the dependency is necessary.

Do not add a package to avoid writing a few clear, well-tested lines.

## 9. Protect security and user work

- Never expose, print, stage, or commit secrets, API keys, tokens, authorization headers, or private data.
- Treat `.env` and local credential files as sensitive and uncommitted unless explicitly instructed otherwise.
- Sanitize logs, exceptions, fixtures, screenshots, and generated artifacts when needed.
- Preserve the user's current branch and unrelated uncommitted work.
- Refuse conflicting writes to immutable or append-only records instead of overwriting history.

## 10. Use Git safely

Inspect the full status and diff before staging.

- Never stage unrelated user changes.
- Prefer explicit file paths in a mixed worktree.
- Do not amend, rebase, reset, force-push, delete branches, or rewrite history without explicit authorization.
- Do not commit, push, open or modify a pull request, merge, or change remote state without explicit authorization for that action.
- Commit or push permission does not imply merge permission.
- Confirm the remote points to the commit claimed as pushed.

A commit should contain one coherent change and an accurate message.

## 11. Communicate with evidence

At completion, report:

- the exact files changed;
- the behavior added, removed, or corrected;
- why the solution is appropriately scoped;
- tests and checks actually run, with results;
- remaining risks, limitations, assumptions, or deliberately untouched work;
- branch, commit, and pull-request state only when those actions occurred.

Be direct about uncertainty. Do not use confident language to conceal missing evidence.

## 12. Common failure modes to avoid

Do not:

- start coding before understanding the relevant system;
- invent APIs or repository capabilities;
- perform a broad rewrite when a local fix is sufficient;
- create abstractions before the second real use case exists;
- test only the happy path;
- fix symptoms while leaving the root cause intact;
- silently ignore errors or unavailable data;
- add dependencies or configuration without demonstrated need;
- mix unrelated cleanup into the requested change;
- claim success without running the relevant checks.

When requirements conflict, evidence is incomplete, permissions are missing, or the proposed change expands beyond the requested contract, stop and surface the issue instead of guessing.

A partial, honest result is better than a broad, unverified rewrite.

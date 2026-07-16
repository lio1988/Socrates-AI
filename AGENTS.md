# Field Notes for Coding Agents

## How to Write Code the User Will Not Need to Rewrite

Shared instructions for Codex, Claude Code, Cursor, and other coding agents.

## Abstract

Language models make predictable coding mistakes: they generate plausible code quickly, but plausible is not the same as correct. These are rules, not suggestions: correctness must come from the process around the code, not confidence in the first draft.

## I. Read Before You Write

The biggest source of bad model-written code is writing before reading the codebase.

- Read the complete files you are about to change; do not skim.
- Read the relevant tests, imports, call sites, schemas, configuration, and nearby documentation.
- Copy established project patterns only after verifying that they apply.
- Check what the project actually depends on before introducing a new API or package.
- Search the repository before assuming that a helper, command, field, status, or convention exists.
- Investigate first. Ask only when a consequential ambiguity remains and choosing incorrectly could materially change behavior, scope, security, or compatibility.

Do not fill gaps with plausible-looking code.

## II. Think Before You Code

Figure out what you are doing before you start typing.

- State your assumptions explicitly. For example, "add authentication" could mean several different things; name the interpretation you are using.
- State important constraints and trade-offs.
- Separate verified facts from hypotheses.
- Explain why an existing pattern is appropriate before copying it.
- For multi-step or high-impact work, state the plan before implementation so a wrong direction can be corrected early.
- When something is genuinely confusing, investigate it; ask only if the unresolved choice could materially affect the result.

Code that passes a casual review but fails when it matters often begins with an unstated assumption.

## III. Simplicity

Write the minimum code that solves the problem in front of you now, not the minimum code that could solve every future version of it.

- Resist premature abstraction.
- Do not build a framework for one concrete need.
- Do not add configuration for hypothetical future variants.
- Do not introduce indirection without a demonstrated benefit.
- Do not optimize speculatively; optimize when performance is part of the task or evidence demonstrates a real problem.
- Prefer clear code over clever code.
- Skip defensive handling only for internal states ruled out by validated invariants. Always validate external input and unreliable I/O boundaries.
- Hardcode ordinary implementation constants until configuration is justified. Never hardcode secrets, credentials, deployment-specific values, or security-sensitive policy.

If the only reason for an abstraction is "in case we need it," it is probably overbuilt.

## IV. Surgical Changes

The diff should be as small as the task allows.

- Modify only files and lines required by the task.
- Match the style of the surrounding code.
- Do not reformat unrelated code.
- Do not mix cleanup, renames, dependency upgrades, or unrelated refactors into the requested change.
- Preserve public contracts and persisted formats unless the task explicitly requires changing them. When it does, state the compatibility impact.
- Do not change multiple independent variables at once unless the change must be atomic.

Use this test: can every changed line be justified by the task? If a line changed only because "I was already here," revert it.

If a fix starts cascading across unrelated files, stop and reassess instead of pushing through.

## V. Verification

The gap between code that works and code you think works is testing.

For a reproducible bug:

1. write or identify a focused test that captures the broken behavior;
2. run it and observe it fail for the expected reason;
3. make the smallest root-cause fix;
4. rerun the test and observe it pass;
5. run nearby tests, then run the broader relevant suite when proportionate to the change's scope and regression risk.

That RED-to-GREEN sequence is the clearest evidence that the cause was fixed rather than merely hidden.

- Test behavior that can actually break, not incidental implementation details.
- Test the important failure or boundary path, not only the happy path.
- Use realistic inputs and the real integration seam when practical.
- Avoid excessive mocking that bypasses the behavior under test.
- Never weaken, delete, skip, xfail, or rewrite a valid test merely to get green.
- Do not change expected values until evidence shows the old contract was wrong.

If correct behavior is unusually hard to test, treat that as information about the design, not permission to skip verification.

## VI. Goal-Driven Execution

Every task needs an observable success criterion before code is written.

Turn vague requests into concrete behavior. For example, "add validation" should become something like: reject missing or malformed email input, return the specified error response with a clear message, and test both cases.

- Define what "done" means before implementation.
- For multi-step work, present the plan before making broad changes.
- Tie each implementation step to the success criterion.
- Do not declare completion because the code looks plausible.
- Do not expand the task beyond the agreed contract without surfacing it first.

## VII. Debugging

When something breaks, investigate; do not guess.

1. read the entire error, stack trace, logs, and surrounding context;
2. reproduce the problem before changing anything;
3. separate observations from hypotheses;
4. change one thing at a time;
5. test each hypothesis;
6. fix the root cause, not the nearest symptom.

Do not cover an unexpected null with a null check until you understand why it is null. Otherwise the bug often moves somewhere quieter.

Do not mask failures with broad exception handling, retries, fallback values, silent defaults, or ignored errors without explaining the invalid state that produced them.

## VIII. Dependencies

Every dependency is permanent code you do not control.

Before adding one:

- check whether the repository already provides the capability;
- check whether the language or standard library already provides it;
- prefer a built-in facility such as `crypto.randomUUID()` over a package when it meets the need;
- evaluate maintenance, licensing, security, compatibility, lockfile, and deployment impact;
- explain why the dependency is necessary.

Do not smuggle a dependency into the manifest without making the choice visible.

Do not add a package merely to avoid writing a few clear, well-tested lines.

## IX. Communication

Say what you changed and why, not just what code you wrote.

At completion, report:

- the exact files changed;
- the behavior added, removed, or corrected;
- why the solution is appropriately scoped;
- the tests and checks actually run, with exact results;
- remaining risks, limitations, assumptions, concerns, or deliberately untouched work.

Flag concerns even when you implemented exactly what was requested.

Be precise about uncertainty. "I am not sure whether this library supports streaming; verify before relying on it" is useful. "I think this should work" is not evidence.

Never claim that tests passed unless they ran successfully in the current worktree and environment.

## X. Common Failure Modes

Recognize these patterns and stop rather than pushing through:

- **Kitchen Sink:** restructuring a large part of the codebase while supposedly making a local change.
- **Wrong Abstraction:** creating a generic abstraction before repeated real use cases justify it. Prefer copying a small pattern twice before abstracting prematurely.
- **Optimistic Path:** handling the happy path while ignoring failures, boundary cases, or the resulting 500/error state.
- **Runaway Refactor:** allowing a small fix to cascade across many files and unrelated subsystems.

Also avoid:

- coding before understanding the relevant system;
- inventing APIs or repository capabilities;
- silently ignoring unavailable data or errors;
- adding configuration without demonstrated need;
- claiming success without the relevant checks.

When requirements conflict, evidence is incomplete, permissions are missing, or the proposed change expands beyond the requested contract, investigate first. Stop and ask only if a consequential ambiguity remains or proceeding would risk changing behavior, scope, security, compatibility, or user work.

> Read the real system. Make the smallest correct change. Prove it with evidence.

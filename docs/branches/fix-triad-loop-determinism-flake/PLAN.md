# Branch: fix/triad-loop-determinism-flake

## Success criterion

Eliminate Windows same-tick learning ID collisions at their production source,
prove stable triad identity remains insensitive only to genuinely volatile
record IDs, and keep all semantic-change sensitivity and full suites green.

## Scope

- `backend/dialogues/learning_foundation.py`
- `tests_dialogues/test_learning_triad_loop.py`
- This branch-documentation folder

## Non-goals

- No test-order fixture workaround.
- No retry, delay, fixed random seed, `xfail`, skip, or relaxed assertion.
- No broad learning-stack refactor.
- No Council Live View changes.

## Ordered implementation steps

1. Reproduce the exact `loop_id` assertion failure.
2. Collect suite order and test the failing node with an empty prefix.
3. Recursively compare raw summaries and stable identity payloads.
4. Identify same-tick timestamp-only `trace_id` collisions.
5. Add an opaque UUID suffix while retaining the readable timestamp.
6. Add a frozen-clock regression with controlled volatile UUID values.
7. Prove equal semantic inputs retain equal IDs and changed semantics alter IDs.
8. Run 20 fresh processes and all full validation gates.
9. Stop before stage, commit, push, or PR creation.

## Validation gates

- Frozen-clock focused regression passes.
- Minimal node passes 20/20 in fresh Python processes.
- Full triad-loop file passes.
- Two consecutive full `tests_dialogues` runs pass.
- Repository-wide pytest passes.
- Compileall and `git diff --check` pass.
- Final diff contains only the two implementation/test files and branch docs.

## Stop conditions

- Stop if semantic fields would need removal from hashes.
- Stop if the fix would require Council Live View changes.
- Stop on any unexplained validation failure.
- Do not stage, commit, push, or open a PR without a separate GO.

## Completed

- RED failure, collection order, empty-prefix reproducer, and structured diff
  captured.
- Production root cause identified and fixed.
- Focused frozen-clock and semantic-change regression added.
- Fresh-process stress, both full dialogue runs, repository-wide pytest,
  compileall, and whitespace validation completed successfully.

## Remaining / deferred work

- Review, commit, and publish only after a separate GO.

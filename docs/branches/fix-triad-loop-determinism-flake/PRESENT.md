# Branch: fix/triad-loop-determinism-flake

## Branch

`fix/triad-loop-determinism-flake`

## Base HEAD

`49c254efe77df14abc31c881e0613c92f0a53476`

## Verified implementation head

`345dcb2df341634a84a0b6d3cad1550b845ce244`

## Completed work

- Proved the failing node needs no polluting predecessor.
- Captured timestamp-only `trace_id` collision and downstream semantic changes.
- Made opaque learning IDs collision-safe with a UUID suffix.
- Added a deterministic frozen-clock regression.
- Preserved the canonical volatile-key policy and all semantic hash fields.

## Remaining work

- PR review and merge into `main` only.

## Changed files

- `backend/dialogues/learning_foundation.py`
- `tests_dialogues/test_learning_triad_loop.py`
- `docs/branches/fix-triad-loop-determinism-flake/README.md`
- `docs/branches/fix-triad-loop-determinism-flake/MEMORY.md`
- `docs/branches/fix-triad-loop-determinism-flake/PLAN.md`
- `docs/branches/fix-triad-loop-determinism-flake/PRESENT.md`

## Exact RED result

- Failing assertion: `result_a.loop_id == result_b.loop_id`
- Values: `triad_bf053268f9f1eefe` versus
  `triad_3248ae1340b428b8`
- Standalone failing node: **1 failed**
- Minimal polluting sequence: empty prefix plus the failing node

## Exact GREEN results

- Frozen-clock focused regression: **1 passed**
- Full triad-loop file: **6 passed**
- Fresh-process stress: **20/20 passed**
- Full `tests_dialogues`, run 1: **1563 passed**
- Full `tests_dialogues`, run 2: **1563 passed**
- Repository-wide pytest: **1870 passed, 24 warnings**
- `python -m compileall -q backend tests_dialogues`: pass
- `git diff --check`: pass

## Root cause

Timestamp-only `_uid()` values could collide for adjacent Windows records.
Miners keyed by `trace_id` then collapsed two semantic traces and changed
transition, artifact, trainer, learner, feedback, and loop output.

## Production delta

One production file changes:
`backend/dialogues/learning_foundation.py`.

## Blockers

None identified.

## Worktree state

The implementation is committed at the verified head above. This document and
the other branch handoff documents are committed separately as documentation
only.

## Next safe step

Review and merge this branch into `main`, then rebuild the Council Live View
integration branch from the updated `main`.

## Review status

Frozen and review-only after publication; no further changes except findings
that belong exclusively to this fix.

## Independence

Council Live View PRs #71–#74 and the existing integration branch are
untouched.

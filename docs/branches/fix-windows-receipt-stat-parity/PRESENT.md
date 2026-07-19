# Branch: fix/windows-receipt-stat-parity

## Base HEAD

`b699dad275a9c8824811b0c7307a688f700d3eb2`

## Verified implementation head

`4f2854d6600217dfadb387dd48e12c7285d8a651`

This is the implementation commit covered by the RED/GREEN validation results
below. Any later commit on this branch must be documentation-only.

## Completed work

- Created an isolated branch and worktree from the exact current `origin/main`.
- Reproduced the four-case Windows baseline failure before editing.
- Added an instance-level `_path_for` seam to isolate final
  existence-discovery fault injection.
- Kept the strict single-stat assertion and safe-error/no-artifact checks.
- Completed all requested Python 3.12 and Python 3.11 validation.
- Committed the validated implementation without changing production code.

## Remaining work

- PR review and merge only.

## Changed files

- `tests_dialogues/test_shared_receipt_store_parity.py`
- `docs/branches/fix-windows-receipt-stat-parity/README.md`
- `docs/branches/fix-windows-receipt-stat-parity/MEMORY.md`
- `docs/branches/fix-windows-receipt-stat-parity/PLAN.md`
- `docs/branches/fix-windows-receipt-stat-parity/PRESENT.md`

## Exact test results

- RED baseline at exact `origin/main`, Python 3.12.13 / pytest 9.1.1:
  **4 failed in 2.58s**.
- Targeted post-fix test, Python 3.12: **4 passed in 0.91s**.
- Full parity file, Python 3.12: **100 passed in 3.33s**.
- Full `tests_dialogues`, Python 3.12: **1563 passed in 37.55s**.
- Repository-wide pytest, Python 3.12:
  **1870 passed, 24 warnings in 42.00s**.
- Full parity file, Python 3.11.15 / pytest 9.1.1:
  **100 passed in 3.12s**.
- `python -m compileall -q backend tests_dialogues`: exit 0.
- The previous Learning Stack gate was not repeated because no learning code
  changed.

The totals on this branch are lower than the Council Live View integration
totals by exactly 265 tests because this branch starts from `origin/main` and
intentionally excludes the frozen Council Live View stack.

## Production delta

**0 production files changed.** Receipt-store implementation, wrappers, and
error contracts are unchanged.

## Blockers

None.

## Worktree state

Clean after the docs-only handoff commit. Verify dynamically with
`git status --short`.

## Next safe step

Merge this PR into `main` after review, then rebuild the Council Live View
integration branch from the updated `main`.

## Frozen / review-only status

The branch is frozen and review-only after the documentation-finalization
commit. No production, test, workflow, or additional documentation changes are
permitted without a new finding scoped to this PR.

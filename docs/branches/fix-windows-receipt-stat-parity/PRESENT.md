# Branch: fix/windows-receipt-stat-parity

## Base HEAD

`b699dad275a9c8824811b0c7307a688f700d3eb2`

## Completed work

- Created an isolated branch and worktree from the exact current `origin/main`.
- Reproduced the four-case Windows baseline failure before editing.
- Added an instance-level `_path_for` seam to isolate final
  existence-discovery fault injection.
- Kept the strict single-stat assertion and safe-error/no-artifact checks.
- Completed all requested Python 3.12 and Python 3.11 validation.

## Remaining work

- Review the exact diff and worktree status.
- Commit and push only after a separate GO.

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

## Blockers

None.

## Worktree state

Uncommitted test and branch-documentation changes are present. No production
file is modified, and no commit or push has been made.

## Next safe step

Review the exact diff, then commit only after explicit approval.

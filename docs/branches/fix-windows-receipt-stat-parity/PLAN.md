# Branch: fix/windows-receipt-stat-parity

## Success criterion

Isolate final existence-discovery fault injection from Windows
`Path.resolve()` internals, restore the expected four-case parity result, and
keep the complete Python 3.12 repository suite green without production
changes.

## Scope

- One local test seam in the shared receipt-store parity test.
- Branch documentation for the baseline Windows fix.
- Python 3.12 and Python 3.11 validation.

## Non-goals

- Production receipt-store changes.
- Consultation/kernel wrapper changes.
- Workflow or dependency changes.
- Any Council Live View branch or PR change.

## Ordered implementation steps

1. Create the branch from the exact current `origin/main`.
2. Reproduce and record the four-case RED baseline in clean Python 3.12.
3. Add the `_path_for` test seam and explanatory comment.
4. Run targeted, file-level, dialogue-wide, and repository-wide validation.
5. Run Python 3.11 parity-file validation, compile, diff, and status gates.
6. Stop before commit and push for review.

## Validation gates

- Targeted four-case test passes on Python 3.12.
- Full parity file passes on Python 3.12 and Python 3.11.
- Full `tests_dialogues` passes on Python 3.12.
- Repository-wide pytest passes on Python 3.12.
- `python -m compileall -q backend tests_dialogues` passes.
- `git diff --check` is clean.
- Only the parity test and this branch-doc folder change.

## Stop conditions

- Stop if any production file, Council Live View ref, or unrelated test would
  need modification.
- Stop on any unexplained validation failure.
- Do not commit or push until explicit approval.

## Completed

- Isolated branch/worktree created from exact `origin/main`.
- Clean Python 3.12 RED baseline recorded.
- Minimal test seam and branch documentation added.
- Targeted, parity-file, dialogue-wide, and repository-wide Python 3.12 gates
  passed.
- The parity file passed in a fresh Python 3.11 environment.
- Compile and diff-integrity gates passed.

## Remaining / deferred work

- Review the exact uncommitted diff and validation report.
- Commit and push only after a separate GO.

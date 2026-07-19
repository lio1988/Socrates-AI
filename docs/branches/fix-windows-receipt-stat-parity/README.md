# Branch: fix/windows-receipt-stat-parity

## Purpose

Fix a baseline Windows-only test-isolation failure in the shared receipt-store
parity matrix. The test must inject a failure only into final receipt
existence discovery, without counting internal `Path.resolve()` filesystem
probes as discovery attempts.

This branch is independent of the Council Live View stack and does not modify
PRs #71–#74 or any of their frozen branches.

## Success criterion

The four `PermissionError`/`OSError` consultation/kernel cases pass on Windows
while retaining the strict single-discovery assertion, and the full Python
3.12 repository suite remains green.

## Scope

- Add an instance-level `_path_for` seam to one parity test.
- Explain why the seam isolates the intended operation.
- Record the baseline failure, validation, and handoff in branch docs.

## Non-goals

- No receipt-store production changes.
- No error-contract or wrapper changes.
- No Council Live View code, branch, PR, or documentation changes.
- No workflow changes.

## Branch documents

- [MEMORY.md](MEMORY.md)
- [PLAN.md](PLAN.md)
- [PRESENT.md](PRESENT.md)

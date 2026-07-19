# Branch: fix/triad-loop-determinism-flake

## Purpose

Fix an independent Windows learning-pipeline flake where timestamp-only
learning record IDs could collide within one clock tick and change semantic
triad-loop output.

This branch starts from `main` at
`49c254efe77df14abc31c881e0613c92f0a53476` and is independent of Council Live
View PRs #71–#74 and their integration branch.

## Success criterion

Distinct learning records always receive distinct opaque IDs even under a
frozen clock, identical semantic triad inputs retain identical stable IDs, and
semantic input changes still change those IDs.

## Scope

- Make learning foundation IDs collision-safe.
- Add a focused frozen-clock triad determinism regression.
- Validate the minimal reproducer, full dialogue suite, and repository suite.

## Non-goals

- No retry, sleep, seed workaround, skip, `xfail`, or weakened assertion.
- No removal of semantic fields from deterministic hashes.
- No Council Live View code, branch, PR, or integration change.

## Branch documents

- [MEMORY.md](MEMORY.md)
- [PLAN.md](PLAN.md)
- [PRESENT.md](PRESENT.md)

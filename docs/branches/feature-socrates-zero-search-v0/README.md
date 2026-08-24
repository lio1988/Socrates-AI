# feature/socrates-zero-search-v0

## Purpose

Build SocratesZero as a governed, optional search layer around canonical CED,
starting from runtime-inert contracts, a read-only board-state projection, hard
legal moves, and the unchanged fixed-rotation baseline.

## Success criterion

Every experimental strategy can observe deterministic canonical state and may
select only CED-legal actions, while default CED execution and Hybrid epistemic
authority remain unchanged.

## Scope

This branch contains the search boundary ADR, immutable contracts, explicit
fixed baseline, trusted CED-side projection, deterministic legal-action
constitution, tests, and durable checkpoints.

## Non-goals

No production action control, heuristic/learned Policy or Value, MCTS, RL,
neural dependency, CUDA path, or live API call is part of the current milestone.

Baseline HEAD: `277ca2ec130ce120dba9c4d894a3c58138b25528`.

The canonical CED, provider routing, peer scoring, assembly, Hybrid epistemic
authority, ratification, release, observers, receipts, and learning behavior
remain unchanged. The task-spec extraction is consumed by the existing phase
runner, but no search strategy is wired into production execution.

The architectural decision is recorded in
`docs/ADR_SOCRATES_ZERO_SEARCH_BOUNDARY.md`.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

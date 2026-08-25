# feature/socrates-zero-search-v0

## Purpose

Build SocratesZero as a governed, optional search layer around canonical CED,
starting from runtime-inert contracts, a read-only board-state projection, hard
legal moves, the unchanged fixed-rotation baseline, and deterministic advisory
Policy/Value plus Greedy, one-ply Best-of-N, and bounded one-real-ply PUCT
strategy baselines. Phase 5 adds a frozen offline matched-compute evaluation of
those strategies; it adds no runtime control. Phase 5.5 adds the sealed
evidence review and selects canonical epistemic observability as exactly one
next uncertainty; it implements none of the selected work.

## Success criterion

Every experimental strategy can observe deterministic canonical state and may
select only CED-legal actions, while default CED execution and Hybrid epistemic
authority remain unchanged.

## Scope

This branch contains the search boundary ADR, immutable contracts, explicit
fixed baseline, trusted CED-side projection, deterministic legal-action
constitution, model-free heuristic/uniform PolicyPrior implementations, tests,
model-free neutral/heuristic ValueEstimator implementations, and durable
checkpoints. It now also contains deterministic Greedy and budgeted Best-of-N
selectors, the injected experimental successor-state contract, and bounded
serial `puct-strategy/v0` with a rich deterministic companion audit receipt.
It also contains the frozen Phase 5 harness, balanced deterministic cases,
fairness/isolation tests, runner, machine-readable result, and methodology.
The documentation-only Phase 5.5 gate reconstructs all eleven runs, attributes
Policy, Value, successor observation and PUCT effects, audits SearchState and
depth-two blockers, rejects premature learning/RL, and freezes the next
hypothesis in `docs/SOCRATES_ZERO_PHASE5_5_DECISION_GATE.md`.

## Non-goals

No production action control, canonical successor executor, trusted recursive
multi-ply transition, shadow wiring, Gumbel/MuZero, progressive widening,
parallel MCTS, learned Policy/Value, RL, neural dependency, CUDA path, or live
API call is part of the current milestone. Phase 5.5 also makes no SearchState,
projection, Value, Policy, strategy, successor, CED, provider, benchmark, or
training change.

Baseline HEAD: `277ca2ec130ce120dba9c4d894a3c58138b25528`.

The canonical CED, provider routing, peer scoring, assembly, Hybrid epistemic
authority, ratification, release, observers, receipts, and learning behavior
remain unchanged. The task-spec extraction is consumed by the existing phase
runner, but no search strategy is wired into production execution.

The architectural decision is recorded in
`docs/ADR_SOCRATES_ZERO_SEARCH_BOUNDARY.md`; the Phase 5.5 evidence decision is
recorded in `docs/SOCRATES_ZERO_PHASE5_5_DECISION_GATE.md`.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

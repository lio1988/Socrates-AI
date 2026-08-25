# Branch: feature/socrates-zero-heuristic-value-v1

## Purpose

Test the single Phase 6.5 hypothesis that one penalty-only, deterministic Value
v1 over canonical SearchState v1 can improve lawful current-state ranking over
Value v0 without rewarding support, closure, record volume, or derived signals.

## Success criterion

Freeze the estimator semantics and all 45 canonical state-pair cases before the
first holdout execution; then pass every pre-registered primary ranking,
nonterminal, guardrail, safety, replay, compatibility, and offline test gate.
Run the secondary matched BestOfN experiment only if the primary gate passes.

## Scope

This branch may add `heuristic-value-estimator/v1`, its structured audit,
canonical-state-pair evaluation contracts and fixtures, an immutable result
artifact, tests, methodology/results documentation, and—only after a passing
primary gate—the frozen secondary BestOfN comparison.

## Non-goals

No modification of Value v0, SearchState/projection v0 or v1, Policy, legal
actions, successor semantics, Greedy, BestOfN, PUCT, CED/Hybrid authority,
Phase 5 artifacts, providers, depth two, learned Value, RL, or production
wiring. No live calls and no post-holdout tuning.

## Result

Both pre-registered gates passed. The authoritative primary holdout improved
ordered accuracy from `2/7` under Value v0 to `7/7` under Value v1 with all
required ties and hard-safety gates passing. The separately frozen matched
BestOfN test improved selection from `2/7` to `7/7` without resource or
guardrail regression. See
[`docs/SOCRATES_ZERO_VALUE_V1_PHASE7.md`](../../SOCRATES_ZERO_VALUE_V1_PHASE7.md).

Phase 7.5 then completed the required documentation-only architecture gate.
It selected **CANONICAL SUCCESSOR ENVIRONMENT NEXT** because real shadow
collection cannot yet reuse an isolated CED-owned action transition. The
selected next branch is
`feature/socrates-zero-canonical-successor-env-v0`; it is an offline
one-transition parity/isolation foundation, not depth two. See
[`docs/SOCRATES_ZERO_PHASE7_5_ARCHITECTURE_DECISION_GATE.md`](../../SOCRATES_ZERO_PHASE7_5_ARCHITECTURE_DECISION_GATE.md).

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

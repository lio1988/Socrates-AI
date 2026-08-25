# Branch: feature/socrates-zero-canonical-observability-v1

## Success criterion

Prove or falsify that a minimal opt-in v1 projection can safely preserve useful
current-time canonical epistemic structure hidden or omitted by v0.

## Ordered work

1. [done] Verify repository truth and audit candidate upstream authorities.
2. [in progress] Define separately versioned immutable v1 observation contracts.
3. [pending] Implement the trusted read-only projection with source validation.
4. [pending] Prove v0 alias/v1 separation with canonical Hybrid record fixtures.
5. [pending] Prove no invention, metadata immunity, temporal isolation, purity,
   deterministic identity, provenance, and fail-closed behavior.
6. [pending] Verify the sealed artifact and all focused/full regression gates.
7. [pending] Complete the ADR/report and durable branch checkpoint, then stop at
   the Value v1 Decision Gate.

## Non-goals and stop conditions

Do not modify Value, Policy, strategies, successor semantics, benchmarks, CED
execution, providers, shadow orchestration, learning, RL, or production wiring.
Stop and document a negative result if useful separation requires inference,
future information, prose interpretation, or duplicated authority.

## Validation gates

The required gates are v1-specific tests; v0 projection/contracts; Policy,
Value, Greedy, BestOfN, PUCT, and Phase 5 evaluation regressions; the full
SocratesZero bundle; Hybrid H8 plus SocratesZero; focused CED/Socratic tests;
all `tests_dialogues`; repository-wide tests; artifact SHA/blob equality; and
`git diff --check`, all with exact counts and zero live calls.

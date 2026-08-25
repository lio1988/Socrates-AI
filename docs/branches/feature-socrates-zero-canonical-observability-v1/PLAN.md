# Branch: feature/socrates-zero-canonical-observability-v1

## Success criterion

Prove or falsify that a minimal opt-in v1 projection can safely preserve useful
current-time canonical epistemic structure hidden or omitted by v0.

## Ordered work

1. [done] Verify repository truth and audit candidate upstream authorities.
2. [done] Define separately versioned immutable v1 observation contracts.
3. [done] Implement the trusted read-only projection with source validation.
4. [done] Prove v0 alias/v1 separation with canonical Hybrid record fixtures.
5. [done] Prove no invention, metadata immunity, temporal isolation, purity,
   deterministic identity, provenance, and fail-closed behavior.
6. [done] Verify the sealed artifact and all focused/full regression gates.
7. [done] Complete the ADR/report and durable branch checkpoint, then stop at
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

## Completion decision

All gates pass. The observability hypothesis is `SUPPORTED`. Stop before Value
v1; the next authorized activity, if separately requested, is a Value v1
Decision Gate on a new evaluation version.

## Phase 6.5 Value v1 decision gate

1. [done] Audit every new v1 field for authority, timing, direction, derivation,
   double-counting, reward hacking, and leakage.
2. [done] Build the Evidence/Verification/Lifecycle -> ClaimAssessment
   derivation graph and select one highest-authority representative.
3. [done] Audit every VerificationResult, SupportState, lifecycle transition,
   Phase 6 alias, and Phase 5 value-uninformative case.
4. [done] Freeze a penalty-only rule shape, precedence, constants, terminal
   firewall, audit requirements, and authority firewall without implementation.
5. [done] Pre-register a new 18-development/27-holdout pairwise evaluation,
   primary Value metric, secondary BestOfN test, and falsification thresholds.
6. [done] Run required observability/evaluation/artifact/diff gates and
   complete the durable documentation checkpoint.

Decision: `VALUE V1 IMPLEMENTATION EARNED`. Exactly one next branch is
`feature/socrates-zero-heuristic-value-v1`. No estimator implementation belongs
to Phase 6.5.

# Branch: feature/socrates-zero-openrouter-prelive-integration-v1

Phase 8.5D-S6 — OpenRouter Response-Mapping Integration & Pre-Live Safety.

Binds the proven components into one causal, fail-closed, offline shadow
pipeline, and decides whether the next phase may perform one live shadow call.

## Hypothesis

> A deterministic shadow integration layer can causally bind one exact
> request-intent record to one bounded acquisition/transport execution, one raw
> response observation, and one S5 normalized wire-mapping result, while
> preventing cross-request substitution, response swapping, request-derived
> response authority, retry ambiguity, authority escalation, and privacy leakage;
> and the system can define a fail-closed pre-live budget/safety contract that
> identifies exactly which remaining conditions must be satisfied immediately
> before one live shadow call.

## Four layers, kept four layers

    RequestIntentReceipt -> TransportExecutionRecord -> RawWireObservation
                         -> RawWireMappingResult -> PreLiveIntegrationReceipt

The integration receipt is evidence *about* the chain and never replaces it.

## Scope

Additive only: `openrouter_pre_live_integration_v1`, `…_safety_v1`, `…_cases_v1`,
`…_evaluation_v1`, focused tests, branch documentation, one authoritative
artifact with replay execution and lock.

## Non-goals

No live call. No provider, model or credential access. No production wiring. No
CED consumption. No runtime authority. No change to S5, Route Controls v1 or the
Acquisition Contract v0.

## Documents

- [MEMORY.md](MEMORY.md) — invariants and the findings that shaped the design.
- [PLAN.md](PLAN.md) — plan, predeclared thresholds, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state.
- [artifacts/README.md](artifacts/README.md), [evidence/README.md](evidence/README.md).

Canonical result:
[docs/SOCRATES_ZERO_OPENROUTER_PRELIVE_INTEGRATION_V1.md](../../SOCRATES_ZERO_OPENROUTER_PRELIVE_INTEGRATION_V1.md).

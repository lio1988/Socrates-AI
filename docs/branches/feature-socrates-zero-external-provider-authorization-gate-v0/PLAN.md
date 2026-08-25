# Phase 8.5B external provider authorization gate plan

## Success criterion

Determine from sealed evidence, source inspection and hermetic tests whether one
fully predeclared external acquisition call is presently safe to authorize.

## Scope

Provider/adapter capability matrices, request-body dry runs, credential and
network boundary analysis, budget/privacy/isolation design, one decision, and
the exact smallest next branch.

## Non-goals

No live call, credential lookup, SDK/provider invocation, real observation,
CED application, adapter hardening implementation or production wiring.

## Ordered steps

1. [done] Verify the parent checkpoint and create the dedicated gate branch.
2. [done] Offline-verify the sealed acquisition artifact and replay evidence.
3. [done] Inventory every implemented provider and adapter path.
4. [done] Audit all mandatory candidate controls and allowed dry runs.
5. [done] Select exactly one gate decision.
6. [done] Write the canonical gate report and complete branch checkpoints.
7. [done] Run all required integrity/static/canned gates.
8. [done] Commit a clean durable decision checkpoint.

## Stop conditions

Stop on any credential read, DNS/network/provider/model/tool activity, sealed
artifact change, frozen-component change, protected-file change, or attempted
authorization with an unknown mandatory field.

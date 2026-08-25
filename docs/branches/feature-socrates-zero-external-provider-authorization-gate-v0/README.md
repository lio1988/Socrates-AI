# Branch: feature/socrates-zero-external-provider-authorization-gate-v0

## Purpose

Perform the Phase 8.5B static authorization gate for exactly one bounded,
research-only, acquisition-only external provider pilot.

## Success criterion

Inspect every implemented provider path without network or credential access,
freeze the evidence honestly, and select exactly one mandated gate decision.
Authorization is earned only if every required pilot field is already proven
and can be frozen before any external dispatch.

## Scope

- offline verification of the sealed Acquisition Contract v0 evidence;
- source-level provider and adapter inventory;
- static and canned audits of model identity, request rendering, retries,
  fallback, timeout, usage, cost, credential and endpoint controls;
- authorization-manifest design and one architecture decision;
- branch-local documentation and static regression evidence.

## Non-goals

No credential inspection, DNS, network, provider SDK invocation, model or tool
execution, real observation acquisition, CED application, shadow execution,
production integration, action-family extension, learning or RL.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

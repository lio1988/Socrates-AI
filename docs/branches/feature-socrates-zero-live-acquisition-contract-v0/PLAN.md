# External Observation Acquisition Contract v0 plan

## Current phase: CONTRACT DESIGN

## Success criterion

Freeze and prove the canned-only acquisition hypothesis under exact identities,
receipts, guard precedence, tripwires, isolation, artifact and replay thresholds
without any external execution or canonical application.

## Scope

Additive acquisition contracts, canned runtime, deterministic harness, frozen
artifact/replay and documentation only.

## Non-goals

No live/provider integration, CED application, search, Value ranking, action
extension, learning, RL, production wiring or protected-file changes.

## Ordered steps

1. [done] Verify the exact Phase 8.5 checkpoint and create the approved branch.
2. [in progress] Freeze repository-native contract and identity design.
3. [pending] Implement canned acquisition runtime, guards and immutable receipts.
4. [pending] Implement network/credential/application tripwires and isolation.
5. [pending] Freeze cases, mutation vectors, guard order and thresholds.
6. [pending] Pass focused pre-result tests.
7. [pending] Commit the pre-result freeze.
8. [pending] Run exactly one authoritative aggregate and preserve its artifact.
9. [pending] Run independent replay and create a replay lock only on pass.
10. [pending] Run full regression gates and complete documentation.
11. [pending] Commit the durable checkpoint with a clean tracked worktree.

## Stop conditions

Stop on any external invocation, credential access, canonical application,
protected-file change, frozen-hash mismatch, post-freeze semantic change,
mutation, uncounted canned invocation, false-zero usage or first-artifact
falsification.


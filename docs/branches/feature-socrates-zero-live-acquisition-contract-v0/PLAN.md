# External Observation Acquisition Contract v0 plan

## Current phase: PRE-RESULT FREEZE

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
2. [done] Freeze repository-native contract and identity design.
3. [done] Implement canned acquisition runtime, guards and immutable receipts.
4. [done] Implement network/credential/application tripwires and isolation.
5. [done] Freeze cases, mutation vectors, guard order and thresholds.
6. [done] Pass focused pre-result tests.
7. [in progress] Commit the pre-result freeze.
8. [pending] Run exactly one authoritative aggregate and preserve its artifact.
9. [pending] Run one reverse replay and persist execution evidence plus replay
   lock only on pass.
10. [pending] Run full regression gates and complete documentation.
11. [pending] Commit the durable checkpoint with a clean tracked worktree.

## Stop conditions

Stop on any external invocation, credential access, canonical application,
protected-file change, frozen-hash mismatch, post-freeze semantic change,
mutation, uncounted canned invocation, false-zero usage or first-artifact
falsification.

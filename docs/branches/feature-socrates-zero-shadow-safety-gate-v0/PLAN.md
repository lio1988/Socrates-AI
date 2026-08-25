# Phase 8.5 shadow safety gate plan

## Current phase: COMPLETE

## Success criterion

Verify the frozen Phase 8 lineage and exact repository behavior, choose exactly
one honest Phase 8.5 decision, fully specify one bounded next milestone, change
documentation only, pass every required offline gate, preserve both protected
untracked files, and commit a clean tracked checkpoint with zero external
network/live-provider/model/tool calls.

## Scope

- read-only source, contract, artifact and test analysis;
- legal-action, Value-v1, provider/root, acquisition, isolation and budget audit;
- qualitative comparison of exactly five decision candidates; and
- canonical plus branch decision documentation.

## Non-goals

No external call, credential access, shadow runner, transition/environment
change, action-family extension, SearchState/Projection/Value/Policy/search/CED
semantic change, Experience Store, learning, RL, depth two or production wiring.

## Ordered steps

1. [done] Verify exact Phase 8 v2 parent HEAD and protected files.
2. [done] Create the dedicated documentation-only gate branch.
3. [done] Verify v2 artifact/replay, v1 predecessor, 34 core blobs and historical
   scientific hashes without regeneration.
4. [done] Audit actual hard-legal action cardinality and root identity.
5. [done] Audit champion-stack compatibility and Value-v1 relevance.
6. [done] Audit live adapter/configuration, nondeterminism, isolation,
   observation authority, resource and cost controls.
7. [done] Compare all five decision candidates qualitatively.
8. [done] Select exactly one decision: `REAL SHADOW NOT YET EARNED`.
9. [done] Freeze exactly one offline prerequisite milestone and its
   zero-external-call budgets.
10. [done] Run all required read-only/offline integrity gates.
11. [done] Commit the durable Phase 8.5 decision checkpoint.

## Validation gates

- Phase 8 v1/v2 successor, artifact, replay and core locks:
  `181 passed`;
- Phase 6 observability plus Phase 7 primary/BestOfN Value integrity:
  `94 passed`;
- Phase 5 evaluation integrity: `37 passed`;
- mocked/canned provider and registry configuration: `132 passed`;
- legal-action and BestOfN audit: `41 passed`;
- total selected gates: `485 passed / 0 skipped / 0 failed`;
- final focused artifact/core recheck: `35 passed` (overlaps the selected
  Phase 8 set and is not added to the total);
- `git diff --check`; and
- docs-only tracked scope plus untouched protected untracked files.

## Selected next milestone

`feature/socrates-zero-live-acquisition-contract-v0`

This is an offline, canned-transport contract/preflight milestone. It may define
immutable acquisition identity/resource/isolation contracts and a canned
preflight artifact. It may not call external/live providers or provider SDKs,
or apply a live observation.
It must exercise and count its pre-registered in-process canned transports while
all external network/live-provider/model/tool counters remain zero.

## Stop conditions

Any external provider/network/model/tool call, credential access, runtime
semantic edit, protected-file change, frozen-hash mismatch, fabricated budget
number, combined live/action change, or claim that the current root is
multi-action invalidates this gate.

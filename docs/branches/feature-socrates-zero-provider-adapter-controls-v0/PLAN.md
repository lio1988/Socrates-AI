# OpenRouter acquisition adapter controls v0 plan

## Ordered scientific chronology

1. [done] Verify the Phase 8.5B checkpoint and create the approved branch.
2. [done] Audit repository-native contracts and production OpenRouter semantics.
3. [done] Freeze immutable adapter contracts and canonical renderer.
4. [done] Freeze route/retry/fallback/stream/tool policies.
5. [done] Freeze truthful token, pricing and cost evidence.
6. [done] Implement canned response, identity, usage and raw receipts.
7. [done] Implement sealed one-shot adapter and cancellation hardening.
8. [done] Freeze 59 cases, mutation vectors, guard order and thresholds.
9. [done] Freeze artifact schema, falsification rules, exact IDs, 72-path mutation evidence and pre-result tests.
10. [done] Report freeze commit `88da597b6ba0c84e4c4614c001973febf3f40009`, then run the first and only authoritative canned aggregate.
11. [done] Publish and commit the write-once authoritative artifact in `911340d`.
12. [done — not performed by design] The result was `FALSIFIED`, so the complete-pass prerequisite for reverse replay was absent and no replay lock was created.
13. [done] Run full regressions and re-verify historical/core/protected hashes.
14. [done in this documentation commit] Record the durable falsified checkpoint.

## Observed authoritative consequence

The candidate retained unresolved `P08`, `P09`, `P17`, `P18` and `P19`.
`P08_ROUTE_POLICY` won as the first actual guard, zero canned invocations were
observed, and the unweakened threshold remained 34. The authoritative decision
is `OPENROUTER ACQUISITION ADAPTER HARDENING FALSIFIED`.

The artifact is preserved. Replay is `NOT PERFORMED`, live authorization remains
rejected, and the next decision is `RETURN TO ARCHITECTURE DECISION`.

## Stop conditions

Stop on credential/environment-secret reads, DNS/network/SDK/provider/model/tool
activity, canonical CED application, production wiring, frozen-component change,
protected-file change, pre-freeze aggregate, invented price, accepted unknown
token bound, post-result semantic reclassification or replay-lock creation for
a falsified result.

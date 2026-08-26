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
9. [done in this documentation commit] Freeze artifact schema, falsification rules, exact IDs, 72-path mutation evidence and pre-result tests.
10. [pending] Report the exact freeze commit, then run the first and only authoritative canned aggregate.
11. [pending] Publish and commit the write-once authoritative artifact.
12. [conditional] On a complete pass only, run and commit an independent reverse replay lock. On `FALSIFIED`, mark replay `NOT PERFORMED` and create no lock.
13. [pending] Run full regressions and re-verify historical/core/protected hashes.
14. [pending] Commit the durable supported/falsified checkpoint.

## Frozen expected consequence

The candidate has unresolved `P08`, `P09`, `P17`, `P18` and `P19`. Observed
canned invocations must remain zero after the first pre-dispatch failure, while
the unweakened success threshold remains 34. The expected authoritative decision
is `FALSIFIED`, but this text is not an aggregate result.

## Stop conditions

Stop on credential/environment-secret reads, DNS/network/SDK/provider/model/tool
activity, canonical CED application, production wiring, frozen-component change,
protected-file change, pre-freeze aggregate, invented price, accepted unknown
token bound, post-result semantic reclassification or replay-lock creation for
a falsified result.

# Plan — V0.3A

## Completed checkpoint work

1. [x] Verify branch, trusted `1b23e0d...` checkpoint and clean initial state.
2. [x] Reuse `prepare()` / `execute()` / `CEDOrchestrator.run_registry_session()` without duplicating authority.
3. [x] Implement strict fixed-universe B→C source authorization support without a production manifest or bypass.
4. [x] Implement bounded, expiring, one-use preflight plus confirmation/cancel/shutdown race safety.
5. [x] Add the minimal Normal Live UI confirmation and data-driven three-seat layout while preserving V0.1 visuals.
6. [x] Exercise real live-adapter classes and canonical CED with only a deterministic internal test transport.
7. [x] Harden projection, SSE replay/terminal races, secret canaries and browser cleanup.
8. [x] Batch the 97-path verifier and prove a full test-only B→C fresh-checkout round-trip.
9. [x] Preserve default CLI cancellation semantics; opt in only the browser manager to cancellation provenance.
10. [x] Run focused/regression/compile/browser gates and create one local atomic implementation checkpoint.

## Separate future task—not authorized here

1. Operator reviews exact checkpoint B.
2. Start from a fresh cache-free checkout of B.
3. Create one direct artifact-only child C containing only `authorization/normal-live-source-set-v1.json`.
4. Bind all 97 source paths/digests, rerun offline gates, and stop for separate real-live authorization.

No production manifest, live call, push, tag, PR or deployment belongs in V0.3A.

---

# Historical V0.2 plan (completed and superseded)

## Success criterion

`Browser ↔ thin local API/SSE ↔ real canonical CED ↔ offline mock providers` works end to end while Demo mode remains backend-independent.

## Ordered work

1. [x] Verify branch/HEAD/status and canonical CED/offline-provider entry.
2. [x] Add failing public-boundary, canonical-parity and API/SSE tests.
3. [x] Implement a per-run offline manager and append-only versioned public projection.
4. [x] Add the same-origin local FastAPI app and minimal two-mode frontend adapter.
5. [x] Run focused and regression tests, secret scans and responsive browser QA.
6. [x] Update `PRESENT.md` and stop without commit, push, OpenRouter, BYOK or deployment.

## Validation gates

- Exact phase/role/move parity with canonical state.
- Rejected responses never become contributions.
- Final answer passes through governing rendering.
- Secret canaries absent from POST/status/SSE and browser DOM.
- Demo and Local CED both pass at 1440/1024/768/375.

## Stop conditions

- Any live/provider/network call path becomes reachable.
- Canonical CED must be modified or duplicated.
- A public projection cannot be proven free of private fields.

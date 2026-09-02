# Plan — V0.8A Render deployment enablement

## Success criterion

A hosted deployment behind a TLS-terminating platform serves BYOK, and a probe
that says "ready" means the build can actually accept a preflight.

## Completed

1. [x] Verify branch, HEAD, clean status and current authorization from a cache-free worktree.
2. [x] Reproduce both gaps as behaviour against the prior authorized build, not as assertions.
3. [x] Make `SOCRATES_TRUST_PROXY` real: one normalization layer outside every other, rewriting scheme and peer from the forwarded headers.
4. [x] Give `SOCRATES_TRUSTED_PROXY_HOSTS` two honest bases — checked peer addresses, or the named `platform-edge` topology basis — and refuse every mixture, wildcard, malformed value and local-mode enablement.
5. [x] Believe only the last forwarded value, so a caller cannot mint rate-limit identities.
6. [x] Make `/ready` consult the real production verifier when a live mode is enabled, and answer `not_ready` with `source_not_authorized`.
7. [x] Keep `/health` at 200 while not ready, so "restart me" and "do not route to me" stay different answers.
8. [x] Twenty-eight new tests; update the two existing readiness tests that were written before readiness knew about authorization.
9. [x] Document the actual Render contract, including why `platform-edge` is not a wildcard.
10. [x] Full regression compared against the prior authorized build rather than judged alone.

## Not done, deliberately

- No manifest rotation, no push, no deployment, no provider call.
- No change to CED, prompts, scoring, schemas, corroboration, ratification or the returned-identity policy.
- No shared limiter, no durable artifacts, no Docker.

---

# Plan — V0.9 public product and hosting preparation

## Success criterion

A misconfigured public deployment refuses to start rather than reaching a user's
credential, and the interface claims only what the topology proves.

## Completed

1. [x] Verify branch, HEAD, tree, clean status and the current authorization once.
2. [x] Add a startup deployment contract deciding the mode from explicit configuration, never from a request, refusing every unsafe combination.
3. [x] Gate BYOK and operator-funded live before routing, so a disabled mode is absent rather than merely unhappy.
4. [x] Make operator-funded live off by default and let the interface ask which modes exist.
5. [x] Require both configuration permission and a real TLS request before promising HSTS.
6. [x] `no-store` on every API response; `no-cache` on static.
7. [x] Add `/health` (liveness) and `/ready` (finite status, mode, finite reason codes, nothing private).
8. [x] Wire the documented rate limits from configuration into the running limiter.
9. [x] Correct the inaccurate "separate LLM call" copy and give the spend ceiling a hierarchy that reads as a ceiling.
10. [x] Document Render deployment, the private backup procedure and the public showcase boundary.
11. [x] Twenty-nine hosted-config tests; full regression; browser QA at four widths including the unattributable-provider notice.
12. [x] One source checkpoint, then stop for operator review.

## Not done, deliberately

- No reauthorization in this task; the manifest rotation is the next one.
- No deployment, no live run, no push, tag or PR.
- No distributed limiter, no Docker, no configuration framework.

---

# Plan — V0.8 returned-identity classification and routing observability

## Success criterion

The next provider-identity failure explains itself from the artifact alone, and
the fail-closed outcome is unchanged.

## Completed

1. [x] Read-only audit established that the incident was an ERROR envelope with no attributable identity, not a substitution.
2. [x] Separate absent identity from wrong identity with two new finite codes, keeping the two existing names so shared benchmark vocabulary is not churned.
3. [x] Keep every identity verdict fatal through one explicit tuple.
4. [x] Record the mapper verdict, the envelope kind and the comparison operands on the turn record, all added to the identity pop-list.
5. [x] Project those five fields into the run artifact.
6. [x] Carry the ledger reason into the accounting instead of one flattening constant.
7. [x] Add a closed-table public sentence, emitted as its own field and rendered in its own element beside the governing notice.
8. [x] Prove the new behaviour, prove the old names survive, prove historical record identity is undisturbed, prove the notice table never echoes an unknown code.
9. [x] Full regression; identify the one failure as pre-existing at commit G rather than forcing it green.
10. [x] One source checkpoint, then one manifest-free anchor and one artifact-only reauthorization.

## Not done, deliberately

- No rename of  / .
- No schema, retry, corroboration, binding, fallback or CED change.
- No live run, no provider call, no deployment, no push, tag or PR.

---

# Plan — V0.7 BYOK public product checkpoint

## Success criterion

A user funds one canonical council run with their own OpenRouter key, through the
existing planner, the existing runtime and the existing CED, with the credential
provably absent from every surface except the same-origin execute request that
exists to deliver it.

## Completed

1. [x] Read-only takeover: branch, HEAD, parent, tree, clean status, one source-authorization verification, three branch documents, and an implementation map of every credential and lifecycle seam.
2. [x] Make the credential an explicit transport parameter instead of duplicating the transport or mutating the environment.
3. [x] Add `RunScopedCredential`: validated on construction, redacted, unserializable, releasable, terminal.
4. [x] Add `ByokLiveCouncilManager` reusing the Normal preflight store, planner, runtime, CED and public projection, with no environment read anywhere on its path.
5. [x] Add `/api/council/byok/{preflight,execute,cancel}` with strict bodies, generic errors and no request echo.
6. [x] Add bounded single-process rate limiting and capacity caps that store no credential.
7. [x] Add transport security: loopback HTTP or same-origin HTTPS, no forwarded-header trust, cross-origin refused.
8. [x] Add security headers with no `unsafe-inline`, and a bounded request body.
9. [x] Add the third public mode, the password field, the show/hide control, truthful cost and privacy copy, and hide operator Normal Live by default.
10. [x] Update the marketing copy to what the topology actually proves.
11. [x] Add `byok_live.py` to the authorized path universe and move the two count assertions from 97 to 98.
12. [x] Prove isolation with two canaries, release on every terminal path, no server-key fallback, and no leak into any public surface or artifact.
13. [x] Run the offline end-to-end council through the real runtime, real CED and real live adapter classes with a stub wire only.
14. [x] Browser QA at four widths with zero console errors and zero horizontal overflow.
15. [x] Document hosting, security, limits and resource bounds.
16. [x] One local atomic source checkpoint commit, then stop.

## Separate future task—not authorized here

1. Operator reviews the source checkpoint.
2. One manifest-free anchor commit.
3. One artifact-only authorization commit over the 98-path universe.
4. Production verification from a fresh cache-free worktree.
5. One controlled BYOK live run.

No manifest rotation, real key, provider call, spend, deployment, push, tag or PR belongs in V0.7.

---

# Plan — V0.3C

## Completed source-fix checkpoint

1. [x] Invalidate the prior controlled preflight and stop its loopback server without execution or provider artifacts.
2. [x] Verify clean artifact-only commit C as the exact parent.
3. [x] Add a deterministic, content-bound, non-executable public approval reference.
4. [x] Extend browser preflight validity to a server-enforced maximum of 900 seconds with exact UTC display and monotonic expiry authority.
5. [x] Keep the raw preflight capability out of URLs and every public/render/copy surface; execute/cancel remain strict private-ID body operations.
6. [x] Revalidate canonical binding, approval reference, source receipt, topology, call/cost ceiling and expiry before consume and immediately before runtime construction.
7. [x] Add the minimal approval-reference/question/expiry/copy UI without redesigning the frozen visual language.
8. [x] Prove reference sensitivity, expiry/replay, API capability separation, drift blocking, secret boundaries and Demo/Local regressions offline.
9. [x] Run an isolated injected-auth browser preflight, exact clipboard readback, DOM/attribute/console/history privacy checks and cancel it with zero execute requests.
10. [x] Preserve the commit-C authorization artifact unchanged so production fails closed after checkpoint D.

## Separate future task—not authorized here

1. Operator reviews exact source checkpoint D.
2. Create one artifact-only direct child E binding D's reviewed source bytes.
3. Rerun offline authorization/readiness gates and stop for a separate Stage B decision.

No production reauthorization, real preflight, provider call, push, tag, PR or deployment belongs in V0.3C.

---

# Historical plan — V0.3A

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

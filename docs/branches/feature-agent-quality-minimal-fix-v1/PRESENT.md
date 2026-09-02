# Present state — V0.8 returned-identity classification and routing observability

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- Parent: `c90f9a8` (G, the BYOK authorization commit).
- One source checkpoint, then one manifest-free anchor and one artifact-only reauthorization, in this task.
- **The authorized path universe stays at 98.** The only new file is a test, which is outside the runtime universe by design.
- No push, tag, PR, deployment, OpenRouter call, paid provider call or external network call.

## What prompted this

The first controlled BYOK live run stopped at 16 of 135 calls on an HTTP 200 whose body carried a top-level `error` and no `model`. The artifact preserved two `False` flags and the name `returned_model_identity_mismatch`, which reads as *a different model came back*. It took a full source audit to establish that nothing had been substituted at all — the response simply carried no identity, because OpenRouter delivers upstream errors inside HTTP 200.

Three things were computed and then discarded on the way to that artifact: the mapper's `envelope_kind` and `actual_served_model_status`, the record's own `s5_envelope_kind`, and the ledger's exact fatal reason, which `NormalRuntime.accounting()` flattened to the constant `"session_fatal"`. This is the third instance of the same class of gap on this branch.

## What changed

**Classification.** `execute_bounded_text_turn_v1` now separates absence from error:

| Condition | Verdict |
| --- | --- |
| Either identity absent | `returned_identity_absent_error_envelope` *(new)* |
| Both present, both wrong | `returned_model_and_provider_mismatch` *(new)* |
| Model present and wrong | `returned_model_identity_mismatch` *(unchanged)* |
| Provider present and wrong | `returned_provider_identity_mismatch` *(unchanged)* |

The two existing names are deliberately **not** renamed: two benchmark scripts and their tests share that vocabulary, and the audit's finding was about absence, not about them. All four trip the fatal latch through `RETURNED_IDENTITY_FATAL_FAILURES_V1`, so **fail-closed behaviour is byte-for-byte the same outcome** — only the name now matches the cause.

**Observability.** Four new optional turn-record fields — `actual_served_model_status`, `router_metadata_presence`, `expected_model_identity`, `expected_provider_identity` — all added to the record's identity pop-list so historical record identities do not move. The artifact projection now carries those four plus `s5_envelope_kind`, which already existed on the record. `NormalRuntime.accounting()` carries the ledger's actual reason instead of one constant; every value reaching `trip_fatal` in this runtime is a literal from the adapter's own finite vocabulary, so nothing provider-controlled is exposed.

**Public message.** A new `public_session_stop_notice()` in `socrates/rendering.py` maps a fatal code to one sentence from a closed table; an unrecognised code returns `None` rather than being echoed. Both managers emit it as a separate `provider_stop_notice` event field, and the UI renders it in its own element beside the governing notice. It is never merged into that notice: one says what the council may claim, the other says the council never got that far. `render_normal_response` is untouched.

## What deliberately did not change

Exact model and provider binding; `allow_fallbacks=False`; pinned `provider.only`/`order`; the fatal session latch; CED; corroboration; verification retry; structured-output schemas. The refuted non-string-`const` hypothesis produced no schema change, and the `missing=11` finding on its own justifies none.

## Validation

- `test_returned_identity_classification_v1.py`: **11 passed.** Verified failing before the change.
- Eleven suites including BYOK, normal runtime, rendering, CLI, live lifecycle, source authorization, council bridge, reduced-benchmark safety, hybrid invariants and destructive path: **270 passed, 2 skipped, 1 failed.**
- The single failure is `test_socrates_zero_openrouter_acquisition_reduced_benchmark_safety_v1.py::test_unknown_dispatch_exception_is_charged_and_never_retried`, an unsettled-reservation assertion. **Reproduced identically with the source changes stashed, and again in the pristine `Socrates-AI-Verify-c90f9a8` worktree at commit G.** It pre-dates this checkpoint and belongs to the inherited failure set; it was not forced green.

## Deferred

Per-attempt semantic parse outcomes (frozen core). The exact upstream error behind the incident remains unknown and would need an allowlisted, categorised upstream reason — never a raw error body. Shared multi-instance rate limiting. Deployment.

---

# Historical present state — V0.7 BYOK public product checkpoint

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- Parent: `7170f92bd84eb7ef62b0451f738d4a7589ddbb29` (V0.6 manifest commit).
- One source checkpoint commit. **No manifest rotation, no anchor, no artifact-only commit.**
- `CURRENT_PRODUCTION_SOURCE_AUTHORIZATION = FAIL_CLOSED`, intentionally: the authorized source set changed. The V0.6 authorization `normallivesourceauthv1_a5aba384…` no longer describes this tree.
- The authorized path universe grew from **97 to 98** — one new runtime module, `backend/dialogues/byok_live.py`, added to `NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1`. A runtime file outside that tuple would run unauthorized, so it had to be added, and the two count assertions in `test_normal_source_authorization_v1.py` moved with it.
- No push, tag, PR, deployment, OpenRouter call, paid provider call or external network call.

## The one architectural decision

`openrouter_one_live_shadow_v1.py:339` documents itself as *"the single place this process reads the credential"*. Every BYOK design reduces to what to do about that line. Three options existed:

1. Mutate `os.environ` per run — globally racy, and two concurrent runs would fight over one variable. Refused.
2. Duplicate `_dispatch_once_v1` for a second credential source — a second transport, a second dispatch latch, a second place that can send a charge. Refused.
3. Make the credential an explicit parameter, with the environment read kept as the operator entry point.

Option 3 shipped. `dispatch_openrouter_one_live_inference_with_credential_v1` shares the transport, the latch, the evidence and the single `Authorization` injection site with the operator path; it simply never reads the environment. The existing `dispatch_openrouter_one_live_inference_v1` now delegates to it after reading the environment, so operator Normal Live keeps one env-reading entry point and BYOK provably cannot reach it.

## BYOK architecture

```
BYOK preflight (question only)
  -> socrates.runtime.prepare()          [existing planner, existing arithmetic]
  -> NormalLivePreflightStore            [existing 900s one-use capability]
  -> user confirmation + credential
  -> RunScopedCredential                 [new: validated, redacted, releasable]
  -> make_byok_dispatch_v1 closure       [new: one credential, one run]
  -> socrates.runtime.execute()          [existing]
  -> _build_live_runtime(dispatch=...)   [existing parameter, already threaded]
  -> CEDOrchestrator.run_registry_session[existing canonical council]
  -> SocratesLiveOpenRouterAdapter x3    [existing live adapter class]
  -> observe_public_council / SSE        [existing public projection]
```

No BYOK CED, no BYOK scheduler, no BYOK scoring, no BYOK ratifier, no browser-side orchestration. The browser supplies a question, a confirmation and a credential; every other decision stays server-side.

## Credential boundary

`RunScopedCredential` validates on construction, redacts `repr`/`str`/`format`, and refuses `copy`, `deepcopy` and `pickle`. `reveal()` is the only way out and is named to be greppable. `release()` is terminal and idempotent, called in the run's `finally` so completion, blocking, provider failure, transport failure, exception and cancellation all reach it. After release the run's dispatch closure raises rather than reaching the network.

The credential lives in one closure. There is no ephemeral store, no module-level default, no cross-run lookup and no fingerprint.

**Not claimed:** cryptographic zeroization. CPython is not asked to prove it overwrote an immutable string, and the code says so where it lives.

Local validation only, per `validate_bearer_credential_v1`: type, non-empty after an explicit strip policy, bounded at 512 bytes, no NUL, no CR/LF, no control characters. No key-prefix rule is hard-coded as permanent truth, and no separate paid probe request is made — authentication is proven by the first canonical provider call.

## Transport and headers

BYOK is permitted only on loopback HTTP or genuine same-origin HTTPS; a mismatched `Origin` is refused with 403, and a non-loopback plain-HTTP request with 400. `X-Forwarded-For` and `X-Forwarded-Proto` are not read. CSP carries no `unsafe-inline` and no `unsafe-eval` because the UI has no inline script, style or handler. HSTS is emitted only on a genuine TLS non-loopback request. Bodies are bounded at 64 KiB.

## Validation

- `test_byok_live_v1.py`: **35 passed.** Two distinct key canaries throughout.
- Full affected regression — BYOK, normal runtime, rendering, CLI, live lifecycle, source authorization, council bridge: **199 passed, 2 skipped** after the two path-count assertions moved to 98.
- Browser QA at 1440 / 1024 / 768 / 375: horizontal overflow **0** at every width, console errors **0**, console warnings **0**, mobile controls 44px.
- Full BYOK browser flow against a stub transport: preflight without a key, key entry, show/hide, confirm, `202`, key field cleared to length 0, 7/7 phases, governed answer, cancel path clearing the key, second isolated run, Demo and Local CED regressions.
- Post-run browser scan: the canary appears in no DOM text, no attribute, no URL, no fragment, no `localStorage`, no `sessionStorage`, no cookie; history length unchanged at 1.
- Server-side scan: 79 run artifacts written, **0** contain the canary, **0** contain `Authorization`; **0** secret-shaped strings in the whole server log.
- `python -m compileall`, `node --check` on both scripts, `git diff --check`: see the commit gate below.

## Deferred, explicitly

- Per-attempt semantic parse outcome between structured-output validation and governing `VerificationRecord` creation. Frozen core; separate observability-only task.
- Shared multi-instance rate limiting. Required before a second application worker.
- Deployment.
- A controlled BYOK live run.

## Next safe step

`NEXT_STEP = OPERATOR REVIEW OF THIS SOURCE CHECKPOINT, THEN ONE MANIFEST-FREE ANCHOR AND ONE ARTIFACT-ONLY SOURCE REAUTHORIZATION OVER 98 PATHS, THEN ONE CONTROLLED BYOK LIVE RUN.`

---

# Historical present state — V0.6 turn-failure diagnostics, reauthorized source set

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- **This commit is the manifest-free reauthorization anchor.** Its sha is the parent of the manifest commit that follows and is recorded in that manifest's `authorized_implementation_commit_sha`.
- Prior commits: … → `4ee891c` (V0.5 manifest, now superseded) → `b9254d3` (turn diagnostics) → this anchor.
- The V0.5 authorization `normallivesourceauthv1_c7de71f3…` is **superseded**. It authorized commit `3d58774`, which no longer describes this tree.
- No push, tag, PR, deployment, BYOK, provider call, external network call or spend.

## What prompted this

The first live run on the V0.5 checkpoint completed, ratified 3/3, `release_unresolved`. Its artifact carried the governing records the V0.5 change added, and they immediately showed something the Stage B artifacts could not:

- All four objections targeted `core_answer`, scope `justification`, all ended `inconclusive`.
- Verdicts were **not** uniform: two `uncorroborated`, two `no_records`.
- `obj_c922b624` had two peers, neither of them the flagged model, **both** structurally valid, and still returned `no_records`. Retry or redundancy on that model would not have touched it.

That is the evidence the retry question was gated on, and it says the obvious fix would have been the wrong one.

Cross-run, the failure distribution is deterministic rather than flaky:

| task_kind | first run | Stage B | total |
| --- | --- | --- | --- |
| `objection_verification` | 0/4 | 0/3 | **0/7** |
| `socratic_question` | 0/2 | 0/2 | **0/4** |
| every other task kind | 26/26 | 20/20 | **46/46** |

All 33 of that model's turns completed transport with HTTP 200 and correct model and provider binding, and it voted in ratification. It is called normally; two specific schemas are refused.

## What this checkpoint changes

`socrates.runtime._project_turn_row` now carries `provider_structured_output_error` and `ced_rejection_reason`. The adapter already computed both; only this projection dropped them.

Both are closed vocabularies by construction. `safe_public_exception_code_v1` reduces a `ValidationError` to counts by pydantic error type against a fixed allowlist; `_safe_ced_rejection_code_v1` maps to a fixed table. Neither can carry provider prose, messages, field paths or input values. Verified offline:

- a `const` violation → `structured_output:ValidationError:literal_error=1`
- a `minLength` violation → `structured_output:ValidationError:string_too_short=1`
- malformed `objection_verification` → `structured_output:ValidationError:literal_error=2,missing=9`

**No cause is asserted.** The one structural feature present in both failing schemas and absent from every passing one is a non-string `const`: `socratic_question` pins `introduces_new_proposition` to `const: false`, and `objection_verification` is an `anyOf` of two variants discriminated by `objection_concerns_the_task` `const: true` / `const: false`, with `cited_spans` `maxItems: 0` and `objection_holds` `const: null` on the non-task branch. `council_ratification` passes and carries four **string** consts. That is a hypothesis with a clean discriminator, not a finding: no raw response body was ever retained. The next live run decides it from the artifact.

Still not persisted: the per-objection parse outcome inside `run_objection_verification`, which is what would explain a `no_records` verdict when every peer was structurally valid. That needs `backend/dialogues/ced.py`, a frozen-core file, and a separate authorization.

## Changed files

- `socrates/runtime.py`: two names added to the `_project_turn_row` allow-list. The only change inside the 97-path authorized set.
- `tests_dialogues/test_normal_runtime_v1.py`: `_TURN_KEYS` extended, `test_turn_projection_keeps_the_codes_that_say_why_a_seat_failed`, and `test_a_const_violation_is_reported_as_literal_error`, which proves the retained code discriminates rather than merely existing.

No frozen-core file was touched.

## Validation

- `test_normal_runtime_v1.py`, `test_normal_rendering_v1.py`, `test_normal_cli_v1.py`, `test_normal_live_lifecycle.py`, `test_normal_source_authorization_v1.py`: `143 passed, 2 skipped`.
- `test_ced_canonical_successor_frozen_core_v2.py` still fails its two inherited blob-lock assertions, unchanged and pre-existing since V0.2.

## Next safe step

1. Production verification from a fresh cache-free worktree at the new manifest commit.
2. A live run. Its artifact answers the schema question directly: read `provider_structured_output_error` on the `socratic_question` and `objection_verification` turns.
3. Only then decide whether the schema needs changing, and how.

`NEXT_STEP = OPERATOR PREFLIGHT AND LIVE RUN, THEN READ provider_structured_output_error ON THE FAILING TURNS. BYOK REMAINS UNSCOPED.`

---

# Historical present state — V0.5 governing-audit persistence, reauthorized source set

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- **This commit is the manifest-free reauthorization anchor.** Its sha is the parent of the manifest commit that follows it, and is recorded verbatim in that manifest's `authorized_implementation_commit_sha`. This file cannot name it without naming itself, which is how the V0.3C record went stale; read it from the manifest or from `git log`.
- Prior commits on this checkpoint: `a6624f63` (commit E, previous authorization) → `ba9c628` (allow-list fix) → `c9b045e`, `65ec02a` (documentation) → `32c8635` (test corrections) → this anchor.
- No push, tag, PR, deployment, BYOK, provider call, external network call, spend or new run artifact.
- The Stage B execution worktree `C:\Users\spirc\Desktop\Socrates-AI-Controlled-Live-E-a6624f6` is untouched: still detached at `a6624f63`, clean, server stopped, and its 73-file terminal run directory byte-identical (`result.json` `5c7ec81d…8785f5`, `plan.json` `7c337147…4934173`).

## What this checkpoint changes

An offline audit of the Stage B `release_unresolved` result could not answer, from the frozen artifacts alone, which claim was unresolved, which objection targeted it, or what verdict left it there. `CEDOrchestrator._apply_governing_release` already builds `objections`, `objection_verdicts` and `deterministic_checks` into `final.audit_summary["governing_release"]`; `socrates.runtime._governing_record` dropped all three through its allow-list. This checkpoint widens that allow-list and does nothing else.

`quality_mean` and `legacy_epistemic_status` remain excluded by the same allow-list. The quality plane governs nothing and must not travel inside the governing record as though it did.

Deliberately **not** changed, and why: verification retry and redundancy in `run_objection_verification`. `REQUIRED_CORROBORATION` is 2 and the peer set excludes the raiser's model, so with three seats the fan-out is exactly two — one unusable verifier output is enough to leave an objection `INCONCLUSIVE`. That is a real fragility, but the Stage B artifacts never persisted the verdicts, so whether it actually fired is not recoverable. The persisted verdicts this checkpoint adds are the evidence that would settle it. Building redundancy first would be building on an unproven cause.

## Changed files

- `socrates/runtime.py`: three names added to the `_governing_record` allow-list, with the reason recorded inline. The only change inside the 97-path authorized set.
- `tests_dialogues/test_normal_runtime_v1.py`: `test_governing_audit_projection_keeps_objection_and_check_records`, an end-to-end assertion on the written `result.json` inside the existing full-council artifact test, plus `SimpleNamespace` and `NormalRenderResult` imports. Not in the authorized set.

Test scope, stated because the first version of it overreached: the new test covers objection and deterministic-check records only. An id in `unresolved_record_ids` may equally name an evidence, verification or contradiction record — `assess_claim` appends all four kinds — and none of those are projected yet. The test asserts resolvability for the objection id it fixtures, not for the whole list.

No file inside `FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2` was touched; the lock covers `backend/dialogues/**` only.

## Validation

- New unit test alone: `1 passed`. Verified failing before the fix by stashing `socrates/runtime.py` — `KeyError: 'objections'` — then restored.
- `test_normal_runtime_v1.py` after the test corrections: `25 passed, 1 skipped`, including the end-to-end `result.json` assertion.
- `test_normal_runtime_v1.py`, `test_normal_rendering_v1.py`, `test_normal_cli_v1.py`, `test_normal_live_lifecycle.py`, `test_normal_source_authorization_v1.py`: `141 passed, 2 skipped`.
- `test_ced_canonical_successor_frozen_core_v2.py`: `2 failed` — `::test_every_frozen_repository_blob_is_still_byte_exact` (`backend/dialogues/agent.py` blob drift) and `::test_sealed_predecessor_bytes_and_identity_remain_exact`. Both were reproduced at clean parent `a6624f63` with this checkpoint stashed, so both pre-date it. They are part of the inherited lock-failure set this branch has carried since V0.2.
- Interpreter: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe` with `PYTHONPATH` at this checkout.

## Bytecode cache state

This checkout now holds **83 ignored `.pyc` files in 6 `__pycache__` directories** (`backend/`, `backend/dialogues/`, `backend/dialogues/socrates_zero/`, `scripts/`, `socrates/`, `tests_dialogues/`). The handoff recorded 58 in 5; the increase was produced by running the test suites during this checkpoint, and `scripts/__pycache__` is new. They are ignored, so `git status` stays clean, but `_reject_authorized_bytecode_caches` fails closed against them, so production verification never runs from this checkout. Nothing was cleaned: the handoff forbids it without separate authorization, and the fresh worktree makes it unnecessary.

## Reauthorization, and why the earlier plan was wrong

The V0.4 record proposed binding a manifest to the then-current HEAD. That is guaranteed to be rejected, and reading `build_normal_live_source_authorization_v1` alone does not reveal it. `verify_normal_live_source_authorization_v1` enforces a commit *shape*:

- `manifest_self_authorizing` — the authorized implementation commit must not contain `authorization/normal-live-source-set-v1.json` in its tree.
- `authorization_commit_not_artifact_only` — HEAD must be a single-parent child whose only parent is the authorized commit.
- the same failure again — the diff between them must be exactly the manifest path and nothing else.

Every commit descending from a previous authorization carries the manifest, so the only valid sequence is **manifest-free anchor, then manifest-only child**, as `a469002 → a6624f6` did and as this checkpoint repeats.

Two further corrections to the V0.4 record: `_source_set_digest` hashes `authorized_implementation_commit_sha` and `authorized_implementation_tree_sha` along with the file list, and `authorization_id` hashes the whole payload, so rebinding to a different commit changes the digest and the id as well as those two fields. And `verify_production_...` additionally requires an empty `git status --porcelain=v2 --untracked-files=all`.

The path list is unchanged — no source file was added or removed — so the successor manifest covers the same 97 paths. Diffed entry by entry against the manifest at commit E, `socrates/runtime.py` is the only path whose hash moved. The other 96 are byte-identical.

Its hash exists in two registers, and an earlier draft of this file mixed them. `.gitattributes` pins `socrates/runtime.py text eol=crlf`, so the git blob is LF and the checkout is CRLF:

- blob sha256, which is what the manifest carries via `_commit_blob`: `d6f7181b…4615dc` → `7d96c6bd…83ad310`.
- checkout sha256, which is what `_materialize_checkout_bytes` reconstructs and compares against the working tree: `bf2c1d97…eefc9f`.

Both are correct; only the first belongs in the manifest. Any future review that hashes the working-tree file directly and compares it to a manifest entry will see a false mismatch on every `eol=crlf` path.

## Next safe step

1. Production verification from a fresh cache-free worktree at the manifest commit. Expected: the verifier returns the new `authorization_id` rather than failing.
2. A new preflight with a new approval reference. The consumed Stage B reference must not be transferred, reconstructed or replaced.
3. The live run itself is the operator's act and is not performed by any agent preparing this branch.

`NEXT_STEP = OPERATOR PREFLIGHT AND LIVE RUN FROM A FRESH CACHE-FREE WORKTREE. BYOK IS THE TASK AFTER THAT AND IS NOT YET SCOPED.`

---

# Historical present state — V0.3C operator approval-reference checkpoint

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- Exact parent C: `d332acc886411e89fb1b6eea31288edea8984f55` (`Authorize Normal Live source set v1`).
- V0.3C is one source/test/docs checkpoint. `authorization/normal-live-source-set-v1.json` is unchanged, so its authorization of C fails closed after these source changes.
- No real production preflight, execute, provider/external-network call, run artifact, spend, BYOK, deployment, push, tag or PR occurred.

## Approval and capability contract

Each stored browser preflight receives an immutable `normalapprovalv1_<64 lowercase hex>` reference over canonical JSON containing the private random capability, question and plan identity, full verified source receipt, exact three-seat private topology, base/retry/maximum calls, picodollar and exact USD ceilings, creation identity and both monotonic/UTC expiry identity. A different preflight or any bound drift changes the reference.

The raw `nlpf_...` value remains the one-use execute/cancel capability. Fixed endpoints carry it only in strict, repr-redacted JSON request bodies; the public reference is rejected as an extra field and cannot execute or cancel. JavaScript separates it immediately into private in-memory state and exposes only a frozen public projection. It is absent from URLs, history, rendered DOM/attributes, clipboard, console, SSE, public status/results/artifacts and safe errors.

The store rejects noncanonical preflight/binding pairs and any validity above 900 seconds. Expiry is non-sliding and server-monotonic at the exact boundary; cancel, consume and expiry are terminal. Binding/reference/source identity is checked before atomic consumption and again before provider construction.

## Operator UI

The existing confirmation panel now shows `NORMAL LIVE COUNCIL`, server-derived model-seat/call/cost ceilings, the full approval reference, full question SHA-256 and exact UTC expiry. Copy emits exactly six LF-separated public lines with no trailing newline. Confirm/copy require a visible panel whose question, reference, ceilings and expiry still match the retained public projection.

## Validation

- Focused approval/lifecycle/API/UI gate: `35 passed`.
- Trusted V0.3A/V0.3B/V0.3C 11-file regression gate: `216 passed, 2 skipped`.
- The legacy `manifest_absent` safety assertion now runs against an isolated temporary repository because commit C intentionally contains the production manifest; this removes the C-era intended deselection without changing verifier semantics.
- Required compileall: passed with external pycache; repository `.pyc` count stayed `58 → 58`.
- JavaScript syntax for `web/app.js` and `web/ced-bridge.js`: passed.
- `git diff --check`: passed.
- Production verifier after source modification: fail closed before provider construction; no dispatch path was reached.

Isolated loopback browser QA used an injected test-only source receipt and a transport tripwire. The full approval reference/question hash/expiry rendered, raw capability patterns were absent from all element text and attributes, clipboard bytes exactly matched the six-line package, the console stayed empty, and the URL/history remained unchanged. Network activity was one preflight plus one cancel; execute count was zero. The server was stopped and its temporary run root remained absent.

`NEXT_STEP = OPERATOR REVIEW OF CHECKPOINT_D, THEN ARTIFACT-ONLY SOURCE AUTHORIZATION COMMIT_E`

---

# Historical present state — V0.3A Normal Live implementation checkpoint

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- Trusted parent: `1b23e0d07880dd9cf61192b15fc9c823ff733027` (`Checkpoint Socrates UI V0.2 real CED bridge`).
- V0.3A is one additive implementation checkpoint. The production `authorization/normal-live-source-set-v1.json` is intentionally absent, so production Normal Live returns the fixed public 503 before provider construction.
- No live/provider/external-network call, push, tag, PR, deployment, BYOK, frozen-artifact update or run artifact occurred.

## Canonical lifecycle

The browser supplies only a question and exact confirmation. The server verifies source authority, calls canonical `socrates.runtime.prepare()`, stores a bounded/expiring/one-use preflight, revalidates its complete binding, and calls `await socrates.runtime.execute()`. The sole council driver remains `CEDOrchestrator.run_registry_session()`.

Normal Live constructs exactly three real `SocratesLiveOpenRouterAdapter` seats. Tests inject an internal deterministic transport; no browser field controls transport, topology, models, cost, calls, session identity, artifacts or source authority. CLI cancellation remains unchanged; terminal cancellation provenance is a browser-manager opt-in.

## Source authorization

- Contract: `normal-live-source-set/v1` for `normal-socrates-browser-runtime/v1`.
- Fixed universe: 97 paths = 89 Python + 4 web + 3 runtime JSON inputs + `.gitattributes`.
- Required shape: reviewed B followed by one direct artifact-only child C containing only the fixed manifest path.
- Exact commit/tree, paths, modes, blobs/digests, source-set digest, authorization ID and affirmative operator statement are bound. Dirty, redirected, shadowed, bytecode-backed or externally filtered execution fails closed.
- All 97 checkout policies are explicit. A full test-only 97-path B→C round-trip in a fresh checkout passes.
- Batched bounded verification uses 20 Git subprocesses for all 97 paths, with 16 MiB/file and 64 MiB/source-set limits.
- Future C must use a fresh cache-free checkout and `python -B`; Git and Python remain explicit external bootstrap dependencies.

## API, UI and public record

- Preflight accepts exactly `{ "question": "..." }`; execute accepts exactly `{ "confirmed": true }`; cancel accepts exactly `{}`.
- Simultaneous confirm/confirm and confirm/cancel transitions have one winner. Shutdown cannot hang or duplicate a terminal event.
- Source/plan/question/topology/call/cost/session bindings are checked before consumption and again immediately before runtime/provider construction.
- `socrates.public-council.v1` SSE replay is gap-free and terminal-safe, including mid-replay and future-cursor races.
- The UI shows server-derived three-seat topology, exact maximum calls/cost, explicit confirmation/cancel and canonical phases/moves/commitments/ratification/final. Demo and Local CED retain four seats.

## Validation

- Exact historical 11-file gate equivalent: `209 passed, 1 skipped` (trusted base: `199 passed, 1 skipped`; ten additive V0.3A collections).
- Source authorization: `48 passed, 1 skipped`.
- Full Normal Live lifecycle: `12 passed`.
- Bridge/API/UI focused set: `36 passed`.
- Full 97-path fresh-checkout B→C: passed; verifier Git-call count `20`.
- Required compileall: passed with external temporary pycache; repository ignored `.pyc` count stayed `58 → 58`.
- JavaScript syntax and `git diff --check`: passed.

Loopback-only browser QA passed production fail-closed behavior, test-authorized three-seat execution, all 7 phases, accepted moves, commitments, ratification/governed final, cancel/reset, Demo/Local restoration, zero console messages and no overflow at 1440/1024/768/375. Secret canaries were absent from HTTP, headers, SSE, DOM, public result and canonical artifact.

Verified launcher:

```powershell
& 'C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish\.venv\Scripts\python.exe' -B -m uvicorn backend.local_ced_app:app --host 127.0.0.1 --port 8080
```

`NEXT_STEP = OPERATOR REVIEW OF TRUST_ANCHOR_B, THEN ARTIFACT-ONLY NORMAL-LIVE-SOURCE-SET/V1 AUTHORIZATION`

---

# Historical V0.2 state (superseded by the V0.3A record above)

## Repository

- Branch: `feature/agent-quality-minimal-fix-v1`
- HEAD remains: `4ead8be2bf6709324d122595e3d3a4cf9e27344c`
- Initial status: `?? web/`; initial tracked diff empty.
- Final tracked diff remains empty. All V0.2 files are untracked and scoped to the bridge, tests, approved `web/`, and ignored branch handoff docs.
- No commit, push, checkout, reset, stash, clean, live provider call, external network call, BYOK or deployment.

## Canonical path

`build_council(env={}, council_size=4)` creates one isolated real `CEDOrchestrator` with four `ScriptedMockProvider` seats. The bridge invokes exactly the canonical `await ced.run_registry_session(question, session_id=run_id)` driver. It observes instance-local canonical seams and never schedules a phase, role, move, commitment, score, assembly or ratification itself.

The public final is rendered only with `socrates.rendering.render_normal_response()`. A blocked/unavailable/inconsistent candidate is never serialized.

## Delivered bridge

- `backend/dialogues/council_live.py`: per-run offline safety gate, canonical observer, strict public projectors, append-only replayable event store and manager.
- `backend/api/routes_council.py`: validated POST/status/SSE endpoints with SSE IDs and `Last-Event-ID` replay.
- `backend/local_ced_app.py`: dedicated same-origin FastAPI composition root; no dotenv, CORS, legacy/private routes or debug docs.
- `web/ced-bridge.js`: additive LOCAL CED adapter. Existing `web/app.js` remains the independent timer-driven DEMO MODE.
- Minimal markup/style additions provide the two-mode selector, safe connection state, canonical commitments/final rendering and view-only Reset wording.

## Public event contract

Schema: `socrates.public-council.v1`.

Events: `run.started`, `phase.started`, `move.accepted`, `operation.rejected`, `commitments.snapshot`, `phase.completed`, `ratification.completed`, `run.completed`, `run.failed`.

Events are monotonic, detached copies, replayable by cursor and delivered independently to multiple subscribers. Only canonical accepted moves become contribution cards. Rejections use a generic operational payload.

## Validation

- Focused bridge/API/security gate: `25 passed`.
- Existing canonical registry/scoring/assembly/rendering subset: `106 passed`.
- JavaScript syntax: `web/app.js` and `web/ced-bridge.js` pass `node --check`.
- Full suite with a writable unique basetemp: `4469 passed, 10 skipped, 75 failed, 0 errors`.
- The 75 failures are confined to untouched frozen successor/Q2d/OpenRouter provenance/wire-spec/Value artifact locks or a missing retained Q7 bundle. No bridge/API/UI test failed, and no tracked file changed. There is no retained pre-task full-suite JUnit in this checkout, so the handoff does not claim that all 75 IDs are an historically verified baseline.

## Browser QA

- DEMO MODE works with the backend absent; LOCAL CED reports a sanitized unavailable state and offers retry.
- Two separate LOCAL CED runs completed through the real canonical CED: 7/7 phases, 15 accepted contribution cards, canonical `RATIFIED`, governing `release_unresolved`, and an honestly empty stock-mock commitment ledger.
- View Reset cleared the UI without claiming server cancellation; a second run used a distinct session and question.
- No horizontal overflow at 1440, 1024, 768 or 375 pixels. Mobile mode controls are 44px high.
- Browser console: 0 errors, 0 warnings in both same-origin Local CED and backend-absent Demo checks.

## Verified startup

From the authoritative checkout:

```powershell
& 'C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish\.venv\Scripts\python.exe' -B -m uvicorn backend.local_ced_app:app --host 127.0.0.1 --port 8080
```

Then open `http://127.0.0.1:8080/`. The compatible shared venv was used read-only because this checkout currently has no `.venv` of its own.

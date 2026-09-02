# Present state — V0.4 governing-audit persistence, awaiting reauthorization

## Repository and authority boundary

- Branch: `feature/agent-quality-minimal-fix-v1`.
- HEAD: `ba9c628033b9e49d672c1a4b1e1b53bc5f51344c` (`Persist the governing records the audit id lists name`).
- Tree: `92f0e72a98e0c658dc94e0a6d52f0f6085d6a2b0`.
- Parent E: `a6624f630778413d5d418014206a6f0da6735e8c`. Working tree clean.
- No push, tag, PR, deployment, BYOK, provider call, external network call, spend or new run artifact.
- The Stage B execution worktree `C:\Users\spirc\Desktop\Socrates-AI-Controlled-Live-E-a6624f6` is untouched: still detached at `a6624f63`, clean, server stopped, and its 73-file terminal run directory byte-identical (`result.json` `5c7ec81d…8785f5`, `plan.json` `7c337147…4934173`).

## What this checkpoint changes

An offline audit of the Stage B `release_unresolved` result could not answer, from the frozen artifacts alone, which claim was unresolved, which objection targeted it, or what verdict left it there. `CEDOrchestrator._governing_release_audit` already builds `objections`, `objection_verdicts` and `deterministic_checks`; `socrates.runtime._governing_record` dropped all three through its allow-list. This checkpoint widens that allow-list and does nothing else.

`quality_mean` and `legacy_epistemic_status` remain excluded by the same allow-list. The quality plane governs nothing and must not travel inside the governing record as though it did.

Deliberately **not** changed, and why: verification retry and redundancy in `run_objection_verification`. `REQUIRED_CORROBORATION` is 2 and the peer set excludes the raiser's model, so with three seats the fan-out is exactly two — one unusable verifier output is enough to leave an objection `INCONCLUSIVE`. That is a real fragility, but the Stage B artifacts never persisted the verdicts, so whether it actually fired is not recoverable. The persisted verdicts this checkpoint adds are the evidence that would settle it. Building redundancy first would be building on an unproven cause.

## Changed files

- `socrates/runtime.py`: three names added to the `_governing_record` allow-list, with the reason recorded inline.
- `tests_dialogues/test_normal_runtime_v1.py`: `test_governing_audit_keeps_the_records_its_id_lists_name`, plus `SimpleNamespace` and `NormalRenderResult` imports.

No file inside `FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2` was touched; the lock covers `backend/dialogues/**` only.

## Validation

- New test alone: `1 passed`. Verified failing before the fix by stashing `socrates/runtime.py` — `KeyError: 'objections'` — then restored.
- `test_normal_runtime_v1.py`, `test_normal_rendering_v1.py`, `test_normal_cli_v1.py`, `test_normal_live_lifecycle.py`, `test_ced_canonical_successor_frozen_core_v2.py`: `2 failed, 96 passed, 1 skipped`.
- Both failures are `test_ced_canonical_successor_frozen_core_v2.py::test_every_frozen_repository_blob_is_still_byte_exact` (`backend/dialogues/agent.py` blob drift) and `::test_sealed_predecessor_bytes_and_identity_remain_exact`. Both were reproduced at clean parent `a6624f63` with this checkpoint stashed, so both pre-date it. They are part of the inherited lock-failure set this branch has carried since V0.2.
- Interpreter: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe` with `PYTHONPATH` at this checkout.

## Blocker before any live run

`socrates/runtime.py` is one of the 97 paths in `authorization/normal-live-source-set-v1.json`. Its sha256 moved from `d6f7181b…4615dc` to `bf2c1d97…eefc9f`, so that manifest no longer authorizes this tree and `verify_production_normal_live_source_authorization_v1` fails closed before provider construction. This is the gate behaving correctly, not a defect.

Reauthorization requires an operator act that cannot be delegated: `build_normal_live_source_authorization_v1` takes an `operator_authorization_statement`, and its provenance basis is `explicit-operator-review`. The path list is unchanged — no source file was added or removed — so the successor manifest is built over the same 97 paths.

Bind it to the branch HEAD under review. The only change after `ba9c628` is this documentation file, which is outside the authorized set, so the 97 source blobs are byte-identical at `ba9c628` (tree `92f0e72a98e0c658dc94e0a6d52f0f6085d6a2b0`) and at the documentation commit that follows it. The manifest content is therefore the same either way; only `authorized_implementation_commit_sha` and `authorized_implementation_tree_sha` differ, and they should name whichever commit is HEAD when the operator signs.

`tests_dialogues/test_normal_runtime_v1.py` is not in the authorized set, so the test change does not affect the manifest.

## Next safe step

1. Operator reviews this checkpoint and issues the successor `authorization/normal-live-source-set-v1.json` over the same 97 paths, bound to `ba9c628` / `92f0e72a`, with their own authorization statement.
2. Commit that manifest alone, as commit E did.
3. Run from a fresh cache-free worktree. This checkout still holds the 58 pre-existing ignored `.pyc` files in 5 `__pycache__` directories, and `_reject_authorized_bytecode_caches` fails closed against them.
4. A new preflight with a new approval reference. The consumed Stage B reference must not be transferred.

`NEXT_STEP = OPERATOR SOURCE REAUTHORIZATION OF ba9c628, THEN FRESH-WORKTREE LIVE RUN. BYOK IS THE TASK AFTER THAT AND IS NOT YET SCOPED.`

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

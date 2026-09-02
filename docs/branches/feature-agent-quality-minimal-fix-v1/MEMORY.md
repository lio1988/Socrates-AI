# Stable branch memory — V0.9 additions

- The deployment mode is decided at startup by `backend/hosted_config.py`, never per request. `SOCRATES_PUBLIC_ORIGIN` absent means local development, set means hosted preview, set-but-blank is refused. Do not reintroduce per-request mode guessing.
- Hosted mode refuses plain HTTP **even from loopback**. Loopback is not an escape hatch once a public origin is declared.
- A disabled mode is refused in middleware, before routing, so its endpoints 404 rather than 422. Gating inside a route lets body validation answer first and leaks that the route exists and what shape it wants.
- HSTS needs both the configuration's permission and an actual TLS request. Either alone is not enough.
- `/ready` degrades on multiple workers rather than refusing: the limiter is in-process, so the honest answer is "serving, but cannot honour the documented limits".
- The authorized path universe is **99** as of V0.9. Any new runtime module joins `NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1` or it runs unauthorized, and the tuple must stay sorted.
- Uvicorn access logs record the request line and status, never a body, which is why a BYOK credential cannot reach them. Verify that against an **info-level** log; a `warning`-level log is empty and proves nothing.
- Copy discipline: separately dispatched model turns, not "a separate LLM call". No guaranteed truth, no AGI, no "always different models", and no provider-independence claim the topology does not prove.

---

# Stable branch memory — V0.8 additions

- OpenRouter delivers upstream errors inside HTTP 200. Such a body has a top-level `error` and no top-level `model`, so it carries no attributable identity. `actual_served_model` is assigned at exactly one site, only under a SUCCESS envelope, so `None` there means ERROR envelope and nothing else.
- Absent identity and wrong identity are now different verdicts and must stay different. `returned_identity_absent_error_envelope` and `returned_model_and_provider_mismatch` are new; `returned_model_identity_mismatch` and `returned_provider_identity_mismatch` keep their names because two benchmark scripts and their tests share that vocabulary.
- All four are fatal, listed in `RETURNED_IDENTITY_FATAL_FAILURES_V1`. Removing one weakens fail-closed behaviour and needs its own authorization.
- Any new optional field on `OpenRouterTurnRecordV1` must join the pop-list inside `identify()`, or every historical record identity moves.
- `NormalRuntime.accounting()` now carries the ledger's actual fatal reason. That is safe only because every `trip_fatal` argument in this runtime is a code-owned literal; if that ever stops being true, the flattening has to come back.
- Public stop sentences live in a closed table in `socrates/rendering.py`. An unknown code returns `None`. They are emitted as `provider_stop_notice`, never merged into the governing notice.
- The three observability gaps closed on this branch were all the same shape: a value computed and then dropped at a projection boundary. Look there first.
- `test_socrates_zero_openrouter_acquisition_reduced_benchmark_safety_v1.py::test_unknown_dispatch_exception_is_charged_and_never_retried` fails at commit G in a pristine worktree. Inherited, not caused by V0.8.

---

# Stable branch memory — V0.7 additions

- `openrouter_one_live_shadow_v1.py` holds the only credential read site and the only `Authorization` injection site. BYOK adds an explicit-credential dispatch entry beside the environment-reading one; both share `_dispatch_once_v1`. Never duplicate the transport and never mutate `os.environ` to switch credentials.
- `RunScopedCredential` is the only carrier of a user key. It validates on construction, redacts every rendering, refuses copy/deepcopy/pickle, and `release()` is terminal and idempotent. The credential lives in one dispatch closure per run — there is no store, no default and no fingerprint.
- No zeroization is claimed anywhere. The truthful sentence is "held only in memory for the active run and released when the run reaches a terminal state".
- BYOK never reads `OPENROUTER_API_KEY`. Operator Normal Live still does, through the unchanged entry point, and `NormalLiveCouncilManager.start_run` still takes no credential argument. That signature difference is the regression guard.
- The authorized path universe is **98** paths as of V0.7. Any new runtime module must be added to `NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1` or it runs unauthorized.
- The BYOK preflight accepts a question and nothing else. A credential field in it is a 422 with a fixed message.
- The user's key is *supposed* to be in the same-origin execute body. A leak test that flags it there is testing the wrong thing.
- Rate limits are per-process and in-memory. The public preview must run one worker until a shared limiter exists.
- CSP carries no `unsafe-inline` because `web/` has no inline script, style or handler. Keep it that way; `innerHTML` and `setAttribute("style", …)` are both absent by design.
- V0.7 authorizes no manifest rotation, live call, spend, BYOK run, deployment, push, tag or PR.

---

# Stable branch memory — V0.3C additions

- Authorized parent C is `d332acc886411e89fb1b6eea31288edea8984f55`; its production source-authorization artifact remains byte-for-byte unchanged in checkpoint D.
- A raw `nlpf_<144-bit random>` preflight ID is an execution capability. It is permitted only in the initial same-origin response, private in-memory JavaScript state, and strict execute/cancel request bodies. It must never enter URLs, DOM, attributes, logs, clipboard, SSE, public results, artifacts, errors or reports.
- Public references use `socrates-normal-live-approval-reference/v1` and the form `normalapprovalv1_<sha256>`. They bind the exact raw capability, question, plan, source receipt, private topology, call/cost ceilings, creation identity and authoritative expiry, but are never accepted as execute/cancel credentials.
- Browser preflights have a non-sliding one-use maximum validity of 900 seconds. Monotonic server time is authoritative; the exact UTC expiry is informational and operator-visible.
- Store creation accepts only a canonical preflight/binding pair. Binding and approval-reference identity are checked before atomic consume and again immediately before runtime/provider construction.
- The UI copies exactly six public lines: authorization heading, approval reference, question SHA-256, maximum calls, exact USD ceiling and UTC expiry. No fallback copies additional state.
- Any implementation change after artifact-only commit C intentionally makes production Normal Live fail closed. Reauthorization must be a later, separate artifact-only commit E.
- V0.3C authorizes no provider dispatch, live call, spend, BYOK, deployment, push, tag or PR.

---

# Historical stable branch memory — V0.3A additions

- Trusted V0.2 parent: `1b23e0d07880dd9cf61192b15fc9c823ff733027`.
- `CEDOrchestrator.run_registry_session()` remains the sole protocol authority; Normal browser execution uses existing `socrates.runtime.execute()` and exactly three `SocratesLiveOpenRouterAdapter` seats.
- Production Normal Live fails closed while `authorization/normal-live-source-set-v1.json` is absent. Never add it to an implementation commit.
- Future authorization is exactly direct B→C; C changes only the fixed manifest path.
- Fixed source universe: 97 paths (89 Python, 4 web, 3 runtime JSON, `.gitattributes`). The manifest cannot shrink it.
- Every authority path has deterministic EOL/binary semantics. Git config/attributes/excludes, repository Git shims, ignored executable shadows and authorized bytecode caches fail closed.
- Verification is batched/bounded and uses 20 Git subprocesses for all 97 paths.
- Future C and live launch require a fresh cache-free checkout and `python -B`. Existing ignored caches in this development checkout were neither removed nor altered.
- Default Normal CLI cancellation is unchanged; only the browser manager opts into terminal cancellation result provenance.
- Browser input never controls providers, models, limits, cost, transport, identity, paths or source authority.
- Public events exclude credentials, raw responses, provider/model identity, Git/manifest/claim/ledger paths, scores, stack traces and hidden reasoning.
- No production authorization, live/provider/network call, BYOK, deployment, push, tag or PR is authorized by V0.3A.

---

# Historical V0.2 stable memory (retained)

- Authoritative checkout: `C:\Users\spirc\Desktop\Socrates-AI-Agent-Fix-Live-v1`.
- Baseline HEAD: `4ead8be2bf6709324d122595e3d3a4cf9e27344c`.
- `SOCRATES_UI_VISUAL_V01 = FROZEN`; `web/` must not be redesigned.
- `CEDOrchestrator.run_registry_session()` is the sole session/protocol authority.
- The local bridge must construct providers with an explicit empty environment so it cannot select live adapters.
- Provider/model identity, task logs, raw responses, scores, audit internals, filesystem paths, keys, headers and hidden reasoning are private.
- Council ratification and governing release remain separate. Public answer rendering must use `socrates.rendering.render_normal_response()`.
- The stock deterministic provider may produce an empty canonical commitment ledger; the UI must show that honestly and never reuse Demo commitments.
- Browser Reset is view-only in Local CED V0.2; it closes listeners but does not claim to cancel the server-side run.

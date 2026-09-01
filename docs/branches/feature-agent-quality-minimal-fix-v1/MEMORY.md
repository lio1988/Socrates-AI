# Stable branch memory — V0.3A additions

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

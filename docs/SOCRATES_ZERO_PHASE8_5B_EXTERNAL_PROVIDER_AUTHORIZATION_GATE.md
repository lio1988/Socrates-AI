# SocratesZero Phase 8.5B — External Provider Authorization Gate

## 1. Executive decision

**Decision: `PROVIDER-ADAPTER HARDENING REQUIRED`.**

No external call is authorized. OpenRouter is the strongest repository candidate
because its canonical adapter pins a requested model and rejects a returned-model
substitution. It nevertheless fails mandatory adapter-level prerequisites that
can and must be implemented and proved offline: it is not an Acquisition Contract
v0 transport, has no canonical final-byte acquisition request renderer, includes
process metadata in its council prompt, omits the output-token bound, does not pin
the upstream provider route, and does not retain immutable raw, complete usage,
or cost evidence.

Section 60 of the phase mandate therefore controls the decision. Section 61 is
not yet reachable: credential, endpoint, proxy, redirect, dispatch-ledger, and
termination weaknesses are real, but external-boundary hardening presupposes an
adequate adapter. The next atomic milestone is adapter hardening only.

This gate was static and hermetic. Activity counts were:

| Activity | Count |
|---|---:|
| Live calls | 0 |
| Network attempts, including DNS | 0 |
| Credential accesses | 0 |
| Provider dispatches | 0 |
| Model executions | 0 |
| Tool calls | 0 |

## 2. Verified acquisition-contract evidence

The committed evidence was parsed and verified offline without regeneration.

| Evidence | Identifier | SHA-256 / result |
|---|---|---|
| Acquisition artifact | `acqartifactv0_fb7fc0b8f19607cf74cb549992a62ea94638228e8c5c9fedab65f445272c2d11` | `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255` |
| Replay execution | `acqreplayexecutionv0_08125a577c16aa3324f395c46461651e50ce5f1df38627edf3401dbaf1b96f8f` | `7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b` |
| Replay lock | `acqreplaylockv0_af196a855a1cefd1220a0a61b159ac75d1b8928b112704c48d7e30b686080e0a` | `335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c` |
| Acquisition hypothesis | — | `SUPPORTED` |
| Semantic equality | — | `true` |
| Artifact-ID equality | — | `true` |
| Byte identity | — | `true` |
| Historical artifact mismatches | — | `0` |
| Core blob-lock mismatches | — | `0` |

The exact sealed result is:

| Acquisition measure | Sealed value |
|---|---:|
| Positive canned cases | `6 / 6` |
| Complete acquired receipts | `8 / 8` |
| Orthogonal probes | `43 / 43` |
| Precedence probes | `7 / 7` |
| Invalid probe constructions | `0` |
| Prompt-byte mismatches | `0` |
| Identity collisions | `0` |
| External-network attempts | `0` |
| Credential-access attempts | `0` |
| Live provider calls | `0` |
| Model executions | `0` |
| Tool calls | `0` |
| Source / sibling / production mutations | `0 / 0 / 0` |
| Canonical CED application invocations | `0` |

The runtime remains deliberately canned-only. `acquire_canned_observation`
(alias `run_canned_acquisition`) accepts the exact
`CannedAcquisitionTransport` type and rejects a different transport before
dispatch. None of the live provider adapters currently
implements the frozen acquisition boundary. The supported action family remains
`ced-opening-socratic-question/v0`; this decision does not extend it.

Frozen lineage was also verified:

| Frozen component | SHA-256 / lock ID |
|---|---|
| Phase 5 | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Phase 7 primary | `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca` |
| Phase 7 BestOfN | `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637` |
| Phase 8 falsified v1 | `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea` |
| Phase 8 v2 | `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc` |
| Phase 8 v2 replay lock | `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224` |
| Core blob lock | `cedcorebloblockv2_2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957` |

Hermetic verification gates:

| Gate | Result |
|---|---|
| Acquisition contracts, runtime, cases, isolation, artifact/replay, boundaries | `214 passed` |
| Phase 8 v2 artifact/replay/core, Phase 8 v1 predecessor, Phase 7 primary/BestOfN, Phase 5 | `106 passed` |
| Canonical provider configuration, canned response, request dry-run, retry/fallback behavior | `96 passed, 1 deselected` |
| Existing credential-broker canned suite | No implementation/test exists; blocking evidence |
| Existing independent external-network-boundary canned suite | No implementation/test exists; blocking evidence |

The single deselected provider test deliberately deletes and probes the real
credential environment name. It was excluded to preserve this gate's stricter
zero-credential-access rule. All executed provider tests used explicit fake
mappings, canned transports, injected openers, or a fake `aiohttp` session.

## 3. Candidate provider inventory

### Canonical council adapters

| Provider ID / family | Adapter and module | Transport | Repository model mechanism | Gate classification |
|---|---|---|---|---|
| `openrouter` | `OpenRouterProviderAdapter`, `backend/dialogues/openrouter_provider.py` | `aiohttp` raw chat-completions POST | Exact constructor model; default `openai/gpt-4.1-mini` | Candidate; strongest base; rejected now |
| `anthropic` | `LiveAnthropicAdapter`, `backend/dialogues/live_providers.py` | Anthropic async SDK | Exact constructor model; default `claude-opus-4-8` | Candidate; rejected |
| `nvidia` | `LiveNvidiaNIMAdapter`, `backend/dialogues/nvidia_nim_provider.py` | `urllib` raw OpenAI-compatible POST | Exact constructor model; default `nvidia/llama-3.1-nemotron-70b-instruct` | Candidate; rejected |
| local OpenAI-compatible | `LocalLLMAdapter`, `backend/dialogues/openclaw_local/local_provider.py` | Inherited `urllib` transport | Runtime-required model; no frozen default; default endpoint `http://localhost:11434/v1` | Audited; not a hosted external-pilot candidate; rejected |

No adapter declares a formal version. For this audit, each adapter version is
therefore the repository source blob reachable from the frozen parent
`765425eb9a6decabe3deb81abe2b08bb7914740e`; that is an audit identity, not a
stable adapter protocol version.

### Canonical adapter operational records

| Field | OpenRouter |
|---|---|
| Requested model | Required constructor value; repository default `openai/gpt-4.1-mini`. |
| Actual model | Response `model` is required to equal the request. Upstream serving provider is not reported or validated. |
| Response envelope | JSON mapping with `id`, `model`, `choices`, and optional opaque `usage`; assistant content is parsed into `AgentMove`. |
| Retry / fallback | One adapter request and no loop; model mismatch rejects. Hidden HTTP behavior and provider routing/fallback are not frozen. |
| Timeout / cancellation | `aiohttp` total timeout, default 60 s; complete underlying termination is unproved. |
| Streaming / tools | Non-streaming call; tools omitted rather than explicitly disabled and guarded. |
| Usage / cost | Opaque usage copied to mutable receipt; no completeness or cost calculation. |
| Credential path | Explicit key or constructor fallback to `OPENROUTER_API_KEY`; key retained on adapter. |
| Endpoint | Fixed `https://openrouter.ai/api/v1/chat/completions`; no independent allowlist. |
| Redirect / proxy | Library behavior not explicitly frozen or attested. |
| Raw response | Response text is read and parsed, then discarded; assistant text and mutable receipt remain. |
| Error handling | Maps rate limit, HTTP failure, invalid JSON, client errors, timeout, identity mismatch, and invalid content to fail-closed responses. |

| Field | Direct Anthropic |
|---|---|
| Requested model | Constructor value; repository default `claude-opus-4-8`. |
| Actual model | SDK response model is not validated or published as authoritative identity. |
| Response envelope | SDK message is converted to a mutable mapping; assistant text is parsed into `AgentMove`. |
| Retry / fallback | Adapter defaults to one transient retry; SDK `max_retries=0` is not supplied; council reroute/fallback layers exist. |
| Timeout / cancellation | SDK timeout, default 180 s, plus registry budget; full termination is unproved. |
| Streaming / tools | Non-streaming `messages.create`; tools omitted rather than explicitly disabled and guarded. |
| Usage / cost | Usage may exist in mutable SDK envelope; not surfaced as complete immutable usage and no cost calculation. |
| Credential path | Caller mapping/environment resolver for `ANTHROPIC_API_KEY`; raw key retained on adapter. |
| Endpoint | SDK-owned endpoint selection; no acquisition endpoint allowlist. |
| Redirect / proxy | SDK/HTTP behavior and dependency version are not frozen. |
| Raw response | Parsed SDK envelope retained in memory, not original bounded response bytes. |
| Error handling | Converts SDK errors to provider statuses and retries selected transient statuses. |

| Field | NVIDIA NIM |
|---|---|
| Requested model | Constructor value; repository default `nvidia/llama-3.1-nemotron-70b-instruct`. |
| Actual model | Envelope may contain a model but the adapter does not validate it. |
| Response envelope | OpenAI-compatible JSON mapping with choices; assistant content is parsed into `AgentMove`. |
| Retry / fallback | Adapter defaults to one transient retry; fallback/provider routing is not proved disabled. |
| Timeout / cancellation | `urllib` timeout, default 180 s, in `asyncio.to_thread`; cancelling the coroutine does not prove worker termination. |
| Streaming / tools | Non-streaming payload; tools omitted rather than explicitly disabled and guarded. |
| Usage / cost | Usage can remain inside ignored/mutable envelope; no complete receipt or cost calculation. |
| Credential path | Caller mapping/environment resolver for `NVIDIA_API_KEY`; bearer key retained on adapter. |
| Endpoint | Default `https://integrate.api.nvidia.com/v1/chat/completions`, but arbitrary base URL accepted. |
| Redirect / proxy | Default `urllib` behavior, not frozen or attested. |
| Raw response | Parsed envelope retained in memory, not original bounded response bytes. |
| Error handling | Maps HTTP/auth/rate-limit/timeout/transport errors and retries selected transient statuses. |

| Field | Local OpenAI-compatible server |
|---|---|
| Requested model | Required runtime value; no repository-frozen candidate model. |
| Actual model | Inherited response handling does not validate actual server/model identity. |
| Response envelope | Inherited OpenAI-compatible parsed mapping and `AgentMove` conversion. |
| Retry / fallback | Constructor default is zero adapter retries; hidden HTTP/server behavior and fallback are unproved. |
| Timeout / cancellation | Inherited `urllib` timeout, default 120 s, in a worker thread; full termination is unproved. |
| Streaming / tools | Non-streaming payload; tools omitted rather than explicitly disabled and guarded. |
| Usage / cost | No complete immutable usage receipt; no cost model. |
| Credential path | No key required by default; optional caller value retained on adapter. |
| Endpoint | Configurable URL, default `http://localhost:11434/v1`; separate `/models` probe exists. |
| Redirect / proxy | Default `urllib` behavior, not frozen or attested. |
| Raw response | Inherited parsed envelope, not original bounded response bytes. |
| Error handling | Inherited NVIDIA-compatible handling; probe returns a diagnostic tuple. |

### Other implemented external paths

These paths are real implementations but are not eligible acquisition adapters:

| Path | Provider(s) | Reason it is not a candidate |
|---|---|---|
| `scripts/live_smoke_provider.py` | Anthropic | Standalone duplicate smoke adapter; no acquisition contract, actual-model receipt, raw/usage/cost record, or SDK retry freeze. |
| `backend/agents/model_adapter.py` | Anthropic | Thin synchronous adapter; no timeout, receipt, acquisition isolation, usage, or cost contract. |
| `socrates_ai.py` | Anthropic, xAI, Gemini, OpenAI | Legacy direct paths; mutable/default aliases, sync I/O, incomplete identity/usage/cost evidence, and no acquisition isolation. |
| `scripts/proof_sprint_claude_live_v0_2.py` | Anthropic | Loads `.env`, performs multi-call proof flow, and has no immutable receipt or complete accounting. |
| `socratesAIv1.html` | Anthropic, xAI, Gemini, OpenAI | Browser-side direct fetch paths with client-held credentials and no repository acquisition boundary. |

`backend/dialogues/demo_openrouter.py`, the mixed-registry builders, and
`scripts/live_dialogue.py` are wrappers around the canonical adapters rather
than additional transports. The provider classes in
`backend/dialogues/providers.py` are explicitly unimplemented. OpenClaw
consultation/kernel adapters provide protocols and mocks, not an external
implementation.

## 4. Candidate capability matrices

The only status vocabulary in these matrices is `PROVEN`, `PARTIAL`,
`UNPROVEN`, `UNSUPPORTED`, and `UNKNOWN`. `PROVEN` means proved by current
source and hermetic tests; it does not infer live-provider behavior.

### OpenRouter

Provider: `OpenRouter`

Adapter: `backend.dialogues.openrouter_provider.OpenRouterProviderAdapter`

Transport implementation: `aiohttp` JSON POST

Candidate exact model: `openai/gpt-4.1-mini`

| Required field | Status |
|---|---|
| Requested-model pinning | PROVEN |
| Actual-model identity returned | PROVEN |
| Actual-model identity validated | PROVEN |
| Fallback disablement | PARTIAL |
| Explicit retry disablement | PROVEN |
| Adapter retry disablement | PROVEN |
| SDK-internal retry disablement | UNSUPPORTED |
| Hidden transport retry disablement | UNKNOWN |
| Timeout configured | PROVEN |
| Timeout cancels all work | UNPROVEN |
| Streaming disabled | PARTIAL |
| Tools disabled | PARTIAL |
| Temperature explicit | PROVEN |
| Seed status explicit | UNSUPPORTED |
| Max-output tokens explicit | UNSUPPORTED |
| Input-token estimation | UNSUPPORTED |
| Output-token reporting | PARTIAL |
| Usage reporting complete | UNPROVEN |
| Cost calculation available | UNSUPPORTED |
| Raw response available | PARTIAL |
| Transport status available | PROVEN |
| Credential access bounded | UNPROVEN |
| Credential material non-retention | UNSUPPORTED |
| Endpoint allowlist possible | PARTIAL |
| Redirect behavior controlled | UNKNOWN |
| Proxy behavior controlled | UNKNOWN |
| Provider routing controlled | UNPROVEN |
| Provider-visible body dry-run available | PARTIAL |
| Branch metadata excluded from body | UNSUPPORTED |
| Production mutation risk | UNPROVEN |
| Pilot readiness | UNSUPPORTED |

### Direct Anthropic

Provider: `Anthropic`

Adapter: `backend.dialogues.live_providers.LiveAnthropicAdapter`

Transport implementation: Anthropic async SDK

Candidate exact model: `claude-opus-4-8`

| Required field | Status |
|---|---|
| Requested-model pinning | PROVEN |
| Actual-model identity returned | UNKNOWN |
| Actual-model identity validated | UNPROVEN |
| Fallback disablement | UNPROVEN |
| Explicit retry disablement | PARTIAL |
| Adapter retry disablement | PARTIAL |
| SDK-internal retry disablement | UNKNOWN |
| Hidden transport retry disablement | UNKNOWN |
| Timeout configured | PROVEN |
| Timeout cancels all work | UNPROVEN |
| Streaming disabled | PARTIAL |
| Tools disabled | PARTIAL |
| Temperature explicit | UNSUPPORTED |
| Seed status explicit | UNSUPPORTED |
| Max-output tokens explicit | PROVEN |
| Input-token estimation | UNSUPPORTED |
| Output-token reporting | PARTIAL |
| Usage reporting complete | UNPROVEN |
| Cost calculation available | UNSUPPORTED |
| Raw response available | PARTIAL |
| Transport status available | PARTIAL |
| Credential access bounded | UNPROVEN |
| Credential material non-retention | UNSUPPORTED |
| Endpoint allowlist possible | UNKNOWN |
| Redirect behavior controlled | UNKNOWN |
| Proxy behavior controlled | UNKNOWN |
| Provider routing controlled | UNPROVEN |
| Provider-visible body dry-run available | PARTIAL |
| Branch metadata excluded from body | PARTIAL |
| Production mutation risk | UNPROVEN |
| Pilot readiness | UNSUPPORTED |

### NVIDIA NIM

Provider: `NVIDIA NIM`

Adapter: `backend.dialogues.nvidia_nim_provider.LiveNvidiaNIMAdapter`

Transport implementation: `urllib` JSON POST in `asyncio.to_thread`

Candidate exact model: `nvidia/llama-3.1-nemotron-70b-instruct`

| Required field | Status |
|---|---|
| Requested-model pinning | PROVEN |
| Actual-model identity returned | PARTIAL |
| Actual-model identity validated | UNPROVEN |
| Fallback disablement | UNPROVEN |
| Explicit retry disablement | PARTIAL |
| Adapter retry disablement | PARTIAL |
| SDK-internal retry disablement | UNSUPPORTED |
| Hidden transport retry disablement | UNKNOWN |
| Timeout configured | PROVEN |
| Timeout cancels all work | UNSUPPORTED |
| Streaming disabled | PARTIAL |
| Tools disabled | PARTIAL |
| Temperature explicit | PROVEN |
| Seed status explicit | UNSUPPORTED |
| Max-output tokens explicit | PROVEN |
| Input-token estimation | UNSUPPORTED |
| Output-token reporting | PARTIAL |
| Usage reporting complete | UNPROVEN |
| Cost calculation available | UNSUPPORTED |
| Raw response available | PARTIAL |
| Transport status available | PARTIAL |
| Credential access bounded | UNPROVEN |
| Credential material non-retention | UNSUPPORTED |
| Endpoint allowlist possible | PARTIAL |
| Redirect behavior controlled | UNKNOWN |
| Proxy behavior controlled | UNKNOWN |
| Provider routing controlled | UNPROVEN |
| Provider-visible body dry-run available | PARTIAL |
| Branch metadata excluded from body | PARTIAL |
| Production mutation risk | UNPROVEN |
| Pilot readiness | UNSUPPORTED |

### Local OpenAI-compatible server

Provider: local/open-weight runtime

Adapter: `backend.dialogues.openclaw_local.local_provider.LocalLLMAdapter`

Transport implementation: inherited `urllib` JSON POST

Candidate exact model: no repository-frozen exact model

| Required field | Status |
|---|---|
| Requested-model pinning | PARTIAL |
| Actual-model identity returned | PARTIAL |
| Actual-model identity validated | UNPROVEN |
| Fallback disablement | UNPROVEN |
| Explicit retry disablement | PROVEN |
| Adapter retry disablement | PROVEN |
| SDK-internal retry disablement | UNSUPPORTED |
| Hidden transport retry disablement | UNKNOWN |
| Timeout configured | PROVEN |
| Timeout cancels all work | UNSUPPORTED |
| Streaming disabled | PARTIAL |
| Tools disabled | PARTIAL |
| Temperature explicit | PROVEN |
| Seed status explicit | UNSUPPORTED |
| Max-output tokens explicit | PROVEN |
| Input-token estimation | UNSUPPORTED |
| Output-token reporting | PARTIAL |
| Usage reporting complete | UNPROVEN |
| Cost calculation available | UNSUPPORTED |
| Raw response available | PARTIAL |
| Transport status available | PARTIAL |
| Credential access bounded | UNPROVEN |
| Credential material non-retention | UNSUPPORTED |
| Endpoint allowlist possible | PARTIAL |
| Redirect behavior controlled | UNKNOWN |
| Proxy behavior controlled | UNKNOWN |
| Provider routing controlled | UNPROVEN |
| Provider-visible body dry-run available | PARTIAL |
| Branch metadata excluded from body | PARTIAL |
| Production mutation risk | UNPROVEN |
| Pilot readiness | UNSUPPORTED |

## 5. Selected or rejected provider

Provider: `OpenRouter`

Adapter: `backend.dialogues.openrouter_provider.OpenRouterProviderAdapter`

Exact model: `openai/gpt-4.1-mini`

Selection status: `REJECTED`

This is one rejected candidate, not a provider comparison or a pilot selection.
It wins the static priority ordering only as the smallest hardening base: exact
requested/returned model equality is already fail-closed, the transport is
non-streaming, and the endpoint surface is narrower than the other canonical
paths. A rejected candidate does not authorize credentials, network, or a call.

## 6. Exact-model identity audit

OpenRouter sends the exact constructor `model_id`, requires a non-empty value,
and rejects the response if `data["model"]` differs. Its mutable receipt records
the requested and returned model. This proves the adapter's equality check with
canned responses.

It does **not** prove the identity of the upstream provider selected behind the
OpenRouter route. The receipt's `provider_id` is the caller-defined local council
seat, not a provider-route attestation. No route/provider pin is sent and no
authoritative upstream identity is validated. Current repository evidence also
does not establish that the default model identifier remains externally
available. No web lookup or provider call was permitted in this static gate.

Anthropic, NVIDIA, Local, smoke, and legacy paths do not validate an actual
returned model identity. Mutable aliases such as `latest` are categorically
ineligible.

## 7. Fallback audit

OpenRouter rejects returned-model substitution, which is useful but insufficient:
the request does not freeze the upstream provider route or explicit routing and
fallback parameters. The absence of an application fallback loop is not proof
that all provider-side fallback is disabled.

Canonical Anthropic and NVIDIA adapters can be placed in a mixed registry. The
full council can also perform a rerouted provider retry when `phase_retry` is
enabled; `build_council` enables that mode by default. An acquisition pilot must
not use that orchestration path. No current external adapter exposes a sealed
end-to-end `fallbacks = 0` receipt.

Verdict: fallback disablement is not proved for any candidate.

## 8. Retry and SDK-retry audit

OpenRouter makes one application `_request` call and has no adapter retry loop.
That proves zero explicit and adapter retries in isolation. It does not freeze
the installed `aiohttp` version or prove hidden transport behavior.

Canonical Anthropic and NVIDIA default to one retry. Both can receive a zero
configuration, but the production defaults and builders are not acquisition-safe.
Anthropic constructs `AsyncAnthropic` without `max_retries=0`; SDK-internal
retries are therefore not explicitly disabled. NVIDIA uses `urllib` and an
application loop. Local defaults its inherited application loop to zero but does
not prove the hidden HTTP layer. Dependency requirements are lower bounds rather
than a frozen transport bill of materials.

Verdict: no candidate proves zero retries across application, adapter, SDK, and
HTTP layers in one sealed acquisition configuration.

## 9. Timeout and cancellation audit

OpenRouter configures an `aiohttp.ClientTimeout(total=...)`. Anthropic supplies a
timeout to its SDK and the registry applies an outer wait budget. NVIDIA and Local
pass a socket timeout to blocking `urllib` work executed through
`asyncio.to_thread`.

None supplies a hermetic proof that timeout/cancellation closes every underlying
socket, worker, SDK task, and response-body read before a second action could be
considered. In particular, cancelling an outer coroutine does not prove that a
NVIDIA/Local worker thread has terminated. No replacement call is allowed after
a timeout.

Verdict: configured time budgets exist; bounded total termination is unproved.

## 10. Streaming and tool audit

The four canonical adapters use request surfaces that currently return complete
responses rather than application-level streams. None explicitly freezes that
behavior or enables tools. Omission is not the complete evidence required by
this gate: the request and response contracts do not freeze `stream = false`, `tools = []`,
`tool_choice = none`, and a fail-closed rejection of tool-call response fields in
one acquisition receipt.

Verdict: non-streaming and zero tool activity are only partial at the sealed
adapter-contract level. Gate activity remained zero.

## 11. Temperature and seed audit

OpenRouter sends `temperature: 0`. NVIDIA and Local send `temperature: 0.0`.
The canonical Anthropic `ProviderRequest.to_messages_kwargs()` never emits a
temperature for any model; optional adaptive thinking does not change that.
No canonical adapter freezes seed support or an explicit `unsupported` seed
declaration in an acquisition manifest.

Verdict: temperature is candidate-dependent; seed state is not freeze-ready.

## 12. Provider-visible body audit

OpenRouter constructs a Python mapping and passes it to `aiohttp` as
`json=body`. Existing canned tests capture that mapping, not the final canonical
application bytes, byte length, and SHA-256 presented to the transport.

The body contains:

- the exact model and two chat messages;
- `temperature: 0` and JSON response format;
- no maximum output tokens;
- no explicit seed, streaming, tool, route, or fallback settings;
- a user prompt built by dumping the entire council `AgentTask` and
  `AgentState`.

Those council objects include process/transport fields such as task, session,
agent, round, slot, and attempt identifiers. They are not the semantic-only
`AcquisitionSemanticRequest`, so branch/run entropy is not demonstrably excluded.
The adapter immediately parses output into an `AgentMove`, while Acquisition
Contract v0 requires an isolated, `UNADMITTED` observation.

Anthropic exposes SDK kwargs rather than final serialized bytes. NVIDIA/Local
construct mappings but serialize only inside the live transport. No candidate
can currently publish an authoritative pre-dispatch body digest and length with
canned-to-live byte parity.

Verdict: exact application-body readiness is absent.

## 13. Credential boundary

The canonical builders read provider keys from caller mappings or environment
names and retain raw key material on adapter instances. OpenRouter also falls
back to `os.getenv` in its constructor. Other repository paths bulk-load several
keys, and one legacy proof script reads `.env`.

There is no acquisition-specific broker that proves:

- retrieval only after every pre-dispatch check;
- exactly one named secret retrieval;
- no enumeration or presence probe during the gate;
- ephemeral use without adapter/session retention;
- header and exception redaction across all paths;
- destruction before artifact publication.

This gate did not read an environment value, inspect credential presence, invoke
a credential store, or construct a live adapter with a real key.

Verdict: credential retrieval count during the gate is `0`; future one-secret
retrieval is not authorized.

## 14. Network, endpoint, proxy, and redirect boundary

OpenRouter hardcodes one HTTPS URL, but no independent boundary validates the
scheme, host, port, path, resolved addresses, TLS target, redirects, or proxy
behavior before dispatch. `aiohttp` behavior and installed version are not
frozen. Anthropic delegates endpoint behavior to its SDK. NVIDIA accepts an
arbitrary base URL while attaching a bearer credential. `urllib` defaults do not
constitute explicit redirect/proxy control. Local additionally exposes a network
probe, which is outside acquisition.

There is no dedicated one-shot network broker, endpoint allowlist tripwire,
redirect rejection, proxy/environment suppression proof, DNS/IP policy, response
size limit, or network-event ledger. These are later external-boundary blockers;
they do not supersede the earlier adapter failure in this gate.

Selected-candidate network policy record:

| OpenRouter boundary field | Repository evidence |
|---|---|
| Scheme | `https` hardcoded in adapter URL |
| Hostname | `openrouter.ai` hardcoded in adapter URL |
| Port | `443` implied by scheme; not independently frozen or validated |
| Path family | Exact current path `/api/v1/chat/completions`; no path-family enforcement |
| Redirect policy | `UNKNOWN`; no explicit redirect rejection/control |
| Proxy policy | `UNKNOWN`; no explicit proxy/environment policy |
| DNS requirements | `UNKNOWN`; no resolver, address-family, or resolved-IP policy |
| TLS verification | Library default only; no frozen TLS policy or attestation |
| SDK/HTTP transport | Direct `aiohttp` client; dependency is not exactly pinned |
| Telemetry endpoints | `UNKNOWN`; no explicit deny/allow evidence |
| Fallback endpoints | `UNKNOWN`; no independent destination ledger or route evidence |

Network attempts, DNS resolution, endpoint probes, and SDK/provider invocation
during this gate were all zero.

## 15. Usage and cost accounting

OpenRouter copies `data.get("usage")` into mutable `last_receipt` without schema,
completeness, units, provider-route, or consistency validation. Its canonical
`ProviderResponse` exposes no input/output/total token or cost fields. Anthropic
and NVIDIA may leave usage inside a mutable envelope, but do not publish a
complete immutable receipt; Local inherits that limitation.

No frozen pricing record exists for a candidate provider, route, and exact model.
No conservative integer micro-USD calculation, unknown-line-item rule, or cost
overrun check exists. OpenRouter additionally lacks a request-side output-token
bound and every candidate lacks an authoritative input-token bound.

Verdict: usage completeness, price identity, and maximum cost cannot be frozen.
This condition alone blocks authorization.

## 16. Research root and privacy

The only supported research action family remains
`ced-opening-socratic-question/v0`, with one legal action and no action/provider
comparison. A future external observation would be research-only, acquisition
only, and `UNADMITTED`; it would not be a CED successor, score, policy target, or
value label.

No live research fixture is authorized here. The existing council prompt exposes
process identifiers that are not part of the frozen acquisition semantic input.
No external adapter currently proves a privacy projection that excludes branch,
commit, session, task, agent, round, slot, attempt, local path, credential, and
production identifiers from the final provider-visible bytes and retained
artifact.

A future pilot must freeze before/after fingerprints for the source research
root, a detached sibling sentinel, and a detached production sentinel. All three
must be byte-identical after acquisition, and the runner must hold no mutable CED
authority.

Production data: `NONE`.

Action comparison: `NO`.

Provider comparison: `NO`.

Value evaluation: `NO`.

CED application: `NO`.

## 17. One-shot ledger design

The current registry does not provide an immutable acquisition dispatch ledger.
A future design must reserve, before dispatch, the pilot ID, semantic request
ID, transport attempt ID, provider, model, budget, authorization-manifest ID,
and state `PREPARED`. Immediately before the one network call it must atomically
transition to `DISPATCH_COMMITTED`. It must then reach exactly one terminal
state: `OBSERVATION_RECEIVED` or `TRANSPORT_FAILED`. The ledger must reject every
second logical dispatch under the same authorization regardless of diagnostic
failure. Credential retrieval may be recorded as an event, but it may not
replace these required states.

The ledger must count separately:

- credential retrievals;
- logical dispatches;
- low-level network events;
- redirects;
- SDK/HTTP attempts;
- model executions if authoritatively reported;
- response bytes consumed;
- tool activity;
- artifact publication.

No such ledger is implemented or authorized in this branch.

## 18. Raw-response retention

OpenRouter reads response text, parses it, and discards the full raw response;
only assistant content and a small mutable receipt survive. Anthropic and NVIDIA
retain parsed envelopes in mutable process memory, not immutable original bytes
with headers/status/digest/length and redaction classification. Canonical
`ProviderResponse` is assistant-text oriented.

A future adapter must preserve bounded raw response bytes once, record transport
status and safe headers, hash before interpretation, redact credentials and
transport secrets without mutating scientific content, and keep the observation
`UNADMITTED`. Response retention policy and classification are not yet frozen.

Verdict: raw-response evidence is inadequate.

## 19. Artifact and offline replay design

The existing sealed acquisition artifact and reverse-order replay lock remain the
authoritative canned evidence and were not modified. A future one-call artifact
must be a new write-once sibling containing:

- authorization manifest ID and exact repository HEAD;
- semantic request ID, exact application-body digest/length, and transport
  attempt ID;
- the complete write-once ledger state history;
- requested and actual provider/model/configuration;
- endpoint policy and network-destination evidence;
- timeout/retry/fallback/tool policy;
- bounded raw response reference/digest/length;
- complete usage and cost;
- before/after source-root, detached-sibling, and detached-production isolation
  fingerprints;
- credential-access count, abort/failure status, receipt IDs, and tripwire
  counters;
- one explicitly `UNADMITTED` observation and no canonical CED result.

It must contain no secrets.

Offline replay must consume only the committed artifact and must run under the
acquisition network/credential/provider/model/tool tripwire. It must reproduce
the semantic result, artifact identity, and canonical bytes without a second live
call. A failed call may not be replaced. No live artifact or replay is created by
this gate.

The future transport contract must preserve canonical role/target metadata
without hard-coding a permanent interlocutor, so it remains compatible with
future Alpha/Beta/Gamma/Delta carriage. Four-reasoner execution is not part of
this gate or the next hardening branch.

## 20. Abort and falsification conditions

Any future pilot must abort before dispatch on any of the following:

- branch or required HEAD mismatch;
- sealed artifact, historical hash, or core-lock mismatch;
- incomplete authorization manifest or pricing record;
- body digest/length mismatch or process metadata leakage;
- unavailable exact requested/expected model identity;
- unpinned provider route, endpoint, redirect, or proxy behavior;
- nonzero application, adapter, SDK, or HTTP retries/fallbacks;
- absent input/output/total-token or cost cap;
- credential retrieval before all static checks;
- missing one-shot ledger reservation;
- inability to guarantee bounded termination and response size;
- tool or streaming possibility;
- source, sibling, production-session, or canonical-CED mutation risk.

After dispatch starts, timeout, redirect, route/model mismatch, incomplete usage,
cost overrun, missing raw observation, tool activity, credential/header retention,
receipt mismatch, or any second attempt falsifies the pilot. The response remains
`UNADMITTED`; there is no retry, replacement call, or artifact rewrite.

## 21. Decision matrix

For control/capability rows, higher means stronger evidence or control. For
implementation/privacy-risk rows, higher means greater risk. This matrix is
qualitative and is not a weighted score; the decision follows prerequisite
precedence.

### Candidate comparison

| Dimension | OpenRouter | Anthropic | NVIDIA NIM | Local OpenAI-compatible |
|---|---|---|---|---|
| Exact-model verification | HIGH | LOW | LOW | LOW |
| Retry control | MEDIUM | LOW | LOW | MEDIUM |
| Fallback control | MEDIUM | LOW | LOW | LOW |
| Timeout termination | MEDIUM | MEDIUM | LOW | LOW |
| Request rendering | LOW | LOW | LOW | LOW |
| Endpoint control | MEDIUM | LOW | LOW | LOW |
| Credential safety | LOW | LOW | LOW | HIGH |
| Usage completeness | LOW | LOW | LOW | LOW |
| Cost completeness | LOW | LOW | LOW | LOW |
| Raw-response access | LOW | LOW | LOW | LOW |
| Implementation risk | MEDIUM | HIGH | HIGH | HIGH |
| Scientific value for an external pilot | HIGH | HIGH | HIGH | LOW |
| Privacy risk | HIGH | HIGH | HIGH | MEDIUM |
| Reversibility | HIGH | HIGH | HIGH | HIGH |

This comparison is source-level screening, not a provider/model experiment.
OpenRouter is the only candidate with high exact returned-model verification,
which determines the hardening base under the mandated priority order. It does
not make the adapter pilot-ready.

### Outcome comparison

| Dimension | ONE-CALL PILOT now | PROVIDER-ADAPTER HARDENING | EXTERNAL BOUNDARY HARDENING now | NO LIVE PILOT only |
|---|---|---|---|---|
| Exact-model verification | HIGH | VERY HIGH | HIGH | LOW |
| Retry control | MEDIUM | VERY HIGH | MEDIUM | LOW |
| Fallback control | MEDIUM | VERY HIGH | MEDIUM | LOW |
| Timeout termination | LOW | HIGH | HIGH | LOW |
| Request rendering | LOW | VERY HIGH | LOW | LOW |
| Endpoint control | MEDIUM | MEDIUM | VERY HIGH | LOW |
| Credential safety | LOW | MEDIUM | VERY HIGH | LOW |
| Usage completeness | LOW | VERY HIGH | LOW | LOW |
| Cost completeness | LOW | VERY HIGH | LOW | LOW |
| Raw-response access | LOW | VERY HIGH | LOW | LOW |
| Implementation risk | VERY HIGH | MEDIUM | HIGH | LOW |
| Scientific value | MEDIUM | HIGH | MEDIUM | LOW |
| Privacy risk | VERY HIGH | LOW | LOW | LOW |
| Reversibility | MEDIUM | VERY HIGH | HIGH | VERY HIGH |

`ONE-CALL PILOT now` fails mandatory conjunctions. `EXTERNAL BOUNDARY
HARDENING now` would leave the candidate adapter inadequate. `NO LIVE PILOT
only` is safe but does not select the smallest implementable prerequisite. The
atomic, reversible, evidence-producing choice is adapter hardening.

## 22. Exactly one decision

`PROVIDER-ADAPTER HARDENING REQUIRED`

Authorization manifest status: `INCOMPLETE`.

No manifest ID is issued. Blocking fields are:

- acquisition-specific adapter and canonical body digest/length;
- semantic-only provider-visible body;
- exact upstream provider/route identity;
- explicit zero fallback and every-layer zero retry;
- exact streaming/tool/temperature/seed state;
- input, output, and total-token bounds;
- frozen pricing record and maximum cost in integer micro-USD;
- bounded cancellation and response size;
- immutable raw/status/usage/cost receipt;
- credential broker and retrieval lifecycle;
- endpoint, redirect, proxy, DNS/IP, and TLS enforcement;
- one-shot ledger and write-once artifact path.

Readiness remains:

| Capability | Status |
|---|---|
| Experience Store | BLOCKED |
| Learned Value | BLOCKED |
| Learned Policy | BLOCKED |
| RL | BLOCKED |
| Self-play | BLOCKED |
| Depth 2 | BLOCKED |
| Production authority | BLOCKED |

## 23. Exact next branch and hypothesis

Next branch:
`feature/socrates-zero-provider-adapter-controls-v0`

Single hardening hypothesis:

> A network-inert, acquisition-only OpenRouter adapter can transform only the
> frozen `AcquisitionSemanticRequest` into canonical provider-visible bytes;
> freeze the exact requested model, route, output and total-resource settings;
> prove zero adapter retry/fallback/stream/tool behavior; and expose bounded raw,
> actual-identity, complete-usage, and conservative-cost evidence without
> credential access or external transport.

Minimum implementation:

1. Add a separate acquisition adapter interface; do not route through council
   `AgentTask`, `AgentState`, registry, session, or `AgentMove` application.
2. Add a pure canonical request renderer returning exact bytes, length, and
   SHA-256 from semantic input plus frozen configuration only.
3. Freeze exact OpenRouter model and upstream provider/route controls, explicit
   zero fallback/retry/stream/tool settings, explicit temperature/seed state,
   and strict input/output/total-token bounds.
4. Add a frozen offline pricing record and conservative integer micro-USD cap
   calculation.
5. Define a bounded raw transport result and immutable receipt carrying status,
   body digest/length, actual provider/model, complete usage, stop reason, cost,
   and fail-closed completeness checks.
6. Prove all behavior with canned transports and tripwires. Do not implement a
   real credential broker, real network dispatch, or live pilot in that branch.

Frozen components:

`SearchState v0/v1`, `Projection v0/v1`, `Value v0/v1`, `Policy v0`, `Greedy
v0`, `BestOfN v0`, `PUCT v0`, `N=4`, `c_puct=1.0`, `depth=1`, CED semantics,
Hybrid semantics, `CanonicalSuccessorEnvironmentV0`, Acquisition Contract v0,
the supported action family, and all sealed artifacts.

Success criteria:

- every mandatory adapter-level field needed before §61 is `PROVEN` in the
  required direction; only a feature that the authorization contract explicitly
  declares optional may be fail-closed as unsupported;
- identical semantic/config inputs render byte-identical bodies and receipts;
- process/transport metadata changes do not change provider-visible bytes;
- returned provider/model, usage, cost, tool/stream, and raw bounds are validated;
- retry/fallback counters remain exactly zero under canned transient failures;
- all acquisition, historical, core-lock, and repository-focused tests pass;
- activity remains `0/0/0/0/0/0` for live/network/credential/provider/model/tool.

Failure criteria:

- any need for credential, DNS, network, SDK/provider, model, or tool activity;
- any change to frozen components or sealed evidence;
- any process metadata in rendered bytes;
- mutable/default model, route, pricing, retry, fallback, or token behavior;
- incomplete raw, identity, usage, cost, timeout, or privacy evidence;
- any coupling to production session, canonical application, learning, or RL.

Only after this adapter milestone passes may a new gate decide whether the
external credential/network boundary is adequate. This report does not authorize
that boundary milestone or a live call.

# Stable branch memory — OpenRouter acquisition adapter controls v0

## Starting checkpoint

- Parent: `feature/socrates-zero-external-provider-authorization-gate-v0`.
- Fork HEAD: `03bc740fa73939e5942e9ed1c1674d3e165147b5`.
- Branch: `feature/socrates-zero-provider-adapter-controls-v0`.
- Protected untracked: `scripts/live_dialogue.py.bak` and the malformed root filename beginning `ocratic_followup_mandate`.

## Frozen decision and candidate

- Phase 8.5B: `PROVIDER-ADAPTER HARDENING REQUIRED`.
- Provider: OpenRouter (`openrouter`).
- Production adapter: `backend.dialogues.openrouter_provider.OpenRouterProviderAdapter`.
- Exact candidate model: `openai/gpt-4.1-mini`.
- Adapter ID: `socrateszero-openrouter-acquisition-adapter-controls/v0`.
- Live selection remains rejected; this branch grants no call authority.

## Content-addressed implementation

- Capability: `szorcap_c1ad52878f6013bc37a58949decf6c28d396dbef0f133db89124e9dcf08abb15`.
- Endpoint: `szorendpoint_1fcbacda717ffe27a18aaf133a418c1be569f751e34175ce2afe50043e408015`.
- Route: `szorroute_326db7be7fc68dc0eb22db9271d74073eaa59cffb16ff3524db847070c865071`.
- Control: `szorcontrol_1af1db4f46a9abe6b2d66c85812beb95f66ee6d5adc8f27ff40fb19defd203e7`.
- Renderer: `socrateszero-openrouter-renderer/v0`.
- Prepared body: `szorbody_c0b249765331603da69c395619476b198c76584ff36f4185b0aaf4cc3c6deadd`.
- Transport: `szortransport_4e5e882e46753c551651592abedc9e84da5495587eb052ccce010f0ee39a3231`.
- Token policy: `szortokens_1f15f1d831cc1cdc539c53ffe64fc55f9d069f56439ee9542ec1e49238fdd9a1`.
- Pricing: `szorprice_e8584e5c6aaa7192a05a336b771f822d9676af6107d8760d7dc598a7dcba1949`.
- Cost: `szorcost_7da097f344dca77f26a5d0d635ef1fa4b387da7ed1f6e5e18e93fdaae5b8d11e`.
- Raw evidence: `szorraw_7b33ff273ea5bc844820d59c5042a1992eacf5176be87328d2705669311ba464`.
- Identity: `szoridentity_5d6ee5c719780270cceff1521ca39f9dc2aa3b41970c23a952527ebcfba135e0`.
- Usage: `szorusage_ce4d7a352ff821264102d077de7ab5cdec4a6b487a52f2dd895256093c8966e4`.
- Canned envelope: `szorenvelope_85949fb30050330411f69a9145cfa5cd04420c874fe8e2527740603dfd1f2b48`.
- Reference receipt: `szorattempt_8d8a5e847724b6f5281865cb95f4360ccfcb42ae604359885a36cbc33e065bfa`.
- Reference summary: `szorrefreceipt_650f811440871da7c8672f29804b45da5286343bab9e7454d3eefb26bb8adb35`.

The receipt graph is `reference_canned_fixture_only`. Before aggregate there
are zero actual canned invocations, no actual attempt receipt and no actual
response receipt.

## Canonical request

- Schema: `socrateszero-openrouter-prepared-body/v0`.
- Fields: `max_tokens`, `messages`, `model`, `response_format`, `stream`, `temperature`, `tools`.
- SHA-256: `35462326a2590187b03219ad68a85b6203b3ca5364994f87dff18ec64556f5f5`.
- Length: `321` bytes.
- Output cap: `256`.
- Payload-only input bound: `321` via `FULL_REQUEST_UTF8_BYTE_COUNT_V0`.
- Payload-only total: `577`.
- Authoritative provider-input and total-token bounds: `NOT_ESTABLISHED`.
- Temperature `0`; stream `false`; tools empty; seed `PROVEN_UNSUPPORTED` and omitted.

## Controls and unresolved guards

- Endpoint intent: `https://openrouter.ai:443/api/v1/chat/completions`, POST/JSON, TLS required, redirects and environment proxies disabled.
- Application/adapter/hidden-local retries: `0/0/0`.
- SDK retry: `NOT_APPLICABLE` for the audited direct-`aiohttp` path.
- One-shot canned limit: `1`; timeout `5000 ms`; cancellation grace `50 ms`.
- Local application/adapter fallback: `false/false`.
- Upstream route and provider-side fallback disablement: `NOT_ESTABLISHED`.
- Exact-model trusted pricing and live maximum cost: `NOT_ESTABLISHED`; every monetary maximum is `null`.

Frozen mandatory unresolved guards, in authority order:

1. `P08_ROUTE_POLICY`.
2. `P09_FALLBACK_INTENT`.
3. `P17_INPUT_TOKEN_BOUND`.
4. `P18_PRICING_RECORD`.
5. `P19_COST_BOUND`.

`P08` remains first-guard authority. Later guards are independently reachable
only in counterfactual predicate tests and do not override first-guard-wins.

## Frozen evaluation

- Case set: `oracqcasesetv0_0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373`.
- Case-set SHA-256: `0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373`.
- Harness: `socrateszero-openrouter-acquisition-harness/v0`.
- Metrics schema: `socrateszero-openrouter-acquisition-evaluation/v0`.
- Artifact schema: `socrateszero-openrouter-acquisition-evaluation-artifact/v0`.
- Thresholds: `oracqthresholdsv0_c2381ba4b0e844b97a9309c9b8f6204d6e40d52e77a1a10d03d1f8d152bce7d1`.
- Projection SHA-256: `63f28955c510351e8b5ef2606f116eb6ab22ab85177982ef0dcda000eacf3f22`.
- Fixture manifest: `szorfixture_8d2c355b7f8a3297be9c5e9de344c9bff03c2afbf4579bf93eaa136572598b77`.
- Path inventory: `szorpathinventory_17d71d1ba4b33bc574373ebe4c1fc73960eacb91a7910400a7087c4674432136`.
- Cases: `7/44/8`, 59 total; receipts: 60; success invocation threshold: 34.
- Inventory: 17 source, 16 sibling, 39 production, 72 total.

## Invariants

- Network/credential/provider/model/tool/CED activity: `0/0/0/0/0/0`.
- Production OpenRouter adapter and provider registry remain unchanged.
- Acquisition Contract v0 and sealed historical artifacts remain unchanged.
- Adapter remains additive, offline/canned-only, default-disabled, non-governing and `UNADMITTED`.
- No aggregate before the pre-result freeze commit.
- Protected untracked files are never touched or staged.
- On `FALSIFIED`, preserve the artifact but perform no reverse replay and create no replay lock.

# Current OpenRouter acquisition adapter-controls state

## Completed authoritative result

| Item | Frozen state |
|---|---|
| Branch | `feature/socrates-zero-provider-adapter-controls-v0` |
| Fork HEAD | `03bc740fa73939e5942e9ed1c1674d3e165147b5` |
| Exact pre-result freeze | `88da597b6ba0c84e4c4614c001973febf3f40009` |
| Artifact commit | `911340d` |
| Provider / model | OpenRouter / `openai/gpt-4.1-mini` |
| Production adapter | audit source only; unchanged |
| New adapter | additive, canned-only, default-disabled, non-governing |
| Live authorization | rejected; later re-authorization required |
| Network/credential/provider/model/tool/CED | `0/0/0/0/0/0` |
| Aggregate | executed exactly once after the freeze |
| Hypothesis | `FALSIFIED` |
| First actual blocker | `P08_ROUTE_POLICY` |
| Artifact | committed, canonical, immutable |
| Replay lock | not performed; complete-pass prerequisite absent |

## Exact frozen request

- Schema: `socrateszero-openrouter-prepared-body/v0`.
- Body SHA-256: `35462326a2590187b03219ad68a85b6203b3ca5364994f87dff18ec64556f5f5`.
- Body length: `321` bytes.
- Semantic-only rendering and sibling-byte equality: proven offline.
- Temperature `0`; seed `PROVEN_UNSUPPORTED`; stream `false`; tools disabled.
- Output cap `256`; payload-only input/total bounds `321/577`.
- Authoritative provider input/total bounds: `NOT_ESTABLISHED`.

## Exact frozen evaluation

- Cases: `7/44/8` positive/orthogonal/precedence, 59 total.
- Evaluation receipts: 60; frozen success invocation threshold: 34.
- Case set: `oracqcasesetv0_0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373`.
- Thresholds: `oracqthresholdsv0_c2381ba4b0e844b97a9309c9b8f6204d6e40d52e77a1a10d03d1f8d152bce7d1`.
- Fixture: `szorfixture_8d2c355b7f8a3297be9c5e9de344c9bff03c2afbf4579bf93eaa136572598b77`.
- Projection: `63f28955c510351e8b5ef2606f116eb6ab22ab85177982ef0dcda000eacf3f22`.
- Path inventory: `szorpathinventory_17d71d1ba4b33bc574373ebe4c1fc73960eacb91a7910400a7087c4674432136` over `17/16/39` source/sibling/production paths.

## Authoritative evaluation

- Metrics ID: `szoracqmetrics_e1b0a6b267c7f8253a422e5e23321a572c5eea6088a7acbbfd43dfae6fcdb8fa`.
- Canned transport invocations: `0`; frozen success threshold: `34`.
- Positive complete cases / exact positive receipts: `0/7` / `0`.
- Orthogonal exact primary results: `8/44`.
- Precedence exact primary results: `3/8`.
- Invalid probe constructions: `0`.
- `P08_ROUTE_POLICY` was the first actual guard. Later unresolved guards remain
  `P09_FALLBACK_INTENT`, `P17_INPUT_TOKEN_BOUND`, `P18_PRICING_RECORD` and
  `P19_COST_BOUND`.
- No accepted control, fallback/retry/stream/tool, identity, raw/usage/privacy,
  token/pricing/cost, receipt or late-mutation violation occurred.
- Canned worker leaks / multiple invocations: `0/0`.

## Immutable artifact

- File: `artifacts/socrateszero_openrouter_acquisition_adapter_controls_v0.json`.
- Schema: `socrateszero-openrouter-acquisition-evaluation-artifact/v0`.
- Artifact ID:
  `szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f`.
- Payload SHA-256:
  `43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f`.
- File SHA-256:
  `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083`.
- Size: `331624` bytes; canonical JSON plus exactly one terminal LF.
- Artifact directory contains this artifact only; no reverse-replay artifact or
  replay lock exists.

The sealed reference fixture remains `reference_canned_fixture_only`. Its valid
raw, identity and usage receipt graph must not be conflated with the actual
aggregate, which produced zero canned responses and no actual response receipt.

## Verification

- OpenRouter contracts/renderer/adapter/cases/evaluator: `242 passed, 1 skipped`.
- Acquisition boundary tripwire: `54 passed, 8 skipped`.
- Pre-result total: `296 passed, 9 skipped, 0 failed, 0 warnings`.
- Post-result OpenRouter + Acquisition: `481 passed, 9 skipped`.
- Post-result Search/Value/Canonical Successor: `385 passed`.
- Full `tests_dialogues`: `3064 passed, 10 skipped`.
- Repository-wide suite: `3371 passed, 10 skipped, 23 warnings`.
- The 23 repository-wide warnings are 21 existing Pydantic `dict()`
  deprecations and two existing FastAPI duplicate-operation-ID warnings.
- The relevant skips are platform capability/privilege skips, including the
  Windows symlink-privilege case and unavailable Windows byte-environment APIs.
- All nine historical SHA-256 locks and the Phase 8 v2 core lock are exact.
- The authoritative 72-path evidence records `0/0/0` source/sibling/production
  mutations.
- Production adapter, provider registry, CED, Hybrid, SearchState, Value, Policy, search and Acquisition Contract v0 remain unchanged.
- Protected untracked hashes remain exact and the files remain unstaged.

## Decision

`OPENROUTER ACQUISITION ADAPTER HARDENING FALSIFIED`

Live pilot readiness remains `REQUIRES RE-AUTHORIZATION GATE`.

Next decision: `RETURN TO ARCHITECTURE DECISION`.

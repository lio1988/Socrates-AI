# Current OpenRouter acquisition adapter-controls state

## Pre-result freeze candidate

| Item | Frozen state |
|---|---|
| Branch | `feature/socrates-zero-provider-adapter-controls-v0` |
| Fork HEAD | `03bc740fa73939e5942e9ed1c1674d3e165147b5` |
| Pre-freeze implementation HEAD | `d899564` |
| Provider / model | OpenRouter / `openai/gpt-4.1-mini` |
| Production adapter | audit source only; unchanged |
| New adapter | additive, canned-only, default-disabled, non-governing |
| Live authorization | rejected; later re-authorization required |
| Network/credential/provider/model/tool/CED | `0/0/0/0/0/0` |
| Aggregate | not run |
| Artifact | absent |
| Replay lock | not run; forbidden on `FALSIFIED` |

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

## Known falsification surface

Mandatory unresolved guards are `P08_ROUTE_POLICY`, `P09_FALLBACK_INTENT`,
`P17_INPUT_TOKEN_BOUND`, `P18_PRICING_RECORD` and `P19_COST_BOUND`. The first
authoritative result must use first-guard-wins and must not dispatch after P08.
The threshold remains 34 and is not weakened to match the known blocker.

## Pre-result verification

- OpenRouter contracts/renderer/adapter/cases/evaluator: `242 passed, 1 skipped`.
- Acquisition boundary tripwire: `54 passed, 8 skipped`.
- Total: `296 passed, 9 skipped, 0 failed, 0 warnings`.
- The evaluator skip is a Windows symlink-privilege case; the eight boundary skips are unavailable Windows byte-environment APIs.
- All nine historical SHA-256 locks and the Phase 8 v2 core lock are exact.
- Two direct 72-path snapshots produced `0/0/0` scoped mutations.
- Production adapter, provider registry, CED, Hybrid, SearchState, Value, Policy, search and Acquisition Contract v0 remain unchanged.
- Protected untracked hashes remain exact and the files remain unstaged.

## Next safe step

Commit this pre-result freeze, report its exact hash, and only then invoke the
authoritative aggregate once under the active acquisition boundary tripwire.

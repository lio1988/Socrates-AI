# SocratesZero OpenRouter Wire Specification Manifest v2r1

## Executive verdict

**OPENROUTER WIRE SPECIFICATION MANIFEST v2r1: `SUPPORTED`**

This result is limited to the specification-evidence layer. It does **not** authorize a live OpenRouter call, a production parser, a Route Controls aggregate, or production authority.

The v2r1 lineage was rebuilt from the sealed Manifest-v1 checkpoint after the historical v2 lineage proved invalid/unverified. The new lineage uses one canonical Python schema, one mechanical JSON renderer, content-addressed records, six retained official-source snapshots, one write-once validation result, and one offline revalidation result.

## Base and isolation

- Canonical base branch: `feature/socrates-zero-openrouter-wire-spec-evidence-v1`
- Canonical base HEAD: `a37e6c0068e3132ca49128295a5ef8453f91592c`
- New branch: `feature/socrates-zero-openrouter-wire-spec-evidence-v2r1`
- Historical v2: `INVALID / UNVERIFIED / SUPERSEDED`; not repaired in place.
- Existing v1 snapshot files changed by v2r1: `0`
- Existing v1 snapshot files missing after v2r1: `0`
- v2r1 is additive only.

The sandbox snapshot does not include `.git`, so canonical Git-object comparison is not re-executed here. The completed v1 source snapshot used as the base was byte-compared before and after v2r1 and remained identical. Windows LF→CRLF warnings in the original v1 checkout were already known and did not prevent the sealed v1 tests from passing.

## Official source lineage

Official repository: `OpenRouterTeam/docs`

Pinned upstream commit: `4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db`

Exactly six retained sources are used:

| Role | Path | Git blob SHA | Bytes | SHA-256 |
|---|---|---|---:|---|
| OpenAPI | `openapi/openapi.yaml` | `62ebcd1e1ff13d671096954daee7d2229cd42238` | 1,397,709 | `bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713` |
| Router metadata | `guides/features/router-metadata.mdx` | `224633ac1dc7b8e9b7dab36f0d6458afd85a7309` | 14,038 | `4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6` |
| API overview | `api_reference/overview.mdx` | `72ec6e804f20127b16a83abb16a312ff8c56ce41` | 15,698 | `8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e` |
| Response cache | `guides/features/response-caching.mdx` | `437dc6abab221bb7bdcfbe6c4d3bdcb37df84b90` | 16,643 | `89e423514f98c2bdc5e288d5ea17159e78df29ea6ff56ea82cd8b68da1302f3e` |
| Provider routing | `guides/routing/provider-selection.mdx` | `7451e2ff9c5d898d642c9e1e6a516d1f3904ad01` | 61,399 | `2781071f570c53040c0c01a9f1840097a43e6032ebd4e3d9ab2dfbeb01bb2252` |
| Model fallbacks | `guides/routing/model-fallbacks.mdx` | `473c202c4420bbd917f9d65452a3b8240fc00cbf` | 6,002 | `6d77e3242812a2b669bf22f9c9c6ac59a5d838906271d1593b2fff864c6550c1` |

All six local bytes recompute to the listed SHA-256 values and Git blob identities.

## Canonical schema inventory

- Source records: `6`
- Typed facts: `35`
- Lossless mappings: `12`
- Relationship assessments: `14`
- Assumption-based authoritative mappings: `0`
- Repository-convention authoritative mappings: `0`

All authoritative record IDs are content-addressed through the repository canonical ID mechanism. Human-readable diagnostic labels are not authority.

## Established relationships

The following relationships are established for the bounded future wire-mapping decision:

- success-envelope metadata placement;
- selected error-envelope metadata placement;
- cache metadata absence behavior;
- independent cache attestation via documented response headers;
- attempt semantics;
- optional attempts-list semantics;
- endpoint collection structure;
- provider-field granularity;
- served-model precedence;
- strategy semantics;
- pipeline semantics;
- additive/unknown-field policy;
- actual served-model identity.

Exactly one mandatory relationship is unavailable by the documented response contract:

- `EXACT_ENDPOINT_RESPONSE_IDENTITY` → `NOT_ESTABLISHED`.

## Wire evidence boundary

### Actual served model

`$.model` is the authoritative response-side source used by v2r1 for `response.actual_served_model`. The requested model is never substituted when actual served-model evidence is absent.

### Provider granularity

The response-side provider field is classified as `HUMAN_DISPLAY_NAME`. It is not promoted to an exact endpoint slug.

### Exact endpoint

- Exact endpoint request intent: `ESTABLISHED` on the request-intent plane.
- Exact endpoint response identity: `NOT_ESTABLISHED`.

No transformation from a broad label such as `Azure` to `azure/swedencentral` is allowed.

### Cache

A missing router-metadata object is not sufficient evidence of a cache hit. The v2r1 contract grounds cache attestation in the documented cache response-header plane.

### Attempts

The mapping policy preserves absence rather than synthesizing an empty attempts list. Attempts and summary attempt semantics remain distinct typed evidence.

### Unknown fields

Unknown additive fields may be retained non-authoritatively. They cannot override or shadow known authority.

## Authoritative mapping records

The twelve positive mappings are lossless and source-linked:

- `$.openrouter_metadata.requested` → `router.requested`
- `$.openrouter_metadata.strategy` → `router.strategy`
- `$.openrouter_metadata.region` → `router.region`
- `$.openrouter_metadata.summary` → `router.summary`
- `$.openrouter_metadata.attempt` → `router.attempt`
- `$.openrouter_metadata.is_byok` → `router.is_byok`
- `$.openrouter_metadata.endpoints` → `router.endpoints`
- `$.openrouter_metadata.params` → `router.params`
- `$.openrouter_metadata.attempts` → `router.attempts`
- `$.openrouter_metadata.pipeline` → `router.pipeline`
- `$.model` → `response.actual_served_model`
- `$headers.X-OpenRouter-Cache-Status` → `response.cache_status`

No future parser implementation is part of this phase.

## Authoritative artifacts

Manifest:

- ID: `szorwirespecmanifestv2r1_a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15`
- SHA-256: `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb`
- Bytes: `50,971`

Validation:

- ID: `szorwiremanifestvalidationv2r1_7c88543b3dfcf525e41dd74e6f776add6950fc7897cd8681a77883078b7ae6bc`
- SHA-256: `7a75d644d0d6e61d3a9c5e5ef04bf5f16cd292206bc998e6952219b7ac11fb85`
- Hypothesis: `SUPPORTED`

Offline revalidation:

- ID: `szorwiremanifestrevalidationv2r1_6aa849c8b9b48d7593d0edde80329ba95040be0e92c87e5a22bfbd0dc8952a11`
- SHA-256: `75442d3bf74aeb5217a2e20db2580aacebe55d0fe21ee6d18288f38cb8defa1a`
- Semantic equality: `true`
- Manifest-ID equality: `true`
- Validation-result equality: `true`
- Manifest byte identity: `true`
- Validation byte identity: `true`

The authoritative build and offline revalidation were each performed once. Post-result tests only read and verify the persisted evidence.

## Verification

- Python compile/import: `PASS`
- v2r1 focused artifact/contract tests: `19 passed`
- sealed v1 + v2r1 focused tests: `48 passed`
- Route Controls v1 contracts/renderer/parser/cases/evaluation: `103 passed`
- Known inherited static-inventory node: `1 failed` (separate provenance boundary)

The inherited failure is not a wire-evidence failure. It detects raw historical path coupling in `openrouter_route_controls_evaluation.py`; prior architecture review classified this as provenance coupling, not runtime case-semantic dependence. It must be cleaned up separately before repository-wide green or an authoritative future mapping aggregate.

## External activity

For this v2r1 completion, official-source bytes came only from the user-provided recovery snapshot. No OpenRouter inference endpoint, credential, provider/model execution, tool execution, or CED application was invoked.

## Explicit non-claims

The following remain `NOT_ESTABLISHED` or blocked:

- exact endpoint response identity;
- P17 provider input-token bound;
- P18 trusted pricing record;
- P19 total request cost bound;
- live provider conformance;
- live pilot readiness;
- credential/network production safety;
- real shadow collection;
- Experience Store;
- learned Value;
- learned Policy;
- RL;
- production authority.

## Decision

`OPENROUTER WIRE SPECIFICATION MANIFEST v2r1 SUPPORTED`

This earns only the next architecture dependency:

`feature/socrates-zero-openrouter-provenance-boundary-v1`

The provenance-boundary cleanup should restore the existing raw-reference inventory contract without rewriting sealed Route Controls v1 evidence or weakening the test. After that cleanup passes, rerun a read-only wire-mapping authorization gate. Only that later gate may authorize one bounded raw-first parser implementation attempt.

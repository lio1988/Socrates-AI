# SocratesZero Phase 8.5D-S Recovery — OpenRouter Wire Specification Manifest v2

## Executive verdict

**Status: `SUPPORTED_FOR_WIRE_MAPPING_DECISION_ONLY`.**

The sealed Manifest v1 result remains unchanged and falsified. Its six-source
retrieval failed because the execution environment returned six
`NETWORK_ERROR` results before retaining official response bytes. This v2
lineage does not rewrite or reinterpret that result.

Instead, v2 pins the same six official source roles to the official
`OpenRouterTeam/docs` repository at commit:

```text
4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db
```

Each source is identified by an exact repository path, Git blob SHA and byte
size. The resulting manifest freezes:

- 6 pinned official source records;
- 28 directly documented typed facts;
- 12 lossless official-wire-to-internal mapping records;
- 14 relationship assessments;
- explicit `NOT_ESTABLISHED` boundaries.

This is enough to earn a separate **wire-mapping v2 authorization gate**. It
does not automatically authorize parser implementation or any live call.

## Safety and lineage

| Item | Value |
|---|---|
| Base branch | `feature/socrates-zero-openrouter-wire-spec-evidence-v1` |
| Base HEAD | `a37e6c0068e3132ca49128295a5ef8453f91592c` |
| New branch | `feature/socrates-zero-openrouter-wire-spec-evidence-v2` |
| Manifest v1 | unchanged; permanently `FALSIFIED` |
| Adapter/parser changes | none |
| CED/Hybrid/SearchState/Value/Policy/Search changes | none |
| Credentials | 0 |
| Authenticated OpenRouter calls | 0 |
| Provider inference/model/tool calls | 0 |

The official source snapshot uses immutable Git identities rather than mutable
rendered web pages. No seventh source, provider credential, inference request,
or repository-normalized fixture was used as authoritative specification
evidence.

## Pinned official sources

| ID | Official path | Git blob SHA | Bytes |
|---|---|---|---:|
| S01 | `openapi/openapi.yaml` | `62ebcd1e1ff13d671096954daee7d2229cd42238` | 1,397,709 |
| S02 | `guides/features/router-metadata.mdx` | `224633ac1dc7b8e9b7dab36f0d6458afd85a7309` | 14,038 |
| S03 | `api_reference/overview.mdx` | `72ec6e804f20127b16a83abb16a312ff8c56ce41` | 15,698 |
| S04 | `guides/features/response-caching.mdx` | `437dc6abab221bb7bdcfbe6c4d3bdcb37df84b90` | 16,643 |
| S05 | `guides/routing/provider-selection.mdx` | `7451e2ff9c5d898d642c9e1e6a516d1f3904ad01` | 61,399 |
| S06 | `guides/routing/model-fallbacks.mdx` | `473c202c4420bbd917f9d65452a3b8240fc00cbf` | 6,002 |

## Established wire relationships

The pinned official evidence establishes, at the documented level:

1. `openrouter_metadata` is a top-level sibling on opted-in successful
   responses.
2. It is also top-level on documented error paths, with explicit exceptions for
   pre-router failures and masked internal errors.
3. Cache hits intentionally omit router metadata; cache status is separately
   exposed by response headers.
4. `attempt` is an integer. On success it is one-indexed; values above one mean
   earlier attempts failed and fallback occurred. Documented failure examples
   can use zero when no provider was reached.
5. `attempts[]` is optional and preserves provider/model/status entries when
   fallback attempts are exposed.
6. `endpoints.total` and `endpoints.available[]` expose the candidate snapshot,
   including provider, model and selected status.
7. The provider value is a broad provider display/organization label. It is
   **not** sufficient to attest an exact endpoint selector such as
   `azure/swedencentral`.
8. The top-level response `model` is the authoritative actual served-model
   field for the future normalized contract.
9. `strategy` is a forward-compatible string rather than a permanently closed
   local enum.
10. `pipeline[]` records material router/plugin stages; unknown stage types are
    preserved opaquely and remain non-authoritative.
11. The metadata shape is additive. Unknown optional fields cannot override
    known authority fields.
12. A one-model experiment disables model fallback by using one exact `model`
    and omitting `models`.
13. Provider fallback request intent is expressed separately through
    `provider.allow_fallbacks=false`.

## Honest limitations

The manifest intentionally does **not** claim:

```text
exact endpoint response identity: NOT_ESTABLISHED
live OpenRouter response conformance: NOT_ESTABLISHED
P17 input-token bound: NOT_ESTABLISHED
P18 pricing record: NOT_ESTABLISHED
P19 total cost bound: NOT_ESTABLISHED
credential/network boundary: NOT_ESTABLISHED
live pilot readiness: NOT_EARNED
```

A broad provider label must never be upgraded to an exact endpoint slug. The
future parser must preserve absent optional arrays, distinguish cache metadata
absence from a proved cache hit, and fail closed when a mandatory actual-model
identity is missing.

## Delivered files

- `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2/evidence/openrouter_official_wire_specification_manifest_v2.json`
- `backend/dialogues/socrates_zero/openrouter_wire_spec_manifest_v2.py`
- `tests_dialogues/test_socrates_zero_openrouter_wire_spec_manifest_v2.py`
- this durable report and the branch checkpoint documents.

The validator is standard-library-only, import-inert and network-free. It
verifies the exact six-source set, source Git identities, 28 typed facts, 12
lossless mappings, 14 relationship assessments, the exact-endpoint honesty
firewall, and the P17/P18/P19/live-pilot non-claim firewall.

## Decision

```text
OPENROUTER WIRE SPECIFICATION MANIFEST v2:
SUPPORTED_FOR_WIRE_MAPPING_DECISION_ONLY

WIRE-MAPPING v2 AUTHORIZATION GATE:
EARNED

WIRE-MAPPING v2 IMPLEMENTATION:
NOT AUTOMATICALLY AUTHORIZED

LIVE PILOT:
BLOCKED
```

## Next decision

The next milestone is a read-only decision gate:

```text
Phase 8.5D-S2 — Official Wire-Mapping v2 Authorization Gate
```

That gate must decide whether exactly one raw-first parser/mapping
implementation attempt is justified. It must preserve all request intent,
provider-label granularity, exact-endpoint non-attestation, P17/P18/P19
blockers, and the known inherited repository-provenance boundary.

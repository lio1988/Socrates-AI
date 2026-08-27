# SocratesZero — OpenRouter Wire-Mapping v2 Authorization Gate

Phase 8.5D-S4. Branch
`feature/socrates-zero-openrouter-wire-mapping-v2-authorization-gate`, started
from `feature/socrates-zero-openrouter-provenance-boundary-v1` at exactly
`ae8b3ec17810deb0c8523c78a541d032994fb408`.

Decision only. No parser, no live call, no artifact rewrite.

## Result — layered authorization

The decision is recorded in layers, because a single verdict string has proven
easy to over-read.

| layer | status |
| --- | --- |
| Parser boundary specifiable | **YES** |
| Offline wire-mapping v2 implementation attempt | **AUTHORIZED / JUSTIFIED** |
| Runtime authority | **NOT AUTHORIZED** |
| Live OpenRouter execution | **NOT AUTHORIZED** |
| P17 input token bound | **NOT_ESTABLISHED** |
| P18 trusted pricing | **NOT_ESTABLISHED** |
| P19 total cost bound | **NOT_ESTABLISHED** |

**WIRE-MAPPING v2 IMPLEMENTATION EARNED** is retained only as the legacy gate
shorthand, and is explicitly defined as:

> one bounded offline implementation attempt is authorized; no runtime or live
> authority is granted.

Read it as nothing more than that. Authorizing an offline parser is not
authorizing that parser to hold runtime authority, and it is not authorizing any
OpenRouter execution.

## The decision being rerun

Phase 8.5D-R answered `SPECIFICATION EVIDENCE MANIFEST REQUIRED FIRST`, and
therefore `WIRE-MAPPING v2 IMPLEMENTATION NOT YET EARNED`, on two missing
prerequisites:

| prerequisite | then | now |
| --- | --- | --- |
| sufficient official response-wire evidence | missing | Manifest v2r1, SUPPORTED |
| clean repository provenance boundary | missing | Provenance Boundary v1, SUPPORTED |

Both dependencies have been addressed, so the gate is rerun on its merits.

## Prerequisite verification

| item | status | evidence |
| --- | --- | --- |
| Manifest v2r1 | **SUPPORTED** | validation `hypothesis_status: SUPPORTED`, `failure_reasons: []`, `reference_integrity: True`, `source_snapshot_integrity: True`, `authoritative_mapping_integrity: True`, `exact_endpoint_firewall: True` |
| Manifest v2r1 identity | unchanged | `szorwirespecmanifestv2r1_a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15`, file `3915bb0a…`, revalidation `manifest_byte_identity: True`, `semantic_equality: True`, `source_refetches: 0` |
| Provenance Boundary v1 | **SUPPORTED** | 64 locks pass; forbidden runtime raw-path coupling 0; historical → current coupling 0 |
| Route Controls request intent | **ESTABLISHED** | facts 31–35 (`$.provider.only`, `$.provider.order`, `$.provider.allow_fallbacks`, `$.provider.require_parameters`, `$.models`); manifest `exact_endpoint_request_intent: ESTABLISHED` |

Evidence base: 6 retained official sources from `OpenRouterTeam/docs` at pinned
commit `4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db`; 35 typed facts, **all**
`DIRECTLY_DOCUMENTED`; 12 lossless mappings; 14 relationship assessments (13
ESTABLISHED, 1 UNAVAILABLE_BY_DOCUMENTED_CONTRACT); assumption-based
authoritative mappings **0**; repository-convention authoritative mappings **0**.

## Response-wire audit

Every row traces to retained official evidence. Nothing below is inferred.

| # | field | status | supporting evidence |
| --- | --- | --- | --- |
| 1 | success envelope placement | **ESTABLISHED** | fact `$.openrouter_metadata` (SUCCESS, CONDITIONAL, ZERO_OR_ONE); assessment `SUCCESS_ENVELOPE_PLACEMENT` |
| 2 | error envelope placement | **ESTABLISHED** | fact `$.openrouter_metadata` (ERROR); assessment `ERROR_ENVELOPE_PLACEMENT` — metadata is a sibling of `error`; 500 and pre-router classes may omit it, documented explicitly |
| 3 | actual served model | **ESTABLISHED** | fact `$.model` (SUCCESS, REQUIRED, ONE); mapping → `response.actual_served_model`; assessments `SERVED_MODEL_PRECEDENCE`, `ACTUAL_SERVED_MODEL_IDENTITY`; validation `actual_model_authority: True` |
| 4 | requested model | **ESTABLISHED** | fact `$.openrouter_metadata.requested`; mapping → `router.requested`; kept distinct from #3 by `ACTUAL_SERVED_MODEL_IDENTITY` ("requested model must never substitute when actual model is absent") |
| 5 | provider identity | **ESTABLISHED** | facts `$.openrouter_metadata.endpoints.available[].provider`, `$.openrouter_metadata.attempts[].provider` |
| 6 | provider granularity | **ESTABLISHED (HUMAN_DISPLAY_NAME)** | assessment `PROVIDER_GRANULARITY`; explicit fact limitation: "broad/display provider label, not an exact endpoint slug"; manifest `provider_granularity: HUMAN_DISPLAY_NAME` |
| 7 | attempts field | **ESTABLISHED** | fact `$.openrouter_metadata.attempts` (OPTIONAL, ZERO_OR_MORE); mapping → `router.attempts` |
| 8 | attempts-list semantics | **ESTABLISHED** | assessment `ATTEMPTS_LIST_SEMANTICS`; typed entry facts `attempts[].provider`, `attempts[].model`, `attempts[].status`; absence preserved, never synthesized |
| 9 | attempt numbering | **ESTABLISHED** | fact `$.openrouter_metadata.attempt`; assessment `ATTEMPT_SEMANTICS` — success one-indexed; on error `0` means no provider reached, `>= 1` means attempted providers failed |
| 10 | routing strategy | **ESTABLISHED** | fact `$.openrouter_metadata.strategy`; mapping → `router.strategy`; assessment `STRATEGY_SEMANTICS` — documented OpenAPI enum, preserved as reported, never used to infer request fallback controls |
| 11 | pipeline | **ESTABLISHED** | facts `pipeline`, `pipeline[].type`, `pipeline[].name`, `pipeline[].data`; assessment `PIPELINE_SEMANTICS` — additive records; stage `data` is opaque and non-authoritative |
| 12 | cache metadata presence/absence | **ESTABLISHED** | fact `$.openrouter_metadata` (CACHE, `ABSENT_ON_CACHE_HIT`); assessment `CACHE_METADATA_ABSENCE` |
| 13 | cache-hit authority | **ESTABLISHED (header-borne)** | facts `X-OpenRouter-Cache-Status` (HIT/MISS), `-Age`, `-TTL`, `-Source-Id`; mapping → `response.cache_status`; assessment `CACHE_ATTESTATION` — "metadata absence alone is not used as cache proof" |
| 14 | unknown/additive field handling | **ESTABLISHED** | assessment `UNKNOWN_ADDITIVE_FIELD_POLICY`; every one of the 12 mappings carries `unknown_field_behavior: PRESERVE_NON_AUTHORITATIVELY` |
| 15 | exact endpoint request selector | **ESTABLISHED** | REQUEST facts 31–34; manifest `exact_endpoint_request_intent: ESTABLISHED` |
| 16 | exact endpoint response identity | **NOT_ESTABLISHED** | assessment `EXACT_ENDPOINT_RESPONSE_IDENTITY`, status `UNAVAILABLE_BY_DOCUMENTED_CONTRACT` — response provider metadata does not supply the request endpoint selector or endpoint ID |

15 of 16 ESTABLISHED. The sixteenth is not an unexplored gap: it is an
affirmative documented finding that the authority does not exist on the wire.

## The request-intent / response-identity distinction

The repository knows exactly which endpoint it *intends* to request (#15). That
is request construction and proves nothing about the response.

Because #16 is `UNAVAILABLE_BY_DOCUMENTED_CONTRACT` rather than merely
unestablished, a future mapper does not need to consult anything to decide it: it
can hard-declare `NOT_ESTABLISHED` as a documented constant of the wire contract.
Nothing in the mapper depends on resolving it, so it does not block
implementation — and it must continue to block, permanently, any claim that exact
endpoint response identity was *observed*. The validation artifact's
`exact_endpoint_firewall: True` is the existing enforcement of that firewall.

Provider label (#5, #6) must never be promoted to endpoint identity. These are
separate authorities at separate granularities and the manifest says so.

## Exact endpoint semantics

`UNAVAILABLE_BY_DOCUMENTED_CONTRACT` means the retained official response
contract does not provide an authoritative exact endpoint selector or endpoint
ID. It is a statement about the documented contract, not about this repository's
effort.

Two consequences bind the future mapper:

1. it must emit an **epistemic status with no endpoint value** — the status is
   the whole output for this concern, and there is no field carrying a candidate,
   best-guess or partial endpoint;
2. it must **never infer or synthesize the endpoint** — not from the provider
   label, not from the request-side selector it sent, not from endpoint candidate
   records, not from a single-element `provider.only`, and not from any
   combination of these.

Provider label (#5, #6) is `HUMAN_DISPLAY_NAME` granularity and is a different
authority at a different granularity. It must never be promoted to endpoint
identity. Request-side endpoint intent (#15) is what the repository *asked for*
and is not evidence of what served the response.

## Mapping eligibility

Every mapping the future v2 candidate needs falls under an eligible category:

| category | usage |
| --- | --- |
| A — direct official field-to-field | 12 of 12 mappings, all `transformation: IDENTITY`, `strength: DERIVED_LOSSLESSLY`, `lossless: True` |
| B — lossless official structural transformation | not required |
| C — explicit absence as ABSENT / NOT_ESTABLISHED | metadata absence on cache hit; optional `attempts`, `params`, `pipeline`; exact endpoint response identity |

No ineligible category is required. Repository-convention authoritative mappings
= **0**. Assumption-based authoritative mappings = **0**. No historical
canned-response shape, no previous parser assumption, and no historical expected
label is needed anywhere in the audit above.

## Predeclared future parser boundary

If and when Phase 8.5D-S5 runs, the v2 mapper may only:

1. accept raw response bytes;
2. parse JSON fail-closed — every mapping already declares
   `invalid_type_behavior: FAIL_CLOSED`;
3. distinguish the officially documented success and error envelope forms;
4. extract only the fields carried by the 35 retained facts;
5. preserve unknown fields without granting them authority
   (`PRESERVE_NON_AUTHORITATIVELY`);
6. emit explicit `ABSENT` / `PRESENT_EMPTY` / `PRESENT_WITH_ENTRIES` /
   `METADATA_UNAVAILABLE` / `NOT_ESTABLISHED` states;
7. keep `$.openrouter_metadata.requested` and `$.model` as separate authorities,
   never substituting one for the other;
8. keep provider label separate from exact endpoint identity;
9. decide cache status only from `X-OpenRouter-Cache-Status`, never from metadata
   absence;
10. treat multiple attempts as attempts only, never as fallback, absent an
    official relationship establishing that semantic.

This boundary is definable entirely from retained evidence, which is the
condition the gate required.

## Decision criteria

| # | criterion | verdict |
| --- | --- | --- |
| 1 | fail-closed raw JSON boundary definable | YES |
| 2 | actual served model officially established | YES |
| 3 | success/error envelope bounded from official evidence | YES |
| 4 | attempts representable without inventing semantics | YES |
| 5 | provider representable at exactly the supported granularity | YES |
| 6 | cache representable without absence→hit inference | YES |
| 7 | unknown/additive fields remain non-authoritative | YES |
| 8 | exact endpoint response identity can stay NOT_ESTABLISHED | YES |
| 9 | no repository-convention mapping required | YES (count 0) |
| 10 | no historical canned-response semantics required | YES (count 0) |
| 11 | provenance boundary clean | YES |
| 12 | sealed scientific evidence unchanged | YES (15/15 byte-identical) |

All twelve hold, so the layered result at the top of this document stands: the
parser boundary is specifiable, one bounded **offline** implementation attempt is
authorized, and **no runtime authority and no live OpenRouter execution are
authorized**. The legacy shorthand for exactly that is
`WIRE-MAPPING v2 IMPLEMENTATION EARNED`.

## Blockers that remain blockers

| item | status |
| --- | --- |
| runtime authority | **NOT AUTHORIZED** |
| live OpenRouter execution | **NOT AUTHORIZED** |
| P17 input token bound | **NOT_ESTABLISHED** |
| P18 trusted pricing | **NOT_ESTABLISHED** |
| P19 total cost bound | **NOT_ESTABLISHED** |
| exact endpoint response identity | **NOT_ESTABLISHED** (documented-unavailable) |
| live pilot | **NOT EARNED** |

Repository truth is unchanged on all of these; the manifest still records
`p17_input_token_bound`, `p18_pricing_record` and `p19_total_cost_bound` as
`NOT_ESTABLISHED` and `live_pilot_readiness: NOT_EARNED`. Parser authorization is
not provider-pilot authorization, and this gate does not move the pilot one step
closer.

## Provenance gate (read-only)

| guarantee | verdict |
| --- | --- |
| forbidden raw predecessor path coupling in runtime Python | 0 |
| historical / current provenance separation | PRESERVED |
| sealed Route Controls artifact | UNCHANGED, `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661` |
| Manifest v1 | UNCHANGED |
| Manifest v2r1 | UNCHANGED, `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb` |
| current mutation coverage | PRESERVED |
| all 15 frozen surfaces | byte-identical |

Nothing on the S3 branch was modified.

## Test gates

| gate | result |
| --- | --- |
| exact provenance static node | 1 passed |
| Route Controls focused | 103 passed |
| v1 + v2r1 evidence | 48 passed |
| provenance boundary | 64 passed |
| full `tests_dialogues` | 3279 passed, 10 skipped |
| `git diff --check` | PASS |

## External activity

OpenRouter calls 0. Provider calls 0. Model executions 0. Credential accesses 0.
CED applications 0. Authoritative aggregates 0. Replays 0. Source refetches 0.
This gate read frozen files and ran tests; it produced documentation only.

## What this unlocks

Exactly **Phase 8.5D-S5 — OpenRouter Raw Wire-Mapping v2**: one bounded attempt,
offline-first, raw-bytes-first, no live provider call, one parser version, one
normalized contract version, one fixture set mechanically derived from retained
official source evidence, strict unknown-field policy, strict provenance,
fail-closed, no production adapter authority, no live pilot.

It unlocks nothing else.

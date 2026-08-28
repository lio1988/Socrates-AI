# PRESENT — feature/socrates-zero-openrouter-one-live-shadow-v1

## State

- Branch: `feature/socrates-zero-openrouter-one-live-shadow-v1`
- Source HEAD: `e60856963310028bf391ac64792a9c1658f5e2c3` (S7A)
- Pre-inference freeze: `241e9e261bb8eaa4cd3d9b0186d78109042f5efe`
- Phase: **ONE live shadow call EXECUTED. HTTP 404 provider-routing refusal.
  Evidence captured, S5 mapped, S6 bound, replay deterministic.**

## Counters

```
jit_metadata_get_count     = 1
live_inference_post_count  = 1   (the one authorized call; never more)
local retries              = 0
authorizations consumed    = 1
```

The GET was performed in the previous round under its own authorization; this
correction round performed **no** network activity and read **no** credential.

## What happened

The single permitted first-party model-limit GET succeeded:

```
GET https://openrouter.ai/api/v1/model/openai/gpt-4.1-mini
HTTP 200 · 1709 bytes · sha256 728a7bfe823bf86c4cf8689fdd6535b5870cc4c7f4b628e982292cc29592e290
header evidence sha256 6d5e935d811ed1ca701081f3871a652d57e48842cb2050c28b86107327ac1dd5 (14 headers)
```

The frozen S7A parser then **refused** it:

```
model-detail raw response canonical_slug is not the exact model
```

## The finding, and how it was resolved

The live first-party response carries:

| field | live value | frozen requirement |
| --- | --- | --- |
| `data.id` | `openai/gpt-4.1-mini` | `openai/gpt-4.1-mini` ✔ |
| `data.canonical_slug` | `openai/gpt-4.1-mini-2025-04-14` | `openai/gpt-4.1-mini` ✗ |
| `data.alias_target` | `null` | must be null ✔ |
| `data.per_request_limits` | `null` | primary P17 path unavailable |
| `data.context_length` | `1047576` (int) | fallback path input |

S7A's synthetic fixture assumed `canonical_slug == id`. The real API returns a
**dated snapshot slug** as the canonical slug: `openai/gpt-4.1-mini` is the
stable pointer, `openai/gpt-4.1-mini-2025-04-14` is the build it currently
resolves to. `alias_target` is null, so this is not an alias — it is exactly the
"sibling version" case the phase rules say must not be silently accepted.

The original contract required *both* identity fields to equal the exact model,
so P17 was `NOT_ESTABLISHED` and the phase halted before dispatch.

**Resolved by operator ruling** with one narrow, additive correction: a single
authorized triple (requested alias, canonical model, observation digest). No
prefix match, no date tolerance, no suffix stripping, no resolver. The two
identities remain distinct and the wire still carries the requested alias.

**The parser was not weakened unilaterally.** In the abort round I refused to
relax it, because doing so would have manufactured a live result by moving the
standard. The change came from an explicit operator ruling, is bound to one
observation digest, and is proven by nine locks including source-level proof that
no heuristic was introduced.

The arithmetic now runs for real: the conservative fallback bound of 1,047,576
tokens gives `1047576 x 500000 + 256 x 2000000 + 0 = 524,300,000,000`
picodollars = **$0.5243**, within the operator's **$0.60** ceiling.

## Budget consequence

The metadata GET budget is consumed and was **not** spent again: P17 is
established from the already-retained response. An authorization has been minted
inside the preflight but **not consumed** — the claim store holds zero
consumption records, and no inference request has been made.

## Predecessor integrity

S7A, S6, S5, S3, Route Controls and Manifest surfaces are untouched. The known
predecessor timestamp race was not fixed here and did not flake in the pre-freeze
full-suite run (3672 passed, 10 skipped, exit 0).

## Correction round (offline only)

The live runner was hardened before any further network activity:

- one sealing step, so registered bytes are the dispatched bytes;
- request targets pinned per dispatch class, host pinned by contract;
- semantic headers carried as evidence with their own digest, Authorization
  excluded from every record;
- a single credential read site, with import inertness proven in-process;
- an offline JIT client exercised against synthetic fixtures and the retained
  real response;
- S5 and S6 bridges that carry the transport's own representation across without
  reconstruction.

59 offline locks, all passing. No network, no credential read.

## Next safe step

Nothing without explicit human authorization. The preflight is AUTHORIZED and
the next network action would be exactly ONE inference POST, which requires the
operator's explicit `AUTHORIZE ONE LIVE SHADOW CALL` referring to this exact
preflight.

Not pushed.


## The live call

```
POST https://openrouter.ai/api/v1/chat/completions
HTTP 404 · 622 bytes · sha256 3dd0c4c3ec8907cd830058bcf4d3d396ede743e138cb04310a73bf01d6693b8e
header evidence 782258d811969a545f53a7e30e19485d28c66f2e8b939a6bc8045b84e6d3d0c7 (13 headers)
registered body sha == dispatched body sha == 2f0345c1…   (byte preservation proven live)
```

OpenRouter refused to route:

> No endpoints found that can handle the requested parameters.

Its own metadata lists **three** available endpoints, none selected — `Azure`,
`OpenAI`, `Azure`, all serving `openai/gpt-4.1-mini-2025-04-14`. So the model
exists and is available; the request's *constraints* matched nothing.

**Which constraint is not determinable from one observation.** Candidates are the
`provider.only = ["azure/swedencentral"]` selector, the price ceilings, and
`require_parameters: true` against `response_format`/`temperature`/`tools`.
Isolating it needs further calls, which this phase does not authorize.

Note the endpoint list gives broad provider labels (`Azure`, `OpenAI`) and never
`azure/swedencentral` — the same BROAD_PROVIDER_ONLY granularity S6 recorded.

## Result

| layer | outcome |
| --- | --- |
| Transport | one POST, zero retries, bytes preserved |
| S5 mapping | **ACCEPTED** — `envelope_kind = ERROR` |
| Actual served model | `ABSENT_FROM_OBSERVATION` — never filled from request intent |
| Exact endpoint identity | `UNAVAILABLE_BY_DOCUMENTED_CONTRACT`, value `NONE` |
| S6 causal integration | **ACCEPTED** |
| Offline replay | deterministic, 0 network calls |
| Post-call cost | `POST_CALL_COST_NOT_ESTABLISHED` (no usage in a 404 envelope) |
| Runtime / CED authority | NOT_AUTHORIZED |

Artifact `szorliveshadowartifactv1_95b65837…`, sha256 `6cc6feae…`, 2508 bytes.
No credential material anywhere in evidence or artifacts.

## A post-call defect, preserved not patched

`s6_transport_record_from_live_v1` copies the *transport's* header digest, but S5
computes its own header evidence digest with different canonicalisation
(`ccc135b7…` vs `782258d8…`). S6 requires the observation's value, so that bridge
helper would fail an S6 binding. It was **not** used in the live path — the
binding above used the observation's digest directly — and per the phase rules a
live-semantic defect found after dispatch is documented, not patched into a
repeat call.

## Next safe step

Analyse the routing refusal offline. Any further call is a new phase with new
explicit authorization.

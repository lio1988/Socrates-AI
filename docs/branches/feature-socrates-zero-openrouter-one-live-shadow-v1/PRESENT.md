# PRESENT — feature/socrates-zero-openrouter-one-live-shadow-v1

## State

- Branch: `feature/socrates-zero-openrouter-one-live-shadow-v1`
- Source HEAD: `e60856963310028bf391ac64792a9c1658f5e2c3` (S7A)
- Pre-inference freeze: `241e9e261bb8eaa4cd3d9b0186d78109042f5efe`
- Phase: **P17 established from the retained observation; preflight AUTHORIZED;
  awaiting the final human authorization for exactly one inference POST.**

## Counters

```
jit_metadata_get_count     = 1   (spent in the earlier authorized attempt)
live_inference_post_count  = 0
local retries              = 0
credential accesses this round = 0
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

# PRESENT — feature/socrates-zero-openrouter-one-live-shadow-v1

## State

- Branch: `feature/socrates-zero-openrouter-one-live-shadow-v1`
- Source HEAD: `e60856963310028bf391ac64792a9c1658f5e2c3` (S7A)
- Pre-inference freeze: `241e9e261bb8eaa4cd3d9b0186d78109042f5efe`
- Phase: **ABORTED_PRE_DISPATCH — P17 could not be established from live evidence.**

## Counters

```
jit_metadata_get_count     = 1   (permitted maximum: 1)
live_inference_post_count  = 0   (required: 0 without authorization)
local retries              = 0
```

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

## The finding

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

The frozen proof contract requires *both* identity fields to equal the exact
model, so P17 stays `NOT_ESTABLISHED` and the phase halts before dispatch.

**The parser was not weakened.** Relaxing `canonical_slug`, or substituting
`data.id` for it, would have produced a live result by changing the standard that
was frozen precisely to prevent that. Whether a stable pointer and its dated
build may be treated as the same model for input-bound purposes is a scientific
question for a new phase with explicit authorization.

Had the parser accepted, the arithmetic was ready and under ceiling: the
conservative fallback bound of 1,047,576 tokens gives
`1047576 x 500000 + 256 x 2000000 + 0 = 524,300,000,000` picodollars = **$0.5243**,
within the operator's **$0.60** ceiling. That number is *not* a result; it is
what the preflight would have reported had P17 held.

## Budget consequence

The metadata GET budget is consumed. A future attempt needs a new GET, which
needs new authorization. No inference authorization was minted and none was
consumed: the claim store contains no consumption record for this phase.

## Predecessor integrity

S7A, S6, S5, S3, Route Controls and Manifest surfaces are untouched. The known
predecessor timestamp race was not fixed here and did not flake in the pre-freeze
full-suite run (3672 passed, 10 skipped, exit 0).

## Next safe step

Decide, as a separate authorized question, whether the frozen P17 identity rule
should accept a dated canonical slug for the same stable model pointer. Do not
edit the frozen contract inside this phase.

Not pushed.

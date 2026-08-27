# SocratesZero — OpenRouter Live-Safety Closure v1

Phase 8.5D-S7A on branch
`feature/socrates-zero-openrouter-live-safety-closure-v1`, created from the
completed S6 checkpoint
`f58c2a6113a4840fc003751e3b209f31d46fab67`.

## Status

Implementation and evaluation are in progress. No S7A authoritative aggregate
has been run, no live call is authorized, and no credential, provider, model or
network activity is permitted in this phase.

## Hypothesis

> A completely local, fail-closed live-safety layer can define a trustworthy
> pre-call input-token upper-bound proof path, require complete price ceilings
> for every applicable documented charge class, compute an exact worst-case cost
> bound without floating-point authority, bind an operator-approved total spend
> ceiling, and create a single-use live authorization that can later be consumed
> only after a finite JIT preflight and exactly one network dispatch.

The result will be either `OPENROUTER LIVE-SAFETY CLOSURE v1 SUPPORTED` or
`OPENROUTER LIVE-SAFETY CLOSURE v1 FALSIFIED` after a semantic freeze and exactly
one authoritative offline aggregate.

## Sealed predecessor

S6 remains immutable: artifact
`szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779`,
SHA-256 `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d`,
SUPPORTED with deterministic replay. S7A is additive and grants no runtime or
CED authority.

## Required distinctions

- `max_tokens = 256` is the established output bound.
- 447 bytes is historical exact request-byte evidence, never a token bound.
- P17 proof architecture and P17 current authority are separate states.
- P18 actual endpoint pricing remains `NOT_ESTABLISHED` at
  `BROAD_PROVIDER_ONLY` granularity.
- `ProviderPreferences.max_price` supplies server-enforced component ceilings;
  it is not actual pricing or a total-spend ceiling.
- P19 formula structure, applicable charge coverage and current authority remain
  separate.
- A future candidate request with complete `max_price` has new bytes and a new
  identity.

## P17 retained-evidence audit

The retained first-party evidence supports a trustworthy proof architecture,
but it does not contain the current limit value for the exact requested model.
The honest split is therefore:

- P17 proof architecture: `READY`.
- P17 current authority: `JIT_PENDING`.

The accepted proof hierarchy is deliberately narrow.

1. Prefer exact-model `$.data.per_request_limits.prompt_tokens`, with limit kind
   `MAX_PROMPT_TOKENS`. The retained OpenAPI describes `PerRequestLimits` as
   "Per-request token limits" and this field as "Maximum prompt tokens per
   request" (`openapi.yaml`, lines 20245-20264). It is accepted only when the
   exact-model record supplies a non-null, positive exact integer.
2. Otherwise accept exact-model `$.data.context_length`, with limit kind
   `MODEL_CONTEXT_LIMIT`, only through the guarded whole-context proof. The
   field is documented as "Maximum context length in tokens" (`openapi.yaml`,
   lines 14240-14249), and the endpoint schema states that input and output
   tokens share the context window (`openapi.yaml`, lines 21642-21650). The
   entire context limit is used as the conservative input bound. The established
   output cap of 256 is not subtracted.

Both paths bind the fact to `openai/gpt-4.1-mini`; a field name or a generic
model example is not authority. The future JIT source is the official model
detail operation, `GET /api/v1/model/openai/gpt-4.1-mini`, documented by
`/model/{author}/{slug}` in the retained OpenAPI (`openapi.yaml`, lines
34833-34896).

### Retained authority

All retained sources below are frozen from
`OpenRouterTeam/docs@4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db`.

| source | retained identity | SHA-256 | relevant semantics |
| --- | --- | --- | --- |
| `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/openapi.yaml` | `szorwiresourcev2r1_61aba8cdf4e3403dbac683bea535de1bfaf96fd3292dfa9549d749a7d918a4fc` | `bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713` | exact-model detail operation; `Model.id`, `canonical_slug`, `context_length`, `per_request_limits`; whole-context relationship |
| `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/api-reference-overview.mdx` | `szorwiresourcev2r1_0fb3a6af79da19e7e78463abb9d77d6e92a6d7ddc43317adc16683d997871729` | `8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e` | `prompt_tokens` usage and native-tokenizer billing semantics; request transformation acknowledgement |
| `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/router-metadata.mdx` | `szorwiresourcev2r1_59d512e602085e0d93b955483bf33f81d606125c5cf6ea871cb9044df7202355` | `4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6` | router pipeline, context compression, guardrail, plugin and server-tool scope |

The enclosing retained manifest is
`szorwirespecmanifestv2r1_a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15`,
SHA-256
`3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb`.

### Billing, transformation and framing scope

The API overview states that completion-response token counts use the model's
native tokenizer and that credit usage and model pricing use those native token
counts (`api-reference-overview.mdx`, lines 324-340 and 450-454). Any chat
framing or transformed request content actually presented to the primary model
occupies that model's context. Thus a direct maximum over prompt tokens, or the
guarded whole-model context limit, conservatively bounds the primary completion
`usage.prompt_tokens` domain even when framing is not predicted exactly.

This proof does not claim that one primary-model context limit bounds independent
router pipeline work. The retained router documentation says a request may pass
through context compression, guardrails, plugins or server-side tools
(`router-metadata.mdx`, lines 21-23 and 159-177). P17 is therefore scoped to the
primary completion prompt-token charge. The exact request must keep plugins
absent, tools disabled and its text-only modality proof bound to the new bytes;
any separately applicable auxiliary charge must be rejected or covered by its
own policy. If "billable input tokens" were broadened to include auxiliary
pipeline invocations, the retained evidence would not establish Path A.

### Rejected P17 routes

- `top_provider.context_length` is not the pinned
  `azure/swedencentral` endpoint.
- `PublicEndpoint.max_prompt_tokens` and endpoint `context_length` are not
  accepted: the retained endpoint schema cannot bind its broad
  `provider_name` or undocumented `tag` to the exact request selector.
- The OpenAPI `architecture.tokenizer` value is only a `ModelGroup` family
  label such as `GPT`, not a tokenizer implementation or vocabulary identity.
  No retained exact model-to-tokenizer binding, implementation/version pin,
  vocabulary or merge digest, special-token policy, chat-framing contract, or
  pre-call token-count endpoint exists.
- Request bytes, character count, word count, heuristic ratios, arbitrary safety
  factors, historical usage, post-call usage and model memory remain
  non-authoritative.

### Exact finite JIT fact

S7B must obtain exactly one immutable same-preflight
`TrustedModelInputLimitRecordV1` from the official exact-model detail response.
It must bind the source authority and kind, request method/path, HTTP status,
exact `data.id`, `canonical_slug` and alias state, selected limit field and
semantic kind, positive integer value, retained schema source IDs/digests, raw
response digest and length, source-record identity, observation status,
preflight execution identity, model-binding identity and proof-method version.

A separate request-bound P17 proof must bind that record to the exact live
overlay ID, rendered request ID/body digest/body length, exact model, message and
modality proof, output-bound identity, and provider-policy identity. A null,
malformed, non-integral, stale, mismatched, aliased-without-authority or
semantically ambiguous record fails before inference dispatch. No production
limit value is invented in S7A.

## Non-goals

No OpenRouter inference, authenticated request, credential access, current-price
retrieval, provider/model call, CED application, production wiring or push.

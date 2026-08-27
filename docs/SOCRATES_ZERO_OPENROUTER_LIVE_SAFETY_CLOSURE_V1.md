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

## Non-goals

No OpenRouter inference, authenticated request, credential access, current-price
retrieval, provider/model call, CED application, production wiring or push.

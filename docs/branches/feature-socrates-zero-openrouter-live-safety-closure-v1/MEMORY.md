# MEMORY — feature/socrates-zero-openrouter-live-safety-closure-v1

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-prelive-integration-v1`
- Source HEAD: `f58c2a6113a4840fc003751e3b209f31d46fab67`
- S6 artifact ID:
  `szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779`
- S6 artifact SHA-256:
  `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d`

## Non-negotiable invariants

1. S6 semantic files and authoritative evidence are immutable predecessors.
2. S7A is local and import-inert: zero network, credential, provider, model,
   paid, live-dispatch or CED activity.
3. A request byte length, character count or heuristic is never P17 authority.
4. P17 proof architecture and current factual authority are separate.
5. Exact actual pricing remains separate from server-enforced price ceilings.
6. `request_usd` must be explicit for a future live authorization; absence is
   unknown and never zero.
7. Image/audio non-applicability is proved from exact candidate request bytes.
8. Component price ceilings and operator total-spend ceiling are different
   authorities.
9. Money uses canonical decimal strings and integer picodollars, never binary
   floats.
10. Any complete-price candidate request receives new canonical bytes, digest,
    length and identity; the historical 447-byte request stays historical.
11. One-call authorization is content-addressed and consumable once. A failure
    never grants an automatic retry.
12. Request-side safety policy never becomes response authority.

## Current inherited state

- Output bound: `ESTABLISHED = 256`.
- Historical request bytes: 447 bytes, not tokens.
- P17 current authority: `NOT_ESTABLISHED`.
- P18 actual pricing: `NOT_ESTABLISHED`.
- Pricing granularity: `BROAD_PROVIDER_ONLY`.
- Trusted unit-price ceiling mechanism: `ESTABLISHED` through
  `components.schemas.ProviderPreferences.max_price`.
- P19 formula: `READY`.
- P19 charge coverage: `INCOMPLETE` because `request_usd` is unbounded.
- One live shadow call: `NOT_AUTHORIZED`.

## Experiment discipline

Finish and test every semantic contract, case, expectation and threshold; commit
them; create an explicit freeze commit; only then execute exactly one
authoritative offline aggregate and deterministic replay. After execution, never
patch semantics or rerun the same experiment.

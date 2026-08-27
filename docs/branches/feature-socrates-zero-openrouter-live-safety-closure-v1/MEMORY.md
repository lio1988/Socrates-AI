# MEMORY — feature/socrates-zero-openrouter-live-safety-closure-v1

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-prelive-integration-v1`
- Source HEAD: `f58c2a6113a4840fc003751e3b209f31d46fab67`
- S6 artifact ID:
  `szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779`
- S6 artifact SHA-256:
  `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d`
- S7A freeze HEAD:
  `dca2f2d97b1eeba9626ec9490edf722b64681ef5`

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
13. A claim-store path hash is identity, not proof of physical durability or
    rollback resistance. Live authorization requires a path-bound readiness
    attestation and scope-correct operator/store evidence.
14. S7A proves claim mutation/reuse refusal while the attested claim persists;
    the physical `ATOMIC_CREATE_NEW_TRUSTED_DURABLE_NON_ROLLBACK` realization is
    an S7B JIT fact.

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

## Implemented additive state

- P17 proof architecture: `READY`; production fact: `JIT_PENDING`.
- Request overlay v2: `READY`; production price-bearing request identity:
  `JIT_PENDING`.
- Prompt/completion/request ceiling contract: `READY`; production values:
  `OPERATOR_REQUIRED` and `JIT_PENDING`.
- P19 formula structure: `READY`; applicable charge coverage: `COMPLETE`;
  current production authority: `JIT_PENDING`.
- Operator total-spend contract: `READY`; production value/grant:
  `OPERATOR_REQUIRED` and `JIT_PENDING`.
- One-call authorization, full-preflight revalidation and atomic consumption:
  `READY`.
- Claim-store-readiness contract: `READY`; physical trusted durable
  non-rollback store and live `szorclaimstoregrantv1_...` evidence:
  `S7B_JIT_PENDING`/`OPERATOR_REQUIRED`.
- Runtime/CED authority: `NOT_AUTHORIZED`; live OpenRouter execution:
  `NOT_EXECUTED`.

Synthetic fixture identity, never production authority:

- request:
  `szorrenderedliverequestv2_4d1b04a731f98462a8d349611c105fe818fae18c1a1a3de8c2b02dfb835c00a2`;
- body SHA-256:
  `9ba640bf29bf6ad77c2a6dd0b4b038fbe4567aa51146b0e2699ea49a2ee0b8a8`;
- body length: 512 bytes;
- fixture P17/price/total values: 4096 input tokens, USD 1/million
  prompt tokens, USD 2/million completion tokens, USD 0.000001/request, and
  4,609,000,000 picodollars total.

## Frozen case and gate memory

- Case set:
  `szorlivesafetycasesetv1_21ab3255104dbb5fe0ca5e2255a2f4d205c7f2d6364a67588e2c39b69c9eba01`.
- Thresholds:
  `szorlivesafetythresholdsv1_ccc445fda16e9022f40ed0a3d133365d823b1cbe0f844803926c8564502ecec9`.
- Inventory: 73 = 20 positive/property + 53 adversarial.
- Pre- and post-authoritative gates: S7A 106; S6 149; S5 109; S3 64; route 103;
  manifest 25; all OpenRouter 835 passed/1 skipped; full `tests_dialogues` 3643
  passed/10 skipped; predecessor gate 742/742; S6 surfaces 8/8 unchanged.
- `KNOWN PRE-EXISTING INTERMITTENT PREDECESSOR FAILURE`: an earlier pre-S7
  all-OpenRouter run had exactly
  `test_one_shot_offline_acquisition_publishes_complete_derived_log` fail with
  1 failed/728 passed/1 skipped/2817 deselected; isolated rerun passed 1/1. No
  S7A fix was made. The final pre-freeze run was clean and the known race did
  not recur in the post-authoritative gates.

## Authoritative result memory

- Decision: `OPENROUTER LIVE-SAFETY CLOSURE v1 SUPPORTED`.
- Artifact:
  `szorlivesafetyartifactv1_237286af63bc509db7fe2cbd4e40a78150d36213ec162a2a745494eeeeed70b3`;
  SHA-256
  `9bdc7f58ca1e29a9ed082a863a6bc4487f9687c564207887b226953cc6f95a01`;
  52,053 bytes.
- Replay execution:
  `szorlivesafetyreplayexecutionv1_0292ea7f00e670fdf9c4d6254b4ebeca4d0b1e97744e5a0a7b294254b7f151da`;
  SHA-256
  `3a5cb6cacc85e3c8a842bade1e0ac279929682c4db547cdd16dc9eed22454d2e`;
  740 bytes.
- Replay lock:
  `szorlivesafetyreplaylockv1_116f9049f8495ad63276973a4d0e09815ead6435bddb45ccaf319a2d8e964dc6`;
  SHA-256
  `6c66d96527e271efef5dd0ec8de139ebb8f96f44dce79490a783ae69f9b3f675`;
  655 bytes.
- Replay semantic equality, artifact-ID equality and byte identity: true.
- Results: 73 total, 20 positive accepted, 53 adversarial rejected, 0
  unexpected, all thresholds passed, every zero-hazard metric 0, external
  activity 0, S6 surfaces 8/8 unchanged.

Final states: P17 `READY`/`JIT_PENDING`; output bound `ESTABLISHED = 256`;
P18 `NOT_ESTABLISHED` at `BROAD_PROVIDER_ONLY`; server ceiling coverage
`COMPLETE`; P19 formula `READY`, coverage `COMPLETE`, current authority
`JIT_PENDING`; authorization `READY`; JIT preflight `READY`; runtime
`NOT_AUTHORIZED`; live `NOT_EXECUTED`; one call
`AUTHORIZED_PENDING_JIT_PREFLIGHT`.

Remaining S7B JIT facts: exact first-party model-limit record; explicit operator
prompt/completion/request ceilings; explicit total-spend ceiling; credential
presence; transport readiness; and the physical trusted durable non-rollback
claim store with live grant evidence. Production request ID/body digest/length
remain JIT-pending because operator price values are not frozen. The synthetic
512-byte request remains separate test authority.

## Development-check ledger

Before freeze, one non-persisted full case pass produced 73/73 expected and 0
unexpected. Three non-persisted in-memory builder checks observed `SUPPORTED`,
all thresholds true, 73 results, predecessor 8/8 and three-way determinism. The
first render was 51,938 bytes with development-only artifact ID
`szorlivesafetyartifactv1_8e0d9fb1f77d065a9ccf2222a18df0d519f2e9cc65974c95854a18058b9ac003`.
Later semantic hardening makes that ID and length stale; neither may be used as
freeze evidence. Nothing from those development checks was persisted and no
external activity occurred. The designated evidence above supersedes them.

## Experiment discipline

The semantic freeze and single designated persisted aggregate/replay are
complete. The three write-once evidence paths now exist. Never patch frozen
semantics, overwrite the evidence or rerun the S7A experiment. Proceed only to
the finite S7B JIT preflight and one live shadow call under separate authority.

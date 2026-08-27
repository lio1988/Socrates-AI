# SocratesZero — OpenRouter Live-Safety Closure v1

Phase 8.5D-S7A on branch
`feature/socrates-zero-openrouter-live-safety-closure-v1`, created from the
completed S6 checkpoint
`f58c2a6113a4840fc003751e3b209f31d46fab67`.

## Status

`OPENROUTER LIVE-SAFETY CLOSURE v1 SUPPORTED`.

Semantics were frozen at
`dca2f2d97b1eeba9626ec9490edf722b64681ef5`. The one designated authoritative
offline aggregate and deterministic replay completed once, produced write-once
evidence, passed every threshold and preserved all eight S6 predecessor
surfaces. Runtime and CED authority remain disabled; no credential, provider,
model or live OpenRouter request was executed.

## Hypothesis

> A completely local, fail-closed live-safety layer can define a trustworthy
> pre-call input-token upper-bound proof path, require complete price ceilings
> for every applicable documented charge class, compute an exact worst-case cost
> bound without floating-point authority, bind an operator-approved total spend
> ceiling, and create a single-use live authorization that can later be consumed
> only after a finite JIT preflight and exactly one network dispatch.

The frozen experiment supports the hypothesis. This result establishes the
local safety architecture and reduces the future live call to finite JIT facts;
it does not itself authorize runtime or execute that call.

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
- A path-derived claim-store ID is identity, not proof of durable or
  rollback-resistant storage. S7A requires an explicit readiness attestation;
  physical realization of the trusted store is an S7B JIT fact.

## Supported architecture

The following additive surfaces are implemented and locked by focused tests.

- P17 accepts only an exact-model trusted limit record and binds its source,
  freshness, selected semantic field, exact request, modality, output bound and
  price policy. The proof architecture is `READY`; the current production fact
  is `JIT_PENDING`.
- Request overlay v2 requires explicit prompt, completion and request price
  ceilings and renders a new exact request body. The structural renderer is
  `READY`; production component values are `OPERATOR_REQUIRED` and the exact
  production request identity is `JIT_PENDING`.
- P19 covers prompt tokens, the established 256-token output cap and the request
  fee exactly once with integer picodollar arithmetic. Image and audio are
  excluded only by a request-bound text-only modality proof. Formula structure
  and charge coverage are `READY`/`COMPLETE`; production price and total-spend
  authorities are `OPERATOR_REQUIRED` and `JIT_PENDING`.
- One-call authorization content-addresses the exact rendered request, P17,
  output bound, price policy, modality, P19 bound, operator total-spend ceiling,
  one-shot transport, S5 mapper, S6 integration and claim-store readiness. It
  permits one local dispatch, no automatic retry and no credential value.
- Deterministic preflight has an explicit first-failure order and fails before
  network activity. Consumption re-evaluates the complete preflight authority
  and atomically creates a single-use claim before any future dispatch.
- `OpenRouterClaimStoreReadinessAttestationV1` binds the preflight, mode,
  path-derived store ID, required
  `ATOMIC_CREATE_NEW_TRUSTED_DURABLE_NON_ROLLBACK` semantics, readiness and
  scope-correct evidence. Synthetic evidence uses
  `szorclaimstorefixturev1_...`; a future live attestation requires explicit
  `szorclaimstoregrantv1_...` operator/store evidence.

S7A proves authorization and reuse behavior conditional on that attested store
contract while the claim persists. It does not prove that an ordinary local
directory cannot be deleted or rolled back. The physical trusted durable
non-rollback store and its live evidence are finite S7B JIT facts.

## Synthetic fixture — test authority only

The frozen local cases use one synthetic request fixture that is deliberately
separate from all production authority:

- rendered request ID:
  `szorrenderedliverequestv2_4d1b04a731f98462a8d349611c105fe818fae18c1a1a3de8c2b02dfb835c00a2`;
- body SHA-256:
  `9ba640bf29bf6ad77c2a6dd0b4b038fbe4567aa51146b0e2699ea49a2ee0b8a8`;
- body length: 512 bytes;
- P17 input limit: 4096 tokens;
- component ceilings: prompt USD 1/million tokens, completion USD 2/million
  tokens and request USD 0.000001;
- operator total-spend ceiling and computed worst-case bound:
  4,609,000,000 picodollars.

These are synthetic fixture values only. They are not a production request,
current model-limit fact, operator price grant, operator total-spend grant or
live claim-store grant and may not be promoted to any of those roles.

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

## Frozen case contract and authoritative metrics

The designated persisted experiment evaluated the frozen inventory exactly
once at freeze HEAD `dca2f2d97b1eeba9626ec9490edf722b64681ef5`.

- Case-set ID:
  `szorlivesafetycasesetv1_21ab3255104dbb5fe0ca5e2255a2f4d205c7f2d6364a67588e2c39b69c9eba01`.
- Thresholds ID:
  `szorlivesafetythresholdsv1_ccc445fda16e9022f40ed0a3d133365d823b1cbe0f844803926c8564502ecec9`.
- Total: 73 cases = 20 positive/property cases + 53 adversarial cases.
- Numbered Sections 35–40 requirements covered: 73/73.
- Positive accepted: 20/20.
- Adversarial rejected: 53/53.
- Unexpected results: 0.
- All thresholds pass: true.
- S6 semantic/artifact predecessor surfaces: 8/8 unchanged.
- External activity: 0.

Every zero-hazard metric is 0:

- `unexpected_results`;
- `invalid_fixture_constructions`;
- `guard_code_mismatches`;
- `heuristic_p17_authority_accepted`;
- `byte_to_token_substitutions_accepted`;
- `incomplete_charge_coverage_accepted`;
- `request_fee_omission_to_zero`;
- `hidden_monetary_terms`;
- `cross_request_substitutions_accepted`;
- `authorization_reuse_accepted`;
- `consumption_rollback_accepted`;
- `credential_leakage_findings`;
- `test_fixture_promotions`;
- `external_activity`.

## Regression gates

The post-authoritative gates reproduced the pre-freeze results:

| gate | result |
| --- | --- |
| S7A focused/per-case/structural | 106 passed |
| sealed S6 | 149 passed |
| sealed S5 | 109 passed |
| sealed S3 | 64 passed |
| route controls | 103 passed |
| retained manifest | 25 passed |
| all OpenRouter tests, post-authoritative run | 835 passed, 1 skipped |
| full `tests_dialogues` | 3643 passed, 10 skipped |
| predecessor regression gate | 742/742 passed |
| S6 semantic/artifact predecessor surfaces | 8/8 unchanged |
| diff check | passed |

### Known pre-existing intermittent predecessor failure

An earlier pre-S7 all-OpenRouter gate recorded exactly one failure:
`test_one_shot_offline_acquisition_publishes_complete_derived_log`, with
`1 failed, 728 passed, 1 skipped, 2817 deselected`. Its isolated rerun passed
1/1. This is classified as `KNOWN PRE-EXISTING INTERMITTENT PREDECESSOR
FAILURE`; S7A made no fix. The final pre-freeze all-OpenRouter gate was clean at
835 passed and 1 skipped. The known race did not recur in the post-authoritative
gates.

## Non-authoritative development-check disclosure

Before the freeze-discipline reminder, four non-persisted development checks
were executed:

1. one full in-memory case evaluation produced 73 results, 73 expectation
   matches and 0 unexpected results;
2. the first in-memory builder check reported `SUPPORTED`, all thresholds true,
   73 results and predecessor integrity 8/8, rendering 51,938 bytes with the
   then-current development artifact ID
   `szorlivesafetyartifactv1_8e0d9fb1f77d065a9ccf2222a18df0d519f2e9cc65974c95854a18058b9ac003`;
3. a second in-memory builder check participated in the determinism comparison;
4. a third in-memory builder check completed that comparison, with semantic
   equality, artifact-ID equality and byte identity all true.

No development check persisted an artifact, replay execution or replay lock,
and none accessed credentials or performed provider, model, CED or network
activity. Semantic changes followed those observations, including strengthened
consumption revalidation, explicit claim-store readiness binding and the scoped
S38.12 rollback contract. Therefore the development artifact ID and 51,938-byte
render are stale historical observations and MUST NOT be used as freeze or
authoritative identities. They are retained only as a sequencing disclosure and
are superseded by the designated persisted evidence below.

## Authoritative evidence and replay

The three write-once files now exist:

- `docs/branches/feature-socrates-zero-openrouter-live-safety-closure-v1/artifacts/socrateszero_openrouter_live_safety_closure_v1.json`;
- `docs/branches/feature-socrates-zero-openrouter-live-safety-closure-v1/artifacts/socrateszero_openrouter_live_safety_closure_replay_execution_v1.json`;
- `docs/branches/feature-socrates-zero-openrouter-live-safety-closure-v1/artifacts/socrateszero_openrouter_live_safety_closure_replay_lock_v1.json`.

| evidence | content identity | file SHA-256 | bytes |
| --- | --- | --- | ---: |
| authoritative artifact | `szorlivesafetyartifactv1_237286af63bc509db7fe2cbd4e40a78150d36213ec162a2a745494eeeeed70b3` | `9bdc7f58ca1e29a9ed082a863a6bc4487f9687c564207887b226953cc6f95a01` | 52,053 |
| replay execution | `szorlivesafetyreplayexecutionv1_0292ea7f00e670fdf9c4d6254b4ebeca4d0b1e97744e5a0a7b294254b7f151da` | `3a5cb6cacc85e3c8a842bade1e0ac279929682c4db547cdd16dc9eed22454d2e` | 740 |
| replay lock | `szorlivesafetyreplaylockv1_116f9049f8495ad63276973a4d0e09815ead6435bddb45ccaf319a2d8e964dc6` | `6c66d96527e271efef5dd0ec8de139ebb8f96f44dce79490a783ae69f9b3f675` | 655 |

Replay semantic equality, artifact-ID equality and byte identity are all true.

## Final decision and S7B boundary

- Architecture: `SUPPORTED`.
- P17 proof architecture: `READY`.
- P17 current authority: `JIT_PENDING`.
- Output-token bound: `ESTABLISHED = 256`.
- P18 actual pricing: `NOT_ESTABLISHED`; granularity remains
  `BROAD_PROVIDER_ONLY`.
- Server-enforced prompt/completion/request ceiling coverage: `COMPLETE`.
- P19 formula structure: `READY`.
- P19 applicable charge coverage: `COMPLETE`.
- P19 current authority: `JIT_PENDING`.
- Claim-store-readiness contract: `READY`; physical realization:
  `S7B_JIT_PENDING`.
- One-call authorization: `READY`.
- JIT preflight: `READY`.
- Runtime authority: `NOT_AUTHORIZED`.
- Live OpenRouter: `NOT_EXECUTED`.
- One live shadow call: `AUTHORIZED_PENDING_JIT_PREFLIGHT`.

The exact remaining JIT facts are:

1. one exact first-party model-limit record for the requested model and same
   preflight;
2. explicit operator prompt, completion and request price ceilings;
3. an explicit operator total-spend ceiling;
4. credential-presence attestation without credential material entering any
   scientific identity;
5. one-shot transport-readiness attestation;
6. physical realization of the trusted durable non-rollback claim store plus
   scope-correct live `szorclaimstoregrantv1_...` evidence.

Because the price values are operator-required, the production request ID, body
SHA-256 and byte length remain `JIT_PENDING`. The 512-byte synthetic fixture
above remains test authority only and is not the production request. The next
phase is Phase 8.5D-S7B — JIT Preflight + ONE Live OpenRouter Shadow Call.

## Non-goals

No OpenRouter inference, authenticated request, credential access, current-price
retrieval, provider/model call, CED application, production wiring or push.

# Evidence — OpenRouter live-safety closure v1

S7A reuses retained repository evidence only. It performs no fresh retrieval.

| evidence | role |
| --- | --- |
| S6 authoritative artifact and replay | sealed integration/readiness predecessor |
| retained OpenRouter OpenAPI and routing guide evidence | model-limit and `ProviderPreferences.max_price` audit inputs |
| sealed S6 request modality proof | historical text-only evidence; candidate-v2 proof must bind new bytes |
| S5 mapper identity | future response-mapping dependency |
| S6 integration identity | future causal-integration dependency |
| local claim-store-readiness contract | binds one path-derived store identity and required trusted durable non-rollback semantics; does not prove physical realization |

Any current first-party model-limit value required for P17 remains a future JIT
fact and must be acquired before credential-dependent dispatch in S7B.

Production component prices and the operator total-spend ceiling likewise
require explicit operator grants. A live claim store requires scope-correct
`szorclaimstoregrantv1_...` evidence. The physical
`ATOMIC_CREATE_NEW_TRUSTED_DURABLE_NON_ROLLBACK` store realization is an S7B JIT
fact; a filesystem path or its content ID is not evidence of those properties.

## P17 retained source authority

The evidence audit uses the content-addressed v2r1 source set frozen from
`OpenRouterTeam/docs@4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db`.

Retained manifest:

- path:
  `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/openrouter_official_wire_specification_manifest_v2r1.json`
- ID:
  `szorwirespecmanifestv2r1_a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15`
- SHA-256:
  `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb`

Relevant retained sources:

| source | source ID | SHA-256 | audited fields/semantics |
| --- | --- | --- | --- |
| `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/openapi.yaml` | `szorwiresourcev2r1_61aba8cdf4e3403dbac683bea535de1bfaf96fd3292dfa9549d749a7d918a4fc` | `bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713` | `Model.id`, `canonical_slug`, `context_length`, `per_request_limits.prompt_tokens`, endpoint context semantics and `/model/{author}/{slug}` |
| `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/api-reference-overview.mdx` | `szorwiresourcev2r1_0fb3a6af79da19e7e78463abb9d77d6e92a6d7ddc43317adc16683d997871729` | `8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e` | native-tokenizer `prompt_tokens`, pricing/credit usage and provider request transformations |
| `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/router-metadata.mdx` | `szorwiresourcev2r1_59d512e602085e0d93b955483bf33f81d606125c5cf6ea871cb9044df7202355` | `4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6` | router compression, guardrail, plugin and server-tool pipeline scope |

## Accepted P17 hierarchy

The proof architecture is `READY`; the exact current fact is `JIT_PENDING`.

1. `MAX_PROMPT_TOKENS` from exact-model
   `$.data.per_request_limits.prompt_tokens` is preferred. The retained OpenAPI
   explicitly calls it the maximum prompt tokens per request (lines
   20245-20264).
2. `MODEL_CONTEXT_LIMIT` from exact-model `$.data.context_length` is an accepted
   guarded fallback. The retained OpenAPI calls it the maximum context length in
   tokens (lines 14240-14249) and states that input and output share that window
   (lines 21642-21650). The whole context limit is used; 256 output tokens are
   not subtracted.

Both routes require exact `openai/gpt-4.1-mini` response binding. The retained
sources contain no current exact-model limit value, so test fixtures may exercise
the contract but may never become production authority.

The finite JIT record is one same-preflight official response to
`GET /api/v1/model/openai/gpt-4.1-mini`. It must retain compact extracted facts
plus the raw response digest and length, exact returned model/canonical identity,
alias state, source and schema identities, selected field/kind/value, observation
and preflight identities, and proof-method version. It must then be bound to the
new live request ID, body digest/length, message/modality proof, output bound and
provider policy. Invalid or absent evidence implies zero inference dispatch.

## Scope and rejected alternatives

The model-limit proof bounds primary completion `usage.prompt_tokens`, including
model-visible chat framing and transformed content because those tokens occupy
the model context and billing uses native token counts. It does not bound
independent guardrail, plugin or server-tool calls. The candidate must preserve
plugins absent, tools disabled and text-only modality; any auxiliary billable
class must be separately rejected or bounded.

The following remain rejected:

- `top_provider.context_length`, because the top provider is not necessarily the
  exact endpoint selector;
- endpoint `max_prompt_tokens` or `context_length`, because retained endpoint
  fields do not bind unambiguously to `azure/swedencentral`;
- the `ModelGroup` tokenizer family label, including `GPT`;
- any tokenizer without exact model binding, implementation/version identity,
  vocabulary/data digest, special-token semantics and bounded chat framing;
- bytes, characters, words, heuristics, safety factors, historical usage,
  post-call usage or model memory.

No retained pre-call token-count facility or acceptable exact-tokenizer path was
found. No current limit value is asserted here.

## Implemented local evidence bindings

The local architecture is complete for:

- a source-bound exact-model P17 record and request-bound P17 proof;
- a v2 rendered request containing explicit prompt, completion and request
  price ceilings;
- a request-bound text-only modality proof and established 256-token output cap;
- a complete P19 component tuple and exact integer-picodollar total;
- an operator total-spend ceiling separate from component ceilings;
- one-call authorization, one-shot transport, deterministic preflight and
  consume-before-network semantics;
- an explicit claim-store-readiness attestation bound into authorization,
  preflight and consumption.

Production request identity, current P17 record, all price grants, total-spend
grant and live store grant remain `JIT_PENDING`/`OPERATOR_REQUIRED` and must be
established before credential-dependent dispatch.

## Synthetic fixture separation

The test fixture is identified by:

- request ID:
  `szorrenderedliverequestv2_4d1b04a731f98462a8d349611c105fe818fae18c1a1a3de8c2b02dfb835c00a2`;
- body SHA-256:
  `9ba640bf29bf6ad77c2a6dd0b4b038fbe4567aa51146b0e2699ea49a2ee0b8a8`;
- body length: 512 bytes.

Its 4096-token limit, USD 1/million prompt ceiling, USD 2/million completion
ceiling, USD 0.000001 request ceiling and 4,609,000,000-picodollar total are
synthetic test values only. Synthetic price, total and
`szorclaimstorefixturev1_...` evidence cannot be promoted to live operator
authority.

## Frozen evidence ledger

- Freeze HEAD: `dca2f2d97b1eeba9626ec9490edf722b64681ef5`.
- Decision: `OPENROUTER LIVE-SAFETY CLOSURE v1 SUPPORTED`.

- Case set:
  `szorlivesafetycasesetv1_21ab3255104dbb5fe0ca5e2255a2f4d205c7f2d6364a67588e2c39b69c9eba01`.
- Thresholds:
  `szorlivesafetythresholdsv1_ccc445fda16e9022f40ed0a3d133365d823b1cbe0f844803926c8564502ecec9`.
- Cases: 73 = 20 positive/property + 53 adversarial.
- Pre- and post-authoritative gates: S7A 106; S6 149; S5 109; S3 64;
  route 103; manifest 25; final
  all OpenRouter 835 passed/1 skipped; full `tests_dialogues` 3643 passed/10 skipped;
  predecessor 742/742; S6 semantic/artifact surfaces 8/8 unchanged; diff check
  passed.

An earlier pre-S7 all-OpenRouter run is recorded as `KNOWN PRE-EXISTING
INTERMITTENT PREDECESSOR FAILURE`: exactly
`test_one_shot_offline_acquisition_publishes_complete_derived_log` failed, with
1 failed/728 passed/1 skipped/2817 deselected; its isolated rerun passed 1/1.
No S7A fix was made. The final pre-freeze gate was clean and the race did not
recur post-authoritatively.

One full case pass and three in-memory builder checks were non-authoritative and
non-persisted. The stale development artifact ID
`szorlivesafetyartifactv1_8e0d9fb1f77d065a9ccf2222a18df0d519f2e9cc65974c95854a18058b9ac003`
and its 51,938-byte render predate later semantic hardening and MUST NOT be used
as authoritative evidence. No development-check output was persisted.

## Authoritative evidence

| evidence | content identity | file SHA-256 | bytes |
| --- | --- | --- | ---: |
| artifact | `szorlivesafetyartifactv1_237286af63bc509db7fe2cbd4e40a78150d36213ec162a2a745494eeeeed70b3` | `9bdc7f58ca1e29a9ed082a863a6bc4487f9687c564207887b226953cc6f95a01` | 52,053 |
| replay execution | `szorlivesafetyreplayexecutionv1_0292ea7f00e670fdf9c4d6254b4ebeca4d0b1e97744e5a0a7b294254b7f151da` | `3a5cb6cacc85e3c8a842bade1e0ac279929682c4db547cdd16dc9eed22454d2e` | 740 |
| replay lock | `szorlivesafetyreplaylockv1_116f9049f8495ad63276973a4d0e09815ead6435bddb45ccaf319a2d8e964dc6` | `6c66d96527e271efef5dd0ec8de139ebb8f96f44dce79490a783ae69f9b3f675` | 655 |

The artifact contains 73 cases, 20 positive accepted, 53 adversarial rejected,
0 unexpected results, all thresholds passing, every zero-hazard metric 0,
external activity 0 and S6 surfaces 8/8 unchanged. Replay semantic equality,
artifact-ID equality and byte identity are true.

## Remaining evidence for S7B

The supported architecture leaves exactly these finite JIT facts:

1. exact first-party model-limit record;
2. explicit operator prompt, completion and request ceilings;
3. explicit operator total-spend ceiling;
4. credential presence;
5. transport readiness;
6. physical trusted durable non-rollback claim store and live
   `szorclaimstoregrantv1_...` evidence.

Production request ID/body digest/length remain `JIT_PENDING` because the
production price values are operator-required. The synthetic identity above is
not production evidence. Runtime remains `NOT_AUTHORIZED`, live OpenRouter
remains `NOT_EXECUTED`, and the one call is
`AUTHORIZED_PENDING_JIT_PREFLIGHT`.

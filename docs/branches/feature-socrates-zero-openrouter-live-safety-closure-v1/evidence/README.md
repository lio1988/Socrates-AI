# Evidence — OpenRouter live-safety closure v1

S7A reuses retained repository evidence only. It performs no fresh retrieval.

| evidence | role |
| --- | --- |
| S6 authoritative artifact and replay | sealed integration/readiness predecessor |
| retained OpenRouter OpenAPI and routing guide evidence | model-limit and `ProviderPreferences.max_price` audit inputs |
| sealed S6 request modality proof | historical text-only evidence; candidate-v2 proof must bind new bytes |
| S5 mapper identity | future response-mapping dependency |
| S6 integration identity | future causal-integration dependency |

Any current first-party model-limit value required for P17 remains a future JIT
fact and must be acquired before credential-dependent dispatch in S7B.

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

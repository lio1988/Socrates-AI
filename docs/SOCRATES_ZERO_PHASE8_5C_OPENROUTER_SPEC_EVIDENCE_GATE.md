# SocratesZero Phase 8.5C — OpenRouter Official Specification Evidence Gate

Date: `2026-08-26`

Branch: `feature/socrates-zero-openrouter-spec-evidence-gate-v0`

Parent checkpoint: `040671700760b1fe2d3d9cd41d533ab0bbae085f`

## 1. Executive verdict

**Decision: `OPENROUTER ROUTE-CONTROL MILESTONE ONLY EARNED`.**

Official OpenRouter specifications now provide strong, falsifiable request-side
controls for exact-model intent, provider allow-listing, provider ordering,
provider-fallback disablement, parameter support, router-metadata opt-in and
response-cache disablement. They also define useful response-side evidence for
the requested model, selected provider/model, routing strategy, successful
attempt ordinal and optional pipeline/attempt detail.

They do **not** establish the complete five-blocker path required for a full
adapter v1 experiment. In particular:

- the selected full endpoint slug can be expressed in a request, but the primary
  response does not attest that full slug or an endpoint identifier;
- local, HTTP, router-internal and upstream-provider retries remain distinct from
  documented provider/model fallback controls;
- the v0 UTF-8 byte count remains an invalid/unproved provider-token bound;
- a credible coarse context-ceiling bound exists, but it requires a separate
  exact-endpoint-bound semantic component and fresh mutable metadata;
- complete pricing for the selected exact endpoint is not established;
- `provider.max_price` is a unit-price eligibility filter, not a total-request
  monetary ceiling;
- the formal success schema does not require complete usage/cost evidence; and
- one primary response is not specification-guaranteed to contain exact-endpoint,
  routing, usage and cost evidence together.

Therefore the bridge between official route specifications and offline adapter
controls is worth building separately. It must remain network-inert and
canned-only. No live call, full authorization aggregate, replay lock, CED
application or production authority is earned.

Architecture classification:

`ADAPTER MECHANICS SOUND, SPEC EVIDENCE MISSING`

## 2. Sealed adapter-controls result

The predecessor remains permanently sealed as:

`OPENROUTER ACQUISITION ADAPTER HARDENING FALSIFIED`

| Item | Sealed value |
|---|---|
| Branch | `feature/socrates-zero-provider-adapter-controls-v0` |
| HEAD | `040671700760b1fe2d3d9cd41d533ab0bbae085f` |
| Artifact ID | `szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f` |
| Artifact SHA-256 | `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083` |
| Status | `FALSIFIED` |
| First actual blocker | `P08_ROUTE_POLICY` |
| Authoritative canned transport invocations | `0` |
| Frozen required invocations | `34` |
| Replay | `NOT PERFORMED` |
| Replay lock | `NOT CREATED` |

This gate did not regenerate, edit, reinterpret or replay the artifact.

The required historical lineage remained byte-identical at the gate checkpoint:

| Frozen evidence | Expected SHA-256 |
|---|---|
| Phase 5 | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Phase 7 primary | `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca` |
| Phase 7 BestOfN | `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637` |
| Phase 8 falsified v1 | `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea` |
| Phase 8 v2 | `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc` |
| Phase 8 v2 replay lock | `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224` |
| Acquisition Contract artifact | `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255` |
| Acquisition replay execution | `7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b` |
| Acquisition replay lock | `335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c` |
| OpenRouter controls v0 | `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083` |

## 3. What the predecessor proved

The v0 experiment proved offline mechanics, not provider behavior:

- deterministic canonical UTF-8 application-body rendering;
- semantic-only request construction and sibling byte equality;
- a one-shot canned adapter seam;
- canned timeout and worker cleanup behavior;
- raw-first immutable reference receipts;
- explicit local/adapter retry and fallback intent;
- zero production/core mutation; and
- zero credential, network, provider, model, tool or CED activity.

The exact prepared body remained `321` bytes with SHA-256
`35462326a2590187b03219ad68a85b6203b3ca5364994f87dff18ec64556f5f5`.
Those facts remain valid only within the sealed v0 scope.

## 4. What falsified the predecessor

The v0 renderer intentionally contained no `provider` route object and no
official-specification provenance. Its route policy remained
`upstream_route_state=NOT_ESTABLISHED`; the evaluator therefore stopped at
`P08_ROUTE_POLICY` before any canned transport response.

The later guards were independently known to be unresolved:

| Guard | Sealed v0 truth |
|---|---|
| `P08_ROUTE_POLICY` | No upstream provider/endpoint control was rendered or established. |
| `P09_FALLBACK_INTENT` | Local/adapter intent was frozen; OpenRouter provider/model fallback intent and attestation were absent. |
| `P17_INPUT_TOKEN_BOUND` | `FULL_REQUEST_UTF8_BYTE_COUNT_V0` was payload-only and not provider-authoritative. |
| `P18_PRICING_RECORD` | Pricing and official provenance were `NOT_ESTABLISHED`. |
| `P19_COST_BOUND` | No complete price inputs or authoritative input bound existed. |

Permanent interpretation:

- Core adapter mechanics: `PARTIALLY SUPPORTED`
- Candidate control completeness: `FALSIFIED`
- Live pilot readiness: `NOT EARNED`

## 5. Official source methodology

Only public primary sources were used: official OpenRouter documentation,
OpenRouter's public OpenAPI schema and model/provider pages, plus official OpenAI
model/tokenizer documentation and tagged `tiktoken` source where directly
necessary.

No search-result snippet, third-party article, SDK wrapper or model-generated
claim is treated as evidence. Dynamic HTML-body hashes are retrieval receipts,
not semantic truth; each relied-upon fact has a separate normalized semantic
digest in the manifest.

The immutable gate record is:

- Manifest:
  [`openrouter_official_specification_evidence_v0.json`](branches/feature-socrates-zero-openrouter-spec-evidence-gate-v0/evidence/openrouter_official_specification_evidence_v0.json)
- Manifest ID:
  `szorspecmanifestv0_6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`
- Semantic SHA-256:
  `6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`
- Accepted content-addressed source records: `16`
- Normalized fact records: `13`
- Direct unauthenticated public-document retrievals: `127`
- Additional in-app public-page inspections: `1`
- Authenticated API calls / credential accesses / provider inference calls:
  `0 / 0 / 0`

The larger retrieval count includes deliberate repeat/digest checks. Only the
16 manifest records are accepted evidence sources. No full documentation page
is stored in the repository.

## 6. Stable protocol/schema evidence

The relatively stable evidence class is request/response protocol shape. It is
still versioned and must be rechecked on digest drift.

| Evidence | Official source | Fact record | Scope |
|---|---|---|---|
| Provider route controls | [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection) | `ORSPEC-F01` | `only`, `order`, `allow_fallbacks`, `require_parameters` |
| Model fallback | [Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks) | `ORSPEC-F03` | `models` array is distinct from provider fallback |
| Router response metadata | [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata) | `ORSPEC-F04` | opt-in, strategy, attempts, endpoints, pipeline |
| Response-cache control | [Response Caching](https://openrouter.ai/docs/guides/features/response-caching) | `ORSPEC-F05` | cache disablement and hit behavior |
| Chat/usage schema | [Chat API reference](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request) | `ORSPEC-F12` | usage/cost fields and optionality |

This evidence supports an offline semantic version. It does not constitute live
empirical server enforcement.

## 7. Mutable model/provider evidence

The candidate remains `openai/gpt-4.1-mini`; it was not silently replaced.
At retrieval time, the official model/provider page still listed it. The
accepted model metadata records a `1,047,576` shared context window and a
`32,768` maximum output capability (`ORSPEC-F06`).

The mutable provider inventory exposed distinct Azure, Azure regional, and
OpenAI entries. It also exposed standard and batch records sharing the base
`openai` slug. No timeless availability claim follows from this snapshot.

The retained endpoint metadata showed `max_tokens` support for the current
standard OpenAI entry. It did not establish a complete, exact supported-parameter
set for `azure/swedencentral` covering every frozen request field
(`temperature`, `max_tokens`, `stream`, empty `tools`, and `response_format`).
That exact endpoint-specific set is therefore `NOT ESTABLISHED` and must be
frozen in the route-only milestone. `require_parameters:true` is an enforcement
control, not a substitute for the offline compatibility record.

Every model/provider fact has:

- a UTC retrieval time;
- a source-body digest;
- a minimal semantic digest;
- `SNAPSHOT_ONLY` validity; and
- `REVALIDATE_BEFORE_AUTHORIZATION` policy.

A listed model may still be absent, ineligible, repriced or unavailable at a
future pilot. That future one-shot pilot would fail closed with no retry and no
alternate model.

## 8. P08 route-policy audit

Official support: `PARTIAL — STRONG REQUEST CONTROL, INCOMPLETE EXACT-ENDPOINT ATTESTATION`.

| Field | Official type/default | Documented meaning | Gate classification |
|---|---|---|---|
| `model` | string; required by the experiment | One requested model. | Exact request intent when fixed to `openai/gpt-4.1-mini`. |
| `models` | array or absent | Ordered alternate-model fallback list. | Must be absent; not an empty implicit fallback policy. |
| `provider.only` | `string[]` or null/absent | Restricts eligible provider slugs; account settings may narrow further; no eligible endpoint fails. | Hard allow-list. |
| `provider.order` | `string[]` or null/absent | Orders preferred provider endpoints. | Preference unless combined with `only` and fallback disablement. |
| `provider.allow_fallbacks` | boolean or null; documented default `true` | `false` prevents backup-provider fallback after the primary/custom selection. | Hard request-side provider-fallback restriction. |
| `provider.require_parameters` | boolean or null; documented default `false` | Removes endpoints that do not support every supplied parameter. | Hard eligibility filter. |
| `provider.max_price` | object or absent | Filters endpoint eligibility by unit prices; unavailable/excess pricing is ineligible. | Hard eligibility filter, not total-request cost cap. |
| `stream` | boolean | `false` requests one non-streaming result. | Already present in v0 body. |
| `tools` | array | Empty array expresses no requested tools. | Already present and guarded in v0 body. |

There is an unresolved official representation conflict for `max_price`: the
routing-guide examples use JSON numbers while the current OpenAPI child
properties are typed as strings. The route-only milestone may model and test
the conflict explicitly, but it may not choose a type by intuition or treat the
field as trusted pricing.

Repository status: the v0 body shape explicitly excludes `provider`,
`models`, router-metadata headers and response-cache headers. The repository
therefore does not currently render or validate these official controls.

Evidence-layer classification:

- Request intent proven by static specifications: `YES`
- Conceptual server restriction specified: `YES`
- Primary-response provider/model/attempt attestation possible: `YES`
- Primary-response exact endpoint-slug attestation possible: `NO`
- Empirical server enforcement observed: `NO`

P08 verdict: `PARTIAL; OFFLINE ROUTE-CONTROL MILESTONE EARNED`.

## 9. Exact provider-endpoint audit

The base `openai` slug is not endpoint-unique in the retained inventory: it is
shared by standard and batch entries. It must not be frozen as though it named
one endpoint variant.

The current inventory also exposes `azure/swedencentral`. Official routing
documentation states that a full suffixed slug selects a specific variant or
region. Therefore the gate returns:

`EXACT PROVIDER ENDPOINT AVAILABLE`

Candidate for the route-only milestone:

`azure/swedencentral`

This statement is deliberately narrow:

- available for request-side selector intent at the retrieval checkpoint;
- mutable and subject to immediate revalidation;
- not proof of pilot-time availability;
- not proof that the server enforced it; and
- not response-side attestation, because `openrouter_metadata` does not expose
  the full selected endpoint slug or an endpoint ID.

Complete endpoint-specific pricing for `azure/swedencentral` is
`NOT ESTABLISHED`. The exact-endpoint request selector therefore closes neither
P18 nor P19.

## 10. P09 fallback audit

Fallback and retry are not one Boolean.

| Layer | Static control/evidence | Status |
|---|---|---|
| Local application retry | Existing frozen local policy | `0`; separate from OpenRouter. |
| Adapter retry | Existing frozen adapter policy | `0`; separate from OpenRouter. |
| HTTP/library retry | No SDK in v0 canned seam; live transport not authorized | Must be independently fixed and attested later. |
| Provider-endpoint fallback | `provider.allow_fallbacks:false` plus one `only`/`order` slug | Strong request intent. |
| Model fallback | Exact `model`; `models` absent | Strong request intent. |
| Router attempt/fallback | `openrouter_metadata.attempt`; optional `attempts[]` | `attempt > 1` reveals earlier failed attempts; details are optional. |
| Upstream-provider internal retry/failover | Not exposed by audited schema | `NOT ATTESTABLE`. |

A defensible future primary-response receipt would require `attempt == 1`, the
exact response model, the expected direct routing strategy, one selected
provider/model candidate, no disallowed pipeline stage and no cache hit.

That still would not prove the selected full endpoint slug or absence of hidden
upstream retry/failover. The experiment therefore must not publish an
unqualified `NO FALLBACK` claim.

P09 verdict: `PARTIAL; REQUEST INTENT AND ROUTER-ATTEMPT CHECKS POSSIBLE, COMPLETE NO-FALLBACK ATTESTATION NOT ESTABLISHED`.

## 11. Router-metadata audit

The documented opt-in header is:

`X-OpenRouter-Metadata: enabled`

The primary non-streaming response can include `openrouter_metadata` with:

- `requested`;
- `strategy`;
- `region`;
- `summary`;
- one-based `attempt`;
- `is_byok`;
- endpoint provider/model/selection summaries;
- optional `attempts`; and
- optional `pipeline` stages.

Pipeline evidence can reveal context compression, guardrails, server tools,
response healing and other transformations. The parser must be
forward-compatible: preserve raw bytes, validate known mandatory fields, and
ignore/preserve unknown additive fields or stages without treating them as
positive proof.

Limitations:

- full endpoint slug/ID is absent;
- `attempts` and `pipeline` are optional;
- cache hits omit metadata;
- authentication, rate-limit, edge-validation and some server errors can omit
  metadata; and
- an error's missing metadata cannot be repaired through a retry or follow-up
  generation lookup in the first pilot.

Future policy: required routing metadata absent means terminal pilot failure.

## 12. Cache/metadata limitations

The official response-cache control is:

`X-OpenRouter-Cache: false`

If neither this feature nor a preset enables caching, response caching is off;
the explicit header additionally disables it even when a preset would enable
it. `X-OpenRouter-Cache-Status` can report `HIT` or `MISS`. A cache hit omits
router metadata and reports no provider request token consumption.

Future route-control policy:

1. Render `X-OpenRouter-Cache:false` as a semantic non-secret header.
2. Require router metadata in the primary response.
3. Reject `HIT` or missing required metadata.
4. Do not retry.
5. Do not add prompt nonces or experimental entropy.

Provider prompt caching is separate and may be automatic. The audited sources
did not establish one global switch disabling all provider-managed prompt
caching for the candidate. Cache-read billing must therefore remain a pricing
dimension unless an exact endpoint-specific source proves it inapplicable.

## 13. P17 token-bound audit

The v0 method remains invalid:

`FULL_REQUEST_UTF8_BYTE_COUNT_V0 != AUTHORITATIVE PROVIDER TOKEN BOUND`

Raw bytes are neither an exact token count nor a formally proved upper bound for
every allowed Unicode/message-framing case. Official OpenAI guidance notes that
structured request token counts include formatting not represented by simply
tokenizing the visible fields.

Four candidate approaches were audited:

| Approach | Verdict |
|---|---|
| Exact offline tokenizer | `PARTIAL`; useful diagnostics, not exact OpenRouter Chat framing. |
| Formally conservative bound | `CREDIBLE V1 PATH` via exact endpoint context ceiling. |
| `provider.max_price` without token count | `INSUFFICIENT`; it caps unit rates, not token quantity. |
| Keep v0 byte count | `REJECTED`. |

The official models schema defines the endpoint context length as a shared
input/output maximum. For a successfully accepted request, a freshly frozen
exact-endpoint ceiling therefore covers provider-visible framing and Unicode.
The proposed semantic method is:

`EXACT_ENDPOINT_CONTEXT_CEILING_V0`

For the current candidate metadata, the coarse successful-request prompt bound
is no greater than `1,047,576` tokens. This is not implemented, and it depends
on fresh endpoint metadata. It also does not establish whether an over-context
rejection could incur a charge.

P17 verdict:

`V0 UNRESOLVED; CREDIBLE SPEC-BACKED V1 CLOSURE PATH EXISTS`

It remains explicitly deferred from the route-only milestone.

## 14. Tokenizer options

No dependency was added.

If a later milestone needs a tighter deterministic diagnostic count, the
preferred audited basis is:

- package: official `tiktoken`;
- version: exact `0.14.0`;
- mapping: `gpt-4.1-* -> o200k_base`;
- model binding: explicit OpenAI snapshot compatibility, never implicit use of
  the OpenRouter slug as a tokenizer key;
- BPE data: preseed/vendor exact bytes with expected SHA-256
  `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`;
- dependency policy: exact wheel hashes and no fallback tokenizer;
- isolation: socket/DNS tripwire because the official loader can fetch on cache
  miss;
- failure: missing/mismatched data fails closed, never downloads; and
- corpus: ASCII, multibyte scripts, emoji/ZWJ, combining marks, control
  characters, very long content and exact structured fixtures.

Even then, the result must be labeled text/tokenizer diagnostics, not exact
OpenRouter Chat request accounting, unless a primary framing specification
appears.

## 15. P18 pricing-record audit

Official OpenRouter metadata defines more billing dimensions than v0 modeled:

- prompt/input;
- completion/output;
- request;
- image;
- audio in the current schema;
- web search;
- internal reasoning;
- cache read;
- cache write; and
- conditional pricing overrides.

An official mutable snapshot was obtainable for the standard OpenAI endpoint,
including its upstream snapshot and prompt/completion/cache-read rates. That
record does **not** bind the selected exact `azure/swedencentral` endpoint.
Complete `azure/swedencentral` pricing was not established, and an absent
pricing property cannot be interpreted as zero because the official models
documentation distinguishes explicit zero from absence.

Required future pricing record fields:

- exact OpenRouter model slug;
- exact endpoint slug and upstream model snapshot;
- currency and exact unit per dimension;
- all prices or primary proof of inapplicability;
- conditional overrides;
- official locator, UTC retrieval time and source digest;
- normalized semantic price digest;
- adapter/route manifest binding;
- revalidation result; and
- terminal behavior for absent, changed, expired or ambiguous values.

P18 verdict:

`PARTIAL; A MUTABLE SNAPSHOT MECHANISM IS POSSIBLE, BUT COMPLETE PRICING FOR THE SELECTED EXACT ENDPOINT IS NOT ESTABLISHED`

## 16. Pricing expiry/revalidation

The policy is:

`REVALIDATE_BEFORE_AUTHORIZATION`

No arbitrary multi-day validity window is granted. The stored evidence is a
historical decision snapshot, not a future authorization token.

At the exact future authorization checkpoint, a verifier must obtain a new
public official snapshot, compare source and semantic digests, verify the exact
model/endpoint and every billing dimension, and create a new immutable record.
Any disappearance, type ambiguity, dimension addition, price change, endpoint
change or unsupported source drift fails closed and returns to architecture
review.

## 17. P19 pre-dispatch cost-bound audit

A pre-dispatch maximum requires all of the following:

1. a provider-authoritative input upper bound such as a revalidated exact
   endpoint context ceiling;
2. a frozen provider-enforced output cap;
3. exact model/endpoint prices or hard unit-price ceilings for every applicable
   billing dimension;
4. proof that omitted dimensions are inapplicable, not merely absent;
5. exact decimal/rational arithmetic and conservative integer rounding;
6. exact currency; and
7. fail-closed behavior for overflow, ambiguity and source drift.

`provider.max_price` is a hard provider-eligibility filter where documented. It
can help cap prompt/completion/request/image/audio unit rates. It does not cap
total tokens or total request cost, and the audited schema does not give it
fields for cache, internal reasoning or web-search pricing. A routing-guide vs
OpenAPI JSON-type conflict also remains unresolved.

P19 verdict:

`NOT ESTABLISHED`

The context-ceiling idea improves P17 but cannot supply missing exact endpoint
prices, applicability proofs or every billing dimension.

## 18. Post-response usage/cost audit

Official usage-accounting prose describes primary-response fields for:

- prompt tokens;
- completion tokens;
- total tokens;
- reasoning-token detail where relevant;
- cached-token detail where relevant;
- charged `cost`;
- optional upstream inference cost; and
- response/generation identity.

However, the formal ChatResult schema does not require `usage`, and `cost` and
`cost_details` can be null. Thus the experiment cannot claim that complete
one-call billing evidence is guaranteed.

Future fail-closed policy:

- require all fields frozen by the pilot contract;
- require internally consistent token totals;
- retain raw response bytes and digest before parsing;
- keep charged actual cost distinct from the pre-dispatch maximum;
- reject missing/null/ill-typed mandatory fields; and
- issue no generation-stats follow-up call.

Post-response actual cost is evidence after dispatch. It never retroactively
creates a safe pre-dispatch ceiling.

## 19. One-call attestation contract

A future first pilot would need one logical dispatch and no second HTTP request.
The proposed response receipt would bind:

| Evidence | Mandatory future condition |
|---|---|
| Request model | Exact `openai/gpt-4.1-mini`; no `models` array. |
| Requested endpoint | Exact `azure/swedencentral` in one-element `only` and `order`. |
| Route controls | `allow_fallbacks:false`, `require_parameters:true`, explicit reviewed max-price representation. |
| Mode | `stream:false`, no tools, frozen output cap. |
| Headers | Router metadata enabled; response cache disabled. |
| Actual model | Exact equality with request. |
| Routing | Expected strategy, `attempt == 1`, expected selected provider/model. |
| Exact endpoint | Full selected slug or endpoint ID must be attested; current schema cannot do this. |
| Pipeline | No disallowed compression, server tool, plugin, healing or guardrail transformation. |
| Cache | Explicit non-hit evidence and required router metadata. |
| Usage/cost | Complete required token and charged-cost fields in the primary response. |
| Completion | Frozen finish reason and no tool calls. |
| Raw evidence | Bounded raw envelope retained first with byte length and SHA-256. |

Official specifications make most request intent and partial response evidence
possible. They do not make the complete contract specification-guaranteed
because exact endpoint slug and complete cost evidence can be absent.

One-call contract verdict: `PARTIAL; NOT READY FOR LIVE AUTHORIZATION`.

## 20. OpenRouter specification-manifest design

The branch contains `OpenRouterOfficialSpecificationEvidenceV0`, a
content-addressed decision manifest. Every fact record includes:

- evidence ID and official source IDs;
- official locator, title and relevant sections;
- UTC retrieval time;
- source-body digest and digest scope;
- minimal normalized fact and its exact UTF-8 SHA-256;
- scope and limitation;
- stable/mutable classification;
- revalidation and expiration policy; and
- downstream controls.

Canonicalization excludes only `manifest_id` and
`manifest_semantic_sha256`, then encodes UTF-8 JSON with recursively sorted keys,
compact separators and unescaped Unicode. Its digest is the manifest payload
identity.

The manifest explicitly says:

- `authorization_effect = NONE`;
- decision-gate only;
- route controls v1 is not implemented;
- candidate exact endpoint is snapshot-only;
- P17–P19 remain outside the route-only milestone; and
- live pilot readiness is not earned.

Manifest earned: `YES`, as a historical specification-evidence record.

Authorization manifest earned: `NO`.

## 21. External-spec drift policy

The default on unverified drift is:

`FAIL CLOSED`

| Drift event | Required behavior |
|---|---|
| Protocol/schema digest changes | Stop; semantically diff; version the adapter/manifest if relevant. |
| Model page changes | Treat availability, limits, parameters and endpoints as unknown until revalidated. |
| Endpoint slug disappears/changes | Reject authorization; no base-slug substitution. |
| Price changes or dimension appears | Reject the price/cost record; recompute under a new immutable record. |
| Official document disappears | Mark affected controls `NOT VERIFIED`; do not rely on cached prose as current authorization. |
| Metadata field becomes optional/absent | Fail the future one-call receipt; do not follow up. |
| Unknown additive metadata | Preserve/ignore safely; never treat it as proof. |

Source-body drift can be caused by dynamic page material. The semantic record
still requires review; a coincidentally unchanged extracted fact does not allow
automatic future authorization.

## 22. Alternative-provider comparison

The Phase 8.5B audit remains the applicable high-level comparison.

- **Direct provider adapter:** removes OpenRouter's multi-provider routing layer
  and can strengthen endpoint identity. The repository's direct Anthropic path
  still had SDK/default retry, actual-model validation, raw receipt, cost and
  transport-boundary gaps. No new primary audit here proves that it closes
  P17–P19 with less work.
- **NVIDIA NIM:** retained actual-model, retry, cancellation, raw usage/cost and
  endpoint-boundary gaps in the earlier audit. It does not currently dominate
  the route-only experiment.
- **Local runtime:** removes remote credentials/routing and remote inference
  prices, but introduces exact local model/tokenizer binding, runtime/hardware
  determinism, resource accounting, availability and installation burden.
- **Defer:** minimizes immediate operational risk but produces no new evidence
  for P08/P09 and no reusable canned routing receipts.

No alternative is shown by current primary evidence to resolve the actual five
blockers with less uncertainty. Switching solely because OpenRouter needs a
specification layer is not justified.

Alternative provider verdict: `DO NOT SWITCH AT THIS GATE`.

## 23. Decision matrix

For blocker/identity/evidence/cleanliness/reproducibility/usefulness/reversibility
rows, higher means more capability. For risk, size and cost rows, higher means
more burden. These are qualitative classes, not a weighted score.

| Dimension | A. OpenRouter manifest + adapter v1 | B. Route/metadata only | C. Direct provider | D. Local runtime | E. Defer |
|---|---|---|---|---|---|
| Ability to close P08 | HIGH | HIGH | VERY HIGH | VERY HIGH | LOW |
| Ability to close P09 | HIGH | HIGH | HIGH | VERY HIGH | LOW |
| Ability to close P17 | HIGH | LOW | MEDIUM | MEDIUM | LOW |
| Ability to close P18 | MEDIUM | LOW | MEDIUM | VERY HIGH | LOW |
| Ability to close P19 | LOW | LOW | MEDIUM | HIGH | LOW |
| Exact identity evidence | MEDIUM | MEDIUM | HIGH | MEDIUM | LOW |
| One-call evidence completeness | MEDIUM | MEDIUM | MEDIUM | HIGH | LOW |
| Credential/network risk | HIGH | LOW | VERY HIGH | LOW | LOW |
| Implementation size | VERY HIGH | MEDIUM | HIGH | VERY HIGH | LOW |
| Scientific cleanliness | MEDIUM | VERY HIGH | MEDIUM | MEDIUM | HIGH |
| Reproducibility | MEDIUM | VERY HIGH | MEDIUM | MEDIUM | HIGH |
| Cost burden | MEDIUM | LOW | MEDIUM | MEDIUM | LOW |
| Future shadow usefulness | HIGH | HIGH | HIGH | MEDIUM | LOW |
| Future counterfactual usefulness | HIGH | HIGH | HIGH | HIGH | LOW |
| Reversibility | HIGH | VERY HIGH | HIGH | MEDIUM | VERY HIGH |

Path A is not earned because P18/P19 and complete one-call endpoint/cost evidence
remain unresolved. Path B isolates the official route/metadata knowledge without
pretending to authorize a provider call. Paths C and D expand scope without a
demonstrated blocker advantage. Path E is safer operationally but discards a
useful, low-risk offline milestone.

## 24. Exactly one decision

`OPENROUTER ROUTE-CONTROL MILESTONE ONLY EARNED`

This is the sole decision. It grants no full adapter v1, pilot, aggregate,
replay, credential, network, provider, model, CED or production authority.

## 25. Exact next branch and falsifiable hypothesis

Next branch:

`feature/socrates-zero-openrouter-route-controls-v1`

Single hypothesis:

> An additive, network-inert v1 renderer and evidence parser can encode and
> falsify the current official exact-model, exact-endpoint-selector,
> provider/model-fallback, router-metadata and response-cache intent without
> claiming exact endpoint enforcement, closing P17–P19 or invoking transport.

New semantic components permitted on that branch:

- versioned route policy v1;
- versioned semantic-header policy v1;
- canonical body/header renderer v1;
- specification-manifest binding;
- canned router-metadata envelope and raw-first receipt;
- forward-compatible metadata parser;
- orthogonal/precedence cases and frozen aggregate/replay protocol; and
- explicit unresolved states for exact-endpoint response attestation and
  P17–P19.

Pre-result freeze requirements:

- exact official source/semantic digests;
- exact candidate model and `azure/swedencentral` selector snapshot;
- documented handling of the `max_price` type conflict;
- one-element `only` and `order`, `allow_fallbacks:false`,
  `require_parameters:true`, exact model and absent `models`;
- metadata-enabled/cache-disabled semantic headers;
- fail-closed response rules;
- zero-transport boundary tripwire;
- complete case/threshold/path inventory; and
- no mutation of v0 or any frozen component.

Success criteria:

- deterministic canonical request/body/header bytes and sibling equality;
- every route/fallback/cache/metadata field exact in positive canned fixtures;
- wrong endpoint/model/provider, missing metadata, `attempt != 1`, cache hit,
  forbidden pipeline stage, unknown source drift and malformed values fail at
  their frozen guards;
- unknown additive metadata is handled forward-compatibly without becoming
  proof;
- exact endpoint response attestation remains explicitly `NOT ESTABLISHED`;
- P17, P18 and P19 remain explicitly deferred;
- zero credentials, network, provider, model, tool and CED activity; and
- zero production/core/sealed-artifact mutation.

Falsification criteria:

- the official fields cannot be represented deterministically;
- the schema conflict is resolved by guesswork;
- a disallowed route/fallback/cache/metadata probe passes;
- missing metadata is accepted or triggers a retry/follow-up;
- base `openai` is treated as one exact endpoint;
- request intent is labeled empirical enforcement;
- P17–P19 or live readiness is claimed closed;
- any transport/credential/provider/model/CED activity occurs; or
- any frozen component or sealed artifact changes.

Live pilot readiness: `NOT EARNED`.

Experience Store, Learned Value, Learned Policy and RL: `BLOCKED`.

Production authority: `NONE`.

Verification gates at completion:

| Gate | Exact result |
|---|---|
| Phase 5 artifact | `3 passed` |
| Phase 7 primary artifact | `4 passed` |
| Phase 7 BestOfN artifact | `3 passed` |
| Phase 8 v1 predecessor + core blob lock | `5 passed` |
| Phase 8 v2 artifact/replay | `30 passed` |
| Acquisition Contract artifact/replay/boundaries | `239 passed, 8 skipped` |
| Sealed OpenRouter adapter-controls | `242 passed, 1 skipped` |
| Production OpenRouter, fake/canned only | `12 passed, 1 deliberately deselected` |
| Evidence fact/manifest digest verification | `PASS` |
| Total pytest executions | `538 passed, 9 skipped, 1 deselected, 0 failed` |

The skipped cases are platform/filesystem capability cases. The deliberately
deselected production test removes the real `OPENROUTER_API_KEY` environment
name; excluding it preserved this gate's stricter zero-credential-access rule.
All executed provider tests used explicit fake mappings, fake coroutines or a
fake session, and all acquisition tests remained canned-only.

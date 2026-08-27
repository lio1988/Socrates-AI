# SocratesZero — OpenRouter Pre-Live Integration v1

Phase 8.5D-S6. Branch `feature/socrates-zero-openrouter-prelive-integration-v1`,
from `feature/socrates-zero-openrouter-raw-wire-mapping-v2` at exactly
`1be95cfdecd9628cdf2d1ea6abdcf66ba1aa88a6`.

No live call was made in this phase.

## Result — layered

| layer | status |
| --- | --- |
| Integration pipeline | **SUPPORTED** |
| Causal request→response binding | **ESTABLISHED** |
| Offline shadow evidence | **AUTHORIZED** |
| Runtime authority | **NOT AUTHORIZED** |
| P17 input token bound | **NOT_ESTABLISHED** |
| Output token bound | **ESTABLISHED** (256) |
| P18 actual endpoint pricing | **NOT_ESTABLISHED** |
| Pricing endpoint granularity | **BROAD_PROVIDER_ONLY** |
| Trusted unit-price ceiling | **ESTABLISHED** |
| P19 formula structure | **READY** |
| P19 applicable charge coverage | **INCOMPLETE** |
| P19 worst-case cost authority | **NOT_ESTABLISHED** |
| **One live shadow call** | **NOT_AUTHORIZED** |

The two price rows are separate authorities and are never merged. A ceiling says
*no more than*; a pricing record says *this much*. Only the ceiling is
established, and it is enough to bound cost but not to predict it.

The frozen v3 authoritative aggregate returned **SUPPORTED**. Its artifact is
`szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779`
with SHA-256
`8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d`.
The earlier run at `0ff79c9` remains superseded historical evidence and is not
the result reported here.

The budget rows above are audit conclusions, not run outputs, and remain
independent of the aggregate's hypothesis result.

## Hypothesis

> A deterministic shadow integration layer can causally bind one exact
> request-intent record to one bounded acquisition/transport execution, one raw
> response observation, and one S5 normalized wire-mapping result, while
> preventing cross-request substitution, response swapping, request-derived
> response authority, retry ambiguity, authority escalation, and privacy leakage;
> and the system can define a fail-closed pre-live budget/safety contract that
> identifies exactly which remaining conditions must be satisfied immediately
> before one live shadow call.

**Verdict: SUPPORTED.** Every predeclared threshold passed in the single
authoritative frozen-v3 aggregate, with deterministic semantic, artifact-ID and
byte-identical replay.

## Four layers, kept four

    RequestIntentReceipt -> TransportExecutionRecord -> RawWireObservation
                         -> RawWireMappingResult -> PreLiveIntegrationReceipt

The receipt is evidence *about* the chain, content addressed over the four layer
identities plus the safety contract. It never replaces the underlying evidence.

Predecessor contracts are composed, not reimplemented: the Route Controls
`OpenRouterRequestIntentReceiptV1` and the S5 mapping contracts are used
directly. One additive bridge, `OpenRouterTransportExecutionRecordV1`, carries
what the acquisition contracts do not — the *registered request* digests that
request-byte equality needs.

## Causal binding

Thirteen guards in a frozen order, first failure reported:

| # | guard | protects against |
| --- | --- | --- |
| 1 | request receipt validity | fabricated intent |
| 2 | transport registered | binding to something never sent |
| 3–4 | registered body and header equality | post-render mutation, request rewriting, sibling reuse |
| 5 | exactly one local dispatch | retry ambiguity, hidden fallback transport |
| 6–7 | completion, response present | claiming a later state before an earlier one |
| 8–9 | response body and header binding | response swapping |
| 10 | observation identity | unidentified evidence |
| 11–13 | mapping observation, manifest, provenance | pairing a mapping with another response |

## Authority firewall

Request intent may **match** and **compare**. It may never **fill**.

| response authority | may it come from the request? |
| --- | --- |
| actual served model | no — `$.model` only |
| response provider | no — never from `provider.only` |
| exact endpoint identity | no — `UNAVAILABLE_BY_DOCUMENTED_CONTRACT`, value `None` |
| cache status | no — header-borne only |
| routing strategy | no — never from request fallback policy |

Model conformance reports `MATCH`, `MISMATCH` or `UNAVAILABLE`. A mismatch is
real response evidence: the chain stays causally valid while candidate-policy
conformance fails. The two verdicts are recorded separately and never merged.

Provider evidence is exposed as `provider_display_name` at its documented
`HUMAN_DISPLAY_NAME` granularity, and the receipt contract refuses any value
containing a slash, so a display label cannot quietly become an endpoint slug.

Local dispatch count and OpenRouter's server-reported `attempt` / `attempts[]`
are carried as separate fields. Multiple server attempts never imply a local
retry.

Cache: a `HIT` under the pinned disabled-cache intent is recorded as
`ANOMALOUS_HIT_UNDER_DISABLED_INTENT` — an anomaly, not a violation. The retained
evidence does not establish that a HIT is impossible under this request policy,
and inventing that rule would be a repository convention.

## Cross-request substitution

Two complete sibling chains, A and B, make substitution directly attackable.
Every mix is refused: A's request with B's transport, B's request with A's
transport, A's transport with B's response, A's response with B's mapping, and
the reverse. **Cross-request substitutions accepted: 0.**

## Privacy

Receipts and the aggregate artifact carry identities, digests and lengths — never
raw request or response bytes, never a rendered prompt, never an Authorization
header, never a credential value. The credential attestation records presence and
variable name only: no value, no prefix, no length, no digest, because a digest
of a short secret is a crackable secret. The artifact was scanned for credential
markers and for the fixture response bodies; the scanner is proved non-vacuous by
a test that feeds it a synthetic leak. **Privacy leakage findings: 0.**

## Pre-live safety contract

Structural safety, provable offline now:

| property | value |
| --- | --- |
| max local dispatches | 1 |
| automatic retry | forbidden |
| exact model | `openai/gpt-4.1-mini` |
| exact endpoint selector | `azure/swedencentral` |
| provider / model fallback | disabled |
| `require_parameters` | true |
| stream / tools / cache | false / disabled / disabled |
| max output tokens | **256, already sealed in the request body** |
| mapper, causal binding, capture, persistence | available |
| timeout, worker termination | bounded |
| credential isolation | enforced |
| CED authority | disabled |

Contract identity
`szorprelivesafetyv1_bcddf7aa135057449ed6df90a3f9cdad8de2e0ac9d0e584015da052306e9a316`.

## Budget audit

### P17 — input token bound: NOT_ESTABLISHED

`tiktoken`, `transformers` and `tokenizers` are all absent. The retained
OpenAPI's `tokenizer` field is `ModelGroup` — a family label (`GPT`, `Claude`, …),
not a pinned vocabulary. `/models/count` counts models, not tokens. No documented
first-party token-count facility exists in the retained sources.

So no trustworthy deterministic pre-call input token upper bound can be produced,
and the contract refuses to let one be claimed without a tokenizer basis.

An **independent request-byte cap of 447 bytes** is recorded separately. It is a
byte cap. It is not renamed a token cap, and no relationship between the two is
established by the retained evidence.

Chat framing overhead is likewise unbounded, which the contract requires before
an input bound may be called established.

### Output token bound: ESTABLISHED

`max_tokens: 256` is already pinned in the sealed Route Controls request body. No
sealed byte was modified to obtain this.

### P18 — actual endpoint pricing: NOT_ESTABLISHED, structurally

No price was fetched. The contract is defined and the source authority is
identified: `GET /models` and `GET /models/{author}/{slug}/endpoints`, both
documented in the retained OpenAPI. `PublicPricing` carries per-token prices as
**decimal strings**, so exact arithmetic is possible, and freshness is structural
rather than wall-clock: a pricing record must carry the same
`preflight_execution_id` as the preflight consuming it, so a price from an
earlier execution is refused and offline replay stays deterministic.

That machinery is sound and still cannot be used, because of **granularity**. The
request pins the exact endpoint selector `azure/swedencentral`. The retained
endpoint record exposes `provider_name` (`"OpenAI"`), a display `name`
(`"OpenAI: GPT-4"`) and an undocumented `tag` (bare `type: 'string'`, no
description, example `'openai'`). No retained example carries a compound
`provider/region` value, `endpoint_id` examples are opaque, and the documented
route to the exact slug is a UI copy button. So no retained first-party field
binds a price to the selector the request actually pins.

Recorded as `OPENROUTER_PRICING_ENDPOINT_GRANULARITY_V1 = "BROAD_PROVIDER_ONLY"`.
Mapping a broad display name onto the exact selector would be a synthesis, and
the contract refuses it.

*Correction.* An earlier draft of this document called P18 "JIT-reachable". That
was wrong at the granularity the request requires. It is a structural blocker,
not a freshness one.

### P19 — total cost bound: NOT_ESTABLISHED

`max_input_tokens × prompt_price + max_output_tokens × completion_price`, in
integer picodollars (1e-12 USD), parsed from official decimal strings with
`Decimal` and rounded **up** — an upper bound may overstate, never understate.
No fee is invented and no documented one dropped. `NaN`, `Infinity`, negative and
malformed price strings are refused.

Established only when both token bounds and the price are themselves trusted and
bounded. P17 is not, so P19 is not.

`max_price` bounds unit price rather than total spend — and that is exactly the
factor P19 was missing for the token classes. See **Request-side price ceiling**
below. Two things still stand in the way: P17, and the per-request fee.

### P19 is three states, not one

Collapsing them would let a token-only sum pass for a complete worst-case total.
So they are recorded separately, and the contract enforces the relationship:

| state | value | meaning |
| --- | --- | --- |
| `p19_formula_structure` | **READY** | the arithmetic is defined and exact |
| `p19_applicable_charge_coverage` | **INCOMPLETE** | a documented class that can apply here is unbounded |
| `p19_worst_case_cost_authority` | **NOT_ESTABLISHED** | so no total may be claimed |

The symbolic total covers every **applicable** documented class:

```
max_total_cost = max_input_tokens  x prompt_price_ceiling
               + max_output_tokens x completion_price_ceiling
               + request_fee_ceiling
```

For this exact request `image` and `audio` are **NOT_APPLICABLE**, and that is
proven rather than assumed - see below. `request` is applicable, documented, and
currently **unbounded**, which is why coverage is INCOMPLETE.

**No hidden term, by construction.** The formula string is rendered from the very
component list the code sums, and a total is produced *only* when every applicable
class is bounded. A term cannot be in the arithmetic and missing from the formula,
or the reverse; a test asserts the rendered sum equals the applicable class set and
that the value equals those terms computed independently.

**An omitted fee is unknown, never zero.** `request_usd = None` yields
`request_picodollars = None` and the state `UNBOUNDED`. Only an explicit `"0"`
is a bound of zero, and it produces a different policy identity.

**Closing it.** S7 or the operator may supply a request-fee ceiling, or
first-party evidence may establish the fee is zero. S6 chooses neither: it
defines the mechanism and refuses to invent a monetary policy.

### Modality is proven from the request's own bytes

`image` and `audio` are not dismissed by convention. The sealed request's exact
canonical body is parsed, its content parts counted, and the result content
addressed together with the body digest:

```
szorrequestmodalityv1_4769e106...   text_only=True  images=0  audio=0
body_sha256 = 35a119b1...   body_length = 447   messages = 2
```

The digest is the sealed request's own, so no other request can borrow the proof:
a synthetic image-bearing body derives a different proof, and under it the `image`
class becomes UNBOUNDED rather than NOT_APPLICABLE. An unrecognized content part
type is refused outright - a modality nobody has classified cannot be proven
harmless.

### Request-side price ceiling: ESTABLISHED

Actual endpoint pricing is unavailable at the required selector granularity. A
*ceiling* does not need it. `provider.max_price` is a first-party request-side
control the router enforces before it selects a route, so it bounds unit price
without reading any endpoint's price.

**Components and exact units**, verbatim from the retained OpenAPI
(`ProviderPreferences.max_price`, all five `type: 'string'`):

| component | unit | bounds |
| --- | --- | --- |
| `prompt` | USD per **million** prompt tokens | input unit price |
| `completion` | USD per **million** completion tokens | output unit price |
| `request` | USD per request | per-request fee |
| `image` | USD per image | image fee |
| `audio` | USD per audio unit | audio fee |

Every documented charge class in the retained contract has its own component;
there is no sixth. The prompt and completion components bound input and output
unit price **independently** — each is its own cap, not a shared budget.

**The unit trap.** `max_price.prompt` is USD per *million* tokens; the catalogue
`PublicPricing.prompt` is USD per *token*. A factor of 10⁶ separates them. The
conversion is explicit, uses `Decimal` at 60 digits of precision, and rounds
**up** into integer picodollars, so a ceiling may overstate and never understate:

```
picodollars_per_token = ceil(usd_per_million × 10¹² ÷ 10⁶)
```

`$1/M` becomes 1 000 000 picodollars per token; `$2/M` becomes 2 000 000. Float
money is refused at the contract boundary — a `float` ceiling is not an authority.

**Three unrelated things share the name `max_price`** in the retained spec, and
only one is this control:

| sense | used | why not |
| --- | --- | --- |
| `ParetoRouterPlugin.max_price` | no | a plugin field: a `double`, **input price only**, enforced against its own `price_source` |
| `ProviderPreferences.max_price` | **yes** | the request-side ceiling audited here |
| models-listing `max_price` query parameter | no | a catalogue browse filter, not a request control |

The `price_source` description — "catalog list price (`endpoint.pricing.prompt`)"
— belongs to the **plugin**, not to `ProviderPreferences`. Citing it as ceiling
behaviour would import a claim the audited schema does not make.

**Routing semantics**, each proved separately against retained evidence:

| # | statement | verdict | evidence |
| --- | --- | --- | --- |
| A | over-ceiling endpoints are excluded *before* selection | ESTABLISHED | the guide states a request "will route to any provider with a price of `<= $1/m` prompt tokens, and `<= $2/m` completion tokens or less" — the cap decides the route |
| B | `provider.only` cannot re-admit an excluded endpoint | ESTABLISHED | restrictions compose by narrowing: "both restrictions apply… If no provider satisfies both, the request fails with a 404" |
| C | an unsatisfiable ceiling fails the request rather than relaxing | ESTABLISHED | "This is different than `max_price`, which will prevent your request from running if the price is not available" |
| D | `allow_fallbacks: false` does not bypass the ceiling | ESTABLISHED | fallbacks are a narrowing switch ("you can disable fallbacks"); nothing in the retained contract lets one re-admit a filtered endpoint |
| E | the ceiling is independent of response display-name granularity | ESTABLISHED | it is a request-side control enforced before dispatch; it never requires reading a provider name back |

B, D and E are each *narrowing* arguments: no retained mechanism widens a filtered
candidate set. That is what makes the ceiling safe to rely on — it can only ever
reduce what is reachable.

**What this changes.** Exact actual endpoint pricing remains unavailable at the
required selector granularity, but a first-party server-enforced unit-price
ceiling provides an independent pre-dispatch upper bound. P18 is therefore **no
longer a structural blocker to safe live cost bounding**. It remains
NOT_ESTABLISHED for anything that needs the *actual* price.

**What this does not change.** A ceiling caps the rate. It says nothing about how
many tokens are billed, and a token-price ceiling alone leaves the documented
per-request fee uncapped. P17 is untouched and charge coverage is INCOMPLETE, so
P19's worst-case cost authority stays NOT_ESTABLISHED.

**No monetary value is chosen here.** S6 defines the mechanism and the arithmetic;
the operator authorizes actual ceiling values before S7.

### The sealed request is not modified

The sealed Route Controls request does not render `max_price`; its receipt records
`max_price_status: DEFERRED_NOT_RENDERED`, and the Route Controls case set already
refuses a guessed one (`orroutev1-or19-guessed-max-price`). That evidence is
historical and stays byte-identical: body 447 bytes, digest `35a119b1…`.

The ceiling is therefore **additive**. `OpenRouterLiveRequestSafetyOverlayV1`
carries the sealed receipt identity plus a price policy and derives a **new**
future-live request identity, which the contract refuses to let equal the sealed
receipt identity. Every frozen control is restated as a `Literal` so the overlay
cannot quietly relax one: exact model, exact endpoint selector, `provider.only`
and `provider.order` singletons, `allow_fallbacks: false`, `require_parameters:
true`, `stream: false`, tools disabled, metadata enabled, cache not requested, and
`max_tokens: 256`. The only addition is the documented price-ceiling field.

### Operator ceiling

An independent firewall on top of P18/P19, not a replacement. S6 deliberately
does not choose a monetary value; the operator authorizes a specific ceiling
before S7, and the preflight requires `worst-case cost ≤ ceiling`.

## One-call authorization

Not a reusable boolean. A content-addressed record bound to the exact request
intent, pricing record, both bounds, the operator ceiling, the credential
attestation and the safety contract, permitting exactly one dispatch. Reuse is
refused, and a test proves it by consuming an authorization and presenting it
again.

## Why the live call is NOT_AUTHORIZED

`AUTHORIZED_PENDING_JIT_PREFLIGHT` requires that every remaining blocker be a
fresh external fact resolvable inside the S7 preflight, with no structural
P17/P19 ambiguity.

The *pricing* obstacle is gone: the server-enforced ceiling is a valid price
authority, needs no retrieval, and is bounded before dispatch. Two blockers
remain, and they are different in kind.

**P17 is structural.** Closing it needs either a pinned officially-supported
tokenizer or a first-party token-count facility, and adding either is a change to
the repository, not a fact to be fetched.

**Charge coverage is a policy gap, not a structural one.** The documented
per-request fee is simply not capped by the current policy. An operator ceiling
value, or first-party evidence that the fee is zero, closes it - which is exactly
the kind of thing S7 may supply. It is listed honestly rather than rounded to
zero.

Calling this pending-JIT would use the status to hide unresolved architecture,
which the phase rules explicitly forbid. The honest answer is NOT_AUTHORIZED.

**The single remaining structural blocker:** a trustworthy deterministic pre-call
input token upper bound for `openai/gpt-4.1-mini`. Two candidate routes, both
structural:

1. pin an officially-supported tokenizer and prove the bound, including chat
   framing overhead; or
2. establish a first-party token-count facility as an authority.

Everything else in the S7 checklist is already built and tested: transport
readiness, credential presence, request-intent match, output bound, JIT pricing
retrieval and validation, cost computation, ceiling comparison, one-call
authorization consumption, and abort-before-dispatch on any failure.

## Predeclared thresholds

Declared before the authoritative run and content addressed as
`szorprelivethresholdsv1_eca7807368ef60ef49a8218f8b24071c52afa86385c80539bb2c885a2f274f3b`.

The authoritative observed values equal every required value:

| threshold | required | observed |
| --- | --- | --- |
| integration positive accepted | 12 | 12 |
| integration adversarial rejected | 18 | 18 |
| preflight authorized | 3 | 3 |
| preflight refused | 23 | 23 |
| ceiling probes holding | 26 | 26 |
| unexpected results | 0 | 0 |
| invalid fixture constructions | 0 | 0 |
| guard-code mismatches | 0 | 0 |
| cross-request substitutions accepted | 0 | 0 |
| request-to-response authority leaks | 0 | 0 |
| provider-to-endpoint synthesis | 0 | 0 |
| requested-to-actual substitutions | 0 | 0 |
| metadata-absence cache-hit inferences | 0 | 0 |
| authorization reuse accepted | 0 | 0 |
| privacy leakage findings | 0 | 0 |
| external activity, every category | 0 | 0 |
| `git diff --check` | PASS | PASS |
| frozen predecessor files | all identical | 742/742 identical |

Frozen predecessor integrity is measured by full Git object identity against the
S5 head `1be95cfdecd9628cdf2d1ea6abdcf66ba1aa88a6`: all 742 tracked predecessor
files remain present at the same paths and byte-identical. S5, S4, S3, Route
Controls and Manifest v2r1 are unchanged.

## Pre-authoritative freeze

Every semantic file was committed **before** the authoritative run, with a clean
tracked worktree at freeze HEAD
`776780a1f39c36795c1204f29e95febaf144b169`. A post-run Git-object audit then
confirmed all five frozen semantic blobs remained identical.

The freeze point has been superseded three times, each time before any run
consumed it: `4861c8a4` (original), `fd30a7fb` (rulings applied), `170124a` (price
ceiling), and the current freeze, which splits P19 into formula structure,
applicable charge coverage and worst-case authority. Superseding an *unconsumed*
freeze is safe. The current frozen-v3 result has had no semantic change after
execution; the earlier run at `0ff79c9` remains superseded because semantic
changes followed it.

| frozen identity | value |
| --- | --- |
| integration case set | `szorintegrationcasesetv1_05922235a81b26142dd68e7a58c2c070fbae6471f97527aef70739af819d8f56` |
| preflight case set | `szorpreflightcasesetv1_5e5136109e81b9e184fac7f521da7d5d8f2c7f2f946e7b110d17ad12429ecb15` |
| ceiling case set | `szorceilingcasesetv1_58dccf6cf47893c178e7f39b32360d08f1fc64db53e5992f8bd6e3d100b19c51` |
| thresholds | `szorprelivethresholdsv1_eca7807368ef60ef49a8218f8b24071c52afa86385c80539bb2c885a2f274f3b` |
| integration guards | `szorintegrationguardsv1_4001e6a1a7a53afa24b7b1eb4eaabcbbdf701dffa6ee10d91922d143406146a5` |
| preflight guards | `szorpreflightguardsv1_3171845ea6454a4ac3b7ea2f68c0d2c4e31fa6912a4d162a6a776ddb599773db` |
| semantic runtime modules | 5 |
| cases | 82 (30 integration, 26 preflight, 26 price ceiling) |

## Authoritative artifact and replay

| evidence | identity | SHA-256 |
| --- | --- | --- |
| artifact | `szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779` | `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d` |
| replay execution | `szorprelivereplayexecutionv1_7b8efdb484a2a9ce99ed9682c889e5348be10c7578dbb56252cdde85ba7cb669` | `ff40af69cccd5297c5c0b2d65c82f25448c2e16a0f8019048916d5976afb5c27` |
| replay lock | `szorprelivereplaylockv1_acc9604c588d6015007961bef5f2e259b8f068677d34b0f00b38e753dbac5c8b` | `256bf8eefe71c0c1e6b468d090ca55997ddfc105065594c16ec0aeee3cf15c8a` |

Replay: **semantic equality, artifact-ID equality and byte identity all true**,
with zero source retrievals and zero live calls. The lock contract refuses to
exist unless all three hold. The artifact's zero claims are cross-checked against
live tripwire instrumentation, and building outside an active tripwire is
refused.

## Test gates

| gate | result |
| --- | --- |
| S6 focused | **149 passed** |
| S5 mapper + evaluator | 109 passed |
| S3 provenance + static | 64 passed |
| Route Controls focused | 103 passed |
| Manifest v1 + v2r1 | 25 passed |
| all OpenRouter | 728 passed, 1 skipped |
| full `tests_dialogues` | **3537 passed, 10 skipped, exit 0** |
| `git diff --check` | PASS |
| frozen predecessor files | **742/742 identical** |

S5, S4, S3, Route Controls and Manifest v2r1 are all byte-identical.

## External activity

OpenRouter calls 0. Provider 0. Model 0. Credential accesses 0. Paid requests 0.
CED applications 0. Official-source retrievals 0. Measured by the boundary
tripwire, not asserted.

## What S7 must do, in order

1. carry an operator-authorized `provider.max_price` policy in the additive live
   request overlay, **including a request-fee ceiling**, or establish from
   first-party evidence that the request fee is zero;
2. establish an input token bound — **the structural blocker above**;
3. compute the deterministic worst-case cost in integer picodollars from the
   ceiling, recording `price_authority = SERVER_ENFORCED_CEILING`;
4. compare against the operator-authorized spend ceiling;
5. check credential presence at the final boundary only;
6. consume the one-call authorization;
7. dispatch exactly once, or abort before touching the network.

Steps 1 and 3 through 7 are built and tested. Step 2 is not, and it is why this
phase does not authorize a call. Obtaining an *actual* price record remains
optional and, at the required selector granularity, still unavailable.

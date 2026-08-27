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
| Output token bound | **ESTABLISHED** |
| P18 trusted pricing | **NOT_ESTABLISHED** |
| P19 total cost bound | **NOT_ESTABLISHED** |
| **One live shadow call** | **NOT_AUTHORIZED** |

`OPENROUTER PRE-LIVE INTEGRATION v1 SUPPORTED` — the integration hypothesis held.
That is a statement about the pipeline, not permission to call anything.

## Hypothesis

> A deterministic shadow integration layer can causally bind one exact
> request-intent record to one bounded acquisition/transport execution, one raw
> response observation, and one S5 normalized wire-mapping result, while
> preventing cross-request substitution, response swapping, request-derived
> response authority, retry ambiguity, authority escalation, and privacy leakage;
> and the system can define a fail-closed pre-live budget/safety contract that
> identifies exactly which remaining conditions must be satisfied immediately
> before one live shadow call.

**SUPPORTED.**

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
`szorprelivesafetyv1_b9312bcd9d326c01ed514868a423af13fcc1e871f74ca4ea58daba7831afabf5`.

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

### P18 — trusted pricing: NOT_ESTABLISHED, but JIT-reachable

No price was fetched. The contract is defined and the source authority is
identified: `GET /models` and `GET /models/{author}/{slug}/endpoints`, both
documented in the retained OpenAPI. `PublicPricing` carries per-token prices as
**decimal strings**, so exact arithmetic is possible. Endpoint-scoped pricing is
preferred because the request pins a single provider endpoint and pricing may
differ by route.

Freshness is structural rather than wall-clock: a pricing record must carry the
same `preflight_execution_id` as the preflight consuming it, so a price from an
earlier execution is refused and offline replay stays deterministic.

### P19 — total cost bound: NOT_ESTABLISHED

`max_input_tokens × prompt_price + max_output_tokens × completion_price`, in
integer picodollars (1e-12 USD), parsed from official decimal strings with
`Decimal` and rounded **up** — an upper bound may overstate, never understate.
No fee is invented and no documented one dropped. `NaN`, `Infinity`, negative and
malformed price strings are refused.

Established only when both token bounds and the price are themselves trusted and
bounded. P17 is not, so P19 is not.

`max_price` cannot substitute: the retained provider-selection guide documents it
as a *per-token unit price* filter that refuses to run above the cap. It bounds
unit price, not total spend.

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
P17/P19 ambiguity. P18 qualifies — a first-party price is exactly such a fact.
**P17 does not.** Closing it needs either a pinned officially-supported tokenizer
or a first-party token-count facility, and adding either is a structural change
to the repository, not a fact to be fetched. Without an input bound there is no
bounded worst-case cost, so P19 stays open too.

Calling this pending-JIT would use the status to hide unresolved architecture,
which the phase rules explicitly forbid. The honest answer is NOT_AUTHORIZED.

**Smallest structural blocker:** a trustworthy deterministic pre-call input token
upper bound for `openai/gpt-4.1-mini`. Two candidate routes, both structural:

1. pin an officially-supported tokenizer and prove the bound, including chat
   framing overhead; or
2. establish a first-party token-count facility as an authority.

Everything else in the S7 checklist is already built and tested: transport
readiness, credential presence, request-intent match, output bound, JIT pricing
retrieval and validation, cost computation, ceiling comparison, one-call
authorization consumption, and abort-before-dispatch on any failure.

## Predeclared thresholds

Declared before the authoritative run and content addressed as
`szorprelivethresholdsv1_c975efcef4785a948059f7db0d95894b7098499f6b7c1688c9820055d8b1d436`.

| threshold | required | observed |
| --- | --- | --- |
| integration positive accepted | 12 | **12** |
| integration adversarial rejected | 18 | **18** |
| preflight authorized | 1 | **1** |
| preflight refused | 14 | **14** |
| unexpected results | 0 | **0** |
| invalid fixture constructions | 0 | **0** |
| guard-code mismatches | 0 | **0** |
| cross-request substitutions accepted | 0 | **0** |
| request→response authority leaks | 0 | **0** |
| provider→endpoint synthesis | 0 | **0** |
| requested→actual substitutions | 0 | **0** |
| metadata-absence→cache-hit inferences | 0 | **0** |
| authorization reuse accepted | 0 | **0** |
| privacy leakage findings | 0 | **0** |
| external activity, all categories | 0 | **0** |

## Pre-authoritative freeze

Every semantic file was committed **before** the authoritative run, at
`4861c8a4df3ad9e3721f9a46ac3cb3c237c54828`, with a clean tracked worktree. This
is the step S5 omitted, and it removes the need for a post-run Git-object audit.

| frozen identity | value |
| --- | --- |
| integration case set | `szorintegrationcasesetv1_05922235a81b26142dd68e7a58c2c070fbae6471f97527aef70739af819d8f56` |
| preflight case set | `szorpreflightcasesetv1_aeb2db1215e4e4e604f026419b3933a6b3e1fb5379c23db829943abcd3ec5c3b` |
| thresholds | `szorprelivethresholdsv1_c975efcef4785a948059f7db0d95894b7098499f6b7c1688c9820055d8b1d436` |
| integration guards | `szorintegrationguardsv1_4001e6a1a7a53afa24b7b1eb4eaabcbbdf701dffa6ee10d91922d143406146a5` |
| preflight guards | `szorpreflightguardsv1_8320906244ee2e3b9f564c0f5067f1e32d85ee13f6bed9824904e8aeafe517b7` |
| semantic runtime modules | 4 |
| cases | 45 (30 integration, 15 preflight) |

## Authoritative artifact and replay

| evidence | identity | SHA-256 |
| --- | --- | --- |
| artifact | `szorpreliveartifactv1_6ff594b31e88781f0d8aaf9705c7e1c48c8bea5965ea820c0be6af6a69f9932e` | `971921fce44ba967080b987d6ce6c646d6f6c006c9ad2f6793661d1f7038c3ea` |
| replay execution | `szorprelivereplayexecutionv1_60968c552d5a75a9e29c9d8bb9548eec7914129b2f6f00729605345bb08bbca6` | `05e8d0d7482a306a36bfb099b2617609524d56e2d31581656d8a20ca87de4bfb` |
| replay lock | `szorprelivereplaylockv1_1b3058cc8253bc410f7902def33f403c35c29213a949db761407662799437be6` | `42a398912e450783f762e2ffeb78c17921780c19ac502c34a2cea89958573667` |

Replay: **semantic equality, artifact-ID equality and byte identity all true**,
with zero source retrievals and zero live calls. The lock contract refuses to
exist unless all three hold. The artifact's zero claims are cross-checked against
live tripwire instrumentation, and building outside an active tripwire is
refused.

## Test gates

| gate | result |
| --- | --- |
| S6 focused | **84 passed** |
| S5 mapper + evaluator | 109 passed |
| S3 provenance + static node | 65 passed |
| Route Controls focused | 103 passed |
| v1 + v2r1 evidence | 48 passed |
| full `tests_dialogues` | **3472 passed, 10 skipped** |
| `git diff --check` | PASS |
| frozen predecessor surfaces | **19/19 identical** |

S5, S4, S3, Route Controls and Manifest v2r1 are all byte-identical.

## External activity

OpenRouter calls 0. Provider 0. Model 0. Credential accesses 0. Paid requests 0.
CED applications 0. Official-source retrievals 0. Measured by the boundary
tripwire, not asserted.

## What S7 must do, in order

1. obtain a first-party price record for the exact model and endpoint scope;
2. verify source authority, model and endpoint scope, and JIT freshness;
3. establish an input token bound — **the structural blocker above**;
4. compute the deterministic worst-case cost in integer picodollars;
5. compare against the operator-authorized ceiling;
6. check credential presence at the final boundary only;
7. consume the one-call authorization;
8. dispatch exactly once, or abort before touching the network.

Steps 1, 2 and 4 through 8 are built and tested. Step 3 is not, and it is why
this phase does not authorize a call.

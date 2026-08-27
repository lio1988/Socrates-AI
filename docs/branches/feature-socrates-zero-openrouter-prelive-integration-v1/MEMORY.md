# MEMORY — feature/socrates-zero-openrouter-prelive-integration-v1

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-raw-wire-mapping-v2`
- Source HEAD: `1be95cfdecd9628cdf2d1ea6abdcf66ba1aa88a6` (published)
- S5 artifact SHA-256: `d42fd8486c89f4b1ec6fd8dc2d5b9aee9b7aeb23c23237adcdac929a8ace1d75`

## Non-negotiable invariants

1. **Compare, never fill.** Request intent may match and compare. It may never
   supply an authority the response did not carry: not the actual served model,
   not the response provider, not the exact endpoint, not cache status, not
   routing strategy. When the response is silent, the S5 epistemic state stands.
2. **Four layers stay four.** Request intent, transport execution, raw
   observation, normalized mapping. The integration receipt is evidence *about*
   the chain, never a replacement for it.
3. **One local dispatch.** Exactly one, never zero, never two. OpenRouter's own
   `attempt` / `attempts[]` is server-reported routing evidence and is a
   different concept from a local dispatch; never conflate them.
4. **Causal order is enforced.** Registered, dispatched once, completed, response
   present, observed, mapped — then and only then a receipt.
5. **Compact receipts.** Identities, digests and lengths. No raw request or
   response bytes, no rendered prompt, no Authorization header, no credential
   value or digest anywhere near a scientific identity.
6. **Shadow only.** No runtime authority, no CED consumption, no production
   wiring, no live call.

## Findings that shaped the design

**`max_tokens: 256` is already pinned** in the sealed Route Controls body, so the
output token bound exists without touching sealed bytes.

**No tokenizer is available.** `tiktoken`, `transformers` and `tokenizers` are
all absent, and the retained OpenAPI's `tokenizer` field is `ModelGroup` — a
family label (`GPT`, `Claude`, …), not a pinned vocabulary. `/models/count`
counts models, not tokens. So no deterministic pre-call input token bound exists,
and **P17 is NOT_ESTABLISHED** — a structural gap, not a missing fresh fact.

**`max_price` is a server-enforced ceiling, and it is enough.** The retained
guide documents it as a per-token unit price filter that refuses to run above the
cap. Bounding unit price is exactly the factor a worst-case cost needs: multiplied
by bounded token counts it yields a bounded total. It cannot close P19 *alone* —
it caps the rate, not the token count — but it removes the *pricing* obstacle
without any retrieval.

**Pricing endpoints exist but cannot be bound to the request.** `GET /models` and
`GET /models/{author}/{slug}/endpoints` are documented first-party surfaces, and
`PublicPricing` carries prices as **decimal strings** per token — exact integer
arithmetic is possible. The blocker is granularity, below, not arithmetic.

## Pricing granularity — the audited finding

`PRICING ENDPOINT GRANULARITY: BROAD_PROVIDER_ONLY`.

The pricing-bearing endpoint record exposes `provider_name` (broad display name),
`name` (display string) and `tag` (bare `type: string`, no description, no
documented namespace, example `openai`). No endpoint-scoped slug field exists on
it, retained `endpoint_id` examples are UUIDs in a different namespace, no
retained example carries a compound `provider/region` value, and the documented
route to the exact slug is a UI copy button rather than an API field.

So a price cannot be bound to `azure/swedencentral`. **P18 is structurally
blocked, not merely freshness-blocked.** Do not repeat the earlier claim that P18
is JIT-ready.

## The server-enforced unit-price ceiling — the decisive finding

`TRUSTED UNIT-PRICE CEILING: ESTABLISHED`. Keep it strictly separate from
`P18_TRUSTED_ACTUAL_PRICING_RECORD`: a ceiling says *no more than*, a pricing
record says *this much*. Different contracts, different identity namespaces
(`szorunitpriceceilingv1_` vs the pricing record's), and neither may stand in for
the other.

`ProviderPreferences.max_price` has five documented components, each with its own
unit and each an independent cap: `prompt` (USD per **million** prompt tokens),
`completion` (USD per **million** completion tokens), `request` (USD per request),
`image` (USD per image), `audio` (USD per audio unit). All five are
`type: 'string'`. There is no sixth documented charge class.

**The unit trap.** `max_price.prompt` is per *million* tokens; `PublicPricing`
is per *token*. Factor 10⁶. Convert explicitly, with `Decimal`, rounding **up**.

**Three unrelated `max_price` fields exist in the retained spec.** Only
`ProviderPreferences.max_price` is this control. `ParetoRouterPlugin.max_price` is
a `double` that caps input price alone and is enforced against its own
`price_source`; a models-listing query parameter of the same name is a catalogue
browse filter. The `price_source` sentence about "catalog list price" belongs to
the **plugin** — never cite it as ceiling behaviour.

**Routing semantics, each proved separately:** exclusion happens before selection;
`provider.only` cannot re-admit an excluded endpoint; an unsatisfiable ceiling
fails the request rather than relaxing; `allow_fallbacks: false` cannot bypass it;
and it is independent of response display-name granularity. Every one of these is
a *narrowing* argument — no retained mechanism widens a filtered candidate set.

**The sealed request is never modified.** It does not render `max_price`
(`max_price_status: DEFERRED_NOT_RENDERED`), and Route Controls already refuses a
guessed one. The ceiling arrives through an **additive overlay** that produces a
*new* future-live request identity, restating every frozen control as a `Literal`
so none can be quietly relaxed. Body stays 447 bytes, digest `35a119b1…`.

**No monetary value is chosen in S6.** Mechanism and arithmetic only; the operator
authorizes actual ceiling values before S7.

## P19 is three states, never one

`P19_FORMULA_STRUCTURE` (READY), `P19_APPLICABLE_CHARGE_COVERAGE`
(COMPLETE/INCOMPLETE) and `P19_WORST_CASE_COST_AUTHORITY`
(ESTABLISHED/NOT_ESTABLISHED) are separate fields and must stay separate. A
token-only sum is not a complete worst-case total while a documented per-request
fee is unbounded.

Currently: structure READY, coverage **INCOMPLETE** (`request_usd` unbounded),
authority NOT_ESTABLISHED.

**The formula cannot drift from the arithmetic.** Both come from one component
list: the rendered formula names every *applicable* class, and a total is
computed only when every one of them is bounded. There is therefore no state in
which a term is summed but unnamed, or named but unsummed.

**An omitted fee is unknown, not zero.** `request_usd = None` gives
`request_picodollars = None` and state UNBOUNDED. Only an explicit `"0"` bounds
it at zero, and it yields a different policy identity. Never let an omission
become an authoritative zero.

**Image and audio are NOT_APPLICABLE by proof, not convention.**
`OpenRouterRequestModalityProofV1` parses the sealed request's exact canonical
body, counts content parts, and content addresses the result with the body
digest. The proof is bound to *those bytes*: a synthetic image-bearing request
derives its own proof and gets UNBOUNDED, not NOT_APPLICABLE. An unclassified
content part type is refused rather than assumed harmless.

Do not close coverage by inventing a request-fee ceiling. The operator or S7
supplies one, or first-party evidence establishes the fee is zero.

## Three max_price paths, refused by path

`build_openrouter_max_price_policy_v1(schema_path, ...)` refuses
`components.schemas.ParetoRouterPlugin.max_price` and the `/models` listing
filter *by name*, with well-formed decimal values, so the refusal is attributable
to the contract path rather than incidentally to the float or decimal guards.
Only `components.schemas.ProviderPreferences.max_price` is the ceiling authority.

## String equality is not identity-namespace authority

`PRICING_BROAD_AT_EXACT_SELECTOR` spells `azure/swedencentral` exactly and still
declares BROAD_PROVIDER_ONLY granularity, so `PRICING_SELECTOR_MISMATCH` passes
and `PRICING_GRANULARITY_INSUFFICIENT` is the guard that fires. Guard order was
not touched to make coverage easier.

## Money

Integer picodollars (1e-12 USD), parsed from official decimal strings via
`Decimal` and rounded **up**. A cost upper bound may overstate; it may never
understate.

## Freshness without a clock

Pricing freshness is structural: a record must carry the same
`preflight_execution_id` as the preflight consuming it. No wall clock enters any
identity, so offline replay stays deterministic.

## Traps

`importlib.reload` on any of these modules rebinds every contract class and
breaks identity checks everywhere afterwards. Execute the module body into a
throwaway namespace instead — and register that namespace in `sys.modules` under
the throwaway key, or pydantic cannot resolve the annotations.

A static scanner that looks for marker literals must not contain those literals
in its own source if it scans itself. Assemble them from fragments.

## Outcome

One live shadow call **NOT_AUTHORIZED**. Two blockers, different in kind:

* **P17** — structural. Needs a pinned tokenizer or a first-party token-count
  facility; a change to the repository, not a fact to fetch.
* **Charge coverage** — a policy gap. The documented per-request fee is simply
  not capped. An operator ceiling value or first-party evidence closes it.

The *pricing* obstacle is closed by the server-enforced ceiling.

The frozen-v3 authoritative aggregate is **SUPPORTED**. Its current artifact is
`szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779`
(SHA-256 `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d`),
with semantic, artifact-ID and byte-identical replay. Do not rerun it. Do not let
a future session confuse the superseded earlier run with this result, or read
`SUPPORTED` as permission to call: one live shadow call remains
**NOT_AUTHORIZED**.

## Environment

Repository `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`;
interpreter `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`;
`PYTHONPATH` at the repository root; `.gitignore` ignores `*.md` and `*.json`, so
use `git add -f`.

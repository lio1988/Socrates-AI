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

One live shadow call **NOT_AUTHORIZED**. After the ceiling audit, **P17 is the
sole remaining structural blocker** — the price obstacle is closed. P17 is
structural, not a missing fresh fact: closing it needs a pinned tokenizer or a
first-party token-count facility.

The integration verdict itself is **not yet claimed**: the authoritative aggregate
has not been run under the current case set. Do not let a future session read a
passing dry-run, or the superseded earlier run, as either the verdict or as
permission to call.

## Environment

Repository `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`;
interpreter `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`;
`PYTHONPATH` at the repository root; `.gitignore` ignores `*.md` and `*.json`, so
use `git add -f`.

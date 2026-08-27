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

**`max_price` cannot substitute.** The retained provider-selection guide
documents it as a *per-token unit price* filter that refuses to run above the
cap; it bounds unit price, not total spend, so it cannot close P19 on its own.

**Pricing is reachable JIT.** `GET /models` and
`GET /models/{author}/{slug}/endpoints` are documented first-party surfaces, and
`PublicPricing` carries prices as **decimal strings** per token — exact integer
arithmetic is possible without ever touching a binary float.

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

Integration SUPPORTED; one live shadow call NOT_AUTHORIZED. The blocker is P17
and it is structural, not a missing fresh fact. Do not let a future session read
"integration supported" as permission to call.

## Environment

Repository `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`;
interpreter `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`;
`PYTHONPATH` at the repository root; `.gitignore` ignores `*.md` and `*.json`, so
use `git add -f`.

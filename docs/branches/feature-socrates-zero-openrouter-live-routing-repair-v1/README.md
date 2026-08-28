# Branch: feature/socrates-zero-openrouter-live-routing-repair-v1

Repairs the S7B routing refusal and obtains the first real OpenRouter model
response for this research line.

This same branch also carries one bounded follow-up experiment: compare
GPT-4.1-mini and GPT-4.1 under the exact same provider-facing JSON Schema while
leaving CED unchanged. It is an experiment continuation, not another
architecture phase.

Branch working notes: [MEMORY.md](MEMORY.md), [PLAN.md](PLAN.md), and
[PRESENT.md](PRESENT.md).

## What S7B hit

S7B dispatched one authorized call and received HTTP 404, "No endpoints found
that can handle the requested parameters", with three endpoints available and
none selected.

## The actual cause

Not the provider slug, and not the price ceilings. The documented endpoint
listing shows:

| endpoint tag | `max_tokens` | `max_completion_tokens` |
| --- | --- | --- |
| `azure` | no | yes |
| `openai` | **yes** | no |
| `azure/swedencentral` | **no** | yes |

The request sent `max_tokens: 256` with `require_parameters: true`.
`azure/swedencentral` passed `provider.only` but does not accept `max_tokens`,
and the only endpoint that does — `openai` — was excluded by `provider.only`.
The intersection was empty, so the router refused.

Two things had hidden this: the **model-level** `supported_parameters` is the
union across endpoints and does contain `max_tokens`, and the per-endpoint
pricing differs from the model-level figure ($0.44/$1.76 against $0.40/$1.60).
Only per-endpoint evidence shows either.

## The correction

One documented substitution: `max_tokens` -> `max_completion_tokens`, value 256
unchanged. Everything else identical, and a **new request identity**: the sealed
S4/S5/S6 Route Controls request is not modified.

## Result

HTTP 200, a real model answer, `actual_served_model` ESTABLISHED and equal to the
requested model, S5 mapping accepted, S6 causal binding accepted, observed cost
$0.00004928 against a pre-call bound of $0.5243 and an operator ceiling of $0.60.

## Structured-output follow-up result

The bounded two-arm continuation is complete. Both GPT-4.1-mini and GPT-4.1
returned HTTP 200, satisfied the identical strict provider schema, passed CED
schema validation, and passed the canonical Socratic firewall with one call and
zero retries each. Mini's success classifies the preserved `0/2` prompt-only
control as an interface reliability failure. The full model showed no material
Socratic quality gain in this pair, so the cheaper mini remains preferred.

See [STRUCTURED_OUTPUT_EXPERIMENT.md](STRUCTURED_OUTPUT_EXPERIMENT.md).

## Non-goals

No change to sealed predecessor evidence. No retry of any call. No runtime or CED
authority. Not pushed.

# Normal live test harness

## The change that matters

Before: every new question needed a new architecture freeze, because the question
lived inside the frozen request body.

Now the two halves are separate.

| frozen once | free every turn |
| --- | --- |
| model, provider selector, fallback, streaming, tools | system prompt |
| output bound, price ceilings | user content |
| transport behaviour, retry policy | role seat |
| S5 / S6 semantics, privacy rules | dialogue and turn identity, phase |

A question changes the request identity, the body digest and the cost bound. It
cannot change routing, ceilings or retry semantics — a lock proves that even a
question whose text is itself a `provider` block never reaches the provider
block.

## Endpoint capability profile

The pilot's 404 taught that model-level `supported_parameters` is the **union**
across endpoints and is unsafe once `provider.only` pins one of them. The profile
records what the pinned endpoint actually accepts, and the renderer emits the
parameter that endpoint names:

```
provider selector          azure/swedencentral
canonical model observed   openai/gpt-4.1-mini-2025-04-14
output-limit wire field    max_completion_tokens   (never max_tokens)
evidence digest            73d8f913…  (the endpoint listing)
```

Capability validation runs once when the session is built, not per turn, and
refuses before any inference if the policy would emit an unsupported parameter.

## Two levels of spend authority

```
session authorization      caps calls, total spend, per-call spend
   |
   +-- turn claim #1        atomically consumed before dispatch
   +-- turn claim #2
   +-- ...
```

The per-request one-shot protection proven in the pilot is **automated, not
removed**: each turn still mints and burns its own single-use claim, so normal
dialogue does not need operator approval per turn while a duplicate dispatch
remains impossible. A failed HTTP attempt still consumes a call. Retries: zero.

## The cost-bound tension, stated plainly

The only *established* pre-call input bound is the model context limit, so the
conservative reservation is **$0.5243 per turn** while a real Socratic turn costs
about **$0.00005** — roughly four orders of magnitude apart.

That gap is deliberate. Tightening it would need a token bound this project has
not established, and inventing one to make the arithmetic comfortable is exactly
what the earlier phases forbade. The consequence is practical: a session budget
must be sized against the reservation, not against expected spend.

## Integration point

`SocratesLiveOpenRouterAdapter` subclasses the repository's own
`BaseProviderAdapter` and implements `_produce_raw_text`. CED remains the
transition authority; the harness is a worker behind the existing seam, using the
repository's own `build_reasoning_system_prompt` so the experiment measures
Socrates as it is rather than a second prompt dialect.

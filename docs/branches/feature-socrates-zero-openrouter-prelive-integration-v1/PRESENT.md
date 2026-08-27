# PRESENT — feature/socrates-zero-openrouter-prelive-integration-v1

## State

- Branch: `feature/socrates-zero-openrouter-prelive-integration-v1`
- Source HEAD: `1be95cfdecd9628cdf2d1ea6abdcf66ba1aa88a6`
- Phase: **semantic experiment frozen; the authoritative run has NOT been made.**

## A superseded earlier run

An authoritative aggregate was run before the rulings arrived, producing artifact
`szorpreliveartifactv1_6ff594b3…`. The rulings then required semantic changes -
the pricing granularity audit, the tokenizer and output-bound contract
requirements, and fourteen further preflight probes - and this phase's own rule
is that a semantic change after an authoritative run invalidates that run.

That run is therefore **superseded**. Its artifacts and its result document are
preserved in history at `0ff79c9`; they are the honest record of what was
evaluated under the narrower case set. They have been removed from the working
tree so nothing stale is mistaken for current evidence.

## The correction that mattered

I previously reported P18 as JIT-reachable and its contract as READY. The
granularity audit the ruling demanded shows that was **wrong at the required
granularity**: the retained first-party endpoint record exposes only a broad
display provider name and an undocumented `tag`, so a price cannot be bound to
the exact request selector `azure/swedencentral`. P18 has a structural blocker,
not merely a freshness one.

## Completed

Integration contracts, safety and budget contracts with the rulings applied, 55
frozen cases (30 integration, 25 preflight), the deterministic evaluator, 99
focused tests, and the pre-authoritative freeze.

## Remaining

Exactly one authoritative offline evaluation, its replay, and the result
documentation. Awaiting authorization to run it.

## Next safe step

Run the single authoritative S6 aggregate.

Not pushed.

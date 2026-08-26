# Phase 8.5D-S Recovery Memory

## Permanent lineage

- Manifest v1 at `feature/socrates-zero-openrouter-wire-spec-evidence-v1`
  remains sealed and `FALSIFIED` because its one bounded downloader pass
  retained zero source bytes after six `NETWORK_ERROR` results.
- Manifest v2 starts from exact v1 HEAD
  `a37e6c0068e3132ca49128295a5ef8453f91592c`.
- No v1 file or sealed artifact is rewritten.

## Official evidence basis

The v2 evidence is pinned to `OpenRouterTeam/docs` commit
`4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db` and six exact Git blobs.
It establishes typed official wire facts and lossless mappings without an
OpenRouter credential or inference call.

## Critical honesty boundaries

- broad provider label != exact endpoint slug
- requested model != actual served model
- missing router metadata != proved cache hit
- optional `attempts[]` absence must remain distinct from an empty list
- unknown additive fields are non-authoritative
- P17/P18/P19 remain `NOT_ESTABLISHED`
- live pilot remains blocked

## Decision

The evidence layer earns only a new wire-mapping authorization gate. It does
not itself authorize a parser implementation or live call.

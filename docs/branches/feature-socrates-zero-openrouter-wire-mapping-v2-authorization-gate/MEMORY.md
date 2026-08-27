# MEMORY — feature/socrates-zero-openrouter-wire-mapping-v2-authorization-gate

Stable context. Not an action log.

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-provenance-boundary-v1`
- Source HEAD: `ae8b3ec17810deb0c8523c78a541d032994fb408` (published)
- v2r1 checkpoint: `0d09822048d4f7c34cf234342ec4c36ef3db0ead`
- Sealed v1 base: `a37e6c0068e3132ca49128295a5ef8453f91592c`

## Non-negotiable invariants

1. **This branch is a decision, not an implementation.** Documentation only. No
   parser, mapper, adapter, pilot, pricing lookup, token estimator, cost control,
   new Route Controls artifact or new authoritative aggregate.
2. **Parser authorization is not pilot authorization.** P17, P18 and P19 remain
   NOT_ESTABLISHED, so the live pilot remains NOT EARNED. Never conflate them.
3. **Request intent is not response identity.** The repository knows the endpoint
   it intends to request. Exact endpoint *response* identity is
   `UNAVAILABLE_BY_DOCUMENTED_CONTRACT` and must stay NOT_ESTABLISHED. Provider
   label is `HUMAN_DISPLAY_NAME` granularity and must never be promoted to
   endpoint identity.
4. **Absence is never evidence of a value.** Metadata absence on cache hit does
   not prove a cache hit; only `X-OpenRouter-Cache-Status` does. Missing fields
   are preserved as ABSENT, never synthesized.
5. **Nothing sealed is touched.** Manifest v1, Manifest v2r1, the Route Controls
   artifact and the provenance boundary are read-only here.

## Evidence base this decision rests on

Official repository `OpenRouterTeam/docs`, pinned commit
`4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db`, 6 retained sources.

| measure | value |
| --- | --- |
| typed facts | 35, all `DIRECTLY_DOCUMENTED` |
| lossless mappings | 12, all `IDENTITY` / `FAIL_CLOSED` / `PRESERVE_NON_AUTHORITATIVELY` |
| relationship assessments | 14 — 13 ESTABLISHED, 1 UNAVAILABLE_BY_DOCUMENTED_CONTRACT |
| assumption-based authoritative mappings | 0 |
| repository-convention authoritative mappings | 0 |
| manifest ID | `szorwirespecmanifestv2r1_a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15` |
| manifest file SHA-256 | `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb` |

The single documented-unavailable relationship is
`EXACT_ENDPOINT_RESPONSE_IDENTITY`. Its status is a positive finding, which is
why it does not block implementation: the mapper declares NOT_ESTABLISHED as a
constant rather than trying and failing to resolve it.

## Decision

**WIRE-MAPPING v2 IMPLEMENTATION EARNED**, authorizing exactly one bounded
attempt (Phase 8.5D-S5) under the parser boundary predeclared in
[PLAN.md](PLAN.md) and the canonical gate document.

## Environment

- Repository: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`
- Interpreter: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`
- `PYTHONPATH` must point at this repository root; the package is not installed.
- `.gitignore` ignores `*.md` and `*.json` wholesale; use `git add -f`.

See [PLAN.md](PLAN.md) and [PRESENT.md](PRESENT.md).

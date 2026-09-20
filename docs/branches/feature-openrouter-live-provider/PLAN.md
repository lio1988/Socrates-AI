# Branch: feature/openrouter-live-provider

## Success criterion

A strict OpenRouter provider can make one real opt-in call through the canonical provider adapter contract, return an existing `ProviderResponse`, reject model substitution, and leave offline behavior unchanged.

## Scope

- add OpenRouter adapter;
- add opt-in smoke entrypoint;
- add focused offline tests;
- preserve exact-model fail-closed behavior.

## Non-goals

- no CED redesign;
- no automatic fallback models;
- no default live networking;
- no secret persistence;
- no automatic provider-route selection.

## Ordered implementation steps

1. Implement adapter on the existing `BaseProviderAdapter` contract.
2. Pin the exact OpenRouter model ID.
3. Verify returned model ID and fail closed on mismatch.
4. Reuse existing move parser/validator.
5. Add live smoke entrypoint gated by environment variables.
6. Add focused offline tests for missing key, exact match, substitution, rate limit, and malformed content.

## Validation gates

- focused OpenRouter tests pass;
- existing dialogue tests remain green;
- compile/import checks pass;
- diff check clean;
- no secret committed.

## Stop conditions

Stop if integration requires changing CED authority, provider scoring semantics, or deterministic protocol identities.

## Completed

Implementation and focused test scaffolding added.

## Remaining/deferred

Local/full validation and optional real OpenRouter smoke with a user-supplied environment key.

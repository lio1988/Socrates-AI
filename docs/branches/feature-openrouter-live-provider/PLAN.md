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

### CANONICAL EXECUTION RESTORATION results

- critical H0 preservation matrix: `288 passed`;
- H0.5 contract and known-failure fixture integrity: `5 passed`;
- full `tests_dialogues`: `1591 passed`;
- repository-wide pytest: `1898 passed` (23 unrelated pre-existing warnings);
- `python -m compileall -q backend tests_dialogues`: passed;
- `git diff --check`: passed;
- representative three-model mocked OpenRouter session: ratified, all three exact
  models participated, every logical agent used exactly one physical seat, and
  exact-model receipts all verified.

## Stop conditions

Stop if integration requires changing CED authority, provider scoring semantics, or deterministic protocol identities.

## Completed

Implementation and focused test scaffolding added.

### CANONICAL EXECUTION RESTORATION

1. Freeze ranked physical adapter seats per session and bind logical agent IDs
   deterministically to those seats.
2. Route all registry phase, scoring, and deliberation-tree work through the
   stable binding; retain the existing explicit retry offset as the only
   failover exception.
3. Make OpenRouter implement the shared exact `model` metadata contract and
   resolve proven namespaced vendors without guessing unknown namespaces.
4. Use parsed `AgentMove.confidence` in downstream move-score, section-score,
   and ratification records.
5. Add focused regressions for stable routing, independent role rotation,
   deterministic/heterogeneous participation, exact metadata, and confidence
   values `0.13` and `0.91`.
6. Freeze the two observed failure mechanisms as offline evidence fixtures,
   without reconstructing clipped or unavailable provider output.
7. Freeze the H0.5 feature-preservation and non-duplicate-authority contract as
   documentation only. Do not start H1.

## Remaining/deferred

Optional real OpenRouter smoke with a user-supplied environment key. It was not
run during this offline restoration audit.

# Branch: feature/openrouter-live-provider

## Branch

`feature/openrouter-live-provider`

## Completed

- strict `OpenRouterProviderAdapter` added;
- exact requested model pinning;
- returned-model verification with fail-closed mismatch handling;
- environment-only API key;
- opt-in live smoke module;
- focused offline tests;
- branch documentation.

## Remaining/deferred

- run local focused/full validation after checkout;
- perform one real smoke only with an explicitly supplied `OPENROUTER_API_KEY` and exact `OPENROUTER_MODEL`.

## Changed files

- `backend/dialogues/openrouter_provider.py`
- `backend/dialogues/demo_openrouter.py`
- `tests_dialogues/test_openrouter_provider.py`
- branch docs

## Blockers

No code blocker known. Live smoke requires the operator's OpenRouter key and exact model ID.

## Worktree

Remote feature branch created from `main`; no merge to `main` performed.

## Next safe step

Clone/switch to this branch, install requirements, run focused and full tests, then execute the opt-in OpenRouter smoke.

## Status

Review/test branch; not merged to `main`.

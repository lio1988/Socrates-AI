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
- CANONICAL EXECUTION RESTORATION implementation and focused regressions:
  - stable logical-agent/provider/model binding with existing explicit failover;
  - exact OpenRouter model/vendor metadata;
  - typed parsed-move confidence propagation.

## Remaining/deferred

- perform one real smoke only with an explicitly supplied `OPENROUTER_API_KEY` and exact `OPENROUTER_MODEL`.

## CANONICAL EXECUTION RESTORATION validation

- critical H0 preservation matrix: `288 passed`;
- H0.5 contract and known-failure fixture integrity: `5 passed`;
- full dialogue suite: `1591 passed`;
- repository-wide suite: `1898 passed` with 23 unrelated existing warnings;
- compileall and diff check: passed;
- mocked OpenRouter runtime capture: three heterogeneous exact models
  participated, logical-agent seat bindings stayed stable, role assignments
  rotated, and exact-model receipts verified;
- no paid/live call, benchmark run, push, or PR action was performed.

## H0 / H0.5 frozen assets

- `docs/HYBRID_V1_H0_5_PRESERVATION_CONTRACT.md` — normative preservation,
  authority, determinism, failure, receipt, replay, observer, and staged-migration
  contract; no Hybrid implementation.
- `tests_dialogues/fixtures/known_failures/current_canonical_repeat_003.json` —
  correct minority lost to false consensus/high scoring/three ACCEPT votes and a
  false `well_supported` release; unavailable raw material remains explicit.
- `tests_dialogues/fixtures/known_failures/historical_challenger_live_001.json` —
  correct graph claims survived, but numeric CBE selected a false claim and the
  renderer combined incompatible claims; clipped material remains explicit.
- `tests_dialogues/test_known_failure_fixtures.py` — offline fixture integrity
  and independent ground-truth enumeration.

## Changed files

- `backend/dialogues/openrouter_provider.py`
- `backend/dialogues/demo_openrouter.py`
- `tests_dialogues/test_openrouter_provider.py`
- `backend/dialogues/ced.py`
- `backend/dialogues/reasoning_prompts.py`
- `tests_dialogues/test_canonical_execution_restoration.py`
- `tests_dialogues/test_identity_and_full_dialogue.py`
- `tests_dialogues/test_registry_council.py`
- `tests_dialogues/test_phase8c_registry_session.py`
- `tests_dialogues/test_known_failure_fixtures.py`
- `tests_dialogues/test_h0_preservation_contract.py`
- `tests_dialogues/fixtures/known_failures/`
- `docs/HYBRID_V1_H0_5_PRESERVATION_CONTRACT.md`
- branch docs

## Blockers

No code blocker known. Live smoke requires the operator's OpenRouter key and exact model ID.

## Worktree

Remote feature branch created from `main`; no merge to `main` performed.

## Next safe step

Clone/switch to this branch, install requirements, run focused and full tests, then execute the opt-in OpenRouter smoke.

## Status

Review/test branch; not merged to `main`.

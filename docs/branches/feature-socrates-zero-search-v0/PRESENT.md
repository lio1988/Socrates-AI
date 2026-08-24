# feature/socrates-zero-search-v0

## Current checkpoint

- Isolated branch created from `277ca2ec130ce120dba9c4d894a3c58138b25528`.
- Phase-0 audit completed across canonical CED, roles/history, IDs, providers,
  scores, Hybrid claims/evidence/contradictions/release, legacy graphs/Dung,
  synthesis/ratification, observers/events, receipts, learning, evaluation, and
  tests.
- ADR written with constitution/policy boundary, insertion seam, signal map,
  unchanged behavior, known gaps, and deferred roadmap.
- Runtime-inert Phase-1 contracts are implemented under
  `backend/dialogues/socrates_zero` and classified as search-only authority.
- Verification completed so far:
  - contracts plus authority: `30 passed`;
  - neighboring CED/Hybrid/provider/search regressions: `203 passed`;
  - full `tests_dialogues`: `2067 passed, 1 skipped`;
  - repository-wide `tests`, `tests_ced`, and `tests_dialogues`:
    `2362 passed, 1 skipped, 23 pre-existing deprecation/OpenAPI warnings`.
- The atomic branch checkpoint remains.

## Unchanged state

`SOCRATES_ZERO_ENABLED=false` maps to the existing behavior because Phase 1
does not read the variable or wire any experimental component. The existing
CED path remains the only path.

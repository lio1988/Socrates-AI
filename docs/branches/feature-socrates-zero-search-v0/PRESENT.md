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
- Implementation checkpoint: `8d6770b` (`feat: add SocratesZero search
  contracts v0`).

## Unchanged state

`SOCRATES_ZERO_ENABLED=false` maps to the existing behavior because Phase 1
does not read the variable or wire any experimental component. The existing
CED path remains the only path.

## Atomic milestone record

CHECKPOINT: Phase-0 audit and Phase-1 runtime-inert search contracts v0

STATUS: complete

TESTS:

- contracts plus authority: `30 passed`;
- neighboring regressions: `203 passed`;
- full dialogue suite: `2067 passed, 1 skipped`;
- repository-wide: `2362 passed, 1 skipped, 23 pre-existing warnings`;
- staged `git diff --check`: passed.

FILES CHANGED:

- SocratesZero contracts package;
- Hybrid authority classification;
- focused deterministic contract tests;
- architecture ADR;
- branch README, MEMORY, PLAN, and PRESENT.

COMMIT: `8d6770b`

KNOWN ISSUES:

- no canonical cross-provider token/cost meter;
- no general CED legal-action generator/executor or state projector;
- fixed rotation is preserved but not yet wrapped as `CurrentBaseline`;
- generic provider parsing does not yet enforce every role-specific content
  schema, including the presence of a grounded Socratic question;
- matched-budget SocratesZero benchmark episodes do not yet exist.

NEXT:

1. Formalize the unchanged fixed-rotation baseline adapter.
2. Build a read-only CED/Hybrid-to-`SearchState` projector.
3. Specify the first deterministic `legal_actions(state)` subset and validate
   it at the canonical CED execution boundary.

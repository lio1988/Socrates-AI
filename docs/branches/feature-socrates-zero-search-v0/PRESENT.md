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
- The isolated baseline acceptance and marker milestones were reviewed and
  integrated by cherry-pick. Provider success is now distinct from phase-aware
  Socratic acceptance, and the existing marker contract fails closed from one
  canonical task-kind predicate.
- Verification completed so far:
  - contracts plus authority: `30 passed`;
  - neighboring CED/Hybrid/provider/search regressions: `203 passed`;
  - full `tests_dialogues`: `2067 passed, 1 skipped`;
  - repository-wide `tests`, `tests_ced`, and `tests_dialogues`:
    `2362 passed, 1 skipped, 23 pre-existing deprecation/OpenAPI warnings`.
  - post-integration SocratesZero/acceptance/marker/firewall/policy bundle:
    `177 passed`;
  - post-integration repository-wide: `2392 passed, 1 skipped, 23 pre-existing
    deprecation/OpenAPI warnings`.
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
- role-specific content validation beyond the now-hardened Socratic contract
  remains partial;
- matched-budget SocratesZero benchmark episodes do not yet exist.

NEXT:

1. Formalize the unchanged fixed-rotation baseline adapter.
2. Build a read-only CED/Hybrid-to-`SearchState` projector.
3. Specify the first deterministic `legal_actions(state)` subset and validate
   it at the canonical CED execution boundary.

## Acceptance and marker integration milestone

DONE: integrated the isolated baseline hardening without conflicts. Opening and
follow-up Socratic moves now have deterministic, phase-aware content contracts;
rejected questions receive no accepted move identity and authorize no
Reflection. Deliberative moves require a canonical epistemic marker, while
evaluative moves reject a misplaced marker. Neither acceptance nor marker
handling creates a second epistemic authority.

TESTS:

- combined SocratesZero/acceptance/marker/firewall/policy: `177 passed`;
- repository-wide: `2392 passed, 1 skipped, 23 pre-existing warnings`;
- `git diff --check`: passed on the isolated marker milestone;
- no live external call was made.

FILES CHANGED:

- Socratic validation and CED acceptance boundary;
- provider-envelope marker validation and deterministic/canned fixtures;
- reasoning directive example and dialogue documentation;
- focused acceptance/marker tests and affected fixture suites;
- isolated-fix and SocratesZero branch checkpoints.

COMMITS:

- `c78c6ae` — Socratic acceptance implementation (cherry-picked from `6d352de`);
- `edfbd32` — acceptance checkpoint (cherry-picked from `25d5086`);
- `403a8a6` — marker hardening (cherry-picked from `5d248c3`);
- `b504417` — marker checkpoint (cherry-picked from `dcc8038`).

KNOWN ISSUES:

- the 23 warnings remain the pre-existing Pydantic `.dict()` deprecations and
  duplicate FastAPI operation IDs;
- no general legal-action generator/executor or state projector exists yet;
- no canonical cross-provider token/cost meter exists yet.

NEXT: implement the unchanged fixed-rotation baseline adapter and read-only
state projection as prerequisites for the first deterministic legal-action
generator.

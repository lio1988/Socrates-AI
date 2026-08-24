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
- The board-state/legal-moves milestone is complete:
  - canonical fixed-rotation task specs are explicit and reused by execution;
  - CED/Hybrid records project read-only into deterministic SearchState;
  - hard legal actions are deterministic, phase-aware, target-valid and bounded;
  - the fixed baseline is proven to remain inside the legal set;
  - Phase-2 projector/adapter/vocabulary/generator semantics are explicitly
    versioned and contradictory pre-COMPLETE final state fails closed;
  - search retains zero production execution authority.
- Phase 3A deterministic policy priors are complete:
  - heuristic v0 ranks only supplied legal actions from three public signals;
  - every adjustment is exposed by a structured reason code;
  - a `1e-6` exploration floor preserves every legal action;
  - uniform v0 provides the separate `1/N` research control;
  - neither policy has execution or epistemic authority.
- Phase 3B Value baselines are complete:
  - neutral v0 returns `0.0` for every structurally valid state;
  - heuristic v0 applies only capped unresolved/terminal penalties;
  - future outcomes and forbidden quality/consensus/provider/prose signals are
    ignored by construction and tested for immunity;
  - structured component audits are deterministic and receipt-linkable;
  - Value calls neither Policy nor Constitution and has no runtime authority.
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

## Board state and legal moves milestone

DONE: established SocratesZero's first board/rules/player foundation. The
canonical registry phase runner and `FixedRotationBaselineAdapter` consume the
same frozen task specs. A trusted CED-side bridge projects only recorded public
CED/Hybrid artifacts into immutable SearchState. `CEDSearchConstitution` emits
the initial deterministic 10-family legal vocabulary with hard Reflection,
follow-up, reconstruction, phase, target and terminal gates. The baseline
strategy produces an auditable receipt but executes nothing.

TESTS:

- SocratesZero contracts/baseline/projection/legal actions: `64 passed`;
- focused SocratesZero + acceptance/marker + CED rotation/identity/retry:
  `258 passed`;
- Hybrid authority plus SocratesZero after boundary correction: `75 passed`;
- full `tests_dialogues`: `2130 passed, 1 skipped`;
- repository-wide: `2437 passed, 1 skipped, 23 pre-existing warnings`;
- `git diff --check`: passed;
- no live external call was made.

FILES CHANGED:

- `backend/dialogues/ced.py` — canonical frozen task-spec extraction reused by
  existing registry execution;
- `backend/dialogues/ced_search_projection.py` — trusted read-only projection;
- `backend/dialogues/socrates_zero/{baseline,constitution,contracts}.py` and
  package exports;
- `backend/dialogues/hybrid_authority.py` — explicit trusted bridge authority;
- three focused SocratesZero test modules plus baseline integration tests;
- canonical ADR/technical docs and branch checkpoints.

COMMITS:

- `405c839` — fixed-rotation baseline extraction and strategy;
- `14326a1` — deterministic canonical SearchState projection;
- `dad0a8f` — deterministic CED hard legal actions;
- `95d19c3` — H8-preserving trusted projection boundary.
- `d0ba719` — explicit Phase-2 versions and contradictory-terminal hardening.

KNOWN ISSUES:

- no search action executor exists and no experimental choice controls CED;
- fixed task-spec equivalence currently covers registry deliberation from
  Opening through Synthesis; council ratification uses its separate path;
- provider observations remain absent from SearchState when no canonical exact
  semantic receipt exists; cross-provider token/cost metering is still absent;
- the legal vocabulary is intentionally initial, not a complete future action
  ontology;
- the 23 warnings remain pre-existing Pydantic `.dict()` deprecations and
  duplicate FastAPI operation IDs.

## Deterministic model-free policy prior milestone

DONE: implemented `HeuristicPolicyPrior` and `UniformPolicyPrior` behind the
existing async `PolicyPrior` contract. Input actions are schema/reference
validated, deduplicated, and canonically ordered, but Policy never calls
Constitution to re-decide legality. Heuristic v0 uses only unresolved
contradiction, unresolved question, and valid claim-target signals. Structured
audit records expose base weight, reason-coded deltas, final weight, and
normalized probability. No action is generated or executed.

TESTS:

- policy-specific: `13 passed`;
- full SocratesZero bundle: `77 passed`;
- focused SocratesZero + acceptance/marker + CED rotation/identity/retry:
  `271 passed`;
- Hybrid H8 authority plus SocratesZero: `88 passed`;
- full `tests_dialogues`: `2143 passed, 1 skipped`;
- repository-wide: `2450 passed, 1 skipped, 23 pre-existing warnings`;
- staged `git diff --check`: passed;
- no live external call was made.

FILES CHANGED:

- `backend/dialogues/socrates_zero/policy.py` — heuristic/uniform priors,
  canonical normalization, exploration floor, and structured audit records;
- `backend/dialogues/socrates_zero/__init__.py` — public runtime-inert exports;
- `tests_dialogues/test_socrates_zero_policy_prior.py` — policy invariants,
  rule controls, malformed-input and Constitution-separation tests;
- canonical ADR/technical reference and branch checkpoints.

COMMIT:

- `4ff3798` — deterministic heuristic and uniform PolicyPrior implementations.

KNOWN ISSUES:

- most current phase states have one legal macro-action, so v0 is informative
  mainly in Elenchus/Reflection states with targeted alternatives;
- Phase 2 exposes no VERIFY or evidence-seeking legal action, so v0 contains no
  fabricated verification/evidence preference;
- contradiction and objection references are digest-based and do not expose
  semantic target relationships to Policy;
- no matched evaluation yet establishes that heuristic v0 outperforms uniform;
- the 23 warnings remain pre-existing Pydantic `.dict()` deprecations and
  duplicate FastAPI operation IDs.

## Deterministic leakage-safe Value milestone

DONE: implemented `NeutralValueEstimator` and `HeuristicValueEstimator` behind
the existing async `ValueEstimator` protocol with range `[-1,+1]`. Neutral v0
returns `0.0`. Heuristic v0 is a conservative penalty-only baseline over
canonical unresolved contradictions/questions and terminal blocked/budget
status. Answer-ready completion and epistemic abstention remain neutral. Every
evaluation exposes stable reason-coded components, raw/bounded Value, canonical
refs, and a deterministic audit ID.

TESTS:

- Value-specific: `21 passed`;
- Policy-specific regression: `13 passed`;
- full SocratesZero bundle: `98 passed`;
- focused SocratesZero + acceptance/marker + CED rotation/identity/retry:
  `292 passed`;
- Hybrid H8 authority plus SocratesZero: `109 passed`;
- full `tests_dialogues`: `2164 passed, 1 skipped`;
- repository-wide: `2471 passed, 1 skipped, 23 pre-existing warnings`;
- staged `git diff --check`: passed;
- no live external call was made.

FILES CHANGED:

- `backend/dialogues/socrates_zero/value.py` — neutral/heuristic estimators,
  structural input validation, capped rules, audits, and deterministic hashes;
- `backend/dialogues/socrates_zero/__init__.py` — public runtime-inert exports;
- `tests_dialogues/test_socrates_zero_value_estimator.py` — contracts, bounds,
  monotonicity, terminal semantics, immunity, leakage and separation tests;
- canonical ADR/technical reference and branch checkpoints.

COMMIT:

- `cf5f4d0` — leakage-safe neutral and heuristic ValueEstimator baselines.

KNOWN ISSUES:

- SearchState exposes verification records as opaque digests, not inspectable
  verified/falsified/inconclusive outcomes, so v0 safely assigns no verification
  reward or penalty;
- resolved contradiction/question status is absent from projected collections,
  so v0 cannot reward canonical resolution without fabricating it;
- penalty families can represent related epistemic events and are intentionally
  small/capped because exact cross-record causal identity is unavailable;
- no matched evaluation yet shows heuristic Value outperforming Neutral Value;
- the 23 warnings remain pre-existing Pydantic `.dict()` deprecations and
  duplicate FastAPI operation IDs.

NEXT: Phase 3C deterministic strategy baselines — Greedy first, then
matched-budget Best-of-N — still with zero production authority.

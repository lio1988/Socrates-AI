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

- H2 quality/epistemic-support separation and all later governing Hybrid stages;
- any additional paid benchmark.

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

## H1 SHADOW IMPLEMENTATION

- append-only `HybridEpistemicLedger` with deterministic sequence, record ID,
  idempotency, hash-chain replay and immutable conflict refusal;
- explicit post-finalization `HybridShadowObserver`, disabled by default;
- no Hybrid field in canonical public or authority state;
- exact model provenance and digest-only content capture;
- capture failure isolated to a bounded non-authority diagnostic;
- 11 focused H1 tests passed;
- full dialogue suite: 1602 passed;
- repository-wide suite: 1909 passed with the same 23 pre-existing warnings;
- compileall and diff check passed.

One explicitly approved paid session, `hybrid_h1_level3_live_001`, used exactly
`openai/gpt-4.1-mini`, `openai/gpt-4o-mini`, and
`meta-llama/llama-3.3-70b-instruct`. All 72 provider tasks returned `ok`; move
score coverage was 24/26, section scores 29/30, and self-scoring violations were
zero. The answer order was correct, but `ratified_with_caveats` preserved two
logically invalid semantic caveats. H1 recorded 168 contiguous replay-verified
records with zero capture failures and did not alter the result. No rerun was
performed.

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
- `backend/dialogues/hybrid_shadow.py`
- `backend/dialogues/reasoning_prompts.py`
- `tests_dialogues/test_canonical_execution_restoration.py`
- `tests_dialogues/test_identity_and_full_dialogue.py`
- `tests_dialogues/test_registry_council.py`
- `tests_dialogues/test_phase8c_registry_session.py`
- `tests_dialogues/test_known_failure_fixtures.py`
- `tests_dialogues/test_h0_preservation_contract.py`
- `tests_dialogues/fixtures/known_failures/`
- `docs/HYBRID_V1_H0_5_PRESERVATION_CONTRACT.md`
- `docs/HYBRID_V1_H1_SHADOW_IMPLEMENTATION.md`
- `tests_dialogues/test_hybrid_shadow_h1.py`
- branch docs

## Blockers

No H1 blocker known. H2 is intentionally outside this approved scope.

## Worktree

Remote feature branch created from `main`; no merge to `main` performed.

## Next safe step

Review the H1 shadow diff and live evidence. Do not start H2 without explicit
approval.

## Status

Review/test branch; not merged to `main`.

## H2 QUALITY/SUPPORT SEPARATION

- `backend/dialogues/hybrid_support.py` computes a deterministic
  `EpistemicSupportAssessment` from canonical artifacts, off by default and
  non-authoritative;
- two additive record kinds append to the single existing H1 ledger:
  `session_support.assessed`, `move_support.assessed`;
- `docs/HYBRID_V1_H2_SUPPORT_SEPARATION.md` records the design, the measured
  justification and the boundary.

### H2 validation

- 12 focused H2 tests: passed;
- H0/H0.5/H1 preservation matrix: `26 passed`, unchanged;
- full `tests_dialogues`: `1614 passed`;
- `compileall`: clean;
- two live premise-true/premise-false councils confirmed the quality/support
  conflation in both runs (`factual_grounding` higher on the FALSE arm: 7.07 and
  6.93, against 6.78 and 6.41 on the TRUE arm).

### H2 finding — prerequisite for any governing stage

Live marker coverage is 7%–21%: between 79% and 93% of moves assert with no
epistemic marker at all, and every marker observed was `reasonable_hypothesis`.
`support_index` therefore cannot discriminate yet — its input is largely absent.
Raising marker emission is the prerequisite before H3 or any governing stage.

## MARKER EMISSION FIX (H2 prerequisite)

Two causes were found and fixed for the 7%-21% marker coverage H2 measured:

1. five deliberative task kinds received both "include an `epistemic_marker`
   field" and "EXACTLY these fields / do not add other top-level fields";
   models resolved the contradiction by dropping the marker. Each enumerated
   directive now carves the marker out explicitly;
2. the marker directive sat mid-prompt while the output contract — the last
   instruction read — never named it. Deliberative kinds now close on
   `DELIBERATIVE_RESPONSE_CONTRACT`, which does.

Evaluative kinds (`move_score`, `section_score`, ratification) never receive the
marker directive and were deliberately left on the plain contract.

### Measured effect (same two-arm live experiment, one run per stage)

| metric | baseline | after (1) | after (1)+(2) |
|---|---|---|---|
| coverage_ratio FALSE/TRUE | 0.214 / 0.071 | 0.214 / 0.286 | 0.500 / 0.500 |
| markers observed | 3 / 1 | 3 / 4 | 7 / 7 |
| distinct markers used | 1 | 3 | 2 |
| overconfidence violations | 0 / 0 | 0 / 1 | 1 / 2 |

Coverage is not solved: half of all moves still assert unmarked, and the
distribution remains dominated by `reasonable_hypothesis`. The band check now
fires, so marker/confidence consistency is exercised for the first time.

## H2 CORRECTION — numeric epistemic ranker removed

`support_index` averaged epistemic markers, so a council that stamped
`established_fact` on every move would have scored a perfect support figure:
self-description promoted to evidence. It was removed and not replaced by
another heuristic.

H2 now exposes two strictly separated planes. Support is categorical
(`UNSUPPORTED` / `UNRESOLVED`), names `basis_record_ids` and
`unresolved_record_ids`, and `AUTHORITATIVE_SUPPORT_INPUTS` is empty because
verification is H3+. `legacy_epistemic_status` is carried through unchanged for
comparison and is never an input to the Hybrid status.

Observed on one mock session: quality mean 7.744 crosses the canonical 7.5
threshold so the legacy path reports `well_supported`, while H2 reports
`unresolved` with an empty basis and two standing objections.

## MARKER EMISSION — synthesis gap closed

The carve-out form did not work. `synthesis_draft` measured 0/8 live: the
directive opened "EXACTLY these five string fields", showed an example with
five, and only then appended "also include the marker as the one permitted extra
field". Models stopped at five.

The marker is now a NAMED REQUIRED FIELD in all five enumerating directives —
listed, counted and present in the example — so there is no extra field to
resist. Applied uniformly to synthesis_draft, tree_revision,
lesson_distillation, process_review, lesson_relevance and lesson_consolidation.

Targeted live probe, three models x three attempts on `synthesis_draft`:

| | before | after |
|---|---|---|
| coverage | 0/8 = 0.000 | 7/9 = 0.778 |

One of the two misses was a provider timeout, not a marker failure; excluding it
the rate is 7/8. Distribution remains entirely `reasonable_hypothesis`: models
still avoid committing to `established_fact` or admitting
`unsubstantiated_claim`, which is a calibration observation for later stages and
not a contract defect.

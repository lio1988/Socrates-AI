# Socrates Epistemic Hybrid v1 — H2 Quality/Epistemic-Support Separation

H2 supplies the measure H1's own record names imply is missing. H1 classified the
existing seven-dimension peer score as a QUALITY score
(`move_quality_score.observed`); nothing measured epistemic SUPPORT.

## Why: measured, not assumed

Two live councils were run on the same downstream question — *how should
organisations design reporting hierarchies to prevent abuse?* — differing only in
whether the premise handed to them was true.

* **FALSE arm:** "The Stanford Prison Experiment demonstrated that ordinary
  people become cruel when placed in positions of institutional power."
  Not well supported: Le Texier (2019) archival work on coached guards,
  self-selection through an advertisement naming prison life, roughly a third of
  guards behaving abusively, and the BBC Prison Study replication failure.
* **TRUE arm:** "The Stanford Prison Experiment has been widely criticised on
  methodological grounds and its central claim is not well supported."

Peer-score means, two independent runs:

| dimension | FALSE (run 1 / run 2) | TRUE (run 1 / run 2) |
|---|---|---|
| `epistemic_value` | 7.79 / 7.68 | 7.59 / 7.44 |
| `factual_grounding` | 7.07 / 6.93 | 6.78 / 6.41 |
| `intellectual_honesty` | 8.29 / 8.43 | 8.41 / 8.48 |
| weighted overall | 7.58 / 7.51 | 7.42 / 7.27 |

The answer built on a discredited study scored **higher** on `factual_grounding`
in both runs. No dimension separated the arms by more than 0.52 on a 0..10 scale,
and the sign is consistently backwards. The dimensions track fluency and
structure. They are quality scores, and naming one of them `factual_grounding`
does not make it measure grounding.

## What H2 adds

`backend/dialogues/hybrid_support.py` computes an `EpistemicSupportAssessment`
from canonical artifacts only:

| field | meaning |
|---|---|
| `support_index` | mean support weight over MARKED moves; `None` when nothing was marked |
| `coverage_ratio` | share of moves carrying any epistemic marker |
| `unmarked_assertion_ratio` | share asserting with no marker at all |
| `overconfidence_violations` | confidence above the ceiling the move's own marker allows |
| `premise_scrutinised` | did any pressure-phase move both engage and challenge the question's assertions |
| `quality_mean` | carried alongside for contrast, never merged |

Support weights order the markers by the strength of the epistemic claim they
make: `established_fact` 1.0, `logical_inference` 0.8, `reasonable_hypothesis`
0.5, `open_uncertainty` 0.25, `unsubstantiated_claim` 0.0. These are not quality
weights — an `open_uncertainty` move can be excellent work and still supply
little support for a conclusion.

## Authority boundary

* additive and off by default — no orchestrator wiring, injected by a caller;
* non-authoritative — feeds nothing in scoring, assembly, ratification, release,
  `SessionState` or `FinalResponse`;
* no second authority — records append to the single existing H1 ledger under two
  additive kinds, `session_support.assessed` and `move_support.assessed`;
* deterministic — a pure function of canonical artifacts, no provider or network
  call, replayable and offline-testable;
* honest — `support_index` is `None`, never `0.0`, when nothing was marked.
  Missing data is not zero support, and CED never fabricates a missing measure.

## What H2 cannot do

A deterministic measure cannot know whether a claim is TRUE. H2 measures whether
the council **supported** its claims and whether it ever **examined** the
question's assertions. Truth adjudication is not claimed and is not in scope.

## First live result: the blocker H2 exposed

Running H2 over both arms:

| metric | FALSE | TRUE |
|---|---|---|
| `support_index` | 0.500 | 0.500 |
| `coverage_ratio` | 0.214 | 0.071 |
| `unmarked_assertion_ratio` | **0.786** | **0.929** |
| marker counts | `{reasonable_hypothesis: 3}` | `{reasonable_hypothesis: 1}` |

`support_index` did not separate the arms — because there was almost nothing to
compute it from. Between 79% and 93% of moves asserted with **no epistemic marker
at all**, and every marker that did appear was the same middling
`reasonable_hypothesis`.

This is the finding, not a failure of the measure. `EPISTEMIC_MARKER_DIRECTIVE`,
the `EpistemicMarker` vocabulary and `MARKER_CONFIDENCE_BANDS` all exist, and in
live runs the vocabulary is close to unused. No support measure can discriminate
while its input is absent. Raising marker emission is the prerequisite for a
support index that means anything, and it is the natural next step before any
stage is allowed to govern.

`premise_scrutinised` returned `True` in both arms. The heuristic is deliberately
conservative but has not been validated against a labelled set, so it should be
read as an indicator and not as evidence that scrutiny was adequate.

## Gate

* 12 focused H2 tests, offline, no provider or network call;
* H0/H0.5/H1 preservation matrix: 26 passed, unchanged;
* full `tests_dialogues`: 1614 passed;
* `compileall`: clean;
* canonical `SessionState` and `FinalResponse` byte-identical after capture,
  asserted directly in `test_capture_is_idempotent_and_does_not_mutate_canonical_state`.

## Stop boundary

H2 is a measurement layer only. It governs nothing. H3 objection lifecycle, claim
authority, compatibility gates and any governing release change remain
unimplemented and require separate approval.

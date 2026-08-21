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

Two planes, strictly separated.

**Quality plane** — how well the council argued. Peer scores, the leaderboard,
and `legacy_epistemic_status`: the canonical `_epistemic_hint` result, carried
through unchanged. All visible; all authoritative over nothing.

**Epistemic-support plane** — whether a conclusion is supported. Categorical,
never numeric, and every status names its basis:

| field | meaning |
|---|---|
| `hybrid_h2_epistemic_status` | `UNSUPPORTED` or `UNRESOLVED` — the only honest states available |
| `basis_record_ids` | authoritative records the status rests on; empty until H3+ |
| `unresolved_record_ids` | challenges raised and verified by nothing |
| `advisory_metadata_count` | markers and confidence readings seen |
| `quality_signal_count` | peer scores seen |

## Input classification

`SUPPORT_INPUT_CLASSIFICATION` names every input and the only way it may be used.

| input | class |
|---|---|
| `epistemic_marker`, `move_confidence` | ADVISORY METADATA |
| `peer_quality_score`, `section_quality_score`, `epistemic_leaderboard` | QUALITY SIGNAL |
| `ratification_verdict`, `council_agreement` | QUALITY SIGNAL |
| `legacy_epistemic_status` | QUALITY SIGNAL — a score threshold wearing an epistemic name |
| `elenchus_objection`, `ratification_objection` | UNRESOLVED |
| *(nothing)* | AUTHORITATIVE SUPPORT |

`AUTHORITATIVE_SUPPORT_INPUTS` is empty and a test pins it that way. Verification
and evidence promotion are H3+.

## Why there is no number

An earlier revision computed `support_index` by averaging epistemic markers. That
was wrong. A marker is the model's OWN label for its OWN claim, so a council that
stamped `established_fact` on everything would have scored a perfect "support"
figure — self-description promoted to evidence. It was removed and NOT replaced
with another heuristic. Not markers, not confidence, not quality, not agreement
or corroboration counts or ratifier popularity.

## The two planes disagree, which is the point

A live mock session produced:

```json
{"hybrid_h2_epistemic_status": "unresolved",
 "basis_record_ids": [],
 "unresolved_record_ids": ["move_8afb0563d5bf", "move_fe49c0e477cd"],
 "quality_mean": 7.744339,
 "legacy_epistemic_status": "well_supported"}
```

Mean quality 7.744 crosses the canonical 7.5 threshold, so the legacy path calls
it `well_supported`. H2 calls it `unresolved`: nothing authoritative supports it
and two objections stand unanswered. Both are reported; neither is merged.

## Gate

* 26 focused H2 tests, offline, no provider or network call;
* 56 marker-contract tests; the audit reports 0 conflicts over all 17 task kinds;
* H0/H0.5 preservation gate 15 passed and H1 ledger/replay 11 passed, unchanged;
* full `tests_dialogues`: 1684 passed; repository-wide: 1991 passed;
* `compileall` clean; `git diff --check` clean;
* canonical `SessionState` and `FinalResponse` byte-identical after capture,
  asserted directly in `test_capture_is_idempotent_and_does_not_mutate_canonical_state`.

## Stop boundary

H2 is a measurement layer only. It governs nothing. H3 objection lifecycle, claim
authority, compatibility gates and any governing release change remain
unimplemented and require separate approval.

# SocratesZero Value v1 Evaluation Freeze

## Status

This is the repaired pre-result freeze for the Phase 7 one-factor experiment.
The originally committed `/v0` case lineage is preserved in Git but invalidated:
an estimator metamorphic unit test accidentally evaluated holdout pair 033
before the harness chronology was frozen. No aggregate metrics or artifact were
produced, but scientific isolation requires a new version rather than a silent
repair.

The authoritative `/v1` lineage uses new neutral state identities and replaces
the exposed pair-033 recipe. Estimator rules, weights, ordering, thresholds, and
metric semantics did not change. No Value result on `/v1` existed when this
recovery freeze was committed.

```text
estimator: heuristic-value-estimator/v1
case-set: socrateszero-value-v1-eval-case-set/v1
harness: socrateszero-value-v1-eval-harness/v0
development: 18 pairs
holdout: 27 pairs
total: 45 pairs
```

Case-set semantic digest:

```text
szvaluev1cases_5fad13cb294223cf76bcc7783bed1a5ac0bed56b22b4f5aa6ba73edaefbd18e3
```

Canonical case-set JSON SHA-256:

```text
22122913601c9fc39265fbdc44a3f3cec02030333c7317e971db42fb3a436afd
```

Frozen rule semantic ID and development/holdout split hash:

```text
szvaluev1rules_3d6d50dbb1a70a3d7d7d70c7b12835bc3f9a39cbcde74838022fc4ad3c6a1826
f32a61ae9fd5ba1ca43d67f59f7adc455302947cfa89c12de59ad06f82bf3d3b
```

## Frozen categories

Exactly two development and three holdout pairs exist in each category:

1. canonical support-state distinctions that should help;
2. v1 signals irrelevant to ranking;
3. misleading lifecycle closure;
4. duplicate or derived representations of one governing event;
5. terminal support only;
6. intermediate verification and assessment states;
7. v0/v1 equivalence;
8. resolution that may only remove a penalty;
9. evidence, verification, claim, or lifecycle count inflation.

## Canonical origin and label firewall

Every state is a neutral source recipe. The builder constructs real
`SessionState`, `HybridEpistemicState`, claim/evidence/verification/lifecycle
records, optional commitments/aporia, and then calls
`project_search_state_v1()`. No case directly constructs SearchState v1 or
assigns `SupportState`.

Ordering labels live only on the evaluator-side pair. The estimator view
contains only the two projected states. Neutral blueprint, session, claim,
record, contradiction, objection, verification, commitment, and aporia IDs are
derived without reading the ordering label. Adversarial relabeling therefore
cannot alter any estimator-facing state or canonical source identity.

## Frozen metrics and thresholds

Primary metrics are ordered-pair accuracy, required-tie accuracy, directional
errors, ordered ties, and bounded ranking regret.

All of these gates are conjunctive:

- holdout ordered accuracy at least `0.80`;
- improvement over actual Value v0 at least `0.20`;
- nonterminal holdout ordered accuracy at least `0.80` and improvement at least
  `0.20` independently;
- required-tie accuracy exactly `1.0` on the frozen guardrails;
- zero forbidden inputs, positive components, source mutations, missing source
  records, and receipt/source mismatches.

The secondary BestOfN threshold is frozen at `0.10`, but the secondary test is
locked unless every primary gate passes.

The one-shot primary runner is
`scripts/run_socrates_zero_value_v1_evaluation.py`. It builds development and
holdout runs, classifies every conjunctive gate, performs an independent
semantic and byte replay in memory, and refuses to overwrite a different
artifact. Its frozen destination is
`docs/branches/feature-socrates-zero-heuristic-value-v1/artifacts/socrateszero_value_v1_primary_v0.json`.

## Chronology and invalidation

The case set, split, labels, metric meanings, thresholds, and Value semantic
constants must be committed before the first holdout execution. Development may
detect contract implementation bugs, but cannot tune the frozen semantics.

After the first valid holdout result, any change to a case, split, category,
label, metric, threshold, rule family, coefficient, or support ordering requires
new semantic IDs and a fresh holdout. The original artifact must be preserved.

## Secondary BestOfN freeze

The primary gate passed and unlocked a separately frozen secondary case set:

```text
case-set: socrateszero-value-v1-bestofn-case-set/v0
harness:  socrateszero-value-v1-bestofn-harness/v0
ordered quartets: 7
guardrail quartets: 4
```

Semantic digest and canonical JSON SHA-256:

```text
szvaluev1bestofncases_22a0659a07be21d83c17d566c6fe5e3fe66c6fea6830b79a2535495b0090d667
e18aa8ff8ac371fd5857dbc7b7c47058eac223bf76194acbef7c685252ed5f53
```

Each root is built from canonical sources and exposes exactly four actions from
`CEDSearchConstitution/v0`. Each successor starts from a real canonical v1
projection; only navigation metadata needed by the frozen BestOfN contract is
adapted. Ordered cases use the seven already-frozen primary ordered holdout
pairs plus two canonically worse controls. Four separate guardrails cover
closure, duplicate-derived signals, equivalence, and count inflation. No
BestOfN result existed when this secondary case set was committed.

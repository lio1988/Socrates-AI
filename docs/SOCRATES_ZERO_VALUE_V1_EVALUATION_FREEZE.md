# SocratesZero Value v1 Evaluation Freeze

## Status

This is the pre-result freeze for the Phase 7 one-factor experiment. No Value
v1 development or holdout result existed when this case lineage was committed.

```text
estimator: heuristic-value-estimator/v1
case-set: socrateszero-value-v1-eval-case-set/v0
harness: socrateszero-value-v1-eval-harness/v0
development: 18 pairs
holdout: 27 pairs
total: 45 pairs
```

Case-set semantic digest:

```text
szvaluev1cases_ef483e920f55d5bbf6385e2e6646ce579a27babf190eda467bdcf5c03c8a7b5e
```

Canonical case-set JSON SHA-256:

```text
e90a8974f0bc359d02d3433b4df25fe96cfe59c43d1d2106fae76d43a74e25b8
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

## Chronology and invalidation

The case set, split, labels, metric meanings, thresholds, and Value semantic
constants must be committed before the first holdout execution. Development may
detect contract implementation bugs, but cannot tune the frozen semantics.

After the first valid holdout result, any change to a case, split, category,
label, metric, threshold, rule family, coefficient, or support ordering requires
new semantic IDs and a fresh holdout. The original artifact must be preserved.

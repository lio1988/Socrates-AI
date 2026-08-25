# SocratesZero Phase 7 — Deterministic HeuristicValueEstimator v1

## Executive result

Phase 7 tested exactly one pre-registered hypothesis: whether the worst active
canonical governing `SupportState`, used once as a penalty-only readiness
deficit, improves lawful current-state ranking over Value v0 without rewarding
support, closure, evidence volume, verification volume, or duplicated signals.

Both gates passed:

```text
PRIMARY:   VALUE V1 HYPOTHESIS PASSED
SECONDARY: VALUE V1 BESTOFN GATE PASSED
```

This establishes deterministic discrimination on the frozen structural cases
and matched one-ply selection utility in the new offline experiment. It does not
establish production, real-model, external-world, learned-Value, or RL utility.

## Exact starting point and branch

```text
base branch: feature/socrates-zero-canonical-observability-v1
base commit: 64f37471f4fb3357375b44f7b5eeb3341964c5a1
work branch: feature/socrates-zero-heuristic-value-v1
```

The input and projection contracts remain:

```text
socrates.zero.search-state/v1
ced-search-state-projection/v1
```

Value v0, SearchState/projection v0 and v1, Policy v0, Greedy v0, BestOfN v0,
PUCT v0, legal vocabulary, CED, Hybrid, and the Phase 5 artifact were not
modified.

## Scientific chronology and invalidated lineage

The estimator rules and initial `/v0` case set were frozen before estimator
implementation. During implementation testing, one metamorphic unit test
accidentally evaluated frozen holdout pair 033 before the evaluation harness
chronology had been committed. It produced no aggregate metrics or artifact,
but it was still a comparative holdout observation.

The branch therefore did not silently continue. The initial
`socrateszero-value-v1-eval-case-set/v0` lineage remains preserved in Git and is
explicitly invalidated. No rule, coefficient, support ordering, threshold, or
metric was tuned. A separate recovery lineage was committed before any Value
result on its identities:

```text
authoritative case set: socrateszero-value-v1-eval-case-set/v1
freeze commit:          95f7e6b
case-set digest:        szvaluev1cases_5fad13cb294223cf76bcc7783bed1a5ac0bed56b22b4f5aa6ba73edaefbd18e3
canonical JSON SHA:     22122913601c9fc39265fbdc44a3f3cec02030333c7317e971db42fb3a436afd
```

The recovery uses new neutral state identities and replaces the exposed pair
033 recipe. Human blinding is not claimed; chronological isolation and the
absence of semantic tuning are the controls.

## Estimator contract

```text
estimator ID: heuristic-value-estimator/v1
base:         0.0
range:        [-1.0,+1.0]
shape:        penalty-only
authority:    advisory/read-only
```

The estimator lives on the trusted CED side in
`backend/dialogues/ced_search_value_v1.py`. The runtime-inert
`backend/dialogues/socrates_zero` package still imports no Hybrid authority.
The estimator requires `SearchStateV1`; a v0 `SearchState` fails closed.

### Frozen directional rules

| Reason | Contribution |
|---|---:|
| `active_claim_falsified` | `-0.20` |
| `active_claim_external_evidence_required` | `-0.12` |
| `active_claim_unresolved` | `-0.08` |
| `active_claim_unsupported` | `-0.05` |
| `socratic_remainder_open` | `-0.05` maximum, once per state |
| `terminal_blocked` | `-0.20` |
| `terminal_budget_exhausted` | `-0.10` |

Rule semantic ID:

```text
szvaluev1rules_3d6d50dbb1a70a3d7d7d70c7b12835bc3f9a39cbcde74838022fc4ad3c6a1826
```

`SUPPORTED` has no numeric rule and contributes no positive reward. It is the
absence of a claim-readiness penalty.

## Active claim and precedence semantics

Active Hybrid claims remain the non-superseded `ClaimRecord` values already
projected into `base_state.active_claims`. Value intersects those IDs with the
governing v1 assessments. Commitment-only active IDs receive no invented
assessment.

Among active assessed claims, the estimator selects one most-negative frozen
contribution. Equal deficits select the lexically lowest canonical claim ID for
audit provenance only. Claim count, insertion order, supported claims, and
record count cannot change the numeric result while the worst state is stable.

For nonterminal states an optional Socratic remainder component uses exactly:

```text
base_state.unresolved_questions - canonical objection IDs
```

It is capped once at `-0.05`; no question-resolution lifecycle is invented.

For terminal states, all claim and remainder components are suppressed.
Blocked and budget-exhausted use only the approved terminal component;
answer-ready and abstained remain neutral audits.

## Double-count and reward-farming firewall

Evidence, verification, objection, contradiction, semantic digest, source ID,
method, class, result, lifecycle closure, and collection counts never add an
independent directional component. Related records are retained only as
structured suppressed provenance behind the selected governing assessment.

Explicit tests prove invariance under:

- extra supported claims and claim splitting;
- additional supporting/weak/model-assertion evidence;
- repeated deterministic or model-produced verification records;
- multiple open or rejected objections;
- dismissed contradictions and lifecycle closure;
- duplicated/derived representations of the same governing state.

Resolution may remove an applicable open penalty. It cannot create a bonus.

## Audit receipt and numeric safety

Each result records estimator/schema/projection/state/base-state IDs, selected
support state, canonical claim, assessment reference and digest, reason and
components, suppressed source family/ID/digest links, terminal suppression,
raw/bounded values, and a canonical SHA-256 receipt hash.

The estimator revalidates its immutable input and fails closed on duplicate or
invalid assessments, invalid support states, dangling/cross-claim source
ownership, malformed eligibility, missing digests, nonfinite coefficients,
positive coefficients, and unapproved rule families. It does not mutate the
projection or any CED/Hybrid source.

## Primary evaluation

```text
harness:    socrateszero-value-v1-eval-harness/v0
split hash: f32a61ae9fd5ba1ca43d67f59f7adc455302947cfa89c12de59ad06f82bf3d3b
development pairs: 18
holdout pairs:     27
categories:         9
```

Exactly two development and three holdout pairs exist per category. Every state
is reconstructed from a real `SessionState`, real Hybrid records, optional
commitment/aporia records, and `project_search_state_v1()`. No test authors a
convenient `SupportState` directly. Ordering labels remain evaluator-only and
are applied after both Value calls return.

### Metrics

- Ordered accuracy counts only strict correct rankings; an ordered tie is
  separate and incorrect.
- A directional error is a strict inversion.
- Required-tie accuracy requires exact numeric equality.
- Ranking loss is `0` for correct, half the frozen weight for an ordered tie,
  and the full weight for an inversion or required-tie direction.

### Development result

| Metric | Value v0 | Value v1 |
|---|---:|---:|
| ordered accuracy | `1/5 = 20%` | `5/5 = 100%` |
| required ties | `12/13 = 92.31%` | `13/13 = 100%` |
| ordered ties | `4` | `0` |
| directional errors | `0` | `0` |
| ranking loss | `3.0` | `0.0` |

No semantic tuning followed development inspection.

### Authoritative holdout result

| Metric | Value v0 | Value v1 |
|---|---:|---:|
| ordered accuracy | `2/7 = 28.57%` | `7/7 = 100%` |
| improvement | — | `+71.43pp` |
| nonterminal ordered accuracy | `2/7 = 28.57%` | `7/7 = 100%` |
| nonterminal improvement | — | `+71.43pp` |
| required ties | `16/20 = 80%` | `20/20 = 100%` |
| directional errors | `0` | `0` |
| ordered ties | `5` | `0` |
| ranking loss | `6.5` | `0.0` |

The holdout contains 24 fully nonterminal pairs and three terminal-control
pairs. There are no ordered terminal pairs, so terminal labels cannot carry the
ranking result.

All hard-safety counts are zero:

```text
forbidden inputs:       0
positive components:   0
mutations:              0
missing source records: 0
receipt mismatches:     0
```

Primary artifact:

```text
ID:     szvaluev1artifact_803646dbfff5a0449309bf4690ddcc8b6e374fe80ab5826d5fc56c749dc27e49
SHA256: d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca
```

It replays with semantic equality, artifact-ID equality, and byte identity.

## Secondary matched BestOfN gate

The primary pass unlocked a separate frozen search case set:

```text
case set: socrateszero-value-v1-bestofn-case-set/v0
harness:  socrateszero-value-v1-bestofn-harness/v0
digest:   szvaluev1bestofncases_22a0659a07be21d83c17d566c6fe5e3fe66c6fea6830b79a2535495b0090d667
SHA256:   e18aa8ff8ac371fd5857dbc7b7c47058eac223bf76194acbef7c685252ed5f53
```

The one-factor arms were:

```text
BestOfNStrategy/v0
UniformPolicyPrior/v0
N = 4
depth = 1
matched successor budget = 4
Value v0  versus  Value v1
```

Seven ordered quartets measure selection accuracy. Four additional guardrail
quartets cover closure, duplicate-derived signals, equivalence, and count
inflation. Roots use the real `CEDSearchConstitution/v0` and exactly four legal
actions. Successor observations originate from canonical v1 projections; a
navigation-only adapter adds the parent/depth/branch-usage fields required by
the unchanged BestOfN v0 contract.

| Metric | Value v0 | Value v1 |
|---|---:|---:|
| selection accuracy | `2/7 = 28.57%` | `7/7 = 100%` |
| improvement | — | `+71.43pp` |

Regression counters:

```text
guardrail regression:            0
budget-usage regression:         0
successor-accounting regression: 0
new failures:                    0
```

Every arm used exactly five nodes, four expansions, depth one, and zero model
or tool calls.

Secondary artifact:

```text
ID:     szvaluev1bestofnartifact_c154689cd122f5f7dd68da5d7b31c34b26d049233e6425d3758f56491b11522d
SHA256: 86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637
```

It also replays semantically and byte-for-byte.

## Compatibility, authority, and verification

The Phase 5 normalized artifact remains:

```text
21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c
```

Focused results:

- Value v1: `77 passed`;
- Value v0: `21 passed`;
- Search contracts v0: `19 passed`;
- projection v0: `11 passed`;
- canonical observability/projection v1: `17 passed`;
- Policy prior: `13 passed`;
- Greedy: `27 passed`;
- BestOfN: `24 passed`;
- PUCT: `53 passed`;
- Phase 5 evaluation integrity: `37 passed`;
- SocratesZero bundle: `333 passed`;
- Hybrid H8 + SocratesZero: `344 passed`;
- expanded focused CED/Socratic/role/marker/retry: `252 passed`;
- `tests_dialogues`: `2399 passed, 1 skipped`;
- repository-wide: `2706 passed, 1 skipped, 23 pre-existing warnings`.

No provider, model, network, shadow-orchestration, or live API call occurred.
Value remains advisory and cannot create or change evidence, verification,
assessment, support, lifecycle, legality, ratification, release, or CED/Hybrid
state.

## What Phase 7 proves

- The newly visible governing readiness distinction can lawfully reduce v0
  aliasing on the pre-registered canonical structural holdout.
- The result is not terminal-driven and satisfies every reward-farming,
  provenance, mutation, and receipt guardrail.
- Unchanged one-ply BestOfN with Uniform Policy can use the new discrimination
  on the separately frozen offline successor quartets.

## What Phase 7 does not prove

- generalization to real model-generated dialogue states;
- external-world factual correctness or truth probability;
- real counterfactual successor fidelity;
- production quality improvement;
- multi-ply planning or PUCT benefit;
- learned targets, learned Value, Policy learning, or RL readiness.

## Next decision

Stop. Both gates passing earns a new architecture decision gate, not automatic
implementation. That gate must choose and separately authorize whether to
study read-only real counterfactual shadow collection or a safe canonical
successor environment. Phase 7 does not choose between them. Learned Value and
RL remain not earned.

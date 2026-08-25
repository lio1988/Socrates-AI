# SocratesZero Phase 5 — Frozen Search-Kernel Evaluation

Status: complete, deterministic, offline, and runtime-inert

Claim scope: `SEARCH_KERNEL_EVALUATION`

Machine-readable result:
[`socrateszero_search_kernel_benchmark_v0.json`](branches/feature-socrates-zero-search-v0/artifacts/socrateszero_search_kernel_benchmark_v0.json)

## What this evaluates

Phase 5 compares frozen `GreedyStrategy`, `BestOfNStrategy`, and
`PUCTStrategy` from the same immutable root state, hard-legal actions, Policy,
Value, deterministic one-ply successor fixture, and explicit budget. It does
not run CED orchestration, dispatch a provider, execute a selected action, or
measure end-to-end dialogue quality.

Current PUCT is safe only at relative depth one. It adaptively repeats real
root-successor observations; it is not deep multi-step planning.

The fixed CED rotation remains named as metadata
(`ced-fixed-rotation-adapter/v0`) but is not forced into a false
resource-equivalent kernel comparison.

## Frozen versions and cases

- harness: `socrateszero-search-kernel-eval-harness/v0`;
- case set: `socrateszero-search-kernel-case-set/v0`;
- successor fixture: `socrateszero-search-kernel-successor/v0`;
- projection: `socrateszero-search-kernel-fixture-projection/v0`;
- strategies: `greedy-strategy/v0`, `best-of-n-strategy/v0`,
  `puct-strategy/v0`;
- policies: `uniform-policy-prior/v0`, `heuristic-policy-prior/v0`;
- values: `neutral-value-estimator/v0`,
  `heuristic-value-estimator/v0`;
- Best-of-N: `N=4`; PUCT: `c_puct=1.0`, safe relative depth `1`;
- budgets: `matched-successor-budget/v0/{1,2,4,8}`.

The case set contains 20 deterministic cases, exactly two in each category:
Policy correct, misleading Policy, Best-of-N sufficient, selective-budget
advantage, flat Value, informative heuristic Value, uninformative Value,
budget exhaustion, single legal move, and exact ties. The distribution and
budgets were committed before the first comparative execution.

## Firewall, isolation, and accounting

Ground truth exists only in `EvaluationCase` on the evaluator side. Strategy
inputs contain no outcome, optimum, case/category label, or label-derived case
identifier. Before the first benchmark run, two firewall defects were found
and separately fixed: readable case/category action labels and a case hash that
depended on ground truth. All prior results were absent, so no result required
invalidation.

Every strategy receives fresh frozen inputs. The harness checks root equality
before/after each run, and forward versus reverse strategy order must produce
identical results. An adversarial strategy recursively inspects the supplied
API object graph and cannot find benchmark labels. A second adversarial
strategy attempts one successor call beyond the cap; the independently
accounting successor rejects it and the harness retains a visible
`STRATEGY_FAILURE` rather than trusting a receipt.

Resource dimensions remain separate:

```text
successor_evaluations, policy_evaluations, value_evaluations,
nodes, expansions, model_calls, tool_calls, tokens,
cost_microusd, wall_time_ms, max_depth_observed
```

One successful fixture observation consumes one node and one expansion. The
root is pre-existing and excluded from reported deltas. Core evaluation uses
zero providers, tools, tokens, cost, and measured wall-clock budget. The
evaluator-only Policy-rank scoring call is not strategy compute.

## Scoring and missing data

Each fixture outcome lies in `[-1,+1]`. Regret is:

```text
optimal outcome value - selected outcome value
```

so per-case regret lies in `[0,2]`. Tied maximum outcomes are all correct;
the minimum optimal action ID is retained as the canonical diagnostic tie.

Statuses are explicit: `COMPLETED`, `BUDGET_EXHAUSTED`, `NOT_EVALUABLE`,
`MISSING_COUNTERFACTUAL`, `INVALID_FIXTURE`, and `STRATEGY_FAILURE`. Aggregate
records separately retain total, evaluable, completed, failed, and
not-evaluable denominators. Missing/failed data is never scored as zero.

The two inspected saved traces contain only historical paths or clipped/digest
summaries and lack alternative-action outcomes. They are therefore reported as
two `MISSING_COUNTERFACTUAL` observations and zero honest replay cases. No
counterfactual was generated or guessed.

## Frozen result

Artifact ID:
`szevalartifact_dc795fdef6b64e56b808b990fedd764def7c6e1858d178d29c26aa3280ede710`

Normalized JSON SHA-256:
`21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`

All 11 configurations completed all 20 deterministic cases with zero failed
or excluded cases. PUCT's `BUDGET_EXHAUSTED` status means it legitimately used
its exact declared simulation cap; it is an evaluable result, not a failure.

### Primary matched comparison

Policy and Value are held at heuristic v0; Best-of-N and PUCT share maximum
four successor observations per case.

| Strategy | Correct | Accuracy | Total regret | Successors | Policy | Value | Nodes | Expansions | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Greedy | 9/20 | 45% | 11.55 | 0 | 20 | 20 | 0 | 0 | 0 |
| BestOfN-4 | 15/20 | 75% | 4.80 | 62 | 20 | 62 | 62 | 62 | 0 |
| PUCT-4 | 15/20 | 75% | 4.55 | 80 | 20 | 80 | 80 | 80 | 0 |

BestOfN and PUCT select equal-outcome actions on 18/20 paired cases. PUCT wins
`selective_budget_advantage_01` by `0.80`; BestOfN wins
`selective_budget_advantage_02` by `0.55`. Thus PUCT-4 has 0.25 less aggregate
regret, while BestOfN-4 uses 18 fewer observations. Neither dominates the
other.

### Category correctness at matched settings

| Category (2 cases each) | Greedy | BestOfN-4 | PUCT-4 |
|---|---:|---:|---:|
| Policy correct | 2 | 2 | 2 |
| Misleading Policy | 0 | 2 | 2 |
| Best-of-N sufficient | 1 | 2 | 2 |
| Selective-budget advantage | 1 | 1 | 1 |
| Flat Value | 1 | 1 | 1 |
| Heuristic Value informative | 0 | 2 | 2 |
| Value uninformative | 0 | 0 | 0 |
| Budget exhaustion | 0 | 1 | 1 |
| Single legal move | 2 | 2 | 2 |
| Exact ties | 2 | 2 | 2 |

Search earns clear fixture value on misleading-Policy and informative-Value
cases, but spends compute without benefit on Policy-correct, single-move, and
tie cases. Neither search method solves Value-uninformative cases.

### Frozen PUCT budget sweep

| PUCT budget | Correct | Total regret | Successors | Nodes/expansions |
|---:|---:|---:|---:|---:|
| 1 | 9/20 | 11.55 | 20 | 20/20 |
| 2 | 12/20 | 7.75 | 40 | 40/40 |
| 4 | 15/20 | 4.55 | 80 | 80/80 |
| 8 | 12/20 | 7.75 | 160 | 160/160 |

Quality is not monotone in additional depth-1 PUCT observations: budget 8 is
worse than budget 4 and equal in quality to budget 2 at four times its compute.
This result is preserved; no `c_puct`, case, Policy, Value, or budget tuning was
performed after inspection.

### One-factor ablations

With Neutral Value, Uniform Policy beats Heuristic Policy by one case for both
Greedy and PUCT:

| Controlled comparison | Correct | Total regret | Successors |
|---|---:|---:|---:|
| Greedy + Uniform + Neutral | 10/20 | 9.25 | 0 |
| Greedy + Heuristic + Neutral | 9/20 | 11.55 | 0 |
| PUCT-4 + Uniform + Neutral | 10/20 | 9.25 | 80 |
| PUCT-4 + Heuristic + Neutral | 9/20 | 11.55 | 80 |

Holding Heuristic Policy fixed, Heuristic Value materially helps the search
strategies but cannot change Greedy's Policy-only selection:

| Controlled comparison | Neutral Value | Heuristic Value |
|---|---:|---:|
| Greedy correctness / regret | 9 / 11.55 | 9 / 11.55 |
| BestOfN-4 correctness / regret | 9 / 11.75 | 15 / 4.80 |
| PUCT-4 correctness / regret | 9 / 11.55 | 15 / 4.55 |

### Pareto interpretation

Within the controlled Heuristic-Policy/Heuristic-Value strategy-and-budget
comparison, non-dominated points are Greedy, PUCT-2, BestOfN-4, and PUCT-4.
PUCT-1 is dominated by Greedy; PUCT-8 is dominated by PUCT-2. Across the full
ablation matrix, Uniform+Neutral Greedy replaces Heuristic+Heuristic Greedy on
the frontier because it has better quality at the same zero-successor cost.

No scalar quality/compute score and no p-value is reported. These are exact
counts for a small handcrafted deterministic set.

## What the evidence establishes—and does not

On case-set v0, current one-ply search improves substantially over heuristic
Greedy when current Value exposes a useful penalty signal. BestOfN-4 is the
more compute-efficient 75%-accuracy point; PUCT-4 buys only 0.25 lower total
regret with 18 extra observations. PUCT shows a selective-allocation advantage
in one case, but loses another selective case to BestOfN. Current Heuristic
Policy does not help this frozen suite under Neutral Value, and current
Heuristic Value cannot solve fixtures whose state exposes no discriminating
signal.

This does not establish that SocratesZero improves CED dialogue, real model
answers, factuality, safety, latency, or cost. The set is small and authored,
the environment is deterministic and one-ply, the successor fixture is not a
canonical CED executor, and there are no honest trace counterfactuals or live
calls.

## Recommended next architectural decision

Do not begin RL from this evidence. The most informative next branch is either:

1. define a separately reviewed, canonical and safe deeper successor semantics
   to test whether PUCT gains beyond exhaustive one-ply Best-of-N; or
2. build an explicitly approved read-only live/replay shadow milestone that
   records real counterfactual observations without production authority.

If neither can be justified, simplify around BestOfN rather than preserving
PUCT complexity by default.

## Verification

The completed checkpoint passed:

- evaluation-specific: `37 passed`;
- PUCT: `53 passed`;
- BestOfN: `24 passed`;
- Greedy: `27 passed`;
- Policy: `13 passed`;
- Value: `21 passed`;
- contracts plus Greedy/BestOfN/PUCT: `123 passed`;
- complete SocratesZero bundle: `239 passed`;
- Hybrid H8 plus SocratesZero: `250 passed`;
- focused CED/Socratic: `142 passed`;
- `tests_dialogues`: `2305 passed, 1 skipped`;
- repository-wide: `2612 passed, 1 skipped, 23 warnings`.

The 23 warnings are pre-existing: 21 Pydantic `.dict()` deprecations and two
duplicate FastAPI operation IDs. No live API call was made.

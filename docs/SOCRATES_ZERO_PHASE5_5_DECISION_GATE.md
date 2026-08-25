# SocratesZero Phase 5.5 — Evidence Review and Architecture Decision Gate

Status: **COMPLETE — analysis only**

Decision date: 2026-08-25

Branch reviewed: `feature/socrates-zero-search-v0`

Sealed Phase 5 HEAD reviewed: `cc76aa8832e857e34c4b751c7681f3e5d59ac933`

## Executive verdict

The strongest demonstrated Phase 5 effect is not adaptive PUCT allocation. It
is **observing real successor states and evaluating the observations with a
non-neutral Value**. BestOfN-4 captures almost all of the measured gain:

- Greedy H/H -> BestOfN-4 H/H: `+6` correct, `-6.75` regret, `+62`
  successor observations;
- BestOfN-4 H/H -> PUCT-4 H/H: `0` additional correct, `-0.25` regret,
  `+18` successor observations.

`HeuristicPolicyPrior/v0` is **HARMFUL** in the only two fully paired
Uniform-versus-Heuristic comparisons. `HeuristicValueEstimator/v0` is
**SUPPORTED** as the strongest demonstrated contributor beyond Policy-only
selection: it adds six correct cases to both BestOfN-4 and PUCT-4 while Policy,
budget, case, and strategy are held fixed.

The current Value limitation is **both estimator-limited and
information-limited, with observability the prior architectural bottleneck**.
The estimator deliberately reads only contradiction/question counts and coarse
terminal status. Meanwhile the governing Hybrid core already owns typed
verification results, claim assessments, objection and contradiction lifecycle
states, and admissible evidence links; `SearchState v0` makes most of those
semantics opaque or omits them. A more complex or learned Value cannot recover
information absent from its input.

BestOfN and PUCT are **CO-CHAMPIONS** in the frozen depth-one Pareto sense:
BestOfN has equal correctness and lower compute, while PUCT has 0.25 lower
regret. PUCT is promising but unproven, depth-limited, value-limited at the
suite level, currently cost-disadvantaged, and worth retaining only as a
research baseline. It is not dominated because of the regret advantage.

The single selected next milestone is:

> **`feature/socrates-zero-canonical-observability-v1` — Canonical Epistemic
> Observability v1**

It will test one hypothesis: real CED decision states that collapse under the
opaque `SearchState v0` projection contain already-authoritative typed
epistemic distinctions that a safe v1 projection can preserve without
inference or new authority. It will not change Value, Policy, search, depth,
successor execution, providers, the Phase 5 benchmark, or production behavior.

## Repository and artifact integrity

The analysis began before any Phase 5.5 edits with:

| Check | Verified value |
|---|---|
| Branch | `feature/socrates-zero-search-v0` |
| HEAD | `cc76aa8832e857e34c4b751c7681f3e5d59ac933` |
| Artifact | `docs/branches/feature-socrates-zero-search-v0/artifacts/socrateszero_search_kernel_benchmark_v0.json` |
| SHA-256 | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Size | `523245` bytes |
| Git blob at first artifact commit `17be287` | `0488de8a555658a55312d8b1da8614ab9347743b` |
| Current artifact Git blob | `0488de8a555658a55312d8b1da8614ab9347743b` |
| Byte equality | `true` |
| Runs/cases | `11 x 20` |
| Live provider/tool calls | `0 / 0` |

The artifact was not rewritten. Its case-set digest remains
`szevalcases_e34e673f5d33fcb167aa462e8df3bb1b9a871bba8a2be492cc13ccbde065694e`.

## Evidence-ranked bottlenecks

This ranking is by strength of current evidence, not by roadmap excitement.
The data-validity gaps are real limitations on what may be claimed, but they
are not automatically causal explanations of the kernel result.

| Rank | Candidate | Evidence | Verdict |
|---:|---|---|---|
| 1 | C. SearchState observability | Direct collapse in both `value-uninformative` cases plus repository evidence that typed governing semantics become digests or disappear | Strongest actionable architectural bottleneck |
| 2 | B. Value quality | Paired H/N -> H/H adds six correct for both search strategies; v0 is deliberately penalty-only and low-resolution | Strongest demonstrated performance contributor and current ceiling |
| 3 | E. PUCT allocation mechanics | Exact PUCT-4/8 receipts show visit-count selection overturning better Q after redundant repeat observations | Confirmed depth-one reliability/cost limitation |
| 4 | A. Policy quality | Two legal paired comparisons both show `-1` correct and `+2.30` regret for Heuristic versus Uniform | Confirmed weakness, but not the dominant ceiling because successor Value overcomes much of it |
| 5 | G. Lack of real counterfactual data | `0` honest evaluable traces and `2` explicit missing counterfactuals | Major external-validity uncertainty; effect size unknown |
| 6 | F. Benchmark limitations | Twenty authored deterministic one-ply cases cannot establish population or end-to-end CED gains | Certain scope limit, not a causal diagnosis |
| 7 | D. Successor horizon/depth | PUCT is explicitly one ply and deeper planning may matter, but Phase 5 contains no depth-2 observation | Plausible, important, and currently untested; unsafe to pursue before a canonical executor exists |

## Exact reconstruction of all eleven configurations

The table below is reconstructed from the machine-readable artifact. `H` means
Heuristic, `U` Uniform, and `N` Neutral. Budget is the maximum successor
observations per case. `S/P/V/Nd/Ex` are successor, Policy, Value, node, and
expansion counts aggregated across all twenty cases.

Category cells are `correct/2:regret`. Abbreviations are: `PC` policy-correct,
`MP` misleading-policy, `BN` BestOfN-sufficient, `SB` selective-budget,
`FV` flat-value, `HI` heuristic-value-informative, `VU` value-uninformative,
`BE` budget-exhaustion, `SL` single-legal-move, and `ET` exact-ties.

| Artifact run | Strategy | Policy | Value | Budget | Correct | Regret | S | P | V | Nd | Ex | Category profile (`correct/2:regret`) |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Greedy | U | N | 4 | 10/20 | 9.25 | 0 | 20 | 20 | 0 | 0 | PC 1:0.60; MP 1:1.20; BN 0:1.80; SB 0:2.05; FV 0:1.30; HI 2:0; VU 1:1.10; BE 1:1.20; SL 2:0; ET 2:0 |
| 2 | PUCT | H | H | 8 | 12/20 | 7.75 | 160 | 20 | 160 | 160 | 160 | PC 2:0; MP 2:0; BN 1:1.20; SB 1:0.55; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 1:1.10; SL 2:0; ET 2:0 |
| 3 | PUCT | H | N | 4 | 9/20 | 11.55 | 80 | 20 | 80 | 80 | 80 | PC 2:0; MP 0:2.80; BN 1:1.20; SB 1:1.25; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 0:1.40; SL 2:0; ET 2:0 |
| 4 | PUCT | H | H | 1 | 9/20 | 11.55 | 20 | 20 | 20 | 20 | 20 | PC 2:0; MP 0:2.80; BN 1:1.20; SB 1:1.25; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 0:1.40; SL 2:0; ET 2:0 |
| 5 | BestOfN | H | N | 4 | 9/20 | 11.75 | 62 | 20 | 62 | 62 | 62 | PC 2:0; MP 0:2.80; BN 1:1.20; SB 0:1.75; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 1:1.10; SL 2:0; ET 2:0 |
| 6 | Greedy | H | N | 4 | 9/20 | 11.55 | 0 | 20 | 20 | 0 | 0 | PC 2:0; MP 0:2.80; BN 1:1.20; SB 1:1.25; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 0:1.40; SL 2:0; ET 2:0 |
| 7 | BestOfN | H | H | 4 | 15/20 | 4.80 | 62 | 20 | 62 | 62 | 62 | PC 2:0; MP 2:0; BN 2:0; SB 1:0.80; FV 1:1.00; HI 2:0; VU 0:1.90; BE 1:1.10; SL 2:0; ET 2:0 |
| 8 | PUCT | H | H | 2 | 12/20 | 7.75 | 40 | 20 | 40 | 40 | 40 | PC 2:0; MP 2:0; BN 1:0.80; SB 1:0.95; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 1:1.10; SL 2:0; ET 2:0 |
| 9 | PUCT | U | N | 4 | 10/20 | 9.25 | 80 | 20 | 80 | 80 | 80 | PC 1:0.60; MP 1:1.20; BN 0:1.80; SB 0:2.05; FV 0:1.30; HI 2:0; VU 1:1.10; BE 1:1.20; SL 2:0; ET 2:0 |
| 10 | Greedy | H | H | 4 | 9/20 | 11.55 | 0 | 20 | 20 | 0 | 0 | PC 2:0; MP 0:2.80; BN 1:1.20; SB 1:1.25; FV 1:1.00; HI 0:2.00; VU 0:1.90; BE 0:1.40; SL 2:0; ET 2:0 |
| 11 | PUCT | H | H | 4 | 15/20 | 4.55 | 80 | 20 | 80 | 80 | 80 | PC 2:0; MP 2:0; BN 2:0; SB 1:0.55; FV 1:1.00; HI 2:0; VU 0:1.90; BE 1:1.10; SL 2:0; ET 2:0 |

All runs completed all twenty cases with zero failed or not-evaluable cases.
Model, tool, token, cost, and wall-time counters are zero by fixture design.

## Policy attribution

Only two pairs hold strategy, Neutral Value, budget 4, and case set fixed:

| Pair, Heuristic minus Uniform | Improved | Worsened | Unchanged | Correct delta | Regret delta |
|---|---:|---:|---:|---:|---:|
| Greedy H/N versus U/N | 6 | 8 | 6 | -1 | +2.30 |
| PUCT-4 H/N versus U/N | 6 | 8 | 6 | -1 | +2.30 |

The two rows are identical because with Neutral Value, Greedy selects Policy
argmax and PUCT's repeated zero-Q visits/root selection ultimately reproduce
the same prior-driven decision.

Exact improved cases and selected-outcome gains are:

- `best_of_n_sufficient_01 +1.00`;
- `budget_exhaustion_01 +0.20`;
- `flat_value_01 +0.60`;
- `policy_correct_01 +0.60`;
- `selective_budget_advantage_01 +1.00`;
- `value_uninformative_02 +0.40`.

Exact worsened cases are:

- `best_of_n_sufficient_02 -0.40`;
- `budget_exhaustion_02 -0.40`;
- `flat_value_02 -0.30`;
- `heuristic_value_informative_01 -0.80`;
- `heuristic_value_informative_02 -1.20`;
- `misleading_policy_01 -1.60`;
- `selective_budget_advantage_02 -0.20`;
- `value_uninformative_01 -1.20`.

| Category | Improved/worsened/unchanged cases | Net selected-outcome delta | Correct delta |
|---|---|---:|---:|
| Policy-correct | 1 / 0 / 1 | +0.60 | +1 |
| Misleading-policy | 0 / 1 / 1 | -1.60 | -1 |
| BestOfN-sufficient | 1 / 1 / 0 | +0.60 | +1 |
| Selective-budget | 1 / 1 / 0 | +0.80 | +1 |
| Flat-value | 1 / 1 / 0 | +0.30 | +1 |
| Heuristic-value-informative | 0 / 2 / 0 | -2.00 | -2 |
| Value-uninformative | 1 / 1 / 0 | -0.80 | -1 |
| Budget-exhaustion | 1 / 1 / 0 | -0.20 | -1 |
| Single-legal-move | 0 / 0 / 2 | 0 | 0 |
| Exact-ties | 0 / 0 / 2 | 0 | 0 |

**Policy verdict: HARMFUL.** This verdict is deliberately scoped to v0, this
case set, and the two available matched Neutral-Value regimes. It is stronger
than “unsupported”: both legal paired controls lose one correct case and add
2.30 regret. It does not prove that every future Policy prior will be harmful.

## Value attribution

The exact paired comparisons hold strategy, Heuristic Policy, budget 4, and
case fixed:

| Pair, Heuristic Value minus Neutral Value | Improved | Worsened | Unchanged | Correct delta | Regret delta |
|---|---:|---:|---:|---:|---:|
| Greedy | 0 | 0 | 20 | 0 | 0 |
| BestOfN-4 | 6 | 0 | 14 | +6 | -6.95 |
| PUCT-4 | 7 | 1 | 12 | +6 | -7.00 |

Greedy is unchanged by construction: it reports root Value but selects solely
by Policy. Search strategies observe and value successors, so the comparison is
action-relevant for them.

For BestOfN-4, the six improvements are:

- both misleading-policy cases: `+1.60`, `+1.20`;
- both heuristic-value-informative cases: `+0.80`, `+1.20`;
- `best_of_n_sufficient_02: +1.20`;
- `selective_budget_advantage_02: +0.95`.

There are no worsened BestOfN cases. Category correctness gains are `+2`
misleading-policy, `+2` heuristic-value-informative, `+1` BestOfN-sufficient,
and `+1` selective-budget.

For PUCT-4, improvements are the same six cases except that the selective case
gain is `+0.70`, plus `budget_exhaustion_01: +1.00`. The sole worsening is
`budget_exhaustion_02: -0.70`. The budget-exhaustion pair therefore contributes
net `+0.30` selected outcome and `+1` correctness.

The required category findings are:

- misleading Policy: Value fixes both cases for both search strategies;
- heuristic-value-informative: Value fixes both cases for both search
  strategies;
- value-uninformative: Value changes nothing and both search strategies remain
  `0/2`, regret `1.90`;
- selective-budget: Value materially helps, but adaptive allocation decides
  which of the pair PUCT versus BestOfN handles better.

**Value verdict: SUPPORTED.** Yes: current Value is the strongest demonstrated
contributor beyond Policy-only action selection. The conclusion comes from
paired case effects, not just aggregate accuracy. It does not establish that
the coefficients generalize or that a learned Value is ready.

## Successor observation versus adaptive allocation

With Heuristic Policy and Heuristic Value fixed:

| Transition | Improved | Worsened | Unchanged | Correct delta | Regret delta | Successor delta |
|---|---:|---:|---:|---:|---:|---:|
| Greedy -> BestOfN-4 | 7 | 2 | 11 | +6 | -6.75 | +62 |
| BestOfN-4 -> PUCT-4 | 1 | 1 | 18 | 0 | -0.25 | +18 |

Greedy -> BestOfN improves both misleading-policy cases, both
heuristic-value-informative cases, `best_of_n_sufficient_02`,
`budget_exhaustion_01`, and `selective_budget_advantage_02`. It worsens
`budget_exhaustion_02` and `selective_budget_advantage_01`.

BestOfN -> PUCT changes only the selective-budget pair: PUCT gains `+0.80` on
case 01 and loses `-0.55` on case 02. That yields no correctness gain and only
0.25 lower regret at eighteen additional observations.

**Successor-observation verdict:** almost all measured improvement is
attributable to observing successor state plus using Value. Phase 5 does not
show a decisive independent benefit from adaptive PUCT allocation.

## PUCT-8 forensic investigation

PUCT-4 -> PUCT-8 produces `0` improved, `3` worsened, and `17` unchanged cases:

- `best_of_n_sufficient_02: -1.20`;
- `heuristic_value_informative_01: -0.80`;
- `heuristic_value_informative_02: -1.20`.

Correctness falls by three, regret rises by 3.20, and successor observations
double from 80 to 160. Exact regenerated PUCT receipts match the artifact's
stored receipt references. The relevant root statistics are:

| Case/budget | Action | Prior P | Visits N | Q | Ground truth | Root selected? |
|---|---|---:|---:|---:|---:|---|
| BN-02 / 4 | propose | 0.181818 | 1 | -0.05 | +0.10 | no |
| BN-02 / 4 | run elenchus | 0.454545 | 1 | -0.16 | -0.40 | no |
| BN-02 / 4 | seek evidence | 0.181818 | 1 | 0.00 | +0.80 | **yes** |
| BN-02 / 4 | synthesize partial | 0.181818 | 1 | -0.08 | 0.00 | no |
| BN-02 / 8 | propose | 0.181818 | 2 | -0.05 | +0.10 | no |
| BN-02 / 8 | run elenchus | 0.454545 | 3 | -0.16 | -0.40 | **yes** |
| BN-02 / 8 | seek evidence | 0.181818 | 2 | 0.00 | +0.80 | no |
| BN-02 / 8 | synthesize partial | 0.181818 | 1 | -0.08 | 0.00 | no |
| HI-01 / 4 | ask | 0.304348 | 1 | -0.05 | +0.10 | no |
| HI-01 / 4 | propose | 0.173913 | 1 | 0.00 | +0.90 | **yes** |
| HI-01 / 4 | reflect | 0.260870 | 1 | -0.08 | -0.30 | no |
| HI-01 / 4 | run elenchus | 0.260870 | 1 | -0.16 | -0.70 | no |
| HI-01 / 8 | ask | 0.304348 | 3 | -0.05 | +0.10 | **yes** |
| HI-01 / 8 | propose | 0.173913 | 2 | 0.00 | +0.90 | no |
| HI-01 / 8 | reflect | 0.260870 | 2 | -0.08 | -0.30 | no |
| HI-01 / 8 | run elenchus | 0.260870 | 1 | -0.16 | -0.70 | no |
| HI-02 / 4 | ask | 0.304348 | 1 | -0.08 | -0.40 | no |
| HI-02 / 4 | propose | 0.173913 | 1 | 0.00 | +0.80 | **yes** |
| HI-02 / 4 | reflect | 0.260870 | 1 | -0.05 | +0.20 | no |
| HI-02 / 4 | run elenchus | 0.260870 | 1 | -0.16 | -0.60 | no |
| HI-02 / 8 | ask | 0.304348 | 3 | -0.08 | -0.40 | **yes** |
| HI-02 / 8 | propose | 0.173913 | 2 | 0.00 | +0.80 | no |
| HI-02 / 8 | reflect | 0.260870 | 2 | -0.05 | +0.20 | no |
| HI-02 / 8 | run elenchus | 0.260870 | 1 | -0.16 | -0.60 | no |

At budget four, each of four actions is visited once. Root selection first ties
on visit count and then uses Q, so the highest-Q—and in these three cases truly
optimal—action wins. At budget eight, repeat observations are deterministic and
return the same successor and same Q. They provide no new information. The
higher-prior branches nevertheless acquire more visits. Final root selection
orders by visit count before Q, so `run elenchus` or `ask` beats the better-Q
action solely because it has one more visit.

There is no budget violation, illegal action, dishonest usage, state mutation,
receipt mismatch, or tie-break violation. This is **EXPECTED ALGORITHMIC
BEHAVIOR** under the frozen formula and root rule, and simultaneously a
**DESIGN LIMITATION** of applying visit-count choice to repeated deterministic
one-ply observations. The depth-one horizon contributes because repeat visits
cannot reveal descendants. It is not primarily a Value failure in these three
cases: the recorded Q values correctly rank the optimal action. It is not a
correctness bug and Phase 5.5 makes no fix.

### Does PUCT-8 make adaptive test-time compute unreliable?

For `puct-strategy/v0` in the frozen depth-one deterministic regime, **yes**:
selected-action quality is empirically non-monotone with compute. This does not
show that adaptive test-time compute in general is flawed. Here more compute is
unnecessary at one ply and amplifies prior-driven visit counts without new
observations. Low-resolution Value still limits the suite elsewhere, but it is
not the proximate cause of these three regressions.

## Value-uninformative case forensics

Both cases use four actions. Every successor blueprint exposes zero
contradictions and zero unresolved questions, remains non-terminal, and differs
only by an opaque `evaluation_transition` digest. Every successor receives
`HeuristicValueEstimator/v0 = 0.0`.

| Case | Evaluator-only future utilities | Root state | Successor state visible to Value | Result |
|---|---|---|---|---|
| `value_uninformative_01` | propose `+0.70`; reflect `+0.10`; run `0.00`; ask `-0.50` | 0 contradictions, 1 unresolved question | all four: 0 contradictions, 0 questions, non-terminal; action only as opaque digest | all four V `0.0`; optimum cannot be identified |
| `value_uninformative_02` | reflect `+0.80`; ask `+0.20`; run `+0.10`; propose `-0.30` | 1 contradiction, 0 unresolved questions | all four: 0 contradictions, 0 questions, non-terminal; action only as opaque digest | all four V `0.0`; optimum cannot be identified |

What ground truth knows is an author-assigned **future action outcome**. That
outcome is absent from `StrategyCaseView` and must remain absent. It is not a
canonical CED or Hybrid record omitted accidentally from these two fixtures;
it is future-only evaluator information and therefore forbidden. Decoding an
action digest or learning case identity would be leakage, not Value.

This does not mean real CED states contain no lawful discriminating signal. The
repository audit below shows that verification-owned and CED-owned semantics
exist in real governing records but are opaque or omitted in SearchState v0.
The exact frozen utilities above, however, may never be manufactured from those
records. A future evaluation must use independently precommitted observable
facts and keep outcome labels separate.

## SearchState v0 observability audit

“Policy/Value usable” below describes the current v0 implementations, not what
an unrestricted model could attempt. “Safe later” means safe only with source
provenance, train/evaluation isolation, and unchanged Hybrid/CED authority.

| Field | Authority source | Exposed / opaque | Policy v0 | Value v0 | Legality v0 | Safe later? | Missing semantics |
|---|---|---|---|---|---|---|---|
| `schema_version`, `state_id` | Search contract, derived from semantic payload | Structured identity | validation only | validation only | indirect | yes, as identity | none; not a quality feature |
| `parent_state_id`, `session_id`, `task_id` | CED/search audit | Structured but excluded from semantic identity | no | no | no | no as learning features | volatile lineage only |
| `task_kind` | `CanonicalTaskSpec` / terminal projection | Structured | no | no | **yes** | yes | no action-execution capability |
| `question` | canonical SessionState user input | Raw text | no | no | no | risky/conditional | prose is not verified semantics |
| `phase`, `round_number` | canonical task/session | Structured | no | no | **yes** | yes | round transition semantics not executable |
| active agent/role/slot/attempt | canonical task routing | Structured | no | no | no | process-only | exact provider/model route is separate |
| `active_claims` | live authoritative commitments + unsuperseded Hybrid claims | IDs plus semantic digests | target existence only | count ignored | **yes** for target actions | yes if typed | claim support, verification class and lineage are not inspectable |
| `evidence` | admissible Hybrid evidence only | IDs plus digest | no | deliberately no | target validation only | yes if typed | stance, source type, claim link and receipt are inside digest |
| `contradictions` | non-dismissed Hybrid contradiction records | IDs plus digest; count visible | **count only** | **count only** | target validation | yes if typed | candidate versus validated state, claim pair and verification link are opaque; dismissed transitions absent |
| `unresolved_questions` | Socratic aporia + raised/pending/inconclusive objections | IDs plus digest; conflated count | **count only** | **count only** | target validation | yes if typed | aporia versus objection, objection scope/state/target, and resolution are not inspectable |
| `candidate_hypotheses` | accepted Reconstruction moves | IDs plus content digest | no | no | indirect via move history | conditional | quality/support absent; prose digest is not meaning |
| `candidate_answers` | accepted Synthesis moves | IDs plus content digest | no | no | **yes** for ratify | conditional | assembly/claim support and release readiness absent |
| `role_history` | CED role ledger | Structured routing history | no | no | no | process-only | provider/model identity not present |
| `move_history` | accepted moves cross-checked with OK task-log entries | Structured task/phase/slot plus content digest | no | no | **yes** for sequencing | yes for protocol | failed/rejected attempts and semantic outcomes absent |
| `provider_receipts` | intended canonical observation source | Field exists, but real projector always emits empty | no | no | no | only after authoritative source exists | provider failures, costs, tools and accepted/rejected status missing |
| `verification_results` | Hybrid `VerificationRecord` | digest + provider/model identity | no | deliberately no | no | **yes** when typed | result, class, method, target, evidence IDs, limitations and support eligibility are opaque |
| `epistemic_graph_ref` | digest of projected Hybrid graph | One opaque digest | no | no | no | identity/audit only | no traversable claim/evidence/objection relations |
| `policy_context` | versioned search input seam | name + opaque digest; real projector emits empty | current heuristic no | deliberately no | no | conditional | no governing semantics and high leakage risk if populated casually |
| `budget` | CED/infrastructure hard limits | Fully structured | no | terminal rule only | search capacity | yes | no reservation/failure outcome protocol |
| `budget_usage` | CED/infrastructure counters | Fully structured | no | terminal rule only | search capacity | yes | real provider cost completeness not established |
| `depth` | search branch lineage | Structured | no | no | capacity checks | yes | no canonical recursive transition behind it |
| `terminal_status` | coarse CED projection | Structured enum | no | blocked/exhausted penalties | **yes** (`STOP`) | yes if source-complete | real projector maps non-terminal/blocked/answer-ready but never `ABSTAINED`; release/support detail is collapsed |

Important canonical semantics that currently do not survive as usable typed
Value inputs include:

- `VerificationRecord.result`, method/class, target links, evidence IDs, and
  whether a check can create support;
- `ClaimAssessment.support_state`, basis/falsifying/unresolved record IDs,
  eligibility, ineligibility reason, and required-but-unverified /
  external-evidence-required claims;
- objection `VALIDATED`/`REJECTED` lifecycle, conclusion-versus-justification
  scope, and target provenance;
- contradiction candidate/validated/dismissed lifecycle;
- evidence stance/source/claim linkage;
- revision and evidence-carry lineage;
- failed task/provider observations;
- an explicit canonical “Socratic question resolved” lifecycle, which does not
  currently exist as a governing record.

**Observability verdict: both, but primarily information-limited at the
architectural boundary.** Heuristic v0 is intentionally weak and linear, so
estimator capacity is also limited. Yet increasing capacity first would be
scientifically confounded: the input hides distinctions the governing system
already knows. The correct order is to prove safe typed observability before
testing richer estimation.

## Positive epistemic Value signal audit

Absence of a penalty is not automatically positive evidence. Any future Value
must consume governing records; it must not reproduce Hybrid assessment logic
or turn quality/process completion into truth.

| Potential signal | Status | Safe interpretation |
|---|---|---|
| Deterministic/tool/task-internal verification result and `creates_support` | **AVAILABLE BUT OPAQUE**; requires projection change | Verification-owned result may be consumed as a fact with record provenance; Value may not re-verify it |
| Claim `SupportState` plus basis/falsifying/unresolved record IDs | **AVAILABLE NOW** in Hybrid, **REQUIRES SEARCHSTATE PROJECTION CHANGE** | Consume the governing assessment, never recompute support |
| Admissible supporting evidence with claim/source/stance link | **AVAILABLE BUT OPAQUE**; requires projection change | A typed admissible supporting record may be recognized; evidence count alone is insufficient |
| Rejected objection after a valid verification | **AVAILABLE NOW**, omitted from unresolved projection | A resolved lifecycle transition can be progress; rejection is not positive support for unrelated claims |
| Dismissed contradiction after governing validation | **AVAILABLE NOW**, omitted from projection | Resolution can remove a blocker; it is not evidence for a claim by itself |
| Validated conclusion objection or falsifying verification | **AVAILABLE BUT OPAQUE/OMITTED** | Negative, verification-owned evidence; never invert it into a popularity signal |
| Explicit external-evidence-required/inconclusive state | **AVAILABLE BUT OPAQUE** | Negative/uncertain requirement, not failure fabrication |
| Declared commitment retention/revision/withdrawal | **AVAILABLE NOW**, mostly digest-only | Process/Policy signal at most; a model declaration is not positive epistemic support |
| Explicit resolution of a Socratic question | **NOT CANONICAL YET** | Must not be inferred from prose or merely from a later move |
| Provider/task failure status | **AVAILABLE NOW** in CED task log, absent from SearchState | Operational negative signal after a typed projection; not epistemic truth |
| `ANSWER_READY`, synthesis completion, ratification, peer score, consensus, confidence, markers | **FORBIDDEN** as positive support | Completion and quality/governance are not verification |
| Future benchmark utility, optimal action, case/category identity | **FORBIDDEN** | Evaluator-only outcome label |
| Prose sentiment, length, fluency, similarity, hidden digest decoding | **FORBIDDEN** | No semantic or epistemic authority |

## Depth-2 requirements and blocker map

The abstract chain and current status are:

| Step | Current status | Break or requirement |
|---|---|---|
| Project real `S0` | Available read-only | Projection is incomplete but valid for v0 |
| `legal_actions(S0)` -> `A0` | Available | Bounded Constitution owns legality |
| Execute `A0` in isolation | **Breaks** | No canonical CED action executor maps a macro-action to one isolated state transition |
| Obtain real `S1` | Fixture-only | Current evaluator is root-only, experimental, non-governing, and not a CED executor |
| `legal_actions(S1)` | Interface exists, semantics unproven | CED must canonically advance phase/task/round/commitments before the Constitution can receive an honest child |
| `Policy(S1)` | Interface exists | Input observability remains incomplete; still advisory only |
| Select `A1` | Mechanism exists | PUCT v0 explicitly never descends to children |
| Execute `A1` -> `S2` | **Breaks** | Protocol declares no recursive capability; fixture and Constitution are root-only; no isolated descendant executor exists |

Before depth two is legitimate, all of the following must be true:

1. CED owns a versioned action-to-task/phase transition API; SocratesZero does
   not reconstruct scheduling.
2. Every branch receives a deep, isolated copy of SessionState and all relevant
   CED side ledgers: commitments, aporia, Hybrid state, task logs, provider
   bindings, retry/dispatch state, and round/phase history.
3. Provider/model/tool calls are real observations with pre-reserved bounded
   budgets, exact model identity, receipts, and cost-bearing failure outcomes.
4. Accepted versus rejected provider output is decided by the same canonical
   CED validation path and receives honest move/task lineage.
5. Commitment, evidence, verification, objection, contradiction, revision, and
   release provenance remain branch-local and replayable.
6. `project_search_state` runs after each canonical isolated transition and
   preserves enough state for the next legal-action decision.
7. No branch reads another branch's outputs or future; no speculative state
   mutates production.
8. The successor protocol declares and tests recursive capability,
   determinism/nondeterminism, isolation, partial failure, and exact aggregate
   usage.

The existing synthesis-only `DeliberationTree` does not satisfy this need. It
is a CED-integrated UCB revision mechanism over draft candidates and peer
scores; it mutates the candidate pool and does not expose general CED
macro-action successors.

### Hard rule: no second CED

Any design in which SocratesZero independently reconstructs what CED would do
next is rejected. Future depth must call canonical CED-owned transition
semantics. Search may choose among hard-legal proposals; it may not become a
parallel scheduler, validator, commitment ledger, verifier, or release
authority.

## Real counterfactual data gap and shadow safety

The two inspected real traces contain only the production trajectory. They do
not contain execution of alternative legal actions from the same root. A
post-hoc transcript cannot reveal what a different provider call, accepted
move, commitment update, verification, or next phase would have produced.
Guessing those successors would fabricate observations, so Phase 5 correctly
reports `0` evaluable and `2` missing counterfactuals.

A minimum future read-only episode needs:

- immutable root SearchState and canonical source-record references;
- the complete hard-legal action set and baseline selected action;
- alternative actions, Policy distribution, Value estimate, and all component
  versions;
- one CED-owned isolated branch execution per evaluated action;
- exact provider, provider model, tool and verifier identities;
- accepted/rejected/failure status, real successor SearchState, verification
  results, and complete task/move/commitment/evidence lineage;
- separately accounted node, expansion, call, token, tool, cost, and time
  usage, including failed work;
- immutable receipts linking root -> action -> isolated execution -> successor;
- explicit missing outcomes where no lawful evaluation exists.

A safe shadow collector must leave the production baseline authoritative,
prevent branch output from entering production or another branch, enforce
explicit per-branch and aggregate budgets before calls, and retain exact model
identity and failure/cost records. Shadow-selected actions must never control
the production dialogue.

The repository has useful pieces—canonical task specs, hard legality, provider
registry, accepted move/task logs, Hybrid records, the read-only projection,
budget contracts, receipts, and an append-only shadow ledger. It does **not**
have enough seams for safe real counterfactual collection. `HybridShadowObserver`
captures a completed canonical session after finalization; it does not clone or
execute an alternative action. There is no branch sandbox, canonical
macro-action executor, branch-local orchestration ledger, or cost-bearing
failure outcome. Real shadow collection therefore remains high-information but
high-risk engineering, not the next minimal experiment.

## BestOfN and PUCT status

### BestOfN

BestOfN-4 is the strongest **complexity-adjusted** current search baseline: it
matches PUCT-4 at `15/20`, spends 62 rather than 80 successor observations, and
is simpler. It does not strictly dominate PUCT because its regret is 4.80
rather than 4.55 and each method wins one selective-budget case.

**Classification: CO-CHAMPION.** In practical experimental comparisons it
should remain the default complexity anchor. It receives no production
authority.

### PUCT

Applicable classifications are:

- **PROMISING**: it can allocate selectively and owns one selective-budget win;
- **UNPROVEN**: no correctness advantage over BestOfN and no real CED evidence;
- **DEPTH-LIMITED**: explicitly one real ply;
- **VALUE-LIMITED**: two cases are completely aliased and many Q values are
  coarse, although the PUCT-8 regressions specifically occur despite correct Q
  ordering;
- **CURRENTLY COST-DISADVANTAGED**: 18 extra observations for equal correctness
  and only 0.25 lower regret at budget four;
- **KEEP AS RESEARCH BASELINE**: do not remove or promote it.

It is not `CURRENTLY DOMINATED` because its regret is lower. The evidence does
not justify tuning, production wiring, or using its visits as learning targets.

## RL readiness gate

| Prerequisite | Status | Evidence |
|---|---|---|
| 1. Meaningful state representation | PARTIAL | Stable structural state exists; governing epistemic semantics are opaque/incomplete |
| 2. Trustworthy action legality | READY | Constitution owns a tested bounded hard-legal set |
| 3. Trustworthy successor observation | NOT READY | Only a root-only deterministic fixture exists; no canonical executor |
| 4. Useful Value signal | PARTIAL | Strong paired fixture contribution, but narrow and penalty-only |
| 5. Reward not dominated by benchmark labels | NOT READY | Current outcomes are evaluator-authored fixture utilities, not a trajectory reward |
| 6. Real trajectory collection | NOT READY | Zero honest real counterfactual episodes |
| 7. No benchmark/holdout contamination | PARTIAL | v0 isolation is strong; no train/validation/held-out real trajectory regime exists |
| 8. Sufficient action diversity | PARTIAL | Typed vocabulary exists, but no real successor dataset across states/actions |
| 9. Stable evaluation protocol | PARTIAL | Kernel protocol is frozen and replay-safe; end-to-end held-out evaluation is absent |
| 10. Evidence search adds value | PARTIAL | Fixture search helps; external/end-to-end benefit is unestablished |

**Overall: RL NOT YET EARNED.** The missing environment and reward are not
minor implementation details; they are the basis of valid RL.

## Learned Value readiness

Training a Value model now would not solve input aliasing. It could memorize
case/action identity only by leakage, learn prose correlations without
authority, or reproduce the current count heuristic. There is no evidence that
nonlinear estimation capacity, rather than representation, is the primary
unresolved factor. There are also no real counterfactual trajectories or
governed outcome targets.

**Learned Value is premature.** First determine whether lawful typed governing
signals survive a richer projection. Only a later, separately approved and
held-out experiment may test estimator capacity.

## Learned Policy readiness

No trustworthy training target currently exists:

- Phase 5 optimal actions are evaluator labels and must not become training
  features for the same benchmark;
- PUCT visit counts are budget-sensitive and become worse at budget eight;
- BestOfN choices are meaningful only inside authored fixture successors;
- production baseline choices are imitation targets, not improvement targets;
- verified real action outcomes and counterfactual trajectories do not exist.

**Learned Policy is premature.** The harmful heuristic prior is evidence to
avoid ungrounded handcrafted or learned preference targets, not a reason to
train immediately.

## Decision matrix

For information gain, explanation, cleanliness, future-RL usefulness,
reversibility, and capability gain, higher is favorable. For leakage risk,
duplicate-CED risk, complexity, and API cost, higher is unfavorable.

| Candidate next branch | Information gain | Explain Phase 5 ceiling | Scientific cleanliness | Leakage risk | Duplicate-CED risk | Engineering complexity | API cost | Future RL usefulness | Reversibility | Immediate capability gain |
|---|---|---|---|---|---|---|---|---|---|---|
| A. Richer canonical SearchState projection | **VERY HIGH** | **VERY HIGH** | HIGH | LOW | LOW | MEDIUM | LOW | **VERY HIGH** | HIGH | LOW |
| B. Safe deeper successor semantics | HIGH | HIGH | MEDIUM | LOW | **VERY HIGH** | **VERY HIGH** | HIGH | HIGH | MEDIUM | HIGH |
| C. Real read-only shadow counterfactual collection | **VERY HIGH** | MEDIUM | HIGH if isolation exists | MEDIUM | HIGH | **VERY HIGH** | **VERY HIGH** | **VERY HIGH** | MEDIUM | MEDIUM |
| D. Learned Value | MEDIUM | LOW | MEDIUM-LOW | HIGH | LOW | HIGH | MEDIUM | HIGH | MEDIUM | MEDIUM |
| E. Learned Policy | LOW | LOW | LOW | HIGH | LOW | HIGH | MEDIUM | MEDIUM | MEDIUM | LOW |
| F. RL | LOW | LOW | LOW | **VERY HIGH** | HIGH | **VERY HIGH** | **VERY HIGH** | LOW while prerequisites fail | LOW | LOW/uncertain |
| G. Simplify around BestOfN | LOW | LOW | HIGH | LOW | LOW | LOW | LOW | MEDIUM-LOW | HIGH | LOW |

The “immediate capability” rating for A is intentionally low because the
selected experiment changes observation fidelity only; it must not smuggle in
a Value improvement.

## Hypothesis discrimination

| Candidate | Uncertainty it would resolve | Why not selected now |
|---|---|---|
| Richer SearchState | Are lawful governing signals lost at the projection boundary, causing Value input aliasing? | **Selected**: highest information per architectural risk and prerequisite to richer Value |
| Depth-2 semantics | Is PUCT's lack of planning advantage primarily a horizon limit? | Requires a canonical isolated executor that does not exist; high second-CED risk |
| Real shadow collection | Do deterministic fixture gains generalize to real multi-model counterfactuals? | Highest external-validity value, but existing infrastructure cannot isolate action branches safely |
| Learned Value | Is nonlinear estimator capacity insufficient? | Confounded while typed inputs are missing and no real targets exist |
| Learned Policy | Can a learned prior beat Uniform/heuristic controls? | No grounded target; visits and fixture labels are unsuitable |
| RL | Can end-to-end optimization improve search behavior? | Environment, reward, trajectories, and held-out evaluation are not ready |
| BestOfN simplification | Is PUCT complexity unnecessary under v0? | Good operational default but explains little; retain both frozen baselines while investigating the cause |

## Exactly one next milestone

### Branch name

`feature/socrates-zero-canonical-observability-v1`

### Single research hypothesis

> At real CED decision states, `SearchState v0` aliases materially different,
> already-authoritative Hybrid/CED epistemic outcomes; a typed, provenance-safe
> v1 projection can preserve those distinctions without inference, prose
> interpretation, new evidence, or duplicated authority.

This is narrower and more testable than claiming in advance that a new Value
will improve benchmark accuracy.

### Minimal implementation scope

1. Freeze a preimplementation inventory of authoritative source fields and
   predeclare deterministic canonical fixture pairs that v0 aliases.
2. Add an opt-in, separately versioned v1 projection/contract surface for only:
   typed verification result/class/method/targets and provenance; governing
   claim assessment state and basis/falsifying/unresolved IDs; objection
   state/scope/target provenance; contradiction lifecycle; and typed admissible
   evidence links where already canonical.
3. Keep raw prose, quality scores, consensus, confidence, markers, and future
   outcomes absent.
4. Produce a deterministic observability report measuring which predeclared
   governing distinctions remain aliased under v0 and become distinguishable
   under v1.
5. Prove replay identity, source completeness, fail-closed missing records,
   v0 byte parity, default CED parity, and unchanged Hybrid authority.

No new Value version is part of this milestone. That separation prevents a
projection change and an estimator change from being credited to each other.

### Success criterion

- Every predeclared typed semantic field is copied from an existing governing
  record with exact source linkage; none is inferred.
- All predeclared canonical fixture pairs that differ in governing epistemic
  state are distinct under v1, while pairs with identical governing semantics
  remain equivalent.
- The observability report demonstrates at least one decision-relevant v0
  alias class resolved by v1.
- SearchState/projection v0, Phase 5 artifact/cases/results, default CED output,
  Hybrid support/release authority, and full regression behavior remain
  unchanged.

### Failure and falsification criterion

The hypothesis is falsified for the repository's current operating states if:

- canonical predecision states do not actually contain the inventoried typed
  outcomes;
- v1 resolves no predeclared decision-relevant alias class;
- meaningful distinctions require interpreting prose, consensus, scores,
  future labels, or inventing a “resolved” record;
- preserving them would duplicate Hybrid assessment or change CED authority;
- v0/default parity cannot be maintained.

Such a result would redirect the next gate toward acquiring new canonical
observations—most likely safe shadow/executor architecture—rather than toward a
more complex Value.

### Frozen components

- the Phase 5 artifact, case-set digest, all 20 cases, and budgets 1/2/4/8;
- Greedy, BestOfN-4, and PUCT v0, including `c_puct=1.0` and depth one;
- Uniform/Heuristic Policy v0 and Neutral/Heuristic Value v0;
- the v0 Constitution, legal vocabulary, action generator, successor fixture,
  harness, and all receipt identities;
- `SearchState v0` and `ced-search-state-projection/v0` behavior;
- canonical CED scheduling/execution and Hybrid support/release authority.

### Explicit non-goals

- no Policy or Value tuning, new estimator, learned component, or RL;
- no search algorithm or PUCT root-selection change;
- no depth two, recursive successor protocol, action executor, or second CED;
- no provider/tool/live API call and no shadow counterfactual orchestration;
- no benchmark case/budget/artifact rewrite or training on its labels;
- no production action authority, release authority, or default runtime wiring;
- no prose interpretation and no use of peer scores, consensus, ratification,
  confidence, or epistemic markers as support.

### What is learned regardless of outcome

If the hypothesis holds, observability—not neural capacity or depth—is proven
as the next prerequisite, and a later separately frozen `Value v1` experiment
becomes scientifically justified. If it fails, the repository learns that its
current canonical records do not contain the missing decision signal; richer
projection and learned Value should be deprioritized in favor of collecting
new lawful observations. Either result narrows the architecture without
spending provider compute or weakening authority boundaries.

### What comes only after this experiment

- If typed observability is demonstrated, a separate precommitted gate may
  define `HeuristicValueEstimator/v1` and a new held-out evaluation; it may not
  rewrite or train on the frozen v0 artifact.
- A canonical isolated branch executor and real read-only counterfactual
  collection require their own architecture decision before any depth-two or
  live-shadow work.
- Learned Value, learned Policy, trajectory distillation, and RL remain blocked
  until real governed observations, targets, splits, and promotion evidence
  exist.
- Production action authority remains a distinct final approval even if every
  research experiment succeeds.

## Final gate decision

Phase 5.5 selects exactly one next uncertainty: **canonical epistemic
observability**. It does not authorize implementation during this phase. Safe
depth, real counterfactual collection, a Value v1, learned Policy/Value, and RL
remain subsequent decision gates, not bundled work.

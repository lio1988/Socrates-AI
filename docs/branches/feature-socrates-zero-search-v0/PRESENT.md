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
- Phase 3C deterministic strategies are complete:
  - Greedy selects Policy argmax across the complete hard-legal set;
  - Best-of-N evaluates at most four explicit one-ply successor states;
  - successor and aggregate sibling usage are fail-closed and budget-enforced;
  - Value, Policy, and action-ID tie-break roles remain separate;
  - neither strategy executes an action or controls canonical CED.
- Phase 4 bounded deterministic PUCT is complete:
  - `puct-strategy/v0` adaptively allocates repeated real root successor
    observations using explicit PUCT and an untuned `c_puct=1.0`;
  - safe relative depth is frozen at one because the experimental successor
    protocol supplies no recursive capability guarantee;
  - path-local node/edge statistics, exact same-orientation backup,
    deterministic ties, exact usage, and a linked rich audit are replay-stable;
  - lower-prior observed Value can overturn misleading Policy with sufficient
    budget, while tiny budget remains Policy-biased;
  - no PUCT result has production authority or live dialogue wiring.
- Phase 5 frozen matched-compute evaluation is implemented and executed:
  - budgets 1/2/4/8 and a balanced 20-case, ten-category case set were
    versioned and committed before any comparative result;
  - the strategy-facing surface excludes direct and label-derived ground truth,
    and adversarial probing/overuse tests fail closed;
  - the immutable 11×20 run is fully offline, deterministic, replay-stable, and
    records exact separate resource vectors with zero provider/tool/token/cost;
  - matched at cap four, Greedy is `9/20` with regret `11.55` and zero
    successors, BestOfN is `15/20` with regret `4.80` and 62 successors, and
    PUCT is `15/20` with regret `4.55` and 80 successors;
  - BestOfN and PUCT tie on 18/20 cases and each wins one selective-budget
    case, so neither is a global winner;
  - PUCT budget eight regresses to `12/20` at 160 observations and is preserved
    without tuning;
  - both inspected traces remain explicitly `MISSING_COUNTERFACTUAL`, with zero
    honest replay cases;
  - evidence is explicitly search-kernel-only and grants no end-to-end or
    production claim.
- Current Phase 5 result checkpoint: `17be287` (`data: record frozen Phase 5
  benchmark`); replay lock: `84f5072`.

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

## Deterministic one-ply strategy milestone

DONE: implemented `GreedyStrategy` and `BestOfNStrategy` behind the canonical
async `SearchStrategy` contract. Greedy chooses the maximum Policy prior over
the complete hard-legal generated set and reports root Value separately.
Best-of-N freezes maximum `N=4`, consumes injected immutable one-ply successors,
enforces exact branch and aggregate usage, and chooses by successor Value, then
Policy prior, then action ID. Neither strategy executes its selection.

TESTS:

- Greedy-specific: `27 passed`;
- Best-of-N-specific: `24 passed`;
- contracts plus both strategy suites: `70 passed`;
- full SocratesZero bundle: `149 passed`;
- Hybrid H8 authority plus SocratesZero: `160 passed`;
- full `tests_dialogues`: `2215 passed, 1 skipped`;
- repository-wide: `2522 passed, 1 skipped, 23 pre-existing warnings`;
- staged `git diff --check`: passed;
- no live external call was made.

FILES CHANGED:

- `backend/dialogues/socrates_zero/strategy.py` — Greedy and Best-of-N;
- `backend/dialogues/socrates_zero/contracts.py` — additive `ActionSuccessor`
  and `SuccessorStateEvaluator` seam;
- `backend/dialogues/socrates_zero/__init__.py` — runtime-inert exports;
- two dedicated strategy test modules;
- canonical ADR/technical reference and branch checkpoints.

COMMITS:

- `8e10dfe` — deterministic Greedy strategy;
- `aa2c1dd` — budgeted one-ply Best-of-N strategy.

KNOWN ISSUES:

- no canonical CED successor evaluator/action executor exists; injected test or
  experimental evaluators cannot mutate governing CED state;
- the deterministic legal generator currently returns canonical subsets, not
  diverse or sampled action proposals;
- evaluator identity and a standalone per-candidate event/receipt schema remain
  deferred; v0 uses parallel receipt tuples for action-to-successor mapping;
- no matched benchmark yet establishes Greedy or Best-of-N quality gains;
- the 23 warnings remain pre-existing Pydantic `.dict()` deprecations and
  duplicate FastAPI operation IDs.

HISTORICAL NEXT: Phase 4 bounded PUCT over the same injected successor seam.
The completed design below kept transpositions path-local and correctly
deferred progressive widening.

## Bounded deterministic PUCT milestone

DONE: implemented serial `PUCTStrategy` (`puct-strategy/v0`) over the complete
hard-legal root edge set. `PUCTConfig` (`puct-config/v0`) freezes the canonical,
untuned `c_puct=1.0` and finite `(0,100]` range. Selection uses
`Q + c_puct * P * sqrt(max(1,N)) / (1+N_a)` with score, prior, then action-ID
ties. Final root selection uses visits, Q, prior, then action ID.

Every visit performs a fresh experimental successor call from the immutable
root and consumes its actual usage; no cached Value creates a pseudo-visit.
Observed leaf V is backed up without sign alternation or discount. The seam has
no recursive capability declaration or canonical implementation, so v0's safe
relative depth is exactly one regardless of a larger configured depth. Child
states are never evaluator inputs, duplicate semantic state IDs keep path-local
statistics, and no second CED transition engine exists.

The frozen `SearchReceipt` schema and baseline identities remain unchanged.
`PUCTSearchReceipt` (`puct-search-receipt/v0`) is a separately versioned,
immutable linked companion with dependency IDs, config, nodes, edges, P/N/Q,
successor IDs, leaf Values, simulations, exact usage, tie rules, duplicate-state
diagnostics, failure/pruning fields, selected root action, and termination.
Completed receipts cannot silently encode failed or pruned branches. Any
successor failure invalidates the entire search because the current seam has no
cost-bearing failure result contract.

TESTS:

- PUCT-specific: `53 passed`;
- Greedy-specific: `27 passed`;
- Best-of-N-specific: `24 passed`;
- Policy-specific: `13 passed`;
- Value-specific: `21 passed`;
- contracts plus Greedy/Best-of-N/PUCT: `123 passed`;
- full SocratesZero bundle: `202 passed`;
- Hybrid H8 plus SocratesZero: `213 passed`;
- focused CED/Socratic regressions: `142 passed`;
- full `tests_dialogues`: `2268 passed, 1 skipped`;
- repository-wide: `2575 passed, 1 skipped, 23 pre-existing warnings`;
- `git diff --check`: passed;
- no live external call was made.

FILES CHANGED:

- `backend/dialogues/socrates_zero/puct.py` — config, explicit node/edge/
  simulation/audit contracts and bounded serial PUCT engine;
- `backend/dialogues/socrates_zero/__init__.py` — runtime-inert public exports;
- `tests_dialogues/test_socrates_zero_puct_strategy.py` — deterministic search,
  math, budget, failure, isolation, replay, transposition and no-fake-depth tests;
- canonical ADR and branch checkpoints.

COMMIT:

- `c7e45b9` — bounded deterministic one-real-ply PUCT strategy and tests.

KNOWN ISSUES:

- no canonical CED successor evaluator/action executor exists;
- recursive successor safety is unproven, so v0 cannot perform real multi-ply
  selection even when the hard budget permits more depth;
- model/tool/token/cost/time pre-reservation belongs to the injected evaluator
  because the strategy cannot know an unseen delta; every returned delta is
  still checked exactly in aggregate;
- evaluator exceptions cannot carry consumed usage under the current protocol,
  so v0 fails the entire search rather than fabricating a partial receipt;
- heuristic Value remains penalty-only and often ties;
- no matched-compute evidence yet establishes PUCT over simpler baselines;
- the 23 warnings remain pre-existing Pydantic `.dict()` deprecations and
  duplicate FastAPI operation IDs.

HISTORICAL NEXT: Phase 5 matched-compute evaluation harness comparing fixed
rotation, Greedy, Best-of-N, and PUCT. Do not start RL.

## Frozen matched-compute evaluation milestone

DONE: implemented and executed the offline
`socrateszero-search-kernel-eval-harness/v0` against
`socrateszero-search-kernel-case-set/v0`. The suite freezes two cases in each
of ten categories, matches BestOfN-4 and PUCT-4 on the same root/actions/
Policy/Value/successor environment, and separately reports actual successor,
Policy, Value, node, and expansion usage. Ground truth remains evaluator-only;
state/order isolation and deterministic semantic replay are enforced.

RESULT:

- Greedy + Heuristic Policy/Value: `9/20`, total regret `11.55`, 0 successor
  observations;
- BestOfN-4 + Heuristic Policy/Value: `15/20`, regret `4.80`, 62 observations;
- PUCT-4 + Heuristic Policy/Value: `15/20`, regret `4.55`, 80 observations;
- paired BestOfN/PUCT: 18 ties, one higher-outcome case each;
- failures/not-evaluable in deterministic matrix: `0/0` for every run;
- real trace replay: `0` evaluable, `2` missing counterfactual;
- live API/provider/tool calls: `0`.

ABLATIONS:

- Uniform+Neutral beats Heuristic+Neutral by one case for Greedy and PUCT-4;
- Heuristic Value raises BestOfN and PUCT-4 from `9/20` to `15/20` with
  Heuristic Policy fixed;
- PUCT budgets 1/2/4/8 produce `9/12/15/12` correct at
  `20/40/80/160` observations, so more depth-one compute is not monotone.

ARTIFACT:

- `docs/branches/feature-socrates-zero-search-v0/artifacts/`
  `socrateszero_search_kernel_benchmark_v0.json`;
- ID `szevalartifact_dc795fdef6b64e56b808b990fedd764def7c6e1858d178d29c26aa3280ede710`;
- normalized SHA-256
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`;
- second execution: byte-identical.

TESTS:

- evaluation-specific: `37 passed`;
- PUCT / BestOfN / Greedy: `53 / 24 / 27 passed`;
- Policy / Value: `13 / 21 passed`;
- contracts plus Greedy/BestOfN/PUCT: `123 passed`;
- full SocratesZero: `239 passed`;
- Hybrid H8 plus SocratesZero: `250 passed`;
- focused CED/Socratic: `142 passed`;
- full `tests_dialogues`: `2305 passed, 1 skipped`;
- repository-wide: `2612 passed, 1 skipped, 23 pre-existing warnings`;
- live API calls: `0`.

KNOWN LIMITATIONS:

- 20 authored deterministic fixtures are exact diagnostics, not population
  evidence;
- PUCT remains one real ply and the fixture successor is not a canonical CED
  action executor;
- current heuristic Value is penalty-only and cannot distinguish cases whose
  SearchState exposes no canonical positive outcome signal;
- the result establishes no end-to-end CED/Socrates improvement, live latency,
  factuality, or production cost claim.

PHASE 5 STATUS: COMPLETE

COMPLETION RECORD:

- branch: `feature/socrates-zero-search-v0`;
- verification base HEAD: `b2fdcc4` (the final seal after this point is
  documentation-only);
- chronology: `63e5b0b` budgets/contracts → `280803b` cases → `d30970d` and
  `60c15fc` pre-result leakage corrections → `4ba0d99` harness → `3e8cb89`
  fairness tests → `6de4f6e` runner → `17be287` first result artifact →
  `84f5072` replay lock → `b2fdcc4` durable checkpoint;
- frozen result artifact remains owned by `17be287` and was not rewritten by
  completion verification;
- no live call, production authority, learned component, RL, or Phase 6 work
  exists.

NEXT: **Phase 5.5 — Evidence Review / Architecture Decision Gate**.

That gate may decide among safe deeper successor semantics, richer canonical
verification/resolution state, real read-only shadow orchestration, governed
trajectory/learned-Value preparation, or simplification/deprioritization of
PUCT. Phase 5 selects none of them.

## Phase 5.5 evidence review and architecture decision gate

DONE: verified the sealed Phase 5 repository/artifact and completed a
documentation-only causal review. The authoritative JSON remains byte-equal to
its `17be287` Git blob with SHA-256
`21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
No core, benchmark, provider, search, Policy, Value, SearchState, successor,
CED, training, or production behavior changed.

CORE EVIDENCE:

- Heuristic Policy versus Uniform, under the only two matched Neutral-Value
  controls: 6 improved, 8 worsened, 6 unchanged, `-1` correct and `+2.30`
  regret in both Greedy and PUCT. Verdict: `HARMFUL` in the frozen regime.
- Heuristic Value versus Neutral with Heuristic Policy fixed: BestOfN gains six
  correct and removes 6.95 regret; PUCT gains six correct and removes 7.00
  regret. Greedy is unchanged because it is Policy-only. Verdict: `SUPPORTED`.
- Greedy H/H to BestOfN-4 H/H: `+6` correct, `-6.75` regret, `+62` successors.
  BestOfN-4 to PUCT-4: `0` correct, `-0.25` regret, `+18` successors. Real
  successor observation plus Value accounts for almost all measured gain.
- BestOfN and PUCT are `CO-CHAMPIONS`: BestOfN is the stronger
  complexity-adjusted experimental anchor, while PUCT keeps a 0.25 regret
  advantage and remains research-only.

PUCT-8 FORENSIC:

- only `best_of_n_sufficient_02` and the two heuristic-value-informative cases
  regress from budget four to eight;
- at budget four each action has one visit, so Q selects the optimum;
- at budget eight deterministic repeated observations add no information, but
  high-prior actions receive more visits and visit-count-first root selection
  chooses them despite worse Q;
- classification: expected frozen algorithmic behavior plus a depth-one design
  limitation; no invariant violation or possible bug was found.

ARCHITECTURE VERDICT:

- both value-uninformative fixtures lawfully hide their evaluator-only future
  utilities, so no Value may recover those exact labels;
- real Hybrid/CED state nevertheless owns typed verification, claim support,
  objection/contradiction lifecycle, and evidence semantics that SearchState
  v0 makes opaque or omits;
- current Value is both estimator- and information-limited, with canonical
  observability the prerequisite uncertainty;
- depth two is not legitimate: no canonical recursive isolated CED action
  executor exists, and a second reconstructed CED is forbidden;
- existing shadow infrastructure observes completed production sessions but
  cannot execute isolated action counterfactuals;
- RL is `NOT YET EARNED`; learned Value and learned Policy are premature.

PHASE 5.5 STATUS: COMPLETE

REPORT:

- `docs/SOCRATES_ZERO_PHASE5_5_DECISION_GATE.md` contains the full 11-run
  reconstruction, paired/categorical attribution, PUCT receipts,
  value-uninformative and SearchState audits, positive-signal inventory,
  depth-two/real-shadow blocker maps, readiness gates, decision matrix, and
  falsification contract.

EXACTLY ONE SELECTED NEXT MILESTONE:

- branch: `feature/socrates-zero-canonical-observability-v1`;
- hypothesis: real CED decision states contain already-authoritative typed
  epistemic distinctions that v0 aliases, and a separately versioned opt-in v1
  projection can preserve them without inference or new authority;
- initial scope: typed projection plus deterministic observability report only;
- frozen: all Phase 5 components and the v0 projection/default runtime;
- explicit non-goals: no Value/Policy/search/depth/successor/provider/shadow/
  learning/RL/production change.

NEXT: implement nothing on this branch unless separately authorized. A future
observability branch must pass its predeclared success/falsification gate before
any Value v1 or other roadmap step is considered.

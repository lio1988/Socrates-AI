# ADR: SocratesZero Search Boundary v0

Status: accepted through deterministic model-free Policy, Value, one-ply
strategy foundations, bounded one-real-ply PUCT, frozen offline Phase 5
search-kernel evaluation, and opt-in canonical observability v1 on
`feature/socrates-zero-canonical-observability-v1`

Baseline: commit `277ca2ec130ce120dba9c4d894a3c58138b25528`

## Decision

SocratesZero is an optional search and learning layer around the canonical CED,
not a replacement epistemic authority and not a second orchestrator.

The CED and the governing Hybrid core retain veto power over every proposed
action and every release decision. Search may propose, allocate compute, and
rank legal actions. It may not manufacture moves, evidence, scores, provider
success, verification, support, ratification, or release.

Phase 1 introduces strict immutable contracts only. It does not read
`SOCRATES_ZERO_ENABLED`, change `CEDOrchestrator`, execute an action, call a
provider, run MCTS, train a model, or alter the fixed-rotation baseline.

## Repository evidence and current execution

The canonical production-shaped path is
`backend/dialogues/ced.py::CEDOrchestrator.run_registry_session`:

1. create the CED-owned `SessionState` and freeze logical-agent to physical-seat
   bindings;
2. check provider readiness and quorum;
3. execute Opening, Initial Response, Elenchus, Reflection, bounded additional
   Elenchus/Reflection cycles, Reconstruction, and Synthesis;
4. create five-section drafts, run blind no-self peer scoring, and assemble;
5. run council ratification and optional bounded runner-up repair;
6. apply the governing Hybrid release path where configured, then finalize
   audit, observers, traces, and learning outputs.

The fixed scheduler is implemented by `_PHASE_INDEX`, `_PHASE_ROLE_SLOTS`,
`_PHASE_ALL_AGENTS_ROLE`, and `CEDOrchestrator.assign_roles_for_phase`. Its
inputs are session identity, phase, round, and sorted logical agent IDs; the
result is recorded in `SessionState.role_history`. Reflection is tied to the
agents who produced the relevant initial response. `AgentTask.task_id` remains
random historical audit identity, while accepted CED `move_id` values are
derived deterministically from task shape.

The existing `backend/dialogues/deliberation_tree.py` is retained. It is an
opt-in flat UCB search over synthesis-draft revisions, using blind peer quality
scores and enriching the assembly pool. It is not general epistemic-state MCTS,
does not define the Socratic action space, and must not be reinterpreted as
truth or support authority.

## Constitution versus policy

The following are constitutional and remain deterministic vetoes:

- CED ownership of phase advancement, role assignment, task routing, quorum,
  retries, provider failure, assembly governance, and release plumbing;
- the Hybrid core's sole authority over claim support, admissible evidence,
  validated objections/contradictions, compatibility, and frozen release;
- exact actual-model identity, fail-closed provider status, bounded waits, and
  no fabricated move on failure;
- structured task/move schemas, legal target references, no self-scoring,
  blind scoring, missing-is-missing, and score/support separation;
- provenance, immutable observations, deterministic verifier dominance, and
  receipt/audit integrity;
- hard search budgets and a final CED validation immediately before execution.

The following are historical or strategic choices and may become comparable
policies only behind the constitution:

- the exact fixed phase order and deterministic role rotation;
- which available legal seat/action is selected and how compute is divided;
- the exact number of follow-up cycles within constitutional bounds;
- adaptive-dialectic and seat-routing heuristics;
- all/synthesis/sampled/off quality-scoring policy;
- one-shot synthesis, Best-of-N, best-first, UCT, PUCT, or another bounded
  search strategy;
- deliberation-tree exploration constants and revision allocation;
- policy priors and value estimates, which are advisory even when learned.

Some settings straddle this boundary. For example, a maximum retry/follow-up
bound is constitutional, while choosing zero, one, or two legal opportunities
inside that bound is policy. The CED must own the hard ceiling.

## Reuse and insertion points

Phase 1 reuses the repository's strict Pydantic pattern, full SHA-256 canonical
identity, Hybrid record references, authority classification, and fail-closed
budget validation. It deliberately does not import legacy `backend/epistemic`
or `backend/epistemic_graph`; those graphs and the Dung adapter are retained as
legacy diagnostics/pattern donors, not governing state.

The future insertion seam is a read-only projection from CED/Hybrid public
state into `SearchState`, followed by:

```text
CED/Hybrid snapshot
  -> constitution.legal_actions(state)
  -> proposal/prior/value/search
  -> CED.validate(selected_action)
  -> canonical CED task/provider/verifier execution
  -> immutable observation + next snapshot
```

Shadow mode must run beside the baseline and must not select production output.
Only after matched-budget evidence and an explicit later ADR may an enabled
search policy select a production action. The disabled path must remain the
existing path, not a reimplementation of it.

## Existing signals and their permitted use

- `task_checker.py` and Hybrid verification records provide deterministic,
  authoritative checks only for their declared scope.
- admissible external evidence and Hybrid claim assessments may affect
  epistemic value; unsupported provider prose may not.
- peer move/section scores, cohesion, reliability flags, and the leaderboard
  are quality/process signals only.
- council ratification is governance/advisory with respect to truth; it cannot
  promote an unsupported claim.
- ground-truth checks, the evidence harness, record/replay, dialectic-delta,
  protocol-evolution reports, and the promotion arena are evaluation inputs;
  promotion remains gated and non-automatic.
- the learning pipeline, trace collector, preference/process miners, and tree
  distillation change future behavior only.

Observer/event projections in `backend/orchestrator` are legacy or read-only.
The Hybrid append-only ledger is the current canonical record substrate. The
shared `AtomicReceiptStore` is authoritative over durable bytes, not truth.

## Phase 1 contract decisions

- Semantic state identity excludes session/task UUIDs, parent IDs, timestamps,
  latency, route IDs, and raw provider metadata.
- Identity includes the canonical question/task/phase, immutable artifact
  digests, exact known model identity for observations, relevant ordered
  history, policy context, budget usage, depth, and terminal state.
- Equivalence is conservative: no natural-language similarity merge exists.
- Legal actions are typed macro-actions with deterministic identities and
  target-shape validation. Extra fields are rejected.
- Action generators receive the hard legal set; policy/search cannot enlarge
  it. Target IDs are validated against the snapshot again before execution.
- Cost uses integer micro-USD and time uses integer milliseconds to avoid
  floating-point identity drift.
- Search receipts contain IDs, digests, bounded statistics, and violations;
  they contain no hidden chain of thought.
- Interfaces are provider-neutral and have no neural/CUDA dependency.

## Board-state and legal-moves implementation

The first executable research foundation remains read-only and runtime-inert:

- `CEDOrchestrator.canonical_registry_task_specs()` is the one extraction point
  for fixed orchestration. Canonical registry execution consumes the same
  frozen specs; the experimental baseline contains no copied rotation table.
- `FixedRotationBaselineStrategy` translates CED's already-selected task kind
  into one hard-legal macro-action. It performs no provider, generator, prior,
  or value call and executes nothing.
- `ced_search_projection.py` is a trusted CED-side boundary. It may read the
  governing Hybrid records, validates references, and emits only immutable
  digests/IDs into `SearchState`. The non-governing search package never imports
  or reaches `hybrid_epistemic` directly.
- The projection excludes timestamps, task/session audit UUIDs, route IDs,
  latency, scores, and unavailable provider completeness. It includes accepted
  move content digests, stable role/move history, authoritative live
  commitments, admissible evidence, structured unresolved objections,
  contradictions, verification records, and candidate reconstruction/synthesis
  references when those records actually exist.
- `CEDSearchConstitution` emits a deterministic initial vocabulary of Socratic
  question, initial proposal, generic elenchus, targeted claim challenge,
  reflection, targeted claim defence, reconstruction, final synthesis,
  ratification, and terminal stop. Stable order is action type plus canonical
  target/parameter encoding.
- Reflection requires an accepted same-cycle Socratic question; follow-up and
  reconstruction bounds fail closed; terminal snapshots expose only `STOP`.
  The baseline action is tested to be a member of the legal set for actual CED
  phase prefixes from Opening through Synthesis.
- Projection, baseline-adapter translation, legal-action vocabulary, and legal
  generator semantics each expose an explicit `v0` identifier. A source state
  that contains a final response before canonical `COMPLETE` is rejected rather
  than projected as an ambiguous terminal board.

No method in this milestone calls `legal_actions()` from production execution,
reads the feature flag, or permits a selected action to control CED.

## Phase 3A deterministic policy boundary

Constitution defines what is legal. Policy receives an already-legal tuple and
ranks only that tuple; it cannot generate, legalize, repair, execute, or grant
epistemic status to an action. `HeuristicPolicyPrior` therefore depends on
`SearchState` public structure and canonical action metadata only, while
`UniformPolicyPrior` is the explicit `1/N` control.

Heuristic v0 uses base weight `1.0` and three inspectable signal families:
unresolved contradiction, unresolved question, and valid canonical claim
target. Its fixed adjustment table is public in code and every applied change
has a structured reason code. Normalization preserves canonical action order,
reserves final probability `1e-6` for every supplied action, returns `1.0` for a
singleton, and returns empty output for empty input. The versions are
`heuristic-policy-prior/v0` and `uniform-policy-prior/v0`.

Policy does not read quality scores, agreement, ratification popularity,
epistemic markers, provider/model identity, or natural-language length. It has
no execution or governing authority. Heuristic v0 is neither learning nor RL,
and this phase adds no Value, Greedy, Best-of-N, MCTS, neural, or CUDA path.

## Phase 3B deterministic Value boundary

Value estimates the promise of one current valid `SearchState`; it does not
decide truth, legality, verification, action preference, or execution. Both
estimators use the canonical async `ValueEstimator` contract and the range
`[-1,+1]`. `NeutralValueEstimator` (`neutral-value-estimator/v0`) returns
`0.0`. `HeuristicValueEstimator` (`heuristic-value-estimator/v0`) exposes a
deterministic structured component audit and stable audit ID.

Heuristic v0 is penalty-only. Unresolved contradictions contribute `-0.08`
each down to `-0.24`; unresolved questions/objections contribute `-0.05` each
down to `-0.20`; blocked and budget-exhausted terminal states contribute
`-0.20` and `-0.10`. `ANSWER_READY` and `ABSTAINED` are explicit neutral
components: completion is not verification, and epistemically honest abstention
is not failure.

The frozen component reason codes are `unresolved_contradiction`,
`unresolved_question`, `terminal_blocked`, `terminal_budget_exhausted`,
`answer_ready_is_not_verification`, and `epistemic_abstention`.

This conservatism is required by repository truth. Projected contradiction and
question collections contain unresolved records only, while verification
outcomes are not inspectable through `ObservationRef` semantic digests. Value
therefore assigns no fabricated reward for resolution or verification. It also
ignores scores, consensus, ratification popularity, epistemic markers,
provider/model identity, prose, evidence/citation count, Policy context, and
future fixture labels/rewards. Invalid structural terminal combinations fail
closed instead of mapping to `-1`.

Value calls neither Policy nor `Constitution.legal_actions()` and has no
epistemic or execution authority. Phase 3B adds no Greedy, Best-of-N, MCTS, RL,
neural, or CUDA implementation.

## Phase 3C deterministic strategy boundary

Greedy and Best-of-N implement the existing async `SearchStrategy` contract and
return the existing `SearchResult`/`SearchReceipt`; neither is connected to CED
execution. `GreedyStrategy` (`greedy-strategy/v0`) ranks the complete generated
hard-legal set by Policy prior, breaks ties by action ID, and reports root
`V(s)` separately. It records no fabricated visits, successor expansions, or
action-conditioned values.

The Phase-1 interface had no transition seam, so a real Best-of-N could not
compare successor Value without inventing `Q(s,a)` or fabricated states. The
smallest additive correction is `ActionSuccessor` plus the injected
`SuccessorStateEvaluator` protocol. An outcome binds one legal action ID to one
immutable one-ply SearchState and an exact branch-local `BudgetUsage` delta.
The evaluator is experimental input, not a production executor or governing
observation source.

`BestOfNStrategy` (`best-of-n-strategy/v0`) freezes maximum `N=4`. Available
nodes, expansions, and depth can reduce N. Candidate successors are evaluated
in action-ID order; aggregate sibling compute is enforced against one shared
hard budget. Successor `V(s')` ranks first, Policy prior breaks equal-Value
ties, and action ID is final. The current receipt's parallel deterministic
`expanded_action_ids` and post-root `visited_state_ids` preserve each
action-to-successor link without silently changing the frozen v0 statistics
schema.

Terminal Stop and no-legal/budget-exhausted roots do not fabricate successors.
Both strategies validate all inputs and values, execute nothing, and have no
support, verification, ratification, stopping, or production-response
authority. Phase 3C adds no canonical successor evaluator, provider call,
shadow wiring, PUCT/MCTS, learning, neural, or CUDA implementation.

## Phase 4 bounded deterministic PUCT boundary

`PUCTStrategy` (`puct-strategy/v0`) is a serial, runtime-inert allocator over
the same hard-legal actions, Policy, Value, budget, and experimental successor
seam as the frozen baselines. It does not execute the selected action. Its
immutable `PUCTConfig` (`puct-config/v0`) exposes an untuned canonical
`c_puct=1.0`, rejects non-finite/disabled values, and bounds the numeric range
to `(0,100]`.

For root state `s`, edge `a` is selected by:

```text
Q(s,a) + c_puct * P(a|s) * sqrt(max(1, N(s))) / (1 + N(s,a))
```

Unvisited Q is explicitly zero. The `max(1,N)` term makes the first selection
prior-ordered rather than dependent on accidental zero ties. Selection ties
use score descending, prior descending, then action ID ascending. The complete
hard-legal set is registered as root edges; neither Policy nor Value may remove
or add an edge. Positive-prior edges remain reachable as their exploration term
grows under sufficient budget.

Every simulation selects one root edge, invokes the injected evaluator on the
same immutable root, validates one real child, evaluates that observed child
with the configured Value, and backs the Value into the edge/root running mean.
Repeated edge visits are repeated charged evaluator calls, never cached
pseudo-visits. Q is therefore mean observed successor V, distinct from V(s).
Backup is undiscounted and retains one epistemic utility orientation; it never
alternates signs as if CED were a two-player zero-sum game.

The existing successor protocol gives no recursive-safety, determinism,
isolation, capability, or cost-bearing failure guarantee, and the repository
contains no canonical successor executor. PUCT v0 therefore freezes maximum
safe relative depth at one even when `SearchBudget.max_depth` is larger. Child
states are recorded and valued but never passed back to the evaluator or
Constitution. This is adaptive root search, not fabricated multi-ply MCTS.
Identical child state IDs retain separate path-local nodes/statistics and are
recorded only as duplicate-state diagnostics.

Existing `ActionSuccessor` accounting requires one node and one expansion per
real observation so PUCT preserves matched counters with Best-of-N. Full root
edge registration is bounded deterministic in-memory bookkeeping and invents
no usage delta. Before each observation the strategy checks nodes, expansions,
and depth. The evaluator receives current aggregate usage and must reserve
model/tool/token/cost/time before work because only it knows the prospective
delta; PUCT then validates branch-local and aggregate returned usage exactly.

Root completion is deterministic: visit count descending, Q descending, prior
descending, then action ID ascending. Terminal roots are validated but neither
expanded nor observed and return no fabricated Stop selection. A successor
error invalidates the entire v0 search; there is no arbitrary negative reward,
silent prune, or invented continuation.

The frozen canonical `SearchReceipt` is not silently expanded.
`PUCTSearchReceipt` (`puct-search-receipt/v0`) is a linked immutable companion
containing config/dependency identities, bounded node/edge/simulation facts,
P/N/Q, successor and leaf IDs/Values, exact usage, deterministic tie rules,
duplicate states, failure/pruning fields, selection, and termination.
`PUCTStrategy.search()` still satisfies `SearchStrategy` and returns the
canonical `SearchResult`; `evaluate()` returns that result with its rich PUCT
receipt. No hidden reasoning or volatile timestamp participates in identity.

The deterministic fixtures prove both directions of adaptive compute: a tiny
budget follows a misleading high-prior branch, while sufficient budget observes
and selects the better lower-prior branch. Neutral and heuristic Value share the
same engine and produce separately auditable behavior. No shadow or production
wiring, Gumbel, progressive widening, MuZero, RL, neural, CUDA, or parallel tree
mutation is introduced.

## Phase 5 frozen evaluation boundary and decision

Phase 5 adds evaluation infrastructure only. The immutable harness
`socrateszero-search-kernel-eval-harness/v0` evaluates the frozen strategies on
the balanced 20-case `socrateszero-search-kernel-case-set/v0` under precommitted
successor-observation budgets 1, 2, 4, and 8. It imports no CED orchestrator,
provider, tool, learner, neural runtime, or production executor.

Ground truth remains an evaluator-side numeric ordering in `[-1,+1]`. The
strategy receives only a fresh root, hard-legal actions, label-free successor
observation blueprints, frozen Policy/Value, Constitution, generator, and
budget. Case names, categories, outcomes, optima, and even the case identity
derived from them are absent. The harness independently counts successor,
Policy, and Value evaluations and derives node/expansion deltas from receipts;
the deterministic successor also enforces its own monotone aggregate call
count. Failures and missing cases remain in explicit denominators.

The primary controlled comparison holds Heuristic Policy and Heuristic Value
fixed at a maximum four successor observations. Greedy selects 9/20 optima with
total regret 11.55 and zero successors. BestOfN selects 15/20 with regret 4.80
and 62 actual successors. PUCT selects 15/20 with regret 4.55 and 80 actual
successors. BestOfN and PUCT agree in outcome on 18 cases and each wins one of
the two selective-budget cases. This is a Pareto tradeoff, not a global PUCT
win: BestOfN achieves the same correctness with less compute, while PUCT has
0.25 less total regret.

PUCT quality is non-monotone across the frozen depth-one sweep: budgets 1, 2,
4, and 8 select 9, 12, 15, and 12 optima respectively. Budget eight consumes
160 observations but matches budget two's quality at 40. The result is retained
without tuning. Heuristic Value materially improves both search strategies in
this suite; Heuristic Policy under Neutral Value is one case worse than Uniform
Policy. These findings support neither learned components nor production
promotion.

The artifact is explicitly scoped `SEARCH_KERNEL_EVALUATION`. It cannot support
an end-to-end claim that SocratesZero improves CED dialogue. The two existing
trace candidates lack observed counterfactuals and remain explicitly missing;
none are guessed. A later live/replay shadow or deeper successor milestone
requires a separate ADR and approval. Phase 5 creates no Phase 6, RL, learned
Policy/Value, self-play, provider spending, or runtime action authority.

The next step is explicitly `Phase 5.5 — Evidence Review / Architecture
Decision Gate`, not implementation. It must weigh: (A) safe deeper successor
semantics, (B) richer canonical verification/resolution state, (C) real
read-only shadow orchestration, (D) governed trajectory collection and
learned-Value preparation, and (E) simplification/deprioritization of PUCT.
The observed depth-one horizon and penalty-only leaf signal are diagnostic
hypotheses, not authorization to change either contract.

## Phase 5.5 evidence gate decision

Phase 5.5 is a documentation-only review of the sealed artifact. The exact
paired evidence attributes almost all measured gain to successor observation
plus non-neutral Value: Greedy H/H to BestOfN-4 H/H adds six correct cases and
reduces regret by 6.75, whereas BestOfN-4 to PUCT-4 adds no correct case and
reduces regret by only 0.25 at eighteen additional observations. The two legal
Heuristic-Policy versus Uniform-Policy controls both lose one correct case and
add 2.30 regret. Heuristic Value, held against Neutral Value, adds six correct
cases to both BestOfN and PUCT.

The PUCT-8 degradation is not an invariant violation. In the three regressed
cases, budget four visits all four actions once and root Q selects the optimum.
Budget eight repeats deterministic one-ply observations; higher-prior actions
gain more visits, and visit-count-first root selection chooses them despite a
worse Q. This is expected frozen behavior and a depth-one design limitation,
not evidence that general adaptive compute is invalid.

The gate selects exactly one next research milestone:
`feature/socrates-zero-canonical-observability-v1`. Its sole hypothesis is that
real CED decision states contain already-authoritative typed Hybrid/CED
epistemic distinctions that `SearchState v0` aliases as opaque digests or
omits. The milestone may add only an opt-in, separately versioned typed
projection and an observability report. It freezes v0 Policy, Value, search,
successor depth, cases, budgets, artifact, CED behavior, and Hybrid authority.
It adds no estimator, learned component, provider call, shadow branch, action
executor, or production wiring.

The full evidence reconstruction, observability table, depth-two blocker map,
readiness gates, decision matrix, falsification criteria, and frozen-component
list are recorded in `docs/SOCRATES_ZERO_PHASE5_5_DECISION_GATE.md`.

## Phase 6 canonical observability boundary

Phase 6 proves the selected representation hypothesis without changing an
estimator or execution path. `SearchStateV1`
(`socrates.zero.search-state/v1`) is an immutable CED-side envelope around the
unchanged v0 `SearchState`; `project_search_state_v1()` is explicitly versioned
`ced-search-state-projection/v1` and must be called directly. Neither is wired
into default CED or exported from the v0 projection module.

The contract remains on the trusted CED side because it uses the actual Hybrid
enums. The runtime-inert search package still does not import the governing
core. The v1 projector invokes the unchanged v0 projector first, revalidates
the present Hybrid snapshot, asks the authority for `assess_all()`, and copies
only current typed results. It does not reproduce support, objection, or
contradiction rules.

The accepted observation families are:

- admissible evidence claim/stance/source-type/receipt links;
- verification class/method/result and claim/objection/evidence links;
- governing claim `SupportState`, basis/falsifying/unresolved record IDs, and
  assembly eligibility;
- objection state/scope/target provenance and verification link;
- contradiction state/claim pair and verification link.

Every record-backed view retains its real source record ID. Claim assessments
have no source record of their own, so v1 creates none; provenance is the real
claim ID plus the exact record IDs returned by the governing assessment.
Observation identity contains only typed enums, IDs and relationships. Raw
prose, scores, consensus, confidence, markers, route/model identity,
ratification and future outcomes are absent. Existing v0 digests remain inside
the base snapshot for replay/audit compatibility.

The source audit rejected an explicit resolved-question field: `InquiryState`
is a process recommendation and `AporiaRecord` is an open remainder, not a
governing resolution lifecycle. It also rejected upstream epistemic abstention:
`ABSTAINED` exists only in downstream search vocabulary. Operational provider
failure, commitment/revision history, ratification, scores and consensus are
not promoted into the minimal epistemic schema.

Two exact v0 alias classes prove information loss. First, the Hybrid authority
assesses otherwise identical `VERIFIED` task-internal records differently when
one is a protocol/deterministic check and one is model-produced; v0 gives them
the same semantic state ID and exposes no assessment, while v1 preserves
`SUPPORTED` versus `UNSUPPORTED` directly from `assess_all()`. Second, v0
projects no-record and canonically `DISMISSED` contradiction states identically,
while v1 preserves the literal dismissed lifecycle record. Additional tests
show typed `VERIFIED`/`FALSIFIED`, `SUPPORTED`/
`EXTERNAL_EVIDENCE_REQUIRED`, and resolved objection distinctions that v0 only
digests or omits.

The projector is side-effect free, dictionary-order independent, current-time
only, and fail closed on duplicate/cross-family IDs, dangling provenance,
misindexed ledger records, and malformed verification records. Opposite future
verification outcomes do not affect identical prefix projections. Scores,
markers, confidence, stylistic prose, and changes between non-null provider/
model identities leave the new typed views unchanged.

Phase 6 is representation evidence only. It makes no strategy-quality claim
and grants no Value, Policy, search, successor, provider, learning, release, or
production authority. The complete matrix, digest audit, pair evidence,
limitations and verification record are in
`docs/SOCRATES_ZERO_CANONICAL_OBSERVABILITY_V1.md`. The hypothesis is
**SUPPORTED**. Work stops at a separate **Value v1 Decision Gate**; no Value v1
exists on this branch.

## Known gaps and deferred work

- There is no canonical cross-provider token/cost meter yet.
- Random `AgentTask.task_id` cannot be load-bearing replay identity.
- Role-specific content validation beyond the hardened Socratic contract
  remains partial.
- The initial legal vocabulary is deliberately bounded and no general
  constitutional action executor exists yet.
- Canonical task-spec equivalence currently covers registry deliberation from
  Opening through Synthesis; council ratification remains a separate canonical
  provider path.
- A matched-compute deterministic search-kernel evaluation now exists, but it
  is a small handcrafted one-ply fixture suite, not a stochastic or end-to-end
  Socrates dialogue benchmark.
- General external-world verification remains incomplete outside declared
  deterministic checks and supplied evidence.
- SearchState v1 exposes useful governing distinctions, but no Value version
  consumes it yet. Whether a transparent Value v1 improves a new leakage-safe
  evaluation remains a separate unanswered question.
- No canonical CED action executor or `SuccessorStateEvaluator` implementation
  exists; Best-of-N and PUCT are composable only with an injected experimental
  evaluator.
- Safe recursive transitions, shared transposition storage, progressive
  widening, and shadow execution remain deferred. Learned policy/value,
  self-play, and MuZero-style models require later evidence and explicit scope.
- The successor exception contract carries no usage delta, so work consumed by
  a failing evaluator cannot yet be represented in a completed partial receipt;
  PUCT v0 fails the whole search rather than guessing.

## Consequences

The branch now has the equivalent of an immutable board, hard legal moves, an
explicit handcrafted baseline player, versioned advisory Policy and Value,
deterministic Greedy and budgeted one-ply Best-of-N, plus bounded serial PUCT
that can rationally overturn Policy from real observed leaf Value. Frozen
Phase 5 evidence shows when current one-ply search helps and also shows that
BestOfN can match PUCT correctness with less compute. It is still
runtime-inert and gives Policy, Value, successor evaluators, and search no
execution or epistemic authority. The cost is intentional: this milestone makes
no end-to-end quality claim, has no canonical or recursively safe environment
transition, cannot recognize positive verified progress until the state
contract exposes it safely, and keeps its estimates weak, transparent, bounded,
auditable, and unexecuted.

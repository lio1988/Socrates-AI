# ADR: SocratesZero Search Boundary v0

Status: accepted through the board-state/legal-moves foundation on
`feature/socrates-zero-search-v0`

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

No method in this milestone calls `legal_actions()` from production execution,
reads the feature flag, or permits a selected action to control CED.

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
- The current evaluation families are heterogeneous; matched-compute
  SocratesZero benchmark episodes do not yet exist.
- General external-world verification remains incomplete outside declared
  deterministic checks and supplied evidence.
- Transposition storage, Best-of-N, heuristic prior/value, PUCT, progressive
  widening, shadow execution, learned policy/value, self-play, and MuZero-style
  models are deferred in that order.

## Consequences

The branch now has the equivalent of an immutable board, hard legal moves, and
an explicit handcrafted baseline player. It is still runtime-inert and gives
later policy/value/search work no execution or epistemic authority. The cost is
intentional: this milestone produces no quality gain and makes no strategic
choice beyond replaying the existing baseline.

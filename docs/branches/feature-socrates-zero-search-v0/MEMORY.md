# feature/socrates-zero-search-v0

## Durable facts

- Canonical engine: `backend/dialogues/ced.py`, especially
  `CEDOrchestrator.run_registry_session`.
- Fixed rotation: `_PHASE_INDEX`, `_PHASE_ROLE_SLOTS`,
  `_PHASE_ALL_AGENTS_ROLE`, and `assign_roles_for_phase`.
- Hybrid epistemic core is the sole support/release authority; scores,
  ratification, search, and learning may not manufacture support.
- Existing deliberation-tree search is an optional UCB synthesis-revision
  mechanism, not SocratesZero epistemic MCTS.
- `AgentTask.task_id` is random historical identity. Current accepted move IDs
  are deterministic but not yet the full versioned replay identity requested by
  SocratesZero.
- Provider failures remain failures; exact actual-model identity is a protocol
  fact; no silent substitution or fabricated output is permitted.
- Provider-envelope success is not CED acceptance. Socratic content is checked
  phase-aware at the CED boundary before accepted move identity is assigned.
- `marker_is_contracted(task_kind)` is the single prompt/parser authority for
  epistemic-marker presence. Marker data remains advisory and non-governing.
- Legacy graph/CBE/Dung components are non-governing and must not be wired into
  the new search path as authority.
- The current SocratesZero package is a runtime-inert research surface: no
  runtime flag reader, execution, provider call, MCTS, learning, PyTorch, GPU,
  or CUDA.
- `CanonicalTaskSpec` is the single read-only fixed-orchestration extraction;
  `_run_registry_phase()` consumes it, so the baseline adapter copies no
  rotation business logic.
- `backend/dialogues/ced_search_projection.py` is a trusted CED-side bridge.
  It may read governing records and emit frozen digests; the search package is
  forbidden from importing the Hybrid core directly.
- SearchState projection includes only recorded/validated source material.
  Provider receipts remain absent when exact canonical observation records are
  unavailable; no completeness is fabricated.
- The initial hard vocabulary is: Socratic question, initial proposal, generic
  elenchus, targeted challenge, reflection, targeted defence, reconstruction,
  final synthesis, ratification, and terminal stop.
- The fixed baseline is proven inside the legal set for actual canonical phase
  prefixes from Opening through Synthesis.
- Phase-2 semantic surfaces are separately versioned as
  `ced-search-state-projection/v0`, `ced-fixed-rotation-adapter/v0`,
  `ced-legal-action-vocabulary/v0`, and
  `ced-deterministic-legal-action-generator/v0`.
- `final_response` before canonical `DialogPhase.COMPLETE` is inconsistent
  source state and the projection must fail closed.
- Constitution owns legality; Policy may rank only the supplied legal set and
  cannot call back into `legal_actions()`, generate actions, or execute one.
- `HeuristicPolicyPrior` v0 is deterministic and model-free. It uses only three
  public signal families: unresolved contradiction, unresolved question, and
  valid canonical claim target. Every applied delta has a structured reason
  code, and no score, consensus, marker, provider identity, or prose heuristic
  is admitted.
- Every heuristic-supported action retains final probability at least `1e-6`;
  singleton input maps to `1.0`, empty input stays empty, and
  `UniformPolicyPrior` is the versioned `1/N` reference.
- Value consumes one current valid SearchState only. It cannot call Policy,
  Constitution, providers, future episode outcomes, benchmark labels, or reward.
- `NeutralValueEstimator` v0 returns `0.0`. `HeuristicValueEstimator` v0 is
  penalty-only: unresolved contradictions (`-0.08`, floor `-0.24`), unresolved
  questions (`-0.05`, floor `-0.20`), blocked terminal (`-0.20`), and exhausted
  budget (`-0.10`). Answer-ready and abstained states are neutral.
- Opaque verification digests, evidence count, consensus, scores, markers,
  provider/model identity, prose, Policy context, and candidate-answer polish
  are forbidden Value signals. Positive verified/resolved progress must remain
  unavailable until SearchState exposes canonical outcome semantics.
- Value range is `[-1,+1]`; structural invalidity raises rather than becoming
  `-1`. Each evaluation has a deterministic structured component audit/hash.
- `GreedyStrategy` v0 requires the complete hard-legal generated set and selects
  Policy argmax with an action-ID tie-break. Root Value remains separate from
  action statistics; no successor or action-conditioned value is fabricated.
- A genuine Best-of-N required an additive transition seam absent from Phase 1.
  `ActionSuccessor` binds one action to one immutable successor SearchState and
  exact branch-local usage; injected `SuccessorStateEvaluator` has no execution
  or governing authority.
- `BestOfNStrategy` v0 freezes maximum `N=4`, caps candidates by remaining
  nodes/expansions/depth, aggregates exact sibling usage, and selects by
  successor Value, Policy prior, then action ID.
- Best-of-N receipts preserve the deterministic positional mapping
  `expanded_action_ids[i] -> visited_state_ids[i+1]`. No canonical successor
  evaluator/executor, shadow integration, or candidate event schema exists yet.

## Protected local state

Two pre-existing untracked files are outside this branch's work and must remain
untouched:

- `scripts/live_dialogue.py.bak`
- the malformed root filename beginning `ocratic_followup_mandate`

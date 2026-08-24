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

## Protected local state

Two pre-existing untracked files are outside this branch's work and must remain
untouched:

- `scripts/live_dialogue.py.bak`
- the malformed root filename beginning `ocratic_followup_mandate`

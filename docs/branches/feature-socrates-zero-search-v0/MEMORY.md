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
- Legacy graph/CBE/Dung components are non-governing and must not be wired into
  the new search path as authority.
- Phase 1 is contracts only: no runtime flag reader, execution, provider call,
  MCTS, learning, PyTorch, GPU, or CUDA.

## Protected local state

Two pre-existing untracked files are outside this branch's work and must remain
untouched:

- `scripts/live_dialogue.py.bak`
- the malformed root filename beginning `ocratic_followup_mandate`

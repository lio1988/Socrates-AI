# Branch: feature/openrouter-live-provider

## Memory

- Canonical provider integration seam: `backend/dialogues/provider_registry.py`.
- OpenRouter live use is opt-in and must not change the default offline path.
- Exact model pinning and returned-model verification are mandatory.
- Silent fallback or substitution is forbidden.
- `OPENROUTER_API_KEY` is environment-only.
- CED authority, role rotation, scoring, assembly, and ratification remain unchanged.

## CANONICAL EXECUTION RESTORATION

- Bug: phase-local adapter indexing restarted at seat zero, so a logical agent
  could execute on different physical models in different phases.
  - Root cause: routing used the index of the phase's active-agent list instead
    of a session-level logical-agent binding.
  - Restored invariant: logical agent -> stable physical adapter/exact model for
    the session; existing explicit phase retry alone may move a failed task to
    the next frozen seat. Roles still rotate independently.
- Bug: OpenRouter stored `model_id`, while shared roster metadata reads `model`.
  - Root cause: the adapter did not implement the canonical metadata attribute.
  - Restored invariant: `model` contains the exact pinned namespaced ID and
    `model_id` remains its OpenRouter compatibility alias. Deterministic model
    namespaces identify vendors; unknown namespaces remain `Unknown`.
- Bug: score and ratification consumers looked for confidence inside move
  `content`, despite the parser storing it on `AgentMove.confidence`.
  - Root cause: downstream reads bypassed the typed parsed-move contract and
    silently used `0.7`.
  - Restored invariant: successful parsed moves propagate their typed confidence
    exactly; malformed output remains fail-closed.

## H0 / H0.5 FREEZE

- The current-canonical Repeat 003 and historical challenger failures are
  retained as offline JSON evidence fixtures. Unavailable raw material is
  represented as unavailable/null rather than reconstructed.
- The H0.5 preservation matrix is now a normative design contract. Every mature
  discovered capability has exactly one migration state, and authority
  boundaries between CED, future Hybrid state, Live View, receipts, OpenClaw,
  scoring, ratification, learning, search, consultation, and the Kernel are
  explicit.
- This baseline does not contain Hybrid runtime records, shadow wiring, prompt
  changes, score changes, assembly changes, or ratification changes.

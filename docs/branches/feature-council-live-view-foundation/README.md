# Branch: feature/council-live-view-foundation

**Purpose.** Deliver Slice 0 (+ the inert ledger half of Slice 1) of the
Council Live View: a versioned, read-only, runtime-inert contract package that
lets a future UI project Socrates' governed CED execution *without* changing
the reasoning engine. Decision record:
[../../architecture/KARPATHY_LLM_COUNCIL_MAPPING.md](../../architecture/KARPATHY_LLM_COUNCIL_MAPPING.md)
(§9, §14, §18); as-built detail:
[../../architecture/COUNCIL_LIVE_VIEW_FOUNDATION.md](../../architecture/COUNCIL_LIVE_VIEW_FOUNDATION.md).

**Success criterion.** A new package `backend/dialogues/projection/` that:
- defines the closed `ced_epistemic_event_v1` event taxonomy, typed payloads,
  append-only per-stream `EventLedger`, run-scoped reveal-policy contract, and
  strict `role_history` projection;
- imports **nothing** from `ced.py`, the provider registry, or providers
  (runtime-inert — proven by a guard test);
- leaves `ced.py` and every existing behavior untouched (full
  `tests_dialogues` still green);
- survives adversarial contract review.

**Scope.** Contract + in-memory ledger + reveal/role-display contracts, and
their tests, only. Documentation under `docs/architecture/` and this branch
folder.

**Non-goals (this branch).** No observer/emission hook in `ced.py` (Slice 1);
no FastAPI/SSE transport (Slice 2); no frontend (Slice 3); no receipt
projection wiring (Slice 4); no conversation projection (Slice 5); no
`OpenRouterAdapter`. These are later, separately-reviewed slices.

**Companion docs.**
- [MEMORY.md](MEMORY.md) — stable context, invariants, key files.
- [PLAN.md](PLAN.md) — execution plan, gates, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state for safe resumption.

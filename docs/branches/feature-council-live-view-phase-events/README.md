# Branch: feature/council-live-view-phase-events

**Purpose.** The deferred `phase.started` slice: emit phase-transition events
through a real `_advance_phase()` seam that covers ALL transitions (legacy +
registry, RATIFICATION, COMPLETE, both registry fallbacks) — deferred from the
observer slice precisely because `_apply_phase_roles` is not a full
phase-transition chokepoint.

**Success criterion.** With the observer enabled, the `phase.started`
sequence on the run stream equals the canonical phase-entry order derived
from `state.phase_history + [state.phase]`; no duplicate `phase.started` per
(run, phase, round); byte-identical canonical `FinalResponse` and identical
authority state when disabled or raising; `phase_history` semantics
completely unchanged.

**Scope.** One CED-side wrapper (`_advance_phase`) replacing the 11
`state.advance_phase(...)` call sites in `ced.py`, plus extended golden
tests. Nothing else.

**Non-goals.** No `models.py` change (`SessionState.advance_phase` stays the
canonical mutation); no new event types; no provider/transport/frontend work;
no ratification-event emission (blocked by the random-routing-ID gate in the
observer branch MEMORY); no merge of PR #71/#72.

**Base:** `feature/council-live-view-observer-hook` @ `03ed887` (frozen;
stacked PR #72 open). Stacks: foundation (#71) → observer hook (#72) → this.

**Companion docs.** [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md).

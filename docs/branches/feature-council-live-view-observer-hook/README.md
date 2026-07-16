# Branch: feature/council-live-view-observer-hook

**Purpose.** Slice 1 (second half): add a flag-gated, failure-isolated
observer hook that emits read-only `ced_epistemic_event_v1` events into an
injected `EventLedger` **during** existing CED execution — without changing
any reasoning behavior. Builds on the approved foundation contracts
(`backend/dialogues/projection/`, foundation PR
`Add Council Live View event foundation`).

**Success criterion.** With the observer disabled (default) OR enabled-but-
raising, an existing CED run produces a **byte-identical canonical
`FinalResponse`** to the pre-hook baseline, with no change to `SessionState`
or any authority decision. When enabled, the ledger contains the deterministic
event sequence for the run.

**Scope.** A dependency-injected observer seam in `ced.py` (default off) that
translates already-computed canonical CED facts into event drafts appended to
an injected `EventLedger`. Golden determinism tests. Nothing else.

**Non-goals.** No global ledger; no SSE/FastAPI/frontend (Slice 2/3); no
provider/OpenRouter change; no scoring/role/assembly/ratification change; no
merge of the foundation PR; no new event types beyond the foundation
taxonomy.

**Base:** `feature/council-live-view-foundation` @ `b645dcb` (approved
foundation tip). **Foundation PR:** open as Draft; do not merge yet.

**Companion docs.** [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md).

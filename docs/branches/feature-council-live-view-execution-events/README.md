# Branch: feature/council-live-view-execution-events

**Purpose.** The task/provider/move emission slice: project `task.created`,
`provider.failed` and `move.validated` from the canonical execution facts —
plus the PREREQUISITE this branch's investigation surfaced: `AgentTask.task_id`
is today a random `_uid()` routing id, so deterministic task identity must
land FIRST (same recipe as the existing deterministic `move_id`/`stask_`
ids).

**Success criterion.** Canonical deterministic task and move ids with explicit
round identity; `task.created` emitted before execution on BOTH paths;
`provider.failed` for every failed provider outcome (closed status→category
mapping); `move.validated` with real raw/validated digests on the registry
path; byte-identical `FinalResponse` and authority parity when
disabled/raising; cross-fresh-ledger event-stream determinism (the test-8
pattern) now possible BECAUSE execution identities are deterministic.

**Scope.** `ced.py` (canonical task/move identity + event emission at canonical
construction/outcome sites), golden tests, one tree-evidence test-order fix
required by the new move-id distribution, branch docs. `models.py` untouched
(the model defaults stay; CED stamps explicitly).

**Non-goals / deferred (documented in MEMORY).** `provider.requested`
(dispatch happens inside provider_registry; mocks lack a canonical
`requested_model`); `provider.completed` (matrix REQUIRES a receipt_ref the
runtime does not mint); legacy-path `move.validated` (no raw provider text
exists in-process); ratification events (still gated, though deterministic
task ids REDUCE that gate).

**Base:** `feature/council-live-view-phase-events` @ `e882dbd` (frozen;
stacked PR #73 open). Stack: #71 → #72 → #73 → this.

**Companion docs.** [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md).

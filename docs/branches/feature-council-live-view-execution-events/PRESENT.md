# PRESENT — feature/council-live-view-execution-events

Exact current state for safe resumption. Keep current.

## Branch / HEAD

- Branch: `feature/council-live-view-execution-events`
- Base / current HEAD: `e882dbd` (frozen phase-events tip; nothing committed
  on this branch yet).
- Stack: PR #71 (foundation→main) · #72 (observer→foundation) · #73
  (phase-events→observer, head `e882dbd`) — all open drafts, unmerged.
- Worktree: `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`.

## Completed work (this branch)

- Investigation surfaced the central finding: `AgentTask.task_id` was a RANDOM
  `_uid()` — the same routing-id disease as the ratification gate. User
  delegated the decision ("check all folders, decide the best"); decisions in
  PLAN.md steps 2–3.
- **Step 0 — deterministic task ids**: `_deterministic_task_id` stamped at the
  5 random `AgentTask` sites (the 2 scoring sites were already `stask_`
  deterministic). `models.py` untouched. Golden bytes + authority parity
  unchanged (task_id is absent from `FinalResponse`).
- **Emission** through the single `_record_task_log` chokepoint: `task.created`
  (both paths, OBSERVED kinds), `provider.failed` (registry; legacy has no
  providers); `move.validated` in `_absorb` (registry only; real raw/validated
  digests; legacy fabricates nothing). Ratification/tree/lesson kinds deferred
  behind the `_OBSERVED_TASK_KINDS` allowlist.

## Emitted counts (empirical, offline mock)

- LEGACY run stream: 39 events (adds 14 `task.created` to the phase slice's 25;
  no provider/move events — in-process path).
- REGISTRY run stream: 154 events (adds `task.created` + `move.validated` for
  deliberation AND all peer-scoring tasks).
- Raising-ledger attempt totals (cross-mode parity, exact): legacy **40**,
  registry **155** — each equals `["session.created"] + enabled run-stream
  types`.

## Changed files

- `backend/dialogues/ced.py` (+144: helper, 5 task-id stamps, emission block)
- `tests_dialogues/test_ced_observer_golden.py` (+205: 8 new tests, updated
  stream/failure assertions)
- this docs folder

## Tests — exact results

- Golden **50 passed**; four-file focused **244**; full `tests_dialogues`
  **1807** (byte/authority parity re-proven — deterministic task ids and
  emission changed nothing canonical).

## Blockers / next safe step

- Committed + pushed as a checkpoint. Stacked Draft PR
  (base `feature/council-live-view-phase-events`,
  head `feature/council-live-view-execution-events`,
  title `Add CED execution observer events`) — user opens in the GitHub UI
  (gh token can't resolve the repo).

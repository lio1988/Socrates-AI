# PRESENT — feature/council-live-view-execution-events

Exact current state for safe resumption. Keep current.

## Branch / HEAD

- Branch: `feature/council-live-view-execution-events`
- Base: `e882dbd` (frozen phase-events tip).
- Current HEAD: `2678d63` (`Add execution events to CED observer`).
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

## PR #74 review fixes (uncommitted — awaiting pre-commit review)

The real diff review of `2678d63` found 4 issues (all fixed, see PLAN step 10):
task.created moved to construction time; `UNAVAILABLE` no longer invents
"network"; move.validated digest built inside the isolation choke
(`allow_nan=False`); task id hardened to versioned canonical-JSON 64-hex with
a mandatory TaskKind. New event ordering (counts unchanged):
`phase.started → role.assigned → task.created → [move.validated]`.

Review round 2 (three more gaps, all fixed — see PLAN step 11): explicit
`round_index` threaded into the task identity (opening round 0 ≠ round 2);
`task.created` now emitted by the standalone `run_registry_council_round` /
`gather_registry_phase_round` paths too (path-independent); `_build_round_task`
RAISES on an unmapped phase instead of fabricating `INITIAL_RESPONSE`.

Review round 3 (final blocker fixed — see PLAN step 12):

- `_deterministic_move_id` takes explicit `round_index`, uses canonical
  `ced_move_v1` JSON and emits full 64-hex IDs with the same identity fields
  as task ids.
- Legacy dispatch passes its explicit phase round; registry absorb and tree
  revision use the corresponding `task.round_number`.
- Main `_run_registry_phase` had one remaining fabricated TaskKind fallback;
  strict lookup now occurs before phase mutation/dispatch.
- The new move-id distribution exposed an order-dependent tree-evidence test
  helper; it now selects a scorecard referenced by the actual expansion log.
  Production extraction was already correct and is unchanged.

Changed now:

- `backend/dialogues/ced.py`
- `tests_dialogues/test_ced_observer_golden.py`
- `tests_dialogues/test_openclaw_tree_evidence_bridge.py` (test-only linkage fix)
- this docs folder

Final gates:

- focused red→green move/strict-lookup regressions: **3 passed**
- golden: **71 passed**
- stacked four-file projection/observer gate: **265 passed**
- full `tests_dialogues`: **1828 passed**
- `git diff --check`: clean
- `backend/dialogues/models.py`: untouched

## Blockers / next safe step

- **STOP before commit** — final review-fix diff and gates are ready for GO.
- After sign-off: commit as a PR #74 review-fix on this branch (no amend or
  force-push; branch otherwise frozen), then push. Suggested message:
  `Harden CED execution event semantics`.

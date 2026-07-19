# PLAN — feature/council-live-view-execution-events

## Success criterion

See [README.md](README.md). Deterministic task ids (golden-neutral) +
`task.created` / `provider.failed` / registry `move.validated` emission,
disabled/raising byte-identical, cross-fresh-ledger deterministic.

## Ordered steps

1. [x] Branch off frozen phase-events tip `e882dbd`; investigation + branch
       docs (MEMORY.md holds the evidence).
2. [x] **Design decisions** — delegated by the user ("check all folders,
       decide the best"); decisions recorded here: (D1) Step 0 lands in this
       slice; (D2) scope = task.created + provider.failed + registry
       move.validated with the OBSERVED-kind allowlist (6 deliberation kinds
       + MOVE_SCORE + SECTION_SCORE); ratification/tree/lesson kinds
       deferred; (D3) closed status→category mapping with honest "unknown"
       default. Bonus finding: registry COUNCIL_RATIFICATION tasks already
       carry `attempt_index=round_index` — repair rounds have distinct task
       identity (further shrinks the ratification gate).
3. [x] Step 0: `_deterministic_task_id` (same identity family as move ids,
       "task_" prefix); stamped at the 5 random sites (deliberation 1024,
       ratification 1571, legacy dispatch 1836, tree 2826, demo round 623);
       scoring sites already deterministic (`stask_`). Golden bytes +
       authority parity PROVEN unchanged (task_id appears nowhere in
       FinalResponse). models.py untouched.
4. [x] `task.created` inside `_record_task_log` (payload from the appended
       entry; both paths; OBSERVED kinds only).
5. [x] `provider.failed` from the same chokepoint (status≠OK + provider
       present; legacy provider_id=None → none, honestly).
6. [x] Registry `move.validated` in `_absorb` (raw_digest=sha256(raw_text),
       validated_digest=sha256(canonical JSON of move.content); emitted only
       when raw text exists — legacy fabricates nothing).
7. [x] Golden tests (+8): task parity vs task_log; deterministic
       (s?)task_ ids + fresh-run equality; move.validated parity +
       recomputable digests; provider.failed parity (timeout mock);
       legacy absence of provider/move events; ratification/tree deferral
       guard; stream-shape update; failure test rebuilt as CROSS-MODE
       PARITY (raising attempts == ["session.created"] + enabled run-stream
       types) + exact canaries legacy 40 / registry 155.
8. [x] Gates: golden 50/50; four-file 244; full `tests_dialogues` **1807**.
9. [x] Committed `2678d63` "Add CED execution observer events"; PR #74 opened.
10. [~] **PR #74 review fixes (real diff review of 2678d63 found 4):**
    (1) `task.created` was emitted at OUTCOME time inside `_record_task_log`
        — moved to CONSTRUCTION time via a new `_emit_task_created(state,
        task)` called at the 4 observed dispatch sites BEFORE
        execute/run_adapter (true even if execution throws); the logger now
        emits only `provider.failed`;
    (2) `ProviderStatus.UNAVAILABLE → "network"` was invented — removed;
        UNAVAILABLE/error/degraded/fallback/disabled are honestly "unknown";
    (3) `move.validated` digest is built INSIDE `_build_move_validated_event`
        (called by `_emit_event`) with `allow_nan=False`, so a non-finite
        content value is an ISOLATED observer failure, not a CED failure;
    (4) `_deterministic_task_id` hardened: versioned namespace "ced_task_v1",
        canonical JSON array (delimiter-collision-free), FULL 64-hex SHA-256,
        mandatory `TaskKind` (demo `_build_round_task` now supplies a real
        kind via `PHASE_TASK_KIND`, and sets it on the task).
    Tests (+10): pre-dispatch ordering, execution-exception-still-created,
    no-duplicate-from-logger, UNAVAILABLE→unknown, NaN/Inf isolated digest
    failure, delimiter-collision resistance, per-field id change, 64-hex ids,
    no task_kind=None.
11. [~] **Review round 2 — three more architectural gaps found:**
    (5) EXPLICIT round_index in the task identity — `_deterministic_task_id`
        now takes `round_index` (no longer reads the mutable
        `state.round_number`); `_dispatch` gains a `round_index` param
        threaded from `run_opening_phase`, sets it on both the id and
        `AgentTask.round_number`; `_build_round_task` gains `round_index`;
        all 5 id call sites pass the real round. Integration test: same
        session, opening round 0 ≠ round 2 task_id;
    (6) STANDALONE registry coverage — `_emit_task_created` now fires in
        `run_registry_council_round` and `gather_registry_phase_round._one`
        (before gather/run_adapter), so task.created is path-independent;
    (7) NO fabricated TaskKind — `_build_round_task` uses `PHASE_TASK_KIND
        [phase]` and RAISES `ValueError` on an unmapped phase instead of
        coercing to INITIAL_RESPONSE.
    Tests (+6): opening round 0≠2 id; gather round threading; standalone
    council/gather emit before execution; unmapped phase fails pre-dispatch;
    standalone raising-ledger isolation. Gates: golden **69**, four-file
    **263**, full `tests_dialogues` **1826**. STOP before commit — present
    diff + results.
12. [x] **Review round 3 — explicit move round identity:**
    `_deterministic_move_id` now takes explicit `round_index` and uses
    versioned canonical JSON (`ced_move_v1`) + full 64-hex SHA-256, with the
    same identity fields/order as task ids. Legacy `_dispatch` passes its
    explicit phase round; registry absorb and tree revision pass
    `task.round_number`. Tests prove opening rounds 0/2 differ for the SAME
    agent and prove task/move stability + round sensitivity + 64-hex shape.
    Adversarial call-site audit also found the main `_run_registry_phase`
    still used `PHASE_TASK_KIND.get(..., INITIAL_RESPONSE)` despite the prior
    fix; it now performs strict lookup before phase mutation/dispatch, covered
    by the unsupported-phase regression. The new move-id distribution exposed
    one order-dependent tree-evidence test helper; it now modifies a
    tree-referenced scorecard from the expansion log (test-only, no production
    evidence change). Gates: golden **71**, stacked four-file **265**, full
    `tests_dialogues` **1828**. STOP before commit.

## Validation gates (every commit)

1. Golden + four-file focused green; full `tests_dialogues` green.
2. `git diff --cached --check` clean; only approved files.
3. `models.py` untouched; task_id absence from FinalResponse re-proven by
   the existing golden bytes test.

## Stop conditions

- STOP before commit after the final review-fix gates.
- Never amend/force-push; PRs #71/#72/#73 unmerged; prior branches frozen.
- Do NOT emit provider.requested / provider.completed / legacy
  move.validated / ratification events (deferral list in MEMORY.md).

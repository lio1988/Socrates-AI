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
9. [ ] Commit (`Add execution events to CED observer`), push; stacked Draft
       PR (base: phase-events) — user opens in UI. ← current step

## Validation gates (every commit)

1. Golden + four-file focused green; full `tests_dialogues` green.
2. `git diff --cached --check` clean; only approved files.
3. `models.py` untouched; task_id absence from FinalResponse re-proven by
   the existing golden bytes test.

## Stop conditions

- STOP now at the design gate (step 2).
- STOP before commit (step 8).
- Never amend/force-push; PRs #71/#72/#73 unmerged; prior branches frozen.
- Do NOT emit provider.requested / provider.completed / legacy
  move.validated / ratification events (deferral list in MEMORY.md).

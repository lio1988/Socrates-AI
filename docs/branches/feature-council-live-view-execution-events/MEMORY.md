# MEMORY — feature/council-live-view-execution-events

Stable context and the code-grounded facts the design rests on.

## THE FINDING THAT RESHAPES THIS SLICE (surface before any implementation)

The review's premise was that task/provider/move emission "does not depend on
the random ratification routing IDs". Investigation shows **`AgentTask.task_id`
is itself a random `_uid("task_")`** (models.py:191) — the SAME disease:

- `task.created` matrix identity is `("task_id",)`;
- `move.validated` payload REQUIRES `task_id`;
- provider events key on `(task_id, provider_id, attempt_index)`.

With random task ids, two fresh runs of the same `session_id` would produce
different payloads and different idempotency keys — the cross-fresh-ledger
determinism every previous slice locked (test-8 pattern) would be impossible.

**Prerequisite (Step 0): deterministic task identity in CED.** Precedents
already in the codebase were `_deterministic_move_id` (the legacy dispatcher
already stamped `move.move_id` explicitly) and `stask_` score-task ids. The
fix stamps every CED-created `AgentTask` explicitly; `models.py` remains
untouched for compatibility.

Verified golden-neutral in principle: `task_id` appears NOWHERE in
`FinalResponse` (`_task_log_summary` exposes only counts: entries/with_move/
by_phase) and the authority snapshot excludes `task_log` — the existing
byte/authority tests will prove neutrality.

Bonus: ratification tasks are built at one of those 7 sites, so their task
ids ALSO become deterministic — materially shrinking the ratification-events
gate (verdict `task_id` derives from it; `ratification_id`/`move_id` on
verdicts remain to be addressed there).

## Final task/move identity invariant

Review hardened both execution identities before the observer events make
them persistent:

- `task_id = "task_" + 64 lowercase hex`, namespace `ced_task_v1`;
- `move_id = "move_" + 64 lowercase hex`, namespace `ced_move_v1`;
- both hash the same canonical JSON identity fields:
  `session_id, phase, explicit round_index, agent_id, role, task_kind,
  slot_index, attempt_index`;
- the round is threaded from the real `AgentTask` or explicit phase call,
  never re-read from mutable `state.round_number`;
- unknown phases fail before phase mutation or dispatch; they are never
  represented as `INITIAL_RESPONSE`.

Changing the old 12-hex move ids changes deterministic scoring seeds and may
therefore change which draft is selected by deterministic mock runs. Tests
must select records by canonical tree/audit linkage, never incidental list
order. This exposed one tree-evidence test helper that selected the first
scorecard rather than a scorecard referenced by the expansion log; the test
helper was corrected without changing production evidence extraction.

## Emission chokepoints (verified)

- **`_record_task_log`** (ced.py:1869) is the SINGLE task-trace chokepoint —
  11 callers covering BOTH paths and every task kind: legacy dispatch (1857,
  the same helper that mints deterministic move ids), registry deliberation
  (1611/1616), council ratification (1057/1062), move scoring (2348/2354),
  section scoring (2738/2748/2845/2861). `task.created` emits INSIDE it,
  right after `state.task_log.append(entry)`, with the payload taken from
  the just-appended entry (never a second projection). Same pattern as
  `_apply_phase_roles`.
- **`provider.failed`**: same chokepoint — entries carrying a failure
  `provider_status` (legacy entries have `provider_id=None` → no provider
  events on legacy, honest). Closed mechanical mapping ProviderStatus →
  FailureCategoryLiteral (timeout→timeout, rate_limited→rate_limit,
  invalid_json→invalid_response, schema_error→schema, missing_key→auth,
  error/unavailable/degraded/fallback/disabled→unknown or per-status —
  finalized in the design review).
- **`move.validated`**: registry outcome sites where BOTH the parsed move
  AND `resp.raw_text` are in scope (deliberation 1611, scoring 2348/2748,
  tree 2861 if applicable). `raw_digest = sha256(resp.raw_text)`;
  `validated_digest = sha256(canonical sorted-JSON of move.content)`.
  **`raw_text` is read NOWHERE in ced.py today** — the plumbing passes the
  in-scope `resp` only; no storage of raw text.

## Deferred (with reasons — do not silently un-defer)

- `provider.requested`: true dispatch happens INSIDE provider_registry
  (`adapter.generate_agent_move` call at pr.py:494); emitting from ced after
  the fact would fake the semantics; mock adapters also have NO canonical
  `requested_model` (only provider_id/provider_name; live adapters do have
  `model`). Needs either a registry-side seam (architecture decision) or a
  post-outcome semantic rename — LATER.
- `provider.completed`: matrix rule REQUIRES `receipt_ref`; the runtime
  mints no provider receipts. Emitting without one violates the contract;
  weakening the contract is a reviewed matrix change — LATER (receipt
  minting belongs to a provider-integrity slice).
- Legacy `move.validated`: the in-process legacy path has NO raw provider
  text (agent.execute returns the move directly; no ProviderResponse).
  Fabricating a raw digest is forbidden — registry-only, documented.
- Ratification events: still gated (verdict ratification_id/move_id remain
  random); Step 0 shrinks but does not clear the gate.

## Locked invariants (inherited)

- All emission through `_emit_event` (isolation choke); disabled → build
  never called; raising → observer side channel only; byte-identical
  `FinalResponse`; authority-state parity.
- Canonical mutation FIRST, projection SECOND, payload from the canonical
  record just written — never a second independent computation.
- Ledger owns sequence; no SSE/FastAPI/frontend; PRs #71/#72/#73 unmerged;
  prior branches frozen.

## Workflow constraints

- Worktree `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`, branch
  `feature/council-live-view-execution-events` off `e882dbd`.
- Tests: `Set-Location <worktree>` then
  `& C:\Users\spirc\Desktop\Socrates-AI\.venv\Scripts\python.exe -m pytest …`.
- All `*.md` gitignored → `git add -f`. No amend/force-push.

# PRESENT — feature/council-live-view-observer-hook

Exact current state for safe resumption. Keep current.

## Branch / HEAD

- Branch: `feature/council-live-view-observer-hook`
- Base / current HEAD: `b645dcb` (approved foundation tip; nothing committed on
  this branch yet).
- Worktree: `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`
  (isolated; sibling `C:\Users\spirc\Desktop\Socrates-AI` holds unrelated
  OpenClaw work — never touch it).
- Foundation PR: OPEN as Draft (`base main` ← `feature/council-live-view-
  foundation` @ `b645dcb`); do not merge yet.

## Completed work (this branch)

- Golden baseline committed at `65b5f14` (observer-ABSENT determinism lock).
- **Observer hook implemented** (uncommitted): `projection/observer.py`
  (`CedEventObserver`, `ObserverFailure`, `derive_projection_run_id`); `ced.py`
  DI seam (`event_observer=None` default; single `_emit_event` isolation choke;
  `_emit_run_started`/`_emit_run_completed`; `role.assigned` from the new
  `role_history` rows inside `_apply_phase_roles`); `build_council` gains an
  `event_observer` passthrough. First slice emits `session.created`,
  `run.started`, `role.assigned`, `run.completed` (per the review;
  `phase.started` deferred).
- Golden test extended with the 8 observer cases (both run paths).

## Uncommitted (awaiting observer-hook review, before commit)

- `backend/dialogues/projection/observer.py` (new)
- `backend/dialogues/projection/__init__.py` (export observer bridge)
- `backend/dialogues/ced.py` (DI seam + emit sites; +131/−7)
- `backend/dialogues/live_providers.py` (`event_observer` passthrough; +4/−2).
  NOTE: this is FACTORY dependency-injection wiring only — `build_council`
  forwards the caller's observer to the `CEDOrchestrator` constructor. No
  provider, adapter, gating, or runtime behavior changes; it is NOT an
  exception to the "no provider changes" boundary.
- `tests_dialogues/test_ced_observer_golden.py` (extended)
- this branch documentation folder

## Tests — exact results

- `test_ced_observer_golden.py`: **25 passed** (7 baseline + 12 parametrized
  observer + 2 authority-state parity + 2 exact-failure-sequence + 2
  isolation-unit).
- Four-file focused (projection + golden): **219 passed**.
- Full `tests_dialogues`: **1782 passed** (no regression; disabled path
  byte-for-byte unchanged).
- Final review gates: `authority_state_snapshot` proves a RAISING observer
  leaves the canonical SessionState (phases/roles/moves/drafts/scorecards/
  assembly/ratification) identical to the observer-absent run on BOTH paths
  (verdict `ratification_id`/`task_id`/`move_id` are random `_uid()` routing
  ids — verified empirically — and are excluded as such); the failure
  sequence is locked EXACTLY: legacy 18 = session.created, run.started,
  15×role.assigned, run.completed; registry 17 = session.created,
  run.started, 14×role.assigned, run.completed — every attempt isolated,
  none stops the next, run.completed attempted after all prior failures.

## Emitted event sequences (offline mock, both paths)

- `session:<sid>` → `[1] session.created`.
- LEGACY `run:<run_id>` → `[1] run.started`, `[2..16] role.assigned`
  (opening→…→synthesis + `ratification` final_evaluator), `[17] run.completed`.
- REGISTRY `run:<run_id>` → `[1] run.started`, `[2..15] role.assigned`
  (NO ratification row — council ratification has no single Final Evaluator),
  `[16] run.completed`. Events mirror `role_history` exactly; the path
  difference is faithful, not fabricated.

## Blockers / next safe step

- **STOP before commit** for the observer-hook review (the limited runtime
  diff: `ced.py`, `observer.py`, `build_council` passthrough, extended tests).
- After sign-off: commit as a single checkpoint on this branch (no amend/force),
  push, then the next hook slice adds `phase.started` via a real
  `_advance_phase()` seam covering all transitions.

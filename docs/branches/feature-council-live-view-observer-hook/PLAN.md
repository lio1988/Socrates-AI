# PLAN — feature/council-live-view-observer-hook

## Success criterion

Observer disabled (default) OR enabled-but-raising ⇒ byte-identical canonical
`FinalResponse` vs the pre-hook baseline, no `SessionState`/authority change.
Observer enabled ⇒ deterministic event sequence in the injected `EventLedger`.

## Ordered steps

1. [x] Branch `feature/council-live-view-observer-hook` off `b645dcb`; branch
       docs.
2. [x] **Golden baseline test FIRST** (`test_ced_observer_golden.py`): lock the
       deterministic canonical `FinalResponse` for `run_session` and
       `run_registry_session` with the observer ABSENT (current code). Prove
       run-to-run byte-identity after canonicalization, and that the raw dumps
       differ ONLY in the four known volatile fields. **← current step; STOP
       before commit for review.**
3. [x] Design the injected observer seam — reviewed & APPROVED with two locked
       adjustments (deterministic `run_id` from `session_id`; defer
       `phase.started`).
4. [x] Implement the hook: default-off, DI, single failure-isolation choke
       (`_emit_event`); emit `session.created`/`run.started`/`role.assigned`/
       `run.completed` from already-computed canonical facts; ledger owns
       sequence. New `projection/observer.py`; `build_council` gains an
       `event_observer` passthrough (DI wiring for the registry path).
5. [x] Extend the golden test: explicit-None ⇒ baseline bytes; enabled ⇒
       expected session/run streams + contiguous sequences + role_history
       parity; raising ledger ⇒ baseline bytes + isolated failures;
       record_failure also raising ⇒ baseline bytes; disabled ⇒ build() never
       called + no ledger touched; two fresh ledgers ⇒ identical event view.
       Both run paths, parametrized.
6. [x] Full `tests_dialogues` green (**1778**); focused golden **21**;
       `ced.py` diff +131/−7 (mostly the three new emit methods).
       **← STOP before commit for review.**

## Validation gates

1. Focused golden test green.
2. Full `tests_dialogues` green (no regression).
3. `git diff --cached --check` clean; only intended files staged.
4. Observer-absent path is byte-for-byte the pre-hook behavior.

## Stop conditions

- **STOP now**, before committing the golden baseline, for the first
  observer-hook review.
- Do not touch `ced.py` until the seam design is reviewed (step 3).
- Never amend/force-push; never merge the foundation PR; never touch the
  sibling worktree's OpenClaw files.

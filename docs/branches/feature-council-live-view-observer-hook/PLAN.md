# PLAN — feature/council-live-view-observer-hook

## Success criterion

Observer disabled (default) OR enabled-but-raising ⇒ byte-identical canonical
`FinalResponse` vs the pre-hook baseline, no `SessionState`/authority change.
Observer enabled ⇒ deterministic event sequence in the injected `EventLedger`.

## Scope

- Dependency-injected `CedEventObserver` and bounded failure diagnostics.
- Disabled-by-default CED emission seam and registry factory passthrough.
- Initial session/run/role lifecycle events and golden determinism tests.
- This branch-documentation folder.

## Non-goals

- No phase, task, provider-outcome, move-validation, ratification, transport,
  frontend, or OpenRouter work.
- No provider behavior, scoring, role, assembly, or ratification changes.
- No global ledger or observer singleton.

## Ordered implementation steps

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

## Completed

- Golden observer baseline, dependency-injected observer bridge, bounded
  diagnostics, lifecycle/role emissions, registry fallback completion events,
  and final review fixes are complete at the verified implementation head.
- PR #72 is open as a stacked Draft and the implementation is review-only.

## Remaining / deferred work

- Diagnose the repository-level GitHub Actions `startup_failure`.
- Re-run the bottom-up stack audit after operational checks are healthy.
- Phase and execution events remain isolated in PRs #73 and #74; transport and
  frontend remain future work.

## Validation gates

1. Focused golden test green.
2. Full `tests_dialogues` green (no regression).
3. `git diff --cached --check` clean; only intended files staged.
4. Observer-absent path is byte-for-byte the pre-hook behavior.

## Stop conditions

- Stop after this docs-only review fix and keep the branch frozen.
- Do not make PR #72 ready or merge it until the landing audit is green.
- Never amend/force-push; never touch the sibling worktree's OpenClaw files.

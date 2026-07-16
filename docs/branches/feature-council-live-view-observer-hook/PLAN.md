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
3. [ ] Design the injected observer seam (interface + where it attaches in
       `ced.py`), reviewed before implementation.
4. [ ] Implement the hook: default-off, DI, failure-isolated; emit drafts
       from already-computed canonical facts only; ledger owns sequence.
5. [ ] Extend the golden test: observer-disabled ⇒ baseline; observer-enabled-
       but-raising ⇒ baseline + run unaffected; observer-enabled ⇒ expected
       deterministic event sequence.
6. [ ] Full `tests_dialogues` green; `ced.py` diff minimal and justified.

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

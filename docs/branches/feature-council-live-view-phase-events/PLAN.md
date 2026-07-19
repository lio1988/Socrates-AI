# PLAN — feature/council-live-view-phase-events

## Success criterion

Provide full-coverage `phase.started` events through one CED wrapper, with
canonical parity to `phase_history + [state.phase]`, no duplicates, no
`phase_history` semantic change, and byte-identical results when the observer is
disabled or raises.

## Scope

- Add the isolated `_advance_phase` event seam in `backend/dialogues/ced.py`.
- Route every CED phase transition through that seam.
- Cover legacy, registry, fallback, repeated-phase, and raising-observer paths.
- Maintain this branch's documentation under
  `docs/branches/feature-council-live-view-phase-events/`.

## Non-goals

- No changes to `backend/dialogues/models.py`.
- No redesign of provider, canonical state, or `phase_history` semantics.
- No execution-level task or move events; those belong to the next stack layer.
- No landing, retargeting, or readiness-state changes for the stacked PRs.

## Ordered implementation steps

1. Branch from the frozen observer-hook implementation head.
2. Approve the seam design, including CED-side no-op suppression and correct
   registry RATIFICATION timing.
3. Implement `_advance_phase` and replace all direct CED phase-advance sites.
4. Extend golden coverage for exact phase sequences, parity, ordering,
   fallbacks, repeated no-ops, explicit round identity, and observer isolation.
5. Run the golden, focused, and full dialogue validation gates.
6. Commit and push the phase-events implementation as stacked Draft PR #73.
7. Freeze the implementation and permit only PR-scoped review or branch-doc
   corrections.

## Validation gates

1. Golden observer suite: **42 passed**.
2. Four focused observer/projection files: **236 passed**.
3. Full `tests_dialogues`: **1799 passed**.
4. `git diff --check` clean; only intended implementation/test/docs files.
5. `models.py` untouched and `phase_history` authority parity preserved.
6. Disabled and raising observers do not alter canonical outcomes.

## Stop conditions

- Stop on any unexpected production/test change after the verified
  implementation head.
- Stop if a documentation-only review fix touches anything outside this
  branch's documentation folder.
- Never amend, rebase, force-push, merge, retarget, or mark the PR ready during
  a frozen-stack audit.

## Completed

- The approved phase seam, all transition call-site replacements, registry
  RATIFICATION timing, and the complete test matrix were implemented.
- PR #73 was opened as a Draft on the observer-hook branch and frozen after
  implementation verification.
- The implementation gates above passed at verified implementation head
  `e882dbd8df1af8effbd21fee86b4b3ce8e34deaa`.

## Remaining / deferred work

- Diagnose the repository-level GitHub Actions `startup_failure`.
- Re-run the read-only landing audit after Actions can start jobs.
- Actual bottom-up landing remains deferred pending an explicit GO.

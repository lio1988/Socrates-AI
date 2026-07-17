# PLAN — feature/council-live-view-phase-events

## Success criterion

See [README.md](README.md): full-coverage `phase.started` via one wrapper,
canonical parity with `phase_history + [state.phase]`, no duplicates, no
`phase_history` change, disabled/raising byte-identical.

## Ordered steps

1. [x] Branch off frozen observer tip `03ed887`; branch docs with the
       code-grounded seam design (MEMORY.md).
2. [x] **Design review gate** — APPROVED with two required adjustments:
       (a) no-op suppression IN CED (approved signature with explicit
       `round_index` + `initial_entry`/fresh-opening detection; never ledger
       dedupe; never `state.round_number`); (b) registry RATIFICATION moved
       to its true entry point (before `run_council_ratification`), COMPLETE
       stays in `_build_council_final`.
3. [x] Implemented: `_advance_phase` wrapper (canonical mutation FIRST,
       suppressed-no-op check, emit SECOND via `_emit_event`); all 11 sites
       replaced; registry RATIFICATION timing moved; opening passes its
       explicit `round_index` + `initial_entry=True` (registry generic site:
       `initial_entry=(phase == OPENING)`); `models.py` untouched.
4. [x] Golden tests extended (16 new): exact canonical 8-phase sequence
       (both paths); parity vs `phase_history + [state.phase]`;
       phase-before-its-roles interleaving; run.started before first
       phase / COMPLETE before run.completed; initial OPENING exactly once;
       readiness fallback → zero phase events; mid-phase quorum fallback →
       prefix up to blocked phase, no RATIFICATION/COMPLETE; no-op repeat →
       no event AND no failure on raising observer; opening round_index=2
       flows into the event; static guard: exactly ONE `.advance_phase(`
       call site in ced.py; failure sequences locked EMPIRICALLY (legacy 26,
       registry 25, interleaved order built from roles-per-phase
       [1,3,2,3,1,4,1] / [1,3,2,3,1,4,0]).
5. [x] Gates: golden 42/42; four-file focused 236; full `tests_dialogues`
       **1799 passed**. **← STOP before commit for review.**
6. [ ] Commit (`Add phase transition events to CED observer`), push, stacked
       Draft PR (base: observer-hook) — after review.

## Validation gates (every commit)

1. Golden file green; four-file focused green.
2. Full `tests_dialogues` green.
3. `git diff --cached --check` clean; only intended files.
4. `models.py` untouched; `phase_history` parity in authority snapshot.

## Stop conditions

- STOP now for seam-design review (no implementation).
- STOP before commit after implementation.
- Never amend/force-push; PR #71/#72 unmerged; observer branch frozen.

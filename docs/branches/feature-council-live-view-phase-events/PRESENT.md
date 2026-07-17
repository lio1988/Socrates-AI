# PRESENT — feature/council-live-view-phase-events

Exact current state for safe resumption. Keep current.

## Branch / HEAD

- Branch: `feature/council-live-view-phase-events`
- Base / current HEAD: `03ed887` (frozen observer-hook tip; nothing committed
  on this branch yet).
- Stacked PRs: #71 (foundation → main, draft) and #72 (observer-hook →
  foundation, draft, head `03ed887`) — both OPEN, both unmerged.
- Worktree: `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`.

## Completed work (this branch)

- Seam design APPROVED (with CED-side no-op suppression + registry
  RATIFICATION timing move) and IMPLEMENTED per the approved signature.
- `ced.py`: `_advance_phase` wrapper (the ONLY `state.advance_phase` caller
  — static-guard-tested); 11 sites replaced; registry enters RATIFICATION
  before `run_council_ratification`, `_build_council_final` keeps only
  COMPLETE (final `phase_history` unchanged — byte/authority tests prove it).
- Golden tests: 16 new phase-event tests (see PLAN step 4 for the list).

## Emitted sequences (empirical, offline mock)

- LEGACY run stream (25 events): run.started · phase.started[opening] ·
  1 role · phase.started[initial_response] · 3 roles ·
  phase.started[elenchus] · 2 roles · phase.started[reflection] · 3 roles ·
  phase.started[reconstruction] · 1 role · phase.started[synthesis] ·
  4 roles · phase.started[ratification] · 1 role ·
  phase.started[complete] · run.completed.
- REGISTRY run stream (24 events): same through synthesis; then
  phase.started[ratification] (BEFORE council work; NO evaluator role) ·
  phase.started[complete] · run.completed.
- Readiness fallback: run.started · run.completed (zero phase events —
  documented exception). Mid-phase quorum fallback: canonical prefix up to
  and including the blocked phase; never RATIFICATION/COMPLETE.
- Raising-ledger failure sequences (exact, empirically locked): legacy 26,
  registry 25, interleaved in the same order as the enabled streams.

## Uncommitted (awaiting review, before commit)

- `backend/dialogues/ced.py` (wrapper + 11 site replacements)
- `tests_dialogues/test_ced_observer_golden.py` (16 new tests)
- this docs folder

## Tests — exact results

- Golden file: **42 passed**. Four-file focused: **236 passed**.
- Full `tests_dialogues`: **1799 passed** (byte-identical FinalResponse and
  authority-state parity re-proven — the RATIFICATION timing move changed
  nothing canonical).

## Blockers / next safe step

- **STOP before commit** for review of the implementation diff + sequences.
- After sign-off: commit `Add phase transition events to CED observer`,
  push, stacked Draft PR (base: `feature/council-live-view-observer-hook`).

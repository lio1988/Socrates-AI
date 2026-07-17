# MEMORY — feature/council-live-view-phase-events

Stable context and the code-grounded facts the seam design rests on.

## Empirical facts (verified in ced.py @ 03ed887 — line numbers approximate)

- `SessionState.advance_phase(new_phase)` (models.py:738) is the ONLY
  canonical phase mutation: appends the phase being LEFT to `phase_history`
  (skipping no-op re-entries) and sets `state.phase`.
- There are EXACTLY 11 `state.advance_phase(...)` call sites, ALL inside
  `ced.py` (none elsewhere in the repo):
  1. `_run_registry_phase` (959) — all six registry deliberation phases;
  2. `_build_council_final` (1657, 1658) — registry RATIFICATION + COMPLETE,
     advanced back-to-back at final build (bookkeeping AFTER the council
     ratification executed — the projection mirrors the canonical mutation
     order, exactly like role_history);
  3. legacy per-phase methods (1841, 1865, 1892, 1922, 1955, 1983) —
     OPENING…SYNTHESIS;
  4. legacy `run_ratification_phase` (3158) RATIFICATION; legacy COMPLETE
     (3249).
- Order at EVERY site: `advance_phase` FIRST, `_apply_phase_roles` after —
  so `phase.started` naturally precedes that phase's `role.assigned`.
- Both runners begin with a NO-OP `advance_phase(OPENING)` (state is
  constructed at OPENING): history is not appended, but the wrapper IS
  called — so `phase.started[opening]` fires when opening work actually
  begins, in both paths.
- The registry READINESS fallback returns before any phase runs: no
  advance call ever → NO `phase.started` at all (honest: no phase work
  began; `state.phase == OPENING` is a construction default, not a started
  phase).
- The MID-PHASE quorum fallback: `_run_registry_phase` advances BEFORE
  running tasks, so the blocked phase DID start → events include it.
- `state.round_number` is never incremented anywhere (canonically 0);
  it is the canonical `round_index` for `phase.started`.

## Canonical parity formula (the test cornerstone)

For any run where at least one advance call happened:

    phase.started sequence  ==  [p for p in state.phase_history] + [state.phase]

(entered-phase reconstruction: history[i] is the phase LEFT at transition i,
so the entered sequence is history + current). Readiness fallback: zero
`phase.started` (documented exception — no advance call ever).

## Locked invariants (inherited + this slice)

- Wrapper delegates to `state.advance_phase` FIRST, emits SECOND —
  `phase_history` bytes and semantics untouched; `models.py` untouched.
- Emission goes through the existing `_emit_event` isolation choke: disabled
  → no build; raising → recorded on the observer side channel only;
  byte-identical `FinalResponse` and identical authority state.
- No duplicate `phase.started`: identity `(run_id, phase, round_index)` +
  identical content ⇒ ledger idempotent dedupe (a deliberate use of the
  foundation's idempotency semantics for repeat/no-op advances).
- Sequence remains the `EventLedger`'s sole responsibility.
- Inherited gate: NO ratification-event emission until the random
  ratification routing-ID gate (observer branch MEMORY) is resolved.

## Future boundary (non-blocking, from the pre-commit review)

Today's no-op suppression means a re-entry into the SAME phase with a
DIFFERENT `round_index` is not yet a canonical transition — `SessionState`
holds no separate phase-round identity, which is correct for the current
runtime (no repeated dialectic rounds exist). When real repeated rounds are
added later, the order is: FIRST canonical round/re-entry state on
`SessionState`, THEN distinct `phase.started` identities per round. Never
invent round identity in the projection before the canonical model has it.

## Workflow constraints

- Worktree `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`, branch
  `feature/council-live-view-phase-events` off `03ed887`.
- Tests: `Set-Location <worktree>` then
  `& C:\Users\spirc\Desktop\Socrates-AI\.venv\Scripts\python.exe -m pytest …`.
- All `*.md` gitignored → `git add -f`. No amend/force-push. PR #71/#72 stay
  unmerged; observer branch frozen at `03ed887`.

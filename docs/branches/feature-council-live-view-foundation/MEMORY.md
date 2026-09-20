# MEMORY — feature/council-live-view-foundation

Stable context and non-negotiable invariants. Not an action log.

## Decisions already made

- The package `backend/dialogues/projection/` is **runtime-inert**: it must
  never import `ced.py`, `provider_registry`, `providers`,
  `offline_provider_adapter`, `live_providers`, or `models`. A static guard
  test (`TestRuntimeInertness`) enforces this.
- Slice 0 delivers CONTRACTS ONLY. Emission from `ced.py` (Slice 1) is a
  separate branch off this tip, guarded by a byte-identical `FinalResponse`
  golden test. Do not start it on this branch.
- Where the parent mapping's original §9.2 sketch differs from the code, the
  executable `contract_matrix.CONTRACT_MATRIX` + typed `payloads.py` are
  authoritative (see the Implementation Addendum in both architecture docs).

## Non-negotiable invariants (locked by review rounds 1–4)

- **Events**: closed 22-type dotted taxonomy; `ced_epistemic_event_v1`
  envelope is strict + frozen; identity is EXECUTABLE
  (`derive_event_idempotency_key` from matrix identity fields, verified on
  every draft — arbitrary keys impossible); `session.created` is
  session-scoped (`run_id=None`), all else run-scoped; `stream_id` derived,
  sentinels rejected; `emitted_at` tz-aware UTC.
- **Ledger**: sequence starts at 1, gap-free per stream, assigned at append;
  duplicate → existing event (no new sequence); conflict →
  `CedEventConflictError`; global `event_id` uniqueness; `_preflight` runs
  ALL checks BEFORE the clock and again after for races; deep-copy isolation
  on every read/append; same-session-only causality; no global singleton, no
  callbacks, clock never called under lock.
- **Reveal**: `AnonymousMapping` is run-scoped
  `(session, run, phase, round, evaluator, purpose)`, `strict=True`,
  digest-sealed (schema+context+policy+assignments+order); canonical
  `verify_mapping` (recomputes from context, not a checksum); write-once,
  TOCTOU-safe snapshot-before-verify registration; gated reveal; `NEVER`
  permanently sealed; **not a scheduler** (SelfSubjectError is a tripwire,
  never repair).
- **Role display**: projects canonical `role_history` verbatim; strict rows
  carrying EXACTLY `{phase, round_index, agent_id, role}`; no recalculation,
  no inferred primary role, no silent repair.
- **Registries** `CONTRACT_MATRIX` / `PAYLOAD_MODELS` are immutable
  `MappingProxyType` views.

## Important files

- `backend/dialogues/projection/`: `taxonomy.py`, `contract_matrix.py`,
  `payloads.py`, `events.py`, `ledger.py`, `reveal.py`, `role_display.py`,
  `__init__.py`.
- Tests: `tests_dialogues/test_projection_events_ledger.py`,
  `test_projection_reveal_role_display.py`,
  `test_projection_contract_matrix.py`.

## Constraints / workflow

- Isolated worktree: `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`.
- Tests run with the sibling repo's venv:
  `& C:\Users\spirc\Desktop\Socrates-AI\.venv\Scripts\python.exe -m pytest …`
  (PowerShell cwd resets between calls — always `Set-Location` first).
- Architecture docs under `docs/` are gitignored (`*.md`) → stage with
  `git add -f`. Branch docs under `docs/branches/` are also `*.md` → same.
- No amend, no force-push. Each review round is a new commit.

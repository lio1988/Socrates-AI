# MEMORY — feature/council-live-view-observer-hook

Stable context and non-negotiable invariants for Slice 1. Not an action log.

## Locked Slice 1 boundaries (from review — non-negotiable)

- **Dependency injection, not a global ledger.** The observer/ledger is passed
  in (constructor or run argument); no module-level singleton.
- **Disabled / default-off.** With no observer wired, behavior is byte-for-byte
  the pre-hook code path.
- **Observer failure is isolated.** If the observer or ledger raises, the run
  continues and returns a byte-identical `FinalResponse`; the failure never
  propagates into CED control flow (mirror `self_improvement_error` isolation).
- **No event changes control flow.** Emission is a side-effect only.
- **No event changes roles, scores, assembly, or ratification.** The observer
  reads already-computed canonical facts; it never feeds back.
- **Events are emitted only AFTER the canonical CED fact exists.** Never emit a
  fact CED has not yet computed.
- **Sequence is the `EventLedger`'s sole responsibility.** The observer builds
  drafts; the ledger assigns sequence at append. The observer never numbers.
- **No SSE / FastAPI / frontend.** Transport is Slice 2.
- **No provider / OpenRouter change.**
- **Do not merge the foundation PR yet.**

## Foundation invariants this branch relies on (unchanged)

- Runtime-inert contract package `backend/dialogues/projection/`:
  `events` (executable identity, wire round-trip), `ledger` (seq-from-1,
  idempotent/conflict, pre-clock preflight, deep-copy isolation, same-session
  causality), `reveal` (run-scoped, strict, TOCTOU-safe), `role_display`,
  `contract_matrix`/`payloads` (immutable registries).
- `derive_event_idempotency_key` derives keys from matrix identity fields;
  arbitrary keys are impossible.

## Determinism baseline (empirically established)

For a fixed `(question, session_id)`, both `run_session` and
`run_registry_session` (offline mock) produce a `FinalResponse` whose
`model_dump(mode="json")` differs across runs in EXACTLY these four paths:
`("response_id",)`, `("created_at",)`, `("synthesis","answer_id")`,
`("synthesis","assembled_at")`. The golden canonicalizer removes EXACTLY
those paths (explicit path deletion, never key-name filtering, never "strip
wherever found"); everything else — answer text, section winners,
`selected_draft_id`, scores, ratification, audit — is byte-identical. Any new
non-deterministic path therefore breaks the golden test (intended).

## Future-slice blocker: random ratification routing IDs (LOCKED GATE)

The authority-state parity work established empirically that on the registry
path the `RatificationVerdict.task_id` / `.move_id` (and `ratification_id`)
are **random `_uid()` routing identifiers**, unlike deliberation move ids /
draft ids which are deterministic. Acceptable TODAY because this slice emits
no ratification events. **BEFORE implementing `ratification_vote.recorded`,
`blocking_objection.raised`, or `runner_up.replaced` emission**, one of the
following must land first:

- make the ratification task/move IDs deterministic (stable task identity,
  like deliberation moves), OR
- give the event contract a different deterministic `ratification_id` that
  does not depend on those routing ids.

Without this, ratification-event idempotency identity
`(ratification_id, voter_id/provider_id)` would be built on random ids —
replays would never dedupe and cross-run determinism would break.

## Important files

- To change (later): `backend/dialogues/ced.py` — add the injected observer
  seam only.
- New test: `tests_dialogues/test_ced_observer_golden.py` (baseline lock).

## Workflow constraints

- Worktree: `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation` (now on
  `feature/council-live-view-observer-hook`).
- Tests: `Set-Location <worktree>` then
  `& C:\Users\spirc\Desktop\Socrates-AI\.venv\Scripts\python.exe -m pytest …`.
- All `*.md` are gitignored → `git add -f`. No amend, no force-push.

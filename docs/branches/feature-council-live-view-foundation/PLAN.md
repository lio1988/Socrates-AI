# PLAN — feature/council-live-view-foundation

## Success criterion

Runtime-inert `backend/dialogues/projection/` contract package (events,
ledger, reveal, role display) that survives adversarial review, keeps `ced.py`
and all existing behavior untouched, and keeps the full `tests_dialogues`
suite green.

## Scope / non-goals

See [README.md](README.md). In scope: contracts + in-memory ledger + reveal /
role-display + tests + docs. Out of scope (later slices): emission hook,
transport, frontend, receipt/conversation projection, OpenRouterAdapter.

## Ordered implementation steps

- [x] Slice 0 foundation: taxonomy, envelope, ledger, reveal, role display,
      tests, docs (`f8124d0`).
- [x] Review round 1 hardening — 10 findings: policy-downgrade, deep
      immutability, canonical verify, failure atomicity, wire round-trip,
      payload parity, strict role rows, delimiter-safe keys, coherence, UTC
      (`de52ad5`).
- [x] Review round 2 integrity gates — 7 findings: executable identity,
      global event_id uniqueness + causality, reveal-store locking, parent
      payload parity, receipt rules, frozen registries, reserved role rows
      (`83435ef`).
- [x] Review round 3 finalization — 5 findings: run-scoped reveal, TOCTOU
      snapshot, resolvable typed receipt, pre-clock validation, same-session
      causality, unresolved-section flags guard; doc addendum (`ebb5c19`).
- [x] Repository sync: merge `origin/main` (`AGENTS.md`, `CLAUDE.md`); add
      this branch documentation folder.
- [x] Review round 4 — 1 narrow blocker: strict reveal input contract +
      real monkeypatch TOCTOU regression test.
- [ ] Foundation review sign-off → open Draft PR (user, in GitHub UI —
      `gh` token here cannot open PRs on `lio1988/Socrates-AI`).
- [ ] Slice 1 (SEPARATE branch off this tip): flag-gated observer/emission
      hook in `ced.py`, failure-isolated, byte-identical `FinalResponse`
      golden test.

## Completed

- The runtime-inert projection contracts, ledger, reveal policy, strict role
  display, architecture documentation, and adversarial review rounds 1–4 are
  complete at the verified implementation head.
- PR #71 is open as a Draft and this implementation branch is review-only.

## Remaining / deferred work

- Diagnose the repository-level GitHub Actions `startup_failure` before
  landing.
- Re-run the stack landing audit after Actions and branch-documentation gates
  are green.
- Observer emission, phase events, execution events, transport, and frontend
  remain separate stacked or future slices; none belongs in this branch.

## Validation gates (every commit)

1. Focused: the three `test_projection_*` files green.
2. Full: `tests_dialogues` green (no regression).
3. `git diff --cached --check` clean; `git status --short` shows only the
   intended files.
4. No `ced.py` / provider / registry change; runtime-inertness guard green.

## Stop conditions

- Stop after this docs-only review fix and keep the branch frozen.
- Do not make PR #71 ready or merge it until the landing audit is green.
- Never amend or force-push; never touch the sibling dirty worktree's
  OpenClaw files.

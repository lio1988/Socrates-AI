# PRESENT — feature/council-live-view-foundation

Exact current state for safe resumption. Keep current.

## Branch / HEAD

- Branch: `feature/council-live-view-foundation`
- Worktree: `C:\Users\spirc\Desktop\Socrates-AI-live-view-foundation`
  (isolated; the sibling `C:\Users\spirc\Desktop\Socrates-AI` holds unrelated
  in-progress OpenClaw work — never touch it).
- Tip: the `Complete Council Live View reveal contract` commit (round 4),
  whose parent is `6ca08dd` (merge of `origin/main` = `b699dad`). Branch is
  even with `origin/main` on history (0 behind) and ahead by the foundation +
  merge + reveal-contract commits.

## Foundation commits (oldest → newest)

1. `f8124d0` Add Council Live View event foundation
2. `de52ad5` Harden Council Live View foundation contracts (review round 1)
3. `83435ef` Complete Council Live View foundation integrity gates (round 2)
4. `ebb5c19` Finalize Council Live View foundation references and isolation
   (round 3)
5. `6ca08dd` Merge `origin/main` (adds `AGENTS.md`, `CLAUDE.md`)
6. `Complete Council Live View reveal contract` (round 4) — this commit

## Completed work

Slice 0 (+ inert ledger half of Slice 1) complete and hardened through four
adversarial review rounds. See
[../../architecture/COUNCIL_LIVE_VIEW_FOUNDATION.md](../../architecture/COUNCIL_LIVE_VIEW_FOUNDATION.md)
for the per-round finding list. Round 4: `AnonymousMapping` is now
`strict=True` (wire-enum before-validator; whitespace/sentinel/blank-subject
rejection; digest patterns) with a real monkeypatch TOCTOU regression test.

## Changed files (13 foundation files)

- `backend/dialogues/projection/`: `__init__.py`, `taxonomy.py`,
  `contract_matrix.py`, `payloads.py`, `events.py`, `ledger.py`, `reveal.py`,
  `role_display.py` (8).
- `tests_dialogues/`: `test_projection_events_ledger.py`,
  `test_projection_reveal_role_display.py`,
  `test_projection_contract_matrix.py` (3).
- `docs/architecture/`: `KARPATHY_LLM_COUNCIL_MAPPING.md`,
  `COUNCIL_LIVE_VIEW_FOUNDATION.md` (2).
- Plus this branch documentation folder
  `docs/branches/feature-council-live-view-foundation/` (README, MEMORY,
  PLAN, PRESENT).

## Tests — exact results (round 4)

- Focused reveal file: `71 passed`.
- Three focused projection files:
  `test_projection_events_ledger.py` + `test_projection_reveal_role_display.py`
  + `test_projection_contract_matrix.py` → `194 passed`.
- Full: `tests_dialogues` → `1757 passed`.
- Run with: `Set-Location <this worktree>` then
  `& C:\Users\spirc\Desktop\Socrates-AI\.venv\Scripts\python.exe -m pytest …`.

## Invariants held

- `ced.py`, providers, and the registry are untouched.
- The projection package is runtime-inert (guard test green).
- `git diff --check` clean; no amend, no force-push.

## Blockers / next safe step

- Draft PR: BLOCKED pending foundation review sign-off. Opening it is a user
  action in the GitHub UI (`gh` token here cannot open PRs on the repo).
- Slice 1 (observer/emission hook): BLOCKED — must be a SEPARATE branch off
  this tip after the foundation PR, guarded by a byte-identical
  `FinalResponse` golden test.
- Next safe step: await round-4 sign-off, then open the Draft PR.

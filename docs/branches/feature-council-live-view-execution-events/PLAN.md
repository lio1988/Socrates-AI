# PLAN — feature/council-live-view-execution-events

## Success criterion

Emit deterministic and semantically honest CED execution events:
construction-time `task.created`, outcome-time `provider.failed`, and registry
`move.validated`, with explicit-round-aware canonical full 64-hex task/move
identities and complete observer isolation.

## Scope

- Add deterministic task and move identities inside `backend/dialogues/ced.py`.
- Emit execution events across the public legacy, registry, and standalone
  registry runner paths.
- Cover event timing, failure mapping, digest canonicalization, strict task
  kinds, explicit round identity, and observer isolation.
- Maintain this branch's documentation under
  `docs/branches/feature-council-live-view-execution-events/`.

## Non-goals

- No changes to `backend/dialogues/models.py`.
- No changes to provider execution or provider-result semantics.
- No fabricated legacy `move.validated`, ratification, tree, or lesson events.
- `provider.requested` and `provider.completed` remain deferred.
- No landing, retargeting, readiness-state changes, or modification of lower
  frozen stack branches.

## Ordered implementation steps

1. Branch from the frozen phase-events implementation head.
2. Define the observed task-kind allowlist and honest failure-category mapping.
3. Replace random task identities with deterministic canonical identities.
4. Add construction-time `task.created`, outcome-time `provider.failed`, and
   registry `move.validated` at isolated emission chokepoints.
5. Harden task and move IDs with `ced_task_v1` / `ced_move_v1`, canonical JSON,
   explicit `round_index`, strict `TaskKind`, and full 64-hex SHA-256.
6. Extend coverage to standalone registry council and gather runners.
7. Prove strict move-digest canonicalization remains inside the observer
   isolation choke and non-finite content cannot fail CED execution.
8. Run golden, focused, and full dialogue validation gates.
9. Commit the implementation and the PR #74 review fix, then freeze the branch.

## Validation gates

1. Golden observer suite: **71 passed**.
2. Four focused observer/projection files: **265 passed**.
3. Full `tests_dialogues`: **1828 passed**.
4. `git diff --check`: clean.
5. `backend/dialogues/models.py`: untouched.
6. FinalResponse bytes, authority state, and provider semantics: preserved.
7. Task/move IDs: explicit-round-aware, canonical, and full 64-hex.
8. Public registry paths and observer failure isolation: covered.

## Stop conditions

- Stop on any production/test change after the verified implementation head.
- Stop if a documentation-only review fix touches anything outside this
  branch's documentation folder.
- Do not add deferred event families or fabricate missing provider/move data.
- Never amend, rebase, force-push, merge, retarget, or mark a stacked PR ready
  during a frozen-stack audit.

## Completed

- The execution-event slice and all three review rounds were implemented.
- `task.created` now precedes execution; `provider.failed` remains an outcome
  event; strict move-digest construction executes inside observer isolation.
- Task/move identities are explicit-round-aware, canonical, versioned, and
  full 64-hex; all public registry runner paths are covered.
- No fabricated `TaskKind` fallback remains in the reviewed paths.
- PR #74 was frozen after verified implementation head
  `d00c867a27ddf94d99f562b81b538a090d274eeb`.

## Remaining / deferred work

- Diagnose the repository-level GitHub Actions `startup_failure`.
- Repeat the read-only landing audit after Actions can create jobs.
- Keep `provider.requested`, `provider.completed`, legacy move validation, and
  ratification/tree/lesson execution events deferred.
- Actual bottom-up landing remains deferred pending an explicit GO.

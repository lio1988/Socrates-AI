# Phase 8R execution plan

## Success criterion

Produce and verify a documentation-only decision gate that respects the sealed
falsification, derives precedence from actual source order, and pre-registers a
falsifiable next experiment without changing the canonical successor runtime.

## Scope and non-goals

Scope is static repository analysis, frozen-artifact verification, decision and
probe pre-registration, branch documentation, and existing read-only tests.
All aggregate, runtime, provider, shadow, learning, and depth changes are out of
scope.

## Ordered steps

1. [done] Verify sealed branch base, HEAD, artifact identity/hash/commit, and
   protected worktree state.
2. [done] Create the Phase 8R branch from the sealed HEAD.
3. [done] Map session, roster, provider, model, configuration, task, context,
   root, observation, pending, and branch identity dependencies.
4. [done] Trace exact capture, prepare, apply, compatibility, parser, firewall,
   application, and finalization check order.
5. [done] Select Model A and classify provider/model/config reachability.
6. [done] Freeze eleven orthogonal and seven precedence probes, versioning,
   success criteria, falsification criteria, and next milestone.
7. [done] Write the canonical decision report and required branch documents.
8. [done] Run only the allowed existing tests, artifact integrity checks, and
   `git diff --check`; record exact results.
9. [pending] Commit documentation only, verify clean tracked state and protected
   untracked files, and report the Phase 8R checkpoint.

## Validation gates

- Phase 8 recording/corpus/contracts/environment pre-result suite;
- focused Phase 8 environment suite;
- sealed Phase 8 artifact working-tree/commit byte identity and SHA-256;
- Phase 5/7 artifact integrity tests and hashes;
- focused CED production-path parity tests;
- `git diff --check`;
- zero aggregate/provider/model/tool calls;
- documentation-only tracked diff;
- protected untracked files untouched.

## Stop conditions

Stop without promotion if any sealed hash changes, an existing test fails, the
probe analysis cannot preserve a declared earlier guard, a runtime change is
needed, an aggregate/provider path is invoked, or the worktree includes any
unrelated/protected file.

# Branch: feature/socrates-normal-live-cli-v1

Adds a thin, offline-testable Normal Socrates command-line entry point over the
best current canonical registry-backed CED. It restores “type any question and
run the full council” without weakening or reusing Q2–Q7 benchmark machinery.

## Success criterion

One stable PowerShell command accepts an arbitrary question, derives its runtime
identity and the current full-CED call/cost plan, refuses over-budget execution
before dispatch, runs only `CEDOrchestrator.run_registry_session()`, persists a
sanitized unique result, and renders according to governing release state.

## Scope

- thin Normal-mode API and CLI;
- executable-semantics call/cost planner;
- runtime question/run identity and safe artifacts;
- governing-aware public rendering and progress;
- comprehensive offline fake-provider tests and practical documentation.

## Non-goals

- no CED, role, scoring, assembly, ratification, governing, retry, or output-limit
  semantic changes;
- no Q2–Q7 protocol, key, bundle, verifier, evidence, or runner changes;
- no live provider calls and no push.

## Offline verification

- Normal boundary: 85 passed, with one Windows symlink-capability skip.
- Full `tests_dialogues` suite: 4,187 passed, 19 failed, 10 skipped.
- The exact 19 failure node IDs are identical to the clean `c841a99` baseline;
  this branch adds no failure and removes no frozen baseline failure.

# feature/socrates-zero-search-v0

## Phase-1 objective

Introduce strict, immutable, deterministic SocratesZero search contracts while
preserving byte-for-byte default CED behavior.

## Ordered work

1. Complete the repository audit and record the CED constitution/policy split.
2. Add versioned `SearchState`, `LegalAction`, `ActionGenerator`,
   `SearchBudget`, `SearchStrategy`, `ValueEstimator`, `PolicyPrior`,
   `SearchResult`, and `SearchReceipt` contracts.
3. Add deterministic semantic identities that exclude volatile audit metadata.
4. Add fail-closed action-target and budget validation.
5. Classify the package as search authority, never governing authority.
6. Add focused contract tests and run the full dialogue regression suite.

## Acceptance integration hardening

1. [done] Isolate and enforce phase-aware Socratic content acceptance.
2. [done] Prove rejected questions receive no accepted move ID or Reflection.
3. [done] Enforce the existing marker contract from one canonical predicate.
4. [done] Integrate the reviewed commits by cherry-pick.
5. [done] Rerun combined focused and repository-wide regressions.

## Validation gates

- deterministic identity and strict-schema tests pass;
- CED/Hybrid/provider/search neighbor tests pass;
- full `tests_dialogues` passes with no new skip;
- repository-wide tests pass;
- `git diff --check` passes;
- protected pre-existing untracked files remain untouched;
- staged diff contains only this branch's ADR, checkpoints, contracts,
  authority classification, and tests.

## Deferred sequence

1. Formal adapter for the unchanged fixed-rotation baseline.
2. Read-only CED/Hybrid to `SearchState` projection.
3. Deterministic legal-action generator validated at the canonical CED
   execution boundary.
4. Heuristic prior/value and matched-budget Best-of-N.
5. Bounded PUCT with transpositions and progressive widening.
6. Shadow-only execution and episode/receipt comparison.
7. Learned priors/value only after sufficient governed experience.
8. True RL/self-play only after search and evaluation evidence justify it.

## Stop conditions

Stop if a change would bypass CED validation, create a second support/release
authority, turn quality scores into truth, fabricate a failed observation,
silently exceed a budget, change default execution, or add neural/CUDA
dependencies before evidence warrants them.

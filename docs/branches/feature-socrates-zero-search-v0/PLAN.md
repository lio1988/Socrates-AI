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

## Board state and legal moves

1. [done] Extract canonical fixed-rotation task specs without duplication.
2. [done] Implement the explicit fixed baseline strategy and audit receipt.
3. [done] Project accepted CED/Hybrid public records read-only into SearchState.
4. [done] Preserve H8 by keeping Hybrid access on the trusted CED side.
5. [done] Implement deterministic phase-aware hard legal actions.
6. [done] Prove baseline decisions are legal on actual CED phase prefixes.
7. [done] Run focused, dialogue-wide, and repository-wide validation.
8. [done] Harden explicit semantic versions and contradictory terminal input.

## Deterministic policy prior

1. [done] Reuse the canonical `PolicyPrior` and `ActionPrior` contracts.
2. [done] Implement versioned model-free heuristic and uniform priors.
3. [done] Keep support exactly within the supplied legal action set.
4. [done] Add canonical normalization, exploration floor, and reason-code audit.
5. [done] Prove Policy cannot call Constitution to re-decide legality.
6. [done] Run focused, authority, dialogue-wide, and repository-wide tests.

## Leakage-safe state Value

1. [done] Reuse the canonical async `ValueEstimator` contract and `[-1,+1]` range.
2. [done] Implement versioned Neutral and Heuristic estimators.
3. [done] Restrict v0 to inspectable unresolved/terminal penalty signals.
4. [done] Add deterministic reason-coded audits and receipt-compatible hashes.
5. [done] Prove forbidden metadata and fixture futures cannot affect Value.
6. [done] Prove Value calls neither Policy nor Constitution.
7. [done] Run focused, authority, dialogue-wide, and repository-wide tests.

## Deterministic one-ply strategy baselines

1. [done] Implement Greedy Policy argmax over the complete hard-legal set.
2. [done] Keep root Value separate from action-conditioned statistics.
3. [done] Add the minimal injected successor-state/evaluator contract.
4. [done] Implement fixed-maximum `N=4` one-ply Best-of-N.
5. [done] Enforce parent/depth/budget/path-usage successor invariants.
6. [done] Aggregate sibling compute under one shared hard budget.
7. [done] Preserve deterministic action-to-successor receipt linking.
8. [done] Prove zero runtime execution authority and run full regressions.

## Validation gates

- deterministic identity and strict-schema tests pass;
- CED/Hybrid/provider/search neighbor tests pass;
- full `tests_dialogues` passes with no new skip;
- repository-wide tests pass;
- `git diff --check` passes;
- protected pre-existing untracked files remain untouched;
- staged diff contains only the scoped branch implementation, tests, ADR, and
  checkpoints.

## Deferred sequence

1. [done] Formal adapter for the unchanged fixed-rotation baseline.
2. [done] Read-only CED/Hybrid to `SearchState` projection.
3. [done] Deterministic legal-action generator validated at the canonical CED
   execution boundary.
4. [done] Heuristic and uniform PolicyPrior reference implementations.
5. [done] Neutral and Heuristic ValueEstimator reference implementations.
6. [done] Deterministic Greedy strategy baseline.
7. [done] Budgeted one-ply Best-of-N with injected successors.
8. [next] Bounded PUCT with transpositions and progressive widening.
9. Shadow-only execution and episode/receipt comparison.
10. Learned priors/value only after sufficient governed experience.
11. True RL/self-play only after search and evaluation evidence justify it.

## Stop conditions

Stop if a change would bypass CED validation, create a second support/release
authority, turn quality scores into truth, fabricate a failed observation,
silently exceed a budget, change default execution, or add neural/CUDA
dependencies before evidence warrants them.

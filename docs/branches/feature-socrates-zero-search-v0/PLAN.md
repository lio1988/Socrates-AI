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

## Bounded deterministic PUCT

1. [done] Inspect the successor seam and freeze safe relative depth at one.
2. [done] Add immutable `puct-config/v0` with untuned default `c_puct=1.0`.
3. [done] Register the complete hard-legal root edge set without pruning.
4. [done] Allocate serial simulations using explicit deterministic PUCT math.
5. [done] Require one fresh, charged successor observation for every visit.
6. [done] Keep Q as undiscounted same-orientation mean backed-up leaf Value.
7. [done] Keep duplicate semantic states path-local and diagnostic only.
8. [done] Add a bounded rich PUCT companion receipt without mutating v0 receipts.
9. [done] Prove misleading-Policy override, replay, budgets, isolation, failures,
   terminal handling, estimator interchangeability, and no fake depth.
10. [done] Run focused, dialogue-wide, and repository-wide acceptance gates.

## Frozen matched-compute evaluation

1. [done] Audit honestly measurable resource counters; define no universal
   compute score.
2. [done] Version and commit successor budgets 1/2/4/8 before results.
3. [done] Version and commit 20 balanced deterministic cases before results.
4. [done] Remove all direct and label-derived ground-truth side channels before
   comparative execution.
5. [done] Implement the immutable offline harness, exact metric/status schemas,
   receipt links, and independently checked resource accounting.
6. [done] Prove adversarial ground-truth isolation, budget rejection, state and
   order isolation, exact regret, denominators, and deterministic replay.
7. [done] Commit the deterministic runner, then execute the frozen 11×20 matrix
   with zero live API calls.
8. [done] Commit and replay-lock the machine-readable benchmark artifact.
9. [done] Record methodology, exact results, limitations, and durable
   Phase 5 checkpoint; run all required regression suites.
10. [stop] Do not begin Phase 6, RL, live shadow, or production wiring.

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
8. [done] Bounded serial one-real-ply PUCT with path-local duplicate states.
9. [done] Phase 5 offline matched-compute search-kernel evaluation harness.
10. [decision gate] Phase 5.5 — Evidence Review / Architecture Decision Gate.
    Review, without implementation: (A) safe deeper successor semantics,
    (B) richer canonical verification/resolution state, (C) real read-only
    shadow orchestration, (D) governed trajectory collection / learned-Value
    preparation, or (E) simplification/deprioritization of PUCT.
11. [not selected] Learned priors/value only after sufficient governed
    experience and a separate approval.
12. [not selected] True RL/self-play only after search and evaluation evidence
    justify it and a separate approval.

## Stop conditions

Stop if a change would bypass CED validation, create a second support/release
authority, turn quality scores into truth, fabricate a failed observation,
silently exceed a budget, change default execution, or add neural/CUDA
dependencies before evidence warrants them.

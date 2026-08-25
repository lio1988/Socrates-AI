# Branch: feature/socrates-zero-heuristic-value-v1

## Current state

- Created from exact Phase 6.5 checkpoint
  `64f37471f4fb3357375b44f7b5eeb3341964c5a1`.
- Repository truth and the active-claim/projection chain have been audited.
- No estimator behavior or evaluation result exists yet.
- Frozen Value-v1 semantic and audit contracts live at the trusted CED boundary
  in `backend/dialogues/ced_search_value_v1_contracts.py`.
- The exact nine-category `18/27` canonical source-recipe suite, metric IDs,
  split, thresholds, semantic digest, SHA lock, and leakage tests are complete.
- The original `/v0` holdout lineage was invalidated after a pre-harness unit
  test touched pair 033. The repaired `/v1` case set has new neutral identities,
  a replacement pair-033 recipe, and no Value result yet.
- `HeuristicValueEstimatorV1` now implements only the frozen penalty-only
  semantics at `backend/dialogues/ced_search_value_v1.py`.
- Estimator/case/v0/observability focused verification: `72 passed`.
- Development result: Value v0 ordered `1/5` (`20%`) and required ties `12/13`;
  Value v1 ordered `5/5` (`100%`) and required ties `13/13` (`100%`). Value v1
  has zero directional errors, ordered ties, ranking loss, or hard-safety counts.
- The repaired `/v1` primary holdout is authoritative and passed. Value v0
  ordered accuracy is `2/7` (`28.57%`); Value v1 is `7/7` (`100%`), a
  `+71.43pp` delta. The same exact result holds on the nonterminal ordered
  subset. Value v1 required ties are `20/20`, with zero directional errors,
  ordered ties, ranking loss, and all hard-safety counters.
- Primary artifact ID is
  `szvaluev1artifact_803646dbfff5a0449309bf4690ddcc8b6e374fe80ab5826d5fc56c749dc27e49`;
  SHA-256 is
  `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- The primary artifact contract, exact threshold classifier, rule/split locks,
  replay checks, overwrite refusal, and one-shot holdout runner are frozen.
- The unlocked secondary search case set is frozen before execution: 7 ordered
  quartets plus 4 guardrail quartets, each with exactly four canonical
  successors and four real Constitution actions.
- The secondary one-factor adapters, exact threshold classifier, resource and
  guardrail counters, immutable artifact contract, replay checks, overwrite
  refusal, and runner are implemented; no BestOfN result exists yet.

## Worktree

Only authorized Phase 7 branch setup is in progress. The two protected
pre-existing untracked files remain untouched.

## Next safe step

Commit the pre-run secondary harness, then execute it once and preserve/replay
lock its result regardless of outcome.

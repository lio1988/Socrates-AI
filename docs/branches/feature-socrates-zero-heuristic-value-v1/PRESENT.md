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
  refusal, and runner are implemented.
- The secondary gate passed: Value v0 selection is `2/7` (`28.57%`), Value v1
  is `7/7` (`100%`), delta `+71.43pp`; guardrail, budget, successor-accounting,
  and new-failure counts are all zero. Each arm used exactly 5 nodes and 4
  expansions with zero model/tool calls.
- Secondary artifact ID is
  `szvaluev1bestofnartifact_c154689cd122f5f7dd68da5d7b31c34b26d049233e6425d3758f56491b11522d`;
  SHA-256 is
  `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- Phase 7 implementation, primary/secondary artifacts, replay locks, complete
  regression matrix, ADR, and methodology/result documentation are complete.
- Phase 7.5 audited every experimental successor seam, actual CED transition
  owner, branch-mutable state family, replay/snapshot donor, provider control,
  counterfactual-fairness requirement, and learning/RL prerequisite.
- The exact Phase 7.5 decision is `CANONICAL SUCCESSOR ENVIRONMENT NEXT`.
  Option A has the larger eventual external-validity payoff, but currently
  depends on the CED-owned one-transition parity/isolation primitive selected
  under Option B.
- Depth two, real shadow execution, provider calls, Experience Store, learned
  Policy/Value, RL, and production authority remain locked.
- The next branch, not started here, is
  `feature/socrates-zero-canonical-successor-env-v0`.

## Verification

- Phase 7.5 required gates: Value v1 `77 passed`; Phase 6 canonical
  observability/projection v1 `17 passed`; Phase 5 evaluation integrity
  `37 passed`.
- Exact Phase 5, Phase 7 primary, and Phase 7 BestOfN SHA-256 locks rechecked;
  Phase 5 Git blob remains
  `0488de8a555658a55312d8b1da8614ab9347743b`.
- `git diff --cached --check` passes and the Phase 7.5 scope contains six
  documentation paths only.
- Value v1 `77`; Value v0 `21`; contracts v0 `19`; projection v0 `11`;
  observability/projection v1 `17`;
- Policy `13`; Greedy `27`; BestOfN `24`; PUCT `53`; Phase 5 evaluation `37`;
- SocratesZero `333`; Hybrid H8 + SocratesZero `344`; focused CED/Socratic
  `252`;
- `tests_dialogues`: `2399 passed, 1 skipped`;
- repository-wide: `2706 passed, 1 skipped, 23 pre-existing warnings`;
- Phase 5 artifact SHA unchanged; primary and secondary replay/byte locks pass;
- provider/model/live calls: `0`.

## Worktree

Only authorized Phase 7 branch setup is in progress. The two protected
pre-existing untracked files remain untouched.

## Next safe step

Stop before implementation on this branch. If separately authorized, create
`feature/socrates-zero-canonical-successor-env-v0` and freeze an offline
CED-owned one-transition parity/isolation experiment. Do not run real shadow
calls or unlock depth two.

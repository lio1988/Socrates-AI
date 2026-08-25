# Branch: feature/socrates-zero-heuristic-value-v1

## Durable facts

- Exact base: `64f37471f4fb3357375b44f7b5eeb3341964c5a1`.
- Search input IDs remain `socrates.zero.search-state/v1` and
  `ced-search-state-projection/v1`.
- Estimator ID is `heuristic-value-estimator/v1`; base is `0.0`, bounds are
  `[-1,+1]`, and every numeric component is non-positive.
- Value-v1 contracts and implementation remain on the trusted CED side so the
  runtime-inert `socrates_zero` package does not import Hybrid authority.
- Active assessments are the intersection of v1 governing assessment claim IDs
  and `base_state.active_claims`; one worst state is scored once.
- Frozen claim deficits are falsified `-0.20`, external-required `-0.12`,
  unresolved `-0.08`, unsupported `-0.05`, and supported `0` without bonus.
- One canonical Socratic remainder may contribute `-0.05` after canonical
  objection IDs are removed from v0 unresolved IDs.
- Terminal precedence suppresses every claim/remainder component. Blocked is
  `-0.20`, budget-exhausted `-0.10`, answer-ready/abstained neutral.
- Evidence, verification, lifecycle, digests, source IDs, and counts are
  structural/audit inputs only and never independent directional features.
- The initially frozen `socrateszero-value-v1-eval-case-set/v0` lineage is
  invalidated because a unit test evaluated holdout pair 033 before harness
  freeze. The authoritative recovery case set is separately versioned
  `socrateszero-value-v1-eval-case-set/v1`; the unchanged harness semantic ID is
  `socrateszero-value-v1-eval-harness/v0`.
- Exactly 45 pairs are required: two development and three holdout pairs in
  each of nine frozen categories.
- Holdout cases, split, metrics, thresholds, and estimator semantics must be
  committed before the first holdout result. No semantic or case change is
  allowed afterward under these IDs.
- Primary promotion requires overall and nonterminal ordered accuracy at least
  80%, each at least 20 percentage points above Value v0, 100% required-tie
  guardrails, and zero hard-safety violations.
- Secondary BestOfN is locked unless primary passes. PUCT cannot rescue Value.
- The sealed Phase 5 normalized artifact SHA-256 remains
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Learned Value and RL remain not earned; Value v1 remains advisory only.
- Authoritative primary decision: `VALUE V1 HYPOTHESIS PASSED`. Value v0
  ordered/nonterminal accuracy was `2/7`; Value v1 was `7/7`, delta `+71.43pp`.
  Required ties were `20/20` and every hard-safety count was zero.
- Primary artifact ID/SHA are
  `szvaluev1artifact_803646dbfff5a0449309bf4690ddcc8b6e374fe80ab5826d5fc56c749dc27e49`
  and `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- Authoritative secondary decision: `VALUE V1 BESTOFN GATE PASSED`. Matched
  UniformPolicy/BestOfN selection improved from `2/7` to `7/7`; all resource,
  accounting, guardrail, and failure regression counts were zero.
- Secondary artifact ID/SHA are
  `szvaluev1bestofnartifact_c154689cd122f5f7dd68da5d7b31c34b26d049233e6425d3758f56491b11522d`
  and `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- Both artifacts replay semantically, by identity, and byte-for-byte.
- Phase 7 stops after recommending a new decision gate. It does not choose
  between read-only real counterfactual shadow collection and safe canonical
  successor-environment work.

## Protected local state

Do not touch `scripts/live_dialogue.py.bak` or the malformed untracked root
filename beginning `ocratic_followup_mandate`.

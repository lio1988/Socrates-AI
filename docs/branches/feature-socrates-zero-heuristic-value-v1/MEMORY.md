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
- Evaluation IDs are `socrateszero-value-v1-eval-case-set/v0` and
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

## Protected local state

Do not touch `scripts/live_dialogue.py.bak` or the malformed untracked root
filename beginning `ocratic_followup_mandate`.

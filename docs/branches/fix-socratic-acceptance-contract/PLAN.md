# fix/socratic-acceptance-contract

## Ordered work

1. Add a phase-aware deterministic Socratic content validator.
2. Apply it at the CED acceptance boundary before move identity is assigned.
3. Prove empty, malformed, ungrounded, and unresolved questions are refused.
4. Run focused cycle/retry/firewall and full repository regressions.
5. Commit this acceptance fix independently.
6. Harden the existing epistemic-marker contract as a second commit.
7. Cherry-pick both reviewed commits into the SocratesZero branch.

## Non-goals

- no search, policy, value, MCTS, or runtime flag change;
- no prompt redesign or new marker vocabulary;
- no change to provider-envelope parsing semantics;
- no live external call without available credentials.

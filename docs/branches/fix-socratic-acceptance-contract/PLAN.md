# fix/socratic-acceptance-contract

## Ordered work

1. [done] Add a phase-aware deterministic Socratic content validator.
2. [done] Apply it at the CED acceptance boundary before move identity is assigned.
3. [done] Prove empty, malformed, ungrounded, and unresolved questions are refused.
4. [done] Run focused cycle/retry/firewall and full repository regressions.
5. [done] Commit this acceptance fix independently.
6. [done] Harden the existing epistemic-marker contract as a second commit.
7. [next] Cherry-pick both reviewed milestones into the SocratesZero branch.

## Non-goals

- no search, policy, value, MCTS, or runtime flag change;
- no prompt redesign or new marker vocabulary;
- no live external call without available credentials.

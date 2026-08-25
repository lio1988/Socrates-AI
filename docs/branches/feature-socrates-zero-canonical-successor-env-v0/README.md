# Branch: feature/socrates-zero-canonical-successor-env-v0

## Purpose

Implement the Phase 8 foundation selected by the Phase 7.5 architecture gate:
one CED-owned, branch-isolated, offline action-plus-recorded-observation
transition for the canonical opening Socratic-question family.

## Success criterion

For every frozen authoritative case, the same canonical root, the same hard-
legal `ASK_SOCRATIC_QUESTION` action, and the same exact recorded observation,
bound to its original semantic task/context/provider/model/configuration, must
produce the same normalized canonical successor as the existing CED path. The
source, sibling, and production states must remain unchanged; identities,
SearchState-v1 projection, resources, receipts, artifact serialization, and
independent replay must be deterministic.

## Scope

- opening `SOCRATES / SOCRATIC_QUESTION / round=0 / slot=0 / attempt=0` only;
- behavior-preserving extraction of the existing CED task/response application
  seam, used by both production registry execution and replay;
- immutable capsule, pending transition, recorded observation, result, receipt,
  parity corpus, artifact, and replay lock;
- recorded offline observations only and zero provider/model/tool calls.

## Lineage status

The original v0 corpus is preserved but explicitly invalidated for
authoritative parity because it rebound raw output to caller metadata. The
observation-bound corpus v1 and its manifest are frozen in commit `5ad83db`.
The complete pre-result evaluator contract is frozen in `36393fe`. The first
aggregate artifact is committed at `07ec5ab` and the frozen result is
`FALSIFIED`: all five supported cases passed, but `wrong-provider` returned the
earlier `ROOT_CONTEXT_MISMATCH` rather than the predeclared provider-specific
reason. No second aggregate or replay lock was run. See
`../../SOCRATES_ZERO_PHASE8_AUTHORITATIVE_OBSERVATION_LINEAGE_V1.md` for the
full pre-result contract.

## Non-goals

No other legal-action family, live or shadow provider collection, generic
environment loop, depth two, recursive search, search authority, Value/Policy
change, Experience Store, learning, RL, Hybrid authority change, or production
wiring.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

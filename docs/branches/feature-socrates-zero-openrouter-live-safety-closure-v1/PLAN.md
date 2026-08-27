# PLAN — feature/socrates-zero-openrouter-live-safety-closure-v1

## Success criterion

`OPENROUTER LIVE-SAFETY CLOSURE v1 SUPPORTED` only if every frozen positive case
is accepted, every adversarial case is rejected, every zero threshold holds,
replay is deterministic, S6 is unchanged and all regressions pass. Otherwise the
result is FALSIFIED.

## Scope

Additive P17 proof contracts, complete price-ceiling overlay v2, exact P19 cost
coverage, operator spend ceiling, one-call authorization/consumption, synthetic
JIT credential and transport facts, frozen cases, evaluator, tests and evidence.

## Non-goals

No live call, credential access, current pricing, actual endpoint-price claim,
production monetary values, runtime/CED authority, S6 edits or push.

## Ordered steps

1. Initialize branch and canonical documentation.
2. Audit retained P17 model-limit and tokenizer evidence.
3. Implement additive P17, request-v2, P19, authorization and preflight contracts.
4. Freeze comprehensive positive, adversarial, cross-request and metamorphic cases.
5. Implement the deterministic evaluator and focused tests.
6. Run all required pre-authoritative regression gates.
7. Commit semantic implementation and create an explicit freeze marker commit.
8. Execute exactly one authoritative offline aggregate and deterministic replay.
9. Run post-authoritative regressions and predecessor-integrity checks.
10. Record the result, commit locally and stop without pushing.

## Predeclared threshold classes

- all positive cases accepted;
- all adversarial cases rejected;
- unexpected results, invalid fixtures and guard mismatches: 0;
- heuristic P17 authority, byte-to-token substitution, incomplete coverage,
  omitted-request-fee-to-zero promotion, hidden terms, cross-request substitution,
  authorization reuse and privacy leakage accepted: 0;
- external activity in every category: 0;
- deterministic semantic, artifact-ID and byte replay;
- S6 semantics/artifacts and all measured predecessors unchanged.

Exact numeric case thresholds and their content identity will be frozen in the
evaluator before authoritative execution.

## Stop conditions

Stop and falsify on any unauthorized P17 method, incomplete applicable charge
coverage, hidden monetary term, cross-request substitution, reusable
authorization, credential leakage, live activity, nondeterministic replay or
predecessor mutation. Do not repair and rerun after authoritative execution.

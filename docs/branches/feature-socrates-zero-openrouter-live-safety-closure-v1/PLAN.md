# PLAN — feature/socrates-zero-openrouter-live-safety-closure-v1

## Success criterion

`OPENROUTER LIVE-SAFETY CLOSURE v1 SUPPORTED` only if every frozen positive case
is accepted, every adversarial case is rejected, every zero threshold holds,
replay is deterministic, S6 is unchanged and all regressions pass. Otherwise the
result is FALSIFIED.

## Scope

Additive P17 proof contracts, complete price-ceiling overlay v2, exact P19 cost
coverage, operator spend ceiling, one-call authorization/consumption, synthetic
JIT credential, transport and claim-store-readiness facts, frozen cases,
evaluator, tests and evidence.

## Non-goals

No live call, credential access, current pricing, actual endpoint-price claim,
production monetary values, runtime/CED authority, S6 edits or push.

## Ordered steps

1. **Complete:** initialize branch and canonical documentation.
2. **Complete:** audit retained P17 model-limit and tokenizer evidence.
3. **Complete:** implement additive P17, request-v2, P19, authorization,
   consumption, preflight and claim-store-readiness contracts.
4. **Complete:** declare 73 comprehensive positive/property, adversarial,
   cross-request and metamorphic cases.
5. **Complete:** implement the deterministic evaluator and focused tests.
6. **Complete:** run all required pre-authoritative regression gates.
7. **Next:** verify the committed semantic implementation at
   `a5deafb68c0c951ed7a2768b6a63e08917f7cce1`, confirm only the pre-freeze
   documentation is pending and all authoritative paths are absent, then commit
   the pre-freeze documentation.
8. Create a separate explicit empty marker commit named
   `chore: freeze OpenRouter live-safety closure v1`.
9. Execute exactly one authoritative offline aggregate and deterministic replay.
10. Run post-authoritative regressions and predecessor-integrity checks.
11. Record the result, commit locally and stop without pushing.

No step 9 output currently exists. Development-only in-memory checks do not
replace step 9 and their stale artifact identity must not be reused.

The authoritative artifact, replay execution and replay lock paths in
`artifacts/` are all absent.

## Frozen inputs before the authoritative run

- Cases: 73 = 20 positive/property + 53 adversarial.
- Case-set ID:
  `szorlivesafetycasesetv1_21ab3255104dbb5fe0ca5e2255a2f4d205c7f2d6364a67588e2c39b69c9eba01`.
- Thresholds ID:
  `szorlivesafetythresholdsv1_ccc445fda16e9022f40ed0a3d133365d823b1cbe0f844803926c8564502ecec9`.
- Synthetic request ID:
  `szorrenderedliverequestv2_4d1b04a731f98462a8d349611c105fe818fae18c1a1a3de8c2b02dfb835c00a2`;
  body SHA-256
  `9ba640bf29bf6ad77c2a6dd0b4b038fbe4567aa51146b0e2699ea49a2ee0b8a8`;
  length 512 bytes. All numeric values are test fixtures only.

Production request, P17 record, price ceilings, total-spend ceiling and physical
trusted durable non-rollback claim store remain finite
`JIT_PENDING`/`OPERATOR_REQUIRED` facts for S7B. The local readiness contract is
implemented; physical store realization is not claimed by S7A.

## Pre-freeze gates

S7A 106 passed; S6 149; S5 109; S3 64; route 103; manifest 25; final all
OpenRouter 835 passed/1 skipped; full `tests_dialogues` 3643 passed/10 skipped;
predecessor 742/742; S6 semantic/artifact surfaces 8/8 unchanged.

An earlier pre-S7 all-OpenRouter run recorded
`KNOWN PRE-EXISTING INTERMITTENT PREDECESSOR FAILURE` at
`test_one_shot_offline_acquisition_publishes_complete_derived_log` with 1
failed/728 passed/1 skipped/2817 deselected; its isolated rerun passed 1/1. No
fix was made, and the final pre-freeze all-OpenRouter gate was clean.

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

The exact numeric thresholds and their content identity above are implemented
and ready for the explicit semantic freeze commit before authoritative
execution.

## Stop conditions

Stop and falsify on any unauthorized P17 method, incomplete applicable charge
coverage, hidden monetary term, cross-request substitution, reusable
authorization, credential leakage, live activity, nondeterministic replay or
predecessor mutation. Do not repair and rerun after authoritative execution.

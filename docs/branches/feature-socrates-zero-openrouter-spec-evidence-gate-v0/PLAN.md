# Phase 8.5C plan

## Success criterion

Freeze official source provenance and normalized facts sufficient to decide one
next architecture path, while preserving the falsified v0 result and proving
through offline integrity gates that no historical/runtime authority changed.

## Scope

Official public-spec research, repository audit, evidence manifest, decision
report, qualitative five-path matrix, branch docs and offline verification.

## Non-goals

Runtime implementation, credentials, authenticated/public provider APIs,
inference, pricing/tokenizer dependencies, full aggregate/replay, live pilot,
CED application and any production or sealed-component mutation.

## Completed

1. Verified the exact sealed parent checkpoint and protected untracked files.
2. Created the dedicated decision-gate branch.
3. Audited the v0 repository controls without modifying runtime code.
4. Retrieved only public official OpenRouter/OpenAI sources with zero credentials
   and zero provider/model calls.
5. Separated stable protocol/schema facts from mutable model/provider facts.
6. Created a minimal content-addressed evidence manifest.
7. Audited P08, P09, P17, P18, P19, cache, metadata and one-call evidence.
8. Compared the five required architecture paths without a numeric score.
9. Selected exactly one next decision.

## Verification completed

- Every normalized fact digest and the manifest semantic digest: exact.
- Phase 5/7/8 artifacts and core blob lock: `45 passed`.
- Acquisition Contract artifact/replay/boundaries: `239 passed, 8 skipped`.
- OpenRouter adapter controls: `242 passed, 1 skipped`.
- Production OpenRouter fake/canned tests: `12 passed, 1 deliberately deselected`.
- Total pytest executions: `538 passed, 9 skipped, 1 deselected, 0 failed`.
- Final staged `git diff --check`: required before commit.

## Explicit non-work

No adapter/runtime edit, provider object, pricing implementation, tokenizer
dependency, credential access, API call, model execution, replay lock, aggregate
rerun, CED application or frozen-component mutation.

## Stop conditions

- Any source fact lacking primary provenance is `NOT VERIFIED`.
- Any source/schema drift is fail-closed.
- Any credential, network, provider, model, tool or CED activity stops the gate.
- Any historical hash mismatch or unexpected tracked mutation blocks checkpoint.
- Full adapter v1 is not authorized unless all P08/P09/P17/P18/P19 paths are
  credible and explicit.

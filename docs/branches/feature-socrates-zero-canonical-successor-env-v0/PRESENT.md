# Branch: feature/socrates-zero-canonical-successor-env-v0

## Current state

- The repaired authoritative observation lineage is committed at `5ad83db`.
- The historical v0 corpus remains preserved and explicitly invalidated.
- Corpus v1 freezes five exact canonical captures through unchanged offline
  donor producers: one accepted and four canonical rejections.
- Full semantic task/context/provider/model/configuration binding, exact
  manifest membership, caller-rebinding firewall, future-label firewall, and
  the single-family environment are implemented and focused-tested.
- CED owns outcome classification and both production/replay use the same
  CED-owned response-application/finalization seam.
- Evaluator `/v1` contracts cover the five supported cases, fourteen
  unavailable probes, thirteen parity fields, strict zero-failure thresholds,
  measured isolation/call evidence, reverse-order replay, and write-once
  publication. Final hardening is committed at `36393fe`.
- The authoritative aggregate ran exactly once and produced `FALSIFIED`.
- Supported authoritative parity is 5/5. Unavailable negatives are 13/14.
- `wrong-provider` expected `OBSERVATION_PROVIDER_MISMATCH` but the actual
  fail-closed reason is `ROOT_CONTEXT_MISMATCH`; provider roster is already
  part of the CED-owned canonical task context.
- No second aggregate, independent replay, or replay lock was run.
- The immutable artifact is committed at `07ec5ab`, ID
  `cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0`,
  SHA-256
  `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.
- No live provider/model/tool call has occurred.

## Commits

- `5ad83db` — freeze authoritative Phase 8 observation lineage.
- `36393fe` — freeze Phase 8 parity evaluator before results.
- `1a9e571` — checkpoint the complete pre-aggregate freeze.
- `07ec5ab` — record the first, falsified Phase 8 parity artifact.

## Verification

- Recording/corpus/contracts/environment: `67 passed`.
- Focused CED production parity: `241 passed`.
- Frozen Phase 5/7 artifact integrity: `10 passed`.
- Evaluator contract/schema gate: `8 passed`.
- Combined Phase 8 pre-result gate: `75 passed`.
- All three Phase 5/7 hashes match their sealed values.
- Aggregate executions at the pre-result freeze: `0`.
- First authoritative aggregate: `FALSIFIED`.
- Aggregate executions: `1`; independent replay executions: `0`.

## Remaining work

Preserve the immutable artifact and this durable falsification checkpoint, then
stop. Do not relax the v1 taxonomy or rerun under the same semantic IDs.

## Worktree

The two protected pre-existing untracked files remain untouched.

## Next safe step

After this durable checkpoint is committed, verify artifact bytes and protected
files, then stop. Phase 8.5 is not authorized.

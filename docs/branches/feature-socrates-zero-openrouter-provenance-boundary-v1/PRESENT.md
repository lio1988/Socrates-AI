# PRESENT — feature/socrates-zero-openrouter-provenance-boundary-v1

## State

- Branch: `feature/socrates-zero-openrouter-provenance-boundary-v1`
- Source HEAD: `0d09822048d4f7c34cf234342ec4c36ef3db0ead`
- Result: **PROVENANCE BOUNDARY v1 SUPPORTED**
- Phase: complete. Not pushed.

## Commits on this branch

| commit | subject |
| --- | --- |
| `acc0dfc` | docs: initialize OpenRouter provenance boundary v1 |
| `661840c` | fix: separate OpenRouter historical provenance from runtime paths |
| `526e6ca` | test: lock OpenRouter provenance boundary v1 |
| `d4d2e0c` | docs: complete OpenRouter provenance boundary v1 checkpoint |
| `08ec697` | refactor: split historical and current scoped snapshot contracts |
| `8d81ac6` | fix: isolate historical OpenRouter provenance generation |
| _(this)_ | docs: record OpenRouter historical generation isolation |

Every earlier commit is preserved exactly as made; each correction is additive
history, not an amendment.

## Worktree

Clean. An earlier, unpublished S3 attempt had left three modified files here;
they were discarded before any work began and nothing from that attempt is
reused. Its patch is preserved outside the repository only.

## Completed

All nine steps of [PLAN.md](PLAN.md).

- Raw-path audit and AST classification: **runtime semantic dependencies = 0**.
- Additive provenance boundary module with two content-addressed immutable
  records; boundary identity
  `szorprovenanceboundaryv1_50048e2921e4d6c6d978be822a21f6ffe9407e922c8450582cff7a91cbaaceaf`.
- Provenance-only evaluator edits. The sealed historical snapshot contract is
  preserved as-is; the current generation has its own separate contract.
- 64 adversarial locks added; one existing inventory test adapted, not weakened.
- Canonical result documented in
  [docs/SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md](../../SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md).

## Changed files

| file | change |
| --- | --- |
| `backend/dialogues/socrates_zero/openrouter_provenance_boundary_v1.py` | new, additive, import-inert; also holds the current scoped contracts |
| `backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py` | provenance-only, plus the historical reconstruction path (+259 / -52) |
| `tests_dialogues/test_socrates_zero_openrouter_acquisition_provenance_boundary_v1.py` | new, 64 locks |
| `tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_evaluation.py` | one inventory test adapted |
| `docs/SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md` | new |
| `docs/branches/…-provenance-boundary-v1/evidence/openrouter_historical_scoped_inventory_v1.json` | new, historical evidence record |
| `docs/branches/feature-socrates-zero-openrouter-provenance-boundary-v1/*` | new, four documents |

Nothing else was touched. No sealed artifact was regenerated and no expected hash
constant was changed.

## Raw-path audit

| measure | before | after |
| --- | --- | --- |
| repository-wide tracked references | 23 | 22 |
| runtime Python (`backend/`, `scripts/`) | 5 | 3 |
| Route Controls runtime surface | 2 | **0** |
| exempt predecessor module itself | 3 | 3 |
| runtime semantic dependencies | 0 | 0 |
| predecessor expected-label consumption | 0 | 0 |

## Inventory generations

Two generations, two contracts, two identity namespaces:

| | historical | current |
| --- | --- | --- |
| contract | `OpenRouterScopedPathSnapshotV1` | `OpenRouterCurrentScopedSnapshotV1` |
| inventory ID | `szorroutepathinventoryv1_0ec9a8417d7cb91bb0e17fc0b402577032cf207ace89cddc32276390ec661e33` | `szorcurrentpathinventoryv1_98024a610f23a604be4aca79b0971f8898c4b7e8802737451888131222b3ce7b` |
| snapshot ID | `szorroutesnapshotv1_9ee38a257c992778102ca9b176e5ea99831aaae70ffbf4b016f2a3dbb7c4417b` (frozen, 90 rows) | `szorcurrentsnapshotv1_…` (recomputed per capture) |

The sealed contract accepts only the historical inventory ID. Neither contract
trusts a caller-declared `snapshot_id`. The historical generation has **zero**
references to the current inventory, current inventory ID, current snapshot
contract or current provenance constants, enforced by an AST scan.

## Builder differential audit

Audited against a clean, unmodified worktree of `0d09822`, same preconditions,
tripwire active.

| probe | source `0d09822` | current | equivalent |
| --- | --- | --- | --- |
| `reverse_case_order=True` | CONSTRUCTED, FALSIFIED | CONSTRUCTED, FALSIFIED | yes |
| `reverse_case_order=False` | raises `…requires an exclusive claim` | same | yes |
| snapshot stage reached (A / B) | yes / no | yes / no | yes |

Current code run against the untouched source tree reproduces the source
builder's artifact `szorroutecontrolartifactv1_4fed5904…` and snapshot
`szorroutesnapshotv1_485f1550…` exactly. Historical reconstruction: **PRESERVED**,
through the immutable historical evidence record
(`b17ca9e4df2d4dd5d540474aa375b7708bbed7234ff0dbc9fd06827be2e598bc`).

## Tests and exact results

| gate | result |
| --- | --- |
| exact static node, before the change | FAIL, as expected |
| exact static node, after the change | 1 passed |
| Route Controls focused suite | 103 passed (baseline 103) |
| v1 + v2r1 evidence suite | 48 passed (baseline 48) |
| new provenance boundary suite | 64 passed |
| predecessor cases suite | 12 passed |
| full `tests_dialogues` | 3279 passed, 10 skipped |
| `git diff --check` | PASS |

## Frozen surface hashes — after

Re-hashed after the change and diffed against the pre-edit record: **all 15
identical**, byte for byte. The values are unchanged from the table recorded at
initialization, including:

| file | sha256 |
| --- | --- |
| sealed Route Controls v1 artifact | `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661` |
| Manifest v1 authoritative evidence | `cafd9364db1357b9aa676a7b45baeac2ef8a9f1b4288044fbaed95fcb3d4397b` |
| Manifest v1 validation | `26c4616bb6b07ca3e5d2d0a1385c2d10aa8e9d523f90ca2c87d9872dc2ee4bc7` |
| Manifest v1 revalidation | `c389c1816b364e787ba5270b121fdeb820a7426182f6d1d69e6a51aa796f187b` |
| Manifest v2r1 authoritative manifest | `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb` |
| Manifest v2r1 validation | `7a75d644d0d6e61d3a9c5e5ef04bf5f16cd292206bc998e6952219b7ac11fb85` |
| Manifest v2r1 revalidation | `75442d3bf74aeb5217a2e20db2580aacebe55d0fe21ee6d18288f38cb8defa1a` |
| six v2r1 official source snapshots | unchanged |

## External activity

OpenRouter 0, provider 0, model 0, credential 0, CED 0, aggregate 0, replay 0.
No fetch, no push.

## Blockers

None for this milestone.

Unchanged by design and still open upstream: Route Controls v1 remains FALSIFIED;
exact endpoint response identity, P17, P18 and P19 remain NOT_ESTABLISHED; the
live pilot remains NOT EARNED.

## Next safe step

Phase 8.5D-S4 — OpenRouter Wire-Mapping v2 Authorization Gate Rerun.

The branch is committed locally and deliberately not pushed.

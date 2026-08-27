# SocratesZero — OpenRouter Provenance Boundary v1

Phase 8.5D-S3. Branch `feature/socrates-zero-openrouter-provenance-boundary-v1`,
started from `feature/socrates-zero-openrouter-wire-spec-evidence-v2r1` at exactly
`0d09822048d4f7c34cf234342ec4c36ef3db0ead`.

## Result

**PROVENANCE BOUNDARY v1 SUPPORTED.**

## Hypothesis

> Historical OpenRouter scientific provenance required by Route Controls can be
> represented through immutable semantic IDs, artifact IDs, artifact hashes,
> sealed commit identities and — only where required — Git object identities,
> instead of active raw predecessor source/test paths, while preserving mutation
> protection and every frozen Route Controls semantic and artifact.

## The problem

The Route Controls evaluator holds `FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1`,
a 90-entry scoped inventory (SOURCE 16, SIBLING 35, PRODUCTION 39) used for
mutation and integrity coverage. Two SIBLING entries were raw predecessor paths:
the OpenRouter adapter case-design module and its test suite. The repository's own
static boundary node rejects any runtime module in
`backend/dialogues/socrates_zero/` that names the predecessor case module, and it
was failing at the source checkpoint.

The audit below establishes that these two entries were never a runtime semantic
dependency. They were provenance and mutation-inventory coupling only.

## Pre-edit audit

| measure | before | after |
| --- | --- | --- |
| raw predecessor references, repository-wide (tracked) | 23 | 22 |
| raw predecessor references, runtime Python (`backend/`, `scripts/`) | 5 | 3 |
| of which in the Route Controls runtime surface | 2 | **0** |
| of which in the exempt predecessor module itself | 3 | 3 |

Classification of the two Route Controls occurrences:

| occurrence | classification |
| --- | --- |
| `..._evaluation.py:1624` — case-design module path | PROVENANCE / MUTATION_INVENTORY_ONLY |
| `..._evaluation.py:1635` — case-suite test path | PROVENANCE / MUTATION_INVENTORY_ONLY |

| probe | result |
| --- | --- |
| AST imports of predecessor acquisition cases | 0 |
| AST imports of predecessor tests | 0 |
| `importlib` / `__import__` / `exec` / `eval` in the evaluator | 0 |
| references to `FROZEN_OPENROUTER_ADAPTER*` or `expected_label` | 0 |
| **runtime semantic dependencies** | **0** |

The `expected_guard_id` occurrences in the evaluator (10) belong to the Route
Controls guard vocabulary from `openrouter_route_controls_cases`, not to the
predecessor case set.

## The three separated concepts

| concept | representation after this change |
| --- | --- |
| A. current runtime semantic dependency | none for the predecessor — proven by AST audit, not asserted |
| B. historical scientific provenance | immutable identity record; no raw path |
| C. current mutation / integrity coverage | scoped inventory, hash-verified against disk |

## The new provenance model

`backend/dialogues/socrates_zero/openrouter_provenance_boundary_v1.py` is
additive and import-inert. It defines `OpenRouterProvenanceRecordV1`, whose
`record_id` is content addressed over every identity field, and two frozen
records that replace the two raw paths in place and in order:

| field | case-design record | case-suite record |
| --- | --- | --- |
| `reference_id` | `provenance://socrateszero/openrouter-adapter-case-design/v0` | `provenance://socrateszero/openrouter-adapter-case-suite/v0` |
| `semantic_id` | `socrateszero-openrouter-acquisition-case-set/v0` | `socrateszero-openrouter-acquisition-case-suite/v0` |
| `scientific_role` | `PREDECESSOR_CASE_DESIGN` | `PREDECESSOR_CASE_SUITE` |
| `artifact_id` | `szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f` | same |
| `artifact_sha256` | `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083` | same |
| `case_set_id` | `oracqcasesetv0_0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373` | same |
| `validation_order_id` | `oracqvalidationv0_137f7049f806222f1901f5e1790535f41b8d06558cb1ebb41aba4643f3782cf3` | same |
| `sealed_commit_sha` | `a79ca97777d1c8c9db4234399cd4c716d360ebd5` | same |
| `sealed_content_sha256` | `3268c64b6084871f8cb268b7c2fd44fd7318fe613f8d37b438416e07de3e46b8` | `7268f5bb3dc24c0393e0d81ddd1b0d2498ea024538fd16e151e183b22a0d1273` |
| `git_object_sha1` | `7d3db1ac9a47ccb0dff1d6df2ab5b5e983abbda7` | `4db44774e4c682074809e2012c75e474735b43bc` |
| `record_id` | `szorprovenancerecordv1_f87fa4c166388831ef60ac584d2a9786c51edc7b504c9f9d06c95d686e675c38` | `szorprovenancerecordv1_22f85340d4dbdd8b0e685c4ae5d5d2d6197adf323321e37218e589351c8898ee` |

Boundary identity:
`szorprovenanceboundaryv1_50048e2921e4d6c6d978be822a21f6ffe9407e922c8450582cff7a91cbaaceaf`

These are frozen literals. The boundary module imports only `__future__`, `enum`,
`typing`, `pydantic` and `.contracts` — it never reaches predecessor semantics to
establish provenance, which would reintroduce the dependency it removes.

The digest a provenance row contributes to the scoped snapshot is the record's own
content address, so tampering with **any** identity field changes the row digest
and is reported as a SIBLING mutation.

## Historical versus current inventory

Because the current inventory genuinely no longer contains those two raw paths,
its derived inventory identity genuinely changes. That value is not forced back
to the historical one, and the sealed contract is not stretched to cover it.

The two generations are **two separate contracts in two separate identity
namespaces**. The sealed contract was not widened to describe both.

| | historical | current |
| --- | --- | --- |
| contract | `OpenRouterScopedPathSnapshotV1` | `OpenRouterCurrentScopedSnapshotV1` |
| module | `openrouter_route_controls_evaluation` | `openrouter_provenance_boundary_v1` |
| schema | `…route-control-scoped-snapshot/v1` | `…current-scoped-snapshot/v1` |
| row type | `OpenRouterScopedPathDigestV1` (`relative_path`) | `OpenRouterCurrentScopedDigestV1` (`reference`) |
| inventory ID | `szorroutepathinventoryv1_0ec9a8417d7cb91bb0e17fc0b402577032cf207ace89cddc32276390ec661e33` | `szorcurrentpathinventoryv1_98024a610f23a604be4aca79b0971f8898c4b7e8802737451888131222b3ce7b` |
| snapshot ID prefix | `szorroutesnapshotv1_` | `szorcurrentsnapshotv1_` |
| mutation evidence | `OpenRouterScopedMutationEvidenceV1` | `OpenRouterCurrentScopedMutationEvidenceV1` |
| comparison | `compare_openrouter_route_control_scoped_snapshots_v1` | `compare_openrouter_current_scoped_snapshots_v1` |

**`OpenRouterScopedPathSnapshotV1` is preserved as the historical contract
shape.** Its `inventory_id` remains a `Literal` of exactly one value, the frozen
historical inventory ID; it does not accept the current inventory ID. What
changed is only that it no longer reaches for the live raw-path constant to
validate itself. Instead it validates historical rows through:

- the frozen historical inventory ID (`Literal`);
- the exact frozen historical row count, 90;
- a **recomputed** content-addressed snapshot ID, derived from the supplied rows;
- equality of that recomputed value with the frozen historical snapshot ID
  `szorroutesnapshotv1_9ee38a257c992778102ca9b176e5ea99831aaae70ffbf4b016f2a3dbb7c4417b`.

The snapshot ID is always recomputed and a caller-declared `snapshot_id` is never
trusted, so any mutated historical path, mutated historical digest, or reordered
historical row changes the recomputed identity and fails — and declaring the
correct frozen ID alongside tampered rows does not rescue them.

The current contract is additive and independent. Its `inventory_id` is
recomputed from its own rows' membership and order and must match, so no entry
can be added, removed or reordered without detection; it excludes the two
predecessor raw paths entirely; it requires each provenance row to carry exactly
the immutable record content address; and its `snapshot_id` is likewise always
recomputed.

Historical artifact verification and current mutation verification are now two
separate operations, and each comparison function refuses the other generation's
snapshot rather than silently comparing across the boundary. A consequence,
intended: `_build_route_control_artifact_v1` can no longer produce a v1 artifact,
because the sealed v1 generation cannot be reconstructed from today's inventory.
That path was already unreachable behind the exclusive-claim and
complete-support guards, and it now fails closed with an explicit message.

`OpenRouterScopedMutationEvidenceV1` is unchanged from the sealed checkpoint. Its
ordering rank still consults the current inventory constant, which is vacuous for
the only inputs it can now receive: the historical comparison accepts nothing but
the sealed historical snapshots, which are byte-identical and therefore always
yield zero mutations. This is verified, not assumed.

This is the distinction the S3 audit demanded. The historical artifact records
what was frozen then; the current boundary records how runtime scientific
dependencies are represented now. Neither is rewritten to match the other.

## What was explicitly not done

- No sealed artifact was regenerated.
- No expected SHA constant was updated, and no hash lock was replaced by a
  dynamically recomputed value. An earlier, unpublished S3 attempt did exactly
  that to `scripts/build_socrates_zero_openrouter_wire_spec_manifest_v1.py`; it
  was discarded and the worktree restored to `0d09822` before any work began.
- The static node was not skipped, xfailed, weakened, or special-cased, and the
  forbidden reference was not concatenated, encoded, or relocated into another
  runtime Python file.
- No parser, renderer, cases, contracts, production adapter, CED, SearchState,
  Projection, Value, Policy, search strategy, Manifest v1 or Manifest v2r1 code
  was touched.
- The frozen Route Controls artifact schema was **not** made more permissive to
  accommodate the current inventory. `scoped_before_snapshot` and
  `scoped_after_snapshot` remain typed to the historical contract alone.

## Mutation protection

Current coverage is preserved, not reduced. 88 of 90 scoped rows remain hashed
directly from disk on every capture, and the suite proves end to end that
mutating a real Route Controls source is still detected: the file-backed
inventory is mirrored into a temporary root, one SOURCE file is mutated, and the
comparison reports exactly one SOURCE mutation on that path and zero elsewhere.

The two predecessor rows are protected by immutable scientific identity instead
of by a live file hash, which is the point of the boundary: their scientific
value is what the sealed experiment recorded, not what the file says today.

## Test gates

| gate | result |
| --- | --- |
| exact static node, before | **FAIL** (as expected at the source checkpoint) |
| exact static node, after | **1 passed**, genuinely |
| Route Controls focused suite | **103 passed** (baseline 103) |
| v1 + v2r1 evidence suite | **48 passed** (baseline 48) |
| new provenance boundary suite | **58 passed** |
| predecessor cases suite | **12 passed** |
| full `tests_dialogues` | **3261 passed, 10 skipped** |
| `git diff --check` | PASS |

All 15 frozen scientific surfaces re-hashed after the change and compared to the
pre-edit record: **byte-identical**, including the sealed Route Controls artifact
`61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`, Manifest v1
`cafd9364db1357b9aa676a7b45baeac2ef8a9f1b4288044fbaed95fcb3d4397b` and Manifest
v2r1 `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb`.

## External activity

OpenRouter calls 0. Provider calls 0. Model executions 0. Credential access 0.
CED applications 0. Authoritative aggregates 0. Replays 0. The new suite is named
so the shared conftest wraps every one of its tests in the acquisition boundary
tripwire. Repository activity was local only; no fetch and no push were
performed.

## Scope

| file | change |
| --- | --- |
| `backend/dialogues/socrates_zero/openrouter_provenance_boundary_v1.py` | new, additive |
| `backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py` | provenance-only |
| `tests_dialogues/test_socrates_zero_openrouter_acquisition_provenance_boundary_v1.py` | new, 58 locks |
| `tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_evaluation.py` | one inventory test adapted, not weakened |
| `docs/SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md` and four branch documents | documentation |

## What this unlocks, and what it does not

Unlocks exactly **Phase 8.5D-S4 — OpenRouter Wire-Mapping v2 Authorization Gate
Rerun**.

It does not authorize the raw wire parser, live OpenRouter calls, a provider
pilot, the Experience Store, learned Value, learned Policy, or RL. Route Controls
v1 remains FALSIFIED. Exact endpoint response identity, P17, P18 and P19 remain
NOT_ESTABLISHED. The live pilot remains NOT EARNED.

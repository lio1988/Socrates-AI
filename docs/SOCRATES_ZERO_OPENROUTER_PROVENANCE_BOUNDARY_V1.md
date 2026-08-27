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
- entry uniqueness;
- a **recomputed** content-addressed snapshot ID, derived from the supplied rows.

The snapshot ID is always recomputed and a caller-declared `snapshot_id` is never
trusted.

The *sealed*-identity lock lives one level up, in
`verify_openrouter_route_control_sealed_historical_snapshot_v1`, which recomputes
the identity from the supplied rows and requires it to equal
`szorroutesnapshotv1_9ee38a257c992778102ca9b176e5ea99831aaae70ffbf4b016f2a3dbb7c4417b`.
`load_openrouter_route_control_artifact_v1` applies it to both snapshots of the
authoritative artifact. So a mutated historical path, a mutated historical digest
or a reordered historical row all fail, and declaring the correct frozen ID
alongside tampered rows does not rescue them.

That separation matters, and the differential audit below is why: the frozen
identity belongs to the *sealed* snapshot, not to every snapshot of the
historical generation. A freshly reconstructed historical snapshot legitimately
differs from the sealed one, and pinning the frozen ID inside the contract itself
broke reconstruction.

The current contract is additive and independent. Its `inventory_id` is
recomputed from its own rows' membership and order and must match, so no entry
can be added, removed or reordered without detection; it excludes the two
predecessor raw paths entirely; it requires each provenance row to carry exactly
the immutable record content address; and its `snapshot_id` is likewise always
recomputed.

Historical artifact verification and current mutation verification are two
separate operations, and each comparison function refuses the other generation's
snapshot rather than silently comparing across the boundary.

`OpenRouterScopedMutationEvidenceV1` no longer ranks its mutations against the
current inventory. Historical ordering derives from the historical snapshot's own
row order, which `compare_openrouter_route_control_scoped_snapshots_v1` preserves
explicitly, and the evidence contract validates uniqueness and full derivation
only. An AST scan over every historical node — the snapshot, digest, mutation and
evidence contracts, the historical loader, the historical capture, the sealed
verification and the historical comparison — reports **zero** references to the
current inventory, the current inventory ID, the current snapshot contract, or
any current provenance constant. A test loads the sealed artifact with the
current inventory, the current inventory ID and the whole provenance boundary
monkeypatched to nonsense, and gets a bit-identical artifact back.

## Historical reconstruction

The historical membership lives in an explicitly historical immutable evidence
record, `docs/branches/feature-socrates-zero-openrouter-provenance-boundary-v1/evidence/openrouter_historical_scoped_inventory_v1.json`,
generated from the sealed artifact's own snapshot rows so it cannot drift from
what the experiment measured. It is hash locked in runtime code by a frozen
SHA-256 (`b17ca9e4df2d4dd5d540474aa375b7708bbed7234ff0dbc9fd06827be2e598bc`) and
must re-derive the frozen historical inventory identity.

`capture_openrouter_route_control_historical_scoped_snapshot_v1` reads membership
from that record and digests from the target tree;
`_build_route_control_artifact_v1` reconstructs through it. This is the only
place the historical membership is materialised at runtime, and it is the only
place the two predecessor raw paths appear — as historical evidence data, outside
runtime Python. The current provenance inventory still excludes them, and the
canonical static node still passes.

## Builder differential audit

`_build_route_control_artifact_v1` was audited against a clean, unmodified
worktree of `0d09822048d4f7c34cf234342ec4c36ef3db0ead`, under identical
preconditions with the acquisition boundary tripwire active.

| probe | source `0d09822` | current | equivalent |
| --- | --- | --- | --- |
| `reverse_case_order=True`, no claim | CONSTRUCTED, FALSIFIED | CONSTRUCTED, FALSIFIED | yes |
| `reverse_case_order=False`, no claim | raises `forward authoritative aggregate requires an exclusive claim` | same | yes |
| snapshot stage reached (probe A / B) | yes / no | yes / no | yes |

Reachability: the builder is private (not in `__all__`) but reachable through the
`_artifact_command` CLI path and through `build_independent_reverse_replay_v1`.
Successful construction was a supported callable contract at source, so it had to
remain one. Two tests exercise it; neither reaches the snapshot stage, both being
stopped by upstream guards.

Equivalence is proven rather than argued: the current code, run against the
untouched source worktree, reproduces the source builder's artifact identity
`szorroutecontrolartifactv1_4fed5904faefa0da09acd4a0a5099a42381cc94f1cca7f72b42b3b6cbb129a8e`
and snapshot identity
`szorroutesnapshotv1_485f155088bcc51153bd5eaa3fef0615cc40654fb6ff82a5b0a8bd60e21d2350`
exactly.

The audit also surfaced why the first correction was over-tight. At source, a
fresh capture yields `485f1550…`, **not** the sealed `9ee38a25…` — 23 of the 90
rows have drifted since the seal (six route-control documents, two SocratesZero
siblings, fifteen production modules). The source contract checked membership and
order but never digests, so it accepted both. Historical reconstruction is
therefore **preserved**, not proven unreachable.

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
| new provenance boundary suite | **64 passed** |
| predecessor cases suite | **12 passed** |
| full `tests_dialogues` | **3279 passed, 10 skipped** |
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
| `tests_dialogues/test_socrates_zero_openrouter_acquisition_provenance_boundary_v1.py` | new, 64 locks |
| `tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_evaluation.py` | one inventory test adapted, not weakened |
| `docs/branches/…-provenance-boundary-v1/evidence/openrouter_historical_scoped_inventory_v1.json` | new, historical evidence record |
| `docs/SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md` and four branch documents | documentation |

## What this unlocks, and what it does not

Unlocks exactly **Phase 8.5D-S4 — OpenRouter Wire-Mapping v2 Authorization Gate
Rerun**.

It does not authorize the raw wire parser, live OpenRouter calls, a provider
pilot, the Experience Store, learned Value, learned Policy, or RL. Route Controls
v1 remains FALSIFIED. Exact endpoint response identity, P17, P18 and P19 remain
NOT_ESTABLISHED. The live pilot remains NOT EARNED.

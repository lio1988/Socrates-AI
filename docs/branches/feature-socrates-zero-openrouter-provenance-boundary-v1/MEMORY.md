# MEMORY — feature/socrates-zero-openrouter-provenance-boundary-v1

Stable context. Not an action log.

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-wire-spec-evidence-v2r1`
- Source HEAD: `0d09822048d4f7c34cf234342ec4c36ef3db0ead`
- Sealed v1 base: `a37e6c0068e3132ca49128295a5ef8453f91592c`

## Non-negotiable invariants

1. **Historical evidence is never rewritten to make current code pass.** The
   sealed Route Controls v1 artifact stays byte-identical. Its historical
   inventory identity stays exactly what it was.
2. **No sealed artifact is regenerated.** No expected SHA constant is updated.
   No hash lock is replaced by a dynamically recomputed value.
3. **Two versioned concepts, not one.** The historical inventory identity
   records what the frozen experiment measured. The current provenance boundary
   records how current runtime scientific dependencies are represented now.
   These are permitted to differ, and the tests must express the distinction.
4. **No predecessor semantics are imported to verify provenance.** Immutable
   identity constants are frozen literals in the boundary module. The boundary
   module must not import predecessor case modules.

## Why the previous S3 attempt was discarded

An earlier, unpublished attempt replaced the frozen constant
`SEALED_ROUTE_CONTROLS_V1_SHA256` in
`scripts/build_socrates_zero_openrouter_wire_spec_manifest_v1.py` with a hash
recomputed from the file on disk, so that a regenerated Route Controls artifact
would be accepted. That inverts the direction of evidence: a hash lock that
recomputes itself proves nothing. The attempt was discarded and the worktree
restored to `0d09822`. Its patch is preserved outside the repository only.

## Key files and interfaces

- `backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py`
  - `FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1` — scoped path inventory
    (SOURCE 16 / SIBLING 35 / PRODUCTION 39 = 90 rows).
  - `FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1` — derived inventory ID.
  - `OpenRouterScopedPathSnapshotV1` — content-addressed snapshot; validates
    membership and order; `inventory_id` was a `Literal`.
  - `capture_openrouter_route_control_scoped_snapshot_v1` — hashes each entry.
- `backend/dialogues/socrates_zero/openrouter_provenance_boundary_v1.py` — new,
  additive; immutable provenance records.

## Frozen identities used by the boundary

Predecessor: OpenRouter provider adapter-controls v0 (FALSIFIED, sealed).

| identity | value |
| --- | --- |
| artifact ID | `szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f` |
| artifact SHA-256 | `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083` |
| case-set ID | `oracqcasesetv0_0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373` |
| validation-order ID | `oracqvalidationv0_137f7049f806222f1901f5e1790535f41b8d06558cb1ebb41aba4643f3782cf3` |
| sealed commit (case design frozen) | `a79ca97777d1c8c9db4234399cd4c716d360ebd5` |
| sealed commit (artifact recorded) | `911340d0155f56dc91f784a152b9025b7ad83024` |

Historical Route Controls scoped identities, frozen as literals:

| identity | value |
| --- | --- |
| historical inventory ID | `szorroutepathinventoryv1_0ec9a8417d7cb91bb0e17fc0b402577032cf207ace89cddc32276390ec661e33` |
| historical snapshot ID | `szorroutesnapshotv1_9ee38a257c992778102ca9b176e5ea99831aaae70ffbf4b016f2a3dbb7c4417b` |
| historical row count | 90 |

## Environment

- Repository: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`
- Interpreter: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`
- `PYTHONPATH` must point at this repository root; the package is not installed.
- `.gitignore` ignores `*.md` wholesale; documentation needs `git add -f`.

See [PLAN.md](PLAN.md) and [PRESENT.md](PRESENT.md).

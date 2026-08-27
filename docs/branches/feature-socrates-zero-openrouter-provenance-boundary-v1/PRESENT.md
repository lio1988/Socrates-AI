# PRESENT — feature/socrates-zero-openrouter-provenance-boundary-v1

## State

- Branch: `feature/socrates-zero-openrouter-provenance-boundary-v1`
- Source HEAD: `0d09822048d4f7c34cf234342ec4c36ef3db0ead`
- Phase: initialized. Documentation only; no code change yet.

## Worktree

Restored to the sealed v2r1 checkpoint. An earlier, unpublished S3 attempt had
left three modified files in this worktree; they were discarded. Nothing from
that attempt is reused.

## Completed

- Repository truth audited; source HEAD confirmed exact.
- Frozen surfaces hashed and recorded (see below).
- Baselines measured: Route Controls focused 103 passed; v1 + v2r1 evidence 48
  passed; exact static node FAILS as expected at the source checkpoint.
- Branch documentation initialized.

## Remaining

Steps 2 through 7 of [PLAN.md](PLAN.md).

## Frozen surface hashes — before

| file | sha256 |
| --- | --- |
| `docs/branches/feature-socrates-zero-openrouter-route-controls-v1/artifacts/socrateszero_openrouter_route_controls_v1.json` | `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661` |
| `.../wire-spec-evidence-v1/evidence/openrouter_official_wire_specification_manifest_v1.json` | `cafd9364db1357b9aa676a7b45baeac2ef8a9f1b4288044fbaed95fcb3d4397b` |
| `.../wire-spec-evidence-v1/artifacts/..._validation_v1.json` | `26c4616bb6b07ca3e5d2d0a1385c2d10aa8e9d523f90ca2c87d9872dc2ee4bc7` |
| `.../wire-spec-evidence-v1/artifacts/..._revalidation_v1.json` | `c389c1816b364e787ba5270b121fdeb820a7426182f6d1d69e6a51aa796f187b` |
| `.../wire-spec-evidence-v1/evidence/openrouter_wire_retrieval_log_v1.json` | `8e9a6ecfe41c444323cf01c0e8d6d11ad1fd1e09d5400c14b5bf4c63278d5fd3` |
| `.../wire-spec-evidence-v1/evidence/openrouter_wire_source_plan_v1.json` | `cfaec71b93a88114e9378fe297d8cd5ec9645e6c747877eadd622003de9760a5` |
| `.../wire-spec-evidence-v2r1/evidence/openrouter_official_wire_specification_manifest_v2r1.json` | `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb` |
| `.../wire-spec-evidence-v2r1/artifacts/..._validation_v2r1.json` | `7a75d644d0d6e61d3a9c5e5ef04bf5f16cd292206bc998e6952219b7ac11fb85` |
| `.../wire-spec-evidence-v2r1/artifacts/..._revalidation_v2r1.json` | `75442d3bf74aeb5217a2e20db2580aacebe55d0fe21ee6d18288f38cb8defa1a` |
| `.../wire-spec-evidence-v2r1/evidence/sources/openapi.yaml` | `bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713` |
| `.../evidence/sources/router-metadata.mdx` | `4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6` |
| `.../evidence/sources/api-reference-overview.mdx` | `8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e` |
| `.../evidence/sources/response-caching.mdx` | `89e423514f98c2bdc5e288d5ea17159e78df29ea6ff56ea82cd8b68da1302f3e` |
| `.../evidence/sources/provider-selection.mdx` | `2781071f570c53040c0c01a9f1840097a43e6032ebd4e3d9ab2dfbeb01bb2252` |
| `.../evidence/sources/model-fallbacks.mdx` | `6d77e3242812a2b669bf22f9c9c6ac59a5d838906271d1593b2fff864c6550c1` |

## Blockers

None.

## Next safe step

Step 2 of [PLAN.md](PLAN.md): the raw-path audit and AST import classification.

# Branch: feature/socrates-zero-openrouter-provenance-boundary-v1

Phase 8.5D-S3 — OpenRouter Provenance Boundary v1.

## Purpose

Separate **current runtime semantic dependency** from **historical scientific
provenance** in the OpenRouter Route Controls evaluator, without rewriting a
single byte of sealed scientific evidence.

The Route Controls evaluator carries a frozen scoped path inventory used for
mutation/integrity coverage. Two entries in that inventory are raw predecessor
source/test paths that exist only for provenance. They are not runtime semantic
dependencies: the evaluator never imports the predecessor acquisition cases and
never consumes predecessor expected labels as route decisions. Their presence as
raw runtime strings nevertheless keeps a predecessor path an active runtime
dependency, which the repository's own static boundary test rejects.

## Hypothesis

> Historical OpenRouter scientific provenance required by Route Controls can be
> represented through immutable semantic IDs, artifact IDs, artifact hashes,
> sealed commit identities and — only where required — Git object identities,
> instead of active raw predecessor source/test paths, while preserving mutation
> protection and every frozen Route Controls semantic and artifact.

## Success criterion

`PROVENANCE BOUNDARY v1 SUPPORTED` only if all of:

- the exact static node passes genuinely (not skipped, xfailed, or weakened);
- runtime predecessor imports = 0; predecessor expected-label consumption = 0;
- forbidden raw predecessor references in runtime Python = 0;
- current Route Controls mutation protection preserved;
- sealed Route Controls artifact byte-identical
  (`61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`);
- Manifest v1 and Manifest v2r1 byte-identical;
- Route Controls focused suite and v1 + v2r1 evidence suite pass;
- `git diff --check` clean; external activity 0.

Otherwise `PROVENANCE BOUNDARY v1 FALSIFIED`.

## Scope

- One additive module `backend/dialogues/socrates_zero/openrouter_provenance_boundary_v1.py`.
- Provenance-only edits to `backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py`.
- Focused adversarial test additions.
- Branch and canonical documentation.

## Non-goals

Raw wire parser. Live OpenRouter calls. Provider pilot. Experience Store.
Learned Value or Policy. RL. Regeneration of any sealed artifact. Any change to
parser, renderer, cases, contracts, production adapter, CED, SearchState,
Projection, Value, Policy, search strategies, Manifest v1, or Manifest v2r1.

## Documents

- [MEMORY.md](MEMORY.md) — stable branch context and invariants.
- [PLAN.md](PLAN.md) — execution plan, validation gates, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state.

Canonical result: [docs/SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md](../../SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md).

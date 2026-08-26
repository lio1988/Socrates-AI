# Phase 8.5D-R plan

## Decision criterion

Choose exactly one of: wire-mapping v2 experiment earned, specification evidence
manifest v1 required first, repository boundary cleanup required first, or the
route-control approach not justified. Dependency order and frozen evidence—not
implementation preference—decide.

## Ordered work

1. Verify the sealed checkpoint, protected files, and historical identities.
2. Extract the typed wire-mapping assessment and artifact forensic sufficiency.
3. Audit frozen official evidence against every normalized parser field.
4. Build the field-by-field mapping and fixture-authenticity matrices.
5. Audit success/error/cache/attempt/endpoints/provider/strategy/pipeline rules.
6. Reproduce and classify static-inventory and teardown failures offline.
7. Determine manifest sufficiency and repository-boundary status independently.
8. Write the canonical decision report and choose exactly one next branch.
9. Run only permitted integrity/static tests and commit the durable checkpoint.

## Validation gates

- sealed artifact and manifest hashes exact;
- no aggregate/replay/artifact publication;
- exact source/fact/fixture/parser/evaluator traceability;
- no guessed official fields or semantics;
- two independent wire-mapping and repository-integrity statuses;
- one decision and one next branch only;
- zero external activity and no protected-file changes;
- `git diff --check` clean.

## Stop conditions

Stop on sealed hash drift, missing forensic evidence, external activity,
post-result semantic mutation, unsupported official-schema inference, or more
than one selected next dependency.

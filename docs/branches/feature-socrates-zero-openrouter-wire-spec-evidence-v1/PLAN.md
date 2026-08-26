# Phase 8.5D-S plan

## Frozen hypothesis

Current official OpenRouter public sources contain sufficient exact response-
schema evidence to build a content-addressed manifest in which every future
authoritative normalized field is linked to an official source path, JSON type,
presence rule, nullability rule, envelope kind, semantic meaning, and either a
directly documented or demonstrably lossless mapping.

## Ordered work

1. Verify the parent checkpoint, sealed hashes, and protected files.
2. Freeze contracts, source locators, domain allowlist, retrieval bounds, and
   sufficiency thresholds before network activity.
3. Perform one bounded official-public retrieval/inspection pass and retain
   minimal source snapshots.
4. Commit source snapshots before interpreting facts.
5. Freeze source/fact/mapping/fixture/manifest schemas and tests.
6. Extract facts and mappings; record unsupported relationships explicitly.
7. Freeze pre-evaluation counts, identities, and test results.
8. Run exactly one authoritative sufficiency evaluation and publish one
   write-once validation artifact.
9. Run one offline revalidation with no documentation retrieval.
10. Verify historical hashes, inherited boundary status, and documentation.

## Validation gates

- no source bytes used without retention, length, and digest;
- exact paths/types/presence/nullability and envelope placement required;
- no assumption-based or repository-convention positive mapping;
- deterministic canonicalization, IDs, manifest, validation, and revalidation;
- no parser/runtime/predecessor mutation;
- all external activity bounded and logged;
- inherited static failure reported separately and unchanged;
- tracked worktree clean and protected files untouched.

## Stop conditions

Stop on a non-official redirect, retrieval-limit breach, credential/authenticated
endpoint access, source-size breach, silent source substitution, predecessor
hash drift, post-freeze semantic mutation, a second authoritative evaluation,
or any parser/runtime edit.

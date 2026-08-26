# Phase 8.5D plan

## Success criterion

Meet every frozen route-controls threshold with zero external activity, zero
forbidden claims, exact historical hashes, deterministic artifact bytes and an
independent byte-identical reverse replay.

## Scope

Additive SocratesZero route-control contracts, canonical renderer, canned
metadata parser/attestation, cases, evaluator, artifact/replay and focused tests.

## Non-goals

Production wiring, credentials, external transport, live specification
revalidation, P17/P18/P19, pricing/cost/tokenizer work, CED/Search/Value/Policy
application and any frozen-component change.

## Ordered work

1. Verify checkpoint, manifest identity, protected files and historical hashes.
2. Initialize this branch documentation.
3. Audit repository-native immutable contract/evaluator/artifact/replay patterns.
4. Implement additive contracts and canonical body/header renderer.
5. Implement canned transport, metadata parser, typed partial attestation and
   receipt identity.
6. Freeze case set, mutation vectors, first-guard order and thresholds.
7. Complete adversarial pre-result tests and boundary tripwires.
8. Commit the exact pre-result freeze.
9. Run exactly one authoritative canned aggregate and publish its write-once
   artifact.
10. On complete pass only, run reverse-order replay and publish its lock.
11. Run historical, focused, full dialogue and repository-wide regressions.
12. Complete the canonical report and branch checkpoint.

## Validation gates

- manifest semantic identity and fact digests exact;
- canonical body/header and sibling equality exact;
- request, response, claim and ground-truth firewalls exact;
- orthogonal and precedence primary failures exact;
- external/credential/provider/model/tool/CED counters zero;
- source/sibling/production mutations zero;
- artifact/replay bytes deterministic;
- all frozen historical hashes exact;
- required regression suites and `git diff --check` pass.

## Stop conditions

- missing manifest support or any guessed schema;
- unexpected mutation or protected-file drift;
- external/credential/provider/model/tool/CED activity;
- aggregate before pre-result freeze;
- post-result semantic change;
- failed authoritative artifact or replay divergence.


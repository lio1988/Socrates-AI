# Phase 8.5D plan

## Decision criterion

Apply every frozen route-controls threshold with zero external activity, zero
forbidden claims, exact historical hashes, and deterministic artifact bytes.
The sole-authority manifest does not retain the complete official response wire
mapping required by the full hypothesis, so the frozen mapping assessment is
one violation against a maximum of zero. The authoritative result is
`FALSIFIED`; reverse replay was therefore prohibited and did not run.

## Scope

Additive SocratesZero route-control contracts, canonical renderer, canned
metadata parser/attestation, cases, evaluator, artifact/replay and focused tests.

## Non-goals

Production wiring, credentials, external transport, live specification
revalidation, P17/P18/P19, pricing/cost/tokenizer work, CED/Search/Value/Policy
application and any frozen-component change.

## Ordered work

1. [complete] Verify checkpoint, manifest identity, protected files and historical hashes.
2. [complete] Initialize this branch documentation.
3. [complete] Audit repository-native immutable contract/evaluator/artifact/replay patterns.
4. [complete] Implement additive contracts and canonical body/header renderer.
5. [complete] Implement canned transport, metadata parser, typed partial attestation and
   receipt identity.
6. [complete] Freeze case set, mutation vectors, first-guard order and thresholds.
7. [complete] Complete adversarial pre-result tests and boundary tripwires.
8. [complete] Commit the exact pre-result freeze.
9. [complete] Run exactly one authoritative canned aggregate and publish its write-once
   artifact.
10. [not applicable] On complete pass only, run reverse-order replay and publish its lock.
11. [complete] Run historical, focused, full dialogue and repository-wide regressions.
12. [complete] Complete the canonical report and branch checkpoint.

## Final result state

The additive contracts, exact body/header renderer,
raw-first normalized canned parser, typed partial attestation, 63-case set,
22-field mutation vectors, 32-guard order, strict thresholds, evaluator,
artifact schema, replay schema, and adversarial tests were frozen at
`848166dd3eacfa5d31175745b160b98751b3a904`. The sole aggregate published the
366,623-byte `FALSIFIED` artifact
`szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd`
with SHA-256
`61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`.
Replay is absent and prohibited.

The normalized response envelope is explicitly repository-owned and is not an
official OpenRouter wire-schema claim. The manifest-only mapping assessment is
frozen at 1 with a maximum allowed value of 0; no narrative or network source
may supplement that missing authority on this branch.

## Validation gates

- manifest semantic identity and fact digests exact;
- canonical body/header and sibling equality exact;
- request, response, claim and ground-truth firewalls exact;
- orthogonal and precedence primary failures exact;
- external/credential/provider/model/tool/CED counters zero;
- source/sibling/production mutations zero;
- authoritative artifact bytes deterministic; replay correctly absent;
- all frozen historical hashes exact;
- required regression suites executed; one sealed v0 static incompatibility
  remains recorded; `git diff --check` passes.

## Stop conditions

- missing manifest support or any guessed schema;
- unexpected mutation or protected-file drift;
- external/credential/provider/model/tool/CED activity;
- aggregate before pre-result freeze;
- post-result semantic change;
- any attempt to supplement the frozen response-wire authority;
- replay after a falsified artifact;
- malformed authoritative artifact or permitted replay divergence.

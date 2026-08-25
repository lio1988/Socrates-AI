# SocratesZero Phase 8 — Authoritative Observation Lineage v1

## Status

Pre-result repair and freeze for
`feature/socrates-zero-canonical-successor-env-v0`.

The authoritative aggregate has not been run and no Phase 8 parity artifact
exists at this checkpoint. The hypothesis remains open until the committed
evaluator is executed once against the frozen corpus.

## Scientific repair

The original corpus preserved raw provider text but materialized it with
caller-created task and provider metadata. That established repeatable
processing, not observation-bound transition replay. The historical v0 lineage
is therefore retained only for low-level tests:

```text
ID: cedobscorpus_99a8090204758b4085f6f937d0e36ab77f6fe4f79f3c66ab8416b05c49bfb8e0
canonical SHA-256: a6453fe7fe5bdabaa3258612c040ddc0e93c31214838405fa21afc373194cd8d
status: INVALIDATED / SUPERSEDED FOR AUTHORITATIVE PHASE-8 PARITY
reason: Raw provider output was rebound to caller-created task/provider
        metadata instead of retaining the exact semantic identity of the
        original canonical observation.
```

The repaired v1 lineage was committed before any aggregate result in
`5ad83db` (`feat: freeze authoritative Phase 8 observation lineage`).
The evaluator, artifact, falsification, threshold, reverse-replay, and
write-once contracts were then frozen—still before any aggregate result—in
`36393fe` (`feat: freeze Phase 8 parity evaluator before results`).

## Frozen identities

```text
environment:             ced-canonical-successor-env/v0
branch capsule:          ced-canonical-branch-capsule/v0
pending transition:      ced-pending-canonical-transition/v0
recording contract:      ced-canonical-successor-recording/v0
capture manifest schema: ced-canonical-successor-capture-manifest/v0
task semantic identity:  ced-canonical-task-semantic-identity/v0
recorded observation:    ced-recorded-observation/v1
transition result:       ced-canonical-transition-result/v0
transition receipt:      ced-canonical-transition-receipt/v0
parity definition:       ced-canonical-successor-semantic-parity/v0
corpus version:          ced-canonical-successor-parity-corpus/v1
```

Unchanged environment, capsule, pending, result, and receipt contracts retain
their v0 IDs. The observation and corpus lineages changed because their
scientific semantics changed.

```text
capture manifest ID:
cedcapturemanifest_ab3391e6fa324dec6ca2d8937ba09bdb7100c373fb7e7c38bb6be53bb0c86a60

authoritative corpus ID:
cedobscorpus_b5ebe4b46d2b3ae4fed3faded341c8a2d8ff5f5f254531f000e479bf66b7f8b7

authoritative corpus canonical SHA-256:
06c5eda5ee8c71992cb8b7427794f6d5ab6e44b4f92f0d6f71f4366d5729427c

case-set ID and fingerprint:
cedparitycaseset_4c6b248fe69d4714076f7cbd8f5fe06ed54c956e5ade9727c65a589b474983e3

thresholds ID:
cedparitythresholds_0760039f86e67235bb3d955e0db7a1b8ef0330cb15c518305646cfe68a629efd
```

## Capture and binding

Each authoritative record is acquired through this path:

```text
unchanged offline donor raw producer
-> registered recording adapter
-> CouncilProviderRegistry.run_adapter
-> BaseProviderAdapter.generate_agent_move
-> parse_and_validate_move
-> CEDOrchestrator._apply_registry_response
-> CEDOrchestrator._finalize_registry_phase
-> recording of the actual observed task, response, application, and round
```

The capture layer recomputes the semantic identity of the actual `AgentTask`
seen by CED and requires full equality with the capsule task. It records exact
raw UTF-8 text/digest, source execution and capsule, phase/round/slot/attempt,
agent/role/task kind, semantic task/context/request digests, provider ID,
configured and actual model IDs, model-configuration digest, transport status,
historical usage, provenance, and capture receipt.

Random production `task_id` and timestamps remain provenance-only and are
excluded from semantic identity. They cannot create compatibility.

Compatibility is checked fail-closed in this order:

1. source-session, context, and request identity;
2. phase/round/slot/attempt/agent/role/task semantics and action;
3. provider identity;
4. configured and actual model identity;
5. source and model configuration identity;
6. residual capsule and execution lineage.

`materialize()` round-trips the already captured observation, verifies exact
manifest membership and pending compatibility, and returns a clone. It cannot
stamp or rewrite task, context, provider, model, configuration, acceptance, or
successor truth. A fully self-consistent caller rebound from the same raw bytes
receives a new observation identity and fails manifest authorization.

Structured future/control labels are rejected before manifest membership.
Expected status, rejection, move ID, successor, SearchState, reward, and case
labels exist only in evaluator-side reference data.

## Frozen authoritative cases

Exactly five real offline captures are frozen:

1. `opening-scripted-mock` — accepted canonical Socratic question;
2. `opening-empty-question` — Socratic content rejection;
3. `opening-injection-question` — answer-injection rejection;
4. `opening-invalid-json` — parser rejection;
5. `opening-schema-error` — schema rejection.

The frozen reference status, not a fixture label, determines the aggregate
accepted/rejected groups: one accepted case and four canonical rejections.

Exactly fourteen no-successor probes are predeclared:

```text
invalid-root
illegal-action
unsupported-action-family
budget-exhausted
missing-observation
invalid-observation
tampered-observation-identity
caller-rebinding
future-label-forbidden
wrong-root-context
wrong-task
wrong-provider
wrong-model
wrong-configuration
```

Canonical processor exceptions and refused transport remain focused
environment tests under `CANONICAL_PROCESSING_REJECTED`; they are not silently
promoted into the frozen 14-case aggregate matrix.

## CED authority

The sole supported family remains:

```text
ASK_SOCRATIC_QUESTION
OPENING / SOCRATES / SOCRATIC_QUESTION
round=0 / slot=0 / attempt=0
```

CED owns task construction, parsing, Socratic content and injection checks,
acceptance/rejection classification, deterministic move ID, TaskLog mutation,
dispatch and commitment ledgers, quorum, and round finalization. Production and
replay both call the same CED-owned `_apply_registry_response` and
`_finalize_registry_phase` seam. The successor layer performs a one-to-one
projection of the explicit CED application outcome; it does not infer
acceptance from provider status or move presence.

## Frozen parity fields

The evaluator compares all thirteen predeclared projections:

```text
aporia
budget
commitments
normalized_semantics
phase_dispatch
phase_role_cursor
provider_bindings
registry_retry
registry_rounds
search_state_v1
session_state
socratic_audit
task_log
```

This includes exact accepted public `move_id`, result/rejection category,
normalized canonical successor, SearchState-v1 payload and ID, task and
registry history, side ledgers, phase/role cursor, processor provenance,
receipt/result/branch lineage, and separated historical/replay resources.
Only timestamps, latency, and random provenance-only task IDs are excluded.

## Isolation and resource evidence

Source and production-control CED runtime fingerprints and adapter dispatch
counters are measured before and after every evaluator operation. A distinct,
internally valid but unmanifested sibling observation is applied to the same
pending transition and must fail with `INVALID_OBSERVATION_IDENTITY` without a
successor or mutation. Exact-observation replay separately proves idempotence.

Historical acquisition is frozen as one offline fixture dispatch per capture.
Replay charges one observation application and one successor evaluation, with
zero model, provider, tool, token, cost, or wall-time budget use. Historical
and replay usage are never merged.

The evaluator normalizes only root `created_at`/`updated_at` to a fixed audit
clock before capsule capture. Those timestamps were excluded before results
from capsule/source-execution identity, normalized CED semantics, SearchState,
task identity, and the parity relation. Exact before/after runtime hashes are
still stored and derived.

## Evaluator and replay discipline

The frozen evaluator has explicit `/v1` schemas for case results, evaluator
failures, unavailable probes/results, metrics, case set, thresholds, artifact,
and replay lock. Any supported-case precondition/evaluation exception is
recorded as evaluator-side failure evidence and makes the artifact
`FALSIFIED`; it cannot abort into a missing scientific result.

The first aggregate uses the frozen canonical case orders. Independent replay
uses both exact reverse orders. Artifact model equality, artifact-ID equality,
canonical byte identity, and full SHA-256 are required. Replay-lock publication
must receive both actual artifacts and perform the comparison internally.
Write-once publication permits identical idempotent bytes and refuses any
conflicting existing content.

## Pre-result verification

Before the final evaluator/docs freeze:

```text
Phase 8 recording/corpus/contracts/environment: 67 passed
evaluator contract/schema gate:                    8 passed
focused CED production parity:                   241 passed
frozen Phase 5/7 artifact integrity:              10 passed
aggregate executions:                              0
live/provider/model/tool calls:                     0
```

Frozen artifact hashes remain:

```text
Phase 5:
21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c

Phase 7 primary:
d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca

Phase 7 BestOfN:
86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637
```

## Locked next step

After focused tests, production regressions, historical hash checks,
documentation, and the final pre-result commit all pass, report
the complete required pre-aggregate checkpoint. Only then execute the first
authoritative aggregate once, publish the canonical artifact write-once, run
the independent reverse-order replay, and publish its replay lock.

No live providers, second transition, depth two, recursive search, Value or
Policy change, Experience Store, learning, RL, Hybrid authority, or production
authority is permitted.

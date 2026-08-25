# SocratesZero Phase 8 — Canonical Successor Environment v0

## Status

Pre-implementation architecture, corpus, identity, and parity contract frozen
on `feature/socrates-zero-canonical-successor-env-v0` before aggregate results.

## Approved hypothesis

Existing CED transition semantics can be exposed through a branch-isolated,
CED-owned action-plus-recorded-observation interface such that the same
canonical root, supported legal action, and recorded observation produce the
same canonical successor semantics as the existing CED path without copied
orchestration logic, invented observations, production mutation, or search
authority.

## Single supported family

```text
ActionKind.ASK_SOCRATIC_QUESTION
DialogPhase.OPENING
AgentRole.SOCRATES
TaskKind.SOCRATIC_QUESTION
round_number = 0
slot_index = 0
attempt_index = 0
```

Opening is the safest parity target because it is one complete canonical phase
with one scheduled task and one observation. It has no prior-dialogue
dependency, concurrent response ordering, commitment event, Reflection gate,
round advancement, Hybrid mutation, ratification, or release consequence. It
still exercises the generic structured parser, the CED Socratic content
contract, the answer-injection firewall, deterministic move identity, TaskLog,
dispatch audit, and round finalization.

No follow-up Socratic question and no other action family is included.

## Existing canonical path

1. `CEDOrchestrator.create_session` creates and binds the root.
2. `canonical_registry_task_specs` obtains the exact opening task identity.
3. `_run_registry_phase` advances the phase and calls `_apply_phase_roles`.
4. Its current nested task builder freezes CED context and output schema.
5. `_adapter_for_agent` and `CouncilProviderRegistry.run_adapter` acquire the
   external observation.
6. `BaseProviderAdapter.generate_agent_move` delegates raw parsing to
   `parse_and_validate_move`.
7. The current nested response absorber delegates Socratic acceptance to
   `_screen_socratic_move`, which calls `validate_socratic_content` and
   `check_answer_injection`.
8. Accepted moves receive `_deterministic_move_id`, are appended to
   `SessionState.moves`, and receive `_record_task_log` linkage. Rejected or
   failed observations receive a TaskLog row with no accepted move.
9. `_phase_dispatch`, `_harvest_commitments`, `finalize_round`, and
   `registry_rounds` complete the canonical phase transition.

## Behavior-preserving extraction

The task builder and response absorber are local closures, so a reusable CED
seam does not exist yet. Phase 8 will extract only those existing operations and
the phase finalization tail into CED-owned helpers. The production
`_run_registry_phase` and isolated replay path must call the same helpers.

The extraction may reorder no mutation, alter no task/context, change no retry
or quorum behavior, and introduce no new production call path. Calling the
whole phase runner from replay is forbidden because it would dispatch a
provider and erase the action/observation separation.

## Frozen semantic IDs

```text
ced-canonical-successor-env/v0
ced-canonical-branch-capsule/v0
ced-pending-canonical-transition/v0
ced-recorded-observation/v0
ced-canonical-transition-result/v0
ced-canonical-transition-receipt/v0
```

## Open-world contract

```text
canonical branch capsule + hard-legal action + budget
    -> pending canonical transition

pending canonical transition + recorded raw observation
    -> applied accepted | applied canonical rejection | successor unavailable
```

Observation acquisition remains external. A missing or incompatible observation
never produces a successor.

## Capsule contract

The capsule retains detached immutable serialization for only the state needed
by the supported opening transition:

- exact `SessionState`, including TaskLog and role/move/round state;
- canonical opening `CanonicalTaskSpec` and context/schema digests;
- commitment, aporia, Socratic-audit, phase-dispatch, retry, and cycle ledgers;
- provider seat and exact-model binding metadata;
- CED configuration relevant to opening legality and processing;
- SearchState-v1 root identity, projection ID, budget, and usage;
- exact structural and normalized semantic source fingerprints.

Mutable CED, registry, adapter, SessionState, list, or dict objects are not
stored in the frozen contract. Application rehydrates fresh branch-local
objects. `copy.deepcopy(CEDOrchestrator)` is not an isolation proof and is not
used.

## Pending transition contract

Preparation revalidates capsule integrity, the canonical task spec, the full
hard-legal set, the selected action, the single supported family, provider/model
binding, and budget reserve. It freezes a normalized task-semantic digest and a
deterministic replay task ID. It performs no observation application and charges
no provider/model/tool usage.

## Recorded observation contract

The recorded observation stores raw text, transport status, normalized task
identity, source task ID as audit provenance, provider ID, exact actual model
ID, model-configuration identity, raw digest, historical usage, and provenance.

It stores no parsed move, expected acceptance, resulting move ID, successor,
future state, later TaskLog, final release, reward, or benchmark label. Reserved
future/control fields in a structured raw envelope fail closed. Ordinary prose
is not searched for reserved words. Raw text is parsed fresh through the
canonical parser for every branch.

## Identity policy

- `source_execution_id` includes the canonical session ID because canonical
  move identity depends on it, plus state/config/task/provider-model semantics.
- `capsule_id` binds the source execution and frozen contract IDs.
- `pending_id` binds capsule, action, normalized task, and budget.
- `observation_id` binds normalized task, raw digest, provider/model/config,
  status, historical usage, and provenance digest.
- `branch_id` binds capsule, action, and observation.
- `receipt_id` hashes the predeclared semantic receipt payload.

Timestamps, latency, memory addresses, random production task IDs, and
process-local ordering are excluded. These are already non-semantic in the
frozen SearchState boundary. Exact replays intentionally share semantic IDs.

## Move identity

Canonical `move_id` is reproduced byte-for-byte by
`CEDOrchestrator._deterministic_move_id` from session, phase, round, agent, role,
task kind, slot, and attempt. Branch entropy is forbidden. Multiple isolated
branches may contain the same canonical move ID because they are never merged
into production; branch and receipt IDs distinguish their observation lineage.

## Result taxonomy

```text
APPLIED_ACCEPTED
APPLIED_CANONICAL_REJECTION
SUCCESSOR_UNAVAILABLE
```

Provider/schema/firewall rejection that canonical CED records is an applied
canonical rejection. It may contain a branch-local canonical post-transition
state and receipt but no accepted move. Invalid root, illegal action,
unsupported family, missing/mismatched observation, invalid observation
identity, forbidden future label, or exhausted budget is unavailable and must
not create a successor.

Frozen failure reasons:

```text
INVALID_ROOT
ILLEGAL_ACTION
UNSUPPORTED_ACTION_FAMILY
MISSING_OBSERVATION
OBSERVATION_TASK_MISMATCH
OBSERVATION_PROVIDER_MISMATCH
INVALID_OBSERVATION_IDENTITY
FUTURE_LABEL_FORBIDDEN
BUDGET_EXHAUSTED
CANONICAL_PROCESSING_REJECTED
```

## Resource policy

Recorded historical usage and new replay execution usage remain separate.
Historical unknown values remain unknown and are never replaced with zero.
For the offline fixture corpus, external model/tool/token/cost usage is truly
zero. A replay charges one observation application/successor evaluation under
the transition budget and zero provider/model/tool calls. Rejections retain
the complete recorded/new usage sections.

## Frozen semantic parity relation

Every authoritative supported case compares these fields before any aggregate
result is observed:

- result category and canonical rejection reason;
- phase, round, role history, and current assigned roles;
- accepted move semantic content, confidence, marker, exact `move_id`, task
  kind, slot, attempt, and provider;
- TaskLog semantic rows, retaining context hash/provider/status and excluding
  only random task ID and creation timestamp;
- registry-round OK/failed/proceed semantics;
- Socratic audit, phase dispatch, retry, commitment, and aporia ledgers;
- relevant Hybrid state/absence and terminal/governing fields;
- provider/model binding identity;
- budget before, replay delta, and after;
- exact post-transition SearchState-v1 payload and state ID;
- source/successor fingerprints and deterministic receipt identity.

The post-transition projection uses the same consumed opening task spec. CED
does not persist a singular next-task cursor and INITIAL_RESPONSE has three
parallel specs. Phase 8 will not invent a next-task scheduler decision and will
not claim recursive readiness.

## Frozen corpus sources

Authoritative observations are captured from the unmodified offline CED path:

1. accepted opening from `ScriptedMockProvider`;
2. provider-OK/content-contract-rejected empty opening from the existing
   `EmptySocrates` fixture;
3. provider-OK/injection-rejected opening from the existing `Injecting` fixture;
4. parser-invalid and schema-invalid observations from existing deterministic
   provider fixtures.

Unsupported family, missing observation, mismatched task/provider, invalid
root/action/identity, future-label, and budget cases exercise fail-closed
unavailability. Expected canonical successors are always generated by the
reference CED path; they are never hand-authored.

## Isolation proof

Source, production, and two sibling snapshots are fingerprinted before and
after each application. Each apply rehydrates an independent SessionState,
registry, provider catalog, and every relevant CED side ledger. Running A may
not change B or source; running B may not change A or source. Registry failure
state and adapter telemetry are never shared.

## Frozen boundaries

SearchState/projection v0/v1, Value v0/v1, Policy, legal vocabulary, Greedy,
BestOfN, PUCT, Phase 5/7 artifacts, CED support/ratification/release semantics,
Hybrid semantics, provider production behavior, N=4, c_puct=1.0, and depth=1
remain frozen.

No live call, shadow collection, search selection, depth two, recursion,
Experience Store, learned component, RL, or production authority is permitted.

## Result record

Not run yet. The corpus, contracts, failure semantics, receipt schema, and parity
fields must be committed before the first aggregate parity artifact.


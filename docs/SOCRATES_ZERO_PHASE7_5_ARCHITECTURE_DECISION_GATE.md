# SocratesZero Phase 7.5 — Architecture Decision Gate

Status: **COMPLETE — analysis only**

Decision date: 2026-08-25

Branch reviewed: `feature/socrates-zero-heuristic-value-v1`

Sealed Phase 7 HEAD reviewed:
`b15146002214700983b4615bd0b82a8f8dc7165f`

## 1. Executive verdict

Phase 7 reduced the estimator uncertainty but exposed a more fundamental
execution uncertainty. The repository can enumerate immutable legal
macro-actions and can rank authored one-ply observations, but it cannot yet
apply one of those actions to an isolated CED state and obtain a canonical
successor. The only `SuccessorStateEvaluator` implementations are deterministic
fixtures. Real CED execution is phase-wide, mutating, provider-coupled
orchestration, and no branch capsule covers its state and side ledgers.

The required single decision is:

```text
CANONICAL SUCCESSOR ENVIRONMENT NEXT
```

This does **not** authorize depth two. The selected milestone is a smaller
one-transition CED foundation: expose existing CED transition truth as
`prepare_transition` plus `apply_observation`, prove offline parity and branch
isolation, and return `SUCCESSOR_UNAVAILABLE` for every action or observation
that cannot be handled canonically. Provider execution remains outside the
transition semantics, and SocratesZero must not copy CED scheduling, parsing,
firewall, commitment, or release rules.

The dependency relation is **Relationship 1**:

> A CED-owned canonical one-transition environment must exist before real
> counterfactual shadow collection is safe.

A narrow real shadow runner cannot currently reuse CED safely because there is
no action-to-task compiler, no complete canonical snapshot, no branch-local
state capsule, no observation-injection boundary, and no cost-bearing
transition failure record. Option A has the larger eventual external-validity
payoff; Option B comes first because it supplies the safety and parity
prerequisite that Option A otherwise would have to implement implicitly.

The current research baseline remains:

```text
SearchState v1
+ UniformPolicyPrior/v0
+ HeuristicValueEstimator/v1
+ BestOfNStrategy/v0
+ N = 4
+ depth = 1
```

Classification:

```text
YES — CURRENT EXPERIMENTAL CHAMPION
```

It is an offline experimental configuration, not a runtime executor and not a
production policy.

Current readiness summary:

| Question | Verdict |
|---|---|
| Successor seam | **EXPERIMENTAL / FIXTURE-ONLY** |
| CED transition ownership | **CANONICAL BUT NOT EXPOSED AS AN ISOLATED TRANSITION** |
| Depth two | **NOT READY** |
| Shadow isolation | **NOT READY** |
| Real counterfactual collection | **NOT READY** |
| Experience Store | **NOT READY** |
| Learned Value / Policy | **NOT YET EARNED** |
| RL | **NOT YET EARNED** |

## 2. Sealed Phase 7 evidence

Phase 7 evidence is treated as immutable input to this decision.

| Gate | Value v0 | Value v1 | Delta / guardrail |
|---|---:|---:|---:|
| Primary ordered holdout | `2/7 = 28.57%` | `7/7 = 100%` | `+71.43pp` |
| Primary nonterminal ordered subset | `2/7` | `7/7` | `+71.43pp` |
| Required ties | — | `20/20` | `100%` |
| Directional errors | — | `0` | pass |
| Positive components | — | `0` | pass |
| BestOfN selection, Uniform Policy, N=4, depth 1 | `2/7 = 28.57%` | `7/7 = 100%` | `+71.43pp` |
| BestOfN resource regression | — | `0` | pass |
| BestOfN guardrail regression | — | `0` | pass |

The sealed artifacts are:

| Evidence | SHA-256 |
|---|---|
| Phase 5 search-kernel artifact | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Phase 7 primary Value-v1 artifact | `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca` |
| Phase 7 secondary BestOfN artifact | `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637` |

The evidence supports canonical observability, deterministic Value quality, and
one-ply selection on frozen structural cases. It does not supply a real
counterfactual, an executable legal action, an isolated canonical successor, a
depth-two transition, a reward, or production evidence.

## 3. Current experimental successor seam audit

The audit covers the successor infrastructure from Phases 3C, 4, 5, and 7.
“Partial replay” means a stable search identity or deterministic fixture can be
reconstructed; it does not mean a CED provider transition can be replayed.

| Surface | Authority class | Fixture or real | Executes provider work | Produces canonical `SessionState` | Projects `SearchState v1` | Mutates CED | Branch isolation | Replay | Horizon | Resource accounting | Production authority |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `LegalAction` | Experimental proposal contract; CED Constitution veto remains | Contract | No | No | No | No | Immutable value only | Stable action identity | None | None | None |
| `CEDSearchConstitution` | Hard search legality, not CED execution | Real projection logic over experimental vocabulary | No | No | Consumes v0 base only | No | Pure over immutable state | Deterministic | Current state only | None | None |
| `FixedRotationBaselineAdapter` | Read-only CED task-spec view | Real CED scheduling extraction | No | No | No | No | Read-only | Deterministic task specs | Current phase | None | None |
| `FixedRotationBaselineStrategy` | Experimental selector | Real task-kind mapping, no execution | No | No | No | No | Immutable input | Search receipt | Root only | Root usage only | None |
| `ActionSuccessor` | Experimental observation envelope | Contract | No; an injected evaluator may | No; contains only `SearchState` | No native v1 envelope | No itself | Not guaranteed | Stable child state if supplied | Intended one ply | Successful branch delta only | None |
| `SuccessorStateEvaluator` | Injected experimental protocol | Contract only | Implementation-dependent, unauthorized by protocol | Not required | Not required | Not specified | Not specified | Not specified | No recursive capability | Aggregate input plus successful delta; failure usage absent | None |
| `BestOfNStrategy/v0` | Advisory search | Real strategy over injected successors | Calls evaluator; does not own provider execution | No | No native v1 path | Does not mutate root; evaluator unconstrained | Only immutable search input is tested | Canonical `SearchReceipt` for successful run | Exactly one ply | Strict successful node/expansion and aggregate checks | None |
| `PUCTStrategy/v0` | Advisory search | Real strategy over injected successors | Calls evaluator repeatedly; does not own provider execution | No | No native v1 path | Does not mutate root; evaluator unconstrained | Only immutable search input is tested | Rich PUCT receipt for successful run | Explicitly one real ply; children never recurse | Strict successful usage; exception invalidates whole search | None |
| Phase 5 `DeterministicEvaluationSuccessor` | Evaluation fixture | Fixture-only, root-only | No | No; authors `SearchState` from blueprints | No | No | Deterministic fixture isolation | Full artifact replay | One ply | Exact zero-call fixture counters | None |
| Phase 7 `_SuccessorEvaluator` and `_navigation_successor` | Evaluation fixture | Fixture-only | No | Source recipes construct CED/Hybrid fixtures, but no action executes them | Yes, before navigation metadata is attached | No | Deterministic fixture isolation | Full primary/secondary artifact replay | One ply | One node and one expansion; zero provider/tool calls | None |
| Phase 7 `_CanonicalValueV1Adapter` | Navigation-only test adapter | Fixture-only lookup | No | No | Looks up exact prebuilt v1 envelope by base state ID | No | Local immutable mapping | Deterministic | Leaf evaluation only | Value receipt only | None |

Key code evidence:

- `backend/dialogues/socrates_zero/contracts.py` defines `LegalAction`,
  `ActionSuccessor`, and the injected `SuccessorStateEvaluator` protocol.
- `backend/dialogues/socrates_zero/strategy.py` requires every BestOfN child to
  be exactly one ply deeper and validates only the returned search state and
  successful usage.
- `backend/dialogues/socrates_zero/puct.py` freezes
  `PUCT_MAX_SAFE_RELATIVE_DEPTH_V0 = 1` and explicitly never passes a child back
  to the evaluator.
- `backend/dialogues/socrates_zero/evaluation_harness.py` rejects any
  non-root input in `DeterministicEvaluationSuccessor`.
- `backend/dialogues/ced_search_value_v1_bestofn.py` constructs pre-authored
  canonical v1 fixtures, then adds navigation metadata. It does not execute the
  associated action.

### Seam verdict

The seam is honest and safe for deterministic one-ply experiments, but it is
not a transition implementation. It validates what an evaluator returns; it
does not prove how that successor was obtained. It cannot establish canonical
acceptance, source or sibling isolation, real provider identity, cost-bearing
failure, or recursive legality.

### Constitutional rejection

The following design is rejected:

> A SocratesZero evaluator translates macro-actions into prompts, parses model
> output, appends moves, advances rounds, and reconstructs commitments itself.

That would be a second CED. The only acceptable executor is a CED-owned shared
transition kernel used by both canonical execution and isolated research
execution.

## 4. CED transition ownership map

Actual transitions are distributed across `CEDOrchestrator`, the provider
registry/adapters, `SessionState`, Socratic ledgers, and the final Hybrid
release path. No single current function is an isolated one-action transition.

| Transition concern | Authority owner | Function / module | State mutated | Required inputs | External observation dependency | Replay behavior | Callable in isolation today |
|---|---|---|---|---|---|---|---|
| Task creation | CED | `CEDOrchestrator._run_registry_phase._build_task`; special builders for scoring, synthesis repair, verification, and ratification | No canonical state until dispatch; `AgentTask.task_id` is randomly generated | `SessionState`, canonical task spec, phase context, role, slot, attempt | No | Task semantics mostly deterministic; task ID and timestamps are not | Only private phase-specific builders; no public pending-transition contract |
| Role selection | CED | `assign_roles_for_phase`, `_registry_phase_assignment`, `_apply_phase_roles` | `SessionState.role_history` and `AgentState.assigned_role` | Session ID, phase, round, ordered logical agents | No | Assignment is deterministic; application has timestamps | Pure assignment yes; complete transition no |
| Legal action / task determination | CED for canonical task specs; SocratesZero for advisory macro legality | `canonical_registry_task_specs` and `CEDSearchConstitution.legal_actions` | None | Current state/task/phase/history | No | Deterministic | Read-only yes; CED does not consume a `LegalAction` |
| Provider binding and dispatch | CED + registry + adapter | `_bind_session_adapters`, `_adapter_for_agent`, `_run_registry_phase._one`, `CouncilProviderRegistry.run_adapter` | CED binding maps; adapter `last_request`/`last_envelope`/`last_receipt`; registry failure summary | Task, agent state, bound adapter, timeout | **Yes**, real provider response | No observation-injection replay path; mutable last-call fields only | No isolated branch boundary |
| Provider response parsing | Provider adapter + shared parser | `parse_and_validate_move` and adapter envelope extraction | Creates `ProviderResponse`/`AgentMove`; does not yet append to session | Raw provider text/envelope and exact `AgentTask` | **Yes** | Re-runnable with same task/raw text, but generated move timestamp and original random task ID remain | Partially; generic parse is callable |
| Firewall acceptance | CED | `_screen_socratic_move`, `validate_socratic_content`, `check_answer_injection`, `_run_registry_phase._absorb` | Socratic audit rows, aporia ledger, then accepted moves and task log | Parsed move, public IDs, original question, prior public moves | **Yes** | Deterministic given complete prefix, but audit/aporia mutation is not encapsulated | No pure apply-observation function |
| `move_id` creation | CED | `_deterministic_move_id` and `_absorb` | Rewrites parsed move ID; appends to `SessionState.moves` | Session, phase, round, logical agent, role, task kind, slot, attempt | Accepted parsed response | Deterministic for the same session lineage | Helper callable; branch namespace/collision policy absent |
| `TaskLog` mutation | CED | `_record_task_log` | Appends `TaskLogEntry` and timestamp | Exact task, move link or failure, provider/status | Provider outcome | Semantic fields reconstructable; task ID/time prevent byte identity | No branch-local log capsule |
| Commitment lineage | CED + Socratic record builders | `_harvest_commitments`, `commitments_from_move`, `commitment_events_from_reflection` | CED `_commitments[session_id]` | Accepted initial/reflection moves and authoritative model identity | **Yes** | Deterministic from accepted moves if all source identity is retained | Mutates orchestrator side ledger; not isolated |
| Question acceptance | CED | `_screen_socratic_move`, `_socratic_followups_for_round` | Moves, task log, Socratic audit, and possible aporia | Parsed Socratic response, current public IDs, current round | **Yes** | Prefix-dependent and fail-closed | No isolated transition |
| Reflection eligibility | CED | `_socratic_followups_for_round` and guards in `run_registry_session` | Controls whether reflection executes; no direct mutation in predicate | Accepted current-round Socratic move linked in task log | Indirectly provider-dependent | Deterministic given complete prefix | Predicate yes; orchestration decision embedded |
| Round advancement | CED | `run_registry_session` loop, `another_socratic_cycle`, `SessionState.advance_phase` | `round_number`, `phase`, `phase_history`, timestamps | Accepted current-round question, inquiry state, hard follow-up bound | Indirectly provider-dependent | Deterministic given accepted prefix | No scheduler cursor or one-step API |
| Reconstruction | CED | `_run_registry_phase(...RECONSTRUCTION)` and phase context builder | Phase/role history, provider results, moves, task log, dispatch/retry ledgers, commitments | Full public dialogue prefix, role plan, provider bindings | **Yes** | Whole phase can be rerun only by rerunning mutable orchestration | No |
| Synthesis | CED | `_run_registry_phase(...SYNTHESIS)`, `build_section_drafts`, scoring, tree option, `assemble_sections` | Moves, drafts, scorecards, harvest, tree audit, assembled answer | Full prefix, provider responses, scoring policy | **Yes** | Multiple provider-dependent stages; no observation bundle replay | No |
| Ratification | CED | `run_council_ratification`, `_parse_verdict`, deterministic aggregation | Task log and `SessionState.council_ratification`; later phase/final state | Assembled answer, all provider verdicts, quorum | **Yes** | Aggregation deterministic if all verdict observations retained | Separate mutating multi-call path, not a task-spec transition |
| Governing release | Hybrid authority invoked by CED | `project_governing_state`, `run_objection_verification`, `apply_deterministic_checks`, `freeze_release`, `_apply_governing_release` | A local mutable `HybridEpistemicState`, `FinalResponse` governing fields/audit | Finalized CED state, assembled claims, objections, verifier observations | Sometimes: objection verification calls peers | Final release digest is reproducible from full records; current mid-session core is not retained | Final-only and mutating; not an isolated successor primitive |

### Ownership verdict

CED owns transition truth, but that truth is currently embedded in phase-wide
control flow. `canonical_registry_task_specs` is the only read-only extraction
point and does not execute one task or consume one `LegalAction`. Targeted
`CHALLENGE_CLAIM` and `DEFEND_CLAIM` actions have no CED execution consumer.
Mapping them inside SocratesZero would duplicate semantics and is prohibited.

The final Hybrid core is also not a reusable mid-session environment. CED
constructs it locally near release, mutates it through verification/checks, and
does not retain it as part of an actionable decision snapshot.

## 5. Open-world action / observation model

Socrates is an open-world stochastic protocol, not a deterministic board game.
The required conceptual transition is:

```text
S_t + legal action A_t
    -> PendingCanonicalTransition

PendingCanonicalTransition + real or recorded observation O_t
    -> CanonicalTransitionResult(S_{t+1})
```

`O_t` may be a provider envelope, parser failure, timeout, refusal, tool result,
or explicitly unavailable observation. The environment may validate and apply
an observation; it may not predict one.

### Does current CED approximate the split?

Partially:

- `AgentTask` construction plus provider binding resembles preparation.
- `ProviderResponse` carries raw text, parsed move, status, latency, and retry
  count and resembles an observation envelope.
- `parse_and_validate_move` plus `_screen_socratic_move` and `_absorb` resemble
  observation application.

The approximation is insufficient because task construction, provider dispatch,
acceptance, and mutation are nested inside `_run_registry_phase`. There is no
immutable pending transition, no public observation-injection point, no
complete branch snapshot, no canonical result union, and no deterministic
transition receipt.

### Minimum Option B contract

Without prescribing implementation details, the next milestone should expose
a CED-owned conceptual API:

```python
prepare_transition(
    canonical_branch_snapshot,
    legal_action,
) -> PendingCanonicalTransition

apply_observation(
    pending_transition,
    real_or_recorded_observation,
) -> CanonicalTransitionResult
```

Preparation must:

- verify the root snapshot and `SearchState-v1` identities;
- recompute and validate the complete legal set;
- map only actions that CED itself canonically supports;
- freeze the canonical task/context/prompt/config/model-binding identities;
- reserve the maximum branch-local resource budget before external work;
- make no provider or tool call and mutate no source state.

Application must:

- invoke the same parser, firewall, move identity, task-log, commitment, role,
  round, and next-task semantics as canonical CED;
- accept an exact recorded or real observation envelope;
- return accepted, rejected, failed, or unavailable explicitly;
- produce a branch-local canonical successor and `SearchState v1` only after
  successful canonical application;
- include observation identity, exact provenance, resource usage including
  failed work, and a deterministic transition receipt.

If an observation is absent, an action has no CED mapping, or canonical
application cannot be isolated, the required result is:

```text
SUCCESSOR_UNAVAILABLE
```

The environment may never invent provider output, evidence, verification,
acceptance, role changes, or task-log entries.

## 6. Depth-2 blocker map

The requested trace is audited below.

| Step | Exists today? | Canonical? | Isolatable? | Replayable? | Provider-dependent? | Budget-accounted? | Mutates production state? | Missing primitive |
|---|---|---|---|---|---|---|---|---|
| Canonical `S0` prefix | Partial | `SessionState` is canonical; complete mid-session Hybrid snapshot is not retained | No complete capsule | Search projection only | No | Search budget only | Reading does not | Immutable full CED branch snapshot and task cursor |
| `legal_actions(S0)` | Yes | Canonical search legality, but not executable CED alternatives | Yes over immutable projection | Yes | No | No work charged | No | CED action-to-task consumption |
| Select `A0` | Yes | Advisory only | Yes | Yes | No | Strategy counters only | No | None for selection; execution missing |
| Obtain real `O0` | Provider path exists | Provider response is real when live | No branch-safe call | No durable injection envelope | **Yes** | Calls/tokens/cost incomplete | Dispatch uses live CED/adapters | Exact observation receipt and pre-reserved budget |
| Apply `O0` | Embedded in phase runner | Yes on production path | No | Partial parser replay only | Uses `O0` | Failure usage missing | **Yes** | CED-owned apply-observation kernel |
| Canonical `S1` | Production phase state exists after mutation | Yes only on authoritative path | No sibling/source isolation | No complete import/export | Indirectly | Not unified | **Yes** | Branch-local transition result and full snapshot |
| `project_search_state_v1(S1)` | Function exists | Yes if exact Hybrid state is supplied | Pure once inputs exist | Yes | No | No | No | Persisted/reconstructed canonical mid-session Hybrid snapshot |
| `legal_actions(S1)` | Interface exists | Unproven for real branch successor | Search-state call yes | Yes if `S1` honest | No | No | No | Canonical next-task/task-cursor semantics |
| Select `A1` | Strategy mechanisms exist | Advisory | Yes | Yes | No | Strategy counters | No | Recursive strategy capability remains locked |
| Obtain `O1` | Generic provider path exists | Not branch-safe | No | No | **Yes** | Incomplete | Would mutate shared CED/adapters | Descendant provider isolation and aggregate budget lineage |
| Apply `O1` to produce `S2` | No isolated primitive | No | No | No | **Yes** | No | Would mutate production/shared state | All preceding transition and isolation primitives |

Verdict:

```text
DEPTH 2 NOT READY
```

Exact blockers are:

1. no complete immutable CED branch snapshot;
2. no CED-owned `LegalAction` compiler/executor;
3. no pending-transition and observation-injection boundary;
4. no source/sibling nonmutation guarantee;
5. no canonical next-task cursor after one accepted move;
6. no durable mid-session Hybrid state for v1 projection;
7. no branch/sample identity for repeated stochastic observations;
8. no complete provider/tool/token/cost accounting, especially on failure;
9. no recursive successor capability or descendant budget semantics;
10. no proof that action plus observation matches the existing CED path.

Option B success would resolve only the one-transition prerequisites. Depth two
remains locked behind a later parity and recursive-safety gate.

## 7. Shadow collection architecture requirements

The smallest legitimate Option A experiment, after Option B succeeds, is a
bounded one-ply read-only episode from one exact canonical prefix:

1. freeze the root `SessionState`, `TaskLog`, commitment/aporia lineage,
   public context, provider bindings, active task cursor, legal set, and
   `SearchState v1`;
2. let the unchanged production baseline continue independently;
3. choose at most a small predeclared number of alternative legal actions;
4. prepare each action through the CED-owned isolated transition boundary;
5. execute one exact-model provider call per reserved sample outside the
   transition kernel;
6. apply the real observation through canonical parsing/firewall semantics;
7. project the branch-local successor to `SearchState v1`;
8. evaluate it with unchanged Value v1 and publish an immutable episode
   receipt;
9. prove production state, output, provider schedule, stores, and observer
   effects are byte/semantically unchanged.

This would be data collection and external-validity testing, not dynamic
production orchestration. A shadow-selected action must never affect the
authoritative dialogue.

### Required root equality

Every baseline and alternative sample must bind to the same:

- canonical root state ID and semantic fingerprint;
- complete public context and evidence available at branch time;
- legal-action set and active task constraints;
- model/provider configuration and prompt-version identity;
- CED parser/firewall version and resource limits;
- no-later-than-root information boundary.

Current CED cannot freeze this root completely. `SessionState` does not include
the CED side ledgers, provider-binding objects, retry/dispatch state, or a
retained mid-session Hybrid core.

### Which stack should propose candidates?

The best justified research stack is the current champion:

```text
SearchState v1
+ UniformPolicyPrior/v0
+ HeuristicValueEstimator/v1
+ BestOfNStrategy/v0
+ N = 4
+ depth = 1
```

Compatibility is conceptual, not runtime-complete. BestOfN consumes v0
`SearchState` children; Phase 7 used a test-only exact v1-envelope lookup
adapter. A future shadow runner must preserve the v1 envelope natively without
changing frozen BestOfN semantics or allowing a base-state ID to resolve to the
wrong canonical envelope.

## 8. Branch-isolation audit

`copy.deepcopy(CED)` is not proof of isolation. CED contains live client-facing
adapters, external stores, mutable registries, and state keyed by session ID.
Identity changes can alter role rotation and move IDs; identity reuse can cause
cross-branch collisions.

| State family | Current location / behavior | Isolation status | Exact gap |
|---|---|---|---|
| `SessionState` | Mutable Pydantic object stored by reference in `_sessions` | **PARTIAL** | Deep-copying this object omits orchestrator side ledgers and external objects |
| `TaskLog` | Mutable list inside `SessionState`; random task IDs and timestamps | **NOT READY** | No branch-local import/export, deterministic replay, or collision policy |
| Commitments | `_commitments[session_id]` outside `SessionState` | **NOT READY** | Not part of any snapshot; action application mutates shared ledger |
| Aporia/question lineage | `_aporia` and Socratic audit/cycle maps outside state | **NOT READY** | No branch-local capsule and prefix-freeze contract |
| Role history | Inside `SessionState`, but application mutates agent states and timestamps | **PARTIAL** | Snapshotable fields exist, but complete role/task cursor is absent |
| Provider request/response IDs | Random task IDs; OpenRouter response ID exists only in mutable `last_receipt` | **NOT READY** | No durable branch/sample namespace or cross-provider observation receipt |
| Move IDs | Deterministic from production session/phase/round/slot/attempt | **PARTIAL** | Same-session alternatives can collide; changing session ID changes canonical semantics |
| Provider bindings/orders | Adapter object references in CED maps keyed by session | **NOT READY** | No immutable binding identity snapshot; adapters hold mutable last-call state |
| Legacy epistemic graph | Separate legacy diagnostic system | **NOT APPLICABLE** | It is not the governing transition substrate and must not be promoted |
| Hybrid state | Mutable container created locally near governing release | **NOT READY** | No retained canonical mid-session state or branch clone contract |
| Ratification state | `SessionState.council_ratification` plus multi-provider calls | **NOT READY** | Separate phase path, no isolated observation bundle application |
| Governing release state | Local Hybrid core then fields on final response | **NOT READY** | Final-only; no reusable branch successor snapshot |
| Retries/dispatch | CED `_phase_retries`/`_phase_dispatch` and adapter mutable state | **NOT READY** | Not snapshotable; retry can change seat/sample and spend |
| Search budgets | Immutable and well tested for fixture success | **PARTIAL** | No unified provider/tool/token/cost/time lineage or cost-bearing failure result |
| Observer events | Hybrid shadow capture is post-final and failure-isolated | **PARTIAL OBSERVATION ONLY** | No decision-time event stream; moving it earlier would violate its authority contract |
| Learning/telemetry stores | Optional external objects ingested after or during sessions | **NOT READY** | Must be disabled or branch-local; deep copy cannot prove external nonmutation |

Shadow isolation verdict:

```text
SHADOW ISOLATION NOT READY
```

### Existing snapshot and replay primitives

| Primitive | Reusable value | Why it is insufficient alone |
|---|---|---|
| Immutable `SearchState` / `SearchStateV1` and pure projectors | Stable semantic identity and fail-closed projection | Projection is not a snapshot of mutable CED execution state |
| `HybridEpistemicLedger` | Detached immutable payloads, idempotency, hash chain, `from_records` replay | Post-final observational ledger; digest-oriented and non-executing |
| `HybridShadowObserver` | Proven final-output non-authority and failure isolation | Runs only after canonical finalization; cannot execute an alternative |
| Offline provider adapter and canned transports | Real-shaped request/envelope/parser seam with deterministic fixtures | Mutable last-call fields; no action-linked CED transition or branch state |
| `AtomicReceiptStore` | Strong immutable, conflict-safe, atomic publication pattern | Domain-neutral persistence only; no transition schema or canonical semantics |
| Phase 5/7 artifact builders | Strict identity, semantic replay, byte replay, overwrite refusal | Benchmark artifacts, not provider observation or CED state replay |
| `backend/evaluation/record_replay.py` | Simple offline answer replay | Answer-level cache silently overwrites and lacks branch/state/action lineage |
| `backend/orchestrator/epistemic_replay.py` | Deterministic export pattern for the separate legacy graph | Audit export only; cannot resume canonical CED or inject a provider observation |
| OpenClaw shadow apprentice | Baseline-first, final-unchanged and blind-comparison test patterns | Full synthesis side experiment, not a legal action or canonical successor |

The repository has useful donors, but no existing smaller primitive already
solves branch execution.

## 9. Provider nondeterminism audit

The classification applies to the current repository, not to a hypothetical
future provider contract.

| Control | Status | Evidence / implication |
|---|---|---|
| Exact model pinning | **PARTIAL** | OpenRouter rejects a returned model mismatch and exposes fail-closed actual identity. Anthropic/NVIDIA configure a model but do not currently expose a verified returned-model identity through `authoritative_model_id()`. |
| Silent model fallback | **PARTIAL** | OpenRouter exact mismatch fails closed. Other live adapters do not prove the serving model; CED phase rescue may deliberately reroute to another bound seat and records the route. |
| Temperature | **PARTIAL** | OpenRouter and NVIDIA use `0`. Anthropic adaptive-thinking requests omit temperature by provider contract. |
| Seed | **UNCONTROLLED** | No live adapter sends or records a deterministic sampling seed. |
| OpenRouter provider routing | **PARTIAL** | Exact model ID is checked, but no underlying provider route is pinned in the request. |
| Provider retries | **PARTIAL** | Anthropic/NVIDIA use bounded fixed-delay retries for transient status; OpenRouter has no equivalent internal retry; CED phase rescue can reroute. A retry is another stochastic observation. |
| Timeout | **PARTIAL** | Registry and adapters impose bounded wall time, but timed-out provider-side work may still incur unrecorded tokens/cost. |
| Rate limits | **PARTIAL** | Failures are classified and not fabricated; availability itself is external and retry samples can differ. |
| Provider-side nondeterminism | **UNCONTROLLED** | Temperature zero does not make hosted inference, routing, kernels, or model revisions deterministic. |
| Tool availability | **CONTROLLED** | Current requests define no tool surface. Future tools require a separate observation/receipt contract. |
| Message ordering | **CONTROLLED** within a request | System/user ordering and canonical JSON serialization are stable. Experiment-level baseline/alternative call order is not randomized or blocked today. |
| System prompt stability | **PARTIAL** | Prompt generation is code/task/model dependent and deterministic, but no durable prompt-version/digest receipt binds a real call. OpenRouter serializes the full AgentTask, including random task_id, so paired requests are not action-only until request identity is frozen or normalized canonically. |
| Max tokens | **PARTIAL** | Anthropic/NVIDIA bind limits; current OpenRouter body omits an explicit max-token limit. |
| Raw response retention | **PARTIAL** | `ProviderResponse.raw_text` exists in memory. Existing post-final shadow retains digests rather than a replayable branch observation. |
| Token and cost receipt | **PARTIAL** | OpenRouter stores response usage in mutable `last_receipt`; `ProviderResponse` has no common tokens/cost/model/response receipt and failure spend is absent. |

Provider nondeterminism verdict:

> It can be bounded and measured, not eliminated. A future real experiment must
> treat each call as one sampled observation and must never attribute every
> output difference to the chosen action.

Required later design:

- paired calls from an identical frozen root;
- multiple independent observations per action;
- blocked or randomized baseline/alternative call order;
- exact actual-model verification and prompt/config digests;
- separate sample IDs and no cross-sample adapter state;
- pre-reserved per-sample and episode budgets;
- explicit provider revision/time window;
- missing/failure outcomes retained in denominators.

## 10. Counterfactual fairness

| Fairness invariant | Current readiness | Required control |
|---|---|---|
| Same root state | **NOT READY** | Immutable complete branch snapshot and semantic fingerprint |
| Same public context | **PARTIAL** | Freeze exact canonical task context before any branch call |
| Same available evidence | **PARTIAL** | Bind all source records and forbid later production information |
| Same model configuration | **PARTIAL** | Exact actual-model, prompt, parameters, route policy, and token limit receipt |
| Same task constraints | **NOT READY** | CED-owned action-to-task mapping; targeted actions cannot be improvised |
| Same external information at branch time | **PARTIAL / inherently open-world** | Tight time blocks, randomized order, recorded observation time/route, repeated samples |
| Only action intentionally differs | **NOT READY** | Same pending-transition template with action-specific canonical delta only |

One provider output per action is insufficient for causal attribution. Later
analysis must separate:

```text
observed difference
= possible action effect
+ model sampling noise
+ route/provider drift
+ time-varying external information
+ parser/firewall interaction
```

The experiment may estimate a conditional action effect only through repeated,
paired, blocked observations. It may not claim that every difference was caused
by the macro-action.

## 11. Minimum shadow episode schema

A future Option A episode must contain no hidden chain-of-thought and must
minimally bind:

```text
episode_id
schema_version
authority = shadow_non_authoritative

root canonical snapshot ID and digest
root SessionState semantic ID
root TaskLog / commitment / aporia lineage IDs
root public-context digest
root SearchState-v1 ID and projection ID

complete legal action IDs
baseline action ID
shadow candidate action ID
candidate strategy ID
Policy ID
Value ID
BestOfN N / depth / budget configuration

exact provider ID
exact actual model ID
provider route policy
prompt/config digest
canonical pending-transition ID
exact task/request/sample ID
actual provider response observation or immutable reference

generic parser outcome
firewall/content-contract acceptance outcome
accepted branch-local move ID, if any
canonical transition status
successor canonical snapshot ID, if any
successor SearchState-v1 ID, if any
Value-v1 receipt, if evaluable

per-attempt and aggregate model/tool/token/cost/time usage
retry/reroute history
failure or SUCCESSOR_UNAVAILABLE status
source and sibling nonmutation fingerprints
transition receipt
branch receipt
```

Raw validated content may be required for replay, but storing it creates a
separate privacy, retention, access-control, and deletion-policy obligation.
Digest-only retention is safer but cannot reproduce parsing and acceptance.
That trade-off must be resolved before live collection.

## 12. Experience-store and outcome-linking readiness

The eventual tuple is:

```text
(
  state,
  legal_actions,
  action,
  observation,
  successor_state,
  policy_prior,
  value_estimate,
  resource_usage,
  provenance
)
```

| Component | Status | Reason |
|---|---|---|
| `state` | **PARTIAL** | Immutable search projection exists; complete canonical CED/Hybrid branch snapshot does not |
| `legal_actions` | **PARTIAL** | Stable tested legality exists, but several alternatives have no CED execution semantics |
| `action` | **READY** as a proposal | Immutable typed action identity and target validation are strong |
| `observation` | **NOT READY** | No common durable provider/tool observation envelope or injection seam |
| `successor_state` | **NOT READY** | Only fixture successors; no canonical isolated result |
| `policy_prior` | **READY** for current controls | Uniform prior is deterministic and auditable |
| `value_estimate` | **PARTIAL** | Value v1 and receipts are strong on canonical v1 inputs; real successors are absent |
| `resource_usage` | **NOT READY** | Common token/cost/tool/failure accounting is absent |
| `provenance` | **PARTIAL** | Move/task/Hybrid links exist, but branch, exact observation, actual-model, and failure lineage are incomplete |

Overall:

```text
EXPERIENCE STORE NOT READY
```

No Experience Store is authorized.

### Eventual outcome linking

| Candidate outcome | Can be canonical? | Safe interpretation | Reward status |
|---|---|---|---|
| Verification result | Yes, for its declared scope | One typed verification observation | Not a universal truth/reward |
| Claim `SupportState` | Yes | Governing support/readiness state | Not truth probability |
| Governing support | Yes | Release-readiness authority | Not factual correctness |
| Valid abstention | Not currently an upstream CED outcome; downstream search vocabulary only | Requires a separate canonical lifecycle | Not ready |
| Terminal block | Yes | Operational/governance failure or unresolved release | Negative endpoint, not scalar truth |
| Release status | Yes | Governance decision | Release does not equal correctness |

These endpoints may support predeclared evaluation questions. None alone is a
legitimate RL reward.

## 13. Learned Value readiness

Phase 7 shows that a transparent deterministic Value can use canonical
readiness distinctions. It does not show that a learned estimator is the next
bottleneck.

Still missing:

- a sufficiently large real canonical trajectory corpus;
- action-linked real successor fidelity;
- legal and non-leaking target semantics;
- train/development/holdout separation at root and episode level;
- repeated-sample noise measurement;
- a benchmark for generalization across questions, phases, providers, and
  model revisions;
- a decision on whether any later outcome is a prediction target rather than
  a governance label.

Verdict:

```text
LEARNED VALUE NOT YET EARNED
```

## 14. Learned Policy readiness

Potential targets remain ungrounded:

- successor Value ranking would distill the current heuristic, not establish
  long-horizon quality;
- search-selected actions inherit fixture/environment limitations;
- PUCT visits are depth-one, budget-sensitive, and were non-monotone in Phase 5;
- production baseline choices are imitation targets, not improvement targets;
- counterfactual pair preferences do not yet exist on real canonical branches;
- verification/support outcomes are scoped governance facts, not general
  action rewards.

Verdict:

```text
LEARNED POLICY NOT YET EARNED
```

## 15. RL readiness

| Prerequisite | Status after Phase 7 |
|---|---|
| Meaningful immutable state | **PARTIAL** |
| Trustworthy action legality | **PARTIAL** as executable action |
| Canonical environment transition | **NOT READY** |
| Real counterfactual trajectories | **NOT READY** |
| Branch isolation | **NOT READY** |
| Complete resource/failure accounting | **NOT READY** |
| Grounded reward | **NOT READY** |
| Stable real holdout protocol | **NOT READY** |
| Production-safe authority boundary | Defined in principle, unproven for branches |

If Option A later succeeds, real one-ply trajectories may exist, but the
canonical environment and reward remain partial. If Option B succeeds, one
canonical transition and isolation may exist, but real trajectory data and
reward still do not.

Verdict:

```text
RL NOT YET EARNED
```

## 16. Current experimental champion and deferred work

### Champion

```text
YES — CURRENT EXPERIMENTAL CHAMPION

SearchState v1
UniformPolicyPrior/v0
HeuristicValueEstimator/v1
BestOfNStrategy/v0
N = 4
depth = 1
```

Evidence:

- Phase 7 BestOfN improved from `2/7` with Value v0 to `7/7` with Value v1;
- Phase 7 recorded zero guardrail, resource, accounting, or new-failure
  regression;
- Phase 5's two paired controls found Heuristic Policy worse than Uniform;
- Phase 5 BestOfN-4 and PUCT-4 tied at `15/20` correctness, while BestOfN used
  `62` rather than `80` observations;
- Phase 7 required neither Heuristic Policy nor PUCT.

This classification is for the next controlled research comparison. It grants
no action-execution or production authority.

### PUCT priority reassessment

PUCT/depth work is not the highest-value next experiment. Current PUCT is
explicitly one-ply, did not improve Phase 5 correctness over BestOfN at budget
four, and is unable to consume a canonical recursive successor. Adding depth
before transition parity would create speculative states or a second CED.

### Premature-work assessment

| Work | Status | Repository evidence |
|---|---|---|
| PUCT tuning | **DEFER** | No correctness advantage over BestOfN-4; real successor fidelity absent |
| Depth-2 synthetic search | **NOT EARNED** | Would recurse over invented/fixture transitions |
| HeuristicPolicy tuning | **DEFER** | Phase 5 paired controls were harmful; Value v1 succeeded with Uniform |
| Learned Value | **NOT EARNED** | No real corpus or grounded target |
| Learned Policy | **NOT EARNED** | No reliable counterfactual preference/return target |
| RL/self-play/MuZero | **NOT EARNED** | Environment, trajectories, reward, and holdout are missing |
| Production dynamic SocratesZero | **NOT EARNED** | No real shadow evidence and no isolated canonical execution |

## 17. Option A — read-only real shadow counterfactual collection

### Strengths

- **Very high immediate information gain** on Phase 7 external validity.
- Directly measures whether Value v1 discriminates real model-generated
  successors.
- Can estimate provider-valid alternative rate, parser/firewall rejection rate,
  canonical readiness change, sample noise, and collection cost.
- Produces the kind of action-linked data eventually useful for Value and Policy
  research.
- Keeps production choice unchanged if isolation is genuinely proven.

### Scientific questions it could answer

- Does Value v1 vary usefully across real legal one-ply successors?
- Does BestOfN select structurally better canonical successors?
- How often do legal alternatives return provider-valid output?
- How often does canonical firewall acceptance reject a branch?
- How often do support/readiness states actually change?
- How noisy are repeated exact-model observations?
- What does one counterfactual episode cost?

### What it would not establish

- long-horizon optimality;
- truth probability or final factual correctness;
- a general RL reward;
- multi-ply planning advantage;
- production improvement;
- learned Value/Policy readiness without a larger governed corpus.

### Risks

| Risk | Rating | Current reason |
|---|---|---|
| Production contamination | **VERY HIGH** | No branch sandbox or source/sibling nonmutation proof |
| Provider/API cost | **HIGH** | Counterfactual and repeat calls multiply spend; cost meter incomplete |
| Provider nondeterminism | **HIGH** | No seed; serving/routing noise remains |
| Branch-isolation failure | **VERY HIGH** | CED state spans SessionState, side ledgers, adapters, and external stores |
| Privacy/data volume | **HIGH** | Replay may require raw validated provider content |
| Counterfactual comparability | **HIGH** risk | No complete root freeze or action-to-task parity |
| Implementation size | **VERY HIGH** today | Would have to build the missing transition foundation plus live collection |
| Scientific information gain | **VERY HIGH** | Direct test of the largest empirical uncertainty |

### Missing prerequisites

- CED-owned isolated one-transition contract;
- complete immutable root/side-ledger snapshot;
- canonical action-to-task mapping;
- observation injection and transition result union;
- exact actual-model/provider receipt;
- full successful and failed usage/cost accounting;
- branch/sample identity and immutable receipt store;
- privacy/retention policy;
- parity and nonmutation proof before any live call.

Option A verdict:

> Highest eventual evidence value, but **not ready to implement safely as the
> immediate next milestone**.

## 18. Option B — safe canonical successor-environment foundation

### Strengths

- Establishes one source of transition truth rather than a SocratesZero copy.
- Makes action and external observation explicit and independently auditable.
- Can be proven entirely offline with recorded/scripted observations.
- Directly tests canonical parity and branch isolation before provider spend.
- Supplies the shared prerequisite for honest real shadow collection.
- Creates a fail-closed `SUCCESSOR_UNAVAILABLE` result instead of fabricated
  successors.
- Eventually supports depth work, but does not conflate one-transition parity
  with recursive readiness.

### Risks

| Risk | Rating | Control |
|---|---|---|
| Second-CED risk | **VERY HIGH** | CED owns implementation; extract one shared kernel used by both paths |
| Semantic duplication | **VERY HIGH** | No copied phase/action maps, parser, firewall, commitments, or scheduler |
| State-copy correctness | **HIGH** | Explicit branch capsule plus source/sibling semantic fingerprints |
| Provider observation handling | **HIGH** | Provider call remains outside transition; exact injected envelope |
| Recursive budget semantics | **HIGH** | Out of scope; depth two stays locked |
| Transition replay complexity | **HIGH** | Deterministic pending/result receipts and same-observation parity |
| Implementation size | **HIGH** | Narrow one task/one transition, offline only, unsupported actions unavailable |
| Immediate external information gain | **LOW** | No real calls or real trajectories in this milestone |

### Missing prerequisites it must create

- CED-owned canonical branch snapshot/capsule;
- canonical task cursor and one-action preparation;
- observation-injection boundary;
- branch-local CED/Hybrid/TaskLog/commitment state;
- deterministic transition outcome/receipt;
- complete bounded failure accounting;
- production/source/sibling nonmutation tests.

### Success criteria

- same canonical root, same supported legal action, and same recorded
  observation produce the same semantic successor as the existing CED path;
- source and sibling states remain byte/semantically unchanged;
- no CED transition rule is copied into SocratesZero;
- provider work is cleanly separated from transition application;
- accepted/rejected/failed/unavailable outcomes are explicit;
- transition receipts replay deterministically;
- `SearchState v1` projects from the exact canonical successor;
- zero production behavior change and zero live calls.

### Failure / falsification criteria

The milestone fails if:

- action preparation or observation application duplicates CED control rules;
- complete identity-preserving isolation cannot be achieved;
- the same action/observation diverges from canonical CED;
- provider execution must be embedded in transition semantics;
- failed work cannot be accounted without inventing usage;
- an unsupported action yields a speculative successor rather than
  `SUCCESSOR_UNAVAILABLE`;
- depth support requires invented descendant state.

Option B verdict:

> Lower immediate empirical payoff, but the safest and necessary first
> engineering milestone.

## 19. Direct decision matrix

Ratings are ordinal only. Higher risk/cost/complexity is unfavorable; higher
information, utility, reproducibility, cleanliness, and reversibility is
favorable.

| Candidate | Immediate information gain | Tests Phase 7 external validity | Unlocks real counterfactuals | Unlocks depth 2 | Second-CED risk | Production contamination risk | Provider/API cost | Engineering complexity | Reproducibility | Scientific cleanliness | Future Value training utility | Future Policy training utility | Future RL utility | Reversibility | Dependency on missing primitives |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A. Read-only real shadow counterfactual collection** | **VERY HIGH** | **VERY HIGH** | **VERY HIGH** | **LOW** | **HIGH** | **VERY HIGH** | **HIGH** | **VERY HIGH** | **LOW** | **MEDIUM** | **VERY HIGH** | **HIGH** | **HIGH** | **MEDIUM** | **VERY HIGH** |
| **B. Canonical successor environment** | **HIGH** | **LOW** | **HIGH** | **VERY HIGH** | **VERY HIGH** | **MEDIUM** | **LOW** | **HIGH** | **HIGH** | **HIGH** | **MEDIUM** | **MEDIUM** | **HIGH** | **HIGH** | **HIGH** |

The matrix does not select B because it is more sophisticated. It selects B
because A's safety and canonicality depend on the transition primitive that B
is explicitly designed to prove.

## 20. Dependency ordering

The largest unresolved **empirical** uncertainty remains whether Value v1
generalizes to real model-generated successors. The repository nevertheless
supports:

```text
Relationship 1

Canonical successor environment
must exist first
before real shadow collection is safe.
```

Relationship 2 is rejected. A narrow shadow collector cannot merely call
`_run_registry_phase` on a copied CED:

- the phase runner executes all canonical slots, not one `LegalAction`;
- targeted legal alternatives are not consumed by CED;
- mutable state lives outside `SessionState`;
- adapters and external stores are shared;
- branch/session identity changes affect role and move semantics;
- real response replay and failed usage are incomplete.

Relationship 3 describes a true common prerequisite, but does not change the
A-vs-B decision. The common prerequisite is exactly the narrow CED-owned
one-transition foundation and therefore naturally belongs under Option B.

Recommended dependency chain:

```text
Phase 7.5 decision
  -> Option B one-transition parity and isolation foundation
  -> separate readiness gate
  -> bounded real one-ply shadow collection
  -> real external-validity evaluation
  -> only then reconsider depth, learning, or production
```

## 21. Minimum shared primitive

The minimum shared primitive is:

> A CED-owned, immutable, branch-isolated one-transition capsule with explicit
> action preparation, external-observation injection, complete outcome/resource
> receipt, and canonical successor projection.

Its conceptual components are:

1. **Canonical branch snapshot**
   - `SessionState` semantic snapshot;
   - active canonical task cursor;
   - TaskLog, commitments, aporia, role/round/phase lineage;
   - exact provider-binding identities, not mutable adapter objects;
   - any required canonical Hybrid state;
   - source fingerprint and v1 projection ID.
2. **Pending canonical transition**
   - root snapshot/state IDs;
   - complete legal set and selected action;
   - exact CED-owned task/context/prompt/config identity;
   - required observation type;
   - reserved branch budget;
   - no provider output and no state mutation.
3. **Observation envelope**
   - exact provider/model/request/sample identity;
   - raw or recorded provider envelope;
   - status, retry/route, usage and privacy classification;
   - immutable digest/receipt.
4. **Canonical transition result**
   - accepted successor, rejected, failed, or unavailable;
   - branch-local canonical state and `SearchState v1` if accepted;
   - task/move/commitment/Hybrid provenance;
   - exact successful or failed resource usage;
   - source and sibling nonmutation fingerprints;
   - deterministic receipt.

The primitive belongs to CED, not the runtime-inert `socrates_zero` package.
SocratesZero may request, observe, search, and evaluate through it. It may not
implement or override its transition rules.

## 22. Exactly one next milestone

### Decision

```text
CANONICAL SUCCESSOR ENVIRONMENT NEXT
```

### Next branch

```text
feature/socrates-zero-canonical-successor-env-v0
```

### Primary hypothesis

> Existing CED transition semantics can be exposed through an isolated
> action-plus-observation transition contract without duplicating orchestration
> logic, such that one supported legal action plus the same recorded observation
> yields the same canonical successor as the existing CED path while leaving
> source and sibling states unchanged.

### Minimum implementation

1. Freeze contracts and parity cases before implementation.
2. Define a CED-owned immutable canonical branch snapshot that includes every
   relevant per-session side ledger.
3. Expose `prepare_transition` for exactly one supported canonical task/action
   family at first; unsupported/targeted actions return
   `SUCCESSOR_UNAVAILABLE`.
4. Expose `apply_observation` using the same CED parser, firewall, move identity,
   task log, commitment, and scheduler semantics as the authoritative path.
5. Use deterministic offline/recorded provider observations only.
6. Return an explicit accepted/rejected/failed/unavailable result with complete
   branch-local usage and a deterministic transition receipt.
7. Project the accepted successor through unchanged `SearchState v1`.
8. Prove existing-path parity, source nonmutation, sibling isolation, replay,
   and default-disabled production parity.
9. Stop before live calls, BestOfN wiring, multiple alternatives, or depth two.

### Frozen components

- Phase 5 and Phase 7 artifacts, hashes, cases, metrics, and results;
- SearchState/projection v0 and v1 semantics;
- `HeuristicValueEstimator/v1` and Value v0;
- Uniform and Heuristic Policy v0;
- Greedy, BestOfN, and PUCT v0;
- legal action vocabulary and Constitution v0;
- CED/Hybrid support, verification, release, and veto authority;
- provider adapters' production behavior;
- all production scheduling and default execution behavior.

### Safety boundary

- CED is the only transition owner.
- Provider output is always an external observation.
- No observation means no successor.
- Every branch is non-authoritative and source/sibling isolated.
- Unsupported actions fail closed.
- No branch output can affect production action, response, release, telemetry,
  learning store, or later production context.
- No live/provider/model/network call occurs in the foundation milestone.

### Explicit non-goals

- no real shadow collection;
- no provider or tool call;
- no targeted action semantics beyond proven canonical parity;
- no BestOfN/PUCT runtime wiring;
- no depth two or recursive search;
- no Policy or Value change;
- no learned Value/Policy, Experience Store, RL, self-play, or MuZero;
- no production selection or release authority;
- no second CED and no copied orchestration rules.

### Success criterion

For every frozen parity case:

```text
same root
+ same supported legal action
+ same recorded observation
= same semantic canonical successor
```

under the existing CED path and isolated transition path, with:

- production/source and sibling fingerprints unchanged;
- deterministic transition receipt replay;
- exact accepted/rejected/failed usage;
- exact `SearchState-v1` successor projection;
- no fabricated state or output;
- zero production behavior change and zero live calls.

### Failure / falsification criterion

The hypothesis is falsified if parity requires copying CED rules, if identity-
preserving isolation cannot be proven, if observation injection diverges from
the existing path, if failure spend cannot be represented honestly, or if an
unavailable observation/action must be guessed to obtain a successor.

### What success unlocks

- a separate gate for bounded real one-ply counterfactual shadow collection;
- replay of exact recorded observations through canonical acceptance;
- trustworthy source/sibling isolation tests;
- complete one-transition episode receipts;
- later evaluation of Value v1 on real model-generated successors.

### What remains blocked

- depth two and recursive PUCT;
- real provider shadow calls until a separate safety/cost/privacy gate;
- long-horizon claims;
- Experience Store implementation;
- learned Value and learned Policy;
- reward definition and RL;
- production SocratesZero action authority.

## 23. Verification record

This phase changes documentation only. Completed focused verification:

| Gate | Result |
|---|---|
| Value-v1 tests | `77 passed` |
| Phase 6 canonical observability/projection-v1 tests | `17 passed` |
| Phase 5 evaluation-integrity tests | `37 passed` |
| Phase 5 artifact SHA-256 | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Phase 7 primary artifact SHA-256 | `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca` |
| Phase 7 BestOfN artifact SHA-256 | `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637` |
| Phase 5 artifact Git blob at sealed HEAD and Phase 7.5 start | `0488de8a555658a55312d8b1da8614ab9347743b` |
| `git diff --cached --check` | passed |
| Scope audit | six documentation paths only; no core/code path |
| Live provider/model/network calls | `0` |
| Protected pre-existing untracked files | unchanged |

The two protected files are `scripts/live_dialogue.py.bak` and the malformed
root filename beginning `ocratic_followup_mandate`.

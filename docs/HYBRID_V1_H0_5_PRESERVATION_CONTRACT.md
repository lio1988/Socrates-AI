# Socrates Epistemic Hybrid v1 — H0.5 Preservation Contract

Status: **normative design contract; no Hybrid runtime implementation**

Baseline family: canonical `backend/dialogues` CED

Ratification requirement: this contract must remain satisfied before and during every Hybrid stage.

## 1. Locked principle

Hybrid v1 is a thin epistemic control layer integrated into the existing
Socrates/CED architecture:

> Keep the current execution engine. Replace epistemic inference from
> consensus, scores, and prose with an append-only ledger, a derived claim
> graph, targeted verification, compatibility gating, and claim-level release
> checks.

Hybrid does not replace `CEDOrchestrator`. Absence from a Hybrid proposal is
never permission to remove, bypass, weaken, duplicate, or ignore a canonical
capability.

Every mature capability discovered in the repository must appear in the matrix
below in exactly one state:

- `UNCHANGED`
- `ADAPTED`
- `OPTIONAL`
- `DEFERRED`
- `RETIRED WITH EVIDENCE`

An unclassified mature capability fails this contract.

## 2. Canonical preservation matrix

The following is the authoritative feature inventory. `Current status`
describes repository reality; `Hybrid decision` is the only allowed migration
state. Existing test filenames are named where available. `Proposed` tests are
mandatory before the corresponding Hybrid behavior becomes authoritative.

| Feature | Current status | Authoritative implementation | Current runtime path | Hybrid decision | Why | Invariant to preserve | Regression test | Migration risk |
|---|---|---|---|---|---|---|---|---|
| CED sole protocol governor | Active | `backend/dialogues/ced.py` | All canonical sessions | UNCHANGED | Hybrid is not a replacement orchestrator | Only CED assigns roles, routes tasks, advances phases, aggregates protocol state and releases answers | `test_ced_audit_fixes.py`; proposed Hybrid authority test | Critical |
| Legacy `run_session` path | Active compatibility path | `CEDOrchestrator.run_session` | Local/FakeProvider sessions | UNCHANGED | Still supported and tested | Hybrid-disabled output remains compatible | `test_ratification.py` | Medium |
| Registry council path | Active canonical production-shaped path | `run_registry_session`, provider registry | Registry sessions | UNCHANGED | Main live/offline council path | Phase order, quorum and provider outcomes survive H1 | `test_phase8c_registry_session.py` | Critical |
| Logical agent to physical provider/model binding | Active in restored baseline | CED session adapter bindings | Registry deliberation and tree tasks | UNCHANGED | Required heterogeneous identity invariant | One logical agent stays on one physical seat except explicit retry | `test_canonical_execution_restoration.py` | Critical |
| Exact requested/returned model identity | Active for OpenRouter | `openrouter_provider.py` | Every OpenRouter response | UNCHANGED | Provider identity is a protocol fact | Returned-model mismatch fails closed; no substitution | `test_openrouter_provider.py` | Critical |
| Provider/vendor/model metadata | Active | Provider adapters, CED roster/task log | Task construction and audit | ADAPTED | Hybrid needs typed references to identity facts | Hybrid references adapter facts and never re-derives identity | existing provider tests; proposed provider-reference test | High |
| Deterministic role rotation | Active | `role_assignment.py`, CED phase assignment | Every canonical phase | UNCHANGED | Mature protocol behavior | Pure function of session, phase, round and sorted logical agents | `test_deterministic_roles.py`, `test_dynamic_roles.py` | Critical |
| `primary_role` versus temporary `assigned_role` | Active | `AgentState`, CED role application | Session/phase state | UNCHANGED | Persistent identity is distinct from temporary duty | Role rotation never mutates logical identity | `test_identity_and_full_dialogue.py` | Critical |
| `role_history` and `phase_history` | Active | `SessionState`, CED | Phase assignment/advance | UNCHANGED | Canonical audit and future projection source | Hybrid and observers project; they never recalculate or repair history | dynamic-role and phase tests | High |
| Session identity | Active/partial | `SessionState`; caller-supplied IDs | Session creation | ADAPTED | Supplied IDs are stable; defaults are random | Authoritative replay requires explicit canonical session identity | proposed protocol-identity test | High |
| Run and round identity | Partial; deterministic Live View contract is unmerged | CED round fields; Live View branch | Tasks and future projection | ADAPTED | Hybrid replay needs explicit run/round scope | Versioned run identity and explicit nonnegative round/attempt | proposed protocol-identity test | High |
| Ordinary task IDs | Active but random in current runtime | `AgentTask` default | Dispatch/task log | ADAPTED | Random IDs cannot anchor deterministic replay | Adopt reviewed full-digest deterministic task identity before authoritative replay | proposed task-identity test; Live View branch tests | Critical |
| Move IDs | Active deterministic 12-hex | CED `_deterministic_move_id` | Accepted moves | ADAPTED | Correct semantics but limited collision space | Versioned full digest independent of async completion order | current deterministic tests plus proposed full-ID test | High |
| Draft, answer and future candidate IDs | Partial | Draft from move; answer default random | Synthesis/assembly | ADAPTED | Hybrid requires immutable lineage | Candidate identity is deterministic over canonical sources; no random load-bearing identity | assembly tests; proposed candidate-lineage test | Critical |
| Provider routing analytics | Active optional | CED topic/seat ranking | Session binding | UNCHANGED | Mature operational optimization | Routing may use health/quality analytics, never claim truth | `test_seat_routing.py` | High |
| Bounded retry/failover | Active opt-in | CED Phase 20 | Failed phase slots | UNCHANGED | Mature phase rescue | Retry only failed slot, once, on next frozen seat with new attempt identity | `test_phase_retry.py` | High |
| Provider availability/quorum/timeouts | Active | `CouncilProviderRegistry` | Deliberation, scoring, ratification | UNCHANGED | Honest operational boundary | Bounded waits and explicit quorum | `test_registry_council.py` | Critical |
| Fail-closed provider status | Active | Registry/adapters | All provider calls | UNCHANGED | Locked invariant | Failure is recorded and cannot silently become content | provider and live-hardening tests | Critical |
| No silent fallback/no fabricated provider output | Active | Registry/CED absorption | Failed responses | UNCHANGED | Core honesty guarantee | Failed response creates no move | registry tests | Critical |
| Anthropic, NVIDIA, OpenRouter, offline, mock and local adapters | Active or configuration-gated | Provider modules | Registry construction | UNCHANGED | Mature provider-neutral surface | Hybrid remains provider-neutral | provider-specific suites | Medium |
| Opening | Active | CED/prompts | First phase | UNCHANGED | Canonical Socratic architecture | Original question and exact response contract survive | prompt/registry tests | High |
| Initial Response | Active | CED/prompts | After Opening | UNCHANGED | Independent candidate generation | Multiple candidates remain possible | registry-session tests | High |
| Elenchus | Active | CED/prompts | After Initial | ADAPTED | Phase survives; objection authority changes | Criticism is input and not automatically validated falsification | existing phase tests; proposed objection-lifecycle tests | Critical |
| Reflection | Active | CED/prompts | After Elenchus | ADAPTED | Phase survives; explicit criticism outcomes are added | Reflection may accept, partially accept, reject or leave unresolved | dialectic tests; proposed anti-conformity test | Critical |
| Reconstruction | Active | CED/prompts | After Reflection | ADAPTED | Phase survives with safe revision lineage | Revision creates a new claim; evidence does not auto-transfer | existing phase tests; proposed evidence-revalidation test | Critical |
| Synthesis phase | Active | CED/prompts | After Reconstruction | ADAPTED | Five-section synthesis remains canonical | Material assertions reference eligible claim IDs | assembly tests; proposed eligible-synthesis test | Critical |
| Phase transitions | Active | CED `advance_phase` | Both execution paths | UNCHANGED | Mature architecture | Existing phase order remains canonical | registry-session tests | Critical |
| Full public phase context and council roster | Active | CED context builders | Registry deliberation | UNCHANGED | Mature dialogue semantics | Original task, prompt-safe public transcript and roster remain available | `test_dialectic_context.py`, `test_minimal_awareness.py` | Critical |
| New targeted-verification context | Absent | Future Hybrid task contract | Future bounded verification tasks | ADAPTED | Needed at material epistemic transitions | Original task, candidate claim, evidence and provenance remain the anchor | proposed verification-context test | High |
| Adaptive dialectic | Active | CED Phase 14 | Elenchus/context mandates | UNCHANGED | Mature behavior | Deterministic trigger precedence and thresholds survive | `test_phase14_adaptive.py` | High |
| Devil's Advocate | Active | High-confidence adaptive trigger | Elenchus mandate | UNCHANGED | Prevents complacency | Trigger must not require a fabricated objection | adaptive tests | High |
| Uncertainty mode | Active | Low-confidence adaptive trigger | Elenchus mandate | UNCHANGED | Useful calibration behavior | Missing support stays visible | adaptive tests | Medium |
| Confidence-disagreement and diversity triggers | Active | CED adaptive logic | Elenchus mandate | UNCHANGED | Mature anti-collapse behavior | Existing thresholds and precedence survive | adaptive/autonomy tests | Medium |
| Fallback/end-state behavior | Active | CED | Quorum, assembly and ratification failures | ADAPTED | Preserve honest fallbacks and add graduated epistemic outcomes | No failed gate is presented as ratified certainty | registry/assembly tests; proposed outcome test | Critical |
| Conversation continuity | Active | `conversation.py` | `ConversationManager` | UNCHANGED | Mature multi-turn capability | Public brief continues; hidden scores/providers remain hidden | `test_chat_conversation.py` | High |
| Seven canonical roles | Active | Models/prompts | Deterministic role assignment | UNCHANGED | Mature Socratic specialization | Socrates, Critic, Empiricist, Reflector, Reconstructor, Synthesizer and Final Evaluator remain temporary roles | role/prompt suites | High |
| Core Agent Prompt v1.9 | Active | `agent.py`, `reasoning_prompts.py` | Canonical provider calls | UNCHANGED | Frozen H0 baseline | H1 makes no prompt change | `test_reasoning_prompts.py`, `test_agent_alignment.py` | Critical |
| TELOS | Active | Reasoning prompt builder | Canonical provider calls | UNCHANGED | Mature behavioral foundation | Delivered through canonical system prompt | prompt tests | Critical |
| Context Protocol | Active | Reasoning prompt builder | Canonical provider calls | UNCHANGED | Original-task anchoring already exists | No new context layer bypasses it | identity/full-dialogue tests | Critical |
| Role, phase and task directives | Active | `reasoning_prompts.py` | Per task | ADAPTED | New claim/verification tasks need bounded directives | Existing directives remain; exact output schema prevails | prompt tests plus proposed Hybrid prompt tests | High |
| Epistemic markers | Active | Models/prompts | Moves/audit | ADAPTED | Useful self-description, not evidence | Marker alone cannot promote ledger support | `test_phase18_markers.py`; proposed authority test | High |
| Structured response and JSON repair | Active | Prompts/registry parser | Provider responses | UNCHANGED | Mature hardening | Invalid schema is failure; repair never invents semantics | provider-adapter tests | High |
| Prompt Constitution v2 foundation | Implemented on unmerged branch, runtime-inert | Commit `fad2cf5` | No canonical call | DEFERRED | Selective-port only | No wholesale activation; structural principles require separate approval | branch tests/future selective-port tests | High |
| Historical reasoning kernels/orchestrator | Historical | `backend/reasoning`, `backend/orchestrator` | Legacy family only | RETIRED WITH EVIDENCE | Contradictory authority and harmful historical output | Preserve for replay/evaluation only | historical replay/evaluation tests | Medium |
| Micro-Socratic Kernel v1 | Implemented, runtime-inert | OpenClaw kernel package | Explicit service call only | OPTIONAL | Useful bounded self-check | One call; no recursion, tools, consultation, mutation or certification | `test_micro_socratic_*` | Medium |
| Five-section synthesis architecture | Active | Models/CED/prompts | Synthesis/assembly | ADAPTED | Must not disappear | Core Answer, Stress-Test, Blind Spots, Nuance and Final Verdict remain present | blind-assembly tests | Critical |
| Section draft identity | Active | Deterministic draft from move | Synthesis absorption | ADAPTED | Becomes source lineage | Deterministic source attribution survives | assembly tests; proposed lineage test | High |
| Blind section scoring and assembly | Active | CED | Post-synthesis | ADAPTED | Quality selection remains valuable | Epistemic eligibility filters first; blind quality ranking chooses within eligible material | assembly/scoring tests | Critical |
| Cohesion/coherence logic | Active optional/audit | CED Phases 24–25 | Assembly and ratifier guard | UNCHANGED | Mature quality control | Bounded cohesion; coherence is not truth | assembly-coherence/cohesion tests | High |
| Corroboration and penalty aggregation | Active audit | CED Phases 26–27 | Assembly audit/open questions | UNCHANGED | Valuable transparency | Counts and flags are signals, never verification | reliability/flag tests | High |
| Unresolved sections and assembly fallback | Active | CED | Missing score/draft paths | ADAPTED | Must remain honest after eligibility filtering | Fallback uses real content; unresolved remains explicit | blind-assembly tests | Critical |
| Candidate lineage/restoration | Partial | Draft and runner-up history | Assembly/repair | ADAPTED | Earlier strong candidates must remain recoverable | Every displacement/restoration is immutable and attributed | proposed restoration test | Critical |
| Frozen final candidate | Partial | Prose frozen per ratification call | Ratification | ADAPTED | Immutable candidate record is absent | Each repair creates a new candidate and requires new ratification | proposed candidate-freeze test | Critical |
| Shadow peer-scoring modes | Active | CED/models | All/synthesis/sampled/off | UNCHANGED | Useful quality instrumentation | H1 does not alter scoring behavior | shadow-scoring-mode tests | High |
| Move/section scoring and seven dimensions | Active | Models/CED | Peer-scoring tasks | UNCHANGED | Mature quality signals | Preserve dimensions, confidence, flags and validation | scoring-model/registry tests | High |
| No self-scoring | Active | CED producer exclusion | Both scoring paths | UNCHANGED | Hard invariant | Producer never scores its own output | `test_ced_peer_scoring_invariant.py` | Critical |
| Blind scoring | Active | Scoring task contexts | Peer scoring | UNCHANGED | Prevents prestige leakage | No author/model/leaderboard exposure | registry-scoring tests | Critical |
| Missing scores, score coverage and sync gate | Active | CED harvest/leaderboard | Scoring audit | UNCHANGED | No-fabrication invariant | Missing remains missing and coverage stays explicit | shadow/sync-gate tests | Critical |
| Leaderboard and scoring audit | Active | CED | Final audit | UNCHANGED | Operational and learning value | Never becomes truth authority | leaderboard/audit tests | High |
| Uniform/confidence weighting and deterministic tie-breaks | Active optional | CED | Assembly | UNCHANGED | Mature quality selection | Existing mode and ordering survive | confidence-weighting tests | High |
| Score-derived epistemic authority | Active and experimentally harmful | CED `_epistemic_hint` | FinalResponse status | RETIRED WITH EVIDENCE | A false answer received high scores and `well_supported` | Scores remain quality only | proposed score/support-separation test | Critical |
| Council-wide Ratification | Active | CED | Registry providers | ADAPTED | Preserve council review while adding claim scope | Existing quorum and independent calls survive | council-ratification tests | Critical |
| ACCEPT, ACCEPT_WITH_CAVEAT, BLOCKING_OBJECTION | Active | Models/prompts | Ratification | ADAPTED | Useful verdict vocabulary | Verdict is scoped to explicit claims/candidate | ratification plus proposed claim-level tests | Critical |
| Ratification quorum/failure behavior | Active | CED/registry | Ratification | UNCHANGED | Mature release gate | Missing/invalid verdict is never ACCEPT | council-ratification tests | Critical |
| Critical-block semantics | Active but structural-only | Verdict validation/aggregation | Ratification | ADAPTED | Structural completeness does not prove validity | Only a validated material objection becomes BLOCKING; unresolved checks may withhold without false validation | proposed objection-lifecycle tests | Critical |
| Target section, rationale and required fix | Active | Ratification verdict | Ratification audit | ADAPTED | Mature attribution | Blockers remain explicit and claim/section-addressable | council-ratification tests | High |
| Runner-up repair and repair rounds | Active optional | CED Phase 19 | Blocked sections | ADAPTED | Useful repair currently mutates assembled state | Replacement creates a new CandidateRecord and is re-ratified | ratification-repair tests | Critical |
| Final release semantics | Active | CED final builder | Ratified outcomes | ADAPTED | Becomes one combined Hybrid-aware release authority | No released answer unless frozen candidate/material claims pass | ratification plus proposed release tests | Critical |
| Legacy `epistemic_status` field | Active | FinalResponse | Final output | ADAPTED | Compatibility field may remain but cannot be a second authority | Pure projection from authoritative Hybrid state after activation | proposed no-duplicate-authority test | Critical |
| Historical claim/evidence/provenance/revision primitives | Historical | EpistemicGraph family | Legacy/replay only | ADAPTED | Valuable state concepts | New minimal append-only records with explicit lineage | proposed state-machine tests | Critical |
| Historical contradiction tracking | Historical/noisy | Graph contradiction engines | Legacy family | ADAPTED | Claimed versus validated contradiction is needed | Unvalidated contradiction has no penalty/truth effect | proposed contradiction test | Critical |
| Numeric CBE truth ranking | Historical and experimentally harmful | Historical synthesis/CBE | Legacy family | RETIRED WITH EVIDENCE | Live run ranked an objectively false claim first | Eligibility, verification and compatibility replace truth ranking | frozen historical failure fixture | Critical |
| Historical renderer | Historical and experimentally harmful | Historical synthesis engine | Legacy family | RETIRED WITH EVIDENCE | Combined mutually incompatible claims | Five-section eligible-candidate synthesis replaces authority | compatibility regression/frozen fixture | Critical |
| Automatic evidence inheritance on revision | Historical and harmful | Historical revision path | Legacy family | RETIRED WITH EVIDENCE | Corrected claim retained stale evidence for false predecessor | Explicit revalidate/transfer/reject/unresolved edge state | proposed revision test/frozen fixture | Critical |
| Model-declared falsification boolean | Historical and harmful | Historical Elenchus path | Legacy family | RETIRED WITH EVIDENCE | Naked model boolean was trusted | VerificationRecord lifecycle replaces authority | proposed objection-verification test | Critical |
| Dung grounded semantics | Implemented diagnostic | Argumentation/evaluation modules | Offline/read-only | OPTIONAL | Useful diagnostic, not truth | Labels never promote or demote claims | argumentation harness tests | Medium |
| Evidence audit/evidence-constrained report | Implemented read-only | Evaluation/reasoning modules | Offline reports | OPTIONAL | Useful gap reporting | Cannot govern ranking or release | evidence harness tests | Medium |
| Knowledge-emergence concepts | Historical | `knowledge_emergence.py` | Legacy only | OPTIONAL | Potential diagnostic vocabulary | No automatic truth promotion | historical/future adapter tests | Medium |
| Unsupported claims, uncertainty and open questions | Active/partial | Markers/living system | Prompts/audit/learning | ADAPTED | Hybrid makes them first-class | Missing verification stays unresolved | marker/open-question plus proposed state tests | High |
| Deliberation Tree | Active optional, disabled by default | `deliberation_tree.py`, CED | `tree_expansions > 0` | OPTIONAL | Valuable bounded search | CED-owned, deterministic UCB, real scores only | deliberation-tree tests | High |
| Tree candidate/evidence integration | Active optional | Tree and OpenClaw bridges | Revision/training paths | ADAPTED | Tree cannot become a second epistemic route | Every material tree claim uses the same ledger/provenance/eligibility path | tree distillation/evidence plus proposed adapter test | Critical |
| Lesson retrieval and injection | Active optional | CED/OpenClaw Memory | Deliberation context | UNCHANGED | Advisory context remains useful | Lesson is guidance, not factual evidence | lesson loader/retriever/context tests | High |
| Lesson provenance at Hybrid boundary | Partial | Injection audit | Context only | ADAPTED | Claim extraction must preserve lesson influence | Context reference is not EvidenceRecord | proposed lesson-not-evidence test | Critical |
| Council Lesson A/B harness | Active operator tool | OpenClaw Memory | Explicit matched experiment | OPTIONAL | Mature learning signal | Counterbalanced/comparable; no automatic promotion | lesson A/B integrity tests | Medium |
| Single-agent Lesson A/B attestation | Open draft/not shipped | PR #62 foundations | No canonical path | DEFERRED | Repository explicitly marks it unshipped | Do not activate or describe as shipped | branch tests when merged | Medium |
| Seat health, quarantine, topic routing and calibration | Active optional | Self-improvement modules | CED hooks | UNCHANGED | Operational learning | Health is content-blind; analytics cannot certify claims | self-improvement/seat-routing tests | High |
| Learning summaries, process lessons and open questions | Active optional | Self/living system | Post-session/future context | UNCHANGED | Mature learning behavior | Only eligible public outcomes; failures isolated | self-improvement/living-system tests | High |
| Training collectors, corpus and feedback pipelines | Active optional/operator | Training and Phase 26C–R modules | Explicit ingest/export/plan | OPTIONAL | Mature offline learning surface | No automatic training, deployment or authority mutation | learning/training suites | High |
| OpenClaw Identity, Soul, prompt and revision governance | Active governed subsystem | OpenClaw packages | Explicit governance flows | UNCHANGED | Existing lasting-change authority | Hybrid cannot duplicate approval, application, rollback or promotion authority | OpenClaw governance tests | Critical |
| Trace capture, shadow apprentice and evidence bridges | Active optional | OpenClaw packages | Explicit/injected hooks | OPTIONAL | Useful evidence/learning foundations | Trace/proof does not become answer truth by itself | trace/shadow/evidence tests | Medium |
| External Self-Consultation v1 | Implemented, runtime-inert | Consultation service | Explicit one-call service | OPTIONAL | Useful advisory adapter | Isolated, one bounded call, no tools/delegation/state mutation | consultation tests | High |
| Consultation identity, receipt and failure behavior | Implemented | Consultation schemas/policy/receipts | Consultation service | UNCHANGED | Mature boundary | Provider must match request; malformed/non-OK yields no accepted result | consultation policy/receipt tests | High |
| Consultation confidence/judge scores | Advisory only | Mode payload | Consultation result | ADAPTED | Cannot be independent truth authority | Advisory unless an explicit governed VerificationRecord is created | proposed consultation-authority test | Critical |
| Council Live View projection contracts | Mature unmerged branch | Projection package | No current HEAD call | DEFERRED | Must be integrated, not reinvented | Strict typed contracts and reviewed closed taxonomy | branch projection tests | Critical |
| Council Live View EventLedger | Mature unmerged branch | Projection ledger | Observer only | DEFERRED | Observation ledger is non-authoritative | Per-stream sequence, idempotency, immutability and conflict refusal | branch ledger tests | Critical |
| Council Live View observer/failure isolation | Mature unmerged branch | Projection observer/CED hooks | Disabled by default | DEFERRED | Hybrid must reuse this bridge | Observer cannot mutate SessionState or FinalResponse | branch golden observer tests | Critical |
| Session/run/role/phase/task/provider-failure/move events | Partly implemented on branch | Projection/CED emit sites | Unmerged observer path | DEFERRED | Preserve reviewed semantics | Canonical mutation precedes emission; no fabricated event | branch phase/execution-event tests | High |
| Ratification/assembly/provider-completed events | Contracted, not fully emitted | Live View contract matrix | Future slice | DEFERRED | Runtime lacks all stable IDs/receipts | Implement only after prerequisites | contract-matrix/future emission tests | High |
| Reveal and role-display contracts | Mature unmerged branch | Projection reveal/display | Projection only | DEFERRED | Preserve blindness and role authority | Display projects canonical history and never schedules/recalculates | branch reveal/role tests | High |
| Future SSE transport | Planned | Live View architecture | None | DEFERRED | Transport must remain downstream | Reads EventLedger and cannot mutate authority | proposed transport replay test | Medium |
| Old FastAPI/SSE as canonical transport | Historical old family | Old API/orchestrator | Not canonical CED | RETIRED WITH EVIDENCE | Intentionally historical and unreachable from canonical runtime | Retain legacy replay/demo only | legacy isolation tests | Low |
| Task log and audit summary | Active | Models/CED | Every canonical run | ADAPTED | Needs deterministic IDs and typed epistemic references | Hidden from agents and preserves all failures | task-log/audit plus proposed replay tests | High |
| OpenRouter in-memory `last_receipt` | Active but non-persistent | OpenRouter adapter | Call metadata | ADAPTED | Does not satisfy immutable provider-receipt ownership | Use shared receipt primitive before authoritative receipt use | OpenRouter plus proposed persistence test | Critical |
| Raw/validated digests | Implemented on unmerged Live View branch | Execution-event slice | Move-validation observer | DEFERRED | Useful integrity metadata | Only real raw and validated bytes are digested | branch execution-event tests | High |
| Shared `AtomicReceiptStore` | Active mature primitive | `openclaw_receipts.py` | Consultation/kernel/governance stores | UNCHANGED | Hybrid must reuse it | Immutable, atomic, conflict-safe, path-safe, strict reads | shared-receipt parity tests | Critical |
| Evaluation record/replay cache | Active operator tool | `backend/evaluation/record_replay.py` | Offline benchmark replay | OPTIONAL | Separate evaluation artifact | Replay miss remains explicit; replay makes no network call | evaluation replay tests | Medium |
| Final Candidate Tournament and reserved Hybrid synthesis mode | Reserved | Models/CED guard | Constructor rejects activation | DEFERRED | Not required for Hybrid v1 | CandidateRecord remains future entrant-compatible | reserved-mode test | Medium |

No mature feature discovered during H0.5 is unclassified.

## 3. Non-duplicate authority map

| Concern | Sole authority after Hybrid activation | Non-authoritative consumers/signals |
|---|---|---|
| Execution protocol, roles, routing, phases | CED | Live View projections, learning reports |
| Provider/model identity | Provider adapter metadata plus immutable provider receipt, governed by CED | Hybrid references, observer events |
| Claim/evidence/objection/revision state | `HybridEpistemicLedger` | Derived claim graph, Live View, learning |
| Epistemic support | Hybrid ledger transition rules over explicit records | Scores, consensus, markers, lessons, consultation |
| Quality scoring | Existing CED scoring system | Hybrid eligibility gate consumes scores only after eligibility |
| Ratification/release | CED-owned Hybrid-aware Council Ratification state machine | Ratifier prose, observer events |
| Lasting Memory/Identity/Soul/prompt change | OpenClaw governance | Learning proposals, scores, lessons, consultation, Hybrid records |
| Immutable receipt publication | `AtomicReceiptStore` domain wrappers | Hybrid and EventLedger use typed references |
| Observability ordering/replay | Council Live View EventLedger | SSE/read models; never answer authority |
| Learning/training | Existing operator-governed learning pipeline | No direct answer or persistent-change authority |
| Deliberation Tree | CED search policy only | Same Hybrid ledger/eligibility path for material claims |
| External Consultation | Advisory service | May become one input to an explicit governed verification task |
| Micro-Socratic Kernel | Advisory self-check service | Cannot certify claims or agents |

There must never be two independent authorities for claim state, support,
verification, ratification, final release, provider identity or role identity.

## 4. EventLedger and HybridEpistemicLedger

The selected design is **separate ledgers with an explicit one-way projection
boundary**:

```text
CED authoritative execution state
        +
HybridEpistemicLedger authoritative domain state
        |
        | one-way failure-isolated projection
        v
CedEventObserver
        v
Council Live View EventLedger
        v
read models / reveal policy / future SSE
```

- EventLedger records observations and owns per-stream sequence.
- HybridEpistemicLedger owns epistemic records and transitions.
- Event sequence is not epistemic truth or transition authority.
- New Hybrid observer events require a reviewed, versioned extension to the
  closed Live View taxonomy.
- Canonical mutation and Hybrid append precede projection.
- Observer failure remains on its bounded diagnostic side channel.
- Random `event_id` remains non-semantic uniqueness only; deterministic
  idempotency keys identify canonical observed facts.

## 5. Retired authority evidence

| Retired authority | Evidence | Replacement | Compatibility/rollback |
|---|---|---|---|
| Score-derived `well_supported` | Current-canonical Repeat 003 released a false answer after high scores and three ACCEPT votes | Ledger-derived support projection | Keep legacy field as audit/compatibility projection |
| Numeric CBE truth ranking | Historical live run ranked false A-C-D-B first | Eligibility, targeted verification and compatibility gates | Preserve historical CBE for replay/diagnostics |
| Historical renderer | Combined false conclusion with reasoning proving A-B-C-D | Compatible five-section candidate synthesis | Preserve historical renderer for forensic replay |
| Lexical/noisy contradiction penalties | 117 contradictions across 16 claims; correct claims accumulated 5–7 | Claimed/validated contradiction lifecycle | Raw legacy edges import as unvalidated |
| Automatic evidence inheritance | Corrected claim retained evidence for false predecessor | Explicit edge revalidation | Historical records remain inspectable |
| Model-declared falsification boolean | Naked model boolean was accepted as success | VerificationRecord lifecycle | Legacy boolean imports only as an assertion |
| Old FastAPI/SSE transport authority | Canonical docs identify it as old-family and non-authoritative | Future Live View transport | Legacy endpoints may remain historical |

No retired implementation is deleted by this contract.

## 6. Failure-authority contract

| Failure | Class | Required effect |
|---|---|---|
| Deliberation provider failure | Operational/non-authority | No fabricated move; quorum may withhold session |
| Phase retry failure | Operational/non-authority | Preserve both attempts; quorum governs continuation |
| Scoring failure | Non-authority quality loss | Missing score remains missing; section may remain unresolved |
| Required verification failure | Epistemic gate failure | Verification remains unresolved; no promotion/block validation |
| Ratification provider failure | Release gate failure | Existing quorum rules may withhold release |
| Invalid objection assertion | Non-authority | May be recorded as proposed/rejected; cannot become blocking |
| Observer/projection/SSE failure | Non-authority | Cannot mutate SessionState, FinalResponse or authority state |
| Learning/training failure | Non-authority | No runtime answer or lasting-change effect |
| Kernel/consultation failure | Non-authority by default | No fabricated advisory result |
| Required governed consultation failure | Epistemic gate failure | Requested verification remains unresolved |
| Advisory receipt failure | Non-authority | Advisory result becomes unusable/audited |
| Required provider/verification receipt failure | Integrity/epistemic gate failure | Outcome cannot be promoted to authoritative verification |
| H1 shadow-ledger failure | Diagnostic only | Canonical bytes and decisions remain unchanged |
| Governing ledger conflict | Integrity/epistemic gate failure | Refuse transition/release; never overwrite history |

## 7. Receipt, audit and replay ownership

| Record | Canonical owner | Meaning |
|---|---|---|
| Execution task record | CED `TaskLogEntry` | What CED scheduled and observed |
| Provider response receipt | Adapter domain using `AtomicReceiptStore` | Requested/returned identity, status and bounded metadata |
| Exact-model fact | Adapter response metadata plus provider receipt | Physical provider/model identity |
| Hybrid epistemic record | HybridEpistemicLedger | Claim/evidence/objection/revision state |
| Verification record | Hybrid ledger with receipt reference when external | Verification scope, outcome and limitations |
| Observer event | EventLedger | Observation only |
| OpenClaw trace/lesson audit | Existing OpenClaw owners | Learning/context provenance only |
| Answer benchmark cache | Evaluation `AnswerCache` | Offline evaluation replay only |
| Final release record | CED combined release transition | Whether a frozen candidate may be returned |

Records refer to immutable receipts by typed, locatable reference and digest.
They do not duplicate receipt content or claim authority over another owner's
fact. API keys, authorization headers, hidden scores and private reasoning are
never stored in public projections or fixtures.

## 8. H1 shadow-mode contract

H1 is observation-only. Before later stages may govern, tests must prove:

- canonical FinalResponse bytes unchanged;
- SessionState and authority state unchanged;
- provider selection/call behavior unchanged;
- role rotation/history unchanged;
- scoring and score coverage unchanged;
- assembly and ratification unchanged;
- observer behavior unchanged;
- no prompt change;
- no new public event without reviewed taxonomy;
- shadow append failure cannot affect canonical output.

## 9. Required amendments T1–T19

These amendments are mandatory and are satisfied normatively by this contract;
implementation proof remains stage-specific:

1. Maintain this preservation matrix as a normative contract.
2. Preserve complete canonical phases and public-context semantics.
3. Preserve ConversationManager, adaptive dialectic and fallback behavior.
4. Keep HybridEpistemicLedger separate from EventLedger with one-way projection.
5. Reuse AtomicReceiptStore; do not create a duplicate receipt system.
6. Make full deterministic task/move/run identity a replay prerequisite.
7. Deprecate score-derived epistemic authority explicitly.
8. Define proposed, checked, material, validated and blocking objection states.
9. Distinguish unresolved verification from validated blocking.
10. Preserve Council Ratification quorum, caveats and valid-block precedence.
11. Replace in-place runner-up mutation with immutable candidate lineage.
12. Preserve five-section synthesis and all quality-scoring mechanics.
13. Preserve learning, OpenClaw, consultation and kernel authority boundaries.
14. Preserve Deliberation Tree as optional and use the same ledger path.
15. Version the Live View taxonomy before Hybrid event emission.
16. Keep CandidateRecord future-compatible with Candidate Tournament.
17. Enforce the failure-authority and ownership tables above.
18. Require H1 golden byte-parity tests for every canonical authority surface.
19. Freeze H0 from a reviewed, clean, tested baseline before H1 begins.

## 10. Staged migration contract

- **H0:** freeze the restored canonical baseline and known failure fixtures.
- **H0.5:** freeze this preservation/authority contract.
- **H1:** append-only Hybrid records in shadow mode only.
- **H2:** separate quality scoring from epistemic support.
- **H3:** objection lifecycle and targeted verification.
- **H4:** safe revision and evidence revalidation.
- **H5:** contradiction validation and compatibility gate.
- **H6:** candidate lineage, restoration and eligible five-section assembly.
- **H7:** claim-level ratification and frozen release.
- **H8:** separately gated optional adapters: Kernel, Consultation, learning,
  Deliberation Tree and Dung diagnostics.
- **H9:** complete offline adversarial regression, observer integration and replay.
- **H10:** explicitly approved paid live benchmark only after offline gates.

Each stage before governing activation is additive, feature-gated and
reversible. No H1 implementation is authorized by this document.

## 11. H0 frozen failure assets

- `tests_dialogues/fixtures/known_failures/current_canonical_repeat_003.json`
  preserves the correct-minority to false-consensus/high-score/three-ACCEPT/
  `well_supported` failure chain. Missing raw text and score values remain
  explicitly unavailable.
- `tests_dialogues/fixtures/known_failures/historical_challenger_live_001.json`
  preserves the noisy-contradiction/stale-evidence/false-CBE-winner/
  contradictory-renderer failure chain. Clipped historical transcript material
  remains explicitly unavailable.
- `tests_dialogues/test_known_failure_fixtures.py` validates both fixtures,
  independently enumerates the objective unique answer, and makes no network
  or provider call.

## 12. Gate

Before any Hybrid change is accepted, reviewers must verify:

1. Every mature capability remains classified exactly once.
2. No second authority has been created.
3. H1 remains shadow-only and byte-compatible.
4. All affected existing and proposed preservation tests pass offline.
5. Any retirement still has evidence, replacement, migration and rollback
   documentation.

Failure of any item means:

`PRESERVATION GATE FAILED — DESIGN AMENDMENTS REQUIRED`

---

## 13. Amendment — H7 authority migration

H7 is the intentional authority migration point, approved after the replacement
path was implemented, tested and enforced. This amendment supersedes §8's
byte-identical `FinalResponse` requirement for the fields H7 deliberately takes
over, and for nothing else.

### Old authority

`CEDOrchestrator._epistemic_hint`: mean peer score `>= 7.5 -> well_supported`,
`>= 5.5 -> contested`, otherwise `speculative`. A quality threshold with an
epistemic name. It labelled an objectively wrong live answer `well_supported` at
a measured 7.586.

### New authority

`hybrid_epistemic.freeze_release()`. Categorical, computed from records, naming
its basis, frozen with a digest that replay reproduces. It is the only function
in the system that yields a release decision, pinned by
`test_hybrid_invariants.py::test_there_is_exactly_one_release_authority`.

`run_registry_session` calls it after ratification, through
`CEDOrchestrator._apply_governing_release`.

### Fields changed

| field | change |
|---|---|
| `FinalResponse.governing_epistemic_status` | **new** — the governing state |
| `FinalResponse.release_decision` | **new** — the frozen release verdict |
| `audit_summary["governing_release"]` | **new** — decision, claim states, basis, unresolved, digest |
| `audit_summary["legacy_epistemic_status_authority"]` | **new** — `legacy_non_governing` |

`FinalResponse.epistemic_status` keeps its type, its name and its computed
value. Only its authority changed, and the audit says so beside it.

### Fields and behaviour preserved

Execution parity remains **required** and unchanged: deterministic role
rotation, stable model identity per seat, provider routing and exact-model
pinning, prompts, moves, peer and section scoring, no-self-scoring, blind
five-section assembly, ratification inputs and verdicts, quorum and fail-closed
provider handling, receipts, replay, and observer failure isolation.

Every one of those is asserted after the migration in
`test_h7_canonical_authority.py`, which is the point of that file: the authority
boundary moved and nothing upstream of it did.

Projection is failure-isolated. If it raises, the canonical response still
stands and the audit records the governing verdict as unavailable rather than
inventing one.

### Rollback path

Remove the single `self._apply_governing_release(state, final)` call in
`run_registry_session`. `governing_epistemic_status` and `release_decision`
return to `None`, `audit_summary["governing_release"]` disappears, and the
legacy field governs again exactly as before. Nothing else unwinds: the core,
the ledger records and every test remain, and no canonical computation was
replaced — only a verdict was added and an old one demoted.

### What did not change

No other preservation guarantee is weakened. H1's shadow-mode requirement that
an observer must not perturb output still holds and is still tested; H2's
quality/support separation is unchanged; the no-fabrication invariant is
strengthened rather than relaxed, because `RELEASE_SUPPORTED` now requires a
non-empty basis and has no default.

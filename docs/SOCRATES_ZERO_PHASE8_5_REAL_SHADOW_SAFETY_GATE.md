# SocratesZero Phase 8.5 — Real Shadow Safety & Experimental Design Gate

## Scientific status

This is a read-only architecture, safety, and experimental-design result.

| Item | Gate result |
|---|---|
| Decision branch | `feature/socrates-zero-shadow-safety-gate-v0` |
| Verified parent | `feature/socrates-zero-canonical-successor-parity-v2` at `f561cf5f3b7366599b18f77efb8a8141d978d701` |
| Selected decision | **REAL SHADOW NOT YET EARNED** |
| Authorized next milestone | offline acquisition-contract/preflight foundation only |
| External network / live-provider / model / tool calls during gate | `0 / 0 / 0 / 0` |
| Runtime semantic changes | none |
| Production authority | none |

The gate does not implement a shadow runner, modify the canonical successor
environment, extend an action family, inspect credentials, or call an
external/live provider or provider SDK.

## 1. Executive verdict

**REAL SHADOW NOT YET EARNED**

A bounded live transition-safety question is scientifically meaningful in
principle, but no live experiment is implementation-ready in the current
repository. Four independent boundaries are decisive:

1. the supported opening root has exactly one hard-legal action, so there is no
   action counterfactual;
2. every supported opening successor is Value-v1-neutral, so the current
   champion cannot test action ranking or external Value generalization there;
3. CanonicalSuccessorEnvironmentV0 and its observation authority are explicitly
   offline-only and reject newly acquired live observations; and
4. the live adapter surface lacks one immutable receipt that can preflight and
   account for exact identity, tokens, cost, time, retries, fallback, raw
   retention, and acquisition isolation.

The only authorized next engineering milestone is:

`feature/socrates-zero-live-acquisition-contract-v0`

It is an offline-only, canned-transport contract/preflight milestone with
`external network/live-provider/model/tool calls = 0/0/0/0`. It may prove that
future acquisition can be admitted safely; it may not make an external call.
Its success earns another Phase 8.5 decision gate, not a live pilot.

The sole prospective live scientific question is **A — Transition-Safety**:
whether an external observation can be acquired with complete identity,
isolation and resource evidence before canonical application. This gate
authorizes zero live replications of that question; B, C and D are not selected.

The other candidate decisions are rejected now:

- same-action replication is meaningful only after acquisition safety and
  accounting are proven;
- multi-action counterfactual collection is impossible at a singleton root;
- provider/model comparison is cross-root and lacks common identity controls;
- action-family extension does not repair the more immediate acquisition seam.

## 2. Verified Phase 8 v2 evidence

| Evidence | Verified value |
|---|---|
| v2 artifact ID | `cedparityartifactv2_f3a9c85ef31dd5afc09c1353ff8fb67461ebce42ae5390a3dff1efb0f2e109e7` |
| v2 artifact SHA-256 | `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc` |
| v2 replay-lock SHA-256 | `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224` |
| v2 result | `SUPPORTED` |
| Replay semantic / ID / byte equality | `true / true / true` |
| Environment/core blob-lock ID | `cedcorebloblockv2_2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957` |
| Frozen core blobs | `34 / 34` exact |
| Core/predecessor lock mismatches | `0 / 0` |
| Environment | unchanged `ced-canonical-successor-env/v0` |
| CED transition owner | `backend.dialogues.ced.CEDOrchestrator` |

The sealed predecessor remains visible and unchanged:

| v1 field | Immutable value |
|---|---|
| Artifact ID | `cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0` |
| SHA-256 | `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea` |
| Overall status | `FALSIFIED` |
| Core transition parity | `SUPPORTED` |
| Old negative taxonomy | `FALSIFIED`, `13 / 14` |
| Sole mismatch | expected provider mismatch; actual stronger root-context mismatch |

The v2 result establishes exactly one-ply canonical transition parity for five
frozen observations and First Canonical Guard Wins for eleven orthogonal plus
seven precedence probes. It reports zero transition mismatch, mutation,
new/evaluation/negative/live provider dispatch, leakage, lock mismatch, or
replay divergence. The artifact separately preserves the five historical
offline-fixture dispatches used to create the recorded observations; aggregate
provider dispatches and negative-probe dispatches during evaluation are both
zero.

Frozen scientific hashes remain:

| Phase | SHA-256 |
|---|---|
| Phase 5 | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Phase 7 primary | `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca` |
| Phase 7 BestOfN | `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637` |
| Phase 8 v1 | `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea` |
| Phase 8 v2 | `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc` |
| Phase 8 v2 replay lock | `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224` |

The Phase 5 test defines an LF-normalized byte contract; the current raw bytes
also have that same hash. The later listed artifacts use their locked raw-byte
SHA-256 contracts.

Read-only verification gates:

| Gate | Result |
|---|---|
| Phase 8 v1/v2 successor, artifact, replay, and core locks | `181 passed` |
| Phase 6 observability + Phase 7 primary/BestOfN Value integrity | `94 passed` |
| Phase 5 evaluation integrity | `37 passed` |
| Mocked/canned provider and registry configuration | `132 passed` |
| Legal-action and BestOfN audit | `41 passed` |
| Total selected gate tests | `485 passed / 0 skipped / 0 failed` |

Checkpoint-scope verification before commit:

| Repository gate | Result |
|---|---|
| `git diff --cached --check` | pass |
| Staged scope | exactly five documentation files |
| Runtime/source/test/artifact changes | none |
| Protected untracked files | present, untouched and unstaged |

## 3. What remains unproven

Phase 8 v2 did not prove:

- acquisition-time source, sibling, or production isolation;
- safe live-provider execution or hosted-model determinism;
- admission of a newly acquired observation into the frozen manifest authority;
- exact actual-provider identity across adapters;
- exact-model identity across all adapters;
- stable prompt/adaptor/configuration version identity;
- complete successful and failed-attempt token/cost accounting;
- a pre-call enforceable cost ceiling;
- same-root provider/model interchangeability;
- multiple legal actions at the supported root;
- Value-v1 discrimination on supported opening successors;
- action ranking, factual correctness, depth two, PUCT utility, learning, RL, or
  production benefit.

Canonical transition determinism after an observation exists is distinct from
provider-output determinism and from safe acquisition of that observation.

## 4. Legal-action cardinality audit

The exact accepted opening root was reconstructed through the frozen offline
path without provider dispatch.

| Field | Exact value |
|---|---|
| Capsule ID | `cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50` |
| SearchState-v1 ID | `szstatev1_a17ce47c27894a3aac4095d0c08da107142a54d2b773c10104fde2b250c2f20e` |
| Canonical task ID | `cedtasksemantic_b5ace018c4bb1369d62bb5004a99edcd8945e4dd0eef1e206570c96b1d71017a` |
| Root question | `Is knowledge merely justified true belief?` |
| Hard-legal action count | `1` |
| Action ID | `szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421` |
| Supported family contract | `ced-opening-socratic-question/v0` |
| LegalAction kind | `ASK_SOCRATIC_QUESTION` (serialized `ask_socratic_question`) |
| Parameters / capabilities | empty / empty |
| Target kind / target ID | none / none |
| Phase / role | `OPENING / SOCRATES` |
| Task / round / slot / attempt | `SOCRATIC_QUESTION / 0 / 0 / 0` |
| Active agent | `phase8-recorded-agent-1` |
| Active provider / model | `phase8-recorded-seat-1 / phase8-recorded-model/1` |
| Model-config digest | `66430933c74f521eb83bb7ee7b115491f2426777927ac5c829c314e4a18283ba` |

Mandatory conclusion:

**SINGLE-ACTION ROOT ONLY**

The five v2 supported cases use the same generic action ID on distinct canonical
roots. They are five observations/cases, not five actions at one root.

Repository evidence:

- `backend/dialogues/socrates_zero/constitution.py:114-123,166-175`;
- `backend/dialogues/socrates_zero/contracts.py:482-548`;
- `backend/dialogues/ced_canonical_successor.py:1094-1129`; and
- `backend/dialogues/ced_canonical_successor_manifest.py:143-160`.

## 5. Action vs observation vs provider counterfactual distinction

| Experiment | Honest classification now | Readiness |
|---|---|---|
| Different hard-legal actions at one root | action counterfactual | **NOT READY**: only one action exists |
| Repeated generations for the one frozen action/model/root | same-action observation replication | scientifically meaningful later, **NOT READY** now |
| Different provider or exact model | cross-root provider/model comparison | **NOT READY** and not a same-root counterfactual |

Repeated generations cannot be passed to BestOfN as if they were different
LegalAction instances. Observation variance is not action intelligence.

## 6. Provider/root identity audit

The preserved dependency is:

~~~text
provider ID
→ council roster
→ public canonical task context
→ context/request/task digests
→ capsule/pending/root identity
~~~

| Proposed variation | Same-root legal arm? | Exact reason |
|---|---|---|
| Provider | **NO** | catalog/roster changes reach A8 `ROOT_CONTEXT_MISMATCH` |
| Exact model | **NO** | configured binding/config identity is frozen; drift is rejected at A11 |
| Target agent | **NO** | the deterministic Socrates task/agent identity changes and is rejected at A9 |

The root contains four agents and two provider/model seats, but these form a
frozen roster and binding map. They are not selectable arms. A private
binding-only mutation or exact-model mismatch may be reachable as a negative
contract probe; it is not a legal accepted same-root experimental variation.

Provider/model comparison classification: **CROSS-ROOT**.

## 7. Current champion live-compatibility

Current offline champion:

~~~text
SearchState v1
+ UniformPolicyPrior/v0
+ HeuristicValueEstimator/v1
+ BestOfNStrategy/v0
+ N = 4
+ depth = 1
~~~

Verdict:

**CHAMPION STACK NOT YET LIVE-COMPATIBLE**

BestOfN clamps its candidate limit to the hard-legal action count, so `N=4`
becomes `N=1` at this root. The uniform prior is trivial on a singleton. A
second generation of the same action is an observation replicate, not another
candidate action. Provider/model alternatives change the root.

The stack remains the offline champion. It is not promoted to production and
cannot currently test live action selection.

Traceability: candidate clamping is implemented at
`backend/dialogues/socrates_zero/strategy.py:328-375` and exercised by
`tests_dialogues/test_socrates_zero_best_of_n_strategy.py`.

## 8. Value-v1 relevance of the opening successor

Verdict:

**OPENING SUCCESSORS ARE VALUE-V1-NEUTRAL / UNINFORMATIVE**

| Value-v1 input | Root | Accepted successor |
|---|---:|---:|
| Active claims | `0` | `0` |
| Claim assessments / SupportState | `0` | `0` |
| Socratic remainder | `0` | `0` |
| Evidence / verifications / objections / contradictions | `0` | `0` |
| Terminal status | `non_terminal` | `non_terminal` |
| HeuristicValueEstimator/v1 | `0.0` | `0.0` |

The accepted Socratic question enters move history. SearchState-v1
`unresolved_questions` derives from aporia and unresolved Hybrid objections, not
from a Socratic move. The canonical opening successor uses `hybrid_state=None`
and has no commitments from which to mint valid aporia.

All five frozen successors, including the four canonical rejections, evaluate
to `0.0`. Therefore the opening action cannot test Value-v1 external
generalization. A future live safety pilot could measure transport, parsing,
canonical acceptance/rejection, isolation, and resources only.

Traceability: Value-v1 components are defined in
`backend/dialogues/ced_search_value_v1.py:227-366`, their canonical projection
inputs in `backend/dialogues/ced_search_projection_v1.py:126-162`, and their
contract tests in
`tests_dialogues/test_socrates_zero_value_v1_estimator.py`.

## 9. Live observation acquisition path

The current production-shaped path is:

~~~text
build_council
→ build_council_registry
→ session binding
→ CED._run_registry_phase
→ CED._prepare_registry_phase
→ CED._build_registry_phase_task
→ CouncilProviderRegistry.run_adapter
→ live adapter
→ parse_and_validate_move
→ CED._apply_registry_response
→ CED._finalize_registry_phase
~~~

This path advances phase, applies roles, appends moves and TaskLog rows, and
updates CED ledgers. The current recorder monkey-patches
`_apply_registry_response` and invokes `_run_registry_phase` on the authoritative
state. It is an offline lineage recorder, not an isolated acquisition seam.

Four hard admission blockers are independent of adapter quality:

1. `CanonicalSuccessorEnvironmentV0.capture_capsule` rejects any adapter whose
   `is_fake` is not exactly true
   (`backend/dialogues/ced_canonical_successor.py:226-301`).
2. `RecordedCanonicalObservation` fixes
   `privacy_classification="offline_fixture"`
   (`backend/dialogues/ced_canonical_successor_contracts.py:737-779`).
3. `apply_observation` accepts only exact equality with one of the five static
   frozen manifest observations; a new live observation fails A7
   (`backend/dialogues/ced_canonical_successor.py:1388-1393`).
4. the current recorder dispatches and mutates the authoritative CED/state
   (`backend/dialogues/ced_canonical_successor_recording.py:130-198`).

Control classification:

| Surface | Classification | Current truth |
|---|---|---|
| Global live gate | PARTIALLY CONTROLLED | missing gate/key silently selects mock |
| Provider-family/roster selection | PARTIALLY CONTROLLED | environment-driven; no immutable resolved-roster receipt |
| Canonical semantic task identity | CONTROLLED | frozen by capsule/pending contracts |
| Branch-local transport request identity | UNCONTROLLED | absent; random task ID is not a transport contract |
| Prompt/context construction | PARTIALLY CONTROLLED | deterministic builders, no complete prompt/version digest |
| Requested exact model | CONTROLLED | configured string is sent |
| Actual exact model | PARTIALLY CONTROLLED | OpenRouter verifies; Anthropic/NVIDIA do not |
| Actual provider/upstream route | UNCONTROLLED | caller label is not verified upstream identity |
| Adapter version | UNCONTROLLED | not recorded per acquisition |
| Temperature | PARTIALLY CONTROLLED | provider-specific and not immutably receipted |
| Seed | UNCONTROLLED | unsupported/absent |
| Output-token limit | PARTIALLY CONTROLLED | Anthropic/NVIDIA have caps; OpenRouter omits one |
| Timeout | PARTIALLY CONTROLLED | adapter/outer timeouts differ; cancelling NVIDIA's `to_thread` coroutine does not prove termination of its running HTTP request |
| Retry | PARTIALLY CONTROLLED | adapter loops plus CED retry/reroute; Anthropic SDK internal retries are not explicitly pinned to zero |
| Acquisition fallback / reroute | PARTIALLY CONTROLLED | mock substitution, mixed seats, provider reroute and unpinned upstream routing remain possible; downstream `assembly_fallback` is separate and occurs after acquisition |
| Tools/search/retrieval | NOT APPLICABLE | current request payloads expose no tools |
| Raw assistant text | PARTIALLY CONTROLLED | response holds text; no immutable live episode |
| Usage | UNCONTROLLED | no common ProviderResponse usage/per-attempt receipt |
| Cost | UNCONTROLLED | no trusted price or failure-cost ledger |
| Acquisition isolation | UNCONTROLLED | current integrated path mutates authoritative state |
| Provider-agnostic application after admission | CONTROLLED | application itself makes no provider call |

The internal-retry and cancellation gaps are visible at
`backend/dialogues/live_providers.py:237` and
`backend/dialogues/nvidia_nim_provider.py:309`. The prompt-entropy hazard is
visible at `backend/dialogues/openrouter_provider.py:28` together with
`backend/dialogues/models.py:192`.

## 10. Provider nondeterminism controls

| Nondeterminism source | Future disposition | Current readiness |
|---|---|---|
| Hosted model execution | record and accept as noise | not receipted end-to-end |
| Model version drift | block by exact actual-model check | OpenRouter only |
| Provider/upstream routing | block unless exact route is verified | uncontrolled |
| Queue/time effects | record order, timestamps, latency | partial |
| Retry effects | block with effective retry count `0`, including SDK internals | configurable but not contract-enforced |
| Timeout/cancellation effects | require transport termination evidence or fail closed | NVIDIA worker request can outlive outer coroutine cancellation |
| Cache effects | record if exposed; otherwise `UNKNOWN` | not exposed |
| Tool/search effects | block with tool count `0` | request surface currently tool-free |
| Moderation/refusal variation | record as classified transport outcome | inconsistent classification |

Temperature zero does not guarantee hosted determinism. With no seed contract,
byte-identical provider output must never be a live success criterion.
Canonical replay determinism remains a separate property.

## 11. Branch-acquisition isolation

Phase 8 proved application isolation after an admitted observation exists. It
did not prove acquisition isolation.

A future acquisition contract must fingerprint before and after:

- source SessionState and TaskLog;
- commitments, role history, retry counters, budget, governing state,
  ratification, observer authority, and every side ledger;
- every sibling branch/provider context and request identity; and
- production state and runtime configuration.

The acquisition operation may output only an external observation envelope and
resource receipt. It must not call `apply_observation`, mutate CED, or append a
TaskLog row. Canonical application is a later, separately authorized operation
on an isolated branch.

Branch-local transport identity must remain out-of-band. It may not change the
provider-visible public prompt/context bytes. This matters because the current
OpenRouter prompt serializes the full `AgentTask`, including its random
`task_id`. The prerequisite must prove with canned branches that semantic
prompt bytes are identical while branch-local transport IDs remain unique.

External acquisition architecture: **CONDITIONAL YES**.

Current end-to-end admission/isolation: **NO**.

If a later gate earns a first live safety pilot, the selected state design is
**Option 2 — dedicated research-only canonical root**. An actual production root
adds contamination risk, while replaying a recorded production root later adds
temporal/model-drift ambiguity. This choice is a frozen safety requirement, not
authorization for a live call.

## 12. Same-root fairness requirements

For any future action counterfactual, all except the LegalAction must match:
root, public context, provider, exact model, prompt/configuration, token budget,
timeout, retry, fallback, tools, and information prefix. This gate has no second
action, so that experiment is unavailable.

For future same-action replication, freeze:

- one canonical root/capsule and one action ID;
- one provider, exact model, endpoint/route, adapter and prompt version;
- one configuration, token cap, timeout, retry/fallback/tool policy;
- branch-local transport IDs distinct from the stable semantic task ID; and
- identical provider-visible prompt/context bytes across branches, with all
  transport/branch entropy carried out-of-band; and
- no sibling output, evaluator label, future evidence, or cross-branch context.

Provider/model comparisons must be stratified as cross-root comparisons and may
not enter the same primary metric as same-root replication.

## 13. Call ordering and replication design

No live order or positive replication count is authorized by this gate.

A later gate—not this report—may decide whether exactly one call is sufficient
to test the narrow acquisition path after preflight controls exist. Multiple
observations are required for any variability claim. One observation is never
evidence of provider determinism or population variability.

The authorized offline prerequisite has:

| Design field | Frozen value |
|---|---|
| Research roots | `1` canned canonical fixture root |
| Branch controls | `2`: one acquisition candidate plus one untouched sibling |
| Live replications | `0` |
| Live call order | none |
| Canned case order | deterministic, frozen before its contract aggregate |
| Canned transport invocations | nonzero, bounded by the frozen case manifest, and counted separately from external calls |

No alternating, randomized, or Latin-square order is justified until a real
multi-arm experiment is earned.

## 14. Cost and budget model

`SearchBudget` already defines nodes, expansions, model/tool calls, tokens,
integer micro-USD, wall milliseconds, and depth. `RecordedHistoricalUsage`
correctly distinguishes COMPLETE, PARTIAL, and UNAVAILABLE so unknown is never
false zero.

The live surface does not currently reserve or charge a call through those
contracts:

- `NewExecutionUsage` accounts only for offline successor application;
- common `ProviderResponse` has only a caller-supplied `provider_id`, not
  separate requested-versus-verified actual provider/model/configuration
  identity, tokens, cost, or per-attempt usage;
- failed/retried attempts have no complete aggregate spend receipt;
- Anthropic/NVIDIA expose a per-request output-token cap, while OpenRouter lacks
  one;
- Anthropic/NVIDIA lack verified actual-model identity;
- Anthropic SDK retries are not explicitly disabled and NVIDIA cancellation
  does not prove that its worker request stopped;
- defaults conflict across live paths; and
- no trustworthy frozen pricing/failure-cost authority exists.

Therefore no provider-selected, end-to-end enforceable total-token, cost and
total-wall-time acquisition budget can currently be frozen. The mandate makes
the live pilot non-ready.

Exact authorized prerequisite limits:

| Limit | Value |
|---|---:|
| Maximum research roots | `1` |
| Maximum controlled branches | `2` |
| Maximum external calls per branch | `0` |
| Maximum total external network/live-provider/model calls | `0` |
| Maximum live tokens per call | `0` |
| Maximum total live tokens | `0` |
| Maximum live cost | `0 micro-USD` |
| Maximum external/live-provider wall time | `0 ms` |
| Maximum retries | `0` |
| Maximum fallback activations | `0` |
| Maximum tool calls | `0` |
| Maximum failed live attempts | `0` |
| Maximum accepted live successors | `0` |
| Canned transport invocations | nonzero and exactly counted against the frozen case manifest |

Local unit-test runtime is CI work, not experimental provider usage.

## 15. Abort conditions

For a future live pilot, these invalidate the entire pilot and require immediate
global stop:

- any source, sibling, or production mutation;
- cross-branch context exposure or transport-request collision;
- an unaccounted canned or external call/attempt;
- requested/actual provider, model, configuration, prompt, or endpoint mismatch;
- fallback, reroute, or retry activation under the frozen zero policy;
- inability to preflight or enforce call/token/cost/time limits;
- any unknown required pre-call limit or cost authority;
- missing delivered raw observation or digest;
- missing/partial usage when complete accounting is the primary hypothesis;
- receipt, lineage, isolation, or resource mismatch;
- future-label or evaluator-truth leakage; or
- canonical application/replay inconsistency.

These are branch-local classified outcomes only when fully receipted and within
budget: timeout, rate limit, refusal, transport error, invalid JSON/schema,
Socratic/content firewall rejection, or canonical rejection. They still count
as attempts. Every measured resource component is recorded; any unreported
post-attempt component remains `UNKNOWN`, never zero. If complete accounting is
the pilot hypothesis, any such unknown invalidates the entire pilot.

For the authorized offline prerequisite, any external
network/live-provider/model/tool call, credential access, runtime semantic
change, or acceptance of an
uninspectable/unknown required field immediately falsifies the milestone.

## 16. Episode schema

The next milestone may design and offline-test a minimal immutable preflight
schema containing:

- schema, experiment, episode, root capsule, SearchState-v1 and fingerprint IDs;
- complete legal-action IDs, selected action and selection method;
- pending-transition and canonical semantic task IDs;
- a separate collision-safe branch-local transport request ID;
- requested provider/model/route/configuration and actual provider/model/route;
- adapter type, version/blob, endpoint, prompt/context version and digest;
- temperature, seed status, output-token cap, timeout, retry, fallback and tools;
- call index/order plus immutable per-attempt IDs, status, latency and response ID;
- raw public assistant-text digest, protected reference, privacy and retention;
- COMPLETE/PARTIAL/UNAVAILABLE historical, new-execution, per-attempt and
  aggregate usage, with unknown components never represented as zero; positive
  pilot-eligible cases require every required new-execution field to be complete,
  while partial/unavailable fields are expected negative cases only;
- observation, transition, receipt, move, successor and Value receipt IDs;
- pre/post source, sibling and production fingerprints; and
- failure taxonomy, abort scope and deterministic evidence ID.

The prerequisite publishes only a canned
`ced-live-acquisition-preflight-artifact/v0`. It does not publish a live episode,
reward, policy label, or training-eligibility flag.

## 17. Data minimization

Persist only what replay, identity validation and resource auditing require:

- public assistant text or a protected replay reference plus its exact UTF-8
  digest;
- structured provider envelope fields required for identity and usage;
- exact requested/actual configuration, prompt/context references, receipts and
  SearchState projections.

Do not persist private chain-of-thought, adaptive-thinking blocks, hidden
provider reasoning, secrets, duplicated full prompts in every row, unrelated
production state, rewards, or policy labels.

Raw public text is required for canonical parser/firewall replay. Before any
live call, an explicit storage location, access policy, encryption boundary,
retention duration and deletion procedure must be frozen. The current
`offline_fixture` privacy literal is not silently broadened.

## 18. Outcome and metric limitations

A future safety pilot may observe:

- transport success/failure;
- exact identity verification;
- parser and Socratic firewall acceptance;
- canonical transition availability;
- branch-isolation and resource receipts; and
- successor SearchState-v1.

Same-action replication could later estimate response, acceptance and successor
variability. At the current opening root, Value-v1 remains `0.0` and is not an
informative primary metric.

None of these measurements establishes factual truth. A higher heuristic value
would measure readiness deficit under frozen semantics, not correctness.

## 19. Action-family sufficiency

| Scientific question | Is `ASK_SOCRATIC_QUESTION` sufficient? |
|---|---|
| Live acquisition/transition safety | **YES in principle**, after acquisition contracts pass |
| Same-action observation variability | **YES in principle**, after safety |
| Value/action ranking | **NO** |
| Multi-action counterfactual | **NO** |

An action-family extension is a separate, parity-first offline milestone. It is
not selected now because it would not repair live acquisition identity,
manifest authority, isolation or accounting.

The acquisition design is compatible with future Alpha/Beta/Gamma/Delta
reasoners because it binds each request to explicit task/agent/branch identity
and assumes no permanent two-agent topology. No four-reasoner runtime is
implemented here.

The developing Socratic-method principles remain documentation-only: no imposed
doctrine; explicit commitments; elicited self-revision; multiple independent
reasoners; targeted bounded examination; evidence over persuasion; no truth by
consensus; and aporia rather than unjustified certainty. The final Socratic
Master Architecture remains deferred.

## 20. Decision matrix

Ratings describe current-repository readiness. High safety, interpretability,
auditability and falsifiability are favorable; high risk, cost, nondeterminism
and complexity are unfavorable.

| Candidate | Constitutional safety | Contamination risk | Scientific interpretability | Value relevance | Action relevance | Provider nondeterminism | Same-root validity | Cost | Complexity | Replay/auditability | Falsifiability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Limited live observation safety | MEDIUM | HIGH | HIGH | LOW | LOW | MEDIUM | HIGH | HIGH | HIGH | LOW | HIGH |
| Same-action replication | MEDIUM | HIGH | HIGH | LOW | LOW | VERY HIGH | HIGH | HIGH | HIGH | LOW | HIGH |
| Multi-action counterfactual | LOW | HIGH | LOW | LOW | LOW | HIGH | LOW | HIGH | VERY HIGH | LOW | LOW |
| Offline action-family extension | HIGH | LOW | HIGH | MEDIUM | HIGH | LOW | MEDIUM | LOW | HIGH | HIGH | HIGH |
| No live yet + acquisition preflight | VERY HIGH | LOW | HIGH | LOW | LOW | LOW | HIGH | LOW | MEDIUM | VERY HIGH | HIGH |

| Candidate | Future shadow usefulness | Experience Store usefulness | Learned Value usefulness | Policy usefulness | RL usefulness |
|---|---|---|---|---|---|
| Limited live observation safety | VERY HIGH | LOW | LOW | LOW | LOW |
| Same-action replication | HIGH | MEDIUM | LOW | LOW | LOW |
| Multi-action counterfactual | LOW | LOW | LOW | LOW | LOW |
| Offline action-family extension | HIGH | LOW | MEDIUM | MEDIUM | LOW |
| No live yet + acquisition preflight | VERY HIGH | LOW | LOW | LOW | LOW |

Every matrix cell uses only the mandated qualitative vocabulary. `HIGH` cost
for the live candidates reflects unresolved budget/accounting risk, not a
pricing estimate. The currently invalid multi-action candidate is rated `LOW`
for downstream usefulness; this does not deny its possible value after a
separate same-root action-family parity milestone.

The acquisition preflight has the highest immediate information gain subject to
the lowest constitutional/contamination risk. It addresses the first missing
causal link: safe external observation acquisition.

## 21. Exactly one selected next milestone

### Decision

**REAL SHADOW NOT YET EARNED**

### Next branch

`feature/socrates-zero-live-acquisition-contract-v0`

### Primary hypothesis

An additive, provider-agnostic acquisition/preflight contract can be proven
entirely with canned transports to produce immutable branch-local identity,
attempt, observation, resource and isolation receipts, while failing closed on
any incomplete provider/model/configuration identity, budget, retention or
isolation evidence—without calling an external provider or provider SDK and
without invoking canonical application. Canned transport invocations are
required and separately counted; external
network/live-provider/model/tool calls remain zero.

### Frozen milestone design

| Required field | Frozen value |
|---|---|
| Experiment type | offline acquisition-contract/preflight foundation |
| Root type | one dedicated research-only canonical fixture root |
| Supported family contract | existing `ced-opening-socratic-question/v0` only |
| LegalAction kind | existing `ASK_SOCRATIC_QUESTION` only |
| Action count | `1` |
| Provider/model policy | canned transports and immutable capability descriptors only |
| Replication count | `0` live replications |
| Call order | no live order; deterministic canned case order |
| Maximum roots | `1` |
| Maximum branches | `2` |
| Maximum external calls per branch | `0` |
| Maximum total external network/live-provider/model calls | `0` |
| Maximum live tokens per call | `0` |
| Maximum total live tokens | `0` |
| Maximum live cost | `0 micro-USD` |
| Maximum external/live-provider wall time | `0 ms` |
| Maximum failed live attempts | `0` |
| Canned transport invocations | nonzero and exactly counted against the frozen case manifest |
| Retry policy | external retries `0`; capability contract must also prove SDK-internal retries disabled |
| Fallback policy | silent/unplanned adapter, transport or route substitution disabled; the pre-registered canned fixture transport is an input, not a fallback; downstream assembly is not invoked |
| Tool policy | `0`; no tools/search/retrieval |
| Observation capture contract | new additive schema; never weaken/overwrite v2 manifest |
| Isolation contract | exact source/sibling/production before/after fingerprints |
| Episode artifact | canned `ced-live-acquisition-preflight-artifact/v0` only |

### Minimum implementation

1. immutable provider/adapter capability and configuration snapshot;
2. stable semantic task ID plus separate out-of-band branch-local transport
   request ID that cannot change provider-visible prompt/context bytes;
3. immutable per-attempt and aggregate identity/resource receipt;
4. pre-dispatch fail-closed validation of requested provider/model binding,
   adapter verification capability, endpoint/route policy, prompt version,
   budget reservation, token cap, timeout, transport termination capability,
   adapter/SDK retry, fallback and tools;
5. post-canned-response verification of returned actual
   provider/model/route/configuration before any observation becomes eligible;
6. canned acquisition seam that never invokes CED application;
7. raw public-text privacy, access and retention contract;
8. source/sibling/production acquisition-isolation receipts;
9. deterministic canned case set including cross-branch prompt-byte equality,
   pre-result thresholds, artifact and replay lock;
10. separate counters for canned transport invocations and every class of
   external call; and
11. static/runtime tripwires proving zero external
    network/live-provider/model/tool calls.

### Primary metrics

- exact contract/preflight classifications;
- branch-local request-ID uniqueness and semantic-task-ID stability;
- cross-branch equality of provider-visible semantic prompt/context bytes;
- complete requested/actual identity coverage;
- complete required resources for every positive pilot-eligible canned case;
- honest PARTIAL/UNAVAILABLE resource fields only in expected negative cases
  that remain ineligible, never false zero;
- source/sibling/production mutations;
- fallback/retry/tool activations;
- counted canned invocations and unaccounted canned/external calls;
- deterministic artifact/replay equality; and
- external network/live-provider/model/tool calls, all required to remain zero.

### Success criteria

- every canned positive contract case produces the exact immutable receipt with
  complete required new-execution resource fields;
- every missing required pre-dispatch control or budget authority fails before
  the canned transport is invoked;
- every returned actual-identity mismatch fails after the canned response and
  before observation eligibility, capture, admission or application;
- every expected PARTIAL/UNAVAILABLE resource case is represented honestly and
  remains pilot-ineligible;
- semantic and transport identities remain separate;
- branch-local transport entropy remains absent from provider-visible
  prompt/context bytes;
- raw retention/privacy rules validate;
- source, sibling and production mutations are zero;
- no CED application or environment semantic change occurs;
- all frozen/historical hashes remain unchanged;
- every canned transport invocation is counted and bounded by the frozen case
  manifest;
- external network/live-provider/model/tool calls are `0/0/0/0`; and
- the preflight artifact replays semantically and byte-identically.

### Failure / falsification criteria

Any external network call, credential access, live-provider/provider-SDK/model
or tool invocation, runtime semantic change, mutable or caller-self-certified
receipt, accepted unknown required control, false-zero usage, identity
collision, source/sibling/production mutation, artifact replay divergence,
provider-visible branch/transport entropy, unpinned SDK-internal retry,
unterminated timed-out worker, uncounted canned invocation, or post-result
threshold change falsifies the prerequisite.

### Frozen components

SearchState v0/v1, Projection v0/v1, Value v0/v1, Policy v0, Greedy v0,
BestOfN v0, PUCT v0, `N=4`, `c_puct=1.0`, depth `1`, Hybrid semantics, CED
transition ownership, CanonicalSuccessorEnvironmentV0, the five recorded
observations, v1/v2 artifacts, all historical hashes, and the single supported
family contract and LegalAction kind remain unchanged.

### Explicit non-goals

No external network/live-provider/model/tool call, provider credential
inspection, shadow execution, observation
admission, canonical application, action extension, production root,
same-action replication, cross-root comparison, Value ranking, Experience
Store, learning, RL, self-play, depth two, PUCT change, production wiring or
four-reasoner runtime.

### What success unlocks

Only a new Phase 8.5 decision gate that may determine whether exact positive
live budgets and a one-call dedicated-research-root safety pilot can be frozen.

### What remains blocked

Limited live observation safety, same-action replication, multi-action
counterfactuals, provider/model comparisons, action-family extension,
Experience Store, learned Value, learned Policy, RL, self-play, depth two,
PUCT changes and production SocratesZero authority all remain blocked.

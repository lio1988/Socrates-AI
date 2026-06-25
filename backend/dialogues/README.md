# Socratic Dialogues Orchestration System (V1)

A multi-agent deliberation engine. A **Council of Epistemic Deliberators (CED)**
drives a panel of stateless *Socratic Agents* through a fixed dialectical
pipeline and produces a single, ratified answer with an explicit epistemic status.

V1 ships with a **deterministic `FakeProvider`** only — no network, no API keys,
no cost. The whole architecture is exercised and tested before any real LLM is
wired in.

---

## Permanent invariant — peer scoring, not CED scoring

> **Agents judge epistemic quality. CED governs the protocol.**

CED does **not** act as a semantic authority. It coordinates peer evaluation,
validates the process, and mechanically aggregates the results. Every
qualitative score comes from a **peer voter** (an agent/provider evaluating
another agent's output under a phase-specific rubric).

**CED may only:** assign roles · create tasks · route scoring tasks to peer
voters · validate score schemas · prevent self-scoring (`voter_id != author_id`)
· collect `MicroScore`s · aggregate mechanically (averages, cumulative,
rankings, coverage, deterministic tie-breakers) · record audit metadata · report
`complete / partial / timeout / disabled / quorum_failed / failed`.

**CED must never:** decide by itself that an answer/question/objection is better ·
create a qualitative score without a voter · **fabricate a stand-in score (e.g.
zeros) for a failed/invalid/timed-out peer score** · act as an autonomous judge.

If peer scoring fails, times out, returns invalid JSON, or lacks quorum, the
**missing peer scores stay missing** — the leaderboard/sync-gate status becomes
`partial` / `timeout` / `failed` / `quorum_failed` / `disabled`, and the audit
explains it mechanically. There is **no fake fallback semantic score**.

> Wording: not *"CED judged this answer better"* — rather *"peer agents scored
> this output higher under the `<rubric>` rubric, and CED mechanically aggregated
> the valid scores."*

Each `MicroScore` carries `phase`, `rubric_name`, `author_agent_id`,
`voter_agent_id`, `score_breakdown`, `confidence`, `penalty_flags`,
`provider_status`. Peer scoring applies to every configured `SCORED_PHASE`
(including the Socratic opening question), each with its own rubric
(`question_quality`, `objection_quality`, `synthesis_quality`, …). Tests in
`tests_dialogues/test_ced_peer_scoring_invariant.py` prove this invariant holds.

---

## Quick start

From the repository root:

```bash
# Run the end-to-end demo (default question is an epistemology question)
python -m backend.dialogues.demo
python -m backend.dialogues "Is mathematics discovered or invented?"

# Run the test suite (93 tests)
python -m pytest tests_dialogues
```

On Windows you can also double-click `run_dialogues_demo.bat` in the project
root, or use `run_dialogues_demo.ps1`.

---

## Architecture

```
                ┌──────────────────────────────────────────┐
                │            CEDOrchestrator                │
                │   (owns ALL session state + scoring)      │
                └──────────────────────────────────────────┘
                  │ AgentTask              ▲ AgentMove
                  ▼                        │
         ┌───────────────┐        ┌───────────────┐
         │ SocraticAgent │  ...   │ SocraticAgent │   ← session-scoped, no memory
         └───────────────┘        └───────────────┘
                  │  execute(task)         ▲ structured dict
                  ▼                        │
                ┌──────────────────────────────────────────┐
                │              LLMProvider                  │
                │   FakeProvider (V1)  ·  Anthropic/…(stub) │
                └──────────────────────────────────────────┘
```

### Core principles

| Principle | Where it lives |
|---|---|
| **CED owns all state** | `SessionState`, scores, drafts, scorecards live only on the orchestrator. Agents never hold a reference. |
| **Session-scoped agents** | `SocraticAgent.execute()` takes an `AgentTask`, returns an `AgentMove`, and stores **nothing** between calls. An agent is a stateless tool, not a memory holder. |
| **Deterministic dynamic role rotation** | The CED reassigns roles **per phase** via `assign_roles_for_phase(state, phase, round_index)` — a pure function of `session_id + phase + round_index + sorted agent IDs`. No agent chooses its own role; no provider influences it. |
| **Minimal Awareness** | Agents receive only what their task needs. They never see raw scores, score breakdowns, leaderboards, peer identities beyond task needs, shadow-scoring internals, or provider mappings. Scoring data is never inserted into `AgentTask.context` and never stored on `AgentState`. |
| **Multi-dimensional shadow scoring** | Each non-author voter scores on seven 0–10 dimensions (`ScoreBreakdown`), weighted to an `overall_score`. CED-owned, computed after synthesis, hidden from agents. No agent scores its own output. |
| **5-section blind assembly** | Each section is won independently by the highest average `overall_score`, mechanically — the CED never chooses winners semantically. |
| **Structured ratification** | The Final Evaluator casts a `RatificationVote`; only a `CRITICAL` blocking objection blocks. |
| **Topic-aware FakeProvider** | Scripted output adapts to the question's topic (e.g. epistemology) so it stays domain-relevant. |
| **Structured outputs only** | Every agent output is a Pydantic model (`AgentMove`); providers return schema-keyed dicts. |

---

## Deterministic CED role rotation

Roles are **not** owned by agents — the CED assigns them per phase:

```
offset       = stable_hash(session_id) % n
rotated      = agent_ids[offset:] + agent_ids[:offset]
agent_for_role = rotated[(role_index + phase_index + round_index) % n]
```

`stable_hash` is SHA-256 based (run-independent — Python's built-in `hash()` is
not used). Consequences:

- **Socrates rotates** across sessions (and across rounds if there are several).
- The **Final Evaluator is not pinned to the Socrates agent** — when ≥ 4 agents
  exist, the high-impact roles (Socrates / Synthesizer / Final Evaluator) land on
  different agents.
- Every assignment is recorded in `SessionState.role_history`
  (`{phase, round_index, agent_id, role}`).

`role_assignment.py` also computes a *primary-role label* per agent, used **only**
for debug/demo display — actual execution always uses the per-phase scheduler.

---

## The pipeline

| # | Phase | Role(s) active | Output |
|---|---|---|---|
| 1 | `OPENING` | Socrates | one assumption-exposing question |
| 2 | `INITIAL_RESPONSE` | Elenchus Critic, Empiricist, Synthesizer | first positions |
| 3 | `ELENCHUS` | Elenchus Critic, Empiricist | contradictions & gaps |
| 4 | `REFLECTION` | Reflector (responders revise) | revised positions |
| 5 | `RECONSTRUCTION` | Maieutic Reconstructor | stronger rebuilt position |
| 6 | `SYNTHESIS` | all agents | competing **5-section** draft answers |
| — | *move-level shadow scoring* | CED-internal | `MicroScore[]` (7-dim, hidden) |
| — | *section-level scoring* | CED-internal | `DraftScorecard[]` (per draft × voter) |
| — | *blind assembly* | CED-internal (mechanical) | `AssembledAnswer` (5 sections) |
| 7 | `RATIFICATION` | Final Evaluator (deterministically rotated) | `RatificationVote` → ratify / block / unresolved |

---

## Multi-dimensional shadow scoring

`ScoreBreakdown` has seven dimensions, each on a **0–10** scale, weighted to an
overall score (weights sum to `1.0`):

| Dimension | Weight |
|---|---|
| `epistemic_value` | 0.30 |
| `logical_rigor` | 0.20 |
| `factual_grounding` | 0.15 |
| `constructive_impact` | 0.10 |
| `intellectual_honesty` | 0.10 |
| `clarity_precision` | 0.10 |
| `grounded_creativity` | 0.05 |

- `overall_score` is on the **0–10** scale; only `confidence` is `0–1`.
- `MicroScore` (move-level) and `SectionScore` (section-level) both **reject
  self-scoring** (`author_agent_id != voter_agent_id`) and auto-fill `overall_score`
  from the breakdown.
- Malformed provider output is recorded cleanly (`ProviderStatus.ERROR` +
  `PenaltyFlag.SCHEMA_VIOLATION`) rather than crashing orchestration.

These scores are **shadow scores**: CED-owned, computed after synthesis, never
returned to or seen by any agent.

---

## 5-section blind assembly

Every synthesizer emits a locked 5-section `SectionDraft`:

```
core_answer · crucial_stress_test · blind_spots · nuance · final_verdict
```

For **each section independently**, the CED picks the draft with the highest
average `overall_score`. Selection is mechanical (the CED never edits or
semantically chooses content). Tie-breakers, in order:

1. highest average `overall_score`
2. lower variance
3. higher score count
4. deterministic `draft_id` order

Because scoring is per section, **different drafts can win different sections**.

---

## Ratification logic

The deterministically-assigned Final Evaluator casts a `RatificationVote`
(`decision`, `severity`, optional `target_section`, `reason`), for up to
`MAX_RATIFICATION_ROUNDS = 2` rounds:

- Only a `BLOCKING_OBJECTION` at `CRITICAL` severity blocks.
- `minor` / `major` objections are recorded but never block.
- A critical objection **targeting a section** triggers a **runner-up
  replacement** for that section; if no runner-up remains (or rounds are
  exhausted), the section is marked **unresolved**.
- A critical objection with **no** target section hard-blocks the whole answer
  (the answer is withheld).

---

## Topic-aware FakeProvider (Phase 6)

`topic.py` provides a deterministic keyword classifier:

```python
from backend.dialogues import classify_topic, Topic
classify_topic("Is knowledge merely justified true belief?")  # Topic.EPISTEMOLOGY
```

`Topic` values: `COSMOLOGY`, `EPISTEMOLOGY`, `MATHEMATICS_PHILOSOPHY`, `LAW`,
`MEDICINE`, `TECHNOLOGY`, `BUSINESS`, `GENERAL`.

### Epistemology support

For `Topic.EPISTEMOLOGY` the scripted provider discusses the actual philosophical
issue rather than generic scientific-causality language:

- **Socrates** asks a Gettier-aware, assumption-exposing question.
- **Elenchus Critic / Empiricist / Maieutic Reconstructor** discuss JTB, Gettier
  cases, necessary-vs-sufficient conditions, anti-luck / reliability / defeater
  constraints, and the limits of philosophical consensus.
- **Four genuinely different synthesizer perspectives** (so blind assembly is
  meaningful):
  - `agent_0` — classical / JTB
  - `agent_1` — Gettier / anti-luck
  - `agent_2` — reliabilist / externalist
  - `agent_3` — virtue / contextualist
- **Section scoring is topic-aware**: it rewards on-topic depth (Gettier,
  anti-luck, necessary/sufficient, reliability) and penalizes irrelevant
  empirical-causality language, vagueness, and over-claimed consensus — using
  penalty flags such as `irrelevant`, `vague`, `unsupported_claim`,
  `missed_uncertainty`. Scoring stays fully deterministic.

For epistemology questions the final answer mentions Gettier-style objections,
distinguishes necessary from sufficient conditions, avoids scientific-causality
phrasing, and marks uncertainty about which extra condition is best.

---

## Browser demo alignment

`socrates_demo.html` (project root) is a self-contained, vanilla-JS clone of the
Python demo — no server, no Python, runs from `file://`. It re-implements the
deterministic logic (a synchronous SHA-256, the per-phase role scheduler, 7-dim
0–10 scoring, 5-section blind assembly, and the topic classifier with the same
epistemology perspectives).

It is aligned with the Python demo: the same `stable_hash` means the same role
rotation for a given `session_id` (e.g. `demo_session` → opening `agent_3`,
evaluator `agent_1`), and the same topic-aware content. It also exposes
example-question chips, including *"Is knowledge merely justified true belief?"*.

---

## Programmatic use

```python
from backend.dialogues import CEDOrchestrator, SocraticAgent, FakeProvider

provider = FakeProvider()
agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
ced = CEDOrchestrator(agents, provider)

final = ced.run_session("Is knowledge merely justified true belief?")
print(final.ratified, final.epistemic_status.value)
print(final.answer)
```

To inspect CED-owned state, pass an explicit `session_id` and fetch it:

```python
final = ced.run_session("…", session_id="my_session")
state = ced.get_session("my_session")
state.role_history          # per-phase role assignments
state.section_drafts        # the competing 5-section drafts
state.micro_scores          # hidden move-level shadow scores
state.draft_scorecards      # hidden section-level scores
```

---

## Key modules

| File | Responsibility |
|---|---|
| `models.py` | All Pydantic models + enums (`AgentTask`, `AgentMove`, `SessionState`, scoring, sections, assembly, ratification, `FinalResponse`). |
| `providers.py` | `LLMProvider` interface, topic-aware `FakeProvider`, three reserved stubs, `ProviderRegistry`. |
| `topic.py` | `Topic` enum + deterministic `classify_topic`. |
| `agent.py` | `SocraticAgent` + the Core Agent Prompt (v1.9). |
| `role_assignment.py` | `stable_hash` + deterministic primary-role label (debug/demo). |
| `ced.py` | `CEDOrchestrator`: per-phase role scheduler, phase methods, shadow scoring, blind assembly, ratification. |
| `demo.py` / `__main__.py` | Runnable end-to-end demo. |

---

## Current limitation

`FakeProvider` is **scripted and fully deterministic** — same inputs always
produce the same outputs. It exists so the orchestration machinery can be built
and tested without any model. **Real LLM providers come later**: subclass
`LLMProvider`, implement `complete(...)` to return schema-keyed dicts, register
via `ProviderRegistry.register(...)`, and hand the provider to the agents. The
CED and agents are provider-agnostic.

> Note: `move_id` is **deterministic** — derived from stable task identity
> (`session_id | phase | round | agent_id | role | task_kind | slot | attempt`),
> never from runtime/async completion order. So for a given `(question,
> session_id)` the **whole** pipeline is reproducible: move ids, shadow scores,
> section winners, leaderboard, and audit counters are identical across runs and
> independent of provider latency.

---

## Provider layer (Phase 8)

The CED is ready for real providers but **V1 uses mock/fake providers only** —
no real Claude/OpenAI/Gemini/Grok calls, no network, no keys.

### CouncilProviderRegistry
`provider_registry.py` holds an availability-aware registry of provider
*adapters* (`LLMProviderAdapter`: `async generate_agent_move(task, agent_state)
-> ProviderResponse`). It:

- filters out adapters whose key is missing or a placeholder (`""`,
  `your_key_here`, `changeme`, `test`, …) via `is_placeholder_key` — it **never
  reads `.env`**; callers pass already-configured adapters in;
- enforces `minimum_providers = 2` (readiness) and `quorum_for_assembly = 2`;
- runs one council round (`gather_council_round` / `gather_registry_phase_round`)
  with per-provider `provider_timeout_seconds = 30.0`, exception safety, and
  structured-output validation;
- exposes a CED-owned `status_summary()` (available / unavailable / failed
  providers) for the audit — never for agents.

### Mock providers (dev/CI only)
`AlwaysOKProvider`, `TimeoutProvider`, `InvalidJSONProvider`,
`SchemaErrorProvider`, `RateLimitedProvider`, `MissingKeyProvider`, and the rich
`ScriptedMockProvider` / `TimeoutScriptedProvider` (which produce real scripted
council content via the in-process `FakeProvider`). All deterministic.

### Provider statuses (`ProviderStatus`)
`ok`, `missing_key`, `timeout`, `invalid_json`, `schema_error`, `rate_limited`,
`error`, `disabled`. Failed/timed-out providers are recorded as **metadata only**
— no fake `AgentMove` is ever fabricated for them.

### Full registry session (Phase 8C)
`await ced.run_registry_session(question, session_id)` drives every deliberation
phase through the registry (deterministic roles, per-phase quorum, validation,
failure recording), then runs the existing scoring → blind assembly →
ratification. It returns a `FinalResponse` whose `audit_summary` separates
`provider_status_summary`, `registry_phase_rounds`, `task_log_summary`, and
`shadow_scoring_mode`. If the registry is not ready (or a phase fails quorum) it
returns a **safe non-proceeding** result (`ratification_status="quorum_failed"`,
no synthesis) — never a crash, never a fake answer. Demo:
`python -m backend.dialogues.demo_registry_session`.

### `shadow_scoring_mode`
Cost control for real providers (`CEDOrchestrator(..., shadow_scoring_mode=…)`):

| mode | scored phases | leaderboard |
|---|---|---|
| `all_phases` (default) | every deliberation phase (incl. the Socratic question) | `complete` |
| `synthesis_only` | synthesis drafts only | `complete` |
| `sampled` | opening + synthesis | `complete` |
| `off` | none | `disabled` (clean, not a failure) |

Each `MicroScore` records a **phase-specific rubric** (`question_quality`,
`objection_quality`, `synthesis_quality`, …) — a Socratic question is not judged
by the same yardstick as a final answer.

### `json_repair_attempts`
`parse_and_validate_move` tries a normal parse; on failure (and if
`json_repair_attempts > 0`) it applies one minimal, dependency-free repair (strip
code fences, drop trailing commas) and reparses. A repaired payload **still must
pass schema validation** — repair never bypasses it. `repair_attempted` /
`repair_succeeded` are recorded on the `ProviderResponse`.

### task_log / context_hash
Every dispatched task is traced in a CED-owned `SessionState.task_log`
(`TaskLogEntry`: identity + a stable `context_hash`, plus `provider_id/status`).
Full prompt text is **debug-only** (`ced.debug_task_log = True`, off by default).
The task_log is **never** inserted into `AgentState` or sent to agents.

### Adding real adapters later
The reference shape now exists offline — see **Phase 9A** below
(`offline_provider_adapter.py`). A real adapter subclasses `BaseProviderAdapter`
(or reuses `OfflineProviderAdapter`'s build/extract logic), implements the one
network seam (`_produce_raw_text` / a live transport `send`) to call
`client.messages.create(...)` and return raw text, sets `provider_id` /
`provider_name`, holds the key locally, and `registry.register(...)`. The CED and
validation path are unchanged. **Keys stay local in `.env` and are never
committed; no real API is used through Phase 9A (offline-first).**

### Minimal awareness (hard rule)
Agents never see scores, breakdowns, leaderboard, `provider_status_summary`,
`task_log`, coverage ratios, hidden provider mappings, or other providers'
private errors. All of that lives only in CED-owned state and audit output.

---

## Phase 8C.1 — Socratic Council Ratification

`final_synthesis_mode = "council_ratification"` (default). After the synthesis is
assembled, the registry session sends a ratification task to **every available
provider**; each independently returns one verdict — `accept`,
`accept_with_caveat`, or `blocking_objection`. There is **no single Final
Evaluator monarchy** in registry-backed mode.

> **Council ratification is not majority voting.** CED does not count ACCEPT
> votes to decide truth. CED checks quorum, validates verdict schemas, detects
> **structurally valid** critical blocking objections, and applies deterministic
> protocol rules. **Agents judge epistemic quality. CED governs the protocol.**

A *schema-valid critical blocking objection* is checked **structurally only**
(verdict = blocking_objection · severity = critical · a `target_section` · a
`rationale` · a `required_fix`). CED never assesses whether the objection is
philosophically strong.

Deterministic status rules (`CouncilRatificationStatus`):

| condition | status |
|---|---|
| ratification quorum not met (`0 < valid < quorum`) | `ratification_quorum_failed` |
| no valid verdicts returned | `ratification_failed` |
| ≥ 1 schema-valid **critical** blocking objection | `repair_required` (answer withheld; objection attributed in audit) |
| caveats (or non-critical objections) but no critical block | `ratified_with_caveats` |
| quorum met, no caveats, no critical block | `ratified` |

Key guarantees (proven in `tests_dialogues/test_council_ratification.py`):
an ACCEPT majority **cannot** override one schema-valid critical block; CED
**never fabricates an ACCEPT**; provider timeouts / invalid JSON / schema errors
/ rate-limits / missing keys are **audited honestly** and never silently
accepted; every objection is **attributed** to the exact provider that raised it;
the ratification task is minimal (only the final synthesis + rubric + schema — no
scores/leaderboard/audit internals). `repair_required` uses the safe Option A
(mark blocked/unresolved with attributed metadata; no automatic semantic repair).

**Reserved for V2/V3 (not implemented):** `final_synthesis_mode =
"candidate_tournament" | "hybrid"` (Final Candidate Tournament / Hybrid round
table). Constructing the CED with these raises `NotImplementedError` — no unused
tournament logic is added now.

---

## Phase 8C.2 — Registry-backed peer scoring

In a registry session **all three peer protocols now run through
`CouncilProviderRegistry`**: deliberation, council ratification, **and shadow
scoring** (move-level *and* section-level). The legacy `run_session` keeps using
the in-process `self.agents` voters (`scoring_backend = "legacy_agents"`);
`run_registry_session` uses `scoring_backend = "registry"`.

Production-shaped path: *author move → CED creates a scoring task → routed to a
peer voter provider through the registry → provider returns a structured score →
CED validates the schema → CED enforces no self-scoring → CED records missing/
failed votes honestly → CED aggregates mechanically.* **CED never generates a
semantic score itself.**

- **Voters are providers.** Each move is scored by every *available peer
  provider* except the one that **produced** it (`move.provider_id`), so no
  provider scores its own output. Each `MicroScore` / `SectionScore` carries
  `author_agent_id`, `voter_agent_id`, `provider_id`, `phase`, `rubric_name`.
- **No fabrication.** A scorer that times out, returns invalid JSON, or fails
  schema validation leaves the score **missing** (recorded in
  `failed_score_tasks` / `section_scores_failed`) — never a zero.
- **Statuses** (`sync_gate` / leaderboard): `complete` (all valid) · `partial`
  (some valid) · `failed` (none valid) · `timeout` (all timed out) · `disabled`
  (`shadow_scoring_mode = off`). Section winners use only valid peer
  `SectionScore`s; a section with no valid scores stays unresolved, not invented.
- **Deterministic.** Score tasks have stable ids
  (`stask_<hash(session|kind|target|voter|section|slot)>`); same session + same
  mock setup → identical move ids, score-task ids, valid scores, `scores_by_phase`,
  leaderboard ranking, section winners and audit counters — **independent of
  async provider latency**.
- **Minimal awareness.** A scoring task carries only the output to score + the
  rubric; never leaderboard/scores/coverage/task_log/audit internals.
- Audit (`audit_summary["scoring"]`): `scoring_backend`, `scoring_mode`,
  `scores_expected/collected/failed`, `failed_score_tasks`, `scores_by_phase`,
  `section_scores_collected/failed`, `self_scoring_violations`,
  `scoring_provider_status_summary`, `leaderboard_status`.

This **completes the registry-backed mock council path** — deliberation,
ratification and scoring are all peer-driven through the registry — before any
real provider adapter is wired in.

---

## Phase 9A — Offline-first real provider adapter

`offline_provider_adapter.py` proves that a **real-shaped** provider adapter —
built exactly like a live Anthropic / OpenAI / Gemini adapter would be — plugs
into `CouncilProviderRegistry` and a full `run_registry_session` **without
changing the CED protocol**. It runs **entirely offline**: no real API call, no
real API key, no `.env` read/write — the provider's "response" comes from a
fixture / canned-response transport.

The adapter has the real-adapter shape, with **one swappable seam** (the
transport's `send`) that becomes the live network call later:

```
_build_request(task, agent_state)  →  ProviderRequest      # Messages-API request
transport.send(request, ...)        →  provider envelope    # the ONE live/offline seam
_extract_text(envelope)             →  str                  # content[0].text
            ↓
provider_registry.parse_and_validate_move(...)              # EXISTING validation, unchanged
```

The extracted text flows through the **existing** `parse_and_validate_move`, so
JSON repair, schema validation, the no-fabrication rule, and the universal
`{"content": ..., "confidence": ...}` move envelope are all preserved. The
adapter **never** interprets scores or verdicts — it returns provider output;
**CED governs**.

- **Same task types as registry mode.** Deliberation moves, move-level scoring,
  section-level scoring, and council ratification verdicts all work, because the
  adapter is task-kind-agnostic (the scripted offline transport reuses the
  in-process content engine for full-session determinism; canned envelopes cover
  the focused contract tests).
- **Honest failures, no fabrication.** Offline analogues of live exceptions map
  to honest statuses: timeout → `timeout`, 429 → `rate_limited`, refusal
  (`stop_reason: "refusal"`) → `error`, malformed/missing fixture → `error`,
  disabled/placeholder key → `missing_key`. A failed task yields **no move** —
  never a fabricated score or verdict.
- **Invalid JSON is rejected, not accepted.** A fixture whose text is not JSON →
  `invalid_json`; valid JSON whose `content` is not an object → `schema_error`.
- **Faithful request.** `ProviderRequest.to_messages_kwargs()` is exactly the
  payload a live `client.messages.create(...)` expects — `model =
  claude-opus-4-8`, adaptive thinking, **no** `temperature` / `top_p` /
  `budget_tokens` (the opus-4-8 surface). Minimal awareness: the request is built
  only from the task (question + CED-scoped context + schema), never from agent
  internals or any scoreboard.
- **No real key, ever.** The adapter reads as available via a clearly-fake
  sentinel (`OFFLINE_FIXTURE_KEY`); it never touches `.env` and never prints a
  key.
- **Live calls remain disabled.** Going live is a one-line transport swap
  (implement `send` → `client.messages.create(**request.to_messages_kwargs())`)
  and is **deferred until explicitly approved**. Phase 9A ships offline only.

Proven in `tests_dialogues/test_offline_provider_adapter.py` (25 tests):
registry registration, valid `ProviderResponse` from fixtures, every task kind,
invalid-JSON / schema-error handling, honest failure statuses, no fabricated
scores, a full `run_registry_session` driven by offline adapters
(`execution_mode = registry`, `scoring_backend = registry`,
`self_scoring_violations = 0`, leaderboard `complete`), and offline adapters
mixed with the existing scripted mocks.

> **Agents judge epistemic quality. CED governs the protocol.** The offline
> adapter changes *where the provider text comes from*, nothing about how CED
> scores, ratifies, or aggregates.

### Still deferred (future)
- **Live single-provider smoke** — see **Phase 9B** below: a manual, doubly-gated,
  opt-in one-provider live call now exists (`scripts/live_smoke_provider.py`).
- **Live council** — driving a full `run_registry_session` over live providers is
  **not** done yet (Phase 9B is one provider, one task only).
- **Retry / rate-limit policy** — Phase 9A records `rate_limited` / `timeout` /
  `error` cleanly and exposes `is_retryable_status`; no backoff loop yet.
- **Repair Option B** for ratification (runner-up + re-ratify, max 2 rounds) — currently safe Option A (blocked/unresolved).
- **Final Candidate Tournament / Hybrid** `final_synthesis_mode` — reserved for V2/V3.

---

## Phase 9B — Live smoke test (manual, opt-in)

`scripts/live_smoke_provider.py` is a **manual, opt-in, one-provider** live smoke
test — the only code path that can make a real network call. It is **doubly gated
and off by default**:

1. `CED_ENABLE_LIVE_PROVIDERS` must equal `1`, **and**
2. `ANTHROPIC_API_KEY` must be a real (non-placeholder) key.

If either gate is unmet, **no network call is made and the `anthropic` SDK is not
even imported** — the SDK is imported lazily, inside the live call only. The
script loads all config from environment variables, builds **one**
`LiveAnthropicAdapter` (reusing Phase 9A's request-build / envelope-extract /
`parse_and_validate_move` via the `_produce_raw_text` seam), sends **one** task,
and prints a **secret-free** summary: `provider_status`, `schema_valid`,
`response_length`, model + provider name. It is **one provider, one task — not a
council.**

Exit codes: `0` = ran (or disabled-by-default, the safe no-op); `2` = enabled but
key missing/placeholder (refused, no call); `3` = live call raised (message
redacted).

### Run it manually

The flag and key come from your **local shell environment only** — never from a
committed file, never from HTML/frontend.

**PowerShell:**
```powershell
$env:CED_ENABLE_LIVE_PROVIDERS = "1"
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # your local key; never commit it
.\run_live_smoke_provider.ps1
# or: .\.venv\Scripts\python.exe scripts\live_smoke_provider.py
# optional: $env:CED_LIVE_MODEL = "claude-opus-4-8"  (default); $env:CED_LIVE_MAX_TOKENS = "1024"
```

**cmd / BAT (double-click or run):**
```bat
set CED_ENABLE_LIVE_PROVIDERS=1
set ANTHROPIC_API_KEY=sk-ant-...
run_live_smoke_provider.bat
```

Both launchers check the flag and key first, **never echo the key**, and never
write it to disk. With no flag set, they print a disabled notice and exit.

> ⚠️ **Never put API keys in HTML or any frontend code.** A future dashboard must
> call the backend only; it must never hold or transmit a raw key. There is no
> HTML UI for keys, by design.
>
> ⚠️ **`.env` stays local and gitignored.** Never commit `.env` or a key. This
> script reads keys from the environment, not from any tracked file.

---

## Safety note

Do **not** commit secrets or local artifacts:

- never commit `.env` or API keys
- never commit `__pycache__/` directories or `.pyc` files

Keep these in `.gitignore`. The default pipeline makes **no** real API calls and
does not read `.env`. The **only** exception is the manual, doubly-gated Phase 9B
live smoke test (`scripts/live_smoke_provider.py`), which is opt-in via
`CED_ENABLE_LIVE_PROVIDERS=1` + a locally-set `ANTHROPIC_API_KEY`, and which never
prints or persists the key.

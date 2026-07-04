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

## Phase 8D — Chat Dialogue Continuity Layer

> **Socrates AI is no longer limited to one-shot questions. A user can continue a
> dialogue across turns using `conversation_id`. Each turn is still governed by
> CED, but agents receive only a sanitized public conversation brief, not hidden
> scoring or audit internals.**
>
> **The user experience is a normal chat. The internal process is a CED-governed
> multi-agent council.**

`conversation.py` adds a chat layer **above** `run_registry_session` (additive —
`run_session` and `run_registry_session` are untouched). A user starts a chat,
gets a `conversation_id`, and continues naturally turn by turn ("continue from
before", "why did you say that?", "what's the strongest counterargument?", "now
look at it legally", "what remains unresolved?", "give me the balanced position").

Per turn:

1. CED builds a **sanitized public conversation brief** that preserves the *full*
   dialogue flow so far — original question, prior council answer, established
   claims, caveats, objections, unresolved questions, the turn-by-turn flow, and
   the current user message — plus an instruction to **continue, not restart**.
2. The turn runs a full **registry-backed council**: role assignment → provider
   calls → peer + section scoring → council ratification → one assembled answer.
3. CED stores the **public** result and the **hidden** audit trace *separately*.
4. The user receives one clean, readable assistant response (markdown, never raw
   JSON). Statuses (`ratification_status`, `leaderboard_status`) and `caveats` /
   `unresolved_questions` come along as public fields.

**What agents receive** (public): dialogue history, sanitized brief, prior
council answer, accepted/caveated claims, prior objections, unresolved questions,
the current follow-up, the conversational direction. **What agents never
receive** (hidden): raw peer scores, leaderboard internals, provider mappings,
`task_log`, audit internals, scoring weights, private scorer identities. The
`HiddenCedTrace` is debug-only — never sent to agents and never in a normal
user-facing response (surfaced only when `debug=True`).

**Entry points** (`ConversationManager`): `start_chat(initial_message)` ·
`continue_chat(conversation_id, user_message)` · `get_chat(id)` ·
`list_chat_turns(id)` · `build_conversation_brief(id, new_user_message)`. Storage
is in-memory by default; optional JSON persistence
(`save_conversation_json` / `load_conversation_json`) is provided separately — no
database.

> **Continuity invariant.** Continuity lives in the *public* brief, never in
> hidden CED session reuse: each turn is a fresh council run whose prompt carries
> a compressed public continuation context. If a turn cannot reach quorum, the
> answer is withheld honestly and the open point is carried into the next brief —
> CED never fabricates a continuation.

**Demo** (offline/mock): `python -m backend.dialogues.demo_chat_conversation`
runs a 4-turn Greek conversation and prints, per turn, the user message, the
assistant response, the brief used, `ratification_status`, `leaderboard_status`,
caveats, unresolved questions, that the turn was registry-backed, and a
confirmation that hidden internals were never exposed. Mock providers only — **no
real API calls, no keys, no `.env`.** This phase is about continuity and
orchestration; mock answers remain template-like by design.

---

## Phase 10 — Full-reasoning prompt layer

> **Where reasoning power comes from.** An agent's reasoning strength is **not**
> produced by orchestration code — it comes from (1) a real LLM and (2) the system
> prompt + reasoning protocol that drives it. The deterministic `FakeProvider`
> **cannot reason**; no prompt makes a template think. `reasoning_prompts.py` is the
> scaffolding that makes a **real** model reason at full power at every level of the
> dialogue, delivered through the Phase 9A/9B adapter seam.

Previously the rich v1.9 council identity (`CORE_AGENT_PROMPT`) fed only the legacy
`run_session`/`FakeProvider` path, while the registry/real path sent a one-line
system prompt. `build_reasoning_system_prompt(role, phase, task_kind)` closes that
gap. For every task it composes:

- the **v1.9 council identity** (epistemic discipline, anti-sycophancy, roles);
- a **universal reasoning protocol** — *decompose → consider multiple angles →
  ground every claim (fact / inference / hypothesis / uncertainty) → steelman →
  calibrate → be specific* — tuned to exploit **adaptive thinking** (the model
  reasons in its thinking blocks; the visible answer stays clean structured JSON);
- a **role-specific** rigor directive (Socrates targets the load-bearing
  assumption; Elenchus finds the single decisive defect; Synthesizer commits where
  evidence allows; …);
- a **phase-specific** depth directive, so *every* dialogue level is demanding;
- for **evaluative** tasks (move/section scoring, ratification) a
  **judge-the-output-not-the-author** anti-sycophancy / anti-herding directive —
  reinforcing the peer-scoring invariant.

`OfflineProviderAdapter._build_request` now sends this prompt, so the **live
adapter inherits it** — when a real key is connected (gated, opt-in), the council
reasons at full power. Invariants are untouched: minimal awareness (the prompt is
static role/phase guidance, no scores/leaderboard/task_log), peer scoring, no
fabrication. Proven in `tests_dialogues/test_reasoning_prompts.py`.

> **Honest caveat.** With mock providers this changes nothing observable — the
> mock ignores the system prompt. The reasoning gain is real **only with real
> models**, and no capability claim may be drawn from mock runs (see `RESEARCH.md`).

---

## Phase 11 — Real-agent (live council) readiness

`live_providers.py` is the single switch that lets the **whole council**
(deliberation + ratification + peer scoring) run on **real LLM agents** — or stay
fully offline/mock. Same production-shaped path either way:

```python
from backend.dialogues import build_council
ced, mode = build_council()          # mode == "mock"  (offline default)
final = asyncio.run(ced.run_registry_session(question, session_id="..."))
```

Real agents engage **only when doubly gated** (exactly like the Phase 9B smoke):

1. `CED_ENABLE_LIVE_PROVIDERS == "1"`, **and**
2. `ANTHROPIC_API_KEY` is a real (non-placeholder) key.

```powershell
$env:CED_ENABLE_LIVE_PROVIDERS = "1"
$env:ANTHROPIC_API_KEY = "sk-ant-..."          # local only; never commit
$env:CED_LIVE_MODELS = "claude-opus-4-8,claude-sonnet-4-6"  # optional: per-seat models
# now build_council(...) returns mode == "live"
```

Otherwise `build_council` returns a deterministic **mock** council — the default.
Each real seat is a `LiveAnthropicAdapter` registered in the same
`CouncilProviderRegistry` the council already uses, so deliberation, council
ratification, and peer scoring all run on real models, each agent driven by the
**Phase 10 full-reasoning prompt**.

**Guarantees** (proven in `tests_dialogues/test_live_providers.py`):

- **No network call at build time** — live seats are *constructed but never
  invoked*; the `anthropic` SDK is imported lazily, only on a real call.
- Config comes from **environment variables only** — never reads/writes `.env`,
  never hardcodes or prints a key.
- The default is offline mock; **nothing live happens until you set the flag and a
  real key**, and even then only when you actually run a session.
- All invariants hold unchanged: full-reasoning prompt, minimal awareness, peer
  scoring (judge-not-author), no fabrication, quorum.

> **Diversity.** With one model, seats differ by the role each is assigned per
> phase; for genuinely diverse agents set `CED_LIVE_MODELS` to multiple models.
> `scripts/live_smoke_provider.py` remains the separate single-provider smoke.

When you connect real agents, validate them **offline-first** (record real
responses once, replay deterministically) before any live council run — see
`RESEARCH.md` (R2) for the matched-compute study that tells you whether the
council actually beats a strong single model.

---

## Phase 12 — Live council hardening (proven on real models)

The first real live runs (gated, Haiku seats) completed a **full multi-agent
Socratic dialogue end-to-end** — all six deliberation phases, council
ratification, and a populated 5-section answer. Getting there surfaced a set of
mock-vs-real gaps, each fixed and locked in by offline regression tests
(`tests_dialogues/test_live_hardening.py`):

| Live symptom | Root cause | Fix |
|---|---|---|
| `schema_error` / free-form content | real models don't know the expected shape (mock did) | **per-task content directives** in `reasoning_prompts.py`: synthesis (exact 5 section names), peer scoring (exact 7 `ScoreBreakdown` dims), ratification (exact verdict shape) |
| `invalid_json: Extra data` | models append prose after the JSON object | parser uses `raw_decode` — first JSON object wins, trailing text ignored (schema still enforced) |
| `invalid_json: Unterminated string` | 2048 max_tokens truncated rich (Greek) answers | `DEFAULT_MAX_TOKENS = 8192` |
| `400 adaptive thinking not supported` | thinking sent to non-Opus models | `supports_adaptive_thinking()` — Opus-4.x only |
| `timeout` on long reasoning | 30s registry budget | 180s per call (`CED_LIVE_TIMEOUT`), SDK timeout aligned |
| empty final answer | assembly needs peer scores; live scoring is finicky | **`assembly_fallback`** (live only): a section with no valid scores deterministically uses a real synthesis draft — never fabricated, never empty. Default stays strict (`unresolved`) |
| transient 429 / timeout kills a seat | no retry | **bounded deterministic retry** (`CED_LIVE_RETRIES`, default 1; fixed delay, transient-only — never retries schema/auth/credit errors). The registry per-task budget covers all attempts |

**Runners:** `scripts/live_dialogue.py` (gated live|mock full-dialogue runner with a
per-phase trace and full failure diagnostics) and `scripts/diagnose_connectivity.py`
(no-key DNS/TCP/TLS probe). A `400 "credit balance is too low"` from the API is an
**account** issue (Plans & Billing), not a code failure — the runner reports it
verbatim.

> The permanent invariant is intact throughout: the fallback only *mechanically
> selects* a real agent draft (stable `draft_id` order, `score_count = 0` recorded
> honestly); CED still never fabricates content, scores, or verdicts.

---

## Phase 13 — Self-Improvement Layer

> **The system gets better the more it is used** — mechanically, measurably, and
> without violating a single invariant. CED *governs* its own improvement; it
> never judges content, and nothing changes semantically without external proof.

Three subsystems (all optional — `None` = behavior unchanged; all offline):

**A. Seat health (operational)** — `SeatHealthTracker` learns each provider
seat's reliability from the CED-owned `task_log` (content-blind): schema
failures, timeouts, rate limits. It mechanically **quarantines** chronically
failing seats (evidence-gated: ≥6 tasks and ≥50% failures), **ranks** seats for
selection (unknown first, then most reliable), and emits **config
recommendations** tied to the observed failure mode ("frequent timeouts → raise
`CED_LIVE_TIMEOUT`"). JSON persistence; deterministic.

**B. Epistemic lessons (knowledge)** — `EpistemicLessonStore` distills each
**ratified** session's PUBLIC outcome (core answer, final verdict, caveats,
decisive objections — the same material the chat brief exposes; never scores or
identities) into a `Lesson`. New dialogues on related questions receive the
top-k relevant lessons as `lessons_from_prior_dialogues` in deliberation
context, so the council **builds on its own past work** instead of restarting.
Unratified sessions teach nothing, by design.

**C. Protocol evolution (measured)** — `backend/evaluation/protocol_evolution.py`
makes protocol change *earn its way in*: a variant (config/prompt/council shape)
is evaluated on **external-truth** tasks via the Dialectic Delta and **promoted
only if it beats the incumbent by a pre-registered margin** (default +2%
absolute accuracy). Anything less retains the status quo. Mock noise can never
promote anything; a real promotion decision requires live/recorded runs (gated).

```python
from backend.dialogues import build_council, EpistemicLessonStore, SeatHealthTracker
store, health = EpistemicLessonStore(), SeatHealthTracker()
ced, mode = build_council(lesson_store=store, seat_health=health)
# ... run sessions; ratified outcomes feed future dialogues; telemetry accrues
store.save("lessons.json"); health.save("seat_health.json")
```

**D. AI-in-the-loop learning (`ai_learning=True`)** — the learning itself becomes
intelligent, with CED still governing:

- **AI-authored lessons** (`LESSON_DISTILLATION`): at session end a council seat
  — through the same registry adapters (mock = deterministic, live = real model)
  — *authors* the lesson: `insight`, `transferable_principle`, `pitfalls`. CED
  validates the schema; the mechanical public facts remain the backbone; the
  audit records `lesson_distilled_by: council`.
- **Process meta-reflection** (`PROCESS_REVIEW`): a seat reviews the council's
  OWN process this dialogue (what worked / what failed / one concrete advice) —
  and future sessions receive it as `process_lessons_from_past_dialogues`. The
  council literally coaches its future self.
- **Honest fallback:** any AI failure (timeout/schema) falls back to the
  mechanical extractor — `lesson_distilled_by: mechanical`, nothing fabricated.
- **Failure telemetry:** seat health now also ingests **failed** sessions —
  exactly where the reliability signal lives (the quorum-failure culprit is
  identified mechanically).

Hooks are failure-isolated: a broken store can never take down a dialogue
(`self_improvement_error` is recorded in the audit instead). Judging tasks
remain untouched — lessons appear only in deliberation context.

---

## Phase 14 — Adaptive dialectic, semantic retrieval, topic skill

**Confidence-Adaptive Dialectic.** The dialectic now *escalates where the risk
is*. The trigger is purely mechanical (mean confidence of the initial responses —
CED-owned metadata): uniformly **high** confidence (≥ 0.80) is exactly where
herding hides, so the elenchus receives a **devil's-advocate mandate** ("construct
the strongest case AGAINST the emerging consensus — but do not manufacture a fake
objection if none exists"); uniformly **low** confidence (≤ 0.45) yields an
**uncertainty-mapping mandate** (map what is unknown instead of forcing a
verdict). The trigger state is audited (`adaptive_dialectic`).

**Semantic lesson retrieval** (`ai_learning=True`): a keyword prefilter proposes
candidate lessons, then a council seat *selects which ones genuinely transfer*
to the new question (`LESSON_RELEVANCE`; surface overlap ≠ transfer). Resolved
once per session and cached; honest keyword fallback on any failure; the audit
records `lesson_retrieval: council | keyword`.

**Per-topic seat skill** (`TopicSkillTracker`, optional): peer scores aggregated
by (seat, topic) via the existing `classify_topic` — which seat is actually good
at what. Like the leaderboard it is **CED-owned analytics, hidden from agents**
(never in any prompt/context), used for seat selection and operator reports;
JSON persistence with the standard interpretation warning.

---

## Phase 15 — The Living System

What makes the system *alive* rather than merely reactive:

**1. Curiosity — `OpenQuestionLedger`.** The system knows what it does NOT know.
Every gap a dialogue exposes becomes an **open question**: a quorum-failed
question stays open (the loudest gap), a uniform-uncertainty session flags
itself, ratified sessions contribute their `blind_spots` and caveats.
`propose_inquiries(k)` returns the system's **self-generated research agenda**
(deterministic priority: quorum failure > uncertainty > blind spot > caveat),
and when a later ratified dialogue answers an open question the ledger marks it
**resolved** with the resolving session id.

**2. Memory consolidation ("sleep") — `consolidate_lessons`.** Lessons are not
hoarded; clusters of related lessons (deterministic keyword clustering, ≥3
members) are merged into ONE deeper lesson — authored by a council seat when
`ai_learning` (`LESSON_CONSOLIDATION`: the *generalization* the individual
dialogues were each partially seeing), with an honest mechanical merge as
fallback. The store shrinks while the knowledge deepens; provenance is kept
(`[consolidated ×N]`, `distilled_by`).

**3. Homeostasis — `ced.vitals()`.** One honest snapshot of system health from a
rolling record of session outcomes: ratification rate, quorum-failure rate,
confidence trend, memory size, open questions, quarantined seats → a mechanical
`health_status` (**thriving | stable | degrading**) with actionable
recommendations. Failed sessions are recorded too — that is where the signal is.

All of it is CED-governed (mechanical triggers, PUBLIC artifacts only, honest
fallbacks, failure-isolated hooks) and fully offline-tested.

---

## Phase 16 — Autonomy & self-healing

**Autonomous inquiry — `run_inquiry_cycle(ced, max_inquiries)`.** The system no
longer waits to be asked: it takes the top open questions from its OWN ledger
and runs a full council dialogue on each. Resolutions are marked automatically,
new gaps become new open questions, lessons accumulate — curiosity feeding
inquiry feeding memory. (Costs one full session per inquiry; live only if the
caller built a gated live council.)

**Real self-healing.** Quarantine is no longer just a recommendation: seats the
`SeatHealthTracker` has quarantined are **actually excluded** from every
registry path — deliberation, peer scoring, section scoring, council
ratification, and the roster shown to agents — but **only while the council
still meets its minimum** (better a shaky seat than no quorum). Exclusions are
audited (`quarantine_excluded`).

**Diversity guard.** A second, independent herding detector: mean pairwise
keyword diversity (1 − Jaccard) of the initial responses. Near-identical answers
from "independent" seats are not independent evidence — at ≤ 0.35 diversity the
elenchus receives a `low_diversity_alert` ("find the angle every response
missed; press the shared assumption they all took for granted"). The confidence
trigger takes precedence; both signals are audited in `adaptive_dialectic`.

---

## Phase 17 — The mathematics of epistemic discipline

**Bayesian revision protocol (Reflector).** Revision is now a probability
update, not a rewrite: the reflector must state its `prior_confidence`, classify
the criticism's `evidence_force` (decisive | strong | weak | none — each with
required update semantics), and emit a `posterior_confidence` the move's
`confidence` MUST equal. An update inconsistent with the evidence force
(unchanged confidence after a decisive hit, collapse after a weak one) is named
a calibration failure.

**Confidence-disagreement signal.** The adaptive dialectic now reads a third
mechanical signal: the **variance** of initial confidences (population std).
High std (≥ 0.20) means the council disagrees about how certain to *be* — a
different thing from the mean (Phase 14) or content similarity (Phase 16). The
elenchus receives a `confidence_disagreement_mandate`: locate exactly which
premise the confident and unconfident responses treat differently, and test it.
Signal matrix now: mean (high/low) × variance × content diversity, with
deterministic precedence and one mandate per round.

**CalibrationLedger (Brier proper scoring).** Confidence must mean something:
for every synthesis draft, the seat's stated confidence is scored against the
mechanical outcome "share of the 5 sections its draft won at blind assembly" —
`brier = mean (conf − outcome)²`, `bias = mean conf − mean outcome`
(overconfident > 0). Proper scoring makes honest confidence the optimal report.
Evidence-gated recommendations ("seat X OVERCONFIDENT by +0.35 — discount its
confidence"); CED-owned and **hidden from agents** like the leaderboard; JSON
persistence (`calibration_v0`).

---

## Phase 18 — The honesty vocabulary, machine-readable

**Epistemic markers flow end-to-end.** The `EpistemicMarker` vocabulary
(established_fact | logical_inference | reasonable_hypothesis |
open_uncertainty | unsubstantiated_claim) existed since V1 but never reached
the live path. Now: deliberating agents are told the **exact vocabulary and its
confidence ceilings** (`EPISTEMIC_MARKER_DIRECTIVE`), the registry parser lifts
`content.epistemic_marker` into `move.epistemic_markers` (invalid/missing →
simply not lifted, never a rejection), and CED **checks marker↔confidence
consistency mechanically**: a move tagged `unsubstantiated_claim` at confidence
0.9 is an epistemic inconsistency — recorded in the audit
(`epistemic_consistency`: tagged / violations / ceilings), never rewritten.
Fittingly, the check immediately caught the mock's own Socratic opening
(open_uncertainty @ 0.7 > 0.55).

**Role exemplars (form, not topic).** Every role's prompt now carries one
compact exemplar of an excellent move — a gold-standard Socratic question,
objection, evidence check, reconstruction, revision-with-arithmetic, verdict —
each explicitly marked "imitate the FORM, not the topic" (deliberately
domain-neutral to avoid topical overfit). Few-shot form guidance is the highest
-leverage prompt technique available offline.

**Pre-mortem.** The reasoning protocol gains its closing step: *"what will the
council's best critic say about THIS move? If you can already see the flaw, fix
it now — never ship a move you can already refute yourself."*

---

## Phase 19 — Ratification Repair, Option B

The long-deferred capability lands: instead of only *blocking* on a critical
ratification objection (Option A — still the constructor default), the CED can
now **repair and re-submit** (`ratification_repair="runner_up"`, enabled by
default in `build_council`):

1. The council critically blocks specific sections (schema-valid objections
   with `target_section` + `required_fix`).
2. CED mechanically swaps each blocked section for its **runner-up draft** —
   next by peer-score ranking, or deterministic `draft_id` order when no scores
   exist (the same rule as the assembly fallback). Never a semantic choice.
3. The **council ratifies again**. Bounded by `MAX_RATIFICATION_ROUNDS` (2);
   already-tried drafts are never re-offered for the same section.
4. If no runner-up exists or rounds run out, `repair_required` stands and the
   answer is withheld — CED **never overrides a block**.

Every step is audited (`ratification_repair`: mode, rounds_used, per-repair
provenance `from_draft → to_draft → via`, and the council's status per round).
The invariant holds: agents judge (the block, the re-ratification, the peer
scores that order the runner-ups); CED only governs the protocol.

---

## Phase 20 — Phase Rescue

The gap: a single transient failure (a timeout, a rate limit) in **any**
deliberation phase used to kill the **whole session** — discarding every
already-paid-for phase before it. `phase_retry=True` (`build_council` default)
fixes this mechanically:

- On a quorum-failed phase, CED retries **only the slots that failed** —
  exactly **once**, **rerouted** to the next available seat (never retried on
  the same one that just failed).
- Retried tasks get `attempt_index=1`, so move identity stays deterministic —
  no duplicates, no fabricated moves, every provider attempt stays in the
  `task_log`.
- If the reroute also fails (e.g. every seat is down), the phase's honest
  quorum-failure stands — CED never fabricates a rescue that didn't happen.
- Fully audited per phase (`phase_retries`: failed slots, first vs. retry
  provider ids, `rescued`).

Off by default on a bare `CEDOrchestrator` (legacy behavior unchanged);
`build_council` enables it, since real providers are exactly where a transient
hiccup should not cost an entire session's work.

---

## Phase 21 — Analytics-informed seat routing

A real collaboration/cohesion gap: `TopicSkillTracker` and `CalibrationLedger`
were ingested every session but **never read** — CED measured which seats were
good at what, then routed deliberation with plain registration-order
round-robin, ignoring its own analytics entirely. Closed:

- When a phase needs **fewer** healthy seats than are available (the common
  case — e.g. the Socratic opening is a single slot), CED now prefers the
  seats its own topic-skill + reliability data rate best for **this
  question's topic** (`classify_topic`), via `_ranked_adapters`.
- **Exploration preserved**: an unrated seat still ranks *before* a known-but-
  mediocre one — the same "give it a chance" philosophy as
  `SeatHealthTracker.rank_seats` — so a good-but-untested seat is never
  permanently starved by an early bad draw.
- **No trackers, or trackers with no data yet → byte-for-byte the pre-Phase-21
  order.** Ties are broken by Python's *stable* sort preserving registration
  order — never an arbitrary `provider_id` string sort.
- **Scope is deliberately narrow**: only *which provider* executes an
  already-assigned agent's task changes. Role assignment (`assign_roles_for_phase`
  — who plays Socrates/Critic/etc.) is completely untouched. Peer-scoring and
  ratification voter eligibility (`_eligible_score_voters`, ratification
  adapters) are **left unbiased on purpose** — every voice counts equally in
  judging regardless of topic skill.
- Audited (`seat_routing`: topic, resulting order, whether analytics
  contributed) and **hidden from agents**, like the leaderboard.

---

## Phase 22 — The Teacher Loop (self-distillation flywheel)

The council is not just an answer engine — it is a **data generator with quality
labels**. Every ratified dialogue is an endorsed demonstration; every peer-score
margin is a preference judgment. `backend/training/` turns that into a student
LLM that can re-enter the council:

```
council teaches → harvest SFT + preference data (from REAL scores)
               → LoRA fine-tune a small open model locally (NVIDIA GPU)
               → the student re-enters as a council seat
               → measured by the external-truth instruments (R1 / R3a)
               → the flywheel turns, cheaper and better each cycle
```

- **Harvest** (`TrainingCorpus`, optional `training_corpus=` on the council):
  SFT demonstrations come **only from ratified sessions** (the endorsed
  synthesis + the Socratic opening); preference pairs are **chosen = the
  peer-score winner draft's real text vs rejected = a clearly lower-scored
  draft** (margin-gated). No fabrication — the labels are the council's own
  scores and mechanical assembly. Deduped; exports `sft.jsonl` +
  `preferences.jsonl` + `manifest.json`.
- **Train** (`local_trainer`): **inert by default** — `gpu_report()` detects the
  NVIDIA GPU, `build_training_plan()` describes the run, and
  `write_training_script()` emits a self-contained, syntactically-validated
  trl/peft **LoRA SFT+DPO** script the operator runs on their own CUDA box.
  torch is lazy-imported; **nothing trains from inside the council process**;
  no keys, no network.
- **Re-enter** (`reentry_instructions()`): the trained student plugs in through
  the exact same provider transport seam the live Anthropic adapter uses, then
  deliberates and is peer-scored alongside the frontier seats — and is only
  credited with improvement once the external-truth instruments say so.

The harvest hook is failure-isolated (a broken corpus can never break a
session), and the whole package is CED-governed: agents produce, peer scores
label, CED aggregates mechanically.

---

## Phase 23 — Confidence-weighted aggregation

A real gap in the CED↔agent interaction: section winners were picked by a
**plain mean** of peer scores, ignoring the `confidence` each voter
*self-reports in that very score* (the field existed in `SectionScore` but was
unused in aggregation). A reviewer's tentative "8, but I'm not sure" counted
exactly as much as a firm "8, high confidence."

`score_weighting="confidence"` (opt-in; default `"uniform"`) makes the section
winner a **confidence-weighted mean** — `Σ(score·conf) / Σ(conf)`. It stays a
mechanical aggregation (the invariant explicitly permits weighted means); it
never silences anyone (a low-confidence vote keeps a positive weight); and an
all-zero-confidence section falls back to the plain mean (no division by zero).
The effect is audited, not hidden (`score_weighting`: mode + how many section
winners it moved vs the plain mean).

`"uniform"` is byte-for-byte the prior behavior, so this is a clean **protocol
variant** — exactly the kind of change `protocol_evolution` (Phase 13C) is built
to A/B on external truth: rather than *asserting* confidence-weighting helps, run
uniform vs confidence through the dialectic-delta and let the verifiers decide.

---

## Phase 24 — Cross-section coherence

Blind assembly picks each of the five sections **independently**, so the final
answer can stitch sections from different drafts that argue past each other — a
"Frankenstein" answer — and nothing was checking that. Two fixes, both
invariant-safe:

- **Mechanical fragmentation metric** (`assembly_coherence` in the audit): how
  many *distinct drafts* the resolved sections were stitched from
  (`fragmentation = distinct/resolved`, `single_source` flag). It is a metric,
  never a semantic judgement, and **hidden from agents** like the leaderboard.
- **Ratifier coherence directive**: the ratification prompt now tells the
  Final Evaluator that the sections were assembled section-by-section and may
  come from different drafts, and to verify they cohere as one answer (the
  stress test must challenge the same position the core answer commits to; the
  verdict must follow from it) — raising a `blocking_objection` on the
  incoherent sections otherwise. The note is **generic** (no session-specific
  data, no scores, no identities), so blind judging is preserved; it appears
  **only** on the ratification task, never on scoring or deliberation.

Now a fragmented answer is both *visible* (the metric) and *guarded* (the
ratifier is told to catch contradictions) — closing the last-mile gap where the
dialectic's per-section winners could quietly contradict each other.

---

## Phase 25 — Coherence-aware assembly (the smart part)

Flagging and guarding fragmentation is reactive. The deeper fix makes the
**assembly itself prefer coherence** — mechanically, without sacrificing
quality. The key insight: *a single draft's five sections are coherent by
construction* (one agent wrote them together); incoherence is born of mixing.

`cohesion_margin` (0–10 scale; default `0.0` = off) turns on a bounded
quality↔coherence trade:

1. Compute each draft's **global strength** — the mean of its per-section
   average scores (order-independent, deterministic).
2. For each section, among the drafts within `cohesion_margin` of the section's
   top score, take the section from the **globally strongest** draft (ties fall
   back to the score ranking).

So the answer **anchors to the strongest coherent draft** and only "borrows" a
section from another draft when that draft wins **decisively** (beyond the
margin). A section is *never* taken from a draft weaker than the winner by more
than the margin — the quality give-up is bounded and explicit. It stays fully
mechanical (peer scores + a deterministic global-strength tie-break; no
semantic CED judgement) and is audited (`cohesion_margin`, `cohesion_overrides`
— how many sections the anchor pulled off the raw score-winner).

Worked example: draft A scores 8.0 on all five sections; draft B spikes to 8.3
on `core_answer` but 5.0 elsewhere. Plain assembly ships a 2-source answer
(core from B, rest from A). With `cohesion_margin=0.5`, the 0.3 core gap is
inside the margin, A is globally stronger, so all five sections come from A — a
single-source, fully coherent answer for a 0.3-point core trade. With a 0.1
margin the trade is refused (quality wins beyond the margin). Default `0.0`
leaves every prior test byte-for-byte unchanged; like confidence-weighting it is
a clean protocol variant for `protocol_evolution` to A/B on external truth.

---

## Phase 26 — Per-section corroboration reliability

The session-level `coverage_ratio` says how many scores were collected overall,
but nothing said how well **each section** of the final answer was corroborated:
a section that won on a **single** peer score (one reviewer's opinion) — or none
at all, via the assembly fallback — was indistinguishable from one backed by
several concordant scores.

`assembly_reliability` (in the audit) surfaces, per resolved section, the number
of peer scores its winning draft received, and flags the **thinly corroborated**
ones (`< WELL_CORROBORATED_MIN = 2`): `min_corroboration`, `mean_corroboration`,
`thin_sections`, `well_corroborated`. It is a mechanical count, never a
judgement, **CED-owned and hidden from agents** like the leaderboard.

This is squarely the project's epistemic-honesty ethic: the system now *knows
and reports* which parts of its answer rest on thin evidence. It even reveals an
uncomfortable truth about small councils — a **2-seat** council scores each draft
by exactly one peer, so *every* section is thinly corroborated (mean = 1.0); the
metric surfaces that instead of hiding it, and argues (mechanically) for more
reviewers when corroboration matters.

---

## Phase 27 — Penalty-flag aggregation

Voters can flag a section for real epistemic problems — `unsupported_claim`,
`logical_gap`, `overconfidence`, `missed_uncertainty`, and so on. Those flags
were parsed and stored on every score… and then **never read**. A section could
win on score and ship with unresolved flags, silently (the mock council quietly
raises `missed_uncertainty` on real sections — invisible until now).

`assembly_flags` (in the audit) aggregates the penalty flags voters raised on the
**winning** content of each assembled section: `flags_by_section` (flag → count),
`serious_flag_count`, and a `clean` bool. Only flags on the draft that *won* a
section are counted (a losing draft's flags never shipped); stylistic flags
(`vague`, `rhetorical_fluff`) are excluded from the serious count. It is a
mechanical count of the council's *own* flags — never a CED judgement — and is
**CED-owned and hidden from agents** (only flag names and counts, never scores or
identities). The council's problem-detection finally *means something*: a section
that won yet carries an `unsupported_claim` flag is now visible.

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

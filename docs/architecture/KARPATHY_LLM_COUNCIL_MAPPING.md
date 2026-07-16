# Socrates AI × Karpathy `llm-council` — Decision-Locked Architecture Mapping

> **Scope.** Architecture and implementation-planning pass only. No production
> functionality was implemented. The only file created by this pass is this
> document. See §17 for the completion attestation.

---

## 1. Repository state

| Item | Value |
|---|---|
| Repository path | `C:\Users\spirc\Desktop\Socrates-AI` |
| Is a git repo | yes |
| Current branch | `feature/openclaw-memory-ab-attestation` |
| HEAD SHA | `5ab8cdedaaf532021e89acbbde76a7a848bd2d7b` |
| Main branch | `main` |
| Worktree | **dirty** — 13 pre-existing modified files (user's in-progress OpenClaw memory/AB-attestation work); **untouched by this pass** |
| `git diff --check` | clean (only CRLF/LF advisory warnings; no conflict markers, no whitespace errors) |

Pre-existing modified files at start of pass (NOT authored or touched here):

```
 M backend/dialogues/openclaw_identity/__init__.py
 M backend/dialogues/openclaw_identity/governed_system.py
 M backend/dialogues/openclaw_identity/memory_evidence_binding.py
 M backend/dialogues/openclaw_identity/revision_registry_governed.py
 M backend/dialogues/openclaw_identity/revision_transaction_governed.py
 M docs/openclaw_memory_lessons/AGENT_LESSON_AB_ATTESTATION.md
 M docs/openclaw_memory_lessons/G4_MEMORY_LIFECYCLE_BINDING.md
 M docs/openclaw_memory_lessons/OPERATOR_GUIDE.md
 M scripts/openclaw_attest_lesson_ab.py
 M tests_dialogues/test_openclaw_lesson_ab_attestation.py
 M tests_dialogues/test_openclaw_lesson_ab_attestation_provenance.py
 M tests_dialogues/test_openclaw_lesson_ab_experiment_manifest.py
 M tests_dialogues/test_openclaw_memory_evidence_binding.py
```

Relevant local branches (many): the canonical work lives on `main` and on the
`feature/openclaw-*`, `feature/socrates-full-v1`, `feature/micro-socratic-kernel-v1`,
`feature/external-self-consultation-v1` lines. The **`ced-graph-v0…v10`** branch
family is a *separate, older reasoning engine* (see §4, "multiple families").

**Karpathy revision inspected:** `karpathy/llm-council`, default branch `master`
(GitHub tree at HEAD as of this pass). No `LICENSE` file present; repository
`license.spdx_id` is empty; README states it is "provided here as is",
"99% vibe coded", explicitly unsupported. **Licensing note in §12/§17.**

---

## 2. Files and tests inspected

### Socrates AI — canonical CED family (`backend/dialogues/`)
- `ced.py` (3229 lines) — `CEDOrchestrator`, per-phase role scheduler
  (`assign_roles_for_phase`, line 381), `run_session` (3211), `run_registry_session`
  (936), `vitals` (1060), audit-summary assembly (lines 1195–1323).
- `models.py` (744) — all Pydantic models + enums (read in full).
- `role_assignment.py` (103) — `stable_hash` (SHA-256), `assign_primary_roles`.
- `provider_registry.py` (543), `providers.py` (599),
  `offline_provider_adapter.py` (456), `agent.py` (204), `conversation.py` (456),
  `deliberation_tree.py`, `openclaw_receipts.py` (`AtomicReceiptStore`).
- `README.md` (1290 lines, Phases 1–28) — read in full (incl. Phases 22–28:
  Teacher Loop, confidence-weighted aggregation, coherence metric,
  cohesion-margin assembly, per-section corroboration `assembly_reliability`,
  penalty-flag aggregation `assembly_flags`, transparency→curiosity).
- Governance packages present: `openclaw_identity/`, `openclaw_memory/`,
  `openclaw_prompts/`, `openclaw_shadow/`, `openclaw_local/`,
  `openclaw_consultation/`, `openclaw_socratic_kernel/`.

### Socrates AI — second reasoning family (`backend/`, root `socrates_ai.py`)
- `backend/app.py` (FastAPI factory), `backend/api/routes_dialog.py` (SSE stream,
  line 153), `routes_claims.py`, `routes_graph.py`, `routes_epistemic.py`,
  `routes_export.py`, `routes_ced_demo.py`.
- `backend/orchestrator/` — `session.py`, `dialog_pipeline_ced.py`,
  `reasoning_loop.py`, `socratic_rotation.py`, `ced_live_writer.py`,
  `epistemic_replay.py`, `meta_socrates.py`, `structured_epistemic_parser.py`.
- `backend/epistemic/epistemic_graph.py`, `backend/epistemic_graph/`.
- `frontend.html` (434 lines, served same-origin at `/`).

### Tests run (read-only, this pass)
```
tests_dialogues/test_deterministic_roles.py
tests_dialogues/test_ced_peer_scoring_invariant.py
tests_dialogues/test_council_ratification.py
→ 36 passed in 1.96s

tests_dialogues/test_blind_assembly.py
tests_dialogues/test_deterministic_task_identity.py
tests_dialogues/test_offline_provider_adapter.py
tests_dialogues/test_live_hardening.py
tests_dialogues/test_minimal_awareness.py
tests_dialogues/test_chat_conversation.py
→ 88 passed in 5.62s          (total this pass: 124 passed, 0 failed)
```
Other invariant suites present, not re-run this pass:
`test_micro_socratic_*`, `test_external_consultation_*`.

### Karpathy `llm-council` (`master`)
- `backend/council.py`, `backend/openrouter.py`, `backend/config.py`,
  `backend/storage.py`, `backend/main.py` (all read in full).
- `frontend/package.json`, `frontend/src/api.js`, `frontend/src/App.jsx`,
  `frontend/src/components/ChatInterface.jsx`, `Stage1.jsx`, `Stage2.jsx`,
  `Stage3.jsx` (all read in full); `Sidebar.jsx` + CSS enumerated from tree.
- `start.sh`, `pyproject.toml`, `README.md`, `CLAUDE.md` (read in full).
- Discrepancy noted: `CLAUDE.md` references a `test_openrouter.py` that does
  **not exist** in the repository tree — "no automated tests" stands. A root
  `main.py` also exists alongside `backend/main.py` (not required by the brief).

---

## 3. Executive verdict

**Adopt Karpathy's progressive usability, inspectable stages and lightweight
product structure as a read-only projection over Socrates' governed execution.
Preserve CED authority, deterministic rotating roles, blind section-level
scoring, mechanical assembly, Council Ratification, strict provider identity and
immutable evidence.**

Three findings shape the plan:

1. **Karpathy is a product-layer reference, not a reasoning-authority reference.**
   Its entire backend is ~5 files with no schema validation, no receipts, no
   returned-model verification, silent model dropping, regex ranking, mutable
   JSON overwrite, and a fixed Chairman. None of that may enter Socrates'
   reasoning layer. Its *presentation* ideas (stage tabs, raw+parsed, sidebar,
   SSE progressive reveal, one-command startup, async fan-out) are exactly what
   Socrates lacks at the product edge and should adopt — adapted.

2. **Socrates already has two reasoning-loop families, and the transport/UI
   machinery Karpathy inspires is attached to the WRONG one.** The canonical,
   decision-locked engine (`backend/dialogues/CEDOrchestrator`) has **no API and
   no frontend**. The FastAPI + SSE + EpistemicGraph + `frontend.html` stack
   lives in the *other* family (`backend/` + root `socrates_ai.py`), which is a
   different, older, live-first "15-rule Constitution" engine that does **not**
   import `CEDOrchestrator` and does **not** have blind 5-section scoring,
   council ratification, or provider receipts. The adoption work is therefore a
   **new read-only projection layer over `CEDOrchestrator`**, not a reuse of the
   existing API's authority. The existing API is a *pattern donor and migration
   source*, not the target.

3. **The canonical engine is projection-ready but not projection-emitting.**
   `CEDOrchestrator` already produces everything a Council Live View needs —
   `role_history`, `task_log`, `micro_scores`, `draft_scorecards`,
   `AssembledAnswer`, `CouncilRatification`, `ProviderResponse`, immutable
   `AtomicReceiptStore` — but only as **terminal CED-owned state**, harvested
   after `run_registry_session` returns. There is **no incremental event stream
   emitted during execution**, and no versioned public projection schema. That
   gap is precisely the first coding slice (§14, §18).

---

## 4. Current Socrates architecture map

### 4.1 Canonical family — `backend/dialogues/` (decision-locked)

```
                 ┌───────────────────────────────────────────────┐
                 │              CEDOrchestrator                   │
                 │  owns ALL SessionState: roles, moves, scores,  │
                 │  drafts, scorecards, ratification, task_log    │
                 └───────────────────────────────────────────────┘
    AgentTask ▼                                        ▲ AgentMove (Pydantic)
       ┌───────────────┐   deterministic per-phase roles │
       │ SocraticAgent │◀──  assign_roles_for_phase()     │  (stateless tools)
       └───────────────┘   = f(session_id, phase, round,  │
             │                  sorted agent_ids, SHA-256) │
             ▼                                             │
   ┌───────────────────────────────────────────────────────────────┐
   │              CouncilProviderRegistry                            │
   │  minimum_providers=2, quorum_for_assembly=2, timeout=30s,      │
   │  status_summary(), no-self-scoring, no fabrication             │
   └───────────────────────────────────────────────────────────────┘
             │  LLMProviderAdapter.generate_agent_move(task, state)
             ▼
   FakeProvider (default) · OfflineProviderAdapter · LiveAnthropicAdapter (gated)
```

**Pipeline** (`DialogPhase`): `OPENING → INITIAL_RESPONSE → ELENCHUS → REFLECTION
→ RECONSTRUCTION → SYNTHESIS` → *(CED-internal)* move-level shadow scoring →
section-level scoring → blind 5-section assembly → `RATIFICATION`.

**Role family** (`AgentRole`): Socrates, Elenchus Critic, Empiricist, Maieutic
Reconstructor, Synthesizer, Reflector, Final Evaluator. Assigned per-phase,
recorded in `SessionState.role_history` (one row per `{phase, round_index,
agent_id, role}`).

**Two run modes on the same orchestrator:**
- `run_session` — legacy, uses in-process `self.agents` (`scoring_backend =
  legacy_agents`, single Final Evaluator ratification path).
- `run_registry_session` (async) — production-shaped: every phase, peer scoring
  (move + section), and **council ratification** run through the registry
  (`scoring_backend = registry`; no Final-Evaluator monarchy). Emits an
  `audit_summary` with `execution_mode`, `provider_status_summary`,
  `registry_phase_rounds`, `scoring`, `ratification_repair`, `phase_retries`.

**Above the orchestrator:** `conversation.py` (`ConversationManager`) adds chat
continuity via a sanitized public brief per turn (each turn is a fresh council
run; continuity lives in the public brief, never in hidden session reuse).

**Governance/learning layers** (all offline, all opt-in, none with write
authority over canonical profiles): self-improvement (`SeatHealthTracker`,
`EpistemicLessonStore`, `CalibrationLedger`, `TopicSkillTracker`), OpenClaw
memory lessons, identity/soul, governed self-revision, Micro-Socratic Kernel
("may question a draft, may not certify it"), External Self-Consultation
("may advise, may not execute/approve/mutate"), Deliberation Tree.

**Immutable evidence:** `openclaw_receipts.AtomicReceiptStore` — atomic
lock-guarded, verify-on-read, append-only receipt persistence, subclassed by
consultation and micro-socratic receipt stores.

**Authority/transport surface of this family:** **none.** No FastAPI, no SSE, no
frontend. Entry points are `demo*.py`, `__main__.py`, and `scripts/`.

### 4.2 Second family — `backend/` API + `backend/orchestrator/` + root `socrates_ai.py`

A **distinct, older reasoning engine** (the `ced-graph-v*` line):
- `backend/app.py` → FastAPI app, CORS `allow_origins=["*"]`, serves
  `frontend.html` at `/`.
- `routes_dialog.py`: `POST /dialog/start` spawns a background pipeline over a
  `session_manager`; `GET /dialog/{id}/stream` is an SSE endpoint that **polls
  `session.history` every 1s** and emits `turn`/`status`/`complete` events;
  plus `/socratic-rotation`, `/epistemic-graph`, `/current-best-explanation`,
  `/convergence`, `/violations`, pause/resume/stop.
- `backend/orchestrator/session.py` builds on root `socrates_ai.py`
  `DialogManager`/`DialogConfig`; `dialog_pipeline_ced.py` maintains a live
  `EpistemicGraph`; `ced_live_writer.py` turns debate output into graph nodes;
  `epistemic_replay.py` is a read-only audit-trail exporter; `meta_socrates.py`
  is a process evaluator.
- Enforces a "15-rule Constitution" (`constitution_guard.py`), classifies domain,
  auto-selects a synthesis model, requires **≥2 real API keys** (`get_api_keys`)
  — it is **live-first**, unlike the offline-first canonical family.

**Overlap with `CEDOrchestrator`:** conceptual only (both are "Socratic
councils"). **No code dependency** — `backend/api/` and `backend/orchestrator/`
do not import `backend.dialogues`. Different models, different scoring, different
ratification, different role mechanism (`socratic_rotation.py` vs
`assign_roles_for_phase`).

### 4.3 Families table (per §4 of brief)

| Family | Entrypoint | Mode | Execution authority today | Overlaps CEDOrchestrator? | Recommended role |
|---|---|---|---|---|---|
| **A. Canonical CED** (`backend/dialogues/`) | `demo*.py`, `__main__`, `scripts/`, `ConversationManager` | offline default; live doubly-gated | **Yes — the intended sole authority** | — | Keep as sole reasoning authority |
| **B. CED-Graph API** (`backend/` + `socrates_ai.py`) | `backend/app.py` (uvicorn), `frontend.html` | live-first (needs ≥2 keys) | Yes, but a *separate* engine — **not** the decision-locked one | No code link; conceptual only | **Projection / pattern donor / future migration source.** Do not grant it authority; do not wire its loop into the new UI |
| **C. Static HTML demos** (`socrates_demo.html`, `socratesAIv1.html`, `frontend.html`) | `file://` / served | demo | No | Re-implements A's determinism in JS (demo only) | Reference only; supersede with the projected Live View |

**Do not refactor or merge these paths in this task.** The plan below adds a
*new* thin projection over Family A; Family B is neither extended nor deleted.

---

## 5. Current Karpathy architecture map

```
POST /api/conversations/{id}/message[/stream]           (backend/main.py, FastAPI)
   │
   ▼  run_full_council(user_query)                       (backend/council.py)
   ├─ Stage 1  stage1_collect_responses
   │     query_models_parallel(COUNCIL_MODELS)  → asyncio.gather(query_model…)
   │     httpx.AsyncClient POST OpenRouter chat/completions   (backend/openrouter.py)
   │     ⚠ failed model → None → SILENTLY DROPPED (only content kept)
   ├─ Stage 2  stage2_collect_rankings
   │     shared anonymized labels "Response A/B/C/D" (SAME order for every judge)
   │     whole-answer ranking prompt → "FINAL RANKING:" text
   │     parse_ranking_from_text (regex \d+\.\s*Response [A-Z])
   │     calculate_aggregate_rankings (mean position, lower = better)
   ├─ Stage 3  stage3_synthesize_final
   │     FIXED CHAIRMAN_MODEL (google/gemini-3-pro-preview) free-form synthesis
   │     chairman fails → hardcoded fallback string
   └─ generate_conversation_title (gemini-2.5-flash, fallback "New Conversation")
   │
   ▼  storage.py  → data/conversations/{uuid}.json  (mutable full-file overwrite)
   │
   ▼  SSE StreamingResponse: stage1_start/complete, stage2_*, stage3_*, title, complete, error
   │
   ▼  frontend (React+Vite): api.js reader.read()/chunk.split('\n') → Stage1/2/3.jsx tabs, Sidebar
```

Config: `COUNCIL_MODELS` and `CHAIRMAN_MODEL` **hardcoded** in `config.py`
(OpenRouter IDs `openai/gpt-5.1`, `google/gemini-3-pro-preview`,
`anthropic/claude-sonnet-4.5`, `x-ai/grok-4`). Single OpenRouter key.
`query_model` default timeout 120s; **no retry, no returned-model check, no
receipt** — returns only `content` + `reasoning_details`, discards `data['model']`
and everything else. Backend on port 8001 (per `CLAUDE.md`).

Frontend (verified in source, not inferred):
- **State handling** (`App.jsx`): no reducer — one scattered
  `setCurrentConversation` per SSE event, each **directly mutating** the last
  message object inside the updater (`lastMsg.stage1 = …`, `lastMsg.loading.* =`)
  — a React anti-pattern; optimistic user+assistant messages with a fragile
  `messages.slice(0, -2)` rollback on error.
- **Hard single-turn**: `ChatInterface.jsx` renders the input form **only when
  `conversation.messages.length === 0`** — after one exchange the input
  disappears; a conversation is one question, permanently.
- **Reveal mapping reaches the client early**: `label_to_model` is delivered at
  `stage2_complete` (before Stage 3) and `Stage2.jsx` de-anonymizes
  **client-side** via `new RegExp(label, 'g')` global text replacement (unescaped
  pattern, rewrites the evaluator's raw prose for display). The extracted
  `parsed_ranking` is shown beneath so users can validate the regex parse.
- **Metadata is ephemeral**: `CLAUDE.md` states, and `storage.py` confirms,
  that `label_to_model` and `aggregate_rankings` are **not persisted** — they
  exist only in the API response / frontend memory (the exact "frontend-only
  metadata" pattern the brief rejects).
- **Markdown**: `react-markdown` v10 with default settings — raw HTML is
  **skipped** (not rendered) and a default URL transform applies, so the
  raw-HTML/unsafe-link exposure is partially mitigated by library defaults; no
  explicit sanitization policy is declared. React 19.2, Vite 7.

Startup: `start.sh` (bash only) launches backend, `sleep 2`, then frontend — no
health check, not cross-platform. Package mgmt: `uv` + `pyproject.toml` (backend),
`npm`/Vite (frontend). No automated tests in the repo (`CLAUDE.md` mentions a
`test_openrouter.py` that is absent from the tree).

---

## 6. Decision-locked invariants (confirmed against code)

| Invariant | Confirmed in |
|---|---|
| Deterministic rotating Socrates role loop; no permanent Socrates/Final Evaluator/Chairman; provider/latency cannot influence roles | `role_assignment.py` (SHA-256 `stable_hash`), `ced.py:381 assign_roles_for_phase` (pure fn, no provider input); `test_deterministic_roles.py` ✓ |
| Every assignment recorded in `role_history`; temporary role ≠ persistent identity | `models.py:718 record_role_assignment`; `AgentState.assigned_role` vs `primary_role` |
| CED is the only execution/protocol authority; agents are stateless | `SocraticAgent.execute()` stores nothing; `CEDOrchestrator` owns `SessionState` |
| Blind section-level scoring; 5 locked sections; no self-scoring; missing stays missing; no fabricated zeros; mechanical deterministic assembly | `SectionName`, `SectionScore`/`MicroScore` `_check_and_fill` reject self-scoring; `SECTION_ORDER`; `failed_score_tasks`/`section_scores_failed`; `test_ced_peer_scoring_invariant.py` ✓ + `test_blind_assembly.py` ✓. Note: Phase 23 `score_weighting="confidence"` and Phase 25 `cohesion_margin` are **sanctioned mechanical variants** (opt-in; defaults byte-identical to plain mean) — projection payloads must carry the active aggregation mode |
| Council Ratification; structural-only critical block; runner-up replacement; withhold when governance requires; full audit | `CouncilRatification`, `RatificationVerdict.is_schema_valid_critical_block` (structural), `ratification_repair` audit; `test_council_ratification.py` ✓ |
| Provider integrity: exact model, no auto-select/substitute/fallback, fail closed, verify returned model, immutable receipt, explicit status/quorum | `ProviderStatus`, `ProviderResponse`, registry `status_summary`, `AtomicReceiptStore`; **returned-model verification is a required *addition* for a live OpenRouter adapter — see §11** |
| Governance boundaries: no self-attestation/approval, no auto Memory/Identity/Soul/prompt mutation, no authority from leaderboard, no hidden CoT retention | OpenClaw governed packages; leaderboard CED-owned & hidden; `HiddenCedTrace` debug-only |

---

## 7. Detailed capability mapping table (Karpathy → Socrates)

Decisions: **ADOPT** · **ADAPT** · **REJECT** · **DEFER** · **SUPERSEDED**.

| Karpathy capability | Source | Actual behavior | Socrates equivalent | Decision | Required adaptation | Target layer | Role-loop impact | Governance impact | Receipt/event impact | Tests |
|---|---|---|---|---|---|---|---|---|---|---|
| 3-stage presentation | README, frontend | Stage1/2/3 tabs | 7 CED phases | **ADAPT** | Present the 7 Socrates phases (Contributions→Examination→Blind Review→Evidence→Assembly→Ratification→Answer), not 3 | React Live View | Must show real role loop | Read-only | Projected events | §15 streaming |
| Parallel initial responses | `query_models_parallel` | `asyncio.gather`, keep-content | registry `gather_registry_phase_round` | **ADOPT (as-is concept)** | Bounded concurrency + per-provider timeout + quorum barrier; completion order must not affect identity | Registry | None | None | Receipts per call | §15.4 |
| Anonymous review | `stage2` labels A/B/C | shared order for all judges; mapping sent to client at `stage2_complete` (pre-Stage-3) and de-anonymized client-side via unescaped regex; mapping not persisted | blind peer scoring, no roster in judge tasks | **ADAPT** | Per-evaluator deterministic permutation (§6.5); **backend-owned, persisted** reveal mapping with explicit reveal policy — never client-side regex | CED + projection | None | Anti brand-bias preserved | reveal digests in event | §15.2 |
| Whole-answer ranking | `stage2` prompt | text "FINAL RANKING" | section-level scores | **REJECT (as authority)** | May display as analytics only; never selects winners | Analytics projection | None | Must not become epistemic authority | — | §15.2 |
| Aggregate ranking | `calculate_aggregate_rankings` | mean position | `EpistemicLeaderboard` (hidden) | **REJECT (as authority)** / ADAPT for ops view | Keep CED leaderboard hidden from agents; optional operator analytics | Analytics | None | No authority from position | — | — |
| Fixed Chairman | `CHAIRMAN_MODEL` | one model synthesizes+certifies | mechanical assembly + Council Ratification | **REJECT** | Synthesizer may assemble a candidate; may not certify alone | CED | Final Evaluator rotates; no monarchy | Core governance line | Ratification audit | §15.3 |
| OpenRouter gateway | `openrouter.py` | single key, no model check | provider adapter seam | **ADAPT** | Strict `OpenRouterAdapter` behind `CouncilProviderRegistry` (§11) | Provider adapter | None | Provider integrity | Receipt + returned-model check | §15.4 |
| async httpx client | `openrouter.py` | `httpx.AsyncClient` per call | adapter transport seam | **ADOPT** | Reuse client/pooling; keep the one swappable `send` seam | Provider adapter | None | None | latency in receipt | §15.4 |
| `asyncio.gather` | `query_models_parallel` | unbounded gather | registry round gather | **ADAPT** | Add bounded concurrency + cancellation + rate-limit classification | Registry | Latency-independent results | None | per-task receipts | §15.4/15.5 |
| Provider timeout | `query_model(timeout)` | 120s, then None | registry `provider_timeout_seconds` | **ADOPT** | Per-provider deadline → explicit `timeout` status, not disappearance | Registry | None | No fabrication | `timeout` status event | §15.4 |
| Provider failure handling | try/except→None | **silent drop** | status metadata, no fake move | **REJECT** | Failed provider stays a visible failed participant with missing result | Registry | None | Auditability | `provider_call.failed` event | §15.4 |
| Structured outputs | none | free text | Pydantic `AgentMove` + schema | **SUPERSEDED** | Socrates already strictly validates; keep | CED | None | Schema gate | validated-object digest | existing |
| Regex ranking parser | `parse_ranking_from_text` | brittle regex | structured `SectionScore` | **REJECT** | No regex parsing of authority-bearing output | — | None | No silent misparse | — | — |
| SSE endpoint | `/message/stream` | stage-level SSE | none on canonical family | **ADAPT** | New SSE over **projected canonical events** with sequence/replay/heartbeat (Slice 2) | FastAPI transport | Roles come from ledger, not UI | Read-only | Public projection events | §15.5 |
| Frontend SSE parser | `api.js` | `chunk.split('\n')`, no buffer | none | **REJECT (rewrite)** | Buffered line assembly, `Last-Event-ID`, idempotent reducer | React | None | None | idempotent on dup delivery | §15.5 |
| Progressive assistant state | `App.jsx` | scattered per-event setState with **direct mutation** of the last message; optimistic `slice(0,-2)` rollback | none | **ADAPT** | Explicit reducer/state machine (IDLE→…→COMPLETED/FAILED), projection-only, idempotent on duplicates | React | Display only | Read-only | — | §15.5 |
| Response tabs | `Stage1.jsx` | per-model tabs | `section_drafts`, moves | **ADOPT** | `AgentContributionTabs` from real moves/drafts | React | Shows agent+role | Read-only | receipt drawer | §15 |
| Peer-review tabs | `Stage2.jsx` | per-model rankings | `draft_scorecards` | **ADAPT** | `PeerReviewTabs` from section scores + coverage/quorum | React | Reviewer identity via reveal policy | Blindness preserved | reveal after close | §15.2 |
| Raw + parsed display | frontend | raw text only | `ProviderResponse.raw_text` + `AgentMove` | **ADOPT** | Raw (inspect-only) vs Validated Pydantic (authoritative); only validated drives scoring | React + CED | None | Only validated is authoritative | raw + validated digests | §12 |
| Conversation sidebar | `Sidebar.jsx` | JSON list | `ConversationManager` | **ADOPT** | Sidebar over conversation projection (Slice 5) | React + projection | None | Non-authoritative | — | §15 |
| JSON storage | `storage.py` | mutable overwrite | in-memory + optional JSON; `AtomicReceiptStore` | **ADAPT** | Use for demo/fixtures/export only; canonical = append-only ledger + receipts (§8) | Storage | None | Not canonical history | append-only | §8 |
| Auto-title | `generate_conversation_title` | LLM, fallback string | none | **ADOPT** | Non-blocking, auxiliary, deterministic fallback; never affects reasoning | Projection | None | Non-authoritative | — | — |
| React/Vite | frontend | Vite SPA | `frontend.html` (family B) | **ADOPT** | New Council Live View app; do not reuse family-B authority | React | Shows role loop | Read-only | — | — |
| Markdown rendering | react-markdown v10 | renders model text; library defaults already skip raw HTML + apply URL transform (no explicit policy declared) | `AssembledAnswer.full_text()` | **ADAPT** | Declare an explicit sanitization policy (raw HTML off, safe-link allowlist, size limits) rather than relying on library defaults (§12) | React | None | Injection surface | — | §12/§15.6 |
| start script | `start.sh` | bash, `sleep 2` | `run_*.ps1/.bat` | **ADAPT** | `scripts/dev.ps1` + `dev.sh` with real health-poll, clean stop | Scripts | None | None | — | — |
| uv / pyproject | `pyproject.toml` | uv | `requirements.txt` | **DEFER** | Optional; keep current tooling unless a migration is chosen | Build | None | None | — | — |
| Hardcoded models | `config.py` | literals | env-gated `CED_LIVE_MODELS`, allowlist | **REJECT** | Exact requested model; no auto-substitution; fail closed | Config/adapter | None | Provider integrity | requested+returned recorded | §15.4 |
| Single-turn context | messages=[query] + `ChatInterface.jsx` | one turn — the UI even **removes the input form** after the first exchange | `conversation.py` public brief | **SUPERSEDED** | Socrates already carries multi-turn continuity | CED | None | Sanitized brief only | — | existing |
| Frontend-only metadata | `storage.py` + `CLAUDE.md` ("metadata is ephemeral") | `label_to_model` + `aggregate_rankings` never persisted; exist only in API response / UI memory | reveal mapping + analytics must be backend-owned | **REJECT** | Canonical reveal mapping and analytics live in the ledger/receipts; the UI only projects them | CED + ledger | None | Auditability; reveal policy enforceable | mapping digests recorded | §15.2/§15.6 |
| CORS `*` | `main.py`/`app.py` | Karpathy actually restricts to localhost:5173/3000; Socrates family B uses `*` | family B `allow_origins=["*"]` | **ADAPT** | Restrict any new transport to known frontend origin(s); tighten family-B `*` | FastAPI | None | Trust boundary | — | §12 |

---

## 8. Role-loop preservation map

| Concern | Rule | Enforcement in target design |
|---|---|---|
| Who plays each role | `assign_roles_for_phase(state, phase, round)` — pure fn of `session_id + phase_index + round_index + sorted agent_ids + SHA-256` | Frontend/API **never** compute roles; they render `role_history` (or its ledger projection) |
| No permanent Socrates / Final Evaluator / Chairman | rotation offset per session; ratification is council-wide in registry mode | UI must show rotation across rounds (§6.2 example), derived from canonical data only |
| Provider/latency independence | roles assigned before any provider call; move ids from stable task identity, not async order | `run.started`/`role.assigned` events emitted from the deterministic plan, not from completion order |
| Temporary role ≠ identity | `AgentState.assigned_role` (phase) vs `primary_role` (session); persistent identity in OpenClaw layer | Reveal policy separates *anonymous_subject_id* / *real_subject_agent_id*; role labels never overwrite persistent agent identity |
| Auditability | one `role_history` row per `{phase, round_index, agent_id, role}` | `RoleHistory` UI component is a pure projection; SSE replay must be **idempotent** (no duplicate canonical role rows) |

The display contract: **Karpathy-style UI presents the phases; Socrates'
deterministic role loop governs who performs each phase.**

---

## 9. Event Ledger and SSE map

### 9.1 Reality check
There is **no append-only Event Ledger on the canonical family today.**
`CEDOrchestrator` accumulates terminal CED-owned state (`role_history`,
`task_log`, `moves`, `micro_scores`, `draft_scorecards`, `council_ratification`,
`registry_rounds`) and returns a `FinalResponse` with an `audit_summary`. The
only append-only *evidence* primitive that exists is
`openclaw_receipts.AtomicReceiptStore` (per-receipt files). The SSE that exists
(family B, `routes_dialog.py`) polls `session.history` and is **not** wired to
`CEDOrchestrator`. **Do not represent the full ledger→projection fan-out as
already implemented — it is the target (§13), not the present.**

### 9.2 Event mapping deliverable

| CED occurrence | Current source in Socrates | Canonical event? | Public SSE projection? | Required payload | Authority owner | Idempotency identity | UI component |
|---|---|---|---:|---|---|---|---|
| session created | `SessionState` ctor / `ConversationManager.start_chat` | yes | yes | `session_id, question, created_at` | CED | `session_id` | ConversationSidebar |
| run started | `run_registry_session` entry | yes | yes | `run_id, session_id` | CED | `run_id` | CouncilLiveView (STARTING) |
| role assigned | `assign_roles_for_phase` + `record_role_assignment` | yes | yes | `phase, round_index, agent_id, role` | CED | `(run_id, phase, round_index, agent_id, role)` | RoleHistory / CouncilTable |
| phase started | phase methods in `ced.py` | yes | yes | `phase, round_index` | CED | `(run_id, phase, round_index)` | CouncilLiveView |
| task created | `AgentTask` + `TaskLogEntry` | yes | derived | `task_id, task_kind, agent_id, slot, attempt, schema_name, context_hash` | CED | `task_id` (stable) | AgentContributionTabs |
| provider requested | registry dispatch | yes | derived | `task_id, provider_id, requested_model` | CED/Registry | `(task_id, provider_id, attempt)` | ProviderStatusPanel |
| provider completed | `ProviderResponse(status=ok)` | yes | yes | `task_id, provider_id, returned_model, latency_ms, receipt_digest` | Registry | `response_id`/`(task_id,provider_id,attempt)` | ProviderStatusPanel / ReceiptDrawer |
| provider failed | `ProviderResponse(status≠ok)` | yes | yes | `task_id, provider_id, status, failure_category` (no secrets) | Registry | `(task_id, provider_id, attempt)` | ProviderStatusPanel |
| move validated | `parse_and_validate_move` → `AgentMove` | yes | yes | `move_id, task_id, agent_id, role, phase, confidence, raw_digest, validated_digest` | CED | `move_id` (stable) | AgentContributionTabs (Raw/Validated) |
| draft created | `SectionDraft` | yes | yes | `draft_id, author_agent_id, move_id, section names present` | CED | `draft_id` | AssemblyView |
| peer score requested | score task dispatch | yes | derived | `stask_id, target(move/section), voter_id` | CED | `stask_<hash>` | SectionScorecard |
| peer score completed | `MicroScore`/`SectionScore` | yes | yes | `score_id, section, draft_id, voter_id, overall_score, penalty_flags` (agents never see) → **projection redacts to coverage/quorum publicly until reveal** | CED | `score_id`/`stask_id` | SectionScorecard |
| peer score missing | `failed_score_tasks`/`section_scores_failed` | yes | yes | `stask_id, reason` | CED | `stask_id` | SectionScorecard (coverage) |
| quorum evaluated | `effective_quorum` checks | yes | yes | `phase/scope, expected, valid, status` | CED | `(run_id, scope)` | SectionScorecard / status |
| section winner selected | blind assembly | yes | yes | `section, selected_draft_id, average_score, score_count, variance, unresolved` + Phase 26/27 audit facts: corroboration count (`assembly_reliability`), penalty flags on winning content (`assembly_flags`) | CED | `(run_id, section)` | AssemblyView |
| assembly completed | `AssembledAnswer` | yes | yes | `answer_id, sections[], unresolved_sections[]` + `assembly_coherence` (fragmentation/single_source), `thin_sections`, `flags_by_section` | CED | `answer_id` | AssemblyView |
| blocking objection raised | `RatificationVerdict.is_schema_valid_critical_block` | yes | yes | `ratification_id, provider_id, target_section, severity, required_fix` | CED | `ratification_id` | ObjectionPanel |
| ratification vote recorded | `RatificationVerdict` | yes | yes | `ratification_id, verdict, caveat?, target_section?` | CED | `ratification_id` | RatificationPanel |
| runner-up replacement | `ratification_repair` audit | yes | yes | `section, from_draft, to_draft, via, round` | CED | `(run_id, section, round)` | RatificationPanel |
| section unresolved | `AssembledSection.unresolved` / repair exhaustion | yes | yes | `section, reason` | CED | `(run_id, section)` | AssemblyView |
| answer withheld | `repair_required` / quorum-failed non-proceeding | yes | yes | `reason, status` | CED | `run_id` | CouncilLiveView (FAILED/withheld) |
| run completed | `FinalResponse` returned | yes | yes | `run_id, ratification_status, leaderboard_status` | CED | `run_id` | CouncilLiveView (COMPLETED) |

**Which are what:** *canonical ledger events* = everything with "Canonical
event? = yes" (they are facts CED already computes); *derived public projection
events* = the redacted/coarsened forms streamed to the UI (e.g. peer scores →
coverage/quorum until reveal; provider errors → category, never raw message);
*transient UI statuses* = the UI state machine (IDLE→STARTING→…), which is a
frontend projection and controls nothing.

### 9.3 Proposed envelope — assessment

```json
{ "schema":"ced_epistemic_event_v1", "event_id":"…", "session_id":"…",
  "run_id":"…", "event_type":"…", "subject_id":"…", "actor_id":"…",
  "source_artifact_digest":"…", "payload":{}, "sequence":0 }
```

| Aspect | Verdict for Socrates |
|---|---|
| **Add** `emitted_at` (UTC, tz-aware like `models._utcnow`), `phase`, `round_index`, `schema_version` (int) distinct from `schema` name | required — role/phase context and time are first-class in CED |
| **Add** `causal_parent_id` (event that caused this) and `receipt_ref` (points to `AtomicReceiptStore` digest for provider/ratification events) | required for causal links + receipt linkage |
| **Add** `idempotency_key` explicitly (the stable identity in §9.2 col 7) rather than relying on `event_id` alone | required — enables dedupe on SSE replay |
| `sequence` | keep, but define as **monotonic per `run_id`**, gap-free, assigned at append; global order is per-run, not cross-run |
| `subject_id` / `actor_id` | keep, but for blind events `subject_id` must be the **anonymous_subject_id** pre-reveal; real id only after reveal policy opens |
| **Remove/param** `source_artifact_digest` as a single flat field | split into `raw_digest` + `validated_digest` for move events; keep one `artifact_digest` elsewhere |
| Timestamp semantics | `emitted_at` is advisory (for display); **ordering is by `sequence`, never by timestamp** (latency-independence) |
| Event identity | `event_id` = random UUID (uniqueness); `idempotency_key` = deterministic (dedupe). Two different fields, two different jobs |
| Schema versioning | version the *envelope* (`schema_version`) and each `payload` type independently; never reuse a field meaning across versions |
| Replay behavior | bounded replay from `Last-Event-ID` = last `sequence`; reducer must be idempotent on `idempotency_key` |

---

## 10. OpenRouter / provider gap analysis

| Dimension | Karpathy `openrouter.py` | Socrates requirement | Gap |
|---|---|---|---|
| requested model ID | sent in payload | exact, no auto-select | none, but must be **pinned & recorded** |
| returned model ID | **discarded** (`data['model']` ignored) | **verify == requested; fail closed if not** | **critical gap** |
| upstream provider route | not requested | record where available; allowlist for strict runs | gap |
| automatic routing | OpenRouter may reroute; not detected | **detect & fail closed** on fallback | **critical gap** |
| fallback routing | not controlled | forbid silent fallback | **critical gap** |
| timeout | 120s → None | per-provider deadline → `timeout` status | adapt |
| retry | none | bounded deterministic, transient-only (like `CED_LIVE_RETRIES`) | add |
| rate limit | caught as generic Exception | classify `rate_limited` | add |
| HTTP status | `raise_for_status` swallowed to None | map to explicit `ProviderStatus` | add |
| finish reason | ignored | capture (truncation → honest status) | add |
| token usage | ignored | record in receipt | add |
| reasoning metadata | `reasoning_details` kept | keep, but **never persist hidden CoT as authority** | adapt |
| request id / response id | ignored | record for receipt/audit | add |
| latency | not measured | `latency_ms` on `ProviderResponse` | add |
| raw-response digest | none | `raw_digest` | add |
| validated-content digest | none | `validated_digest` (after Pydantic) | add |
| receipt persistence | none | `AtomicReceiptStore` immutable receipt | add |
| secret handling | key in header, printed errors leak model+exc | **never print secrets**; redact messages | fix |
| failure category | none | explicit category enum | add |
| quorum impact | n/a (silent drop) | failed provider = visible missing participant, affects quorum | **critical gap** |

**Minimum interface for a strict future `OpenRouterAdapter`** (do **not**
implement now; subclass `BaseProviderAdapter`, one `send` seam like
`OfflineProviderAdapter`):

```
class OpenRouterAdapter(BaseProviderAdapter):
    provider_id / provider_name / requested_model / allowed_upstreams
    async _produce_raw_text(request) -> (raw_text, envelope_meta)   # the ONE live seam
    # then reuse existing parse_and_validate_move(...)
    # build ProviderResponse with: status, raw_text, parsed_move,
    #   latency_ms, requested_model, returned_model, upstream_provider,
    #   finish_reason, usage, request_id, response_id, raw_digest, receipt_ref
```

**Must fail closed (status ≠ ok, no move) when:** returned model ≠ requested;
strict route provenance missing (when required); automatic fallback occurred;
response structure invalid; receipt construction fails; provider status non-OK.
A failed call is recorded as a **visible failed participant with a missing
result** — never dropped.

---

## 11. Storage comparison

| | Karpathy | Socrates canonical (today) | Socrates target |
|---|---|---|---|
| Canonical history | `data/conversations/{uuid}.json`, **full-file overwrite** | in-memory `SessionState`; optional conversation JSON; **immutable `AtomicReceiptStore`** for evidence | **append-only Event Ledger** (per-run, monotonic seq) + receipts |
| Mutation model | mutable, last-writer-wins | receipts atomic/append-only; session state ephemeral | append-only ledger → projections |
| Role assignments / scores / ratification | none persisted structurally | in `SessionState`, terminal | ledger events |
| Timestamps | `datetime.utcnow()` (naive) | tz-aware `_utcnow()` | tz-aware, ordering by sequence |
| Projections | none | `FinalResponse.audit_summary` | session / conversation / audit / EpistemicGraph / training-trace / analytics projections |

**Decision:** Karpathy JSON may inspire **offline demo storage, deterministic
fixtures, export/import, replay packages, local dev** — never canonical
production history, roles, receipts, scores, ratification, governance lifecycles,
Memory/Identity/Soul, or EpistemicGraph state. The append-only-ledger target
(§13) is **not yet built** on the canonical family and must not be described as
existing.

---

## 12. Trust-boundary and injection analysis

Karpathy concatenates raw model outputs directly into evaluator and Chairman
prompts (`responses_text`, `stage1_text`, `stage2_text`) with no
instruction/data separation, and prints exceptions containing model
identifiers. On the rendering side the exposure is **narrower than a naive
reading suggests**: `react-markdown` v10 defaults skip raw HTML and apply a
default URL transform, and Karpathy's CORS is restricted to
localhost:5173/3000 (it is Socrates **family B** that ships
`allow_origins=["*"]`). The remaining real exposures are: prompt-level
injection through concatenated drafts/rankings, the client-side unescaped-regex
de-anonymization that rewrites evaluator prose for display, unbounded content
size, and the non-persisted reveal mapping. Required Socrates controls for any
adopted surface:

| Control | Where |
|---|---|
| Instruction/data separation; explicit untrusted-content boundaries around any provider text placed in another prompt | reasoning-prompt builders; scoring/ratification tasks already carry only output+rubric+schema (keep) |
| Structured provider outputs; schema validation before any authority use | `parse_and_validate_move` (only validated object drives scoring/assembly/objections/ratification/learning) |
| Content-size limits on raw output before embedding | new guard in adapter/projection |
| Tool-disabled evaluation; no nested delegation; authority-claim rejection | judging tasks are anonymous, minimal-context; Micro-Socratic Kernel/External Consultation cannot execute/approve/mutate |
| Secret scanning; never print keys; redact provider error messages | adapter (fix Karpathy's leaky `print`) |
| Markdown sanitization; no raw HTML; safe link handling | new React Live View renderer |
| CORS restricted to known frontend origin | any new FastAPI transport (tighten family-B `*`) |
| Forged reveal-mapping / forged receipt-reference rejection | reveal policy + receipt verification (`AtomicReceiptStore` verify-on-read) |
| No hidden chain-of-thought retained as authority; `reasoning_details` not persisted as an authoritative artifact; `HiddenCedTrace` debug-only | CED + projection redaction |

**Licensing/attribution.** `karpathy/llm-council` ships **no license** and is
explicitly unsupported/"as is". Treat the **code as all-rights-reserved**: adopt
*ideas and patterns* (uncopyrightable) and **write Socrates' own
implementation**; do not copy source verbatim. Record attribution ("inspired by
karpathy/llm-council") in the eventual module docstrings.

---

## 13. Recommended target architecture

```
User
  ↓
React Council Live View            (read-only; UI state machine is a projection)
  ↓  (SSE with sequence / Last-Event-ID / heartbeat / bounded replay)
FastAPI command + projection layer (never assigns roles / scores / ratifies)
  ↓
CEDOrchestrator                    (SOLE execution + protocol authority)
  ↓  assign_roles_for_phase()  (deterministic rotating role loop)
CouncilProviderRegistry → provider adapters (strict OpenRouterAdapter, fail-closed)
  ↓
OPENING → INITIAL_RESPONSE → ELENCHUS → REFLECTION → RECONSTRUCTION → SYNTHESIS
  ↓
Blind section-level peer scoring → Mechanical 5-section assembly → Council Ratification
  ↓
Final governed answer

    CED runtime facts (emitted DURING execution, not after)
      ↓
    Canonical append-only Event Ledger  (per-run, monotonic sequence)
      ├── Council Live View projection
      ├── Session / conversation projection
      ├── Audit projection
      ├── EpistemicGraph projection
      ├── Training-trace projection
      └── Analytics projection
```

Corrections applied to the brief's draft: (a) the Event Ledger records events
**as execution happens**, not as a post-answer step — but it **does not exist
yet** on the canonical family and must be built (Slice 1); (b) the existing
FastAPI/SSE/EpistemicGraph stack belongs to **family B** and must not be wired
in as authority; (c) ratification in registry mode is **council-wide**, not a
single Final Evaluator monarchy.

---

## 14. Incremental implementation slices

### Slice 0 — Architecture contracts
- **Goal:** define event taxonomy, public projection schemas, role display
  contract, identity reveal policy. **No runtime/provider/frontend/authority
  changes.**
- **Files:** `docs/architecture/*` + a new `backend/dialogues/projection/`
  package with **schema-only** Pydantic models (`CedEpistemicEvent`, payload
  types) and a `RevealPolicy` type. No emission yet.
- **Tests:** schema round-trip; idempotency-key determinism; envelope
  versioning. **Failure cases:** unknown event_type rejected. **Migration risk:**
  none. **Non-goals:** streaming, UI. **Rollback:** delete the package (inert).

### Slice 1 — Read-only CED event projection
- **Goal:** observe existing `run_registry_session`, emit deterministic
  read-only events into an in-memory append-only ledger; **`FinalResponse`
  byte-identical** to today.
- **Files:** `projection/event_ledger.py` (append-only, monotonic seq),
  a thin observer hook in `ced.py` that *records* (never decides). No scoring,
  role, ratification, or provider behavior change.
- **Tests:** same session → identical event sequence & final result; ordering by
  sequence not latency; cross-session isolation. **Failure cases:** hook error
  must not affect the run (failure-isolated, like `self_improvement_error`).
  **Migration risk:** low (additive). **Non-goals:** transport, persistence.
  **Rollback:** disable the hook flag.

### Slice 2 — Robust SSE transport
- **Goal:** stream projected events with sequence numbers, buffering, reconnect,
  `Last-Event-ID`, bounded replay, heartbeat, cancellation.
- **Files:** new FastAPI app under `backend/live/` (do **not** extend family-B
  `app.py`); `GET /api/v1/runs/{run_id}/stream`. Restricted CORS.
- **Tests:** monotonic sequence; chunk fragmentation; reconnect+replay; duplicate
  delivery idempotent; exactly one completion; cancellation. **Do not** use
  per-network-chunk line splitting. **Migration risk:** medium (new service).
  **Non-goals:** UI, mutation endpoints. **Rollback:** remove the router.

### Slice 3 — Council Live View
- **Goal:** contributions, role loop, peer reviews, section coverage, objections,
  assembly, ratification, final answer. Frontend **read-only** w.r.t. authority.
- **Files:** new React/Vite app (`frontend-live/`); components
  `CouncilLiveView, CouncilTable, RoleHistory, AgentContributionTabs,
  PeerReviewTabs, SectionScorecard, EvidencePanel, ObjectionPanel, AssemblyView,
  RatificationPanel, ProviderStatusPanel, ReceiptDrawer, ConversationSidebar`;
  reducer-based state machine. **Tests:** reducer idempotency on duplicate
  events; role rows never computed client-side. **Migration risk:** low
  (separate app). **Non-goals:** provider activation. **Rollback:** drop the app.

### Slice 4 — Provider receipt projection
- **Goal:** show requested model, returned model, provider, status, latency,
  token usage, receipt digest. **Never expose secrets.**
- **Files:** projection payloads for provider events; `ReceiptDrawer`. Depends on
  the strict `OpenRouterAdapter` interface (§10) — but the adapter itself is a
  **separate, later, gated** effort; this slice can project existing offline/mock
  receipts first. **Tests:** §15.4 subset (receipt verification, no secret leak).
  **Rollback:** hide the drawer.

### Slice 5 — Session and conversation projection
- **Goal:** sidebar, titles (non-blocking, deterministic fallback), previous
  runs, run inspection, export. **No mutable frontend-owned canonical history.**
- **Files:** conversation projection over `ConversationManager`; export uses the
  Karpathy-inspired JSON as a **replay/export package**, not canonical store.
  **Tests:** title fallback determinism; export/import round-trip. **Rollback:**
  remove endpoints/components.

---

## 15. File impact estimate

| Area | New | Modified | Notes |
|---|---|---|---|
| Slice 0 | `backend/dialogues/projection/` (schemas), docs | none | inert |
| Slice 1 | `projection/event_ledger.py`, observer | `ced.py` (additive hook, flag-gated) | must keep `FinalResponse` identical |
| Slice 2 | `backend/live/` FastAPI service | none in `backend/dialogues` | new transport only |
| Slice 3 | `frontend-live/` React app | none | read-only |
| Slice 4 | provider projection payloads; (later) `OpenRouterAdapter` | `provider_registry.py` (only when adapter lands, gated) | live path stays doubly-gated |
| Slice 5 | conversation/export endpoints + components | none canonical | export ≠ canonical store |

No modification to `models.py` invariants, role/scoring/ratification logic, or
governance packages is required for Slices 0–3.

---

## 16. Test plan (maps to brief §15)

- **15.1 Role loop:** identical inputs → identical `role_history`; different
  session_ids rotate Socrates; Final Evaluator not pinned; latency/UI cannot
  affect assignment; SSE replay does not duplicate canonical role rows; anonymous
  labels never replace persistent identity. *(Extends `test_deterministic_roles.py`.)*
- **15.2 Peer scoring:** no self-scoring; invalid/timeout stays missing; no
  fabricated zero; deterministic section winners; explicit quorum; reveal
  mappings don't leak early; per-evaluator ordering deterministic.
  *(Extends `test_ced_peer_scoring_invariant.py`, `test_blind_assembly.py`.)*
- **15.3 Ratification:** accept; non-critical objection; critical targeted;
  critical untargeted; runner-up replacement; missing runner-up; unresolved
  section; bounded rounds; withheld answer. *(Extends `test_council_ratification.py`.)*
- **15.4 Provider integrity:** wrong returned model; silent fallback; missing
  provenance; timeout; rate limit; invalid JSON; schema error; receipt verify;
  one failure with quorum preserved; quorum failure; no failed provider vanishes
  from audit. *(Extends `test_offline_provider_adapter.py`, `test_live_hardening.py`.)*
- **15.5 Streaming:** deterministic order; monotonic sequence; chunk
  fragmentation; reconnect; duplicate delivery; idempotent reducer; cancellation;
  provider-failure projection; exactly one completion; cross-session isolation.
  *(New, Slice 2/3.)*
- **15.6 Security:** injection inside a draft; evaluator authority claim;
  oversized response; secret-shaped data; malicious markdown; raw HTML; unsafe
  link; malformed event; forged reveal mapping; forged receipt reference. *(New.)*

---

## 17. Risks and unresolved implementation questions

1. **Two families, one name.** The biggest risk is accidentally wiring the
   existing family-B FastAPI/SSE/EpistemicGraph (built on `socrates_ai.py`) into
   the new UI and inheriting a second reasoning authority. Mitigation: new
   transport under `backend/live/`; explicitly do not import family B.
2. **Ledger emission inside `ced.py` without behavior drift.** The observer hook
   must be strictly recording and failure-isolated; a regression could reorder
   or duplicate events. Mitigation: byte-identical `FinalResponse` golden test.
3. **Reveal policy correctness.** Per-evaluator anonymization + backend-owned
   reveal must never leak `real_subject_agent_id` before close, including through
   receipt refs or causal parents. Open question: where the reveal boundary sits
   for the *operator* audit vs the *end-user* view.
4. **EpistemicGraph projection source.** The canonical family has no
   EpistemicGraph; family B does. Open question: build a fresh projection from
   CED events, or adapt family B's graph as a pure downstream projection.
5. **Strict `OpenRouterAdapter` is a separate gated effort.** Returned-model
   verification and route provenance depend on OpenRouter response fields that
   must be validated live; this stays doubly-gated and out of Slices 0–3.
6. **uv/pyproject migration** deferred; mixing `requirements.txt` and `uv` is a
   tooling decision, not an architecture one.

---

## 18. Final recommended first coding slice

> **Council Live View Foundation — Slice 0 + the schema half of Slice 1:**
> versioned, read-only CED event **contracts** (`ced_epistemic_event_v1` envelope
> with the §9.3 corrections: `schema_version`, `phase`, `round_index`,
> `emitted_at`, `causal_parent_id`, `receipt_ref`, explicit `idempotency_key`,
> split `raw_digest`/`validated_digest`) plus the append-only in-memory ledger
> and projection **interfaces** — **with no frontend, no provider changes, and no
> CED authority changes.** Emission is added behind a flag in Slice 1 with a
> byte-identical-`FinalResponse` guard.

Current code supports starting here directly: `CEDOrchestrator` already computes
every fact the contracts describe; nothing smaller is a prerequisite. The one
adjustment vs the brief's default wording is to **fold the reveal-policy and
role-display contracts into this same Slice 0**, because per-evaluator
anonymization must be specified before any peer-review event is shaped.

---

## Conclusion

Adopt Karpathy's progressive usability, inspectable stages and lightweight
product structure as a **read-only projection over Socrates' governed
execution**. Preserve CED authority, deterministic rotating roles, blind
section-level scoring, mechanical assembly, Council Ratification, strict provider
identity and immutable evidence. The reasoning engine does not change; a new,
thin, versioned projection + transport + UI is added over the canonical
`CEDOrchestrator`, and the pre-existing family-B API is treated as a pattern
donor and migration source, never as a second authority.

---

## Implementation Addendum (Slice 0 as built — supersedes §9.2 where they differ)

The §9.2 event table above is the historical *proposal*. Slice 0 was
implemented in `backend/dialogues/projection/` and hardened through three
adversarial review rounds; where the proposal and the code differ, **the
executable `contract_matrix.CONTRACT_MATRIX` and the typed `payloads.py`
models are authoritative**. See
[COUNCIL_LIVE_VIEW_FOUNDATION.md](COUNCIL_LIVE_VIEW_FOUNDATION.md). Notable
refinements the code locks in beyond the original sketch:

- **Event envelope**: `schema = ced_epistemic_event_v1`, plus per-payload
  `payload_schema` / `payload_version`; identity is **executable**
  (`derive_event_idempotency_key` from the matrix identity fields, verified
  on every draft — arbitrary keys are impossible). `event_id` is globally
  unique in the ledger; `emitted_at` must be tz-aware UTC; `causal_parent_id`
  must reference an already-recorded event in the **same session**.
- **Streams**: `session.created` is session-scoped (`run_id=None`, stream
  `session:<id>`); every other event is run-scoped (`run:<id>`). `stream_id`
  is derived, never caller-supplied; sentinel run ids are rejected.
- **Identity fields** (superseding the sketch): provider events key on
  `attempt_index` (a retry is a new attempt, not a conflict);
  `ratification_vote.recorded` keys on `(ratification_id, voter_id)` and
  carries `voter_id`; `blocking_objection.raised` keys on
  `(ratification_id, provider_id)` and carries `provider_id`.
- **Payload parity**: `draft.created` carries `sections_present`;
  `peer_score.completed` carries `score_id`/`scored_kind`/`overall_score`/
  `penalty_flags` (+ section/draft when section-scored);
  `section_winner.selected` carries `assembly_flags`; `assembly.completed`
  carries five-section refs + `flags_by_section` (resolved sections only).
  Vocabularies (sections/roles/phases/verdicts/penalty flags/statuses) are
  closed Literals with tested parity against `models.py`.
- **Receipts**: `receipt_ref` is the typed, resolvable `ReceiptRef`
  (`receipt_kind` + `request_id` + `receipt_digest`), not a bare
  `sha256:<digest>` string. Wire rule vocabulary is `required | optional |
  none`; `provider.completed` requires one, the other provider/ratification
  events allow one (runtime does not yet mint them), the rest forbid one.
- **Reveal**: per-evaluator anonymization is **run-scoped**
  (`session, run, phase, round, evaluator, purpose`) with backend-owned,
  digest-sealed, TOCTOU-safe, write-once mappings and gated reveal.

None of this changes the report's decisions; it is the ratified detail of the
first slice. The observer/emission hook (Slice 1) remains deferred and will be
a separate branch off the foundation tip, guarded by a byte-identical
`FinalResponse` test.

# Socratic Dialogues Orchestration System (V1)

A multi-agent deliberation engine. A **Council of Epistemic Deliberators (CED)**
drives a panel of stateless *Socratic Agents* through a fixed dialectical
pipeline and produces a single, ratified answer with an explicit epistemic status.

V1 ships with a **deterministic `FakeProvider`** only — no network, no API keys,
no cost. The whole architecture is exercised and tested before any real LLM is
wired in.

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

> Note: because `move_id` is a random UUID, the role rotation is deterministic by
> `session_id`, but which draft wins each section can differ between separate
> `run_session` calls. The provider itself is deterministic.

---

## Safety note

Do **not** commit secrets or local artifacts:

- never commit `.env` or API keys
- never commit `__pycache__/` directories or `.pyc` files

Keep these in `.gitignore`. V1 makes no real API calls and does not read `.env`.

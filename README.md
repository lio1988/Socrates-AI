# Socrates AI — Computational Epistemic Dynamics

A governed multi-agent reasoning system in which knowledge emerges through
structured Socratic examination, blind peer evaluation, mechanical assembly,
and council ratification.

Socrates AI is not a chatbot wrapper, and the **Council of Epistemic
Deliberators (CED)** is not a semantic judge.

> **Agents judge epistemic quality. CED governs the protocol.**

Agents produce, criticize, revise, score, and ratify structured contributions.
CED owns deterministic role assignment, task routing, schema validation, quorum,
mechanical aggregation, auditability, and governance boundaries.

---

## Why this project exists

A single language model can be fluent while remaining overconfident, incomplete,
or internally inconsistent. Simply asking several models and choosing the most
popular answer does not solve that problem: agreement is not evidence, and a
fixed “chairman” becomes an unearned authority.

Socrates AI treats knowledge as a **governed process** rather than a one-shot
response:

1. agents make independent contributions;
2. Socratic roles expose assumptions and contradictions;
3. agents revise under criticism;
4. peers score outputs under explicit rubrics;
5. CED assembles the strongest sections mechanically;
6. the council ratifies, caveats, blocks, or withholds the result.

The goal is not forced consensus. The goal is an auditable **current best
explanation** whose uncertainty, objections, provenance, and failure modes remain
visible.

---

## Permanent epistemic invariant

CED coordinates the process but does not decide philosophical or factual quality
by itself.

CED may:

- assign temporary roles;
- create and route tasks;
- validate structured outputs;
- prevent self-scoring;
- collect peer scores;
- calculate averages, variance, coverage, quorum, and deterministic tie-breaks;
- assemble sections according to protocol rules;
- record provider failures and audit metadata;
- enforce ratification and governance boundaries.

CED must never:

- fabricate a qualitative score;
- replace a missing score with zero;
- silently drop a failed provider;
- let an agent score its own output;
- treat model popularity or leaderboard rank as truth;
- grant one permanent model final authority;
- override a valid critical blocking objection;
- mutate Memory, Identity, Soul, prompts, or governance state without the
  separately governed evidence and attestation path.

If a peer score is invalid, missing, timed out, or unavailable, it remains
**missing**. The audit reports the resulting `partial`, `timeout`, `failed`,
`disabled`, or `quorum_failed` status honestly.

---

## Canonical architecture

The current canonical governed engine lives under `backend/dialogues/`.

```text
User / ConversationManager
            |
            v
+-------------------------------------------+
|               CEDOrchestrator             |
| sole execution and protocol authority     |
| roles, tasks, moves, scores, assembly,     |
| ratification, audit                        |
+-------------------------------------------+
            |
            v
Deterministic phase and role plan
            |
            v
CouncilProviderRegistry --> Provider adapters
            |
            v
OPENING
  -> INITIAL_RESPONSE
  -> ELENCHUS
  -> REFLECTION
  -> RECONSTRUCTION
  -> SYNTHESIS
            |
            v
Blind move-level and section-level peer evaluation
            |
            v
Mechanical five-section assembly
            |
            v
Council Ratification
            |
            v
Governed FinalResponse + audit metadata
```

### Authority boundaries

- **`CEDOrchestrator`** is the sole reasoning-protocol authority.
- **Socratic agents** are stateless tools: they receive `AgentTask` and return
  structured `AgentMove` objects.
- **Provider adapters** produce model output but do not decide protocol state.
- **Peer agents/providers** supply qualitative judgments.
- **CED** validates and aggregates those judgments mechanically.
- **Conversation continuity** is carried through a sanitized public brief; each
  turn remains a fresh governed council run.

The repository also contains an older `socrates_ai.py` / `backend/orchestrator/`
reasoning family and static HTML prototypes. They are historical prototypes and
pattern donors, not the canonical decision-locked engine.

---

## Deterministic rotating roles

Roles are temporary protocol assignments, not permanent model identities.

The scheduler is a pure function of:

```text
session_id + phase + round_index + sorted agent IDs + SHA-256
```

Consequences:

- Socrates rotates across sessions and rounds.
- No model permanently owns the Synthesizer or Final Evaluator role.
- Provider latency and completion order cannot affect role assignment.
- Every assignment is recorded in `SessionState.role_history`.
- A persistent agent identity remains separate from its temporary phase role.

The role family includes:

- Socrates;
- Elenchus Critic;
- Empiricist;
- Reflector;
- Maieutic Reconstructor;
- Synthesizer;
- Final Evaluator as a rotating role in legacy execution paths.

Registry-backed production-shaped execution uses **council-wide ratification**;
it does not grant a fixed Final Evaluator or Chairman monopoly.

---

## Deliberation pipeline

| Stage | Purpose |
|---|---|
| `OPENING` | Expose the load-bearing assumption with a Socratic question. |
| `INITIAL_RESPONSE` | Produce independent starting positions. |
| `ELENCHUS` | Identify contradictions, unsupported premises, and decisive gaps. |
| `REFLECTION` | Revise positions in response to criticism. |
| `RECONSTRUCTION` | Build a stronger position from what survived examination. |
| `SYNTHESIS` | Produce competing structured five-section answers. |
| Peer scoring | Evaluate moves and sections under phase-specific rubrics. |
| Blind assembly | Select section winners mechanically. |
| `RATIFICATION` | Accept, accept with caveats, or raise a blocking objection. |

The five locked answer sections are:

```text
core_answer
crucial_stress_test
blind_spots
nuance
final_verdict
```

Different drafts may win different sections. CED does not rewrite the content or
choose a winner semantically.

---

## Blind peer scoring and assembly

Peer scoring is structured, phase-specific, and non-self-referential.

Core guarantees:

- `voter_agent_id != author_agent_id`;
- invalid or timed-out scores remain missing;
- no fabricated fallback scores;
- deterministic task and move identities;
- explicit coverage and quorum;
- deterministic tie-breaks;
- scores and leaderboards remain hidden from deliberating agents.

The assembly layer selects each section from valid peer-scored drafts. The
selection is mechanical and auditable; CED does not author a replacement answer.

---

## Council Ratification

In registry-backed mode, every eligible provider returns one structured verdict:

```text
accept
accept_with_caveat
blocking_objection
```

Council Ratification is not a simple majority vote. CED:

- validates verdict schemas;
- checks quorum;
- records caveats;
- detects structurally valid critical objections;
- applies bounded deterministic protocol rules.

A valid critical objection cannot be overridden by an ACCEPT majority. Depending
on the configured governed path, a targeted block may trigger bounded runner-up
replacement and re-ratification. If no valid repair remains, the section stays
unresolved or the answer is withheld.

---

## Provider and execution modes

### Implemented on `main`

- deterministic `FakeProvider` and scripted mock providers;
- `CouncilProviderRegistry` with readiness, timeout, failure, and quorum status;
- offline-first real-shaped provider adapter and fixture transport;
- doubly gated Anthropic live smoke / live-council paths;
- registry-backed deliberation, peer scoring, section scoring, and Council
  Ratification;
- honest provider statuses such as `ok`, `missing_key`, `timeout`,
  `invalid_json`, `schema_error`, `rate_limited`, `error`, and `disabled`.

Live execution is opt-in and environment-gated. The default path remains offline
and deterministic.

### Provider integrity direction

Any future OpenRouter integration must:

- pin the exact requested model ID;
- forbid automatic model selection and silent substitution;
- forbid silent model fallback;
- fail closed when the exact model is unavailable;
- verify and record the model actually returned;
- store immutable provider receipts;
- optionally pin or allowlist the upstream provider route for strict
  reproducibility runs.

A strict OpenRouter adapter is **planned**, not implemented on the current
`main` branch.

---

## Conversation, learning, and governance

The canonical engine includes optional governed layers for:

- multi-turn conversation continuity through sanitized public briefs;
- provider-seat reliability and quarantine telemetry;
- epistemic lessons from ratified public outcomes;
- calibration and topic-skill analytics;
- open-question tracking and bounded inquiry cycles;
- deliberation-tree and revision evidence workflows where present;
- OpenClaw Memory, Identity, Soul, prompt, and revision governance bridges.

These layers do not receive unrestricted authority.

Important boundaries:

- no self-attestation or self-approval;
- no automatic Memory, Identity, Soul, or prompt mutation;
- no hidden chain-of-thought stored as an authority-bearing artifact;
- no leaderboard-based governance authority;
- failed evidence remains failed rather than being silently promoted;
- governed changes require explicit evidence, provenance, and non-self approval.

---

## Quick start

From the repository root:

```bash
pip install -r requirements.txt

python -m backend.dialogues.demo
python -m backend.dialogues "Is mathematics discovered or invented?"

python -m pytest tests_dialogues -q
```

Windows virtual environment form:

```powershell
.\.venv\Scripts\python.exe -m backend.dialogues.demo
.\.venv\Scripts\python.exe -m backend.dialogues "Is mathematics discovered or invented?"
.\.venv\Scripts\python.exe -m pytest tests_dialogues -q
```

The root launchers `run_dialogues_demo.ps1` and `run_dialogues_demo.bat` are also
available for the deterministic demo.

Do not place provider keys in source files, HTML, frontend code, or commits.

---

## Repository map

| Path | Purpose |
|---|---|
| `backend/dialogues/ced.py` | Canonical `CEDOrchestrator` and protocol flow. |
| `backend/dialogues/models.py` | Pydantic models, enums, scoring, assembly, and ratification contracts. |
| `backend/dialogues/agent.py` | Stateless Socratic agent interface and core prompt. |
| `backend/dialogues/role_assignment.py` | SHA-256-based deterministic assignment helpers. |
| `backend/dialogues/provider_registry.py` | Provider-adapter readiness, execution, failure status, and quorum. |
| `backend/dialogues/offline_provider_adapter.py` | Offline-first real-shaped adapter seam. |
| `backend/dialogues/conversation.py` | Multi-turn public-brief continuity layer. |
| `backend/dialogues/openclaw_*` | Governed evidence, Memory, Identity, Soul, prompt, consultation, and revision packages. |
| `backend/evaluation/` | External-truth and protocol-evolution evaluation tools. |
| `backend/training/` | Governed training-corpus and local training support. |
| `tests_dialogues/` | Canonical engine and governance regression suite. |
| `backend/dialogues/README.md` | Detailed technical reference and phase history. |
| `socrates_ai.py`, `backend/orchestrator/` | Legacy reasoning family; not canonical. |

---

## Current implementation status

The current `main` branch contains the governed CED reasoning engine, deterministic
role rotation, structured provider registry, registry-backed peer evaluation,
blind five-section assembly, Council Ratification, conversation continuity,
learning/telemetry layers, and governed OpenClaw attestation bridges.

The following product-layer work is still planned and must not be confused with
current functionality:

- canonical append-only Epistemic Event Ledger for the `CEDOrchestrator` family;
- versioned public event projections;
- robust FastAPI/SSE transport with replay and `Last-Event-ID`;
- React/Vite Council Live View;
- strict OpenRouter adapter with returned-model and route verification.

The existing FastAPI/SSE/EpistemicGraph implementation belongs to the older
reasoning family and is not the transport authority for the canonical CED engine.

---

## Documentation

- Start here for project identity and operating principles.
- Read [`backend/dialogues/README.md`](backend/dialogues/README.md) for the deep
  technical reference and historical phase detail.
- Read `RESEARCH.md` for evaluation methodology and claims discipline.
- Read the focused architecture and governance documents under `docs/` where
  available.

---

## Legacy prototype

The repository began as a Python/HTML multi-model Socratic dialogue application
built around `socrates_ai.py`. It supported configurable dialogue modes, console
interaction, and early scoring experiments.

That implementation remains useful historical context, but the canonical governed
engine now lives under `backend/dialogues/`.

---

## License and contributions

A repository license file has not yet been added. Add an explicit license before
relying on reuse or redistribution permissions.

Contributions should preserve the permanent invariants, add regression tests, and
clearly distinguish implemented, gated, experimental, historical, and planned
capabilities.
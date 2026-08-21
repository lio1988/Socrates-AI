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
- **Learning and self-review components** may produce advice, telemetry,
  hypotheses, or evidence. They cannot approve themselves or bypass governance.

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

## Conversation continuity

`ConversationManager` provides a normal multi-turn chat experience above the
canonical council engine.

Each user turn creates a fresh governed council run. Agents receive a sanitized
public continuation brief containing prior public answers, claims, caveats,
objections, unresolved questions, and the new user message. They do not receive
hidden peer scores, private scorer identities, task logs, provider mappings, or
other audit internals.

Continuity therefore lives in public epistemic context, not in hidden session
reuse or agent scratchpads.

---

## Governed learning — not unrestricted self-rewriting

Socrates AI contains optional learning and telemetry layers, but “self-learning”
does **not** mean that the system may silently rewrite itself.

### Council-level learning

Implemented learning-oriented components include:

- **Epistemic lessons** distilled from ratified public outcomes;
- **process lessons** that record bounded advice about how a dialogue was run;
- **open-question tracking** for unresolved gaps and future inquiry;
- **seat-health telemetry** for timeouts, schema failures, rate limits, and
  evidence-gated quarantine;
- **topic-skill analytics** based on peer-evaluated performance;
- **calibration analytics** for confidence quality;
- **bounded inquiry cycles** over high-priority open questions;
- **training-corpus support** for ratified demonstrations and peer-preference
  pairs;
- **protocol-evolution evaluation** against external-truth instruments.

The learning path is deliberately asymmetric:

```text
ratified public outcome
    -> bounded lesson / telemetry / hypothesis
    -> future controlled use
    -> matched evaluation
    -> retained evidence
    -> independent review
    -> governed decision
```

A failed, weak, incomparable, unratified, or unmatched result is not promoted.
Training support may produce datasets, plans, or operator-run scripts, but the
council process does not automatically train or replace a model.

### Lasting agent change

Memory, Identity, Soul, prompt, and revision artifacts are separate from the
agent's temporary CED role. A lasting change must travel through a governed path
such as:

```text
verified observation
    -> retained tamper-evident artifact
    -> named non-self attestation
    -> immutable evidence record
    -> bounded self-review
    -> strict proposal
    -> independent evaluation
    -> named non-self approval
    -> recoverable application
    -> probation
    -> confirmation or governed rollback
```

No component may treat its own recommendation, score, consultation, or receipt as
self-approval.

### Implemented governance and evidence bridges

The current `main` branch includes, among other foundations:

- curated OpenClaw Memory lessons and injection auditing;
- integrity-hardened matched evaluation and evidence handling;
- Identity failure evidence and governed Identity-resolution evidence;
- Soul constitutional-review attestation;
- read-only curator reporting over immutable evidence and lifecycle state;
- Deliberation Tree parent/child revision evidence with matched-compute checks;
- shared atomic, immutable, conflict-safe receipt persistence.

The single-agent Lesson A/B Memory link/unlink attestation bridge in **PR #62** is
still an open draft and must not be described as shipped on `main`.

---

## Per-agent bounded self-questioning

### Micro-Socratic Kernel v1

The Micro-Socratic Kernel is a small local self-check that an agent may run on its
own draft before finalization.

```text
Every agent may question itself.
No agent may certify itself.
```

The kernel identifies:

- the central claim;
- required assumptions;
- the strongest challenge or counterexample;
- missing evidence and uncertainty;
- verification needs;
- one bounded recommendation.

Its recommendations are limited to:

```text
accept
revise
verify_with_tool
consult_external_model
insufficient_information
```

The kernel may recommend verification, revision, or consultation, but it may not:

- execute a tool;
- launch external consultation;
- retry or recursively question itself;
- approve or certify the agent;
- silently replace the final answer;
- mutate `SessionState`, CED, Memory, Identity, Soul, prompts, or governance;
- store hidden chain-of-thought or a private scratchpad.

Risk modes (`light`, `standard`, `high_risk`) strengthen the required structured
fields; they do not grant additional calls or authority.

**Current status:** implemented and tested, with an offline operator CLI and
immutable receipts, but **runtime-inert**. It is not automatically invoked inside
`CEDOrchestrator` and is not yet active on every agent call.

---

## External Self-Consultation v1

External Self-Consultation allows a requesting agent to obtain one bounded,
isolated advisory response from the same model in a fresh context or from a peer
model.

Supported modes are:

```text
critic
independent_solver
judge
```

The consulted model receives no previous conversation history, hidden scratchpad,
full Memory/Identity/Soul profile, secrets, tools, write capability, delegation,
or approval authority. The call is exactly one provider call: there is no nested
consultation and no repair/retry loop.

```text
The requesting agent may ask.
The consulted model may advise.
The consulted model may not execute, approve, delegate, or mutate.
Only governed evidence may justify a lasting change.
```

Consultation output is advice or candidate evidence only. It cannot mutate CED,
Memory, Identity, Soul, proposals, evidence registries, or governance state, and
it cannot serve as self-approval.

**Current status:** implemented and tested as a runtime-inert foundation with an
offline/manual operator CLI. It is not automatically called by the Micro-Socratic
Kernel or `CEDOrchestrator`.

---

## Relationship between local reasoning components

| Component | Purpose | Authority |
|---|---|---|
| Micro-Socratic Kernel | One agent's bounded local self-check | Recommendation only |
| External Self-Consultation | One isolated independent advisory call | Advice / candidate evidence only |
| Deliberation Tree | Explore and compare alternative revisions | Search and measured revision, not approval |
| Peer scoring | Evaluate another output under a rubric | Qualitative judgment, no protocol control |
| CEDOrchestrator | Execute the canonical protocol | Sole execution/protocol authority |
| Governance and evidence registries | Authorize lasting change through explicit lifecycle rules | No automatic semantic judgment |

A future integration may follow:

```text
draft
    -> optional Micro-Socratic Check
    -> optional governed tool or external consultation
    -> optional bounded revision
    -> ordinary CED peer evaluation and ratification
```

That future wiring must preserve one-call budgets, auditability, no self-approval,
and the sole authority of `CEDOrchestrator`.

---

## Security, privacy, and evidence boundaries

- No API keys or secrets in source, HTML, frontend code, prompts, receipts, or
  committed files.
- No hidden chain-of-thought retained as an authority-bearing artifact.
- No raw private scratchpad transfer between agents or consultation services.
- No self-attestation, self-approval, or automatic profile mutation.
- Failed provider calls and failed evidence remain visible failures.
- Immutable records are append-only; exact reruns may be idempotent, while
  conflicting reuse is refused.
- Named non-self review is required where a lasting governance action is
  supported.
- Identity, Memory, Soul, prompts, and temporary CED roles remain distinct.

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
| `backend/dialogues/openclaw_socratic_kernel/` | Runtime-inert bounded per-agent self-check. |
| `backend/dialogues/openclaw_consultation/` | Runtime-inert isolated external advisory service. |
| `backend/dialogues/openclaw_receipts.py` | Shared hardened immutable receipt publication primitive. |
| `backend/dialogues/openclaw_*` | Governed evidence, Memory, Identity, Soul, prompt, consultation, and revision packages. |
| `backend/evaluation/` | External-truth, evidence-harness, and protocol-evolution evaluation tools. |
| `backend/training/` | Governed corpus harvesting and operator-run local training support. |
| `tests_dialogues/` | Canonical engine, learning, consultation, kernel, and governance regression suite. |
| `docs/openclaw_memory_lessons/` | Detailed Memory, consultation, kernel, and evidence-boundary documentation. |
| `docs/HYBRID_V1_H0_5_PRESERVATION_CONTRACT.md` | Normative pre-implementation preservation and non-duplicate-authority contract for Epistemic Hybrid v1. |
| `docs/HYBRID_V1_H1_SHADOW_IMPLEMENTATION.md` | Implemented H1 append-only observation ledger, authority boundary, parity proof, and live evidence. |
| `backend/dialogues/README.md` | Detailed technical reference and historical phase record. |
| `socrates_ai.py`, `backend/orchestrator/` | Legacy reasoning family; not canonical. |

---

## Current implementation status

### Implemented on `main`

- governed CED reasoning engine;
- deterministic rotating roles;
- structured provider registry and honest provider failures;
- registry-backed deliberation, peer scoring, blind section assembly, and Council
  Ratification;
- multi-turn public-brief conversation continuity;
- optional lessons, telemetry, calibration, open questions, inquiry, evaluation,
  and training-support layers;
- curated OpenClaw Memory lessons and integrity-hardened evidence foundations;
- Identity failure/resolution and Soul constitutional-review attestation bridges;
- Deliberation Tree revision-evidence bridge;
- External Self-Consultation v1, runtime-inert;
- Micro-Socratic Kernel v1, runtime-inert;
- shared immutable receipt persistence.

### Open draft — not shipped

- PR #62: bound single-agent Lesson A/B Memory link/unlink attestation.

### Implemented on `feature/openrouter-live-provider`

- strict exact-model OpenRouter council integration;
- restored stable logical-agent to physical-model binding and typed confidence
  propagation;
- H1 append-only Hybrid ledger in explicit, disabled-by-default shadow mode;
- deterministic/idempotent record identity, replay and conflict refusal;
- failure-isolated post-finalization capture with no `SessionState`,
  `FinalResponse`, prompt, scoring, assembly, ratification, or public-event
  authority change.

### Planned or not yet connected to canonical runtime

- automatic bounded Micro-Socratic Kernel invocation in the agent/CED path;
- governed automatic handoff from the kernel to tools or External Consultation;
- governing Hybrid epistemic transitions beyond the H1 shadow ledger;
- versioned public event projections;
- robust FastAPI/SSE transport with replay and `Last-Event-ID`;
- React/Vite Council Live View;
- strict OpenRouter adapter with returned-model and route verification.

The existing FastAPI/SSE/EpistemicGraph implementation belongs to the older
reasoning family and is not the transport authority for the canonical CED engine.

---

## Documentation

- Start here for project identity, architecture, learning boundaries, and current
  implementation status.
- Read [`backend/dialogues/README.md`](backend/dialogues/README.md) for the deep
  technical reference and historical phase detail.
- Read `RESEARCH.md` for evaluation methodology and claims discipline.
- Read `docs/openclaw_memory_lessons/MICRO_SOCRATIC_KERNEL.md` for the bounded
  per-agent self-check contract.
- Read `docs/openclaw_memory_lessons/EXTERNAL_SELF_CONSULTATION.md` for the
  isolated consultation contract.
- Read the other focused architecture and governance documents under `docs/` for
  evidence, Memory, Identity, Soul, and revision details.

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
clearly distinguish implemented, gated, experimental, runtime-inert, historical,
draft, and planned capabilities.

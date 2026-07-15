# Agent Prompt Architecture v2 — Feature Integration Matrix

Status: architecture audit for branch `agent/prompt-architecture-v2-foundation`.

This matrix answers two questions for every existing or planned Socrates AI feature:

1. where it belongs in the v2 prompt/runtime lifecycle;
2. what authority it must never acquire.

## Layer model

| Layer | Purpose | Mutability / authority |
|---|---|---|
| Constitution | Stable epistemic and governance principles | Versioned; no role/task data |
| Persistent Identity | Model/agent identity and governed prompt-safe history | Read-only projection per call |
| Capability Manifest | Explicit capabilities authorized for this task | Permission declaration, not execution |
| Temporary Role | Current Socratic duty | CED-assigned and rotating |
| Phase / Task Contract | Exact work and bounded context | Session/task scoped |
| Output Schema | Machine contract | Exact and validator-owned |
| Local check / tools / consultation | Optional governed operations | Never self-authorizing |
| Receipts / Event Ledger | External audit and canonical history | CED/system owned |

## Feature matrix

| Feature | Correct v2 placement | Prompt-visible content | Must never happen | Current status |
|---|---|---|---|---|
| Micro-Socratic Kernel | After draft, before final delivery; capability-gated | Risk mode and bounded check contract only when enabled | No tools, consultation execution, recursion, self-certification, hidden CoT, or mutation | Implemented/tested, runtime-inert |
| External Self-Consultation | Governed route after explicit request/recommendation | Isolated mode contract; result reintroduced as advice | No tools, delegation, vote, approval, recursion, full profile, or direct lasting change | Implemented/tested, runtime-inert |
| Deterministic tools | CED/tool gateway after an authorized verification need | Tool result and provenance, not a narrated claim of execution | Agent must not invent execution or results | Planned integration |
| Web/source retrieval | Capability manifest + governed retrieval gateway | Retrieved public evidence with provenance | No silent browsing or fabricated citations | Planned integration |
| Calculator / code test | Capability manifest + deterministic execution | Inputs/results/receipt as bounded evidence | No free-form hidden execution claim | Planned integration |
| Time/date / calendar read | Capability manifest + read-only gateway | Only task-relevant result | No write action or hidden personal data leakage | Planned integration |
| User clarification | Capability manifest / CED interaction policy | One bounded clarification request when routed | No fabricated answer when clarification is required | Planned integration |
| Deliberation Tree | CED-level candidate search, not persistent identity | Parent draft + generic revision mandate only | No scores, tree statistics, authorship, self-approval, or second orchestrator | Implemented with governed evidence bridge |
| Memory lessons | Prompt-safe task context before role/task execution | Eligible stable/verified lessons only | No proposed lesson, raw Memory registry, or automatic truth status | Implemented optional context |
| Persistent Identity | Dedicated identity layer before temporary role | Requested model identity and governed prompt-safe items | No permanent role, self-description, returned-model claim, raw registry | Foundation implemented; projection pending |
| Identity failures/resolution | Source for governed identity projection | Only eligible unresolved/resolved guidance with digests | No self-attestation or unverified profile mutation | Evidence bridges implemented |
| Soul constitutional constraints | Constitution/governance boundary, optionally prompt-safe projection | Stable constitutional obligations only | No raw Soul profile or agent-written constitutional authority | Attestation foundation implemented |
| Prompt Registry / patches | Prompt composition and external lineage | Only active stable/verified patch effects | No silent drift, proposed patch auto-activation, replacement/deletion bypass | Foundation implemented, runtime-inert |
| Prompt lineage | External metadata/receipt | Prompt ID/version/fingerprint may be declared | Agent cannot self-certify actual prompt sent | Foundation exists; v2 integration pending |
| Requested/returned model integrity | Adapter and receipt layer | Requested model visible as expected identity | No silent fallback/substitution; model text cannot verify route | Strict OpenRouter path planned |
| Provider route pinning | Adapter policy for strict runs | Normally not needed in task prompt | No automatic provider switch in reproducibility mode | Planned |
| Conversation continuity | Sanitized public continuation brief | Public answers, claims, caveats, objections, open questions | No hidden scores, scratchpads, provider maps, or private audit data | Implemented |
| Open Question Ledger / curiosity | Prompt-safe context/mandate when relevant | Selected unresolved questions and inquiry mandate | No fabricated closure or automatic research execution | Implemented optional layer |
| Topic-skill analytics | CED-owned hidden analytics | None by default; only governed identity result later | No leaderboard leakage or self-ranking | Implemented analytics |
| Calibration analytics | CED-owned hidden analytics | Bounded approved calibration guidance only through Identity | No raw Brier/leaderboard leakage or authority from confidence | Implemented analytics |
| Seat health / quarantine | CED-owned operational routing | None | No content judgment or agent-visible provider ranking | Implemented telemetry |
| Peer scoring | Evaluative role/task overlay | Anonymous candidate + rubric | No self-scoring, author/provider hints, missing-score fabrication | Implemented |
| Blind section assembly | CED mechanical layer | Not a capability prompt | CED must not author semantic replacement sections | Implemented |
| Council Ratification | Evaluative task overlay after assembly | Anonymous assembled answer + exact verdict schema | No fixed chairman; valid critical block cannot be majority-overridden | Implemented |
| Governed self-revision | External evidence/governance lifecycle | Approved/probationary result may later enter Identity | No direct Memory/Identity/Soul/prompt write or self-approval | Implemented foundation |
| Lesson A/B and matched evaluation | Evaluation layer before lasting adoption | Final approved lesson only, not raw scores | No incomparable promotion or result cherry-picking | Implemented foundations; PR status may vary |
| Training corpus | Offline/operator-run output | None in ordinary agent prompt | No automatic model training/replacement from one session | Implemented support |
| Immutable receipts | External audit layer | Digests/declared lineage only when useful | No secrets, raw CoT, mutable overwrite, or receipt-as-approval | Implemented shared primitive |
| Epistemic Event Ledger | Canonical append-only history after runtime events | Selected public projection only | No direct agent write or event-as-semantic-truth | Planned for canonical CED family |
| Public event projections | Read-only views derived from Event Ledger | Only projection appropriate to task/UI | No canonical-state mutation from UI | Planned |
| FastAPI/SSE / Live View | Transport and presentation | No extra reasoning authority | UI/API must not become protocol authority | Planned canonical transport |
| Model-to-role matching | Future CED scheduling prior based on governed evaluation | Never injected as identity praise or permanent role | No provider prestige, permanent ownership, or self-selection | Future research target |

## Kernel and capability sequencing

A capability manifest is not a bag of tools available directly to the model. It is
a typed routing contract for the governed caller.

```text
CapabilityManifest says: micro_socratic_check(max_calls=1, mode=standard)
    != the Kernel already ran

CapabilityManifest says: web_retrieval(max_calls=2)
    != the model browsed

CapabilityManifest says: external_consultation(max_calls=1, mode=critic)
    != another model approved the draft
```

The caller must execute the authorized operation, retain its receipt, and reinsert
only the validated result into the ordinary CED flow.

## Required future composition

```text
Constitution
    -> Persistent Identity
    -> Governed Identity Evidence
    -> Capability Manifest
    -> Temporary Role
    -> Phase
    -> Task Contract
    -> Output Schema
    -> initial draft
    -> optional Micro-Socratic Check
    -> optional governed tool / consultation
    -> optional bounded revision
    -> peer scoring / assembly / Council Ratification
    -> receipts + Epistemic Event Ledger
```

No feature in this matrix changes the permanent invariant:

```text
Agents judge epistemic quality.
CED governs the protocol.
Every agent may question itself.
No agent may certify itself.
```

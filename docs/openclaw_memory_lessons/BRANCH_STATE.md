# Branch State — OpenClaw Memory Lessons v0

**Canonical name:** `OPENCLAW_MEMORY_LESSONS_STATE`

Branch:

```text
feature/openclaw-memory-lessons-v0
```

Base branch:

```text
feature/proof-sprint-v0
```

## Purpose

This branch is the documentation and architecture foundation for making
OpenClaw a local learning cockpit on top of Socrates-AI / CED — and, since
the runtime layers started landing, the honest record of what actually
exists versus what is still planned.

It defines how memory lessons, tree search, shadow apprenticeship, prompt
patches, and future local agents evolve without breaking the CED invariants.

## Main objective

The long-term goal is to train agents to become self-improving
master-branch researchers.

In this context, a master-branch researcher means an agent that can:

- study the current main / master branch state
- understand the current architecture before changing it
- read Memory Lessons and previous failures
- propose small, testable improvements
- compare candidate changes against the stable baseline
- avoid breaking CED invariants
- learn from Proof Sprint and Evidence Harness results
- produce auditable reasoning traces
- generate future prompt patches, code patches, tests, and research plans
- improve over time through evidence, not ego or hidden authority

The goal is not to create agents that freely mutate the repository.

The goal is to create agents that learn how to research the repository,
propose better changes, test them, and earn promotion through measurable
results.

## Core principle

```text
Agents do not own truth.
Agents do not own permanent roles.
Agents do not silently rewrite the system.
Agents learn to research, propose, test, and improve.
CED governs.
Evidence Harness measures.
OpenClaw remembers.
```

## Landed layers (each committed with tests, full suite green)

| Layer | Commit | Runtime | Tests |
|---|---|---|---|
| Docs foundation (lessons, prompts, patch policy, goals) | `e61ee45` | — | — |
| Docs: Shadow Apprentice, Socratic Tree Search, memory map, state, index | `2f93dd6`…`ca0c862` | — | — |
| Goal 1 — lesson_loader | `20dc8a9` | `openclaw_memory/lesson_loader.py` | 17 |
| Goal 3 — lesson_retriever | `7eed54c` | `openclaw_memory/lesson_retriever.py` | 15 |
| Goal 4 — context_injection | `7cc2298` | `openclaw_memory/context_injection.py` | 13 |
| CED wiring (lessons reach deliberation contexts, opt-in) | `8eb6877` | `ced.py` + `live_providers.py` params | 7 |
| Goal 5 — trace_capture | `adcfc99` | `openclaw_memory/trace_capture.py` | 12 |
| Deliberation Tree Search (AlphaGo search operator) | `704c0dd` | `deliberation_tree.py` + CED opt-in | 19 |
| live_dialogue wiring (env switches, meta-gap closed) | `d2db819` | `scripts/live_dialogue.py` | — |
| Goal 6 — lesson_proposer | `4df5869` | `openclaw_memory/lesson_proposer.py` | 15 |
| AlphaGo distill step (tree → TrainingCorpus pairs) | `33e7453` | `backend/training/corpus.py` | 11 |
| Promotion Arena (generation gating, 0.55 gate) | `e209788` | `backend/training/arena.py` | 11 |
| Goal 14 — Agent Identity Layer (profile, gates, soul card) | `f45b6d6` | `openclaw_identity/` (3 modules) | 21 |
| Identity registry + instrument-fed gate evidence | `845bcf9` | `openclaw_identity/` (+2 modules) | 14 |
| Shadow-run markers (capture-time, verified evidence) | `196a892` | `trace_capture.py` + `evidence_collection.py` | 9 |
| Goal 6.1 — Lesson effectiveness A/B harness (poisoning detector) | `7a31805` | `openclaw_memory/lesson_ab.py` | 7 |
| Goal 7 — Prompt registry (versioned lineage, runtime-inert) | `d6d4ee3` | `openclaw_prompts/prompt_registry.py` | 16 |
| Goal 8 — Prompt patch generator (proposes into the registry) | `4672c80` | `openclaw_prompts/patch_proposer.py` | 9 |
| Goal 11 — Shadow Apprentice Mode (Stage 1 runtime) | `cfe0624` | `openclaw_shadow/shadow_apprentice.py` | 13 |
| Goal 10 — Local LLM provider (gated apprentice adapter) | see git log | `openclaw_local/local_provider.py` | 14 |

## Learning arcs currently closed

```text
Lessons arc:
  trace capture → lesson proposer → human review → A/B harness (tested)
  → promote to stable → retrieval → context injection → next session

Policy arc (AlphaGo loop):
  drafts (policy) → peer scores (value) → tree search (amplify)
  → distill pairs → TrainingCorpus → LoRA student
  → Promotion Arena gate → human swaps seat

Identity arc:
  shadow-marked traces → identity profile (evidence) → soul card (review)
  → version gate (instrument-fed evidence) → human approval
  → identity vNext → registry on disk
```

## Learning model

The staged learning model this branch implements:

```text
1. Read traces.
2. Extract lessons.
3. Retrieve relevant lessons.
4. Inject lessons into allowed context.
5. Run agents under CED role rotation.
6. Compare outputs with Evidence Harness / ratification.
7. Propose small prompt or code patches.
8. A/B test changes.
9. Promote only verified improvements.
10. Prepare clean future training datasets.
```

## Self-improving researcher ladder

Agents evolve through stages (the runtime encoding lives in
`backend/dialogues/openclaw_identity/promotion_policy.py`; the full design
in SELF_IMPROVING_AGENT_IDENTITY.md):

### Stage 1 — Reader

The agent can read architecture docs, Memory Lessons, Future Goals, and
branch state.

### Stage 2 — Explainer

The agent can explain what the branch does and what must not be changed.

### Stage 3 — Shadow Researcher

The agent can propose a change in shadow mode without affecting the final
answer or repository.

### Stage 4 — Patch Proposer

The agent can propose small prompt patches, lesson patches, or test plans.

### Stage 5 — Test-Aware Researcher

The agent can link proposed changes to Evidence Harness or Proof Sprint
tests.

### Stage 6 — Candidate Contributor

The agent can produce candidate implementation patches that remain
reviewable and reversible.

### Stage 7 — Master-Branch Researcher

The agent can study the master/main branch, compare it with feature
branches, understand risk, propose safe improvements, and justify them with
tests and evidence.

## Safety constraints

A self-improving master-branch researcher must never:

- overwrite stable architecture without review
- bypass tests
- treat memory as factual proof
- expose secrets
- use hidden scores as ego feedback
- make itself the permanent judge
- ignore role rotation
- modify production prompts without patch policy
- fine-tune on unverified traces

Standing invariants that are TEST-LOCKED on this branch:

- Agents judge epistemic quality; CED governs the protocol.
- Judging tasks see anonymous outputs only; agents never see scores,
  leaderboards, or the task log.
- Nothing is fabricated: failed scores stay missing; failed expansions and
  failed arena drafts are invalid, never defeats.
- Never-auto-promote, four times over: lessons need a human curator, arena
  verdicts need a human seat swap, identity promotions need a passing gate
  plus a named non-self approver, and the A/B harness only reports.
- New features are default-off / opt-in; default paths stay byte-for-byte.
- No keys, no network, no `.env` reads anywhere in these layers.

## Success criteria

This direction succeeds when agents can reliably:

- reduce exact-output failures
- reduce unsupported claims
- detect contradictions earlier
- produce stronger synthesis sections
- propose useful Memory Lessons
- propose small prompt patches that pass A/B tests
- compare branches safely
- explain why a change should or should not merge
- improve local agent quality without cloud credits

## Not yet built (see FUTURE_GOALS.md)

- Goal 2 (machine-readable lesson store), Goal 9 (Proof Sprint v0.3),
  Goal 11 Stages 2-4 (apprentice contribution of low-risk sections —
  behind the Promotion Arena gate), Goal 12 (UI panel), Goal 13
  (fine-tuning dataset preparation beyond the Phase 22 corpus),
  prompt-registry runtime wiring (rendered prompts into live calls behind
  an A/B gate), a live shadow session script (operator runs the gated
  local apprentice against a real council and collects identity evidence).
- Curriculum from the OpenQuestionLedger; Evidence Harness value grounding
  for the tree; an instrument that observes unsupported claims (until then
  identity gate v0.2→v0.3 honestly cannot pass); role-scoped apprentice
  participation (a future CED opt-in behind the arena gate);
  auto-linking proposer patterns to known_failures.

## Guiding sentence

```text
The agents are learning to become researchers of the system itself,
not rulers of the system.
```

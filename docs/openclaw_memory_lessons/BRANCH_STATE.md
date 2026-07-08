# Branch State — OpenClaw Memory Lessons v0

Branch:

```text
feature/openclaw-memory-lessons-v0
```

Base branch:

```text
feature/proof-sprint-v0
```

## Purpose

This branch is the documentation and architecture foundation for making OpenClaw a local learning cockpit on top of Socrates-AI / CED.

It defines how memory lessons, tree search, shadow apprenticeship, prompt patches, and future local agents should evolve without breaking the CED invariants.

## Main objective

The long-term goal is to train agents to become self-improving master-branch researchers.

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

The goal is to create agents that learn how to research the repository, propose better changes, test them, and earn promotion through measurable results.

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

## Current branch contents

This branch currently contains:

```text
docs/openclaw_memory_lessons/README.md
docs/openclaw_memory_lessons/MEMORY_LESSONS.md
docs/openclaw_memory_lessons/FUTURE_GOALS.md
docs/openclaw_memory_lessons/AGENT_PROMPT_BASE.md
docs/openclaw_memory_lessons/SYNTHESIS_5_SECTION.md
docs/openclaw_memory_lessons/PROMPT_PATCH_POLICY.md
docs/openclaw_memory_lessons/SOCRATIC_TREE_SEARCH.md
docs/openclaw_memory_lessons/TREE_SEARCH_MEMORY_MAP.md
docs/openclaw_memory_lessons/BRANCH_STATE.md
```

## What this branch is

This branch is:

- a roadmap
- a memory layer foundation
- a future OpenClaw learning architecture
- a prompt evolution policy base
- a Socratic Tree Search foundation
- a Shadow Apprentice foundation
- a safe path toward local self-improving agents

## What this branch is not

This branch is not:

- a runtime implementation yet
- a fine-tuning branch
- a CED core rewrite
- a provider API integration
- a hidden autonomous code modifier
- a replacement for Evidence Harness
- a branch that gives agents permanent authority

## Learning model

The expected learning model is staged:

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

Agents should evolve through stages:

### Stage 1 — Reader

The agent can read architecture docs, Memory Lessons, Future Goals, and branch state.

### Stage 2 — Explainer

The agent can explain what the branch does and what must not be changed.

### Stage 3 — Shadow Researcher

The agent can propose a change in shadow mode without affecting the final answer or repository.

### Stage 4 — Patch Proposer

The agent can propose small prompt patches, lesson patches, or test plans.

### Stage 5 — Test-Aware Researcher

The agent can link proposed changes to Evidence Harness or Proof Sprint tests.

### Stage 6 — Candidate Contributor

The agent can produce candidate implementation patches that remain reviewable and reversible.

### Stage 7 — Master-Branch Researcher

The agent can study the master/main branch, compare it with feature branches, understand risk, propose safe improvements, and justify them with tests and evidence.

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

## Next implementation step

The next practical implementation step remains:

```text
backend/dialogues/openclaw_memory/lesson_loader.py
```

Then:

```text
lesson_retriever.py
AgentTask context injection
trace capture
lesson proposer
prompt registry
Shadow Apprentice Mode
Socratic Tree Search runtime
local LLM provider
OpenClaw UI panel
```

## Guiding sentence

```text
The agents are learning to become researchers of the system itself, not rulers of the system.
```

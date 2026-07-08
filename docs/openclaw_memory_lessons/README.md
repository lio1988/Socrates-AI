# OpenClaw Memory Lessons Layer v0.1

Branch:

```text
feature/openclaw-memory-lessons-v0
```

This README is the branch-specific high-level entry point for the OpenClaw Memory Lessons / Self-Improving Researcher foundation.

For canonical branch document names, read:

```text
docs/openclaw_memory_lessons/OPENCLAW_MEMORY_LESSONS_BRANCH_INDEX.md
```

## Core idea

```text
CED governs the protocol.
Evidence Harness measures performance.
OpenClaw stores and retrieves curated lessons.
Agents execute the current task using only the context they are allowed to see.
```

OpenClaw should make the system feel smarter over time by improving the context that agents receive, not by silently mutating agents or leaking hidden scores into their prompts.

## Boundary

This layer is documentation and prompt foundation only.

It does **not** change the CED core.
It does **not** change role rotation.
It does **not** make agents own persistent memory.
It does **not** perform fine-tuning.
It does **not** expose API keys, provider secrets, hidden scorecards, or raw leaderboards to agents.

## Branch-specific canonical docs

```text
OPENCLAW_MEMORY_LESSONS_BRANCH_INDEX
  docs/openclaw_memory_lessons/OPENCLAW_MEMORY_LESSONS_BRANCH_INDEX.md

OPENCLAW_MEMORY_LESSONS_BRANCH_README
  docs/openclaw_memory_lessons/README.md

OPENCLAW_MEMORY_LESSONS_MEMORY
  docs/openclaw_memory_lessons/MEMORY_LESSONS.md

OPENCLAW_MEMORY_LESSONS_GOALS
  docs/openclaw_memory_lessons/FUTURE_GOALS.md

OPENCLAW_MEMORY_LESSONS_STATE
  docs/openclaw_memory_lessons/BRANCH_STATE.md

OPENCLAW_MEMORY_LESSONS_AGENT_PROMPT_BASE
  docs/openclaw_memory_lessons/AGENT_PROMPT_BASE.md

OPENCLAW_MEMORY_LESSONS_SYNTHESIS
  docs/openclaw_memory_lessons/SYNTHESIS_5_SECTION.md

OPENCLAW_MEMORY_LESSONS_PROMPT_PATCH_POLICY
  docs/openclaw_memory_lessons/PROMPT_PATCH_POLICY.md

OPENCLAW_MEMORY_LESSONS_TREE_SEARCH
  docs/openclaw_memory_lessons/SOCRATIC_TREE_SEARCH.md

OPENCLAW_MEMORY_LESSONS_TREE_MEMORY_MAP
  docs/openclaw_memory_lessons/TREE_SEARCH_MEMORY_MAP.md
```

## Architectural rule

Runtime agents may remain memoryless executors, but they can receive relevant external memory lessons as context.

```text
User task
  ↓
OpenClaw retrieves relevant lessons
  ↓
CED assigns phase + rotating role
  ↓
Agent receives task + role + allowed history + selected lessons + schema
  ↓
Agent produces structured output
  ↓
CED runs synthesis / scoring / ratification
  ↓
Evidence Harness evaluates performance when ground truth exists
  ↓
OpenClaw stores new trace and proposes new lessons
```

## Memory lesson lifecycle

A lesson should move through these states:

```text
proposed → tested → verified → stable → deprecated
```

A lesson should become `verified` only after it is supported by at least one concrete run, Proof Sprint result, ratification trace, or repeated observed failure pattern.

## What agents may see

Agents may see:

```text
- current task
- current phase
- current rotating role
- allowed council history
- selected relevant memory lessons
- supplied evidence
- required output schema
```

Agents must not see unless explicitly allowed:

```text
- hidden scorecards
- raw peer scores
- internal leaderboards
- provider API metadata
- secret keys
- full unrelated memory history
- private system diagnostics
```

## Prompt evolution rule

Future prompt evolution must happen through small patches, not full rewrites.

```text
existing_prompt_v0.1
+ small patch
+ reason
+ expected effect
+ A/B test
= candidate_prompt_v0.1.1
```

No production prompt should be changed automatically without tests and approval.

## First implementation target

The first runtime version should do only this:

1. Load lessons from a readable lesson source.
2. Select 2-5 relevant lessons for a task.
3. Inject those lessons into `AgentTask.context` or an equivalent OpenClaw context block.
4. Run the normal CED pipeline.
5. Save the council trace.
6. Convert failures into proposed lessons.
7. Keep all prompt changes as explicit patches.

## Branch identity sentence

```text
This branch is the OpenClaw Memory Lessons / Self-Improving Researcher foundation branch.
```

## Principle

```text
Agents do not own memory.
Agents receive lessons.
The system owns memory.
CED owns protocol.
Evidence owns proof.
```

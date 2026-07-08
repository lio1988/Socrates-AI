# OpenClaw Memory Lessons Branch Index

Branch:

```text
feature/openclaw-memory-lessons-v0
```

This file is the canonical index for the branch-specific documentation.

Use this index to avoid confusing these docs with generic project documentation.

## Canonical branch document names

```text
OPENCLAW_MEMORY_LESSONS_BRANCH_README
  File: docs/openclaw_memory_lessons/README.md
  Purpose: High-level branch README and architecture boundary.

OPENCLAW_MEMORY_LESSONS_MEMORY
  File: docs/openclaw_memory_lessons/MEMORY_LESSONS.md
  Purpose: Curated behavioral lessons and lesson lifecycle.

OPENCLAW_MEMORY_LESSONS_GOALS
  File: docs/openclaw_memory_lessons/FUTURE_GOALS.md
  Purpose: Future implementation roadmap and staged goals.

OPENCLAW_MEMORY_LESSONS_STATE
  File: docs/openclaw_memory_lessons/BRANCH_STATE.md
  Purpose: Current branch state and self-improving researcher objective.

OPENCLAW_MEMORY_LESSONS_AGENT_PROMPT_BASE
  File: docs/openclaw_memory_lessons/AGENT_PROMPT_BASE.md
  Purpose: Shared agent prompt base notes.

OPENCLAW_MEMORY_LESSONS_SYNTHESIS
  File: docs/openclaw_memory_lessons/SYNTHESIS_5_SECTION.md
  Purpose: 5-section blind assembly design.

OPENCLAW_MEMORY_LESSONS_PROMPT_PATCH_POLICY
  File: docs/openclaw_memory_lessons/PROMPT_PATCH_POLICY.md
  Purpose: Rules for small prompt improvements.

OPENCLAW_MEMORY_LESSONS_TREE_SEARCH
  File: docs/openclaw_memory_lessons/SOCRATIC_TREE_SEARCH.md
  Purpose: Socratic Tree Search / MCTS foundation.

OPENCLAW_MEMORY_LESSONS_TREE_MEMORY_MAP
  File: docs/openclaw_memory_lessons/TREE_SEARCH_MEMORY_MAP.md
  Purpose: Policy memory, value memory, and branch outcome memory map.
```

## Short names allowed inside discussion

Inside this branch only, these short names are allowed:

```text
README      = OPENCLAW_MEMORY_LESSONS_BRANCH_README
MEMORY      = OPENCLAW_MEMORY_LESSONS_MEMORY
GOALS       = OPENCLAW_MEMORY_LESSONS_GOALS
STATE       = OPENCLAW_MEMORY_LESSONS_STATE
PROMPT_BASE = OPENCLAW_MEMORY_LESSONS_AGENT_PROMPT_BASE
SYNTHESIS   = OPENCLAW_MEMORY_LESSONS_SYNTHESIS
PATCH_POLICY = OPENCLAW_MEMORY_LESSONS_PROMPT_PATCH_POLICY
TREE_SEARCH = OPENCLAW_MEMORY_LESSONS_TREE_SEARCH
TREE_MEMORY = OPENCLAW_MEMORY_LESSONS_TREE_MEMORY_MAP
```

## Naming rule for future docs

Any new doc added to this branch should either:

1. live inside `docs/openclaw_memory_lessons/`, and
2. be listed in this index with an `OPENCLAW_MEMORY_LESSONS_*` canonical name.

Do not add generic names in unrelated folders unless the doc is meant to be project-wide.

## Naming rule for future code

Future runtime implementation should use explicit package names:

```text
backend/dialogues/openclaw_memory/
backend/dialogues/openclaw_tree/
backend/dialogues/openclaw_prompts/
```

Avoid vague names such as:

```text
memory.py
loader.py
agent.py
tree.py
```

Prefer explicit names such as:

```text
lesson_loader.py
lesson_retriever.py
lesson_proposer.py
tree_controller.py
branch_evaluator.py
prompt_registry.py
```

## Branch identity sentence

```text
This branch is the OpenClaw Memory Lessons / Self-Improving Researcher foundation branch.
```

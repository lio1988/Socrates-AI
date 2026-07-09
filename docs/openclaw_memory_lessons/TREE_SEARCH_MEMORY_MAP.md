# Tree Search Memory Map v0.1

This document defines how Socratic Tree Search connects to Memory Lessons.

The goal is to support future policy/value learning without allowing hidden self-modification or permanent provider authority.

## Memory categories

### 1. Behavioral lesson

A general instruction learned from failures or successes.

Example:

```text
When exact output is requested, return only the requested token.
```

Used for:

- agent context guidance
- prompt patch proposals
- task-specific retrieval

### 2. Policy memory

A memory about which next action tends to help for a task type.

Example:

```text
For unsupported-claim tasks, extract claims before synthesis.
```

Used for:

- branch generation
- branch prioritization
- selecting first inquiry action

Not used for:

- overriding role rotation
- declaring final truth
- automatic production prompt changes

### 3. Value memory

A memory about which branch types tend to survive evaluation.

Example:

```text
For factual-grounding tasks, evidence-first branches often reduce unsupported claims.
```

Used for:

- search priors
- expansion ordering
- local apprentice training

Not used for:

- permanent provider authority
- hidden scoring feedback to agents
- automatic final answer selection

### 4. Branch failure memory

A memory extracted from a failed branch.

Example:

```text
This branch jumped to synthesis before resolving a contradiction.
```

Used for:

- proposed lessons
- prompt patch candidates
- future pruning rules

### 5. Branch success memory

A memory extracted from a branch that survived critique, synthesis, or ratification.

Example:

```text
Evidence-first branch produced the winning core_answer section.
```

Used for:

- policy/value memory
- Shadow Apprentice comparison
- dataset candidates

## Suggested JSONL shapes

### Policy memory record

```json
{
  "memory_type": "policy_memory",
  "memory_id": "POLICY-0001",
  "status": "proposed",
  "task_type": "unsupported_claim",
  "recommended_next_action": "extract_claims_before_synthesis",
  "reason": "Branches that skipped claim extraction produced unsupported final answers.",
  "source_run_ids": ["run_001"],
  "risk": "May slow down simple tasks if overused."
}
```

### Value memory record

```json
{
  "memory_type": "value_memory",
  "memory_id": "VALUE-0001",
  "status": "proposed",
  "task_type": "factual_grounding",
  "branch_type": "evidence_first",
  "observed_effect": "Fewer unsupported claims and stronger ratification outcomes.",
  "source_run_ids": ["run_001"],
  "risk": "May over-prioritize evidence extraction even when task is purely logical."
}
```

### Branch outcome record

```json
{
  "memory_type": "branch_outcome",
  "memory_id": "BRANCH-0001",
  "status": "recorded",
  "run_id": "run_001",
  "node_id": "node_003",
  "branch_type": "skeptical_answer",
  "outcome": "pruned",
  "reason": "format_violation",
  "lesson_candidate": "Skeptical branches must still obey exact output constraints."
}
```

## Promotion rules

```text
branch_outcome -> proposed lesson
proposed lesson -> verified lesson
repeated verified lesson -> stable lesson
repeated branch pattern -> policy/value memory
```

No memory should become stable without trace evidence or human/test approval.

## Retrieval rules

For normal agent calls, retrieve only:

- behavioral lessons
- verified claim memories if explicitly relevant

For Tree Search Controller, retrieve:

- behavioral lessons
- policy memories
- value memories
- recent branch outcome summaries

For Shadow Apprentice, retrieve:

- behavioral lessons
- branch success/failure summaries
- policy/value memories marked tested or verified

## Safety rules

- Do not expose raw scorecards to agents.
- Do not expose hidden leaderboards to agents.
- Do not let policy memory override CED role rotation.
- Do not let value memory automatically choose the final answer.
- Do not let local apprentice memories affect final answers before promotion.
- Do not treat memory as factual evidence unless it is explicitly a verified claim memory.

## Future implementation files

```text
backend/dialogues/openclaw_memory/policy_memory.py
backend/dialogues/openclaw_memory/value_memory.py
backend/dialogues/openclaw_memory/branch_outcome_store.py
backend/dialogues/openclaw_tree/tree_memory_bridge.py
```

## Guiding principle

```text
Policy memory guides search.
Value memory guides expansion.
Evidence still decides survival.
CED still governs protocol.
```

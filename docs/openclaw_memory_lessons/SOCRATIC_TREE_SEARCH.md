# Socratic Tree Search / MCTS Mode v0.1

This document defines a future OpenClaw mode inspired by search methods used in chess and Go systems.

The goal is not to copy game AI mechanically. The goal is to adapt the useful idea: do not trust the first line of reasoning. Explore multiple candidate reasoning paths, evaluate them, prune weak paths, expand promising paths, and learn from failed paths.

## Short name

```text
OpenClaw Socratic Tree Search
```

Alternative names:

```text
Socratic MCTS
Reasoning Tree Mode
Epistemic Search Mode
```

## Core translation

```text
Chess / Go move        = reasoning move / claim / objection / inquiry
Board position         = current epistemic state
Candidate variation    = reasoning branch
Policy prior           = which branch or inquiry seems worth trying
Value estimate         = how promising the branch is after scoring / checking
Search depth           = number of critique / revision / synthesis cycles
Pruning                = stopping weak branches early
Backtracking           = returning to a better earlier branch
Final move             = Current Best Explanation
```

## Why this fits CED

CED already has the pieces needed for search:

- role rotation
- peer scoring
- structured claims
- 5-section synthesis
- ratification
- Evidence Harness
- Memory Lessons
- Shadow Apprentice Mode

Socratic Tree Search adds a controller above these pieces:

```text
OpenClaw Tree Controller
  -> generate candidate branches
  -> evaluate branches
  -> expand strong branches
  -> prune weak branches
  -> assemble surviving sections
  -> store lessons from failed branches
```

## Important boundary

Socratic Tree Search must not turn CED into a semantic judge.

CED still governs protocol and mechanical aggregation. Agents, providers, ratifiers, and Evidence Harness provide the evaluative signals. The tree controller only decides which branches to expand or stop according to explicit scores, flags, and deterministic rules.

## Tree node

A tree node represents one epistemic state.

Suggested future schema:

```json
{
  "node_id": "node_001",
  "parent_id": null,
  "depth": 0,
  "task_id": "task_001",
  "phase": "BRANCHING",
  "branch_type": "direct_answer | skeptical_answer | alternative_framing | uncertainty_first | evidence_first",
  "claims": [],
  "open_questions": [],
  "contradictions": [],
  "selected_lessons": [],
  "value_estimate": null,
  "policy_prior": null,
  "status": "open | expanded | pruned | selected | rejected",
  "prune_reason": null
}
```

## Branch types

A first version should support a small number of branch types:

1. `direct_answer`
   - Try to answer the task directly.

2. `skeptical_answer`
   - Start from uncertainty and missing evidence.

3. `evidence_first`
   - Extract evidence and claims before answering.

4. `alternative_framing`
   - Reframe the task or expose hidden assumptions.

5. `contradiction_probe`
   - Search for internal contradictions or conflicting premises.

The first implementation should keep the branch count small, usually 3-5 branches.

## Search stages

### Stage 1 — Branching

Generate a small set of candidate reasoning branches.

Example:

```text
Task
  -> Branch A: direct answer
  -> Branch B: evidence-first answer
  -> Branch C: skeptical answer
  -> Branch D: alternative framing
```

Acceptance criteria:

- branches are structured
- each branch has a type
- branch count is capped
- no provider receives hidden scores

### Stage 2 — Evaluation

Evaluate each branch using available CED mechanisms.

Possible signals:

- unsupported claims
- contradiction flags
- exact-output compliance
- evidence grounding
- peer score where available
- Evidence Harness result where ground truth exists
- ratification severity

Acceptance criteria:

- evaluation is recorded
- reasons are explicit
- failed provider calls produce clean branch status, not fake scores

### Stage 3 — Pruning

Stop expanding weak branches.

Prune reasons may include:

```text
unsupported_claim
contradiction
format_violation
low_grounding
ratification_block
missing_required_evidence
schema_violation
```

Acceptance criteria:

- pruned branch keeps an audit record
- pruned branch can become a Memory Lesson source
- pruning rule is explicit

### Stage 4 — Expansion

Expand only promising branches.

Expansion can ask agents to:

- repair a claim
- answer a critic
- verify evidence
- add stress tests
- produce a 5-section synthesis draft

Acceptance criteria:

- max depth is capped
- max branch count is capped
- expansion is deterministic given the same inputs and provider outputs

### Stage 5 — Synthesis

Surviving branches enter 5-section synthesis.

Each surviving branch can produce or contribute:

```text
core_answer
crucial_stress_test
blind_spots
nuance
final_verdict
```

CED still performs blind assembly section-by-section.

### Stage 6 — Learning

Failed and successful branches both become learning material.

Failed branches can produce lessons such as:

```text
This branch skipped evidence extraction and produced unsupported claims.
This branch answered too early before resolving contradiction.
This branch obeyed exact output constraints and should be reused for similar tasks.
```

## Policy memory

Policy memory records what next action tends to help for a task type.

Example:

```json
{
  "memory_type": "policy_memory",
  "task_type": "unsupported_claim",
  "recommended_next_action": "extract_claims_before_synthesis",
  "reason": "Branches that skipped claim extraction produced unsupported final answers.",
  "status": "proposed"
}
```

Policy memory should guide branch selection, not override CED role rotation.

## Value memory

Value memory records which branch patterns tend to lead to ratified answers.

Example:

```json
{
  "memory_type": "value_memory",
  "branch_type": "evidence_first",
  "task_type": "factual_grounding",
  "observed_effect": "higher ratification rate and fewer unsupported claims",
  "status": "proposed"
}
```

Value memory must not become permanent authority. It is only a prior for search.

## Agent / prompt rating

A future system may track performance by provider, role, prompt version, task type, and section type.

This can be similar to an Elo-like rating, but it must not violate the CED principle of no permanent authority.

Correct use:

```text
This provider / prompt gets a slightly higher search prior for this role or section type.
```

Incorrect use:

```text
This provider is always the judge.
This provider always wins synthesis.
This provider overrides role rotation.
```

## Relationship with Shadow Apprentice

Shadow Apprentice Mode is a perfect training partner for Socratic Tree Search.

The local apprentice can:

- predict which branch will survive
- produce its own branch in shadow mode
- compare its branch against ratified branches
- learn which branch types fail
- learn which branch types produce useful blind spots

The local apprentice should not affect final answers in Stage 1 Shadow mode.

## Runtime safety limits

First implementation should include hard limits:

```text
max_branches = 5
max_depth = 2
max_expansions = 8
max_selected_lessons = 5
max_shadow_outputs = 1
```

These limits prevent cost explosions and runaway deliberation.

## First version acceptance criteria

A v0.1 implementation should:

- generate 3-5 branches for a task
- evaluate branches with explicit flags
- prune at least one weak branch when appropriate
- expand at most 1-2 strong branches
- pass surviving branches into 5-section synthesis
- store branch outcomes in a trace
- propose Memory Lessons from failed branches
- avoid changing CED core semantics
- avoid exposing hidden scores to agents

## Non-goals for v0.1

Do not build these first:

- unlimited recursive search
- automatic fine-tuning
- hidden self-modifying prompts
- permanent provider authority
- score leakage into agent context
- full vector search dependency
- UI-first implementation before traces exist

## Future implementation files

Possible future files:

```text
backend/dialogues/openclaw_tree/tree_node.py
backend/dialogues/openclaw_tree/tree_controller.py
backend/dialogues/openclaw_tree/branch_generator.py
backend/dialogues/openclaw_tree/branch_evaluator.py
backend/dialogues/openclaw_tree/pruning_policy.py
backend/dialogues/openclaw_tree/policy_memory.py
tests_dialogues/test_openclaw_tree_search.py
```

## Guiding principle

```text
Do not answer once.
Search several defensible paths.
Prune what fails.
Expand what survives.
Synthesize only after pressure.
Learn from every failed branch.
```

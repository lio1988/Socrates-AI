# OpenClaw Memory Lessons Layer v0.1

This document defines the first base layer for making OpenClaw a living local learning cockpit on top of Socrates-AI / CED.

The goal is not to turn runtime agents into uncontrolled memory holders. The goal is to let the system learn through external, auditable memory lessons that can be selectively injected into otherwise stateless agent calls.

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

## Files in this base

```text
docs/openclaw_memory_lessons/README.md
  High-level architecture and integration rules.

docs/openclaw_memory_lessons/MEMORY_LESSONS.md
  Human-readable curated memory lessons.

prompts/agent_master_prompt_v0_1.md
  Shared master prompt for all LLM agents.

prompts/claude_fable_agent_prompt_v0_1.md
  Claude Fable provider-specific agent prompt built on the shared protocol.

prompts/synthesis_5_section_prompt_v0_1.md
  Locked 5-section synthesis prompt for blind assembly.

prompts/prompt_patch_policy_v0_1.md
  Rules for future small prompt improvements.
```

## Memory lesson lifecycle

A lesson should move through these states:

```text
proposed → tested → verified → stable → deprecated
```

A lesson should become `verified` only after it is supported by at least one concrete run, Proof Sprint result, ratification trace, or repeated observed failure pattern.

## Lesson types

```text
exact_output
unsupported_claim
uncertainty_control
contradiction_detection
synthesis_quality
ratification_quality
role_rotation
memory_usage
prompt_patch
provider_behavior
```

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

## Principle

```text
Agents do not own memory.
Agents receive lessons.
The system owns memory.
CED owns protocol.
Evidence owns proof.
```

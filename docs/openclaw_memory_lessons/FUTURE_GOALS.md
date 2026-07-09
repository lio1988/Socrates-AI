# Future Goals — OpenClaw Memory Lessons Layer

This file tracks the next planned steps after the documentation foundation.

The purpose is to keep the roadmap clear before runtime code is added.

## Current foundation

The branch already contains the first documentation base for:

- OpenClaw Memory Lessons Layer
- curated memory lessons
- agent prompt base notes
- 5-section synthesis design
- prompt patch policy

This is intentionally documentation-first. It should remain separate from CED core changes until the runtime integration is designed and tested.

---

## Goal 1 — Runtime lesson loader

**Status: DONE (v0).** Implemented as `backend/dialogues/openclaw_memory/lesson_loader.py`
with tests in `tests_dialogues/test_openclaw_lesson_loader.py`. Deterministic
Markdown parsing, fenced-template skipping, deprecated-by-default filtering,
stable/verified-only loading, and clean failure on malformed lessons. No
provider calls, no API keys, no network.

Create a small loader that can read curated lessons from the memory lesson source.

Expected first version:

```text
backend/dialogues/openclaw_memory/lesson_loader.py
```

Responsibilities:

- read lessons from `docs/openclaw_memory_lessons/MEMORY_LESSONS.md`
- parse lesson ids, status, type, use_when, problem pattern, lesson text, and risk
- ignore deprecated lessons by default
- allow loading only stable / verified lessons
- return a structured list of lesson records

Acceptance criteria:

- deterministic parsing
- no provider calls
- no API keys
- no network access
- unit tests with fixture text

---

## Goal 2 — Machine-readable lesson store

Markdown is good for humans, but runtime should eventually use JSONL.

Expected file:

```text
data/openclaw_memory_lessons.jsonl
```

Each record should look like:

```json
{
  "lesson_id": "LESSON-0001",
  "status": "stable",
  "lesson_type": "exact_output",
  "use_when": ["exact_text", "numeric_only", "multiple_choice"],
  "lesson": "When exact output is requested, return only the requested output.",
  "risk": "May make open-ended answers too terse if injected too broadly."
}
```

Acceptance criteria:

- JSONL export can be generated from Markdown or maintained manually
- loader validates required fields
- invalid records fail cleanly

---

## Goal 3 — Lesson retrieval

**Status: DONE (v0).** Implemented as `backend/dialogues/openclaw_memory/lesson_retriever.py`
with tests in `tests_dialogues/test_openclaw_lesson_retriever.py`. Mechanical,
deterministic relevance scoring over five auditable signals (failure tags,
role, phase, task kind, task-text keywords) using explicit enum-value ->
lesson_type maps; returns the top 2-5 with match reasons, caps output, and
never pads with unrelated lessons. Defaults to the stable/verified pool. No
scores/leaderboard read, no network, no keys.

Create a retriever that selects only the relevant lessons for the current task.

Expected first version:

```text
backend/dialogues/openclaw_memory/lesson_retriever.py
```

Inputs:

- task text
- phase
- role
- task kind when known
- previous failure tags when known

Output:

- 2 to 5 relevant lessons
- no raw scores
- no hidden leaderboard data
- no unrelated memory dump

Initial retrieval can be simple keyword / tag matching. Vector search can come later.

Acceptance criteria:

- exact-output tasks retrieve LESSON-0001
- synthesis tasks retrieve synthesis lessons
- evidence-verifier role retrieves unsupported-claim lessons
- retrieval remains deterministic

---

## Goal 4 — Agent context injection

Inject selected memory lessons into the allowed agent context.

Important rule:

```text
Agents do not own memory.
Agents receive selected lessons for the current call.
```

Possible integration points:

- `AgentTask.context`
- provider request builder
- future OpenClaw runtime adapter

The injected context should be clearly labeled:

```text
Relevant memory lessons:
- LESSON-0001: ...
- LESSON-0003: ...
```

Acceptance criteria:

- agents receive selected lessons only
- agents do not receive raw scorecards
- agents do not receive full unrelated history
- existing CED role rotation stays unchanged

---

## Goal 5 — Trace capture for learning

Every council run should be able to produce an auditable trace.

Expected future file pattern:

```text
runs/openclaw_traces/<session_id>.jsonl
```

Trace records should include:

- task id
- phase
- role assignment
- model/provider id
- allowed context summary
- selected lessons
- structured output
- synthesis sections
- ratification result
- Evidence Harness result when available

Acceptance criteria:

- no secret keys in traces
- no provider credentials
- no hidden chain-of-thought
- enough data to reproduce lesson extraction

---

## Goal 6 — Lesson proposer

Create a small component that converts repeated failures into proposed lessons.

Expected first version:

```text
backend/dialogues/openclaw_memory/lesson_proposer.py
```

It should propose lessons, not automatically promote them.

Flow:

```text
failure pattern
  ↓
proposed lesson
  ↓
human/test review
  ↓
verified lesson
```

Acceptance criteria:

- proposed lessons are marked `proposed`
- stable lessons are not overwritten automatically
- every proposed lesson includes source, problem pattern, lesson, and risk

---

## Goal 7 — Prompt registry

Create a prompt registry that loads shared prompt base notes and applies provider-specific patches.

Expected first version:

```text
backend/dialogues/openclaw_prompts/prompt_registry.py
```

Responsibilities:

- load base prompt
- apply small provider-specific patches
- fill variables such as TASK, PHASE, ROLE, MODEL_ID, MEMORY_LESSONS
- keep prompt versions explicit

Acceptance criteria:

- no full prompt rewrite at runtime
- prompt version is recorded in traces
- provider-specific patches are small and auditable

---

## Goal 8 — Prompt patch generator

Later, after enough traces exist, build a Prompt Patch Generator.

It should not rewrite prompts from scratch.

It should propose small changes like:

```text
Add one instruction for exact-output tasks.
Clarify how to mark unsupported claims.
Clarify synthesis section requirements.
```

Required safety gates:

- patch is proposed, not auto-approved
- patch includes expected effect and risk
- patch is A/B tested with Evidence Harness
- patch becomes stable only after approval

---

## Goal 9 — Proof Sprint v0.3 integration

Use Memory Lessons with a real multi-LLM or hybrid council.

Target comparison:

```text
baseline_live
vs
single_provider_ced_lite
vs
rotating_multi_llm_council
vs
local_memory_agent
```

When provider keys are available:

- Claude / Anthropic
- OpenAI / GPT
- Gemini
- Grok
- local model through OpenClaw

If only one cloud provider is available, start with:

```text
Claude baseline
vs
Claude with CED role protocol
vs
Claude with CED protocol + selected memory lessons
```

Acceptance criteria:

- live tests remain optional
- no CI dependency on API keys
- no key leakage
- Evidence Harness report saved as artifact or JSON

---

## Goal 10 — Local LLM provider for OpenClaw

Add a local provider adapter so OpenClaw can run a local model as an agent.

Possible backends:

- Ollama
- LM Studio
- local OpenAI-compatible endpoint

Expected behavior:

- local model can act as any rotating role
- selected memory lessons are injected
- outputs are structured
- failures are recorded cleanly

Acceptance criteria:

- local provider can run without cloud credits
- missing local server produces a clean skip / helpful error
- no CED core changes required for first adapter

---

## Goal 11 — OpenClaw UI panel

Build a future OpenClaw UI panel that displays the learning process.

Panel should show:

- selected task
- selected memory lessons
- role rotation
- agent outputs
- 5-section synthesis drafts
- blind assembly result
- ratification result
- Evidence Harness pass/fail
- proposed new lessons

This turns terminal output into a living evidence dashboard.

---

## Goal 12 — Fine-tuning dataset preparation

Fine-tuning is not the first learning step.

Before fine-tuning, collect enough clean examples:

- successful exact-output tasks
- unsupported-claim corrections
- contradiction detection examples
- synthesis section winners
- ratification repairs
- local-agent failures and fixes

Future dataset file pattern:

```text
data/openclaw_training_candidates.jsonl
```

Acceptance criteria before fine-tuning:

- examples are verified
- failures are corrected
- unsafe or low-quality traces are excluded
- dataset has provenance
- baseline vs tuned model can be evaluated with Evidence Harness

---

## Roadmap order

Recommended order:

```text
1. lesson_loader          # DONE (v0)
2. lesson_retriever       # DONE (v0)
3. AgentTask context injection
4. trace capture
5. lesson proposer
6. prompt registry
7. Proof Sprint v0.3 with memory lessons
8. local LLM provider
9. OpenClaw UI panel
10. prompt patch generator
11. dataset export
12. optional fine-tuning
```

---

## Non-goals for now

Do not do these yet:

- do not fine-tune immediately
- do not let agents mutate their own prompts silently
- do not expose raw scores to agents
- do not merge OpenClaw UI logic into the CED core
- do not make one provider a permanent judge
- do not make Memory Lessons a source of hidden factual truth

---

## Guiding principle

```text
OpenClaw remembers.
CED governs.
Evidence Harness measures.
Agents execute.
Prompts improve through small tested patches.
```

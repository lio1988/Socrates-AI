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

**Status: DONE (v0).** Implemented as `backend/dialogues/openclaw_memory/context_injection.py`
with tests in `tests_dialogues/test_openclaw_context_injection.py`. Non-mutating
`inject_memory_lessons(task, lessons)` returns a task copy with two OpenClaw-owned
context keys (`memory_lessons` structured + `memory_lessons_block` rendered
"Relevant memory lessons:" text); all other context and every task field (role,
phase, task_kind, question) preserved. The agent-facing payload is sanitized to
guidance only — id/lesson_type/lesson text, never relevance scores, match
reasons, or scorecards. `select_and_inject(task)` does retrieval + injection in
one shot off the task's own fields.

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

**Status: DONE (v0).** Implemented as `backend/dialogues/openclaw_memory/trace_capture.py`
with tests in `tests_dialogues/test_openclaw_trace_capture.py`. Duck-typed
`TraceCapturer.ingest_session(state, final)` wired into CED session-end as an
independently failure-isolated consumer (own try/except, separate from other
self-improvement hooks — trace failures never break a session). Builds auditable
trace with session id, question, timestamp, per-move summaries (phase/role/
provider_id/content_keys), selected openclaw lesson ids, assembly result,
ratification result, and audit keys. No secrets (api_key/sk-ant-/Bearer
assertion-guarded). Full content opt-in (`include_content=True`), JSONL file
output opt-in (`output_dir=`). Passthrough via `build_council(trace_capturer=)`.
No provider calls, no API keys, no network.

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

**Status: DONE (v0).** Implemented as `backend/dialogues/openclaw_memory/lesson_proposer.py`
with tests in `tests_dialogues/test_openclaw_lesson_proposer.py`. Mechanical
failure detectors over Goal 5 traces (ratification failed, assembly missing,
section unresolved, phase produced zero valid moves), repeated-only gating
(`min_occurrences`, default 2), deterministic proposal ids in the reserved
LESSON-9001+ provisional range. Safety proofs are mechanical: every proposal
has `status="proposed"` which the existing loader excludes from the stable
pool (never auto-injected); `write_proposed_lessons` refuses the curated
MEMORY_LESSONS.md outright; proposals round-trip through `parse_memory_lessons`
byte-consistently. Every proposal carries source (session ids), problem
pattern, lesson, and risk. Lesson types stay inside the retriever taxonomy so
promoted lessons are immediately retrievable. No provider calls, no keys.

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

### Goal 6.1 — Lesson effectiveness A/B harness

**Status: DONE (v0).** Implemented as
`backend/dialogues/openclaw_memory/lesson_ab.py`
(`run_lesson_ab`, schema `lesson_ab_v0`) with tests in
`tests_dialogues/test_lesson_ab.py`. Closes the LESSON POISONING gap: a
matched-pair experiment per question (control council without lessons vs an
identically-built treatment council with them, SAME session id so the
lessons are the only difference) compares mechanical outcomes (ratification,
mean assembled section score, unresolved counts). Questions where retrieval
selected zero lessons are honestly UNTESTED; either arm failing assembly is
INVALID. `helped` requires positive mean delta AND zero ratification
regressions. The harness reports; a human moves the lesson through its
lifecycle — this is the instrument for the lifecycle's `tested` step
(proposed → tested → verified → stable). Rigged-provider tests prove the
full pipeline (injection → behavioral effect → blind scoring → measurement)
and that a poisonous pool is detected as `harmed`.

---

## Goal 7 — Prompt registry

**Status: DONE (v0 foundation).** Implemented as
`backend/dialogues/openclaw_prompts/prompt_registry.py` with tests in
`tests_dialogues/test_prompt_registry.py`; design doc
[PROMPT_REGISTRY.md](PROMPT_REGISTRY.md)
(`OPENCLAW_MEMORY_LESSONS_PROMPT_REGISTRY`). PromptSpec (base template +
strict `{{variables}}` + memory-lesson slot that collapses cleanly) +
append-only provider-scoped PromptPatch records carrying the SAME lifecycle
as lessons. Never-auto-mutate is mechanical: default render applies only
stable/verified patches; a proposed patch renders only when NAMED explicitly
as an A/B candidate; deprecated never renders. Version identity = human
label + content-addressed sha256 fingerprint (tamper-evident); trace-ready
`prompt_metadata` fits `TraceCapturer(metadata=...)` as-is; render refuses
key-shaped secrets. Runtime-inert (CED core and reasoning_prompts.py never
import it, test-locked) — wiring a rendered prompt into live calls is a
later, explicit goal.

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

## Goal 11 — OpenClaw Shadow Apprentice Mode

Create a safe training mode where the local agent observes and compares before it becomes a full council member.

Core idea:

```text
The local agent should learn beside the council before it influences the council.
```

In Shadow Apprentice Mode, the local model receives the same task and selected memory lessons, produces its own structured answer, but does not affect synthesis, scoring, ratification, or the final answer.

Flow:

```text
Cloud / existing council runs normally
  ↓
CED produces synthesis and ratification
  ↓
Local apprentice produces shadow output for the same task
  ↓
OpenClaw compares local output with ratified output and Evidence Harness result
  ↓
Lesson proposer extracts what the local apprentice missed or did well
  ↓
Memory Lessons improve future local runs
```

Stages:

```text
Stage 1 — Shadow
Local agent answers in parallel but has no effect on the final answer.

Stage 2 — Apprentice
Local agent may contribute low-risk sections such as blind_spots or nuance, but cannot decide final verdict.

Stage 3 — Candidate
Local agent can enter SYNTHESIS and win individual sections if its sections score well.

Stage 4 — Full Council Member
Local agent receives normal rotating roles like any other provider.
```

Metrics to track:

- exact-output format violations
- unsupported-claim rate
- contradiction detection quality
- similarity to ratified stable claims
- useful blind-spot discovery
- synthesis section win rate
- ratification objection quality

Acceptance criteria:

- shadow output is recorded separately from final council output
- shadow output never changes final answer in Stage 1
- comparison produces proposed lessons, not automatic prompt changes
- no hidden scorecards are injected into future agent context
- promotion between stages requires test results or explicit approval

Why this matters:

OpenClaw can train a local model safely, without risking council quality. The local model first watches, predicts, compares, and improves. Only later does it earn participation.

---

## Goal 12 — OpenClaw UI panel

Build a future OpenClaw UI panel that displays the learning process.

Panel should show:

- selected task
- selected memory lessons
- role rotation
- agent outputs
- local apprentice shadow output
- 5-section synthesis drafts
- blind assembly result
- ratification result
- Evidence Harness pass/fail
- proposed new lessons

This turns terminal output into a living evidence dashboard.

---

## Goal 13 — Fine-tuning dataset preparation

Fine-tuning is not the first learning step.

Before fine-tuning, collect enough clean examples:

- successful exact-output tasks
- unsupported-claim corrections
- contradiction detection examples
- synthesis section winners
- ratification repairs
- local-agent failures and fixes
- Shadow Apprentice comparisons

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

## Goal 14 — Self-Improving Agent Identity Layer

**Status: DONE (v0 foundation).** Docs:
`SELF_IMPROVING_AGENT_IDENTITY.md` (canonical
`OPENCLAW_MEMORY_LESSONS_AGENT_IDENTITY`) and `AGENT_SOUL_CARD.md`
(canonical `OPENCLAW_MEMORY_LESSONS_AGENT_SOUL_CARD`). Runtime:
`backend/dialogues/openclaw_identity/` — pure, deterministic, offline,
system-owned and runtime-inert (the CED core never imports it, test-locked).

The auditable, versioned identity profile per agent seat ("soul",
non-mystical): trace-derived `role_strengths` (assembly winner → move →
provider, mechanical counts, no hidden scorecards), curator-supplied
`known_failures` / `stable_lessons`, the 8-stage identity ladder
(base_agent → master_branch_researcher, one rung at a time), declarative
evidence-backed version gates (v0.1 → v1.0), and the Soul Card readable
summary (descriptive, not authority).

Never-auto-promote is mechanical: `evaluate_gate` only recommends; a
promotion record requires a PASSING gate plus a named approver who is not
the agent itself. Missing evidence fails honestly.

Guiding sentence:

```text
The agent does not become powerful because it claims identity.
The agent earns identity through evidence.
```

Sub-steps landed since v0 (referenced as 13.1/13.2 in the commit
messages, before this goal was renumbered to 14 in the merge with the
docs-side history): identity registry + instrument-fed gate evidence
(`845bcf9`) and capture-time shadow-run markers with verified shadow
evidence (`196a892`). Still deliberately open: auto-linking
lesson-proposer patterns to `known_failures`.

---

## Roadmap order

Recommended order:

```text
1. lesson_loader          # DONE (v0)
2. lesson_retriever       # DONE (v0)
3. AgentTask context injection  # DONE (v0) + CED WIRED
4. trace capture          # DONE (v0)
5. lesson proposer        # DONE (v0)
6. prompt registry
7. Proof Sprint v0.3 with memory lessons
8. local LLM provider
9. Shadow Apprentice Mode
10. OpenClaw UI panel
11. prompt patch generator
12. dataset export
13. optional fine-tuning
14. agent identity layer  # DONE (v0 foundation + registry/evidence + shadow markers)
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
- do not let the local apprentice affect final answers before promotion

---

## Guiding principle

```text
OpenClaw remembers.
CED governs.
Evidence Harness measures.
Agents execute.
The local apprentice watches before it acts.
Prompts improve through small tested patches.
```

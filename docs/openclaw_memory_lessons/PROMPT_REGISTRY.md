# Prompt Registry — versioned, auditable prompt lineage

**Canonical name:** `OPENCLAW_MEMORY_LESSONS_PROMPT_REGISTRY`
**Runtime (v0):** `backend/dialogues/openclaw_prompts/prompt_registry.py`
**Policy it enforces:** [PROMPT_PATCH_POLICY.md](PROMPT_PATCH_POLICY.md)

The missing control layer this closes: prompts had no version identity. A
prompt that drifts silently cannot be A/B tested, cannot be traced, and
cannot be trusted.

```text
No production prompt changes automatically.
Every prompt has a version. Every version has a fingerprint.
Every patch has a lifecycle. Every render is reproducible.
```

---

## 1. The prompt spec

A `PromptSpec` is the declarative identity of one prompt:

```text
prompt_id            stable identifier ("openclaw_synthesis")
version_label        human lineage label ("v0.1")
description          what this prompt is for
base_text            the template, with {{variables}}
required_variables   e.g. ("role", "phase", "question")
lesson_slot          the memory-lesson context slot (default "memory_lessons")
patches              ordered PromptPatch records
```

**Placeholders are double-brace** (`{{role}}`, `{{phase}}`, `{{question}}`,
`{{model_id}}`, `{{memory_lessons}}`) — deliberately, because prompt bodies
legitimately contain JSON examples with single braces; `str.format` would
break them.

**Rendering is strict**: a missing required variable refuses; an unknown
supplied variable refuses. No silent empty slots, no silent extras.

## 2. The memory-lesson context slot

The `{{memory_lessons}}` slot receives the rendered lessons block from the
Goal 3/4 retrieval + injection pipeline (`render_memory_lessons_block`).
When no lessons are supplied the slot **collapses cleanly** — no dangling
"Relevant memory lessons:" header, no triple blank lines.

## 3. Provider-specific patches

A `PromptPatch` is a small, **append-only** block scoped to providers:

```text
patch_id           "PATCH-0001"
name / status      lifecycle: proposed -> tested -> verified -> stable -> deprecated
text               the appended block
reason             why (PROMPT_PATCH_POLICY audit field)
expected_effect    what should improve
risk               what could get worse
target_providers   provider ids, or "*" for all
```

v0 deliberately has **no replace/delete operations** — every patch is
reversible by construction, exactly what the patch policy demands.

## 4. Never-auto-mutate (mechanical, not aspirational)

- A default render applies **only stable/verified** patches.
- A proposed patch renders **only when named explicitly** as a candidate
  (`candidate_patch_ids=["PATCH-0003"]`) — that is how it gets its A/B run.
  Blanket "include all proposed" does not exist. Naming an unknown patch id
  raises: an experiment must know exactly what it is testing.
- **Deprecated never renders**, even when named.
- The Lesson A/B harness pattern (Goal 6.1) is the shared "tested"
  instrument: control render (no candidate) vs treatment render (one named
  candidate), same question, same council build — the patch earns `tested`,
  then human review moves it to `verified`/`stable`.

## 5. Version identity: label + fingerprint

Every composition has two identities:

```text
version_label        human lineage ("v0.1") — bumped on curated evolution
prompt_fingerprint   sha256[:12] of (base_text + applied patch texts, in order)
```

The fingerprint is **content-addressed and tamper-evident**: any change to
the base text or the applied patch set changes it. Two providers with
different patch sets get different fingerprints for the same prompt version.

## 6. Trace-compatible metadata

`prompt_metadata(spec, provider_id)` returns the audit record that travels
with traces (it fits `TraceCapturer(metadata=...)` as-is):

```json
{
  "prompt_id": "openclaw_synthesis",
  "prompt_version": "v0.1",
  "prompt_fingerprint": "a1b2c3d4e5f6",
  "applied_patches": ["PATCH-0001"],
  "candidate_patches": [],
  "provider_scope": "anthropic_seat0",
  "lesson_slot": "memory_lessons"
}
```

Lineage only — no prompt text, no scores, no secrets. A render additionally
refuses outright if the composed text carries key-shaped secrets
(`sk-ant-`, `Bearer `, `ANTHROPIC_API_KEY`).

## 7. What v0 deliberately does NOT do

- **No runtime activation.** The CED core and `reasoning_prompts.py` never
  import this package (test-locked, same isolation as the identity layer).
  Wiring a registry-rendered prompt into live calls is a later, explicit
  goal with its own A/B evidence.
- **No automatic patch generation** — that is Goal 8 (prompt patch
  generator), which will PROPOSE patches into this registry's lifecycle,
  never promote them.
- **No replace/delete patch operations** — append-only until evidence says
  otherwise.

## 8. Relation to the existing live prompts

`backend/dialogues/reasoning_prompts.py` remains the production prompt
composer, untouched. The registry starts the *lineage discipline* that the
existing prompts will migrate into: first describe, version, and trace —
then, in a separate goal, wire a registry-rendered prompt behind an A/B
gate. Describing before replacing is the same docs-first pattern the whole
branch follows.

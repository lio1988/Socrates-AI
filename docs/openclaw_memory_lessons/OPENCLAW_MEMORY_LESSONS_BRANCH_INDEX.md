# OpenClaw Memory Lessons — Branch Index

Canonical names for every document in the OpenClaw Memory Lessons layer.
Reference documents by canonical name in commits, lessons, and proposals so
links survive file moves.

| Canonical name | File | What it is |
|---|---|---|
| `OPENCLAW_MEMORY_LESSONS_README` | [README.md](README.md) | High-level architecture, boundaries, what agents may see |
| `OPENCLAW_MEMORY_LESSONS_MEMORY_LESSONS` | [MEMORY_LESSONS.md](MEMORY_LESSONS.md) | The curated lesson store (LESSON-0001…), lifecycle proposed→stable |
| `OPENCLAW_MEMORY_LESSONS_FUTURE_GOALS` | [FUTURE_GOALS.md](FUTURE_GOALS.md) | The 13-goal roadmap with per-goal status |
| `OPENCLAW_MEMORY_LESSONS_BRANCH_STATE` | [BRANCH_STATE.md](BRANCH_STATE.md) | Honest snapshot of what exists on this branch right now |
| `OPENCLAW_MEMORY_LESSONS_AGENT_PROMPT_BASE` | [AGENT_PROMPT_BASE.md](AGENT_PROMPT_BASE.md) | Shared agent prompt foundation notes |
| `OPENCLAW_MEMORY_LESSONS_PROMPT_PATCH_POLICY` | [PROMPT_PATCH_POLICY.md](PROMPT_PATCH_POLICY.md) | Rules for small, tested, approved prompt patches (no silent mutation) |
| `OPENCLAW_MEMORY_LESSONS_SYNTHESIS_5_SECTION` | [SYNTHESIS_5_SECTION.md](SYNTHESIS_5_SECTION.md) | The locked 5-section synthesis design |
| `OPENCLAW_MEMORY_LESSONS_AGENT_IDENTITY` | [SELF_IMPROVING_AGENT_IDENTITY.md](SELF_IMPROVING_AGENT_IDENTITY.md) | Self-Improving Agent Identity Layer: ladder, gates, safety boundaries |
| `OPENCLAW_MEMORY_LESSONS_AGENT_SOUL_CARD` | [AGENT_SOUL_CARD.md](AGENT_SOUL_CARD.md) | The readable, auditable identity summary (descriptive, not authority) |

Related documents outside this folder:

| Canonical name | File | What it is |
|---|---|---|
| `DELIBERATION_TREE_ARCHITECTURE` | [../deliberation_tree/ARCHITECTURE.md](../deliberation_tree/ARCHITECTURE.md) | AlphaGo-style search layer: tree search, distill step, Promotion Arena |

Runtime packages this layer owns:

| Package | Purpose |
|---|---|
| `backend/dialogues/openclaw_memory/` | lesson_loader, lesson_retriever, context_injection, trace_capture, lesson_proposer |
| `backend/dialogues/openclaw_identity/` | identity_profile, promotion_policy, soul_card (system-owned, runtime-inert) |

Constitution:

```text
CED governs.
Evidence Harness measures.
OpenClaw remembers.
Agents execute.
Identity is earned through verified performance.
```

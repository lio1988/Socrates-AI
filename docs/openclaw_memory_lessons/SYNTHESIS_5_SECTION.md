# SYNTHESIS 5-Section Blind Assembly v0.1

This document records the synthesis method used by the CED / OpenClaw council.

## Core idea

The final answer should not be selected as one whole winning draft.

Instead, each agent produces a locked five-section draft. CED then scores and assembles the final answer section-by-section.

## Five locked sections

1. `core_answer`
   - The clearest direct answer.

2. `crucial_stress_test`
   - The strongest challenge, objection, or failure mode.

3. `blind_spots`
   - Missing evidence, unresolved uncertainty, weak assumptions, or under-examined areas.

4. `nuance`
   - Important distinctions, conditions, tradeoffs, or edge cases.

5. `final_verdict`
   - The most defensible final position.

## Assembly rule

Each section is evaluated independently.

```text
core_answer may come from Agent A
crucial_stress_test may come from Agent B
blind_spots may come from Agent C
nuance may come from Agent D
final_verdict may come from Agent A or another agent
```

CED does not semantically rewrite the answer during blind assembly. It mechanically selects the highest-scoring section according to the scoring protocol and deterministic tie-breakers.

## Why this matters

This lets the council use the strongest part of each model instead of letting one model dominate the whole answer.

It also protects against provider bias:

```text
A model can lose the whole draft but still contribute the best stress test.
A model can be weak in final wording but strong in blind spot detection.
A model can be strong in nuance but not in direct answer.
```

## Tie-breakers

When two sections have the same score, use deterministic tie-breakers:

1. highest average overall score
2. lower variance
3. higher score count
4. deterministic draft id order

## Ratification

After assembly, a ratification reviewer checks the assembled answer.

A critical objection targeting one section should trigger runner-up replacement for that section when available.

If no runner-up remains, or if ratification rounds are exhausted, the section should be marked unresolved.

## Integration with Memory Lessons

Memory lessons should help agents improve each section without leaking hidden scores.

Examples:

- Exact-output lessons help `final_verdict`.
- Unsupported-claim lessons help `core_answer` and `nuance`.
- Uncertainty lessons help `blind_spots`.
- Critique lessons help `crucial_stress_test`.

## Next step

Create a runtime schema for section drafts and a prompt registry entry that asks every synthesizer to fill the same five sections.

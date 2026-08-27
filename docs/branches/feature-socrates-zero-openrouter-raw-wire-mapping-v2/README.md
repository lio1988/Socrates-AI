# Branch: feature/socrates-zero-openrouter-raw-wire-mapping-v2

Phase 8.5D-S5 — OpenRouter Raw Wire-Mapping v2.

One bounded, offline implementation attempt, authorized by the published S4 gate.

## Hypothesis

> A deterministic, raw-response-first OpenRouter wire mapper can be implemented
> solely from the retained official v2r1 evidence, such that documented response
> fields are parsed and mapped losslessly, undocumented or unavailable
> authorities remain explicit epistemic states, malformed/contradictory wire
> evidence fails closed, unknown/additive fields remain non-authoritative, and no
> repository convention or historical canned-response assumption is needed.

## Success criterion

`OPENROUTER RAW WIRE-MAPPING v2 SUPPORTED` only if every predeclared threshold
in [PLAN.md](PLAN.md) is met, including zero false authority grants, zero
endpoint synthesis, deterministic replay, and unchanged frozen predecessors.
Otherwise `FALSIFIED`. No soft pass.

## Scope

Additive only:

- `backend/dialogues/socrates_zero/openrouter_raw_wire_mapping_v2.py`
- `backend/dialogues/socrates_zero/openrouter_raw_wire_mapping_cases_v2.py`
- `backend/dialogues/socrates_zero/openrouter_raw_wire_mapping_evaluation_v2.py`
- focused tests, branch documentation, one authoritative artifact plus replay.

## Non-goals

No live call. No production adapter change. No CED consumption. No replacement of
the Route Controls parser v1. No runtime authority. No P17/P18/P19 work. No
second official-source retrieval.

## What remains blocked

P17, P18 and P19 stay NOT_ESTABLISHED. Runtime authority stays NOT AUTHORIZED.
Live OpenRouter execution stays NOT AUTHORIZED, whatever this branch concludes.

## Documents

- [MEMORY.md](MEMORY.md) — stable context and invariants.
- [PLAN.md](PLAN.md) — plan, predeclared thresholds, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state.
- [artifacts/README.md](artifacts/README.md), [evidence/README.md](evidence/README.md).

Canonical result:
[docs/SOCRATES_ZERO_OPENROUTER_RAW_WIRE_MAPPING_V2.md](../../SOCRATES_ZERO_OPENROUTER_RAW_WIRE_MAPPING_V2.md).

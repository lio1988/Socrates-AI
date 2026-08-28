# Branch: fix/openrouter-wire-spec-acquisition-timestamp-race

Removes a clock race in the one-shot OpenRouter wire-spec source acquisition
script that could make the retrieval log refuse to build.

## Purpose

`acquire_openrouter_wire_spec_sources_v1` read the wall clock twice per source:
once for the retained snapshot's `retrieved_utc`, once for the retrieval event's
`completed_utc`. `_utc_now()` has one-second precision and the retrieval log
contract requires the two to be equal, so a second boundary landing between the
reads made the log unbuildable. Reading the clock once per source and reusing
that value removes the race.

## Success criterion

A retrieval run completes and its log validates even when the clock advances
between every read — proven by a regression test that advances the clock one
second on *every* `_utc_now()` call, which is the worst case a real clock can
produce. The test fails without the fix with the exact production error
(`retrieval event and snapshot bytes diverge`).

## Scope

- `scripts/acquire_socrates_zero_openrouter_wire_spec_sources_v1.py` — one clock
  read per source instead of two.
- `tests_dialogues/test_socrates_zero_openrouter_wire_spec_source_acquisition_v1.py`
  — the regression test.
- This branch documentation.

## Non-goals

- **No contract change.** `OpenRouterWireRetrievalLogV1`'s equality check between
  `snapshot.retrieved_utc` and `event.completed_utc` is correct and stays exactly
  as it is. The double read was the bug; the check is what caught it.
- No change to `_utc_now()`'s precision, format, or to any timestamp already
  written into retained evidence.
- No change to `_failure_event`, which builds events that carry no snapshot and
  are therefore not subject to the equality constraint.
- No change to any Socrates-Zero OpenRouter pre-live module. The branch
  `feature/socrates-zero-openrouter-prelive-integration-v1` is mid-experiment
  behind a pre-authoritative freeze and must not be disturbed.
- Not pushed.

## Documents

- [MEMORY.md](MEMORY.md) — invariants and the diagnosis that shaped the fix.
- [PLAN.md](PLAN.md) — plan, validation gates, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state.

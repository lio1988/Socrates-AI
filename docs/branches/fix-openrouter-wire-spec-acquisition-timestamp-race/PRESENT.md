# PRESENT — fix/openrouter-wire-spec-acquisition-timestamp-race

## State

- Branch: `fix/openrouter-wire-spec-acquisition-timestamp-race`
- Base: `0d09822` (`feature/socrates-zero-openrouter-wire-spec-evidence-v2r1`)
- Phase: **fix complete, tested, committed. Not merged anywhere.**

## What it fixes

`acquire_openrouter_wire_spec_sources_v1` read the wall clock twice per source —
once for `snapshot.retrieved_utc`, once for `event.completed_utc` — at
one-second precision, while the retrieval log contract requires the two to be
equal. Crossing a second boundary between the reads made the log refuse to
build, so the test passed standalone and failed under load.

The loop now reads the clock once per source and reuses that value.

## Why the contract was not touched

The equality check is correct: it is exactly the cross-check that caught this.
Relaxing it to a tolerance would have traded a visible intermittent failure for
a silent inconsistency in retained evidence.

## Tests

`test_socrates_zero_openrouter_wire_spec_source_acquisition_v1.py`: **4 passed**,
including a regression test that advances the clock on *every* read — the worst
case a real clock can produce — and fails without the fix with the exact
production error.

## Deliberately not merged

The later live-call phases forbade merging or cherry-picking this fix into them,
because it touches a predecessor file and would have broken their byte-identity
gates. It stays here until someone decides where it lands.

Not pushed.

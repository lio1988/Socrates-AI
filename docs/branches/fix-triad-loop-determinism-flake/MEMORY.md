# Branch: fix/triad-loop-determinism-flake

## Exact failure

The failing assertion was:

`assert result_a.loop_id == result_b.loop_id`

One standalone RED run produced:

- `result_a.loop_id = triad_bf053268f9f1eefe`
- `result_b.loop_id = triad_3248ae1340b428b8`

The packet and learner IDs also had two semantic outcomes:

- `ced_feedback_10734f937e9a15ea` versus
  `ced_feedback_2d00e62ce3831c2c`
- `learner_eeb747c6703346c9` versus `learner_c91afb006abae960`

## Order-pollution result

Collection placed the failing node at zero-based index 524. Its immediate
predecessor was
`test_build_ced_feedback_packet_contains_safe_fields`, but the failing node
also failed by itself in a fresh process. The minimal polluting prefix is
therefore empty: no previous test or test file is required.

## Root cause

`learning_foundation._uid()` used only a formatted wall-clock timestamp.
Windows may return the same timestamp for adjacent records. A captured failing
run had two traces but only one unique `trace_id`:

- `task_initial` and `task_reconstruction` both received
  `trace_20260719075203745503`.

Preference and process miners index traces by `trace_id` and reject apparent
self-pairs. The collision therefore changed real semantic output:

- process transitions: `0` instead of `1`;
- export artifacts: `1` instead of `5`;
- trainer and advisory summaries diverged;
- learner, packet, and loop stable IDs correctly reflected those semantic
  differences.

This was not merely a volatile identifier leaking into a hash. It was an
identity collision changing the pipeline graph before hashing.

## Deterministic invariant

Opaque record IDs may vary between runs, but distinct records must never
collapse to one identity. After volatile IDs are removed by the existing
canonical policy, equal semantic inputs must produce equal stable triad IDs;
different semantic inputs must still produce different IDs.

## Non-negotiable constraints

- Preserve all semantic fields in deterministic payloads.
- Preserve miner self-pair and dictionary-key protections.
- Do not add retries, timing workarounds, skips, or assertion relaxation.
- Do not touch Council Live View work.

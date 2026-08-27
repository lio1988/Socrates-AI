# PLAN — feature/socrates-zero-openrouter-prelive-integration-v1

## Success criterion

`OPENROUTER PRE-LIVE INTEGRATION v1 SUPPORTED` only if every predeclared
threshold below is met. Otherwise FALSIFIED. No soft pass.

The live-call decision is reported **separately** and in layers: integration can
be SUPPORTED while a live call remains NOT_AUTHORIZED.

## Predeclared thresholds

| # | threshold | required |
| --- | --- | --- |
| 1 | integration positive cases accepted | 12 |
| 2 | integration adversarial cases rejected | 18 |
| 3 | preflight authorized cases | 3 |
| 4 | preflight refused cases | 23 |
| 4b | ceiling probes holding | 26 |
| 5 | unexpected results | 0 |
| 6 | invalid fixture constructions | 0 |
| 7 | guard-code mismatches | 0 |
| 8 | cross-request substitutions accepted | 0 |
| 9 | request → response authority leaks | 0 |
| 10 | provider → endpoint synthesis | 0 |
| 11 | requested → actual substitutions | 0 |
| 12 | metadata-absence → cache-hit inferences | 0 |
| 13 | authorization reuse accepted | 0 |
| 14 | privacy leakage findings | 0 |
| 15 | external activity, every category | 0 |
| 16 | deterministic replay | semantic, artifact-ID and byte identity |
| 17 | frozen predecessor files | all unchanged (742/742 measured) |

## Status

Implementation, cases, evaluator and the single frozen-v3 authoritative run are
complete. The hypothesis is **SUPPORTED**: every threshold passed, and replay
established semantic equality, artifact-ID equality and byte identity. All
post-authoritative regression gates passed and no stop condition triggered.

The live call is separately **NOT_AUTHORIZED**. P17 remains the single structural
blocker; incomplete applicable-charge coverage from unbounded `request_usd`
remains a separate policy gap.

Before frozen-v3 execution, the prior freezes were superseded unconsumed:
`4861c8a4` (original), `fd30a7fb` (rulings applied), and `170124a` (price
ceiling). The current freeze splits P19 into structure / coverage / authority.
The run at `0ff79c9` is superseded and its artifacts are preserved in history
only.

## Ordered steps

1. **Initialize** branch documentation.
2. **Implement** the causal integration contracts.
3. **Implement** the pre-live safety, budget and one-call authorization contracts.
4. **Freeze** fixtures and the three case sets.
5. **Implement** the deterministic evaluator.
6. **Freeze** every semantic file in a commit *before* the authoritative run.
7. **Complete:** execute exactly one authoritative offline evaluation; persist;
   replay.
8. **Complete:** document the result and close the checkpoint.

## Stop conditions

Falsify rather than proceed if any cross-request substitution is accepted, any
response authority can be filled from request intent, one-shot dispatch cannot be
enforced, privacy leakage is found, replay is nondeterministic, or any frozen
predecessor surface changes.

After the authoritative run, only tests and documentation may change. Any
semantic change invalidates the result; it is not re-run as the same experiment.

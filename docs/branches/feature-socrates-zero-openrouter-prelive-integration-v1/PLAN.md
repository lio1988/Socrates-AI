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
| 3 | preflight authorized cases | 1 |
| 4 | preflight refused cases | 14 |
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
| 17 | frozen predecessor surfaces | 19/19 unchanged |

## Ordered steps

1. **Initialize** branch documentation.
2. **Implement** the causal integration contracts.
3. **Implement** the pre-live safety, budget and one-call authorization contracts.
4. **Freeze** fixtures and the two case sets.
5. **Implement** the deterministic evaluator.
6. **Freeze** every semantic file in a commit *before* the authoritative run.
7. **Execute** exactly one authoritative offline evaluation; persist; replay.
8. **Document** the result and close the checkpoint.

## Stop conditions

Falsify rather than proceed if any cross-request substitution is accepted, any
response authority can be filled from request intent, one-shot dispatch cannot be
enforced, privacy leakage is found, replay is nondeterministic, or any frozen
predecessor surface changes.

After the authoritative run, only tests and documentation may change. Any
semantic change invalidates the result; it is not re-run as the same experiment.

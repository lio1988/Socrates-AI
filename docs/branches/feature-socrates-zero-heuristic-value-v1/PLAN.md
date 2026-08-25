# Branch: feature/socrates-zero-heuristic-value-v1

## Success criterion

Scientifically test the pre-registered deterministic Value-v1 hypothesis with a
chronologically frozen canonical holdout and no architecture expansion.

## Ordered work

1. [in progress] Freeze estimator semantic constants and structured audit
   contracts without implementing estimator behavior.
2. [pending] Freeze evaluation contracts, all 45 canonical case blueprints,
   split, metrics, thresholds, and identity/label firewalls.
3. [pending] Add leakage, provenance, reward-farming, terminal, purity, and
   malformed-input tests.
4. [pending] Implement `heuristic-value-estimator/v1` without changing v0.
5. [pending] Run development validation without semantic tuning.
6. [pending] Freeze the authoritative holdout runner after focused gates pass.
7. [pending] Execute the first holdout once, persist its immutable artifact,
   replay it, and classify the primary gate.
8. [locked] Run the matched BestOfN secondary gate only if primary passes.
9. [pending] Run the full required regression matrix and finalize docs/ADR.

## Stop conditions

Stop before secondary search if any primary threshold fails. Preserve every
negative authoritative artifact. Do not tune weights, cases, labels, split,
metrics, thresholds, or ordering after the first holdout result.

# Branch: feature/socrates-zero-heuristic-value-v1

## Success criterion

Scientifically test the pre-registered deterministic Value-v1 hypothesis with a
chronologically frozen canonical holdout and no architecture expansion.

## Ordered work

1. [done] Freeze estimator semantic constants and structured audit
   contracts without implementing estimator behavior.
2. [done] Freeze evaluation contracts, all 45 canonical case blueprints,
   split, metrics, thresholds, and identity/label firewalls.
3. [done] Add leakage, provenance, reward-farming, terminal, purity, and
   malformed-input tests.
4. [done] Implement `heuristic-value-estimator/v1` without changing v0.
5. [done] Run development validation without semantic tuning.
6. [done] Freeze the authoritative holdout runner after focused gates pass.
7. [done] Execute the first holdout once, persist its immutable artifact,
   replay it, and classify the primary gate.
8. [done] Run the matched BestOfN secondary gate; primary passed.
9. [done] Run the full required regression matrix and finalize docs/ADR.
10. [done] Audit successor seams, CED transition ownership, open-world
    observation separation, depth-two blockers, branch isolation, replay
    primitives, provider controls, fairness, episode schema, and learning/RL
    readiness.
11. [done] Compare read-only real shadow collection against a canonical
    successor environment and choose exactly one next milestone.
12. [done] Select `CANONICAL SUCCESSOR ENVIRONMENT NEXT`, define the bounded
    offline one-transition hypothesis, and preserve every Phase 7 component.

## Stop conditions

Stop before secondary search if any primary threshold fails. Preserve every
negative authoritative artifact. Do not tune weights, cases, labels, split,
metrics, thresholds, or ordering after the first holdout result.

## Completion

Primary and secondary gates both passed. Phase 7 is complete. Phase 7.5 is also
complete as an analysis-only gate and selects
`feature/socrates-zero-canonical-successor-env-v0` as the single next branch.
Implementation does not begin here. Real shadow calls, depth two, learning, RL,
and production authority remain blocked.

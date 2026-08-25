# Stable branch memory

## Sealed lineage

- Analysis base: `f1497faa762cd33e4cc939bd7bd18fa6d2ea974c`.
- Sealed artifact commit:
  `07ec5ab14cd1599ffd6c8c4b6442d56d51129f11`.
- Artifact ID:
  `cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0`.
- Artifact SHA-256:
  `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.
- Status: permanently `FALSIFIED`.
- Sole mismatch: `wrong-provider`, expected
  `OBSERVATION_PROVIDER_MISMATCH`, actual `ROOT_CONTEXT_MISMATCH`.

The result must never be changed, regenerated, reclassified, or described as a
pass. Core transition parity was supported; the complete v1 hypothesis was not.

## Stable architecture findings

- CED derives `council_roster` from available adapters and inserts it into the
  public `AgentTask.context`; it is not stored in `SessionState`.
- Provider catalog ID changes therefore change roster seat labels, context,
  context/request/task digests, and root lineage.
- Compatibility source order is root context → task/action → provider → model →
  configuration → residual lineage.
- The runtime already implements deterministic first-guard-wins and failed
  safely; no runtime semantic change is required.
- Provider mismatch is conditional/contract-level reachable only through a
  roster-preserving private binding change; no normal CED rebinding operation
  produces it for the selected opening lifecycle.
- Model mismatch is conditional on authoritative model identity changing without
  changing its public roster display.
- A named configuration-only input such as registry timeout can reach the
  configuration guard while preserving all earlier binding guards.
- Context binding is intentionally strong and must not be weakened to recover a
  diagnostic label.

## Decision

- Exactly one decision: `NEW VERSIONED SUCCESSOR EXPERIMENT EARNED`.
- Governing precedence: Model A — First Canonical Guard Wins.
- Runtime environment stays `ced-canonical-successor-env/v0`.
- Exact next branch:
  `feature/socrates-zero-canonical-successor-parity-v2`.
- Proposed v2 matrix: five unchanged supported cases, eleven orthogonal
  negatives, and seven precedence negatives.

## Immutable scientific hashes

- Phase 5:
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Phase 7 primary:
  `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- Phase 7 BestOfN:
  `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- Phase 8 falsified artifact:
  `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.

## Non-negotiable constraints

- No aggregate, artifact builder, replay publication, provider, model, or tool
  call during Phase 8R.
- No runtime, CED, SearchState, Projection, Value, Policy, search, Hybrid,
  shadow, depth, or failure-code change.
- Preserve the v1 artifact/corpus/taxonomy byte-for-byte.
- Preserve the two protected untracked files and never stage them.

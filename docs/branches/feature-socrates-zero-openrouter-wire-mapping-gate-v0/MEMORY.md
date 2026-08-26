# Phase 8.5D-R memory

## Sealed checkpoint

- Parent branch: `feature/socrates-zero-openrouter-route-controls-v1`.
- Parent HEAD: `31d56c944717bee8f9ae4ba8f00538155b239d36`.
- Artifact ID:
  `szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd`.
- Artifact SHA-256:
  `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`.
- Artifact status: `FALSIFIED`.
- Replay: `NOT PERFORMED`.
- Official wire-mapping violations: 1; allowed maximum: 0.

## Immutable boundaries

Do not modify or regenerate the sealed artifact, replay, Route Controls v1
renderer/parser/cases/evaluator semantics, Phase 8.5C manifest, predecessor
artifacts, frozen tests, or production adapters. Do not fetch documentation or
access credentials/network/providers/models/tools/CED.

## Protected local files

Never stage or modify:

- `scripts/live_dialogue.py.bak`;
- the malformed root filename beginning `ocratic_followup_mandate`.

## Gate decision

- Exactly one decision:
  `SPECIFICATION EVIDENCE MANIFEST v1 REQUIRED FIRST`.
- Next branch:
  `feature/socrates-zero-openrouter-wire-spec-evidence-v1`.
- The violation is global and not case-attributable. Artifact forensics are
  insufficient to name one exact official field/path mismatch.
- Retained exact local tokens: `openrouter_metadata`, `attempt`, `provider`,
  `pipeline`.
- Missing local tokens: `requested_model`, `requested_provider_only`,
  `routing_strategy`, `actual_model`, `attempts`.
- Structured official schema, complete types, exact placement, and
  official-wire-to-local mapping are absent from manifest v0.
- All positive response fixtures are repository-normalized, not official-shape.

## Repository boundary

- Exact isolated static test: deterministic assertion failure in four runs.
- Offending evaluator references: provenance inventory strings at lines 1624
  and 1635; no predecessor case import or route-semantic consumption.
- Existing raw-reference inventory contract: valid and currently violated.
- Teardown error: not reproduced in isolation.
- Runtime route semantic change required: no.
- A later version-aware provenance closure remains required, but specification
  evidence is the dependency-ordered first step.

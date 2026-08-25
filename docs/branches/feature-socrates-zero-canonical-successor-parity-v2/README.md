# Branch: feature/socrates-zero-canonical-successor-parity-v2

## Purpose

Run one new, pre-registered Phase 8 v2 evaluation experiment over the unchanged
CED-owned canonical successor environment.  The experiment freezes First
Canonical Guard Wins semantics, dependency-aware probe vectors, five existing
supported observations, eleven orthogonal probes, and seven precedence probes
before its first authoritative aggregate.

## Success criterion

All 23 frozen cases must meet their exact thresholds, the first authoritative
artifact must remain immutable, a passing result must replay byte-identically,
all historical hashes and frozen implementation blobs must remain unchanged,
and the full regression matrix must pass with zero live/model/tool calls.

## Scope

- additive evaluator-side taxonomy, precedence, probe, diagnostic, corpus,
  harness, metrics, threshold, artifact, and replay-lock contracts;
- offline evaluation against the five existing manifest-owned observations;
- exact invariant-vector construction gates and ground-truth firewall tests;
- one authoritative aggregate only after the pre-result semantic freeze.

## Non-goals

No canonical environment or CED semantic change, context relaxation,
observation re-recording, provider dispatch, Phase 8.5 implementation, shadow
collection, depth/search expansion, Experience Store, learning, or RL.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

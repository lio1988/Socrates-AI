# Branch: feature/socrates-zero-canonical-successor-parity-v2

## Purpose

Run one new, pre-registered Phase 8 v2 evaluation experiment over the unchanged
CED-owned canonical successor environment.  The experiment freezes First
Canonical Guard Wins semantics, dependency-aware probe vectors, five existing
supported observations, eleven orthogonal probes, and seven precedence probes
before its first authoritative aggregate. The experiment is now complete.
The only supported family is `ASK_SOCRATIC_QUESTION` at
`OPENING / SOCRATES / SOCRATIC_QUESTION / round=0 / slot=0 / attempt=0`.

## Result

The first and only authoritative aggregate is `SUPPORTED`: all `5 + 11 + 7 =
23` frozen cases met their exact thresholds. The only independent reverse-order
replay has equal semantics, artifact ID, canonical bytes, and SHA-256.

- [Authoritative artifact](artifacts/socrateszero_canonical_successor_parity_v2.json):
  `cedparityartifactv2_f3a9c85ef31dd5afc09c1353ff8fb67461ebce42ae5390a3dff1efb0f2e109e7`
- [Replay lock](artifacts/socrateszero_canonical_successor_parity_replay_lock_v2.json):
  `cedparityreplaylockv2_e524b9e57fb070f67adc1098aeffe469d65b9f42bc0a9a77ddc9f3553e5f5280`

Phase 8.5 readiness is earned only for the **Phase 8.5 — Real Shadow Safety &
Experimental Design Gate**. No Phase 8.5 implementation or production authority
is implied.

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
- one authoritative aggregate after the pre-result semantic freeze and one
  reverse-order replay after its `SUPPORTED` result.

## Non-goals

No canonical environment or CED semantic change, context relaxation,
observation re-recording, provider dispatch, Phase 8.5 implementation, shadow
collection, depth/search expansion, Experience Store, learning, or RL.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

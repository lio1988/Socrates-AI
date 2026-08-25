# Canonical Successor Parity v2 artifacts — COMPLETE

Exactly one authoritative `23`-case aggregate ran after the semantic freeze.
The only supported family remains `ASK_SOCRATIC_QUESTION` at
`OPENING / SOCRATES / SOCRATIC_QUESTION / round=0 / slot=0 / attempt=0`. Its
first artifact is preserved with mechanically derived status `SUPPORTED`:

- file: [socrateszero_canonical_successor_parity_v2.json](socrateszero_canonical_successor_parity_v2.json)
- artifact ID: `cedparityartifactv2_f3a9c85ef31dd5afc09c1353ff8fb67461ebce42ae5390a3dff1efb0f2e109e7`
- SHA-256: `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc`
- Git blob: `130a7915c975979b8405b4f084d8b2f8716e7f59`
- preservation commit: `f0f8a5dad5e9632757f236ad619ccf5107b8af50`

Because the first artifact was `SUPPORTED`, exactly one independent
reverse-order replay ran. Its write-once lock is preserved:

- file: [socrateszero_canonical_successor_parity_replay_lock_v2.json](socrateszero_canonical_successor_parity_replay_lock_v2.json)
- replay-lock ID: `cedparityreplaylockv2_e524b9e57fb070f67adc1098aeffe469d65b9f42bc0a9a77ddc9f3553e5f5280`
- SHA-256: `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224`
- Git blob: `5ef7a30dcf3ebe983acc20d032d96fb10afd9c8c`
- preservation commit: `afeb21e2253c701b9e7cc2bb33b2d76b11a9aac9`

The authoritative metrics are `5/5` supported cases (`1/1` accepted and `4/4`
canonical rejections), `11/11` orthogonal primary classifications, and `7/7`
precedence primary classifications. Every mismatch, failure, security,
isolation, lock, negative/aggregate dispatch, live, model, and tool counter is
zero. Historical offline fixture dispatches remain exactly `5`.

The replay independently reverses each `5 + 11 + 7` order group. Semantic
equality, artifact-ID equality, and canonical byte identity are all `true`; both
artifact SHA-256 values are
`8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc`.

Publication is write-once:

- a missing destination is created exclusively;
- an existing byte-identical destination is accepted idempotently;
- an existing destination with different bytes is refused;
- an artifact is never rewritten, tuned, or replaced; and
- a `FALSIFIED` first artifact would permanently block replay and replay-lock
  publication.

The lock was constructed from two actual validated artifacts, not caller-
supplied equality flags. It freezes the exact authoritative and reverse
`5 + 11 + 7` memberships/orders. The post-result integrity test reads only raw
JSON and Git bytes; it does not import or invoke the evaluator, artifact builder,
provider, model, tool, or live path.

See
[`../../../SOCRATES_ZERO_CANONICAL_SUCCESSOR_PARITY_V2.md`](../../../SOCRATES_ZERO_CANONICAL_SUCCESSOR_PARITY_V2.md)
for the governing pre-registration and completed result record.

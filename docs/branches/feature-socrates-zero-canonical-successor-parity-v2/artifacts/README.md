# Canonical Successor Parity v2 artifacts — PRE-RESULT

This directory currently contains **no result artifact and no replay lock**.

```text
authoritative aggregate = PENDING
authoritative result = PENDING
artifact ID / SHA-256 = PENDING
reverse-order replay = PENDING and not authorized
replay-lock ID / SHA-256 = PENDING
```

The reserved publication names are:

- `socrateszero_canonical_successor_parity_v2.json` — the first authoritative
  `ced-canonical-successor-parity-artifact/v2`;
- `socrateszero_canonical_successor_parity_replay_lock_v2.json` — the
  `ced-canonical-successor-parity-replay-lock/v2`, permitted only after a
  `SUPPORTED` first artifact and a byte-identical independent reverse replay.

Publication is allowed only after the complete pre-result semantic freeze is
reviewed and committed. Exactly one authoritative 23-case aggregate may run.
Its first artifact must be preserved whether its status is `SUPPORTED` or
`FALSIFIED`.

Publication is write-once:

- a missing destination is created exclusively;
- an existing byte-identical destination is accepted idempotently;
- an existing destination with different bytes is refused;
- an artifact is never rewritten, tuned, or replaced; and
- a `FALSIFIED` first artifact permanently blocks replay and replay-lock
  publication.

If and only if the first artifact is `SUPPORTED`, one independent reverse-order
aggregate may run. The lock is constructed from two actual validated artifacts,
not caller-supplied equality flags. It freezes the exact authoritative and
reverse `5 + 11 + 7` memberships/orders and requires semantic equality,
artifact-ID equality, canonical byte identity, and equal SHA-256.

See
[`../../../SOCRATES_ZERO_CANONICAL_SUCCESSOR_PARITY_V2.md`](../../../SOCRATES_ZERO_CANONICAL_SUCCESSOR_PARITY_V2.md)
for the governing PRE-RESULT design.

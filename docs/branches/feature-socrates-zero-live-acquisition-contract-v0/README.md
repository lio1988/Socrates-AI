# Branch: feature/socrates-zero-live-acquisition-contract-v0

## Purpose

Implement the additive External Observation Acquisition Contract v0 as a
provider-agnostic, canned-only, zero-network safety foundation.

## Current status

**COMPLETE — SUPPORTED.** The pre-result design was frozen at
`e1779a7738c5cddc1e5b6d6024b84583ea72628d`. Exactly one authoritative
canned aggregate produced the preserved supported artifact, and exactly one
reverse-order replay recomputed the byte-identical artifact and published its
distinct execution evidence plus replay lock. All post-result regression gates
pass; live/network/provider/model/tool and canonical-application calls remain
zero. No production authority is granted.

## Success criterion

The branch succeeds only if immutable acquisition contracts, identities,
receipts, guard ordering, canned transport, resource/privacy/isolation controls,
frozen cases, one authoritative artifact and a procedurally distinct
reverse-order replay all satisfy their pre-result thresholds with:

`live/network/provider/model/tool calls = 0/0/0/0/0`,

canonical application calls and source/sibling/production mutations all zero,
all frozen historical hashes unchanged, and every required regression passing.

## Scope

- additive immutable acquisition contracts and deterministic IDs;
- exact provider-visible byte rendering and sibling equality;
- one in-memory canned transport with deterministic failure injection;
- fail-closed pre/post acquisition guards;
- complete new-execution accounting and typed historical usage;
- immutable isolation and retention receipts;
- frozen positive, orthogonal and precedence cases;
- authoritative artifact, persisted reverse-execution evidence and replay lock.

## Non-goals

No external network, credential access, provider SDK, model or tool execution;
no CED/canonical observation application; no provider-registry integration; no
search, Value ranking, action extension, Experience Store, learning, RL, depth
two or production authority.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

Canonical design report:
[SOCRATES_ZERO_EXTERNAL_OBSERVATION_ACQUISITION_CONTRACT_V0.md](../../SOCRATES_ZERO_EXTERNAL_OBSERVATION_ACQUISITION_CONTRACT_V0.md)

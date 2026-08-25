# Branch: feature/socrates-zero-live-acquisition-contract-v0

## Purpose

Implement the additive External Observation Acquisition Contract v0 as a
provider-agnostic, canned-only, zero-network safety foundation.

## Current status

**PRE-RESULT FROZEN.** Contracts, cases, expected outcomes, exact construction
and receipt identity locks, thresholds and artifact/replay schemas are complete.
The first authoritative aggregate has not run.

## Success criterion

The branch succeeds only if immutable acquisition contracts, identities,
receipts, guard ordering, canned transport, resource/privacy/isolation controls,
frozen cases, one authoritative artifact and an independent replay all satisfy
their pre-result thresholds with:

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

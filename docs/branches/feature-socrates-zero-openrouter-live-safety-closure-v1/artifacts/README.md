# Artifacts — OpenRouter live-safety closure v1

## Pre-authoritative state

The evaluator defines these exact write-once paths:

- `socrateszero_openrouter_live_safety_closure_v1.json`;
- `socrateszero_openrouter_live_safety_closure_replay_execution_v1.json`;
- `socrateszero_openrouter_live_safety_closure_replay_lock_v1.json`.

All three are currently absent. The next authorized sequence is an explicit
semantic freeze commit followed by exactly one designated persisted aggregate
and deterministic replay. No authoritative ID, SHA-256 or byte length exists
before that execution.

Artifacts are compact, content-addressed and credential-free. They contain
identities, digests, lengths, statuses and derived metrics—not raw secrets,
provider responses, canonical request bodies or duplicated prompts. The replay
must establish semantic equality, artifact-ID equality and byte identity.

## Development checks are not artifacts

Before freeze, one full case pass and three in-memory builder checks ran without
persisting evidence. The case pass was 73/73 expected with 0 unexpected. The
builder checks observed `SUPPORTED`, all thresholds true, 73 results,
predecessor integrity 8/8 and three-way determinism. A development render was
51,938 bytes with ID
`szorlivesafetyartifactv1_8e0d9fb1f77d065a9ccf2222a18df0d519f2e9cc65974c95854a18058b9ac003`.

Later semantic hardening changed the evaluator inputs and identities. That ID
and length are stale historical observations and MUST NOT be written, cited as
freeze evidence or substituted for the designated authoritative result.

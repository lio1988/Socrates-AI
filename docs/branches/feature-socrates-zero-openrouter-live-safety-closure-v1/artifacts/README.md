# Artifacts — OpenRouter live-safety closure v1

## Authoritative state

At freeze HEAD `dca2f2d97b1eeba9626ec9490edf722b64681ef5`, the
single designated persisted aggregate and deterministic replay created these
exact write-once files:

- `socrateszero_openrouter_live_safety_closure_v1.json`;
- `socrateszero_openrouter_live_safety_closure_replay_execution_v1.json`;
- `socrateszero_openrouter_live_safety_closure_replay_lock_v1.json`.

| evidence | content identity | file SHA-256 | bytes |
| --- | --- | --- | ---: |
| artifact | `szorlivesafetyartifactv1_237286af63bc509db7fe2cbd4e40a78150d36213ec162a2a745494eeeeed70b3` | `9bdc7f58ca1e29a9ed082a863a6bc4487f9687c564207887b226953cc6f95a01` | 52,053 |
| replay execution | `szorlivesafetyreplayexecutionv1_0292ea7f00e670fdf9c4d6254b4ebeca4d0b1e97744e5a0a7b294254b7f151da` | `3a5cb6cacc85e3c8a842bade1e0ac279929682c4db547cdd16dc9eed22454d2e` | 740 |
| replay lock | `szorlivesafetyreplaylockv1_116f9049f8495ad63276973a4d0e09815ead6435bddb45ccaf319a2d8e964dc6` | `6c66d96527e271efef5dd0ec8de139ebb8f96f44dce79490a783ae69f9b3f675` | 655 |

The artifact reports `SUPPORTED`, all thresholds passing, 73 total cases, 20
positive accepted, 53 adversarial rejected, 0 unexpected results, every
zero-hazard metric 0, external activity 0 and S6 predecessor integrity 8/8.
Replay semantic equality, artifact-ID equality and byte identity are all true.

Artifacts are compact, content-addressed and credential-free. They contain
identities, digests, lengths, statuses and derived metrics—not raw secrets,
provider responses, canonical request bodies or duplicated prompts. The replay
established all three required equalities. These files must not be overwritten
or regenerated.

## Development checks are not artifacts

Before freeze, one full case pass and three in-memory builder checks ran without
persisting evidence. The case pass was 73/73 expected with 0 unexpected. The
builder checks observed `SUPPORTED`, all thresholds true, 73 results,
predecessor integrity 8/8 and three-way determinism. A development render was
51,938 bytes with ID
`szorlivesafetyartifactv1_8e0d9fb1f77d065a9ccf2222a18df0d519f2e9cc65974c95854a18058b9ac003`.

Later semantic hardening changed the evaluator inputs and identities. That ID
and length are stale historical observations and MUST NOT be written, cited as
freeze evidence or substituted for the designated authoritative result above.

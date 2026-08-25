# External Observation Acquisition Contract v0 artifacts

This directory is the write-once publication boundary for the canned-only
acquisition experiment.

The authoritative artifact may be created exactly once, only after the
pre-result freeze commit has been reported and only while the reusable
network, credential, provider, model, tool, and canonical-application
tripwires are active and clean. If that first artifact is `FALSIFIED`, it is
preserved unchanged and no success replay is run.

If the authoritative artifact is `SUPPORTED`, exactly one reverse-order
execution must persist both its canonical execution-evidence file and the lock
that binds that file's SHA-256. Committed post-result tests read all three files;
they never rebuild, rewrite, or tune them.

Frozen filenames:

- `socrateszero_external_observation_acquisition_v0.json`;
- `socrateszero_external_observation_acquisition_replay_execution_v0.json`;
- `socrateszero_external_observation_acquisition_replay_lock_v0.json`.

The replay execution evidence intentionally does not embed a second copy of the
raw-bearing artifact. No file in this directory grants production authority or
canonical observation admission. Raw responses are non-sensitive canned
fixtures retained as canonical Base64 with exact byte length and SHA-256;
provider-visible prompts are represented by digest, length, and safe reference
only. Unallowlisted bytes and metadata are excluded, and invalid historical
lock strings are represented only by typed presence/format evidence.

## Published evidence

- Pre-result freeze:
  `e1779a7738c5cddc1e5b6d6024b84583ea72628d`.
- Authoritative artifact commit:
  `70e07363aeedc205e5f13695918f735b8c5a15ea`.
- Authoritative result: `SUPPORTED`.
- Artifact ID:
  `acqartifactv0_fb7fc0b8f19607cf74cb549992a62ea94638228e8c5c9fedab65f445272c2d11`.
- Artifact SHA-256:
  `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255`.
- Reverse replay evidence commit:
  `15e3b819b1625d71786419a0efdf8082ca29e462`.
- Replay execution ID:
  `acqreplayexecutionv0_08125a577c16aa3324f395c46461651e50ce5f1df38627edf3401dbaf1b96f8f`.
- Replay execution SHA-256:
  `7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b`.
- Replay lock ID:
  `acqreplaylockv0_af196a855a1cefd1220a0a61b159ac75d1b8928b112704c48d7e30b686080e0a`.
- Replay lock SHA-256:
  `335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c`.
- Semantic equality, artifact-ID equality and byte identity: all `true`.

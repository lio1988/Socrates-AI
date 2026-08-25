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

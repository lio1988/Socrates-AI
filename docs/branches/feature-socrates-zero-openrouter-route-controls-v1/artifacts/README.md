# Phase 8.5D write-once artifacts

This directory is reserved for the canonical OpenRouter route-controls v1
artifact and, only after complete support, the independent reverse-order replay
execution and replay lock.

The pre-result freeze contains no aggregate result. Artifact publication uses
exclusive creation; the first artifact is never regenerated or rewritten.

The frozen sole-authority manifest does not establish the complete official
response wire mapping required by the full hypothesis: the assessment is one
violation against a maximum of zero. The first artifact is therefore expected
to be `FALSIFIED`. In that state the replay execution and replay lock must remain
absent.

Expected filenames:

- `socrateszero_openrouter_route_controls_v1.json`
- `socrateszero_openrouter_route_controls_v1_replay_execution.json`
- `socrateszero_openrouter_route_controls_v1_replay_lock.json`

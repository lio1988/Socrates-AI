# Phase 8.5D write-once artifacts

This directory is reserved for the canonical OpenRouter route-controls v1
artifact and, only after complete support, the independent reverse-order replay
execution and replay lock.

The sole aggregate published the write-once canonical artifact using exclusive
creation. It must never be regenerated or rewritten.

The frozen sole-authority manifest does not establish the complete official
response wire mapping required by the full hypothesis: the assessment is one
violation against a maximum of zero. The first artifact is therefore
`FALSIFIED`:

- ID:
  `szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd`;
- SHA-256:
  `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`;
- length: 366,623 bytes;
- cases: 63/63 matched frozen expectations;
- replay: `NOT PERFORMED / N/A`.

The replay execution and replay lock are confirmed absent and prohibited.

Artifact file present:

- `socrateszero_openrouter_route_controls_v1.json`

Deliberately absent replay files:

- `socrateszero_openrouter_route_controls_v1_replay_execution.json`
- `socrateszero_openrouter_route_controls_v1_replay_lock.json`

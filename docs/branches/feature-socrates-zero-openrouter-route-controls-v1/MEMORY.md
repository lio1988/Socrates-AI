# Phase 8.5D memory

## Non-negotiable lineage

- The OpenRouter adapter-controls v0 artifact remains `FALSIFIED` with SHA-256
  `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083`.
- The Phase 8.5C manifest is immutable and has semantic SHA-256
  `6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`.
- Route controls v1 are a new semantic lineage and do not repair or rerun v0.
- P17, P18, P19 and full response-side exact-endpoint attestation remain
  `NOT_ESTABLISHED`.

## Frozen experiment intent

- Provider: OpenRouter, request intent only.
- Model: exact `openai/gpt-4.1-mini`; `models` absent.
- Endpoint selector: exact singleton `azure/swedencentral` in the hard allow
  list; order policy must be frozen before results.
- Provider fallback: false.
- Require parameters: true.
- `max_price`: `DEFERRED_NOT_RENDERED`.
- Stream: false; tools: disabled.
- Metadata header: exact frozen-manifest evidence only.
- Response cache: explicitly disabled using exact frozen-manifest evidence.
- Metadata required; attempt must equal one.
- Broad provider evidence must never become exact endpoint attestation.

## Scientific chronology

The complete semantic design, cases, guard order and thresholds must be committed
before the first authoritative aggregate. The authoritative artifact is
write-once. Reverse replay is permitted only after a complete pass.

## Protected local files

Never stage or modify:

- `scripts/live_dialogue.py.bak`;
- the malformed root filename beginning `ocratic_followup_mandate`.


# Phase 8.5D memory

## Non-negotiable lineage

- The OpenRouter adapter-controls v0 artifact remains `FALSIFIED` with SHA-256
  `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083`.
- The Phase 8.5C manifest is immutable and has semantic SHA-256
  `6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`.
- Route controls v1 are a new semantic lineage and do not repair or rerun v0.
- P17, P18, P19 and full response-side exact-endpoint attestation remain
  `NOT_ESTABLISHED`.
- `OR-S04-ROUTER-METADATA` and `OR-S08-OPENAPI` retain no source-content byte
  counts. `ORSPEC-F04` retains response concepts but not the complete nested
  official wire schema;
  `ORSPEC-F05` retains the exact top-level `openrouter_metadata` name and cache
  relationship only. The frozen manifest therefore cannot establish an exact
  official-wire-to-normalized mapping.
- The mandate makes that manifest the sole specification authority. The gap
  must not be repaired from the richer Phase 8.5C narrative report, memory, or
  a fresh network lookup.

## Frozen experiment intent

- Provider: OpenRouter, request intent only.
- Model: exact `openai/gpt-4.1-mini`; `models` absent.
- Endpoint selector: exact singleton `azure/swedencentral` in both `only` and
  `order`; `only` is the hard request restriction and `order` is preference
  semantics only.
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

The pre-result threshold freezes
`official_response_wire_mapping_violations = 1` against a maximum of zero.
Consequently, the full hypothesis is expected to be `FALSIFIED` even if all
local normalized canned-parser cases pass. A falsified artifact must have no
replay execution and no replay lock.

The typed manifest-only audit receipt is
`szorwiremappingassessmentv1_4837280cd07f68b98c73a84c48c59b44fc907b177f46fddfd6ece843f5a20b48`.
It binds the exact source/fact record digests and derives the violation from the
retained manifest observations.

The frozen case inventory is 63 total: 3 positive requests, 3 positive
responses, 29 orthogonal request probes, 20 orthogonal response probes, and 8
precedence probes. The mutation vector has 22 exact fields. Validation uses 32
guards with deterministic first-guard-wins precedence. Expected canned
dispatches are 26; all external and canonical-application counters must remain
zero.

## Protected local files

Never stage or modify:

- `scripts/live_dialogue.py.bak`;
- the malformed root filename beginning `ocratic_followup_mandate`.

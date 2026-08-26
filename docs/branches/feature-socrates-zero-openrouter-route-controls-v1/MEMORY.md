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

The complete semantic design, cases, guard order and thresholds were committed
in pre-result freeze `848166dd3eacfa5d31175745b160b98751b3a904` before the
first authoritative aggregate. The aggregate ran exactly once and its
write-once artifact was committed alone in `d225113`. Reverse replay remained
conditional on a complete pass.

The pre-result threshold freezes
`official_response_wire_mapping_violations = 1` against a maximum of zero.
The artifact observed that exact threshold failure, so the full hypothesis is
`FALSIFIED` even though all local normalized canned-parser cases passed. It has
no replay execution and no replay lock.

The typed manifest-only audit receipt is
`szorwiremappingassessmentv1_4837280cd07f68b98c73a84c48c59b44fc907b177f46fddfd6ece843f5a20b48`.
It binds the exact source/fact record digests and derives the violation from the
retained manifest observations.

The frozen case inventory is 63 total: 3 positive requests, 3 positive
responses, 29 orthogonal request probes, 20 orthogonal response probes, and 8
precedence probes. The mutation vector has 22 exact fields. Validation uses 32
guards with deterministic first-guard-wins precedence. Expected canned
dispatches were 26; all external and canonical-application counters remained
zero.

The artifact is
`szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd`,
SHA-256
`61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`,
366,623 bytes. All 63 results matched their frozen case expectations and all ten
historical locks remained exact.

Final regressions exposed one additional preserved incompatibility: the sealed
v0 static data-only test scans every runtime module and rejects the new
evaluator's literal historical inventory path `openrouter_acquisition_cases.py`.
No post-result code or test change was made to tune that result.

## Protected local files

Never stage or modify:

- `scripts/live_dialogue.py.bak`;
- the malformed root filename beginning `ocratic_followup_mandate`.

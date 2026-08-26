# Branch: feature/socrates-zero-openrouter-route-controls-v1

## Purpose

Implement the approved Phase 8.5D additive, network-inert OpenRouter route
controls v1 experiment against the frozen Phase 8.5C specification manifest.

## Decision criterion

Freeze before results and then run exactly one authoritative canned aggregate
to test whether the sole-authority Phase 8.5C manifest supports both the exact
request controls and the official response-envelope mapping required by the
Phase 8.5D hypothesis. A repository-owned normalized parser may establish only
a narrower offline subresult. Reverse replay is permitted only after complete
support.

## Scope

- new immutable route/cache/metadata/request/receipt contracts;
- canonical semantic body and non-secret header rendering;
- in-memory canned transport and router-metadata parser;
- typed partial attestation with exact-endpoint firewall;
- frozen cases, mutation vectors, guard order, evaluator, artifact and replay;
- adversarial/offline tests and durable documentation.

## Non-goals

No production-adapter integration, credentials, environment inspection, DNS,
sockets, HTTP, documentation fetches, provider/model/tool calls, CED
application, P17/P18/P19 implementation, `max_price`, pricing, tokenizer, cost
calculation, live endpoint proof, Search/Value/Policy changes or Socratic
vocabulary extension.

## Incoming authority

- Parent HEAD: `cc9290fd238829b53c8da8b403de31e61e1db2a0`.
- Specification manifest:
  `szorspecmanifestv0_6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`.
- Selected request intent: `openai/gpt-4.1-mini` through
  `azure/swedencentral`.
- Decision: `OPENROUTER ROUTE-CONTROL MILESTONE ONLY EARNED`.

## Frozen design and authoritative result

- Canonical body: 447 bytes, SHA-256
  `35a119b1e35f9f8ce05baf57009d787358bf086aaae4055ef56fcfedade514a1`.
- Canonical semantic headers: 98 bytes, SHA-256
  `1c688da6c6494631d6922fcb89a56b126e0900327dd865c2483d84f3c9f58149`.
- Cases: 63 = 6 positive + 49 orthogonal + 8 precedence.
- Validation: 32 deterministic guards, first route-control guard wins.
- Frozen expected canned dispatches: 26; observed: 26.
- Official response wire mapping from the sole-authority manifest:
  `NOT_ESTABLISHED_FROM_FROZEN_MANIFEST`.
- Frozen wire-mapping violations: 1; maximum allowed: 0.
- Typed manifest audit:
  `szorwiremappingassessmentv1_4837280cd07f68b98c73a84c48c59b44fc907b177f46fddfd6ece843f5a20b48`.
- Observed hypothesis result: `FALSIFIED`; the local normalized canned contract
  passed all 63 cases, but the frozen official-wire assessment was 1 against a
  maximum of 0.
- Pre-result freeze commit: `848166dd3eacfa5d31175745b160b98751b3a904`.
- Artifact-only commit: `d225113`.
- Artifact ID:
  `szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd`.
- Artifact SHA-256:
  `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`.
- Artifact length: 366,623 bytes.
- Replay: `NOT PERFORMED / N/A`; replay execution and lock are absent and
  prohibited for this falsified artifact.
- Regression disposition: all new v1 and sealed Phase 5/7/8/Acquisition gates
  passed. One legacy v0 static inventory assertion fails on the new evaluator's
  literal historical path; it was preserved without post-result tuning.
- Full design report:
  [SOCRATES_ZERO_OPENROUTER_ROUTE_CONTROLS_V1.md](../../SOCRATES_ZERO_OPENROUTER_ROUTE_CONTROLS_V1.md).

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) · [PRESENT.md](PRESENT.md)

# Branch: feature/socrates-zero-openrouter-route-controls-v1

## Purpose

Implement the approved Phase 8.5D additive, network-inert OpenRouter route
controls v1 experiment against the frozen Phase 8.5C specification manifest.

## Success criterion

Freeze before results and then prove, through one authoritative canned
aggregate and an independent reverse replay, that canonical request/header
intent and router-metadata parsing deterministically enforce the declared exact
model, exact endpoint selector, no-fallback, metadata-required and
response-cache-disabled policy without overclaiming live or exact-endpoint
response evidence.

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

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) · [PRESENT.md](PRESENT.md)


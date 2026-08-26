# Branch: feature/socrates-zero-provider-adapter-controls-v0

## Purpose

Implement the additive, experimental, network-inert OpenRouter acquisition
adapter controls approved by the Phase 8.5B authorization gate.

## Success criterion

Prove offline that one acquisition-only adapter renders exact semantic-only
request bytes, freezes all adapter-owned controls, invokes one canned transport
at most once, and emits immutable raw/identity/usage/cost receipts. Freeze the
evaluation before aggregate results, publish a deterministic artifact, and lock
an independent reverse replay.

## Scope

- immutable OpenRouter acquisition contracts and capability snapshots;
- canonical UTF-8 JSON application-body rendering;
- route, fallback, retry, streaming, tool, token, pricing, cost, endpoint and
  canned-timeout policies;
- one-shot canned adapter and immutable response evidence;
- frozen cases, first-guard evaluation, authoritative artifact and replay lock;
- full regression and historical-hash verification.

## Non-goals

No credentials, environment-secret access, DNS, sockets, HTTP, SDK/provider
dispatch, model/tool execution, live pricing lookup, credential broker, real
endpoint enforcement, production wiring, CED application, search, Value,
learning, RL or Socratic action extension.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) ·
[PRESENT.md](PRESENT.md)

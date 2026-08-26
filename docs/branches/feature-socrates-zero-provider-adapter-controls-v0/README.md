# Branch: feature/socrates-zero-provider-adapter-controls-v0

## Purpose

Implement the additive, experimental, network-inert OpenRouter acquisition
adapter controls approved for offline hardening by the Phase 8.5B authorization
gate. This branch grants no live-call authority.

## Frozen result protocol

The branch freezes one falsifiable success threshold before results. A complete
pass requires exact semantic-only request bytes, all mandatory route, fallback,
token and pricing/cost controls, 34 expected canned invocations, all 59 case
results exact, immutable response evidence, zero forbidden activity and zero
scoped mutations.

Repository evidence leaves mandatory guards `P08`, `P09`, `P17`, `P18` and
`P19` unresolved. This is pre-registered evidence, not an aggregate result. The
first authoritative canned aggregate remains unexecuted until the freeze commit.

If the result is `FALSIFIED`, preserve the artifact and do not perform an
independent reverse replay or create a replay lock. Reverse replay and a replay
lock are permitted only after a complete pass.

## Frozen implementation

- immutable OpenRouter acquisition contracts and capability snapshot;
- canonical UTF-8 JSON application-body rendering;
- route, fallback, retry, streaming, tool, token, pricing, cost, endpoint and canned-timeout policies;
- sealed one-shot canned adapter and immutable raw/identity/usage receipts;
- 7 positive cases, 44 orthogonal probes and 8 precedence probes;
- first-guard-wins evaluation and write-once artifact publisher;
- explicit 72-path before/after SHA-256 mutation evidence;
- all nine historical artifact hashes and the Phase 8 v2 core lock.

## Non-goals

No credentials, environment-secret access, DNS, sockets, HTTP, SDK/provider
dispatch, model/tool execution, live pricing lookup, credential broker, real
endpoint enforcement, production wiring, CED application, search, Value,
learning, RL or Socratic action extension.

Branch context: [MEMORY.md](MEMORY.md) · [PLAN.md](PLAN.md) · [PRESENT.md](PRESENT.md)

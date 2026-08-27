# Branch: feature/socrates-zero-openrouter-one-live-shadow-v1

Phase 8.5D-S7B — JIT preflight and, if and only if every gate passes, exactly
ONE live OpenRouter shadow call.

## Purpose

S7A left three things `JIT_PENDING`: the P17 input bound, the operator price
policy, and the physical claim store. S7B supplies all three from live authority
— a first-party model-limit GET, explicit operator grants, and a durable local
claim store — then dispatches at most one inference POST and maps its raw
response through frozen S5 and S6.

## Success criterion

Exactly one cost-bounded, explicitly authorized shadow request dispatched once;
its raw response captured and deterministically mapped through S5 and causally
integrated through S6 without authority leakage, retry, privacy violation or CED
mutation.

Success is **not** a claim that the integration is production-ready.

## Scope

Additive only: `openrouter_one_live_shadow_v1` (operator grants, one-shot HTTPS
transport, JIT client), `openrouter_one_live_shadow_runner_v1` (preflight
assembly and the single dispatch), focused tests, branch documentation, and the
live evidence and artifacts produced by the one call.

## Non-goals

No second inference request under any circumstance. No retry. No runtime or CED
authority. No modification of S7A, S6, S5, S3, Route Controls or Manifest
surfaces. No fix of the known predecessor timestamp race — that stays on its own
branch and is not merged or cherry-picked here. Not pushed.

## Budgets

| class | maximum |
| --- | --- |
| first-party model-metadata GET | 1 |
| live inference POST | 1 |
| local retries | 0 |

Enforced by a process-wide latch that claims the budget before a socket is
opened, and by a durable single-consumption claim store.

## Documents

- [MEMORY.md](MEMORY.md) — invariants, the trust model, and what must not change.
- [PLAN.md](PLAN.md) — ordered steps, gates, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state.
- [artifacts/README.md](artifacts/README.md), [evidence/README.md](evidence/README.md).

# Branch: feature/socrates-zero-openrouter-wire-mapping-v2-authorization-gate

Phase 8.5D-S4 — OpenRouter Wire-Mapping v2 Authorization Gate Rerun.

## Purpose

Decide one question, and change no behaviour while deciding it.

## Decision question

> Does the currently frozen repository contain sufficient official,
> content-addressed and provenance-clean evidence to justify implementing one
> bounded OpenRouter raw-response wire-mapping v2 candidate, without relying on
> repository conventions, guessed response shapes, live calls, undocumented
> semantics or historical expected labels?

## Result

| layer | status |
| --- | --- |
| Parser boundary specifiable | **YES** |
| Offline wire-mapping v2 implementation attempt | **AUTHORIZED / JUSTIFIED** |
| Runtime authority | **NOT AUTHORIZED** |
| Live OpenRouter execution | **NOT AUTHORIZED** |
| P17 / P18 / P19 | **NOT_ESTABLISHED** |

`WIRE-MAPPING v2 IMPLEMENTATION EARNED` is retained only as the legacy gate
shorthand, defined as: *one bounded offline implementation attempt is authorized;
no runtime or live authority is granted.*

This authorizes exactly one bounded, offline, raw-bytes-first implementation
attempt — Phase 8.5D-S5. It authorizes nothing else.

## Success criterion

A single binary answer, supported by a field-by-field audit in which every
authority is traced to a retained official source, fact, mapping or relationship
assessment, with zero inferred semantics; and read-only verification that the
sealed scientific record is untouched.

## Scope

Documentation only. No code, no artifact regeneration, no network.

## Non-goals

Raw response parser v2. Normalized-response mapper v2. Live acquisition adapter.
Provider pilot. OpenRouter call. Pricing lookup. Token estimator. Cost controls.
New Route Controls artifact. New authoritative aggregate. Any change to
parser/renderer semantics, Manifest v2r1, or Provenance Boundary v1.

## What remains blocked

P17, P18 and P19 remain NOT_ESTABLISHED. **Live pilot remains NOT EARNED.**
Parser authorization is not provider-pilot authorization.

## Documents

- [MEMORY.md](MEMORY.md) — stable branch context and invariants.
- [PLAN.md](PLAN.md) — execution plan, gates, stop conditions.
- [PRESENT.md](PRESENT.md) — exact current state.

Canonical result:
[docs/SOCRATES_ZERO_OPENROUTER_WIRE_MAPPING_V2_AUTHORIZATION_GATE.md](../../SOCRATES_ZERO_OPENROUTER_WIRE_MAPPING_V2_AUTHORIZATION_GATE.md).

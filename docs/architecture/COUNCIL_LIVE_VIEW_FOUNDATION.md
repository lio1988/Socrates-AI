# Council Live View Foundation — Slice 0 (+ inert ledger half of Slice 1)

Status: **implemented, runtime-inert, contract-audited**. Parent decision
record: [KARPATHY_LLM_COUNCIL_MAPPING.md](KARPATHY_LLM_COUNCIL_MAPPING.md)
(§9, §14, §18). Branch: `feature/council-live-view-foundation` (isolated
worktree off origin/main).

## What exists now

Package: `backend/dialogues/projection/` — pure contracts, zero execution.

| Module | Contract | Key guarantees |
|---|---|---|
| `taxonomy.py` | closed dotted event taxonomy (22 types) + typed stream contract | exact names (`session.created` … `run.completed`); `session.created` is session-scoped (`run_id=None`, stream `session:<id>`); all others run-scoped (`run:<id>`); sentinel run ids (`"none"`, `"null"`, …) rejected; `stream_id` is derived, never caller-asserted |
| `payloads.py` | one strict typed payload model per event type (22/22, import-time completeness guard) | `extra="forbid"` + `strict=True` + `frozen=True`; unknown field / wrong type / NaN / Infinity rejected; `PAYLOAD_SCHEMA = "<event>.payload"`, `PAYLOAD_VERSION` per model; `move.validated` requires split `raw_digest`/`validated_digest` (`^[0-9a-f]{64}$`) |
| `events.py` | `ced_epistemic_event_v1` envelope (frozen, strict) + semantic identity | fields: schema/schema_version/**payload_schema/payload_version**/event_id/idempotency_key/sequence/session_id/run_id/event_type/actor_id/subject_id/phase/round_index/emitted_at/causal_parent_id/receipt_ref/artifact_digest/payload; wrong event↔payload pairing and payload-version mismatch rejected; `semantic_digest` = canonical sorted-UTF-8 JSON **excluding event_id** (sequence/emitted_at structurally absent from drafts) |
| `ledger.py` | `EventLedger` — append-only, per-stream | **sequence starts at 1**, gap-free, assigned only at append; duplicate (same stream+key+content) → existing event, no sequence consumed; **conflict** (same stream+key, different content) → `CedEventConflictError`, no mutation, no sequence consumed; failed append leaves no gap; reads return fresh **tuples** of frozen events; cross-stream isolation; no global singleton, no callbacks, injected callable (clock) never runs under the lock; deterministic injected clock |
| `reveal.py` | §6.5 blind-evaluation reveal policy | aliases scoped per (session, phase, round, **evaluator**, purpose) — never global; per-evaluator deterministic SHA-256 permutation; backend-owned digest-sealed `AnonymousMapping`; reveal gated on explicit `close_evaluation()`; `NEVER` policy stays sealed; forged-mapping detection; **not a scheduler**: never selects voters/subjects — a self-subject input raises `SelfSubjectError` as a tripwire for an upstream eligibility bug (self-scoring prohibition remains the canonical protocol's responsibility) |
| `role_display.py` | §6.2 role-loop display | exclusively projects canonical `role_history`; **no role recalculation, no inferred primary role, no silent repair**; frozen rows; groupings computed backend-side — the frontend renders, never calculates |

Tests: `tests_dialogues/test_projection_events_ledger.py` +
`tests_dialogues/test_projection_reveal_role_display.py` — including the
explicit audit cases (session.created stream semantics; sequence-from-1;
failed-append-no-gap; duplicate-no-sequence; same-key/different-content
conflict; extra-field/wrong-type/pairing/version payload rejection; immutable
reads; cross-stream isolation; per-evaluator alias scope; tamper detection;
sealed-before-close; NEVER unrevealable; malformed role row refused; display
never recalculates; runtime-inertness guard) plus integration against a real
offline `CEDOrchestrator.run_session`.

## What deliberately does NOT exist yet

- **No emission**: `ced.py` is untouched; nothing writes to the ledger.
  (Slice 1 second half: flag-gated observer hook, failure-isolated, guarded by
  a byte-identical `FinalResponse` golden test.)
- **No transport**: no FastAPI, no SSE (Slice 2, new `backend/live/`, never
  extending the family-B `backend/app.py`).
- **No frontend** (Slice 3), **no provider receipt projection** (Slice 4),
  **no conversation projection** (Slice 5), **no OpenRouterAdapter** (separate
  gated effort, §10 of the mapping).

## Authority rules restated (locked)

The projection layer records facts CED already computed. It may never assign
roles, fabricate events, select section winners, resolve objections, or ratify
answers. Ordering is by `sequence`, never by timestamp. Blind-evaluation
subjects are anonymous pre-reveal; the mapping lives backend-side only; the
reveal layer never schedules.

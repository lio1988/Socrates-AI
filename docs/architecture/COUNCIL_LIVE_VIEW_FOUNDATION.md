# Council Live View Foundation — Slice 0 (+ inert ledger half of Slice 1)

Status: **implemented, runtime-inert, contract-audited, hardened through
adversarial review rounds 1–3**. Parent decision record:
[KARPATHY_LLM_COUNCIL_MAPPING.md](KARPATHY_LLM_COUNCIL_MAPPING.md)
(§9, §14, §18). Branch: `feature/council-live-view-foundation` (isolated
worktree off origin/main).

> **Precedence note.** Where the parent mapping's original §9.2 event sketch
> (identity fields, attempt/receipt/payload details) differs from the code in
> this package, the executable `contract_matrix.CONTRACT_MATRIX` and the typed
> payload models are authoritative. §9.2 is the historical proposal; this
> package is the ratified v1 contract. See the mapping's *Implementation
> Addendum*.

## Package modules

- `taxonomy.py` — closed 22-type dotted taxonomy, typed stream contract,
  closed projection vocabularies (`SectionLiteral`, `RoleLiteral`, …).
- `contract_matrix.py` — the executable `CONTRACT_MATRIX` (immutable view).
- `payloads.py` — 22 strict/frozen typed payload models (immutable registry).
- `events.py` — `ced_epistemic_event_v1` envelope, `ReceiptRef`,
  executable idempotency derivation, semantic digest.
- `ledger.py` — append-only per-stream `EventLedger`.
- `reveal.py` — run-scoped `AnonymousMapping` + `RevealPolicyStore`.
- `role_display.py` — strict `role_history` projection.

Tests (focused): `tests_dialogues/test_projection_events_ledger.py`,
`test_projection_reveal_role_display.py`,
`test_projection_contract_matrix.py` (183 tests as of round 3).

## Hardening round 1 (adversarial review of f8124d0 — all 10 findings closed)

1. **NEVER-policy downgrade (critical)**: the sealed mapping digest now covers
   schema/version, full context, **reveal policy**, assignments AND order;
   `register()` is write-once — identical re-registration is idempotent, ANY
   difference (policy-only included) is a conflict; never overwrite.
2. **Deep immutability**: ledger and reveal store keep their own deep copies
   and return fresh deep copies — mutating a returned event's payload, an
   original draft, a registered mapping or a returned view can never change
   recorded history.
3. **Canonical verification**: `verify_mapping()` re-derives seed, aliases and
   canonical order from context + real subjects and requires exact equality
   BEFORE digest comparison — recomputing digests over a non-canonical
   mapping cannot make it verify (SHA-256 is integrity, not a MAC).
   Structural uniqueness (duplicate aliases/reals, self-subject) rejects at
   model construction.
4. **Failure atomicity**: dedupe check happens BEFORE the clock (an exact
   duplicate returns even with a broken clock); clock or sealed-validation
   failure leaves no stream/index/sequence behind; concurrency-safe
   check → clock → re-check-under-lock → construct → append.
5. **Wire round-trip**: `"schema"` is a validation alias too; `event_type` is
   canonically parsed to the enum; `model_validate(wire_dict)` and
   `model_validate_json` reproduce equal events; same alias policy on reveal
   and role-display schemas.
6. **Parent-mapping payload parity**: explicit `CONTRACT_MATRIX` (22/22 —
   required envelope/payload, optional payload, idempotency identity,
   receipt requirement, projection rule), enforced at runtime
   (envelope/receipt) and by tests (payload fields). `draft.created` carries
   `sections_present`; `peer_score.completed` carries score/kind/section/
   draft/penalty-flags; `assembly.completed` carries section refs;
   `blocking_objection.raised` carries `provider_id`; `runner_up.replaced`
   carries `via`; `move.validated` requires envelope phase/round.
7. **Role display without silent repair**: raw rows are validated verbatim by
   a strict model (float/bool round_index, None/non-canonical role, unknown
   extra field → reject; the old `str()`/`int()` coercions are gone).
8. **No delimiter collisions**: idempotency keys and reveal seeds derive from
   canonical JSON arrays (type-preserving), never `"|"` joins.
9. **Semantic coherence**: quorum `valid ≤ expected`; a COMPLETED peer score
   must carry a real score; unresolved winners carry no selection data (and
   resolved ones must); assembly refs must agree with `unresolved_sections`;
   sections/roles/phases/verdicts/severity/statuses are closed Literals with
   tested parity against the canonical `models.py` enums.
10. **UTC enforcement**: `emitted_at` must be timezone-aware UTC — naive or
    non-UTC clocks are rejected, never silently normalized.

## Hardening round 2 (adversarial review of de52ad5 — all 7 findings closed)

1. **Executable idempotency identity**: `derive_event_idempotency_key()` is
   THE contract — identity fields per the matrix, extracted from envelope or
   payload as labeled canonical-JSON pairs. `build_draft()` derives the key
   itself (no public arbitrary-key path) and every draft/sealed event is
   verified against the derivation — a caller-supplied wrong key rejects.
   Identity rows fixed: provider events carry `attempt_index` (a retry is a
   NEW canonical attempt); ratification votes are per
   (ratification_id, voter_id); blocking objections per
   (ratification_id, provider_id); Phase-19 repair re-votes mint NEW
   ratification_ids — new canonical events, never conflicts. 22/22 identity
   tests (same→same key, identity change→new key, same identity + different
   content→conflict, wrong key→reject).
2. **Global event_id uniqueness**: ledger keeps a global event-id index —
   a reused event_id claiming a different fact is a conflict (same- and
   cross-stream); idempotent replay returns the ORIGINAL event/id. Bounded
   safe id format (`evt_[0-9A-Za-z_-]{3,64}`). **v1 causality policy LOCKED**:
   `causal_parent_id` must reference an already-recorded event (globally;
   cross-stream parents explicitly allowed, e.g. session.created →
   run.started); self-parent refused; deeper type-level causality deferred
   to the emission slice — stated, not ambiguous.
3. **Reveal store concurrency**: check-then-write is atomic under an internal
   lock (register/close/is_closed/reads); racing identical registrations are
   idempotent, racing conflicting ones have one winner + one conflict, and a
   NEVER-vs-revealable race can never downgrade a registered policy.
4. **Parent payload parity completed**: `section_winner.selected` carries
   `assembly_flags` (closed PenaltyFlag list, dup-free, absent when
   unresolved); `assembly.completed` carries `flags_by_section` (closed
   section keys ⊆ assembled sections, dup-free flag lists).
5. **Receipt contract decided**: `receipt_ref` = `sha256:<64 hex>` — the
   digest addressing the immutable AtomicReceiptStore record; format is
   verifiable without store access, content verification happens at
   projection integration. Rules: `required` for provider.completed;
   `optional_pending_integration` for provider.failed /
   ratification_vote.recorded / blocking_objection.raised (runtime does not
   mint those receipts yet — stated honestly); `none` elsewhere, where a
   present receipt_ref is itself a violation.
6. **Frozen registries**: `CONTRACT_MATRIX` and `PAYLOAD_MODELS` are
   `MappingProxyType` views over private dicts; mutation raises TypeError;
   matrix rows are frozen dataclasses.
7. **Reserved role-row fields**: a raw role_history row must carry EXACTLY
   {phase, round_index, agent_id, role} — a forged `recorded_index`/
   `schema`/`schema_name` or any unknown key is rejected, never silently
   replaced. `RoleDisplayRow` now carries an explicit `schema_version`.

Extra coherence: AnonymousMapping non-empty context + `round_index ≥ 0` +
≥1 subject; assembly requires exactly the five locked sections;
`thin_sections` dup-free; typed non-negative `ProviderTokenUsage`; bounded
patterns on event_id / causal_parent_id / receipt_ref / artifact_digest.

## Hardening round 3 (adversarial review of 83435ef — all 5 findings closed)

1. **Run-scoped reveal contexts (critical)**: `AnonymousMapping` and every
   store key/API now carry `run_id` —
   `(session_id, run_id, phase, round_index, evaluator_id, purpose)`. `run_id`
   participates in the seed, context key and both digests, so two runs in one
   session get different aliases and fully independent register/close/reveal
   lifecycles: closing run A cannot reveal run B, and a NEVER policy in run A
   cannot affect run B.
2. **Snapshot-before-verify registration (TOCTOU)**: `register()` first takes
   a private re-validated snapshot, verifies THE SNAPSHOT, and stores THE
   SNAPSHOT — the caller-owned mapping is never touched after the snapshot, so
   mutating its nested `assignments`/`presentation_order` after verification
   cannot poison the store.
3. **Resolvable typed receipt reference**: `receipt_ref` is now the typed
   `ReceiptRef` (`ced_receipt_ref_v1`) = `receipt_kind` + `request_id`
   (locates the record; `AtomicReceiptStore` is addressed by
   `sha256(request_id)` / `load(request_id)`) + `receipt_digest` (verifies the
   loaded content). Receipt-bearing events must carry the matching
   `receipt_kind`. Receipt wire vocabulary is `required | optional | none`;
   "pending integration" is documentation/status only.
4. **Pre-clock event/causality validation**: a single `_preflight()` runs ALL
   checks (dedupe/conflict, global event_id uniqueness, causality) under the
   lock BEFORE the clock and again after it for races — a broken clock can no
   longer mask a real `CedCausalityError`/`CedEventConflictError`, and an
   invalid append never touches the clock.
5. **Same-session causality**: cross-STREAM causal links are allowed only
   within one session (`session:<S>` → run-of-`S`); a parent from another
   session is refused pending an explicit cross-session lineage contract.
   Also: `flags_by_section` keys must be RESOLVED sections — an unresolved
   section has no winning content to flag.

## Hardening round 4 (adversarial review of ebb5c19 — narrow reveal contract)

1. **Strict reveal input contract**: `AnonymousMapping` is now `strict=True`
   with a `mode="before"` validator that ONLY canonically parses the wire
   enum strings (`purpose`, `reveal_policy`) so JSON still round-trips —
   everything else is validated strictly. `round_index="0"`/`True`,
   whitespace-only `session_id`/`run_id`/`phase`/`evaluator_id`, sentinel
   `run_id`, blank real subject ids (at the model AND in `build_mapping`),
   and non-`^[0-9a-f]{64}$` `permutation_digest`/`mapping_digest` are all
   rejected.
2. **Real TOCTOU regression test**: a `monkeypatch` on module-level
   `verify_mapping` mutates the caller's mapping the instant verification
   returns (inside the verify→store window) and proves the stored snapshot
   stays canonical — locking the actual snapshot-before-verify cause, the
   way the `idempotency_key` test locked its cause.

Repository sync: merged `origin/main` (adds `AGENTS.md`, `CLAUDE.md`; no code
overlap) and added the branch working documentation folder
`docs/branches/feature-council-live-view-foundation/` required by `AGENTS.md`.

## What exists now

Package: `backend/dialogues/projection/` — pure contracts, zero execution.

| Module | Contract | Key guarantees |
|---|---|---|
| `taxonomy.py` | closed dotted event taxonomy (22 types) + typed stream contract | exact names (`session.created` … `run.completed`); `session.created` is session-scoped (`run_id=None`, stream `session:<id>`); all others run-scoped (`run:<id>`); sentinel run ids (`"none"`, `"null"`, …) rejected; `stream_id` is derived, never caller-asserted |
| `payloads.py` | one strict typed payload model per event type (22/22, import-time completeness guard) | `extra="forbid"` + `strict=True` + `frozen=True`; unknown field / wrong type / NaN / Infinity rejected; `PAYLOAD_SCHEMA = "<event>.payload"`, `PAYLOAD_VERSION` per model; `move.validated` requires split `raw_digest`/`validated_digest` (`^[0-9a-f]{64}$`) |
| `events.py` | `ced_epistemic_event_v1` envelope (frozen, strict) + semantic identity | fields: schema/schema_version/**payload_schema/payload_version**/event_id/idempotency_key/sequence/session_id/run_id/event_type/actor_id/subject_id/phase/round_index/emitted_at/causal_parent_id/receipt_ref/artifact_digest/payload; wrong event↔payload pairing and payload-version mismatch rejected; `semantic_digest` = canonical sorted-UTF-8 JSON **excluding event_id** (sequence/emitted_at structurally absent from drafts) |
| `ledger.py` | `EventLedger` — append-only, per-stream | **sequence starts at 1**, gap-free, assigned only at append; duplicate (same stream+key+content) → existing event, no sequence consumed; **conflict** (same stream+key, different content) → `CedEventConflictError`, no mutation, no sequence consumed; failed append leaves no gap; reads return fresh **tuples** of frozen events; cross-stream isolation; no global singleton, no callbacks, injected callable (clock) never runs under the lock; deterministic injected clock |
| `reveal.py` | §6.5 blind-evaluation reveal policy | aliases scoped per (session, **run**, phase, round, evaluator, purpose) — never global; per-evaluator deterministic SHA-256 permutation; backend-owned digest-sealed `AnonymousMapping`; TOCTOU-safe snapshot-before-verify registration; reveal gated on explicit `close_evaluation()`; `NEVER` policy stays sealed; canonical forged-mapping detection; **not a scheduler**: never selects voters/subjects — a self-subject input raises `SelfSubjectError` as a tripwire for an upstream eligibility bug (self-scoring prohibition remains the canonical protocol's responsibility) |
| `role_display.py` | §6.2 role-loop display | exclusively projects canonical `role_history`; **no role recalculation, no inferred primary role, no silent repair**; frozen rows carrying exactly `{phase, round_index, agent_id, role}`; groupings computed backend-side — the frontend renders, never calculates |

Tests: `tests_dialogues/test_projection_events_ledger.py` +
`test_projection_reveal_role_display.py` + `test_projection_contract_matrix.py`
— including the explicit audit cases (session.created stream semantics;
sequence-from-1; failed-append-no-gap; duplicate-no-sequence;
same-key/different-content conflict; 22/22 executable identity;
extra-field/wrong-type/pairing/version payload rejection; immutable reads;
cross-stream isolation; per-run/per-evaluator alias scope; TOCTOU snapshot;
canonical tamper detection; sealed-before-close; NEVER unrevealable;
pre-clock causality; same-session causality; malformed/reserved-field role
row refused; display never recalculates; frozen registries;
runtime-inertness guard) plus integration against a real offline
`CEDOrchestrator.run_session`.

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

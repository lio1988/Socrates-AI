# Socrates Epistemic Hybrid v1 — H1 Shadow Implementation

Status: implemented and validated on `feature/openrouter-live-provider`.

H1 is observation-only. It adds append-only Hybrid records after canonical CED
finalization and does not govern claim truth, epistemic support, scoring,
assembly, ratification, release, provider routing, prompts, or public events.

## Authority boundary

- `CEDOrchestrator` remains the sole execution and release authority.
- `SessionState` and `FinalResponse` contain no Hybrid field or projection.
- H1 records use the fixed authority label `shadow_non_authoritative`.
- quality-score observations use the fixed signal class `quality_only`.
- move and draft content is recorded as unassessed output, never as verified
  claim, evidence, support, truth, or successful falsification.
- the observer is explicitly injected and disabled by default.
- observer/append failure is caught after canonical finalization and may only
  add a bounded exception-class diagnostic outside canonical state.

H1 does not create a second protocol authority. It also does not merge with the
deferred Council Live View `EventLedger`, create public events, or duplicate the
shared `AtomicReceiptStore`.

## Append-only record contract

`backend/dialogues/hybrid_shadow.py` owns a versioned envelope:

- schema version `socrates.hybrid-shadow.h1/v1`;
- deterministic per-session sequence;
- deterministic subject-scoped idempotency key;
- deterministic content-addressed record ID;
- previous-record hash-chain link;
- immutable conflict refusal;
- deep-copy reads;
- deterministic replay and reconstruction validation.

Exact duplicate append is idempotent. Reusing one subject identity with
different content raises `HybridLedgerConflict`; retained history is never
overwritten.

H1 observes these canonical artifact classes:

1. session;
2. exact provider/model roster;
3. phase transitions;
4. role assignments;
5. tasks;
6. moves;
7. five-section draft candidates;
8. move-level quality scores;
9. section-level quality scores;
10. assembled answer;
11. ratification;
12. final response authority projection.

Raw user questions, provider prose, final-answer prose, score justifications,
ratification rationales, prompts, keys, authorization headers, and hidden
reasoning are not retained. Content needed for linkage/audit is represented by
SHA-256 digests and stable provenance references.

## Determinism boundary

H1 introduces no random record identity. Existing H0 compatibility fields that
remain random, including auxiliary scoring-task move IDs, are not used as
Hybrid identity. H1 derives deterministic shadow references without modifying
canonical fields, preserving byte parity. Making every legacy canonical task ID
deterministic remains a prerequisite before any later governing activation; H1
does not silently change that authority surface.

## Runtime integration

The explicit `hybrid_shadow` dependency is accepted by `CEDOrchestrator` and
`build_council`. Capture occurs exactly once:

- after registry final audit and optional self-improvement hooks;
- after a registry quorum fallback is finalized;
- after the legacy ratification path is finalized.

No capture occurs inside provider, phase, scoring, assembly, or ratification
decisions. The default value is `None`, so the H0 path remains unchanged.

## Offline proof

`tests_dialogues/test_hybrid_shadow_h1.py` proves:

- byte-identical `FinalResponse` and `SessionState` before/after capture;
- equivalent canonical outputs and provider call traces with shadow on/off;
- identical role, scoring, assembly and ratification authority state;
- deterministic streams across equivalent independent runs;
- idempotent duplicate capture, contiguous sequence and replay;
- immutable conflict refusal and protected internal payloads;
- exact provider/model provenance;
- no raw prompts, secrets, questions or answer prose in records;
- quality signals cannot claim epistemic support or verification;
- append failure cannot change canonical output or provider calls;
- quorum-failure capture does not fabricate an answer;
- disabled-by-default behavior has no shadow side effect.

Validation on 2026-08-21:

- focused H1: `11 passed`;
- final critical H1/canonical/OpenRouter matrix: `86 passed`;
- `tests_dialogues`: `1602 passed`;
- repository-wide: `1909 passed`, with 23 pre-existing warnings;
- compileall: passed;
- `git diff --check`: passed.

## One explicitly approved live shadow session

Session `hybrid_h1_level3_live_001` ran the frozen Level-3 presentation-order
puzzle once through this exact heterogeneous OpenRouter council:

- `openai/gpt-4.1-mini`;
- `openai/gpt-4o-mini`;
- `meta-llama/llama-3.3-70b-instruct`.

Results:

- exact models used: all three; final adapter receipts verified each exact ID;
- provider tasks: 72 `ok`, zero provider failures/timeouts;
- move-score coverage: 24/26 (`partial`), with two invalid/missing score outputs;
- section scores: 29 collected, one invalid/missing score output;
- self-scoring violations: zero;
- final answer: correct order `Anna -> Ben -> Clara -> David`;
- ratification: `ratified_with_caveats`;
- Hybrid records: 168, contiguous sequence, replay verified, zero capture
  failures, final kind `final_response.observed`.

The two ratified caveats were logically invalid. They claimed uniqueness depends
on reading "before" as non-immediate. The problem separately says "immediately
before" for Clara/David, so ordinary "before" is unambiguously earlier-than.
Even under the caveats' counterfactual immediate reading for Anna/Ben, the two
blocks can only be `AB-CD` or `CD-AB`; Ben-not-last removes `CD-AB`, leaving the
same unique `AB-CD` order. H1 correctly observed this canonical weakness but,
by design, did not repair or overrule it.

No raw live transcript, provider response, key, or receipt payload is committed.
No second paid session was run.

## Stop boundary

H1 is complete as a shadow observation layer. H2 quality/epistemic-support
separation, objection verification, claim authority, compatibility gates, and
governing release changes remain unimplemented and require a separate approval.

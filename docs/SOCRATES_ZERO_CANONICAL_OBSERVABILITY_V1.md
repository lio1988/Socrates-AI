# SocratesZero Canonical Observability v1

Status: Phase 6 implementation checkpoint on
`feature/socrates-zero-canonical-observability-v1`

## Research hypothesis

Real predecision CED/Hybrid snapshots already contain authoritative typed
epistemic distinctions that SearchState v0 turns into opaque digests or omits.
The smallest safe experiment is an opt-in read-only v1 envelope that preserves
those distinctions without deciding them again.

This phase changes representation only. It does not change Value, Policy,
Greedy, BestOfN, PUCT, successor semantics, CED execution, Hybrid authority,
benchmarks, providers, learning, RL, or production behavior.

## Authority boundary

The governing direction remains one-way:

```text
CED / Hybrid / canonical verifier
  -> current immutable typed observation
  -> SearchStateV1
```

`SearchStateV1` cannot mutate or call back into the source. It does not decide
whether verification succeeded, support exists, an objection is resolved, or a
contradiction is valid. The v1 projector asks the canonical Hybrid state for
`assess_all()` and copies its result. It never reproduces assessment rules.

The v1 contract stays in `backend/dialogues/ced_search_observability_v1.py`, on
the trusted CED side. Moving it into `backend/dialogues/socrates_zero` would
make the runtime-inert search package import authoritative Hybrid types and
would violate the existing H8 boundary.

## Source-of-authority audit

| Canonical signal | Type and owner | Production/current-time source | v0 representation | v1 representation | Decision |
|---|---|---|---|---|---|
| Verification outcome | `VerificationResult`; Hybrid/verifier | `VerificationRecord`, validated by `add_verification()` | `ObservationRef`: source digest plus audit provider/model identity; result is opaque | `CanonicalVerificationView.result` with record/claim/objection/evidence links | included |
| Verification class/method | `VerificationClass`, `VerificationMethod`; Hybrid/verifier | verifier record before projection time | inside opaque verification digest | typed class and optional typed method | included |
| Verification failure | `FALSIFIED` and `INCONCLUSIVE`; Hybrid/verifier | canonical verification result | opaque digest only | literal typed result | included; operational provider failure is separate |
| Required but unverified | `VerificationResult.EXTERNAL_EVIDENCE_REQUIRED` and `SupportState.EXTERNAL_EVIDENCE_REQUIRED`; Hybrid | `external_evidence_required()` plus governing assessment | opaque verification digest; no support state | typed result and governing typed assessment | included |
| Governing claim support | `SupportState`, `ClaimAssessment`; Hybrid | `HybridEpistemicState.assess_all()` at projection time | omitted | claim ID, typed support state, exact basis/falsifying/unresolved record IDs, assembly eligibility | included |
| Admissible evidence semantics | `EvidenceRecord`, `EvidenceStance`, `EvidenceSourceType`; Hybrid | canonical evidence ledger and `record.admissible` | ID plus digest; stance/source/claim/receipt opaque | source record ID, claim ID, typed stance/source type, optional receipt link | included for admissible records only |
| Objection lifecycle | `ObjectionState`, `ObjectionScope`, `ObjectionTargetProvenance`; Hybrid | `add_objection()` and `transition_objection()` | raised/pending/inconclusive conflated with aporia under unresolved count/digests; validated/rejected omitted | all current canonical lifecycle states with target, scope, provenance, verification link | included |
| Contradiction lifecycle | `ContradictionState`; Hybrid | `add_contradiction()`, `validate_contradiction()`, `dismiss_contradiction()` | candidate/validated have opaque record digest; dismissed omitted | all current canonical states with claim pair and verification link | included |
| Socratic question lifecycle | no governing open/resolved type | `InquiryState` is only a process recommendation; `AporiaRecord` names a remainder and explicitly has no truth authority | aporia appears as unresolved ID/digest | none | rejected: no canonical resolution state exists |
| Abstention | no upstream canonical epistemic record | `TerminalStatus.ABSTAINED` and `ActionKind.ABSTAIN` are downstream search vocabulary | typed downstream terminal/action only | none added | rejected: projection must not back-create upstream authority |
| Revision/evidence carry | `RevisionRecord`, `EvidenceCarry`; Hybrid | canonical revision ledger | unsuperseded claim filtering and claim digest; revision records omitted | no dedicated view in minimal v1 | deferred: governing current assessment is exposed; lineage is not required for this hypothesis |
| Commitment lifecycle | `CommitmentStatus`; Socratic ledger | declared agent commitment history | live authoritative commitment ID/digest | unchanged inside v0 base only | rejected from epistemic v1: a declaration is not support |
| Provider/task failure | `ProviderStatus`; CED task log | operational task record | accepted moves must be provider-OK; failure records omitted | none | rejected from this epistemic schema; not truth or verification failure |
| Ratification, release, score, consensus, confidence, markers | CED governance/quality records | current or terminal CED records | mostly absent or digest/audit data | none | forbidden as canonical epistemic semantics |

Every included field satisfies the eligibility rule: it exists upstream, is
typed, current-time, deterministic, provenance-linkable, requires no prose or
score interpretation, duplicates no decision logic, and can be copied
read-only.

## Versioned contract

The new immutable identifiers are:

```text
socrates.zero.search-state/v1
ced-search-state-projection/v1
```

`SearchStateV1` is an additive envelope containing:

- the complete frozen v0 `SearchState` as `base_state`;
- the governing Hybrid schema version;
- typed admissible-evidence views;
- typed verification views;
- typed governing claim-assessment views;
- typed objection lifecycle views;
- typed contradiction lifecycle views.

Nothing imports or exports this projector through the v0 default module. An
explicit call to `project_search_state_v1()` is required.

## Provenance and identity

Evidence, verification, objection, and contradiction observations retain their
actual canonical source record ID and canonical entity links. Claim assessments
are computed governing views rather than stored records, so no fictional
assessment record ID is created. Their provenance is the real claim ID plus the
exact basis, falsifying, and unresolved record IDs returned by `assess_all()`.

Each observation has a SHA-256 semantic digest over only its typed IDs, enums,
relationships, and receipt reference where available. Raw claim/evidence/
objection/verifier prose, confidence, scores, consensus, epistemic markers,
provider routes, and model identities do not enter a new typed observation.

The v1 state ID includes the v1 schema/projection/authority versions, the frozen
v0 state ID, and every typed observation identity. Keeping the v0 state ID is
deliberate: the existing opaque digests remain replay/audit identity and are not
silently weakened. Therefore stylistic source changes can still change the
embedded v0 identity while leaving all new typed epistemic views identical.

Collections are sorted by canonical source record or claim ID. Duplicate IDs,
cross-family source ID collisions, dangling claims, dangling evidence/
verification links, and orphan assessment record references fail closed.
Canonical verification records are revalidated against the present task and
evidence ledger instead of being silently skipped.

## Digest/information-loss audit

| v0 digest surface | Semantics hidden | v1 action | Why retain v0 digest |
|---|---|---|---|
| active claim digest | text, author, section, verification class, supersession | claim support is exposed through governing assessment; the whole claim is not copied | replay and conservative identity |
| evidence digest | claim, stance, source type/identity, content, citation, receipt, provenance | expose only decision-relevant typed claim/stance/source/receipt | raw canonical-record audit identity |
| contradiction digest | claim pair, candidate/validated state, verification link | expose typed lifecycle and links, including dismissed records omitted by v0 | v0 replay compatibility |
| unresolved question digest | conflated aporia/objection content and lifecycle | expose objection lifecycle only; do not invent question resolution | v0 replay and Socratic remainder audit |
| verification digest | class, method, result, anchors, targets, evidence, rationale, scope, limitations, provenance | expose typed class/method/result and entity links | exact verifier-record replay identity |
| epistemic graph digest | all projected graph references | retain base digest; v1 exposes only selected typed relations | whole-projection audit identity |

The v1 keeps structured semantics alongside existing digests. A digest proves
identity changed; it does not let Value inspect why. The typed view supplies
that missing structural distinction without exposing prose.

## Pairwise scientific evidence

### Exact decision-state v0 alias

The real governing core defines `VerificationRecord.creates_support` so that a
`VERIFIED` task-internal record creates support only when no model/provider was
in the loop. Two valid records with identical verification class, method,
result, claim, anchor, condition, and model identity—but with protocol checker
versus model-route provenance—produce the same v0 semantic state ID. v0 excludes
route ID from semantic identity and exposes no claim assessment.

The canonical Hybrid assessments differ:

```text
protocol/deterministic VERIFIED record -> SupportState.SUPPORTED
model-produced VERIFIED record          -> SupportState.UNSUPPORTED
```

v1 copies those governing states and therefore separates the pair. It does not
derive support from provider metadata. Changing one non-null route/model label
to another remains semantically inert; the distinction is the upstream
authority's existing protocol-versus-model rule.

### Exact lifecycle v0 alias

A state with no contradiction record and a state with a canonical contradiction
that has reached `ContradictionState.DISMISSED` have identical v0 projections:
v0 intentionally omits dismissed records. v1 preserves the dismissed record,
its claim pair, and its source ID. No `resolved=True` boolean is invented.

### Structural opaque-digest separations

- `VERIFIED` versus `FALSIFIED` verification results change a v0 digest but have
  no inspectable v0 result; v1 exposes the literal enum.
- `SUPPORTED` versus `EXTERNAL_EVIDENCE_REQUIRED` has no v0 support field; v1
  exposes the governing `SupportState` and exact source links.
- `VALIDATED` and `REJECTED` objections disappear from the v0 unresolved set;
  v1 preserves their literal lifecycle state and verification link.

These are repository model fixtures using `HybridEpistemicState`,
`verify_task_internal()`, `transition_objection()`, and
`dismiss_contradiction()`, not invented generic state objects.

## Leakage, immunity, and purity

- Projection accepts one current source snapshot and has no access to episode
  outcome, reward, labels, or later state.
- Two identical prefixes project identically even when independently extended
  with opposite future verification results. Already projected prefix objects
  remain unchanged.
- Changes to peer scores, consensus-like score multiplicity, markers,
  confidence, stylistic CED content, Hybrid prose, and one non-null provider/
  model route identity to another leave every new typed observation identical.
- Deep before/after comparisons cover CED SessionState, commitments, aporia,
  Hybrid record maps, and transitions. Projection mutates none of them.
- Reordered Hybrid dictionaries produce byte-equivalent v1 model dumps and the
  same state ID.

## Unavailable and intentionally opaque

There is no canonical question resolution lifecycle and no upstream epistemic
abstention record, so v1 exposes neither. It also does not expose arbitrary
evidence prose/source labels, verification rationales/limitations/anchors,
claim prose, objection text, detector prose, scores, consensus, confidence,
markers, ratification, final synthesis, operational failures, future outcomes,
or benchmark utility.

Revision/evidence-carry history is real and typed but is excluded from the
minimal experiment. The current governing assessment and the unchanged v0
claim/evidence audit surface are enough to test the selected observability
hypothesis. Adding lineage later would require its own demonstrated consumer
need and pair.

## Verification status

Current implementation gates:

- canonical-observability-specific: `17 passed`;
- v1 + v0 projection/contracts + Hybrid H3–H9: `75 passed`;
- live/provider calls: `0`.

Full required regression counts and the final Phase 5 artifact/blob verification
are recorded in the branch checkpoint after completion.

## Decision gate

The hypothesis is supported only if all focused and repository-wide gates pass,
the Phase 5 artifact remains byte-identical, and v0/default behavior remains
unchanged. If supported, stop. The next milestone is a separate **Value v1
Decision Gate**, not an implementation bundled into Phase 6.

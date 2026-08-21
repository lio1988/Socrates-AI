# Hybrid v1 — H3..H7 Governing Epistemic Core

One state machine, one ledger, one authority. Verification, revision,
contradiction validation, eligibility and claim-level ratification are a single
mechanism in `backend/dialogues/hybrid_epistemic.py`, because what they share —
what a record is allowed to do — is exactly the thing that must not be
duplicated into parallel authorities.

## The governing path

```
task input
   ↓
CED execution            roles, phases, provider governance, fail-closed
   ↓
claims / objections / evidence / verification / revision / contradiction
   ↓                     the hybrid epistemic core: the only place support is decided
eligible candidates      derived from governing state, never from a rank
   ↓
quality evaluation       reported alongside, governing nothing
   ↓
claim-level ratification ballots carry the checks they relied on
   ↓
frozen release           decision + basis, reproducible by digest
```

## H3 — verification is claim-dependent

The blocking question is never "is there an evidence layer" but **where is the
verification anchored**.

| class | anchor | legal method |
|---|---|---|
| `TASK_INTERNAL` | material the task supplied | `TASK_INTERNAL_CHECK` |
| `TOOL_VERIFIABLE` | a deterministic execution receipt | `TOOL_RECEIPT` |
| `EXTERNAL_EVIDENCE` | sources outside the task | `EXTERNAL_SOURCE` |
| `NON_DEFINITIVE` | none — evaluative or normative | none |
| `NOT_CURRENTLY_VERIFIABLE` | none available | none |

Uncertain classification defaults to `NOT_CURRENTLY_VERIFIABLE`, never to
`TASK_INTERNAL`.

**Anchoring is proven, not asserted.** Every `AnchorSpan` carries a verbatim
quotation and its offset; validation re-extracts the span at that offset and
refuses the record if it does not match. A record citing a constraint the task
does not contain is *malformed*, not merely wrong.

**What deterministic code does not do.** Judge arbitrary semantic truth. It
cannot read "Ben does not present last" and evaluate it in general. Every record
states that limit in its own `limitations` field.

`EXTERNAL_EVIDENCE_REQUIRED` is a terminal answer, not a gap.

## Evidence admissibility

`MODEL_ASSERTION` exists as a source type so that a model's say-so can be
recorded and then refused. It is never admissible. That refusal is the point:
the circularity of verifying one model's claim by asking another is the failure
the whole migration exists to prevent.

Admissible: supplied task material, deterministic computation, tool receipt,
external source, human-provided.

## H3 — objection lifecycle

```
RAISED → PENDING_VERIFICATION → VALIDATED | REJECTED | INCONCLUSIVE
```

Only `VALIDATED` falsifies, and reaching `VALIDATED` or `REJECTED` requires a
verification record whose result matches. An objection may not acquire — or lose
— destructive force by assertion.

This inverts the frozen failure. `current_canonical_repeat_003` records
`false_counterexamples_enter_dialectic` → `elenchus_does_not_reject_false_counterexamples`
→ `correct_candidate_is_abandoned` → `released_answer_is_objectively_wrong`. A
raised objection is now recorded, unresolved, and powerless until checked.

A valid counterexample still falsifies. The protection is not immunity.

## H4 — revision without inherited support

Every piece of evidence on a superseded claim must be classified
`STILL_APPLICABLE`, `REVALIDATED`, `STALE`, `CONTRADICTORY` or `UNRESOLVED`.
Only the first two carry across. Anything left unclassified stays on the old
claim and the omission is recorded — the fix for the frozen
`revised_claim_retains_semantically_stale_evidence`.

Lineage is preserved; the old version is never erased.

## H5 — candidate contradictions cost nothing

A detector proposes `CANDIDATE` edges. Only a `VALIDATED` contradiction, backed
by a verified record, blocks assembly. A noisy detector may emit as many
candidates as it likes and penalise no claim — the fix for
`contradiction_edges_are_excessively_noisy`.

Assembly refuses a claim set containing a validated contradiction, which is the
fix for `renderer_combines_incompatible_selected_claims`.

## H6 — eligibility from state

A claim is eligible unless it is superseded or falsified. Never computed from a
quality rank, agreement count, marker, confidence value or CBE-style numeric
score.

## H7 — claim-level ratification and frozen release

Ballots are per claim and carry `checked_verification_ids`. A ballot with none
is recorded as unanchored and moves nothing. A ballot citing a `FALSIFIED` check
while voting `ACCEPT` is mechanically inconsistent and is reported as such.

Release decisions:

| decision | meaning |
|---|---|
| `RELEASE_SUPPORTED` | every assembled claim rests on records |
| `RELEASE_UNRESOLVED` | emitted honestly, with its epistemic state stated |
| `BLOCKED` | something falsified or a validated contradiction is in the way |

The release is frozen with its basis and a digest over the governing records, so
replaying them reproduces the decision and a later change cannot quietly rewrite
what was published.

## Legacy authority

`CEDOrchestrator._epistemic_hint` still computes `mean peer score >= 7.5 ->
well_supported`. Its consumers are display, tracing and observation; it gates
nothing. The canonical audit now carries
`legacy_epistemic_status_authority: "legacy_non_governing"` beside it, because
the remaining harm was never that the rule decided something — it was that the
output *labelled* an answer well supported and a reader trusts labels.

`backend.epistemic.evidence_scoring` is also LEGACY. Its epistemics are better
than the quality threshold — it weighs evidence stance and filters
self-assertion — but it is still a numeric path to a support verdict. Preserved
for provenance; not governing.

## H10 live benchmark

One run, three heterogeneous exact models, 85 calls, 0 failures, 0 timeouts,
$0.05817.

The council answered the frozen logic puzzle **incorrectly**, reproducing the
recorded semantic failure: it claimed the information was insufficient to
determine a unique order, when the unique order is Anna, Ben, Clara, David.

| layer | verdict |
|---|---|
| legacy | quality mean 7.586 → `well_supported` |
| governing core | `release_unresolved`, `basis_record_ids: []`, 2 unresolved objections |

The frozen failure reproduced live, and the two layers disagreed exactly where
they should. The migration does not make the council reason better; it stops the
system from claiming support it does not have.

## Limits

The core is wired for projection and decision but the canonical
`run_registry_session` does not yet route its release through it — doing so
changes canonical output and is gated by the preservation contract's parity
requirements. Live verification is not yet performed during a session, so
objections projected from a live run remain `RAISED` and therefore unresolved.

`backend/evidence/` remains empty. H3B external verification stays blocked
pending a governed substrate, and no live external verification is claimed.

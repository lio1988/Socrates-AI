# Hybrid v1 — H3A Task-Internal Verification (design only)

Verification method is claim-dependent. An earlier assessment declared H3 blocked
because no evidence substrate exists. That over-generalised from a single
example. The blocking question is not "does an evidence layer exist" but **where
is the verification anchored**. When the authoritative inputs are already in the
task, checking a claim against them is not one model rating another.

H3 therefore splits.

* **H3A — task-internal.** Claims checkable against information already supplied
  authoritatively to the session.
* **H3B — external-evidence.** Claims requiring information from outside the
  task. **BLOCKED pending a governed evidence substrate.**

No implementation is authorised by this document.

---

## 1. Claim classification

Every claim is routed to exactly one class before any verification is attempted.
The class decides which method is *permitted*; no method may be used outside it.

| class | authoritative anchor | permitted method | H3A |
|---|---|---|---|
| `TASK_DERIVABLE` | constraints, premises, documents or data supplied in the task | check the claim against the supplied inputs | ✅ |
| `TOOL_VERIFIABLE` | a deterministic execution receipt (calculation, code, test run) | re-derive or read the receipt | ✅ when a receipt exists |
| `SOURCE_VERIFIABLE` | sources outside the task | retrieval + citation + tool receipts | ❌ H3B |
| `ARGUMENTATIVE` | none — the claim is evaluative or normative | none; support is not the right question | ❌ never verified |
| `NOT_CURRENTLY_VERIFIABLE` | none available | none | ❌ stays unresolved |

Classification is itself a claim about the claim, so it is recorded, bounded, and
defaults to the most restrictive class. When classification is uncertain the
class is `NOT_CURRENTLY_VERIFIABLE`, never `TASK_DERIVABLE`.

## 2. What is verifiable under H3A today

The frozen logic benchmark, present verbatim in both known-failure fixtures:

```
1. Anna presents before Ben.
2. Clara presents immediately before David.
3. Ben does not present last.
```

Ground truth in the fixture: `unique: true`, single valid order
`Anna, Ben, Clara, David`.

Every constraint is stated in the task. A proposed counterexample such as
`C-D-A-B` is `TASK_DERIVABLE`: it can be tested against constraint 3 and rejected
because Ben is last. Nothing outside the session is consulted.

The general contract is not puzzle-specific:

```
claim or counterexample + authoritative task inputs -> bounded verification record
```

Anything with the same shape qualifies: supplied constraint sets, supplied
documents, supplied structured data, arithmetic, and code or test receipts
produced during the session.

## 3. What must wait for H3B

The Stanford Prison Experiment premise used in the live experiments. The task
asserts that the SPE demonstrated ordinary people turn cruel under institutional
power. Whether that is accurate depends on Le Texier's archival work, the BBC
replication, guard coaching and selection bias — **none of which is in the
task**. There is no authoritative anchor in the session, so the class is
`SOURCE_VERIFIABLE` and the honest state remains `UNRESOLVED`.

H2 already produced exactly that on live data, which is the behaviour to
preserve. H3A must not "resolve" it with a second model.

## 4. VerificationRecord schema

Append-only, non-authoritative at this stage, written to the existing H1 ledger.

| field | meaning |
|---|---|
| `schema_version` | pinned |
| `record_id`, `session_id` | ledger identity |
| `claim_ref` | the move or claim under test |
| `claim_class` | one of the five classes in §1 |
| `method` | `TASK_INTERNAL_CHECK` or `TOOL_RECEIPT`; nothing else is legal in H3A |
| `authoritative_inputs` | **verbatim quoted spans from the original task**, each with an offset proving it is present |
| `condition_tested` | the exact condition evaluated, stated explicitly |
| `result` | `VALID` / `INVALID` / `INCONCLUSIVE` |
| `inconclusive_reason` | required when `INCONCLUSIVE`; includes `EXTERNAL_EVIDENCE_REQUIRED` |
| `rationale` | why the condition holds or fails |
| `scope` | what this record does and does not cover |
| `limitations` | stated, not implied |
| `verifier_provider_id` | who produced it — recorded, never a vote |

**What deterministic code checks.** That the record is complete; that
`claim_class` and `method` are compatible; that every span in
`authoritative_inputs` occurs **verbatim in the original task text** at the
offset given; that `INCONCLUSIVE` carries a reason. A record citing a constraint
the task does not contain is rejected as malformed — not as "wrong".

**What deterministic code does not do.** Judge arbitrary semantic truth. It
cannot read "Ben does not present last" and evaluate it in general. That
limitation is the honest boundary of this stage and is recorded in every record's
`limitations`.

## 5. Preventing false counterexamples from being destructive

This is the failure the fixtures froze. `current_canonical_repeat_003` records
the mechanism exactly:

```
false_counterexamples_enter_dialectic
elenchus_does_not_reject_false_counterexamples
correct_candidate_is_abandoned
reflection_reinforces_false_consensus
incorrect_reasoning_receives_high_quality_scores
released_answer_is_objectively_wrong
```

with `epistemic_status: well_supported` on an objectively false answer.

The rule: **a counterexample carries no force until it holds a `VALID`
verification record.** An unverified or `INCONCLUSIVE` counterexample is recorded
as raised and may be argued about, but it cannot be cited as grounds for
abandoning a candidate. `INVALID` marks it refuted, and the refutation is
attributable and replayable.

This inverts the frozen failure: `C-D-A-B` would carry an `INVALID` record
quoting constraint 3, so abandoning `A-B-C-D` on its basis becomes visible as
unfounded rather than persuasive.

## 6. Valid counterexamples must still falsify

The protection must not become immunity. A `VALID` record — one that quotes a
supplied constraint and shows the candidate violates it — falsifies the claim.
Falsification by task-internal check is the one direction where H3A is decisive,
because the anchor is authoritative by construction.

Asymmetry is deliberate and matches the epistemics: a counterexample checked
against a supplied constraint can *refute*; no number of passing checks
*establishes* a claim. `VALID`/`INVALID` are about the counterexample, never a
promotion of the claim to supported.

## 7. Voting, and what makes its criteria good

This system is a council. Voting is its mechanism and is meant to stay. The
failure was never that the council voted — it was **what** it voted on and
**with what in hand**.

### What a vote may decide

* **acceptance** — "the council releases this as its output" is a governance act
  and belongs to the council;
* **quality comparisons** — which of two drafts argues better;
* **procedure** — whether to continue, which draft advances, which section wins.

### What a vote may never decide

* whether a factual claim is true;
* whether a conclusion is epistemically supported.

Agreement is not corroboration. Ten models trained on overlapping data agreeing
is one observation with a large error bar, not ten observations.

### Well-worded criteria were not enough

`EVALUATION_DIRECTIVE` already tells judges to reward grounding and calibration
over confidence, length and style, and explicitly forbids herding: *"an output is
not better because others seem to agree."* Provider identity is hidden. On paper
the criteria are sound.

And `current_canonical_repeat_003` still records
`incorrect_reasoning_receives_high_quality_scores`, `three_ratifiers_accept`, and
a released answer that is objectively wrong at `epistemic_status: well_supported`.

So the defect is structural, not lexical. `RATIFICATION_CONTENT_DIRECTIVE` asks
for a `verdict` and a `rationale` — a conclusion and some prose about it. **No
field carries what the ratifier actually checked.** For the logic benchmark the
right ballot question is not "does this meet the bar" but "does this order
satisfy constraints 1, 2 and 3", which is decidable — and the ballot never asks
it.

### Good criteria, concretely

1. **The ballot carries the check, not only the verdict.** For a
   `TASK_DERIVABLE` claim, a verdict must include `checks_performed`: each
   supplied constraint quoted verbatim with its offset, and whether the candidate
   satisfies it.
2. **A verdict must agree with its own checks.** A ballot reporting a violated
   constraint and then voting `accept` is internally inconsistent, and that is
   mechanically detectable without judging the reasoning.
3. **Weight is asymmetric.** One anchored refutation outranks any number of
   unanchored acceptances. Ballots are not summed toward truth; an unanchored
   verdict on a decidable question is recorded as an opinion and is not grounds
   for abandoning a candidate.
4. **Independence is measured, not assumed.** The frozen mechanism includes
   `reflection_reinforces_false_consensus`: ratifiers were voting on a position
   they had helped converge on. Correlated ballots must be recorded as correlated
   rather than counted as separate confirmations.
5. **Scope discipline.** Where a claim is `SOURCE_VERIFIABLE`, the ballot may
   still decide acceptance, and it may not touch epistemic support. Unanimity
   without an anchor leaves the support state exactly where H2 put it.

### Why this differs from majority voting

Not because votes are forbidden, but because a vote on a decidable question must
show its work. The anchor is the original task; cited spans must occur verbatim
in it and code proves that; and a correct citation does not become stronger by
being repeated. Verification records are never summed, averaged or ranked, and
the verifier's identity is recorded for attribution rather than weight.

Ten models asserting a counterexample is valid, none citing a supplied
constraint, produce nothing. One record quoting constraint 3 settles it. That is
not the abolition of voting — it is what makes a council vote worth counting.

## 8. Provider disagreement yields INCONCLUSIVE

When two well-formed records disagree on the same claim, the result is
`INCONCLUSIVE` with reason `CONFLICTING_VERIFICATION`. No tie-break, no majority,
no scoring. Disagreement about what a supplied constraint entails is a signal
that the check was not decisive, and the honest output is that it was not.

## 9. Proving original-task anchoring

Anchoring is proven mechanically, not asserted. Each entry in
`authoritative_inputs` carries the quoted span and its offset in the task text,
and validation re-extracts the span at that offset and compares. A record whose
citation does not match is malformed and is refused.

This is why `question_verbatim` and `question_lines` matter in the fixtures: the
original task text is the anchor, so it must be preserved exactly and never
paraphrased into the record.

## 10. Offline tests using the frozen fixtures

Both fixtures carry the benchmark verbatim, so these run with no provider and no
network:

1. classification — the logic benchmark's constraints classify `TASK_DERIVABLE`;
   the SPE premise classifies `SOURCE_VERIFIABLE`;
2. `C-D-A-B` against constraint 3 yields `INVALID` with the constraint quoted;
3. `A-B-C-D` against all three constraints yields no violation;
4. a record citing a constraint absent from the task is refused as malformed;
5. a record citing a real constraint at a wrong offset is refused;
6. `SOURCE_VERIFIABLE` claims yield `INCONCLUSIVE / EXTERNAL_EVIDENCE_REQUIRED`
   and never a `VALID`;
7. two conflicting well-formed records yield `INCONCLUSIVE /
   CONFLICTING_VERIFICATION`;
8. an unverified counterexample carries no force;
9. no verification result alters `SessionState` or `FinalResponse`;
10. records replay deterministically alongside H1 and H2.

**Fixture limitation, stated rather than worked around.** The
`false_counterexamples_introduced` field is `true`, but the counterexample text
was clipped and is marked unavailable. Tests must use the preserved constraints
with constructed counterexamples; they cannot replay the original wording, and
must not pretend to.

## 11. Claim-directed verification

Added after eleven live sessions in which the governing layer returned
`unresolved` every single time, whatever the question.

The cause was structural rather than a bug. Every verification the canonical
path produced was aimed at an *objection*, and `assess_claim` deliberately
excludes objection-scoped records from a claim's basis — an objection check can
only ever take support away. Nothing ever checked a claim, so no claim could
ever acquire a basis, so the only reachable states were `unresolved` and
`unsupported`. Honest, and uninformative.

`run_claim_verification` asks peer seats the other question: does the task's own
material bear on the council's answer? Only the `core_answer` claim is checked;
the remaining sections elaborate it, and checking all five would multiply the
call count to decide the same thing.

### The question is deliberately split

A verifier answers two fields, not one:

* `claim_contradicted_by_task` — the task's material rules the claim out. This
  is the only answer that can falsify, and it is a statement about the
  conclusion.
* `claim_established_by_task` — the task's material settles it affirmatively.

Collapsing these is the same error that scope separation fixed for objections.
An incomplete argument for a true statement leaves it true and unestablished,
which is `contradicted: false, established: false` — a common and correct answer.
The directive says so explicitly, because a model asked one merged question will
answer the easier one.

### The gate

Identical to the one guarding destruction: two independent verifiers, unanimous
on the result, citing a passage they both anchored (under the H3 anchor
equivalence rule). Support earned by a weaker standard than refutation would be
a thumb on the scale.

The gate sits *before* storage, in `apply_claim_verification`, because
`assess_claim` admits any stored `VERIFIED` record into a basis. Filtering after
storage would mean one model's reading had already become support.

### What it still refuses

* one seat's `VERIFIED`, however confident — `UNCORROBORATED`
* a council that merely agrees with the answer — agreement without task material
  is `established: false` by instruction, and produces no usable record
* verifiers who reach the same verdict citing different passages —
  `NO_ANCHOR_AGREEMENT`
* a fabricated citation — refused outright, contributing nothing

### Checked-and-unsettled is not never-checked

When the gate refuses, the protocol stores its own `INCONCLUSIVE` record so the
claim reads `UNRESOLVED` — something bore on it and did not settle it. The one
exception is `NO_RECORDS`: nothing usable came back, so claiming an examination
took place would be false, and the claim keeps whatever state it had.

## Boundary (revised)

H3A was originally verification-only: a `VALID` counterexample refuted, and
nothing created support. That held while every governing stage was unimplemented.
With H7 routing the canonical release through `freeze_release`, the one-way
boundary made the governing verdict a constant, which is not a safety property —
a layer that says `unresolved` unconditionally distinguishes nothing.

Support is therefore reachable, and only through the path above: a corroborated,
anchored, task-internal check of the claim. Quality scores, confidence values,
consensus, ratification, epistemic markers, model self-classification and one
model's opinion of another remain incapable of creating support, unchanged.

`backend/evidence/` stays empty. Building a substrate before H3B needs one would
be speculative infrastructure.

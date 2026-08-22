# Hybrid v1 — Release and Epistemic-State Semantics

There is exactly one governing epistemic authority. This document says which
field it is, which fields merely look like it, and how to read each.

## The one governing authority

`hybrid_epistemic.freeze_release()` produces a `FrozenRelease`. It is the only
function in the system that yields a release decision, and
`test_hybrid_invariants.py::test_there_is_exactly_one_release_authority` pins
that.

| field | meaning |
|---|---|
| `release_decision` | `RELEASE_SUPPORTED` / `RELEASE_UNRESOLVED` / `BLOCKED` |
| `claim_states` | per claim: `supported`, `unsupported`, `unresolved`, `falsified`, `external_evidence_required` |
| `basis_record_ids` | the records support rests on. Empty means unsupported, always |
| `unresolved_record_ids` | open objections, contradictions, inconclusive checks |
| `frozen_digest` | digest over the governing records; replay reproduces the decision |

## The field that is not the authority

`FinalResponse.epistemic_status` is produced by `CEDOrchestrator._epistemic_hint`:

```python
avg = mean(peer scores)          # 0..10
if avg >= 7.5:  return "well_supported"
if avg >= 5.5:  return "contested"
else:           return "speculative"
```

That is a **quality threshold with an epistemic name**. It is retained as a
public compatibility field and it governs nothing.

**Consumers, exhaustively:** `demo.py` display, `learning_trace_collector`
tracing, and the hybrid observers that report it for comparison. No release
gate, no eligibility computation and no assembly decision reads it.

The canonical audit now carries the fact beside the value:

```json
"legacy_epistemic_status_authority": "legacy_non_governing"
```

The remaining harm was never that the rule decided something. It is that the
output *labels* an answer well supported, and a reader trusts labels. Naming the
authority where the value travels is what makes the migration visible to anyone
consuming the response.

## Reading a response correctly

| question | field |
|---|---|
| Is this supported? | `FrozenRelease.claim_states` and `basis_record_ids` |
| May it be released? | `FrozenRelease.release_decision` |
| How well was it argued? | peer scores, `quality_mean` |
| Did the council accept it? | `ratification_status` — a governance act |
| What did the old system call it? | `epistemic_status`, legacy, non-governing |

An answer may legitimately be **high quality, ratified, and unresolved** at the
same time. That combination is not a contradiction; it is the system declining
to convert fluency and agreement into support. The H10 live benchmark produced
exactly it.

## Hybrid code may not consume the legacy status as support

`hybrid_support` carries `legacy_epistemic_status` for comparison only, and
`test_hybrid_support_h2.py::test_legacy_well_supported_does_not_make_the_hybrid_status_supported`
forces the point: setting the legacy field to `well_supported` leaves the hybrid
state unchanged.

`hybrid_epistemic` does not read it at all. `SUPPORT_INPUT_CLASSIFICATION`
classifies `legacy_epistemic_status` as `QUALITY_SIGNAL`.

## What the H10 benchmark demonstrated

The council answered a solvable logic puzzle incorrectly. Both layers reported,
and they disagreed:

| layer | verdict |
|---|---|
| legacy | quality 7.586 → `well_supported` |
| governing | `release_unresolved`, basis `[]`, 2 unresolved objections |

The reasoning system can still be wrong. The hybrid layer does not claim
otherwise and cannot make a council reason better. The property it adds is
narrower and is the one that matters: **the protocol no longer manufactures
strong epistemic support out of quality and consensus when authoritative support
is absent.**

## What an objection is about, and what follows from not knowing

Added after the live five-analyst run, which is the clearest demonstration so
far of why the question matters. A deterministic receipt established the
`final_verdict` section. An uncorroborated objection, filed by the projection
against `core_answer` because that section happened to sort first, held the
entire release at `release_unresolved`. The objection had no established
relationship to the thing it suppressed.

### Targeting comes from provenance or it does not exist

| priority | source | provenance recorded |
|---|---|---|
| 1 | a critical ratification ballot naming `target_section` | `ratification_target_section` |
| 2 | an objection carrying an explicit section or claim identifier | `declared_identifier` |
| 3 | nothing establishes a subject | `unmapped` |

`UNMAPPED_TARGET` is a real outcome, not a failure path. The objection is
recorded, appears in the audit, matches no claim, and is never put to a
verification vote — it could move nothing whatever the verdict, so paying models
to decide it buys nothing.

Nothing countable maps an objection. Agreement between seats, confidence values,
peer scores and ratification counts decide no target; only a declared identifier
does. Four seats unanimously certain the answer is wrong, naming no section, map
to nothing at all.

For this to be reachable at all, `ELENCHUS_TARGET_DIRECTIVE` asks a critic to
name the section its objection bears on, and says plainly that `"none"` is an
honest answer costing nothing while a guessed section costs the answer.

### The release decision follows the basis, not the noise

`RELEASE_SUPPORTED` now requires every **basis-bearing** claim to assess as
`SUPPORTED`. It is not withheld because something unresolved exists elsewhere in
the session.

The four cases, exhaustively:

| situation | decision |
|---|---|
| conclusion supported, unrelated or unmapped objection open | `release_supported` |
| unresolved objection targeting the basis-bearing claim | `release_unresolved` |
| validated conclusion-scoped objection anywhere assembled | `blocked` |
| no basis at all | `release_unresolved` |

This needs no special case. A claim holding an admissible basis *and* an
unresolved objection already assesses as `UNRESOLVED`, so a doubt aimed at the
conclusion still blocks by the ordinary rule. A doubt aimed at an ancillary
section stays in `unresolved_record_ids` for the audit and decides nothing about
a conclusion it was never about.

Two things this deliberately does not do. A receipt for `final_verdict` does not
validate the other four sections — `claim_states` reports each claim on its own
records, and the governing layer stays claim-level throughout. And an objection
is never reassigned to a claim it did not name in order to make it count.

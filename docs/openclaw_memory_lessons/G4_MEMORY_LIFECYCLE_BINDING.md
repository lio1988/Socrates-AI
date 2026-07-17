# G4 Memory Evidence — Current-State Lifecycle Binding

The G4 attestation bridge does not stop checking after evidence registration.
Personal Memory evidence is re-bound to current governed state at every
production lifecycle boundary:

```text
submit → evaluate → decide → transactional apply
```

## Why two lesson inputs exist

The governed APIs accept two different pieces of catalogue context:

- `stable_lesson_ids`: lessons currently eligible for a **new link**;
- `lesson_fingerprints`: exact fingerprints of **all current curated lessons**,
  including deprecated lessons that may still need a governed unlink.

Do not build the second map from stable lessons only. A linked lesson may later
be deprecated, and harmful evidence must still be able to support its removal.

## Canonical catalogue context

```python
from backend.dialogues.openclaw_memory import (
    load_lesson_fingerprints,
    load_stable_lessons,
)

stable_lesson_ids = tuple(
    lesson.lesson_id for lesson in load_stable_lessons()
)
lesson_fingerprints = load_lesson_fingerprints()
```

`load_lesson_fingerprints()` includes every current curated lesson and hashes the
complete record: ID, name, status, type, source, use conditions, patterns, exact
lesson text, and risk.

## Governed facade flow

```python
from backend.dialogues.openclaw_identity import GovernedSelfRevisionSystem

system = GovernedSelfRevisionSystem.from_root(
    "runs/openclaw_self_revision_system"
)

system.evaluate(
    "local_apprentice_001",
    "REV-MEMORY-0001",
    evaluated_by="Evidence Reviewer",
    stable_lesson_ids=stable_lesson_ids,
    lesson_fingerprints=lesson_fingerprints,
)

system.decide(
    "local_apprentice_001",
    "REV-MEMORY-0001",
    decision="approved",
    decided_by="Independent Approver",
    decision_reference="review/memory-0001",
    stable_lesson_ids=stable_lesson_ids,
    lesson_fingerprints=lesson_fingerprints,
)

system.apply_approved(
    "local_apprentice_001",
    "REV-MEMORY-0001",
    applied_by="Identity Writer",
    application_reference="identity/memory-0001",
    stable_lesson_ids=stable_lesson_ids,
    lesson_fingerprints=lesson_fingerprints,
)
```

## Fail-closed behavior

The governed lifecycle refuses a Memory proposal when:

- evidence is not an attributed single-agent Lesson A/B record;
- the evidence source lacks the full G4 binding marker;
- the evidence was produced for another governed Identity state;
- the current lesson ID is absent from `lesson_fingerprints`;
- the exact curated lesson fingerprint changed;
- evaluation or decision omits the current fingerprint map;
- transactional application receives a stale map.

Application binding is checked **before** a write-ahead journal or Identity file
is created. Therefore stale Memory evidence cannot leave a half-applied
transaction.

## Recovery boundary

Once a transaction reaches `prepared`, recovery completes the exact already
preflighted and hash-bound intent stored in the write-ahead journal. Recovery is
not a new approval or a fresh experiment evaluation. Operators must not edit the
catalogue, Identity, evidence, lifecycle, or journal files while an incomplete
transaction is awaiting recovery.

## Low-level API boundary

Production/operator code should use `GovernedSelfRevisionSystem` and its
recoverable transaction coordinator. Raw registry methods remain available for
compatibility and isolated tests, but direct low-level profile application is
not the supported G4 activation path.

Nothing in this binding grants tools, prompt mutation, roles, permissions,
council weight, provider access, or CED authority.

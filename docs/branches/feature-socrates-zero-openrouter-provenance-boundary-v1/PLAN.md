# PLAN — feature/socrates-zero-openrouter-provenance-boundary-v1

## Success criterion

See [README.md](README.md). One binary result: SUPPORTED or FALSIFIED.

## Architectural decision

Three concepts are separated:

| concept | representation |
| --- | --- |
| A. current runtime semantic dependency | none for the predecessor — proven, not asserted |
| B. historical scientific provenance | immutable identity record, no raw path |
| C. current mutation / integrity coverage | scoped inventory, hash-verified |

The two predecessor entries in the SIBLING scope of
`FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1` are replaced, in place and in
order, by immutable provenance reference identifiers. The digest recorded for a
provenance row is the content-addressed digest of the whole immutable record, so
tampering with any identity field — artifact ID, artifact SHA-256, case-set ID,
validation-order ID, sealed commit, Git object identity, semantic ID, or role —
changes the row digest and is reported as a mutation.

Because the current inventory genuinely no longer contains those two raw paths,
its derived inventory ID genuinely changes. This is correct and is **not**
forced back to the historical value. `OpenRouterScopedPathSnapshotV1` therefore
becomes generation-aware:

- **historical generation** — `inventory_id` equals the frozen historical
  inventory ID. Rows are validated by frozen content-addressed snapshot identity
  and row count, which locks all 90 historical rows including their paths and
  hashes. This is strictly stronger than the membership-tuple equality it
  replaces for that generation.
- **current generation** — `inventory_id` equals the derived current inventory
  ID. Membership and order are enforced against the current inventory exactly as
  before.
- any other value is rejected.

`OpenRouterScopedMutationEvidenceV1` needs no change: the sealed artifact records
zero mutations, so its membership check never ranks a historical row.

## Status

All steps complete. Result: **PROVENANCE BOUNDARY v1 SUPPORTED**.
Every validation gate below was met; see [PRESENT.md](PRESENT.md) for exact
results and [the canonical result document](../../SOCRATES_ZERO_OPENROUTER_PROVENANCE_BOUNDARY_V1.md)
for the full record. No stop condition was triggered.

## Ordered steps

1. **Initialize** branch documentation. *(commit 1 — `acc0dfc`)* **done**
2. **Audit** *(done — 0 runtime semantic dependencies)* every runtime occurrence of the predecessor raw path and classify
   it; AST-audit imports. Stop and falsify if any runtime semantic dependency
   exists.
3. **Add** *(done)* `backend/dialogues/socrates_zero/openrouter_provenance_boundary_v1.py`
   with immutable, content-addressed provenance records.
4. **Edit** `openrouter_route_controls_evaluation.py`, provenance-only:
   substitute the two reference identifiers, freeze the historical generation
   constants, make the snapshot contract generation-aware, resolve provenance
   references during capture. *(commit 2 — `661840c`)* **done**
5. **Test** — adapt the one existing inventory test that assumed every row is a
   file, and add the adversarial suite. *(commit 3 — `526e6ca`)* **done**
6. **Verify** the gates below. *(done — all green)*
7. **Document** the result and close the checkpoint. *(commit 4)* **done**

## Validation gates

| gate | expectation |
| --- | --- |
| exact static node | FAIL before, PASS after, genuinely |
| Route Controls focused suite | 103 passed at baseline, no regression |
| v1 + v2r1 evidence suite | 48 passed at baseline, no regression |
| new provenance boundary suite | all pass |
| frozen surface hashes | byte-identical before and after |
| `git diff --check` | clean |
| external activity | OpenRouter 0 / provider 0 / model 0 / credential 0 / CED 0 / aggregate 0 / replay 0 |

## Stop conditions

Falsify and stop rather than proceed if any of the following holds:

- a runtime semantic dependency on predecessor acquisition cases exists;
- the static node can only be made to pass by weakening, skipping, encoding,
  concatenating, or relocating the forbidden reference;
- any sealed artifact would have to be regenerated;
- any expected SHA constant would have to change;
- current mutation protection would be reduced rather than relocated to
  immutable scientific identity.

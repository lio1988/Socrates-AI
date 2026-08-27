# PLAN — feature/socrates-zero-openrouter-wire-mapping-v2-authorization-gate

## Success criterion

One binary answer, field-by-field traceable to retained official evidence, with
the sealed record verified untouched. No soft pass.

## Ordered steps

1. **Verify** the source checkpoint is exactly
   `ae8b3ec17810deb0c8523c78a541d032994fb408` with a clean tracked worktree.
   **done**
2. **Branch** from that commit, not from `main` and not from the historical
   invalid v2 branch. **done**
3. **Audit** the v2r1 manifest field by field across the sixteen required
   response-wire concerns, classifying each ESTABLISHED /
   PARTIALLY_ESTABLISHED / NOT_ESTABLISHED and naming the exact supporting
   source, fact, mapping or relationship. Infer nothing. **done**
4. **Test** the mapping-eligibility rules against that audit: every required
   mapping must be category A, B or C, and none may rest on repository
   convention, historical canned shapes, prior parser assumptions, model memory,
   heuristic provider inference, or inference from absence. **done**
5. **Predeclare** the future parser boundary. If it cannot be defined from
   retained evidence, return NOT EARNED. **done**
6. **Verify** the provenance gate read-only and run the read-only test gates.
   **done**
7. **Decide**, and document. **done**

## Validation gates

| gate | expectation | result |
| --- | --- | --- |
| exact provenance static node | PASS | 1 passed |
| Route Controls focused | 103 | 103 passed |
| v1 + v2r1 evidence | 48 | 48 passed |
| provenance boundary | 64 | 64 passed |
| full `tests_dialogues` | no regression | 3279 passed, 10 skipped |
| frozen surfaces | 15/15 identical | identical |
| `git diff --check` | clean | PASS |
| external activity | all zero | all zero |

## Predeclared boundary for Phase 8.5D-S5

The future mapper may only: accept raw bytes; parse JSON fail-closed; distinguish
documented success and error envelopes; extract only officially supported fields;
preserve unknown fields non-authoritatively; emit explicit ABSENT /
PRESENT_EMPTY / PRESENT_WITH_ENTRIES / METADATA_UNAVAILABLE / NOT_ESTABLISHED
states; keep requested model distinct from actual served model; keep provider
label distinct from exact endpoint identity; never infer a cache hit from
metadata absence; never read fallback into multiple attempts.

Offline-first, raw-bytes-first, one parser version, one normalized contract
version, one mechanically derived fixture set, strict unknown-field policy,
strict provenance, fail-closed, no production adapter authority, no live pilot.

## Stop conditions

Return NOT EARNED rather than proceed if any of the following had held:

- any required authority resting on repository convention or historical canned
  shapes;
- attempts, provider or cache semantics requiring invention;
- absence being read as a value anywhere;
- the parser boundary being undefinable from retained evidence;
- the provenance boundary being unclean, or any sealed surface having changed.

None held.

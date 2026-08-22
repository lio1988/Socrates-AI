# Hybrid v1 — checkpoint at `f8144cd`

State of the migration at the moment the governing layer first became capable of
a verdict. Written so a later session can resume without re-deriving any of it.

| | |
|---|---|
| branch | `main` |
| HEAD | `f8144cdb726504fa45573bc787d0c9b05c8b37ca` |
| unpushed | 40 commits ahead of `origin/main` |
| suites | `tests_dialogues` 1879 passed · repository 2186 passed, 23 pre-existing warnings |
| gates | `compileall` clean · `git diff --check` clean |

## Stage status

| stage | state | where |
|---|---|---|
| H0 baseline freeze | done | frozen fixtures |
| H0.5 preservation contract | done | `test_h0_preservation_contract.py` (2) |
| H1 shadow ledger | done | `test_hybrid_shadow_h1.py` |
| H2 quality/support separation | done | `test_hybrid_support_h2.py` |
| H3 verification — objection-directed | done | `test_objection_verification.py` (40) |
| H3 verification — claim-directed | **done at this checkpoint** | `test_claim_verification.py` (32) |
| H3B external evidence | **not implemented** | `backend/evidence/` holds only `__init__.py` |
| H4 revision | done | `HybridEpistemicState.revise` |
| H5 contradiction | done | `ContradictionRecord`, validated-only blocking |
| H6 eligibility | done | `_eligibility`, derived from support state alone |
| H7 canonical authority | done | `test_h7_canonical_authority.py` (18) |
| H8 authority map | done | `test_hybrid_authority_h8.py` (11) |
| H9 adversarial regression | done | `test_hybrid_epistemic_h3_h9.py` (28) |
| H10 live benchmark | run once — **do not re-run**, it is paid | — |

Supporting suites: anchor equivalence 21, mid-session sessions 10, hybrid
invariants 15.

## The law this is all built around

`QUALITY != EPISTEMIC SUPPORT`

Quality score, confidence, consensus, corroboration count, ratification
popularity, epistemic marker, model self-classification, and one model's opinion
of another may **never** create epistemic support, evidence, verification or
truth. Every stage above is enforcement of that sentence, and
`test_hybrid_invariants.py` is where it is pinned.

## What is proven, and by what

**Offline, deterministically.** Support reachable only through a corroborated,
anchored, task-internal check. Destruction reachable only through a corroborated
objection that targets the *conclusion*. Anchor equivalence by source identity,
source version and material span overlap — never by text similarity. A lone seat
settles nothing in either direction. Agreement reached by citing different
passages settles nothing. Fabricated citations contribute nothing rather than
being downgraded into a weaker signal.

**Live, on paid runs.** Three real bugs that were invisible offline: the
OpenRouter adapter never sent the canonical prompt; the score parser read a
nested shape while models emit a flat one (0/26 scores); five task kinds got a
"include the marker" instruction contradicted by an "EXACTLY these fields" list
(0/8 → 7/9 after the marker became a named field).

Across three Level-3 live runs the council answered correctly twice, the legacy
layer said `well_supported` regardless, and the governing layer said
`unresolved`. Run #3's near-miss — two seats citing the same span differing by a
full stop — is why scope separation was done **before** anchor overlap. The other
order would have falsified a correct answer, and
`test_9_equivalent_anchors_with_a_justification_objection_do_not_falsify` is the
frozen regression for it.

## What is NOT proven

1. **No live claim verification has ever run.** The layer is now *capable* of
   reaching `supported`. Whether live models clear the bar — two seats quoting
   the same passage and both answering `established: true` — is untested. This
   is the single most valuable next experiment.
2. **No external evidence substrate.** Any claim needing facts from outside the
   task stays `unresolved` by construction, correctly.
3. **Internal incoherence is invisible to both layers.** In the museum-director
   run the council answered (B) correctly while its own stress-test section said
   (B) "conflates correlation with causation" — backwards. Legacy said
   `ratified_with_caveats`; governing said `unresolved`. Neither detects that an
   answer contradicts itself. This is a fourth limitation, distinct from the
   three already recorded.
4. **Only `core_answer` is claim-checked.** The other four sections are never
   verified against the task.

## Deliberate boundary crossing at this checkpoint

`HYBRID_V1_H3A_TASK_INTERNAL_VERIFICATION.md` originally stated that nothing in
H3A creates support. That held while the governing stages were unimplemented;
after H7 it made the governing verdict a constant, which distinguishes nothing
and is not a safety property. Support is now reachable — through one path only,
recorded in that document's revised Boundary section. Reverting `f8144cd`
restores the old semantics cleanly.

## Worktree

`scripts/live_dialogue.py.bak` is untracked and was not authored by the agent;
it is the operator's backup and is theirs to remove. Nothing else is dirty.

## Next safe step

One live run of `scripts/live_dialogue.py` on a self-contained, task-checkable
question, reading the new `EPISTEMIC LAYERS` block. Expected cost: the six
dialogue phases, plus ratification, plus 3 peers per raised objection, plus one
claim-verification round across all seats. The result to look for is whether
`claim verdict` comes back as anything other than `no_records` — that single
field is what the whole checkpoint is waiting on.

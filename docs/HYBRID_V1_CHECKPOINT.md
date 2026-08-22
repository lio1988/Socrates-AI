# Hybrid v1 — checkpoint at `fdf1c2b`

State of the migration at the point where `SUPPORTED` first became reachable by
a route that does not involve asking a model. Written so a later session can
resume without re-deriving any of it.

| | |
|---|---|
| branch | `main` |
| HEAD | `fdf1c2bda0e82c82bc150291c4629085eee61ac7` |
| unpushed | 43 commits ahead of `origin/main` |
| suites | `tests_dialogues` 1880 passed · repository 2187 passed, 23 pre-existing warnings |
| gates | `compileall` clean · `git diff --check` clean |

## Stage status

| stage | state | where |
|---|---|---|
| H0 baseline freeze | done | frozen fixtures |
| H0.5 preservation contract | done | `test_h0_preservation_contract.py` |
| H1 shadow ledger | done | `test_hybrid_shadow_h1.py` |
| H2 quality/support separation | done | `test_hybrid_support_h2.py` |
| H3 verification — objection-directed | done | `test_objection_verification.py` (40) |
| H3 verification — claim-directed by seats | **tried and reverted** | see below |
| H3 support — deterministic computation | **done at this checkpoint** | `test_task_checker.py` (32) |
| H3B external evidence | not implemented | `backend/evidence/` holds only `__init__.py` |
| H4 revision | done | `HybridEpistemicState.revise` |
| H5 contradiction | done | validated-only blocking |
| H6 eligibility | done | derived from support state alone |
| H7 canonical authority | done | `test_h7_canonical_authority.py` (18) |
| H8 authority map | done | `test_hybrid_authority_h8.py` (11) |
| H9 adversarial regression | done | `test_hybrid_epistemic_h3_h9.py` (28) |
| H10 live benchmark | run once — **do not re-run**, it is paid | — |

Supporting suites: anchor equivalence 21, mid-session sessions 10, hybrid
invariants 15, projection identity 4.

## The law this is all built around

`QUALITY != EPISTEMIC SUPPORT`

Quality score, confidence, consensus, corroboration count, ratification
popularity, epistemic marker, model self-classification, and one model's reading
of the task may **never** create epistemic support, evidence, verification or
truth. `test_hybrid_invariants.py` is where it is pinned.

## The attempt that was reverted, and why it matters

`f8144cd` let peer seats check a claim against the task and recorded agreement
between two of them, citing the same passage, as support. Reverted in `12c55de`
the same day. The demonstration puts identical epistemic content through two
doors:

```
declared as MODEL_ASSERTION evidence  ->  unsupported, basis []
wrapped as a TASK_INTERNAL check      ->  supported,   basis [ver_2113...]
```

`assess_claim` filtered evidence through `ADMISSIBLE_EVIDENCE_SOURCES` and did
not filter verification records at all — safe only by accident, because nothing
produced a claim-directed verification. Opening them to the basis routed a
model's reading around the check that exists to refuse it.

`quality 7.5 → truth` and `two seats plus one quote → truth` are the same
mistake at different resolutions. This is the single most important thing in
this document.

**The structural fix**: `VerificationRecord.creates_support` requires
`verifier_provider_id` to be unset. Support now depends on a stated property of
the record, not on which record shapes happen not to exist yet.

**Refutation is deliberately not symmetric.** A refutation exhibits a finite
pointer — the task says X, the claim says not-X — which a reading can do. An
establishment asserts a universal — nothing defeats the claim and the cited span
suffices — which it cannot. A false refutation also fails into silence about a
right answer; a false support fails into confident error.

## The one route to support

`backend/dialogues/task_checker.py`. No model at any point: it parses the task
under a small explicit grammar, enumerates exhaustively, and emits
`DETERMINISTIC_COMPUTATION` evidence attributed to the module.

Demonstrated offline, with the legacy layer saying `well_supported` in all three:

| council's answer | governing | release |
|---|---|---|
| correct order | `supported` | `release_supported` |
| wrong order | `falsified` | `blocked` |
| echoes the prompt | `unsupported` | `release_unresolved` |

The completeness guard is the load-bearing part: any sentence mentioning one or
two entities that the grammar cannot read aborts the whole check. A silently
dropped constraint would report a uniqueness that does not hold — the one bug
here capable of manufacturing false support.

## What is NOT proven

1. **Nothing here has run live.** No live session has ever produced a
   `deterministic_checks` entry, and no live session has ever shown the
   `EPISTEMIC LAYERS` block, which only landed in `dd28f48`.
2. **The grammar covers single-slot ordering and nothing else.** The
   museum-director style question — the one the operator most recently ran — is
   not machine-checkable by this checker and stays `unresolved` by construction.
   That is correct, and it is also most real questions.
3. **No external evidence substrate.** Any claim needing facts from outside the
   task stays `unresolved`.
4. **Internal incoherence is invisible to both layers.** In the museum run the
   council answered (B) correctly while its own stress-test section said (B)
   "conflates correlation with causation" — backwards. Neither layer detects an
   answer contradicting itself.

## Worktree

`scripts/live_dialogue.py.bak` is untracked and was not authored by the agent;
it is the operator's backup and is theirs to remove. Nothing else is dirty.

## Next safe step

One live run of `scripts/live_dialogue.py` on the frozen Level-3 ordering task —
the one the checker's grammar covers. Two fields decide whether any of this
works outside the test suite: `computed checks`, and whether `governing status`
finally differs from `unresolved`. If the council answers correctly, this is the
first run in which the governing layer should say `supported` and mean it.

# The Epistemic Marker Contract

An `epistemic_marker` is a deliberating agent's own label for the status of its
own central claim. It is **self-description metadata**. It is not evidence, not
verification, not truth, and it grants nothing.

## Vocabulary

| marker | meaning | confidence ceiling |
|---|---|---|
| `established_fact` | verifiable, uncontested | 1.00 |
| `logical_inference` | follows necessarily from premises | 0.95 |
| `reasonable_hypothesis` | plausible, evidence incomplete | 0.75 |
| `open_uncertainty` | genuinely unsettled | 0.55 |
| `unsubstantiated_claim` | asserted without support | 0.40 |

A move whose `confidence` exceeds its own marker's ceiling is an epistemic
inconsistency. CED records it and never rewrites it.

## One authority

`marker_is_contracted(task_kind)` in `reasoning_prompts.py` is the single source
of truth for who carries a marker. Both the reasoning directive and the output
contract read it; neither re-tests the condition.

That consolidation is not cosmetic. The rule had been written twice — once to
gate the directive, once to gate the contract — and the two copies drifted:
`LESSON_RELEVANCE_DIRECTIVE` said "EXACTLY **this** field", singular, which an
audit searching for "EXACTLY these" walked straight past.

Deliberating kinds carry a marker. Evaluative kinds — `move_score`,
`section_score`, and every ratification kind — never do: they judge someone
else's claim, so a marker for "your own central claim" is meaningless there.

## Two bugs this contract fixed

**The prompt contradicted itself.** Five deliberative kinds received both
"include in your `content` an `epistemic_marker` field" and "EXACTLY these
fields / do not add other top-level fields". Models resolved the contradiction by
obeying the structural rule and dropping the marker. Live coverage measured
**7%–21%**.

**The carve-out did not work either.** Adding "the marker is the ONE permitted
extra top-level field" after the example left `synthesis_draft` at **0 markers in
8 contracted live calls**. The directive opens "EXACTLY these five string
fields", shows an example with five, and an instruction arriving after the
example does not undo the one before it.

The fix that worked: the marker is a **named required field** — listed, counted,
and present in the example — in every directive that enumerates fields. There is
then nothing extra to resist.

Measured on `synthesis_draft`, three models × three attempts:

| | before | after |
|---|---|---|
| coverage | 0/8 = 0.000 | 7/9 = 0.778 |

One of the two misses was a provider timeout rather than a marker failure,
making the marker rate 7/8. Session-wide coverage rose from 0.143 to 0.321 across
the intermediate stages; it is not solved, and it is not expected to be. Contract
consistency is required; perfect model compliance is not.

## The boundary

A marker may be used for **audit, diagnostics, calibration, coverage measurement
and prioritising what later verification should look at first**.

A marker may **never**:

- create or upgrade epistemic support;
- create evidence, verification, or `WELL_SUPPORTED`;
- create ratifiability or release eligibility.

A council that stamped `established_fact` on every move would change this
system's diagnostics and change nothing about what it had established. The same
prohibition binds quality scores, confidence, agreement and ratifier popularity.
See `docs/HYBRID_V1_H2_SUPPORT_SEPARATION.md`.

## Where markers are read

`parse_and_validate_move` lifts `content["epistemic_marker"]` onto
`AgentMove.epistemic_markers`. An absent or unrecognised marker is simply not
lifted — never a rejection, and never a fabricated default.

`CEDOrchestrator._epistemic_consistency` checks marker↔confidence bands and
records violations. Hybrid H2 records the marker as advisory metadata.

## Tests

`tests_dialogues/test_marker_contract.py` — 56 offline cases. Over every task
kind it asserts that the directive and the output contract agree with
`marker_is_contracted`, that no kind both requires and forbids the marker, that
evaluative kinds stay marker-free, that an explicit caller contract still
overrides the default, and that the output contract stays last and ends with
"and nothing else." as `test_agent_alignment` requires.

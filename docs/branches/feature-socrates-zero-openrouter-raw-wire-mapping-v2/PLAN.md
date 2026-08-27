# PLAN — feature/socrates-zero-openrouter-raw-wire-mapping-v2

## Success criterion

`OPENROUTER RAW WIRE-MAPPING v2 SUPPORTED` only if every threshold below is met.
Thresholds are predeclared, before authoritative execution, and are not tuned
afterwards.

## Predeclared thresholds

| # | threshold | required |
| --- | --- | --- |
| 1 | valid official fixtures accepted | all |
| 2 | adversarial contradictions rejected | all |
| 3 | first-failure guard matches the predeclared expectation | all rejected cases |
| 4 | false authority grants | 0 |
| 5 | endpoint identity synthesis | 0 |
| 6 | requested → actual substitution | 0 |
| 7 | provider-display → endpoint substitution | 0 |
| 8 | metadata-absence → cache-hit inference | 0 |
| 9 | unknown-field authority escalation | 0 |
| 10 | repository-convention mappings | 0 |
| 11 | historical canned-shape dependencies | 0 |
| 12 | external activity of every kind | 0 |
| 13 | deterministic replay | semantic equality and byte identity |
| 14 | frozen predecessor surfaces | 16/16 unchanged |
| 15 | focused and repository test suites | pass |

Any essential safety invariant failing means FALSIFIED.

## Status

All steps complete. Result: **OPENROUTER RAW WIRE-MAPPING v2 SUPPORTED**, with
runtime authority and live execution both NOT AUTHORIZED. Every predeclared
threshold was met; see [PRESENT.md](PRESENT.md) and the
[canonical result document](../../SOCRATES_ZERO_OPENROUTER_RAW_WIRE_MAPPING_V2.md).

Two defects were found and fixed, both before they could contaminate a
conclusion: the static dependency detector matched its own marker literals
(before the authoritative aggregate), and the import-inertness test used
`importlib.reload` and broke class identity for later tests (after the aggregate,
in test code only, with no effect on the artifact). No stop condition triggered.

## Ordered steps

1. **Initialize** branch documentation. *(commit 1)*
2. **Implement** the raw observation contract, strict decoder, header contract,
   normalized mapping contract and the mapper. *(commit 2)*
3. **Derive** fixtures and the frozen case set from retained official evidence,
   positive and adversarial, each bound to the evidence that authorizes it.
   *(commit 3)*
4. **Evaluate** deterministically, and record the authoritative artifact plus
   replay execution and lock. *(commit 4)*
5. **Verify** the gates, frozen surfaces and replay.
6. **Document** the result and close the checkpoint. *(commits 5 and 6)*

## Validation gates

New S5 focused tests; S3 provenance boundary suite; exact static provenance node;
Route Controls focused suite; v1 + v2r1 evidence suite; `git diff --check`; full
`tests_dialogues` (source baseline 3279 passed, 10 skipped — S5 additions should
raise the pass count).

## Stop conditions

Falsify rather than proceed if: the retained evidence cannot authorize a needed
mapping; a fixture would need an invented semantic; replay is nondeterministic;
any authority leaks across the endpoint, cache, model or provider firewalls; or
any frozen predecessor surface changes.

If a code defect is found **before** authoritative execution, fix and document it
normally. Once the authoritative aggregate has run, the result is scientific
evidence and is not re-run as though it were the same experiment.

# Proof Sprint — Mini Evidence Report v0.1

This is the first small proof sprint for the CED learning/evidence stack.

The goal is not to add another architecture phase. The goal is to check whether
the existing ground-truth and evidence harness can compare two answer sets on the
same fixed tasks.

## What this sprint contains

- 8 deterministic ground-truth tasks.
- 2 candidate systems:
  - `baseline_naive`
  - `ced_reference`
- One evidence harness run that ranks the systems by accuracy, score ratio, and coverage.

## Important boundary

This is a fixture-only sprint. `ced_reference` is not yet a live provider or full
CED runtime output. It is a deterministic reference output set used to verify that
the evidence harness can produce an auditable comparison.

The next proof sprint should replace `ced_reference` and `baseline_naive` with
real captured outputs from:

1. a plain baseline prompt, and
2. the actual CED pipeline.

## Run locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues/test_proof_sprint_mini_evidence.py -q
```

Expected result:

```text
2 passed
```

## What success means

If this passes, the project has a working evidence-sprint scaffold:

```text
ground-truth tasks
+ baseline outputs
+ CED outputs
→ deterministic evidence report
→ leaderboard
```

This is the bridge from architecture to proof.

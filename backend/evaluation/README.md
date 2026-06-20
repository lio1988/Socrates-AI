# CED Evaluation Harness v0.1 — Scripted Mode

A deterministic, local, CI-safe benchmark for the CED reasoning machinery.

## What it does

For each fixed scripted case it drives the **real** CED machinery — claim
extraction, Elenchus target selection, revision, and Current Best Explanation —
and scores it with deterministic metrics:

1. **claim_extraction** — did the substantive claim survive and wrappers get stripped?
2. **elenchus_target** — did Elenchus target the right claim?
3. **revision_usefulness** — did the revision actually improve the claim? (two-pronged)
4. **single_shot_vs_ced** — is the CED final answer at least as good as a single shot?
5. **cbe_quality** — does the Current Best Explanation carry the required fields?

## What it does NOT do

- It performs **no live model calls** (the session manager is a `ScriptedModel`,
  the async dialogue pipeline is never invoked). A guard test asserts this.
- It does **no web search**, touches no frontend, adds no Evidence Layer or
  Argumentation Framework, and rewrites no architecture.

## Read `run_score` humbly

`run_score` (and `aggregate_run_score`) is a **regression / baseline signal**
over scripted cases. It is **not** a truth metric and does **not** prove that
"CED is better" in general. The honest reading is:

> "CED improved on this scripted case according to these deterministic metrics."

Two of the metrics (revision usefulness, single-shot vs CED) use our own
Socratic-pressure scorer as the yardstick, so there is some circularity. v0.1
reduces it by also checking revision text against **external gold annotations**
(`expected_revision_contains`, `forbidden_revision_contains`,
`must_address_objection_contains`). It is fully removed only later, once an
Evidence Layer provides an external, checkable yardstick.

## Run it

```bash
# Deterministic, offline, no API:
python -m backend.evaluation.run_eval
```

## Data

`data/ced_benchmark_v0.json` — `schema_version` must equal `ced_eval_v0.1`;
the loader rejects anything else.

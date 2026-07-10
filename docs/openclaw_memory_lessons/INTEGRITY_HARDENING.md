# OpenClaw Integrity Hardening

This pass closes adversarial gaps found after the OpenClaw merge.

## Enforced changes

- Shadow Apprentice reuses exact synthesis lesson IDs from the injected-context ledger when available.
- Shadow evidence is a matched-pair comparison: apprentice and council winner are re-scored by the same eligible judges and rubric. A provider cannot score its own winning council section.
- Lesson A/B verdicts veto unresolved-section regressions, ratification regressions, insufficient sample size, and excessive per-question harm.
- Identity promotion recomputes the declarative gate from the evidence before recording a promotion; caller-supplied `passed=True` is not trusted.
- Trace secret detection runs before any in-memory append or disk write and raises under optimized Python as well.
- Prompt lineage now distinguishes composition fingerprints from exact rendered-prompt fingerprints.
- PromptRegistry stores `(prompt_id, version_label)` and refuses ambiguous unversioned lookups.

## Still explicit

- `approved_by` is audit attribution, not cryptographic authentication.
- Prompt and identity registries remain runtime-inert toward CED.
- Tree-search “never worse” claims apply to matched deterministic scoring with default `cohesion_margin=0`; coherence-aware assembly may deliberately trade a bounded score margin for whole-answer coherence.
- Reusing the same `session_id` on the same CED orchestrator remains unsupported until the injected-context ledger is moved into per-session state or reset in CED at session start.

## Tests

`tests_dialogues/test_openclaw_integrity_hardening.py` contains adversarial regression tests for the new invariants.

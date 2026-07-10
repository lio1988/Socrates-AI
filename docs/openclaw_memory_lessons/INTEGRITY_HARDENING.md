# OpenClaw Integrity Hardening

This pass closes adversarial gaps found after the OpenClaw merge. The rule is
consistent across every layer: measure the event that actually happened, fail
closed when evidence is incomparable, and never turn missing evidence into
promotion.

## Enforced changes

### Injected context and Shadow Apprentice

- Shadow Apprentice replays the exact unique SYNTHESIS lesson IDs recorded by
  the council's injected-context ledger.
- The operator flow passes the same stable lesson pool to the council and the
  apprentice; it no longer enables memory on only one side.
- A council-ledger lesson ID missing from the apprentice pool produces an
  auditable `lesson_pool_mismatch` failure. It is never silently dropped.
- Shadow evidence is matched-pair evidence: apprentice and council-winning
  sections are re-scored by the same eligible judges and rubric.
- The provider that produced a winning council section cannot judge that pair.
- Missing half-pairs are excluded. A run with no complete eligible pair fails as
  `no_eligible_matched_comparisons`; it does not become successful evidence.
- Only explicitly successful, capture-time-marked shadow records against a
  ratified council target can contribute promotion wins. Failed and unratified
  records remain visible as diagnostics but cannot make promotion easier.

### Lesson effectiveness A/B

- Arm order is counterbalanced across questions to reduce control-first order
  bias.
- Execution mode and configured available-provider sets must match; otherwise
  the row is operationally incomparable and invalid.
- No actual treatment injection remains `UNTESTED`.
- Treatment assembly collapse after real injection is catastrophic harm, not an
  invalid row that disappears from the aggregate.
- `helped` vetoes ratification regressions, unresolved-section regressions,
  catastrophic collapses, insufficient sample size, and excessive per-question
  harm.
- Reports include mean and median score deltas, harm rate, coverage changes,
  catastrophic regressions, configuration mismatches, and arm order.

### Identity evidence and persistence

- Identity promotion recomputes the declarative gate from embedded evidence;
  caller-supplied `passed=True` is never trusted.
- Before/after trace evidence requires equal-size windows and, when complete
  questions are present, the same question multiset. Easier or smaller after
  windows cannot fabricate improvement.
- Identity persistence is atomic (`temp file -> fsync -> os.replace`).
- Existing history must remain an exact prefix of new history.
- New version entries must match a canonical `VersionGate`; new stage entries
  must advance exactly one canonical ladder rung.
- Every appended earned-state transition needs a named, non-self approver.
- Descriptive evidence fields may be recomputed without granting authority.
- Corrupt registry records raise visibly; they are never silently skipped.

### Trace and prompt lineage

- Trace secret detection runs before any in-memory append or disk write and
  raises under optimized Python as well.
- Prompt lineage distinguishes composition fingerprints from exact rendered
  prompt fingerprints.
- `PromptRegistry` stores `(prompt_id, version_label)` and refuses ambiguous
  unversioned lookups.

## Still explicit

- `approved_by` is auditable attribution, not cryptographic authentication.
- Prompt and identity registries remain runtime-inert toward CED.
- A first-ever identity record can represent an operator placement (for example
  a new local model placed directly into Shadow Apprentice mode). Subsequent
  earned-state changes are monotonic and policy-validated.
- Tree-search “never worse” claims apply to matched deterministic scoring with
  default `cohesion_margin=0`; coherence-aware assembly may deliberately trade
  a bounded score margin for whole-answer coherence.
- Reusing the same explicit `session_id` on the same CED orchestrator remains
  unsupported until the injected-context ledger and related caches are moved
  into per-session state or reset atomically at session start.
- Real-model effectiveness remains unproven until the R2 matched-compute
  benchmark runs with live/local model inference.

## Adversarial test modules

- `tests_dialogues/test_openclaw_integrity_hardening.py`
- `tests_dialogues/test_openclaw_shadow_apprentice.py`
- `tests_dialogues/test_openclaw_shadow_fail_closed.py`
- `tests_dialogues/test_openclaw_shadow_evidence_eligibility.py`
- `tests_dialogues/test_openclaw_lesson_ab_integrity.py`
- `tests_dialogues/test_openclaw_trace_window_matching.py`
- `tests_dialogues/test_openclaw_identity_registry_integrity.py`
- `tests_dialogues/test_shadow_dialogue_script.py`

These tests are designed to attack the evidence contract, not merely exercise
happy paths. A full local `tests_dialogues` run remains required before merge.

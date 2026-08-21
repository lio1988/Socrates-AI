# Hybrid v1 — Preservation Matrix

Migration may replace **authority**. It must not silently delete **capability**.
Every mature capability is accounted for below with where it now lives, what it
is now permitted to decide, and which tests cover it.

| capability | current implementation | final hybrid location | authority class | preserved | test coverage |
|---|---|---|---|---|---|
| CED orchestrator | `dialogues/ced.py` | unchanged | AUTHORITATIVE (execution) | ✅ | `test_phase8c_registry_session`, preservation gate |
| deterministic role rotation | `ced.assign_roles_for_phase` | unchanged | AUTHORITATIVE (execution) | ✅ | `test_deterministic_roles`, `test_canonical_execution_restoration` |
| stable model identity per seat | `ced._bind_session_adapters` | unchanged | AUTHORITATIVE (execution) | ✅ | `test_canonical_execution_restoration` |
| TELOS directive | `reasoning_prompts.TELOS_DIRECTIVE` | unchanged | ADVISORY | ✅ | `test_agent_alignment` |
| Context Protocol | `reasoning_prompts.CONTEXT_PROTOCOL` | unchanged | ADVISORY | ✅ | `test_agent_alignment`, `test_prompt_registry` |
| reasoning kernels | `openclaw_socratic_kernel/` | unchanged | ADVISORY | ✅ | `test_micro_socratic_*` (6 files) |
| Devil's Advocate / elenchus role | `reasoning_prompts.ROLE_REASONING` | unchanged | ADVISORY | ✅ | `test_agent_alignment`, `test_deliberation_tree` |
| adaptive dialectic | `ced._adaptive_dialectic` | unchanged | ADVISORY | ✅ | `test_living_system` |
| five-section synthesis | `ced.build_section_drafts` / assembly | unchanged | AUTHORITATIVE (execution) | ✅ | `test_blind_assembly`, `test_assembly_coherence` |
| peer scoring (7 dimensions) | `ced.run_registry_shadow_scores` | unchanged | **QUALITY** | ✅ | `test_hybrid_support_h2`, `test_ced_peer_scoring_invariant` |
| section scoring | `ced.score_section_drafts_with_registry` | unchanged | **QUALITY** | ✅ | `test_assembly_reliability` |
| no-self-scoring | `ced._eligible_score_voters` | unchanged | AUTHORITATIVE (execution) | ✅ | `test_ced_peer_scoring_invariant` |
| epistemic leaderboard | `ced.build_epistemic_leaderboard` | unchanged | **QUALITY** | ✅ | `test_registry_council` |
| Council Ratification | `ced.run_council_ratification` | unchanged, reclassified | **ADVISORY** | ✅ | `test_council_ratification`, `test_hybrid_authority_h8` |
| claim-level ratification | *new* | `hybrid_epistemic.ClaimBallot` | AUTHORITATIVE | ➕ new | `test_hybrid_epistemic_h3_h9` CASE 1/5 |
| OpenClaw learning boundaries | `openclaw_memory/` | unchanged | LEARNING | ✅ | `test_learning_*` (14 files) |
| consultation boundaries | `openclaw_consultation/` | unchanged | ADVISORY | ✅ | `test_external_consultation_*` (5 files) |
| Deliberation Tree optionality | `ced._run_deliberation_tree` | unchanged | SEARCH | ✅ | `test_deliberation_tree` |
| Council Live View observer | `orchestrator/ced_live_writer.py` | unchanged | OBSERVER | ✅ | `tests_ced/` |
| provider fail-closed | `provider_registry.run_adapter` | unchanged | AUTHORITATIVE | ✅ | `test_provider_adapters`, `test_live_hardening` |
| exact-model pinning | `openrouter_provider`, `nvidia_nim_provider` | unchanged | AUTHORITATIVE | ✅ | `test_openrouter_provider`, `test_nvidia_nim_provider` |
| receipts | `openclaw_receipts.AtomicReceiptStore`, adapter receipts | unchanged | AUTHORITATIVE | ✅ | `test_micro_socratic_receipts`, `test_external_consultation_receipts` |
| replay | `hybrid_shadow.HybridEpistemicLedger.replay` | extended to H2/H3-H7 kinds | AUTHORITATIVE | ✅ | `test_hybrid_shadow_h1`, `test_hybrid_epistemic_h3_h9` CASE 8 |
| auditability | `FinalResponse.audit_summary` | extended | AUTHORITATIVE | ✅ | preservation gate |
| H1 ledger semantics | `hybrid_shadow.py` | unchanged | AUTHORITATIVE | ✅ | `test_hybrid_shadow_h1` (11) |
| H2 quality/support separation | `hybrid_support.py` | unchanged | OBSERVER | ✅ | `test_hybrid_support_h2` (26) |
| epistemic markers | `reasoning_prompts` | unchanged, contract fixed | ADVISORY | ✅ | `test_marker_contract` (56) |
| legacy epistemic hint (≥7.5) | `ced._epistemic_hint` | retained, labelled | **LEGACY** | ✅ retained | `test_hybrid_support_h2`, `test_hybrid_authority_h8` |
| legacy evidence scoring | `epistemic/evidence_scoring.py` | retained | **LEGACY** | ✅ retained | `tests/test_ced_evidence_layer_v0` |
| EpistemicGraph provenance/lineage | `epistemic_graph/` | retained; superseded by claim lineage | **LEGACY** | ✅ retained | `tests/test_ced_graph_v*` |
| CBE numeric ranking | `epistemic_graph/cbe_engine.py` | retained, not governing | **LEGACY** | ✅ retained | `tests/test_ced_graph_v4_cbe_ranking` |
| contradiction detection | `epistemic_graph/contradiction_engine.py` | proposes candidates only | **LEGACY** | ✅ retained | `test_hybrid_epistemic_h3_h9` CASE 4 |
| argumentation / Dung | `epistemic/argumentation_framework.py` | retained as diagnostics | **LEGACY** | ✅ retained | `tests/test_ced_argumentation_v0` |

## Consolidations

Two old mechanisms are mapped to one new one, and both are named so neither
disappears quietly:

* **`epistemic_graph` contradiction detection** and **CBE ranking** →
  `hybrid_epistemic` contradiction lifecycle and record-based eligibility. The
  graph keeps proposing; selection stops being a numeric contest.
* **`epistemic/evidence_scoring` thresholds** and the **CED quality threshold**
  → `hybrid_epistemic` categorical support. Both retained for comparison; both
  non-governing.

## Nothing deleted

No file, model, engine or prompt directive was removed during H3–H10. Every
authority change is a reclassification in `hybrid_authority.AUTHORITY_MAP`,
which is enforced by import graph in `test_hybrid_authority_h8.py`.

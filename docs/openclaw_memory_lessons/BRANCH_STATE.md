# Branch State — feature/openclaw-memory-lessons-v0

**Canonical name:** `OPENCLAW_MEMORY_LESSONS_BRANCH_STATE`

Honest snapshot of what exists on this branch. Updated when a layer lands.

## Landed layers (each committed with tests, full suite green)

| Layer | Commit | Runtime | Tests |
|---|---|---|---|
| Docs foundation (lessons, prompts, patch policy, goals) | `e61ee45` | — | — |
| Goal 1 — lesson_loader | `20dc8a9` | `openclaw_memory/lesson_loader.py` | 17 |
| Goal 3 — lesson_retriever | `7eed54c` | `openclaw_memory/lesson_retriever.py` | 15 |
| Goal 4 — context_injection | `7cc2298` | `openclaw_memory/context_injection.py` | 13 |
| CED wiring (lessons reach deliberation contexts, opt-in) | `8eb6877` | `ced.py` + `live_providers.py` params | 7 |
| Goal 5 — trace_capture | `adcfc99` | `openclaw_memory/trace_capture.py` | 12 |
| Deliberation Tree Search (AlphaGo search operator) | `704c0dd` | `deliberation_tree.py` + CED opt-in | 19 |
| live_dialogue wiring (env switches, meta-gap closed) | `d2db819` | `scripts/live_dialogue.py` | — |
| Goal 6 — lesson_proposer | `4df5869` | `openclaw_memory/lesson_proposer.py` | 15 |
| AlphaGo distill step (tree → TrainingCorpus pairs) | `33e7453` | `backend/training/corpus.py` | 11 |
| Promotion Arena (generation gating, 0.55 gate) | `e209788` | `backend/training/arena.py` | 11 |
| Goal 13 — Agent Identity Layer (this commit) | see git log | `openclaw_identity/` (3 modules) | 21 |

## Learning arcs currently closed

```text
Lessons arc:
  trace capture → lesson proposer → human review → promote to stable
  → retrieval → context injection → next session

Policy arc (AlphaGo loop):
  drafts (policy) → peer scores (value) → tree search (amplify)
  → distill pairs → TrainingCorpus → LoRA student
  → Promotion Arena gate → human swaps seat

Identity arc (new):
  traces → identity profile (evidence) → soul card (review)
  → version gate (evaluate) → human approval → identity vNext
```

## Standing invariants (all test-locked)

- Agents judge epistemic quality; CED governs the protocol.
- Judging tasks see anonymous outputs only; agents never see scores,
  leaderboards, or the task log.
- Nothing is fabricated: failed scores stay missing; failed expansions and
  failed arena drafts are invalid, never defeats.
- Never-auto-promote, three times over: lessons need a human curator, arena
  verdicts need a human seat swap, identity promotions need a passing gate
  plus a named non-self approver.
- New features are default-off / opt-in; default paths stay byte-for-byte.
- No keys, no network, no `.env` reads anywhere in these layers.

## Not yet built (see FUTURE_GOALS.md)

- Goal 2 (machine-readable lesson store), Goal 7 (prompt registry),
  Goal 8 (prompt patch generator), Goal 9 (Proof Sprint v0.3),
  Goal 10 (local LLM provider), Goal 11 (UI panel), Goal 12 (fine-tuning
  dataset preparation beyond the Phase 22 corpus).
- §6.3 curriculum (OpenQuestionLedger → next questions), §6.4 Evidence
  Harness value grounding.
- Identity persistence (profile registry file), auto-linking proposer
  patterns to known_failures, gate evidence auto-collection.

## Branch status

All commits LOCAL ONLY (not pushed to origin). Full suite green at every
commit listed above.

# Deliberation Tree Search — search as a policy-improvement operator

*The AlphaGo self-improvement loop, mapped onto the CED council and built as a
mechanical, invariant-safe, opt-in layer.*

---

## 1. The study: what AlphaGo's "self-improvement tree" actually is

AlphaGo / AlphaZero's strength does not come from the neural network alone.
It comes from a **closed loop of four operators**:

| # | Operator | AlphaGo mechanism | What it does |
|---|----------|-------------------|--------------|
| 1 | **Propose** (policy) | policy network π(a\|s) | fast intuition: candidate moves |
| 2 | **Evaluate** (value) | value network v(s) | estimates how good a position is |
| 3 | **Search** (amplify) | MCTS guided by π and v | *spends compute to produce a move provably better than the raw policy* |
| 4 | **Distill** (learn) | train π toward MCTS visit counts, v toward game outcome | the amplified behavior is compressed back into the network |

The critical insight is operator 3: **tree search is a policy-improvement
operator**. The output of the search (visit-count distribution) is a strictly
better policy than the raw network. Training on the search output therefore
ratchets capability upward — each generation's search produces the next
generation's training data. Self-play supplies a perfectly matched curriculum,
and the game outcome supplies un-fakeable ground truth for the value network.

## 2. The mapping: AlphaGo → CED

| AlphaGo | CED equivalent | Status before this layer |
|---------|----------------|--------------------------|
| policy network proposes moves | council seats author synthesis drafts | EXISTS (SYNTHESIS phase) |
| value network evaluates | blind peer section-scoring | EXISTS (Phase 8C.2, anonymous, no fabrication) |
| MCTS selectively deepens promising branches | — | **MISSING: deliberation was one-shot.** Drafts were scored once and assembly picked winners; no score-guided revision, no compute allocation to the most promising draft |
| visit counts = improved policy | blind per-section assembly over the candidate pool | EXISTS but static (pool never grew) |
| game outcome z (ground truth) | council ratification (+ Evidence Harness for factual claims) | EXISTS (weaker than win/loss — honest limitation) |
| self-play game records | OpenClaw trace capture (Goal 5) | EXISTS |
| train π on search output | Teacher Loop (Phase 22): SFT + preference pairs from real peer scores | EXISTS, ready to consume tree trajectories |
| generation gating (new must beat old) | — | MISSING (future: arena/benchmark, R2 replay) |
| curriculum from self-play | OpenQuestionLedger (system's own research agenda) | EXISTS, arc not closed yet |

The single missing operator was **search**. This layer adds it.

## 3. The mechanism: `DeliberationTree`

`backend/dialogues/deliberation_tree.py` — a pure, mechanical, fully
unit-testable tree. It performs **zero** LLM calls; CED orchestrates the
calls and feeds results in. The tree only does selection math and bookkeeping.

- **Node** = one synthesis draft (its `draft_id`), with:
  - `own_score` — that draft's real mean peer score (never fabricated;
    `None` when every peer score failed),
  - `visits` / `value_sum` — subtree statistics (mean backup),
  - `expansions` — how many times this node was selected for revision.
- **Roots** = the council's original synthesis drafts.
- **Selection** = UCB1 over *all* nodes (flat frontier):
  `U(n) = Q(n)/10 + c · sqrt( ln(1+T) / (1+expansions(n)) )`
  where `Q(n) = value_sum/visits` (0–10 peer-score scale, normalized) and
  `T` = total expansions so far. Deterministic tie-break by `node_id`.
- **Expansion** = CED issues a `TREE_REVISION` task: a seat receives the
  selected draft's five sections (anonymous — no ids, no author, no scores)
  plus a generic strengthen mandate, and produces a full 5-section revision.
- **Evaluation** = the revision is peer-scored through the *identical* blind
  section-scoring path as every original draft (no-self-scoring preserved).
- **Backup** = the child's real mean score propagates up its ancestor chain.
- **Output** = the revised drafts join `state.section_drafts`; blind assembly
  then runs over the **enriched pool**.

### Honest deviations from AlphaGo (documented, deliberate)

1. **Flat UCB1, not descending PUCT.** With per-session budgets of 1–6
   expansions, descending re-selection adds complexity without measurable
   benefit. Any node (original or revision) is directly selectable.
2. **Assembly stays the decider.** AlphaGo *plays* the search's chosen move.
   Here the tree does not force its best leaf — it enriches the candidate
   pool and blind per-section assembly remains the final, mechanical,
   score-based selector. This preserves every existing assembly invariant
   (coherence margin, runner-up repair, corroboration audit) unchanged.
3. **Real peer scores, not a learned value function.** Q comes from the
   council's actual blind scoring, so the search inherits the council's
   epistemic guarantees (missing stays missing, nothing fabricated).

### The never-worse guarantee

`_section_ranking` is order-independent and pool-monotone: adding candidate
drafts can only raise or preserve each section winner's score (in the default
uniform/no-cohesion mode, with deterministic scores for shared drafts). The
enriched pool is a superset of the original pool, so **a tree-enabled session
can never assemble a lower-scoring section than the same session without the
tree**. The search can only help or do nothing.

### The amplification metric

The audit reports `amplification_gain` = (best revision's own score) − (best
original draft's own score). Positive gain = search genuinely improved on the
one-shot policy — the AlphaGo effect, measured honestly per session. Zero or
negative = the revisions didn't beat the originals; assembly simply ignores
them (never-worse). This is the number that must be positive on live runs to
justify the extra compute.

## 4. Invariant safety

- **Agents judge epistemic quality; CED governs the protocol.** Selection
  (which draft to revise) is protocol governance from CED-owned scores —
  precedented by Phase 19 (repair), 20 (rescue), 21 (seat routing). The
  *revising agent* sees only: the standard SYNTHESIS deliberation context +
  the parent draft's five section texts + a generic mandate. **No scores, no
  tree statistics, no draft ids, no author identities** enter the task context
  (test-locked).
- **No fabrication.** A failed revision produces a task-log entry and an audit
  record — never a fake draft. A revision whose peer scores all fail stays
  unscored (`own_score=None`) and can never become `best_node`.
- **Judging stays anonymous.** Revisions are scored through the same
  anonymous section-scoring tasks; the producer seat is excluded from voting
  on its own revision, exactly as for original drafts.
- **Default off, byte-for-byte.** `tree_expansions=0` (default) leaves every
  existing code path untouched. The audit then reports
  `deliberation_tree: {"enabled": false}`.
- **CED-owned audit, hidden from agents:** nodes, expansion log, selection
  order, per-expansion scores, amplification gain.

## 5. Wiring

```
run_registry_session:
    ... phases ... → build_section_drafts → shadow scores → section scoring
    → [ tree loop: select → TREE_REVISION task → score new draft → backup ]   # opt-in
    → assemble_sections (enriched pool) → ratification → repair → audits
```

- `CEDOrchestrator(tree_expansions=N, tree_exploration=c)` — both opt-in.
- `build_council(tree_expansions=N, tree_exploration=c)` — passthrough.
- `score_section_drafts_with_registry(..., drafts=[new])` — incremental
  scoring of only the new draft (appends scorecards; default path unchanged).
- New `TaskKind.TREE_REVISION` — clean audit identity; the live prompt path
  composes the synthesis content directive + a revision directive; the mock
  provider emits 5-section content for it.

## 6. Closing the full AlphaGo loop

1. **Distill — DONE (v0).** `backend/training/corpus.py::harvest_tree_preferences`
   converts every search trajectory where a revision beat its parent into a
   whole-draft preference pair: chosen = the search-discovered draft, rejected
   = the one-shot draft it improved on, prompt = the SAME question the raw
   policy saw. Margins are recomputed from the session's real scorecards (the
   audit's cached numbers are never trusted), gated by the corpus's own
   `min_margin`. Harvested automatically by `TrainingCorpus.ingest_session`
   at session end whenever the tree ran; `provenance="tree_revision"` and
   `stats()["tree_preference_pairs"]` keep the signal auditable. This is
   operator 4 of §1 made real: *training the base policy on these pairs
   compresses the amplified (search) behavior back into the network* — the
   next generation produces search-quality drafts in one shot, and the search
   then amplifies from a higher base. The LoRA path that consumes the corpus
   (Phase 22 `write_training_script` → student re-enters as a seat) already
   exists; mastery of choosing among lines of thinking is what the pairs
   encode: which revision of which draft the council's own scores endorsed.
2. **Generation gating — DONE (v0).** `backend/training/arena.py::PromotionArena`
   — the candidate seat (e.g. the Phase 22 LoRA student) fights the incumbent
   head-to-head on a fixed benchmark: both draft full five-section answers,
   a judge panel (never the contenders) scores them through the SAME anonymous
   section-scoring contract the council uses, with neutral labels that rotate
   every question (no label ever systematically means "candidate").
   Mechanical verdict: promote ⇔ decided ≥ min_decided AND win_rate ≥ gate
   (default 0.55 — AlphaGo's). Failures are INVALID, never defeats; ties
   decide nothing; insufficient evidence keeps the incumbent (burden of proof
   on the challenger). The arena only reports — a human performs the seat
   swap, the same never-auto-promote symmetry as the OpenClaw lesson
   lifecycle.
3. **Curriculum** — OpenQuestionLedger entries become the next sessions'
   questions: the system searches hardest where its own uncertainty lives.
4. **Value grounding** — Evidence Harness verdicts as the `z` signal for
   factual questions (stronger ground truth than ratification alone).

*OpenClaw remembers. CED governs. Evidence measures. Agents execute —
and now the search amplifies.*

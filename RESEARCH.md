# Socrates AI / CED — Scientific Research Program

**Question.** Does a CED‑governed Socratic dialectic among 4 LLM agents produce
*better* answers than a single LLM?

This document turns that aspiration into a **falsifiable** research program: a
precise hypothesis, an honest reading of the evidence, the mechanisms that could
make it true, the experiments that could prove it **false**, and an
implementation path grounded in this repository.

> **Scientific stance.** "Multi‑agent is better" is **not** self‑evident. The
> literature is mixed, and naïve multi‑agent debate frequently fails to beat a
> *well‑prompted single model at matched compute*. We design the study so it can
> reject our own thesis. The goal is truth, not advocacy.

> *Citations below are recalled from training and must be verified against the
> primary sources before publication (model knowledge cutoff applies).*

---

## 1. Hypotheses (pre‑registered, falsifiable)

Let **B5** = the CED Socratic council, and let baselines be matched on **total
inference compute** (tokens and/or model calls), not on "one call vs many".

- **H1 (the bet).** At matched compute, B5 outperforms the *strongest* single‑model
  baseline on defined task families, by a pre‑registered effect size, with
  external metrics.
- **H0 (null).** No difference at matched compute.
- **H2 (deflation).** Any gain is explained by **ensembling/sampling**, i.e.
  B5 ≈ self‑consistency@k — the *dialectic* adds nothing beyond drawing more
  samples.
- **H3 (cost trap).** Gains exist but vanish under **cost normalization** — B5 is
  Pareto‑dominated on the quality‑vs‑compute frontier by single‑model + CoT +
  self‑consistency / self‑refine.

The program is **designed to be able to accept H0/H2/H3**. If it does, we report
that. A result that "the council ties self‑consistency but is more auditable and
better calibrated" is a *real, publishable* finding — and a more defensible one
than the naïve claim.

---

## 2. Honest reading of the evidence

**Supportive.** Multi‑agent debate can improve factuality/reasoning on some tasks
(Du et al. 2023, *Multiagent Debate*; Liang et al. 2023, *MAD / divergent
thinking*; the "Society of Mind" framing). Self‑critique helps a single model
too (Madaan et al. 2023, *Self‑Refine*; Shinn et al. 2023, *Reflexion*).

**Cautionary — the parts a reviewer will press.**
- **Self‑consistency is the real competitor.** Sampling k chains and voting
  (Wang et al. 2022) is cheap and strong; "More Agents Is All You Need"
  (Li et al. 2024) shows simple sampling‑and‑voting rivals elaborate multi‑agent
  schemes. Many debate gains shrink or vanish when the baseline is single‑model +
  CoT + self‑consistency **at matched compute**, not a single greedy call.
- **Debate can amplify confident errors.** Agents herd and flatter
  (sycophancy: Sharma et al. 2023). Consensus ≠ correctness; a council can
  converge faster on a *wrong* answer.
- **Judging is itself biased.** LLM‑as‑judge has position/verbosity/self‑preference
  biases (Zheng et al. 2023, *Judging LLM‑as‑a‑Judge*). Our "better answer" claim
  is only as good as the adjudication protocol.

**Implication.** The scientific question is **not** "does adding agents help?" It
is: *does this specific Socratic/CED structure beat **both** a strong single model
**and** naïve debate, at matched compute, on the tasks where dialectic should
matter — and where does it not?*

---

## 3. Mechanisms — why CED *might* beat naïve debate (each is testable)

Each mechanism already exists in the codebase and maps to an ablation (§7).

| ID | Mechanism (code) | Predicted effect | How it differs from naïve debate |
|----|------------------|------------------|----------------------------------|
| **M1** | **Elenchus** adversarial critique phase | Surfaces hidden errors; counters agreement bias | Debate is often cooperative; elenchus is structurally adversarial |
| **M2** | **Blind peer scoring, no self‑scoring** (`MicroScore`, voter≠author) | Reduces authority/herding bias in selection | Debate lets a loud/confident agent dominate |
| **M3** | **No‑fabrication + quorum + council ratification** | Better **calibration / selective prediction**; blocks confident‑wrong consensus | Debate forces an answer even when the panel shouldn't |
| **M4** | **Deterministic role rotation / diversity** | Wider solution coverage | Homogeneous agents collapse to one mode |
| **M5** | **Blind per‑section assembly** | Decorrelates errors across sub‑answers | Single‑draft debate correlates all errors |

**Core scientific bet:** M3 (and M2) are the *distinctive* levers. The council's
likeliest real edge is **knowing when it doesn't know** and **not fabricating
consensus** — i.e. *calibration and auditability*, not necessarily raw accuracy.

---

## 4. The central methodological risk: circularity (already named in‑repo)

`backend/evaluation/README.md` honestly states that two metrics use *CED's own
Socratic scorer as the yardstick* → circular; "does not prove CED is better." The
program's first job is to **break the circularity** with **external ground truth**:

1. **Verifiable tasks** with objective answers (no LLM judge needed).
2. **Reference/rubric** tasks scored against gold annotations.
3. **Blind human + multi‑family LLM** adjudication for contested tasks, with bias
   controls and inter‑rater agreement.

No claim of superiority may rest on CED scoring CED.

---

## 5. Task taxonomy (where dialectic should and should not help)

| Tier | Nature | Datasets (examples) | Metric | Prior |
|------|--------|---------------------|--------|-------|
| **A** | Verifiable | GSM8K, MATH, MMLU‑Pro, GPQA, FEVER, TruthfulQA | Exact accuracy, ECE | Dialectic helps most on **hard, multi‑step** A; adds only cost on **easy recall** A |
| **B** | Adjudicable vs reference | Legal/medical reasoning w/ reference answers; long‑form QA w/ gold rubrics | Rubric score, pairwise pref | Plausible gains via error‑correction |
| **C** | Contested / normative | Ethics, policy, strategy (no single truth) | Argument coverage, steelman quality, blind human preference | **Best case for CED** — value is *coverage + surfaced blind spots*, not one correct token |

**Prediction:** B5 gains are **largest on C and hard‑A**, **smallest/negative on
easy‑A**. A result that contradicts this is informative either way.

---

## 6. Baselines — the crux (must be strong, matched compute)

Comparing a council against a *single greedy call* is the #1 way this research
goes wrong. Required ladder:

- **B0** single greedy *(floor only)*
- **B1** single + Chain‑of‑Thought
- **B2** **self‑consistency@k** (sample k, majority/agg) — *the real competitor*
- **B3** **self‑refine / Reflexion** (single model critiques & revises itself)
- **B4** **naïve multi‑agent debate** (no CED governance, no peer scoring, no ratification)
- **B5** **CED Socratic council** (the system)
- **B6** **CED ablations** (remove M1…M5 one at a time)

**Compute matching.** Equalize total tokens / API calls across B2–B5 so we measure
**structure, not budget**. Primary result is a **quality‑vs‑compute Pareto curve**,
not a single number. "B5 wins at 8× the cost" is **not** a win — it must beat the
frontier traced by B2/B3 at the *same* compute.

---

## 7. Ablation matrix (isolate each mechanism)

| Ablation | Toggle (existing / to add) | Predicted result if mechanism matters |
|----------|----------------------------|----------------------------------------|
| − Elenchus (M1) | add `enable_elenchus` flag | accuracy ↓ on hard‑A, blind‑spot coverage ↓ on C |
| − Peer scoring (M2) | `shadow_scoring_mode = off` (exists) | selection quality ↓, herding ↑ |
| − Ratification/quorum (M3) | `final_synthesis_mode` / quorum flags (exist) | calibration ↓ (ECE ↑), confident‑wrong ↑ |
| − Role diversity (M4) | freeze roles / clone agents | coverage ↓, diversity metric ↓ |
| − Blind assembly (M5) | single‑draft mode | error correlation ↑ |

If removing a mechanism does **not** hurt, that mechanism is **not earning its
cost** — and we should say so.

---

## 8. Metrics & statistics

- **Quality:** accuracy/EM (A); rubric + blind pairwise preference (B/C).
- **Calibration:** **ECE**, selective accuracy / risk‑coverage (does M3 make the
  council *abstain well*?). *This is the metric most likely to favor CED.*
- **Cost‑normalized quality:** quality per 1k tokens / per call; report Pareto.
- **Error‑correction dynamics:** rate of wrong→right flips (benefit) vs right→wrong
  flips (herding harm).
- **Herding/sycophancy rate;** **diversity** of intermediate positions.
- **Adjudication protocol:** blind, randomized order, ≥2 LLM judges of *different
  families* + human spot‑checks, position‑bias controls, inter‑rater agreement.
- **Stats:** pre‑register hypotheses & analysis; paired tests on shared items;
  bootstrap CIs; multiple‑comparison correction; report **effect sizes**, not just
  p‑values; power analysis to fix sample sizes.

---

## 9. Falsification & honest failure modes

We declare **H1 false** if, at matched compute, B5 is ≤ B2/B3 on Tier‑A **and**
not preferred on Tier‑C **and** not better‑calibrated. Watch for:

- **Herding** (consensus on confident‑wrong) — measured by right→wrong flip rate.
- **Cost/latency** — a full 6‑phase council per query may be 10–40× a single call.
- **Judge bias** — controlled, never single‑judge, never CED‑judges‑CED.
- **Domain overfit** — FakeProvider/topic heuristics skew toward epistemology;
  real eval must span all tiers, not philosophy alone.

**When NOT to use CED (state it plainly):** easy factual recall, latency‑critical,
or tight cost budgets — there a single model + CoT/self‑consistency likely wins.

---

## 10. The most likely *real* contribution (reframing the thesis)

The naïve claim ("better answers, period") will probably **fail on easy
benchmarks at matched compute.** The defensible, distinctive contributions of this
architecture are:

1. **Calibration / selective prediction** — the no‑fabrication + quorum +
   ratification design is literally built to *withhold* rather than guess. If it
   yields lower ECE and better risk‑coverage than single‑model + self‑consistency,
   that is a genuine, useful result for high‑stakes use.
2. **Contested / multi‑perspective questions (Tier C)** — where "better" means
   *coverage, steelmanning, surfaced blind spots*, the council should win on blind
   human preference.
3. **Auditability** — the epistemic trace (roles, peer scores, ratification,
   honest "unresolved") is a **process guarantee** valuable in law/medicine even
   when raw accuracy ties.

> **Reframed thesis (defensible & testable):** *At a stated compute premium, the
> CED Socratic council produces answers that are **better‑calibrated**,
> **better on contested/multi‑perspective questions**, and **auditable**, while
> being **no worse** than a strong single‑model baseline on verifiable tasks.*

That is a Stanford‑grade claim: bold, mechanistic, and **falsifiable**.

---

## 11. Implementation roadmap (grounded in this repo)

Reuse `backend/evaluation/` (`harness.py`, `metrics.py`, `benchmark_cases.py`) and
the Phase 9A/9B real‑provider seam (`offline_provider_adapter.py` →
`live_smoke_provider.py`).

- **R1 — Break circularity. ✅ DONE** (`baseline_harness.py`): external verifiers
  (no LLM judge), oracle/self‑consistency baselines, the council wired in, instrument
  validated offline. Ground truth in `backend/evaluation/data/verifiable_v0.json`.
- **R2 — Record once, replay deterministically. ✅ DONE (offline‑first)**
  (`record_replay.py`): `RecordingAnswerer` captures each answerer's outputs once
  (live only when YOU run it gated); `ReplayAnswerer` re‑scores offline forever,
  reproducing the matched‑compute comparison with no network/cost. Phase 11
  (`live_providers.build_council`) supplies the real council when gated. **Next:**
  record a real run (gated) and replay the council vs single‑model vs self‑consistency
  Pareto on a small hard‑A set — no live conclusions until that recording exists.
- **R3a — Dialectic Delta instrument. ✅ DONE (offline‑first)**
  (`dialectic_delta.py`): measures whether the dialogue ITSELF improves answers —
  initial responses vs final synthesis on external truth, with the §8
  error‑correction dynamics (corrected / degraded / net_gain) and a conservative
  ANY‑correct initial convention. The context‑flow fix (critiques now reach the
  synthesis; the Socratic question reaches every phase) is what this instrument
  will test on real models.
- **R3 — Ablations.** Add the missing toggles (`enable_elenchus`, quorum knobs);
  run B6. Attribute every gain to a mechanism (M1–M5).
- **R4 — Calibration study.** ECE + risk‑coverage across baselines. *Test the core
  bet (M3).* Likely the headline result.
- **R5 — Contested‑task human study (Tier C).** Blind pairwise preference with
  bias controls and inter‑rater agreement.
- **R6 — Report.** Reproducible benchmark + paper‑style writeup with **honest
  negative results** where they occur.

**Multi‑turn note (Phase 8D).** The chat continuity layer enables a further study:
does Socratic *dialogue over turns* (challenge → revise) improve answers vs a
single‑turn council? Continuity is carried by the sanitized public brief, so this
is measurable without confounding hidden state.

---

## 12. Threats to validity (kept visible)

- **Circularity** (CED scoring CED) — mitigated by §4 external ground truth.
- **Judge bias** — multi‑family judges + human spot‑checks + blinding.
- **Compute confound** — matched‑compute Pareto, never "more calls = better".
- **Cherry‑picking** — pre‑registration; report all tiers and ablations, including
  losses.
- **Mock→real gap** — FakeProvider is template‑deterministic; *no scientific claim
  may be drawn from mock runs.* All headline claims require real models.

---

### One‑line summary

> We will test — and try hard to **falsify** — the claim that CED‑governed Socratic
> dialectic beats a strong single model at matched compute. The honest expected
> win is **calibration, contested‑question quality, and auditability**, not raw
> accuracy on easy benchmarks — and that is a result worth proving rigorously.

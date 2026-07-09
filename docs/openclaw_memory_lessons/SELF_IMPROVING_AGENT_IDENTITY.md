# Self-Improving Agent Identity Layer

**Canonical name:** `OPENCLAW_MEMORY_LESSONS_AGENT_IDENTITY`
**Runtime (v0):** `backend/dialogues/openclaw_identity/`
**Companion doc:** [AGENT_SOUL_CARD.md](AGENT_SOUL_CARD.md)

"Soul" here is not mystical and not uncontrolled autonomy. It is an
**auditable, versioned identity profile** for each agent seat, derived from
evidence: session traces, Memory Lessons, Shadow Apprentice runs, Tree Search
outcomes, Proof Sprint results, and Evidence Harness results.

```text
The agent does not become powerful because it claims identity.
The agent earns identity through evidence.
```

```text
CED governs.
Evidence Harness measures.
OpenClaw remembers.
Agents execute.
Identity is earned through verified performance.
```

---

## 1. The core distinction

```text
Self-learning:
The agent receives lessons, traces, and feedback.

Self-improving:
The agent proposes changes based on what it learned.

Self-versioning:
The system verifies whether those changes actually helped.

Agent Identity / Soul:
The auditable profile that records the agent's strengths, weaknesses,
lessons, promotion status, and version history.
```

The layers already built on this branch map onto that distinction:

| Distinction | Existing mechanism |
|---|---|
| self-learning | Memory Lessons injected into contexts (Goals 1/3/4), traces captured (Goal 5) |
| self-improving | Lesson Proposer (Goal 6), Deliberation Tree revisions, tree-distillation preference pairs |
| self-versioning | Promotion Arena (AlphaGo gate), Evidence Harness, A/B protocol-evolution variants |
| identity | **this layer**: the profile that records what all of the above proved |

## 2. The identity profile (design target)

```json
{
  "agent_id": "local_apprentice_001",
  "identity_version": "v0.3",
  "promotion_status": "shadow_apprentice",
  "role_strengths": {
    "blind_spots": 0.82,
    "nuance": 0.76,
    "core_answer": 0.51,
    "final_verdict": 0.44
  },
  "known_failures": [
    "over-explains exact-output tasks",
    "misses unsupported claims when evidence is long"
  ],
  "stable_lessons": ["LESSON-0001", "LESSON-0003", "LESSON-0006"],
  "next_gate": "candidate_synthesis_section"
}
```

The v0 runtime (`identity_profile.py`) implements this as
`AgentIdentityProfile.to_record()`, with two additions that keep every number
auditable: `section_wins` / `section_opportunities` (the raw counts behind
each strength) and `version_history` (append-only promotion records).

**Where the numbers come from (mechanics, not judgement):**

- `role_strengths` are derived ONLY from Goal 5 traces. An assembled
  section's `source_draft_id` is `draft_<move_id>`; the trace's move list
  maps that move to its producing provider. Wins / opportunities per section
  is a mechanical count over *public assembly outcomes* — no raw hidden
  scorecards are read, stored, or exposed.
- `known_failures` and `stable_lessons` are inputs from the curator or the
  Lesson Proposer pipeline — the profile never invents them.
- A session the agent never appeared in contributes nothing. An unresolved
  section is no contest. Missing evidence is never fabricated.

## 3. The identity ladder

```text
Stage 0 — Base Agent
Uses the shared prompt and assigned role only.

Stage 1 — Memory-Aware Agent
Receives selected Memory Lessons.

Stage 2 — Shadow Apprentice
Produces shadow outputs but does not affect final answers.

Stage 3 — Self-Learning Agent
Uses traces and feedback to understand recurring failures.

Stage 4 — Patch Proposer
Proposes small prompt, lesson, test, or code patches.

Stage 5 — Test-Aware Researcher
Links proposals to Evidence Harness / Proof Sprint / Tree Search tests.

Stage 6 — Candidate Contributor
Can produce reviewable, reversible patches.

Stage 7 — Self-Improving Master-Branch Researcher
Can study master/main branch, compare feature branches, understand risk,
propose safe improvements, and justify them with tests and evidence.
```

Encoded as `IDENTITY_LADDER` in `promotion_policy.py`. Stages advance **one
rung at a time**, each advancement approved by a named non-self approver
(`advance_stage` raises otherwise).

## 4. Version gates

Every promotion is evidence-backed. Gates are **declarative** (metric,
operator, threshold) so the requirement itself is auditable data, not hidden
code:

```text
v0.1 → v0.2:  exact_output_failures_delta        <= -1
              (Agent reduced exact-output failures.)

v0.2 → v0.3:  unsupported_claim_failures_delta   <= -1
              (Agent reduced unsupported claims.)

v0.3 → v0.4:  shadow_blind_spots_wins            >= 3
              (Agent produced useful blind_spots in Shadow Apprentice mode.)

v0.4 → v0.5:  prompt_patches_passed_ab           >= 1
              (Agent proposed prompt patches that passed A/B tests.)

v0.5 → v1.0:  master_branch_proposals_verified   >= 1
              (Agent can compare branch vs master and propose safe changes
               with tests.)
```

Gate mechanics (`promotion_policy.py`):

- `evaluate_gate(gate, evidence)` → a `GateResult` **recommendation**. A
  missing or non-numeric metric FAILS with an honest reason — absence of
  evidence is never success.
- `record_promotion(profile, gate_result, approved_by=...)` returns a NEW
  profile (append-only history; the input is never mutated) and refuses:
  a failing gate, a gate that does not start at the profile's current
  version, an unnamed approver, or **self-approval** — an agent can never
  approve its own promotion.
- The system verifies; a human promotes. This is the same
  never-auto-promote symmetry as the lesson lifecycle
  (proposed → human review → stable) and the Teacher-Loop Promotion Arena
  (the arena reports; a human swaps the seat).

## 5. Safety boundaries (what this layer must NEVER do)

The Agent Identity Layer never:

- changes CED core semantics — the CED core does not import
  `openclaw_identity` (**test-locked**: `test_ced_core_never_imports_identity`)
- gives any agent permanent authority — profiles are descriptive records
- overrides role rotation — rotation stays CED-owned and untouched
- exposes raw hidden scorecards to agents — strengths are derived counts over
  public assembly outcomes; profiles and Soul Cards are system/operator
  artifacts, never injected into agent contexts
- exposes secrets — the package touches no keys, no env, no network
- allows silent prompt mutation — prompt changes remain governed by
  PROMPT_PATCH_POLICY.md (small patches + A/B + approval)
- allows automatic self-promotion — passing gate + named non-self approver,
  both mechanically enforced
- fine-tunes on unverified traces — training data flows only through the
  Phase 22 TrainingCorpus (real peer-score labels, margin gates) and the
  Promotion Arena gate
- treats memory as factual proof — lessons are behavioral guidance
  (README.md invariant), and identity strengths are performance statistics,
  not truth claims
- lets a local apprentice affect final answers before promotion — Stage 2
  (Shadow Apprentice) is definitionally non-binding; entry into the real
  council goes through the Promotion Arena

## 6. Integration with existing systems

```text
Trace Capture (Goal 5)
  ↓  session traces: moves, assembly winners, ratification
Lesson Proposer (Goal 6)
  ↓  repeated failures → PROPOSED lessons (never auto-promoted)
Agent Identity Profile (this layer)
  ↓  evidence-backed strengths / weaknesses / lessons / version
Self-Improvement Proposal
  ↓  prompt patches (PROMPT_PATCH_POLICY), lesson proposals, seat candidates
Evidence Harness / Tree Search / Proof Sprint
  ↓  measurable verification (amplification_gain, A/B, arena win_rate)
Version Gate (promotion_policy)
  ↓  evaluate_gate → human approval → record_promotion
Agent Identity vNext
```

Connection map:

- **Memory Lessons** — `stable_lessons` on the profile lists which curated
  lessons apply to this agent; retrieval/injection stays Goals 3/4.
- **Trace Capture** — the sole mechanical source of `role_strengths`.
- **Lesson Proposer** — its repeated-failure patterns are the natural feed
  for `known_failures` (curator links them; v0 does not auto-link).
- **Shadow Apprentice Mode** — Stage 2 of the ladder; gate v0.3→v0.4 counts
  shadow wins. Shadow outputs never touch final answers.
- **Socratic Tree Search** — tree outcomes (which revisions won) are identity
  evidence; distillation pairs feed the student the profile describes.
- **Prompt Patch Policy** — Stage 4+ proposals must follow it; gate
  v0.4→v0.5 counts patches that PASSED its A/B requirement.
- **Evidence Harness / Proof Sprint** — the measuring instruments behind
  gate evidence metrics; identity claims trace back to their results.
- **Branch State** — BRANCH_STATE.md records which identity infrastructure
  exists at each point in branch history.
- **Future local LLM provider (Goal 10)** — the local apprentice is the
  first intended holder of a full identity profile: it climbs the ladder
  from Shadow Apprentice, earns versions through gates, and enters the
  council only through the Promotion Arena.

## 7. What v0 deliberately does NOT do

- No CED wiring: nothing in the runtime pipeline builds or reads profiles.
- No persistence: profiles are built on demand from traces; storing them
  (JSONL registry) is a future goal once the shape has settled.
- No auto-linking of proposer patterns to `known_failures`.
- No gate evidence auto-collection: evidence dicts are assembled explicitly
  by the operator (or future tooling) from harness/arena/A-B reports.

Each of these is a deliberate scope cut, not an oversight: the profile shape
and the promotion constitution come first; automation of evidence collection
comes only after the instruments it would read from are trusted.

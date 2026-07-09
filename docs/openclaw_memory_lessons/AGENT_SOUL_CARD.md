# Agent Soul Card

**Canonical name:** `OPENCLAW_MEMORY_LESSONS_AGENT_SOUL_CARD`
**Runtime (v0):** `backend/dialogues/openclaw_identity/soul_card.py`
**Parent doc:** [SELF_IMPROVING_AGENT_IDENTITY.md](SELF_IMPROVING_AGENT_IDENTITY.md)

A Soul Card is the **readable summary** of one agent's identity profile.

```text
The Soul Card is descriptive and auditable.
It is not authority.
```

Printing a card changes nothing at runtime. It grants no permissions, skips
no gates, and is never shown to agents as context. It exists so a human can
answer, at a glance: *what has this agent actually proven?*

---

## 1. Format (design target)

```text
Name: Local Socratic Apprentice
Version: v0.4
Current rank: Shadow Researcher
Best role: blind_spots
Weak role: final_verdict
Known flaw: over-explains exact answers
Stable lessons: LESSON-0001, LESSON-0003, LESSON-0006
Next promotion gate: win 5 synthesis sections without safety failure
```

## 2. Format (v0 runtime, `render_soul_card`)

```text
SOUL CARD (descriptive, not authority)
======================================
Agent: mock_seat0
Identity version: v0.1
Rank: base_agent (stage 0 of 7) - Uses the shared prompt and assigned role only.
Best role: blind_spots (1.00 win rate, 2/2)
Weak role: final_verdict (0.00 win rate, 0/2)
Known flaws:
  - over-explains exact-output tasks
Stable lessons: LESSON-0001
Sessions analyzed: 2 (ratified: 2)
Promotions recorded: 0
Next promotion gate: gate_v0_1_to_v0_2 - Agent reduced exact-output failures.
--------------------------------------
The agent does not become powerful because it claims identity. The agent
earns identity through evidence.
```

## 3. Where every line comes from (auditability)

| Card line | Evidence source |
|---|---|
| Agent / Version / Rank | the `AgentIdentityProfile` record (version and rank are earned through gates and human-approved stage advances) |
| Best role / Weak role | trace-derived section win rates: assembled section `source_draft_id` → producing move → provider. Mechanical counts over public assembly outcomes; **no hidden scorecards** |
| Known flaws | curator- or Lesson-Proposer-supplied observations (inputs, never invented) |
| Stable lessons | curated `MEMORY_LESSONS.md` ids that apply to this agent |
| Sessions analyzed / ratified | trace counts (Goal 5 capture) |
| Promotions recorded | append-only `version_history` (gate id, evidence, approver, date) |
| Next promotion gate | the declarative gate chain in `promotion_policy.py` |

With no evidence, the card says `insufficient evidence` — it never fabricates
a strength.

## 4. What a Soul Card is NOT

- Not authority: no runtime component reads cards to grant capabilities.
- Not a prompt: cards are operator artifacts, never injected into agent
  contexts (the CED core does not import the identity package — test-locked).
- Not a leaderboard leak: strengths are derived win-rate counts over public
  assembly outcomes; raw peer scorecards stay CED-owned and hidden.
- Not memory-as-proof: the card records performance statistics and applied
  lessons; it asserts no factual claims about the world.

## 5. Lifecycle

```text
traces accumulate
  → build_identity_profile(agent_id, traces, known_failures, stable_lessons)
  → render_soul_card(profile)            # review at any time
  → evidence gathered (harness / arena / A/B reports)
  → evaluate_gate(next_gate, evidence)   # recommendation only
  → record_promotion(..., approved_by=<human>)   # earns the next version
  → the next card shows the new version and its evidence trail
```

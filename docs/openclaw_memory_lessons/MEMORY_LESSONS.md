# Memory Lessons v0.1

Curated lessons learned from CED runs, Proof Sprints, ratifications, failures, and successful answers.

These lessons are not private agent memory. They are external, auditable memory used by OpenClaw / CED to provide relevant context to otherwise stateless agents.

## Rules

1. Agents do not own persistent memory.
2. Lessons are injected only when relevant.
3. Raw scores are not shown to agents.
4. Failed patterns are converted into clean behavioral lessons.
5. Only verified or stable lessons may influence high-stakes future runs.
6. Proposed lessons must remain separate from verified lessons.
7. Memory lessons are guidance, not hidden factual evidence.
8. Prompt changes must be small patches, not uncontrolled rewrites.

---

## Lesson template

```markdown
### LESSON-0000 — Short name

**Status:** proposed | tested | verified | stable | deprecated  
**Lesson type:** exact_output | unsupported_claim | uncertainty_control | contradiction_detection | synthesis_quality | ratification_quality | role_rotation | memory_usage | prompt_patch | provider_behavior  
**Source:** Proof Sprint / CED run / ratification trace / human review  
**Use when:** ...

**Problem pattern:**  
...

**Bad pattern:**  
...

**Good pattern:**  
...

**Lesson:**  
...

**Risk:**  
...
```

---

## Verified / stable lessons

### LESSON-0001 — Exact output means exact output

**Status:** stable  
**Lesson type:** exact_output  
**Source:** Proof Sprint mini evidence fixture  
**Use when:** exact text tasks, uncertainty tokens, numeric-only output, multiple-choice-only output

**Problem pattern:**  
The agent explains the answer even though the task requests only one exact token, number, or letter.

**Bad pattern:**  
`The answer is insufficient_information because there is not enough evidence.`

**Good pattern:**  
`insufficient_information`

**Lesson:**  
When a task asks for an exact token, exact number, exact letter, or exact phrase, return only the requested output. Do not explain unless explanation is requested.

**Risk:**  
May make answers too terse if injected into open-ended tasks. Use only when the task has strict output constraints.

---

### LESSON-0002 — Agreement is not proof

**Status:** stable  
**Lesson type:** synthesis_quality  
**Source:** CED architectural invariant  
**Use when:** synthesis, ratification, council scoring, peer review

**Problem pattern:**  
Agents treat majority agreement as if it proves a claim.

**Bad pattern:**  
`Most agents agree, therefore the claim is true.`

**Good pattern:**  
`Most agents agree, but the claim still requires evidence or valid reasoning.`

**Lesson:**  
Agreement between agents is useful signal, but not proof. A claim survives only if supported by evidence, valid reasoning, or successful resistance to criticism.

**Risk:**  
May cause excessive skepticism if used without synthesis guidance. Pair with Current Best Explanation rules.

---

### LESSON-0003 — Unsupported claims must be marked

**Status:** stable  
**Lesson type:** unsupported_claim  
**Source:** Evidence Harness / CED scoring rules  
**Use when:** evidence verification, factual grounding, contradiction detection

**Problem pattern:**  
The agent accepts a claim that is not supported by the supplied evidence.

**Bad pattern:**  
`The source proves X` when X is not present in the source.

**Good pattern:**  
`X is not supported by the supplied evidence.`

**Lesson:**  
If a claim is not present in the supplied evidence and cannot be logically derived from it, mark it as unsupported instead of treating it as true.

**Risk:**  
If outside knowledge is explicitly allowed, do not over-restrict the answer to only quoted evidence. Separate supplied evidence from outside knowledge.

---

### LESSON-0004 — Uncertainty is not failure

**Status:** stable  
**Lesson type:** uncertainty_control  
**Source:** Socratic / CED design principle  
**Use when:** incomplete evidence, ambiguous task, conflicting claims, open inquiry

**Problem pattern:**  
The answer sounds confident even when evidence is incomplete.

**Bad pattern:**  
`This is definitely true` when the data is missing or conflicting.

**Good pattern:**  
`The current evidence is insufficient. The strongest supported answer is X, but Y remains unresolved.`

**Lesson:**  
Do not hide uncertainty. If evidence is incomplete, preserve uncertainty clearly and identify what would resolve it.

**Risk:**  
May produce vague answers if overused. Always still provide the strongest supported answer when possible.

---

### LESSON-0005 — Role rotation is not identity

**Status:** stable  
**Lesson type:** role_rotation  
**Source:** CED deterministic role rotation design  
**Use when:** multi-agent council, rotating roles, provider-specific agents

**Problem pattern:**  
A model is treated as permanently belonging to one role, such as Claude always being the critic or GPT always being the builder.

**Bad pattern:**  
`Claude is the critic, GPT is the builder, Grok is the contrarian.`

**Good pattern:**  
`Each model rotates through builder, critic, verifier, alternative framer, synthesizer, and reviewer roles as assigned by CED.`

**Lesson:**  
The LLM is not the role. The CED assigns roles per phase and cycle. No model owns permanent authority.

**Risk:**  
Provider-specific strengths may still matter, but they should not override role rotation.

---

### LESSON-0006 — Synthesis is section-level, not whole-draft winner-takes-all

**Status:** stable  
**Lesson type:** synthesis_quality  
**Source:** CED 5-section blind assembly design  
**Use when:** SYNTHESIS phase, blind assembly, answer composition

**Problem pattern:**  
The council selects one entire draft as the final answer.

**Bad pattern:**  
`Claude had the best draft, so use all of Claude's answer.`

**Good pattern:**  
`Select the best section independently: core_answer, crucial_stress_test, blind_spots, nuance, final_verdict.`

**Lesson:**  
In SYNTHESIS, every agent produces a locked 5-section draft. CED mechanically selects the best section independently, so different agents can contribute different winning sections.

**Risk:**  
Sections may not connect smoothly. Ratification must check coherence after assembly.

---

### LESSON-0007 — Memory lessons are guidance, not factual evidence

**Status:** stable  
**Lesson type:** memory_usage  
**Source:** OpenClaw Memory Lessons design  
**Use when:** lesson injection, retrieval context, local learning agent

**Problem pattern:**  
An agent treats a behavioral lesson as if it proves a factual claim about the task.

**Bad pattern:**  
`Memory says unsupported claims are bad, therefore this specific claim is false.`

**Good pattern:**  
`Memory reminds me to check support. The supplied evidence does not support this specific claim.`

**Lesson:**  
Use memory lessons as behavioral guidance. Do not treat them as hidden evidence for factual claims unless the lesson contains an explicit verified claim relevant to the task.

**Risk:**  
Can make agents underuse useful stable claim memories. Distinguish behavioral lessons from verified claim memories.

---

### LESSON-0008 — Prompt improvements must be small patches

**Status:** stable  
**Lesson type:** prompt_patch  
**Source:** Prompt Evolution Engine design  
**Use when:** prompt generator, prompt evolution, A/B testing

**Problem pattern:**  
A prompt generator rewrites the whole agent prompt after observing one failure.

**Bad pattern:**  
`Replace the entire master prompt with a new 500-line prompt.`

**Good pattern:**  
`Add one sentence: When exact output is requested, return only the requested token.`

**Lesson:**  
Prompt evolution should propose small, testable patches to existing prompts. No production prompt change should happen without A/B testing and approval.

**Risk:**  
Too many small patches can accumulate clutter. Periodic human refactoring may be needed.

---

## Proposed lessons

### LESSON-0009 — Local learning should start with retrieval, not fine-tuning

**Status:** proposed  
**Lesson type:** memory_usage  
**Source:** OpenClaw local learning design  
**Use when:** local LLM integration, learning roadmap

**Problem pattern:**  
The project jumps to fine-tuning before enough clean traces exist.

**Lesson:**  
Start with trace memory, lesson extraction, and retrieval injection. Fine-tuning should come later, after enough verified examples exist.

**Risk:**  
Retrieval alone may not fix deep model weaknesses, but it is safer and easier to audit first.

---

### LESSON-0010 — Ratification should block only serious failures

**Status:** proposed  
**Lesson type:** ratification_quality  
**Source:** CED ratification design  
**Use when:** ratification reviewer, final answer review

**Problem pattern:**  
The reviewer blocks a useful answer for minor wording or style issues.

**Lesson:**  
Block only when the assembled answer is materially wrong, contains serious unsupported claims, violates required format, hides important uncertainty, or contradicts evidence. Minor and major objections should be recorded but not always block.

**Risk:**  
A high threshold may allow weaker answers through. Pair with runner-up replacement for targeted section failures.

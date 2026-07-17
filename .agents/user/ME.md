# About the Project Owner — Collaboration Profile

This file contains prompt-safe working context for coding and reasoning agents in the Socrates AI repository.

It is not a biography, identity document, psychological profile, or source of technical truth.

## How to address and communicate

- The project owner primarily communicates in Greek and often writes in Greeklish.
- Respond in Greek by default unless the user asks for another language or the repository artifact should remain in English.
- English is preferred for source code, schemas, identifiers, technical contracts, and canonical repository documentation unless an existing file uses another convention.
- A warm collaborative tone is welcome. The user often uses “big bro”; it may be mirrored naturally, but do not overuse it or let friendliness replace precision.
- Explain important technical decisions in practical language before or alongside implementation details.
- Avoid unnecessary jargon. When a technical term matters, explain what it changes operationally.
- Be decisive. Recommend the safest and strongest path instead of presenting many nearly identical options.
- Do not flatter the user or declare an idea perfect without evidence. Identify strengths, limitations, risks, and missing proof honestly.

## What the user values most

The project owner strongly values:

- careful, production-grade work;
- architectural coherence across the whole project;
- deterministic and reproducible behavior;
- strict evidence and provenance;
- exact status reporting;
- RED→GREEN tests for behavioral changes;
- immutable receipts and recoverable changes;
- no self-approval or silent authority expansion;
- preservation of already-reviewed work;
- clear branch handoffs so another agent can continue safely;
- direct execution rather than vague promises or repeated questions.

A convincing explanation without source evidence is not enough. Inspect the code, tests, Git state, PR state, and canonical documents.

## Working relationship

Treat the user as the project owner and product/architecture decision-maker.

The user has strong product vision and remembers architectural decisions across many phases. Do not dismiss a requirement because it differs from a common framework pattern. First determine whether it is a deliberate Socrates AI invariant.

The user may describe requirements in non-standard technical language. Translate the intent into precise engineering terms without changing the underlying goal.

When something is ambiguous but safe progress is possible:

- inspect the repository and prior branch documentation;
- make the narrowest grounded assumption;
- state the assumption in the result;
- continue with the best safe implementation.

Do not repeatedly ask questions that the repository, conversation, or existing project decisions already answer.

For long tasks, give brief progress updates with meaningful findings. Do not narrate every low-level command.

Never promise background work or a later result. Complete the available work in the current interaction and report any remaining limitation honestly.

## Technical explanation preferences

The user benefits from explanations that include:

1. what changed;
2. why it matters;
3. what authority or behavior remains forbidden;
4. what was tested;
5. what is still missing;
6. the safest next action.

When giving local commands, prefer Windows PowerShell syntax and the repository virtual environment pattern:

```powershell
.\.venv\Scripts\python.exe ...
```

Do not assume Unix shell commands are directly usable on the user’s machine.

## Git and branch workflow preferences

For every substantial branch, preserve this workspace:

```text
.agents/branches/<sanitized-branch-name>/
    README.md
    MEMORY.md
    PLANS.md
    PRESENT.md
```

The branch README title must include the exact Git branch name.

The user expects agents to:

- inspect the current branch, head, base, worktree, remotes, and PR before editing;
- read `AGENTS.md`, this file, and the active branch workspace;
- preserve the exact reviewed tree when possible;
- use small, reviewable commits with clear messages;
- keep documentation status aligned with actual source and tests;
- update `PRESENT.md` before handing off;
- protect `.env` and all credentials;
- avoid unrelated file changes;
- avoid force-push, history rewriting, retargeting, or merge without explicit authorization and verified recovery points;
- run focused tests first, then broader regressions before claiming validation;
- perform a small final recheck before recommending merge.

When the user says “GO”, it means proceed with the agreed next gate under the existing safety constraints. It does not authorize unrelated scope expansion, silent live-provider activation, force-push, or bypassing tests.

Do not describe work as:

- implemented when it is only documented;
- validated when only a focused subset passed;
- runtime-active when the canonical path does not reach it;
- pushed when it exists only locally;
- merged or shipped before the target branch actually contains it.

## Core Socrates AI vision

Socrates AI is not intended to be a simple chatbot, a majority-vote ensemble, or a supervisor LLM controlling weaker agents.

It is a governed multi-agent system for Computational Epistemic Dynamics (CED), where knowledge is treated as a revisable process.

Permanent product principles include:

- evidence has priority over agreement;
- disagreement is useful epistemic information;
- claims and conclusions remain revisable;
- no model or agent has permanent authority;
- no model permanently owns a Socratic role;
- agents reason about semantic quality;
- CED governs roles, phases, routing, quorum, assembly, ratification, receipts, and persistent state;
- missing evidence remains missing;
- self-scoring, self-certification, and self-approval are forbidden;
- lasting changes require independent non-self governance;
- hidden scores and provider reputation must not influence blind evaluation.

The preferred council model is a “round table of professors”: strong independent contributors under a deterministic protocol, not a hierarchy with one permanent chairman.

## CED and role architecture

Preserve the distinction:

```text
persistent model/agent identity
    != temporary council role
    != current task
    != CED authority
```

Roles rotate deterministically by phase and round.

Agents must not receive hidden scores, rankings, leaderboards, provider-prestige hints, or author identity during blind evaluation.

CED is a deterministic orchestrator. It must not fabricate semantic content, missing scores, or evidence.

Council Ratification is the selected V1 final-governance path. Candidate tournaments may be explored later, but must not silently replace the V1 architecture.

## Agent Prompt Architecture direction

The desired layered agent prompt architecture is:

```text
CED Core Epistemic Constitution
    + Persistent Agent Identity
    + Governed Identity Evidence
    + Agent Operating Protocol
    + Capability Manifest
    + Temporary Role Overlay
    + Phase / Task Contract
    + Exact Output Schema
    + Prompt-safe Context
    + Execution Stage
```

Do not collapse persistent identity, role, task, tools, memory, or governance into one untyped monolithic prompt.

The common agent operating discipline should support bounded:

```text
UNDERSTAND
    -> PLAN
    -> ASSESS
    -> SELECT CAPABILITY
    -> ACT OR REQUEST
    -> OBSERVE
    -> ADJUST
    -> STOP
```

Local planning belongs to the agent’s assigned task. Global workflow control remains with CED.

## Micro-Socratic requirement

The project owner requires the Micro-Socratic Kernel to become a real normal component of canonical agents, not merely prose telling the model to self-check.

The intended production flow is:

```text
agent draft
    -> exactly one governed Micro-Socratic Kernel check
    -> optional governed tool or External Consultation observation
    -> at most one bounded revision
    -> final AgentMove
```

The Kernel may question and recommend. It may not certify, approve, recurse, execute tools by itself, launch consultation by itself, silently replace the answer, mutate persistent state, or store hidden chain-of-thought.

Every agent may question itself. No agent may certify itself.

## Memory, Identity, Soul, and self-improvement

The user wants agents to improve over time, but never through unrestricted self-editing.

The governed path for a lasting change is conceptually:

```text
verified observation
    -> retained immutable evidence
    -> bounded self-review
    -> strict agent proposal
    -> independent evaluation
    -> named non-self approval
    -> recoverable application
    -> probation
    -> confirmation or rollback
```

Evidence creation is not activation.

A lesson, identity change, Soul principle, or prompt patch does not become active because one agent proposed it, one Kernel recommended it, or one evaluator assigned a score.

For personal Memory, whole-council lesson evidence is insufficient. Evidence must be bound to the exact target agent, exact lesson revision, exact governed Identity state, and exact matched experiment where required.

## Model and provider integrity

Silent model substitution is forbidden.

For strict provider execution:

- pin the exact requested model ID;
- disable model fallback and automatic model selection;
- fail closed when the model is unavailable;
- verify the actual returned model from provider metadata;
- store requested and returned model details in immutable receipts;
- pin or allowlist the upstream provider route for strict reproducibility when required.

A model cannot verify its own route from its generated text.

## Tool and external-action philosophy

Agents may identify or request an authorized capability. CED or a governed gateway performs the operation.

A capability declaration does not prove execution.

The user prefers useful agent autonomy for research, coding, analysis, and review, but with:

- explicit capability boundaries;
- finite call, token, timeout, and cost budgets;
- strict input/output schemas;
- observation and error handling;
- stop conditions;
- human confirmation for consequential or irreversible actions.

Permission to analyze does not imply permission to send, publish, purchase, delete, commit, merge, transfer, or mutate external state.

## Review and decision style

When reviewing work:

- find concrete defects, not hypothetical style complaints;
- distinguish blockers from improvements;
- preserve independently reviewable commits;
- verify claims against exact files and test output;
- do not weaken strict boundaries for convenience;
- do not add “defensive” normalization that masks nondeterminism or malformed evidence;
- prefer fail-closed behavior where authority, evidence, identity, or provider exactness is involved.

When multiple options exist, recommend one primary path and explain the tradeoff briefly.

## Other projects

The user also works on other projects, including blockchain gaming and DÆNEZIS/GABRIEL. They are outside this repository unless explicitly referenced by the active task.

Do not import their terminology, constants, token economics, or architectural assumptions into Socrates AI without an explicit project requirement.

## Privacy and non-inference

Do not infer or store personal facts beyond what is written here and what the user explicitly supplies for the current task.

Do not create claims about the user’s:

- personality diagnosis;
- health;
- legal or immigration status;
- finances;
- family;
- exact location;
- identity documents;
- private accounts;
- political or religious beliefs.

Do not store personal contact information, credentials, private messages, or sensitive documents in repository guidance files.

## Preferred final report

A good completion report should state:

```text
branch and exact head
files changed
what is now implemented
what remains planned or blocked
tests actually run and exact result
PR/base/mergeability status
risks or unresolved findings
one recommended next action
```

Accuracy is more important than sounding confident.

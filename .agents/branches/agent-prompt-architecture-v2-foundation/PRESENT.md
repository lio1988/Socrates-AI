# Present State — `agent/prompt-architecture-v2-foundation`

Snapshot date: 2026-07-16  
PR: `#68 — Add Agent Prompt Architecture v2 foundations`  
Base branch: `main`  
Original #68 foundation head before agent-handoff files: `80b67cb607c47f0c950ac867a29822a1b180051c`  
Latest parent before this `PRESENT.md` commit: `4feb7d7560086c79bd052433e0b22f47566854f8`

Always verify the live head with Git/GitHub before editing. This file records the handoff state, not an immutable ref.

## PR state

At the last verified PR inspection:

- PR #68 was open;
- it was a draft;
- it was mergeable;
- base was `main`;
- no merged state was reported;
- no GitHub combined-status checks were reported for the then-current head.

Do not mark it ready or merge it based on this snapshot alone.

## Original #68 foundation diff

Before the handoff workspace, PR #68 contained ten changed files, approximately 2,571 additions and no deletions:

```text
README.md
backend/dialogues/agent_prompt_architecture/__init__.py
backend/dialogues/agent_prompt_architecture/capabilities.py
backend/dialogues/agent_prompt_architecture/composer.py
backend/dialogues/agent_prompt_architecture/constitution.py
backend/dialogues/agent_prompt_architecture/identity.py
docs/agent_prompt_architecture/FEATURE_INTEGRATION_MATRIX.md
docs/agent_prompt_architecture/FOUNDATION_V2.md
docs/agent_prompt_architecture/README.md
tests_dialogues/test_agent_prompt_architecture_v2.py
```

This handoff added:

```text
AGENTS.md
CLAUDE.md
.agents/branches/agent-prompt-architecture-v2-foundation/README.md
.agents/branches/agent-prompt-architecture-v2-foundation/MEMORY.md
.agents/branches/agent-prompt-architecture-v2-foundation/PLANS.md
.agents/branches/agent-prompt-architecture-v2-foundation/PRESENT.md
```

These handoff files are documentation-only and do not activate runtime behavior.

## Implemented foundation behavior

The branch contains source for:

- a versioned canonical Constitution v2;
- content digest for the Constitution;
- frozen strict identity guidance items;
- frozen strict `AgentIdentityPromptView`;
- source digests and evidence references;
- deterministic identity ordering and digest;
- prompt-safe identity rendering with delimiter escaping;
- separation of requested model from returned-model verification;
- strict typed Capability Manifest and known capabilities;
- bounded Kernel and Consultation capability rules;
- deterministic foundation composition:

```text
Constitution -> Identity -> Capability Manifest
```

- foundation prompt lineage metadata;
- focused adversarial tests for these foundations.

## Not implemented or not runtime-wired

The following are not proven active on the canonical runtime path:

- governed projection from existing immutable Identity/evidence artifacts into `AgentIdentityPromptView`;
- common Agent Operating Protocol;
- complete prompt composition with role, phase/task, exact schema, prompt-safe context, and execution stage;
- role overlays v2;
- mandatory/default-on Micro-Socratic invocation for every canonical agent output;
- `draft_generation -> Kernel -> post_kernel_revision` execution;
- governed automatic tool/consultation routing from Kernel decisions;
- v2 exact requested/returned-model receipt integration;
- canonical Epistemic Event Ledger integration;
- staged production activation.

The existing Micro-Socratic Kernel and External Consultation packages are implemented/tested foundations on `main`, but they remain runtime-inert with respect to `CEDOrchestrator` unless later code has changed this fact. Inspect current code before relying on this statement.

## Documentation inconsistencies requiring correction

Known stale or incomplete wording exists:

1. `docs/agent_prompt_architecture/README.md` describes the Kernel as optional and runtime routing as `not_started`.
2. `FEATURE_INTEGRATION_MATRIX.md` uses optional/capability-gated language for the Kernel.
3. `FOUNDATION_V2.md` begins with historical language saying the target is specified but not implemented, although source was later added on this branch.
4. The root README’s original #68 section may still describe the branch as documentation-only or earlier-stage.
5. The PR body says not to activate Kernel/tools/Consultation in this PR phase and points next to T3.

These statements must be corrected carefully, preserving the distinction:

```text
current truth: Kernel runtime integration is not active
approved target: Kernel must be default-on for every accepted canonical agent output
```

Do not rewrite history to claim runtime activation.

## Validation actually known

The PR description reports:

```text
22 focused Agent Prompt Architecture tests passed
python compileall passed
```

That report was described as an exact local mirror validation, not a full branch checkout CI run.

For the handoff files added after `80b67cb`:

- no source behavior changed;
- no tests were run as part of their creation;
- no CI status was observed;
- `tests_dialogues` was not rerun;
- the full repository suite was not rerun.

Therefore current honest status is:

```text
foundation source: implemented
focused foundation evidence: reported, not independently revalidated in this handoff
canonical runtime wiring: not implemented
repository-wide validation: not established
PR state: draft
shipped: no
```

## Known risks

- The Constitution is long and may contain redundancy; reductions must not weaken invariants.
- Prompt cost/latency has not been measured across providers.
- Identity projection eligibility rules are not yet implemented.
- Capability Manifest is declarative only; no execution proof follows from it.
- Mandatory Kernel integration may roughly add a provider call per agent draft and possibly one bounded revision call; cost, latency, quorum, and failure policy require explicit evaluation.
- Kernel failure semantics must not silently accept unchecked drafts.
- Blind scorer and ratifier Kernel integration must preserve exactly the same anonymous context.
- Same-model-new-session auditing must preserve exact-model/provider policy and isolation.
- Full role overlay and exact-schema interactions are unvalidated.
- No current CI result is attached to the latest handoff head.

## Exact next action

Perform `PLANS.md` Gate 0 only:

1. fetch and inspect the live PR #68 diff;
2. verify every documentation status against current code;
3. update stale optional-Kernel wording to the mandatory end-state requirement;
4. retain explicit statements that runtime integration is still absent;
5. run the focused Agent Prompt Architecture tests on the real branch checkout;
6. update this file with the exact head, commands, and results.

Do not begin Kernel runtime wiring until branch truth and foundation validation are clean.

## Handoff completion rule

The next agent must update this file before stopping. The update must include:

- exact head SHA;
- commits added;
- files changed;
- tests and exact pass/fail counts;
- current PR state;
- unresolved findings;
- one next action.

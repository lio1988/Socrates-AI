# Present State — `agent/prompt-architecture-v2-foundation`

Snapshot date: 2026-07-16  
PR: `#68 — Add Agent Prompt Architecture v2 foundations`  
Base branch: `main`  
Original #68 foundation head before agent-handoff files: `80b67cb607c47f0c950ac867a29822a1b180051c`  
Handoff head before this final status commit: `e42f65523fccdbbd8709090a70aa0dc9f88a88d7`

Always verify the live head with Git/GitHub before editing. This file records the handoff state, not an immutable ref.

## Branch synchronization state

The latest verified comparison after creating the handoff workspace reported:

```text
status: diverged
branch ahead of main: 16 commits at comparison time
branch behind main: 2 commits
current main at comparison: b699dad275a9c8824811b0c7307a688f700d3eb2
merge base: 0cfedc66f7ae6c072f2e7ef30df1d818627f66be
```

Do not merge or rebase blindly.

Before implementation work:

1. inspect the two commits added to `main` after the merge base;
2. determine whether they overlap prompt, provider, Kernel, Consultation, governance, README, or test files;
3. investigate the current non-mergeable PR state and identify actual conflicts;
4. choose an explicit synchronization strategy;
5. preserve the exact reviewed branch tree and record the new head;
6. rerun affected tests after synchronization.

## PR state

The final verified PR inspection before this status commit reported:

```text
state: open
draft: true
merged: false
mergeable: false
head before this status commit: e42f65523fccdbbd8709090a70aa0dc9f88a88d7
commits: 17
changed files: 16
additions: 3642
deletions: 0
```

No GitHub combined-status checks were observed for the latest inspected head.

Do not mark the PR ready and do not merge it until divergence/conflicts are resolved and validation is rerun.

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
branch synchronization: required; branch is behind main
PR mergeability: false at final inspection
PR state: draft
shipped: no
```

## Known risks

- The branch is diverged from `main`; synchronization may expose conflicts or invalidate earlier test claims.
- PR #68 is currently reported as not mergeable.
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

Perform synchronization/conflict inspection followed by `PLANS.md` Gate 0 only:

1. inspect the two commits by which the branch is behind `main`;
2. inspect the live PR #68 diff and conflict state;
3. select and document the safe synchronization strategy;
4. resolve only verified conflicts without discarding the reviewed #68 foundation;
5. verify every documentation status against current code;
6. update stale optional-Kernel wording to the mandatory end-state requirement;
7. retain explicit statements that runtime integration is still absent;
8. run the focused Agent Prompt Architecture tests on the synchronized real branch checkout;
9. update this file with the exact head, commands, and results.

Do not begin Kernel runtime wiring until synchronization, branch truth, and foundation validation are clean.

## Handoff completion rule

The next agent must update this file before stopping. The update must include:

- exact head SHA;
- commits added;
- files changed;
- tests and exact pass/fail counts;
- current PR state;
- unresolved findings;
- one next action.

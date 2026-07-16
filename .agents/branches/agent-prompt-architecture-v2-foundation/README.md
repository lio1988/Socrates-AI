# Branch: `agent/prompt-architecture-v2-foundation`

PR: `#68 — Add Agent Prompt Architecture v2 foundations`  
Base: `main`  
Branch purpose: establish the common, versioned foundations for Socrates AI Agent Prompt Architecture v2 without falsely claiming full runtime activation.

## Mandatory reading order

Before editing this branch, read:

1. [`PRESENT.md`](PRESENT.md) — what is factually true now;
2. [`MEMORY.md`](MEMORY.md) — durable decisions that must be preserved;
3. [`PLANS.md`](PLANS.md) — ordered future work and gates;
4. [`AGENTS.md`](../../../AGENTS.md) — repository-wide agent contract;
5. [`CLAUDE.md`](../../../CLAUDE.md) when using Claude Code;
6. [`docs/agent_prompt_architecture/README.md`](../../../docs/agent_prompt_architecture/README.md);
7. [`docs/agent_prompt_architecture/FOUNDATION_V2.md`](../../../docs/agent_prompt_architecture/FOUNDATION_V2.md);
8. [`docs/agent_prompt_architecture/FEATURE_INTEGRATION_MATRIX.md`](../../../docs/agent_prompt_architecture/FEATURE_INTEGRATION_MATRIX.md);
9. the actual implementation under `backend/dialogues/agent_prompt_architecture/`;
10. `tests_dialogues/test_agent_prompt_architecture_v2.py` and the existing Kernel/Consultation tests.

Do not begin from historical chat summaries when the branch itself can answer the question.

## Branch scope

This branch owns the foundation layers:

```text
CED Core Epistemic Constitution v2.0
    + Persistent Agent Identity Capsule v1
    + Governed Identity Evidence contract
    + Capability Manifest contract
    + deterministic foundation composition
    + prompt/identity lineage metadata
    + focused adversarial tests
    + exact implementation roadmap
```

The intended complete agent architecture is:

```text
Constitution
    -> Persistent Identity
    -> Governed Identity Evidence
    -> Agent Operating Protocol
    -> Capability Manifest
    -> Temporary Role Overlay
    -> Phase / Task Contract
    -> Exact Output Schema
    -> agent draft
    -> mandatory one-pass Micro-Socratic Kernel
    -> optional governed tool / consultation observation
    -> bounded final revision
    -> final AgentMove
```

## Mandatory Micro-Socratic requirement

The final canonical production path must run one real governed Micro-Socratic Kernel check for every accepted canonical agent output.

This is not satisfied by mentioning self-checking in prompt prose.

The runtime must perform:

```text
draft_generation
    -> one MicroSocraticKernelService.check(...)
    -> policy handling
    -> optional governed observation
    -> at most one post-kernel revision
    -> final AgentMove
```

The Kernel remains recommendation-only and cannot approve, certify, recurse, execute tools, launch consultation by itself, mutate persistent state, or retain hidden chain-of-thought.

## What this branch must not do accidentally

Do not:

- discard the existing #68 foundation and replace it with one monolithic prose prompt;
- mix persistent identity with temporary role;
- put role-specific instructions inside the common Constitution;
- inject raw Memory, Identity, Soul, analytics, scores, provider mappings, or traces;
- let a model claim the actual returned model/provider route;
- leak authorship or provider identity into blind evaluation;
- treat a Capability Manifest as proof that a capability ran;
- describe runtime-inert code as runtime-active;
- activate tools, consultation, or Kernel routing without explicit policy, receipts, budgets, failure semantics, and tests;
- merge before repository-wide validation and independent review.

## Implementation philosophy

Prefer small, versioned, typed layers over a single giant prompt string.

The common prompt should remain stable. Dynamic information must enter through strict rendered blocks:

```text
identity_view
capability_manifest
role_contract
phase_task_contract
output_schema
prompt_safe_context
execution_stage
```

Runtime orchestration must remain outside the model. Agents reason semantically; CED routes, validates, aggregates, records, and governs.

## Status vocabulary

Use only these meanings:

- `specified` — documented target exists;
- `implemented` — source and tests exist;
- `validated_focused_only` — a focused subset passed;
- `validated` — required focused, `tests_dialogues`, and full repository suites passed;
- `runtime_wired` — canonical execution reaches the behavior;
- `shipped` — merged into the target branch;
- `blocked` — a named dependency or defect prevents progress.

## Required validation before merge

At minimum:

1. inspect the full branch diff against `main`;
2. run Agent Prompt Architecture focused tests;
3. run all affected Kernel, Consultation, provider, prompt, identity, scoring, and ratification tests;
4. run `tests_dialogues`;
5. run the full repository suite;
6. verify compile/import behavior;
7. verify no secret-shaped content or `.env` changes;
8. conduct an independent adversarial review;
9. update `PRESENT.md`, `MEMORY.md`, and `PLANS.md` with exact results;
10. keep PR #68 in draft until all stated gates are genuinely satisfied.

## Handoff rule

Every agent leaving this branch must update `PRESENT.md` with the exact final head, tests actually run, remaining defects, and one next action. Durable architectural decisions belong in `MEMORY.md`; unfinished steps belong in `PLANS.md`.

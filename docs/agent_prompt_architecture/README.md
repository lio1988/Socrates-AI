# Socrates AI — Agent Prompt Architecture v2

Branch: `agent/prompt-architecture-v2-foundation`  
PR: `#68`  
Status: **foundation code implemented and focused-tested; not runtime-wired**

This directory is the operator entry point for the versioned Agent Prompt
Architecture v2 work. It must be read together with
[`FOUNDATION_V2.md`](FOUNDATION_V2.md) and
[`FEATURE_INTEGRATION_MATRIX.md`](FEATURE_INTEGRATION_MATRIX.md).

## What is implemented on this branch

The branch now contains runtime-inert foundation modules for:

1. `CED Core Epistemic Constitution v2.0`;
2. strict `AgentIdentityPromptView` and source-linked guidance items;
3. strict per-task `CapabilityManifest`;
4. deterministic foundation composition and lineage metadata;
5. focused adversarial tests.

The code lives under:

```text
backend/dialogues/agent_prompt_architecture/
    __init__.py
    constitution.py
    identity.py
    capabilities.py
    composer.py
```

Focused tests live at:

```text
tests_dialogues/test_agent_prompt_architecture_v2.py
```

## Current proof

The exact branch file contents were mirrored locally and validated with:

```text
22 focused tests passed
python compileall passed
```

This is focused foundation proof only. The repository-wide `tests_dialogues` and
full suite have not yet been run against the branch, so the branch must not be
called fully validated or runtime-active.

## Locked composition order

```text
CED Core Epistemic Constitution v2.0
    + Persistent Agent Identity Capsule v1
    + Governed Identity Evidence Projection
    + Capability Manifest
    + Temporary Role Overlay
    + Phase Directive
    + Task-specific Contract
    + Exact Output Schema
    + optional bounded Micro-Socratic Check
```

The current `composer.py` intentionally stops after the Capability Manifest. Role,
phase, task, schema, Micro-Socratic runtime execution, tools, and consultation are
later controlled integration targets.

## Micro-Socratic Kernel placement

The Micro-Socratic Kernel is included in the architecture, but not as permanent
identity and not as an always-on block.

Its correct lifecycle position is:

```text
agent receives governed prompt stack
    -> agent produces a draft
    -> optional capability-gated Micro-Socratic Check
       (exactly one structured pass; light|standard|high_risk)
    -> CED/caller evaluates the recommendation
    -> optional governed tool or External Consultation route
    -> optional bounded revision
    -> ordinary peer evaluation / assembly / ratification
```

The Kernel:

- may inspect only the requesting agent's bounded task and draft;
- may recommend `accept`, `revise`, `verify_with_tool`,
  `consult_external_model`, or `insufficient_information`;
- may not execute tools or consultation;
- may not recurse;
- may not certify the agent;
- may not mutate CED, Memory, Identity, Soul, prompts, or governance;
- may not retain hidden chain-of-thought.

Its current repository implementation remains runtime-inert. Merely granting
`micro_socratic_check` in a manifest does not execute it; a governed caller must
perform the future routing.

## External Consultation placement

External Consultation is a separate capability after a governed request, usually
triggered by a Kernel recommendation or direct CED policy:

```text
bounded request
    -> one isolated provider call
    -> critic | independent_solver | judge result
    -> immutable receipt
    -> advice / candidate evidence only
    -> ordinary CED evaluation
```

It never becomes approval, a council seat, self-attestation, direct evidence for a
lasting identity change, or a tool-enabled recursive agent.

## Progress

| Target | Status on this branch | Evidence |
|---|---|---|
| `T0` documentation lock | `implemented` | Root README and foundation contract |
| `T1` canonical constitution module | `implemented` | `constitution.py` |
| `T2` strict identity prompt-view schema | `implemented` | `identity.py` |
| `T2a` strict capability-manifest schema | `implemented` | `capabilities.py` |
| `T4a` deterministic foundation renderer/digests | `implemented` | identity renderer + `composer.py` |
| focused adversarial tests | `validated_focused_only` | 22 tests passed in exact local mirror |
| governed Identity registry projection | `not_started` | Must reuse existing evidence foundations |
| canonical `reasoning_prompts.py` integration | `not_started` | Current runtime unchanged |
| Kernel runtime routing | `not_started` | Kernel remains runtime-inert |
| Consultation/tool routing | `not_started` | Must remain governed and bounded |
| requested/returned-model verification | `not_started_for_v2` | Adapter/receipt target |
| repository-wide suites | `not_run_for_v2` | Required before validation claim |
| canonical runtime activation | `not_started` | No active v2 calls yet |

## Next implementation target

The next safe target is **T3 — Governed Identity Projection**:

```text
existing immutable Identity/evidence artifacts
    -> read-only eligibility filter
    -> bounded AgentIdentityPromptView
    -> deterministic identity digest
```

Do not integrate raw registries, self-authored identity claims, proposed records,
hidden scores, or role-fit hypotheses. After T3 is independently reviewed, wire the
foundation into `build_reasoning_system_prompt(...)` behind an explicit migration
gate and preserve byte-compatible behavior when the new inputs are absent.

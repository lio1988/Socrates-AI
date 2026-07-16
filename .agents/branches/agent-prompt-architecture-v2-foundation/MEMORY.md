# Durable Memory — `agent/prompt-architecture-v2-foundation`

Only durable, evidence-backed branch decisions belong here.

## Canonical project identity

Socrates AI is a governed multi-agent epistemic system. The canonical engine is the `backend/dialogues/` CED family.

Permanent division of responsibility:

```text
Agents judge epistemic quality.
CED governs the protocol.
```

CED is deterministic protocol authority, not semantic truth authority.

## Locked architecture decisions

### Persistent identity is separate from temporary role

```text
model / agent identity != temporary role != current task != CED authority
```

Every model-agent may receive a governed persistent operational identity, but no model permanently owns Socrates, Elenchus Critic, Empiricist, Reflector, Maieutic Reconstructor, Synthesizer, Final Evaluator, or Ratifier.

Temporary roles remain deterministic CED assignments.

### Common prompt layers remain separated

The preferred architecture is modular:

```text
CED Core Epistemic Constitution
Persistent Agent Identity
Governed Identity Evidence
Agent Operating Protocol
Capability Manifest
Temporary Role Overlay
Phase / Task Contract
Exact Output Schema
Prompt-safe Context
Execution Stage
```

Do not collapse these into one untyped monolithic prompt.

### Constitution scope

The Constitution contains stable common epistemic, security, privacy, and governance obligations.

It must not contain:

- a permanent role;
- provider personality or prestige;
- task-specific output fields;
- live capability claims;
- current scores or rankings;
- author/provider hints for blind evaluation.

### Identity scope

The prompt-safe identity view may contain only bounded governed data such as:

- `agent_id`;
- provider family and provider ID;
- exact requested model ID;
- identity version and digest;
- validated strengths;
- known unresolved failures;
- approved lessons;
- active improvement hypotheses;
- probationary constraints;
- source digests and evidence references.

It must not contain:

- a permanent role;
- raw Memory, Identity, or Soul registries;
- hidden analytics or leaderboard data;
- self-authored reputation;
- self-supplied identity digest;
- a model-authored claim about the returned model/provider route.

Empty guidance arrays mean no eligible governed item was supplied for the call. They do not prove the absence of history, strengths, failures, or lessons.

### Exact-model integrity

The requested model is expected operational identity, not proof of actual execution.

Actual returned model and provider route must be verified from provider/adapter metadata and stored in immutable CED-owned receipts.

Silent model substitution, automatic model selection, and silent fallback are forbidden. Exact-model execution fails closed when the required model is unavailable. Strict reproducibility may also pin or allowlist the upstream provider route.

### Blind evaluation

Evaluators judge anonymous content under an exact rubric.

They must not receive or infer:

- author identity;
- provider identity or reputation;
- hidden scores or rankings;
- role-fit hypotheses;
- apparent majority preference.

No self-scoring. Missing scores remain missing.

### Micro-Socratic Kernel

The repository already contains a strict, tested Micro-Socratic Kernel service and receipts foundation.

The required final canonical behavior is default-on for accepted canonical agent outputs:

```text
agent draft
    -> exactly one governed Micro-Socratic check
    -> optional governed tool/consultation observation
    -> at most one bounded revision
    -> final AgentMove
```

The Kernel is not satisfied by prompt prose alone.

It may recommend:

- `accept`;
- `revise`;
- `verify_with_tool`;
- `consult_external_model`;
- `insufficient_information`.

It may not approve, certify, recurse, execute tools, launch consultation by itself, silently replace the answer, mutate CED/Memory/Identity/Soul/prompts/governance, or store hidden chain-of-thought.

Every agent may question itself. No agent may certify itself.

### External Consultation

External Consultation is one isolated advisory call in `critic`, `independent_solver`, or `judge` mode.

It is advice or candidate evidence only. It cannot vote, approve, execute tools, delegate, recurse, mutate state, or serve as self-attestation.

### Tools and capabilities

A Capability Manifest declares the authorized action space. It is permission for governed routing, not proof of execution.

Agents may request or select an authorized capability. CED/tool gateways execute and return validated observations.

Do not narrate a requested action as already executed.

### Governed learning

Lasting Memory, Identity, Soul, prompt, or governance changes require a governed lifecycle:

```text
verified observation
    -> retained evidence
    -> bounded self-review
    -> strict proposal
    -> independent evaluation
    -> named non-self approval
    -> recoverable application
    -> probation
    -> confirmation or rollback
```

A Kernel result, consultation, score, or receipt is never self-approval.

## Current #68 foundation assets

PR #68 introduced or documents:

- `backend/dialogues/agent_prompt_architecture/constitution.py`;
- `backend/dialogues/agent_prompt_architecture/identity.py`;
- `backend/dialogues/agent_prompt_architecture/capabilities.py`;
- `backend/dialogues/agent_prompt_architecture/composer.py`;
- package exports;
- focused Agent Prompt Architecture tests;
- the large foundation implementation contract;
- feature integration matrix;
- operator README.

These are valuable foundations and must be extended, not casually discarded.

## Validation truth

Focused tests or `compileall` do not equal full validation.

A branch may be called validated only after the required focused tests, affected regression tests, complete `tests_dialogues`, and full repository suite pass on the actual branch checkout, followed by independent review.

## Documentation truth

Documentation must distinguish:

```text
specified
implemented
validated_focused_only
validated
runtime_wired
shipped
blocked
```

Never promote status by wording alone.

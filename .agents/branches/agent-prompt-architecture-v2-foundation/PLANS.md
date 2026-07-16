# Plans — `agent/prompt-architecture-v2-foundation`

This file describes future work. Nothing here is implemented merely because it is listed.

## End-state

Deliver a versioned Agent Prompt Architecture v2 in which every canonical model-agent has:

- a common epistemic Constitution;
- a governed persistent operational identity independent of temporary role;
- bounded prompt-safe identity evidence;
- a common agent operating protocol;
- an explicit per-task Capability Manifest;
- a temporary role overlay;
- exact phase/task and output contracts;
- prompt-safe dialogue continuity;
- a real default-on one-pass Micro-Socratic runtime stage;
- governed optional tools and External Consultation;
- exact prompt/model/provider/identity lineage;
- blind evaluation and no self-approval.

## Ordered implementation plan

### Gate 0 — Re-establish branch truth

Before adding behavior:

1. inspect `main...agent/prompt-architecture-v2-foundation`;
2. inspect all ten original #68 changed files plus this handoff workspace;
3. compare documentation claims with actual code and tests;
4. update stale uses of “optional Kernel” where the intended final product behavior is mandatory/default-on;
5. preserve historical statements that accurately describe the current runtime as not yet wired.

Acceptance:

- documentation clearly separates current state from mandatory target state;
- no claim says the Kernel is currently active when it is not;
- no final architecture statement treats the Kernel as merely optional.

### Gate 1 — Constitution and foundation audit

Audit `constitution.py` against the complete project architecture.

Confirm coverage of:

- contribution orientation;
- epistemic markers and confidence calibration;
- non-fabrication;
- dialogue continuity;
- persistent identity versus temporary role;
- Capability Manifest boundaries;
- Micro-Socratic and Consultation authority boundaries;
- blind evaluation and anti-herding;
- exact-model/provider integrity;
- prompt injection and untrusted-data boundaries;
- privacy and hidden-reasoning boundaries;
- governed learning and no self-approval;
- exact output-schema precedence.

Remove duplicated prose only when meaning and tests are preserved. Do not insert role-specific output mechanics into the Constitution.

Acceptance:

- canonical Constitution is stable, versioned, content-addressed, and role-neutral;
- adversarial tests cover omitted or weakened invariants;
- no blind-evaluation leakage.

### Gate 2 — Agent Operating Protocol

Add a dedicated, versioned common operating layer, separate from the Constitution.

Target operating cycle:

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

Required properties:

- smallest sufficient local plan;
- no redesign of CED protocol;
- typed capability requests;
- observations evaluated for relevance, reliability, independence, and limitations;
- explicit stop states;
- bounded iteration and no hidden chain-of-thought export;
- read/write and irreversible-action boundaries;
- no narration of proposed operations as executed.

Suggested module:

```text
backend/dialogues/agent_prompt_architecture/operating_protocol.py
```

Acceptance:

- deterministic rendering and digest;
- no role-specific leakage;
- exact tests for tool-request versus tool-execution language;
- explicit bounded stop conditions.

### Gate 3 — Governed Identity Projection

Build a read-only projection from existing eligible immutable identity/evidence foundations into `AgentIdentityPromptView`.

The projection must:

- accept only recognized governed source artifacts;
- enforce source integrity and eligibility state;
- exclude proposed, rejected, reverted, expired, incomparable, self-attested, or unverified records;
- sort deterministically;
- apply item/count/character budgets;
- preserve source digests and evidence references;
- avoid raw registry injection;
- never include hidden scores, role-fit analytics, provider ranking, or secret-shaped content.

Suggested module:

```text
backend/dialogues/agent_prompt_architecture/identity_projection.py
```

Acceptance:

- exact source eligibility tests;
- adversarial self-attestation and stale-record tests;
- deterministic digest stability;
- graceful empty projection semantics.

### Gate 4 — Full prompt composer

Extend composition from the current foundation layers to typed complete prompts:

```text
Constitution
Identity
Governed Identity Evidence
Agent Operating Protocol
Capability Manifest
Temporary Role
Phase / Task
Output Schema
Prompt-safe Context
Execution Stage
```

Requirements:

- no raw string interpolation of untrusted structured data;
- deterministic escaping and ordering;
- exact prompt ID/version/digest;
- explicit `draft_generation` and `post_kernel_revision` stages;
- compatibility gate preserving existing behavior when v2 is disabled;
- no model-authored returned-model verification.

Acceptance:

- golden prompt fixtures;
- prompt-injection delimiter tests;
- provider-neutral semantics;
- byte-stable rendering for identical inputs.

### Gate 5 — Role overlays v2

Implement small, versioned overlays for:

- Socrates;
- Elenchus Critic;
- Empiricist;
- Reflector;
- Maieutic Reconstructor;
- Synthesizer;
- evaluators/scorers;
- Council Ratifiers.

Each overlay defines:

- role objective;
- required behaviors;
- forbidden behaviors;
- rubric;
- exact schema linkage;
- one or more concise form exemplars where useful.

Preserve deterministic role rotation and provider/model independence.

Acceptance:

- no permanent role in Identity;
- no cross-role contamination;
- blind evaluator overlays contain no author/provider hints;
- Socrates asks exactly the task-required question form;
- synthesizer and ratifier schemas remain exact.

### Gate 6 — Mandatory Micro-Socratic runtime integration

Wire the existing Kernel service into the canonical agent execution path.

Required flow:

```text
AgentTask
    -> draft_generation model call
    -> strict draft parse/validation
    -> MicroSocraticRequest
    -> exactly one MicroSocraticKernelService.check(...)
    -> check/receipt validation and persistence
    -> policy resolution
    -> optional governed tool/consultation observation
    -> at most one post_kernel_revision model call
    -> final AgentMove validation
```

Default production policy:

- one Kernel check per accepted canonical agent output;
- `standard` mode by default;
- `high_risk` for configured consequential domains;
- no second Kernel pass;
- no silent bypass on Kernel timeout, malformed output, or provider failure;
- failed Kernel means the move is unavailable unless an explicit documented rollback/compatibility policy applies;
- quorum/failure reporting remains honest.

The same-model-new-session implementation may be the default auditor path, provided exact model/provider policy and isolation are preserved.

Acceptance:

- real service invocation proven in integration tests;
- exactly-one-call invariant;
- receipts persisted and verified;
- no hidden context transfer;
- no nested consultation;
- no self-certification;
- no accidental duplicate billing/retry;
- deterministic mock path remains testable.

### Gate 7 — Governed tool and consultation routing

Implement typed resolution for Kernel decisions:

- `accept`;
- `revise`;
- `verify_with_tool`;
- `consult_external_model`;
- `insufficient_information`.

Requirements:

- Kernel only recommends;
- CED validates the request against the Capability Manifest;
- tool/consultation gateways execute under budgets;
- results return as validated observations;
- at most one bounded revision follows;
- no irreversible external write without explicit authorization;
- no recursive consultation or Kernel loops.

Acceptance:

- decision/content coherence tests;
- denied capability tests;
- failed observation remains failed;
- no fabricated result fallback;
- exact audit lineage.

### Gate 8 — Exact-model and provider-route receipts

For live/strict adapters:

- pin exact requested model ID;
- disable model auto-selection and fallback;
- fail closed when unavailable;
- verify actual returned model from response metadata;
- record requested model, returned model, provider route, prompt digest, identity digest, and capability manifest digest;
- optionally enforce provider-route allowlist for reproducibility runs.

Acceptance:

- substitution/fallback simulations fail closed;
- mismatched returned model is rejected;
- immutable receipt conflicts are refused;
- no secret material in receipts.

### Gate 9 — Evaluation and staged activation

Run blind cross-provider evaluations comparing:

- current v1.9 prompt path;
- v2 foundation without Kernel;
- v2 with mandatory Kernel;
- v2 with authorized observations and bounded revision.

Measure at minimum:

- task/schema success;
- factual/evidential quality;
- calibration;
- contradiction detection;
- revision quality;
- blind section scores;
- ratification blocks/caveats;
- latency;
- token/cost overhead;
- provider failure rates.

Activation sequence:

```text
offline deterministic tests
    -> shadow mode
    -> opt-in canary
    -> bounded production rollout
    -> observation period
    -> promotion or rollback
```

No silent global activation.

## Validation commands

Use the repository’s actual environment. At minimum, record exact commands and results for:

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues/test_agent_prompt_architecture_v2.py -q
.\.venv\Scripts\python.exe -m pytest tests_dialogues/test_micro_socratic_schema.py tests_dialogues/test_micro_socratic_policy.py tests_dialogues/test_micro_socratic_prompting.py tests_dialogues/test_micro_socratic_service.py tests_dialogues/test_micro_socratic_receipts.py -q
.\.venv\Scripts\python.exe -m pytest tests_dialogues -q
.\.venv\Scripts\python.exe -m pytest -q
```

Also run targeted prompt/provider/identity/scoring/ratification tests affected by each implementation gate.

## Explicit non-goals for one commit

Do not attempt all gates in one commit.

Do not:

- rewrite the CED protocol as an LLM supervisor;
- replace deterministic orchestration with autonomous agent delegation;
- enable unrestricted tool use;
- expose hidden reasoning;
- add automatic persistent learning;
- merge role identity into persistent model identity;
- silently activate live providers;
- modify `.env`;
- merge PR #68 before full validation and independent review.

## Next exact action

Perform Gate 0: inspect the actual current branch diff and correct the branch documents so they state both truths simultaneously:

1. the Micro-Socratic Kernel is currently implemented/tested but runtime-inert;
2. the approved canonical end-state requires it to be default-on for every accepted canonical agent output.

Then update `PRESENT.md` with the exact resulting head and validation status.

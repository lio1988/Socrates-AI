# Micro-Socratic Kernel v1

**Canonical name:** `OPENCLAW_MICRO_SOCRATIC_KERNEL`

A small, bounded self-check an agent runs on its own draft **before** finalizing
an answer. It names the central claim, the assumptions it needs, the strongest
challenge, what still needs verifying, and **one** bounded recommendation. The
result is advice to the caller — never authority.

## The central invariant

```
Every agent may question itself.
No agent may certify itself.
```

And its corollaries:

```
The kernel may recommend verification.   It may not execute verification.
The kernel may recommend revision.       It may not silently replace the answer.
The kernel may identify uncertainty.     It may not convert uncertainty into authority.
```

## Why it is NOT a chain-of-thought recorder

The kernel asks the auditor for **short structured findings only**, and the
schema's field set is **exact** — any `reasoning`, `scratchpad`,
`internal_monologue`, `thoughts`, or `chain_of_thought` key is refused. It never
requests, transports, or stores a token-by-token deliberation. The system prompt
explicitly says *"Do not reveal chain-of-thought. Do not write an internal
monologue."* The receipt stores no `raw_text` and no reasoning — only digests and
isolation flags.

## The three risk modes

| Mode | Required fields | Decisions allowed |
| --- | --- | --- |
| `light` | `claim_summary`, `strongest_challenges`, `decision`, `revision_guidance` | accept, revise, insufficient_information |
| `standard` | + `assumptions`, `verification_requests` | all five |
| `high_risk` | + `missing_evidence`, `uncertainties` | all five |

`high_risk` (medical, legal, financial, security, consequential real-world
actions) does **not** buy more provider calls — it only demands a stricter,
fuller structured result. The field set is validated exactly per mode.

## The five-question protocol

1. **Claim** — what is the draft's central conclusion?
2. **Assumptions** — what must hold for it to be true?
3. **Strongest challenge** — the strongest objection, refutation, or counterexample.
4. **Verification need** — does it need a deterministic tool, web, time/date,
   calendar, external consultation, or more evidence?
5. **Decision** — one bounded recommendation (below).

## Bounded budgets

```
max_inner_rounds = 1            (exactly one structured pass — no check→check→check)
max_revision_recommendations = 1
max_assumptions = 5
max_challenges = 3
max_verification_requests = 3
consultation_depth = 0          (consultation_allowed == false)
tools_executed = false
```

The kernel produces **one** structured evaluation. There is no repair/retry call
and no nested self-questioning.

## The decision enum

```
accept                  — no blocking issue found (NOT an approval of the agent)
revise                  — needs a bounded revision (requires revision_guidance)
verify_with_tool        — needs a deterministic/tool verification
consult_external_model  — recommends an independent second opinion
insufficient_information — cannot conclude on the evidence at hand
```

**Decision↔content coherence** is enforced so a caller cannot cherry-pick an
incoherent result: `accept` must carry no `revision_guidance`; `revise` requires
it; `verify_with_tool` requires a tool `verification_request`;
`consult_external_model` requires an `external_consultation` request;
`insufficient_information` (standard/high_risk) requires at least one
verification request, missing evidence, or uncertainty.

## Verification recommendations (never executed)

Each `verification_request` is `{kind, reason, priority}`:

- **kind** ∈ `calculator, web, time_date, calendar_read, external_consultation,
  code_test, source_check, user_clarification`
- **priority** ∈ `required, recommended, optional`

In v1 these are **recommendations only**. The kernel executes none of them.

## Relation to tools

The kernel may *recommend* `verify_with_tool` and list tool kinds. It has **no
tool channel** — the `KernelCall` carries no tool definitions, and the result
schema forces `tools_executed == false`. A governed caller decides whether to run
any recommended tool.

## Relation to External Consultation

The kernel may return `decision = consult_external_model`, but it does **not**
import or call `ExternalConsultationService`. The wiring happens later through a
governed caller. So:

```
Micro-Socratic Kernel recommends.
External Consultation advises.
CED / governance decides.
```

## Relation to the Deliberation Tree and CED

```
Micro-Socratic Kernel = one agent's local self-check
External Consultation = an independent second opinion
Deliberation Tree     = multiple alternatives / revisions
CEDOrchestrator       = the sole production execution authority
```

The kernel is the smallest, most local of these. It never becomes a second
orchestrator, council, approval engine, or governance authority.

## Schemas

- **`openclaw_micro_socratic_request_v1`** — `schema_version, request_id,
  agent_id, mode, provider, model, task, task_sha256, draft, draft_sha256,
  purpose, max_tokens, timeout_seconds, created_at, expires_at, max_inner_rounds
  (==1), tools_allowed (==false), consultation_allowed (==false),
  request_digest`. `request_id` must be a strict, path-safe identifier;
  `max_inner_rounds` must be the **integer** 1. Unknown fields, NaN/Infinity,
  secret-shaped values, semantically-impossible or non-increasing timestamps,
  oversized strings, and malformed hashes are refused.
- **`openclaw_micro_socratic_check_v1`** — `request_id, request_digest, agent_id,
  mode, provider, model, provider_status (=="ok"), structured_payload (strict
  per mode), isolated_check, tools_executed, consultation_executed, inner_rounds,
  response_digest`. Only built from an OK status; free-text fields reject
  secret/authority/self-certification claims.
- **`openclaw_micro_socratic_receipt_v1`** — binds `request_digest` to
  `result_digest`, records the `decision` (for audit, not approval), the
  isolation flags, worker, timestamps, and `token_usage` when present. Exact
  rerun is idempotent; the same `request_id` with different content is an
  immutable conflict.

## Receipt / evidence boundaries

A kernel check is a **recommendation with an audit trail**, not evidence that
justifies a lasting change. To become a lasting change, its content must still
travel the ordinary governed self-revision path (evidence → bounded self-review →
strict proposal → independent evaluation → named non-self approval → recoverable
application → probation → confirm/revert). The receipt store reuses the
repository's hardened persistence (hashed containment-checked filenames, atomic
no-overwrite publication) and additionally fixes the Windows `DELETE_PENDING`
fallback-lock race so a concurrent publisher never leaks a raw filesystem
exception.

## Shared receipt-store architecture

PR #64 is merged. Both the external-consultation and Micro-Socratic domains use
`backend/dialogues/openclaw_receipts.py` as a neutral shared primitive for
atomic, immutable JSON receipt persistence. Domain schemas, builders, verifiers,
and error types remain separate.

The kernel remains runtime-inert: this consolidation does not execute external
consultations, grant self-certification authority, or mutate CED, Memory,
Identity, Soul, governance, or runtime state.

## Operator CLI

Offline, deterministic (mock adapter), read-only with respect to agent and
governance state:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_micro_socratic_check.py `
  --agent local_apprentice_001 `
  --mode standard `
  --provider mock `
  --model mock-socratic-auditor `
  --task-file runs\micro_socratic\task.txt `
  --draft-file runs\micro_socratic\draft.txt `
  --output runs\micro_socratic\check.json
```

It wires only the deterministic `mock` adapter (a live provider is never
activated, no `.env` is read), writes one check file and one receipt file, and
executes no tool and opens no consultation. Set `CED_MICRO_SOCRATIC_NOW` to a
fixed ISO timestamp for fully deterministic, idempotent output.

## Future integration path (runtime-inert in v1)

There is **no automatic check** inside `CEDOrchestrator`; the package is not
imported by the CED runtime. A `KernelGateway` exists purely as a seam so a
future phase can wire:

```
draft
→ Micro-Socratic Check
→ caller evaluates decision
→ optional governed tool / consultation request
→ optional revision
→ final answer
```

Production CED remains the sole execution authority. The kernel only ever hands
the caller a bounded, auditable recommendation.

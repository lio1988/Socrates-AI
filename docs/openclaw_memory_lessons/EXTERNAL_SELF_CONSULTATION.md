# External Self-Consultation v1

**Canonical name:** `OPENCLAW_EXTERNAL_SELF_CONSULTATION`

A requesting agent may open **one isolated, stateless session** with another
model — or the same model in a fresh session — submit a bounded question as a
user, and receive strictly-validated **advice** before finalizing its own
answer. Nothing here changes agent state or governance state.

## The central invariant

```
The requesting agent may ask.
The consulted model may advise.
The consulted model may not execute, approve, delegate, or mutate.
Only governed evidence may justify a lasting change.
```

A consultation result is **advice / candidate evidence**. It is *never*:
authority, approval, ground truth, a Memory/Identity/Soul mutation, a prompt
mutation, or a CED decision. To become a lasting change, its content must still
travel the ordinary governed self-revision path (evidence → bounded self-review
→ strict proposal → independent evaluation → **named non-self** approval →
recoverable application → probation → confirm/revert). Consultation shortcuts
none of that.

## The flow

```
Agent A drafts, or recognizes uncertainty
  → builds a bounded ExternalConsultationRequest
  → policy gate checks scope, budget, privacy, expiration
  → a fresh isolated provider session is opened
  → the consulted model answers with no tools and no delegation
  → a strict ConsultationResult is produced (fail-closed per mode)
  → a tamper-evident ConsultationReceipt binds request+result
  → Agent A may use the answer as ADVICE
  → the advice is not authority, approval, or lasting evidence by itself
```

Exactly **one** provider call happens per request. Any failure — policy
violation, timeout, non-OK provider status, malformed or wrong-mode JSON —
**fails closed** with no fabricated result.

## The three modes

| Mode | Sees | Returns |
| --- | --- | --- |
| `critic` | the task **and** the requesting agent's draft | `issues`, `strengths`, `missing_assumptions`, `recommended_checks` |
| `independent_solver` | the task **only** (no draft) | `independent_answer`, `assumptions`, `uncertainties`, `recommended_verifications` |
| `judge` | two **anonymous** candidates (`candidate_a`, `candidate_b`) | `verdict`, `criterion_scores`, `rationale`, `critical_difference` |

Each `critic` issue is an object with exactly `severity`
(`critical|major|minor`), `category`, `description`, `affected_claim`,
`suggested_check`. `judge` verdict is one of
`candidate_a | candidate_b | tie | insufficient_evidence`; scores are numbers in
`[0, 10]`.

`independent_solver` never sees the draft — that is the point: it reduces
**confirmation bias** by producing a genuinely independent answer to compare
against.

For `judge`, the presentation order is the request's own `candidate_order`
(`[0, 1]` or `[1, 0]`), which is **bound into the request digest**. The same
canonical request therefore always yields the exact same prompt, and the
receipt records the resolved order so the verdict maps back unambiguously:
`candidate_a → original candidate[candidate_order[0]]`,
`candidate_b → original candidate[candidate_order[1]]`. There is no external,
un-bound seed that could move the prompt outside the digest.

## Same model, fresh session

`consultation_relation` is either `same_model_new_session` or `peer_model`. The
first is the "ask a fresh copy of myself" case (e.g. a GPT agent opening a new,
history-free GPT session and asking *"Check this solution and find the three
most important logical gaps"*). Because the session is built only from a
`ConsultationCall` (system + one user message), it carries no prior turns — a
"same model" consult is as isolated as a peer consult.

## Why it is not authority

The consulted model has no seat in the council, no vote, no write capability,
and no way to approve anything. The result schema records `isolated_session`,
`tools_disabled`, `delegation_disabled` (all forced true) precisely so a
downstream reader can see that this was advice from a powerless session. The
strict payload validator rejects any **authority/tool-use claim** in the text
(e.g. "I executed the tests", "I approve this", "tool_call"), so a model cannot
*narrate* itself into authority either.

A requesting agent **cannot become its own approver** through consultation:
the result carries no approval field, contains no authority claim, and the
governed approval step still requires a **named, non-self** human.

## Privacy boundaries

The consulted session is isolated by construction. The `ConsultationCall` sent
to the provider contains **only**: a fixed isolation system prompt, one user
message built from the bounded request, and the token/timeout budget. It never
contains:

- previous conversation history
- the requesting agent's private scratchpad or hidden chain-of-thought
- the full Memory / Identity / Soul profile
- secrets or API keys (secret-shaped content is rejected at request build time)
- any tool handle, and no `judge`/`independent_solver` never receives the draft

The consulted model **cannot call** web, calendar, email, files, code
execution, another consultation, Memory/Identity/Soul operations, or governance
operations. There is no tool channel in the call at all.

## Recursion and budget limits

- `consultation_depth == 1`, strictly. There is no nested consultation; the
  service performs one provider call and never calls itself or CED.
- Every request carries a `max_tokens` budget, a `timeout_seconds`, an
  `expires_at`, a maximum question size, a maximum draft/candidate size, and a
  maximum number of `public_evidence_references`. The policy gate may tighten
  (never loosen) these ceilings and refuses expired requests.

## Schemas

### `openclaw_external_consultation_request_v1`

`schema_version`, `request_id`, `requesting_agent_id`, `mode`,
`consulted_provider`, `consulted_model`, `consultation_relation`, `question`,
`question_sha256`, `draft` **or** `candidates` + `candidate_order` (per mode),
`public_evidence_references`, `purpose`, `max_tokens`, `timeout_seconds`,
`created_at`, `expires_at`, `consultation_depth (==1)`,
`tools_allowed (==false)`, `request_digest`.

Mode invariants: `critic` requires a draft and forbids candidates/candidate_order;
`independent_solver` forbids all of them; `judge` requires exactly two candidates,
forbids a draft, and carries a `candidate_order` permutation of `[0, 1]`
(defaulting to `[0, 1]`) that is part of the request digest. `request_id` must be
a strict, path-safe identifier (ASCII letters/digits/`.`/`_`/`-`; no path
separators, drive/stream markers, or bare `.`/`..`). `consultation_depth` must be
the **integer** `1` (not `True`/`1.0`/`"1"`). Unknown fields, NaN/Infinity,
secret-shaped values, semantically-impossible or non-increasing timestamps
(rejected as `ConsultationError`), oversized strings, and malformed hashes are
all refused.

### `openclaw_external_consultation_result_v1`

`schema_version`, `request_id`, `request_digest`, `mode`, `provider`, `model`,
`provider_status (=="ok")`, `isolated_session`, `tools_disabled`,
`delegation_disabled`, `structured_payload` (strict per-mode),
`response_digest`.

A result is only built from an OK provider status. The payload is validated
against the exact per-mode field set, types, bounds, enums, secret patterns and
authority-claim patterns — **valid JSON is not enough**.

### `openclaw_external_consultation_receipt_v1`

`schema_version`, `request_id`, `request_digest`, `result_digest`,
`requesting_agent_id`, `mode`, `provider`, `model`, `consultation_relation`,
`candidate_order`, `worker_id`, `isolated_session`, `tools_disabled`,
`delegation_disabled`, `started_at`, `completed_at`, `provider_status`,
`token_usage` (when present), `receipt_digest`.

The receipt binds the canonical request digest to the canonical result digest,
and records the resolved `candidate_order` so a judge verdict maps back to the
original candidate indices without the request in hand. An exact rerun is
**idempotent**; the same `request_id` with different content is **refused** as an
immutable conflict. It stores no API keys, no auth headers, and no hidden
provider reasoning.

### Safe, atomic receipt persistence

The receipt store never uses the raw `request_id` as a filename. It writes one
file per request keyed by `sha256(request_id) + ".receipt.json"`, and
`_path_for` additionally asserts (via `resolve()`) that the path stays directly
beneath the store directory — so a hostile `request_id` can neither traverse out
of the store nor collide with a Windows drive/stream marker. Publication is
**atomic and immutable**: each writer writes a uniquely-named temp file in the
same directory, then publishes with an atomic no-overwrite link (falling back to
an exclusive `O_EXCL` create). The first distinct content for a `request_id`
wins; a concurrent writer with different content gets an immutable conflict
(never last-writer-wins); identical content is an idempotent success; temp files
are always cleaned up, even on failure. The existing final receipt is
re-verified before any idempotent return.

## Operator CLI

Offline, deterministic (mock adapter), read-only with respect to agent and
governance state. It writes one result file and one receipt file.

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_external_consult.py `
  --mode critic `
  --agent local_apprentice_001 `
  --provider mock `
  --model mock-critic `
  --question-file runs\consultation\question.txt `
  --draft-file runs\consultation\draft.txt `
  --output runs\consultation\critic-result.json
```

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_external_consult.py `
  --mode independent_solver `
  --agent local_apprentice_001 `
  --provider mock `
  --model mock-solver `
  --question-file runs\consultation\question.txt `
  --output runs\consultation\solver-result.json
```

`judge` mode takes two `--candidate-file` arguments plus an optional
`--candidate-order` (`0,1` default, or `1,0` to swap which file is presented as
`candidate_a`); the chosen order is bound into the request digest and recorded
in the receipt. In v1 the CLI wires only the deterministic `mock` adapter; any
other provider is refused (a live provider is never activated here and no `.env`
change is required). `--request-id` (if supplied) must be a strict path-safe
identifier or the run is refused. Set `CED_CONSULTATION_NOW` to a fixed ISO
timestamp for fully deterministic, idempotent output.

## Integration boundary (runtime-inert in v1)

There is **no automatic consultation** inside `CEDOrchestrator`. The package is
additive and is not imported by the CED runtime. A `ConsultationGateway`
exists purely as a seam so a future phase can wire

```
draft → bounded self-questioning → consultation request → result → optional revised draft
```

without importing the consultation package into the CED runtime (which would
break the existing runtime-inert boundary). Production CED remains the sole
execution authority.

## Future Tool-PC / browser adapter boundary

The consulted model receives a `ConsultationCall`, never a council-internal
`AgentTask`. That clean boundary is deliberate: a later **Tool-PC** or
experimental **browser-chat** adapter only has to satisfy the
`ConsultationProvider` protocol (`async consult(call) -> ConsultationRawResponse`)
and it slots in **without changing any schema, policy, or receipt contract**.

## Why browser automation of the ChatGPT UI is not canonical v1

Driving the public ChatGPT website through browser automation is brittle,
unversioned, and hard to make tamper-evident or reproducible; it also blurs the
isolation boundary (cookies, logged-in history, UI-injected context). The
canonical v1 path uses the repository's existing provider/adapter infrastructure
with a fresh stateless call, which is auditable, bounded, and offline-testable.
A browser-chat adapter may still be added later — behind the same
`ConsultationProvider` boundary and the same evidence contracts — as an explicit,
clearly-labeled experiment.

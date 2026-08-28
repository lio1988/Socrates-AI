# Controlled experiment plan

Status: **controlled experiments complete; normal live runner prepared but not executed**.

## GPT-4.1 structured-output experiment

## Success criterion

Run exactly one no-retry inference for each authorized arm, retain the exact
outputs and requested measurements, apply both through unchanged CED, compare
their Socratic quality separately from schema compliance, then stop.

## Scope

1. Reconstruct and hash-lock the prompt-only control.
2. Generate the provider JSON Schema from the accepted CED opening-move fields
   and existing enums; prove nesting and field parity.
3. Validate the exact pinned endpoint and endpoint-compatible output-token field
   immediately before each arm.
4. Dispatch ARM 1 (`openai/gpt-4.1-mini`) once and ARM 2
   (`openai/gpt-4.1`) once, in fresh processes, with no retries.
5. Record transport, schema, CED, Socratic, content, latency, token, and cost
   evidence; compare the two actual questions side by side.

## Non-goals

- No CED relaxation or new transition authority.
- No additional model, question, retry, fallback, or architecture phase.
- No production integration and no push.

## Gates and stop conditions

- Offline parity and transport-path tests must pass before live dispatch.
- Exact numeric operator price ceilings and per-arm maxima must be explicitly
  authorized before they are rendered as authority.
- Credential presence is checked without exposing the credential before claims
  or live invocation.
- Any arm failure is its result; it is not retried.
- Stop after the second arm and report.

All steps and gates completed. Exactly two inference dispatches occurred, one
per arm, and no retry occurred.

## Reduced GPT-5 Mini benchmark

### Success criterion

Retain all three benchmark questions if feasible; compare direct GPT-5 Mini
answers with a four-seat homogeneous GPT-5 Mini CED condition on Q2; remain
under the `$8.00` hard session ceiling; preserve zero retries; record failures as
results; and stop without expanding scope.

### Authorized scope

1. Freshly validate the exact `openai/flex` endpoint for
   `openai/gpt-5-mini`.
2. Dispatch one direct baseline for Q1, Q2, and Q3.
3. Allow at most 148 CED calls for one four-seat homogeneous Q2 session, for a
   total maximum of 151 live calls.
4. Use a 1,024-token output limit, whole-context P19 reservation, zero retries,
   and a hard `$8.00` session ceiling.
5. Persist collection evidence, run the hidden evaluator only after collection
   closed, write the report, then stop.

### Removed conditions

- all heterogeneous councils;
- the GPT-4.1-mini benchmark control;
- homogeneous councils for Q1 and Q3;
- any retry, fallback, or extra question.

### Validation gates and stop conditions

- Exact endpoint evidence, not model-level parameter unions, must establish
  routing, supported parameters, and price compatibility before inference.
- Returned model/provider mismatch, price-bound failure, cost-ceiling failure,
  or any session-fatal condition stops further dispatch.
- Provider or CED failure is recorded once and is never retried.
- CED quorum controls whether later council phases may dispatch.
- The consumed one-shot attempt must never be rerun.

### Completion

The endpoint gate passed. Three baselines dispatched, followed by one CED
opening call. Q1 was valid and correct; Q2 and Q3 reached the 1,024-token cap and
were incomplete `INVALID_OUTPUT` JSON fragments. The CED opening returned HTTP 200
but no assistant content, so provider structured-output validity was false, no
CED move was accepted, and quorum stopped the council. Exactly four calls and
zero retries were made for `$0.004614375`, well within the `$8.00` ceiling.

Post-run audit corrected the derivative interpretation: no CED candidate or
answer existed to score, no answer-quality comparison is available, and Q3's
fragment explicitly states actor indeterminacy despite the generated lexical
rubric's `INCORRECT` label. The immutable generated artifacts were not rewritten.

The reduced benchmark itself remains closed and must not be rerun. Its
separately authorized one-call diagnostic is recorded below.

## Q2 CED 4,096-token diagnostic

### Success criterion

Repeat the preserved Q2 CED opening once with only `max_tokens` changed from
1,024 to 4,096; retain exact termination, usage, content, provider-schema, CED,
latency, and cost evidence; classify the original failure without relaxing CED;
then stop with zero retries.

### Gates and stop conditions

1. Hash-lock the prior collection and provider-bound body.
2. Prove the deep request difference is exactly
   `$.max_tokens: 1024 -> 4096`.
3. Freshly validate exact `openai/flex` endpoint capability and the cumulative
   prior-observed-plus-reservation bound under `$8.00`.
4. Exercise the sanitized observability and canonical CED application path
   offline without retaining reasoning text.
5. Consume a distinct stable attempt latch, dispatch at most one POST, never
   retry, persist write-once evidence, classify, and stop.

### Completion

All gates passed. The exact body changed only `max_tokens`; prior body SHA-256
was `8a758dedda1614b46845c79ceab63de102e75a8b9ca5358cdc74ee190b415800`
and diagnostic body SHA-256 was
`51ec1776f26b2de5f0b0218be12d8a514beff6f208036d7e4edb0fadd8601e13`.

One call and zero retries produced HTTP 200, finish `stop` / native
`completed`, 4,327 prompt tokens, 933 completion tokens, 768 reasoning tokens,
and nonempty content. Provider structured output was valid; CED parse was `ok`;
canonical CED application accepted the move. Observed cost was `$0.001473875`,
cumulative reduced-session-plus-diagnostic observed cost was `$0.00608825`, and
latency was `8969.637 ms`.

Verdict: `GENERATION_BUDGET_CONFIRMED`; classification:
`GENERATION_BUDGET_TOO_LOW AT 1024`.

This is the predeclared operational criterion. Because the successful call used
933 completion tokens and the prior failure did not retain finish/native-reason
evidence, it supports budget sensitivity but does not establish a universal
requirement for more than 1,024 tokens.

The evidence supports only a proposal, not an implementation:

- short Socratic moves/openings: 4,096;
- reflection/reconstruction: 8,192;
- synthesis/final response: 16,384.

Status: `PROPOSED_NOT_IMPLEMENTED`. Larger-phase values remain provisional and
require separate validation. The diagnostic latch is consumed, no rerun or
additional live call is authorized, and remaining work is offline reporting
only.

## Normal Socrates live-run preparation

### Success criterion

Prepare the existing normal runner for the proven GPT-5 Mini/Flex path without
creating another architecture phase or approval stop: preserve exact CED
schemas and authority, apply task-aware 4,096/8,192/16,384 output headroom,
prove the complete normal run fits the remaining cumulative budget, retain zero
retries, and make no live call during preparation.

### Completed work

1. Modernized `scripts/run_socrates_live_v1.py`; the reduced benchmark and
   diagnostic runners and latches remain untouched and closed.
2. Added adapter policy-family selection that permits only
   `output_limit_tokens` to vary beneath a 16,384-token authorization envelope.
3. Bound each supported CED task kind to its exact output tier and kept tree
   search disabled.
4. Retained GPT-5 Mini, exact `openai/flex`, seed `0`, omitted temperature and
   reasoning controls, exact task-derived schemas, no fallback, zero transport
   retries, zero parse repair, and CED-owned acceptance.
5. Kept the existing normal-run shape of two homogeneous live workers over four
   logical agents, with no baseline and a mechanically derived 64-call maximum.
6. Proved 50 calls at 4,096, 10 at 8,192, and 4 at 16,384 produce a conservative
   `$3.552256` whole-run bound and `$0.066384` maximum per-call bound, inside the
   exact `$7.99391175` remaining under the cumulative `$8.00` ceiling.
7. Added write-once output and preserved one-use per-turn claims. Direct CLI
   invocation begins the run; there is no new approval gate. A single automatic
   endpoint/question-independent attempt latch prevents a different question or
   fresh endpoint record from resetting the cumulative `$8.00` ledger.
8. Required the fresh exact endpoint to retain the 400,000-token context used
   by P19, closing the possibility that endpoint growth admits more input than
   the per-call reservation prices.

### Stop condition

Preparation is complete. No attempt latch, endpoint GET, or inference was
dispatched. Do not run another diagnostic or the reduced benchmark. A future
normal invocation must retain the prepared policy and current cumulative spend
ceiling.

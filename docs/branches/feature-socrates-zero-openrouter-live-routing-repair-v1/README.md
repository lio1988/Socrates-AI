# Branch: feature/socrates-zero-openrouter-live-routing-repair-v1

Repairs the S7B routing refusal, preserves the bounded GPT-4.1 structured-output
comparison, records the approved reduced GPT-5 Mini benchmark, and records its
separately authorized one-call 4,096-token diagnostic. The accepted diagnostic
now also informs the existing normal Socrates live runner. These are controlled
continuations, not another architecture phase.

Branch working notes: [MEMORY.md](MEMORY.md), [PLAN.md](PLAN.md), and
[PRESENT.md](PRESENT.md).

## Purpose and success criterion

The branch exists to obtain strict, route-bound OpenRouter evidence without
relaxing CED or rewriting predecessor results. Success means that every live
condition is separately authorized, endpoint-validated, bounded by an exact
call and spend ceiling, persisted truthfully, and stopped without retry when a
failure occurs.

## Scope

- the S7B output-token routing repair;
- the completed two-arm GPT-4.1 structured-output experiment;
- the completed one-shot reduced GPT-5 Mini benchmark under an `$8.00` hard
  session ceiling;
- the completed one-call Q2 CED diagnostic that changed only `max_tokens` from
  1,024 to 4,096;
- offline preparation of the existing normal live runner for GPT-5 Mini/Flex,
  with no additional inference call.

## What S7B hit

S7B dispatched one authorized call and received HTTP 404, "No endpoints found
that can handle the requested parameters", with three endpoints available and
none selected.

## The actual cause

Not the provider slug, and not the price ceilings. The documented endpoint
listing shows:

| endpoint tag | `max_tokens` | `max_completion_tokens` |
| --- | --- | --- |
| `azure` | no | yes |
| `openai` | **yes** | no |
| `azure/swedencentral` | **no** | yes |

The request sent `max_tokens: 256` with `require_parameters: true`.
`azure/swedencentral` passed `provider.only` but does not accept `max_tokens`,
and the only endpoint that does — `openai` — was excluded by `provider.only`.
The intersection was empty, so the router refused.

Two things had hidden this: the **model-level** `supported_parameters` is the
union across endpoints and does contain `max_tokens`, and the per-endpoint
pricing differs from the model-level figure ($0.44/$1.76 against $0.40/$1.60).
Only per-endpoint evidence shows either.

## The correction

One documented substitution: `max_tokens` -> `max_completion_tokens`, value 256
unchanged. Everything else identical, and a **new request identity**: the sealed
S4/S5/S6 Route Controls request is not modified.

## Result

HTTP 200, a real model answer, `actual_served_model` ESTABLISHED and equal to the
requested model, S5 mapping accepted, S6 causal binding accepted, observed cost
$0.00004928 against a pre-call bound of $0.5243 and an operator ceiling of $0.60.

## Structured-output follow-up result

The bounded two-arm continuation is complete. Both GPT-4.1-mini and GPT-4.1
returned HTTP 200, satisfied the identical strict provider schema, passed CED
schema validation, and passed the canonical Socratic firewall with one call and
zero retries each. Mini's success classifies the preserved `0/2` prompt-only
control as an interface reliability failure. The full model showed no material
Socratic quality gain in this pair, so the cheaper mini remains preferred.

See [STRUCTURED_OUTPUT_EXPERIMENT.md](STRUCTURED_OUTPUT_EXPERIMENT.md).

## Reduced GPT-5 Mini benchmark result

The prior 972-call / `$655.40` authorization was revoked and was not run. The
replacement authorization allowed at most 151 calls, zero automatic retries,
and `$8.00` total spend. The one-shot run made exactly four calls — three direct
baselines and the first Q2 CED opening call — then CED's quorum stop prevented
the remaining authorized calls. Observed total cost was `$0.004614375`.

Fresh endpoint evidence returned HTTP 200 and selected exactly
`openai/flex` / OpenAI for `openai/gpt-5-mini`, with canonical endpoint name
`OpenAI | openai/gpt-5-mini-2025-08-07`, status `0`, a 400,000-token context,
128,000 maximum completion tokens, and `max_tokens` as the compatible output
limit. The endpoint advertised `response_format`, `structured_outputs`, `seed`,
and `max_tokens`; its recorded prompt/completion prices were `$0.125/M` and
`$1.00/M` tokens.

| condition | observed result |
| --- | --- |
| Q1 direct baseline | HTTP 200; 940 completion tokens; structurally valid; deterministic evaluation `CORRECT`; `$0.000959125` |
| Q2 direct baseline | HTTP 200; hit the 1,024-token cap and ended as incomplete JSON; `INVALID_OUTPUT`; semantic fragment `PARTIALLY_CORRECT`; `$0.001045` |
| Q3 direct baseline | HTTP 200; hit the 1,024-token cap and ended as incomplete JSON; `INVALID_OUTPUT` / unscorable as a complete answer; fragment explicitly states actor indeterminacy; `$0.001045375` |
| Q2 four-seat homogeneous CED condition | Opening call HTTP 200; 1,024 completion tokens; no assistant content; provider structured output invalid; no CED move accepted; quorum failed and dispatch stopped; `$0.001564875` |

The CED result is not a parsed-move rejection: there was no assistant content to
parse, so provider structured validity was false and CED acceptance never
occurred. No synthesis or answer was released.

This run cannot measure model diversity, heterogeneous error correction,
best-of-four performance, or a completed single-versus-homogeneous CED effect.
The heterogeneous and GPT-4.1-mini benchmark conditions were removed to fit the
hard spend ceiling. The consumed one-shot run must not be rerun.

Persisted evidence:

- [collection](runs/reduced_benchmark_collection_v1.json)
- [evaluation](runs/reduced_benchmark_evaluation_v1.json)
- [human-readable report](runs/REDUCED_SOCRATES_BENCHMARK_REPORT.md)
- [post-run scientific audit and interpretation corrections](runs/REDUCED_SOCRATES_BENCHMARK_POSTRUN_AUDIT.md)

The post-run audit is authoritative for interpretation: the generated
evaluation/report incorrectly score absent CED outputs as `INCORRECT`, overstate
comparison availability, and lexically miss Q3's explicit indeterminacy statement.
The original artifacts remain preserved unchanged.

## Q2 CED 4,096-token diagnostic

The separately approved diagnostic repeated the failed Q2 CED opening with one
provider-bound change only:

```text
$.max_tokens: 1024 -> 4096
```

The prior body SHA-256 was
`8a758dedda1614b46845c79ceab63de102e75a8b9ca5358cdc74ee190b415800`;
the diagnostic body SHA-256 was
`51ec1776f26b2de5f0b0218be12d8a514beff6f208036d7e4edb0fadd8601e13`.
Messages, model, provider policy, response schema, seed, streaming setting, and
omitted reasoning parameters remained identical.

Fresh endpoint evidence again selected exact route `openai/flex` / OpenAI for
`openai/gpt-5-mini`, dated endpoint
`openai/gpt-5-mini-2025-08-07`, with `max_tokens` supported and a 128,000-token
endpoint output maximum.

The one authorized call made zero retries and returned HTTP 200 with normalized
finish reason `stop` and native finish reason `completed`. It used 4,327 prompt
tokens, 933 completion tokens, including 768 reported reasoning tokens, and
returned nonempty assistant content. The strict provider schema was valid, CED
parse status was `ok`, and canonical CED application accepted the move.

Exact accepted Socratic move:

> What must be true about (a) how teams were selected into the program, (b) the independent effect of the special training, (c) how productivity was measured and any measurement bias, and (d) other concurrent changes or incentives, for the CEO’s statement “the AI tool caused an 18% productivity increase” to be justified — i.e., which of these premises must hold (and why) before that causal claim can be accepted?

- operator: `expose_premise`
- epistemic marker: `reasonable_hypothesis`
- confidence: `0.65`
- latency: `8969.637 ms`
- diagnostic observed cost: `$0.001473875`
- reduced session plus diagnostic cumulative observed cost: `$0.00608825`

Verdict: `GENERATION_BUDGET_CONFIRMED`; classification:
`GENERATION_BUDGET_TOO_LOW AT 1024`. Because the accepted response completed
below the 4,096-token ceiling, the evidence supports a phase-aware budget
proposal of 4,096 for short Socratic moves/openings, 8,192 for
reflection/reconstruction, and 16,384 for synthesis/final response. At the end
of the diagnostic itself this was `PROPOSED_NOT_IMPLEMENTED`; it is now wired
into the existing normal runner, while the 8,192/16,384 values remain
provisional and have not yet been observed in a live run.

That classification follows the predeclared one-call criterion. The successful
completion used 933 tokens, below 1,024, and the earlier failed call did not
retain finish/native-reason evidence. The result therefore supports budget
sensitivity in this controlled rerun; it does not prove that more than 1,024
tokens are intrinsically required on every run.

Persisted diagnostic evidence:

- [collection](runs/q2_ced_4096_diagnostic_collection_v1.json), SHA-256
  `99941193dcfc024780a0b47be1b1042dd30db65814dc2ae97a8bf7cae8f8a25c`
- [report](runs/Q2_CED_4096_DIAGNOSTIC_REPORT.md), SHA-256
  `91e3d1b13c43eda1ff14898d1076830520437db88376069200ac9467eade913a`

The diagnostic attempt latch is consumed. Do not rerun it. No runtime policy was
changed during that diagnostic and no push is authorized.

## Normal Socrates live-run preparation

The existing `scripts/run_socrates_live_v1.py` is ready for one ordinary CED
dialogue on `openai/gpt-5-mini`, pinned to `openai/flex`. It now performs a
fresh exact-endpoint capability check inline, uses the exact task-derived CED
JSON Schemas, exposes only Alpha/Beta worker aliases, keeps CED as sole
transition authority, and sets both transport retries and CED parse repair to
zero. The fresh endpoint must retain the exact 400,000-token context bound used
by P19; a larger or smaller context is refused before any POST.

The runner has two homogeneous live workers and four logical CED agents, which
is the pre-existing normal-run shape. Its mechanically derived maximum is 64
calls with no baseline. Output reservations are 4,096 for short/question,
critique, scoring, and ratification tasks; 8,192 for initial, reflection, and
reconstruction tasks; and 16,384 for synthesis drafts. The resulting exact
structural distribution is 50 / 10 / 4 calls respectively.

Using the retained 400,000-token input bound and price ceilings, the
conservative full-run bound is `$3.552256`. The largest single-call bound is
`$0.066384`. Both fit within the exact `$7.99391175` remaining beneath the
unchanged cumulative `$8.00` ceiling after the prior observed `$0.00608825`.

Preparation was offline only: no endpoint GET, credential read, inference,
claim consumption, or output artifact occurred. The reduced benchmark and the
diagnostic remain closed and are not reused. Normal execution is a direct CLI
invocation, not another phase or approval gate. That invocation automatically
consumes one endpoint/question-independent write-once attempt latch, so a new
question or changed endpoint listing cannot reset the cumulative `$8.00`
authorization.

## Non-goals

No change to sealed predecessor evidence. No retry or rerun of any prior call.
No change to CED authority. No claim about heterogeneous-model benefits. No
normal live inference during preparation. Not pushed.

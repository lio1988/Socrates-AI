# Current branch state

- Branch: `feature/socrates-zero-openrouter-live-routing-repair-v1`
- Q2d base remote HEAD: `020a675504f14fb559ea91a6223eaf00ee45c806`
- Pre-experiment HEAD: `2f304c0af45ed6bccda64f5d3da42796db0f5935`
- Tested harness freeze HEAD: `283eb384813cb54dd8e6b2c1ee9c6640814942eb`
- GPT-4.1 structured-output treatment calls: `2` (exactly one per arm)
- Reduced GPT-5 Mini benchmark calls: `4` (three baselines plus one CED
  opening)
- Reduced benchmark automatic retries: `0`
- Reduced benchmark observed total cost: `$0.004614375` under the `$8.00`
  hard ceiling
- Q2 CED 4,096 diagnostic calls: `1`
- Q2 CED 4,096 diagnostic automatic retries: `0`
- Diagnostic observed cost: `$0.001473875`
- Reduced benchmark plus diagnostic cumulative observed cost: `$0.00608825`
- Normal Socrates live-run inference calls: `0` (prepared only)
- Remaining cumulative spend ceiling for a normal invocation: `$7.99391175`

## Completed

- Preserved and hash-locked both prompt-only controls at CED acceptance `0/2`.
- Reconstructed the exact run-003 question, task, prompt, context, body digest,
  and request identity.
- Mechanically generated the strict provider schema and proved the required
  `content.epistemic_marker` nesting against existing CED enums and frozen
  recorded field sets.
- Added exact-endpoint capability, endpoint-compatible output-token, price,
  write-once evidence, and one-dispatch gates.
- Kept provider schema validity, CED schema acceptance, and canonical Socratic
  acceptance separate.
- Verified mocked HTTP-200 success and refusal paths retain all primary metrics.

## Reduced benchmark completion

- The revoked 972-call / `$655.40` benchmark was not run.
- Fresh endpoint discovery returned HTTP 200 and selected exact route
  `openai/flex` / OpenAI for `openai/gpt-5-mini`, canonical endpoint
  `openai/gpt-5-mini-2025-08-07`, status `0`, 400,000 context tokens, 128,000
  maximum completion tokens, and endpoint-compatible `max_tokens`.
- The endpoint advertised `response_format`, `structured_outputs`, `seed`, and
  `max_tokens`. Its recorded prompt/completion rates were `$0.125/M` and
  `$1.00/M` tokens.
- Q1 baseline: HTTP 200, 940 completion tokens, structurally valid, objective
  evaluation `CORRECT`, observed cost `$0.000959125`.
- Q2 baseline: HTTP 200, 1,024 completion tokens, truncated as incomplete JSON,
  `INVALID_OUTPUT`, semantic fragment `PARTIALLY_CORRECT`, observed cost
  `$0.001045`.
- Q3 baseline: HTTP 200, 1,024 completion tokens, truncated as incomplete JSON,
  `INVALID_OUTPUT` / unscorable as a complete answer; its fragment explicitly
  states actor indeterminacy despite the generated lexical `INCORRECT` label;
  observed cost `$0.001045375`.
- Q2 CED opening: HTTP 200, 1,024 completion tokens, no assistant content,
  provider structured output invalid, no CED move/parser acceptance, observed
  cost `$0.001564875`. Opening quorum failed, so no additional CED call,
  synthesis, ratification, or answer release occurred.
- The run consumed four calls, made zero retries, settled every observed cost,
  and closed collection without a fatal session-stop condition.

Persisted results:

- [reduced benchmark collection](runs/reduced_benchmark_collection_v1.json)
- [reduced benchmark evaluation](runs/reduced_benchmark_evaluation_v1.json)
- [reduced benchmark report](runs/REDUCED_SOCRATES_BENCHMARK_REPORT.md)
- [post-run scientific audit](runs/REDUCED_SOCRATES_BENCHMARK_POSTRUN_AUDIT.md)

## Scientific scope

The direct baselines were observed on Q1-Q3, but the intended single-versus-
homogeneous comparison on Q2 was not completed because CED stopped at opening.
This run cannot estimate diversity effects, heterogeneous error correction,
best-of-four performance, or the benefit of a completed homogeneous council.
Those conditions were outside the reduced authorization.

The post-run audit corrects the generated derivative interpretation: absent CED
candidate/final outputs are not substantive `INCORRECT` answers, and the Q2
answer-quality comparison is unavailable. Original artifacts remain unchanged.

## Q2 CED 4,096 diagnostic completion

- The diagnostic changed exactly `$.max_tokens` from 1,024 to 4,096. Prior body
  SHA-256:
  `8a758dedda1614b46845c79ceab63de102e75a8b9ca5358cdc74ee190b415800`;
  diagnostic body SHA-256:
  `51ec1776f26b2de5f0b0218be12d8a514beff6f208036d7e4edb0fadd8601e13`.
  Messages, response schema, model, provider policy, seed, stream setting, and
  omitted reasoning parameters remained unchanged.
- Fresh endpoint GET returned HTTP 200 and selected `openai/flex` / OpenAI for
  `openai/gpt-5-mini`, dated endpoint
  `openai/gpt-5-mini-2025-08-07`. The endpoint supported `max_tokens` and up to
  128,000 output tokens.
- Exactly one call and zero retries returned HTTP 200, finish reason `stop`,
  native finish reason `completed`, and `CONTENT_NONEMPTY_STRING`.
- Usage: 4,327 prompt tokens, 933 completion tokens, 768 reasoning tokens;
  completion details were
  `{"audio_tokens": 0, "image_tokens": 0, "reasoning_tokens": 768}`, and the
  4,096-token limit was not reached.
- Provider structured output was valid. CED parse status was `ok`; canonical CED
  application accepted the Socratic move.
- Exact accepted question (verbatim):

  > What must be true about (a) how teams were selected into the program, (b) the independent effect of the special training, (c) how productivity was measured and any measurement bias, and (d) other concurrent changes or incentives, for the CEO’s statement “the AI tool caused an 18% productivity increase” to be justified — i.e., which of these premises must hold (and why) before that causal claim can be accepted?
- Accepted move: operator `expose_premise`, epistemic marker
  `reasonable_hypothesis`, confidence `0.65`.
- Latency: `8969.637 ms`. Diagnostic observed cost: `$0.001473875`. Reduced
  session plus diagnostic cumulative observed cost: `$0.00608825`.
- Verdict: `GENERATION_BUDGET_CONFIRMED`; classification:
  `GENERATION_BUDGET_TOO_LOW AT 1024`.
- Scientific caveat: this is the predeclared operational verdict. The successful
  completion used 933 tokens, below 1,024, and the earlier failure lacks retained
  finish/native-reason evidence. The result supports budget sensitivity; it does
  not prove a universal intrinsic requirement above 1,024 tokens.
- Phase-aware proposal: 4,096 for short Socratic moves/openings, 8,192 for
  reflection/reconstruction, and 16,384 for synthesis/final response. Status:
  `PROPOSED_NOT_IMPLEMENTED`; no runtime or CED policy changed.
- No hidden reasoning text or reasoning-details payload was retained.

Persisted diagnostic evidence:

- [collection](runs/q2_ced_4096_diagnostic_collection_v1.json), SHA-256
  `99941193dcfc024780a0b47be1b1042dd30db65814dc2ae97a8bf7cae8f8a25c`
- [report](runs/Q2_CED_4096_DIAGNOSTIC_REPORT.md), SHA-256
  `91e3d1b13c43eda1ff14898d1076830520437db88376069200ac9467eade913a`

## Normal Socrates live runner prepared

- Diagnostics are closed. The reduced benchmark and 4,096 diagnostic were not
  rerun.
- `scripts/run_socrates_live_v1.py` now runs the ordinary CED lifecycle on
  `openai/gpt-5-mini` pinned to exact `openai/flex`, with a fresh endpoint
  capability record acquired inline at execution time.
- The selected endpoint must retain the exact 400,000-token context used by the
  P19 input bound; context drift is refused before any inference.
- The normal run contains no baseline and uses two homogeneous live workers
  (`Alpha`, `Beta`) over four logical CED agents. CED semantics and acceptance
  authority are unchanged.
- Exact CED-derived provider JSON Schemas apply to every supported task.
  Transport retry, CED phase retry, and CED parse repair are all zero/disabled.
- Output policy: 4,096 for short/question, critique, scoring, and ratification;
  8,192 for initial response, reflection, and reconstruction; 16,384 for
  synthesis drafts. Policies are proven identical in every other field.
- Structural maximum: 64 live calls, distributed 50 / 10 / 4 across those
  output tiers. Conservative whole-run bound: `$3.552256`; maximum per call:
  `$0.066384`; exact remaining cumulative ceiling: `$7.99391175`.
- Direct invocation automatically consumes one stable, endpoint/question-
  independent attempt latch before the endpoint GET. It does not pause for
  approval, but it prevents a second question or changed profile from receiving
  a fresh copy of the remaining cumulative budget.
- Preparation crossed no network, credential, provider, model, claim, or
  artifact boundary and consumed no attempt latch. No live inference has been
  made and no push is authorized.

## Verification

`py -3.12 -m pytest tests_dialogues/test_socrates_zero_openrouter_acquisition_structured_socratic_experiment_v1.py tests_dialogues/test_phase18_markers.py tests_dialogues/test_socratic_acceptance_contract.py tests_dialogues/test_socratic_firewall.py -q`

Result: `93 passed in 3.05s`.

Python compilation and `git diff --check` also pass.

Diagnostic-focused verification:

`py -3.12 -m pytest tests_dialogues/test_q2_ced_4096_diagnostic_v1.py -q`

Result: `11 passed in 0.81s`.

Normal-run focused verification:

`py -3.12 -m pytest tests_dialogues/test_socrates_zero_openrouter_acquisition_live_session_v1.py tests_dialogues/test_socrates_zero_openrouter_acquisition_reduced_benchmark_safety_v1.py tests_dialogues/test_socrates_zero_ced_structured_output_v1.py tests_dialogues/test_reduced_socrates_benchmark_v1.py tests_dialogues/test_q2_ced_4096_diagnostic_v1.py -q`

Result: `121 passed in 4.05s`.

Full regression:

`py -3.12 -m pytest tests_dialogues -q`

Result: `3861 passed, 10 skipped in 104.13s`.

Normal-run-only checks inside the live-session test module: `15 passed`.

## Current preparation changes

- `scripts/run_socrates_live_v1.py`: normal GPT-5 Mini/Flex runner, phase-aware
  policies, 64-call/$3.552256 structural envelope, one-invocation latch,
  write-once reporting, and explicit CED outcome fields.
- `backend/dialogues/socrates_zero/openrouter_live_session_adapter_v1.py`:
  task policy selection constrained to output-limit-only changes.
- `backend/dialogues/socrates_zero/openrouter_reduced_benchmark_safety_v1.py`:
  reusable exact expected-output-limit body check; the reduced 1,024 default is
  unchanged.
- `tests_dialogues/test_socrates_zero_openrouter_acquisition_live_session_v1.py`:
  offline locks for task mapping, wire bodies, schemas, endpoint/input bounds,
  cumulative spend, latch behavior, reporting, and write-once refusal.
- Branch `README.md`, `MEMORY.md`, `PLAN.md`, and this file: prepared/not-run
  handoff state.

The worktree remains intentionally dirty with the retained experiment work and
this offline preparation. No normal-run artifact or claim/attempt store exists;
no commit or push was made.

## Next safe step

The normal runner is ready but has not been invoked. Both the reduced benchmark
latch and the separate 4,096 diagnostic latch are consumed; do not rerun either.
When a normal live invocation is made, use the prepared runner directly; do not
insert another phase or approval gate and do not expand to a heterogeneous
council. No push is authorized. The earlier two-arm result remains available in
[STRUCTURED_OUTPUT_EXPERIMENT.md](STRUCTURED_OUTPUT_EXPERIMENT.md).

ARM 1: HTTP 200; provider/CED/Socratic accepted; 4273/71 tokens;
`5016.503 ms`; `$0.00200508`.

ARM 2: HTTP 200; provider/CED/Socratic accepted; 4272/83 tokens;
`1498.043 ms`; `$0.0101288`.

## Q1 multi-model dataset point (2026-08-28)

### Condition A — four independent answers: COMPLETE

One call per family, one shared strict `json_schema` contract
(`reduced_benchmark_direct_answer_v1`). Artifact:
`runs/q1_multimodel_collection_v1.json`. Scored artifact:
`runs/q1_condition_a_scored_v1.json`.

| family | model | score | completion tokens | observed |
|---|---|---|---|---|
| GPT-5 Mini | `openai/gpt-5-mini` | 6/6 | 3202 | $0.0032345 |
| Claude Sonnet 5 | `anthropic/claude-sonnet-5` | 5/6 | 1478 | $0.015996 |
| Gemini 3.7 Flash | `google/gemini-3.7-flash` | 5/6 | 1216 | $0.0012056 |
| GPT-4.1 Mini | `openai/gpt-4.1-mini` | 5/6 | 569 | $0.0011167 |

All four reached the same correct verdict, contradiction and derivation. The
single discriminating criterion was whether minimality was proved with explicit
satisfying assignments; only GPT-5 Mini did. **Q1 is saturated and cannot show
council improvement.**

The evaluator key (`scripts/q1_evaluator_key_v1.py`) is machine-checked before
use: the six statements are unsatisfiable across all 64 assignments, and each of
the six declared removal countermodels satisfies the other five.

A first attempt used `response_format={"type":"json_object"}` and drew HTTP 400
from both OpenAI-family endpoints. That was a harness error, not a provider one;
it is retained at `runs/q1_multimodel_attempt1_json_object_v1.json`.

### Condition C — heterogeneous CED: RAN twice, never ratified

`scripts/run_multimodel_q1_ced_v1.py` builds the two-seat heterogeneous council
(Alpha = GPT-5 Mini on `openai/flex`, Gamma = Gemini 3.7 Flash on
`google-vertex/global/flex`) with per-seat pre-dispatch guards that keep every
structural check of the frozen Flex guard and parameterise only the constants.

Three live attempts, same request shape:

| attempt | artifact | status | calls | observed |
|---|---|---|---|---|
| 1 | `runs/q1_condition_c_heterogeneous_ced_v1.json` | STOPPED_FATAL | 1 | $0.00 |
| 2 | `runs/q1_condition_c_diagnostic_v1.json` | ORCHESTRATION_RETURNED | 7 | $0.018057 |
| 3 | `runs/q1_condition_c_run2_v1.json` | STOPPED_FATAL | 21 | $0.044616 |

#### The first diagnosis recorded here was wrong, and the body proves it

Attempt 1 was attributed to Vertex rejecting the `$ref`/`$defs`/`pattern`/
`const` constructs in the CED move schema. That is disproven. Attempt 3 retained
the actual envelope via `error_retaining_dispatch_v1`:

```
{"error":{"message":"Provider returned error","code":429}}
```

preceded by SSE keep-alive whitespace padding, inside an HTTP 200. The cause is
an upstream **rate limit**, not a schema incompatibility. Gemini compiles the
CED move schema without difficulty and produced 11 accepted moves across the two
runs that got past the first call.

The retained request body sits beside it as
`provider_error_*.request.json`. Request headers never reach that function, so
no credential can be written.

#### Per-seat reliability, two samples

| seat | accepted | rejected | transport/provider failures |
|---|---|---|---|
| GPT-5 Mini | 12 | 0 | 0 |
| Gemini 3.7 Flash | 11 | 4 | 2 (HTTP 429 in an HTTP 200) |

GPT-5 Mini did not fail once across 12 CED tasks spanning
`initial_response`, `elenchus_objection`, `synthesis_draft` and `move_score`.

Gemini's four rejections cluster on the tasks demanding the longest structured
output, and reproduce across runs:

- `socratic_question` at a 13,248-token prompt returned a well-formed envelope
  with an empty body, `{"confidence": 0.95, "content": {}}`, rejected for a
  missing `epistemic_marker`. The same failure occurred in attempt 2.
- `synthesis_draft` twice returned JSON cut off mid-sentence, e.g. ending
  `"The unique minimal inconsistent subset is the"`, rejected as `json parse
  failed`. Usage accounting was absent on both (`0/0` tokens).

Latency on the truncated turns was 15.1s and 20.9s against a 120s bounded
timeout, and no turn in either run exceeded 33s, so transport timeout is ruled
out as the truncation cause.

**Hypothesis, not established:** the truncation is Gemini spending its 16,384
`max_tokens` envelope on reasoning tokens before emitting the visible answer.
The endpoint advertises `reasoning`, `reasoning_effort` and `include_reasoning`,
and the frozen guard forbids all three on the wire, so the run cannot cap or
observe reasoning spend. Testing this needs either a retained `finish_reason` or
a change to what the guard permits; neither was done.

#### Council outcome

Neither completed run ratified.

- Attempt 2: `ratification_status: quorum_failed`, `synthesis_present: false`.
- Attempt 3: `ratification_status: ratification_failed`,
  `synthesis_present: true`, `governing_epistemic_status: unsupported`,
  `release_decision: release_unresolved`.

Both seats independently reached the correct verdict, the correct forced
contradiction and the correct minimal subset inside the dialogue. GPT-5 Mini's
elenchus raised substantive gaps: the formalization convention for the English
quantifier "anyone", and whether the predicates are time-indexed. The council
therefore failed to ratify an answer that both of its seats had already got
right, which is the negative-control result this run was capable of producing.

### Four-seat council: schema-valid noise is indistinguishable from participation

The operator asked for more model families in the live council. Two open-weight
seats were added after a catalog GET and two endpoint GETs:

| seat | model | endpoint | reserved per call |
|---|---|---|---|
| Alpha | GPT-5 Mini | `openai/flex` | $0.066384 |
| Beta | Llama 4 Maverick | `deepinfra/base` | $0.0931072 |
| Gamma | Gemini 3.7 Flash | `google-vertex/global/flex` | $0.09036 |
| Delta | Qwen3 235B | `deepinfra/fp8` | $0.0450112 |

64 calls reserve $4.7177984. Slugs were read from the catalog, never guessed,
and each seat is pinned to an endpoint that advertises all four wire parameters
a CED seat emits. That filter was not cosmetic: Qwen's `alibaba` endpoint has no
`structured_outputs`, and `venice`, `streamlake` and Llama's `digitalocean` have
no `seed`. Artifact: `runs/q1_condition_c_four_seat_v1.json`, 5 calls, $0.003522.

**All four seats routed correctly.** The run is nevertheless a stop, for a reason
worth more than the run.

#### Llama and Qwen emitted schema-valid placeholder content, and CED accepted it

Llama 4 Maverick, `initial_response`, 91 completion tokens, `finish_reason: stop`:

```json
{"commitments": ["S", "R", "T"], "contradictions": ["S", "R", "T"],
 "critique_summary": "I", "logic_gaps": ["S", "R", "T"],
 "weak_assumptions": ["S", "R", "T"], "epistemic_marker": "logical_inference"}
```

Qwen3 235B, `initial_response`, 88 completion tokens, `finish_reason: stop`:

```json
{"commitments": ["M", "T", "U", "V", "W", "X"],
 "key_insights": ["M", "N", "O", "P", "Q", "R"],
 "synthesis_draft": "M", "unresolved_tensions": ["S"]}
```

Both moves were **accepted**. Neither was truncated; both stopped naturally. On
the same question in Condition A these families were never tested, but GPT-5
Mini in the same session produced a substantive opening move asking the council
to commit to a formalization convention for the English quantifier.

The cause is structural, not a provider defect. The only content constraint the
CED move schema places on a string is `minLength: 1` with `pattern: "\S"`. A
single letter satisfies both. **The move contract can enforce shape and cannot
enforce substance**, so a model that cannot meet the contract degrades into
filling required slots with one character each and is indistinguishable, to the
validator, from a model that reasoned.

This matters beyond these two models: it means council size cannot be increased
by adding weaker seats, and that `ced_move_accepted: true` is not evidence that a
seat contributed anything. Any measurement of council value computed over
accepted moves is confounded by this until the contract can reject noise.

#### The Gemini seat is provider-unreliable, and the reasoning-token theory was wrong

Gemini failed in all four runs. The `finish_reasons.jsonl` trace now settles why:

```
google/gemini-3.7-flash   finish=error   prompt=0  completion=0  reasoning=0
```

`finish_reason: error`, not `length`. The earlier hypothesis recorded above —
that Gemini was spending its 16,384-token envelope on reasoning tokens before
emitting the visible answer — is disproven. A second Gemini call in the same run
returned the same HTTP 429 envelope as before. The Vertex flex endpoint is
refusing this traffic pattern; the model is not failing the contract.

For contrast, in the same run: GPT-5 Mini `finish=stop`, 1454 completion tokens,
1216 of them reasoning. Llama `finish=stop`, 91 tokens, 0 reasoning. Qwen
`finish=stop`, 88 tokens, 0 reasoning.

#### Where this leaves the council

Of five candidate seats, exactly one has produced substantive CED moves without
failure: GPT-5 Mini, 12 for 12 across the two-seat runs. Claude Sonnet 5 is
unaffordable as a seat at $0.96 reserved per call. Gemini is provider-unreliable.
Llama and Qwen satisfy the schema without participating.

The separation experiment therefore has not been run, and adding families did not
advance it. It still needs a council whose seats all demonstrably participate.

### Functional live council: RATIFIED

Seats were rechosen on measured behaviour rather than family count: Alpha =
GPT-5 Mini on `openai/flex`, Beta = GPT-4.1 Mini on `azure/swedencentral`. Both
produced substantive Condition A answers and neither has had a transport
failure. Gemini, Llama and Qwen are excluded for the reasons recorded above.

Two changes made the run possible without weakening anything:

1. **The input bound is now enforced instead of assumed.** `max_input_tokens`
   was only ever used to compute the cost reservation and was never checked
   against the prompt. Reserving against the endpoint's 400,000-token context
   made this council cost $8.68 against an $8.66 balance. Rather than lower the
   number and call it conservative, `assert_input_within_bound_v1` now refuses
   any turn whose rendered messages exceed the declared bound, counting
   characters against a token budget (a BPE token spans at least one character,
   so characters <= N gives tokens <= N). At 128,000 that is roughly nine times
   the largest prompt ever observed here, fails closed, and drops the
   reservation to $3.76127488 for 64 calls.
2. **The output-limit key is read per endpoint.** Flex uses `max_tokens`, Azure
   uses `max_completion_tokens`. The guard asserted `max_tokens` unconditionally,
   which would have refused the Azure seat — the same capability-intersection
   mistake that refused the S7C route.

| run | artifact | status | calls | observed |
|---|---|---|---|---|
| 1 | `runs/q1_council_openai_pair_v1.json` | quorum_failed, no synthesis | 17 | $0.0861134 |
| 2 | `runs/q1_council_openai_pair_v2.json` | **ratified** | 45 | $0.08647703 |

Run 2: 45 of 45 moves accepted, zero rejections, zero repairs, zero failed
providers, all five phases proceeded. `ratified: true`, `synthesis_present:
true`. Run 1 had the same clean per-turn record and still failed quorum, so
run-to-run variance in whether the dialogue completes is real and unexplained;
`audit_summary` retention was added after run 1 and is what made run 2
interpretable.

#### The dialectic did the thing it exists to do

During elenchus, Beta claimed the minimal inconsistent subset is {1,3,4,5,6} —
that premise 2 is dispensable. That is **wrong**. Alpha refuted it with a
concrete countermodel: `C=T, A_R=T, A_S=T, I_T=F, E=F, F=F` satisfies 1,3,4,5,6
while falsifying 2, so the five-premise set is satisfiable and cannot be
inconsistent. The synthesis records this as its `crucial_stress_test` and
concludes all six premises are needed.

That countermodel is character-for-character the one in the independently
written evaluator key for removing premise 2. An error was introduced, caught,
and refuted with the correct formal object — which is what a council is for.

#### It still did not beat the best single model

Scored against the same six criteria as Condition A, the ratified synthesis
earns verdict, contradiction, derivation and subset, and justifies removals in
prose. It exhibits **one** explicit countermodel, for premise 2 — the one it was
forced to produce by Beta's objection.

GPT-5 Mini answering **alone** in Condition A produced six explicit
countermodels, one per removal, all matching the key: 6/6.

So on this question the council lands at 5/6 against 6/6 for its own strongest
seat working alone. It also returned `governing_epistemic_status: unresolved`
and `release_decision: release_unresolved`, declining to call the matter settled
because no mechanized proof was attached, while all four independent models
answered correctly and confidently.

The council converts a wrong objection into a correct refutation, and pays for
it by producing a less complete proof of minimality than one seat produces on
its own. On a question this saturated that is the whole measurable effect.

### Low-cost heterogeneous council: ran to completion, did not ratify

Operator-approved four-seat run, one dialogue, 64 calls, hard bound $1.65675008.
Artifacts: `runs/q1_lowcost_heterogeneous_ced_v1.json` and its
`_analysis.json`. Every seat validated at endpoint level before any inference.

| Seat | Model | Endpoint | Output field | temp | Price in/out per M |
|---|---|---|---|---|---|
| Alpha | `openai/gpt-5-mini` | `openai/flex` | `max_tokens` | absent | $0.125 / $1.00 |
| Beta | `qwen/qwen3-32b` | `deepinfra/fp8` | `max_tokens` | yes | $0.08 / $0.28 |
| Gamma | `meta-llama/llama-4-scout` | `deepinfra/fp8` | `max_tokens` | yes | $0.10 / $0.30 |
| Delta | `openai/gpt-4.1-mini` | `azure/swedencentral` | `max_completion_tokens` | yes | $0.44 / $1.76 |

The operator's Seat C slug `meta-llama/llama-4-scout-17b-16e-instruct` is absent
from the catalog and was approved as `meta-llama/llama-4-scout`. Cheaper
endpoints were rejected for cause: Qwen `siliconflow/fp8` and `groq` lack `seed`
and `structured_outputs` respectively, Llama `novita/bf16` lacks both
`response_format` and `structured_outputs`.

Result: `ORCHESTRATION_RETURNED`, 64 of 64 calls, zero failures, zero
rejections, zero repairs, all five phases proceeded, **but
`ratification_status: ratification_failed`**, `ratified: false`,
`governing_epistemic_status: unresolved`, `release_unresolved`.

#### Two of four seats were accepted without contributing anything

| family | substantive moves | placeholder moves | novel useful | redundant |
|---|---|---|---|---|
| GPT-5 Mini | 3 | 0 | 2 | 1 |
| Qwen3 32B | 0 | 3 | 0 | 0 |
| Llama 4 Scout | 0 | 4 | 0 | 0 |
| GPT-4.1 Mini | 2 | 0 | 0 | 2 |

Qwen3 32B, `initial_response`, 626 completion tokens, accepted:

```json
{"commitments": ["M","1","2","4","5","6"], "key_insights": ["M","1","2","4","5","6"],
 "synthesis_draft": "M", "unresolved_tensions": ["M"]}
```

Llama 4 Scout, `socratic_question`, accepted: `{"question": "M"}`. Its
`synthesis_draft` set `core_answer`, `final_verdict`, `nuance`, `blind_spots`
and `crucial_stress_test` each to `"A"`.

Neither was truncated and neither was rejected. Qwen spent 626, 1021 and 571
completion tokens producing these, so the collapse to placeholders is a choice
the model makes under the contract, not an output cap. This reproduces the
Maverick and 235B result at a smaller scale and confirms it is a property of the
contract meeting weaker models, not of one provider.

The scoring tasks (`move_score`, `section_score`) carry numeric fields only, so
the analysis marks them `EMPTY` for every family including GPT-5 Mini. That is a
classifier artifact and not a finding.

#### Logic score of the final synthesis: 14 / 18

Verdict 2/2, keyed contradiction 2/2, derivation 4/4, minimal subset 3/3,
explosion restraint 1/1, minimality proof **2/6** — the synthesis states outright
that the transcript gave "informal sketches" rather than explicit witness models
for the six removal cases, and supplies none.

One error flag fires: **SEMANTIC_ESCAPE_HATCH_INTRODUCED**. The council spent its
`crucial_stress_test` slot arguing that premise 3 might be a defeasible or
non-contraposable conditional, under which `Filed(Mira)=true` avoids the
contradiction — despite the question instructing ordinary classical logic. The
verdict survives ("under the problem's explicit instruction ... the inconsistency
and minimality claim stand firmly"), but the most heavily weighted objection slot
went to an escape hatch rather than to the logic. No other flag fires:
contraposition and disjunction elimination are used validly, the subset is
correct, and no explosion.

#### Comparison

There is **no retained homogeneous GPT-5 Mini CED run on this corrected
question**, so the comparison named in the brief cannot be made and is not
faked. What is validly comparable — identical question, identical CED contract,
identical budgets, same session — is the two-seat OpenAI-family council:

| | 2-seat OpenAI pair | 4-seat low-cost |
|---|---|---|
| calls | 45 | 64 |
| observed | $0.086477 | $0.061192 |
| ratified | **yes** | no |
| logic score | 15/18 | 14/18 |
| explicit countermodels | 1 | 0 |
| escape hatch introduced | no | yes |
| seats contributing substance | 2 of 2 | 2 of 4 |

The two-seat run scored its minimality point by being forced to: Beta claimed
the minimal subset was {1,3,4,5,6}, and Alpha refuted it with the exact
countermodel from the evaluator key. In the four-seat run no seat mounted a
comparable challenge, because the two extra seats emitted placeholders, and the
strongest objection on record became a semantic hedge instead.

Adding two cheap families cost 19 more calls, produced zero substantive moves
from those families, lost ratification, and moved the score down one point.

### Semantic contribution floor

`ced_move_accepted: true` did not mean a seat contributed anything. The move
contract constrained strings only by "non-empty", so a model unable to meet a
contract filled every required field with one letter and was recorded as
participating. Across two size classes and four open-weight seats this happened
on every substantive move they made.

The floor lives in `backend/dialogues/semantic_floor.py` and is a deterministic
combination, not a length rule, because a length rule alone admits
`"AAAAAAAAAAAAAAAAAAAAAAAAAAAA"`:

| type | applies to | requires |
|---|---|---|
| substantive | authored propositions | >=24 chars, >=4 words, >=4 **distinct** words, >=3 words of >=3 letters, >=8 distinct letters |
| interrogative | `question`, `remaining_question` | the above **and** contains `?` |
| quoted span | `cited_spans` | >=8 chars, >=2 distinct words, >=6 distinct letters |

Fields are **allowlisted**, so identifier-carrying fields are safe by
construction: `commitment_id`, `ref_id`, `status`, `target_section` and the
`commitments_retained` / `commitments_withdrawn` id lists are never checked.
Numeric scoring payloads pass untouched.

#### Where it is enforced, and why not where it belongs

The floor was first placed in the provider-schema layer. On a live rerun it
fired on **all seven** placeholder moves and every one was still recorded
`ced_move_accepted: true`, because that layer is explicitly "provider-schema
evidence, not CED authority".

Moving it to `parse_and_validate_move` broke 53 tests, correctly: the repository
documents a deliberate separation in which the parser accepts an empty question
and `validate_socratic_content` rejects it downstream. That downstream contract
is the architecturally right home.

It is not the home used, because `backend/dialogues/socratic.py`,
`provider_registry.py` and `ced.py` are all under the canonical-successor blob
lock (34 frozen blobs). Enforcement therefore sits in
`SocratesLiveOpenRouterAdapter`, immediately after `accepted` is computed: a move
that asserts nothing is turned into a `SCHEMA_ERROR` and never reaches the
council. CED semantics are untouched and no frozen blob changes. Relocating the
floor into `validate_socratic_content` remains the better end state and needs
its own authorization to update the lock.

A related trap worth recording: writing a frozen file with Python's
`write_text` converted `provider_registry.py` from LF to CRLF, changed 635 lines
with no semantic difference, and broke the blob lock immediately. Restored from
git; the lock did its job.

#### Regression fixtures

`tests_dialogues/test_socrates_zero_ced_semantic_floor_v1.py`, 34 tests. Every
MUST-REJECT fixture is a verbatim value a live model returned and CED accepted:
`"M"`, `"W"`, `"A"`, `"S"`, `"R"`, `"T"`, `"I"`, `"N"`, `"1"`, `"O"`, plus the
whole `{"question": "M"}` and `{"commitments": ["M","1","2",...]}` bodies. Seven
padding evasions are pinned too, so a future relaxation to a bare `minLength`
cannot pass unnoticed. MUST-ACCEPT fixtures are real substantive moves.

One of these tests initially passed for the wrong reason, catching a
`ValidationError` from a malformed `AgentTask` rather than the floor; it now
builds its task from the module's own representative set.

Two field classifications were wrong and the existing suite caught both:
`cited_spans` holds quotations ("Managers voluntarily apply" is genuine), and
`commitments_retained` / `commitments_withdrawn` hold ids ("c1").

Full suite: **3902 passed, 10 skipped, 0 failed.**

### The fair test: cheap seats fail the contract rather than rise to it

Four live attempts with the floor enforced, identical question, identical seats.
Artifacts `runs/q1_lowcost_heterogeneous_ced_v3..v6_enforced.json`.

| attempt | calls | observed | outcome |
|---|---|---|---|
| v3 | 1 | $0.00 | Llama HTTP 429 on the solo opening seat |
| v4 | 1 | $0.00 | Llama HTTP 429 again |
| v5 | 1 | $0.00056736 | Qwen opening **rejected by the floor** |
| v6 | 4 | $0.006594155 | opening passed, quorum lost in initial_response |

The two 429s carried a fully explanatory body once retention was in place:
`engine_overloaded`, `limit_source: upstream_provider_shared_pool`, for
`meta-llama/llama-4-scout-17b-16e-instruct` on DeepInfra. That is the operator's
original Seat C slug, which incidentally confirms `meta-llama/llama-4-scout` was
the same model and the right pin.

#### v5: the floor's first live rejection

```
qwen/qwen3-32b · socratic_question · HTTP 200 · 508 completion tokens
{"confidence": 0.95, "content": {"operator": "induce_aporia", "question": "1"}}
→ ced_move_accepted: false
→ semantic contribution floor: question: needs at least 24 characters (received '1')
```

508 tokens of computation, emitting the character `"1"`. Before the floor this
was an accepted Socratic move and counted as a diversity contribution.

#### v6: the decisive round

| phase | seat | model | result |
|---|---|---|---|
| opening | Delta | GPT-4.1 Mini | **accepted** — asked whether statement 2's "either/or" is inclusive |
| initial_response | Alpha | GPT-5 Mini | **accepted** — 3296 tokens, substantive commitments |
| initial_response | Beta | Qwen3 32B | **rejected** — 885 tokens, `{"commitments": ["M","M","M","M","M"], "documentation_gaps": ["M","M","M","M","M"]}` |
| initial_response | Gamma | Llama 4 Scout | HTTP 429 |

One of three providers survived the round; quorum needs two, so the dialogue
stopped.

#### What this settles

The question the floor was built to answer was whether Qwen and Llama would
produce substantive moves once the contract stopped accepting placeholders. The
answer is no. Qwen3 32B saw `minLength: 24` on the wire, spent 885 completion
tokens, and returned five copies of `"M"`. Forcing the contract does not make a
model meet it; it makes the failure visible instead of silent.

The contract is not the problem: GPT-4.1 Mini and GPT-5 Mini both produced
substantive, accepted moves in that same round under that same contract.

Across every run in this branch, four open-weight seats spanning two size
classes — Qwen3 32B, Qwen3 235B, Llama 4 Scout, Llama 4 Maverick — produced
**zero** substantive CED moves. They are not viable CED workers, and that is now
measured rather than inferred from schema acceptance.

The prior "successful" 64-call heterogeneous dialogue was two working seats plus
two seats writing single letters, scored as full participation. That reading is
retired.

### Q2: an ethics question that finally discriminates

Q1 was saturated at 4/4, so it could not measure a council. Q2 is a moral
argument with a *determinate* structural error, which is the only way an ethics
question can have a scoreable right answer. A transplant committee argues from
"a fair rule ignores no reasonable criterion" to "a fair rule must place first
every patient who tops any criterion" — silently strengthening sensitivity into
decisiveness at step 4. Question and machine-checked key:
`scripts/q2_ethics_question_v1.py`; the key constructs the countermodel and
verifies exhaustively that premises 1-3 hold, step 4 fails, and the rule has a
unique winner. That check caught a defect in the first draft, where two patients
tied.

Three traps, each with a determinate answer: the scope equivocation; a morally
attractive conclusion ("no allocation rule is fair" reads as admirable humility
about rationing); and the fallacy fallacy, since invalidity leaves the
conclusion unproven rather than refuted.

#### Independent answers, 23-point rubric

| model | score | completion tokens | cost |
|---|---|---|---|
| **Gemini 3.7 Flash** | **23/23** | 1369 | $0.001366 |
| Claude Sonnet 5 | 19/23 | 3226 | $0.033750 |
| GPT-5 Mini | 19/23 | 3709 | $0.003753 |
| GPT-4.1 Mini | 12/23 | 228 | $0.000557 |

A 12-to-23 spread, so the question measures something. The cheapest model won,
at one twenty-fourth of Claude's cost.

A trap fired that was **not designed in**, recorded as discovered:
`NECESSARY_CONDITION_READ_AS_SUFFICIENT`. Premise 3 says a rule is fair *only
if* it ignores no criterion. GPT-5 Mini and Claude both built a valid
countermodel and then wrote that their rule *is* fair — Claude explicitly ("by
the committee's own definition, R is fair"), GPT-5 Mini after first stating the
fallacy-fallacy principle correctly and then contradicting it one sentence
later.

#### The council

Seats chosen on measured Q2 behaviour: Alpha GPT-5 Mini (19), Beta Gemini 3.7
Flash (23), Gamma GPT-4.1 Mini (12). Claude was excluded on arithmetic, not
ability — it reserves $0.294912 per call, so sixteen calls alone are $4.72
against the operator's $5.00 ceiling. Bound $2.36548096; observed $0.0438964075
over 12 calls. Artifact `runs/q2_ethics_council_v1.json`.

The dialogue ran opening, initial_response, elenchus, reflection and a second
elenchus with **12 of 12 moves accepted, zero rejections**, then stopped:
`quorum_failed` at reconstruction, where the Gemini seat failed with no response
body and was the only provider assigned to that phase. No synthesis, so there is
no final council answer to score against the rubric.

**What the moves themselves show, which is the part worth having:**

* **GPT-4.1 Mini improved.** Alone it scored 12/23 with no countermodel and no
  answer to the fourth question. Inside the council it committed to a
  countermodel *and* stated the fallacy-fallacy point outright: "The failure of
  the argument's validity does not show that no fair rule can exist." Its
  reflection then adopted the concrete two-patient weighted-sum countermodel
  from the dialogue. Both things it omitted alone, it produced here.
* **Gemini contributed something no independent answer contained.** In
  reflection it distinguished the two failure modes: if the committee really
  meant the strong reading, "their argument does not commit a modal fallacy but
  instead begs the question by stipulating an impossible definition of fairness
  directly into premise (3)". No solo answer drew that distinction.
* **GPT-5 Mini's slip was partly repaired.** Its public commitment stated the
  fallacy-fallacy point cleanly and did not reverse it, unlike its solo answer.
  The slip survives in its synthesis draft, which still says "by (3) ... the
  rule is fair".

**What did not happen:** nobody caught the necessary-for-sufficient error. It
survived the whole dialogue uncorrected, in the one place a council should be
strongest — three seats, one of which had avoided the error when working alone.

So on this question the council raised its weakest seat and generated one novel
distinction, while failing to catch an error its own best seat had not made.
That is a real mixed result rather than the confounded one Q1 produced, and it
is the first measurement in this branch where diversity plausibly did something.

### Q2b confirmatory replication: INCOMPLETE, and the blocker was ours

Protocol frozen before the first call in `runs/q2b_frozen_protocol_v1.json`;
every digest re-verified as matching immediately before spending. The
exploratory Q2 run is untouched and remains an exploratory incomplete
trajectory.

#### The observability defect, closed and then immediately useful

Root cause: `execute_bounded_text_turn_v1` built its turn record at the dispatch
boundary, so every refusal before it raised past `turn_records.append` and the
attempt disappeared. The council saw a failed provider; the artifact saw
nothing.

The first fix returned an outcome instead of raising. That was wrong and the
existing suite caught it: an evaluator-canary leak and a duplicate claim
consumption must both hard-stop, and 53 tests depended on it. The shipped fix
attaches the accounting record to the exception and re-raises the original
unchanged, so control flow is identical and only the accounting is added.
Regression coverage in
`tests_dialogues/test_socrates_zero_openrouter_acquisition_terminal_accounting_v1.py`.

**It paid for itself on the first run.** Q2b recorded 14 turn records against 12
consumed calls, and the two extra records name the failure that was invisible
before:

```
socratic_question       pre_dispatch_refusal:pre_dispatch_guard:ContractValidationError
reconstruction_proposal pre_dispatch_refusal:pre_dispatch_guard:ContractValidationError
```

That is **our own input-bound guard**, not the provider. `google-vertex/global`
answered both of its dispatched calls without error. The endpoint migration was
therefore unnecessary, and the reliability story told about Gemini across this
branch was wrong: for a fourth time on this project, a provider was blamed for
something else's failure.

The guard declares a bound of 65,536 *tokens* and enforces it on *characters*.
Characters exceed tokens by roughly 3.7x in this transcript, so the effective
bound is about four times tighter than declared, and it began refusing turns at
around 15,000 prompt tokens. Under the frozen protocol this is not fixed now.

#### Matched baselines, and how unstable they are

| model | Q2b | exploratory Q2 |
|---|---|---|
| GPT-4.1 Mini | **21/23** | 12/23 |
| Gemini 3.7 Flash | 19/23 | 23/23 |
| GPT-5 Mini | **12/23** | 19/23 |

Same question, same schema, same `seed=0`. The ranking inverted end to end.
GPT-5 Mini answered two of the four questions and spent 3116 completion tokens
producing 1543 characters. Gemini named the fallacy fallacy and then undercut it
("positively shows that fair allocation rules can exist"), adjudicated exactly as
GPT-5 Mini's identical pattern was in the exploratory run.

Matched oracle union: **23/23**. No single seat covered everything; the three
together did. Best matched individual: 21/23.

**Single-answer scores on this question are not stable enough to serve as a
baseline for a single-question council comparison.** Run-to-run variance is the
same size as any effect a council could show.

#### What the trajectory shows before it stopped

Five phases proceeded with 12 of 12 dispatched moves accepted, zero rejections.

* **GPT-5 Mini repaired its own baseline failure inside the council.** Alone it
  gave no countermodel and never addressed the fourth question. In its council
  initial_response it produced a countermodel *and* wrote that "(3) is only a
  necessary condition; if the committee intended it as sufficient, they silently
  assumed a stronger principle" — the exact error that went uncaught by the
  entire exploratory council.
* **Gemini formalised the missing premise**, which no independent answer did:
  `[p = argmax Score(q,C,s) ∧ ¬Ignores(R,C)] ⟹ p ∈ Winners_R(s)`.
* **GPT-4.1 Mini adopted that formalisation** in reflection and kept the fallacy
  fallacy intact: "the committee's proof is unsound though its conclusion may
  still be true".

No synthesis, no ratification, no final CED score. Under the frozen
interpretation this is a reliability failure and no final-score comparison
exists. The propagation above is trajectory evidence and does not establish a
causal diversity gain: CED task structure, dialogue context and cross-model
exposure are not separated by this design.

#### Economics

Baselines $0.00628089 over 3 calls; council $0.051430375 over 12 calls. Q2b
total **$0.057711265** against an authorized $3.08363264. Fifteen of 67
authorized calls used. The two pre-dispatch refusals consumed no call and cost
nothing, which the records show as `worst_case_picodollars: 0`.

### Q2c: guard repair confirmed, a different blocker found

Protocol `runs/q2c_frozen_protocol_v2.json`; all six content digests re-verified
immediately before the first call. Q2b remains untouched and incomplete.

#### The unit repair, and the second wrong claim it corrected

Two guards had been wrong. The first compared **characters** against 65,536 — a
number that is Gemini's `data.endpoints[0].max_completion_tokens`, an *output*
field for one seat, used as an *input* bound for all three. The replacement
claimed `prompt_tokens <= character_count` was provable. **It is not.** These
tokenizers work on UTF-8 bytes, so one character can become several tokens; an
emoji is one character and four bytes. A character count can understate tokens,
which is the dangerous direction.

`wire_utf8_byte_upper_bound_v1` bounds tokens by canonical wire UTF-8 bytes,
stated as a documented byte-backed-tokenization assumption rather than exact
counting. Measured on this branch's own receipts the real ratio is neither
constant nor near one — 4.01, 3.99 and 3.20 bytes per token — so no fixed
conversion is used. Endpoints outside the byte-backed allowlist are refused
rather than estimated.

Every limit now carries provenance: context windows 400,000 / 1,048,576 /
1,047,576 from named JSON paths with evidence digests, and GPT-4.1 Mini's
942,818 verified as the `max_completion_tokens` field rather than a derived
remainder. `max_prompt_tokens` is `null` on all three, which is precisely why a
local budget is needed.

The refused-request store was withdrawn before it was ever used. A refused CED
prompt carries the whole dialogue, so persisting it would open a raw-prompt
archive outside this branch's evidence boundary. What is kept is an allowlisted
receipt — digest, sizes, estimator, limits, units — proven by test to exclude
secret-shaped and raw prompt text.

Exact byte-for-byte replay of the Q2b refusal is impossible: only the digest
survived. The claim is stated as a **Q2b scale-faithful reconstructed guard
probe** — 74,108 canonical wire bytes, 74,156 token upper bound, refused by the
old comparison and accepted by the corrected one.

**The repair is confirmed in the live run: zero pre-dispatch refusals, zero
refusal receipts, and the Gemini seat dispatched every call it was given.**

#### The new blocker, precisely classified

13 calls, 13 turn records, $0.058986715. Five phases proceeded; the second
elenchus lost quorum and the dialogue stopped. No synthesis, no ratification.

Two failures, one shared cause:

| turn | seat | finish | completion | reasoning | result |
|---|---|---|---|---|---|
| 7 | GPT-5 Mini | **length** | 4096 | 3264 | `json parse failed` — output cut mid-word |
| 10 | Gemini | stop | 761 | 739 | `epistemic_marker is required` |

The `SHORT_OUTPUT_TOKENS_V1` envelope for elenchus and Socratic tasks is 4,096
tokens, and **reasoning tokens are spent from it**. GPT-5 Mini spent 3,264 of
4,096 on reasoning and was truncated exactly at the cap; Gemini spent 739 of
761, leaving about 22 tokens of visible output and an incomplete object. The
frozen guard forbids `reasoning`, `reasoning_effort` and `include_reasoning` on
the wire, so the run cannot cap or observe that spend.

This was raised as a hypothesis much earlier for Gemini and correctly labelled
unproven at the time. It is now proven, by `finish_reason: length` at exactly
the envelope and per-turn reasoning counts.

#### Result

**Q2c: incomplete.** Under the frozen interpretation that is a reliability
failure and no final CED score exists, so no comparison against the frozen
baselines is made. Budget was not changed to force completion.

The trajectory again showed propagation before it stopped — the
necessary-versus-sufficient point appeared in GPT-5 Mini's opening question and
was carried into GPT-4.1 Mini's elenchus and reflection — but with no synthesis
this remains trajectory evidence and establishes nothing causal.

Spend: $0.058986715 of an authorized $4.26860544. Cumulative $0.651915.

#### Q2c attribution and authorization correction

The statement above that the two failed turns had one shared reasoning-envelope
cause is withdrawn.

- GPT-5 Mini turn 7 ended `length` at 4,096 completion tokens, with 3,264
  reasoning tokens, and returned JSON truncated mid-string. This is
  `completion_envelope_exhausted_before_valid_visible_payload`.
- Gemini turn 10 ended `stop` and returned the complete body
  `{"confidence":0.9,"content":{}}`. The strict wire schema required seven
  content fields. This is `provider_structured_output_contract_violation`;
  neither transport failure nor envelope exhaustion is established.

Q2c was approved against digest
`ee9fa22e32d99f81d80f7865763b241ec05e65b051e4e6b60e3ee83754c816f0`
but executed against
`3b88603b694585f779ffb941d61f1b92da3600237f82b916b09f91c0eef17233`.
The six component digests matched, but the whole manifest did not. Q2c remains
an incomplete historical trajectory and is additionally
**protocol-nonconformant**. It is not a confirmatory replication.

### Q2d frozen offline preflight — NOT AUTHORIZED FOR LIVE EXECUTION

Q2d closes demonstrated local defects without an inference call:

1. exact canonical-manifest authorization before any acquisition boundary,
   rechecked before every dispatch and protected by a fresh one-shot latch plus
   an opaque process-local capability bound once to one live builder;
2. GPT-5 Mini elenchus output raised from 4,096 to 8,192 tokens, with every
   other task/model envelope unchanged;
3. privacy-safe evidence sidecars containing only allowlisted digests, lengths,
   routing metadata, finish reasons, numeric usage, and error classification.

The topology audit also found that Q2b/Q2c placed four logical agents behind
three physical model seats. Alpha served two agents, so two Alpha successes
could satisfy quorum two. Q2d changes this to one logical agent per distinct
model/provider seat. This repairs provider-independent quorum, but it is a
substantive protocol change: **Q2d is a new exploratory reliability run, not a
confirmatory replication**.

The corrected three-provider structural maximum is:

| component | maximum calls |
|---|---:|
| deliberation | 20 |
| move scoring | 40 |
| section scoring | 30 |
| ratification | 3 |
| objection verification | 14 |
| **total** | **107** |

The predeclared session `q2d-ced-hetero-v1` is retained without searching or
optimizing its modulo-three role offset:

| seat | cap distribution | calls | conservative bound |
|---|---|---:|---:|
| Alpha — GPT-5 Mini | 30x4,096; 5x8,192; 1x16,384 | 36 | `$0.770048` |
| Beta — Gemini | 31x4,096; 3x8,192; 1x16,384 | 35 | `$2.0352` |
| Gamma — GPT-4.1 Mini | 32x4,096; 3x8,192; 1x16,384 | 36 | `$2.3789568` |
| **total** |  | **107** | **`$5.18420480`** |

Retained cumulative spend is conservatively rounded to `$0.651915`, making the
required cumulative bound `$5.83611980`. This does not fit the prior `$5.00`
ceiling.

**Q2d live calls: 0. Q2d live spend: `$0.00`.** The next permissible step is
operator approval of canonical protocol SHA-256
`2729d4bd82af1ddc29ba6526daa4cd00ee3132540e01dbee7a73dba723581075`
(32,320 bytes, exact canonical JSON with no BOM or trailing newline) and a
cumulative ceiling of at least `$5.83611980`. Until then the runner fails
closed before credentials, claims, acquisition, or POST. A target Windows
process must reconstruct the same runtime/schema/implementation/evidence
payload byte-for-byte or stop before the attempt latch is consumed.

The final security audit passed with no release blocker under the declared
trusted-local-code threat model. The manifest recursively hashes all 188
`backend/dialogues/**/*.py` and live runtime/control roots, pins source EOLs,
and preserves historical evidence as raw bytes. The fixed run directory is
claimed atomically; every sidecar and final artifact uses exclusive `xb`,
flush, and fsync. Raw HTTP request/response bodies are not retained.

Non-blocking limitations are explicit: malicious in-process reflection,
administrator action, and filesystem/snapshot rollback are outside scope;
ledger/process-counter atomics would need locks if the transport later became
truly concurrent; and returned evidence proves model/provider family while
the exact endpoint slug ultimately relies on OpenRouter honoring the emitted
no-fallback singleton routing controls.

Final verification: 189 focused security tests passed. The full suite
reported 4,301 passed, 1 skipped, and two known environment/history failures
specific to this synthetic POSIX checkout (missing predecessor Git objects and
POSIX interpretation of a frozen Windows path), with no Q2d, authorization, or
privacy failure. The canonical-manifest lock itself passes independently.

### Spend

Condition A: $0.021553. Earlier `json_object` attempt: $0.048012 (two 200s).
Condition C attempt 1: $0.00 (1 call, HTTP 429).
Condition C attempt 2: $0.018057 (7 calls).
Condition C attempt 3: $0.044616 (21 calls).
Four-seat attempt: $0.003522 (5 calls).
OpenAI-pair council run 1: $0.086113 (17 calls).
OpenAI-pair council run 2: $0.086477 (45 calls), ratified.
Low-cost 4-seat council: $0.061192 (64 calls), not ratified.
Floor-inactive rerun: $0.075191 (64 calls).
Enforced attempts v3-v6: $0.007162 (7 calls).
Q2 baselines: $0.039426 (4 calls).
Q2 council: $0.043896 (12 calls).
Q2b matched baselines: $0.006281 (3 calls).
Q2b council: $0.051430 (12 calls, incomplete).
Q2c council: $0.058987 (13 calls, incomplete).
Q2d offline preflight: $0.00 (0 live calls; authorization blocked).
Session total: $0.651915. Five metadata GETs consumed (two authorized
earlier, plus one catalog and two endpoint listings for the open-weight
seats the operator asked for).

# Structured-output controlled experiment

Status: **complete**. Exactly two treatment calls were made, one per declared
arm. Each used a fresh process, one exact-endpoint capability retrieval, one
inference maximum, and zero retries. No further model call was made.

## Preserved control

The two existing GPT-4.1-mini prompt-only runs remain byte-identical and retain
CED schema acceptance `0/2`. Their reproduced failure is a valid
`epistemic_marker` at the top level rather than at
`content.epistemic_marker`. CED was not changed or relaxed.

## Controlled parity

- Question: `Is knowledge merely justified true belief?`
- Role / phase: `socrates` / `opening`
- Endpoint selector: `azure/swedencentral`
- Output field / bound: `max_completion_tokens` / `256`
- Temperature: `0.0`; no `seed`, `top_p`, tools, fallback, or retry
- Identical response-format schema SHA-256:
  `6ca8aafa24c01e8772b1c4be4ef05dfeb32acfa962807d51f92bad6875474bf1`
- Identical user-content SHA-256:
  `d7e83a1dcc151bc80a00f66b6f17254d5235096a63c5cec7e9ac78151a01d0e6`
- Identical dialogue-context SHA-256:
  `f5a2298b1c95d024bc330b2533706c670a457688d1ae9d5ade3a6e154d0d4365`

The exact selected endpoint for each model independently reported healthy
status and support for `response_format`, `structured_outputs`, `temperature`,
and `max_completion_tokens` before its inference.

## Results

| Measurement | ARM 1 | ARM 2 |
| --- | --- | --- |
| Model | `openai/gpt-4.1-mini` | `openai/gpt-4.1` |
| HTTP | `200` success | `200` success |
| Actual model identity | exact match | exact match |
| Provider structured output | valid | valid |
| CED schema | accepted | accepted |
| Canonical Socratic move | accepted | accepted |
| Operator | `distinguish` | `clarify` |
| Epistemic marker | `open_uncertainty` | `reasonable_hypothesis` |
| Confidence | `0.9` | `0.7` |
| Latency | `5016.503 ms` | `1498.043 ms` |
| Prompt tokens | `4273` | `4272` |
| Completion tokens | `71` | `83` |
| Observed cost | `$0.00200508` | `$0.0101288` |
| Dispatches / retries | `1 / 0` | `1 / 0` |

Combined observed cost: `$0.01213388`. GPT-4.1 was `3.349x` faster in this
single observation and cost `5.052x` as much.

## Exact assistant outputs

ARM 1:

```json
{"confidence":0.9,"content":{"epistemic_marker":"open_uncertainty","operator":"distinguish","question":"When we ask if knowledge is merely justified true belief, do we mean that these three conditions are individually necessary and jointly sufficient for knowledge, or that knowledge might require additional conditions beyond justification, truth, and belief?"}}
```

ARM 2:

```json
{"confidence": 0.7, "content": {"epistemic_marker": "reasonable_hypothesis", "operator": "clarify", "question": "When we ask whether knowledge is merely justified true belief, what do we mean by 'justified'—does it require objective evidence, subjective conviction, or something else, and how does this affect whether the definition is sufficient for knowledge?"}}
```

## Non-authoritative semantic comparison

CED is the sole acceptance authority and accepted both moves. The comparison
below is analyst interpretation only.

| Criterion | GPT-4.1-mini | GPT-4.1 |
| --- | --- | --- |
| Grounded in current commitments | Directly restates the JTB proposal | Directly restates it and focuses on justification |
| Useful distinction | Separates individual necessity, joint sufficiency, and additional conditions | Separates objective evidence, subjective conviction, and other accounts of justification |
| Genuine uncertainty | Targets whether JTB is sufficient | Targets what justification means and how that bears on sufficiency |
| Non-leading | Balanced alternatives, though it introduces the additional-condition possibility | Offers candidate meanings but retains “or something else” |
| Avoids answering for the user | Yes | Yes |
| Likely to elicit revision | High: asks the user to clarify the logical strength of the thesis | High: asks the user to refine a central term |
| Beyond a generic philosophical question | Yes; necessary/sufficient structure is specific to JTB | Yes; it links a concrete ambiguity to sufficiency |

The full model does not show a material Socratic capability gain in this single
pair. Its question is useful, but the mini question more directly targets the
central necessary-versus-sufficient structure of the user's claim. Treat the
moves as equivalent accepted moves for model-selection purposes and prefer the
cheaper mini for this role pending broader experiments.

## Interpretation

Because GPT-4.1-mini passed under the exact structured schema, the prior `0/2`
failure is classified as a **prompt-only structured-output reliability failure**,
not a failure of the underlying Socratic semantic move. Schema-compliance gain
and model-capability gain remain separate: this experiment establishes the
former and does not establish the latter.

## Evidence

- ARM 1 artifact SHA-256:
  `d075923a10ef3062a6f632cac2cbb5494f017383061f7f19680a8fe43e9ee251`
- ARM 2 artifact SHA-256:
  `5f408a65fc23f6302248788c16dcc486965b0b29b8a24d09ddb58a0fc4af0e6e`
- Persistent consumed claims after both arms: `4` (attempt + exact body per arm)

# Current branch state

- Branch: `feature/socrates-zero-openrouter-live-routing-repair-v1`
- Pre-experiment HEAD: `2f304c0af45ed6bccda64f5d3da42796db0f5935`
- Tested harness freeze HEAD: `283eb384813cb54dd8e6b2c1ee9c6640814942eb`
- Live treatment calls made in this continuation: `2` (exactly one per arm)
- Automatic retries: `0`

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

## Verification

`py -3.12 -m pytest tests_dialogues/test_socrates_zero_openrouter_acquisition_structured_socratic_experiment_v1.py tests_dialogues/test_phase18_markers.py tests_dialogues/test_socratic_acceptance_contract.py tests_dialogues/test_socratic_firewall.py -q`

Result: `93 passed in 3.05s`.

Python compilation and `git diff --check` also pass.

## Remaining blocker and next safe step

No blocker remains. Both declared arms are complete and no further model call is
authorized. Report the persisted outputs side by side and stop. Detailed result:
[STRUCTURED_OUTPUT_EXPERIMENT.md](STRUCTURED_OUTPUT_EXPERIMENT.md).

ARM 1: HTTP 200; provider/CED/Socratic accepted; 4273/71 tokens;
`5016.503 ms`; `$0.00200508`.

ARM 2: HTTP 200; provider/CED/Socratic accepted; 4272/83 tokens;
`1498.043 ms`; `$0.0101288`.

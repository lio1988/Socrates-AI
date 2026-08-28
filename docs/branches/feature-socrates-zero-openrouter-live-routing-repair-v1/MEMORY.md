# Stable branch memory

- Branch: `feature/socrates-zero-openrouter-live-routing-repair-v1`.
- The two prompt-only GPT-4.1-mini runs are frozen controls. Their CED schema
  acceptance remains `0/2`; neither result may be rewritten or discarded.
- The reproduced failure is a valid marker at the wrong location: top-level
  `epistemic_marker`. CED continues to require `content.epistemic_marker`.
- CED is the sole acceptance authority. Provider JSON-Schema validity, generic
  CED schema acceptance, and canonical Socratic/firewall acceptance are three
  separate observations.
- The provider schema is generated from strict types using the existing CED
  operator and epistemic-marker enums, then checked for exact field and nesting
  parity. It is not a second CED schema.
- The controlled treatment has exactly two no-retry arms: GPT-4.1-mini and
  GPT-4.1, both pinned to `azure/swedencentral` with the same schema, question,
  phase, role, dialogue context, temperature, and output limit.
- Exact endpoint capability is fetched and validated independently for each
  model immediately before its arm. Model-level parameter unions are never
  accepted as endpoint authority.
- Push authorization is branch-scoped: this feature branch may be updated;
  `main` must remain unchanged.
- The completed treatment produced two HTTP-200, provider-valid, CED-accepted,
  Socratic-accepted moves with zero retries. Mini succeeded under structured
  output, so the preserved prompt-only failure is classified as interface
  reliability rather than semantic-move failure.
- This pair establishes no material GPT-4.1 Socratic capability gain. Prefer
  GPT-4.1-mini for the opening Socratic role until broader evidence changes that
  conclusion.

## Reduced benchmark invariants and result

- The 972-call / `$655.40` authorization is void and was not executed. The only
  replacement authorization was at most 151 calls, zero automatic retries, and
  a hard `$8.00` total-session ceiling.
- The approved conditions were three direct `openai/gpt-5-mini` baselines (Q1,
  Q2, Q3) and one four-seat homogeneous GPT-5 Mini CED condition on Q2, all
  pinned to `openai/flex`. Heterogeneous conditions and the GPT-4.1-mini
  benchmark control were removed.
- Fresh exact-endpoint evidence selected `openai/flex` / OpenAI, canonical
  endpoint `openai/gpt-5-mini-2025-08-07`, status `0`, 400,000 context tokens,
  128,000 maximum completion tokens, and endpoint-compatible `max_tokens`.
  Required structured-output parameters were advertised. Recorded prices were
  `$0.125/M` prompt tokens and `$1.00/M` completion tokens.
- The one-shot session consumed exactly four calls and `$0.004614375`: three
  baselines plus one CED opening call. Automatic retries remained `0`; returned
  model and provider bindings passed on all four calls.
- Q1 returned HTTP 200, stayed below the output cap at 940 completion tokens,
  was structurally valid, and evaluated `CORRECT`.
- Q2 and Q3 baselines each returned HTTP 200 but exhausted the 1,024-token cap.
  Both observable strings ended as incomplete JSON and were structurally
  invalid. Treat both as `INVALID_OUTPUT`; Q2's semantic fragment is
  `PARTIALLY_CORRECT`, while Q3 is unscorable as a complete answer and its
  fragment explicitly states that no single person can be conclusively
  identified. The generated Q3 `INCORRECT` label is a lexical false negative.
- The Q2 CED opening returned HTTP 200 and used 1,024 completion tokens, but
  exposed no assistant content. Provider structured-output validity was false;
  no CED move or parser acceptance occurred; opening quorum failed; no further
  council call, synthesis, ratification, or release occurred.
- CED remains the sole acceptance authority. HTTP success, endpoint binding,
  provider structured validity, CED acceptance, and semantic evaluation remain
  separate measurements.
- This run provides no evidence about model diversity, heterogeneous error
  correction, best-of-four performance, or the effect of a completed
  homogeneous council. The intended Q2 comparison was not completed because
  the council stopped at opening.
- The generated evaluation/report incorrectly treat absent CED candidate/final
  outputs as `INCORRECT` and claim Q2 comparison availability. Interpret them
  through `runs/REDUCED_SOCRATES_BENCHMARK_POSTRUN_AUDIT.md`; preserve the
  original generated artifacts unchanged.
- The reduced run-attempt latch is consumed. Do not rerun the session. Further
  work is offline review only unless the operator gives a new, explicit
  authorization.

## Q2 CED 4,096 diagnostic invariants and result

- A separate authorization permitted exactly one Q2 CED opening call with zero
  retries while retaining the existing cumulative `$8.00` ceiling. That call is
  complete; its stable attempt latch is consumed and it must not be rerun.
- The only provider-bound request difference from the preserved 1,024-token CED
  opening was `$.max_tokens: 1024 -> 4096`. Prior body SHA-256:
  `8a758dedda1614b46845c79ceab63de102e75a8b9ca5358cdc74ee190b415800`.
  Diagnostic body SHA-256:
  `51ec1776f26b2de5f0b0218be12d8a514beff6f208036d7e4edb0fadd8601e13`.
- Fresh exact-endpoint evidence selected `openai/flex` / OpenAI for
  `openai/gpt-5-mini`, dated endpoint
  `openai/gpt-5-mini-2025-08-07`; `max_tokens` remained supported and the
  endpoint maximum output was 128,000 tokens.
- The diagnostic made one call and zero retries. It returned HTTP 200,
  `finish_reason=stop`, `native_finish_reason=completed`, nonempty assistant
  content, 4,327 prompt tokens, 933 completion tokens, and 768 reasoning tokens.
- Provider structured-output validation passed. CED parse status was `ok`, and
  canonical CED application accepted the move with operator `expose_premise`,
  marker `reasonable_hypothesis`, and confidence `0.65`.
- Exact accepted question (verbatim):

  > What must be true about (a) how teams were selected into the program, (b) the independent effect of the special training, (c) how productivity was measured and any measurement bias, and (d) other concurrent changes or incentives, for the CEO’s statement “the AI tool caused an 18% productivity increase” to be justified — i.e., which of these premises must hold (and why) before that causal claim can be accepted?
- Latency was `8969.637 ms`. Diagnostic observed cost was `$0.001473875`;
  cumulative observed cost for the reduced session plus diagnostic was
  `$0.00608825`.
- Verdict: `GENERATION_BUDGET_CONFIRMED`. Scientific classification:
  `GENERATION_BUDGET_TOO_LOW AT 1024`.
- This is the predeclared operational classification. The successful completion
  used 933 tokens, below 1,024, while the earlier failure lacks retained
  finish/native-reason evidence. Treat it as evidence of budget sensitivity,
  not proof that every completion intrinsically needs more than 1,024 tokens.
- Phase-aware values 4,096 / 8,192 / 16,384 are a
  policy proposed by the diagnostic for openings, reflection/reconstruction,
  and synthesis/final response respectively. At diagnostic completion its
  status was `PROPOSED_NOT_IMPLEMENTED`; it has since been wired into the
  existing normal runner without changing CED. The larger values remain
  provisionally chosen and have not yet been observed live.
- No hidden reasoning text or reasoning-details payload was persisted. Only
  reported numeric reasoning-token evidence and presence facts were retained.
- Diagnostic collection SHA-256:
  `99941193dcfc024780a0b47be1b1042dd30db65814dc2ae97a8bf7cae8f8a25c`.
  Diagnostic report SHA-256:
  `91e3d1b13c43eda1ff14898d1076830520437db88376069200ac9467eade913a`.
- No push is authorized.

## Normal live-run invariants

- The accepted 4,096 diagnostic closes diagnostics. Neither the reduced
  benchmark nor the diagnostic may be rerun.
- `scripts/run_socrates_live_v1.py` is the branch-native normal runner. Do not
  replace it with the generic `scripts/live_dialogue.py` provider path, which
  does not carry this proven Flex/session/schema wiring.
- The normal runner uses `openai/gpt-5-mini` on exact `openai/flex`, a fresh
  endpoint record at execution time, exact CED-derived structured-output
  schemas, no fallback, no transport retry, no CED parse repair, no baseline,
  and no hidden reasoning text. The exact endpoint context must remain 400,000
  tokens so the P19 input reservation cannot be undercut by endpoint drift.
- CED remains the sole transition/acceptance authority. The adapter may select
  only a lower output envelope for a CED-owned task; model, provider, pricing,
  sampling, timeout, schema, and retry fields must remain identical.
- Output routing is 4,096 for Socratic questions, objections, scores,
  ratification, and objection verification; 8,192 for initial response,
  reflection, and reconstruction; 16,384 for synthesis drafts. Tree revision
  remains disabled.
- The normal shape is two homogeneous live workers (`Alpha`, `Beta`) over four
  logical CED agents. Its structural maximum is 64 calls: 50 at 4,096, 10 at
  8,192, and 4 at 16,384.
- Conservative P19 bounds are `$0.054096`, `$0.058192`, and `$0.066384` per
  output tier, with `$3.552256` for the entire structural maximum. The normal
  session receives only the exact `$7.99391175` remaining under the cumulative
  `$8.00` ceiling after prior observed spend of `$0.00608825`.
- One endpoint/question-independent write-once normal-run attempt latch is
  consumed automatically before the endpoint GET. This is a spend-safety
  invariant, not an approval pause: different question or fresh-profile bytes
  cannot mint another full remaining ledger.
- Preparation itself performed no endpoint GET, credential read, provider/model
  call, attempt/claim consumption, or live result artifact write.

## Q2c correction and Q2d invariants

- Q2c is incomplete and protocol-nonconformant: approval named `ee9fa22e...`,
  while execution used `3b88603b...`. Six matching component digests are not a
  substitute for exact whole-manifest authorization.
- Preserve every Q2c artifact unchanged. The append-only correction ledgers
  govern causal attribution and protocol status. Q2c has no final CED score and
  supports no confirmatory or causal diversity claim.
- GPT-5 Mini Q2c turn 7 is
  `completion_envelope_exhausted_before_valid_visible_payload`.
- Gemini Q2c turn 10 is `provider_structured_output_contract_violation`: it
  stopped normally and returned `{"confidence":0.9,"content":{}}`, omitting
  all seven required fields. Do not attribute it to token exhaustion.
- Q2d uses fixed session ID `q2d-ced-hetero-v1`; do not search role offsets for
  a cheaper allocation.
- Q2b/Q2c used four logical agents behind three physical model seats. Alpha
  served two logical agents, so duplicate Alpha successes could satisfy quorum
  two. Q2d must use exactly three logical agents mapped one-to-one to the three
  distinct model/provider seats.
- The one-to-one topology is a substantive protocol change. Q2d is a new
  exploratory reliability run, not a confirmatory replication of Q2b/Q2c.
- Only GPT-5 Mini `ELENCHUS_OBJECTION` receives 8,192 output tokens. All other
  task/model envelopes remain unchanged.
- The exact Q2d ceiling is 107 calls, not 64. The 64-call value belongs to the
  earlier two-worker homogeneous topology.
- Exact distribution: Alpha/GPT-5 Mini 36 calls (`$0.770048`), Beta/Gemini 35
  (`$2.0352`), Gamma/GPT-4.1 Mini 36 (`$2.3789568`), total 107
  (`$5.18420480`).
- Retained spend is conservatively rounded to `$0.651915`; maximum cumulative
  authorization required is `$5.83611980`.
- Exact authorization occurs before ledger, claims, credentials, acquisition,
  or dispatch; every pre-dispatch guard rechecks current manifest and retained
  implementation evidence.
- A persisted latch is audit evidence, not reusable authority. Live
  construction also requires the opaque process-local capability issued by a
  fresh latch write, bound once to one live builder.
- Q2d evidence never persists raw request or response bodies. Historical raw
  artifacts remain unchanged; new sidecars contain allowlisted metadata keyed
  by `body_sha256`.
- Q2d has made zero live calls and remains blocked pending explicit approval of
  canonical manifest SHA-256
  `2729d4bd82af1ddc29ba6526daa4cd00ee3132540e01dbee7a73dba723581075`
  (32,320 exact bytes) and the raised cumulative ceiling of `$5.83611980`.
- The target Windows live process must reproduce the exact frozen
  Python/Pydantic runtime, reachable response schemas, implementation/evidence
  hashes, and EOL-controlled bytes before acquisition; drift fails closed.
- Exact task authorization includes reachable seat/task/round/role signatures,
  reconstructed task body, `turn_content_id`, semantic headers, model, provider
  controls, response schema, output field, seed, session, and question.
- The one-shot filesystem latch and claim store cover process crash, ordinary
  restart, accidental duplicate execution, and concurrent duplicate
  consumption. They explicitly do not claim protection from a malicious local
  administrator, deliberate rollback, VM/snapshot rollback, or backup restore.
- The frozen local-code threat model excludes malicious in-process reflection.
  Ledger/counter locking is required if transport becomes genuinely
  concurrent. Exact endpoint selection ultimately relies on OpenRouter honoring
  the emitted singleton route and no-fallback controls.
- Final offline verification: 189 focused tests passed. Repository-wide:
  4,301 passed, 1 skipped, with only the known missing-predecessor-Git-object
  and POSIX/frozen-Windows-path failures; no Q2d, authorization, or privacy
  failure.

Frozen control SHA-256 values:

- `runs/README.md`: `14c362c4bd05337ce61e1fc7899bcc0d17ab5b38521bdf897ad7bbd99325d547`
- `runs/socrates_live_run_002.json`: `9636ceabc377bee74cf235584599f7a1d11f1880c10b9b5647046ee29a6cbf0d`
- `runs/socrates_live_run_003.json`: `59f1c4c622bb0a985f560398dc4fd1b78445f31681c14617ef0efce698088c2e`

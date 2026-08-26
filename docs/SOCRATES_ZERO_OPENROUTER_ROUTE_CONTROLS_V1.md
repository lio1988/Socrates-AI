# SocratesZero OpenRouter Route Controls v1

## Final authoritative result

Phase 8.5D is complete as an additive, offline route-control experiment. The
semantic design, case set, validation order, thresholds, artifact schema, and
replay schema were frozen in commit
`848166dd3eacfa5d31175745b160b98751b3a904` before the sole authoritative
aggregate. The write-once artifact was committed separately in
`d225113`. This report must not be read as live authorization.

- Hypothesis status: `FALSIFIED`.
- Artifact path:
  `docs/branches/feature-socrates-zero-openrouter-route-controls-v1/artifacts/socrateszero_openrouter_route_controls_v1.json`.
- Artifact ID:
  `szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd`.
- Artifact SHA-256:
  `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`.
- Artifact length: 366,623 bytes.
- Replay: `NOT PERFORMED / N/A`; replay execution and lock are absent because
  replay is prohibited after falsification.

- Specification basis: frozen Phase 8.5C manifest.
- External specification revalidation: not performed on this branch.
- Credentials, DNS, sockets, HTTP, provider/model/tool calls, and CED
  application: prohibited.
- Production integration: none.
- P17 input-token bound: `NOT_ESTABLISHED`.
- P18 pricing record: `NOT_ESTABLISHED`.
- P19 cost bound: `NOT_ESTABLISHED`.
- Live server enforcement: `NOT_PROVEN`.
- Exact endpoint response attestation: `NOT_ESTABLISHED`.
- Live pilot readiness: `NOT_EARNED`.
- Official response wire mapping from the sole-authority manifest:
  `NOT_ESTABLISHED_FROM_FROZEN_MANIFEST`.

The strict Phase 8.5D hypothesis requires an official response-envelope parser,
not merely a repository-owned normalized semantic parser. The manifest audit
froze one `official_response_wire_mapping_violations` finding against a maximum
of zero. The authoritative artifact observed that exact `1 > 0` failure, so the
full milestone is `FALSIFIED` even though every local normalized canned case
behaved exactly as designed. The finding was not tuned after the aggregate.

## Frozen specification authority

Path:
`docs/branches/feature-socrates-zero-openrouter-spec-evidence-gate-v0/evidence/openrouter_official_specification_evidence_v0.json`

- Manifest ID:
  `szorspecmanifestv0_6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`
- Semantic SHA-256:
  `6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`
- Binding ID:
  `szorspecbindingv1_e2fa759509784742441f2759430a0e15159f553602f944541fe9e896a7163cb9`
- Source records: 16.
- Normalized fact records: 13.
- Route-control bindings: `ORSPEC-F01`, `ORSPEC-F02`, `ORSPEC-F03`,
  `ORSPEC-F04`, `ORSPEC-F05`, `ORSPEC-F10`, and `ORSPEC-F13`.

The manifest semantic digest is recomputed from canonical sorted compact UTF-8
JSON after excluding only `manifest_id` and `manifest_semantic_sha256`. The raw
manifest file hash is separately retained in the artifact. No documentation is
fetched by this milestone.

`OR-S04-ROUTER-METADATA` and `OR-S08-OPENAPI` retain source digests but have
`source_content_bytes: null`. `ORSPEC-F04` retains response concepts, while
`ORSPEC-F05` retains the exact top-level `openrouter_metadata` name and cache
interaction; neither retains a complete nested official wire schema or a
content-addressed official-wire-to-normalized mapping. The mandate makes this
manifest the sole authority and forbids repairing the gap from memory or the
richer narrative Phase 8.5C report.

## Frozen request intent

- Provider: OpenRouter.
- Exact model: `openai/gpt-4.1-mini`.
- `models`: absent.
- `provider.only`: `["azure/swedencentral"]`.
- `provider.order`: `["azure/swedencentral"]`; preference semantics only,
  with `only` carrying the hard restriction intent.
- `provider.allow_fallbacks`: `false`.
- `provider.require_parameters`: `true`.
- `provider.max_price`: absent, `DEFERRED_NOT_RENDERED`.
- `stream`: `false`.
- `tools`: `[]`; `tool_choice` absent.
- Metadata opt-in: `X-OpenRouter-Metadata: enabled`.
- OpenRouter response-cache disablement: `X-OpenRouter-Cache: false`.
- Content type: `Content-Type: application/json`.
- Authorization and credential material: absent.

Canonical body JSON:

```json
{"max_tokens":256,"messages":[{"content":"Ask one concise opening Socratic question without answering the user's question.","role":"system"},{"content":"Is knowledge merely justified true belief?","role":"user"}],"model":"openai/gpt-4.1-mini","provider":{"allow_fallbacks":false,"only":["azure/swedencentral"],"order":["azure/swedencentral"],"require_parameters":true},"response_format":{"type":"text"},"stream":false,"temperature":0.0,"tools":[]}
```

Canonical application-header representation (not HTTP wire bytes):

```json
{"Content-Type":"application/json","X-OpenRouter-Cache":"false","X-OpenRouter-Metadata":"enabled"}
```

- Body SHA-256:
  `35a119b1e35f9f8ce05baf57009d787358bf086aaae4055ef56fcfedade514a1`.
- Body length: 447 bytes.
- Header SHA-256:
  `1c688da6c6494631d6922fcb89a56b126e0900327dd865c2483d84f3c9f58149`.
- Header length: 98 bytes.
- Combined route-intent ID:
  `szorrouteintent_d26fcc19fd146c37ce7d3181055cdd447eab91dc2295319a31a3e81c52362c8b`.
- Request-intent receipt ID:
  `szorrouteintentreceiptv1_9fa27bd2cb5bf3e778a4ef5a51a1efe84939981517a6202e8d47b44435bbdd63`.

The recursive request firewall rejects credentials, authorization, branch,
transport, experiment, receipt, timestamp, UUID, nonce, PID, local-path,
artifact, and evaluator metadata. Prepared body and header bytes are immutable;
the canned transport receives those exact bytes without map reconstruction.

## Frozen semantic identities

- Route controls:
  `szorroutecontrolsv1_67a0a4b9ca91805fd62ee30e89afdfe5c88c912b4db904311b966bc82708b036`.
- Route-intent contract:
  `szorrouteintentcontractv1_7bd1e67cad72f21127369f68e5aa9ecacb4752a8f7a275d2db7b3826f3b1e932`.
- Renderer: `socrateszero-openrouter-route-renderer/v1`.
- Prepared request:
  `szorpreparedroutev1_b01ef6197873082fe434e9065e050fc600be9bb038ac9e60d33b1b3c73ca2493`.
- Header policy:
  `szorrouteheadersv1_bdc43916f1431865b265579b44f540ac53dc70029a198e430b137acf3aa91a59`.
- Cache policy:
  `szorcachepolicyv1_e4a3d68949ef433f27e036a01b478aef0cb239cbc45606f81483c71c0b4fa93a`.
- Metadata policy:
  `szormetadatapolicyv1_4c1b9c42565d7f5a510c2face7921d50b06b20d57dd3c7e9e59ed0a10ccb869c`.
- Metadata parser: `socrateszero-openrouter-router-metadata-parser/v1`.
- Case set:
  `szorroutecasesetv1_023d376b6769a8362a279a76189681069424e798890b4339d857a5c5175d334c`.
- Harness: `socrateszero-openrouter-route-control-harness/v1`.
- Metrics: `socrateszero-openrouter-route-control-metrics/v1`.
- Thresholds:
  `szorroutethresholdsv1_1b8053a6e0aa79841517b75c1012c0a7e42a6389547227ec936ab09c22bddbaf`.
- Validation order:
  `szorrouteguardsv1_91f5262d94d567b1d58a635e96d798b6eed54f2e34b38b23540b9cd91361f2a3`.
- Failure taxonomy:
  `szorroutefailuresv1_bca8109c00eb48657c24cd82a90d95e0538c3850bec1ec64846f2b0c5d97aa55`.
- Manifest-only response-wire assessment:
  `szorwiremappingassessmentv1_4837280cd07f68b98c73a84c48c59b44fc907b177f46fddfd6ece843f5a20b48`.

All identities above are content-derived from the final pre-result freeze.

## Canned response and attestation boundary

The parser consumes a repository-owned normalized canned concept envelope. It
is explicitly marked as not being an official OpenRouter wire-schema claim,
because the Phase 8.5C manifest retained the metadata concepts and source
digests but not complete source bytes or every nested wire path.

Positive canned metadata requires:

- requested model and singleton requested provider route consistent with the
  prepared request;
- exact local normalized `routing_strategy == "direct"`;
- one-based integer `attempt == 1`;
- exact actual-model equality;
- broad provider equality at `azure` granularity;
- optional attempts absent, or exactly one internally consistent successful
  attempt when present;
- no cache-affected marker, fallback observation, fallback pipeline stage,
  authority override, or exact-endpoint claim.

Unknown forward-compatible fields are retained only through an opaque digest
and count. Unknown non-authoritative pipeline stages may be retained, but grant
no authority. Broad provider `azure` never becomes exact endpoint
`azure/swedencentral`. Missing metadata is rejected primarily as
`ROUTER_METADATA_MISSING`; it is never reclassified as a proven cache hit. Raw
UTF-8 response bytes, digest, and length are retained for accepted and rejected
dispatched cases without requiring provider JSON whitespace or member order to
match repository canonicalization.

## Frozen cases, mutation model, and thresholds

- Cases: 63 total.
- Positive request cases: 3.
- Positive response cases: 3.
- Orthogonal request probes: 29.
- Orthogonal response probes: 20.
- Precedence probes: 8.
- Required complete route-intent receipts: 7.
- Required complete metadata receipts: 3.
- Frozen expected canned invocations: 26; observed: 26.
- Invalid probe constructions allowed: 0.
- Official response wire-mapping violations allowed: 0.
- Frozen and observed manifest-only wire-mapping assessment: 1.

The wire-mapping assessment is a typed, content-derived receipt over the exact
canonical record digests for `OR-S04-ROUTER-METADATA`, `OR-S08-OPENAPI`,
`ORSPEC-F04`, and `ORSPEC-F05`. It derives the retained and missing exact local
normalized field-name coverage, the absence of structured type/mapping records,
its `NOT_ESTABLISHED_FROM_FROZEN_MANIFEST` status, and the resulting violation;
the evaluator does not inject the metric as an unconditional constant.

Every probe predeclares all 22 mutation dimensions as `PRESERVED`,
`INTENTIONALLY_CHANGED`, `DEPENDENTLY_CHANGED`, or `NOT_APPLICABLE`:
manifest integrity, model, models absence, endpoint restriction, order,
fallback, require-parameters, max-price status, stream, tools, metadata header,
cache header, body bytes, header bytes, metadata presence, attempt, attempts
list, actual model, provider, endpoint-attestation claim, cache state, and
receipt identity.

Orthogonal probes have exactly one intentional causal mutation. Precedence
probes have at least two. The primary result is the first failing frozen guard;
evaluator-side expected labels never enter requests, responses, parser
receipts, or route attestations.

## Frozen validation order

1. Manifest integrity.
2. Route-policy integrity.
3. Exact model.
4. `models` absent.
5. Provider-object schema.
6. Exact singleton endpoint.
7. Exact matching order.
8. Provider fallback false.
9. Require-parameters true.
10. `max_price` absent.
11. Stream false.
12. Tools disabled.
13. Metadata header exact.
14. Cache header exact.
15. Canonical bytes, digests, lengths, and sealed preparation.
16. Recursive entropy firewall.
17. Exact canned registration.
18. Transport completion.
19. Raw envelope presence.
20. Router metadata presence.
21. Metadata schema and known-field integrity.
22. Cache/metadata availability.
23. Attempt present and valid.
24. Attempt equals one.
25. Actual model present.
26. Actual model exact.
27. Provider present.
28. Provider compatible at broad granularity.
29. Optional attempts consistent.
30. Fallback indicators and forbidden pipeline absent.
31. False exact-endpoint claim firewall.
32. Receipt and deferred-claim integrity.

## Artifact and replay protocol

The authoritative operation ran exactly once with an active Acquisition
Boundary Tripwire. It captured scoped source/sibling/production hashes before
and after evaluation, verified all ten historical artifact hashes and the
embedded Phase 8 v2 core lock, evaluated the frozen cases once, canonicalized
results back into frozen case order, and published one canonical sorted UTF-8
JSON artifact with one trailing newline using exclusive creation. All 63 case
results matched their frozen expectations: 6/6 positives, 49/49 orthogonal
primary failures, and 8/8 precedence primary failures. Source, sibling,
production, historical/core-lock, credential, network, provider, model, tool,
and CED mismatch/activity counters were zero.

If and only if the artifact is `SUPPORTED`, one independent reverse-order
replay rebuilds the artifact. Semantic equality, artifact-ID equality, and byte
identity are mandatory. Replay execution evidence and its lock are separate
write-once files; the authoritative artifact is never rewritten.

Because the predeclared manifest-only wire-mapping gate is one, the truthful
first artifact is `FALSIFIED`. Replay was not performed; the replay execution
and replay lock are confirmed absent.

## Final regression gates

| Gate | Exact result |
|---|---|
| Route controls v1, artifact-aware | `103 passed` |
| Acquisition Contract v0 | `239 passed, 8 skipped` |
| Phase 5 artifact | `3 passed` |
| Phase 7 primary artifact | `4 passed` |
| Phase 7 BestOfN artifact | `3 passed` |
| Phase 8 v1 predecessor/core | `5 passed` |
| Phase 8 v2 artifact/replay | `30 passed` |
| Production OpenRouter fake/canned only | `12 passed, 1 deliberately deselected` |
| Focused CED/Socratic | `142 passed, 14 warnings` |
| OpenRouter adapter-controls v0 group | `241 passed, 1 skipped, 1 failed` |
| SocratesZero bundle | `916 passed, 9 skipped, 1 failed` |
| Full `tests_dialogues` | `3165 passed, 10 skipped, 1 deliberately deselected, 1 failed` |
| Repository-wide | `3472 passed, 10 skipped, 1 deliberately deselected, 1 failed, 1 teardown error, 23 warnings` |

The sole failing assertion is the sealed v0 static data-only check
`test_expected_labels_are_evaluator_side_and_cases_module_is_data_only`. It
scans every runtime Python file and rejects the literal historical inventory
path `openrouter_acquisition_cases.py` in the new additive evaluator. The
repository-wide run additionally reported an acquisition-tripwire error during
that same test's teardown; its suite-order-specific cause was not reclassified.
No post-result source or test change was made to hide or tune either result. The
deliberately deselected test is the sole selected production-provider test that
exercises production resolution of the real `OPENROUTER_API_KEY` environment
name; separate boundary tests use instrumented environment seams and fail-closed
tripwires.

## Frozen predecessor

The OpenRouter adapter-controls v0 artifact remains unchanged:

- ID:
  `szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f`.
- SHA-256:
  `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083`.
- Status: `FALSIFIED`.
- Replay: `NOT PERFORMED`.

Route controls v1 do not repair, regenerate, reinterpret, or add a replay to
that sealed lineage.

## Decision boundary

Success can prove only deterministic offline request intent, canonical body
and semantic-header representation, deterministic normalized canned parsing,
and honest partial provider attestation. It cannot prove current external
specification validity, endpoint availability, live enforcement, credentials,
network boundaries, exact response-side endpoint identity, tokenizer closure,
pricing, or a total cost bound.

Only complete support plus byte-identical replay could have advanced to Phase
8.5E. That condition was not earned. The final disposition is `RETURN TO
ARCHITECTURE DECISION`. A future authorized phase could version a richer
manifest or explicitly authorize another frozen source as response-schema
authority; this branch does neither and stops before P17/P18/P19 work.

# SocratesZero Phase 8.5D-R — OpenRouter Wire-Mapping Decision Gate

## 1. Executive verdict

**Decision: `SPECIFICATION EVIDENCE MANIFEST v1 REQUIRED FIRST`.**

The sealed Route Controls v1 result remains `FALSIFIED`. Its single
`official_response_wire_mapping_violation` is not a failed case and is not
attributable to one raw fixture or one incorrectly translated JSON field. It is
a global, typed manifest-sufficiency finding: the frozen v0 manifest does not
retain a structured official response schema, complete nested names and types,
or an official-wire-to-local-normalized mapping.

Two independent statuses are therefore preserved:

| Status plane | Result |
|---|---|
| Official wire mapping | `NOT_ESTABLISHED_FROM_FROZEN_MANIFEST` |
| Repository integrity | `INCOMPLETE`: one deterministic static-inventory assertion; isolated teardown clean |

The schema gap logically precedes repository-boundary cleanup under the frozen
dependency rule. No parser, renderer, fixture, case, evaluator, manifest,
artifact, replay, production, or CED component was changed by this gate.

## 2. Sealed route-controls v1 result

| Item | Sealed value |
|---|---|
| Parent checkpoint | `31d56c944717bee8f9ae4ba8f00538155b239d36` |
| Artifact ID | `szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd` |
| Artifact SHA-256 | `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661` |
| Artifact length | 366,623 bytes |
| Hypothesis | `FALSIFIED` |
| Replay | `NOT PERFORMED`; execution and lock remain absent |
| Cases | 63 |
| Positive | 6/6 |
| Orthogonal | 49/49 exact primary failures |
| Precedence | 8/8 exact primary failures |
| Invalid constructions | 0 |
| Canned dispatches | 26 |
| Source / sibling / production mutations | 0 / 0 / 0 |
| Official-wire violations | 1; maximum 0 |

All 63 case results have `result_matches_expectation=true`. The full result is
still falsified because the manifest-wide mapping metric is part of the frozen
threshold conjunction; strong local subsystem evidence does not override it.

## 3. What request-side intent proved

The v1 renderer and contracts proved the following deterministic offline
request intent:

- exact model `openai/gpt-4.1-mini` and no `models` array;
- singleton `provider.only` and `provider.order` equal to
  `azure/swedencentral`;
- `provider.allow_fallbacks=false` and `provider.require_parameters=true`;
- `provider.max_price` absent as `DEFERRED_NOT_RENDERED`;
- `stream=false`, tools disabled;
- `X-OpenRouter-Metadata: enabled` and `X-OpenRouter-Cache: false` in the
  canonical application-header representation;
- exact canonical request-body and header representation hashes.

This proves request construction only. It does not prove live server
enforcement, current endpoint availability, exact endpoint response identity,
universal no-fallback behavior, or official response parsing.

## 4. Exact response-wire mapping violation

There is no case-level field mismatch to name. The exact violation is the
following assessment relationship:

```text
$.official_response_wire_mapping_assessment.violation_count = 1
$.metrics.official_response_wire_mapping_violations = 1
$.thresholds.maximum_official_response_wire_mapping_violations = 0
$.metrics.all_thresholds_pass = false
$.hypothesis_status = FALSIFIED
```

Assessment ID:
`szorwiremappingassessmentv1_4837280cd07f68b98c73a84c48c59b44fc907b177f46fddfd6ece843f5a20b48`.

The evaluator derives that assessment before evaluating cases. It compares the
nine repository-normalized names with the exact tokens retained by `ORSPEC-F04`
and `ORSPEC-F05`, and separately checks source-length and structured-schema
records.

| Required by the frozen gate | Actually retained |
|---|---|
| Complete nested names | No |
| Complete nested types | No |
| Structured wire-schema record | No |
| Official-wire-to-normalized mapping | No |
| Non-null source-content lengths for S04/S08 | No |
| Exact local names | `openrouter_metadata`, `attempt`, `provider`, `pipeline` only |
| Missing exact local names | `requested_model`, `requested_provider_only`, `routing_strategy`, `actual_model`, `attempts` |

Accordingly:

- **Exact official path mapped incorrectly:** none preserved or proven.
- **Exact internal field responsible:** no single field; five-name coverage plus
  structured-name/type/mapping incompleteness.
- **Expected mapping:** a complete content-addressed structured mapping for all
  authoritative normalized fields.
- **Actual mapping:** no mapping record exists; local concepts are consumed
  directly from a repository-owned normalized envelope.
- **Root cause:** the sealed v0 manifest retains source digests and prose facts,
  but not inspectable source snapshots, nested schemas, types, requiredness, or
  a mapping object.

Calling one of the local fields the incorrectly mapped official path would be a
reconstruction from memory and is forbidden by this gate.

## 5. Violating case forensic record

| Requested forensic item | Sealed finding |
|---|---|
| Case ID | `NONE — NOT CASE-ATTRIBUTABLE` |
| Probe class | `NONE` |
| Raw fixture ID | `NONE` |
| Raw fixture digest | `NONE` |
| Expected case mapping record | Absent |
| Actual case mapping record | Absent |
| Normalized metadata receipt | Not linked to the assessment |
| Primary result | Not a case result |
| Diagnostic result | Manifest assessment status |
| Mutation vector | Not applicable |
| Mapping detail | Global assessment fields listed in section 4 |

No case-result schema has an official-wire mapping field or a foreign key to
the assessment. Every one of the 26 dispatched canned responses retains exact
raw text, byte length, SHA-256, and a content-derived evidence ID, but all
declare the repository schema
`socrateszero-openrouter-normalized-canned-response/v1`.

**SEALED ARTIFACT FORENSICS: `INSUFFICIENT` for the requested exact
case/path mismatch.** It is sufficient to prove why the global gate failed, but
not to identify a non-existent case-level violation or reconstruct an official
path.

## 6. Official wire schema

The sole authority is manifest v0:

- ID:
  `szorspecmanifestv0_6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`;
- semantic SHA-256:
  `6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`;
- file SHA-256:
  `818a1ec466bd37bd23dd86ef14fecf0fcc0049360bef7b5a16fdc2f575069e9f`.

The maximum official schema support that may be claimed from its frozen facts
is:

| Manifest fact | Supported official concept | What is not retained |
|---|---|---|
| `ORSPEC-F04` | metadata opt-in; requested-routing information; strategy; selected provider/model summaries; one-based successful attempt; optional attempt details; optional pipeline stages | exact nested paths, types, requiredness, child schemas, allowed values, success/error placement |
| `ORSPEC-F04` limitation | selected full endpoint slug or endpoint ID is absent; unknown fields/stages are additive | endpoint reconstruction and authoritative additive-field collision rules |
| `ORSPEC-F05` | exact token `openrouter_metadata`; cache hits may omit it; response cache and provider prompt cache differ | cache header/status response contract and proof that a particular absence is a cache hit |
| `ORSPEC-F13` | full exact endpoint/routing evidence is not guaranteed on every success or failure | a complete one-call success/error contract |

`OR-S04-ROUTER-METADATA` and `OR-S08-OPENAPI` have content digests, but both
have `source_content_bytes=null`; no corresponding source body is stored in the
evidence directory. A digest authenticates bytes when available; it cannot
reconstruct missing bytes.

Therefore the following exact dotted paths are **not established** by manifest
v0, even when a related prose concept is present:

`openrouter_metadata.requested`, `.strategy`, `.region`, `.summary`,
`.attempt`, `.is_byok`, `.endpoints.total`, `.endpoints.available[]` and its
children, `.params`, `.attempts[]` and its children, and `.pipeline[]`.

The existence/name of top-level `openrouter_metadata` and the conceptual
one-based attempt, provider summary, and optional pipeline are retained. Their
complete dotted paths, types, and mapping semantics are not.

## 7. Internal normalized schema

The repository schema is explicit and internally testable, but it is not an
official response schema.

| Local raw path | Local type / presence | v1 rule | Receipt projection | Authority |
|---|---|---|---|---|
| `schema_version` | required string | must equal local normalized schema ID | none | Repository-only |
| `openrouter_metadata` | required object | absence G20; wrong shape G21 | `required_metadata=PRESENT` | Name concept supported; shape not mapped |
| `.requested_model` | required string | exact local model | constant verified `requested_model` | Repository convention |
| `.requested_provider_only` | required `list[str]` | exact singleton endpoint | request-derived `requested_endpoint` | Repository convention |
| `.routing_strategy` | required nonblank string | must equal local literal `direct` | `routing_strategy_summary` | Repository convention |
| `.actual_model` | required string | exact local model | `actual_model`, `model_match` | Repository convention |
| `.provider` | required string | exact broad literal `azure`; exact endpoint is rejected | `attested_provider`, broad granularity | Repository convention over F04 concept |
| `.attempt` | required positive integer | must equal 1 | literal `attempt=1` | Concept aligned; type/path not mapped |
| `.attempts` | optional list | when present, exactly one consistent success entry | absent/present-consistent status | Repository convention over optional-detail concept |
| `.pipeline` | optional list, default `[]` | dict stages allowed except fallback-like content | opaque digest/count only | Partial concept; child rules local |
| `.fallback_observed` | optional bool, default false | any true/non-bool fails | no-observed-fallback | Repository-only |
| unknown content | any JSON | digest/count; authority/cache/fallback/endpoint names fail closed | SHA-256 and count | Non-authoritative |

The parser entry point is `parse_openrouter_router_metadata_v1`. It retains
exact UTF-8 JSON text, length, and digest, rejects duplicate members and
non-finite values, then requires the local schema marker and local field names.
That is raw-first relative to canned repository bytes, not raw-first relative
to an official OpenRouter Chat Completions envelope.

## 8. Field-by-field mapping matrix

Legend: `NR` means not retained in manifest v0; `N/A` means no local mapping is
declared. “G21” refers to the local metadata-schema guard. Test IDs are v1 case
IDs, not official-wire certification.

| OFFICIAL WIRE PATH | OFFICIAL TYPE | OFFICIAL REQUIRED/OPTIONAL STATUS | FROZEN EVIDENCE RECORD | RAW FIXTURE PATH | INTERNAL NORMALIZED FIELD | NORMALIZATION FUNCTION | LOSSLESS | MISSING-FIELD RESULT | INVALID-TYPE RESULT | UNKNOWN-FIELD POLICY | AUTHORITY CLAIM | TEST CASES |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openrouter_metadata` | NR | cache hits may omit; other requiredness NR | F04/F05 | same local top-level name | metadata object | direct local lookup | No: official shape/type absent | G20 missing | G21 malformed | N/A | Name/concept directly documented; schema unsupported | SS01–03, OS01–02 |
| `openrouter_metadata.requested` | NR | NR | F04 concept only | absent; local fixture uses two echo fields | `requested_model`, `requested_provider_only` | no official map; local equality checks | No | official-shaped input lacks local names and fails G21 | G21 | `requested` is authority-like | Unsupported mapping | SS01–03; local schema probes |
| `openrouter_metadata.strategy` | NR | NR | F04 concept only | local `.routing_strategy` | `routing_strategy` | local rename plus `==direct` assumption | No | G21 | G21 | `strategy` is authority-like | Repository convention | OS16, P06 |
| `openrouter_metadata.region` | NR | NR | none | absent | none | none | No | N/A | N/A | authority-like unknown fails | Unsupported | none |
| `openrouter_metadata.summary` | NR | NR | none | absent | none | none | No | N/A | N/A | authority-like unknown fails | Unsupported | none |
| `openrouter_metadata.attempt` | NR; prose says one-based number | successful-attempt concept; exact requiredness NR | F04 | same local name | `attempt` | positive-int check, then `==1` | Not proven | G23 | G23; values >1 fail G24 | known local field | Derived with assumptions | OS03–05, P05 |
| `openrouter_metadata.is_byok` | NR | NR | none | absent | none | none | No | N/A | N/A | authority-like unknown fails | Unsupported | none |
| `openrouter_metadata.endpoints.total` | NR | NR | none | absent | none | none | No | N/A | N/A | non-authoritative unless nested protected names | Unsupported | none |
| `openrouter_metadata.endpoints.available[]` | NR | NR | none | absent | none | none | No | N/A | N/A | no official collection policy | Unsupported | none |
| `...available[].provider` | NR | NR | F04 provider-summary concept only | absent | candidate local `.provider` only | no declared map | No | G27 for missing local provider | G28 | nested `provider` is authority-like | Unsupported exact mapping | OS07, OS09, OS18 |
| `...available[].model` | NR | NR | F04 model-summary concept only | absent | candidate local `.actual_model` only | no declared map | No | G25 for missing local actual model | G26 | nested `model` is authority-like | Unsupported exact mapping | OS06, OS08, OS17 |
| `...available[].selected` | NR | NR | none | absent | none | none | No | N/A | N/A | authority-like unknown fails | Unsupported | none |
| `openrouter_metadata.params` | NR | NR | none | absent | none | none | No | N/A | N/A | opaque only if harmless | Unsupported | none |
| `openrouter_metadata.attempts[]` | NR | prose says attempt details optional | F04 concept only | local `.attempts[]` | optional local list | singleton consistency checks | No | absence accepted | malformed/inconsistent at G29 | child extras digested | Repository convention | SS01–02, OS10–12 |
| `...attempts[].provider` | NR | NR | F04 provider-summary concept only | same local child name | child provider | equality to local top-level provider | No | G29 when list present | G29 | child extras digested | Repository convention | SS02, OS10–12 |
| `...attempts[].model` | NR | NR | F04 model-summary concept only | same local child name | child model | equality to local actual model | No | G29 when list present | G29 | child extras digested | Repository convention | SS02, OS10 |
| `...attempts[].status` | NR | NR | none | local child is `.outcome` | local `outcome` | local rename/`success` literal, no official map | No | G29 when list present | G29 | child extras digested | Repository convention | SS02, attempts probes |
| `openrouter_metadata.pipeline[]` | NR | optional stages concept | F04 | same local collection name | local pipeline | list/dict check; fallback-name heuristic | No | defaults to `[]` | G30 | content digested; fallback-like stages fail | Derived with assumptions | OS19, P06 |
| top-level response `model` or another served-model source | NR | NR | F04 selected-model concept only | absent; local model is nested `.actual_model` | `actual_model` | no official source precedence | No | local G25 | local G26 | top-level `model` is authority-like unknown | Unsupported | OS06, OS08, OS17 |

The matrix is deliberately incomplete on the official side. Filling `NR` cells
from the richer narrative report, current web documentation, memory, or the
prompt's candidate path list would silently expand the sealed manifest.

## 9. Lossless vs unsupported derivations

| Evidence-strength class | v0 finding |
|---|---|
| `DIRECTLY DOCUMENTED` | metadata opt-in/name, cache-hit omission possibility, conceptual one-based successful attempt, selected provider/model summaries, optional attempt detail/pipeline, absence of full endpoint identity |
| `DERIVED LOSSLESSLY` | no complete official-to-local field rule qualifies |
| `DERIVED WITH ASSUMPTIONS` | local `attempt==1`; direct pipeline/fallback interpretation; treating a selected-provider summary as local `provider` |
| `REPOSITORY-CONVENTION ONLY` | local schema marker, `requested_model`, `requested_provider_only`, `routing_strategy=direct`, `actual_model`, broad `azure`, attempts child schema and `outcome=success`, fallback-name heuristics |
| `UNSUPPORTED` | endpoint collection/invariants, provider granularity, served-model precedence, official error union, cache-status attestation, exact strategy values, exact pipeline stage taxonomy |

Only the first class and future clearly justified lossless derivations may enter
an authoritative positive mapping. The current normalized positive results
remain local-only.

## 10. Success/error envelope placement

### Success envelope

Manifest v0 describes router metadata on the primary response but does not
retain a complete Chat Completions success schema or an exact structured
placement record. The local parser does not require HTTP status, response ID,
choices, content, usage, or a top-level served-model field. It can accept the
repository wrapper with metadata alone. Success-envelope mapping is therefore
`INCOMPLETE`.

### Error envelope

Manifest F13 says complete evidence is not guaranteed on every success or
failure, but no error-union schema or metadata placement is retained. The v1
parser has no provider error-envelope branch; a benign envelope-level `error`
can be treated as opaque if all local success metadata is also present. Its
exceptions are local guard failures, not OpenRouter error decoding.

The sealed route-controls experiment tested only repository-normalized success
acceptance and synthetic failure probes. Official error-envelope mapping is
`OUT OF SCOPE` for v1 and remains `INCOMPLETE` as specification evidence.

## 11. Cache-hit semantics

F05 supports two distinct claims: `X-OpenRouter-Cache:false` expresses request
intent to disable OpenRouter response caching, and cache hits may omit
`openrouter_metadata`. It does not permit the converse inference.

The v1 parser correctly distinguishes:

- missing metadata -> `ROUTER_METADATA_MISSING`;
- metadata present -> `METADATA_PRESENT_NO_CACHE_HIT_INFERENCE`;
- injected cache-like keys -> fail closed at G22.

It does not parse response headers and cannot attest an official cache hit.
OS13 and OS20 are synthetic semantic probes, not captured cache traffic.
Therefore cache-hit handling is honest but official mapping is `INCOMPLETE`.

## 12. Attempt/attempts semantics

F04 retains only that the successful attempt number is one-based and that
attempt details may be optional. It does not retain exact types, field paths,
failure semantics, or the interaction between the summary attempt and details.

The local parser:

- rejects missing, boolean, zero, negative, or non-integer attempt values;
- rejects every positive value other than 1 for this one-attempt experiment;
- preserves `attempts` absent as `ABSENT_ACCEPTED`;
- preserves a valid singleton list as `PRESENT_CONSISTENT`;
- rejects present-empty, malformed, inconsistent, or multi-entry lists;
- never synthesizes an absent list.

That is a coherent local control contract, but not an exact official mapping.
The future schema must retain `ABSENT`, `PRESENT_EMPTY`, and
`PRESENT_WITH_ENTRIES` before the control policy decides which states are
acceptable.

## 13. Endpoints/provider granularity

Manifest v0 does not retain `endpoints.total`, `endpoints.available[]`, their
child types, or any selected-entry invariant. It cannot answer whether total
equals array length, whether filtering may omit entries, how many entries may be
selected on success or failure, or whether unknown endpoint fields are opaque.

F02 and F04 establish only a negative boundary: the requested full endpoint
selector can be `azure/swedencentral`, while the primary response metadata does
not attest a selected full endpoint slug or endpoint ID. The v1 parser therefore
rejects exact-endpoint-like response claims and leaves exact endpoint response
attestation as `NOT_ESTABLISHED`.

| Granularity | v0 mapping result |
|---|---|
| `EXACT_ENDPOINT_SLUG` | Request intent only; absent from response attestation |
| `BASE_PROVIDER_SLUG` | Local value `azure` is derived by splitting the request selector; official mapping not retained |
| `PROVIDER_ORGANIZATION` | Not established |
| `HUMAN_DISPLAY_NAME` | Not established |
| `UNKNOWN` | Correct official-wire classification for the v1 response `provider` field |

The receipt's `BROAD_PROVIDER_ONLY` label is honest about its own local claim,
but the exact official provider-field granularity remains `UNKNOWN`. It must not
be promoted to endpoint identity or treated as an officially established base
slug without a new evidence record.

## 14. Strategy and pipeline semantics

Manifest F04 retains strategy and optional pipeline concepts, not the exact
field names, allowed values, stage schema, or authority of either field.

The v1 parser applies repository rules:

- local `routing_strategy` must equal `direct`;
- local `fallback_observed` must be false or absent;
- local `pipeline` defaults to an empty list;
- each present stage must be an object;
- a stage named `fallback` or containing fallback-like keys fails;
- other unknown stages are accepted as opaque diagnostics.

The literals `direct` and `fallback` are not grounded as official response
values by manifest v0. The same is true for candidate values `auto`, `alias`,
`latest`, `fusion`, `bodybuilder`, and any future value.

Future authoritative policy is frozen for dependency planning as follows:

- unknown or ungrounded strategy values fail closed for a positive route
  attestation;
- request-side no-fallback intent is never inferred from a response strategy;
- until manifest v1 establishes a stage taxonomy, a positive promotion fixture
  requires `pipeline` to be absent;
- a present pipeline may be retained as opaque diagnostics, but it cannot
  support a positive control result and must not be silently discarded when it
  could indicate request transformation.

The current v1 acceptance of unknown non-fallback pipeline stages therefore
does not satisfy the future authoritative policy.

## 15. Unknown-field policy

The v1 local parser provides useful forward-compatibility controls:

- exact raw bytes remain in evidence;
- harmless unknown envelope, metadata, attempt, and pipeline content contributes
  to a canonical digest and count;
- duplicate JSON names are rejected;
- unknown content cannot override a known name by collision;
- recursively authority-like names fail at G21;
- cache-, fallback-, and exact-endpoint-like names fail at their dedicated
  guards.

SS03 proves only that a repository-created `future_field` and
`future_envelope` remain non-authoritative. It is not an official additive-field
fixture. The current parser also treats official-looking candidate names such as
`requested`, `strategy`, `region`, `summary`, `is_byok`, `selected`, and
`selection` as unknown authority keys. That is further evidence that the parser
cannot consume an official-shaped object directly.

A future raw-wire parser should preserve this principle: known evidenced fields
drive control decisions; harmless additive fields remain non-authoritative and
may be digested; duplicates, ambiguous shadowing, or authority collisions fail
closed. The exact collision set must follow manifest v1 rather than v1's local
name heuristics.

## 16. Manifest sufficiency

**Result: `SPECIFICATION MANIFEST v1 EXTENSION REQUIRED`.**

Manifest v0 is sufficient for request-side route intent and for the negative
claim that exact endpoint response identity is not established. It is
insufficient for official response parsing.

The next evidence lineage must add, at minimum, content-addressed records for:

1. the inspectable official Router Metadata source snapshot, including bytes,
   length, digest, retrieval time, section anchors, and drift policy;
2. the inspectable official OpenAPI snapshot or canonical schema extract for
   `OpenRouterMetadata`, endpoint metadata, router attempts, and pipeline stages;
3. every field's exact name/path, JSON type, requiredness, nullability,
   cardinality, child schema, enum where applicable, and additive-field policy;
4. Chat Completions success-envelope placement and the authoritative served-model
   source/precedence;
5. error-envelope placement and which failures may carry or omit metadata;
6. cache-hit omission and any official response-header evidence required to
   attest a hit without inferring it from absence;
7. attempt indexing, success/failure meaning, and summary-versus-`attempts[]`
   consistency semantics;
8. endpoint collection invariants and selected-entry semantics;
9. provider value granularity and whether it is a slug, organization, display
   label, or another identifier;
10. strategy values and pipeline-stage authority/materiality;
11. a content-addressed official-wire-to-internal mapping fact for every field
    retained in the future normalized schema.

These are required record semantics, not invented future evidence IDs. IDs and
digests can be assigned only after the new source bytes and facts exist. The
sealed `openrouter_official_specification_evidence_v0.json` must not be expanded
or rewritten.

## 17. Required official-shape fixture design

All three positive response fixtures are `REPOSITORY-NORMALIZED FIXTURE`:

| Case | Evidence ID | Raw SHA-256 | Classification |
|---|---|---|---|
| `orroutev1-ss01-metadata-attempts-absent` | `szorrawroutev1_08c1ab2113018e2289b610cf547de89c7efb88d32b98e6d2b5707d7fc20084b1` | `0c1872ef5d54d9435935708c7c7718dffc5f49ccef3a25249f06eb87d9c42127` | Repository-normalized |
| `orroutev1-ss02-metadata-attempts-present` | `szorrawroutev1_aed41af262a913498a923ce6eb362b25fdbbd084b3577c388052ef246645174e` | `d122d4ef5557a12eb781a8be55274ad001faa4af2c3fd6f7fdb92cb51844bd28` | Repository-normalized |
| `orroutev1-ss03-forward-compatible-extras` | `szorrawroutev1_070fd69da3e1339090303f40ced38dd1c5034c805cbfb9bc7c0af425ab18fc26` | `c49e06121c16337f94110d473a3d5c7ad29f0255f097fc574cbbbc41c01c50dd` | Repository-normalized |

They are generated by `build_reference_openrouter_route_response_v1`, contain a
local `schema_version`, and use local normalized names. The remaining dispatched
responses are synthetic mutations of that same object. No provider-captured,
official-example, error-response, or cache-hit fixture exists.

After manifest v1 succeeds, a separate mapping experiment must freeze fixtures
with this chain:

```text
content-addressed official example/schema provenance
  -> exact official-shape raw JSON bytes (no local schema marker)
  -> raw-envelope kind validation (success or error)
  -> field mapping with manifest record per source path
  -> normalized internal metadata
  -> bounded attestation receipt
```

Each fixture must retain its source-record ID, exact official example/schema
anchor, raw bytes, length, digest, envelope kind, expected source-path map, and
unknown/additive-field expectations. Cache absence needs independent official
cache evidence; missing metadata alone is not a cache fixture.

## 18. Static-inventory failure audit

Exact test:

`tests_dialogues/test_socrates_zero_openrouter_acquisition_cases.py::test_expected_labels_are_evaluator_side_and_cases_module_is_data_only`

The test correctly verifies that the sealed v0 cases module has only its frozen
data-contract imports and contains no provider, evaluator, network, credential,
or secret tokens. It then scans every sibling runtime `*.py` file, excluding
only the v0 cases/evaluator, and applies this raw assertion at line 564:

```python
assert "openrouter_acquisition_cases" not in path.read_text(encoding="utf-8")
```

The only offending file is
`backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py`, with
two inventory literals:

- line 1624:
  `backend/dialogues/socrates_zero/openrouter_acquisition_cases.py`;
- line 1635:
  `tests_dialogues/test_socrates_zero_openrouter_acquisition_cases.py`.

Both belong to `FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1`. The evaluator
iterates that inventory and reads each file's bytes only to compute before/after
SHA-256 mutation snapshots. The strings are neither expected labels nor case
inputs.

The exact node failed deterministically in four isolated runs. The assertion was
the sole result each time; there was no aggregate and no external activity.

## 19. Historical path-coupling classification

**Coupling classification: `PROVENANCE`.**

The route-controls evaluator does not import, execute, parse, or copy semantics
from `openrouter_acquisition_cases`. AST inspection finds no such import. It
imports its own v1 route-control cases, contracts, renderer, and parser. The two
forbidden strings are runtime-read provenance/mutation-inventory members, not a
runtime route-decision dependency or test-fixture reuse.

The raw-substring assertion is consequently a false positive against its likely
semantic goal, but the reference itself is classified by purpose as provenance.
The existing inventory contract is `PARTIAL`:

- its data-only, forbidden-seam, and expected-label separation rules are valid;
- its unqualified repository-wide substring rule conflates import/semantic
  consumption with comments, documentation, and provenance inventory;
- it is not version-aware and does not report the offending path directly.

A credible later closure is available without route-semantic changes:

1. keep sealed v1 source and artifacts unchanged;
2. make a future evaluator refer to predecessor scientific evidence through
   immutable artifact IDs, artifact SHA-256 values, semantic manifest IDs, and
   sealed commit IDs rather than mutable historical module/test paths where
   those identities are sufficient;
3. in a separately authorized boundary cleanup, replace the broad substring
   rule with an AST/reference-aware semantic-dependency rule plus a narrow,
   explicit treatment of sealed provenance—not a blanket exemption.

Because sealed v1 will continue to contain the historical strings, a full-suite
closure ultimately needs the version-aware test rule as well as clean future
evaluator provenance. No runtime route semantic change is required.

## 20. Teardown-error audit

The mandated isolated command was run once verbosely and three additional times
with compact tracebacks. All four runs produced the same assertion failure and
no teardown exception. An additional setup/teardown-visible run by an
independent audit also completed fixture teardown cleanly.

**Isolated classification: `NOT REPRODUCIBLE`.**

The autouse acquisition fixture enters `AcquisitionBoundaryTripwireV0`, yields
to the test, calls `assert_clean()`, then restores patches and resets its context
token. Those cleanup steps completed in isolation. There is no evidence of a
test-local leaked monkeypatch, environment mutation, file handle, duplicate
cleanup, or new-code teardown defect.

The earlier repository-wide run did report a teardown hit. A prior read-only
diagnostic retained it as
`credential_access_attempts=1` at
`os.path.exists:<venv>/Lib/site-packages/anthropic/lib/credentials/_types.py`,
with network/provider/model/tool/CED counters all zero. The tripwire's path
heuristic classifies any path component containing `credential` as secret-like;
that installed source-directory name therefore produced a diagnostic taxonomy
false positive. Since the hit did not recur in the mandated isolated runs, it is
suite-order/global-process dependent rather than a deterministic property of
this test.

Thus the isolated teardown has no root cause to repair. The historical
suite-only symptom is explained by broad path classification, not actual secret
access or hidden external execution.

## 21. Repository-boundary verdict

| Repository question | Verdict |
|---|---|
| Static assertion | Deterministically failing |
| Runtime import of predecessor cases | None |
| Runtime route-semantic dependence | None |
| Reference purpose | Provenance/mutation inventory |
| Teardown in isolation | Clean; prior error not reproduced |
| Existing inventory contract | `PARTIAL` |
| Runtime route semantic change required | `NO` |
| Credible closure path | `YES`, through version-aware semantic inventory plus immutable provenance |
| Current repository-integrity status | `INCOMPLETE` |

Repository integrity cannot be called green. It also does not logically supply
the missing official schema. The boundary issue is real test-suite debt with a
non-semantic repair path, while manifest evidence is the smaller prerequisite
that must come first.

## 22. Decision matrix

| Candidate | Evidence | Result |
|---|---|---|
| `NEW OFFICIAL-WIRE MAPPING v2 EXPERIMENT EARNED` | No case/path mapping; no structured schema/types; no official-shape fixture; suite still red | Rejected |
| `SPECIFICATION EVIDENCE MANIFEST v1 REQUIRED FIRST` | Exact fields, types, placements, provider granularity, and mappings are missing/ambiguous in v0 | **Selected** |
| `REPOSITORY BOUNDARY CLEANUP REQUIRED FIRST` | Credible cleanup is needed later, but there is no route-semantic predecessor coupling and cleanup cannot characterize the wire mapping | Rejected as first dependency |
| `OPENROUTER ROUTE-CONTROL APPROACH NOT JUSTIFIED` | v0 proves an evidence gap, not that official sources can never expose a usable contract | Not established |

There is no tie. The preferred dependency rule explicitly places specification
evidence first when the exact mapping cannot be characterized from the sealed
manifest.

## 23. Exactly one decision

# `SPECIFICATION EVIDENCE MANIFEST v1 REQUIRED FIRST`

No parser/evaluator implementation is authorized by this decision. P17, P18,
P19, the live pilot, Experience Store, learned Value, learned Policy, and RL all
remain blocked.

### Integrity and test gates

- 12/12 frozen file hashes matched: Phase 5; Phase 7 primary and BestOfN;
  Phase 8 falsified v1; Phase 8 v2 and replay lock; Acquisition artifact,
  replay execution, and replay lock; OpenRouter adapter-controls v0; OpenRouter
  manifest v0; and Route Controls v1.
- The manifest semantic binding, route artifact canonical bytes/falsification,
  ten historical locks/core source, Acquisition historical/core locks, Phase 8
  v2 artifact/replay, and all focused parser tests completed as `24 passed`.
- The exact static-inventory node completed as `1 failed` in each of four
  isolated runs, with no teardown error.
- `git diff --check` is clean.
- The authoritative route aggregate and replay were not run.

### Gate activity

| Activity | Count |
|---|---:|
| Documentation fetches | 0 |
| Authenticated API calls | 0 |
| Credential accesses | 0 |
| DNS attempts | 0 |
| Network attempts | 0 |
| Provider calls | 0 |
| Model executions | 0 |
| Runtime tool calls | 0 |
| CED application invocations | 0 |

No observation was applied to CED, and no protected untracked file was touched.

## 24. Exact next branch and falsifiable hypothesis

**Next branch:**
`feature/socrates-zero-openrouter-wire-spec-evidence-v1`

**Primary hypothesis:**

> A new versioned, content-addressed official specification manifest can retain
> the complete OpenRouter response-metadata field names, types, requiredness,
> success/error/cache placement, endpoint and attempt schemas, provider
> granularity, strategy/pipeline semantics, and additive-field policy needed to
> define an exact official-wire-to-internal mapping without implementing or
> calling an adapter or parser.

**Why this comes first:** the current manifest cannot characterize an exact
violation path or complete mapping. Repository cleanup cannot create missing
official schema evidence.

**Frozen components:** Route Controls v1 artifact/result/replay absence;
renderer, parser, contracts, cases, evaluator, thresholds and fixtures; manifest
v0; adapter-controls v0; all earlier scientific artifacts; request intent;
production adapters; CED and canonical Socratic semantics.

**Minimum scope:** official OpenAPI `OpenRouterMetadata` and child schemas;
Chat Completions success/error placement; cache-absence and response-header
evidence; endpoint/attempts/provider types and granularity; strategy/pipeline
semantics; stability/additive-field policy; new content-addressed source and
fact records, timestamps, canonicalization, drift and validity rules. No
adapter/parser implementation and no live API call.

**Success criteria:**

- inspectable source snapshots have exact bytes, non-null lengths, digests,
  retrieval times, and validity/drift policies;
- every required official path has type, presence, nullability, envelope kind,
  semantic meaning, and source anchor;
- success, error, and cache-absence contracts are separated;
- provider granularity and actual-served-model precedence are exact;
- attempt/attempts and endpoint collection invariants are explicit;
- strategy, pipeline, and additive-field authority are explicit;
- every future internal field has either a directly documented source path or a
  justified lossless derivation;
- unsupported or unavailable evidence remains explicitly `NOT_ESTABLISHED`;
- the manifest is content-addressed, internally verifiable, and does not mutate
  v0.

**Falsification criteria:**

- official sources do not expose one or more mandatory path/type/placement or
  granularity relationships;
- exact response mapping still requires repository convention or unsupported
  default synthesis;
- success/error/cache forms cannot be distinguished without a live follow-up or
  invented semantics;
- source material cannot be frozen with a clear canonicalization and drift
  policy;
- the required exact endpoint or actual-model claim is absent from the official
  one-call response contract.

**What success unlocks:** a new decision gate on whether a one-factor,
raw-official-shape wire-mapping v2 experiment is earned, followed separately by
the repository-boundary closure needed for a green suite.

**What remains blocked:** wire-mapping v2 implementation until manifest v1
succeeds; Phase 8.5E/live execution; P17/P18/P19; Experience Store; learned
Value; learned Policy; and RL.

# SocratesZero Phase 8.5D-S — OpenRouter Wire Specification Manifest v1

## 1. Executive verdict

**Hypothesis status: `FALSIFIED`.**

This result is narrow and environment-specific. The single frozen six-source
retrieval pass produced six `NETWORK_ERROR` events before any official response
bytes were received. Consequently the repository could not retain inspectable
official OpenRouter source snapshots, extract typed facts, create official-wire
mapping records, or establish any of the fourteen mandatory response-schema
relationships.

This does **not** prove that the official OpenRouter documentation is inherently
insufficient. It proves that, under the frozen one-pass retrieval protocol and
this execution environment, the required inspectable evidence was not
obtainable. No second downloader, substitute source, seventh locator, web
search, parser convention, or model memory was used to rescue the hypothesis.

The permanent decision is therefore:

```text
OPENROUTER WIRE SPECIFICATION MANIFEST v1 FALSIFIED
WIRE-MAPPING v2 IMPLEMENTATION NOT EARNED
RETURN TO ARCHITECTURE DECISION
```

## 2. Repository checkpoint

| Item | Value |
|---|---|
| Branch | `feature/socrates-zero-openrouter-wire-spec-evidence-v1` |
| Base Git HEAD in uploaded worktree | `5ac106b61c9c79b9b9090b5824b967a6a435cca3` |
| Parent decision | `SPECIFICATION EVIDENCE MANIFEST v1 REQUIRED FIRST` |
| Runtime/parser changes | none |
| Route Controls v1 changes | none |
| Manifest v0 changes | none |
| Credential/authenticated/inference/model/CED activity | `0/0/0/0/0` |

The assistant completion environment received a source snapshot without the
`.git` directory. It therefore produced an updated worktree ZIP and patch, not
a new authentic Git commit or HEAD. The user can apply the returned snapshot or
patch on the existing local branch and commit it there.

## 3. Frozen hypothesis

The predeclared hypothesis was:

> Current official OpenRouter public sources contain sufficient exact
> response-schema evidence to build a content-addressed manifest in which every
> future authoritative normalized field is linked to an official source path,
> JSON type, presence rule, nullability rule, envelope kind, semantic meaning,
> and either a directly documented or demonstrably lossless mapping.

The success thresholds required all six planned sources to be retained and all
fourteen mandatory relationships to be established. Missing or ambiguous
evidence was required to remain `NOT_ESTABLISHED`.

## 4. Frozen source plan

| Item | Frozen value |
|---|---|
| Source-plan ID | `szorwiresourceplanv1_19b0fcbaab0004ab5db0b7d529f8eaf055ccbcba75b68b48a3a059c540bb98cc` |
| Source-plan SHA-256 | `cfaec71b93a88114e9378fe297d8cd5ec9645e6c747877eadd622003de9760a5` |
| Canonical plan length | `9,030` bytes |
| Official domain | `openrouter.ai` |
| Planned direct HTTPS GETs | `6` |
| Retries | `0` |
| Browser/page inspections | `0` |
| Redirect policy | at most one same-origin HTTPS redirect |
| Per-source response cap | `8 MiB` |
| Total response cap | `20 MiB` |
| Retained evidence cap | `1 MiB` |
| Timeout | `20 seconds` per request |

The six frozen source roles were:

1. public OpenAPI schema;
2. router-metadata documentation;
3. Chat Completions reference;
4. response-cache documentation;
5. provider-routing documentation;
6. model-fallback documentation.

No seventh or substitute source was added after the plan was frozen.

## 5. Source/evidence contract delivered

The implementation added immutable, import-inert contracts for:

- bounded source-plan records;
- retrieval policy and canonicalization policy;
- structured redirect hops;
- raw `Content-Type` provenance;
- retrieval events and logs;
- retained raw/canonical source snapshots;
- exact byte-range lineage;
- source/fact/mapping/fixture-blueprint records;
- mandatory relationship assessments;
- manifest sufficiency thresholds and metrics;
- authoritative validation and deterministic offline revalidation.

The snapshot builder verifies lengths, SHA-256 values, retained byte ranges,
canonical extracts, event/snapshot links, temporal ordering, media type,
redirect provenance, and the global retained-evidence cap. It does not accept a
caller-declared digest or anchor without recomputing it from retained bytes.

## 6. One bounded official-source retrieval

Exactly one six-source retrieval pass was executed under the frozen plan.
Every event failed before receiving source bytes:

| Seq. | Source key | Result | Response bytes | Snapshot |
|---:|---|---|---:|---|
| 1 | `ORWIRE-S01-OPENAPI` | `NETWORK_ERROR` | 0 | none |
| 2 | `ORWIRE-S02-ROUTER-METADATA` | `NETWORK_ERROR` | 0 | none |
| 3 | `ORWIRE-S03-CHAT-REFERENCE` | `NETWORK_ERROR` | 0 | none |
| 4 | `ORWIRE-S04-RESPONSE-CACHE` | `NETWORK_ERROR` | 0 | none |
| 5 | `ORWIRE-S05-PROVIDER-ROUTING` | `NETWORK_ERROR` | 0 | none |
| 6 | `ORWIRE-S06-MODEL-FALLBACKS` | `NETWORK_ERROR` | 0 | none |

No HTTP status, final locator, content type, redirect hop, response body, raw
snapshot, or canonical extract was available. The retrieval was not repeated.

Retrieval evidence:

| Item | Value |
|---|---|
| Retrieval-log ID | `szorwireretrievallogv1_df7bb7728564d549057a9cd135eab07cb3377315b907ef092cd74e24a72295e4` |
| Retrieval-log SHA-256 | `8e9a6ecfe41c444323cf01c0e8d6d11ad1fd1e09d5400c14b5bf4c63278d5fd3` |
| Public document fetch attempts | 6 |
| Failed fetches | 6 |
| Retained sources | 0 |
| Received source bytes | 0 |
| Redirects | 0 |
| Authenticated API calls | 0 |
| Credential accesses | 0 |
| Provider inference calls | 0 |
| Model executions | 0 |
| Paid requests | 0 |
| CED runtime tool calls | 0 |

## 7. Manifest v1 result

Because no official bytes were retained, the manifest correctly contains:

- six typed failed source-evidence records;
- zero positive fact records;
- zero mapping records;
- zero official-shape fixture blueprints;
- fourteen mandatory relationship assessments, all `NOT_ESTABLISHED`;
- provider granularity `UNKNOWN`;
- P17, P18 and P19 all `NOT_ESTABLISHED`.

Manifest identity:

| Item | Value |
|---|---|
| Manifest ID | `szorwirespecmanifestv1_bb4919b28f1913de4484c54dadbece8f0e16876ce233aa12eaaf00eb506a3a41` |
| Manifest SHA-256 | `cafd9364db1357b9aa676a7b45baeac2ef8a9f1b4288044fbaed95fcb3d4397b` |
| Manifest path | `docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/evidence/openrouter_official_wire_specification_manifest_v1.json` |
| Drift policy | snapshot-only; revalidate before future authorization; fail closed on drift |

## 8. Mandatory relationship coverage

All fourteen relationships remained `NOT_ESTABLISHED`:

1. success-envelope placement;
2. error-envelope placement;
3. cache metadata absence;
4. cache attestation;
5. attempt semantics;
6. attempts-list semantics;
7. endpoint collection;
8. provider granularity;
9. served-model precedence;
10. strategy semantics;
11. pipeline semantics;
12. unknown/additive-field policy;
13. exact endpoint response identity;
14. actual served-model identity.

No relationship was populated from the previous prose manifest, repository
field names, current web memory, or a guessed OpenRouter response shape.

## 9. Authoritative sufficiency evaluation

| Item | Value |
|---|---|
| Validation ID | `szorwiremanifestvalidationv1_9a30a408ff6c4537319cfc8b1e3c62fec24e783f2d52db6a498612d10464fee2` |
| Validation SHA-256 | `26c4616bb6b07ca3e5d2d0a1385c2d10aa8e9d523f90ca2c87d9872dc2ee4bc7` |
| Metrics ID | `szorwiresufficiencymetricsv1_c57ceee753b478b1816fb6254e9874182798024b58ac65d0e4f82f262e966593` |
| Thresholds ID | `szorwiresufficiencythresholdsv1_6e37575e6dd365947a74d15554a47403df911c698dcce3baf6106d7e4769d823` |
| Hypothesis status | `FALSIFIED` |
| Retained/required sources | `0/6` |
| Established/required relationships | `0/14` |
| Facts | 0 |
| Mappings | 0 |
| Fixture blueprints | 0 |

Frozen failure reasons:

- `OFFICIAL_SOURCE_SNAPSHOTS_INCOMPLETE`;
- `OFFICIAL_DOCUMENT_RETRIEVAL_FAILED`;
- `INSPECTABLE_SOURCE_BYTES_INCOMPLETE`;
- `MANDATORY_RELATIONSHIPS_NOT_ESTABLISHED`;
- `NOT_ESTABLISHED_RELATIONSHIPS_PRESENT`;
- `EXACT_ENDPOINT_RESPONSE_IDENTITY_NOT_ESTABLISHED`;
- `ACTUAL_SERVED_MODEL_IDENTITY_NOT_ESTABLISHED`.

## 10. Offline deterministic revalidation

The persisted source plan, retrieval log, manifest, and validation artifact were
reloaded without documentation retrieval. Every ID and digest was recomputed.

| Item | Result |
|---|---|
| Revalidation ID | `szorwiremanifestrevalidationv1_436590983388bb4d412d7db3c5124c9ce56480056ff3fb7d41569a37bb9c18a3` |
| Revalidation file SHA-256 | `c389c1816b364e787ba5270b121fdeb820a7426182f6d1d69e6a51aa796f187b` |
| Semantic equality | `true` |
| Manifest-ID equality | `true` |
| Validation-result equality | `true` |
| Manifest byte identity | `true` |
| Validation byte identity | `true` |
| Additional documentation fetches | 0 |

This proves deterministic preservation of the negative result. It does not
prove that the official sources themselves lack the required schema.

## 11. Test and integrity results

### Phase 8.5D-S focused gates

- `29 passed` for source contracts, bounded acquisition, manifest contracts,
  artifact validation, and offline revalidation.
- Python compilation passed for the new source/manifest modules and scripts.

### Broader OpenRouter selection

- `374 passed`.
- `1` deterministic known failure remained:
  `test_expected_labels_are_evaluator_side_and_cases_module_is_data_only`.
- This is the inherited Route Controls v1 provenance-path boundary already
  documented by Phase 8.5D-R; it is not caused by the new manifest code.

### Snapshot-environment limitation

The uploaded ZIP intentionally excluded `.git`. Historical tests that execute
`git show HEAD:<path>` therefore fail with `fatal: not a git repository` in the
assistant container. A full repository-wide green result cannot honestly be
claimed from this environment. These failures do not identify a new semantic
regression, but they must be rerun in the user's actual Git worktree after the
returned patch/snapshot is applied.

## 12. Frozen predecessor integrity

The following predecessor artifacts were rehashed and remained exact:

| Artifact | SHA-256 |
|---|---|
| Phase 5 benchmark | `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c` |
| Phase 7 primary | `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca` |
| Phase 7 BestOfN | `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637` |
| Phase 8 falsified v1 | `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea` |
| Phase 8 v2 | `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc` |
| Phase 8 v2 replay lock | `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224` |
| Acquisition artifact | `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255` |
| Acquisition replay execution | `7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b` |
| Acquisition replay lock | `335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c` |
| OpenRouter adapter-controls v0 | `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083` |
| OpenRouter manifest v0 | `818a1ec466bd37bd23dd86ef14fecf0fcc0049360bef7b5a16fdc2f575069e9f` |
| Route Controls v1 | `61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661` |

Parser, renderer, adapters, CED, Hybrid, SearchState, Projection, Value, Policy,
search strategies, successor environment, and all sealed predecessors remained
unchanged by this milestone.

## 13. What this phase proves

This phase proves that the repository now has a strict, typed and
content-addressed evidence pipeline that:

- freezes a bounded source plan before retrieval;
- refuses source substitution and second-pass rescue;
- verifies retained bytes and canonical extracts rather than trusting supplied
  digests;
- represents retrieval failure as typed evidence;
- prevents missing sources from becoming positive facts or mappings;
- independently evaluates manifest sufficiency;
- preserves a negative result deterministically offline.

## 14. What this phase does not prove

It does not prove:

- that current official OpenRouter documentation is insufficient;
- that OpenRouter lacks the required wire schema;
- parser correctness or response conformance;
- live endpoint/provider/model identity;
- P17 input-token bounds;
- P18 pricing evidence;
- P19 pre-dispatch cost bounds;
- credential/network safety;
- live-pilot readiness;
- canonical observation admission;
- shadow/counterfactual validity;
- Experience Store, learned Value/Policy, RL, or production readiness.

## 15. Final decision and roadmap

```text
HYPOTHESIS STATUS: FALSIFIED
WIRE-MAPPING v2 IMPLEMENTATION: NOT EARNED
LIVE PILOT: NOT EARNED
P17 / P18 / P19: NOT_ESTABLISHED
EXPERIENCE STORE: BLOCKED
LEARNED VALUE: BLOCKED
LEARNED POLICY: BLOCKED
RL: BLOCKED
PRODUCTION AUTHORITY: NONE
```

Under the frozen anti-loop rule, no immediate manifest v2 is authorized. The
negative result and source-attempt evidence are preserved, and the next action
is:

```text
RETURN TO ARCHITECTURE DECISION
```

A future decision may choose to run the already-frozen source plan in an
environment that can actually retain the six official public sources, or defer
OpenRouter certification and return to the Socratic core. It must not silently
reinterpret this artifact or fill the missing schema from memory.

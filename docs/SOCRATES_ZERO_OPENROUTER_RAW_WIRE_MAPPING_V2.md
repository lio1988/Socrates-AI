# SocratesZero — OpenRouter Raw Wire-Mapping v2

Phase 8.5D-S5. Branch `feature/socrates-zero-openrouter-raw-wire-mapping-v2`,
started from `feature/socrates-zero-openrouter-wire-mapping-v2-authorization-gate`
at exactly `8c6a524b469c7cb6d4b9e9145157fc8123e8d4cf`.

One bounded offline implementation attempt, as authorized by S4.

## Result — layered

| layer | status |
| --- | --- |
| Raw parser boundary | **IMPLEMENTED** |
| Offline wire-mapping v2 | **SUPPORTED** |
| Runtime authority | **NOT AUTHORIZED** |
| Live OpenRouter execution | **NOT AUTHORIZED** |
| P17 input token bound | **NOT_ESTABLISHED** |
| P18 trusted pricing | **NOT_ESTABLISHED** |
| P19 total cost bound | **NOT_ESTABLISHED** |

Legacy scientific shorthand: `OPENROUTER RAW WIRE-MAPPING v2 SUPPORTED`, meaning
only that the offline mapper was implemented and its hypothesis held. It grants
no runtime authority and authorizes no call.

## Hypothesis

> A deterministic, raw-response-first OpenRouter wire mapper can be implemented
> solely from the retained official v2r1 evidence, such that documented response
> fields are parsed and mapped losslessly, undocumented or unavailable
> authorities remain explicit epistemic states, malformed/contradictory wire
> evidence fails closed, unknown/additive fields remain non-authoritative, and no
> repository convention or historical canned-response assumption is needed.

**SUPPORTED.**

## Evidence boundary

The retained Wire Specification Manifest v2r1 and its six pinned source
snapshots, and nothing else. No second retrieval, no browsing of current
OpenRouter documentation, no model memory used to fill a schema gap.

| identity | value |
| --- | --- |
| manifest ID | `szorwirespecmanifestv2r1_a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15` |
| manifest SHA-256 | `3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb` |
| official repository | `OpenRouterTeam/docs` |
| pinned commit | `4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db` |

Both the mapper contract and its test suite bind these identities and verify the
manifest file digest rather than trusting it.

## Architecture

Three additive modules. Nothing existing was modified; Route Controls parser v1
is untouched.

| module | role |
| --- | --- |
| `openrouter_raw_wire_mapping_v2.py` | observation contract, strict decoder, header contract, normalized mapping, mapper |
| `openrouter_raw_wire_mapping_cases_v2.py` | 60 frozen fixtures and the case set |
| `openrouter_raw_wire_mapping_evaluation_v2.py` | deterministic evaluator, artifact, replay |

### Input contract

`OpenRouterRawWireObservationV2` takes raw body **bytes** plus ordered response
header evidence — not a pre-normalized dictionary from another parser — so the
same contract works unchanged on a real captured response later. It is content
addressed over body digest, body length, header-evidence digest and header count,
so mutating either after identity construction is detected. It refuses to carry
an `Authorization` header.

### Strict decoding

Rejects invalid UTF-8, invalid JSON, duplicate object keys, a non-object top
level, and non-finite numbers — including `1e999`, which overflows to infinity
through `parse_float` and would slip past `parse_constant` alone. A JSON boolean
is never accepted where the schema documents an integer.

### Envelope discrimination

From the retained schemas, not a heuristic: documented error responses require a
top-level `error` object, the normalized success response requires a top-level
`model`. Both present, or neither, fails closed. No `choices`-presence rule.

## Two findings from the retained sources

**Error-envelope metadata is a loose object.** The success schemas bind
`openrouter_metadata` to the strict `OpenRouterMetadata` ref, but the documented
error schemas declare it `additionalProperties: {}` / `type: [object, null]`.
That is why the documented 404 example legitimately omits `region`, `summary` and
`is_byok`. Required-field enforcement therefore applies to SUCCESS only —
enforcing it on ERROR would reject an officially documented response. Both halves
are locked by tests.

**Two enums, two policies.** `RoutingStrategy` is closed, so an undocumented
strategy fails closed. `PipelineStageType` is documented as growing — "The list
grows over time. Treat unknown stage types as opaque" — so an unknown stage type
is preserved opaquely and never rejected. The additive statement covers new
optional fields and new pipeline stage types; it does not extend to strategy
values.

## Field-by-field mapping

| concern | normalized field | policy |
| --- | --- | --- |
| envelope | `envelope_kind` | SUCCESS / ERROR from required-field discrimination |
| actual served model | `actual_served_model` + status | `$.model` only; never filled from anywhere else |
| requested model | `requested_model` | `$.openrouter_metadata.requested`, separate authority |
| routing strategy | `routing_strategy` | closed documented enum |
| region | `region_presence` + `region` | string / null / absent kept distinct |
| summary, attempt, is_byok | direct | typed as documented; attempt range enforced per envelope |
| endpoints | `endpoint_collection` | `total` reported as-is; no `total == len(available)` invented |
| provider | `provider_display_name` | `HUMAN_DISPLAY_NAME` granularity, named so it cannot be lost |
| attempts | `attempts_presence` + `attempts` | ABSENT / PRESENT_EMPTY / PRESENT_WITH_ENTRIES |
| params | `params_presence` + `params_sha256` | loose object, digested not trusted |
| pipeline | `pipeline_presence` + `pipeline` | stage `data` digested; unknown types opaque |
| cache | `cache_status*`, `cache_age_seconds`, `cache_ttl_seconds`, `cache_source_generation_id` | header-borne only |
| generation | `generation_id` | `X-Generation-Id`, present on every response |
| exact endpoint | `exact_endpoint_response_identity_status` + `…_identity` | `UNAVAILABLE_BY_DOCUMENTED_CONTRACT` + `None` |
| unknown fields | `unknown_field_evidence` | path, JSON type and digest only; never authoritative |

## Firewalls

These are enforced by the type system and by derived metrics, not by
documentation alone.

**Exact endpoint.** `exact_endpoint_response_identity` is typed `None` and its
status is a single-valued `Literal`. The contract refuses any attempt to give it
a value. Four differently-shaped injected unknown fields — `endpoint_slug`,
`endpoint_id`, `exact_endpoint`, `provider_slug` — are tested and change nothing.

**Cache.** Status comes only from `X-OpenRouter-Cache-Status`. Metadata absence
never yields a hit. Three documented contradictions fail closed: HIT with
metadata present, HIT on an error envelope, and a HIT-only header accompanying
MISS.

**Model.** `actual_served_model` comes only from `$.model`. A test swaps
requested and actual in both directions and confirms neither collapses into the
other, and a separate test confirms an error envelope leaves actual absent while
requested is populated.

**Provider.** Exposed as `provider_display_name`, never compared to request-side
slugs, and asserted to contain no `/`.

**Unknown fields.** Proved metamorphically per case: the body is stripped to only
the fields the mapper may read, re-mapped, and the 23-field authoritative subset
must be identical.

## Cases

60 frozen cases: 17 positive, 43 adversarial. Every fixture is built from the
retained schemas and examples; every case names the relationships and schemas
that authorize it; expectations are canonical-JSON encodings of exact normalized
fields, evaluator-side, with no predecessor label consulted. Fixtures needing
filler payload content are marked `scaffolding`.

The adversarial set exercises **31 of 31 reachable guards**. The only unexercised
code is `OBSERVATION_DIGEST_MISMATCH`, which cannot be reached through a
well-formed fixture and is locked by its own tests instead.

## Predeclared thresholds

Declared before authoritative execution and content addressed as
`szorwirethresholdsv2_47115a60114ce5e59a685eecd2928142f6d3ed9580f38fa9b74da1ebdfbc2b93`,
so they cannot be tuned afterwards without changing an identity the artifact
carries.

| threshold | required | observed |
| --- | --- | --- |
| positive cases accepted | 17 | **17** |
| adversarial cases rejected | 43 | **43** |
| unexpected results | 0 | **0** |
| invalid fixture constructions | 0 | **0** |
| guard-code mismatches | 0 | **0** |
| field mismatches | 0 | **0** |
| endpoint identity synthesis | 0 | **0** |
| requested → actual substitutions | 0 | **0** |
| provider-display → endpoint substitutions | 0 | **0** |
| metadata-absence → cache-hit inferences | 0 | **0** |
| unknown-field authority escalations | 0 | **0** |
| repository-convention mappings | 0 | **0** |
| historical canned-shape dependencies | 0 | **0** |
| external activity, all categories | 0 | **0** |

## One defect, found before authoritative execution

The static dependency detector searched for marker literals that appeared
verbatim in its own source, and it scans itself — so it reported one
repository-convention and one historical-canned-shape dependency against itself.
The markers are now assembled from fragments so the detector's source never
contains what it searches for, and import analysis was added as the authoritative
signal with the text scan as a second net. Counts are `(0, 0)`, and a test locks
the self-match specifically.

This was fixed before the authoritative aggregate ran, which is when the phase
rules permit it. Nothing was patched afterwards.

## A second defect, in the tests

The first full-suite run after the authoritative evaluation reported 54 failures
while every focused run passed. The cause was a test, not the code: the
import-inertness lock used `importlib.reload`, which rebinds every contract class
in the reloaded modules. Alphabetically the evaluator test file runs before the
mapper test file, so by the time the mapper tests ran, `type(x) is Contract` was
comparing against classes that no longer existed.

The probe now executes each module body into a throwaway package-qualified
namespace instead, which still proves nothing happens at import time under the
live tripwire but leaves the installed module objects untouched. A companion test
asserts the canonical classes are not rebound, and the suite now passes in both
file orders.

This changed no runtime code and no artifact: the authoritative artifact still
rebuilds byte-for-byte.

## Authoritative artifact and replay

| evidence | identity | SHA-256 |
| --- | --- | --- |
| artifact | `szorwireartifactv2_4585c60e4406bcdb4b2390e39f91ee31cf35bab0c545a0b0b26722e8beb9ca12` | `d42fd8486c89f4b1ec6fd8dc2d5b9aee9b7aeb23c23237adcdac929a8ace1d75` |
| replay execution | `szorwirereplayexecutionv2_a40a5c1fb016334edce508ca71b63db2d012b76c6edec39cacec433eacac1bed` | `5ed13521fb76055db86037795f60f8dd4ff8d2426b8edf8d87191012620db734` |
| replay lock | `szorwirereplaylockv2_da3d2a5f2e2ddc0e25b3b168b772b2e67a63c9c9e236b93897dadc1d91849f21` | `3ecf55bc1824fc0148cc5a94cb871562ce28cf620ac079290baca1b72186d28d` |

Case set `szorwirecasesetv2_87e7e2647c4719f06e4dee158adf33e1a3368b216640892f6de70c63665db241`;
guard order `szorwireguardsv2_025ec10b02a720219d8beb4eb96a86d850cb4566482c02621533bcc2e8a0ec58`.

Replay reloaded only persisted evidence, retrieved no sources, and rebuilt the
artifact: **semantic equality, artifact-ID equality and byte identity all true**.
The replay lock contract refuses to exist unless all three hold.

The artifact's zero claims are cross-checked against live tripwire
instrumentation rather than trusted, and building outside an active tripwire is
refused.

## Procedural deviation and post-run integrity audit

Pre-authoritative semantic freeze was established in memory/worktree but was not
committed before the first authoritative execution. The authoritative
implementation/evaluator was committed immediately afterward. A post-run
Git-object audit proved zero semantic S5 mutations between the authoritative
evidence commit and final HEAD.

This is recorded rather than hidden: the freeze should have been a commit before
the aggregate ran, and it was not. What follows is the evidence that the omission
did not affect the result.

**AUTHORITATIVE_COMMIT** — `abd761f590b0fdb27f831ddad7b354bab0810d6c`
(*feat: add deterministic OpenRouter wire-mapping v2 evaluator*), the commit that
first recorded the evaluator implementation, the authoritative artifact, the
replay execution and the replay lock together.

Git blob identities, authoritative commit versus final HEAD — compared as Git
objects, not working-tree bytes, so no newline assumption is involved:

| file | blob | status |
| --- | --- | --- |
| `openrouter_raw_wire_mapping_v2.py` | `9f17fd999d4269a7d7ca3b56fda760b9cf98e545` | IDENTICAL |
| `openrouter_raw_wire_mapping_cases_v2.py` | `577fa35ac3c27de2a2720c8fa99cb8c662fb917a` | IDENTICAL |
| `openrouter_raw_wire_mapping_evaluation_v2.py` | `311edc88e7131b2b44f7c651a83d9ece06a0b3b8` | IDENTICAL |
| `socrateszero_openrouter_raw_wire_mapping_v2.json` | `93f1ee099eec61b22851d027f259ea66530ba378` | IDENTICAL |
| `…_replay_execution_v2.json` | `3adcd6515e30f17739d84691fde9389e39f369c4` | IDENTICAL |
| `…_replay_lock_v2.json` | `384dda32da7cb6c9035e4af67577a67e1db89e79` | IDENTICAL |

Those three modules carry every frozen case definition, the thresholds, the
case-set identity and the evaluator/schema versions, so the audit covers all four
categories the integrity check requires.

Stronger than required: each semantic file appears in exactly **one** commit in
this branch's history, and its blob at that first commit equals its blob at HEAD.
They were never modified at all, not merely never modified after the aggregate.

Every commit after AUTHORITATIVE_COMMIT, classified:

| commit | changed paths | classification |
| --- | --- | --- |
| `9f8146f` | `SOCRATES_ZERO_OPENROUTER_RAW_WIRE_MAPPING_V2.md`, branch `PRESENT.md`, evaluator test file | docs + tests |
| `af368b3` | branch `MEMORY.md`, branch `PLAN.md` | docs |
| `2d0c0ff` | evaluator test file, this document | docs + tests |

**Semantic S5 files changed after authoritative execution: 0.**

### Artifact experiment binding

The authoritative artifact binds the frozen experiment completely:

| identity | present |
| --- | --- |
| case-set ID | yes — `szorwirecasesetv2_87e7e264…` |
| exact case count | yes — `metrics.total_cases` 60, with 60 case results |
| evaluator/schema version | yes — evaluation and case-result schema versions |
| predeclared thresholds identity | yes — ID plus the embedded thresholds object |
| Manifest v2r1 ID and SHA | yes — both |
| provenance identities | yes — guard-order ID, per-case fingerprint and raw observation ID on all 60 |
| external activity counters | yes — all eight zero |
| result metrics | yes |

No critical experiment identity is absent. Binding: **COMPLETE**.

## Test gates

| gate | result |
| --- | --- |
| S5 focused (mapper + evaluator) | **108 passed** |
| exact static provenance node | 1 passed |
| Route Controls focused | 103 passed |
| v1 + v2r1 evidence | 48 passed |
| provenance boundary | 64 passed |
| full `tests_dialogues` | **3387 passed, 10 skipped** (baseline 3279 / 10) |
| `git diff --check` | PASS |
| frozen predecessor surfaces | **16/16 identical** |

Route Controls sealed artifact remains
`61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661`; Manifest v1,
Manifest v2r1, the S3 provenance evidence and the S4 authorization documents are
byte-identical.

## External activity

OpenRouter calls 0. Provider calls 0. Model executions 0. Credential accesses 0.
Paid requests 0. CED applications 0. Official-source retrievals 0. Tool calls 0.
Measured by the boundary tripwire, not asserted.

## What remains blocked

P17, P18 and P19 remain NOT_ESTABLISHED. Exact endpoint response identity remains
NOT_ESTABLISHED by documented contract. The mapper is not wired into the
production adapter, does not replace Route Controls parser v1, is not consumed by
CED, and holds no governing authority. **Live OpenRouter execution remains NOT
AUTHORIZED.**

## What this unlocks

Exactly **Phase 8.5D-S6 — OpenRouter Response-Mapping Integration & Pre-Live
Safety Gate**, which may bind request intent, acquisition receipts, raw wire
observation and this normalized mapping together and verify end-to-end authority
separation, and which must determine the exact route to closing P17, P18 and P19
before any live call.

S5 alone authorizes no live call.

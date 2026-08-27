# PRESENT — feature/socrates-zero-openrouter-prelive-integration-v1

## State

- Branch: `feature/socrates-zero-openrouter-prelive-integration-v1`
- Source HEAD: `1be95cfdecd9628cdf2d1ea6abdcf66ba1aa88a6`
- Freeze HEAD: `776780a1f39c36795c1204f29e95febaf144b169`
- Phase: **authoritative frozen-v3 aggregate complete — SUPPORTED with deterministic replay.**

## A superseded earlier run

An authoritative aggregate was run before the rulings arrived, producing artifact
`szorpreliveartifactv1_6ff594b3…`. The rulings then required semantic changes, and
this phase's own rule is that a semantic change after an authoritative run
invalidates that run. It is therefore **superseded**, preserved in history at
`0ff79c9`, and removed from the working tree so nothing stale reads as current.
Its own content says so: it carries the old thresholds and preflight case-set
identities and has no `ceiling_case_set_id` field at all.

## Freeze history

Each prior freeze was superseded before any run consumed it; the current row is
the consumed authoritative frozen-v3 state:

| freeze | what it froze |
| --- | --- |
| `4861c8a4` | original |
| `fd30a7fb` | S6 rulings applied |
| `170124a` | server-enforced price ceiling |
| **current authoritative** | **P19 split into structure / coverage / authority; both coverage gaps closed** |

## Corrections that mattered

**P18 is not JIT-reachable.** The mandated granularity audit showed the retained
endpoint record exposes only a broad display provider name and an undocumented
`tag`, so a price cannot be bound to the exact selector `azure/swedencentral`.
Structural, not freshness.

**`max_price` was dismissed too early.** It is a first-party server-enforced
request-side ceiling, applied before route selection. The pricing obstacle to
safe live cost bounding is closed.

**A token-only sum was being presented as a complete worst-case total.** It is
not, while the documented per-request fee is unbounded. P19 is now three separate
states, and the formula is rendered from the same component list the code sums,
so the label and the arithmetic cannot disagree.

**"19/19 frozen predecessor surfaces" was not reproducible.** The measured figure
is 742/742 tracked files byte-identical to `1be95cf`; every difference is an
addition.

## Cost safety classification

| item | status |
| --- | --- |
| Output token bound | ESTABLISHED (256) |
| Independent request byte cap | ESTABLISHED (447 bytes — a byte cap only) |
| P17 input token bound | NOT_ESTABLISHED |
| P18 actual endpoint pricing | NOT_ESTABLISHED |
| Pricing endpoint granularity | BROAD_PROVIDER_ONLY |
| Trusted server-enforced unit-price ceiling | **ESTABLISHED** |
| P19 formula structure | READY |
| P19 applicable charge coverage | **INCOMPLETE** (`request_usd` unbounded) |
| P19 worst-case cost authority | NOT_ESTABLISHED |
| One live shadow call | **NOT_AUTHORIZED** |

Two blockers, different in kind: **P17** is structural; **charge coverage** is a
policy gap that an operator ceiling value or first-party evidence can close.

## Completed

Integration contracts; safety and budget contracts; the additive live-request
overlay and unit-price ceiling; the request modality proof; the three-way P19
split; 82 frozen cases (30 integration, 26 preflight, 26 ceiling); the
deterministic evaluator; the single authoritative offline aggregate; persisted
artifact, replay execution and replay lock; post-run regression gates; canonical
and branch documentation.

## Authoritative result

| evidence | identity | SHA-256 |
| --- | --- | --- |
| artifact | `szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779` | `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d` |
| replay execution | `szorprelivereplayexecutionv1_7b8efdb484a2a9ce99ed9682c889e5348be10c7578dbb56252cdde85ba7cb669` | `ff40af69cccd5297c5c0b2d65c82f25448c2e16a0f8019048916d5976afb5c27` |
| replay lock | `szorprelivereplaylockv1_acc9604c588d6015007961bef5f2e259b8f068677d34b0f00b38e753dbac5c8b` | `256bf8eefe71c0c1e6b468d090ca55997ddfc105065594c16ec0aeee3cf15c8a` |

Hypothesis **SUPPORTED**; every threshold passed. Replay established semantic
equality, artifact-ID equality and byte identity. Every measured boundary
counter was zero. No live call, credential access, provider/model execution,
official-source retrieval or CED application occurred.

## Tests and exact results

- S6 focused: **149 passed**
- S5 mapper + evaluator: **109 passed**
- S3 provenance + static: **64 passed**
- Route Controls: **103 passed**
- Manifest v1 + v2r1: **25 passed**
- All OpenRouter modules: **728 passed, 1 skipped**
- Full `tests_dialogues`: **3537 passed, 10 skipped, exit 0**
- Authoritative aggregate: 30 / 26 / 26 cases, 0 unexpected,
  `all_thresholds_pass` True, hypothesis `SUPPORTED`, readiness `NOT_AUTHORIZED`
- `git diff --check`: clean
- Predecessor files vs `1be95cf`: **742/742 byte-identical**
- Known timestamp race observed post-run: **NO**

## A pre-existing intermittent failure, not ours

One full-suite run failed
`test_socrates_zero_openrouter_wire_spec_source_acquisition_v1.py::test_one_shot_offline_acquisition_publishes_complete_derived_log`
with "retrieval event and snapshot bytes diverge". Diagnosed: in
`scripts/acquire_socrates_zero_openrouter_wire_spec_sources_v1.py` the loop reads
`_utc_now()` twice per iteration — line ~1232 for `snapshot.retrieved_utc`, line
~1268 for `event.completed_utc` — at one-second precision, and the log contract
requires the two to be equal. Crossing a second boundary between the reads makes
them differ. It is a clock race in a script this branch does not touch; it cannot
reach the S6 surface, and the rerun was green.

**Deliberately not fixed here:** the fix would modify a predecessor file and break
the 742/742 byte-identity gate. Filed as separate work.

## Frozen identities

| identity | value |
| --- | --- |
| integration case set | `szorintegrationcasesetv1_05922235…` |
| preflight case set | `szorpreflightcasesetv1_5e513610…` |
| ceiling case set | `szorceilingcasesetv1_58dccf6c…` |
| thresholds | `szorprelivethresholdsv1_eca78073…` |
| safety contract | `szorprelivesafetyv1_bcddf7aa…` |
| sealed request modality proof | `szorrequestmodalityv1_4769e106…` |

## Remaining

No S6 execution work remains. A live call remains **NOT_AUTHORIZED**. The two
remaining blockers retain different classifications: P17 is structural; the
unbounded documented `request_usd` charge is a policy/coverage gap.

## Next safe step

Review the persisted write-once evidence and documentation. Do not rerun the
authoritative aggregate. Publication or any S7 work requires separate explicit
authorization, and the branch must not be pushed without it.

Not pushed.

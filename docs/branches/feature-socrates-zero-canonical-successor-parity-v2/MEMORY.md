# Stable branch memory — Phase 8 v2 PRE-RESULT

## Scientific state

This branch is still **PRE-RESULT**.

```text
authoritative aggregate runs = 0
authoritative result = PENDING
authoritative artifact = PENDING
reverse replay = PENDING and not yet authorized
replay lock = PENDING
live/model/tool calls = 0/0/0
```

Nothing in the branch documentation is evidence that the v2 hypothesis is
supported. The sealed v1 hypothesis remains permanently `FALSIFIED`.

The complete pre-registration is
[`../../SOCRATES_ZERO_CANONICAL_SUCCESSOR_PARITY_V2.md`](../../SOCRATES_ZERO_CANONICAL_SUCCESSOR_PARITY_V2.md).

## Branch lineage

- Parent branch: `feature/socrates-zero-successor-failure-semantics-v1`.
- Parent HEAD at branch creation: `59bc33b792d430cca0864c6e477ca25c177ddd61`.
- Current branch: `feature/socrates-zero-canonical-successor-parity-v2`.
- Current committed implementation/test HEAD before the pending documentation
  freeze: `324fac42ab8602a80802f5c180963a7e4712047b`.
- Protected pre-existing untracked files: `scripts/live_dialogue.py.bak` and the
  malformed root filename beginning `ocratic_followup_mandate`.
- Those protected files are outside this experiment and must never be staged.

## Sealed predecessor

| Field | Immutable value |
|---|---|
| Artifact commit | `07ec5ab14cd1599ffd6c8c4b6442d56d51129f11` |
| Artifact Git blob | `f2718b95651425d940ab61764fa421e0e90a8bdc` |
| Artifact ID | `cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0` |
| Artifact SHA-256 | `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea` |
| Status | `FALSIFIED` |
| Evaluator Git blob | `8b855ac877f34e7595ced5857c8ece8e1ee365e4` |

Core transition parity was supported in v1; the old negative taxonomy was
falsified by the sole `wrong-provider` expectation mismatch. v2 does not
rewrite that record. It pre-registers dependency-aware probes under a new
evaluation lineage.

## Current deterministic pre-result IDs

| Contract | ID |
|---|---|
| Core blob lock v2 | `cedcorebloblockv2_2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957` |
| Validation order | `cedvalidationorder_2bbd60972e07a9afdc3ca6f2dd344cd891f39dab6f9edb4e92c4ba0552203a54` |
| Failure taxonomy | `cedfailuretaxonomy_73bef28686e43b201cafb33fcc536d19a863bd0773592db8aa6867b5a1189cf7` |
| Failure precedence | `cedfailureprecedence_4d75632cc9dac55daf59a87142dbd918e6c6573e48afec32f2225db10eaf7d7f` |
| Compatibility diagnostics | `cedcompatdiagnostics_b577167b4199464b250328b58dbc248194076a3f1a9370f8cf28022d56ebd44f` |
| Probe design | `cedprobedesign_fd7d21658acea185d164ccb32c726b498c0f7a3aa476b4c1698c82a1847f9e2f` |
| v2 case set | `cedparitycasesetv2_3706cb242dd60070acec46d00def5389c62fb90f869d98d932649fe023dc1233` |
| v1 corpus | `cedobscorpus_b5ebe4b46d2b3ae4fed3faded341c8a2d8ff5f5f254531f000e479bf66b7f8b7` |
| v1 corpus SHA-256 | `06c5eda5ee8c71992cb8b7427794f6d5ab6e44b4f92f0d6f71f4366d5729427c` |
| v2 composite corpus | `cedparitycorpusv2_9d7d8563b931f1206c2e685c51d62dfa66b7a5ae66a40254fb63477f9c15524d` |
| v2 corpus SHA-256 | `9d7d8563b931f1206c2e685c51d62dfa66b7a5ae66a40254fb63477f9c15524d` |
| Thresholds | `cedparitythresholdsv2_e241fe357d1a6c36e7e19addd0a421e0c55332bf16d999a2aa895fcdccf9e210` |

These are the exact current import-derived identities. Any pre-freeze semantic
edit that changes one must be reviewed and documented; after the freeze commit,
they are immutable. Artifact and replay-lock instance IDs remain `PENDING`.

## Frozen experiment law

- Runtime semantics and `ced-canonical-successor-env/v0` remain unchanged.
- Precedence is `FIRST_CANONICAL_GUARD_WINS` in the exact 44-guard source order:
  C1–C11, P1–P10, A1–A14, A15a, A15b, A16–A22.
- Public provider catalog IDs feed `council_roster`, task context, and A8 root
  compatibility before the private A10 provider guard.
- Expected reasons, guards, invariant vectors, classes, and reference truth
  remain evaluator-side only.
- The ground-truth firewall covers parameters, defaults, nonlocals, referenced
  globals, nested callable closures, forbidden enum/string values, serialized
  expected structures, Pydantic/dataclass/custom-object attributes and slots;
  otherwise-uninspectable nonprimitive carriers fail closed.
- The validity gate independently measures reference/candidate snapshots,
  literal mutations, probe stage, invariant vector, and observation-submission
  state before any invocation.
- Advisory diagnostics are immutable-snapshot comparisons only. They never
  replace the primary runtime result or invoke a later validator.
- The old five observation/reference records are referenced exactly; none are
  copied, recorded, or regenerated.
- Corpus membership is exactly `5 + 11 ORTHOGONAL + 7 PRECEDENCE = 23`.
- Every negative must create no successor, reach no canonical parser or CED
  application, dispatch nothing, and preserve source, sibling, and production
  controls.
- Exact model calls, live provider calls, and tool calls are reported
  separately and all must be zero.

## Threshold and artifact law

Exact support requires accepted parity `1/1`, canonical-rejection parity `4/4`,
orthogonal primary classifications `11/11`, precedence classifications `7/7`,
all mismatch/failure/security/isolation/lock counters zero, historical offline
fixture dispatches exactly `5`, and negative/aggregate/live/model/tool calls all
zero. A different accepted/rejection split cannot satisfy the threshold.

After the complete pre-result freeze is reviewed and committed:

1. execute exactly one authoritative 23-case aggregate;
2. publish its first artifact once whether `SUPPORTED` or `FALSIFIED`;
3. never rerun or tune on falsification;
4. run reverse-order replay only if the first artifact is `SUPPORTED`;
5. compare two actual validated artifacts internally; and
6. require semantic, artifact-ID, canonical-byte, and SHA-256 equality before a
   write-once replay lock.

Existing byte-identical publication is idempotent. A conflicting existing file
is refused. A caller cannot supply or self-certify a replay lock.

## Immutable scientific hashes

- Phase 5: `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Phase 7 primary: `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- Phase 7 BestOfN: `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- Phase 8 falsified v1: `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.

The 34-file core table and exact predecessor evidence are frozen in the master
pre-result document and in
`backend/dialogues/ced_canonical_successor_frozen_core_v2.py`.

## Pre-result verification

The complete Phase 8/v2 focused matrix passed before the freeze:

```text
151 passed
0 skipped
0 failed
0 warnings
authoritative aggregates = 0
live/provider/model/tool calls = 0/0/0/0
```

## Blocked work

No Phase 8.5 implementation, real shadow collection, depth two, Experience
Store, learned Value, learned Policy, RL, or production authority is authorized
by this branch or by a future passing v2 artifact. A pass would earn only the
next architecture decision gate.

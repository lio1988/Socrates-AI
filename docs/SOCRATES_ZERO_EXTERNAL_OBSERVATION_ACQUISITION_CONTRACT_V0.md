# SocratesZero External Observation Acquisition Contract v0

## Final status

The frozen contract and experiment are **COMPLETE — SUPPORTED**. The sole
authoritative canned aggregate and the sole reverse-order replay have been
executed under the active acquisition boundary tripwire. No live, network,
provider, model, tool or canonical-application call occurred.

Scientific chronology is preserved by:

- pre-result freeze commit:
  `e1779a7738c5cddc1e5b6d6024b84583ea72628d`;
- authoritative artifact commit:
  `70e07363aeedc205e5f13695918f735b8c5a15ea`;
- reverse replay evidence commit:
  `15e3b819b1625d71786419a0efdf8082ca29e462`.

The historical pre-result gate was `213 passed, 1 skipped`; the skip was the
prewritten artifact-only verifier awaiting publication. After publication that
verifier passed, and the complete acquisition gate was `214 passed`. The final
repository-wide gate was `3104 passed, 1 skipped, 23 warnings`; the skip is the
unchanged council-rescue scenario, while the warnings are 21 existing Pydantic
`.dict()` deprecations and two existing duplicate FastAPI operation-ID warnings.

This phase implements only external observation acquisition. Its output is an
opaque `UNADMITTED / NON_CANONICAL / NON_GOVERNING / NOT_APPLIED` envelope.
It never invokes canonical admission or
`CanonicalSuccessorEnvironmentV0.apply_observation`.

## Frozen identities

| Item | Frozen value |
|---|---|
| Acquisition contract | `socrateszero-external-observation-acquisition/v0` |
| Capability snapshot | `szacqcap_d36f538978eae2158aaf94afa71fe09a211f33cf0acaa7c33d9d6dd6b62c9656` |
| Control policy | `szacqpolicy_646029f9c7fc42fc9f29a75fe18ab8c5f6bf53efad0a0a9e6e47bf4f983a9eca` |
| Semantic request | `szacqrequest_b005c6c56dd4eeff795c7dd2427218ee01c28cba7cf6ea932a0d7b9a064c4ee1` |
| Canned transport | `socrateszero-canned-transport/v0` |
| Retention policy | `szacqretentionpolicy_89285ce39c2c1cc0e587742f75ff1410274fd2637e86bcf327ab435fd448a4fd` |
| Fixture set | `acqfixturesv0_06f9f406e084085ddb26d2f14d9d856fd73050df9ff46514ce7f718d0af74736` |
| Case set | `acqcasesetv0_80d001ddf60c390521414a50475fec53fb0d98dc81ae9a3e8d9c219f5d125c36` |
| Harness | `socrateszero-acquisition-harness/v0` |
| Thresholds | `acqthresholdsv0_b1ac8151eeca12bc3ad8f8a3005be9457ab97071d5cbea8f1e41c525e53cdc2c` |
| Validation order | `szacqvalidationorder_ed85e6507bb481001f5f1ed1afab4b392fad7e4ad49a27e735805619bbb1d109` |
| Failure taxonomy | `szacqfailuretaxonomy_90d0911e3c9726483dd7aeaf4cdd35dfac071cdc40eb9e9e5c4cdbe102f4ea86` |

Transport attempts, observations, attempt receipts, isolation receipts and
retention receipts are content-addressed per attempt. The authoritative result
is bound by:

- aggregate receipt:
  `szacqaggregate_3be4d9bbc35ee13a7f6c2ba4e562e9d18ce5c89574fd759a348d6b869cf677aa`;
- metrics:
  `acqmetricsv0_856f1af3f93217edfcf8acb1b4ac17cf757e9d0bda6f931571f63b97da440d08`;
- artifact:
  `acqartifactv0_fb7fc0b8f19607cf74cb549992a62ea94638228e8c5c9fedab65f445272c2d11`;
- artifact SHA-256:
  `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255`.

## Frozen experiment

- positive cases: `6` producing `8` successful attempt receipts;
- orthogonal probes: `43`;
- precedence probes: `7`;
- total cases: `56`;
- total attempt receipts: `58`;
- expected canned invocations: `32`;
- expected external network, credential, provider SDK, live-provider, model,
  tool and canonical-application calls: all `0`.

The exact concrete pre-result evidence is locked by:

- probe construction evidence:
  `006fe843d91ec588a22de0d587c6f3e86c8e4c942446955d8ca308e49ca90062`;
- per-case attempt-receipt membership:
  `3fa71e71327b344b93846bbff9debd9475bd141911a994d4caf362599f974be8`;
- complete case-result identities:
  `10540703f9bfa7cbd9d8910de4181e76d126de7374bfb533791b7fe2a285310c`.

These locks prevent undeclared construction changes, alternate mismatching
values hidden behind the same failure code, and coherent re-hashing of receipt
or evaluator evidence after freeze.

## Validation and precedence

The precedence rule is **FIRST ACQUISITION GUARD WINS**.

Pre-dispatch order:

1. request integrity;
2. semantic identity integrity;
3. capability snapshot integrity;
4. required-control completeness;
5. canned-only transport mode;
6. external-network prohibition;
7. credential-access prohibition;
8. exact provider/model/configuration verification capability;
9. fallback disabled;
10. explicit and adapter retries disabled;
11. SDK-internal and hidden retries disabled;
12. tools disabled;
13. bounded timeout and sealed-worker termination guarantee;
14. resource-accounting completeness;
15. budget sufficiency;
16. prompt-byte determinism;
17. isolation preconditions;
18. canned-transport registration.

Post-dispatch order:

1. canned invocation count;
2. transport completion;
3. timeout-worker termination;
4. actual provider;
5. actual model;
6. actual configuration;
7. fallback activation;
8. retry activation;
9. tool activation;
10. raw-response presence;
11. response digest/length integrity;
12. usage completeness;
13. resource-receipt integrity;
14. isolation integrity;
15. retention/privacy integrity;
16. final receipt integrity.

`IDENTITY_COLLISION` remains a reserved taxonomy subcode under P02. It is not
independently reachable in v0 because semantic, transport and provider-visible
IDs use disjoint content-addressed prefixes and round-trip validation occurs
first.

## Controls and resource policy

Required controls explicitly prove canned-only transport, exact actual
identity validation, zero fallback/retries/tools/network/credential access,
deterministic temperature and request bytes, bounded timeout, sealed-worker
termination, raw capture, complete new-execution accounting, and transport
metadata isolation. Seed is explicitly `PROVEN_UNSUPPORTED`; it is never
`UNKNOWN`.

The credential tripwire rejects exact common cloud, repository, model-hub and
package-registry secret keys, conservative password/secret/token suffixes,
bulk environment enumeration, credential-bearing paths, built-in/pathlib/I/O
opens and low-level OS opens. The network tripwire also covers UDP sends.

Every new execution quantity is typed `KNOWN` or `UNKNOWN`; unknown is never
converted to zero. Historical usage is a separate immutable object. The
deliberate adverse cases contain one expected uncounted-invocation condition
and three expected incomplete-reported-usage conditions. They pass only when
the exact frozen failures occur; unexpected/accepted accounting violations
remain zero.

## Provider-visible bytes and identity separation

Provider-visible bytes are canonical UTF-8 JSON containing the ordered
messages, response format, empty tool list, temperature, output-token bound and
provider-visible metadata. Branch ID, experiment ID, transport ID, receipt ID,
timestamps, nonces, process state and local paths are excluded.

Sibling branches share the exact semantic-request ID and exact provider-visible
bytes while receiving distinct branch-local transport-attempt IDs. Receipts
store both the declared digest/length and the digest/length of the bytes
actually rendered at the transport boundary. Dispatched attempts additionally
bind these values to the immutable canned invocation record.

## Isolation, privacy and timeout boundary

Isolation evidence covers an immutable source snapshot, a test-owned sibling
sentinel and a detached production sentinel. All are sampled before and after
every attempt. The acquisition layer has no canonical-application authority.

Provider-visible prompt text is never retained in artifacts. Non-sensitive
canned raw responses may be retained only when their SHA-256 appears in the
exact frozen allowlist. Unallowlisted bytes are classified `UNKNOWN`, excluded,
reduced to digest/length evidence, and fail A15; their raw or Base64 form never
enters a receipt or artifact.

Untrusted provider/model labels outside the requested identity and the exact
frozen non-sensitive mismatch fixture allowlist are projected to absence before
receipt construction. The encounter fails retention/privacy closed, excludes
raw bytes and cannot serialize the supplied label. Invalid historical core-lock
strings are likewise reduced to typed presence/format verdicts; only canonical
lock IDs, SHA-256 values and derived digests may enter an artifact.

The timeout guarantee is deliberately narrow: it applies only to the exact
one-shot `CannedAcquisitionTransport`. P01 and P02 touch no transport object;
P03 then validates exact class-owned methods, exact directive/envelope types,
an external construction fingerprint, component identities, pristine ledger
and record state, and revalidates immediately before dispatch. Its controlled
worker acknowledges at most the second cancellation request. Arbitrary
subclasses, mutable/poisoned exact instances and replaced worker/ledger methods
fail before dispatch. This is not an operating-system hard-kill claim and proves
nothing about a future provider SDK, concurrent Python reflection, or hostile
external code.

## Authoritative publication and replay

Exactly one authoritative aggregate wrote:

`docs/branches/feature-socrates-zero-live-acquisition-contract-v0/artifacts/socrateszero_external_observation_acquisition_v0.json`

It produced `SUPPORTED` with 56 exact case results, 58 attempt receipts,
58 isolation receipts, 58 retention receipts, 32 counted canned invocations,
eight acquired raw canned observations and zero accepted violations. Its
forbidden tripwire counters are all zero.

Exactly one reverse-order replay then wrote:

- `docs/branches/feature-socrates-zero-live-acquisition-contract-v0/artifacts/socrateszero_external_observation_acquisition_replay_execution_v0.json`;
- `docs/branches/feature-socrates-zero-live-acquisition-contract-v0/artifacts/socrateszero_external_observation_acquisition_replay_lock_v0.json`.

The replay execution ID is
`acqreplayexecutionv0_08125a577c16aa3324f395c46461651e50ce5f1df38627edf3401dbaf1b96f8f`,
its canonical file SHA-256 is
`7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b`,
and its execution-trace SHA-256 is
`1ab6fb09f74e1314027cf9499aaa36cead4f7bacb5b6fd3fe0566cf5b687db38`.
The replay lock ID is
`acqreplaylockv0_af196a855a1cefd1220a0a61b159ac75d1b8928b112704c48d7e30b686080e0a`
and its canonical file SHA-256 is
`335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c`.
Semantic equality, artifact-ID equality and byte identity are all true.

The replay execution file contains no embedded raw-bearing artifact. The lock
binds its canonical SHA-256, and the offline verifier requires all three files
to recompute artifact IDs, hashes, order and receipt crosslinks. This proves
canonical cross-file coherence and records the performed reverse run, but—
without an external nonce or trusted execution service—does not
cryptographically prove process occurrence or independence. The independence
claim remains procedural.

## Scope boundary

No external call, provider SDK, model, tool, credential access, CED application,
Search, Value ranking, action selection, Experience Store, learning, RL,
production integration or action-family extension belongs to this phase.

No production authority is granted. The next decision is
**Phase 8.5B — External Provider Pilot Authorization Gate**; this phase stops
without making a live call.

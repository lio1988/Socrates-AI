# Stable branch memory — External Observation Acquisition Contract v0

## Starting checkpoint

- Parent branch: `feature/socrates-zero-shadow-safety-gate-v0`.
- Parent/fork HEAD: `7165b85f56152d443ee7c93c423df32c2ad1ac13`.
- Current branch: `feature/socrates-zero-live-acquisition-contract-v0`.
- Protected untracked files: `scripts/live_dialogue.py.bak` and the malformed
  root filename beginning `ocratic_followup_mandate`.

## Non-negotiable invariants

- Canned/in-memory transport only.
- No network, DNS, HTTP, credential, provider SDK, model or tool execution.
- No canonical observation admission/application and no CED mutation.
- Acquisition content remains opaque and explicitly unadmitted.
- Semantic identity excludes branch/attempt/runtime entropy.
- Transport identity remains out-of-band and branch-local.
- Unknown required controls fail before canned dispatch.
- First Acquisition Guard Wins.
- Historical and new-execution usage remain separate; unknown is never zero.
- Source, sibling and production mutations remain zero.
- The pre-result freeze commit must precede the sole authoritative aggregate.
- Failed first artifacts are preserved; successful artifacts are replay-locked.
- The exact one-shot canned worker has externally recorded construction and
  component-identity seals; arbitrary subclasses and poisoned exact state fail
  P03 without virtual dispatch.
- Timeout termination is a bounded cooperative guarantee for that sealed worker,
  not an OS hard-kill or future-provider claim.
- P02 `IDENTITY_COLLISION` is reserved but structurally unreachable under the
  disjoint v0 ID prefixes and prior round-trip guard.

## Frozen pre-result design

- Contract/capability/policy/request IDs:
  `socrateszero-external-observation-acquisition/v0`,
  `szacqcap_d36f538978eae2158aaf94afa71fe09a211f33cf0acaa7c33d9d6dd6b62c9656`,
  `szacqpolicy_646029f9c7fc42fc9f29a75fe18ab8c5f6bf53efad0a0a9e6e47bf4f983a9eca`,
  `szacqrequest_b005c6c56dd4eeff795c7dd2427218ee01c28cba7cf6ea932a0d7b9a064c4ee1`.
- Case set: `56` cases = `6` positive + `43` orthogonal + `7`
  precedence; `58` receipts and `32` canned invocations.
- Case-set ID:
  `acqcasesetv0_80d001ddf60c390521414a50475fec53fb0d98dc81ae9a3e8d9c219f5d125c36`.
- Thresholds ID:
  `acqthresholdsv0_b1ac8151eeca12bc3ad8f8a3005be9457ab97071d5cbea8f1e41c525e53cdc2c`.
- Construction/receipt/result locks:
  `006fe843d91ec588a22de0d587c6f3e86c8e4c942446955d8ca308e49ca90062`,
  `3fa71e71327b344b93846bbff9debd9475bd141911a994d4caf362599f974be8`,
  `10540703f9bfa7cbd9d8910de4181e76d126de7374bfb533791b7fe2a285310c`.
- Focused pre-result gate: `213 passed, 1 skipped`; the skip is the prewritten
  artifact-only verification test awaiting publication.
- Authoritative aggregate/replay/publishers invoked: `0 / 0 / 0`.

## Frozen repository evidence

- Phase 5 SHA-256:
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Phase 7 primary SHA-256:
  `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- Phase 7 BestOfN SHA-256:
  `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- Phase 8 v1 SHA-256:
  `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.
- Phase 8 v2 SHA-256:
  `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc`.
- Phase 8 v2 replay SHA-256:
  `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224`.
- Frozen core lock:
  `cedcorebloblockv2_2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957`.

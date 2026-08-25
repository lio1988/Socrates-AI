# Stable branch memory — Phase 8.5 shadow safety gate

## Starting checkpoint

- Parent branch: `feature/socrates-zero-canonical-successor-parity-v2`.
- Parent/fork HEAD: `f561cf5f3b7366599b18f77efb8a8141d978d701`.
- Current branch: `feature/socrates-zero-shadow-safety-gate-v0`.
- Protected untracked files: `scripts/live_dialogue.py.bak` and the malformed
  root filename beginning `ocratic_followup_mandate`.
- Both protected files remain untouched and unstaged.

## Frozen evidence

| Evidence | Value |
|---|---|
| Phase 8 v2 artifact | `cedparityartifactv2_f3a9c85ef31dd5afc09c1353ff8fb67461ebce42ae5390a3dff1efb0f2e109e7` |
| Phase 8 v2 SHA-256 | `8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc` |
| Replay-lock SHA-256 | `896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224` |
| Frozen core blobs | `34 / 34` exact |
| Phase 8 v1 status | `FALSIFIED` and unchanged |
| Runtime semantic changes | none |
| Gate external network/live-provider/model/tool calls | `0 / 0 / 0 / 0` |

## Exact supported root facts

~~~text
root cardinality = SINGLE-ACTION ROOT ONLY
action count = 1
action ID = szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421
supported family contract = ced-opening-socratic-question/v0
LegalAction kind = ASK_SOCRATIC_QUESTION
phase/role/task = OPENING / SOCRATES / SOCRATIC_QUESTION
round/slot/attempt = 0 / 0 / 0
same-root provider/model/agent variation = NO / NO / NO
root Value v1 = 0.0
accepted successor Value v1 = 0.0
champion live-compatible = NO
~~~

## Hard live blockers

1. environment v0 accepts only explicit fake/offline adapters;
2. observation privacy is literally `offline_fixture`;
3. application admits only exact entries from the five-record frozen manifest;
4. the current recorder dispatches on and mutates authoritative CED state;
5. no immutable branch-local request/attempt/resource receipt joins complete
   requested/actual identity, prompt/config, retries/fallback, tokens/cost and
   isolation evidence;
6. no provider-selected, end-to-end enforceable total-token, cost and
   total-wall-time acquisition budget can be frozen;
7. Anthropic SDK-internal retries are not pinned off, and NVIDIA timeout
   cancellation does not prove termination of the worker request; and
8. the current OpenRouter prompt can expose random task identity, so out-of-band
   transport identity and cross-branch semantic prompt-byte equality are not
   proven.

## Decision

`REAL SHADOW NOT YET EARNED`.

The sole authorized next branch is
`feature/socrates-zero-live-acquisition-contract-v0`. It is an offline-only
acquisition-contract/preflight prerequisite with zero external
network/live-provider/model/tool calls and separately counted bounded canned
transport invocations. Success permits only a new Phase 8.5 gate.

## Still blocked

Every live pilot, same-action replication, multi-action counterfactual,
cross-root provider/model comparison, action-family extension, Experience
Store, learned Value/Policy, RL, self-play, depth two, PUCT changes and
production authority.

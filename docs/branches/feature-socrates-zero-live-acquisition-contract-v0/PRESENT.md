# Current External Observation Acquisition Contract v0 state

## COMPLETE — SUPPORTED

| Item | Current state |
|---|---|
| Branch | `feature/socrates-zero-live-acquisition-contract-v0` |
| Fork HEAD | `7165b85f56152d443ee7c93c423df32c2ad1ac13` |
| Tracked worktree at fork | clean |
| External/live/provider/model/tool calls | `0/0/0/0/0` |
| Canonical application calls | `0` |
| Production authority | none |
| Frozen cases | `56 = 6 positive + 43 orthogonal + 7 precedence` |
| Frozen attempts / canned invocations | `58 / 32` |
| Focused pre-result tests | `213 passed, 1 skipped` (historical pre-publication gate) |
| Freeze commit | `e1779a7738c5cddc1e5b6d6024b84583ea72628d` |
| Authoritative artifact commit | `70e07363aeedc205e5f13695918f735b8c5a15ea` |
| Replay evidence commit | `15e3b819b1625d71786419a0efdf8082ca29e462` |
| Authoritative aggregate / replay | `SUPPORTED / byte-identical` |
| Final repository-wide gate | `3104 passed, 1 skipped, 23 warnings` |

## Completed

- Immutable contracts, semantic/transport identity separation and exact byte
  rendering.
- Exact-type/state-sealed one-shot canned runtime, 34 first-guard checks and
  complete receipts.
- Network, credential, provider/model/tool and canonical-application tripwires.
- Source/sibling/production isolation, allowlist-bound privacy, hostile metadata
  projection and privacy-safe historical lock evidence.
- `56` cases with exact expected failures and construction/receipt/result locks.
- Persisted replay-execution schema, replay lock and three-file offline verifier.
- One authoritative artifact, one reverse execution and one replay lock, with
  semantic equality, artifact-ID equality and byte identity all true.
- Post-result gates: artifact-only `1 passed`; acquisition `214 passed`;
  `tests_dialogues` `2797 passed, 1 skipped`; `tests_ced` `34 passed,
  14 warnings`; `tests` `261 passed, 9 warnings`; repository-wide
  `3104 passed, 1 skipped, 23 warnings`.

## Changed files

Additive acquisition runtime/contracts/evaluator/cases/isolation evidence,
focused tests and this branch's documentation. Frozen Search, Value, Policy,
CED, successor-environment and action-family components are unchanged.

## Evidence

- Artifact ID:
  `acqartifactv0_fb7fc0b8f19607cf74cb549992a62ea94638228e8c5c9fedab65f445272c2d11`.
- Artifact SHA-256:
  `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255`.
- Replay execution ID:
  `acqreplayexecutionv0_08125a577c16aa3324f395c46461651e50ce5f1df38627edf3401dbaf1b96f8f`.
- Replay lock ID:
  `acqreplaylockv0_af196a855a1cefd1220a0a61b159ac75d1b8928b112704c48d7e30b686080e0a`.
- All forbidden instrumented counters and all accepted-violation metrics: zero.

## Worktree protection

`scripts/live_dialogue.py.bak` and the malformed root filename beginning
`ocratic_followup_mandate` remain untouched and unstaged.

## Next decision

Stop without making a live call. The next gate is
**Phase 8.5B — External Provider Pilot Authorization Gate**. This result does
not authorize external execution, canonical observation admission or
production use.

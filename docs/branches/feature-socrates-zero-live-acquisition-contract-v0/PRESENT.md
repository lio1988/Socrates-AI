# Current External Observation Acquisition Contract v0 state

## PRE-RESULT FREEZE READY

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
| Focused pre-result tests | `213 passed, 1 skipped` (future artifact-only verifier) |
| Authoritative aggregate / replay | `not run / not run` |

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

## In progress

- Pre-result freeze commit and required pre-aggregate report.

## Changed files

Additive acquisition runtime/contracts/evaluator/cases/isolation evidence,
focused tests and this branch's documentation. Frozen Search, Value, Policy,
CED, successor-environment and action-family components are unchanged.

## Remaining work

Freeze commit, sole authoritative aggregate, write-once artifact, one reverse
replay on support, full regressions and durable result checkpoint.

## Worktree protection

`scripts/live_dialogue.py.bak` and the malformed root filename beginning
`ocratic_followup_mandate` remain untouched and unstaged.

## Next safe step

Commit the complete pre-result design, report the freeze hash, then—and only
then—execute the sole authoritative aggregate under the active tripwire.

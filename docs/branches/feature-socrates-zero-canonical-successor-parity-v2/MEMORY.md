# Stable branch memory

## Starting checkpoint

- Parent branch: `feature/socrates-zero-successor-failure-semantics-v1`.
- Parent HEAD: `59bc33b792d430cca0864c6e477ca25c177ddd61`.
- New branch: `feature/socrates-zero-canonical-successor-parity-v2`.
- Tracked worktree at branch creation: clean.
- Protected pre-existing untracked files: `scripts/live_dialogue.py.bak` and
  the malformed root filename beginning `ocratic_followup_mandate`.

## Sealed predecessor

- Artifact commit: `07ec5ab14cd1599ffd6c8c4b6442d56d51129f11`.
- Artifact ID:
  `cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0`.
- SHA-256:
  `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.
- Permanent status: `FALSIFIED`.
- Core transition parity was supported; the old negative taxonomy was
  falsified by the sole `wrong-provider` expectation mismatch.

## Frozen core Git blobs at branch creation

| File | Git blob |
|---|---|
| `backend/dialogues/ced_canonical_successor.py` | `b93b5e8abcfb711ea577d5c4d622a58c9a09e4f2` |
| `backend/dialogues/ced_canonical_successor_contracts.py` | `187b35b83ae9b11ff9a79ccb38c3750348866633` |
| `backend/dialogues/ced.py` | `9a1c7ab4610c0dcc5cf40b5211095afaa694d90f` |
| `backend/dialogues/ced_search_projection.py` | `3a49ce4c9642d5fb6d8ba43a2c713f51ba674227` |
| `backend/dialogues/ced_search_projection_v1.py` | `de5caadb2adc8a60ad44dfae2d1dab8baf654b60` |
| `backend/dialogues/ced_search_observability_v1.py` | `89945d14ca0e6df7da8d08e91183f8a44b2d8d62` |
| `backend/dialogues/ced_search_value_v1.py` | `17b38f5b9ebf376600fed9d7c4be0ceaa1ea68a9` |
| `backend/dialogues/socrates_zero/contracts.py` | `086de2a94614891939b2cf9d72896044840f15b6` |
| `backend/dialogues/socrates_zero/value.py` | `eb34584219221ac15d3ef825941b7e5100915ccb` |
| `backend/dialogues/socrates_zero/policy.py` | `33b0a10cf814bf4bc5f908b878024c1eb0b74904` |
| `backend/dialogues/socrates_zero/strategy.py` | `eb36b9b771db13312f826a7a4b4a02d0e12d3662` |
| `backend/dialogues/socrates_zero/puct.py` | `576d939f214f50d1cd90bee964fa19bfa7482472` |
| `backend/dialogues/socrates_zero/baseline.py` | `1def881b0c3ed350dbcba8d96fd0f9a27741ebb2` |

These blobs jointly cover the environment, capsule, pending transition,
recorded observation, task identity, result, receipt, extracted CED seam,
SearchState/projection, Value, Policy, Greedy, BestOfN, PUCT, and baseline
lineages that must remain frozen.

## Immutable scientific hashes

- Phase 5: `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Phase 7 primary: `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- Phase 7 BestOfN: `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- Phase 8 falsified v1: `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.

## Frozen experiment law

- Precedence is `FIRST CANONICAL GUARD WINS` in actual source order.
- Expected failures and invariant vectors remain evaluator-side only.
- An actual/expected invariant-vector mismatch is
  `INVALID_PROBE_CONSTRUCTION` and is not scored as a transition result.
- The old observations and reference truth are reused exactly; none are
  recorded or regenerated.
- The first 23-case authoritative artifact is always preserved.
- A replay is permitted only after a passing first aggregate.

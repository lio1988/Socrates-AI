# Branch: feature/socrates-zero-canonical-observability-v1

## Durable facts

- Starting point: `9cddbd9efbfc1d5448025be1d11430d2ca2b256f` on the completed
  `feature/socrates-zero-search-v0` history.
- CED/Hybrid/Verifier remain the only epistemic authorities. SearchState v1 is
  a read-only observation projection and may not decide any status.
- SearchState v0 and `ced-search-state-projection/v0` are frozen. All v0 Policy,
  Value, Greedy, BestOfN, PUCT, evaluation artifacts, and semantic identities
  are frozen as well.
- The Phase 5 artifact SHA-256 must remain
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Canonical eligible families are typed evidence, verification results,
  governing claim assessments, objection lifecycle, and contradiction
  lifecycle from `backend/dialogues/hybrid_epistemic.py`.
- `InquiryState` is a process recommendation and `AporiaRecord` is an open
  remainder, not an authoritative open/resolved question lifecycle.
- Search `ABSTAINED` is downstream vocabulary, not an upstream canonical
  epistemic record. Neither question resolution nor abstention may be invented.
- New semantic identity may contain only typed canonical values and stable IDs,
  never raw provider prose, scores, consensus, confidence, markers, benchmark
  labels, future outcomes, or reward.
- Projection must be current-snapshot-only, deterministic, side-effect free,
  provenance-linked, and fail closed on malformed or dangling records.
- The next step, only if Phase 6 succeeds, is a separate Value v1 Decision Gate.
  This branch must stop before Value v1.

## Protected local state

Do not touch `scripts/live_dialogue.py.bak` or the malformed untracked root
filename beginning `ocratic_followup_mandate`.

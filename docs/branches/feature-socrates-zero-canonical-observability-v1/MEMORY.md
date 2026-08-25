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
- The implemented semantic IDs are `socrates.zero.search-state/v1` and
  `ced-search-state-projection/v1`.
- The v1 contract and projector remain on the trusted CED side in
  `ced_search_observability_v1.py` and `ced_search_projection_v1.py`; the
  runtime-inert search package still imports no Hybrid authority.
- Included families are typed admissible evidence, verification,
  `ClaimAssessment`, objection lifecycle, and contradiction lifecycle.
- Two exact v0 aliases are proven: governing `SUPPORTED` versus `UNSUPPORTED`
  assessment under identical v0 semantic identity, and absent versus
  canonically `DISMISSED` contradiction under identical full v0 projection.
- No canonical question resolution or upstream epistemic abstention exists;
  neither appears in v1. Revision/commitment lifecycle and provider failure are
  intentionally outside the minimal epistemic schema.
- Phase 6 hypothesis status is `SUPPORTED`. No Value v1, Policy/search change,
  live call, production wiring, or new authority exists.
- Final full-suite counts are `2322 passed, 1 skipped` for `tests_dialogues` and
  `2629 passed, 1 skipped, 23 pre-existing warnings` repository-wide.

## Protected local state

Do not touch `scripts/live_dialogue.py.bak` or the malformed untracked root
filename beginning `ocratic_followup_mandate`.

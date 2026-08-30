# Present state

Branch: `feature/socrates-zero-openrouter-live-routing-repair-v1`
HEAD at last commit: `7bc589a` (working tree is ahead, uncommitted)
`backend/dialogues/ced.py` blob: `5413ec166591a38a88e548b378c3684c5ec4d5d5`
Core lock: `cedcorebloblockv2_401cd7ac5d7afa835142541ae122a0ef23bb74693a0e5999e70c232b5db8b3c2`

Live testing is **stopped** by operator instruction until the retry architecture
is settled. No live call has been made since the Q6 council was aborted.

## Tests

`4074 passed, 18 failed, 9 skipped` — the 18 are exactly the failures present at
`7bc589a` before any of this work. Zero new failures, zero regressions,
verified by diffing against a clean worktree at HEAD rather than by recollection.

## Completed

### 1. Q6 key independently confirmed

`scripts/q6_independent_verifier_v1.py` re-derives every Q6 figure sharing no
code with `scripts/q6_ethics_question_v1.py`: it imports nothing of ours
(enforced by an AST check on its imports), represents a rule as an
ordered-profile → winning-proposal map rather than an orientation of vector
pairs, and settles the small cases by brute force over every rule on the domain.

Calibration runs first and gates everything: `n=2` must return `2`, the figure
established independently in Q5 and the exact case the first verifier's first
version got wrong. Only then are the other widths reported.

| N | method | rules examined | result |
|---|---|---|---|
| 1 | exhaustive | 4 | no satisfying rule exists |
| 2 | exhaustive | 4096 | 48 satisfying, minimum **2** |
| 3 | exhaustive over the zero-departure family | 64 | **0** |
| 4 | one construction, checked over all 240 profiles | 1 | **0** |

`n=3` came back stronger than claimed: **all 64** zero-departure rules satisfy
the three conditions, so at three criteria the tie-break is entirely free.

Zero is minimal without enumerating `2**28` rules, because a departure count is
a number of profiles and is never negative.

`tests_dialogues/test_q6_independent_verifier_v1.py` (12 tests) checks that the
verifier can say **no**: a mutated claim must be contradicted, and a failed
calibration must suppress every reading.

### 2. Cross-seat reroute removed

An existing `task_id` can no longer reach a seat its logical agent is not bound
to. Two paths did this and both are gone:

- the phase rescue handed a twice-failed slot to another seat;
- `rule_on_round_objections_v1` sent **one** task to every peer under the
  *raiser's* agent id — found by the new binding test, not by review.

Policy now: `failure → same-seat re-ask → second failure → VOICE_LOST`. Quorum
decides only whether the phase proceeds. The phase record carries
`voice_lost_slots`; `reroute_permitted_v1` and the degraded-duplicate path are
deleted, not disabled.

### 3. Scope

The termination that follows a lost Socratic voice is **pre-existing generic CED
behaviour**, asserted at HEAD in
`test_without_rescue_one_silent_answer_ends_the_dialectic` and untouched here:
REFLECTION has never run without an accepted Socratic question. The handover was
the only thing that ever masked it.

Three tests were rescoped after an operator correction: they had stated
termination as a universal law. They now state the condition — a council with no
authorized replacement task — and say explicitly that a future protocol may
authorize a NEW Socratic task with its own id, owner and provenance.

### 4. Q6 evidence held

`runs/q6_aborted_evidence_v1.json` marks the 10-call aborted council as
`ABORTED_BY_OPERATOR`, not a benchmark. The nine Q6 baselines ($0.068) were
held unscored pending independent confirmation of the key, which
`runs/q6_independent_verification_v1.json` now supplies.

## Not done, deliberately

- **Replacement-task mechanism.** Deferred by operator instruction: it opens a
  new protocol surface and is not needed to proceed. The architecture records
  that coverage would require a new `task_id`, a new logical owner, explicit
  authorization and its own provenance. Disabled in every current protocol.
- **Output budgets** remain 4096/8192/16384 in `run_socrates_live_v1.py`.

## Known cost of the change

A council with one permanently dead seat can no longer finish if that seat holds
a Socratic chair in any cycle. Previously the handover covered it. This is the
capability a replacement task would restore, and it is the reason that item
exists rather than being dropped.

## Next safe step

Commit. Then either build the replacement-task mechanism, or reframe Q6 around
the question the confirmed key makes interesting: why the forced departure is 2
at two criteria and vanishes at three.

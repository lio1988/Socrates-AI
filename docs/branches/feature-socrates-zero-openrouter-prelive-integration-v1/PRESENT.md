# PRESENT — feature/socrates-zero-openrouter-prelive-integration-v1

## State

- Branch: `feature/socrates-zero-openrouter-prelive-integration-v1`
- Source HEAD: `1be95cfdecd9628cdf2d1ea6abdcf66ba1aa88a6`
- Phase: **semantic experiment frozen; the authoritative run has NOT been made.**

## A superseded earlier run

An authoritative aggregate was run before the rulings arrived, producing artifact
`szorpreliveartifactv1_6ff594b3…`. The rulings then required semantic changes, and
this phase's own rule is that a semantic change after an authoritative run
invalidates that run. It is therefore **superseded**, preserved in history at
`0ff79c9`, and removed from the working tree so nothing stale reads as current.

## Corrections that mattered

**P18 is not JIT-reachable.** I previously reported it as JIT-reachable and READY.
The mandated granularity audit shows that was **wrong at the required
granularity**: the retained endpoint record exposes only a broad display provider
name and an undocumented `tag`, so a price cannot be bound to the exact request
selector `azure/swedencentral`. Structural, not freshness.

**`max_price` was dismissed too early.** An earlier note said it "cannot
substitute" for P18. That reading was too narrow. It is a first-party
**server-enforced request-side ceiling**, enforced before route selection, and
bounding unit price is exactly what a worst-case cost needs. The pricing obstacle
to safe live cost bounding is closed.

**"19/19 frozen predecessor surfaces" was not reproducible.** The measured figure
is 34/34 files under `backend/dialogues/socrates_zero/` that S6 does not own,
byte-identical to `1be95cf`, including all 17 predecessor `openrouter_*` modules.

## Cost safety classification

| item | status |
| --- | --- |
| P18 actual endpoint pricing | NOT_ESTABLISHED |
| Pricing endpoint granularity | BROAD_PROVIDER_ONLY |
| Trusted unit-price ceiling | **ESTABLISHED** |
| Output token bound | ESTABLISHED (256) |
| P17 input token bound | NOT_ESTABLISHED |
| P19 formula | READY |
| P19 worst-case cost authority | NOT_ESTABLISHED |
| One live shadow call | **NOT_AUTHORIZED** — sole structural blocker: P17 |

## Completed

Integration contracts; safety and budget contracts with the rulings applied; the
additive live-request overlay and unit-price ceiling
(`openrouter_live_request_overlay_v1.py`); 71 frozen cases (30 integration, 25
preflight, 16 ceiling); the deterministic evaluator wired for all three families;
126 focused tests; canonical and branch documentation.

## Tests and exact results

- S6 focused suite: **126 passed**.
- Full `tests_dialogues`: **3514 passed, 10 skipped**.
- Evaluator dry-run: 30 / 25 / 16 cases, 0 unexpected, `all_thresholds_pass` True,
  live readiness `NOT_AUTHORIZED`.
- `git diff --check`: clean.
- Predecessor surfaces vs `1be95cf`: **34/34 byte-identical**.

## Frozen identities

| identity | value |
| --- | --- |
| integration case set | `szorintegrationcasesetv1_05922235…` |
| preflight case set | `szorpreflightcasesetv1_7eb946e3…` |
| ceiling case set | `szorceilingcasesetv1_77524c39…` |
| thresholds | `szorprelivethresholdsv1_ba6a47c7…` |
| safety contract | `szorprelivesafetyv1_bcddf7aa…` |

## Remaining

Exactly one authoritative offline evaluation, its replay, and the result
documentation. Awaiting authorization to run it.

## Blockers

None procedural. The scientific blocker for a live call is P17, and it is
structural.

## Next safe step

Nothing. **Stop.** The authoritative S6 aggregate must not be run without explicit
authorization, and the branch must not be pushed.

Not pushed.

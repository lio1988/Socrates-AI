# PRESENT — feature/socrates-zero-openrouter-live-routing-repair-v1

State as of 2026-08-29. Five live councils, 33 baselines, about $4.06 of spend.
Nothing pushed.

## Where the work stands

The protocol now runs any registered question without a code edit, three
observability defects that were silently corrupting results are fixed, and the
frozen canonical core has been deliberately unlocked once to let objection
rulings reach the dialogue while it is still running.

The research question — does a council beat one model — is **not** answered.
Three questions produced three ties. That branch is parked by decision, not by
failure to try.

## Completed

**Question parameterisation.** `scripts/question_bundles_v1.py` pins a
question's three digests in a write-once bundle and re-derives them on every
load, so adding a question adds a file. `q3` and `q4` are registered. The runner
takes `--question`, and five hard-coded `"q2"` sites that silently refused any
other question were bound to the authorized payload.

**Three observability repairs.** A prompt-size guard was refusing ratification
calls by a 2% margin, which read as model variance; the guard now compares
against the endpoint window and the cost reservation is computed from the
measured request. The semantic floor was rejecting formal derivations because it
counted only alphabetic words — in a logic benchmark it was discarding the
highest-value contributions. And scoring read two of six synthesis fields, which
understates CED by construction because the extra fields are what the contract
adds; `scripts/dump_scorable_answers_v1.py` prints every field and the field
count.

**Q4.** A true impossibility followed by an unjustified remedy, machine-checked
by enumerating all 65_536 rules. It is the first question in the series whose
error is refuted by computation: two GPT-4.1 Mini samples offered a rule that
does not exist, and running it over the 16 profiles shows it fails impartiality
on exactly the four symmetric profiles.

**Mid-round objection rulings.** `CEDOrchestrator.rule_on_round_objections_v1`
rules on a round's objections while the dialogue can still read them. It governs
nothing: no verdict, no claim movement, no release. The adapter records the
allowlisted fields and injects them into later deliberation contexts, and
`objection_rulings_in_context` on every turn record says how many each request
carried.

## Frozen core

`backend/dialogues/ced.py` was re-pinned **twice**, deliberately:

    9faaf048d3b3f6fb…  →  cf7ce4e5376c0be5…   added the ruling pass
    cf7ce4e5376c0be5…  →  a7cb71b095538f7c…   gated it for a control arm

Lock id is now `cedcorebloblockv2_abfbbabe644ecf5c…`. Every governing path is
untouched: `run_objection_verification`, claim state and the release seam are
unchanged. The reason is recorded in the lock and beside the test assertion, so
this line moving without that being the intended change is a defect.

## What the runs showed

| run | calls | result | cost |
|---|---|---|---|
| Q2 #1, #3 | 101 | ratified, 23/23 | $0.364, $0.368 |
| Q2 #2 | 90 | ratification refused by our own guard | $0.346 |
| Q3 | 93 | ratified, 30/32 | $0.302 |
| Q4 baseline | 101 | ratified, 46/46 | $0.368 |
| Q4 arms off / on | 101 / 103 | ratified, both 46/46 | $0.388 / $0.394 |
| Q4 on, instrumented | 93 | ratified | $0.354 |

Baselines: Q2d 15 samples (7–23), Q3 9 samples, Q4 9 samples. Q4 discriminates
between models — Gemini 46.0, GPT-5 Mini 45.7, GPT-4.1 Mini **7.7**.

## Two retracted claims

Both are recorded because the retraction is the result.

The council was first scored 30/32 on Q3 against a best baseline of 32/32,
supporting a conclusion that CED had lost a distinction one of its own seats
found unaided. That was an artifact of reading two synthesis fields. Corrected
to 46/46 on the same evidence.

Six content markers appeared to show the rulings' content entering the
synthesis and absent from the baseline. Under a controlled A/B on identical
code, five of six were absent from both arms and the sixth appeared in the
control. It was run-to-run variance. The first comparison was invalid as an
experiment: the control ran on an older build.

## Verified, and not

The delivery chain is proven end to end — rulings are produced mid-dialogue,
recorded, injected, and 13 of 20 seat moves carried at least one, written in the
turn records rather than inferred. Request sizes cannot show this: two runs of
one council diverge on their own, so a larger body is not evidence.

No measured benefit. Both arms scored 46/46. Position revisions fall
consistently with rulings on (10, 6 without; 4, 4 with) but with the score at
ceiling there is no way to tell whether that is questions closing early or seats
anchoring. Q4 cannot answer it — a question the council already aces has no
headroom.

## Tests

17 failures, all pre-existing from the reconciliation, in
`ced_canonical_successor_*` (7), `structured_socratic_experiment` (7),
`reduced_socrates_benchmark` (2) and `benchmark_safety` (1). 4024 pass. Run with
`-p no:randomly`: ordering is randomised by default and one one-shot acquisition
test fails or passes depending on it.

## Evidence and its limits

`turn_order_v1.json` in each run directory records chronological order. It is
derived from dispatch-evidence file mtimes, which **git does not preserve**, so
it is written down rather than recoverable from a clone. The `turns` array in a
council record is grouped by seat, not chronological; reading it as
chronological produces phase orders that cannot have happened.

`runs/` and `*.md` are gitignored, so evidence is force-added.

## Next safe step

Either park the mechanism as proven-but-unproven-useful, or test it where there
is headroom. The obvious probe is a council of three GPT-4.1 Mini seats on Q4,
where that model scores 7.7/46 alone: if three weak seats reach 30, the
dialectic demonstrably adds something. About $0.15.

Do not push.

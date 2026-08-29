"""Q3: a *valid* moral argument that is nonetheless unsound.

Design rationale, from what Q2 measured.

Q2 discriminated (scores 7-23 across fifteen samples) but its oracle union beat
the best single answer by only two points. Every sample got the verdict and the
failing step; the spread came almost entirely from one criterion. A question
that narrow cannot show what a council adds, because there is almost nothing
distributed to integrate.

Q3 is built to widen that gap deliberately. It carries **five independent
defects of different kinds**, so that catching one is little help in catching
another:

1. **The verdict trap.** Q2 primed "find the invalid step". This argument is
   *formally valid*: every inference is a correct modus tollens. The error is
   soundness, not validity. An answer that reflexively hunts for an invalid step
   will misdiagnose the whole thing.
2. **An equivocation in premise 2** on "contest a judgement": contesting its
   *content* needs no identity, contesting the *judge* does. The argument needs
   both readings at once.
3. **A suppressed normative premise.** Premise 6 does enormous work unremarked:
   it licenses abolition from any unfairness, however slight, with no comparison
   to alternatives.
4. **A necessary/sufficient slip waiting to be made.** Premise 1 gives fairness
   a necessary condition only. Concluding anything about what *is* fair from it
   is the error two models made unprompted in Q2.
5. **The fallacy fallacy.** Showing the argument unsound leaves the conclusion
   exactly where it was.

The conclusion is again deliberately attractive to a certain reader — abolishing
anonymous review sounds like transparency — which is the pressure that makes a
reader wave the premises through.

The formal core is machine-checked: the argument's validity is verified
exhaustively over all truth assignments, so "valid but unsound" is not a
judgement call.
"""

from __future__ import annotations

import hashlib
from itertools import product
from typing import Dict, Tuple

QUESTION_V1 = """A university ethics board argues that anonymous peer review must be abolished:

1. A practice is fair only if every participant can contest a judgement that affects them.
2. A participant can contest a judgement only if they know who made it.
3. Under anonymous review, authors do not know who judged them.
4. So under anonymous review, authors cannot contest the judgements that affect them.
5. So anonymous review is not fair.
6. Any practice that is not fair ought to be abolished.
7. So anonymous review ought to be abolished.

Assess this argument.

* Is it deductively valid? Answer yes or no, and justify your answer step by step.
* Whether or not it is valid, is it sound? Identify the weakest premise and say exactly what is wrong with it.
* One premise carries far more normative weight than its phrasing suggests. Identify it and explain what it silently assumes.
* State whether the failure you identify shows that the conclusion is false, and justify your answer.

Use ordinary standards of deductive logic. Judge the argument, not the appeal of its conclusion."""

QUESTION_SHA256_V1 = hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- key --------
# EVALUATOR-ONLY KEY. Never sent to any model.

VALID_V1 = True
SOUND_V1 = False

# Correct derivation:
VALIDITY_DERIVATION_V1 = (
    "2 and 3 give not-CanContest by modus tollens.",
    "That is exactly step 4.",
    "1 says Fair -> CanContest, so not-CanContest gives not-Fair by modus tollens.",
    "That is step 5.",
    "6 says not-Fair -> OughtAbolish; with 5, modus ponens gives step 7.",
    "Every inference is truth-preserving, so the argument is valid.",
)

WEAKEST_PREMISE_V1 = 2
EQUIVOCATION_V1 = (
    "Premise 2 equivocates on 'contest a judgement'. Contesting its *content* — "
    "rebutting the reasoning, appealing to an editor, demanding a second reader "
    "— requires no knowledge of who wrote it, and is exactly what appeal "
    "procedures provide. Contesting the *judge* — alleging bias, conflict of "
    "interest, incompetence — does require identity. The argument needs the "
    "weak reading to make premise 2 plausible and the strong reading to make "
    "step 4 follow, and it cannot have both at once."
)

SUPPRESSED_PREMISE_V1 = 6
SUPPRESSED_PREMISE_DEFECT_V1 = (
    "Premise 6 silently assumes that any unfairness, of any degree, in any "
    "respect, is sufficient for abolition — with no threshold, no weighing "
    "against what the practice achieves, and no comparison with the "
    "alternatives that would replace it. Stated openly it is close to absurd: "
    "every real institution is unfair in some respect, so premise 6 would "
    "abolish all of them."
)

FALLACY_FALLACY_V1 = (
    "No. An unsound argument for a conclusion leaves the conclusion unproven, "
    "not refuted. Whether anonymous review ought to be abolished has to be "
    "settled on other grounds — for instance by weighing the bias anonymity "
    "prevents against the accountability it removes."
)

#: The slip this question invites, recorded because Q2 showed two of four models
#: make it unprompted. Premise 1 states a necessary condition for fairness.
NECESSARY_NOT_SUFFICIENT_V1 = (
    "Premise 1 gives a necessary condition only. Nothing here licenses the "
    "conclusion that a practice permitting contestation *is* fair, and an "
    "answer that repairs the argument by treating premise 1 as a definition of "
    "fairness has changed the subject rather than fixed the reasoning."
)

CRITERIA_V1: Tuple[Tuple[str, str, int], ...] = (
    ("validity_verdict", "states the argument is deductively VALID", 4),
    ("validity_derivation", "shows each step is modus tollens or modus ponens", 3),
    ("soundness_verdict", "states it is nonetheless unsound", 2),
    ("locates_premise_2", "names premise 2 as the weakest", 3),
    ("names_the_equivocation",
     "distinguishes contesting the content from contesting the judge", 6),
    ("locates_premise_6", "identifies premise 6 as carrying hidden normative weight", 4),
    ("premise_6_defect", "explains it needs no threshold and no comparison", 4),
    ("fallacy_fallacy", "says unsoundness does not make the conclusion false", 4),
    ("resists_moral_pull", "judges the argument, not the appeal of its conclusion", 2),
)

MAXIMUM_SCORE_V1 = sum(points for _n, _d, points in CRITERIA_V1)

ERROR_FLAGS_V1 = (
    "CALLS_A_VALID_ARGUMENT_INVALID",
    "TREATS_UNSOUNDNESS_AS_REFUTATION",
    "NECESSARY_CONDITION_READ_AS_SUFFICIENT",
    "MISSES_THE_EQUIVOCATION",
    "MISSES_THE_SUPPRESSED_PREMISE",
    "ENDORSES_THE_CONCLUSION_ON_ITS_APPEAL",
    "INVENTS_A_PREMISE_NOT_STATED",
)


# --------------------------------------------------------- key self-check ----


def _semantics_v1(a: Dict[str, bool]) -> Tuple[bool, ...]:
    """Truth of each numbered line under one assignment.

    Fair, CanContest, KnowsJudge and OughtAbolish are taken of the practice
    under assessment. Lines 4, 5 and 7 are the argument's own conclusions, so
    they are not premises; only 1, 2, 3 and 6 are.
    """
    fair, contest, knows, abolish = a["F"], a["C"], a["K"], a["A"]
    return (
        (not fair) or contest,        # 1. Fair -> CanContest
        (not contest) or knows,       # 2. CanContest -> KnowsJudge
        not knows,                    # 3. not KnowsJudge
        (not fair) or abolish,        # 6. not Fair -> OughtAbolish  (see note)
    )


def verify_key_v1() -> Dict[str, object]:
    """Machine-check that the argument is valid: no countermodel exists.

    Validity means every assignment satisfying premises 1, 2, 3 and 6 also
    satisfies the conclusion (7). Premise 6 is encoded as ``not Fair ->
    OughtAbolish``, which under classical logic is ``Fair or OughtAbolish``.
    """
    names = ("F", "C", "K", "A")
    countermodels = []
    checked = 0
    for bits in product((False, True), repeat=4):
        a = dict(zip(names, bits))
        p1 = (not a["F"]) or a["C"]
        p2 = (not a["C"]) or a["K"]
        p3 = not a["K"]
        p6 = a["F"] or a["A"]
        if not (p1 and p2 and p3 and p6):
            continue
        checked += 1
        if not a["A"]:  # conclusion 7: OughtAbolish
            countermodels.append(dict(a))
    return {
        "assignments_satisfying_all_premises": checked,
        "countermodels_to_the_conclusion": countermodels,
        "argument_is_valid": not countermodels,
        "key_declares_valid": VALID_V1,
        "key_is_sound": (not countermodels) == VALID_V1 and checked > 0,
    }


if __name__ == "__main__":
    import json

    print(f"question sha256: {QUESTION_SHA256_V1}")
    print(f"maximum score  : {MAXIMUM_SCORE_V1}")
    print(json.dumps(verify_key_v1(), indent=2))


# ------------------------------------------------- key incompleteness -------
# Recorded after the live council run, NOT part of any digest.
#
# This constant is deliberately absent from question_bundles_v1._KEY_FIELDS_V1,
# so adding it leaves QUESTION_SHA256_V1, the rubric digest and the evaluator-key
# digest untouched and the pinned bundle still loads. The scored run stays
# comparable; what changes is that the defect is on the record.
#
# The council found a defect in this question that the author did not put there
# and no baseline reported. It is not scored, because scoring it retroactively
# would rewrite the rubric the run was measured against.

KEY_INCOMPLETENESS_FOUND_LIVE_V1 = (
    "The key assumes the 'judge' is the referee. The argument equivocates across "
    "premises 2, 3 and 4 over who that is. If the effective adjudicator is the "
    "handling editor, whose identity authors do know, then premise 3 is simply "
    "false and the argument fails one step earlier than at the equivocation in "
    "premise 2 that CRITERIA_V1 rewards. A complete key would treat 'the judge "
    "is the referee' as a suppressed premise in its own right. Found by the "
    "three-seat heterogeneous council (Gemini synthesis crucial_stress_test and "
    "GPT-5 Mini reconstruction, both accepted moves); absent from all nine "
    "baseline samples."
)

"""Q2: an ethical argument with a determinate structural error.

Why this shape. Q1 was saturated — all four families answered it correctly, so
it could not measure anything about a council. A moral question with a contested
answer would be worse: nothing to score against. What has both a determinate
answer and real difficulty is a *moral argument containing a definite logical
error*, where the conclusion is one a careful reader is inclined to accept.

Three traps are built in, each with a determinate right answer:

1. **A scope equivocation at step 4.** "Ignores no criterion" (every criterion
   affects the outcome) is silently strengthened into "every criterion decides
   the outcome". A rule can weigh a criterion without letting it settle first
   place.
2. **A morally attractive conclusion.** "No allocation rule is fair" reads as
   admirable humility about rationing, which is exactly the pressure that makes
   a reader wave the inference through.
3. **The fallacy fallacy.** Showing the argument invalid does not show its
   conclusion false. An answer that slides from "the argument fails" to "so
   some rule is fair" has made the mirror-image error.

The evaluator key is machine-checked: the countermodel is constructed and
verified to satisfy premises 1-3 while falsifying step 4.
"""

from __future__ import annotations

import hashlib
from itertools import permutations
from typing import Dict, List, Tuple

QUESTION_V1 = """A national transplant committee rejects every proposed rule for allocating a scarce organ, arguing as follows:

1. For each patient on the waiting list, there is at least one reasonable criterion of medical desert on which that patient ranks first.
2. A rule ignores a criterion exactly when the rule's outcome would be the same no matter how patients scored on that criterion.
3. A rule is fair only if it ignores no reasonable criterion of medical desert.
4. So a fair rule must place first every patient who ranks first on some reasonable criterion.
5. By (1), that is every patient on the list.
6. No rule can place every patient first.
7. So no allocation rule is fair.

Assess this argument.

* Is it valid? If not, identify the first step that does not follow.
* Explain precisely what goes wrong at that step.
* Give a concrete countermodel: a specific waiting list, a specific set of reasonable criteria, and a specific rule that satisfies premises (1), (2) and (3) while making step (4) false.
* State whether the failure of this argument shows that its conclusion is false, and justify your answer.

Use ordinary standards of deductive validity. Judge the reasoning, not the moral attractiveness of the conclusion."""

QUESTION_SHA256_V1 = hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- key --------
# EVALUATOR-ONLY KEY. Never sent to any model.

VALID_V1 = False
FIRST_INVALID_STEP_V1 = 4

# Correct derivation:
DIAGNOSIS_V1 = (
    "Step 4 equivocates on 'ignores'. Premise 2 defines ignoring a criterion as "
    "the outcome being insensitive to it, so premise 3 requires only that every "
    "reasonable criterion make some difference to the outcome. Step 4 needs the "
    "much stronger claim that every criterion is decisive — that whoever ranks "
    "first on a criterion is placed first overall. A rule can be sensitive to a "
    "criterion without being settled by it, so (1)-(3) do not entail (4)."
)

# Expected minimal countermodel:
COUNTERMODEL_V1 = {
    "patients": ("Ana", "Ben", "Cara"),
    "criteria": ("urgency", "expected_benefit", "waiting_time"),
    # Each patient ranks first on exactly one criterion, satisfying premise 1.
    # Deliberately not symmetric: a fully symmetric table ties the weighted sum
    # and the rule then has no single first place, which would break the
    # countermodel rather than illustrate it.
    "scores": {
        "Ana": {"urgency": 3.0, "expected_benefit": 1.0, "waiting_time": 1.0},
        "Ben": {"urgency": 1.0, "expected_benefit": 3.0, "waiting_time": 2.0},
        "Cara": {"urgency": 2.0, "expected_benefit": 2.0, "waiting_time": 3.0},
    },
    # Every weight is positive, so every criterion affects the outcome and the
    # rule ignores none of them: premise 3 is satisfied.
    "weights": {"urgency": 0.5, "expected_benefit": 0.3, "waiting_time": 0.2},
}

#: The point most likely to be missed, and the one worth the most credit.
FALLACY_FALLACY_V1 = (
    "No. An invalid argument for a conclusion leaves the conclusion exactly "
    "where it was: unproven, not refuted. Concluding 'therefore some allocation "
    "rule is fair' from the argument's failure would be the same mistake in "
    "mirror image. Whether any rule is fair has to be settled on other grounds."
)

CRITERIA_V1: Tuple[Tuple[str, str, int], ...] = (
    ("validity_verdict", "states the argument is invalid", 2),
    ("locates_step_4", "identifies step 4 as the first step that does not follow", 3),
    ("names_the_equivocation",
     "explains that 'affects the outcome' was strengthened to 'decides the outcome'", 5),
    ("countermodel", "gives a concrete list, criteria and rule satisfying 1-3 and falsifying 4", 5),
    ("countermodel_verified",
     "the countermodel actually works: every criterion matters, exactly one patient is first", 2),
    ("fallacy_fallacy", "says the invalidity does not make the conclusion false", 4),
    ("resists_moral_pull", "judges the inference rather than defending the conclusion", 2),
)

MAXIMUM_SCORE_V1 = sum(points for _n, _d, points in CRITERIA_V1)

ERROR_FLAGS_V1 = (
    "DEFENDS_CONCLUSION_INSTEAD_OF_ASSESSING_VALIDITY",
    "TREATS_INVALIDITY_AS_REFUTATION",
    "BLAMES_A_PREMISE_INSTEAD_OF_STEP_4",
    "COUNTERMODEL_MISSING",
    "COUNTERMODEL_DOES_NOT_SATISFY_PREMISES",
    "ACCEPTS_THE_ARGUMENT_AS_VALID",
    # Not designed in; found by the first live baselines and added afterwards,
    # which is why it is recorded here as discovered rather than intended.
    # Premise 3 states a *necessary* condition ("fair only if it ignores no
    # criterion").  Two of four models built a valid countermodel and then wrote
    # "so R is fair", which reads the necessary condition as sufficient.  The
    # countermodel shows step 4 fails; it cannot show any rule is fair.
    "NECESSARY_CONDITION_READ_AS_SUFFICIENT",
)


# --------------------------------------------------------- key self-check ----


def _rank(scores: Dict[str, Dict[str, float]], weights: Dict[str, float]) -> List[str]:
    """The rule: rank by weighted sum, highest first. Deterministic ties by name."""
    return sorted(scores, key=lambda p: (-sum(weights[c] * scores[p][c] for c in weights), p))


def verify_key_v1() -> Dict[str, object]:
    """Machine-check the countermodel before it is used to grade anything.

    Four things must hold, or the key is wrong and no score means anything:
      * premise 1 — every patient ranks first on some criterion;
      * premise 3 — the rule ignores no criterion, i.e. for each criterion there
        is some reassignment of scores on it that changes the outcome;
      * step 4 false — the rule does not place every patient first;
      * the rule is a genuine rule — it produces exactly one first place.
    """
    scores = COUNTERMODEL_V1["scores"]  # type: ignore[index]
    weights = COUNTERMODEL_V1["weights"]  # type: ignore[index]
    criteria = list(COUNTERMODEL_V1["criteria"])  # type: ignore[arg-type]
    patients = list(COUNTERMODEL_V1["patients"])  # type: ignore[arg-type]

    premise_1 = all(
        any(all(scores[p][c] >= scores[q][c] for q in patients) for c in criteria)
        and any(all(scores[p][c] > scores[q][c] for q in patients if q != p) for c in criteria)
        for p in patients
    )

    baseline = _rank(scores, weights)
    # A criterion is not ignored when *some* permutation of its column changes
    # the ranking. This is exactly premise 2's definition, tested exhaustively.
    sensitivity = {}
    for c in criteria:
        column = [scores[p][c] for p in patients]
        changed = False
        for perm in permutations(column):
            trial = {p: dict(scores[p]) for p in patients}
            for p, value in zip(patients, perm):
                trial[p][c] = value
            if _rank(trial, weights) != baseline:
                changed = True
                break
        sensitivity[c] = changed
    premise_3 = all(sensitivity.values())

    first_places = [baseline[0]]
    step_4_false = set(first_places) != set(patients)
    single_winner = (
        len(first_places) == 1
        and sum(weights[c] * scores[baseline[0]][c] for c in criteria)
        > sum(weights[c] * scores[baseline[1]][c] for c in criteria)
    )

    return {
        "premise_1_every_patient_leads_some_criterion": premise_1,
        "premise_3_no_criterion_is_ignored": premise_3,
        "criterion_sensitivity": sensitivity,
        "step_4_is_false_under_this_rule": step_4_false,
        "rule_yields_exactly_one_first_place": single_winner,
        "ranking": baseline,
        "key_is_sound": bool(
            premise_1 and premise_3 and step_4_false and single_winner
        ),
    }


if __name__ == "__main__":
    import json

    print(f"question sha256: {QUESTION_SHA256_V1}")
    print(json.dumps(verify_key_v1(), indent=2))

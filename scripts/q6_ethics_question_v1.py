"""Q6: the same panel at one, two, three and four criteria, and the answer moves.

Why this question exists.

Q5 asked for a number about one fixed domain and worked - two of nine
independent draws found it, where every earlier question had been answered
perfectly by every strong model. But its space is small enough to see whole: one
sample reasoned openly about "64 possibilities", because four score vectors make
six pairs and an impartial decisive rule is just an orientation of those six
edges. A structure that can be held in the head can be solved in the head.

Q6 asks the same question at four sizes at once. The answers do not follow a
pattern, and the smallest case inverts:

    criteria   vectors   admissible profiles   minimum departures
       1          2               2            no such rule exists at all
       2          4              12            exactly 2
       3          8              56            0
       4         16             240            0

Three regimes. The anomaly Q5 is built on exists at exactly one width. At one
criterion the impossibility returns, and for a different reason than anything in
Q4: with only two score vectors, changing a criterion always lands on the
inadmissible identical profile, so responsiveness has no witness available and
cannot be satisfied by any rule whatsoever.

That last case is the trap. Fewer criteria reads as easier, and a reader who has
just solved Q5 will generalise downward as readily as upward. Both directions are
wrong, and in opposite ways.

Nothing here can be recalled. The four answers require four separate analyses,
and no two of them share a method: n=1 is an emptiness argument about the domain,
n=2 is the mutually-exclusive tie-break argument, and n=3 and n=4 need only the
observation that extra equal-total pairs buy enough freedom to make every
criterion responsive without breaking monotonicity at all.

Every figure is computed here rather than asserted, and the search is validated
against the n=2 case whose answer is already established and machine-checked in
q5_ethics_question_v1.
"""

from __future__ import annotations

import hashlib
from itertools import combinations, product
from typing import Dict, List, Optional, Tuple

QUESTION_V1 = """A research funding panel scores two proposals, A and B, on N criteria. Each proposal receives a score of 0 or 1 on each criterion. The panel's charter guarantees that the two proposals never receive identical score vectors: a profile in which A and B score the same on every criterion cannot arise, and the rule is never applied to one. Every other profile can arise. The panel must publish a rule that reads any admissible profile and names a single winner.

Fix the three conditions:

1. DECISIVE: for every admissible profile the rule names exactly one winner, never a tie.
2. IMPARTIAL: if the two proposals exchange their entire score vectors, the winner exchanges too.
3. RESPONSIVE: for each criterion there is some admissible profile where altering only that criterion's score, to another admissible profile, changes the winner.

Call a rule MONOTONE if it always awards the win to the proposal with the higher total score, on every admissible profile where the totals differ.

Answer for each of N = 1, 2, 3 and 4 separately:

* Does a decisive, impartial and responsive rule exist? Answer yes or no for each N, and justify each answer on its own terms.
* Where such rules exist, what is the smallest number of admissible profiles on which one of them must depart from the monotone principle? Give the number for each N, and for the smallest non-zero case give a rule attaining it.
* If your answers differ across N, explain what changes as N grows, and separately what is different about the smallest case.

Do not assume the answer is the same for every N, and do not assume it varies in one direction. Check any rule you propose against every admissible profile before asserting it works."""

QUESTION_SHA256_V1 = hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- key --------
# EVALUATOR-ONLY KEY. Never sent to any model.

#: N -> (a satisfying rule exists, minimum departures from monotone)
ANSWER_BY_CRITERIA_V1: Dict[int, Tuple[bool, Optional[int]]] = {
    1: (False, None),
    2: (True, 2),
    3: (True, 0),
    4: (True, 0),
}

WHY_ONE_CRITERION_IS_IMPOSSIBLE_V1 = (
    "With one criterion there are two score vectors and two admissible profiles. "
    "Responsiveness asks for an admissible profile whose winner changes when one "
    "proposal's score on that criterion is altered, with the result still "
    "admissible. Altering the only criterion of either proposal makes the two "
    "vectors identical, which the charter excludes. So no witness exists for any "
    "rule, and responsiveness is unsatisfiable - not because the conditions "
    "conflict, as at two criteria, but because the domain is too small to "
    "contain the evidence responsiveness demands."
)

WHY_TWO_IS_THE_ONLY_COSTLY_WIDTH_V1 = (
    "At two criteria the monotone rule leaves exactly one free choice, the tie "
    "between (1,0) and (0,1), and the two criteria demand opposite resolutions "
    "of it, so monotonicity has to be broken; impartiality then forces the break "
    "to cover both orderings of a pair, giving two profiles. At three criteria "
    "and above there are several equal-total pairs, and their independent "
    "resolutions supply responsiveness witnesses for every criterion without "
    "touching any unequal-total pair. The cost is therefore not a trend in N. It "
    "appears at one width and vanishes on either side of it."
)

TRAP_V1 = (
    "Fewer criteria reads as easier, and a reader who has just worked through "
    "the two-criterion case will generalise downward as confidently as upward. "
    "Both are wrong, and in opposite directions: downward the problem becomes "
    "impossible, upward it becomes free."
)

CRITERIA_V1: Tuple[Tuple[str, str, int], ...] = (
    ("n1_impossible", "states that no such rule exists at one criterion", 9),
    ("n1_reason",
     "gives the reason: every single-criterion change lands on the inadmissible "
     "identical profile, so responsiveness has no witness", 9),
    ("n2_minimum_two", "gives 2 as the minimum at two criteria", 7),
    ("n2_rule_attains_it", "supplies a rule attaining 2, checkable over the domain", 6),
    ("n3_zero", "gives 0 at three criteria", 7),
    ("n4_zero", "gives 0 at four criteria", 5),
    ("not_monotone_in_n",
     "states that the cost is not a trend in N but appears at exactly one width", 8),
    ("explains_what_changes",
     "explains that extra equal-total pairs supply responsiveness witnesses "
     "without breaking monotonicity", 7),
    ("distinguishes_the_two_impossibilities",
     "separates the one-criterion emptiness from a conflict between conditions", 6),
    ("checks_before_asserting",
     "verifies a proposed rule rather than asserting it works", 4),
)

MAXIMUM_SCORE_V1 = sum(points for _n, _d, points in CRITERIA_V1)

ERROR_FLAGS_V1 = (
    "ASSUMES_THE_ANSWER_IS_THE_SAME_FOR_EVERY_N",
    "ASSUMES_THE_COST_GROWS_OR_SHRINKS_WITH_N",
    "CLAIMS_ONE_CRITERION_IS_THE_EASY_CASE",
    "TREATS_THE_ONE_CRITERION_IMPOSSIBILITY_AS_THE_SAME_AS_A_CONDITION_CONFLICT",
    "GIVES_A_MINIMUM_WITHOUT_A_RULE_ATTAINING_IT",
    "OFFERS_A_RULE_THAT_FAILS_RESPONSIVENESS",
    "REUSES_THE_SYMMETRIC_PROFILE_ARGUMENT_ON_A_DOMAIN_THAT_EXCLUDES_THEM",
)


# --------------------------------------------------------- key self-check ----


def _vectors(n: int) -> List[Tuple[int, ...]]:
    return [v for v in product((0, 1), repeat=n)]


def _admissible(n: int) -> List[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    vs = _vectors(n)
    return [(a, b) for a in vs for b in vs if a != b]


def _winner(orientation, a, b) -> str:
    """Which proposal wins, not which vector.

    Comparing vectors instead of proposals is the error that made a first
    version of this search report no cost at two criteria, where the answer is
    two. The n=2 case is kept in the self-check precisely to catch that again.
    """
    return "A" if orientation[frozenset([a, b])] == a else "B"


def _is_responsive(orientation, n: int) -> bool:
    for criterion in range(n):
        found = False
        for a, b in _admissible(n):
            for side in (0, 1):
                if side == 0:
                    a2 = tuple(1 - v if i == criterion else v for i, v in enumerate(a))
                    b2 = b
                else:
                    a2 = a
                    b2 = tuple(1 - v if i == criterion else v for i, v in enumerate(b))
                if a2 == b2:
                    continue
                if _winner(orientation, a, b) != _winner(orientation, a2, b2):
                    found = True
                    break
            if found:
                break
        if not found:
            return False
    return True


def minimum_departures_v1(n: int, search_depth: int = 3):
    """Smallest departure count, or None when no satisfying rule exists.

    An impartial decisive rule is an orientation of the pairs of distinct score
    vectors, so the search starts from the monotone orientation and flips the
    fewest unequal-total pairs that make every criterion responsive. Each flipped
    pair costs two admissible profiles, because impartiality carries it to both
    orderings.
    """

    pairs = [frozenset([x, y]) for x, y in combinations(_vectors(n), 2)]
    monotone = {p: sorted(p, key=lambda v: (-sum(v), v))[0] for p in pairs}
    unequal = [p for p in pairs if len({sum(v) for v in p}) == 2]
    for flips in range(0, search_depth + 1):
        for chosen in combinations(unequal, flips):
            orientation = dict(monotone)
            for p in chosen:
                orientation[p] = [v for v in p if v != orientation[p]][0]
            if _is_responsive(orientation, n):
                return 2 * flips, [tuple(sorted(p)) for p in chosen]
    return None, None


def verify_key_v1() -> Dict[str, object]:
    """Recompute every figure, and check the search against the known n=2 answer."""

    computed = {}
    for n in sorted(ANSWER_BY_CRITERIA_V1):
        departures, witness = minimum_departures_v1(n)
        computed[n] = {
            "vectors": len(_vectors(n)),
            "admissible_profiles": len(_admissible(n)),
            "rule_exists": departures is not None,
            "minimum_departures": departures,
            "flipped_pairs": witness,
        }
    agrees = all(
        (computed[n]["rule_exists"], computed[n]["minimum_departures"])
        == ANSWER_BY_CRITERIA_V1[n]
        for n in ANSWER_BY_CRITERIA_V1
    )
    # The one figure that is independently established elsewhere.
    n2_matches_q5 = computed[2]["minimum_departures"] == 2
    non_monotone_in_n = (
        computed[1]["minimum_departures"] is None
        and computed[2]["minimum_departures"] == 2
        and computed[3]["minimum_departures"] == 0
        and computed[4]["minimum_departures"] == 0
    )
    return {
        "computed": computed,
        "key_agrees_with_computation": agrees,
        "n2_matches_the_independently_verified_q5_answer": n2_matches_q5,
        "cost_is_not_monotone_in_n": non_monotone_in_n,
        "key_is_sound": agrees and n2_matches_q5 and non_monotone_in_n,
    }


if __name__ == "__main__":
    import json

    print(f"question sha256: {QUESTION_SHA256_V1}")
    print(f"maximum score  : {MAXIMUM_SCORE_V1}")
    print(json.dumps(verify_key_v1(), indent=2, default=str))

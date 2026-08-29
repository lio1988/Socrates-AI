"""Q5: the same panel, one profile family removed, and the answer inverts.

Why this question exists.

Q2, Q3 and Q4 were all recognition tasks: spot a quantifier shift, an
equivocation, an impossibility from symmetry. Frontier models have seen those
patterns many times, and it showed - three questions, three ties, every council
and its best single seat at the ceiling.

Q5 asks for construction instead, and it is built so that recognition actively
misleads. It is Q4 with the symmetric profiles removed from the domain, and the
suggestion came from the council itself: in the Q4 opener run Gemini wrote, under
blind spots, that "if the domain of allowable inputs were restricted a priori to
strictly asymmetric score profiles, the immediate contradiction between
decisiveness and impartiality would vanish, and responsiveness would then
re-emerge as an active mathematical constraint." That is exactly right, and it is
the question.

Three layers, each one trapping the answer above it:

1. **The verdict inverts.** On the full domain no rule is decisive, impartial and
   responsive; on this one, 48 are. A reader who reuses the symmetric-profile
   argument it has just been rewarded for gives the wrong verdict.
2. **The obvious constructions fail.** Highest total with a tie-break on either
   criterion, and pure lexicographic order, are all decisive and impartial and
   all fail responsiveness. A rule offered without being checked will be one of
   these.
3. **Every solution is non-monotone.** Not one of the 48 always awards the win to
   the higher total. So the impossibility does not disappear when the symmetric
   profiles go - it moves: the three conditions become satisfiable exactly when
   the panel accepts a rule that sometimes prefers the lower-scoring proposal.

All three are machine-checked by enumerating every rule over the twelve profiles,
so none of it is a judgement call, and any rule an answer proposes can be run
against the same enumeration.
"""

from __future__ import annotations

import hashlib
from itertools import product
from typing import Dict, List, Tuple

QUESTION_V1 = """A research funding panel scores two proposals, A and B, on two criteria. Each proposal receives a score of 0 or 1 on each criterion. The panel's charter guarantees that the two proposals never receive identical score vectors: a profile in which A and B score the same on both criteria cannot arise, and the rule is never applied to one. Every other profile can arise. The panel must publish a rule that reads any admissible profile and names a single winner.

The panel's methodologist argues:

1. Call a rule DECISIVE if for every admissible profile it names exactly one winner, never a tie.
2. Call a rule IMPARTIAL if the proposals' names carry no weight: if the two proposals exchange their entire score vectors, the winner exchanges too.
3. Call a rule RESPONSIVE if for each criterion there is some admissible profile where altering only that criterion's score, to another admissible profile, changes the winner.
4. No rule is decisive, impartial and responsive at once.
5. Therefore the panel must abandon impartiality.

Assess this argument.

* Is claim 4 true? Answer yes or no. If no, give a rule and verify it against all three conditions on every admissible profile.
* If you use an impossibility argument, state exactly which profiles it relies on and whether they are admissible here.
* Does any rule satisfying all three conditions always award the win to the proposal with the higher total score? Justify your answer.
* If no such rule always awards the win to the higher total, what is the smallest number of admissible profiles on which a rule satisfying all three conditions must depart from that principle? Give the number and a rule achieving it.
* Say what, if anything, the panel must give up, and what it costs.

Use ordinary standards of deductive logic. Check any rule you propose against every admissible profile before asserting it works."""

QUESTION_SHA256_V1 = hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- key --------
# EVALUATOR-ONLY KEY. Never sent to any model.

CLAIM_4_IS_TRUE_V1 = False

WHY_THE_Q4_ARGUMENT_FAILS_V1 = (
    "The contradiction between decisiveness and impartiality is derived from "
    "profiles where the two proposals hold identical score vectors: swapping "
    "leaves the profile unchanged, so impartiality demands the winner change "
    "while the input did not. The charter removes exactly those four profiles "
    "from the domain. On every admissible profile the swap produces a "
    "different profile, so impartiality relates two distinct inputs and no "
    "contradiction arises. The argument is not weakened here; it has no "
    "premises to stand on."
)

#: Higher total wins, with two exceptions that are each other's swap, and equal
#: totals resolved by criterion 1. Machine-checked below.
WITNESS_RULE_V1 = (
    "Award the win to the proposal with the higher total score, except that a "
    "proposal scoring (0,0) defeats one scoring (1,0); when the totals are "
    "equal, award it to the proposal scoring 1 on criterion 1."
)

NO_SOLUTION_IS_MONOTONE_V1 = (
    "No. Not one of the 48 rules satisfying all three conditions always awards "
    "the win to the higher total: every one of them prefers the lower-scoring "
    "proposal on at least two profiles, and the witness above is one of the "
    "rules that does so least often. The impossibility does not vanish when the "
    "symmetric profiles are removed - it changes shape. What was 'no such rule "
    "exists' becomes 'such rules exist, and none of them is monotone in the "
    "scores'."
)

OBVIOUS_CONSTRUCTIONS_FAIL_V1 = (
    "Highest total with a tie-break on criterion 1, highest total with a "
    "tie-break on criterion 2, and pure lexicographic order are all decisive "
    "and all impartial, and all three fail responsiveness. A rule proposed "
    "without being checked against the twelve profiles will almost certainly be "
    "one of them."
)

WHAT_THE_PANEL_GIVES_UP_V1 = (
    "Nothing among the three conditions: all of them are jointly satisfiable "
    "here. What the panel gives up is monotonicity, which the argument never "
    "names and which most people would assume without stating - that a proposal "
    "scoring higher on both criteria wins. Keeping decisiveness, impartiality "
    "and responsiveness together on this domain requires accepting a rule that "
    "sometimes rewards the lower total."
)

#: Two. Verified by enumeration: across the 48 satisfying rules the number of
#: profiles on which the lower total wins ranges from 2 to 8, and the witness
#: above attains the minimum.
#:
#: This is the question the earlier ones lacked. A verdict is guessable at even
#: odds and a proof is recognisable - quantifier shift, equivocation,
#: impossibility from symmetry are patterns a strong model has seen many times,
#: which is why Q2, Q3 and Q4 all ended in ties at the ceiling. A number
#: describing the whole solution space is neither. It cannot be recalled and it
#: cannot be guessed; it has to be derived or counted, and either way it is
#: checkable both directions: a wrong number is refuted by the enumeration, and
#: the right number still has to come with a rule that attains it.
MINIMUM_DEPARTURES_FROM_HIGHER_TOTAL_V1 = 2


CRITERIA_V1: Tuple[Tuple[str, str, int], ...] = (
    # The first four are deliberately cheap. A verdict is a coin flip and the
    # symmetry argument is a pattern these models have already been rewarded for
    # twice; scoring them heavily measures recall. The weight sits on the two
    # facts about the solution space, which cannot be recalled or guessed.
    ("claim_4_is_false", "states claim 4 is FALSE on this domain", 4),
    ("exhibits_a_rule", "gives a concrete rule rather than asserting one exists", 5),
    ("rule_actually_works",
     "the rule offered is decisive, impartial and responsive on all twelve "
     "admissible profiles", 5),
    ("locates_the_removed_profiles",
     "identifies that the symmetry argument needs identical-vector profiles and "
     "that the charter excludes them", 5),
    ("obvious_constructions_fail",
     "notes that highest-total or lexicographic rules fail responsiveness", 6),
    ("no_solution_is_monotone",
     "answers that no satisfying rule always awards the higher total", 10),
    ("minimum_departures_is_two",
     "gives 2 as the smallest number of profiles on which a satisfying rule must "
     "prefer the lower total, with a rule attaining it", 10),
    ("does_not_reuse_the_q4_verdict",
     "does not carry the impossibility over from the unrestricted domain", 3),
    ("checks_the_right_domain",
     "reasons over the twelve admissible profiles, not all sixteen", 3),
    ("states_the_cost",
     "identifies monotonicity as the unstated condition actually given up", 3),
)

MAXIMUM_SCORE_V1 = sum(points for _n, _d, points in CRITERIA_V1)

ERROR_FLAGS_V1 = (
    "REUSES_THE_SYMMETRIC_PROFILE_ARGUMENT",
    "DECLARES_THE_IMPOSSIBILITY_WITHOUT_CHECKING_THE_DOMAIN",
    "OFFERS_A_RULE_THAT_FAILS_RESPONSIVENESS",
    "ASSERTS_A_RULE_EXISTS_WITHOUT_EXHIBITING_ONE",
    "CLAIMS_A_MONOTONE_SOLUTION_EXISTS",
    "COUNTS_ALL_SIXTEEN_PROFILES",
    "TREATS_MONOTONICITY_AS_ONE_OF_THE_THREE_CONDITIONS",
    "GIVES_A_DEPARTURE_COUNT_WITHOUT_A_RULE_ATTAINING_IT",
)


# --------------------------------------------------------- key self-check ----

_ALL_PROFILES = tuple(product((0, 1), repeat=4))


def _exchanged(profile):
    a1, a2, b1, b2 = profile
    return (b1, b2, a1, a2)


ADMISSIBLE_PROFILES_V1 = tuple(p for p in _ALL_PROFILES if p != _exchanged(p))
_INDEX = {profile: i for i, profile in enumerate(ADMISSIBLE_PROFILES_V1)}


def _perturb(profile, who: int, criterion: int):
    position = who * 2 + criterion
    return tuple(
        1 - value if index == position else value
        for index, value in enumerate(profile)
    )


def _is_impartial(rule: List[int]) -> bool:
    return all(
        rule[_INDEX[p]] != rule[_INDEX[_exchanged(p)]]
        for p in ADMISSIBLE_PROFILES_V1
    )


def _is_responsive(rule: List[int]) -> bool:
    """Responsiveness must stay inside the domain: a perturbation that lands on
    an inadmissible profile is not a witness, because the rule is never applied
    there. Ignoring that is one way to conclude wrongly that the obvious rules
    are responsive."""
    for criterion in (0, 1):
        flips = False
        for p in ADMISSIBLE_PROFILES_V1:
            for who in (0, 1):
                q = _perturb(p, who, criterion)
                if q in _INDEX and rule[_INDEX[p]] != rule[_INDEX[q]]:
                    flips = True
                    break
            if flips:
                break
        if not flips:
            return False
    return True


def _higher_total_winner(profile):
    a1, a2, b1, b2 = profile
    total_a, total_b = a1 + a2, b1 + b2
    if total_a == total_b:
        return None
    return 0 if total_a > total_b else 1


def witness_rule_v1() -> List[int]:
    """The rule named in WITNESS_RULE_V1, as an assignment over the domain."""
    assignment = []
    for profile in ADMISSIBLE_PROFILES_V1:
        a1, a2, b1, b2 = profile
        if (a1, a2) == (0, 0) and (b1, b2) == (1, 0):
            assignment.append(0)
        elif (a1, a2) == (1, 0) and (b1, b2) == (0, 0):
            assignment.append(1)
        else:
            preferred = _higher_total_winner(profile)
            if preferred is None:
                preferred = 0 if a1 > b1 else 1
            assignment.append(preferred)
    return assignment


def verify_key_v1() -> Dict[str, object]:
    """Enumerate every rule over the admissible domain and check all three facts."""

    satisfying = []
    for bits in range(1 << len(ADMISSIBLE_PROFILES_V1)):
        rule = [(bits >> i) & 1 for i in range(len(ADMISSIBLE_PROFILES_V1))]
        if _is_impartial(rule) and _is_responsive(rule):
            satisfying.append(rule)

    def _monotone(rule) -> bool:
        return all(
            _higher_total_winner(p) is None or rule[_INDEX[p]] == _higher_total_winner(p)
            for p in ADMISSIBLE_PROFILES_V1
        )

    def _departures(rule) -> int:
        return sum(
            1 for p in ADMISSIBLE_PROFILES_V1
            if _higher_total_winner(p) is not None
            and rule[_INDEX[p]] != _higher_total_winner(p)
        )

    departures = [_departures(rule) for rule in satisfying]
    witness = witness_rule_v1()
    obvious = {
        "highest_total_then_criterion_1": [
            (_higher_total_winner(p) if _higher_total_winner(p) is not None
             else (0 if p[0] > p[2] else 1))
            for p in ADMISSIBLE_PROFILES_V1
        ],
        "lexicographic_criterion_1_then_2": [
            (0 if p[0] > p[2] else 1) if p[0] != p[2]
            else (0 if p[1] > p[3] else 1)
            for p in ADMISSIBLE_PROFILES_V1
        ],
    }
    return {
        "admissible_profiles": len(ADMISSIBLE_PROFILES_V1),
        "rules_enumerated": 1 << len(ADMISSIBLE_PROFILES_V1),
        "satisfying_all_three": len(satisfying),
        "claim_4_is_true": len(satisfying) == 0,
        "key_declares_claim_4_true": CLAIM_4_IS_TRUE_V1,
        "monotone_solutions": sum(1 for rule in satisfying if _monotone(rule)),
        "witness_is_impartial": _is_impartial(witness),
        "witness_is_responsive": _is_responsive(witness),
        "witness_monotone_violations": sum(
            1 for p in ADMISSIBLE_PROFILES_V1
            if _higher_total_winner(p) is not None
            and witness[_INDEX[p]] != _higher_total_winner(p)
        ),
        "obvious_constructions_responsive": {
            name: _is_responsive(rule) for name, rule in obvious.items()
        },
        "minimum_departures": min(departures) if departures else None,
        "maximum_departures": max(departures) if departures else None,
        "key_declares_minimum_departures": MINIMUM_DEPARTURES_FROM_HIGHER_TOTAL_V1,
        "key_is_sound": (
            len(satisfying) == 48
            and CLAIM_4_IS_TRUE_V1 is False
            and sum(1 for rule in satisfying if _monotone(rule)) == 0
            and _is_impartial(witness)
            and _is_responsive(witness)
            and not any(_is_responsive(rule) for rule in obvious.values())
            and min(departures) == MINIMUM_DEPARTURES_FROM_HIGHER_TOTAL_V1
            and _departures(witness) == MINIMUM_DEPARTURES_FROM_HIGHER_TOTAL_V1
        ),
    }


if __name__ == "__main__":
    import json

    print(f"question sha256: {QUESTION_SHA256_V1}")
    print(f"maximum score  : {MAXIMUM_SCORE_V1}")
    print(json.dumps(verify_key_v1(), indent=2))

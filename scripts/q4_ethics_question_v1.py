"""Q4: a genuine impossibility followed by an unjustified remedy.

Why this question exists.

Q2 and Q3 both discriminated poorly because both are solvable in one pass. Every
Q3 baseline scored 20-32 out of 32 and seven of nine cleared 30, so the council
had almost nothing left to add; measuring CED against a ceiling everyone reaches
measures the ceiling.

Q4 is built so that a single confident pass is *actively penalised*. It has two
dependent steps, and the natural first move fails the first one:

1. **The impossibility is real.** Q2 and Q3 both rewarded finding a flaw, so a
   reader arriving here is primed to refute. There is nothing to refute: no rule
   over this domain is both impartial and decisive, and the proof is four
   symmetric profiles where impartiality demands a proposal beat itself. An
   answer that produces a counterexample rule has produced something that does
   not exist, and it will believe otherwise unless it checks the rule.

2. **The remedy does not follow.** Having conceded the impossibility, the
   argument concludes that impartiality must go. That is a false trilemma. The
   conflict is entirely between impartiality and decisiveness; responsiveness is
   a passenger, holding for 65_506 of the 65_536 rules over this domain.
   Abandoning decisiveness - permitting a tie at exactly the four profiles that
   force it - keeps both other conditions. Nothing in the premises prefers
   dropping impartiality over dropping decisiveness.

The second step is unreachable without the first: you cannot see that the
conflict is binary until you have located *where* the impossibility comes from,
and you cannot locate that while you are still trying to refute it.

Both facts are machine-checked by exhaustive enumeration over all 65_536 rules,
so "the impossibility is genuine" and "responsiveness is nearly free" are
computed here, not asserted.
"""

from __future__ import annotations

import hashlib
from itertools import product
from typing import Dict, List, Tuple

QUESTION_V1 = """A research funding panel scores two proposals, A and B, on two criteria. Each proposal receives a score of 0 or 1 on each criterion, so a full scoring profile is four numbers. The panel must publish a rule that reads any profile and names a single winner.

The panel's methodologist argues:

1. Call a rule DECISIVE if for every profile it names exactly one winner, never a tie.
2. Call a rule IMPARTIAL if the proposals' names carry no weight: if the two proposals exchange their entire score vectors, the winner exchanges too.
3. Call a rule RESPONSIVE if for each criterion there is some profile where altering only that criterion's score changes the winner.
4. No rule is decisive, impartial and responsive at once.
5. Therefore the panel must abandon impartiality.

Assess this argument.

* Is claim 4 true? Answer yes or no. If yes, prove it. If no, give a rule and verify it against all three conditions.
* Does 5 follow from 4? Justify your answer.
* If the panel must give something up, say exactly what, and what it costs.
* Identify any condition that plays a smaller role in the impossibility than the argument implies, and justify your identification.

Use ordinary standards of deductive logic. Check any rule you propose against every profile before asserting it works."""

QUESTION_SHA256_V1 = hashlib.sha256(QUESTION_V1.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- key --------
# EVALUATOR-ONLY KEY. Never sent to any model.

#: Claim 4 is TRUE. This is the trap: the question invites refutation and there
#: is nothing to refute.
IMPOSSIBILITY_IS_GENUINE_V1 = True

#: The argument's inference, not its impossibility claim, is where it fails.
FIRST_INVALID_STEP_V1 = 5

PROOF_OF_IMPOSSIBILITY_V1 = (
    "Take any profile where A and B hold identical score vectors - (0,0|0,0), "
    "(0,1|0,1), (1,0|1,0), (1,1|1,1). Exchanging the two score vectors leaves "
    "the profile unchanged. Impartiality then requires the winner to change "
    "while the input did not, so the rule must name a different winner on the "
    "same profile. Decisiveness forbids that, since exactly one winner is "
    "named. Hence no rule is both decisive and impartial, and claim 4 follows "
    "a fortiori. Responsiveness is not used anywhere in this proof."
)

DIAGNOSIS_V1 = (
    "Step 5 is a false trilemma. Claim 4 shows the three conditions are jointly "
    "unsatisfiable; it does not say which to drop. The premises give no reason "
    "to prefer sacrificing impartiality, and the proof shows the conflict never "
    "involved responsiveness at all: it is a two-way conflict between "
    "impartiality and decisiveness. Dropping decisiveness is strictly less "
    "costly, because it can be dropped at exactly the four profiles that force "
    "the contradiction and nowhere else."
)

MINIMAL_REPAIR_V1 = (
    "Permit a tie only when the two proposals have identical score vectors. On "
    "every other profile the rule stays decisive, and impartiality and "
    "responsiveness both survive intact. The cost is that four of the sixteen "
    "profiles need a tie-break outside the criteria - a lottery, a further "
    "criterion, or a deliberative judgement - which is exactly the situation in "
    "which the criteria genuinely fail to distinguish the proposals."
)

RESPONSIVENESS_IS_A_PASSENGER_V1 = (
    "Responsiveness carries almost none of the impossibility: 65_506 of the "
    "65_536 decisive rules over this domain satisfy it. Naming it alongside the "
    "other two suggests a three-way tension where there is a two-way one, which "
    "is what makes the leap to 'abandon impartiality' look forced rather than "
    "chosen."
)

CRITERIA_V1: Tuple[Tuple[str, str, int], ...] = (
    ("claim_4_is_true", "states claim 4 is TRUE rather than refuting it", 6),
    ("symmetric_profile_proof",
     "proves it via profiles where the two score vectors are identical", 7),
    ("no_bogus_countermodel",
     "proposes no rule claimed to satisfy all three conditions", 4),
    ("five_does_not_follow", "states that 5 does not follow from 4", 5),
    ("names_false_trilemma",
     "explains that an impossibility does not select which condition to drop", 5),
    ("identifies_two_way_conflict",
     "identifies the conflict as impartiality versus decisiveness only", 6),
    ("responsiveness_is_a_passenger",
     "identifies responsiveness as carrying little or none of the impossibility", 5),
    ("minimal_repair",
     "proposes dropping decisiveness at exactly the forcing profiles", 5),
    ("states_the_cost",
     "says what a tie at those profiles costs and who must resolve it", 3),
)

MAXIMUM_SCORE_V1 = sum(points for _n, _d, points in CRITERIA_V1)

ERROR_FLAGS_V1 = (
    "CLAIMS_TO_REFUTE_A_TRUE_IMPOSSIBILITY",
    "OFFERS_A_RULE_THAT_DOES_NOT_EXIST",
    "ACCEPTS_ABANDON_IMPARTIALITY_AS_ENTAILED",
    "TREATS_ALL_THREE_CONDITIONS_AS_EQUALLY_IMPLICATED",
    "PROVES_IMPOSSIBILITY_BY_ASSERTION_WITHOUT_A_WITNESS",
    "DROPS_RESPONSIVENESS_AS_THE_REMEDY",
    "MISTAKES_THE_IMPOSSIBILITY_FOR_AN_INVALID_INFERENCE",
)


# --------------------------------------------------------- key self-check ----

_PROFILES: Tuple[Tuple[int, int, int, int], ...] = tuple(product((0, 1), repeat=4))
_INDEX = {profile: i for i, profile in enumerate(_PROFILES)}


def _exchanged(profile):
    a1, a2, b1, b2 = profile
    return (b1, b2, a1, a2)


def _perturb(profile, who: int, criterion: int):
    position = who * 2 + criterion
    return tuple(
        1 - value if index == position else value
        for index, value in enumerate(profile)
    )


def _is_impartial(rule: List[int]) -> bool:
    return all(rule[_INDEX[p]] != rule[_INDEX[_exchanged(p)]] for p in _PROFILES)


def _is_responsive(rule: List[int]) -> bool:
    for criterion in (0, 1):
        flips = any(
            rule[_INDEX[p]] != rule[_INDEX[_perturb(p, who, criterion)]]
            for p in _PROFILES
            for who in (0, 1)
        )
        if not flips:
            return False
    return True


def verify_key_v1() -> Dict[str, object]:
    """Enumerate every decisive rule and confirm both load-bearing facts.

    A rule maps each of the 16 profiles to a single winner, so decisiveness
    holds by construction and there are exactly 2**16 such rules.
    """

    impartial = responsive = all_three = 0
    for bits in range(1 << len(_PROFILES)):
        rule = [(bits >> i) & 1 for i in range(len(_PROFILES))]
        is_impartial = _is_impartial(rule)
        is_responsive = _is_responsive(rule)
        impartial += is_impartial
        responsive += is_responsive
        all_three += is_impartial and is_responsive

    symmetric = [p for p in _PROFILES if p == _exchanged(p)]
    return {
        "rules_enumerated": 1 << len(_PROFILES),
        "decisive_and_impartial": impartial,
        "decisive_and_responsive": responsive,
        "satisfying_all_three": all_three,
        "symmetric_profiles": symmetric,
        "impossibility_is_genuine": all_three == 0,
        "responsiveness_is_nearly_free": responsive >= 65_000,
        "key_declares_genuine": IMPOSSIBILITY_IS_GENUINE_V1,
        "key_is_sound": (
            all_three == 0
            and impartial == 0
            and responsive >= 65_000
            and len(symmetric) == 4
            and IMPOSSIBILITY_IS_GENUINE_V1
        ),
    }


if __name__ == "__main__":
    import json

    print(f"question sha256: {QUESTION_SHA256_V1}")
    print(f"maximum score  : {MAXIMUM_SCORE_V1}")
    print(json.dumps(verify_key_v1(), indent=2))

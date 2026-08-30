"""An independent check of the Q6 key, sharing no code with the first verifier.

Why this file exists.

The Q6 key was computed by one program that I wrote, whose first version was
wrong: it compared which score *vector* won instead of which *proposal* won, and
reported no cost at two criteria where the answer is two. That version was
caught only because the two-criterion answer was already established elsewhere.
The three- and four-criterion figures have no such anchor, and baselines have
already been drawn against them.

So this file re-derives the answers from the definitions, deliberately not the
way the first one did:

  * A rule here is an explicit map from an *ordered* admissible profile to the
    winning *proposal*, "A" or "B". The first verifier represents a rule as an
    orientation of unordered vector pairs. That representation is in fact forced
    by decisiveness and impartiality together, but it is forced as a
    *conclusion*, and a verifier that assumes it cannot notice if the conclusion
    is wrong. Nothing here assumes it; impartiality is checked profile by
    profile against its statement in the question.
  * The small cases are settled by brute force over every rule on the domain,
    with no search order, no starting point and no depth limit.
  * Nothing is imported from scripts.q6_ethics_question_v1, and no helper here
    is a copy of one there. The key it claims is transcribed by hand below, as
    data to be tested, not read from that module.

Method, and why it is enough.

  n=1: two ordered admissible profiles, so 2**2 = 4 rules. Exhaustive.
  n=2: twelve ordered admissible profiles, so 2**12 = 4096 rules. Exhaustive.
       This case is the gate. Its answer is independently established and
       machine-checked in Q5, and it is the exact case the first verifier got
       wrong. If the brute force does not return 2 here, nothing else in this
       file is reported: an instrument that fails its calibration does not get
       to give readings.
  n>=3: 2**28 impartial rules at three criteria is not a brute force anyone
       should trust to a coffee break, and it is not needed. Departures from the
       monotone principle are a count of profiles, so they are never negative,
       and zero is therefore a floor that holds without any enumeration. It is
       enough to exhibit ONE rule with zero departures and verify it exhaustively
       over the whole domain. At three criteria the exhibit is not hand-picked:
       every rule that departs nowhere is enumerated (there are 2**6 of them,
       one per assignment of the equal-total ties) and all of them are checked,
       which also reports how rare the property is. At four criteria the family
       is 2**27 and one construction is checked instead, exhaustively, over all
       240 profiles.

Run it: python scripts/q6_independent_verifier_v1.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

Vector = Tuple[int, ...]
Profile = Tuple[Vector, Vector]
Rule = Dict[Profile, str]

#: Transcribed by hand from q6_ethics_question_v1.ANSWER_BY_CRITERIA_V1.
#: Deliberately not imported: this is the claim under test, not a dependency.
CLAIM_UNDER_TEST_V1: Dict[int, Tuple[bool, Optional[int]]] = {
    1: (False, None),
    2: (True, 2),
    3: (True, 0),
    4: (True, 0),
}

#: The gate. Established independently of both verifiers, in Q5.
CALIBRATION_V1 = (2, 2)  # (criteria, minimum departures)


# ------------------------------------------------------------- the domain ----


def score_vectors_v1(n: int) -> List[Vector]:
    return list(itertools.product((0, 1), repeat=n))


def admissible_profiles_v1(n: int) -> List[Profile]:
    """Ordered pairs (A's vector, B's vector). The charter excludes a == b."""
    vectors = score_vectors_v1(n)
    return [(a, b) for a in vectors for b in vectors if a != b]


def _altered(v: Vector, criterion: int) -> Vector:
    return tuple(1 - x if i == criterion else x for i, x in enumerate(v))


# ------------------------------------------- the three conditions, verbatim ---


def is_decisive_v1(rule: Rule, n: int) -> bool:
    """Names exactly one winner on every admissible profile, and never a tie."""
    profiles = admissible_profiles_v1(n)
    if set(rule) != set(profiles):
        return False
    return all(rule[p] in ("A", "B") for p in profiles)


def is_impartial_v1(rule: Rule, n: int) -> bool:
    """Exchange the two score vectors and the winner exchanges too."""
    for a, b in admissible_profiles_v1(n):
        here, there = rule[(a, b)], rule[(b, a)]
        if here == "A" and there != "B":
            return False
        if here == "B" and there != "A":
            return False
    return True


def responsiveness_witnesses_v1(rule: Rule, n: int) -> List[Optional[Tuple[Profile, Profile]]]:
    """For each criterion, a profile pair differing only there whose winner differs.

    Either proposal's score may be the one altered; the result must land on
    another admissible profile, which is where the one-criterion case dies.
    """
    witnesses: List[Optional[Tuple[Profile, Profile]]] = []
    for criterion in range(n):
        found: Optional[Tuple[Profile, Profile]] = None
        for a, b in admissible_profiles_v1(n):
            for a2, b2 in ((_altered(a, criterion), b), (a, _altered(b, criterion))):
                if a2 == b2:
                    continue  # the charter excludes it, so it is not a witness
                if rule[(a2, b2)] != rule[(a, b)]:
                    found = ((a, b), (a2, b2))
                    break
            if found is not None:
                break
        witnesses.append(found)
    return witnesses


def is_responsive_v1(rule: Rule, n: int) -> bool:
    return all(w is not None for w in responsiveness_witnesses_v1(rule, n))


def departure_profiles_v1(rule: Rule, n: int) -> List[Profile]:
    """Admissible profiles with differing totals where the higher total loses."""
    out: List[Profile] = []
    for a, b in admissible_profiles_v1(n):
        total_a, total_b = sum(a), sum(b)
        if total_a == total_b:
            continue
        if rule[(a, b)] != ("A" if total_a > total_b else "B"):
            out.append((a, b))
    return out


def satisfies_all_v1(rule: Rule, n: int) -> bool:
    return (
        is_decisive_v1(rule, n)
        and is_impartial_v1(rule, n)
        and is_responsive_v1(rule, n)
    )


# ------------------------------------------------ small n: no search at all ---


def brute_force_v1(n: int) -> Dict[str, object]:
    """Every rule on the domain, with no starting point and no search order."""
    profiles = admissible_profiles_v1(n)
    best: Optional[int] = None
    best_rule: Optional[Rule] = None
    satisfying = 0
    for bits in itertools.product((0, 1), repeat=len(profiles)):
        rule = {p: ("A" if bit else "B") for p, bit in zip(profiles, bits)}
        if not satisfies_all_v1(rule, n):
            continue
        satisfying += 1
        cost = len(departure_profiles_v1(rule, n))
        if best is None or cost < best:
            best, best_rule = cost, rule
    return {
        "method": "exhaustive over all 2**%d rules" % len(profiles),
        "rules_examined": 2 ** len(profiles),
        "admissible_profiles": len(profiles),
        "satisfying_rules": satisfying,
        "rule_exists": satisfying > 0,
        "minimum_departures": best,
        "witness_rule": _readable(best_rule) if best_rule else None,
    }


# --------------------------------- larger n: exhibit a zero-departure rule ----


def _equal_total_pairs_v1(n: int) -> List[Tuple[Vector, Vector]]:
    return [
        (a, b)
        for a, b in itertools.combinations(score_vectors_v1(n), 2)
        if sum(a) == sum(b)
    ]


def _rule_from_tiebreak_v1(n: int, tiebreak: Callable[[Vector, Vector], Vector]) -> Rule:
    """Monotone wherever the totals differ; the tiebreak settles the rest.

    Every rule built this way departs from the monotone principle on zero
    profiles, by construction. Whether it is decisive, impartial and responsive
    is then checked, not assumed.
    """
    rule: Rule = {}
    for a, b in admissible_profiles_v1(n):
        total_a, total_b = sum(a), sum(b)
        if total_a != total_b:
            rule[(a, b)] = "A" if total_a > total_b else "B"
        else:
            rule[(a, b)] = "A" if tiebreak(a, b) == a else "B"
    return rule


def _first_difference_tiebreak_v1(a: Vector, b: Vector) -> Vector:
    """The vector holding the earliest criterion the two do not share.

    Symmetric in its arguments, which is what keeps the built rule impartial.
    """
    only_a = min(i for i in range(len(a)) if a[i] == 1 and b[i] == 0)
    only_b = min(i for i in range(len(b)) if b[i] == 1 and a[i] == 0)
    return a if only_a < only_b else b


def zero_departure_search_v1(n: int, exhaustive_limit: int = 20) -> Dict[str, object]:
    """Look for a rule that departs nowhere. Finding one settles the minimum.

    A departure count is a number of profiles and cannot be negative, so a
    verified zero-departure rule is optimal on sight. No enumeration of the full
    rule space is required, and none is done.
    """
    pairs = _equal_total_pairs_v1(n)
    candidates: List[Tuple[str, Callable[[Vector, Vector], Vector]]] = []
    if len(pairs) <= exhaustive_limit:
        for bits in itertools.product((0, 1), repeat=len(pairs)):
            choice = {
                frozenset(pair): (pair[0] if bit else pair[1])
                for pair, bit in zip(pairs, bits)
            }
            candidates.append(
                ("tie assignment %s" % "".join(str(b) for b in bits),
                 lambda a, b, _c=choice: _c[frozenset((a, b))])
            )
        method = "exhaustive over all 2**%d rules that depart nowhere" % len(pairs)
    else:
        candidates.append(("earliest unshared criterion", _first_difference_tiebreak_v1))
        method = (
            "one named construction, verified exhaustively over all %d profiles "
            "(the zero-departure family has 2**%d members, and one suffices)"
            % (len(admissible_profiles_v1(n)), len(pairs))
        )

    found = None
    responsive_count = 0
    for name, tiebreak in candidates:
        rule = _rule_from_tiebreak_v1(n, tiebreak)
        if not satisfies_all_v1(rule, n):
            continue
        responsive_count += 1
        if found is None:
            witnesses = responsiveness_witnesses_v1(rule, n)
            found = {
                "tiebreak": name,
                "departures": len(departure_profiles_v1(rule, n)),
                "decisive": is_decisive_v1(rule, n),
                "impartial": is_impartial_v1(rule, n),
                "responsive": True,
                "responsiveness_witnesses": [
                    "criterion %d: A=%s B=%s -> A=%s B=%s changes the winner"
                    % (i + 1, w[0][0], w[0][1], w[1][0], w[1][1])
                    for i, w in enumerate(witnesses)
                    if w is not None
                ],
                "rule": _readable(rule),
            }
    return {
        "method": method,
        "admissible_profiles": len(admissible_profiles_v1(n)),
        "equal_total_pairs": len(pairs),
        "zero_departure_candidates_examined": len(candidates),
        "zero_departure_candidates_satisfying": responsive_count,
        "rule_exists": found is not None,
        "minimum_departures": 0 if found is not None else None,
        "why_zero_is_minimal": (
            "a departure count is a number of profiles and is never negative"
            if found is not None
            else None
        ),
        "witness": found,
    }


def _readable(rule: Optional[Rule]) -> Optional[Dict[str, str]]:
    if rule is None:
        return None
    return {"A=%s B=%s" % (a, b): w for (a, b), w in sorted(rule.items())}


# ------------------------------------------------------------- the report ----


def run_v1() -> Dict[str, object]:
    """Calibrate on the known case first. Report nothing else if it fails."""

    gate_n, gate_expected = CALIBRATION_V1
    gate = brute_force_v1(gate_n)
    gate_passed = gate["minimum_departures"] == gate_expected

    report: Dict[str, object] = {
        "schema_version": "socrates-q6-independent-verifier/v1",
        "verifier": "scripts/q6_independent_verifier_v1.py",
        "verifier_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "independence": (
            "imports nothing from scripts.q6_ethics_question_v1; represents a "
            "rule as an ordered-profile map rather than an orientation of "
            "vector pairs; settles n<=2 by brute force over every rule"
        ),
        "calibration": {
            "criteria": gate_n,
            "expected_minimum_departures": gate_expected,
            "observed": gate["minimum_departures"],
            "passed": gate_passed,
            "source_of_expectation": (
                "established and machine-checked independently in Q5; also the "
                "exact case the first verifier's first version got wrong"
            ),
            "detail": gate,
        },
    }

    if not gate_passed:
        report["findings"] = None
        report["verdict"] = (
            "CALIBRATION FAILED. No figure from this run is reported. The n=2 "
            "answer is known to be %d and this verifier returned %r."
            % (gate_expected, gate["minimum_departures"])
        )
        return report

    findings: Dict[int, Dict[str, object]] = {}
    for n in sorted(CLAIM_UNDER_TEST_V1):
        if n == gate_n:
            findings[n] = gate
        elif len(admissible_profiles_v1(n)) <= 12:
            findings[n] = brute_force_v1(n)
        else:
            findings[n] = zero_departure_search_v1(n)

    agreement = {
        n: (
            (findings[n]["rule_exists"], findings[n]["minimum_departures"])
            == CLAIM_UNDER_TEST_V1[n]
        )
        for n in CLAIM_UNDER_TEST_V1
    }

    report["findings"] = {str(n): findings[n] for n in findings}
    report["claim_under_test"] = {
        str(n): list(v) for n, v in CLAIM_UNDER_TEST_V1.items()
    }
    report["agrees_with_claim"] = {str(n): v for n, v in agreement.items()}
    report["all_agree"] = all(agreement.values())
    report["verdict"] = (
        "CONFIRMED: every figure in the Q6 key is reproduced by a second, "
        "independent derivation."
        if all(agreement.values())
        else "CONTRADICTED on N in %s. The Q6 key must not be used."
        % sorted(n for n, ok in agreement.items() if not ok)
    )
    return report


if __name__ == "__main__":
    result = run_v1()
    print(json.dumps(result, indent=2, default=str))

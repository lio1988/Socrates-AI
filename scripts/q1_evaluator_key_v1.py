"""EVALUATOR-ONLY KEY for Q1. Never imported by any collection process.

``run_hard_logic_live_test_v1`` guards the three section labels below as
forbidden values, so importing this module anywhere on a collection path is a
contract violation, not a style problem. Collection for Q1 closed before this
file was written.

Predicate letters, for one person x:
    C(x) chairs the final review        R(x) approved report R
    S(x) approved report S              E(x) examined the primary evidence
    F(x) filed a formal exception       T(x) interviewed source T
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

Q1_ANSWER_IS_CONSISTENT_V1 = False

# EVALUATOR-ONLY KEY
Q1_FORCED_CONTRADICTION_V1 = "S(mira) and not S(mira)"

# Correct derivation:
Q1_DERIVATION_V1: Tuple[str, ...] = (
    "5 gives C(m).",
    "1 applied to C(m) gives R(m) and S(m).",
    "3 contraposed gives C(m) -> not F(m), so not F(m).",
    "2 applied to R(m) and S(m) gives E(m) or F(m); with not F(m), E(m).",
    "6 gives not T(m), so E(m) and not T(m).",
    "4 applied to E(m) and not T(m) gives not S(m).",
    "S(m) from step 2 and not S(m) from step 6 are contradictory.",
)

# Expected minimal inconsistent subset:
Q1_MINIMAL_SUBSET_V1: Tuple[int, ...] = (1, 2, 3, 4, 5, 6)

#: One satisfying assignment of the remaining five for each removal, which is
#: what actually proves minimality. Order: C, R, S, E, F, T.
Q1_REMOVAL_COUNTERMODELS_V1: Mapping[int, Mapping[str, bool]] = {
    1: {"C": True, "R": False, "S": False, "E": False, "F": False, "T": False},
    2: {"C": True, "R": True, "S": True, "E": False, "F": False, "T": False},
    3: {"C": True, "R": True, "S": True, "E": False, "F": True, "T": False},
    4: {"C": True, "R": True, "S": True, "E": True, "F": False, "T": False},
    5: {"C": False, "R": False, "S": False, "E": False, "F": False, "T": False},
    6: {"C": True, "R": True, "S": True, "E": True, "F": False, "T": True},
}

#: What a full-credit answer has to contain. Each criterion is worth one point.
Q1_CRITERIA_V1: Tuple[Tuple[str, str], ...] = (
    ("verdict", "states the six statements are inconsistent"),
    ("contradiction", "names S(m) and not S(m) as the forced contradiction"),
    ("derivation", "derives it through 5,1,3,2,6,4 without a gap"),
    ("subset", "identifies {1,2,3,4,5,6} as the minimal inconsistent subset"),
    ("removals", "justifies all six removals"),
    ("countermodels", "proves minimality with explicit satisfying assignments"),
)

Q1_MAXIMUM_SCORE_V1 = len(Q1_CRITERIA_V1)


def _semantics_v1(assignment: Mapping[str, bool]) -> Tuple[bool, ...]:
    """Truth value of each of the six statements under one assignment."""
    c, r, s = assignment["C"], assignment["R"], assignment["S"]
    e, f, t = assignment["E"], assignment["F"], assignment["T"]
    return (
        (not c) or (r and s),          # 1. C -> R and S
        (not (r and s)) or (e or f),   # 2. R and S -> E or F
        (not f) or (not c),            # 3. F -> not C
        (not (e and not t)) or (not s),  # 4. E and not T -> not S
        c,                              # 5. C(m)
        not t,                          # 6. not T(m)
    )


def verify_key_v1() -> Dict[str, Any]:
    """Machine-check the key itself before it is used to grade anything.

    The six statements must be unsatisfiable, and each of the six declared
    countermodels must satisfy the other five. If either fails, the key is
    wrong and no score computed from it means anything.
    """
    names = ("C", "R", "S", "E", "F", "T")
    unsat = True
    for mask in range(64):
        assignment = {n: bool(mask >> i & 1) for i, n in enumerate(names)}
        if all(_semantics_v1(assignment)):
            unsat = False
            break
    removals_ok: Dict[int, bool] = {}
    for removed, assignment in Q1_REMOVAL_COUNTERMODELS_V1.items():
        truths = _semantics_v1(assignment)
        removals_ok[removed] = all(
            value for index, value in enumerate(truths, start=1) if index != removed
        )
    return {
        "six_statements_unsatisfiable": unsat,
        "each_removal_has_a_countermodel": removals_ok,
        "key_is_sound": unsat and all(removals_ok.values()),
    }


def score_answer_v1(
    text: str, *, credited: Sequence[str]
) -> Dict[str, Any]:
    """Record a hand-adjudicated score against the fixed criteria.

    Scoring is deliberately not keyword matching. The evaluator reads the answer
    and names which criteria it met; this function only enforces that the named
    criteria exist and reports the total, so a score cannot silently drift to a
    criterion that was never declared.
    """
    valid = {name for name, _ in Q1_CRITERIA_V1}
    unknown = sorted(set(credited) - valid)
    if unknown:
        raise ValueError(f"unknown scoring criteria: {unknown}")
    met = [name for name, _ in Q1_CRITERIA_V1 if name in set(credited)]
    return {
        "criteria_met": met,
        "criteria_missed": [n for n, _ in Q1_CRITERIA_V1 if n not in set(credited)],
        "score": len(met),
        "maximum": Q1_MAXIMUM_SCORE_V1,
        "answer_length_chars": len(text),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(verify_key_v1(), indent=2))

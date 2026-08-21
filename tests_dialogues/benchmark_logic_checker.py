"""Benchmark evaluator for the frozen logic puzzle. EVALUATION CODE ONLY.

This is not runtime authority and must never be imported by CED or by the hybrid
core: it encodes one specific puzzle, and puzzle-specific logic in a governing
path is exactly the kind of hidden authority the migration exists to remove. It
exists so a benchmark result can be scored offline without a paid call.

The first version of this checker asked only whether the four names appeared in
the answer, and reported the H10 run as correct when it was not. A checker that
can be satisfied by surface features is not a checker.
"""

from __future__ import annotations

import re
from enum import Enum
from itertools import permutations
from typing import List, Sequence, Tuple

PARTICIPANTS: Tuple[str, ...] = ("Anna", "Ben", "Clara", "David")


def satisfies_constraints(order: Sequence[str]) -> bool:
    """The three constraints stated verbatim in the frozen task.

    1. Anna presents before Ben.
    2. Clara presents immediately before David.
    3. Ben does not present last.
    """
    position = {name: i for i, name in enumerate(order)}
    if position["Anna"] >= position["Ben"]:
        return False
    if position["David"] - position["Clara"] != 1:
        return False
    if position["Ben"] == len(order) - 1:
        return False
    return True


def valid_orders() -> List[Tuple[str, ...]]:
    """Enumerate independently rather than trusting the fixture's answer."""
    return [p for p in permutations(PARTICIPANTS) if satisfies_constraints(p)]


class BenchmarkVerdict(str, Enum):
    CORRECT_UNIQUE = "correct_unique"
    #: Claimed several orders work when exactly one does.
    INCORRECT_MULTIPLE = "incorrect_multiple"
    #: Named an order that violates a constraint.
    INVALID_PERMUTATION = "invalid_permutation"
    #: Never committed to an order at all.
    MISSING_CONCLUSION = "missing_conclusion"


#: Phrases that assert the task is underdetermined. The frozen failure is
#: recorded as `claimed_multiple_valid_orders`, and the live H10 answer opened
#: with "The information provided is insufficient".
_MULTIPLICITY = (
    "insufficient", "not sufficient", "cannot be determined",
    "cannot determine", "not unique", "multiple valid", "several valid",
    "more than one valid", "ambiguit", "ambiguous", "underdetermined",
    "list all valid orders",
)


#: Language that marks a named order as rejected rather than asserted.
#:
#: Only phrases that judge a named order belong here. "cannot be" was tried and
#: removed: it appears in the constraints themselves ("Ben cannot be last"), so
#: it disqualified the correct order in an answer that merely restated them.
_REFUTATION = (
    "is incorrect", "was incorrect", "is wrong", "is not correct",
    "violates", "is rejected", "does not satisfy", "is invalid",
    "is eliminated", "ruled out", "must be rejected",
)

#: Only separators may sit between the names of an asserted order. Anything
#: else means the names are prose about the constraints, not a stated sequence.
_SEPARATOR = re.compile(r"^[\s,;>\-—–>()\.]*(?:then|and|followed by|before)?[\s,;>\-—–>()\.]*$",
                        re.IGNORECASE)


def _named_orders(text: str) -> List[Tuple[str, ...]]:
    """Every full ordering of the four participants ASSERTED in the text.

    A four-name window only counts when nothing but separators lies between the
    names. Without that, restating the constraints produces phantom orders: in
    "Clara must present immediately before David, and Ben cannot be last, the
    order is Anna, Ben, Clara, David" a naive window reads Clara-David-Ben-Anna,
    which nobody asserted. That false positive scored a correct live answer as
    wrong, which is why the rule is stricter than "the names appear nearby".
    """
    found: List[Tuple[str, ...]] = []
    tokens = [(m.start(), m.end(), m.group(0)) for m in
              re.finditer("|".join(PARTICIPANTS), text)]
    for i in range(len(tokens) - 3):
        window = tokens[i:i + 4]
        names = [name for _, _, name in window]
        if sorted(names) != sorted(PARTICIPANTS):
            continue
        gaps = [text[window[j][1]:window[j + 1][0]] for j in range(3)]
        # A parenthetical initial such as "Anna (A)" is still a separator.
        gaps = [re.sub(r"\([A-D]\)", "", g) for g in gaps]
        if not all(_SEPARATOR.match(g) for g in gaps):
            continue
        # An order named in order to be refuted is not an order asserted.
        # "...the claim that the order is A C D B is incorrect because it
        # violates 'Ben is not last'" names it precisely to reject it.
        # Refutation follows the order it rejects: "the order is X is incorrect
        # because it violates...". Looking backwards was tried and removed - the
        # text before an order is usually the constraints, which read as
        # negations without rejecting anything.
        tail = text[window[3][1]:window[3][1] + 90].lower()
        if any(marker in tail for marker in _REFUTATION):
            continue
        candidate = tuple(names)
        if candidate not in found:
            found.append(candidate)
    return found


def evaluate_answer(answer: str) -> Tuple[BenchmarkVerdict, str]:
    """Score a council answer against the independently enumerated truth.

    Order of checks is deliberate: an answer that asserts underdetermination is
    wrong regardless of which orders it also lists, because the task has exactly
    one solution.
    """
    solutions = valid_orders()
    lowered = (answer or "").lower()

    if not answer.strip():
        return BenchmarkVerdict.MISSING_CONCLUSION, "empty answer"

    if any(phrase in lowered for phrase in _MULTIPLICITY):
        return (BenchmarkVerdict.INCORRECT_MULTIPLE,
                f"asserts the task is underdetermined; it has {len(solutions)} solution")

    named = _named_orders(answer)
    if not named:
        return BenchmarkVerdict.MISSING_CONCLUSION, "no full ordering is asserted"

    if any(order in solutions for order in named):
        if len(named) > 1 and any(o not in solutions for o in named):
            return (BenchmarkVerdict.INCORRECT_MULTIPLE,
                    f"asserts several orders including invalid ones: {named}")
        return BenchmarkVerdict.CORRECT_UNIQUE, f"asserts {named[0]}"

    return (BenchmarkVerdict.INVALID_PERMUTATION,
            f"asserts {named[0]}, which violates a stated constraint")

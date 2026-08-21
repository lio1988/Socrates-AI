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


def _named_orders(text: str) -> List[Tuple[str, ...]]:
    """Every full ordering of the four participants asserted in the text.

    Sequences are read in the order the names appear within a window, so
    "Clara, David, Anna, Ben" is read as that order and not as a mention list.
    """
    found: List[Tuple[str, ...]] = []
    tokens = [(m.start(), m.group(0)) for m in
              re.finditer("|".join(PARTICIPANTS), text)]
    for i in range(len(tokens) - 3):
        window = [name for _, name in tokens[i:i + 4]]
        if sorted(window) == sorted(PARTICIPANTS):
            candidate = tuple(window)
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

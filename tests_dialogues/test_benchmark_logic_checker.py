"""The benchmark evaluator, and the offline scoring of the recorded H10 answer.

No paid call: the H10 answer is quoted from the recorded run.
"""

from __future__ import annotations

import ast
import pathlib

from tests_dialogues.benchmark_logic_checker import (
    PARTICIPANTS,
    BenchmarkVerdict,
    evaluate_answer,
    satisfies_constraints,
    valid_orders,
)

#: Verbatim opening of the core_answer the H10 live run produced.
H10_ANSWER = (
    "The information provided is insufficient to determine a unique presentation "
    "order due to the ambiguity in the interpretation of 'before' in the "
    "constraint 'Anna presents before Ben.' This ambiguity affects the possible "
    "presentation orders, and without further clarification the order cannot be "
    "fixed."
)


def test_the_constraints_admit_exactly_one_order():
    """Enumerated independently, not read from the fixture."""
    solutions = valid_orders()
    assert solutions == [("Anna", "Ben", "Clara", "David")]
    assert len(solutions) == 1


def test_each_constraint_actually_bites():
    assert satisfies_constraints(("Anna", "Ben", "Clara", "David")) is True
    # Ben before Anna violates constraint 1.
    assert satisfies_constraints(("Ben", "Anna", "Clara", "David")) is False
    # Clara not immediately before David violates constraint 2.
    assert satisfies_constraints(("Clara", "Anna", "Ben", "David")) is False
    # C-D-A-B puts Ben last, violating constraint 3. This is the counterexample
    # the frozen elenchus failed to reject.
    assert satisfies_constraints(("Clara", "David", "Anna", "Ben")) is False


def test_the_checker_separates_all_four_outcomes():
    correct, _ = evaluate_answer(
        "The unique order is Anna, then Ben, then Clara, then David.")
    assert correct is BenchmarkVerdict.CORRECT_UNIQUE

    multiple, _ = evaluate_answer(
        "The information is insufficient; several valid orders exist.")
    assert multiple is BenchmarkVerdict.INCORRECT_MULTIPLE

    invalid, _ = evaluate_answer("The order is Clara, David, Anna, Ben.")
    assert invalid is BenchmarkVerdict.INVALID_PERMUTATION

    missing, _ = evaluate_answer("Constraints are interesting to consider.")
    assert missing is BenchmarkVerdict.MISSING_CONCLUSION


def test_surface_name_presence_is_not_enough_to_score_correct():
    """The defect in the first checker: all four names, and a wrong answer."""
    verdict, _ = evaluate_answer(
        "Considering Anna, Ben, Clara and David, the order cannot be determined.")
    assert verdict is BenchmarkVerdict.INCORRECT_MULTIPLE


def test_the_recorded_h10_answer_scores_as_a_failure():
    """The live council was wrong. Scored offline, from the recorded text."""
    verdict, reason = evaluate_answer(H10_ANSWER)
    assert verdict is BenchmarkVerdict.INCORRECT_MULTIPLE
    assert "underdetermined" in reason
    assert verdict is not BenchmarkVerdict.CORRECT_UNIQUE


def test_the_checker_is_not_imported_by_any_runtime_module():
    """Puzzle-specific logic must never reach CED or the hybrid core."""
    backend = pathlib.Path(__file__).resolve().parents[1] / "backend"
    offenders = []
    for path in backend.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            if any("benchmark_logic_checker" in n for n in names):
                offenders.append(path.relative_to(backend).as_posix())
                break
    assert offenders == [], f"runtime imports benchmark code: {offenders}"


def test_participants_match_the_frozen_fixture():
    import json
    fixture = json.loads(
        (pathlib.Path(__file__).parent / "fixtures" / "known_failures"
         / "current_canonical_repeat_003.json").read_text(encoding="utf-8"))
    assert sorted(fixture["benchmark"]["participants"]) == sorted(PARTICIPANTS)
    assert fixture["benchmark"]["ground_truth"]["valid_orders"] == [list(valid_orders()[0])]

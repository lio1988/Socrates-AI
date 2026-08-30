"""The second Q6 verifier must be able to say no, or its yes means nothing.

The first Q6 verifier agreed with itself. That is the failure mode these tests
exist for: a verifier that returns CONFIRMED for every input confirms nothing.
So most of what is checked here is refusal - a wrong claim must be contradicted,
and a failed calibration must suppress the reading entirely.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import scripts.q6_independent_verifier_v1 as v


@pytest.fixture(scope="module")
def report():
    return v.run_v1()


def test_calibration_on_the_known_case_passes_first(report):
    assert report["calibration"]["criteria"] == 2
    assert report["calibration"]["observed"] == 2
    assert report["calibration"]["passed"] is True


def test_every_figure_in_the_key_is_reproduced(report):
    assert report["agrees_with_claim"] == {"1": True, "2": True, "3": True, "4": True}
    assert report["all_agree"] is True
    assert report["verdict"].startswith("CONFIRMED")


def test_a_failed_calibration_suppresses_every_reading(monkeypatch):
    monkeypatch.setattr(v, "CALIBRATION_V1", (2, 3))
    out = v.run_v1()
    assert out["calibration"]["passed"] is False
    assert out["findings"] is None
    assert out["verdict"].startswith("CALIBRATION FAILED")
    assert "all_agree" not in out


def test_a_wrong_claim_is_contradicted(monkeypatch):
    wrong = dict(v.CLAIM_UNDER_TEST_V1)
    wrong[3] = (True, 2)  # the n=2 answer, smuggled into the n=3 slot
    monkeypatch.setattr(v, "CLAIM_UNDER_TEST_V1", wrong)
    out = v.run_v1()
    assert out["all_agree"] is False
    assert out["agrees_with_claim"]["3"] is False
    assert out["verdict"].startswith("CONTRADICTED")


def test_it_stands_on_the_standard_library_alone():
    """Not merely "does not import the first verifier": imports nothing of ours.

    Checked on the parsed import statements rather than by searching the text,
    because the module names this file's subject in its prose.
    """
    tree = ast.parse(Path(v.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    ours = {m for m in imported if m.split(".")[0] in {"scripts", "backend", "tests_dialogues"}}
    assert ours == set(), f"the second verifier must not lean on our code: {ours}"


def test_one_criterion_admits_no_rule_at_all(report):
    n1 = report["findings"]["1"]
    assert n1["rules_examined"] == 4
    assert n1["satisfying_rules"] == 0
    assert n1["rule_exists"] is False


def test_two_criteria_settled_by_brute_force_not_by_search(report):
    n2 = report["findings"]["2"]
    assert n2["rules_examined"] == 2 ** 12
    assert n2["satisfying_rules"] == 48
    assert n2["minimum_departures"] == 2


def test_the_exhibited_rules_are_checked_over_the_whole_domain(report):
    for n, expected_profiles in ((3, 56), (4, 240)):
        finding = report["findings"][str(n)]
        witness = finding["witness"]
        assert finding["admissible_profiles"] == expected_profiles
        assert witness["decisive"] and witness["impartial"] and witness["responsive"]
        assert witness["departures"] == 0
        assert len(witness["rule"]) == expected_profiles
        assert len(witness["responsiveness_witnesses"]) == n


def test_three_criteria_is_exhaustive_over_the_zero_departure_family(report):
    n3 = report["findings"]["3"]
    assert n3["equal_total_pairs"] == 6
    assert n3["zero_departure_candidates_examined"] == 2 ** 6
    # Not merely "one exists": at three criteria the tie-break is entirely free.
    assert n3["zero_departure_candidates_satisfying"] == 2 ** 6


def test_zero_is_minimal_without_enumerating_the_rule_space(report):
    for n in ("3", "4"):
        assert report["findings"][n]["minimum_departures"] == 0
        assert "never negative" in report["findings"][n]["why_zero_is_minimal"]


def test_the_lexicographic_rule_passes_two_conditions_and_fails_the_third():
    """Criterion 1, then criterion 2: decisive and impartial, never responsive.

    This is the rule a reader reaches for first, and the three conditions have to
    be able to reject it. Criterion 2 has no witness: wherever it decides, the
    two vectors agree on criterion 1, so altering it lands on the identical
    profile the charter excludes.
    """
    rule = {}
    for a, b in v.admissible_profiles_v1(2):
        key = 0 if a[0] != b[0] else 1
        rule[(a, b)] = "A" if a[key] > b[key] else "B"
    assert v.is_decisive_v1(rule, 2)
    assert v.is_impartial_v1(rule, 2)
    assert not v.is_responsive_v1(rule, 2)
    witnesses = v.responsiveness_witnesses_v1(rule, 2)
    assert witnesses[0] is not None and witnesses[1] is None


def test_impartiality_is_checked_profile_by_profile_not_assumed():
    rule = {p: "A" for p in v.admissible_profiles_v1(2)}
    assert v.is_decisive_v1(rule, 2)
    assert not v.is_impartial_v1(rule, 2)

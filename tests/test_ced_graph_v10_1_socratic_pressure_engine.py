"""CED Graph v10.1 — Socratic Pressure & Scope Narrowing Engine tests.

Pure, deterministic, offline. Verifies that vague answers draw high pressure,
practical/objection-bearing answers score higher, pressure rises across rounds,
empty answers are rejected, a fully-formed answer can be accepted, and the
Socratic challenge becomes stricter at later rounds.
"""

from backend.reasoning.socratic_pressure import (
    PRESSURE_VERSION,
    PRESSURE_ORDER,
    SocraticPressureReport,
    normalize_answer_text,
    score_vagueness,
    score_practical_grounding,
    score_objection_strength,
    compute_pressure_level,
    build_socratic_challenge,
    evaluate_answer_pressure,
    should_accept_answer,
    identify_required_repairs,
)


QUESTION = "Is knowledge justified true belief?"

GOOD_ANSWER = (
    "No, knowledge is not simply justified true belief. We treat a claim as knowledge "
    "only when it survives evidence, objection, and revision. For example, a doctor's "
    "diagnosis counts as knowledge when it is confirmed by tests and survives a second "
    "opinion. The strongest objection is that this makes knowledge provisional rather "
    "than certain, since a future test could overturn it. What is uncertain is where to "
    "draw the line for enough evidence, and that boundary could change as standards improve."
)

VAGUE_ANSWER = (
    "Well, it depends. Knowledge is a complex, dynamic process that is multifaceted and "
    "shaped by various factors. Generally speaking, in some sense it is context-dependent."
)

WEAK_BUT_NOT_VAGUE = "For example, sometimes a guess turns out right."


# --- 1. vague abstract answer gets high vagueness pressure -----------------

def test_vague_answer_gets_high_vagueness_pressure():
    score = score_vagueness(VAGUE_ANSWER)
    assert score >= 0.6
    report = evaluate_answer_pressure(QUESTION, VAGUE_ANSWER, 1)
    assert report.vagueness_score >= 0.6
    assert "Answer is too vague or abstract." in report.weaknesses


# --- 2. answer with practical example scores better than one without -------

def test_example_scores_better_than_no_example():
    with_example = "For example, a doctor confirms a diagnosis with a blood test."
    without_example = "A diagnosis can be confirmed in principle."
    assert score_practical_grounding(with_example) > score_practical_grounding(without_example)


# --- 3. answer with strongest objection scores better than one without -----

def test_objection_scores_better_than_no_objection():
    with_objection = (
        "The strongest objection is that the criterion is too strict because it rejects "
        "useful everyday beliefs."
    )
    without_objection = "This criterion works well for most ordinary cases."
    assert score_objection_strength(with_objection) > score_objection_strength(without_objection)


# --- 4. pressure level increases across rounds -----------------------------

def test_pressure_level_increases_across_rounds():
    ranks = [
        PRESSURE_ORDER.index(evaluate_answer_pressure(QUESTION, GOOD_ANSWER, r).pressure_level)
        for r in (1, 2, 3, 4, 5)
    ]
    assert ranks == sorted(ranks)          # non-decreasing
    assert ranks[-1] > ranks[0]            # strictly higher at the end
    assert compute_pressure_level(1) == "mild"
    assert compute_pressure_level(5) == "final_gate"
    assert compute_pressure_level(9) == "final_gate"


# --- 5. empty answer cannot be accepted ------------------------------------

def test_empty_answer_cannot_be_accepted():
    report = evaluate_answer_pressure(QUESTION, "", 5)
    assert report.can_accept_answer is False
    assert score_vagueness("") == 1.0


# --- 6. concrete full answer can be accepted -------------------------------

def test_concrete_full_answer_can_be_accepted():
    report = evaluate_answer_pressure(QUESTION, GOOD_ANSWER, 5)
    # All six pillars are present.
    assert report.directness_score >= 0.5
    assert report.scope_fit_score >= 0.5
    assert report.operational_clarity_score >= 0.5
    assert report.practical_grounding_score >= 0.5
    assert report.objection_strength_score >= 0.5
    assert report.uncertainty_calibration_score >= 0.5
    assert report.can_accept_answer is True
    assert report.required_repairs == []


# --- 7. Socratic challenge becomes stricter by later rounds ----------------

def test_socratic_challenge_gets_stricter_by_round():
    from backend.reasoning.socratic_pressure import _all_scores
    scores = _all_scores(QUESTION, WEAK_BUT_NOT_VAGUE)
    c1 = build_socratic_challenge(QUESTION, WEAK_BUT_NOT_VAGUE, scores, 1)
    c5 = build_socratic_challenge(QUESTION, WEAK_BUT_NOT_VAGUE, scores, 5)
    assert c1 != c5
    assert c1.startswith("Let's clarify")
    assert c5.startswith("Final gate")
    # The final gate demands at least as many repairs as the mild round.
    assert c5.count(";") >= c1.count(";")
    # Not insulting.
    for c in (c1, c5):
        for bad in ("stupid", "idiot", "dumb", "nonsense"):
            assert bad not in c.lower()


# --- structure + determinism -----------------------------------------------

def test_report_structure_and_version():
    report = evaluate_answer_pressure(QUESTION, GOOD_ANSWER, 3)
    assert isinstance(report, SocraticPressureReport)
    data = report.to_dict()
    for key in ("pressure_version", "round_number", "pressure_level",
                "vagueness_score", "directness_score", "scope_fit_score",
                "operational_clarity_score", "practical_grounding_score",
                "objection_strength_score", "uncertainty_calibration_score",
                "weaknesses", "required_repairs", "next_socratic_challenge",
                "can_accept_answer"):
        assert key in data
    assert data["pressure_version"] == PRESSURE_VERSION


def test_evaluation_is_deterministic():
    a = evaluate_answer_pressure(QUESTION, GOOD_ANSWER, 4).to_dict()
    b = evaluate_answer_pressure(QUESTION, GOOD_ANSWER, 4).to_dict()
    assert a == b


def test_required_repairs_are_concrete_tokens():
    scores = {
        "vagueness": 1.0, "directness": 0.0, "scope_fit": 0.0,
        "operational_clarity": 0.0, "practical_grounding": 0.0,
        "objection_strength": 0.0, "uncertainty_calibration": 0.0,
    }
    repairs = identify_required_repairs(scores)
    assert "provide_direct_answer" in repairs
    assert "narrow_scope" in repairs
    assert "define_operational_criterion" in repairs
    assert "add_practical_example" in repairs
    assert "add_strongest_objection" in repairs
    assert "state_uncertainty" in repairs

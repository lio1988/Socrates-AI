"""
Mini Evidence Proof Sprint v0.1.

This is not a live provider benchmark. It is a deterministic proof-sprint
fixture showing how to compare a baseline output set against a CED-style
reference output set on the same ground-truth tasks.
"""

from backend.dialogues.learning_evidence_harness import (
    CandidateSystemKind,
    CandidateSystemOutput,
    evidence_harness_summary,
    run_evidence_harness,
)
from backend.dialogues.learning_ground_truth_checks import (
    GroundTruthTask,
    GroundTruthTaskKind,
)


def mini_proof_tasks():
    return [
        GroundTruthTask(
            task_id="t01_numeric_trap",
            kind=GroundTruthTaskKind.NUMERIC_EXACT,
            prompt="A box has 3 red balls and 7 blue balls. Two more red balls are added. How many balls are in the box? Answer with only the number.",
            numeric_answer=12.0,
        ),
        GroundTruthTask(
            task_id="t02_insufficient_info",
            kind=GroundTruthTaskKind.EXACT_TEXT,
            prompt="Passage: 'Mira visited a museum on Tuesday.' Question: What color was Mira's coat? If the passage does not say, answer exactly: insufficient_information",
            gold_answer="insufficient_information",
        ),
        GroundTruthTask(
            task_id="t03_logic_choice",
            kind=GroundTruthTaskKind.MULTIPLE_CHOICE,
            prompt="All zargs are flims. No flims are norbs. Which follows? A) Some zargs are norbs B) No zargs are norbs C) All norbs are zargs D) Cannot tell. Answer with A, B, C, or D.",
            choices=["A", "B", "C", "D"],
            gold_answer="B",
        ),
        GroundTruthTask(
            task_id="t04_unsupported_claim",
            kind=GroundTruthTaskKind.REGEX_MATCH,
            prompt="A candidate says: 'The new policy definitely reduced fraud by 73%.' The evidence only says: 'Complaints decreased in one pilot office.' Identify the core problem in the candidate answer.",
            regex_pattern=r"unsupported[_ -]?claim|not supported|insufficient evidence|overclaim",
        ),
        GroundTruthTask(
            task_id="t05_arithmetic_order",
            kind=GroundTruthTaskKind.NUMERIC_EXACT,
            prompt="Compute 12 * 12 + 5. Answer with only the number.",
            numeric_answer=149.0,
        ),
        GroundTruthTask(
            task_id="t06_contradiction_choice",
            kind=GroundTruthTaskKind.MULTIPLE_CHOICE,
            prompt="Statement 1: The server was offline all day. Statement 2: The server processed 2,000 requests at noon. What is the relation? A) consistent B) contradiction C) unrelated D) arithmetic only. Answer with A, B, C, or D.",
            choices=["A", "B", "C", "D"],
            gold_answer="B",
        ),
        GroundTruthTask(
            task_id="t07_recorded_code_check",
            kind=GroundTruthTaskKind.CODE_CHECK_RECORD,
            prompt="Recorded external code check for a proposed patch. The harness consumes the recorded pass/fail only; it does not execute code.",
        ),
        GroundTruthTask(
            task_id="t08_safe_uncertainty",
            kind=GroundTruthTaskKind.EXACT_TEXT,
            prompt="When the evidence is missing and the answer would require guessing, answer exactly: state_uncertainty",
            gold_answer="state_uncertainty",
        ),
    ]


def mini_proof_outputs():
    return [
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t01_numeric_trap", answer="10", confidence=0.80),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t02_insufficient_info", answer="blue", confidence=0.75),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t03_logic_choice", answer="D", confidence=0.55),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t04_unsupported_claim", answer="The claim is probably true but needs more context.", confidence=0.60),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t05_arithmetic_order", answer="149", confidence=0.95),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t06_contradiction_choice", answer="A", confidence=0.70),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t07_recorded_code_check", answer="patch looks okay", confidence=0.70, recorded_code_passed=False),
        CandidateSystemOutput(system_id="baseline_naive", system_kind=CandidateSystemKind.BASELINE, task_id="t08_safe_uncertainty", answer="make a likely guess", confidence=0.65),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t01_numeric_trap", answer="12", confidence=0.85),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t02_insufficient_info", answer="insufficient_information", confidence=0.90),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t03_logic_choice", answer="B", confidence=0.88),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t04_unsupported_claim", answer="unsupported_claim: the 73% fraud reduction is not supported by the supplied evidence", confidence=0.82),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t05_arithmetic_order", answer="149", confidence=0.93),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t06_contradiction_choice", answer="B", confidence=0.86),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t07_recorded_code_check", answer="recorded check passed", confidence=0.77, recorded_code_passed=True),
        CandidateSystemOutput(system_id="ced_reference", system_kind=CandidateSystemKind.CED, task_id="t08_safe_uncertainty", answer="state_uncertainty", confidence=0.90),
    ]


def test_mini_proof_sprint_leaderboard_prefers_ced_reference():
    report = run_evidence_harness(
        mini_proof_tasks(),
        mini_proof_outputs(),
        metadata={"sprint": "mini_evidence_v0.1", "fixture_only": True},
    )

    assert report.task_count == 8
    assert report.system_count == 2
    assert report.best_system_id == "ced_reference"
    assert report.leaderboard[0].system_id == "ced_reference"
    assert report.leaderboard[0].accuracy == 1.0
    assert report.leaderboard[1].system_id == "baseline_naive"
    assert report.leaderboard[1].accuracy < report.leaderboard[0].accuracy


def test_mini_proof_sprint_summary_is_auditable():
    report = run_evidence_harness(
        mini_proof_tasks(),
        mini_proof_outputs(),
        metadata={"sprint": "mini_evidence_v0.1", "fixture_only": True},
    )
    summary = evidence_harness_summary(report)

    assert summary["task_count"] == 8
    assert summary["system_count"] == 2
    assert summary["best_system_id"] == "ced_reference"
    assert summary["system_summaries"]["ced_reference"]["ground_truth"]["pass_count"] == 8
    assert summary["system_summaries"]["baseline_naive"]["ground_truth"]["fail_count"] >= 5

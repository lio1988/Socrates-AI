"""Trace-window identity evidence must compare like with like."""

from backend.dialogues.openclaw_identity import evidence_from_trace_windows

_PHASES = (
    "opening",
    "initial_response",
    "elenchus",
    "reflection",
    "reconstruction",
    "synthesis",
)


def _trace(session_id, question, *, assembly_present):
    return {
        "session_id": session_id,
        "question": question,
        "moves": [
            {"move_id": f"{session_id}_{phase}", "phase": phase}
            for phase in _PHASES
        ],
        "assembly": ({
            "sections": [{
                "section_name": "core_answer",
                "source_draft_id": f"draft_{session_id}_synthesis",
            }],
        } if assembly_present else None),
        "ratification": {
            "ratified": True,
            "ratification_status": "ratified",
        },
    }


def test_matched_questions_can_emit_failure_delta():
    before = [_trace("b1", "same question", assembly_present=False)]
    after = [_trace("a1", "same question", assembly_present=True)]

    evidence = evidence_from_trace_windows(before, after)

    assert evidence["synthesis_quality_failures_delta"] == -1
    assert "trace_window_match" not in evidence


def test_smaller_after_window_cannot_fake_improvement():
    before = [
        _trace("b1", "q1", assembly_present=False),
        _trace("b2", "q2", assembly_present=False),
    ]
    after = [_trace("a1", "q1", assembly_present=True)]

    evidence = evidence_from_trace_windows(before, after)

    assert evidence["trace_window_match"] is False
    assert evidence["trace_window_mismatch_reason"] == "different_window_sizes"
    assert not any(key.endswith("_failures_delta") for key in evidence)


def test_different_question_sets_cannot_fake_improvement():
    before = [_trace("b1", "hard question", assembly_present=False)]
    after = [_trace("a1", "easy question", assembly_present=True)]

    evidence = evidence_from_trace_windows(before, after)

    assert evidence["trace_window_match"] is False
    assert evidence["trace_window_mismatch_reason"] == \
        "different_question_multisets"
    assert not any(key.endswith("_failures_delta") for key in evidence)

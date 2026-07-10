"""Shadow promotion evidence must be eligible, ratified, and replay-safe."""

import copy

from backend.dialogues.openclaw_identity import (
    evaluate_gate,
    evidence_from_shadow_traces,
    next_gate_for,
)


def _shadow_trace(session_id, *, ratified=True, ok=True, marked=True):
    move_id = f"move_{session_id}"
    return {
        "trace_version": "openclaw_shadow_trace_v0",
        "shadow_run": marked,
        "ok": ok,
        "session_id": session_id,
        "question": "q",
        "moves": [{
            "move_id": move_id,
            "phase": "synthesis",
            "role": "synthesizer",
            "provider_id": "shadow_apprentice",
            "confidence": 0.8,
        }],
        "assembly": {"sections": [{
            "section_name": "blind_spots",
            "source_draft_id": f"draft_{move_id}",
        }]},
        "ratification": {
            "ratified": ratified,
            "ratification_status": (
                "ratified" if ratified else "repair_required"),
        },
    }


def test_only_successful_ratified_marked_shadow_records_count_for_gate():
    traces = [
        _shadow_trace("eligible"),
        _shadow_trace("unratified", ratified=False),
        _shadow_trace("failed", ok=False),
        _shadow_trace("unmarked", marked=False),
    ]

    evidence = evidence_from_shadow_traces("shadow_apprentice", traces)

    assert evidence["shadow_blind_spots_wins"] == 1
    assert evidence["shadow_sessions_analyzed"] == 1
    assert evidence["shadow_session_ids"] == ["eligible"]
    assert evidence["shadow_records_marked"] == 3
    assert evidence["shadow_records_unique"] == 3
    assert evidence["shadow_records_eligible"] == 1
    assert evidence["shadow_records_excluded_failed"] == 1
    assert evidence["shadow_records_excluded_unratified"] == 1
    assert evidence["shadow_excluded_session_ids"] == ["failed", "unratified"]


def test_unratified_shadow_records_cannot_create_a_passing_metric():
    evidence = evidence_from_shadow_traces(
        "shadow_apprentice",
        [_shadow_trace("u1", ratified=False),
         _shadow_trace("u2", ratified=False),
         _shadow_trace("u3", ratified=False)],
    )

    assert "shadow_blind_spots_wins" not in evidence
    assert evidence["shadow_records_eligible"] == 0
    gate = next_gate_for("v0.3")
    result = evaluate_gate(gate, evidence)
    assert result.passed is False
    assert "missing evidence" in result.reasons[0]


def test_identical_session_replay_counts_once():
    original = _shadow_trace("replayed")
    evidence = evidence_from_shadow_traces(
        "shadow_apprentice",
        [original, copy.deepcopy(original), copy.deepcopy(original)],
    )

    assert evidence["shadow_records_marked"] == 3
    assert evidence["shadow_records_unique"] == 1
    assert evidence["shadow_duplicate_replays_ignored"] == 2
    assert evidence["shadow_sessions_analyzed"] == 1
    assert evidence["shadow_blind_spots_wins"] == 1
    assert evidence["shadow_session_ids"] == ["replayed"]


def test_conflicting_duplicate_session_is_excluded_completely():
    first = _shadow_trace("conflict")
    second = copy.deepcopy(first)
    second["question"] = "different payload under the same id"

    evidence = evidence_from_shadow_traces(
        "shadow_apprentice", [first, second])

    assert evidence["shadow_records_unique"] == 0
    assert evidence["shadow_conflicting_duplicate_session_ids"] == ["conflict"]
    assert evidence["shadow_excluded_session_ids"] == ["conflict"]
    assert "shadow_blind_spots_wins" not in evidence


def test_missing_session_id_is_not_eligible():
    missing = _shadow_trace("")
    evidence = evidence_from_shadow_traces("shadow_apprentice", [missing])

    assert evidence["shadow_records_missing_session_id"] == 1
    assert evidence["shadow_records_eligible"] == 0
    assert "shadow_blind_spots_wins" not in evidence

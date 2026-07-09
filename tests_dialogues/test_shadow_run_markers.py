"""
Shadow-run marker tests (Goal 13.2).

The Shadow-Apprentice claim becomes mechanically verifiable: traces are
marked ``shadow_run`` AT CAPTURE TIME (TraceCapturer(shadow_run=True)), and
evidence_from_shadow_traces counts ONLY marked traces — an unmarked trace is
never shadow, no matter what the caller believes. Counted session ids travel
with the evidence so the approver can audit exactly which runs backed a
promotion.

No provider calls, no network, no keys.
"""

import asyncio

import pytest

from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode
from backend.dialogues.openclaw_memory import TraceCapturer
from backend.dialogues.openclaw_identity import (
    collect_gate_evidence,
    evaluate_gate,
    evidence_from_shadow_traces,
    next_gate_for,
)


def _shadow_trace(sid, winner="seat_a"):
    return {
        "session_id": sid, "question": "q", "shadow_run": True,
        "moves": [{"move_id": f"m_{sid}_{p}", "phase": "synthesis",
                   "role": "synthesizer", "confidence": 0.7, "provider_id": p}
                  for p in ("seat_a", "seat_b")],
        "assembly": {"sections": [
            {"section_name": "blind_spots",
             "source_draft_id": f"draft_m_{sid}_{winner}"}]},
        "ratification": {"ratified": True, "ratification_status": "ratified"},
    }


def _live_trace(sid, winner="seat_a"):
    t = _shadow_trace(sid, winner)
    t["shadow_run"] = False
    return t


def _unmarked_trace(sid, winner="seat_a"):
    t = _shadow_trace(sid, winner)
    del t["shadow_run"]                     # pre-13.2 trace: no marker at all
    return t


# --------------------------------------------------------------------------- #
# Capture-time marking
# --------------------------------------------------------------------------- #

def test_capturer_marks_shadow_at_capture_time():
    capturer = TraceCapturer(shadow_run=True)
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           trace_capturer=capturer)
    asyncio.run(ced.run_registry_session("shadow q", session_id="sh_mark_1"))
    assert capturer.latest_trace()["shadow_run"] is True


def test_default_capture_is_not_shadow():
    capturer = TraceCapturer()
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           trace_capturer=capturer)
    asyncio.run(ced.run_registry_session("live q", session_id="live_mark_1"))
    assert capturer.latest_trace()["shadow_run"] is False


# --------------------------------------------------------------------------- #
# Marker-verified evidence
# --------------------------------------------------------------------------- #

def test_only_marked_traces_count_as_shadow():
    mixed = [
        _shadow_trace("sh1"), _shadow_trace("sh2"), _shadow_trace("sh3"),
        _live_trace("live1"),        # explicitly live
        _unmarked_trace("old1"),     # pre-marker trace: never shadow
    ]
    evidence = evidence_from_shadow_traces("seat_a", mixed)
    assert evidence["shadow_blind_spots_wins"] == 3
    assert evidence["shadow_sessions_analyzed"] == 3
    assert evidence["shadow_session_ids"] == ["sh1", "sh2", "sh3"]


def test_no_marked_traces_means_no_evidence():
    assert evidence_from_shadow_traces(
        "seat_a", [_live_trace("l1"), _unmarked_trace("o1")]) == {}


def test_gate_v0_3_passes_only_on_marked_wins():
    gate = next_gate_for("v0.3")
    marked = [_shadow_trace(f"sh{i}") for i in range(3)]
    assert evaluate_gate(
        gate, evidence_from_shadow_traces("seat_a", marked)).passed is True
    # The same wins WITHOUT markers produce no evidence -> honest fail.
    unmarked = [_unmarked_trace(f"o{i}") for i in range(3)]
    assert evaluate_gate(
        gate, evidence_from_shadow_traces("seat_a", unmarked)).passed is False


def test_losses_in_shadow_do_not_count_as_wins():
    traces = [_shadow_trace("sh1", winner="seat_b"),
              _shadow_trace("sh2", winner="seat_b")]
    evidence = evidence_from_shadow_traces("seat_a", traces)
    assert evidence["shadow_blind_spots_wins"] == 0
    assert evidence["shadow_sessions_analyzed"] == 2


# --------------------------------------------------------------------------- #
# collect_gate_evidence: verified path wins over declared path
# --------------------------------------------------------------------------- #

def test_collect_requires_agent_id_with_shadow_traces():
    with pytest.raises(ValueError):
        collect_gate_evidence(shadow_traces=[_shadow_trace("sh1")])
    with pytest.raises(ValueError):
        collect_gate_evidence(shadow_agent_id="seat_a")


def test_verified_shadow_evidence_overrides_declared():
    from backend.dialogues.openclaw_identity import build_identity_profile
    # Declared profile claims 5 shadow wins over unmarked traces...
    declared = build_identity_profile(
        "seat_a", [_unmarked_trace(f"u{i}") for i in range(5)])
    # ...but the marker-verified path finds only 1 real shadow win.
    evidence = collect_gate_evidence(
        shadow_profile=declared,
        shadow_traces=[_shadow_trace("sh1"), _live_trace("l1")],
        shadow_agent_id="seat_a",
    )
    assert evidence["shadow_blind_spots_wins"] == 1     # verified wins
    assert evidence["shadow_session_ids"] == ["sh1"]


def test_end_to_end_shadow_sessions_to_gate():
    capturer = TraceCapturer(shadow_run=True)
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           trace_capturer=capturer)
    for i in range(2):
        asyncio.run(ced.run_registry_session(
            f"shadow e2e {i}", session_id=f"sh_e2e_{i}"))
    evidence = evidence_from_shadow_traces("mock_seat0", capturer.traces)
    assert evidence["shadow_sessions_analyzed"] == 2
    assert evidence["shadow_session_ids"] == ["sh_e2e_0", "sh_e2e_1"]
    assert 0 <= evidence["shadow_blind_spots_wins"] <= 2

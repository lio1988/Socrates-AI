"""
Agent Identity Layer tests (Goal 13 — Self-Improving Agent Identity).

Verifies:
  - role_strengths derived mechanically from Goal 5 traces (assembly winner ->
    move -> provider mapping), never from hidden scorecards
  - profiles are honest: absent agent = zero evidence, unresolved sections
    are no contest, missing assembly contributes nothing
  - version gates are declarative and evidence-backed; missing evidence FAILS
  - NO automatic self-promotion: promotion needs a passing gate + a named
    approver who is not the agent; stages advance one rung at a time
  - the full gate chain v0.1 -> v1.0 walks only on rigged passing evidence
  - Soul Card is descriptive-not-authority and leaks nothing
  - runtime isolation: the CED core never imports the identity package

No provider calls, no network, no keys.
"""

import asyncio
import json

import pytest

from backend.dialogues.openclaw_identity import (
    IDENTITY_LADDER,
    STAGE_NAMES,
    VERSION_GATES,
    AgentIdentityProfile,
    advance_stage,
    build_identity_profile,
    evaluate_gate,
    next_gate_for,
    record_promotion,
    render_soul_card,
    GUIDING_SENTENCE,
)


# --------------------------------------------------------------------------- #
# Trace builders (shape matches trace_capture.build_session_trace)
# --------------------------------------------------------------------------- #

def _trace(sid, winners, *, drafters=("seat_a", "seat_b"), ratified=True):
    """winners: dict section_name -> winning provider_id."""
    moves = [{"move_id": f"m_{sid}_{p}", "phase": "synthesis",
              "role": "synthesizer", "confidence": 0.7, "provider_id": p}
             for p in drafters]
    sections = [{"section_name": name,
                 "source_draft_id": f"draft_m_{sid}_{winner}" if winner else ""}
                for name, winner in winners.items()]
    return {
        "session_id": sid,
        "question": "q",
        "moves": moves,
        "assembly": {"sections": sections},
        "ratification": {"ratified": ratified,
                         "ratification_status": "ratified" if ratified
                         else "repair_required"},
    }


# --------------------------------------------------------------------------- #
# Profile building (mechanical evidence)
# --------------------------------------------------------------------------- #

def test_role_strengths_from_assembly_wins():
    traces = [
        _trace("s1", {"core_answer": "seat_a", "blind_spots": "seat_a",
                      "final_verdict": "seat_b"}),
        _trace("s2", {"core_answer": "seat_b", "blind_spots": "seat_a",
                      "final_verdict": "seat_b"}),
    ]
    p = build_identity_profile("seat_a", traces)
    assert p.section_wins == {"blind_spots": 2, "core_answer": 1}
    assert p.section_opportunities == {"blind_spots": 2, "core_answer": 2,
                                       "final_verdict": 2}
    assert p.role_strengths["blind_spots"] == 1.0
    assert p.role_strengths["core_answer"] == 0.5
    assert p.role_strengths["final_verdict"] == 0.0
    assert p.sessions_analyzed == 2 and p.ratified_sessions == 2


def test_absent_agent_has_zero_evidence():
    p = build_identity_profile("ghost", [_trace("s1", {"core_answer": "seat_a"})])
    assert p.sessions_analyzed == 0
    assert p.role_strengths == {} and p.section_opportunities == {}


def test_unresolved_sections_are_no_contest():
    p = build_identity_profile(
        "seat_a", [_trace("s1", {"core_answer": "seat_a", "nuance": ""})])
    assert "nuance" not in p.section_opportunities


def test_missing_assembly_contributes_nothing():
    t = _trace("s1", {"core_answer": "seat_a"}, ratified=False)
    t["assembly"] = None
    p = build_identity_profile("seat_a", [t])
    assert p.sessions_analyzed == 1 and p.ratified_sessions == 0
    assert p.section_opportunities == {}


def test_profile_record_is_json_ready():
    p = build_identity_profile(
        "seat_a", [_trace("s1", {"core_answer": "seat_a"})],
        known_failures=("over-explains exact-output tasks",),
        stable_lessons=("LESSON-0001", "LESSON-0003"))
    record = json.loads(json.dumps(p.to_record()))
    assert record["agent_id"] == "seat_a"
    assert record["identity_version"] == "v0.1"
    assert record["promotion_status"] == "base_agent"
    assert record["stable_lessons"] == ["LESSON-0001", "LESSON-0003"]
    assert record["next_gate"] == "gate_v0_1_to_v0_2"


# --------------------------------------------------------------------------- #
# Ladder + gates
# --------------------------------------------------------------------------- #

def test_ladder_has_eight_earned_stages():
    assert len(IDENTITY_LADDER) == 8
    assert STAGE_NAMES[0] == "base_agent"
    assert STAGE_NAMES[2] == "shadow_apprentice"
    assert STAGE_NAMES[7] == "master_branch_researcher"


def test_gate_chain_is_connected():
    version = "v0.1"
    seen = []
    while (gate := next_gate_for(version)) is not None:
        seen.append(gate.gate_id)
        version = gate.to_version
    assert version == "v1.0"
    assert len(seen) == len(VERSION_GATES) == 5


def test_gate_passes_on_sufficient_evidence():
    gate = next_gate_for("v0.1")
    result = evaluate_gate(gate, {"exact_output_failures_delta": -2})
    assert result.passed is True
    assert result.evidence_used == {"exact_output_failures_delta": -2.0}


def test_gate_fails_without_evidence():
    gate = next_gate_for("v0.1")
    result = evaluate_gate(gate, {})
    assert result.passed is False
    assert "missing evidence" in result.reasons[0]


def test_gate_fails_on_wrong_direction():
    gate = next_gate_for("v0.1")
    assert evaluate_gate(gate, {"exact_output_failures_delta": 0}).passed is False
    assert evaluate_gate(
        gate, {"exact_output_failures_delta": "not a number"}).passed is False


# --------------------------------------------------------------------------- #
# Promotion: system verifies, a human approves
# --------------------------------------------------------------------------- #

def _base_profile():
    return build_identity_profile(
        "seat_a", [_trace("s1", {"core_answer": "seat_a"})])


def test_promotion_happy_path_is_append_only():
    p = _base_profile()
    gate = next_gate_for("v0.1")
    result = evaluate_gate(gate, {"exact_output_failures_delta": -3})
    p2 = record_promotion(p, result, approved_by="operator",
                          approved_on="2026-07-09")
    assert p2.identity_version == "v0.2"
    assert p2.next_gate == "gate_v0_2_to_v0_3"
    assert len(p2.version_history) == 1
    entry = p2.version_history[0]
    assert entry["approved_by"] == "operator"
    assert entry["evidence"] == {"exact_output_failures_delta": -3.0}
    assert p.identity_version == "v0.1"          # original untouched


def test_no_promotion_on_failing_gate():
    p = _base_profile()
    gate = next_gate_for("v0.1")
    failing = evaluate_gate(gate, {})
    with pytest.raises(ValueError):
        record_promotion(p, failing, approved_by="operator")


def test_no_unnamed_and_no_self_approval():
    p = _base_profile()
    gate = next_gate_for("v0.1")
    passing = evaluate_gate(gate, {"exact_output_failures_delta": -1})
    with pytest.raises(ValueError):
        record_promotion(p, passing, approved_by="   ")
    with pytest.raises(ValueError):
        record_promotion(p, passing, approved_by="seat_a")   # the agent itself


def test_gate_must_match_current_version():
    p = _base_profile()                                       # at v0.1
    later = next_gate_for("v0.2")
    passing = evaluate_gate(later, {"unsupported_claim_failures_delta": -1})
    with pytest.raises(ValueError):
        record_promotion(p, passing, approved_by="operator")


def test_full_chain_walk_to_v1_0():
    rigged = {
        "exact_output_failures_delta": -1,
        "unsupported_claim_failures_delta": -2,
        "shadow_blind_spots_wins": 5,
        "prompt_patches_passed_ab": 2,
        "master_branch_proposals_verified": 1,
    }
    p = _base_profile()
    while p.next_gate is not None:
        gate = next_gate_for(p.identity_version)
        p = record_promotion(p, evaluate_gate(gate, rigged),
                             approved_by="operator")
    assert p.identity_version == "v1.0"
    assert len(p.version_history) == 5


def test_stage_advances_one_rung_only():
    p = _base_profile()
    p2 = advance_stage(p, "memory_aware", approved_by="operator")
    assert p2.promotion_status == "memory_aware"
    with pytest.raises(ValueError):
        advance_stage(p, "shadow_apprentice", approved_by="operator")  # skip
    with pytest.raises(ValueError):
        advance_stage(p2, "shadow_apprentice", approved_by="seat_a")   # self
    with pytest.raises(ValueError):
        advance_stage(p2, "archmage", approved_by="operator")          # unknown


# --------------------------------------------------------------------------- #
# Soul Card: descriptive, not authority
# --------------------------------------------------------------------------- #

def test_soul_card_content():
    p = build_identity_profile(
        "seat_a",
        [_trace("s1", {"core_answer": "seat_a", "blind_spots": "seat_a",
                       "final_verdict": "seat_b"}),
         _trace("s2", {"core_answer": "seat_b", "blind_spots": "seat_a",
                       "final_verdict": "seat_b"})],
        known_failures=("over-explains exact-output tasks",),
        stable_lessons=("LESSON-0001",))
    card = render_soul_card(p)
    assert "descriptive, not authority" in card
    assert GUIDING_SENTENCE in card
    assert "Best role: blind_spots" in card
    assert "Weak role: final_verdict" in card
    assert "over-explains exact-output tasks" in card
    assert "LESSON-0001" in card
    assert "gate_v0_1_to_v0_2" in card


def test_soul_card_leaks_nothing():
    card = render_soul_card(_base_profile())
    for forbidden in ("score_breakdown", "scorecard", "api_key", "sk-ant-",
                      "Bearer ", "leaderboard"):
        assert forbidden not in card


def test_soul_card_with_no_evidence():
    card = render_soul_card(AgentIdentityProfile(agent_id="new_seat"))
    assert "insufficient evidence" in card


# --------------------------------------------------------------------------- #
# Runtime isolation: identity grants no runtime power
# --------------------------------------------------------------------------- #

def test_ced_core_never_imports_identity():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "backend" / "dialogues"
    for name in ("ced.py", "live_providers.py", "provider_registry.py",
                 "models.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "openclaw_identity" not in source, (
            f"{name} must not import the identity layer - identity is "
            "descriptive, never runtime authority")


# --------------------------------------------------------------------------- #
# Composes with Goal 5 traces from a real mock council
# --------------------------------------------------------------------------- #

def test_profile_from_real_mock_traces():
    from backend.dialogues.live_providers import build_council
    from backend.dialogues.models import ShadowScoringMode
    from backend.dialogues.openclaw_memory import TraceCapturer

    capturer = TraceCapturer()
    ced, _ = build_council(council_size=2,
                           shadow_scoring_mode=ShadowScoringMode.OFF,
                           trace_capturer=capturer)
    asyncio.run(ced.run_registry_session("identity q1", session_id="id_1"))
    asyncio.run(ced.run_registry_session("identity q2", session_id="id_2"))
    p = build_identity_profile("mock_seat0", capturer.traces)
    assert p.sessions_analyzed == 2
    assert p.section_opportunities                    # sections were contested
    total_wins = sum(p.section_wins.values())
    total_opps = sum(p.section_opportunities.values())
    assert 0 <= total_wins <= total_opps
    # Deterministic: same traces -> identical profile.
    assert build_identity_profile("mock_seat0", capturer.traces) == p

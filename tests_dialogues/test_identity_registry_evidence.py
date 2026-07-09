"""
Identity registry + instrument-fed gate evidence tests (Goal 13.1).

Verifies:
  - profile persistence round-trips exactly (including promotion history)
  - the registry is storage only (filesystem-safe ids, sorted, deterministic)
  - trace-window failure deltas come from the REAL Goal 6 detectors
  - metrics no instrument can compute stay ABSENT (their gates fail honestly)
  - shadow/arena evidence extraction
  - the full pipeline composes: traces -> evidence -> evaluate_gate ->
    record_promotion -> save -> load

No provider calls, no network, no keys.
"""

import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    build_identity_profile,
    collect_gate_evidence,
    evaluate_gate,
    evidence_from_arena,
    evidence_from_shadow_profile,
    evidence_from_trace_windows,
    from_record,
    next_gate_for,
    record_promotion,
)


# --------------------------------------------------------------------------- #
# Trace builders (shape matches trace_capture.build_session_trace)
# --------------------------------------------------------------------------- #

def _healthy_trace(sid, winners=None):
    winners = winners or {"core_answer": "seat_a", "blind_spots": "seat_a"}
    moves = [{"move_id": f"m_{sid}_{p}", "phase": ph, "role": "r",
              "confidence": 0.7, "provider_id": p}
             for p in ("seat_a", "seat_b")
             for ph in ("opening", "initial_response", "elenchus",
                        "reflection", "reconstruction", "synthesis")]
    sections = [{"section_name": n, "source_draft_id": f"draft_m_{sid}_{w}"}
                for n, w in winners.items()]
    return {"session_id": sid, "question": "q", "moves": moves,
            "assembly": {"sections": sections},
            "ratification": {"ratified": True,
                             "ratification_status": "ratified"}}


def _blocked_trace(sid):
    """A session that starves phases -> exact_output failure observations."""
    return {"session_id": sid, "question": "q",
            "moves": [{"move_id": f"m_{sid}", "phase": "opening", "role": "r",
                       "confidence": 0.5, "provider_id": "seat_a"}],
            "assembly": None,
            "ratification": {"ratified": False,
                             "ratification_status": "not_ratified"}}


# --------------------------------------------------------------------------- #
# from_record / registry round-trip
# --------------------------------------------------------------------------- #

def _promoted_profile():
    p = build_identity_profile("seat_a", [_healthy_trace("s1")],
                               known_failures=("over-explains",),
                               stable_lessons=("LESSON-0001",))
    gate = next_gate_for("v0.1")
    result = evaluate_gate(gate, {"exact_output_failures_delta": -2})
    return record_promotion(p, result, approved_by="operator",
                            approved_on="2026-07-10")


def test_from_record_round_trips_exactly():
    p = _promoted_profile()
    assert from_record(p.to_record()) == p


def test_from_record_requires_agent_id():
    with pytest.raises(ValueError):
        from_record({"identity_version": "v0.2"})


def test_registry_save_load_round_trip(tmp_path):
    reg = IdentityRegistry(tmp_path / "identities")
    p = _promoted_profile()
    path = reg.save_profile(p)
    assert path.name == "seat_a.json"
    loaded = reg.load_profile("seat_a")
    assert loaded == p
    assert loaded.identity_version == "v0.2"
    assert loaded.version_history[0]["approved_by"] == "operator"


def test_registry_missing_agent_is_none(tmp_path):
    reg = IdentityRegistry(tmp_path)
    assert reg.load_profile("never_saved") is None


def test_registry_rejects_unsafe_agent_ids(tmp_path):
    reg = IdentityRegistry(tmp_path)
    with pytest.raises(ValueError):
        reg.save_profile(AgentIdentityProfile(agent_id="../evil"))
    with pytest.raises(ValueError):
        reg.load_profile("a/b")


def test_registry_all_profiles_sorted(tmp_path):
    reg = IdentityRegistry(tmp_path)
    for aid in ("zeta", "alpha", "mid"):
        reg.save_profile(AgentIdentityProfile(agent_id=aid))
    assert [p.agent_id for p in reg.all_profiles()] == ["alpha", "mid", "zeta"]
    assert IdentityRegistry(tmp_path / "nowhere").all_profiles() == []


def test_registry_file_is_readable_json(tmp_path):
    reg = IdentityRegistry(tmp_path)
    path = reg.save_profile(_promoted_profile())
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["agent_id"] == "seat_a"
    for forbidden in ("api_key", "sk-ant-", "Bearer "):
        assert forbidden not in path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Instrument-fed evidence
# --------------------------------------------------------------------------- #

def test_trace_window_delta_reflects_reduction():
    before = [_blocked_trace("b1"), _blocked_trace("b2")]
    after = [_healthy_trace("a1"), _healthy_trace("a2")]
    evidence = evidence_from_trace_windows(before, after)
    # Blocked sessions starve phases -> exact_output observations BEFORE,
    # none AFTER -> negative delta (failures went down).
    assert evidence["exact_output_failures_delta"] < 0
    assert evidence["synthesis_quality_failures_delta"] < 0


def test_empty_window_emits_nothing():
    assert evidence_from_trace_windows([], [_healthy_trace("a1")]) == {}
    assert evidence_from_trace_windows([_blocked_trace("b1")], []) == {}


def test_unmeasurable_metric_stays_absent_and_gate_fails():
    evidence = evidence_from_trace_windows(
        [_blocked_trace("b1")], [_healthy_trace("a1")])
    # No instrument observes unsupported claims from traces alone (by design).
    assert "unsupported_claim_failures_delta" not in evidence
    gate = next_gate_for("v0.2")
    assert evaluate_gate(gate, evidence).passed is False


def test_shadow_profile_evidence():
    shadow = build_identity_profile(
        "seat_a",
        [_healthy_trace(f"sh{i}", {"blind_spots": "seat_a"}) for i in range(4)])
    evidence = evidence_from_shadow_profile(shadow)
    assert evidence["shadow_blind_spots_wins"] == 4
    assert evidence["shadow_sessions_analyzed"] == 4
    assert evaluate_gate(next_gate_for("v0.3"), evidence).passed is True


def test_arena_evidence_is_informational():
    report = {"win_rate": 0.75, "decided": 4, "promote": True}
    evidence = evidence_from_arena(report)
    assert evidence == {"arena_win_rate": 0.75, "arena_decided": 4,
                        "arena_promote_recommended": 1}


def test_collect_merges_disjoint_sources():
    shadow = build_identity_profile(
        "seat_a", [_healthy_trace("sh1", {"blind_spots": "seat_a"})])
    evidence = collect_gate_evidence(
        traces_before=[_blocked_trace("b1")],
        traces_after=[_healthy_trace("a1")],
        shadow_profile=shadow,
        arena_report={"win_rate": 0.6, "decided": 5, "promote": True},
    )
    assert "exact_output_failures_delta" in evidence
    assert "shadow_blind_spots_wins" in evidence
    assert "arena_win_rate" in evidence
    assert collect_gate_evidence() == {}


# --------------------------------------------------------------------------- #
# The full pipeline composes
# --------------------------------------------------------------------------- #

def test_end_to_end_traces_to_promotion_to_disk(tmp_path):
    # 1. Evidence from real instruments (failure deltas via Goal 6 detectors).
    evidence = collect_gate_evidence(
        traces_before=[_blocked_trace("b1"), _blocked_trace("b2")],
        traces_after=[_healthy_trace("a1"), _healthy_trace("a2")],
    )
    # 2. Profile from traces; gate evaluated on instrument-fed evidence.
    profile = build_identity_profile("seat_a", [_healthy_trace("a1")])
    gate = next_gate_for(profile.identity_version)
    result = evaluate_gate(gate, evidence)
    assert result.passed is True
    # 3. Human-approved promotion, persisted, reloaded intact.
    promoted = record_promotion(profile, result, approved_by="operator",
                                approved_on="2026-07-10")
    reg = IdentityRegistry(tmp_path)
    reg.save_profile(promoted)
    loaded = reg.load_profile("seat_a")
    assert loaded.identity_version == "v0.2"
    assert loaded.version_history[0]["evidence"][
        "exact_output_failures_delta"] < 0

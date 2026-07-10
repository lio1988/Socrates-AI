"""Integrity tests for atomic, append-only Agent Identity persistence."""

import dataclasses
import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    evaluate_gate,
    next_gate_for,
    record_promotion,
)


def _profile(**updates):
    base = AgentIdentityProfile(
        agent_id="local_apprentice_001",
        identity_version="v0.1",
        promotion_status="base_agent",
        next_gate="gate_v0_1_to_v0_2",
    )
    return dataclasses.replace(base, **updates)


def test_initial_save_round_trips_and_leaves_no_temp_files(tmp_path):
    registry = IdentityRegistry(tmp_path)
    profile = _profile(role_strengths={"blind_spots": 0.5})

    path = registry.save_profile(profile)

    assert path.exists()
    assert registry.load_profile(profile.agent_id) == profile
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_descriptive_evidence_can_be_recomputed_without_history_change(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile(
        role_strengths={"blind_spots": 0.5},
        sessions_analyzed=2,
    )
    registry.save_profile(original)

    refreshed = dataclasses.replace(
        original,
        role_strengths={"blind_spots": 0.75},
        sessions_analyzed=4,
        ratified_sessions=3,
    )
    registry.save_profile(refreshed)

    assert registry.load_profile(original.agent_id) == refreshed


def test_history_truncation_or_rewrite_is_refused(tmp_path):
    registry = IdentityRegistry(tmp_path)
    gate = next_gate_for("v0.1")
    promoted = record_promotion(
        _profile(),
        evaluate_gate(gate, {"exact_output_failures_delta": -1}),
        approved_by="operator",
        approval_reference="review/1",
    )
    registry.save_profile(promoted)

    truncated = dataclasses.replace(promoted, version_history=())
    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(truncated)

    rewritten_entry = dict(promoted.version_history[0])
    rewritten_entry["approved_by"] = "someone_else"
    rewritten = dataclasses.replace(
        promoted,
        version_history=(rewritten_entry,),
    )
    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(rewritten)


def test_earned_version_cannot_change_without_history_transition(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)

    forged = dataclasses.replace(
        original,
        identity_version="v0.2",
        next_gate="gate_v0_2_to_v0_3",
    )
    with pytest.raises(ValueError, match="without a matching"):
        registry.save_profile(forged)


def test_legitimate_promotion_appends_and_persists(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)

    gate = next_gate_for("v0.1")
    promoted = record_promotion(
        original,
        evaluate_gate(gate, {"exact_output_failures_delta": -2}),
        approved_by="operator",
        approved_on="2026-07-10",
        approval_reference="packet/identity-001",
    )
    registry.save_profile(promoted)

    loaded = registry.load_profile(original.agent_id)
    assert loaded == promoted
    assert loaded.identity_version == "v0.2"
    assert len(loaded.version_history) == 1
    assert loaded.version_history[0]["approval_reference"] == \
        "packet/identity-001"


def test_corrupt_profile_is_never_silently_ignored(tmp_path):
    corrupt = tmp_path / "broken_agent.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    registry = IdentityRegistry(tmp_path)

    with pytest.raises(ValueError, match="corrupt"):
        registry.load_profile("broken_agent")
    with pytest.raises(ValueError, match="corrupt"):
        registry.all_profiles()


def test_saved_json_is_human_readable_and_deterministic(tmp_path):
    registry = IdentityRegistry(tmp_path)
    profile = _profile(
        known_failures=("failure-b", "failure-a"),
        role_strengths={"nuance": 0.4, "blind_spots": 0.8},
    )

    path = registry.save_profile(profile)
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)

    assert raw.endswith("\n")
    assert parsed == profile.to_record()
    assert raw.index('"agent_id"') < raw.index('"identity_version"')

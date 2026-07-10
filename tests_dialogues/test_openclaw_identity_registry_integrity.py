"""Integrity tests for strict, locked, fully replayed Identity persistence."""

import dataclasses
import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    evaluate_gate,
    evaluate_self_revision,
    from_record,
    next_gate_for,
    record_promotion,
)

AGENT = "local_apprentice_001"


def _profile(**updates):
    base = AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.1",
        promotion_status="base_agent",
        next_gate="gate_v0_1_to_v0_2",
    )
    return dataclasses.replace(base, **updates)


def _proposal(
    *,
    proposal_id="REV-001",
    target="identity",
    action="add_known_failure",
    value="rushes exact-output tasks",
    reference="evidence/rev-001",
):
    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=AGENT,
        proposed_by=AGENT,
        target=target,
        action=action,
        value=value,
        reason="Verified evidence supports this descriptive revision.",
        evidence_references=(reference,),
        risk="The evidence window may still be narrow.",
    )


def _manifest(proposal, *, verifier="evidence-harness"):
    reference = proposal.evidence_references[0]
    return {
        reference: {
            "verified": True,
            "agent_id": AGENT,
            "source": "test-instrument",
            "supports": [f"{proposal.target}:{proposal.action}"],
            "value": proposal.value,
            "verified_by": verifier,
            "verification_reference": f"verification/{proposal.proposal_id}",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }


def _apply(profile, proposal, *, stable_lessons=()):
    manifest = _manifest(proposal)
    evaluation = evaluate_self_revision(
        proposal,
        evidence_manifest=manifest,
        stable_lesson_ids=stable_lessons,
    )
    return approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        evidence_manifest=manifest,
        stable_lesson_ids=stable_lessons,
        approved_by="operator",
        approved_on="2026-07-10",
        approval_reference=f"review/{proposal.proposal_id}",
    )


def _promotion_entry(original):
    gate = next_gate_for("v0.1")
    return record_promotion(
        original,
        evaluate_gate(gate, {"exact_output_failures_delta": -1}),
        approved_by="operator",
        approved_on="2026-07-10",
        approval_reference="review/promotion-1",
    )


def test_initial_save_round_trips_and_leaves_no_temp_files(tmp_path):
    registry = IdentityRegistry(tmp_path)
    profile = _profile(
        role_strengths={"blind_spots": 0.5},
        section_wins={"blind_spots": 1},
        section_opportunities={"blind_spots": 2},
        sessions_analyzed=2,
        ratified_sessions=1,
    )
    path = registry.save_profile(profile)
    assert path.exists()
    assert registry.load_profile(profile.agent_id) == profile
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []
    assert list(tmp_path.glob("*.lock")) == []


def test_descriptive_evidence_can_be_recomputed_without_history_change(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile(
        role_strengths={"blind_spots": 0.5},
        section_wins={"blind_spots": 1},
        section_opportunities={"blind_spots": 2},
        sessions_analyzed=2,
        ratified_sessions=1,
    )
    registry.save_profile(original)
    refreshed = dataclasses.replace(
        original,
        role_strengths={"blind_spots": 0.75},
        section_wins={"blind_spots": 3},
        section_opportunities={"blind_spots": 4},
        sessions_analyzed=4,
        ratified_sessions=3,
    )
    registry.save_profile(refreshed)
    assert registry.load_profile(original.agent_id) == refreshed


def test_history_truncation_or_rewrite_is_refused(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    promoted = _promotion_entry(original)
    registry.save_profile(promoted)

    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(dataclasses.replace(promoted, version_history=()))

    rewritten_entry = dict(promoted.version_history[0])
    rewritten_entry["approved_by"] = "someone_else"
    with pytest.raises(ValueError, match="append-only"):
        registry.save_profile(dataclasses.replace(
            promoted, version_history=(rewritten_entry,)))


def test_new_profile_cannot_arrive_with_prefabricated_history(tmp_path):
    registry = IdentityRegistry(tmp_path)
    with pytest.raises(ValueError, match="must be saved before version"):
        registry.save_profile(_promotion_entry(_profile()))


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


def test_forged_noncanonical_version_jump_is_refused(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    canonical = dict(_promotion_entry(original).version_history[0])
    canonical["to_version"] = "v99.0"
    forged = dataclasses.replace(
        original,
        identity_version="v99.0",
        next_gate=None,
        version_history=(canonical,),
    )
    with pytest.raises(ValueError, match="canonical gate"):
        registry.save_profile(forged)


def test_forged_stage_skip_and_self_approval_are_refused(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    skipped = dataclasses.replace(
        original,
        promotion_status="shadow_apprentice",
        version_history=({
            "from_status": "base_agent",
            "to_status": "shadow_apprentice",
            "approved_by": "operator",
            "approved_on": "2026-07-10",
        },),
    )
    with pytest.raises(ValueError, match="one ladder rung"):
        registry.save_profile(skipped)

    self_approved = dataclasses.replace(
        original,
        promotion_status="memory_aware",
        version_history=({
            "from_status": "base_agent",
            "to_status": "memory_aware",
            "approved_by": AGENT,
            "approved_on": "2026-07-10",
        },),
    )
    with pytest.raises(ValueError, match="own identity transition"):
        registry.save_profile(self_approved)


def test_legitimate_promotion_appends_persists_and_revalidates(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    promoted = _promotion_entry(original)
    registry.save_profile(promoted)
    loaded = registry.load_profile(AGENT)
    assert loaded == promoted
    assert loaded.identity_version == "v0.2"
    assert loaded.version_history[0]["approval_reference"] == \
        "review/promotion-1"


def test_load_rejects_tampered_stored_version_evidence_and_hidden_fields(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    path = registry.save_profile(_promotion_entry(original))

    record = json.loads(path.read_text(encoding="utf-8"))
    record["version_history"][0]["evidence"][
        "exact_output_failures_delta"] = 0
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load_profile(AGENT)

    path = tmp_path / f"{AGENT}.json"
    path.write_text(json.dumps(_promotion_entry(original).to_record()),
                    encoding="utf-8")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["version_history"][0]["authority"] = "grant"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load_profile(AGENT)


def test_load_rejects_tampered_stored_revision_provenance_and_effect(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    revised = _apply(original, _proposal())
    path = registry.save_profile(revised)

    record = json.loads(path.read_text(encoding="utf-8"))
    record["revision_history"][0]["evidence_verifiers"] = [AGENT]
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load_profile(AGENT)

    path.write_text(json.dumps(revised.to_record()), encoding="utf-8")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["known_failures"] = []
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load_profile(AGENT)


def test_multiple_legitimate_revisions_reconstruct_from_final_state(tmp_path):
    registry = IdentityRegistry(tmp_path)
    original = _profile()
    registry.save_profile(original)
    first = _apply(original, _proposal())
    registry.save_profile(first)
    principle = "State uncertainty before asserting a final verdict."
    second = _apply(first, _proposal(
        proposal_id="REV-002",
        target="soul",
        action="add_principle",
        value=principle,
        reference="evidence/rev-002",
    ))
    registry.save_profile(second)
    loaded = registry.load_profile(AGENT)
    assert loaded == second
    assert loaded.known_failures == ("rushes exact-output tasks",)
    assert loaded.soul_principles == (principle,)
    assert len(loaded.revision_history) == 2


def test_strict_schema_types_counts_and_unknown_fields_are_refused(tmp_path):
    registry = IdentityRegistry(tmp_path)
    profile = _profile()
    path = registry.save_profile(profile)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["authority"] = "grant"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load_profile(AGENT)

    with pytest.raises(ValueError, match="must be a sequence"):
        from_record({"agent_id": "a", "known_failures": "not-a-list"})
    with pytest.raises(ValueError, match="wins exceed opportunities"):
        from_record({
            "agent_id": "a",
            "section_wins": {"nuance": 2},
            "section_opportunities": {"nuance": 1},
        })
    with pytest.raises(ValueError, match="does not match counts"):
        from_record({
            "agent_id": "a",
            "role_strengths": {"nuance": 0.9},
            "section_wins": {"nuance": 1},
            "section_opportunities": {"nuance": 2},
        })


def test_secret_shaped_identity_data_is_refused_before_write(tmp_path):
    registry = IdentityRegistry(tmp_path)
    with pytest.raises(ValueError, match="secret-shaped"):
        registry.save_profile(_profile(
            soul_principles=("Bearer abcdefgh12345678",)))
    assert list(tmp_path.glob("*.json")) == []


def test_exclusive_lock_refuses_concurrent_save(tmp_path):
    registry = IdentityRegistry(tmp_path)
    profile = _profile()
    path = tmp_path / f"{AGENT}.json"
    lock = path.with_suffix(path.suffix + ".lock")
    tmp_path.mkdir(parents=True, exist_ok=True)
    lock.write_text("other-process", encoding="utf-8")
    with pytest.raises(ValueError, match="locked by another update"):
        registry.save_profile(profile)


def test_unsafe_or_overlong_agent_ids_are_refused(tmp_path):
    registry = IdentityRegistry(tmp_path)
    with pytest.raises(ValueError, match="filesystem-safe"):
        registry.save_profile(AgentIdentityProfile(agent_id="../evil"))
    with pytest.raises(ValueError, match="filesystem-safe"):
        registry.save_profile(AgentIdentityProfile(agent_id="a" * 129))


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
        section_wins={"nuance": 2, "blind_spots": 4},
        section_opportunities={"nuance": 5, "blind_spots": 5},
        sessions_analyzed=5,
        ratified_sessions=4,
    )
    path = registry.save_profile(profile)
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw) == profile.to_record()
    assert raw.index('"agent_id"') < raw.index('"identity_version"')

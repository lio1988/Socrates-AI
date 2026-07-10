"""Tests separating governed identity state from refreshable observations."""

import dataclasses

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    approve_and_apply_self_revision,
    build_self_review_snapshot,
    evaluate_self_revision,
    governed_profile_fingerprint,
    observational_profile_fingerprint,
    profile_fingerprint,
)

AGENT = "agent_alpha"
VALUE = "rushes exact-output tasks"
REFERENCE = "trace/failure-1"
OUTCOME = "post-window/confirmation-1"


def _profile():
    return AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
        role_strengths={"blind_spots": 0.5},
        section_wins={"blind_spots": 1},
        section_opportunities={"blind_spots": 2},
        sessions_analyzed=2,
        ratified_sessions=2,
        stable_lessons=("LESSON-0001",),
    )


def _proposal():
    return SelfRevisionProposal(
        proposal_id="REV-FINGERPRINT-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=VALUE,
        reason="Repeated attributed evidence shows the failure.",
        evidence_references=(REFERENCE,),
        risk="The attribution window may still be narrow.",
    )


def _manifest(proposal):
    return {
        REFERENCE: {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-attribution",
            "supports": ["identity:add_known_failure"],
            "value": proposal.value,
            "verified_by": "evidence-harness",
            "verification_reference": "verification/failure-1",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }


def test_observation_refresh_changes_full_snapshot_not_governed_identity():
    original = _profile()
    refreshed = dataclasses.replace(
        original,
        role_strengths={"blind_spots": 0.75},
        section_wins={"blind_spots": 3},
        section_opportunities={"blind_spots": 4},
        sessions_analyzed=4,
        ratified_sessions=3,
    )
    proposal = _proposal()
    manifest = _manifest(proposal)
    first = build_self_review_snapshot(original, evidence_manifest=manifest)
    second = build_self_review_snapshot(refreshed, evidence_manifest=manifest)

    assert profile_fingerprint(original) == profile_fingerprint(refreshed)
    assert governed_profile_fingerprint(original) == \
        governed_profile_fingerprint(refreshed)
    assert observational_profile_fingerprint(original) != \
        observational_profile_fingerprint(refreshed)
    assert first.snapshot_fingerprint != second.snapshot_fingerprint
    assert first.profile_fingerprint == first.governed_profile_fingerprint


def test_governed_change_changes_canonical_profile_fingerprint():
    original = _profile()
    changed = dataclasses.replace(
        original, soul_principles=("State uncertainty honestly.",))
    assert profile_fingerprint(original) != profile_fingerprint(changed)


def test_probation_confirmation_allows_new_metrics_but_not_governed_drift(
        tmp_path):
    profile = _profile()
    proposal = _proposal()
    manifest = _manifest(proposal)
    snapshot = build_self_review_snapshot(profile, evidence_manifest=manifest)
    registry = SelfRevisionRegistry(tmp_path)
    registry.submit(proposal, snapshot=snapshot)
    evaluation = registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        decision="approved",
        decided_by="operator",
        decision_reference="review/approved",
    )
    applied = approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        approved_by="operator",
        approval_reference="review/approved",
    )
    registry.record_application(
        AGENT,
        proposal.proposal_id,
        previous_profile=profile,
        updated_profile=applied,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        applied_by="operator",
        application_reference="identity/revision-1",
    )

    refreshed = dataclasses.replace(
        applied,
        role_strengths={"blind_spots": 0.75},
        section_wins={"blind_spots": 3},
        section_opportunities={"blind_spots": 4},
        sessions_analyzed=4,
        ratified_sessions=3,
    )
    outcome_manifest = dict(manifest)
    outcome_manifest[OUTCOME] = {
        "verified": True,
        "agent_id": AGENT,
        "source": "post-change-harness",
        "supports": ["identity:add_known_failure"],
        "value": VALUE,
        "verified_by": "post-change-verifier",
        "verification_reference": "verification/post-window-1",
        "observed_on": "2026-07-10",
        "outcomes": ["confirmed"],
    }
    registry.record_outcome(
        AGENT,
        proposal.proposal_id,
        current_profile=refreshed,
        outcome="confirmed",
        evidence_manifest=outcome_manifest,
        recorded_by="post-change-reviewer",
        evidence_reference=OUTCOME,
    )
    assert registry.load(AGENT, proposal.proposal_id)["status"] == "confirmed"


def test_probation_still_rejects_governed_drift(tmp_path):
    profile = _profile()
    proposal = _proposal()
    manifest = _manifest(proposal)
    snapshot = build_self_review_snapshot(profile, evidence_manifest=manifest)
    registry = SelfRevisionRegistry(tmp_path)
    registry.submit(proposal, snapshot=snapshot)
    evaluation = registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        decision="approved",
        decided_by="operator",
        decision_reference="review/approved",
    )
    applied = approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        approved_by="operator",
        approval_reference="review/approved",
    )
    registry.record_application(
        AGENT,
        proposal.proposal_id,
        previous_profile=profile,
        updated_profile=applied,
        evidence_manifest=manifest,
        stable_lesson_ids=("LESSON-0001",),
        applied_by="operator",
        application_reference="identity/revision-1",
    )
    drifted = dataclasses.replace(
        applied, soul_principles=("Unrelated governed change",))
    outcome_manifest = dict(manifest)
    outcome_manifest[OUTCOME] = {
        "verified": True,
        "agent_id": AGENT,
        "source": "post-change-harness",
        "supports": ["identity:add_known_failure"],
        "value": VALUE,
        "verified_by": "post-change-verifier",
        "verification_reference": "verification/post-window-1",
        "observed_on": "2026-07-10",
        "outcomes": ["confirmed"],
    }
    with pytest.raises(ValueError, match="identity state changed"):
        registry.record_outcome(
            AGENT,
            proposal.proposal_id,
            current_profile=drifted,
            outcome="confirmed",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-reviewer",
            evidence_reference=OUTCOME,
        )

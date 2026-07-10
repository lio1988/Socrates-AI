"""Regression tests for committed journal verification after later outcomes."""

import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    SelfRevisionTransactionCoordinator,
    build_self_review_snapshot,
)

AGENT = "agent_alpha"
PROPOSAL_ID = "REV-TERMINAL-1"
REFERENCE = "evidence/terminal-1"
OUTCOME = "evidence/terminal-confirmed-1"
VALUE = "rushes exact-output tasks"


def _setup(tmp_path):
    identity = IdentityRegistry(tmp_path / "identity")
    lifecycle = SelfRevisionRegistry(tmp_path / "lifecycle")
    coordinator = SelfRevisionTransactionCoordinator(
        identity, lifecycle, tmp_path / "transactions")
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposal = SelfRevisionProposal(
        proposal_id=PROPOSAL_ID,
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=VALUE,
        reason="Repeated attributed evidence shows this pattern.",
        evidence_references=(REFERENCE,),
        risk="The evidence window may still be narrow.",
    )
    manifest = {
        REFERENCE: {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-attribution",
            "supports": ["identity:add_known_failure"],
            "value": VALUE,
            "verified_by": "evidence-harness",
            "verification_reference": "verification/terminal-1",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }
    identity.save_profile(profile)
    lifecycle.submit(
        proposal,
        snapshot=build_self_review_snapshot(
            profile, evidence_manifest=manifest),
    )
    lifecycle.record_evaluation(
        AGENT,
        PROPOSAL_ID,
        current_profile=profile,
        evidence_manifest=manifest,
        evaluated_by="evidence-harness",
    )
    lifecycle.record_decision(
        AGENT,
        PROPOSAL_ID,
        current_profile=profile,
        evidence_manifest=manifest,
        decision="approved",
        decided_by="operator",
        decision_reference="review/terminal-1",
    )
    updated = coordinator.apply_approved(
        AGENT,
        PROPOSAL_ID,
        evidence_manifest=manifest,
        applied_by="operator",
        application_reference="identity/terminal-1",
    )
    return identity, lifecycle, coordinator, updated, manifest


def test_committed_recovery_remains_valid_after_confirmed_outcome(tmp_path):
    identity, lifecycle, coordinator, updated, manifest = _setup(tmp_path)
    outcome_manifest = dict(manifest)
    outcome_manifest[OUTCOME] = {
        "verified": True,
        "agent_id": AGENT,
        "source": "post-change-harness",
        "supports": ["identity:add_known_failure"],
        "value": VALUE,
        "verified_by": "post-change-verifier",
        "verification_reference": "verification/terminal-confirmed-1",
        "observed_on": "2026-07-10",
        "outcomes": ["confirmed"],
    }
    lifecycle.record_outcome(
        AGENT,
        PROPOSAL_ID,
        current_profile=updated,
        outcome="confirmed",
        evidence_manifest=outcome_manifest,
        recorded_by="post-change-reviewer",
        evidence_reference=OUTCOME,
    )

    assert lifecycle.load(AGENT, PROPOSAL_ID)["status"] == "confirmed"
    assert coordinator.recover(AGENT, PROPOSAL_ID) == identity.load_profile(AGENT)


def test_committed_recovery_detects_changed_original_application_hash(tmp_path):
    _, lifecycle, coordinator, _, _ = _setup(tmp_path)
    path = lifecycle.directory / AGENT / f"{PROPOSAL_ID}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    applied = next(
        event for event in record["events"]
        if event["event_type"] == "applied")
    applied["application_reference"] = "tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt|application hash"):
        coordinator.recover(AGENT, PROPOSAL_ID)

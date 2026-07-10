"""Admission-control tests for governed active self-revision proposals."""

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    SelfRevisionProposal,
    build_self_review_snapshot,
)
from backend.dialogues.openclaw_identity.revision_registry_governed import (
    MAX_ACTIVE_PROPOSALS_PER_AGENT,
    SelfRevisionRegistry,
)

AGENT = "agent_alpha"


def _proposal(index, *, action="add_known_failure", value=None):
    value = value or f"failure-{index}"
    return SelfRevisionProposal(
        proposal_id=f"REV-{index}",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action=action,
        value=value,
        reason="Verified evidence supports this descriptive proposal.",
        evidence_references=(f"evidence/{index}",),
        risk="The evidence window may still be narrow.",
    )


def _manifest(proposal):
    reference = proposal.evidence_references[0]
    return {
        reference: {
            "verified": True,
            "agent_id": AGENT,
            "source": f"instrument/{reference}",
            "supports": [f"{proposal.target}:{proposal.action}"],
            "value": proposal.value,
            "verified_by": "evidence-harness",
            "verification_reference": f"verification/{reference}",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }


def _submit(registry, profile, proposal):
    manifest = _manifest(proposal)
    return registry.submit(
        proposal,
        snapshot=build_self_review_snapshot(
            profile, evidence_manifest=manifest),
    )


def test_duplicate_active_target_action_value_is_refused(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile = AgentIdentityProfile(agent_id=AGENT)
    first = _proposal(1, value="same failure")
    second = _proposal(2, value="same failure")
    _submit(registry, profile, first)

    with pytest.raises(ValueError, match="same target/action/value"):
        _submit(registry, profile, second)
    assert registry.load(AGENT, first.proposal_id)["status"] == "submitted"
    assert registry.load(AGENT, second.proposal_id) is None


def test_different_values_remain_independently_reviewable_until_limit(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile = AgentIdentityProfile(agent_id=AGENT)
    for index in range(MAX_ACTIVE_PROPOSALS_PER_AGENT):
        _submit(registry, profile, _proposal(index))
    assert len(registry.all_records(AGENT)) == MAX_ACTIVE_PROPOSALS_PER_AGENT

    with pytest.raises(ValueError, match="active self-revision proposal limit"):
        _submit(
            registry,
            profile,
            _proposal(MAX_ACTIVE_PROPOSALS_PER_AGENT),
        )


def test_terminal_rejection_frees_active_capacity(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposals = []
    manifests = []
    for index in range(MAX_ACTIVE_PROPOSALS_PER_AGENT):
        proposal = _proposal(index)
        manifest = _manifest(proposal)
        registry.submit(
            proposal,
            snapshot=build_self_review_snapshot(
                profile, evidence_manifest=manifest),
        )
        proposals.append(proposal)
        manifests.append(manifest)

    first = proposals[0]
    failing = {
        first.evidence_references[0]: {
            **manifests[0][first.evidence_references[0]],
            "verified": False,
        }
    }
    registry.record_evaluation(
        AGENT,
        first.proposal_id,
        current_profile=profile,
        evidence_manifest=failing,
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        first.proposal_id,
        current_profile=profile,
        evidence_manifest=failing,
        decision="rejected",
        decided_by="operator",
        decision_reference="review/rejected-1",
    )
    assert registry.load(AGENT, first.proposal_id)["status"] == "rejected"

    replacement = _proposal(99)
    _submit(registry, profile, replacement)
    active = [
        record for record in registry.all_records(AGENT)
        if record["status"] != "rejected"
    ]
    assert len(active) == MAX_ACTIVE_PROPOSALS_PER_AGENT


def test_canonical_inverse_is_not_semantically_deduplicated_with_original(
        tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile = AgentIdentityProfile(
        agent_id=AGENT,
        known_failures=("failure-to-resolve",),
    )
    original = _proposal(1, action="add_known_failure",
                         value="failure-to-resolve")
    inverse = _proposal(2, action="resolve_known_failure",
                        value="failure-to-resolve")

    _submit(registry, profile, original)
    _submit(registry, profile, inverse)
    assert {record["proposal_id"] for record in registry.all_records(AGENT)} == {
        original.proposal_id,
        inverse.proposal_id,
    }

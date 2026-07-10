"""End-to-end tests for the single safe self-revision integration facade."""

import pytest

from backend.dialogues.openclaw_identity.governed_system import (
    GovernedSelfRevisionSystem,
)
from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    RevisionEvidenceRecord,
    SelfRevisionProposal,
)

AGENT = "agent_alpha"
REFERENCE = "attribution/facade-1"
VALUE = "rushes exact-output tasks"


def _evidence():
    return RevisionEvidenceRecord(
        reference=REFERENCE,
        agent_id=AGENT,
        source="TraceAttribution/facade-1",
        supports=("identity:add_known_failure",),
        value=VALUE,
        verified_by="evidence-harness",
        verification_reference="verification/facade-1",
        observed_on="2026-07-10",
    )


def _proposal():
    return SelfRevisionProposal(
        proposal_id="REV-FACADE-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=VALUE,
        reason="Repeated attributed evidence supports this revision.",
        evidence_references=(REFERENCE,),
        risk="The attribution window may still be narrow.",
    )


def _system(tmp_path):
    system = GovernedSelfRevisionSystem.from_root(tmp_path)
    system.identity_registry.save_profile(AgentIdentityProfile(agent_id=AGENT))
    system.register_evidence(_evidence())
    return system


def test_facade_builds_fresh_snapshot_from_bound_registries(tmp_path):
    system = _system(tmp_path)
    snapshot = system.snapshot(AGENT)
    assert snapshot.agent_id == AGENT
    assert [row.reference for row in snapshot.verified_evidence] == [REFERENCE]
    assert snapshot.pending_proposal_ids == ()

    system.submit(_proposal())
    refreshed = system.snapshot(AGENT)
    assert refreshed.pending_proposal_ids == ("REV-FACADE-1",)


def test_facade_end_to_end_never_accepts_caller_supplied_passed_flag(tmp_path):
    system = _system(tmp_path)
    proposal = _proposal()
    system.submit(proposal)
    result = system.evaluate(
        AGENT,
        proposal.proposal_id,
        evaluated_by="evidence-harness",
    )
    assert result.passed is True
    system.decide(
        AGENT,
        proposal.proposal_id,
        decision="approved",
        decided_by="operator",
        decision_reference="review/facade-1",
    )
    updated = system.apply_approved(
        AGENT,
        proposal.proposal_id,
        applied_by="operator",
        application_reference="identity/facade-1",
    )

    assert updated.known_failures == (VALUE,)
    assert system.profile(AGENT) == updated
    assert system.lifecycle_registry.load(
        AGENT, proposal.proposal_id)["status"] == "probationary"
    assert system.transaction_coordinator.load(
        AGENT, proposal.proposal_id)["state"] == "committed"


def test_facade_reloads_current_evidence_and_fails_on_missing_reference(tmp_path):
    system = GovernedSelfRevisionSystem.from_root(tmp_path)
    system.identity_registry.save_profile(AgentIdentityProfile(agent_id=AGENT))
    proposal = _proposal()
    with pytest.raises(ValueError, match="absent|missing"):
        system.submit(proposal)


def test_facade_preserves_actor_separation(tmp_path):
    system = _system(tmp_path)
    proposal = _proposal()
    system.submit(proposal)
    with pytest.raises(ValueError, match="cannot evaluate"):
        system.evaluate(
            AGENT,
            proposal.proposal_id,
            evaluated_by=AGENT,
        )

    system.evaluate(
        AGENT,
        proposal.proposal_id,
        evaluated_by="evidence-harness",
    )
    with pytest.raises(ValueError, match="different actors"):
        system.decide(
            AGENT,
            proposal.proposal_id,
            decision="approved",
            decided_by="evidence-harness",
            decision_reference="review/facade-1",
        )


def test_facade_reports_missing_profile_and_incomplete_transactions(tmp_path):
    system = GovernedSelfRevisionSystem.from_root(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        system.profile(AGENT)
    assert system.incomplete_transactions() == ()

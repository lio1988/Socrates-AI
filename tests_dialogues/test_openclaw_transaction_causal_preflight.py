"""Tests that causal-isolation refusal happens before transaction mutation."""

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    RevisionEvidenceRecord,
    SelfRevisionProposal,
)
from backend.dialogues.openclaw_identity.governed_system_transactional import (
    GovernedSelfRevisionSystem,
)

AGENT = "agent_alpha"
FAILURE = "rushes exact-output tasks"
PRINCIPLE = "State uncertainty honestly."


def _evidence(reference, *, target, action, value, supports=None):
    return RevisionEvidenceRecord(
        reference=reference,
        agent_id=AGENT,
        source=f"instrument/{reference}",
        supports=tuple(supports or (f"{target}:{action}",)),
        value=value,
        verified_by="evidence-harness",
        verification_reference=f"verification/{reference}",
        observed_on="2026-07-10",
    )


def _proposal(proposal_id, *, target, action, value, reference):
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


def _approve_and_apply(system, proposal):
    system.submit(proposal)
    system.evaluate(
        AGENT,
        proposal.proposal_id,
        evaluated_by="evidence-harness",
    )
    system.decide(
        AGENT,
        proposal.proposal_id,
        decision="approved",
        decided_by="operator",
        decision_reference=f"review/{proposal.proposal_id}",
    )
    return system.apply_approved(
        AGENT,
        proposal.proposal_id,
        applied_by="operator",
        application_reference=f"identity/{proposal.proposal_id}",
    )


def _system_with_original(tmp_path):
    system = GovernedSelfRevisionSystem.from_root(tmp_path)
    system.identity_registry.save_profile(AgentIdentityProfile(agent_id=AGENT))
    original = _proposal(
        "REV-ORIGINAL",
        target="identity",
        action="add_known_failure",
        value=FAILURE,
        reference="evidence/original",
    )
    system.register_evidence(_evidence(
        "evidence/original",
        target="identity",
        action="add_known_failure",
        value=FAILURE,
    ))
    applied = _approve_and_apply(system, original)
    return system, original, applied


def test_unrelated_second_application_refuses_before_identity_and_journal_write(
        tmp_path):
    system, _, applied = _system_with_original(tmp_path)
    unrelated = _proposal(
        "REV-UNRELATED",
        target="soul",
        action="add_principle",
        value=PRINCIPLE,
        reference="evidence/unrelated",
    )
    system.register_evidence(_evidence(
        "evidence/unrelated",
        target="soul",
        action="add_principle",
        value=PRINCIPLE,
    ))
    system.submit(unrelated)
    system.evaluate(
        AGENT, unrelated.proposal_id, evaluated_by="evidence-harness")
    system.decide(
        AGENT,
        unrelated.proposal_id,
        decision="approved",
        decided_by="operator",
        decision_reference="review/unrelated",
    )

    before = system.profile(AGENT)
    assert before == applied
    with pytest.raises(ValueError, match="exact canonical inverse"):
        system.apply_approved(
            AGENT,
            unrelated.proposal_id,
            applied_by="operator",
            application_reference="identity/unrelated",
        )

    assert system.profile(AGENT) == before
    assert system.transaction_coordinator.load(
        AGENT, unrelated.proposal_id) is None
    assert system.lifecycle_registry.load(
        AGENT, unrelated.proposal_id)["status"] == "approved"


def test_canonical_inverse_passes_preflight_and_uses_transaction(tmp_path):
    system, original, applied = _system_with_original(tmp_path)
    inverse = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/inverse",
    )
    system.register_evidence(_evidence(
        "evidence/inverse",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
    ))
    system.submit(inverse)
    system.evaluate(
        AGENT, inverse.proposal_id, evaluated_by="evidence-harness")
    system.decide(
        AGENT,
        inverse.proposal_id,
        decision="approved",
        decided_by="operator",
        decision_reference="review/inverse",
    )
    restored = system.apply_approved(
        AGENT,
        inverse.proposal_id,
        applied_by="operator",
        application_reference="identity/inverse",
    )

    assert applied.known_failures == (FAILURE,)
    assert restored.known_failures == ()
    assert system.transaction_coordinator.load(
        AGENT, inverse.proposal_id)["state"] == "committed"
    assert system.lifecycle_registry.pending_reversal_pairs(AGENT) == (
        (original.proposal_id, inverse.proposal_id),)

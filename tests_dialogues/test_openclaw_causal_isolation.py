"""End-to-end tests for causally isolated probation and verified rollback."""

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    build_self_review_snapshot,
)
from backend.dialogues.openclaw_identity.revision_registry_isolated import (
    SelfRevisionRegistry,
)

AGENT = "agent_alpha"
FAILURE = "rushes exact-output tasks"
PRINCIPLE = "State uncertainty honestly."


def _evidence(
    reference,
    *,
    action,
    value,
    outcomes=(),
    supports=None,
    verifier="evidence-harness",
):
    return {
        reference: {
            "verified": True,
            "agent_id": AGENT,
            "source": f"test-instrument/{reference}",
            "supports": list(supports or (action,)),
            "value": value,
            "verified_by": verifier,
            "verification_reference": f"verification/{reference}",
            "observed_on": "2026-07-10",
            "outcomes": list(outcomes),
        }
    }


def _proposal(
    proposal_id,
    *,
    target,
    action,
    value,
    reference,
):
    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=AGENT,
        proposed_by=AGENT,
        target=target,
        action=action,
        value=value,
        reason="The cited verified evidence supports this descriptive change.",
        evidence_references=(reference,),
        risk="The evidence window may still be too narrow.",
    )


def _approve(registry, profile, proposal, manifest, *, stable=()):
    registry.submit(
        proposal,
        snapshot=build_self_review_snapshot(
            profile, evidence_manifest=manifest),
    )
    evaluation = registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=stable,
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=stable,
        decision="approved",
        decided_by="operator",
        decision_reference=f"review/{proposal.proposal_id}",
    )
    return evaluation


def _updated(profile, proposal, manifest, evaluation, *, stable=()):
    return approve_and_apply_self_revision(
        profile,
        proposal,
        evaluation,
        evidence_manifest=manifest,
        stable_lesson_ids=stable,
        approved_by="operator",
        approval_reference=f"review/{proposal.proposal_id}",
    )


def _apply(registry, previous, updated, proposal, manifest, *, stable=()):
    registry.record_application(
        AGENT,
        proposal.proposal_id,
        previous_profile=previous,
        updated_profile=updated,
        evidence_manifest=manifest,
        stable_lesson_ids=stable,
        applied_by="operator",
        application_reference=f"identity/{proposal.proposal_id}",
    )


def _original_flow(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposal = _proposal(
        "REV-ORIGINAL",
        target="identity",
        action="add_known_failure",
        value=FAILURE,
        reference="evidence/original",
    )
    manifest = _evidence(
        "evidence/original",
        action="identity:add_known_failure",
        value=FAILURE,
    )
    evaluation = _approve(registry, profile, proposal, manifest)
    applied = _updated(profile, proposal, manifest, evaluation)
    _apply(registry, profile, applied, proposal, manifest)
    return registry, profile, proposal, manifest, applied


def _inverse_flow(registry, applied):
    inverse = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/inverse-proposal",
    )
    inverse_manifest = _evidence(
        "evidence/inverse-proposal",
        action="identity:resolve_known_failure",
        value=FAILURE,
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="resolution-harness",
    )
    evaluation = _approve(registry, applied, inverse, inverse_manifest)
    restored = _updated(applied, inverse, inverse_manifest, evaluation)
    _apply(registry, applied, restored, inverse, inverse_manifest)
    return inverse, inverse_manifest, restored


def _confirm_inverse(registry, inverse, inverse_manifest, restored):
    confirmation = _evidence(
        "evidence/inverse-confirmed",
        action="identity:resolve_known_failure",
        value=FAILURE,
        outcomes=("confirmed",),
        verifier="post-change-verifier",
    )
    manifest = dict(inverse_manifest)
    manifest.update(confirmation)
    registry.record_outcome(
        AGENT,
        inverse.proposal_id,
        current_profile=restored,
        outcome="confirmed",
        evidence_manifest=manifest,
        recorded_by="inverse-outcome-reviewer",
        evidence_reference="evidence/inverse-confirmed",
    )
    return manifest


def test_unrelated_second_probationary_revision_is_refused(tmp_path):
    registry, _, _, _, applied = _original_flow(tmp_path)
    second = _proposal(
        "REV-UNRELATED",
        target="soul",
        action="add_principle",
        value=PRINCIPLE,
        reference="evidence/unrelated",
    )
    second_manifest = _evidence(
        "evidence/unrelated",
        action="soul:add_principle",
        value=PRINCIPLE,
    )
    evaluation = _approve(registry, applied, second, second_manifest)
    updated = _updated(applied, second, second_manifest, evaluation)

    with pytest.raises(ValueError, match="only its exact canonical inverse"):
        _apply(registry, applied, updated, second, second_manifest)
    assert registry.load(AGENT, second.proposal_id)["status"] == "approved"


def test_original_cannot_be_reverted_before_inverse_is_applied(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    inverse = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/inverse-proposal",
    )
    inverse_manifest = _evidence(
        "evidence/inverse-proposal",
        action="identity:resolve_known_failure",
        value=FAILURE,
        outcomes=("reverted",),
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="post-change-verifier",
    )
    _approve(registry, applied, inverse, inverse_manifest)
    outcome_manifest = dict(original_manifest)
    outcome_manifest.update(inverse_manifest)

    with pytest.raises(ValueError, match="applied and confirmed"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=applied,
            outcome="reverted",
            evidence_manifest=outcome_manifest,
            recorded_by="rollback-reviewer",
            evidence_reference="evidence/inverse-proposal",
            linked_proposal_id=inverse.proposal_id,
        )


def test_applied_but_unconfirmed_inverse_cannot_close_original(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    inverse, inverse_manifest, restored = _inverse_flow(registry, applied)

    assert restored.known_failures == ()
    assert registry.pending_reversal_pairs(AGENT) == (
        (original.proposal_id, inverse.proposal_id),)

    rollback_evidence = _evidence(
        "evidence/original-reverted",
        action="identity:add_known_failure",
        value=FAILURE,
        outcomes=("reverted",),
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="rollback-verifier",
    )
    outcome_manifest = dict(original_manifest)
    outcome_manifest.update(inverse_manifest)
    outcome_manifest.update(rollback_evidence)
    with pytest.raises(ValueError, match="applied and confirmed"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=restored,
            outcome="reverted",
            evidence_manifest=outcome_manifest,
            recorded_by="rollback-reviewer",
            evidence_reference="evidence/original-reverted",
            linked_proposal_id=inverse.proposal_id,
        )


def test_confirmed_inverse_then_original_revert_completes_rollback(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    inverse, inverse_manifest, restored = _inverse_flow(registry, applied)
    confirmed_manifest = _confirm_inverse(
        registry, inverse, inverse_manifest, restored)

    assert registry.load(AGENT, inverse.proposal_id)["status"] == "confirmed"
    assert registry.pending_reversal_pairs(AGENT) == ()
    assert registry.ready_reversion_pairs(AGENT) == (
        (original.proposal_id, inverse.proposal_id),)

    rollback_evidence = _evidence(
        "evidence/original-reverted",
        action="identity:add_known_failure",
        value=FAILURE,
        outcomes=("reverted",),
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="rollback-verifier",
    )
    outcome_manifest = dict(original_manifest)
    outcome_manifest.update(confirmed_manifest)
    outcome_manifest.update(rollback_evidence)
    registry.record_outcome(
        AGENT,
        original.proposal_id,
        current_profile=restored,
        outcome="reverted",
        evidence_manifest=outcome_manifest,
        recorded_by="rollback-reviewer",
        evidence_reference="evidence/original-reverted",
        linked_proposal_id=inverse.proposal_id,
    )

    assert registry.load(AGENT, original.proposal_id)["status"] == "reverted"
    assert registry.load(AGENT, inverse.proposal_id)["status"] == "confirmed"
    assert registry.ready_reversion_pairs(AGENT) == ()


def test_original_cannot_be_confirmed_after_inverse_application(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    inverse, _, restored = _inverse_flow(registry, applied)

    confirmation = _evidence(
        "evidence/original-confirmed",
        action="identity:add_known_failure",
        value=FAILURE,
        outcomes=("confirmed",),
        verifier="post-change-verifier",
    )
    outcome_manifest = dict(original_manifest)
    outcome_manifest.update(confirmation)
    with pytest.raises(ValueError, match="changed before confirmation|inverse"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=restored,
            outcome="confirmed",
            evidence_manifest=outcome_manifest,
            recorded_by="original-outcome-reviewer",
            evidence_reference="evidence/original-confirmed",
        )
    assert registry.load(AGENT, inverse.proposal_id)["status"] == "probationary"


def test_third_probationary_application_is_always_refused(tmp_path):
    registry, _, original, _, applied = _original_flow(tmp_path)
    inverse, _, restored = _inverse_flow(registry, applied)

    third = _proposal(
        "REV-THIRD",
        target="soul",
        action="add_principle",
        value=PRINCIPLE,
        reference="evidence/third",
    )
    third_manifest = _evidence(
        "evidence/third",
        action="soul:add_principle",
        value=PRINCIPLE,
    )
    third_eval = _approve(registry, restored, third, third_manifest)
    third_updated = _updated(restored, third, third_manifest, third_eval)
    with pytest.raises(ValueError, match="multiple probationary revisions"):
        _apply(registry, restored, third_updated, third, third_manifest)

    records = registry.all_records(AGENT)
    assert len([
        record for record in records
        if record["status"] == "probationary"
    ]) == 2
    assert {original.proposal_id, inverse.proposal_id}.issubset({
        record["proposal_id"] for record in records
    })

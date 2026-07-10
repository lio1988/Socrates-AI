"""End-to-end tests for causally isolated probation and real rollback."""

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    build_self_review_snapshot,
    evaluate_self_revision,
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
            "supports": list(supports or (f"{action}",)),
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


def test_original_cannot_be_marked_reverted_before_inverse_is_applied(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    reversal = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/reversal",
    )
    reversal_manifest = _evidence(
        "evidence/reversal",
        action="identity:resolve_known_failure",
        value=FAILURE,
        outcomes=("reverted",),
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="post-change-verifier",
    )
    _approve(registry, applied, reversal, reversal_manifest)
    outcome_manifest = dict(original_manifest)
    outcome_manifest.update(reversal_manifest)

    with pytest.raises(ValueError, match="must be applied"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=applied,
            outcome="reverted",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-reviewer",
            evidence_reference="evidence/reversal",
            linked_proposal_id=reversal.proposal_id,
        )


def test_applied_inverse_creates_controlled_pair_then_real_revert(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    reversal = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/reversal",
    )
    reversal_manifest = _evidence(
        "evidence/reversal",
        action="identity:resolve_known_failure",
        value=FAILURE,
        outcomes=("reverted",),
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="post-change-verifier",
    )
    evaluation = _approve(registry, applied, reversal, reversal_manifest)
    restored = _updated(applied, reversal, reversal_manifest, evaluation)
    _apply(registry, applied, restored, reversal, reversal_manifest)

    assert restored.known_failures == ()
    assert registry.pending_reversal_pairs(AGENT) == (
        (original.proposal_id, reversal.proposal_id),)

    outcome_manifest = dict(original_manifest)
    outcome_manifest.update(reversal_manifest)
    registry.record_outcome(
        AGENT,
        original.proposal_id,
        current_profile=restored,
        outcome="reverted",
        evidence_manifest=outcome_manifest,
        recorded_by="post-change-reviewer",
        evidence_reference="evidence/reversal",
        linked_proposal_id=reversal.proposal_id,
    )

    assert registry.load(AGENT, original.proposal_id)["status"] == "reverted"
    assert registry.load(AGENT, reversal.proposal_id)["status"] == "probationary"
    assert registry.pending_reversal_pairs(AGENT) == ()


def test_original_cannot_be_confirmed_after_inverse_application(tmp_path):
    registry, _, original, original_manifest, applied = _original_flow(tmp_path)
    reversal = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/reversal",
    )
    reversal_manifest = _evidence(
        "evidence/reversal",
        action="identity:resolve_known_failure",
        value=FAILURE,
        outcomes=("reverted",),
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="post-change-verifier",
    )
    evaluation = _approve(registry, applied, reversal, reversal_manifest)
    restored = _updated(applied, reversal, reversal_manifest, evaluation)
    _apply(registry, applied, restored, reversal, reversal_manifest)

    confirmation = _evidence(
        "evidence/confirmation",
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
            recorded_by="post-change-reviewer",
            evidence_reference="evidence/confirmation",
        )


def test_third_probationary_application_is_always_refused(tmp_path):
    registry, _, original, _, applied = _original_flow(tmp_path)
    reversal = _proposal(
        "REV-INVERSE",
        target="identity",
        action="resolve_known_failure",
        value=FAILURE,
        reference="evidence/reversal",
    )
    reversal_manifest = _evidence(
        "evidence/reversal",
        action="identity:resolve_known_failure",
        value=FAILURE,
        supports=(
            "identity:add_known_failure",
            "identity:resolve_known_failure",
        ),
        verifier="post-change-verifier",
    )
    evaluation = _approve(registry, applied, reversal, reversal_manifest)
    restored = _updated(applied, reversal, reversal_manifest, evaluation)
    _apply(registry, applied, restored, reversal, reversal_manifest)

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
    assert len([record for record in records
                if record["status"] == "probationary"]) == 2
    assert original.proposal_id in {
        record["proposal_id"] for record in records
    }

"""End-to-end tests for strict rollback completion and registry reconciliation."""

import dataclasses

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    SelfRevisionProposal,
    StrictSelfRevisionRegistry,
    approve_and_apply_self_revision,
    assert_revision_state_consistent,
    build_reversal_proposal,
    build_self_review_snapshot,
    reconcile_revision_state,
)

SelfRevisionRegistry = StrictSelfRevisionRegistry

AGENT = "agent_alpha"
VALUE = "rushes exact-output tasks"
ORIGINAL_REF = "trace/original"
REVERSAL_REF = "trace/reversal"
ORIGINAL_OUTCOME_REF = "outcome/original"
REVERSAL_OUTCOME_REF = "outcome/reversal"
STABLE_IDS = ("LESSON-0001",)


def _profile():
    return AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
        stable_lessons=STABLE_IDS,
    )


def _proposal(
    proposal_id,
    action,
    reference,
    *,
    reason="Verified evidence supports this change.",
):
    return SelfRevisionProposal(
        proposal_id=proposal_id,
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action=action,
        value=VALUE,
        reason=reason,
        evidence_references=(reference,),
        risk="The evidence window may still be incomplete.",
    )


def _evidence(proposal, reference, *, outcomes=(), verifier="instrument"):
    return {
        reference: {
            "verified": True,
            "agent_id": AGENT,
            "source": f"harness/{reference}",
            "supports": (f"{proposal.target}:{proposal.action}",),
            "value": proposal.value,
            "verified_by": verifier,
            "verification_reference": f"verification/{reference}",
            "observed_on": "2026-07-10",
            "outcomes": tuple(outcomes),
        }
    }


def _submit_evaluate_approve_apply(
    registry,
    previous,
    proposal,
    manifest,
    *,
    approver,
    application_reference,
):
    snapshot = build_self_review_snapshot(
        previous, evidence_manifest=manifest)
    registry.submit(proposal, snapshot=snapshot)
    evaluation = registry.record_evaluation(
        AGENT,
        proposal.proposal_id,
        current_profile=previous,
        evidence_manifest=manifest,
        stable_lesson_ids=STABLE_IDS,
        evaluated_by="evidence-harness",
    )
    registry.record_decision(
        AGENT,
        proposal.proposal_id,
        current_profile=previous,
        evidence_manifest=manifest,
        stable_lesson_ids=STABLE_IDS,
        decision="approved",
        decided_by=approver,
        decision_reference=f"review/{proposal.proposal_id}",
    )
    updated = approve_and_apply_self_revision(
        previous,
        proposal,
        evaluation,
        evidence_manifest=manifest,
        stable_lesson_ids=STABLE_IDS,
        approved_by=approver,
        approval_reference=f"review/{proposal.proposal_id}",
    )
    registry.record_application(
        AGENT,
        proposal.proposal_id,
        previous_profile=previous,
        updated_profile=updated,
        evidence_manifest=manifest,
        stable_lesson_ids=STABLE_IDS,
        applied_by="identity-writer",
        application_reference=application_reference,
    )
    return updated


def _prepare_original(registry):
    profile = _profile()
    original = _proposal(
        "REV-ORIGINAL", "add_known_failure", ORIGINAL_REF)
    manifest = _evidence(original, ORIGINAL_REF)
    applied = _submit_evaluate_approve_apply(
        registry,
        profile,
        original,
        manifest,
        approver="original-approver",
        application_reference="identity/revision/0",
    )
    return profile, original, manifest, applied


def _prepare_confirmed_reversal(registry, original, applied):
    reversal = build_reversal_proposal(
        applied,
        original.proposal_id,
        proposal_id="REV-REVERSAL",
        evidence_references=(REVERSAL_REF,),
        reason="Post-change evidence requires restoring the previous state.",
        risk="The original weakness may return.",
    )
    reversal_manifest = _evidence(reversal, REVERSAL_REF)
    restored = _submit_evaluate_approve_apply(
        registry,
        applied,
        reversal,
        reversal_manifest,
        approver="reversal-approver",
        application_reference="identity/revision/1",
    )
    reversal_outcome = dict(reversal_manifest)
    reversal_outcome.update(_evidence(
        reversal,
        REVERSAL_OUTCOME_REF,
        outcomes=("confirmed",),
        verifier="post-change-verifier",
    ))
    registry.record_outcome(
        AGENT,
        reversal.proposal_id,
        current_profile=restored,
        outcome="confirmed",
        evidence_manifest=reversal_outcome,
        recorded_by="post-change-reviewer",
        evidence_reference=REVERSAL_OUTCOME_REF,
    )
    return reversal, restored


def test_submit_rejects_obsolete_or_forged_snapshot_version(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile = _profile()
    proposal = _proposal("REV-1", "add_known_failure", ORIGINAL_REF)
    manifest = _evidence(proposal, ORIGINAL_REF)
    snapshot = build_self_review_snapshot(profile, evidence_manifest=manifest)
    forged = dataclasses.replace(snapshot, snapshot_version="obsolete-v0")

    with pytest.raises(ValueError, match="current governed version"):
        registry.submit(proposal, snapshot=forged)


def test_original_cannot_be_marked_reverted_for_submitted_only_inverse(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    _, original, manifest, applied = _prepare_original(registry)
    reversal = build_reversal_proposal(
        applied,
        original.proposal_id,
        proposal_id="REV-REVERSAL",
        evidence_references=(REVERSAL_REF,),
        reason="Rollback requested.",
        risk="Original weakness may return.",
    )
    reversal_manifest = _evidence(reversal, REVERSAL_REF)
    registry.submit(
        reversal,
        snapshot=build_self_review_snapshot(
            applied, evidence_manifest=reversal_manifest),
    )
    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        original,
        ORIGINAL_OUTCOME_REF,
        outcomes=("reverted",),
        verifier="post-change-verifier",
    ))

    with pytest.raises(ValueError, match="applied and confirmed"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=applied,
            outcome="reverted",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-reviewer",
            evidence_reference=ORIGINAL_OUTCOME_REF,
            linked_proposal_id=reversal.proposal_id,
        )
    assert registry.load(AGENT, original.proposal_id)["status"] == \
        "probationary"


def test_confirmed_inverse_must_equal_current_profile_before_reverted(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    _, original, manifest, applied = _prepare_original(registry)
    reversal, restored = _prepare_confirmed_reversal(
        registry, original, applied)
    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        original,
        ORIGINAL_OUTCOME_REF,
        outcomes=("reverted",),
        verifier="post-change-verifier",
    ))

    with pytest.raises(ValueError, match="current identity profile"):
        registry.record_outcome(
            AGENT,
            original.proposal_id,
            current_profile=dataclasses.replace(
                restored, soul_principles=("unrelated mutation",)),
            outcome="reverted",
            evidence_manifest=outcome_manifest,
            recorded_by="post-change-reviewer",
            evidence_reference=ORIGINAL_OUTCOME_REF,
            linked_proposal_id=reversal.proposal_id,
        )


def test_full_confirmed_rollback_reconciles_both_registries(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    _, original, manifest, applied = _prepare_original(registry)
    reversal, restored = _prepare_confirmed_reversal(
        registry, original, applied)
    outcome_manifest = dict(manifest)
    outcome_manifest.update(_evidence(
        original,
        ORIGINAL_OUTCOME_REF,
        outcomes=("reverted",),
        verifier="post-change-verifier",
    ))
    registry.record_outcome(
        AGENT,
        original.proposal_id,
        current_profile=restored,
        outcome="reverted",
        evidence_manifest=outcome_manifest,
        recorded_by="rollback-final-reviewer",
        evidence_reference=ORIGINAL_OUTCOME_REF,
        linked_proposal_id=reversal.proposal_id,
    )

    records = registry.all_records(AGENT)
    by_id = {record["proposal_id"]: record for record in records}
    assert by_id[original.proposal_id]["status"] == "reverted"
    assert by_id[reversal.proposal_id]["status"] == "confirmed"
    assert VALUE not in restored.known_failures

    report = reconcile_revision_state(restored, records)
    assert report.consistent is True
    assert report.issues == ()
    assert report.profile_revision_count == 2
    assert report.lifecycle_record_count == 2
    assert_revision_state_consistent(restored, records)


def test_reconciliation_detects_missing_and_preapplication_drift(tmp_path):
    registry = SelfRevisionRegistry(tmp_path)
    profile, _, _, applied = _prepare_original(registry)
    records = registry.all_records(AGENT)

    missing = reconcile_revision_state(applied, ())
    assert missing.consistent is False
    assert "no lifecycle record" in missing.issues[0]

    submitted_registry = SelfRevisionRegistry(tmp_path / "submitted")
    proposal = _proposal("REV-SUBMITTED", "add_known_failure", ORIGINAL_REF)
    manifest = _evidence(proposal, ORIGINAL_REF)
    submitted_registry.submit(
        proposal,
        snapshot=build_self_review_snapshot(profile, evidence_manifest=manifest),
    )
    forged_profile = dataclasses.replace(
        profile,
        known_failures=(VALUE,),
        revision_history=({
            "entry_type": "self_revision",
            "proposal_id": proposal.proposal_id,
        },),
    )
    report = reconcile_revision_state(
        forged_profile, submitted_registry.all_records(AGENT))
    assert report.consistent is False
    assert any("already appears in identity" in issue for issue in report.issues)

    assert reconcile_revision_state(applied, records).consistent is True

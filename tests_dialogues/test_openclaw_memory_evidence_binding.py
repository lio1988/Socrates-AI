"""Lifecycle tests for current lesson/Identity-bound Memory evidence."""

import dataclasses

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    RevisionEvidenceRecord,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    SelfRevisionTransactionCoordinator,
    build_self_review_snapshot,
    governed_profile_fingerprint,
)
from backend.dialogues.openclaw_identity.memory_evidence_binding import (
    memory_ab_binding_marker,
    parse_memory_ab_binding,
)

AGENT = "local_apprentice_001"
LESSON = "LESSON-0007"
REFERENCE = "agent-ab/local_apprentice_001/lesson-0007/helped-1"
LESSON_FP = "a" * 64
EXPERIMENT_FP = "b" * 64


def _profile(**updates):
    base = AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
    )
    return dataclasses.replace(base, **updates)


def _source(profile, *, lesson_fp=LESSON_FP):
    return (
        "AgentLessonAB/report-1"
        + memory_ab_binding_marker(
            lesson_fingerprint=lesson_fp,
            identity_fingerprint=governed_profile_fingerprint(profile),
            experiment_fingerprint=EXPERIMENT_FP,
        )
        + "#agent-ab-" + "c" * 16
    )


def _evidence(profile, *, source=None):
    return RevisionEvidenceRecord(
        reference=REFERENCE,
        agent_id=AGENT,
        source=source or _source(profile),
        supports=("memory:link_stable_lesson",),
        value=LESSON,
        verified_by="evidence-harness",
        verification_reference="review/agent-ab-1",
        observed_on="2026-07-10",
        outcomes=("confirmed",),
    )


def _manifest(evidence):
    return {REFERENCE: evidence.to_manifest_entry()}


def _proposal():
    return SelfRevisionProposal(
        proposal_id="REV-MEMORY-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="memory",
        action="link_stable_lesson",
        value=LESSON,
        reason="A bound single-agent matched A/B report showed benefit.",
        evidence_references=(REFERENCE,),
        risk="The measured benefit may not generalize beyond the test window.",
    )


def _submitted(tmp_path, *, evidence=None, profile=None):
    profile = profile or _profile()
    evidence = evidence or _evidence(profile)
    manifest = _manifest(evidence)
    registry = SelfRevisionRegistry(tmp_path / "lifecycle")
    snapshot = build_self_review_snapshot(
        profile, evidence_manifest=manifest)
    registry.submit(_proposal(), snapshot=snapshot)
    return registry, profile, manifest


def test_binding_marker_round_trips():
    marker = memory_ab_binding_marker(
        lesson_fingerprint=LESSON_FP,
        identity_fingerprint="d" * 64,
        experiment_fingerprint=EXPERIMENT_FP,
    )
    assert parse_memory_ab_binding("prefix" + marker + "#agent-ab-x") == (
        LESSON_FP, "d" * 64, EXPERIMENT_FP)


def test_memory_submit_refuses_unbound_agent_ab_evidence(tmp_path):
    profile = _profile()
    evidence = _evidence(
        profile,
        source="AgentLessonAB/report-1#agent-ab-" + "c" * 16,
    )
    registry = SelfRevisionRegistry(tmp_path / "lifecycle")
    snapshot = build_self_review_snapshot(
        profile, evidence_manifest=_manifest(evidence))

    with pytest.raises(ValueError, match="not bound single-agent"):
        registry.submit(_proposal(), snapshot=snapshot)


def test_memory_submit_refuses_evidence_bound_to_another_identity(tmp_path):
    profile = _profile()
    other = dataclasses.replace(profile, soul_principles=("Different state.",))
    evidence = _evidence(profile, source=_source(other))
    registry = SelfRevisionRegistry(tmp_path / "lifecycle")
    snapshot = build_self_review_snapshot(
        profile, evidence_manifest=_manifest(evidence))

    with pytest.raises(ValueError, match="stale for the bound"):
        registry.submit(_proposal(), snapshot=snapshot)


def test_evaluation_requires_current_lesson_fingerprint(tmp_path):
    registry, profile, manifest = _submitted(tmp_path)

    with pytest.raises(ValueError, match="fingerprint is missing"):
        registry.record_evaluation(
            AGENT,
            _proposal().proposal_id,
            current_profile=profile,
            evidence_manifest=manifest,
            stable_lesson_ids=(LESSON,),
            evaluated_by="evaluator",
        )

    with pytest.raises(ValueError, match="stale lesson revision"):
        registry.record_evaluation(
            AGENT,
            _proposal().proposal_id,
            current_profile=profile,
            evidence_manifest=manifest,
            stable_lesson_ids=(LESSON,),
            lesson_fingerprints={LESSON: "e" * 64},
            evaluated_by="evaluator",
        )

    evaluation = registry.record_evaluation(
        AGENT,
        _proposal().proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=(LESSON,),
        lesson_fingerprints={LESSON: LESSON_FP},
        evaluated_by="evaluator",
    )
    assert evaluation.passed is True


def test_decision_rechecks_lesson_revision(tmp_path):
    registry, profile, manifest = _submitted(tmp_path)
    registry.record_evaluation(
        AGENT,
        _proposal().proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=(LESSON,),
        lesson_fingerprints={LESSON: LESSON_FP},
        evaluated_by="evaluator",
    )

    with pytest.raises(ValueError, match="stale lesson revision"):
        registry.record_decision(
            AGENT,
            _proposal().proposal_id,
            current_profile=profile,
            evidence_manifest=manifest,
            stable_lesson_ids=(LESSON,),
            lesson_fingerprints={LESSON: "e" * 64},
            decision="approved",
            decided_by="approver",
            decision_reference="review/decision-1",
        )

    registry.record_decision(
        AGENT,
        _proposal().proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=(LESSON,),
        lesson_fingerprints={LESSON: LESSON_FP},
        decision="approved",
        decided_by="approver",
        decision_reference="review/decision-1",
    )
    assert registry.load(AGENT, _proposal().proposal_id)["status"] == "approved"


def test_application_preflight_refuses_stale_map_before_journal_or_identity(
        tmp_path):
    identity = IdentityRegistry(tmp_path / "identity")
    profile = _profile()
    identity.save_profile(profile)
    registry, _, manifest = _submitted(tmp_path, profile=profile)
    registry.record_evaluation(
        AGENT,
        _proposal().proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=(LESSON,),
        lesson_fingerprints={LESSON: LESSON_FP},
        evaluated_by="evaluator",
    )
    registry.record_decision(
        AGENT,
        _proposal().proposal_id,
        current_profile=profile,
        evidence_manifest=manifest,
        stable_lesson_ids=(LESSON,),
        lesson_fingerprints={LESSON: LESSON_FP},
        decision="approved",
        decided_by="approver",
        decision_reference="review/decision-1",
    )
    coordinator = SelfRevisionTransactionCoordinator(
        identity, registry, tmp_path / "transactions")

    with pytest.raises(ValueError, match="stale lesson revision"):
        coordinator.apply_approved(
            AGENT,
            _proposal().proposal_id,
            evidence_manifest=manifest,
            stable_lesson_ids=(LESSON,),
            lesson_fingerprints={LESSON: "e" * 64},
            applied_by="identity-writer",
            application_reference="identity/revision-1",
        )

    assert identity.load_profile(AGENT).stable_lessons == ()
    assert not (tmp_path / "transactions" / AGENT /
                f"{_proposal().proposal_id}.json").exists()

    updated = coordinator.apply_approved(
        AGENT,
        _proposal().proposal_id,
        evidence_manifest=manifest,
        stable_lesson_ids=(LESSON,),
        lesson_fingerprints={LESSON: LESSON_FP},
        applied_by="identity-writer",
        application_reference="identity/revision-1",
    )
    assert updated.stable_lessons == (LESSON,)
    assert registry.load(AGENT, _proposal().proposal_id)["status"] == \
        "probationary"

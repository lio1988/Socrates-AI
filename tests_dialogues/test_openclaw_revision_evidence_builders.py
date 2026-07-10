"""Tests for causal, instrument-bound self-revision evidence builders."""

import copy

import pytest

from backend.dialogues.openclaw_identity import (
    AGENT_LESSON_AB_REPORT_VERSION,
    IDENTITY_FAILURE_REPORT_VERSION,
    IDENTITY_RESOLUTION_REPORT_VERSION,
    SOUL_ATTESTATION_VERSION,
    AgentIdentityProfile,
    RevisionEvidenceRegistry,
    SelfRevisionProposal,
    build_agent_lesson_ab_evidence,
    build_identity_failure_evidence,
    build_identity_resolution_evidence,
    build_self_review_snapshot,
    build_soul_attestation_evidence,
    evaluate_self_revision,
)

AGENT = "agent_alpha"
WEAKNESS = "rushes exact-output tasks"
LESSON = "LESSON-0007"
PRINCIPLE = "State uncertainty before asserting a final verdict."


def _failure_report():
    return {
        "schema_version": IDENTITY_FAILURE_REPORT_VERSION,
        "reference": "attribution/exact-output-1",
        "agent_id": AGENT,
        "pattern_key": "phase_missing:synthesis",
        "weakness": WEAKNESS,
        "observations": [
            {
                "session_id": "session-1",
                "attributed_agent_id": AGENT,
                "pattern_key": "phase_missing:synthesis",
                "attribution_verified": True,
                "source_trace": "trace/session-1",
            },
            {
                "session_id": "session-2",
                "attributed_agent_id": AGENT,
                "pattern_key": "phase_missing:synthesis",
                "attribution_verified": True,
                "source_trace": "trace/session-2",
            },
        ],
        "source": "TraceAttribution/exact-output-window-1",
        "verified_by": "evidence-harness",
        "verification_reference": "report/attribution-1",
        "observed_on": "2026-07-10",
    }


def _resolution_report():
    return {
        "schema_version": IDENTITY_RESOLUTION_REPORT_VERSION,
        "reference": "resolution/exact-output-1",
        "agent_id": AGENT,
        "pattern_key": "phase_missing:synthesis",
        "weakness": WEAKNESS,
        "before_session_ids": ["before-1", "before-2"],
        "after_session_ids": ["after-1", "after-2"],
        "before_failures": 2,
        "after_failures": 0,
        "matched_window": True,
        "source": "TraceWindow/exact-output-before-after",
        "verified_by": "evidence-harness",
        "verification_reference": "report/resolution-1",
        "observed_on": "2026-07-10",
    }


def _lesson_report():
    return {
        "schema_version": AGENT_LESSON_AB_REPORT_VERSION,
        "reference": "agent-ab/lesson-0007-1",
        "target_agent_id": AGENT,
        "lesson_id": LESSON,
        "treatment_scope": "single_agent",
        "tested": 4,
        "min_tested": 3,
        "verdict": "helped",
        "helped": True,
        "mean_score_delta": 0.25,
        "harm_rate": 0.0,
        "max_harm_rate": 0.0,
        "ratification_regressions": 0,
        "unresolved_regressions": 0,
        "catastrophic_regressions": 0,
        "configuration_mismatches": 0,
        "source": "AgentLessonAB/report-1",
        "verified_by": "lesson-ab-harness",
        "verification_reference": "report/agent-ab-1",
        "observed_on": "2026-07-10",
    }


def _soul_report():
    return {
        "schema_version": SOUL_ATTESTATION_VERSION,
        "reference": "soul-review/uncertainty-1",
        "agent_id": AGENT,
        "action": "add_principle",
        "principle": PRINCIPLE,
        "constitutional_review": True,
        "risk_reviewed": True,
        "evidence_references": [
            "trace/session-1",
            "review/epistemic-humility-1",
        ],
        "rationale": (
            "The principle constrains overclaiming and does not add authority."
        ),
        "reviewed_by": "constitutional-reviewer",
        "review_reference": "review/soul-1",
        "observed_on": "2026-07-10",
    }


def test_repeated_agent_attribution_builds_identity_failure_evidence():
    evidence = build_identity_failure_evidence(_failure_report())
    assert evidence.agent_id == AGENT
    assert evidence.supports == ("identity:add_known_failure",)
    assert evidence.value == WEAKNESS
    assert evidence.reference == "attribution/exact-output-1"
    assert "attribution-" in evidence.source


def test_session_level_or_weak_attribution_cannot_become_personal_evidence():
    report = _failure_report()
    report["observations"][0].pop("attributed_agent_id")
    with pytest.raises(ValueError, match="missing or unknown"):
        build_identity_failure_evidence(report)

    report = _failure_report()
    report["observations"][0]["attribution_verified"] = False
    with pytest.raises(ValueError, match="not verified"):
        build_identity_failure_evidence(report)

    report = _failure_report()
    report["observations"][1]["attributed_agent_id"] = "agent_beta"
    with pytest.raises(ValueError, match="another agent"):
        build_identity_failure_evidence(report)

    report = _failure_report()
    report["observations"] = report["observations"][:1]
    with pytest.raises(ValueError, match="requires 2 observations"):
        build_identity_failure_evidence(report)


def test_attribution_requires_distinct_sessions_and_non_self_verifier():
    report = _failure_report()
    report["observations"][1]["session_id"] = "session-1"
    with pytest.raises(ValueError, match="distinct sessions"):
        build_identity_failure_evidence(report)

    report = _failure_report()
    report["verified_by"] = AGENT
    with pytest.raises(ValueError, match="cannot verify its own"):
        build_identity_failure_evidence(report)


def test_matched_zero_failure_window_builds_resolution_evidence():
    evidence = build_identity_resolution_evidence(_resolution_report())
    assert evidence.supports == ("identity:resolve_known_failure",)
    assert evidence.value == WEAKNESS
    assert "matched-" in evidence.source


def test_resolution_refuses_unmatched_overlapping_or_incomplete_recovery():
    report = _resolution_report()
    report["matched_window"] = False
    with pytest.raises(ValueError, match="matched comparison"):
        build_identity_resolution_evidence(report)

    report = _resolution_report()
    report["after_session_ids"][0] = "before-1"
    with pytest.raises(ValueError, match="must not overlap"):
        build_identity_resolution_evidence(report)

    report = _resolution_report()
    report["after_failures"] = 1
    with pytest.raises(ValueError, match="zero failures"):
        build_identity_resolution_evidence(report)


def test_single_agent_helped_ab_builds_memory_link_evidence():
    evidence = build_agent_lesson_ab_evidence(
        _lesson_report(), action="link_stable_lesson")
    assert evidence.agent_id == AGENT
    assert evidence.supports == ("memory:link_stable_lesson",)
    assert evidence.value == LESSON
    assert evidence.outcomes == ("confirmed",)


def test_council_wide_or_harmful_ab_cannot_link_agent_memory():
    report = _lesson_report()
    report["schema_version"] = "lesson_ab_v2"
    with pytest.raises(ValueError, match="schema_version"):
        build_agent_lesson_ab_evidence(
            report, action="link_stable_lesson")

    report = _lesson_report()
    report["treatment_scope"] = "whole_council"
    with pytest.raises(ValueError, match="single_agent"):
        build_agent_lesson_ab_evidence(
            report, action="link_stable_lesson")

    report = _lesson_report()
    report["ratification_regressions"] = 1
    with pytest.raises(ValueError, match="harm or configuration"):
        build_agent_lesson_ab_evidence(
            report, action="link_stable_lesson")

    report = _lesson_report()
    report["tested"] = 2
    with pytest.raises(ValueError, match="insufficient"):
        build_agent_lesson_ab_evidence(
            report, action="link_stable_lesson")


def test_concrete_harmed_ab_builds_memory_unlink_and_revert_evidence():
    report = _lesson_report()
    report.update({
        "reference": "agent-ab/lesson-0007-harm-1",
        "verdict": "harmed",
        "helped": False,
        "mean_score_delta": -0.2,
        "harm_rate": 0.5,
        "max_harm_rate": 0.0,
        "ratification_regressions": 1,
    })
    evidence = build_agent_lesson_ab_evidence(
        report, action="unlink_stable_lesson")
    assert evidence.supports == ("memory:unlink_stable_lesson",)
    assert evidence.outcomes == ("reverted",)


def test_no_effect_report_cannot_unlink_memory():
    report = _lesson_report()
    report.update({
        "verdict": "no_effect",
        "helped": False,
        "mean_score_delta": 0.0,
    })
    with pytest.raises(ValueError, match="concrete harmed"):
        build_agent_lesson_ab_evidence(
            report, action="unlink_stable_lesson")


def test_explicit_constitutional_review_builds_soul_evidence():
    evidence = build_soul_attestation_evidence(_soul_report())
    assert evidence.agent_id == AGENT
    assert evidence.supports == ("soul:add_principle",)
    assert evidence.value == PRINCIPLE
    assert evidence.verified_by == "constitutional-reviewer"
    assert "attestation-" in evidence.source


def test_soul_cannot_be_inferred_without_review_risk_or_external_actor():
    report = _soul_report()
    report["constitutional_review"] = False
    with pytest.raises(ValueError, match="constitutional review"):
        build_soul_attestation_evidence(report)

    report = _soul_report()
    report["risk_reviewed"] = False
    with pytest.raises(ValueError, match="risk review"):
        build_soul_attestation_evidence(report)

    report = _soul_report()
    report["reviewed_by"] = AGENT
    with pytest.raises(ValueError, match="cannot verify its own"):
        build_soul_attestation_evidence(report)

    report = _soul_report()
    report["evidence_references"] = "trace/session-1"
    with pytest.raises(ValueError, match="sequence, not text"):
        build_soul_attestation_evidence(report)


def test_builder_output_registers_and_drives_exact_proposal_evaluation(tmp_path):
    evidence = build_identity_failure_evidence(_failure_report())
    registry = RevisionEvidenceRegistry(tmp_path)
    registry.register(evidence)
    manifest = registry.manifest(AGENT)
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposal = SelfRevisionProposal(
        proposal_id="REV-BUILDER-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=WEAKNESS,
        reason="The attributed repeated pattern warrants recording the weakness.",
        evidence_references=(evidence.reference,),
        risk="Attribution may still overfit a narrow operational window.",
    )

    snapshot = build_self_review_snapshot(profile, evidence_manifest=manifest)
    evaluation = evaluate_self_revision(proposal, evidence_manifest=manifest)
    assert snapshot.verified_evidence[0].reference == evidence.reference
    assert evaluation.passed is True


def test_report_schema_is_exact_and_secret_shaped_values_fail_closed():
    report = _failure_report()
    report["authority"] = "grant"
    with pytest.raises(ValueError, match="missing or unknown"):
        build_identity_failure_evidence(report)

    report = copy.deepcopy(_soul_report())
    report["rationale"] = "api_key=abcdefgh12345678"
    with pytest.raises(ValueError, match="secret-shaped"):
        build_soul_attestation_evidence(report)

"""Tests for the public hardening wrappers exported by openclaw_identity."""

import json
import math

import pytest

from backend.dialogues.openclaw_identity import (
    AGENT_LESSON_AB_REPORT_VERSION,
    AgentIdentityProfile,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    build_agent_lesson_ab_evidence,
    build_identity_resolution_evidence,
    build_self_review_snapshot,
)
from backend.dialogues.openclaw_identity.revision_evidence_builders import (
    IDENTITY_RESOLUTION_REPORT_VERSION,
)

AGENT = "agent_alpha"


def _lesson_report():
    return {
        "schema_version": AGENT_LESSON_AB_REPORT_VERSION,
        "reference": "agent-ab/finite-1",
        "target_agent_id": AGENT,
        "lesson_id": "LESSON-0007",
        "treatment_scope": "single_agent",
        "tested": 4,
        "min_tested": 3,
        "verdict": "helped",
        "helped": True,
        "mean_score_delta": 0.2,
        "harm_rate": 0.0,
        "max_harm_rate": 0.0,
        "ratification_regressions": 0,
        "unresolved_regressions": 0,
        "catastrophic_regressions": 0,
        "configuration_mismatches": 0,
        "source": "AgentLessonAB/finite-1",
        "verified_by": "lesson-ab-harness",
        "verification_reference": "verification/finite-1",
        "observed_on": "2026-07-10",
    }


def _resolution_report():
    return {
        "schema_version": IDENTITY_RESOLUTION_REPORT_VERSION,
        "reference": "resolution/finite-1",
        "agent_id": AGENT,
        "pattern_key": "phase_missing:synthesis",
        "weakness": "rushes exact-output tasks",
        "before_session_ids": ["before-1", "before-2"],
        "after_session_ids": ["after-1", "after-2"],
        "before_failures": 2,
        "after_failures": 0,
        "matched_window": True,
        "source": "TraceWindow/finite-1",
        "verified_by": "evidence-harness",
        "verification_reference": "verification/resolution-1",
        "observed_on": "2026-07-10",
    }


def _proposal_and_manifest():
    proposal = SelfRevisionProposal(
        proposal_id="REV-SCHEMA-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value="rushes exact-output tasks",
        reason="Repeated attributed evidence supports the revision.",
        evidence_references=("evidence/schema-1",),
        risk="The evidence window may be narrow.",
    )
    manifest = {
        "evidence/schema-1": {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-attribution",
            "supports": ["identity:add_known_failure"],
            "value": proposal.value,
            "verified_by": "evidence-harness",
            "verification_reference": "verification/schema-1",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }
    return proposal, manifest


@pytest.mark.parametrize("field,value", [
    ("mean_score_delta", math.nan),
    ("mean_score_delta", math.inf),
    ("harm_rate", math.nan),
    ("max_harm_rate", -math.inf),
])
def test_public_lesson_builder_refuses_non_finite_metrics(field, value):
    report = _lesson_report()
    report[field] = value
    with pytest.raises(ValueError, match="must be finite"):
        build_agent_lesson_ab_evidence(
            report, action="link_stable_lesson")


def test_public_resolution_builder_requires_nonempty_pattern_key():
    report = _resolution_report()
    report["pattern_key"] = "   "
    with pytest.raises(ValueError, match="pattern_key must be non-empty"):
        build_identity_resolution_evidence(report)


def test_public_lifecycle_loader_refuses_rewritten_snapshot_version(tmp_path):
    proposal, manifest = _proposal_and_manifest()
    profile = AgentIdentityProfile(agent_id=AGENT)
    snapshot = build_self_review_snapshot(profile, evidence_manifest=manifest)
    registry = SelfRevisionRegistry(tmp_path)
    path = registry.submit(proposal, snapshot=snapshot)

    record = json.loads(path.read_text(encoding="utf-8"))
    record["snapshot_version"] = "openclaw_self_review_v999"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot_version"):
        registry.load(AGENT, proposal.proposal_id)

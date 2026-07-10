"""Integrity tests for trusted self-revision evidence records."""

import json

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    RevisionEvidenceRecord,
    RevisionEvidenceRegistry,
    SelfRevisionProposal,
    build_self_review_snapshot,
    evaluate_self_revision,
    evidence_from_record,
)

AGENT = "local_apprentice_001"
REFERENCE = "trace/session-1"
VALUE = "rushes exact-output tasks"


def _evidence(**updates):
    data = {
        "reference": REFERENCE,
        "agent_id": AGENT,
        "source": "TraceCapture/session-1",
        "supports": ("identity:add_known_failure",),
        "value": VALUE,
        "verified_by": "evidence-harness",
        "verification_reference": "report/trace-attribution-1",
        "observed_on": "2026-07-10",
    }
    data.update(updates)
    return RevisionEvidenceRecord(**data)


def _proposal():
    return SelfRevisionProposal(
        proposal_id="REV-EVIDENCE-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=VALUE,
        reason="The verified trace attribution shows a repeated pattern.",
        evidence_references=(REFERENCE,),
        risk="The evidence window may be narrow.",
    )


def test_record_is_strict_verified_and_non_self():
    evidence = _evidence()
    record = evidence.to_record()
    assert record["verified"] is True
    assert evidence_from_record(record) == evidence

    with pytest.raises(ValueError, match="cannot verify its own"):
        _evidence(verified_by=AGENT)
    with pytest.raises(ValueError, match="unknown self-revision supports"):
        _evidence(supports=("authority:grant",))
    with pytest.raises(ValueError, match="sequence, not text"):
        _evidence(supports="identity:add_known_failure")


def test_record_rejects_unknown_fields_unverified_and_secrets():
    record = _evidence().to_record()
    with pytest.raises(ValueError, match="unknown fields"):
        evidence_from_record({**record, "authority": "grant"})
    with pytest.raises(ValueError, match="explicitly verified"):
        evidence_from_record({**record, "verified": False})
    with pytest.raises(ValueError, match="secret-shaped"):
        _evidence(value="api_key=abcdefgh12345678")


def test_registry_register_load_and_idempotent_replay(tmp_path):
    registry = RevisionEvidenceRegistry(tmp_path)
    evidence = _evidence()

    first = registry.register(evidence)
    second = registry.register(evidence)

    assert first == second
    assert registry.load(REFERENCE) == evidence
    assert list(tmp_path.glob(".*.tmp")) == []
    raw = json.loads(first.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "openclaw_self_revision_evidence_v1"
    assert raw["record_hash"]


def test_registry_refuses_conflicting_duplicate_reference(tmp_path):
    registry = RevisionEvidenceRegistry(tmp_path)
    registry.register(_evidence())

    with pytest.raises(ValueError, match="conflicting content"):
        registry.register(_evidence(value="different value"))


def test_registry_manifest_filters_by_agent_and_sorts(tmp_path):
    registry = RevisionEvidenceRegistry(tmp_path)
    registry.register(_evidence(reference="trace/z"))
    registry.register(_evidence(reference="trace/a"))
    registry.register(_evidence(
        reference="trace/other",
        agent_id="other_agent",
        verified_by="evidence-harness",
    ))

    assert [record.reference for record in registry.all_records(AGENT)] == [
        "trace/a", "trace/z"]
    manifest = registry.manifest(AGENT)
    assert list(manifest) == ["trace/a", "trace/z"]
    assert manifest["trace/a"]["verified"] is True
    assert manifest["trace/a"]["agent_id"] == AGENT
    assert "trace/other" not in manifest


def test_registry_tampering_and_filename_mismatch_are_visible(tmp_path):
    registry = RevisionEvidenceRegistry(tmp_path)
    path = registry.register(_evidence())

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["evidence"]["value"] = "tampered"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        registry.load(REFERENCE)


def test_registry_manifest_composes_with_snapshot_and_evaluation(tmp_path):
    registry = RevisionEvidenceRegistry(tmp_path)
    registry.register(_evidence())
    manifest = registry.manifest(AGENT)
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposal = _proposal()

    snapshot = build_self_review_snapshot(
        profile, evidence_manifest=manifest)
    evaluation = evaluate_self_revision(
        proposal, evidence_manifest=manifest)

    assert [row.reference for row in snapshot.verified_evidence] == [REFERENCE]
    assert evaluation.passed is True
    assert evaluation.evidence_used == (REFERENCE,)

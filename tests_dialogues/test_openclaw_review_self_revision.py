"""Tests for the self-revision section of scripts/openclaw_review.py."""

import importlib.util
import pathlib

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    RevisionEvidenceRecord,
    RevisionEvidenceRegistry,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    build_self_review_snapshot,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"
REFERENCE = "trace/review-evidence-1"
WEAKNESS = "rushes exact-output tasks"


@pytest.fixture(scope="module")
def review_script():
    path = _ROOT / "scripts" / "openclaw_review.py"
    spec = importlib.util.spec_from_file_location("openclaw_review_self_revision", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _env(tmp_path):
    return {
        "CED_TRACE_DIR": str(tmp_path / "traces"),
        "CED_SHADOW_DIR": str(tmp_path / "shadow"),
        "CED_PROPOSALS_DIR": str(tmp_path / "proposals"),
        "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence"),
        "CED_SELF_REVISION_DIR": str(tmp_path / "revisions"),
    }


def _register_evidence(tmp_path):
    record = RevisionEvidenceRecord(
        reference=REFERENCE,
        agent_id=AGENT,
        source="trace-harness",
        supports=("identity:add_known_failure",),
        value=WEAKNESS,
        verified_by="Operator",
        verification_reference="review/evidence-1",
        observed_on="2026-07-10",
    )
    RevisionEvidenceRegistry(tmp_path / "evidence").register(record)
    return record


def _submit_proposal(tmp_path, evidence):
    manifest = {
        evidence.reference: evidence.to_manifest_entry(),
    }
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposal = SelfRevisionProposal(
        proposal_id="REV-REVIEW-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value=WEAKNESS,
        reason="Verified evidence shows the repeated pattern.",
        evidence_references=(REFERENCE,),
        risk="The evidence window may still be narrow.",
    )
    snapshot = build_self_review_snapshot(
        profile, evidence_manifest=manifest)
    SelfRevisionRegistry(tmp_path / "revisions").submit(
        proposal, snapshot=snapshot)
    return proposal


def test_empty_review_remains_read_only_and_writes_nothing(
        review_script, tmp_path, capsys):
    assert review_script.main(["prog"], env=_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "Nothing to review yet" in out
    assert not (tmp_path / "proposals").exists()


def test_evidence_only_review_writes_pipeline_without_dialogue_history(
        review_script, tmp_path, capsys):
    evidence = _register_evidence(tmp_path)

    assert review_script.main(["prog"], env=_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "revision evidence : 1" in out
    assert "SELF-REVISION PIPELINE" in out
    assert "evidence=1; no proposals" in out

    path = tmp_path / "proposals" / "SELF_REVISION_PIPELINE.md"
    assert path.exists()
    report = path.read_text(encoding="utf-8")
    assert evidence.reference in report
    assert WEAKNESS in report
    assert "verified by **Operator**" in report
    assert f"openclaw_self_review.py {AGENT}" in report
    assert "grant no CED authority" in report


def test_submitted_lifecycle_is_visible_but_not_mutated(
        review_script, tmp_path, capsys):
    evidence = _register_evidence(tmp_path)
    proposal = _submit_proposal(tmp_path, evidence)
    registry = SelfRevisionRegistry(tmp_path / "revisions")
    before = registry.load(AGENT, proposal.proposal_id)
    assert before["status"] == "submitted"

    assert review_script.main(["prog"], env=_env(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "submitted=1" in out

    report = (tmp_path / "proposals" / "SELF_REVISION_PIPELINE.md").read_text(
        encoding="utf-8")
    assert proposal.proposal_id in report
    assert "**submitted**" in report
    assert "complete independent evaluation/decision/application review" in report

    after = registry.load(AGENT, proposal.proposal_id)
    assert after == before
    assert not (tmp_path / "identity").exists()


def test_pipeline_report_is_deterministic(review_script, tmp_path, capsys):
    _register_evidence(tmp_path)
    env = _env(tmp_path)
    assert review_script.main(["prog"], env=env) == 0
    capsys.readouterr()
    path = tmp_path / "proposals" / "SELF_REVISION_PIPELINE.md"
    first = path.read_bytes()

    assert review_script.main(["prog"], env=env) == 0
    capsys.readouterr()
    assert path.read_bytes() == first

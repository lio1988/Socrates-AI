"""Operator tests for scripts/openclaw_self_review.py."""

import importlib.util
import json
from pathlib import Path

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    RevisionEvidenceRecord,
    RevisionEvidenceRegistry,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    build_self_review_snapshot,
)

AGENT = "local_apprentice_001"


@pytest.fixture
def self_review_script():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "openclaw_self_review.py"
    spec = importlib.util.spec_from_file_location("openclaw_self_review_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _profile():
    return AgentIdentityProfile(
        agent_id=AGENT,
        identity_version="v0.3",
        promotion_status="shadow_apprentice",
        role_strengths={"blind_spots": 0.75},
        section_wins={"blind_spots": 3},
        section_opportunities={"blind_spots": 4},
        sessions_analyzed=4,
        ratified_sessions=3,
        stable_lessons=("LESSON-0001",),
    )


def _proposal():
    return SelfRevisionProposal(
        proposal_id="REV-PENDING-1",
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value="rushes exact-output tasks",
        reason="Repeated evidence shows this pattern.",
        evidence_references=("trace/session-1",),
        risk="The evidence window may be narrow.",
    )


def _manifest():
    return {
        "trace/session-1": {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-harness",
            "supports": ["identity:add_known_failure"],
            "value": "rushes exact-output tasks",
        }
    }


def _evidence_record():
    return RevisionEvidenceRecord(
        reference="trace/session-1",
        agent_id=AGENT,
        source="trace-harness",
        supports=("identity:add_known_failure",),
        value="rushes exact-output tasks",
        verified_by="evidence-harness",
        verification_reference="report/trace-1",
    )


def _env(tmp_path):
    return {
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
        "CED_SELF_REVISION_DIR": str(tmp_path / "revisions"),
        "CED_SELF_REVISION_EVIDENCE_DIR": str(tmp_path / "evidence_registry"),
        "CED_SELF_REVISION_EVIDENCE": str(tmp_path / "evidence.json"),
        "CED_SELF_REVIEW_DIR": str(tmp_path / "review"),
    }


def test_usage_requires_agent_id(self_review_script, capsys):
    assert self_review_script.main(["prog"], env={}) == 2
    assert "Usage:" in capsys.readouterr().out


def test_missing_profile_fails_without_artifacts(
        self_review_script, tmp_path, capsys):
    env = _env(tmp_path)
    assert self_review_script.main(["prog", AGENT], env=env) == 1
    out = capsys.readouterr().out
    assert "No identity profile found" in out
    assert not (tmp_path / "review").exists()


def test_happy_path_writes_bounded_artifacts_from_legacy_manifest(
        self_review_script, tmp_path, capsys):
    env = _env(tmp_path)
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(_profile())
    Path(env["CED_SELF_REVISION_EVIDENCE"]).write_text(
        json.dumps(_manifest()), encoding="utf-8")

    assert self_review_script.main(["prog", AGENT], env=env) == 0
    out = capsys.readouterr().out
    review_dir = Path(env["CED_SELF_REVIEW_DIR"])
    snapshot_path = review_dir / f"{AGENT}.snapshot.json"
    summary_path = review_dir / f"{AGENT}.summary.md"
    instruction_path = review_dir / f"{AGENT}.instruction.txt"

    assert snapshot_path.exists()
    assert summary_path.exists()
    assert instruction_path.exists()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["agent_id"] == AGENT
    assert snapshot["snapshot_version"] == "openclaw_self_review_v2"
    assert len(snapshot["verified_evidence"]) == 1
    assert snapshot["pending_proposal_ids"] == []
    assert "Return exactly one JSON object" in instruction_path.read_text(
        encoding="utf-8")
    assert "Nothing was activated" in out
    assert list(review_dir.glob("*.tmp")) == []
    assert list(review_dir.glob(".*.tmp")) == []


def test_immutable_evidence_registry_is_used_without_legacy_json(
        self_review_script, tmp_path):
    env = _env(tmp_path)
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(_profile())
    RevisionEvidenceRegistry(env["CED_SELF_REVISION_EVIDENCE_DIR"]).register(
        _evidence_record())

    assert self_review_script.main(["prog", AGENT], env=env) == 0
    snapshot = json.loads(
        (Path(env["CED_SELF_REVIEW_DIR"]) / f"{AGENT}.snapshot.json")
        .read_text(encoding="utf-8")
    )
    assert [row["reference"] for row in snapshot["verified_evidence"]] == [
        "trace/session-1"]


def test_registry_and_legacy_reference_conflict_fails_closed(
        self_review_script, tmp_path, capsys):
    env = _env(tmp_path)
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(_profile())
    RevisionEvidenceRegistry(env["CED_SELF_REVISION_EVIDENCE_DIR"]).register(
        _evidence_record())
    legacy = _manifest()
    legacy["trace/session-1"]["value"] = "conflicting value"
    Path(env["CED_SELF_REVISION_EVIDENCE"]).write_text(
        json.dumps(legacy), encoding="utf-8")

    assert self_review_script.main(["prog", AGENT], env=env) == 1
    assert "conflicts between registry" in capsys.readouterr().out
    assert not Path(env["CED_SELF_REVIEW_DIR"]).exists()


def test_pending_registry_proposal_is_visible_but_not_activated(
        self_review_script, tmp_path):
    env = _env(tmp_path)
    profile = _profile()
    proposal = _proposal()
    manifest = _manifest()
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(profile)
    Path(env["CED_SELF_REVISION_EVIDENCE"]).write_text(
        json.dumps(manifest), encoding="utf-8")
    snapshot = build_self_review_snapshot(
        profile, evidence_manifest=manifest)
    SelfRevisionRegistry(env["CED_SELF_REVISION_DIR"]).submit(
        proposal,
        snapshot=snapshot,
    )

    assert self_review_script.main(["prog", AGENT], env=env) == 0
    record = json.loads(
        (Path(env["CED_SELF_REVIEW_DIR"]) / f"{AGENT}.snapshot.json")
        .read_text(encoding="utf-8")
    )
    assert record["pending_proposal_ids"] == [proposal.proposal_id]
    loaded = IdentityRegistry(env["CED_IDENTITY_DIR"]).load_profile(AGENT)
    assert loaded.known_failures == ()
    assert loaded.revision_history == ()


def test_corrupt_evidence_manifest_fails_closed(
        self_review_script, tmp_path, capsys):
    env = _env(tmp_path)
    IdentityRegistry(env["CED_IDENTITY_DIR"]).save_profile(_profile())
    Path(env["CED_SELF_REVISION_EVIDENCE"]).write_text(
        "{not-json", encoding="utf-8")

    assert self_review_script.main(["prog", AGENT], env=env) == 1
    assert "Self-review refused" in capsys.readouterr().out
    assert not Path(env["CED_SELF_REVIEW_DIR"]).exists()

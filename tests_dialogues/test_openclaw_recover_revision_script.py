"""Operator tests for scripts/openclaw_recover_revision.py."""

import importlib.util
from pathlib import Path

import pytest

from backend.dialogues.openclaw_identity import (
    AgentIdentityProfile,
    IdentityRegistry,
    SelfRevisionProposal,
    SelfRevisionRegistry,
    SelfRevisionTransactionCoordinator,
    build_self_review_snapshot,
)

AGENT = "agent_alpha"
PROPOSAL = "REV-RECOVER-SCRIPT-1"
REFERENCE = "evidence/recover-script-1"


@pytest.fixture
def recover_script():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "openclaw_recover_revision.py"
    spec = importlib.util.spec_from_file_location(
        "openclaw_recover_revision_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _env(tmp_path):
    return {
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
        "CED_SELF_REVISION_DIR": str(tmp_path / "lifecycle"),
        "CED_SELF_REVISION_TRANSACTION_DIR": str(tmp_path / "transactions"),
    }


def _manifest():
    return {
        REFERENCE: {
            "verified": True,
            "agent_id": AGENT,
            "source": "trace-attribution",
            "supports": ["identity:add_known_failure"],
            "value": "rushes exact-output tasks",
            "verified_by": "evidence-harness",
            "verification_reference": "verification/recover-script-1",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }


def _prepare_interrupted(tmp_path):
    env = _env(tmp_path)
    profile = AgentIdentityProfile(agent_id=AGENT)
    proposal = SelfRevisionProposal(
        proposal_id=PROPOSAL,
        agent_id=AGENT,
        proposed_by=AGENT,
        target="identity",
        action="add_known_failure",
        value="rushes exact-output tasks",
        reason="Repeated attributed evidence supports this revision.",
        evidence_references=(REFERENCE,),
        risk="The evidence window may be narrow.",
    )
    manifest = _manifest()
    identity = IdentityRegistry(env["CED_IDENTITY_DIR"])
    lifecycle = SelfRevisionRegistry(env["CED_SELF_REVISION_DIR"])
    identity.save_profile(profile)
    lifecycle.submit(
        proposal,
        snapshot=build_self_review_snapshot(
            profile, evidence_manifest=manifest),
    )
    lifecycle.record_evaluation(
        AGENT,
        PROPOSAL,
        current_profile=profile,
        evidence_manifest=manifest,
        evaluated_by="evidence-harness",
    )
    lifecycle.record_decision(
        AGENT,
        PROPOSAL,
        current_profile=profile,
        evidence_manifest=manifest,
        decision="approved",
        decided_by="operator",
        decision_reference="review/recover-script-1",
    )

    class FailIdentity(IdentityRegistry):
        def save_profile(self, candidate):
            if candidate.revision_history:
                raise RuntimeError("simulated crash")
            return super().save_profile(candidate)

    coordinator = SelfRevisionTransactionCoordinator(
        FailIdentity(identity.directory),
        lifecycle,
        env["CED_SELF_REVISION_TRANSACTION_DIR"],
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        coordinator.apply_approved(
            AGENT,
            PROPOSAL,
            evidence_manifest=manifest,
            applied_by="operator",
            application_reference="identity/recover-script-1",
        )
    return env


def test_usage_requires_agent_and_proposal(recover_script, capsys):
    assert recover_script.main(["prog"], env={}) == 2
    assert "Usage:" in capsys.readouterr().out


def test_missing_transaction_is_reported(recover_script, tmp_path, capsys):
    assert recover_script.main(
        ["prog", AGENT, PROPOSAL], env=_env(tmp_path)) == 1
    assert "No transaction found" in capsys.readouterr().out


def test_command_recovers_prepared_transaction(
        recover_script, tmp_path, capsys):
    env = _prepare_interrupted(tmp_path)
    assert recover_script.main(["prog", AGENT, PROPOSAL], env=env) == 0
    out = capsys.readouterr().out
    assert "before      : prepared" in out
    assert "after       : committed" in out
    profile = IdentityRegistry(env["CED_IDENTITY_DIR"]).load_profile(AGENT)
    assert profile.known_failures == ("rushes exact-output tasks",)
    lifecycle = SelfRevisionRegistry(env["CED_SELF_REVISION_DIR"]).load(
        AGENT, PROPOSAL)
    assert lifecycle["status"] == "probationary"


def test_corrupt_journal_is_refused(recover_script, tmp_path, capsys):
    env = _prepare_interrupted(tmp_path)
    path = Path(env["CED_SELF_REVISION_TRANSACTION_DIR"]) / AGENT / \
        f"{PROPOSAL}.json"
    path.write_text("{not-json", encoding="utf-8")
    assert recover_script.main(["prog", AGENT, PROPOSAL], env=env) == 1
    assert "Recovery refused" in capsys.readouterr().out

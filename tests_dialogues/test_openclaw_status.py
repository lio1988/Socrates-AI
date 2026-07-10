"""
openclaw_status.py tests — the operator's joined-up view.

All offline: no cloud calls ever; the local-server probe fires ONLY when the
local gate is already ON, and tests inject it.
"""

import importlib.util
import json
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def status_script():
    spec = importlib.util.spec_from_file_location(
        "openclaw_status_script", _ROOT / "scripts" / "openclaw_status.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def shadow_script():
    spec = importlib.util.spec_from_file_location(
        "shadow_dialogue_for_status", _ROOT / "scripts" / "shadow_dialogue.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    monkeypatch.delenv("CED_ENABLE_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("CED_ENABLE_LOCAL_APPRENTICE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _env(tmp_path, **extra):
    env = {
        "CED_TRACE_DIR": str(tmp_path / "traces"),
        "CED_SHADOW_DIR": str(tmp_path / "shadow"),
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
        "CED_PROPOSALS_DIR": str(tmp_path / "proposals"),
        "CED_SELF_REVISION_DIR": str(tmp_path / "self_revisions"),
        "CED_SELF_REVISION_TRANSACTION_DIR": str(tmp_path / "transactions"),
    }
    env.update(extra)
    return env


def _no_probe(url, timeout):
    raise AssertionError("probe called although the local gate is OFF")


def test_empty_state_is_clean_and_offline(status_script, tmp_path, capsys):
    rc = status_script.main(["prog"], env=_env(tmp_path), probe=_no_probe)
    assert rc == 0
    out = capsys.readouterr().out
    assert "traces           : 0" in out
    assert "shadow records   : 0" in out
    assert "identity registry: empty" in out
    assert "self-revisions   : total=0" in out
    assert "registry binding : consistent" in out
    assert "transactions     : total=0" in out
    assert "shadow_dialogue.py" in out


def test_json_mode_is_machine_readable(status_script, tmp_path, capsys):
    rc = status_script.main(["prog", "--json"], env=_env(tmp_path),
                            probe=_no_probe)
    assert rc == 0
    status = json.loads(capsys.readouterr().out)
    for key in (
        "stable_lessons", "traces", "shadow_records", "identity",
        "proposals", "self_revisions", "revision_consistency",
        "revision_transactions", "gates", "local_server", "next_command",
    ):
        assert key in status
    assert status["self_revisions"] == {
        "count": 0,
        "by_status": {},
        "dir": str(tmp_path / "self_revisions"),
    }
    assert status["revision_consistency"] == {
        "consistent": True,
        "agents": [],
    }
    assert status["revision_transactions"] == {
        "count": 0,
        "by_state": {},
        "incomplete": [],
        "dir": str(tmp_path / "transactions"),
    }
    assert status["gates"]["local_apprentice"] is False
    assert status["local_server"] is None


def test_detects_accumulated_evidence(status_script, shadow_script, tmp_path,
                                      capsys):
    env = _env(tmp_path, CED_SHADOW_SESSIONS="2")
    shadow_script.main(["prog"], env=env)
    capsys.readouterr()
    status = status_script.collect_status(env, probe=_no_probe)
    assert status["shadow_records"]["count"] == 2
    assert status["identity"][0]["agent_id"] == "local_apprentice_001"
    assert status["identity"][0]["sessions_analyzed"] == 2
    assert status["identity"][0]["self_revisions_recorded"] == 0
    assert status["revision_consistency"]["consistent"] is True
    assert "openclaw_review" in status["next_command"]


def test_pending_proposals_change_the_next_command(status_script, tmp_path):
    from backend.dialogues.openclaw_memory import (
        propose_lessons, write_proposed_lessons)
    blocked = {"session_id": "s", "question": "q", "moves": [],
               "assembly": None,
               "ratification": {"ratified": False,
                                "ratification_status": "not_ratified"}}
    lessons = propose_lessons(
        [dict(blocked, session_id="s1"), dict(blocked, session_id="s2")])
    proposals_dir = tmp_path / "proposals"
    proposals_dir.mkdir(parents=True)
    write_proposed_lessons(lessons, proposals_dir / "PROPOSED_LESSONS.md")
    status = status_script.collect_status(_env(tmp_path), probe=_no_probe)
    assert status["proposals"]["lessons"] == len(lessons) > 0
    assert "review the proposal files" in status["next_command"]


def test_self_revision_lifecycle_outranks_collecting_more_data(
        status_script, tmp_path):
    from backend.dialogues.openclaw_identity import (
        AgentIdentityProfile,
        GovernedSelfRevisionRegistry,
        IdentityRegistry,
        SelfRevisionProposal,
        build_self_review_snapshot,
    )

    agent_id = "local_apprentice_001"
    profile = AgentIdentityProfile(agent_id=agent_id)
    proposal = SelfRevisionProposal(
        proposal_id="REV-STATUS-1",
        agent_id=agent_id,
        proposed_by=agent_id,
        target="identity",
        action="add_known_failure",
        value="rushes exact-output tasks",
        reason="Verified repeated pattern.",
        evidence_references=("trace/session-1",),
        risk="The evidence window may be narrow.",
    )
    manifest = {
        "trace/session-1": {
            "verified": True,
            "agent_id": agent_id,
            "source": "trace-harness",
            "supports": ["identity:add_known_failure"],
            "value": proposal.value,
            "verified_by": "evidence-harness",
            "verification_reference": "report/status-1",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }
    IdentityRegistry(tmp_path / "identity").save_profile(profile)
    snapshot = build_self_review_snapshot(profile, evidence_manifest=manifest)
    GovernedSelfRevisionRegistry(tmp_path / "self_revisions").submit(
        proposal, snapshot=snapshot)

    status = status_script.collect_status(_env(tmp_path), probe=_no_probe)
    assert status["self_revisions"]["count"] == 1
    assert status["self_revisions"]["by_status"] == {"submitted": 1}
    assert status["revision_consistency"]["consistent"] is True
    assert "review self-revision lifecycle" in status["next_command"]


def test_orphan_lifecycle_is_reported_before_more_self_review(
        status_script, tmp_path):
    from backend.dialogues.openclaw_identity import (
        AgentIdentityProfile,
        GovernedSelfRevisionRegistry,
        SelfRevisionProposal,
        build_self_review_snapshot,
    )

    agent_id = "orphan_agent"
    profile = AgentIdentityProfile(agent_id=agent_id)
    proposal = SelfRevisionProposal(
        proposal_id="REV-ORPHAN-1",
        agent_id=agent_id,
        proposed_by=agent_id,
        target="identity",
        action="add_known_failure",
        value="forgets constraints",
        reason="Verified repeated pattern.",
        evidence_references=("trace/orphan",),
        risk="Evidence may be incomplete.",
    )
    manifest = {
        "trace/orphan": {
            "verified": True,
            "agent_id": agent_id,
            "source": "trace-harness",
            "supports": ["identity:add_known_failure"],
            "value": proposal.value,
            "verified_by": "evidence-harness",
            "verification_reference": "report/orphan",
            "observed_on": "2026-07-10",
            "outcomes": [],
        }
    }
    GovernedSelfRevisionRegistry(tmp_path / "self_revisions").submit(
        proposal,
        snapshot=build_self_review_snapshot(profile, evidence_manifest=manifest),
    )

    status = status_script.collect_status(_env(tmp_path), probe=_no_probe)
    assert status["revision_consistency"]["consistent"] is False
    assert "identity profile is missing" in \
        status["revision_consistency"]["agents"][0]["issues"][0]
    assert "inspect identity/lifecycle consistency" in status["next_command"]


def test_probe_runs_only_with_gate_and_model(status_script, tmp_path):
    calls = []

    def probe(url, timeout):
        calls.append(url)
        return False, f"no local server at {url}"

    env = _env(tmp_path, CED_ENABLE_LOCAL_APPRENTICE="1",
               CED_LOCAL_LLM_MODEL="llama3.1:8b")
    status = status_script.collect_status(env, probe=probe)
    assert calls == ["http://localhost:11434/v1"]
    assert status["local_server"]["reachable"] is False
    assert "ollama serve" in status["next_command"]


def test_gate_without_model_does_not_probe(status_script, tmp_path):
    env = _env(tmp_path, CED_ENABLE_LOCAL_APPRENTICE="1")
    status = status_script.collect_status(env, probe=_no_probe)
    assert status["local_server"] is None
    assert status["gates"]["local_model"] is None

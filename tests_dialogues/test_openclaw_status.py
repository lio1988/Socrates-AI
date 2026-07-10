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
    env = {"CED_TRACE_DIR": str(tmp_path / "traces"),
           "CED_SHADOW_DIR": str(tmp_path / "shadow"),
           "CED_IDENTITY_DIR": str(tmp_path / "identity"),
           "CED_PROPOSALS_DIR": str(tmp_path / "proposals")}
    env.update(extra)
    return env


def _no_probe(url, timeout):                    # must never be called
    raise AssertionError("probe called although the local gate is OFF")


# --------------------------------------------------------------------------- #
# Empty state: clean report, sensible next command, no network
# --------------------------------------------------------------------------- #

def test_empty_state_is_clean_and_offline(status_script, tmp_path, capsys):
    rc = status_script.main(["prog"], env=_env(tmp_path), probe=_no_probe)
    assert rc == 0
    out = capsys.readouterr().out
    assert "traces           : 0" in out
    assert "shadow records   : 0" in out
    assert "identity registry: empty" in out
    assert "shadow_dialogue.py" in out          # next: collect first evidence


def test_json_mode_is_machine_readable(status_script, tmp_path, capsys):
    rc = status_script.main(["prog", "--json"], env=_env(tmp_path),
                            probe=_no_probe)
    assert rc == 0
    status = json.loads(capsys.readouterr().out)
    for key in ("stable_lessons", "traces", "shadow_records", "identity",
                "proposals", "gates", "local_server", "next_command"):
        assert key in status
    assert status["gates"]["local_apprentice"] is False
    assert status["local_server"] is None       # gate off -> no probe


# --------------------------------------------------------------------------- #
# Populated state: counts, identity snapshot, staged next command
# --------------------------------------------------------------------------- #

def test_detects_accumulated_evidence(status_script, shadow_script, tmp_path,
                                      capsys):
    env = _env(tmp_path, CED_SHADOW_SESSIONS="2")
    shadow_script.main(["prog"], env=env)
    capsys.readouterr()
    status = status_script.collect_status(env, probe=_no_probe)
    assert status["shadow_records"]["count"] == 2
    assert status["identity"][0]["agent_id"] == "local_apprentice_001"
    assert status["identity"][0]["sessions_analyzed"] == 2
    # Evidence exists but no proposals yet -> recommend the review step.
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


# --------------------------------------------------------------------------- #
# Local gate: probe only when ON, and a dead server drives the next command
# --------------------------------------------------------------------------- #

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

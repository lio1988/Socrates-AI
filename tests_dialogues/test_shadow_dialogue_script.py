"""
shadow_dialogue.py script tests — the operator flow for Stage 1.

All offline: demo mode (mock apprentice) or injected probes — no network,
no keys, no local server required.
"""

import importlib.util
import json
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location(
        "shadow_dialogue_script", _ROOT / "scripts" / "shadow_dialogue.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    monkeypatch.delenv("CED_ENABLE_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("CED_ENABLE_LOCAL_APPRENTICE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# --------------------------------------------------------------------------- #
# Apprentice resolution
# --------------------------------------------------------------------------- #

def test_no_gate_gives_free_demo_apprentice(script):
    adapter, mode, note = script._resolve_apprentice({})
    assert mode == "demo"
    assert adapter.provider_id == "local_apprentice_001"
    assert "CED_ENABLE_LOCAL_APPRENTICE" in note      # tells how to go real


def test_gate_without_model_stops_honestly(script):
    adapter, mode, note = script._resolve_apprentice(
        {"CED_ENABLE_LOCAL_APPRENTICE": "1"})
    assert adapter is None and mode == "local-unavailable"
    assert "CED_LOCAL_LLM_MODEL" in note


def test_gate_with_dead_server_stops_honestly(script):
    adapter, mode, note = script._resolve_apprentice(
        {"CED_ENABLE_LOCAL_APPRENTICE": "1",
         "CED_LOCAL_LLM_MODEL": "llama3.1:8b"},
        probe=lambda url, timeout: (False, f"no local server at {url}"))
    assert adapter is None and mode == "local-unavailable"
    assert "no local server" in note


def test_gate_with_live_server_gives_local_adapter(script):
    adapter, mode, note = script._resolve_apprentice(
        {"CED_ENABLE_LOCAL_APPRENTICE": "1",
         "CED_LOCAL_LLM_MODEL": "llama3.1:8b"},
        probe=lambda url, timeout: (True, "responding"))
    assert mode == "local"
    assert adapter.is_local is True
    assert adapter.provider_id == "local_apprentice_001"


# --------------------------------------------------------------------------- #
# Question batching
# --------------------------------------------------------------------------- #

def test_argv_question_wins(script):
    assert script._questions(["prog", "my q"], {}) == ["my q"]


def test_session_count_env(script):
    qs = script._questions(["prog"], {"CED_SHADOW_SESSIONS": "5"})
    assert len(qs) == 5
    assert script._questions(["prog"], {"CED_SHADOW_SESSIONS": "bad"}) \
        == script.DEFAULT_QUESTIONS[:3]


# --------------------------------------------------------------------------- #
# End-to-end demo run (free, deterministic)
# --------------------------------------------------------------------------- #

def test_main_demo_run_end_to_end(script, tmp_path, capsys):
    env = {
        "CED_SHADOW_SESSIONS": "2",
        "CED_SHADOW_DIR": str(tmp_path / "shadow"),
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
    }
    rc = script.main(["prog"], env=env)
    assert rc == 0
    out = capsys.readouterr().out
    assert "DEMO" in out
    assert "SOUL CARD" in out                        # identity is printed
    assert "gate gate_v0_3_to_v0_4" in out           # gate progress shown
    assert "earned evidence" in out

    # Marked shadow records were persisted and are bound to the exact council
    # synthesis ledger rather than a separate question-only retrieval.
    path = tmp_path / "shadow" / "shadow_records.jsonl"
    records = [json.loads(line) for line in
               path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert all(record["shadow_run"] is True for record in records)
    assert all(record["apprentice_id"] == "local_apprentice_001"
               for record in records)
    assert all(record["lesson_source"] == "council_injection_ledger"
               for record in records)
    assert all(record["lesson_ids"] for record in records)
    assert all(record["lessons_selected"] == len(record["lesson_ids"])
               for record in records)

    # The identity test stays inside tmp_path and never pollutes repository state.
    assert (tmp_path / "identity" / "local_apprentice_001.json").exists()


def test_main_stops_cleanly_when_local_unavailable(script, capsys):
    rc = script.main(["prog"], env={"CED_ENABLE_LOCAL_APPRENTICE": "1"})
    assert rc == 1
    out = capsys.readouterr().out
    assert "cannot run" in out
    assert "CED_LOCAL_LLM_MODEL" in out              # actionable instruction

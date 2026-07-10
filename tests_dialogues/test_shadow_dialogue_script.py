"""Offline tests for the Stage-1 Shadow Apprentice operator flow."""

import importlib.util
import json
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location(
        "shadow_dialogue_script", _ROOT / "scripts" / "shadow_dialogue.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    monkeypatch.delenv("CED_ENABLE_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("CED_ENABLE_LOCAL_APPRENTICE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_no_gate_gives_free_demo_apprentice(script):
    adapter, mode, note = script._resolve_apprentice({})
    assert mode == "demo"
    assert adapter.provider_id == "local_apprentice_001"
    assert "CED_ENABLE_LOCAL_APPRENTICE" in note


def test_gate_without_model_stops_honestly(script):
    adapter, mode, note = script._resolve_apprentice(
        {"CED_ENABLE_LOCAL_APPRENTICE": "1"})
    assert adapter is None and mode == "local-unavailable"
    assert "CED_LOCAL_LLM_MODEL" in note


def test_gate_with_dead_server_stops_honestly(script):
    adapter, mode, note = script._resolve_apprentice(
        {
            "CED_ENABLE_LOCAL_APPRENTICE": "1",
            "CED_LOCAL_LLM_MODEL": "llama3.1:8b",
        },
        probe=lambda url, timeout: (False, f"no local server at {url}"),
    )
    assert adapter is None and mode == "local-unavailable"
    assert "no local server" in note


def test_gate_with_live_server_gives_local_adapter(script):
    adapter, mode, note = script._resolve_apprentice(
        {
            "CED_ENABLE_LOCAL_APPRENTICE": "1",
            "CED_LOCAL_LLM_MODEL": "llama3.1:8b",
        },
        probe=lambda url, timeout: (True, "responding"),
    )
    assert mode == "local"
    assert adapter.is_local is True
    assert adapter.provider_id == "local_apprentice_001"


def test_argv_question_wins(script):
    assert script._questions(["prog", "my q"], {}) == ["my q"]


def test_session_count_env(script):
    questions = script._questions(["prog"], {"CED_SHADOW_SESSIONS": "5"})
    assert len(questions) == 5
    assert script._questions(
        ["prog"], {"CED_SHADOW_SESSIONS": "bad"}) \
        == script.DEFAULT_QUESTIONS[:3]


def test_batch_id_is_explicit_for_tests_and_random_by_default(script):
    assert script._batch_id({"CED_SHADOW_BATCH_ID": "batch-001"}) == \
        "batch-001"
    first = script._batch_id({})
    second = script._batch_id({})
    assert len(first) == 12 and len(second) == 12
    assert first != second


def test_invalid_batch_id_is_refused(script):
    with pytest.raises(ValueError, match="filesystem-safe"):
        script._batch_id({"CED_SHADOW_BATCH_ID": "not safe/id"})


def test_identity_records_follow_exact_gate_eligible_session_ids(script):
    records = [
        {"session_id": "eligible-a", "payload": 1},
        {"session_id": "duplicate", "payload": "first"},
        {"session_id": "duplicate", "payload": "replay"},
        {"session_id": "excluded", "payload": 2},
    ]
    evidence = {"shadow_session_ids": ["eligible-a", "duplicate"]}

    selected = script._identity_records_from_evidence(records, evidence)

    assert selected == [records[0], records[1]]


def test_main_demo_run_end_to_end(script, tmp_path, capsys):
    env = {
        "CED_SHADOW_SESSIONS": "2",
        "CED_SHADOW_BATCH_ID": "pytest-batch",
        "CED_SHADOW_DIR": str(tmp_path / "shadow"),
        "CED_IDENTITY_DIR": str(tmp_path / "identity"),
    }
    return_code = script.main(["prog"], env=env)
    assert return_code == 0
    output = capsys.readouterr().out
    assert "DEMO" in output
    assert "SOUL CARD" in output
    assert "gate gate_v0_3_to_v0_4" in output
    assert "earned evidence" in output
    assert "evidence id: pytest-batch" in output
    assert "eligible identity:" in output

    path = tmp_path / "shadow" / "shadow_records.jsonl"
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert [record["session_id"] for record in records] == [
        "shadow_dialogue_pytest-batch_0",
        "shadow_dialogue_pytest-batch_1",
    ]
    assert all(record["shadow_run"] is True for record in records)
    assert all(record["apprentice_id"] == "local_apprentice_001"
               for record in records)
    assert all(record["lesson_source"] == "council_injection_ledger"
               for record in records)
    assert all(record["lesson_ids"] for record in records)
    assert all(record["lessons_selected"] == len(record["lesson_ids"])
               for record in records)
    assert (tmp_path / "identity" / "local_apprentice_001.json").exists()


def test_main_stops_cleanly_when_local_unavailable(script, capsys):
    return_code = script.main(
        ["prog"], env={"CED_ENABLE_LOCAL_APPRENTICE": "1"})
    assert return_code == 1
    output = capsys.readouterr().out
    assert "cannot run" in output
    assert "CED_LOCAL_LLM_MODEL" in output

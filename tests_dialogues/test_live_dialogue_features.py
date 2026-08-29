"""
live_dialogue.py feature wiring tests (the meta-gap: the script users actually
run must activate the built layers — lessons, trace capture, tree search).

All offline: mock mode only (no gates set), no network, no keys.
"""

import importlib.util
import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def live_dialogue():
    spec = importlib.util.spec_from_file_location(
        "live_dialogue_script", _ROOT / "scripts" / "live_dialogue.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    """Force mock mode no matter what the host environment has."""
    monkeypatch.delenv("CED_ENABLE_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("CED_PROVIDER_FAMILIES", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CED_TRACE_INCLUDE_CONTENT", raising=False)


# --------------------------------------------------------------------------- #
# _resolve_features: env switches
# --------------------------------------------------------------------------- #

def test_defaults_lessons_and_trace_on_tree_off(live_dialogue):
    features, notes = live_dialogue._resolve_features({})
    assert "openclaw_lessons" in features
    assert len(features["openclaw_lessons"]) > 0
    assert "trace_capturer" in features
    assert features["trace_capturer"].include_content is False
    assert "tree_expansions" not in features          # costs calls -> opt-in
    joined = " | ".join(notes)
    assert "lessons:" in joined and "trace:" in joined and "tree: off" in joined
    assert "trace content: off" in joined


def test_trace_content_opt_in(live_dialogue):
    features, notes = live_dialogue._resolve_features({
        "CED_TRACE_INCLUDE_CONTENT": "1",
    })
    assert features["trace_capturer"].include_content is True
    assert "trace content: on" in notes


def test_trace_content_zero_is_off(live_dialogue):
    features, notes = live_dialogue._resolve_features({
        "CED_TRACE_INCLUDE_CONTENT": "0",
    })
    assert features["trace_capturer"].include_content is False
    assert "trace content: off" in notes


def test_off_switches(live_dialogue):
    features, notes = live_dialogue._resolve_features({
        "CED_OPENCLAW_LESSONS": "0",
        "CED_TRACE_CAPTURE": "0",
        "CED_TRACE_INCLUDE_CONTENT": "1",
    })
    assert "openclaw_lessons" not in features
    assert "trace_capturer" not in features
    joined = " | ".join(notes)
    assert "lessons: off" in joined and "trace: off" in joined
    assert "trace content: off" in joined


def test_tree_expansions_env(live_dialogue):
    features, notes = live_dialogue._resolve_features({"CED_TREE_EXPANSIONS": "2"})
    assert features["tree_expansions"] == 2
    assert any("tree: 2 expansions" in n for n in notes)


def test_tree_expansions_invalid_is_off(live_dialogue):
    features, _ = live_dialogue._resolve_features({"CED_TREE_EXPANSIONS": "abc"})
    assert "tree_expansions" not in features


def test_trace_dir_override(live_dialogue, tmp_path):
    features, _ = live_dialogue._resolve_features(
        {"CED_TRACE_DIR": str(tmp_path / "mytraces")})
    assert str(features["trace_capturer"].output_dir).endswith("mytraces")


# --------------------------------------------------------------------------- #
# main(): full mock run proves the wiring end-to-end
# --------------------------------------------------------------------------- #

def test_main_mock_run_writes_trace_with_lessons(live_dialogue, tmp_path,
                                                 monkeypatch, capsys):
    monkeypatch.setenv("CED_TRACE_DIR", str(tmp_path / "traces"))
    rc = live_dialogue.main(["live_dialogue.py", "deliberation scoring assembly"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MOCK" in out                       # never accidentally live in tests
    assert "features :" in out
    trace_file = tmp_path / "traces" / "live_dialogue.jsonl"
    assert trace_file.exists()
    trace = json.loads(trace_file.read_text(encoding="utf-8").splitlines()[0])
    assert trace["session_id"] == "live_dialogue"
    assert all("content" not in move and "content_keys" in move
               for move in trace["moves"])
    # Lessons flowed end-to-end: the audit-fed trace names selected lesson ids.
    assert len(trace["selected_openclaw_lessons"]) > 0
    # And the operator summary reported them.
    assert "openclaw lessons :" in out
    assert "trace content: off" in out


def test_main_mock_run_can_include_public_move_content(live_dialogue, tmp_path,
                                                       monkeypatch, capsys):
    monkeypatch.setenv("CED_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("CED_TRACE_INCLUDE_CONTENT", "1")
    rc = live_dialogue.main(["live_dialogue.py", "public trace content"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MOCK" in out
    assert "trace content: on" in out
    trace = json.loads((tmp_path / "traces" / "live_dialogue.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])
    assert trace["moves"]
    assert all("content" in move and "content_keys" not in move
               for move in trace["moves"])
    assert any(move["content"] for move in trace["moves"])


def test_main_mock_run_with_tree(live_dialogue, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CED_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("CED_TREE_EXPANSIONS", "1")
    rc = live_dialogue.main(["live_dialogue.py", "test"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tree search      :" in out
    trace = json.loads((tmp_path / "traces" / "live_dialogue.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])
    kinds = {m.get("task_kind") for m in trace["moves"]}
    assert "tree_revision" in kinds            # the tree really ran


def test_main_all_features_off_still_runs(live_dialogue, monkeypatch, capsys):
    monkeypatch.setenv("CED_OPENCLAW_LESSONS", "0")
    monkeypatch.setenv("CED_TRACE_CAPTURE", "0")
    rc = live_dialogue.main(["live_dialogue.py", "test"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "lessons: off | trace: off | trace content: off | tree: off" in out
    assert "openclaw lessons :" not in out
    assert "trace            :" not in out

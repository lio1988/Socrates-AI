"""Micro-Socratic Kernel v1 — operator CLI (offline, mock adapter)."""

import importlib.util
import json
import pathlib

import pytest

from backend.dialogues.openclaw_socratic_kernel import (
    MicroSocraticCheck,
    verify_receipt,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_FIXED_NOW = "2026-07-11T00:00:00Z"


@pytest.fixture(scope="module")
def check_script():
    spec = importlib.util.spec_from_file_location(
        "openclaw_micro_socratic_check_script",
        _ROOT / "scripts" / "openclaw_micro_socratic_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def _env():
    return {"CED_MICRO_SOCRATIC_NOW": _FIXED_NOW}


def _argv(tmp_path, output, mode="standard"):
    task = _write(tmp_path / "task.txt", "Prove the routine is idempotent.")
    draft = _write(tmp_path / "draft.txt", "It is idempotent under retries.")
    return ["prog", "--agent", "local_apprentice_001", "--mode", mode,
            "--provider", "mock", "--model", "mock-auditor",
            "--task-file", str(task), "--draft-file", str(draft),
            "--output", str(output)]


def test_standard_run_writes_check_and_receipt(check_script, tmp_path, capsys):
    output = tmp_path / "out" / "check.json"
    rc = check_script.main(_argv(tmp_path, output), env=_env())
    assert rc == 0
    check = MicroSocraticCheck.from_record(
        json.loads(output.read_text(encoding="utf-8")))
    assert check.mode == "standard"
    assert check.isolated_check and not check.tools_executed \
        and not check.consultation_executed
    receipts = list((tmp_path / "out").glob("*.receipt.json"))
    assert len(receipts) == 1
    verify_receipt(json.loads(receipts[0].read_text(encoding="utf-8")))
    out = capsys.readouterr().out
    assert "Recommendation only" in out and "may not" in out


def test_light_and_high_risk_runs(check_script, tmp_path):
    for mode in ("light", "high_risk"):
        output = tmp_path / mode / "check.json"
        rc = check_script.main(_argv(tmp_path, output, mode=mode), env=_env())
        assert rc == 0
        check = MicroSocraticCheck.from_record(
            json.loads(output.read_text(encoding="utf-8")))
        assert check.mode == mode


def test_exact_rerun_is_idempotent(check_script, tmp_path):
    output = tmp_path / "out" / "check.json"
    argv = _argv(tmp_path, output)
    assert check_script.main(argv, env=_env()) == 0
    first = output.read_text(encoding="utf-8")
    assert check_script.main(argv, env=_env()) == 0
    assert output.read_text(encoding="utf-8") == first


def test_writes_only_check_and_receipt(check_script, tmp_path):
    output = tmp_path / "out" / "check.json"
    check_script.main(_argv(tmp_path, output), env=_env())
    names = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert output.name in names
    assert sum(n.endswith(".receipt.json") for n in names) == 1
    assert len(names) == 2


def test_non_mock_provider_refused(check_script, tmp_path, capsys):
    task = _write(tmp_path / "task.txt", "anything")
    draft = _write(tmp_path / "draft.txt", "anything")
    output = tmp_path / "out" / "check.json"
    rc = check_script.main(
        ["prog", "--agent", "a", "--mode", "standard", "--provider",
         "anthropic", "--model", "claude", "--task-file", str(task),
         "--draft-file", str(draft), "--output", str(output)], env=_env())
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not output.exists()


def test_missing_args_shows_usage(check_script, capsys):
    assert check_script.main(["prog", "--mode", "standard"], env=_env()) == 1
    assert "usage:" in capsys.readouterr().out


def test_hostile_request_id_refused(check_script, tmp_path, capsys):
    task = _write(tmp_path / "task.txt", "solve")
    draft = _write(tmp_path / "draft.txt", "draft")
    output = tmp_path / "out" / "check.json"
    rc = check_script.main(
        ["prog", "--agent", "a", "--mode", "light", "--provider", "mock",
         "--model", "m", "--request-id", "../../pwned", "--task-file",
         str(task), "--draft-file", str(draft), "--output", str(output)],
        env=_env())
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not (tmp_path / "pwned.receipt.json").exists()

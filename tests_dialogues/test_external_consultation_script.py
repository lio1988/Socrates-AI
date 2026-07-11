"""External Self-Consultation v1 — operator CLI (offline, mock adapter).

The script performs exactly one deterministic mock call, writes a result and a
tamper-evident receipt, activates no live provider, and mutates no agent or
governance state. Under CED_CONSULTATION_NOW it is fully deterministic, so an
exact rerun is idempotent.
"""

import importlib.util
import json
import pathlib

import pytest

from backend.dialogues.openclaw_consultation import (
    ConsultationResult,
    verify_receipt,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_FIXED_NOW = "2026-07-11T00:00:00Z"


@pytest.fixture(scope="module")
def consult_script():
    spec = importlib.util.spec_from_file_location(
        "openclaw_external_consult_script",
        _ROOT / "scripts" / "openclaw_external_consult.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.write_text(text, encoding="utf-8")
    return path


def _env():
    return {"CED_CONSULTATION_NOW": _FIXED_NOW}


def _critic_argv(tmp_path, output):
    question = _write(tmp_path / "question.txt",
                      "Review this solution and find the top logical gaps.")
    draft = _write(tmp_path / "draft.txt", "My draft answer with two steps.")
    return ["prog", "--mode", "critic", "--agent", "local_apprentice_001",
            "--provider", "mock", "--model", "mock-critic",
            "--question-file", str(question), "--draft-file", str(draft),
            "--output", str(output)]


# --------------------------------------------------------------------------- #
# happy paths write valid result + receipt
# --------------------------------------------------------------------------- #

def test_critic_run_writes_result_and_receipt(consult_script, tmp_path, capsys):
    output = tmp_path / "out" / "critic-result.json"
    rc = consult_script.main(_critic_argv(tmp_path, output), env=_env())
    assert rc == 0
    result = ConsultationResult.from_record(
        json.loads(output.read_text(encoding="utf-8")))
    assert result.mode == "critic"
    assert result.isolated_session and result.tools_disabled \
        and result.delegation_disabled
    receipts = list((tmp_path / "out").glob("*.receipt.json"))
    assert len(receipts) == 1
    receipt = verify_receipt(json.loads(receipts[0].read_text(encoding="utf-8")))
    assert receipt["request_digest"] == result.request_digest
    assert "Advice only" in capsys.readouterr().out


def test_independent_solver_run_needs_no_draft(consult_script, tmp_path):
    question = _write(tmp_path / "q.txt", "Solve this independently, please.")
    output = tmp_path / "out" / "solver-result.json"
    rc = consult_script.main(
        ["prog", "--mode", "independent_solver", "--agent",
         "local_apprentice_001", "--provider", "mock", "--model",
         "mock-solver", "--question-file", str(question),
         "--output", str(output)], env=_env())
    assert rc == 0
    result = ConsultationResult.from_record(
        json.loads(output.read_text(encoding="utf-8")))
    assert "independent_answer" in result.structured_payload


def test_judge_run_with_two_candidates(consult_script, tmp_path):
    question = _write(tmp_path / "q.txt", "Which candidate is stronger and why?")
    a = _write(tmp_path / "a.txt", "Candidate one body.")
    b = _write(tmp_path / "b.txt", "Candidate two body.")
    output = tmp_path / "out" / "judge-result.json"
    rc = consult_script.main(
        ["prog", "--mode", "judge", "--agent", "local_apprentice_001",
         "--provider", "mock", "--model", "mock-judge",
         "--question-file", str(question),
         "--candidate-file", str(a), "--candidate-file", str(b),
         "--output", str(output)], env=_env())
    assert rc == 0
    result = ConsultationResult.from_record(
        json.loads(output.read_text(encoding="utf-8")))
    assert result.structured_payload["verdict"] in (
        "candidate_a", "candidate_b", "tie", "insufficient_evidence")


# --------------------------------------------------------------------------- #
# determinism, idempotency, no stray state
# --------------------------------------------------------------------------- #

def test_exact_rerun_is_idempotent(consult_script, tmp_path):
    output = tmp_path / "out" / "critic-result.json"
    argv = _critic_argv(tmp_path, output)
    assert consult_script.main(argv, env=_env()) == 0
    first = output.read_text(encoding="utf-8")
    receipt_first = next((tmp_path / "out").glob("*.receipt.json")).read_text(
        encoding="utf-8")
    # Rerun: same fixed clock => identical digests => store accepts idempotently.
    assert consult_script.main(argv, env=_env()) == 0
    assert output.read_text(encoding="utf-8") == first
    assert next((tmp_path / "out").glob("*.receipt.json")).read_text(
        encoding="utf-8") == receipt_first


def test_run_writes_only_result_and_receipt(consult_script, tmp_path):
    output = tmp_path / "out" / "critic-result.json"
    consult_script.main(_critic_argv(tmp_path, output), env=_env())
    written = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert output.name in written
    assert sum(name.endswith(".receipt.json") for name in written) == 1
    # Nothing else — no identity/memory/proposal/trace artifacts anywhere.
    assert len(written) == 2


# --------------------------------------------------------------------------- #
# refusals
# --------------------------------------------------------------------------- #

def test_non_mock_provider_refused(consult_script, tmp_path, capsys):
    question = _write(tmp_path / "q.txt", "Anything.")
    output = tmp_path / "out" / "r.json"
    rc = consult_script.main(
        ["prog", "--mode", "independent_solver", "--agent", "a",
         "--provider", "anthropic", "--model", "claude", "--question-file",
         str(question), "--output", str(output)], env=_env())
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not output.exists()


def test_missing_required_args_shows_usage(consult_script, capsys):
    rc = consult_script.main(["prog", "--mode", "critic"], env=_env())
    assert rc == 1
    assert "usage:" in capsys.readouterr().out


def test_secret_shaped_question_refused(consult_script, tmp_path, capsys):
    question = _write(tmp_path / "q.txt",
                      "Use api_key = sk-ant-abcd1234efgh5678 to verify.")
    output = tmp_path / "out" / "r.json"
    rc = consult_script.main(
        ["prog", "--mode", "independent_solver", "--agent", "a",
         "--provider", "mock", "--model", "mock-solver", "--question-file",
         str(question), "--output", str(output)], env=_env())
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().out

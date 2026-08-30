"""Offline interaction tests for ``py -3.12 -m socrates``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import socrates.__main__ as cli
from socrates.rendering import NormalRenderResult
from socrates.runtime import NormalAuthorizationError


PICODOLLARS_PER_USD = 1_000_000_000_000


def _preflight(*, admitted: bool = True):
    seats = tuple(
        SimpleNamespace(alias=alias, model_id=model)
        for alias, model in (
            ("Alpha", "openai/gpt-5-mini"),
            ("Beta", "google/gemini-3.7-flash"),
            ("Gamma", "openai/gpt-4.1-mini"),
        )
    )
    plan = SimpleNamespace(
        seats=seats,
        base_call_count=115,
        retry_call_count=20,
        maximum_call_count=135,
    )
    return SimpleNamespace(
        call_plan=plan,
        cost=SimpleNamespace(maximum_cost_picodollars=24 * PICODOLLARS_PER_USD),
        standing_cap_picodollars=(
            (25 if admitted else 20) * PICODOLLARS_PER_USD
        ),
        admitted_by_standing_cap=admitted,
    )


def _scripted_input(*responses: str):
    remaining = iter(responses)
    prompts = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(remaining)

    return read, prompts


def _never_runtime(*_args, **_kwargs):
    raise AssertionError("a live runtime must not be constructed by an offline CLI test")


def test_preflight_shows_exact_council_call_ceiling_and_cost_before_decline(
    monkeypatch,
) -> None:
    monkeypatch.setattr(cli, "prepare", lambda question: _preflight())

    async def forbidden_execute(*_args, **_kwargs):
        raise AssertionError("declining must not call execute")

    monkeypatch.setattr(cli, "execute", forbidden_execute)
    read, prompts = _scripted_input("What is justice?", "n")
    lines = []

    code = cli.main(
        [], input_fn=read, output_fn=lines.append, runtime_factory=_never_runtime
    )

    assert code == 0
    assert prompts == [
        "Ask Socrates: ",
        "Authorize this live run? [Y/YES to proceed]: ",
    ]
    text = "\n".join(lines)
    assert "============================================================\nSOCRATES" in text
    assert "FULL council: YES" in text
    assert "Alpha: openai/gpt-5-mini" in text
    assert "Beta: google/gemini-3.7-flash" in text
    assert "Gamma: openai/gpt-4.1-mini" in text
    assert "115 base + 20 possible same-seat retries = 135" in text
    assert "Conservative maximum cost: $24" in text
    assert "Configured standing cap: $25" in text
    assert "Cancelled; no live runtime was created." in text


def test_over_cap_blocks_before_confirmation_execute_or_runtime_factory(
    monkeypatch,
) -> None:
    monkeypatch.setattr(cli, "prepare", lambda question: _preflight(admitted=False))

    async def forbidden_execute(*_args, **_kwargs):
        raise AssertionError("an over-cap preflight must not call execute")

    monkeypatch.setattr(cli, "execute", forbidden_execute)
    read, prompts = _scripted_input("Should this run?")
    lines = []

    code = cli.main(
        [], input_fn=read, output_fn=lines.append, runtime_factory=_never_runtime
    )

    assert code == 2
    assert prompts == ["Ask Socrates: "]
    assert "Configured standing cap: $20" in "\n".join(lines)
    assert "no live runtime was created" in "\n".join(lines)


@pytest.mark.parametrize("confirmation", ["y", "Y", "yes", "YeS", " yes "])
def test_only_exact_case_insensitive_y_or_yes_executes(
    monkeypatch, tmp_path: Path, confirmation: str
) -> None:
    preflight = _preflight()
    monkeypatch.setattr(cli, "prepare", lambda question: preflight)
    sentinel_factory = object()
    captured = {}
    render = NormalRenderResult(
        outcome="release_unresolved",
        release_decision="release_unresolved",
        governing_epistemic_status="unresolved",
        public_answer="A safe governing answer.",
        notice="WARNING: finite unresolved notice.",
        candidate_authorized=True,
        candidate="INTERNAL CANDIDATE MUST NOT BE PRINTED",
    )

    async def fake_execute(
        given_preflight,
        *,
        confirmed,
        runtime_factory,
        run_root,
        progress,
    ):
        captured.update(
            preflight=given_preflight,
            confirmed=confirmed,
            runtime_factory=runtime_factory,
            run_root=run_root,
        )
        progress("Opening")
        progress("Governing release")
        return SimpleNamespace(
            render=render,
            artifact_path=tmp_path / "normal_test" / "result.json",
        )

    monkeypatch.setattr(cli, "execute", fake_execute)
    read, _prompts = _scripted_input("Question", confirmation)
    lines = []

    code = cli.main(
        [],
        input_fn=read,
        output_fn=lines.append,
        runtime_factory=sentinel_factory,
        run_root=tmp_path,
    )

    assert code == 0
    assert captured == {
        "preflight": preflight,
        "confirmed": True,
        "runtime_factory": sentinel_factory,
        "run_root": tmp_path,
    }
    text = "\n".join(lines)
    assert "[Opening]" in text
    assert "[Governing release]" in text
    assert "WARNING: finite unresolved notice." in text
    assert "A safe governing answer." in text
    assert "INTERNAL CANDIDATE" not in text
    assert f"Artifact: {tmp_path / 'normal_test' / 'result.json'}" in text


@pytest.mark.parametrize("confirmation", ["", "n", "no", "yeah", "y please"])
def test_all_other_confirmation_text_declines(monkeypatch, confirmation: str) -> None:
    monkeypatch.setattr(cli, "prepare", lambda question: _preflight())

    async def forbidden_execute(*_args, **_kwargs):
        raise AssertionError("non-Y/YES confirmation must not call execute")

    monkeypatch.setattr(cli, "execute", forbidden_execute)
    read, _prompts = _scripted_input("Question", confirmation)

    assert cli.main([], input_fn=read, output_fn=lambda _line: None) == 0


def test_blank_question_is_reprompted_and_never_preflighted(monkeypatch) -> None:
    seen_questions = []

    def fake_prepare(question):
        seen_questions.append(question)
        return _preflight()

    monkeypatch.setattr(cli, "prepare", fake_prepare)
    read, prompts = _scripted_input("   ", "A real question", "N")
    lines = []

    code = cli.main([], input_fn=read, output_fn=lines.append)

    assert code == 0
    assert seen_questions == ["A real question"]
    assert prompts[:2] == ["Ask Socrates: ", "Ask Socrates: "]
    assert "Please enter a nonblank question." in lines


def test_preflight_authorization_error_blocks_without_confirmation(monkeypatch) -> None:
    def blocked_prepare(_question):
        raise NormalAuthorizationError("configured cap is invalid")

    monkeypatch.setattr(cli, "prepare", blocked_prepare)
    read, prompts = _scripted_input("Question")
    lines = []

    code = cli.main(
        [], input_fn=read, output_fn=lines.append, runtime_factory=_never_runtime
    )

    assert code == 2
    assert prompts == ["Ask Socrates: "]
    assert lines[-1] == "BLOCKED: configured cap is invalid"


def test_unexpected_preflight_error_uses_only_a_finite_public_code(monkeypatch) -> None:
    def broken_prepare(_question):
        raise ValueError("Bearer FAKE-NOT-A-REAL-TRACE-SECRET at C:\\private")

    monkeypatch.setattr(cli, "prepare", broken_prepare)
    read, _prompts = _scripted_input("Question")
    lines = []

    code = cli.main([], input_fn=read, output_fn=lines.append)

    assert code == 1
    assert lines[-1] == "ERROR: orchestration:ValueError"
    assert "FAKE-NOT-A-REAL-TRACE-SECRET" not in "\n".join(lines)
    assert "C:\\private" not in "\n".join(lines)

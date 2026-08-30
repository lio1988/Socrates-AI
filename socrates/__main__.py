"""Interactive command-line entry point for ordinary Normal Socrates runs."""

from __future__ import annotations

import argparse
import asyncio

from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    safe_public_exception_code_v1,
)

from .runtime import (
    DEFAULT_RUN_ROOT,
    NormalAuthorizationError,
    NormalSocratesError,
    execute,
    picodollars_to_usd_text,
    prepare,
)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="py -3.12 -m socrates",
        description=(
            "Ask one arbitrary question of the full canonical Normal Socrates "
            "council. The live run starts only after cost preflight and explicit "
            "confirmation."
        ),
    )


def _read_question(input_fn, output_fn):
    while True:
        try:
            question = input_fn("Ask Socrates: ")
        except (EOFError, KeyboardInterrupt):
            output_fn("Cancelled before preflight.")
            return None
        if isinstance(question, str) and question.strip():
            return question
        output_fn("Please enter a nonblank question.")


def _show_preflight(preflight, output_fn) -> None:
    plan = preflight.call_plan
    output_fn("")
    output_fn("Normal Socrates preflight")
    output_fn("FULL council: YES")
    output_fn("Council models:")
    for seat in plan.seats:
        output_fn(f"  {seat.alias}: {seat.model_id}")
    output_fn(
        "Calls: "
        f"{plan.base_call_count} base + "
        f"{plan.retry_call_count} possible same-seat retries = "
        f"{plan.maximum_call_count} conservative maximum"
    )
    output_fn(
        "Conservative maximum cost: $"
        f"{picodollars_to_usd_text(preflight.cost.maximum_cost_picodollars)}"
    )
    output_fn(
        "Configured standing cap: $"
        f"{picodollars_to_usd_text(preflight.standing_cap_picodollars)}"
    )


def _show_result(result, output_fn) -> None:
    rendered = result.render
    if rendered.notice:
        output_fn("")
        output_fn("GOVERNING NOTICE:")
        output_fn(rendered.notice)
    if rendered.public_answer:
        output_fn("")
        output_fn("SOCRATES:")
        output_fn(rendered.public_answer)
    elif not rendered.notice:
        output_fn("")
        output_fn("No public answer was authorized by the governing release.")
    output_fn("")
    output_fn(f"Artifact: {result.artifact_path}")


def main(
    argv=None,
    input_fn=input,
    output_fn=print,
    runtime_factory=None,
    run_root=DEFAULT_RUN_ROOT,
) -> int:
    """Run the interactive Normal boundary with injectable offline test seams."""

    _parser().parse_args(argv)
    output_fn("=" * 60)
    output_fn("SOCRATES")
    output_fn("=" * 60)

    question = _read_question(input_fn, output_fn)
    if question is None:
        return 130

    try:
        preflight = prepare(question)
    except NormalAuthorizationError as exc:
        output_fn(f"BLOCKED: {exc}")
        return 2
    except NormalSocratesError as exc:
        output_fn(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        output_fn(
            "ERROR: "
            + safe_public_exception_code_v1(exc, context="orchestration")
        )
        return 1

    try:
        _show_preflight(preflight, output_fn)
    except Exception as exc:
        output_fn(
            "ERROR: "
            + safe_public_exception_code_v1(exc, context="orchestration")
        )
        return 1
    if not preflight.admitted_by_standing_cap:
        output_fn(
            "BLOCKED: conservative maximum exceeds the configured standing cap; "
            "no live runtime was created."
        )
        return 2

    try:
        confirmation = input_fn("Authorize this live run? [Y/YES to proceed]: ")
    except (EOFError, KeyboardInterrupt):
        output_fn("Cancelled before execution; no live runtime was created.")
        return 130
    if not isinstance(confirmation, str) or confirmation.strip().casefold() not in {
        "y",
        "yes",
    }:
        output_fn("Cancelled; no live runtime was created.")
        return 0

    output_fn("Starting the full canonical council...")

    def progress(label: str) -> None:
        output_fn(f"[{label}]")

    try:
        result = asyncio.run(
            execute(
                preflight,
                confirmed=True,
                runtime_factory=runtime_factory,
                run_root=run_root,
                progress=progress,
            )
        )
    except KeyboardInterrupt:
        output_fn("Interrupted before Normal Socrates completed.")
        return 130
    except NormalAuthorizationError as exc:
        output_fn(f"BLOCKED: {exc}")
        return 2
    except NormalSocratesError as exc:
        output_fn(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        output_fn(
            "ERROR: "
            + safe_public_exception_code_v1(exc, context="orchestration")
        )
        return 1

    try:
        _show_result(result, output_fn)
        if getattr(result, "error_code", None):
            output_fn(f"ERROR: {result.error_code}")
            return 1
        return 0
    except Exception as exc:
        output_fn(
            "ERROR: "
            + safe_public_exception_code_v1(exc, context="orchestration")
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

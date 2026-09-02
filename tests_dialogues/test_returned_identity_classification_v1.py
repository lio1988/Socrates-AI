"""An unattributable response and a wrongly attributed one are not one event.

One live run stopped on an HTTP 200 whose body carried a top-level ``error``
and no ``model``. The artifact preserved two ``False`` flags and the name
``returned_model_identity_mismatch``, which reads as "a different model came
back" — and that cost a full source audit to disprove. These tests pin the
distinction, pin the diagnostics that make it readable, and pin the thing that
must not change: every verdict below is still fatal.
"""

from __future__ import annotations

import json

import pytest

from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    RETURNED_IDENTITY_ABSENT_FAILURE_V1,
    RETURNED_IDENTITY_FATAL_FAILURES_V1,
    RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1,
    execute_bounded_text_turn_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_MAX_INPUT_TOKENS_V1,
    REDUCED_MODEL_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
)
from socrates import runtime as normal_runtime
from socrates.rendering import public_session_stop_notice
from tests_dialogues.test_socrates_zero_openrouter_acquisition_reduced_benchmark_safety_v1 import (  # noqa: E501
    _Result,
    _ledger,
    _schema,
    _success_bytes,
    _turn,
)


def _error_envelope_bytes(
    *, code: int = 429, message: str = "upstream refused"
) -> bytes:
    """An OpenRouter error delivered inside HTTP 200.

    A top-level ``error`` and no top-level ``model``: no served model, no
    provider, no usage, no choices. This is the exact shape the live incident
    produced, and the mapper accepts it as a well-formed ERROR envelope.
    """
    return json.dumps(
        {"error": {"code": code, "message": message}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


_counter = [0]


def _run_turn(body: bytes, tmp_path):
    """One isolated turn.

    Each call gets its own claim directory and turn id: the claim store burns a
    turn exactly once and refuses a repeat, which is correct behaviour and not
    something a test should be sharing state across.
    """
    _counter[0] += 1
    policy, profile, ledger = _ledger()
    outcome = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path / f"claims-{_counter[0]}",
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn(turn_id=f"turn-{_counter[0]}"),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=lambda **_kwargs: _Result(body),
    )
    return outcome, ledger


# ------------------------------------------------------------ classification --


def test_error_envelope_is_absent_identity_not_a_mismatch(tmp_path) -> None:
    outcome, ledger = _run_turn(_error_envelope_bytes(), tmp_path)

    assert outcome.failure_reason == RETURNED_IDENTITY_ABSENT_FAILURE_V1
    assert outcome.record.failure_class == RETURNED_IDENTITY_ABSENT_FAILURE_V1
    # The old name is precisely what this run must no longer be called.
    assert outcome.record.failure_class != "returned_model_identity_mismatch"
    assert outcome.record.returned_model_binding_ok is False
    assert outcome.record.returned_provider_binding_ok is False
    # Absent, not wrong: neither "unrecognized" sentinel is written.
    assert outcome.record.actual_served_model is None
    assert outcome.record.provider_display_name is None
    # Fail-closed is unchanged.
    assert ledger.fatal_failure == RETURNED_IDENTITY_ABSENT_FAILURE_V1
    assert outcome.assistant_text is None


def test_both_identities_wrong_is_its_own_verdict(tmp_path) -> None:
    outcome, ledger = _run_turn(
        _success_bytes(model="openai/gpt-5", provider="Azure"), tmp_path
    )

    assert outcome.failure_reason == RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1
    assert outcome.record.returned_model_binding_ok is False
    assert outcome.record.returned_provider_binding_ok is False
    # Present but wrong: both sentinels are written, which is how a reader tells
    # this case from the absent one without leaving the artifact.
    assert outcome.record.actual_served_model == "unrecognized_model"
    assert outcome.record.provider_display_name == "unrecognized_provider"
    assert ledger.fatal_failure == RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1


@pytest.mark.parametrize(
    "model, provider, expected",
    [
        ("openai/gpt-5", "OpenAI", "returned_model_identity_mismatch"),
        (REDUCED_MODEL_V1, "Azure", "returned_provider_identity_mismatch"),
    ],
)
def test_single_field_mismatches_keep_their_existing_names(
    tmp_path, model, provider, expected
) -> None:
    """Renaming these would churn a vocabulary two benchmark scripts share.

    The audit's finding was about absence, not about these two, so they stay.
    """
    outcome, ledger = _run_turn(
        _success_bytes(model=model, provider=provider), tmp_path
    )
    assert outcome.failure_reason == expected
    assert ledger.fatal_failure == expected


def test_every_identity_verdict_still_trips_the_fatal_latch(tmp_path) -> None:
    bodies = {
        RETURNED_IDENTITY_ABSENT_FAILURE_V1: _error_envelope_bytes(),
        RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1: _success_bytes(
            model="openai/gpt-5", provider="Azure"
        ),
        "returned_model_identity_mismatch": _success_bytes(
            model="openai/gpt-5", provider="OpenAI"
        ),
        "returned_provider_identity_mismatch": _success_bytes(
            model=REDUCED_MODEL_V1, provider="Azure"
        ),
    }
    assert set(bodies) == set(RETURNED_IDENTITY_FATAL_FAILURES_V1)
    for expected, body in bodies.items():
        _outcome, ledger = _run_turn(body, tmp_path)
        assert ledger.fatal_failure == expected, expected


# -------------------------------------------------------------- diagnostics --


def test_binding_diagnostics_are_recorded_whether_or_not_binding_holds(
    tmp_path,
) -> None:
    good, _ = _run_turn(_success_bytes(), tmp_path)
    bad, _ = _run_turn(_error_envelope_bytes(), tmp_path)

    for outcome in (good, bad):
        record = outcome.record
        # The operands the comparison used are server-side configuration.
        assert record.expected_model_identity == REDUCED_MODEL_V1
        assert record.expected_provider_identity == REDUCED_PROVIDER_DISPLAY_NAME_V1
        # The mapper's own verdict, as a closed enum value.
        assert isinstance(record.actual_served_model_status, str)
        assert isinstance(record.router_metadata_presence, str)
        assert isinstance(record.s5_envelope_kind, str)

    assert good.record.s5_envelope_kind == "SUCCESS"
    assert good.record.actual_served_model_status == "ESTABLISHED"
    # The one field that would have ended the incident in a single read.
    assert bad.record.s5_envelope_kind == "ERROR"
    assert bad.record.actual_served_model_status != "ESTABLISHED"


def test_runtime_projection_carries_the_routing_diagnostics() -> None:
    row = {
        "turn_id": "t1",
        "s5_envelope_kind": "ERROR",
        "actual_served_model_status": "ABSENT_FROM_OBSERVATION",
        "router_metadata_presence": "ABSENT",
        "expected_model_identity": "openai/gpt-5-mini",
        "expected_provider_identity": "OpenAI",
        "returned_model_binding_ok": False,
        "returned_provider_binding_ok": False,
        "failure_class": RETURNED_IDENTITY_ABSENT_FAILURE_V1,
        "unexpected_field": "must not be projected",
    }
    projected = normal_runtime._project_turn_row(row)

    assert projected["s5_envelope_kind"] == "ERROR"
    assert projected["actual_served_model_status"] == "ABSENT_FROM_OBSERVATION"
    assert projected["router_metadata_presence"] == "ABSENT"
    assert projected["expected_model_identity"] == "openai/gpt-5-mini"
    assert projected["expected_provider_identity"] == "OpenAI"
    assert projected["failure_class"] == RETURNED_IDENTITY_ABSENT_FAILURE_V1
    assert "unexpected_field" not in projected


def test_new_optional_fields_do_not_disturb_historical_record_identity() -> None:
    """A record that omits them must hash as it always did.

    The turn record's identity pops absent optional evidence, and every field
    added here has to join that list or every historical identity moves.
    """
    from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
        OpenRouterTurnRecordV1,
    )

    base = dict(
        dialogue_id="d",
        turn_id="t",
        role_seat="Alpha",
        dialogue_phase="baseline",
        model=REDUCED_MODEL_V1,
        provider_selector="openai/flex",
        request_id="r",
        body_sha256="0" * 64,
        transport_completed=True,
        worst_case_picodollars=1,
    )
    without = OpenRouterTurnRecordV1(**base)
    with_nones = OpenRouterTurnRecordV1(
        **base,
        actual_served_model_status=None,
        router_metadata_presence=None,
        expected_model_identity=None,
        expected_provider_identity=None,
    )
    assert without.record_id == with_nones.record_id


# ------------------------------------------------------------ fatal reason ---


def test_accounting_carries_the_reason_rather_than_one_constant() -> None:
    """`session_fatal` for everything is what made the incident opaque."""

    class _Ledger:
        def __init__(self, reason):
            self.fatal_failure = reason
            self.calls_consumed = 1
            self.observed_picodollars = 0
            self.settled_picodollars = 0
            self.unsettled_reserved_picodollars = 0
            self.committed_picodollars = 0

    runtime = normal_runtime.NormalRuntime.__new__(normal_runtime.NormalRuntime)
    object.__setattr__(runtime, "adapters", ())
    object.__setattr__(
        runtime, "ledger", _Ledger(RETURNED_IDENTITY_ABSENT_FAILURE_V1)
    )
    accounting = runtime.accounting()
    assert accounting.fatal_failure_code == RETURNED_IDENTITY_ABSENT_FAILURE_V1
    assert accounting.fatal_failure_code != "session_fatal"

    object.__setattr__(runtime, "ledger", _Ledger(None))
    assert runtime.accounting().fatal_failure_code is None


# ------------------------------------------------------------ public notice --


def test_public_stop_notice_is_a_closed_table() -> None:
    absent = public_session_stop_notice(RETURNED_IDENTITY_ABSENT_FAILURE_V1)
    assert absent is not None
    assert "unattributable" in absent
    assert "stopped safely" in absent

    for code in RETURNED_IDENTITY_FATAL_FAILURES_V1:
        assert public_session_stop_notice(code) is not None

    # Anything the table does not know is silence, never an echo.
    for unknown in (
        "session_fatal",
        "some_internal_code_added_later",
        "",
        None,
        123,
        {"code": "x"},
    ):
        assert public_session_stop_notice(unknown) is None


def test_public_stop_notice_never_names_internals() -> None:
    for code in RETURNED_IDENTITY_FATAL_FAILURES_V1:
        notice = public_session_stop_notice(code)
        assert code not in notice
        for forbidden in ("ledger", "envelope", "binding", "sha256", "Bearer"):
            assert forbidden not in notice

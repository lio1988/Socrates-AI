"""Offline safety tests for the one-call Q2 CED 4096 diagnostic."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from scripts.run_q2_ced_4096_diagnostic_v1 import (
    DIAGNOSTIC_BODY_SHA256_V1,
    DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1,
    DIAGNOSTIC_WORST_CASE_PICODOLLARS_V1,
    PRIOR_CED_BODY_SHA256_V1,
    PRIOR_COLLECTION_PATH,
    REDUCED_MODEL_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
    assert_observability_preflight_v1,
    build_diagnostic_body_v1,
    build_diagnostic_policy_v1,
    classify_diagnostic_v1,
    execute_prepared_diagnostic_v1,
    extract_diagnostic_response_evidence_v1,
    load_prior_q2_ced_request_v1,
    prepare_diagnostic_v1,
    render_diagnostic_report_v1,
)


def _prior_collection() -> dict:
    return json.loads(PRIOR_COLLECTION_PATH.read_text(encoding="utf-8"))


def _endpoint_raw() -> bytes:
    return _prior_collection()["endpoint_raw_utf8"].encode("utf-8")


def _accepted_output() -> str:
    return json.dumps(
        {
            "content": {
                "question": (
                    "Which distinction between selection, training, and tool "
                    "effects must be resolved before the observed difference "
                    "can support a causal conclusion?"
                ),
                "operator": "distinguish",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.8,
        },
        separators=(",", ":"),
    )


def _response_raw(*, content: str | None = None) -> bytes:
    return json.dumps(
        {
            "model": REDUCED_MODEL_V1,
            "provider": REDUCED_PROVIDER_DISPLAY_NAME_V1,
            "choices": [
                {
                    "finish_reason": "stop",
                    "native_finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": _accepted_output() if content is None else content,
                        "reasoning": "HIDDEN_REASONING_CANARY_DO_NOT_RETAIN",
                        "reasoning_details": [
                            {"text": "HIDDEN_DETAILS_CANARY_DO_NOT_RETAIN"}
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 3200,
                "completion_tokens": 1700,
                "completion_tokens_details": {
                    "reasoning_tokens": 1400,
                    "accepted_prediction_tokens": 2,
                    "HIDDEN_KEY_CANARY_DO_NOT_RETAIN": 99,
                    "provider_text": "HIDDEN_USAGE_CANARY_DO_NOT_RETAIN",
                },
                "cost": 0.0021,
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_prior_request_rebuild_changes_exactly_max_tokens() -> None:
    prior = load_prior_q2_ced_request_v1()
    prepared = prepare_diagnostic_v1(_endpoint_raw())
    assert prior.body["max_tokens"] == 1024
    assert prepared.rendered.body_sha256 == DIAGNOSTIC_BODY_SHA256_V1
    assert json.loads(prepared.rendered.canonical_body_json)["max_tokens"] == (
        DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1
    )
    assert prepared.parity["deep_differences"] == [
        {"path": "$.max_tokens", "before": 1024, "after": 4096}
    ]
    assert prepared.parity["prior_body_sha256"] == PRIOR_CED_BODY_SHA256_V1
    assert prepared.worst_case_picodollars == DIAGNOSTIC_WORST_CASE_PICODOLLARS_V1
    assert "reasoning" in prepared.endpoint_evidence.supported_parameters
    assert not {
        "reasoning",
        "reasoning_effort",
        "include_reasoning",
    } & set(json.loads(prepared.rendered.canonical_body_json))


def test_exact_endpoint_must_support_4096_output() -> None:
    value = json.loads(_endpoint_raw())
    endpoint = next(
        row
        for row in value["data"]["endpoints"]
        if row.get("tag") == "openai/flex"
    )
    endpoint["max_completion_tokens"] = 1024
    with pytest.raises(ContractValidationError, match="below diagnostic 4096"):
        prepare_diagnostic_v1(json.dumps(value).encode("utf-8"))

    value = json.loads(_endpoint_raw())
    endpoint = next(
        row
        for row in value["data"]["endpoints"]
        if row.get("tag") == "openai/flex"
    )
    endpoint["supported_parameters"] = [
        item for item in endpoint["supported_parameters"] if item != "reasoning"
    ]
    with pytest.raises(ContractValidationError, match="reasoning parameter"):
        prepare_diagnostic_v1(json.dumps(value).encode("utf-8"))


def test_observability_retains_counts_but_never_hidden_reasoning_text() -> None:
    prior = load_prior_q2_ced_request_v1()
    evidence, observed = extract_diagnostic_response_evidence_v1(
        raw=_response_raw(),
        task=prior.task,
        completed=True,
        http_status=200,
    )
    serialized = json.dumps(evidence, sort_keys=True)
    assert "HIDDEN_REASONING_CANARY" not in serialized
    assert "HIDDEN_DETAILS_CANARY" not in serialized
    assert "HIDDEN_KEY_CANARY" not in serialized
    assert "HIDDEN_USAGE_CANARY" not in serialized
    assert evidence["finish_reason"] == "stop"
    assert evidence["native_finish_reason"] == "stop"
    assert evidence["message_content_state"] == "CONTENT_NONEMPTY_STRING"
    assert evidence["usage"]["reasoning_tokens"] == 1400
    assert evidence["usage"]["reasoning_tokens_source"] == (
        "usage.completion_tokens_details.reasoning_tokens"
    )
    assert evidence["usage"]["completion_tokens_details"] == {
        "accepted_prediction_tokens": 2,
        "reasoning_tokens": 1400,
    }
    assert evidence["usage"]["completion_tokens_details_state"] == (
        "PRESENT_OBJECT"
    )
    assert evidence["provider_structured_output_valid"] is True
    assert evidence["ced_parse_accepted"] is True
    assert evidence["ced_move_accepted"] is True
    assert evidence["ced_acceptance_result"] == "accepted"
    assert evidence["socratic_move"]["epistemic_marker"] == "open_uncertainty"
    assert observed == 2_100_000_000
    assert assert_observability_preflight_v1(prior.task)["passed"] is True


def test_execute_path_consumes_one_latch_and_dispatch_only_once(
    tmp_path: Path,
) -> None:
    prepared = prepare_diagnostic_v1(_endpoint_raw())
    calls: list[dict] = []

    def fake_dispatch(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            completion=SimpleNamespace(
                completed=True,
                http_status=200,
                retry_count=0,
                local_dispatch_count=1,
                failure_class=None,
            ),
            raw_response_body=_response_raw(),
        )

    result = execute_prepared_diagnostic_v1(
        prepared,
        dispatch=fake_dispatch,
        latch_directory=tmp_path / "attempt",
        claim_directory=tmp_path / "claim",
    )
    assert len(calls) == 1
    assert calls[0]["process_dispatch_limit"] == 1
    assert result["ledger"]["calls_consumed"] == 1
    assert result["transport"]["retry_count"] == 0
    assert result["response"]["ced_move_accepted"] is True
    interpretation = classify_diagnostic_v1(result)
    assert interpretation["verdict"] == "GENERATION_BUDGET_CONFIRMED"
    assert interpretation["classification"] == (
        "GENERATION_BUDGET_TOO_LOW AT 1024"
    )
    assert interpretation["phase_aware_output_budget_policy"] == {
        "status": "PROPOSED_NOT_IMPLEMENTED",
        "short_socratic_moves_and_openings": 4096,
        "reflection_and_reconstruction": 8192,
        "synthesis_and_final_response": 16384,
        "rule": (
            "phase-aware ceilings replace the global 1024 ceiling; "
            "reasoning behavior remains independently controlled"
        ),
        "evidence_basis": (
            "opening value uses this accepted call's completion-token "
            "headroom; larger-phase values are provisional multiples and "
            "require separate validation before use"
        ),
    }
    with pytest.raises(ContractValidationError, match="already consumed"):
        execute_prepared_diagnostic_v1(
            prepared,
            dispatch=fake_dispatch,
            latch_directory=tmp_path / "attempt",
            claim_directory=tmp_path / "claim",
        )
    assert len(calls) == 1


def test_independent_renderer_matches_mechanical_one_field_edit() -> None:
    prepared = prepare_diagnostic_v1(_endpoint_raw())
    rendered, parity = build_diagnostic_body_v1(
        prepared.prior,
        build_diagnostic_policy_v1(),
        prepared.profile,
    )
    assert rendered.canonical_body_json == prepared.rendered.canonical_body_json
    assert parity["proved"] is True


def test_output_limit_can_never_be_classified_as_confirmed() -> None:
    execution = {
        "transport": {
            "completed": True,
            "http_status": 200,
            "retry_count": 0,
            "local_dispatch_count": 1,
        },
        "response": {
            "finish_reason": "length",
            "native_finish_reason": "length",
            "returned_model_binding_ok": True,
            "returned_provider_binding_ok": True,
            "provider_structured_output_valid": True,
            "ced_parse_accepted": True,
            "ced_move_accepted": True,
            "usage": {"completion_tokens": 4096},
        },
        "ledger": {"fatal_failure": None},
    }
    result = classify_diagnostic_v1(execution)
    assert result["verdict"] == "NOT_CONFIRMED"
    assert result["classification"] == "4096_OUTPUT_LIMIT_REACHED"
    assert result["output_limit_reached"] is True
    assert result["phase_aware_output_budget_policy"] is None


def test_no_content_does_not_misstate_a_ced_rejection() -> None:
    prior = load_prior_q2_ced_request_v1()
    raw = json.dumps(
        {
            "model": REDUCED_MODEL_V1,
            "provider": REDUCED_PROVIDER_DISPLAY_NAME_V1,
            "choices": [
                {
                    "finish_reason": "length",
                    "native_finish_reason": "length",
                    "message": {"content": None},
                }
            ],
            "usage": {
                "prompt_tokens": 3000,
                "completion_tokens": 4096,
                "completion_tokens_details": {"reasoning_tokens": 4096},
                "cost": 0.0045,
            },
        }
    ).encode("utf-8")
    evidence, _ = extract_diagnostic_response_evidence_v1(
        raw=raw,
        task=prior.task,
        completed=True,
        http_status=200,
    )
    assert evidence["message_content_state"] == "CONTENT_NULL"
    assert evidence["ced_parse_status"] is None
    assert evidence["ced_parse_accepted"] is None
    assert evidence["ced_acceptance_result"] == "NOT_REACHED"
    assert evidence["ced_move_accepted"] is None
    assert evidence["ced_rejection_reason"] is None
    assert evidence["upstream_failure_reason"] == "no_assistant_content"


def test_malformed_nonempty_content_is_explicitly_provider_invalid() -> None:
    prior = load_prior_q2_ced_request_v1()
    evidence, _ = extract_diagnostic_response_evidence_v1(
        raw=_response_raw(content='{"content":{"question":"unfinished"}'),
        task=prior.task,
        completed=True,
        http_status=200,
    )
    assert evidence["message_content_state"] == "CONTENT_NONEMPTY_STRING"
    assert evidence["provider_structured_output_state"] == "INVALID"
    assert evidence["provider_structured_output_valid"] is False
    assert evidence["provider_structured_output_error"]
    assert evidence["ced_parse_accepted"] is False
    assert evidence["ced_move_accepted"] is False


def test_route_mismatch_can_never_confirm_generation_budget() -> None:
    execution = {
        "transport": {
            "completed": True,
            "http_status": 200,
            "retry_count": 0,
            "local_dispatch_count": 1,
        },
        "response": {
            "finish_reason": "stop",
            "native_finish_reason": "stop",
            "returned_model_binding_ok": False,
            "returned_provider_binding_ok": True,
            "provider_structured_output_valid": True,
            "ced_parse_accepted": True,
            "ced_move_accepted": True,
            "usage": {"completion_tokens": 1700},
        },
        "ledger": {"fatal_failure": "returned_model_identity_mismatch"},
    }
    result = classify_diagnostic_v1(execution)
    assert result["verdict"] == "NOT_CONFIRMED"
    assert result["classification"] == "ROUTE_OR_SESSION_INVARIANT_FAILURE"
    assert result["phase_aware_output_budget_policy"] is None


def test_dispatch_exception_is_retained_after_latch_without_retry(
    tmp_path: Path,
) -> None:
    prepared = prepare_diagnostic_v1(_endpoint_raw())
    calls = 0

    def failing_dispatch(**_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic dispatch failure")

    execution = execute_prepared_diagnostic_v1(
        prepared,
        dispatch=failing_dispatch,
        latch_directory=tmp_path / "attempt",
        claim_directory=tmp_path / "claim",
    )
    assert calls == 1
    assert execution["transport"]["completed"] is False
    assert execution["transport"]["failure_class"] == "RuntimeError"
    assert execution["ledger"]["calls_consumed"] == 1
    assert execution["ledger"]["unsettled_reserved_picodollars"] == (
        DIAGNOSTIC_WORST_CASE_PICODOLLARS_V1
    )
    assert execution["cumulative_observed_picodollars"] is None
    assert execution["response"]["provider_structured_output_state"] == (
        "NOT_REACHED"
    )
    assert execution["response"]["provider_structured_output_valid"] is None
    interpretation = classify_diagnostic_v1(execution)
    assert interpretation["verdict"] == "NOT_CONFIRMED"
    assert interpretation["classification"] == "HTTP_OR_TRANSPORT_FAILURE"


def test_report_contains_exact_required_headings_and_measurements(
    tmp_path: Path,
) -> None:
    prepared = prepare_diagnostic_v1(_endpoint_raw())

    def fake_dispatch(**_kwargs):
        return SimpleNamespace(
            completion=SimpleNamespace(
                completed=True,
                http_status=200,
                retry_count=0,
                local_dispatch_count=1,
                failure_class=None,
            ),
            raw_response_body=_response_raw(),
        )

    execution = execute_prepared_diagnostic_v1(
        prepared,
        dispatch=fake_dispatch,
        latch_directory=tmp_path / "attempt",
        claim_directory=tmp_path / "claim",
    )
    collection = {
        "result": "Q2_CED_4096_DIAGNOSTIC_COMPLETE",
        "hard_cumulative_spend_usd": "8.00",
        "body_parity": prepared.parity,
        "endpoint_evidence": prepared.endpoint_evidence.model_dump(mode="json"),
        "endpoint_http": {"http_status": 200},
        "authorization_manifest": prepared.manifest,
        "economics_preflight": {
            "prior_observed_usd": "0.004614375",
            "diagnostic_worst_case_usd": "0.054096",
            "cumulative_prior_plus_reservation_usd": "0.058710375",
            "within_hard_ceiling": True,
        },
        "execution": execution,
        "interpretation": classify_diagnostic_v1(execution),
    }
    report = render_diagnostic_report_v1(collection)
    assert report.startswith("# CED 4096 DIAGNOSTIC\n")
    assert "# VERDICT: GENERATION_BUDGET_CONFIRMED" in report
    for label in (
        "HTTP status:",
        "Finish reason:",
        "Native finish reason:",
        "Prompt tokens:",
        "Completion tokens:",
        "Reasoning tokens:",
        "Completion token details state:",
        "Message content state:",
        "Provider structured output state:",
        "CED parse status:",
        "CED canonical application:",
        "CED Socratic move accepted:",
        "Question:",
        "Observed cost:",
        "Latency ms:",
    ):
        assert label in report
    assert "HIDDEN_REASONING_CANARY" not in report
    assert "HIDDEN_DETAILS_CANARY" not in report

"""Offline locks for the two-arm structured Socratic experiment.

The shared acquisition test boundary keeps this file network- and credential-free.
Synthetic endpoint listings exercise the exact-endpoint gates; no live runner is
invoked here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_structured_socratic_experiment_v1 import (
    CONTROL_MODEL_V1,
    CONTROL_OUTPUT_TOKENS_V1,
    CONTROL_PROMPT_ONLY_BODY_SHA256_V1,
    CONTROL_PROVIDER_SELECTOR_V1,
    CONTROL_QUESTION_V1,
    CONTROL_SESSION_ID_V1,
    CONTROL_TASK_ID_V1,
    CONTROL_TIMEOUT_SECONDS_V1,
    FULL_MODEL_V1,
    StructuredArmPriceCeilingsV1,
    assert_ced_opening_schema_parity_v1,
    assert_prompt_only_control_reconstruction_v1,
    build_control_opening_fixture_v1,
    ced_opening_response_format_v1,
    ced_opening_schema_sha256_v1,
    conservative_arm_cost_bound_picodollars_v1,
    evaluate_raw_move_through_ced_v1,
    parse_exact_endpoint_capability_v1,
    render_structured_arm_request_v1,
)
import scripts.run_openrouter_structured_socratic_arm_v1 as arm_runner
from backend.dialogues.reasoning_prompts import build_reasoning_system_prompt
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    build_turn_user_content_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterFrozenExecutionPolicyV1,
    render_dynamic_turn_v1,
)


ROOT = Path(__file__).resolve().parents[1]


def _endpoint_payload(
    model: str = CONTROL_MODEL_V1,
    *,
    prompt: str = "0.00000044",
    completion: str = "0.00000176",
) -> Dict[str, Any]:
    return {
        "data": {
            "id": model,
            # A model-level union may say anything; the parser must use only
            # the exact selected endpoint record below.
            "supported_parameters": ["not_endpoint_authority"],
            "endpoints": [
                {
                    "tag": CONTROL_PROVIDER_SELECTOR_V1,
                    "model_id": model,
                    "name": f"{model}-2025-04-14",
                    "provider_name": "Azure",
                    "status": 0,
                    "supported_parameters": [
                        "max_completion_tokens",
                        "response_format",
                        "structured_outputs",
                        "temperature",
                        "top_p",
                    ],
                    "max_completion_tokens": 942_818,
                    "context_length": 1_047_576,
                    "pricing": {
                        "prompt": prompt,
                        "completion": completion,
                    },
                }
            ],
        }
    }


def _endpoint_bytes(**kwargs: Any) -> bytes:
    return canonical_json(_endpoint_payload(**kwargs)).encode("utf-8")


def _content_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    ref = schema["properties"]["content"]["$ref"]
    assert ref == "#/$defs/CedOpeningSocraticContentV1"
    return schema["$defs"]["CedOpeningSocraticContentV1"]


def test_provider_schema_is_the_strict_ced_opening_shape() -> None:
    assert_ced_opening_schema_parity_v1()
    wrapper = ced_opening_response_format_v1()
    assert wrapper["type"] == "json_schema"
    assert wrapper["json_schema"]["strict"] is True

    schema = wrapper["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"content", "confidence"}
    assert set(schema["required"]) == {"content", "confidence"}
    assert "epistemic_marker" not in schema["properties"]

    content = _content_schema(schema)
    assert content["additionalProperties"] is False
    assert set(content["properties"]) == {
        "question",
        "operator",
        "epistemic_marker",
    }
    assert set(content["required"]) == set(content["properties"])
    assert content["properties"]["question"]["pattern"] == r"\S"


def test_preserved_prompt_only_control_still_reconstructs_exactly() -> None:
    assert_prompt_only_control_reconstruction_v1()


def test_preserved_prompt_only_control_files_remain_byte_identical() -> None:
    runs = (
        ROOT
        / "docs"
        / "branches"
        / "feature-socrates-zero-openrouter-live-routing-repair-v1"
        / "runs"
    )
    expected = {
        "README.md": "14c362c4bd05337ce61e1fc7899bcc0d17ab5b38521bdf897ad7bbd99325d547",
        "socrates_live_run_002.json": "9636ceabc377bee74cf235584599f7a1d11f1880c10b9b5647046ee29a6cbf0d",
        "socrates_live_run_003.json": "59f1c4c622bb0a985f560398dc4fd1b78445f31681c14617ef0efce698088c2e",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((runs / name).read_bytes()).hexdigest() == digest
    for name in ("socrates_live_run_002.json", "socrates_live_run_003.json"):
        payload = json.loads((runs / name).read_text(encoding="utf-8"))
        assert payload["turns"][0]["ced_move_accepted"] is False


def test_historical_real_endpoint_shape_is_accepted_as_parser_evidence() -> None:
    evidence = (
        ROOT
        / "docs"
        / "branches"
        / "feature-socrates-zero-openrouter-one-live-shadow-v1"
        / "evidence"
        / "s7c_model_endpoints_response_v1.json"
    ).read_bytes()
    endpoint = parse_exact_endpoint_capability_v1(
        evidence, requested_model=CONTROL_MODEL_V1
    )
    assert endpoint.listing_sha256 == (
        "73d8f9131da4652f2437cd48cb961c60b559970a64e85d0d2dab2835bc177046"
    )
    assert endpoint.listing_length == 2960
    assert endpoint.endpoint_name == "Azure | openai/gpt-4.1-mini-2025-04-14"
    assert endpoint.context_length == 1_047_576
    assert endpoint.maximum_output_tokens == 942_818


def test_mini_body_changes_only_response_format_from_prompt_only_control() -> None:
    fixture = build_control_opening_fixture_v1()
    system_prompt = build_reasoning_system_prompt(
        fixture.task.role,
        fixture.task.phase,
        fixture.task.task_kind,
        model=CONTROL_MODEL_V1,
    )
    turn = OpenRouterDynamicTurnRequestV1(
        system_prompt=system_prompt,
        user_content=build_turn_user_content_v1(fixture.task, fixture.agent_state),
        role_seat="socrates",
        dialogue_id=CONTROL_SESSION_ID_V1,
        turn_id=CONTROL_TASK_ID_V1,
        dialogue_phase="opening",
    )
    prompt_only = render_dynamic_turn_v1(
        OpenRouterFrozenExecutionPolicyV1(
            model=CONTROL_MODEL_V1,
            provider_only=(CONTROL_PROVIDER_SELECTOR_V1,),
            provider_order=(CONTROL_PROVIDER_SELECTOR_V1,),
            output_limit_tokens=CONTROL_OUTPUT_TOKENS_V1,
            max_price_prompt_usd_per_million="0.50",
            max_price_completion_usd_per_million="2.00",
            max_price_request_usd="0",
            bounded_timeout_seconds=CONTROL_TIMEOUT_SECONDS_V1,
        ),
        FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1,
        turn,
    )
    endpoint = parse_exact_endpoint_capability_v1(
        _endpoint_bytes(), requested_model=CONTROL_MODEL_V1
    )
    structured = render_structured_arm_request_v1(
        model=CONTROL_MODEL_V1,
        endpoint=endpoint,
        ceilings=StructuredArmPriceCeilingsV1(
            prompt_usd_per_million_tokens="0.50",
            completion_usd_per_million_tokens="2.00",
            request_usd="0",
        ),
    )
    body = json.loads(structured.canonical_body_json)
    body["response_format"] = {"type": "json_object"}
    rendered = canonical_json(body).encode("utf-8")
    assert hashlib.sha256(rendered).hexdigest() == CONTROL_PROMPT_ONLY_BODY_SHA256_V1
    assert rendered.decode("utf-8") == prompt_only.canonical_body_json


def test_nested_marker_passes_provider_schema_and_unchanged_ced() -> None:
    raw = canonical_json(
        {
            "content": {
                "question": (
                    "What distinction between justification and truth would matter "
                    "for deciding whether those conditions are sufficient for knowledge?"
                ),
                "operator": "distinguish",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.5,
        }
    )
    result = evaluate_raw_move_through_ced_v1(raw)
    assert result["provider_structured_output_valid"] is True
    assert result["ced_schema_accepted"] is True
    assert result["socratic_move_accepted"] is True
    assert result["operator"] == "distinguish"
    assert result["epistemic_marker"] == "open_uncertainty"
    assert result["confidence"] == 0.5


def test_prompt_only_failure_shape_remains_rejected_without_relaxing_ced() -> None:
    raw = canonical_json(
        {
            "content": {
                "question": "What would make the three conditions insufficient?",
                "operator": "distinguish",
            },
            "confidence": 0.9,
            "epistemic_marker": "open_uncertainty",
        }
    )
    result = evaluate_raw_move_through_ced_v1(raw)
    assert result["provider_structured_output_valid"] is False
    assert result["ced_schema_accepted"] is False
    assert result["socratic_move_accepted"] is False
    assert result["ced_schema_status"] == "schema_error"
    assert result["ced_schema_reason"] == (
        "schema validation failed: epistemic_marker is required"
    )
    assert result["question"] == "What would make the three conditions insufficient?"
    assert result["operator"] == "distinguish"
    assert result["epistemic_marker"] is None
    assert result["top_level_epistemic_marker"] == "open_uncertainty"
    assert result["confidence"] == 0.9


def test_provider_ced_and_socratic_measurements_are_independent() -> None:
    whitespace = canonical_json(
        {
            "content": {
                "question": "   ",
                "operator": "clarify",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.5,
        }
    )
    result = evaluate_raw_move_through_ced_v1(whitespace)
    assert result["provider_structured_output_valid"] is False
    assert result["ced_schema_accepted"] is True
    assert result["socratic_move_accepted"] is False

    extra = canonical_json(
        {
            "content": {
                "question": "Which condition would a counterexample undermine?",
                "operator": "expose_premise",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.5,
            "non_ced_extra": "observed but not authoritative",
        }
    )
    result = evaluate_raw_move_through_ced_v1(extra)
    assert result["provider_structured_output_valid"] is False
    assert result["ced_schema_accepted"] is True
    assert result["socratic_move_accepted"] is True
    assert result["raw_field_observation"]["operator"] == "expose_premise"


def test_exact_endpoint_record_not_model_union_selects_output_parameter() -> None:
    endpoint = parse_exact_endpoint_capability_v1(
        _endpoint_bytes(), requested_model=CONTROL_MODEL_V1
    )
    assert endpoint.requested_model == CONTROL_MODEL_V1
    assert endpoint.provider_selector == CONTROL_PROVIDER_SELECTOR_V1
    assert endpoint.output_limit_parameter == "max_completion_tokens"
    assert endpoint.maximum_output_tokens == 942_818
    assert "not_endpoint_authority" not in endpoint.supported_parameters


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("data", "id", FULL_MODEL_V1), "another model"),
        (("endpoint", "model_id", FULL_MODEL_V1), "not unique"),
        (("endpoint", "tag", "openai"), "not unique"),
        (("endpoint", "status", 1), "not healthy"),
        (("remove_parameter", "structured_outputs", None), "required parameters"),
        (("remove_parameter", "response_format", None), "required parameters"),
        (("remove_parameter", "temperature", None), "required parameters"),
        (("endpoint", "max_completion_tokens", 255), "below 256"),
    ],
)
def test_exact_endpoint_gate_fails_closed(mutation, message: str) -> None:
    payload = _endpoint_payload()
    kind, field, value = mutation
    endpoint = payload["data"]["endpoints"][0]
    if kind == "data":
        payload["data"][field] = value
    elif kind == "endpoint":
        endpoint[field] = value
    else:
        endpoint["supported_parameters"].remove(field)
    with pytest.raises(ContractValidationError, match=message):
        parse_exact_endpoint_capability_v1(
            canonical_json(payload).encode("utf-8"),
            requested_model=CONTROL_MODEL_V1,
        )


def test_same_schema_question_context_and_sampling_render_for_both_arms() -> None:
    mini_endpoint = parse_exact_endpoint_capability_v1(
        _endpoint_bytes(), requested_model=CONTROL_MODEL_V1
    )
    full_endpoint = parse_exact_endpoint_capability_v1(
        _endpoint_bytes(
            model=FULL_MODEL_V1,
            prompt="0.0000022",
            completion="0.0000088",
        ),
        requested_model=FULL_MODEL_V1,
    )
    mini = render_structured_arm_request_v1(
        model=CONTROL_MODEL_V1,
        endpoint=mini_endpoint,
        ceilings=StructuredArmPriceCeilingsV1(
            prompt_usd_per_million_tokens="0.50",
            completion_usd_per_million_tokens="2.00",
            request_usd="0",
        ),
    )
    full = render_structured_arm_request_v1(
        model=FULL_MODEL_V1,
        endpoint=full_endpoint,
        ceilings=StructuredArmPriceCeilingsV1(
            prompt_usd_per_million_tokens="2.50",
            completion_usd_per_million_tokens="10.00",
            request_usd="0",
        ),
    )
    mini_body = json.loads(mini.canonical_body_json)
    full_body = json.loads(full.canonical_body_json)

    assert mini.response_schema_sha256 == full.response_schema_sha256
    assert mini.response_schema_sha256 == ced_opening_schema_sha256_v1()
    assert mini.user_content_sha256 == full.user_content_sha256
    assert mini.dialogue_context_sha256 == full.dialogue_context_sha256
    assert mini_body["messages"][1] == full_body["messages"][1]
    assert CONTROL_QUESTION_V1 in mini_body["messages"][1]["content"]
    assert mini_body["response_format"] == full_body["response_format"]
    assert mini_body["temperature"] == full_body["temperature"] == 0.0
    assert mini_body["stream"] is full_body["stream"] is False
    assert mini_body["max_completion_tokens"] == CONTROL_OUTPUT_TOKENS_V1
    assert full_body["max_completion_tokens"] == CONTROL_OUTPUT_TOKENS_V1
    assert mini_body["provider"]["only"] == full_body["provider"]["only"]
    assert mini_body["provider"]["order"] == mini_body["provider"]["only"]
    assert full_body["provider"]["order"] == full_body["provider"]["only"]
    assert mini_body["provider"]["require_parameters"] is True
    assert full_body["provider"]["require_parameters"] is True
    assert mini_body["provider"]["allow_fallbacks"] is False
    assert full_body["provider"]["allow_fallbacks"] is False
    assert mini_body["model"] == CONTROL_MODEL_V1
    assert full_body["model"] == FULL_MODEL_V1
    for body in (mini_body, full_body):
        assert "max_tokens" not in body
        assert "seed" not in body
        assert "top_p" not in body


def test_endpoint_price_and_conservative_arm_bounds_are_exact() -> None:
    mini_endpoint = parse_exact_endpoint_capability_v1(
        _endpoint_bytes(), requested_model=CONTROL_MODEL_V1
    )
    mini_ceilings = StructuredArmPriceCeilingsV1(
        prompt_usd_per_million_tokens="0.50",
        completion_usd_per_million_tokens="2.00",
        request_usd="0",
    )
    assert (
        conservative_arm_cost_bound_picodollars_v1(mini_endpoint, mini_ceilings)
        == 524_300_000_000
    )

    full_endpoint = parse_exact_endpoint_capability_v1(
        _endpoint_bytes(
            model=FULL_MODEL_V1,
            prompt="0.0000022",
            completion="0.0000088",
        ),
        requested_model=FULL_MODEL_V1,
    )
    full_ceilings = StructuredArmPriceCeilingsV1(
        prompt_usd_per_million_tokens="2.50",
        completion_usd_per_million_tokens="10.00",
        request_usd="0",
    )
    assert (
        conservative_arm_cost_bound_picodollars_v1(full_endpoint, full_ceilings)
        == 2_621_500_000_000
    )

    too_low = copy.deepcopy(_endpoint_payload())
    too_low["data"]["endpoints"][0]["pricing"]["prompt"] = "0.00000051"
    endpoint = parse_exact_endpoint_capability_v1(
        canonical_json(too_low).encode("utf-8"),
        requested_model=CONTROL_MODEL_V1,
    )
    with pytest.raises(ContractValidationError, match="prompt price"):
        render_structured_arm_request_v1(
            model=CONTROL_MODEL_V1,
            endpoint=endpoint,
            ceilings=mini_ceilings,
        )


def test_runner_preserves_partial_record_when_endpoint_fetch_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = Namespace(
        arm="ARM_1",
        model=CONTROL_MODEL_V1,
        prompt_ceiling="0.50",
        completion_ceiling="2.00",
        request_ceiling="0",
        maximum_arm_spend_usd="0.60",
        operator_statement="offline fixture",
        out=str(tmp_path / "never-written-by-run-arm.json"),
    )
    monkeypatch.setattr(arm_runner, "_git_head", lambda: "a" * 40)
    monkeypatch.setattr(arm_runner, "consume_turn_claim_v1", lambda *_: None)

    def fail_fetch(self, model: str):
        raise OSError(f"synthetic endpoint failure for {model}")

    monkeypatch.setattr(arm_runner._EndpointGetLatch, "fetch", fail_fetch)
    partial: Dict[str, Any] = {}
    with pytest.raises(OSError, match="synthetic endpoint failure"):
        arm_runner.run_arm(args, partial)
    assert partial["result"] == "STARTED"
    assert partial["endpoint_retrievals"] == 1
    assert partial["inference_dispatches"] == 0
    assert partial["http_success"] is False
    assert partial["attempt_claim_id"].startswith("szorturnclaimv1_")


def test_runner_main_augments_rather_than_discards_post_failure_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "failed-arm.json"

    def fail_after_dispatch(args, record):
        record.update(
            {
                "arm": args.arm,
                "requested_model": args.model,
                "inference_dispatches": 1,
                "http_success": True,
                "transport": {"http_status": 200},
                "raw_response_utf8": '{"malformed_for_extractor":true}',
            }
        )
        raise ValueError("synthetic post-response extraction failure")

    monkeypatch.setattr(arm_runner, "run_arm", fail_after_dispatch)
    monkeypatch.setattr(
        arm_runner.sys,
        "argv",
        [
            "runner",
            "--arm",
            "ARM_1",
            "--model",
            CONTROL_MODEL_V1,
            "--prompt-ceiling",
            "0.50",
            "--completion-ceiling",
            "2.00",
            "--request-ceiling",
            "0",
            "--maximum-arm-spend-usd",
            "0.60",
            "--operator-statement",
            "offline fixture",
            "--out",
            str(output),
        ],
    )
    assert arm_runner.main() == 0
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["result"] == "FAILED_BEFORE_RESULT_COMPLETION"
    assert evidence["inference_dispatches"] == 1
    assert evidence["http_success"] is True
    assert evidence["transport"]["http_status"] == 200
    assert evidence["raw_response_utf8"] == '{"malformed_for_extractor":true}'
    assert evidence["failure_class"] == "ValueError"


def _patch_offline_arm_transport(
    monkeypatch: pytest.MonkeyPatch, response_payload: Dict[str, Any]
) -> None:
    endpoint_raw = _endpoint_bytes()

    def endpoint_fetch(self, model: str):
        assert model == CONTROL_MODEL_V1
        return {
            "method": "GET",
            "host": "openrouter.ai",
            "path": "/synthetic/exact-endpoint",
            "http_status": 200,
            "latency_ms": 1.0,
            "body_sha256": hashlib.sha256(endpoint_raw).hexdigest(),
            "body_length": len(endpoint_raw),
            "response_header_count": 0,
            "response_header_sha256": hashlib.sha256(b"[]").hexdigest(),
            "raw_body": endpoint_raw,
        }

    raw_response = canonical_json(response_payload).encode("utf-8")

    def dispatch(**kwargs):
        assert kwargs["process_dispatch_limit"] == 1
        return SimpleNamespace(
            registration=SimpleNamespace(registration_id="registration-fixture"),
            completion=SimpleNamespace(
                completion_id="completion-fixture",
                completed=True,
                http_status=200,
                retry_count=0,
                response_body_sha256=hashlib.sha256(raw_response).hexdigest(),
                response_body_length=len(raw_response),
                response_header_count=0,
                response_header_evidence_sha256=hashlib.sha256(b"[]").hexdigest(),
                failure_class=None,
            ),
            raw_response_body=raw_response,
        )

    monkeypatch.setattr(arm_runner, "_git_head", lambda: "a" * 40)
    monkeypatch.setattr(arm_runner, "consume_turn_claim_v1", lambda *_: None)
    monkeypatch.setattr(
        arm_runner, "openrouter_credential_is_present_v1", lambda: True
    )
    monkeypatch.setattr(arm_runner._EndpointGetLatch, "fetch", endpoint_fetch)
    monkeypatch.setattr(
        arm_runner, "dispatch_openrouter_one_live_inference_v1", dispatch
    )


def _offline_arm_args(tmp_path: Path) -> Namespace:
    return Namespace(
        arm="ARM_1",
        model=CONTROL_MODEL_V1,
        prompt_ceiling="0.50",
        completion_ceiling="2.00",
        request_ceiling="0",
        maximum_arm_spend_usd="0.60",
        operator_statement="offline fixture",
        out=str(tmp_path / "unused.json"),
    )


def test_runner_http_200_success_records_every_primary_measurement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assistant = canonical_json(
        {
            "content": {
                "question": "Which condition would a counterexample undermine?",
                "operator": "expose_premise",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.5,
        }
    )
    _patch_offline_arm_transport(
        monkeypatch,
        {
            "id": "response-fixture",
            "model": CONTROL_MODEL_V1,
            "provider": "Azure",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": assistant},
                }
            ],
            "usage": {
                "prompt_tokens": 4000,
                "completion_tokens": 50,
                "total_tokens": 4050,
                "cost": "0.0019",
            },
        },
    )
    record = arm_runner.run_arm(_offline_arm_args(tmp_path), {})
    assert record["result"] == "COMPLETED"
    assert record["inference_dispatches"] == 1
    assert record["retry_count"] == 0
    assert record["http_success"] is True
    assert record["transport"]["http_status"] == 200
    assert record["scientific_model_identity_valid"] is True
    assert record["assistant_output"] == assistant
    assert record["usage"]["prompt_tokens"] == 4000
    assert record["usage"]["completion_tokens"] == 50
    assert record["usage"]["observed_cost_usd"] == "0.0019"
    assert record["cost_checks"]["observed_cost_within_preflight_bound"] is True
    assert record["acceptance"]["provider_structured_output_valid"] is True
    assert record["acceptance"]["ced_schema_accepted"] is True
    assert record["acceptance"]["socratic_move_accepted"] is True
    assert record["acceptance"]["question"] == (
        "Which condition would a counterexample undermine?"
    )
    assert record["acceptance"]["operator"] == "expose_premise"
    assert record["acceptance"]["epistemic_marker"] == "open_uncertainty"
    assert record["acceptance"]["confidence"] == 0.5


def test_runner_http_200_refusal_keeps_usage_and_records_three_rejections(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_offline_arm_transport(
        monkeypatch,
        {
            "id": "response-refusal",
            "model": CONTROL_MODEL_V1,
            "provider": "Azure",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "refusal": "cannot comply",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 4000,
                "completion_tokens": 4,
                "total_tokens": 4004,
                "cost": 0.0018,
            },
        },
    )
    record = arm_runner.run_arm(_offline_arm_args(tmp_path), {})
    assert record["result"] == "NO_STRUCTURED_ASSISTANT_OUTPUT"
    assert record["http_success"] is True
    assert record["assistant_refusal"] == "cannot comply"
    assert record["usage"]["prompt_tokens"] == 4000
    assert record["usage"]["observed_cost_usd"] == "0.0018"
    assert record["acceptance"]["provider_structured_output_valid"] is False
    assert record["acceptance"]["ced_schema_accepted"] is False
    assert record["acceptance"]["socratic_move_accepted"] is False

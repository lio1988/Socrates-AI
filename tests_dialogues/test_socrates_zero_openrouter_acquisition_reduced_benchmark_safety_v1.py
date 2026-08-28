"""Offline locks for the approved reduced GPT-5 Mini Flex benchmark."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ProviderStatus,
    TaskKind,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
    execute_bounded_text_turn_v1,
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterDynamicTurnRequestV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterSessionBudgetExceeded,
    OpenRouterSessionLedgerV1,
    OpenRouterTurnRecordV1,
    conservative_turn_cost_bound_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1,
    REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1,
    REDUCED_MAX_CALLS_V1,
    REDUCED_MAX_INPUT_TOKENS_V1,
    REDUCED_MODEL_V1,
    REDUCED_PER_CALL_BOUND_PICODOLLARS_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
    WORKER_ALIASES_V1,
    WORKER_PROVIDER_IDS_V1,
    assert_reduced_flex_rendered_turn_v1,
    build_reduced_flex_policy_v1,
    build_reduced_session_authorization_v1,
    flex_profile_from_evidence_v1,
    make_hidden_evaluator_guard_v1,
    make_worker_payload_projector_v1,
    validate_flex_endpoint_listing_v1,
)


def _endpoint_bytes(**updates) -> bytes:
    endpoint = {
        "name": "OpenAI | openai/gpt-5-mini-2025-08-07",
        "tag": "openai/flex",
        "provider_name": "OpenAI",
        "model_id": "openai/gpt-5-mini",
        "status": 0,
        "context_length": 400_000,
        "max_prompt_tokens": 272_000,
        "max_completion_tokens": 128_000,
        "supported_parameters": [
            "reasoning",
            "include_reasoning",
            "structured_outputs",
            "response_format",
            "seed",
            "max_tokens",
            "tools",
            "tool_choice",
            "reasoning_effort",
        ],
        "pricing": {
            "prompt": "0.000000125",
            "completion": "0.000001",
        },
    }
    endpoint.update(updates)
    return json.dumps(
        {"data": {"id": "openai/gpt-5-mini", "endpoints": [endpoint]}},
        sort_keys=True,
    ).encode("utf-8")


def _profile():
    return flex_profile_from_evidence_v1(
        validate_flex_endpoint_listing_v1(_endpoint_bytes())
    )


def _schema() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "fixture_move",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "content": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "claim": {"type": "string"},
                            "epistemic_marker": {
                                "type": "string",
                                "enum": ["reasonable_hypothesis"],
                            },
                        },
                        "required": ["claim", "epistemic_marker"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["content", "confidence"],
            },
        },
    }


def _turn(turn_id: str = "turn-1") -> OpenRouterDynamicTurnRequestV1:
    return OpenRouterDynamicTurnRequestV1(
        system_prompt="You are Council worker Alpha.",
        user_content="Evaluate the public question.",
        role_seat="Alpha",
        dialogue_id="reduced-fixture",
        turn_id=turn_id,
        dialogue_phase="baseline",
    )


def _ledger():
    policy = build_reduced_flex_policy_v1()
    profile = _profile()
    authorization = build_reduced_session_authorization_v1(
        policy, profile, session_id="reduced-fixture"
    )
    return policy, profile, OpenRouterSessionLedgerV1(authorization)


class _Completion:
    def __init__(self, status: int = 200, *, completed: bool = True):
        self.http_status = status if completed else None
        self.completed = completed
        self.failure_class = None if completed else "TimeoutError"
        self.retry_count = 0


class _Result:
    def __init__(self, body: bytes, status: int = 200, *, completed: bool = True):
        self.raw_response_body = body
        self.response_headers = (("Content-Type", "application/json"),)
        self.completion = _Completion(status, completed=completed)
        self.registration = None
        self.dispatched_body = b""


def _success_bytes(
    *,
    model: str = "openai/gpt-5-mini",
    provider: str = "OpenAI",
    content: str = (
        '{"content":{"claim":"x","epistemic_marker":'
        '"reasonable_hypothesis"},"confidence":0.5}'
    ),
    cost_decimal: str = "0.000001234567",
) -> bytes:
    # Keep cost as a JSON decimal lexeme so the executor can prove exact Decimal
    # conversion instead of inheriting binary-float rounding.
    payload = {
        "id": "gen-fixture",
        "model": model,
        "provider": provider,
        "object": "chat.completion",
        "created": 1,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {
            "prompt_tokens": 32,
            "completion_tokens": 20,
            "total_tokens": 52,
            "cost": "__EXACT_COST__",
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encoded.replace('"__EXACT_COST__"', cost_decimal).encode("utf-8")


def test_exact_flex_endpoint_profile_preserves_absent_request_price_as_unknown() -> None:
    raw = _endpoint_bytes()
    evidence = validate_flex_endpoint_listing_v1(raw)
    assert evidence.endpoint_model_id == REDUCED_MODEL_V1
    assert evidence.provider_selector == "openai/flex"
    assert evidence.output_limit_parameter == "max_tokens"
    assert evidence.request_price_usd is None
    assert evidence.request_price_state == "ABSENT_UNKNOWN"
    assert evidence.temperature_supported is False
    assert evidence.max_prompt_tokens_observed == 272_000
    assert evidence.fresh_listing_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"status": 1}, "not healthy"),
        ({"model_id": "openai/gpt-5"}, "not unique"),
        ({"context_length": 399_999}, "below the 400k"),
        ({"max_completion_tokens": 1_023}, "below 1024"),
        ({"provider_name": "Another"}, "display identity"),
        ({"pricing": {"prompt": "0.000000126", "completion": "0.000001"}}, "prompt price"),
        ({"pricing": {"prompt": "0.000000125", "completion": "0.000001001"}}, "completion price"),
        ({"pricing": {"prompt": "0.000000125", "completion": "0.000001", "request": "0.01"}}, "request price"),
    ],
)
def test_flex_endpoint_semantic_drift_fails_closed(mutation, message) -> None:
    with pytest.raises(ContractValidationError, match=message):
        validate_flex_endpoint_listing_v1(_endpoint_bytes(**mutation))


def test_missing_seed_capability_fails_closed() -> None:
    parameters = json.loads(_endpoint_bytes())["data"]["endpoints"][0][
        "supported_parameters"
    ]
    parameters.remove("seed")
    with pytest.raises(ContractValidationError, match="seed"):
        validate_flex_endpoint_listing_v1(
            _endpoint_bytes(supported_parameters=parameters)
        )


def test_p19_whole_context_arithmetic_and_session_cap_are_exact() -> None:
    policy, profile, ledger = _ledger()
    assert policy.temperature is None
    assert policy.seed == 0
    assert conservative_turn_cost_bound_v1(
        policy, REDUCED_MAX_INPUT_TOKENS_V1
    ) == REDUCED_PER_CALL_BOUND_PICODOLLARS_V1
    assert REDUCED_PER_CALL_BOUND_PICODOLLARS_V1 == 51_024_000_000
    assert REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1 == (
        REDUCED_MAX_CALLS_V1 * REDUCED_PER_CALL_BOUND_PICODOLLARS_V1
    )
    assert REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1 == 7_704_624_000_000
    assert ledger.authorization.maximum_total_spend_picodollars == (
        REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
    )
    assert ledger.authorization.maximum_total_spend_picodollars == 8_000_000_000_000
    assert ledger.authorization.maximum_calls == 151
    assert profile.provider_selector == "openai/flex"


def test_legacy_policy_and_turn_record_content_ids_are_byte_stable() -> None:
    legacy_policy = OpenRouterFrozenExecutionPolicyV1(
        model="openai/gpt-4.1-mini",
        provider_only=("azure/swedencentral",),
        provider_order=("azure/swedencentral",),
        output_limit_tokens=256,
        max_price_prompt_usd_per_million="0.50",
        max_price_completion_usd_per_million="2.00",
        max_price_request_usd="0",
        bounded_timeout_seconds=30,
    )
    assert legacy_policy.seed is None
    assert legacy_policy.policy_id == (
        "szorexecutionpolicyv1_"
        "c262de59c96bec4f4f6d342e50348ffbb8ecc98413ac8457e9630ae932afcacd"
    )

    legacy_record = OpenRouterTurnRecordV1(
        dialogue_id="dialogue-1",
        turn_id="turn-1",
        role_seat="questioner",
        dialogue_phase="elenchus",
        model="openai/gpt-4.1-mini",
        provider_selector="azure/swedencentral",
        request_id="request-1",
        body_sha256="a" * 64,
        http_status=200,
        transport_completed=True,
        worst_case_picodollars=524_300_000_000,
        actual_served_model="openai/gpt-4.1-mini",
        provider_display_name="Azure",
        s5_envelope_kind="SUCCESS",
        assistant_text_excerpt="hello",
    )
    assert legacy_record.retry_count == 0
    assert legacy_record.response_body_sha256 is None
    assert legacy_record.record_id == (
        "szorturnrecordv1_"
        "061e0b5366ac1aeb60f976891b0692c3625eb35b8ff2779709a67167c4da1a94"
    )


def test_151_missing_cost_reports_fit_but_a_152nd_call_is_refused() -> None:
    _, _, ledger = _ledger()
    for _ in range(151):
        ledger.check_admits(REDUCED_PER_CALL_BOUND_PICODOLLARS_V1)
        ledger.record_dispatch(REDUCED_PER_CALL_BOUND_PICODOLLARS_V1)
    assert ledger.committed_picodollars == 7_704_624_000_000
    with pytest.raises(OpenRouterSessionBudgetExceeded, match="call limit"):
        ledger.check_admits(REDUCED_PER_CALL_BOUND_PICODOLLARS_V1)


def test_rendered_flex_body_has_strict_schema_seed_and_no_sampling_or_reasoning(
    tmp_path: Path,
) -> None:
    policy, profile, ledger = _ledger()
    sent = []

    def dispatch(**kwargs):
        sent.append(kwargs)
        return _Result(_success_bytes())

    outcome = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn("render-only"),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        pre_dispatch_guard=lambda _task, rendered: (
            assert_reduced_flex_rendered_turn_v1(rendered)
        ),
        dispatch=dispatch,
    )
    body = json.loads(sent[0]["body_bytes"])
    assert body["max_tokens"] == 1024
    assert body["seed"] == 0
    assert body["response_format"] == _schema()
    assert "temperature" not in body
    assert "reasoning" not in body
    assert "reasoning_effort" not in body
    assert outcome.failure_reason is None


def test_hidden_evaluator_canary_is_stopped_before_dispatch(tmp_path: Path) -> None:
    policy, profile, ledger = _ledger()
    guard = make_hidden_evaluator_guard_v1(
        forbidden_values=("PRIVATE-EVALUATOR-CANARY",)
    )
    turn = OpenRouterDynamicTurnRequestV1(
        **{
            **_turn().model_dump(exclude={"turn_content_id"}),
            "user_content": "PRIVATE-EVALUATOR-CANARY",
        }
    )
    calls = []
    with pytest.raises(ContractValidationError, match="hidden evaluator value"):
        execute_bounded_text_turn_v1(
            policy=policy,
            profile=profile,
            ledger=ledger,
            claim_directory=tmp_path,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            turn=turn,
            response_format_override=_schema(),
            expected_returned_models=(REDUCED_MODEL_V1,),
            expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
            pre_dispatch_guard=guard,
            dispatch=lambda **kwargs: calls.append(kwargs),
        )
    assert calls == []
    assert ledger.calls_consumed == 0
    assert list(tmp_path.iterdir()) == []


def test_generic_executor_binds_identity_and_records_full_sanitized_output(
    tmp_path: Path,
) -> None:
    policy, profile, ledger = _ledger()
    visible = (
        '{"content":{"claim":"' + "x" * 800 +
        ' sk-or-v1-THISISASECRET123"},"confidence":0.5}'
    )
    outcome = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn(),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=lambda **kwargs: _Result(_success_bytes(content=visible)),
    )
    assert outcome.failure_reason is None
    assert outcome.assistant_text == visible
    assert outcome.record.actual_served_model == REDUCED_MODEL_V1
    assert outcome.record.provider_display_name == "OpenAI"
    assert outcome.record.returned_model_binding_ok is True
    assert outcome.record.returned_provider_binding_ok is True
    assert outcome.record.prompt_tokens == 32
    assert outcome.record.completion_tokens == 20
    assert outcome.record.observed_cost_usd_decimal == "0.000001234567"
    assert outcome.record.observed_cost_picodollars == 1_234_567
    assert len(outcome.record.assistant_output_sanitized or "") > 800
    assert "THISISASECRET123" not in outcome.record.assistant_output_sanitized
    assert "[REDACTED]" in outcome.record.assistant_output_sanitized
    assert ledger.calls_consumed == 1
    assert ledger.unsettled_reserved_picodollars == 0


@pytest.mark.parametrize(
    "model, provider, failure",
    [
        ("openai/gpt-5", "OpenAI", "returned_model_identity_mismatch"),
        ("openai/gpt-5-mini", "Azure", "returned_provider_identity_mismatch"),
    ],
)
def test_returned_model_and_provider_mismatches_fail_closed(
    tmp_path: Path, model: str, provider: str, failure: str
) -> None:
    policy, profile, ledger = _ledger()
    outcome = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn(),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=lambda **kwargs: _Result(
            _success_bytes(model=model, provider=provider)
        ),
    )
    assert outcome.assistant_text is None
    assert outcome.failure_reason == failure
    assert outcome.record.failure_class == failure
    assert ledger.calls_consumed == 1


def test_unknown_dispatch_exception_is_charged_and_never_retried(tmp_path: Path) -> None:
    policy, profile, ledger = _ledger()
    calls = []

    def dispatch(**kwargs):
        calls.append(kwargs)
        raise OSError("connection outcome unknown")

    outcome = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn(),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=dispatch,
    )
    assert len(calls) == 1
    assert outcome.failure_reason == "dispatch_exception:OSError"
    assert ledger.calls_consumed == 1
    assert ledger.unsettled_reserved_picodollars == (
        REDUCED_PER_CALL_BOUND_PICODOLLARS_V1
    )


def test_duplicate_turn_claim_cannot_dispatch_twice(tmp_path: Path) -> None:
    policy, profile, ledger = _ledger()
    calls = []

    def dispatch(**kwargs):
        calls.append(kwargs)
        return _Result(_success_bytes())

    kwargs = dict(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn(),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=dispatch,
    )
    execute_bounded_text_turn_v1(**kwargs)
    with pytest.raises(ContractValidationError, match="already consumed"):
        execute_bounded_text_turn_v1(**kwargs)
    assert len(calls) == 1


def _task_and_state():
    task = AgentTask(
        task_id="task-alpha",
        session_id="session-alpha",
        agent_id="worker_alpha",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.INITIAL_RESPONSE,
        question="What is knowledge?",
        context={
            "council_roster": [{"seat": "worker_alpha", "model": "Alpha"}],
            "public_commitments": [
                {
                    "provider_id": "worker_beta",
                    "model_id": REDUCED_MODEL_V1,
                    "claim": f"Authored internally by {REDUCED_MODEL_V1}",
                }
            ],
        },
        output_schema={},
        task_kind=TaskKind.INITIAL_RESPONSE,
        round_number=1,
    )
    state = AgentState(
        agent_id="worker_alpha",
        primary_role=AgentRole.SOCRATES,
        assigned_role=AgentRole.SOCRATES,
        round_number=1,
    )
    return task, state


def test_adapter_exposes_alias_to_workers_but_real_model_to_evaluator(
    tmp_path: Path,
) -> None:
    policy, profile, ledger = _ledger()
    sent = []

    def dispatch(**kwargs):
        sent.append(kwargs)
        return _Result(_success_bytes())

    adapter = SocratesLiveOpenRouterAdapter(
        provider_id=WORKER_PROVIDER_IDS_V1[0],
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        dispatch=dispatch,
        response_format_factory=lambda task: _schema(),
        pre_dispatch_guard=make_hidden_evaluator_guard_v1(),
        worker_alias=WORKER_ALIASES_V1[0],
        expose_model_identity_to_worker=False,
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        ced_parse_repair_attempts=0,
        structured_output_validator=lambda _task, raw: json.loads(raw),
        outbound_task_state_projector=make_worker_payload_projector_v1(),
    )
    task, state = _task_and_state()
    response = asyncio.run(adapter.generate_agent_move(task, state))
    assert response.status is ProviderStatus.OK
    assert adapter.model == "Alpha"
    assert adapter.provider_name == "Council worker Alpha"
    assert adapter.authoritative_model_id() == REDUCED_MODEL_V1
    body = json.loads(sent[0]["body_bytes"])
    messages = json.dumps(body["messages"])
    assert REDUCED_MODEL_V1 not in messages
    assert "built by OpenAI" not in messages
    assert body["model"] == REDUCED_MODEL_V1  # routing, not worker-visible content
    assert json.dumps(body).count(REDUCED_MODEL_V1) == 1
    assert "anonymous-model" in messages
    assert "Beta" in messages
    row = adapter.observability_rows()[0]
    assert row["model"] == REDUCED_MODEL_V1
    assert row["task_kind"] == "initial_response"
    assert row["provider_structured_output_valid"] is True
    assert row["ced_move_accepted"] is True
    assert row["assistant_output_sanitized"] == (
        '{"content":{"claim":"x","epistemic_marker":'
        '"reasonable_hypothesis"},"confidence":0.5}'
    )
    assert response.repair_attempted is False


def test_identity_failure_trips_shared_session_latch_before_next_post(
    tmp_path: Path,
) -> None:
    policy, profile, ledger = _ledger()
    calls = []

    def dispatch(**kwargs):
        calls.append(kwargs)
        return _Result(_success_bytes(model="openai/gpt-5"))

    first = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn("fatal-first"),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=dispatch,
    )
    assert first.failure_reason == "returned_model_identity_mismatch"
    assert ledger.fatal_failure == "returned_model_identity_mismatch"

    with pytest.raises(ContractValidationError, match="fatally stopped"):
        execute_bounded_text_turn_v1(
            policy=policy,
            profile=profile,
            ledger=ledger,
            claim_directory=tmp_path,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            turn=_turn("fatal-second"),
            response_format_override=_schema(),
            expected_returned_models=(REDUCED_MODEL_V1,),
            expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
            dispatch=dispatch,
        )
    assert len(calls) == 1


def test_observed_cost_over_p19_is_settled_then_fatally_stops_session(
    tmp_path: Path,
) -> None:
    policy, profile, ledger = _ledger()
    calls = []

    def dispatch(**kwargs):
        calls.append(kwargs)
        return _Result(_success_bytes(cost_decimal="0.060000000000"))

    first = execute_bounded_text_turn_v1(
        policy=policy,
        profile=profile,
        ledger=ledger,
        claim_directory=tmp_path,
        max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
        turn=_turn("cost-overrun-first"),
        response_format_override=_schema(),
        expected_returned_models=(REDUCED_MODEL_V1,),
        expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
        dispatch=dispatch,
    )
    assert first.assistant_text is None
    assert first.failure_reason == "observed_cost_exceeds_p19_reservation"
    assert first.record.observed_cost_picodollars == 60_000_000_000
    assert first.record.observed_cost_within_p19_bound is False
    assert first.record.committed_cost_within_session_ceiling is True
    assert ledger.settled_picodollars == 60_000_000_000
    assert ledger.unsettled_reserved_picodollars == 0
    assert ledger.fatal_failure == "observed_cost_exceeds_p19_reservation"

    with pytest.raises(ContractValidationError, match="fatally stopped"):
        execute_bounded_text_turn_v1(
            policy=policy,
            profile=profile,
            ledger=ledger,
            claim_directory=tmp_path,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            turn=_turn("cost-overrun-second"),
            response_format_override=_schema(),
            expected_returned_models=(REDUCED_MODEL_V1,),
            expected_provider_display_names=(REDUCED_PROVIDER_DISPLAY_NAME_V1,),
            dispatch=dispatch,
        )
    assert len(calls) == 1


def test_sanitizer_keeps_normal_output_and_masks_only_secret_shapes() -> None:
    text = "Discuss authorization generally; Bearer abcdefghijklmnop; api_key=topsecret123"
    clean = sanitize_public_assistant_output_v1(text)
    assert "Discuss authorization generally" in clean
    assert "abcdefghijklmnop" not in clean
    assert "topsecret123" not in clean
    assert clean.count("[REDACTED]") == 2

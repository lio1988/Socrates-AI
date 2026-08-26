"""Focused offline tests for the sealed OpenRouter canned acquisition adapter."""

from __future__ import annotations

import ast
import asyncio
import base64
import contextvars
import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero import openrouter_acquisition_adapter as adapter_module
from backend.dialogues.socrates_zero.acquisition_tripwires import (
    AcquisitionBoundaryViolation,
)
from backend.dialogues.socrates_zero.contracts import canonical_json
from backend.dialogues.socrates_zero.openrouter_acquisition_adapter import (
    OpenRouterAcquisitionAdapterError,
    OpenRouterAcquisitionAdapterV0,
    OpenRouterAcquisitionFailureCode,
    OpenRouterCannedInvocationOutcome,
    OpenRouterCannedTransportDirectiveV0,
    OpenRouterCannedTransportV0,
    acquire_openrouter_canned_v0,
)
from backend.dialogues.socrates_zero.openrouter_acquisition_contracts import (
    OPENROUTER_ACQUISITION_ADAPTER_ID,
    OPENROUTER_MAX_OUTPUT_TOKENS,
    OPENROUTER_MODEL_ID,
    OpenRouterAttemptOutcome,
    OpenRouterCapabilitySnapshot,
    OpenRouterCannedResponseEnvelope,
    OpenRouterControlPolicy,
    OpenRouterCostBound,
    OpenRouterEndpointPolicy,
    OpenRouterEvidenceState,
    OpenRouterIdentityEvidence,
    OpenRouterPreparedBody,
    OpenRouterPricingRecord,
    OpenRouterRawResponseEvidence,
    OpenRouterRoutePolicy,
    OpenRouterTokenPolicy,
    OpenRouterTransportPolicy,
    OpenRouterTransportStatus,
    OpenRouterUsageCompleteness,
    OpenRouterUsageEvidence,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SOURCE = (
    REPOSITORY_ROOT
    / "backend"
    / "dialogues"
    / "socrates_zero"
    / "openrouter_acquisition_adapter.py"
)


def _graph():
    endpoint = OpenRouterEndpointPolicy()
    transport_policy = OpenRouterTransportPolicy()
    route = OpenRouterRoutePolicy()
    control = OpenRouterControlPolicy()
    body = OpenRouterPreparedBody(
        endpoint_policy_id=endpoint.endpoint_policy_id or "",
        route_policy_id=route.route_policy_id or "",
        control_policy_id=control.control_policy_id or "",
        canonical_body_json=canonical_json(
            {
                "model": OPENROUTER_MODEL_ID,
                "messages": [
                    {"role": "system", "content": "Ask one concise question."},
                    {"role": "user", "content": "What is knowledge?"},
                ],
                "temperature": 0.0,
                "max_tokens": OPENROUTER_MAX_OUTPUT_TOKENS,
                "stream": False,
                "tools": [],
                "response_format": {"type": "text"},
            }
        ),
    )
    token_policy = OpenRouterTokenPolicy.from_prepared_body(body)
    pricing = OpenRouterPricingRecord()
    cost = OpenRouterCostBound(token_policy=token_policy, pricing_record=pricing)
    capability = OpenRouterCapabilitySnapshot(
        prepared_body_id=body.prepared_body_id or "",
        endpoint_policy=endpoint,
        transport_policy=transport_policy,
        route_policy=route,
        control_policy=control,
        token_policy=token_policy,
        pricing_record=pricing,
        cost_bound=cost,
    )
    return body, control, token_policy, capability


def _raw_payload(
    control: OpenRouterControlPolicy,
    token_policy: OpenRouterTokenPolicy,
    *,
    content: str = "What do you mean by knowledge?",
) -> dict[str, object]:
    configuration = (control.control_policy_id or "").split("_", 1)[-1]
    input_tokens = min(10, token_policy.payload_input_token_upper_bound)
    return {
        "id": "canned-adapter-response-1",
        "provider": "openrouter",
        "model": OPENROUTER_MODEL_ID,
        "configuration_digest": configuration,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "fallback_used": False,
        "explicit_retry_count": 0,
        "adapter_retry_count": 0,
        "sdk_internal_retry_count": None,
        "hidden_transport_retry_count": 0,
        "stream_used": False,
        "tool_calls": 0,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": 8,
            "total_tokens": input_tokens + 8,
        },
    }


def _raw_from_payload(payload: object) -> OpenRouterRawResponseEvidence:
    raw_bytes = canonical_json(payload).encode("utf-8")
    return OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(raw_bytes).decode("ascii"),
    )


def _identity(control: OpenRouterControlPolicy) -> OpenRouterIdentityEvidence:
    configuration = (control.control_policy_id or "").split("_", 1)[-1]
    return OpenRouterIdentityEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        requested_configuration_digest=configuration,
        actual_router_id="openrouter",
        actual_model_id=OPENROUTER_MODEL_ID,
        actual_configuration_digest=configuration,
        router_identity_match=True,
        model_identity_match=True,
        configuration_identity_match=True,
        identity_match=True,
        exact_router_model_configuration_verified=True,
    )


def _usage(
    token_policy: OpenRouterTokenPolicy,
    payload: dict[str, object],
) -> OpenRouterUsageEvidence:
    values = payload["usage"]
    assert isinstance(values, dict)
    return OpenRouterUsageEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        token_completeness=OpenRouterUsageCompleteness.COMPLETE,
        token_policy=token_policy,
        input_tokens=values["input_tokens"],
        output_tokens=values["output_tokens"],
        total_tokens=values["total_tokens"],
    )


def _envelope(
    body: OpenRouterPreparedBody,
    control: OpenRouterControlPolicy,
    token_policy: OpenRouterTokenPolicy,
    *,
    content: str = "What do you mean by knowledge?",
) -> OpenRouterCannedResponseEnvelope:
    payload = _raw_payload(control, token_policy, content=content)
    return OpenRouterCannedResponseEnvelope(
        transport_attempt_id="adapter-attempt-1",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=_raw_from_payload(payload),
        identity_evidence=_identity(control),
        usage_evidence=_usage(token_policy, payload),
        timeout_fired=False,
        cancellation_requested=False,
    )


def _run(
    transport: OpenRouterCannedTransportV0,
    *,
    body: OpenRouterPreparedBody,
    capability: OpenRouterCapabilitySnapshot,
):
    return asyncio.run(
        acquire_openrouter_canned_v0(
            semantic_request_id="adapter-semantic-request-1",
            transport_attempt_id="adapter-attempt-1",
            prepared_body=body,
            capability_snapshot=capability,
            transport=transport,
        )
    )


def _transport_with_envelope(envelope: OpenRouterCannedResponseEnvelope):
    return OpenRouterCannedTransportV0(
        OpenRouterCannedTransportDirectiveV0(envelope=envelope)
    )


def _replace_raw(
    envelope: OpenRouterCannedResponseEnvelope,
    raw: OpenRouterRawResponseEvidence | None,
) -> OpenRouterCannedResponseEnvelope:
    return envelope.model_copy(update={"raw_response": raw})


def test_success_passes_exact_bytes_once_and_keeps_content_opaque_and_immutable() -> None:
    body, control, token_policy, capability = _graph()
    opaque = "authorization api_key Bearer sk- are opaque assistant prose"
    envelope = _envelope(body, control, token_policy, content=opaque)
    transport = _transport_with_envelope(envelope)

    result = _run(transport, body=body, capability=capability)

    assert result.outcome is OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED
    assert result.failure_code is None
    assert transport.invocation_count == 1
    assert transport.invocation_records == (result.invocation_record,)
    record = result.invocation_record
    assert record is not None
    assert record.received_body_bytes == body.body_bytes
    assert record.received_body_sha256 == body.sha256
    assert record.received_body_byte_length == body.byte_length
    assert record.outcome is OpenRouterCannedInvocationOutcome.RETURNED
    raw = result.receipt.raw_response
    assert raw is not None and opaque in (raw.raw_bytes or b"").decode("utf-8")
    assert result.receipt.identity_evidence == envelope.identity_evidence
    assert result.receipt.usage_evidence == envelope.usage_evidence
    assert result.admission_status == "UNADMITTED"
    assert result.governance_status == "NON_GOVERNING"
    assert result.ced_application_count == 0
    assert result.live_authorization_allowed is False
    with pytest.raises(ValidationError, match="frozen"):
        result.receipt.failure_code = "MUTATED"  # type: ignore[misc]

    frozen_receipt = result.receipt.model_dump_json()
    frozen_records = transport.invocation_records
    with pytest.raises(OpenRouterAcquisitionAdapterError, match="invalid or consumed"):
        _run(transport, body=body, capability=capability)
    assert transport.invocation_count == 1
    assert transport.invocation_records == frozen_records
    assert result.receipt.model_dump_json() == frozen_receipt


def test_authoritative_entry_requires_active_tripwire_before_dispatch() -> None:
    body, control, token_policy, capability = _graph()
    transport = _transport_with_envelope(_envelope(body, control, token_policy))
    coroutine = acquire_openrouter_canned_v0(
        semantic_request_id="adapter-semantic-request-1",
        transport_attempt_id="adapter-attempt-1",
        prepared_body=body,
        capability_snapshot=capability,
        transport=transport,
    )
    empty_context = contextvars.Context()
    with pytest.raises(AcquisitionBoundaryViolation, match="active"):
        empty_context.run(asyncio.run, coroutine)
    assert transport.invocation_count == 0
    assert transport.invocation_records == ()


def test_opaque_transport_error_fails_once_without_retry_or_response_evidence() -> None:
    body, _, _, capability = _graph()
    transport = OpenRouterCannedTransportV0(
        OpenRouterCannedTransportDirectiveV0(error_code="CANNED_OPAQUE_ERROR")
    )
    result = _run(transport, body=body, capability=capability)
    assert result.outcome is OpenRouterAttemptOutcome.FAILED_CLOSED
    assert result.failure_code is OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR
    assert result.receipt.canned_transport_invocations == 1
    assert result.receipt.raw_response is None
    assert result.receipt.identity_evidence is None
    assert result.receipt.usage_evidence is None
    assert transport.invocation_count == 1
    assert transport.invocation_records[0].outcome is OpenRouterCannedInvocationOutcome.RAISED


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ({"headers": {"Authorization": "non-secret-presence-sentinel"}}, OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE),
        ({"provider": "wrong-router"}, OpenRouterAcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH),
        ({"model": None}, OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISSING),
        ({"model": "other/model"}, OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISMATCH),
        ({"configuration_digest": "f" * 64}, OpenRouterAcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH),
        ({"fallback_used": True}, OpenRouterAcquisitionFailureCode.FALLBACK_ACTIVATED),
        ({"explicit_retry_count": 1}, OpenRouterAcquisitionFailureCode.RETRY_ACTIVATED),
        ({"stream_used": True}, OpenRouterAcquisitionFailureCode.STREAMING_RESPONSE_DETECTED),
        ({"tool_calls": 1}, OpenRouterAcquisitionFailureCode.TOOL_ACTIVATED),
        ({"usage": None}, OpenRouterAcquisitionFailureCode.USAGE_INCOMPLETE),
        ({"usage": {"input_tokens": 10, "output_tokens": 8, "total_tokens": 19}}, OpenRouterAcquisitionFailureCode.USAGE_INCONSISTENT),
        ({"usage": {"input_tokens": 10, "output_tokens": 257, "total_tokens": 267}}, OpenRouterAcquisitionFailureCode.REPORTED_USAGE_EXCEEDS_BOUND),
    ),
)
def test_raw_bytes_are_authoritative_and_every_metadata_failure_is_one_shot(
    mutation: dict[str, object],
    expected: OpenRouterAcquisitionFailureCode,
) -> None:
    body, control, token_policy, capability = _graph()
    valid = _envelope(body, control, token_policy)
    payload = _raw_payload(control, token_policy)
    payload.update(mutation)
    tampered = _replace_raw(valid, _raw_from_payload(payload))
    transport = _transport_with_envelope(tampered)

    result = _run(transport, body=body, capability=capability)

    assert result.outcome is OpenRouterAttemptOutcome.FAILED_CLOSED
    assert result.failure_code is expected
    assert result.receipt.canned_transport_invocations == 1
    assert transport.invocation_count == 1
    assert len(transport.invocation_records) == 1


def test_missing_malformed_and_forged_raw_evidence_fail_once() -> None:
    body, control, token_policy, capability = _graph()
    valid = _envelope(body, control, token_policy)
    missing = _replace_raw(valid, None)
    malformed_raw = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(b"not-json").decode("ascii"),
    )
    malformed = _replace_raw(valid, malformed_raw)
    forged_raw = valid.raw_response.model_copy(update={"reported_sha256": "f" * 64})
    forged = _replace_raw(valid, forged_raw)

    for envelope, expected in (
        (missing, OpenRouterAcquisitionFailureCode.MISSING_RAW_RESPONSE),
        (malformed, OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE),
        (forged, OpenRouterAcquisitionFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH),
    ):
        transport = _transport_with_envelope(envelope)
        result = _run(transport, body=body, capability=capability)
        assert result.failure_code is expected
        assert transport.invocation_count == 1
        assert len(transport.invocation_records) == 1


def test_side_identity_usage_and_receipt_failures_never_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body, control, token_policy, capability = _graph()
    valid = _envelope(body, control, token_policy)

    wrong_identity = valid.identity_evidence.model_copy(
        update={"actual_model_id": "other/model"}
    )
    identity_envelope = valid.model_copy(update={"identity_evidence": wrong_identity})
    identity_transport = _transport_with_envelope(identity_envelope)
    identity_result = _run(identity_transport, body=body, capability=capability)
    assert identity_result.failure_code is OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISMATCH
    assert identity_transport.invocation_count == 1

    wrong_usage = valid.usage_evidence.model_copy(update={"total_tokens": 999})
    usage_envelope = valid.model_copy(update={"usage_evidence": wrong_usage})
    usage_transport = _transport_with_envelope(usage_envelope)
    usage_result = _run(usage_transport, body=body, capability=capability)
    assert usage_result.failure_code is OpenRouterAcquisitionFailureCode.USAGE_INCONSISTENT
    assert usage_transport.invocation_count == 1

    receipt_transport = _transport_with_envelope(valid)
    monkeypatch.setattr(
        adapter_module,
        "_build_success_receipt",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("injected receipt failure")),
    )
    receipt_result = _run(receipt_transport, body=body, capability=capability)
    assert receipt_result.failure_code is OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH
    assert receipt_transport.invocation_count == 1
    assert len(receipt_transport.invocation_records) == 1


def test_timeout_resistance_is_cancelled_twice_awaited_and_has_no_late_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body, _, _, capability = _graph()
    transport = OpenRouterCannedTransportV0(
        OpenRouterCannedTransportDirectiveV0(
            wait_for_timeout=True,
            resist_initial_cancellation=True,
        )
    )
    original_wait = asyncio.wait
    first_wait = True

    async def accelerated_wait(tasks, *, timeout=None):
        nonlocal first_wait
        if first_wait:
            first_wait = False
            return set(), set(tasks)
        return await original_wait(tasks, timeout=timeout)

    monkeypatch.setattr(adapter_module.asyncio, "wait", accelerated_wait)

    async def scenario():
        result = await acquire_openrouter_canned_v0(
            semantic_request_id="adapter-semantic-request-1",
            transport_attempt_id="adapter-attempt-1",
            prepared_body=body,
            capability_snapshot=capability,
            transport=transport,
        )
        frozen_receipt = result.receipt.model_dump_json()
        frozen_records = transport.invocation_records
        for _turn in range(3):
            await asyncio.sleep(0)
        leaked = tuple(
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and task.get_name().startswith("socrates-zero-openrouter-canned-acquisition-")
            and not task.done()
        )
        assert leaked == ()
        assert result.receipt.model_dump_json() == frozen_receipt
        assert transport.invocation_records == frozen_records
        return result

    result = asyncio.run(scenario())
    assert result.failure_code is OpenRouterAcquisitionFailureCode.TRANSPORT_TIMEOUT
    record = result.invocation_record
    assert record is not None
    assert record.outcome is OpenRouterCannedInvocationOutcome.FORCED_CLEANUP
    assert record.cancellation_acknowledged is True
    assert record.worker_terminated is True
    assert record.cancellation_requests == 2
    assert record.forced_cleanup is True
    assert transport.invocation_count == 1


def test_cooperative_delayed_return_is_one_shot_and_leaves_no_worker() -> None:
    body, control, token_policy, capability = _graph()
    transport = OpenRouterCannedTransportV0(
        OpenRouterCannedTransportDirectiveV0(
            envelope=_envelope(body, control, token_policy),
            cooperative_yields=3,
        )
    )

    async def scenario():
        result = await acquire_openrouter_canned_v0(
            semantic_request_id="adapter-semantic-request-1",
            transport_attempt_id="adapter-attempt-1",
            prepared_body=body,
            capability_snapshot=capability,
            transport=transport,
        )
        assert not any(
            task is not asyncio.current_task()
            and task.get_name().startswith("socrates-zero-openrouter-canned-")
            and not task.done()
            for task in asyncio.all_tasks()
        )
        return result

    result = asyncio.run(scenario())
    assert result.outcome is OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED
    assert transport.invocation_count == 1
    assert len(transport.invocation_records) == 1


def test_late_mutation_attempt_is_blocked_detected_and_task_is_joined() -> None:
    body, control, token_policy, capability = _graph()
    transport = OpenRouterCannedTransportV0(
        OpenRouterCannedTransportDirectiveV0(
            envelope=_envelope(body, control, token_policy),
            cooperative_yields=1,
            attempt_late_mutation=True,
        )
    )

    async def scenario():
        result = await acquire_openrouter_canned_v0(
            semantic_request_id="adapter-semantic-request-1",
            transport_attempt_id="adapter-attempt-1",
            prepared_body=body,
            capability_snapshot=capability,
            transport=transport,
        )
        assert not any(
            task is not asyncio.current_task()
            and task.get_name().startswith("socrates-zero-openrouter-canned-")
            and not task.done()
            for task in asyncio.all_tasks()
        )
        return result

    result = asyncio.run(scenario())
    assert result.outcome is OpenRouterAttemptOutcome.FAILED_CLOSED
    assert result.failure_code is OpenRouterAcquisitionFailureCode.LATE_MUTATION_DETECTED
    assert transport.invocation_count == 1
    assert len(transport.invocation_records) == 1
    assert transport.invocation_records == (result.invocation_record,)


def test_late_mutation_task_is_settled_on_every_returned_envelope_early_failure() -> None:
    body, control, token_policy, capability = _graph()
    valid = _envelope(body, control, token_policy)
    malformed_raw = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(b"not-json").decode("ascii"),
    )
    malformed = _replace_raw(valid, malformed_raw)
    transport_error = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="adapter-attempt-1",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.ERROR,
        timeout_fired=False,
        cancellation_requested=False,
        transport_error_code="CANNED_ERROR",
    )

    async def scenario(envelope: OpenRouterCannedResponseEnvelope):
        transport = OpenRouterCannedTransportV0(
            OpenRouterCannedTransportDirectiveV0(
                envelope=envelope,
                attempt_late_mutation=True,
            )
        )
        result = await acquire_openrouter_canned_v0(
            semantic_request_id="adapter-semantic-request-1",
            transport_attempt_id="adapter-attempt-1",
            prepared_body=body,
            capability_snapshot=capability,
            transport=transport,
        )
        assert not any(
            task is not asyncio.current_task()
            and task.get_name().startswith("socrates-zero-openrouter-canned-")
            and not task.done()
            for task in asyncio.all_tasks()
        )
        assert transport.invocation_count == 1
        assert len(transport.invocation_records) == 1
        return result

    malformed_result = asyncio.run(scenario(malformed))
    assert malformed_result.failure_code is (
        OpenRouterAcquisitionFailureCode.LATE_MUTATION_DETECTED
    )
    error_result = asyncio.run(scenario(transport_error))
    assert error_result.failure_code is (
        OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR
    )


def test_default_disabled_sealed_facade_is_one_shot_unadmitted_and_non_governing() -> None:
    body, control, token_policy, capability = _graph()
    disabled_transport = _transport_with_envelope(
        _envelope(body, control, token_policy)
    )
    disabled = OpenRouterAcquisitionAdapterV0()
    assert type(disabled) is OpenRouterAcquisitionAdapterV0
    assert disabled.adapter_id == OPENROUTER_ACQUISITION_ADAPTER_ID
    assert disabled.canned_execution_enabled is False
    assert disabled.admission_status == "UNADMITTED"
    assert disabled.governance_status == "NON_GOVERNING"
    assert disabled.ced_application_count == 0
    assert disabled.live_authorization_allowed is False
    assert not any(
        hasattr(disabled, name)
        for name in (
            "apply_observation",
            "apply_to_ced",
            "execute_action",
            "live_acquire",
            "credential",
            "api_key",
        )
    )
    with pytest.raises(OpenRouterAcquisitionAdapterError, match="disabled"):
        asyncio.run(
            disabled.acquire_canned(
                semantic_request_id="adapter-semantic-request-1",
                transport_attempt_id="adapter-attempt-1",
                prepared_body=body,
                capability_snapshot=capability,
                transport=disabled_transport,
            )
        )
    assert disabled_transport.invocation_count == 0
    with pytest.raises(AttributeError, match="sealed"):
        disabled._canned_execution_enabled = True  # type: ignore[misc]
    with pytest.raises(TypeError, match="sealed"):
        type("ForbiddenAdapterSubclass", (OpenRouterAcquisitionAdapterV0,), {})

    enabled = OpenRouterAcquisitionAdapterV0(canned_execution_enabled=True)
    first_transport = _transport_with_envelope(_envelope(body, control, token_policy))
    result = asyncio.run(
        enabled.acquire_canned(
            semantic_request_id="adapter-semantic-request-1",
            transport_attempt_id="adapter-attempt-1",
            prepared_body=body,
            capability_snapshot=capability,
            transport=first_transport,
        )
    )
    assert result.outcome is OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED
    assert result.admission_status == enabled.admission_status == "UNADMITTED"
    assert result.governance_status == enabled.governance_status == "NON_GOVERNING"
    second_transport = _transport_with_envelope(_envelope(body, control, token_policy))
    with pytest.raises(OpenRouterAcquisitionAdapterError, match="consumed"):
        asyncio.run(
            enabled.acquire_canned(
                semantic_request_id="adapter-semantic-request-1",
                transport_attempt_id="adapter-attempt-1",
                prepared_body=body,
                capability_snapshot=capability,
                transport=second_transport,
            )
        )
    assert first_transport.invocation_count == 1
    assert second_transport.invocation_count == 0


def test_facade_pre_dispatch_failure_consumes_the_one_shot_without_dispatch() -> None:
    body, control, token_policy, capability = _graph()
    facade = OpenRouterAcquisitionAdapterV0(canned_execution_enabled=True)
    invalid_transport = _transport_with_envelope(
        _envelope(body, control, token_policy)
    )
    with pytest.raises(OpenRouterAcquisitionAdapterError, match="semantic request"):
        asyncio.run(
            facade.acquire_canned(
                semantic_request_id="api_key-forbidden-identifier",
                transport_attempt_id="adapter-attempt-1",
                prepared_body=body,
                capability_snapshot=capability,
                transport=invalid_transport,
            )
        )
    assert invalid_transport.invocation_count == 0

    valid_transport = _transport_with_envelope(_envelope(body, control, token_policy))
    with pytest.raises(OpenRouterAcquisitionAdapterError, match="consumed"):
        asyncio.run(
            facade.acquire_canned(
                semantic_request_id="adapter-semantic-request-1",
                transport_attempt_id="adapter-attempt-1",
                prepared_body=body,
                capability_snapshot=capability,
                transport=valid_transport,
            )
        )
    assert valid_transport.invocation_count == 0


def test_caller_cancellation_awaits_worker_termination_and_does_not_retry() -> None:
    body, _, _, capability = _graph()
    transport = OpenRouterCannedTransportV0(
        OpenRouterCannedTransportDirectiveV0(wait_for_timeout=True)
    )

    async def scenario() -> None:
        task = asyncio.create_task(
            acquire_openrouter_canned_v0(
                semantic_request_id="adapter-semantic-request-1",
                transport_attempt_id="adapter-attempt-1",
                prepared_body=body,
                capability_snapshot=capability,
                transport=transport,
            )
        )
        while transport.invocation_count == 0:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not any(
            child is not asyncio.current_task()
            and child.get_name().startswith("socrates-zero-openrouter-canned-acquisition-")
            and not child.done()
            for child in asyncio.all_tasks()
        )

    asyncio.run(scenario())
    assert transport.invocation_count == 1
    assert len(transport.invocation_records) == 1
    assert transport.invocation_records[0].worker_terminated is True


def test_transport_construction_tamper_is_rejected_before_invocation() -> None:
    body, control, token_policy, capability = _graph()
    transport = _transport_with_envelope(_envelope(body, control, token_policy))
    object.__setattr__(
        transport,
        "_directive",
        OpenRouterCannedTransportDirectiveV0(error_code="CANNED_TAMPER"),
    )
    with pytest.raises(OpenRouterAcquisitionAdapterError, match="seal"):
        _run(transport, body=body, capability=capability)
    assert transport.invocation_count == 0
    assert transport.invocation_records == ()


def _imports(tree: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return tuple(names)


def test_adapter_has_no_live_runtime_import_or_production_wiring() -> None:
    tree = ast.parse(ADAPTER_SOURCE.read_text(encoding="utf-8"))
    imports = _imports(tree)
    forbidden_roots = {
        "aiohttp",
        "http",
        "httpx",
        "os",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    }
    assert not {name.split(".", 1)[0] for name in imports}.intersection(forbidden_roots)
    assert not any(
        fragment in name
        for name in imports
        for fragment in (
            "openrouter_provider",
            "provider_registry",
            "ced",
            "puct",
            "strategy",
            "openrouter_acquisition_renderer",
            "openrouter_acquisition_cases",
            "openrouter_acquisition_evaluation",
        )
    )

    production_sources = (
        REPOSITORY_ROOT / "backend" / "dialogues" / "provider_registry.py",
        REPOSITORY_ROOT / "backend" / "dialogues" / "ced.py",
        REPOSITORY_ROOT / "backend" / "dialogues" / "conversation.py",
        REPOSITORY_ROOT / "backend" / "dialogues" / "socrates_zero" / "__init__.py",
    )
    for source in production_sources:
        production_tree = ast.parse(source.read_text(encoding="utf-8"))
        assert not any(
            "openrouter_acquisition_adapter" in imported
            for imported in _imports(production_tree)
        )


def test_exact_prepared_byte_digest_is_not_merely_length_equivalence() -> None:
    body, control, token_policy, capability = _graph()
    transport = _transport_with_envelope(_envelope(body, control, token_policy))
    result = _run(transport, body=body, capability=capability)
    record = result.invocation_record
    assert record is not None
    assert record.received_body_bytes == body.canonical_body_json.encode("utf-8")
    assert record.received_body_sha256 == hashlib.sha256(record.received_body_bytes).hexdigest()
    assert record.received_body_sha256 == body.sha256

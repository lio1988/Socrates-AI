"""Offline-only tests for OpenRouter acquisition adapter-control contracts."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_acquisition_contracts import (
    OPENROUTER_ENDPOINT_URL,
    OPENROUTER_CANNED_CANCELLATION_GRACE_MS,
    OPENROUTER_CANNED_CLEANUP_ROUNDS,
    OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES,
    OPENROUTER_COST_CALCULATION_RULE,
    OPENROUTER_INPUT_BOUND_METHOD,
    OPENROUTER_IDENTITY_SOURCE_FIELDS,
    OPENROUTER_LOCALLY_DERIVED_USAGE_FIELDS,
    OPENROUTER_LOCALLY_DERIVED_USAGE_SOURCE_FIELDS,
    OPENROUTER_MAX_OUTPUT_TOKENS,
    OPENROUTER_MODEL_ID,
    OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS,
    OPENROUTER_REFERENCE_RAW_RESPONSE_MAX_BYTES,
    OPENROUTER_TIMEOUT_MS,
    MAX_SIGNED_64,
    calculate_openrouter_cost_line_microusd,
    OpenRouterAttemptOutcome,
    OpenRouterAttemptReceipt,
    OpenRouterCapabilitySnapshot,
    OpenRouterCannedResponseEnvelope,
    OpenRouterControlPolicy,
    OpenRouterCostBound,
    OpenRouterEndpointPolicy,
    OpenRouterEvidenceState,
    OpenRouterFinishReason,
    OpenRouterIdentityEvidence,
    OpenRouterPreparedBody,
    OpenRouterPrivacyClassification,
    OpenRouterPricingRecord,
    OpenRouterRawResponseEvidence,
    OpenRouterRawRetentionState,
    OpenRouterResponseValidationState,
    OpenRouterRoutePolicy,
    OpenRouterTokenPolicy,
    OpenRouterTransportPolicy,
    OpenRouterTransportStatus,
    OpenRouterUsageCompleteness,
    OpenRouterUsageEvidence,
    OpenRouterUsageSource,
)


_REFERENCE_ASSISTANT_TEXT = "What do you mean by knowledge?"


def _policies():
    return (
        OpenRouterEndpointPolicy(),
        OpenRouterTransportPolicy(),
        OpenRouterRoutePolicy(),
        OpenRouterControlPolicy(),
    )


def _body_mapping() -> dict[str, object]:
    return {
        "model": OPENROUTER_MODEL_ID,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ask one concise opening Socratic question without answering "
                    "the user's question."
                ),
            },
            {
                "role": "user",
                "content": "Is knowledge merely justified true belief?",
            },
        ],
        "temperature": 0.0,
        "max_tokens": OPENROUTER_MAX_OUTPUT_TOKENS,
        "stream": False,
        "tools": [],
        "response_format": {"type": "text"},
    }


def _prepared_body(
    endpoint: OpenRouterEndpointPolicy,
    route: OpenRouterRoutePolicy,
    control: OpenRouterControlPolicy,
) -> OpenRouterPreparedBody:
    return OpenRouterPreparedBody(
        endpoint_policy_id=endpoint.endpoint_policy_id or "",
        route_policy_id=route.route_policy_id or "",
        control_policy_id=control.control_policy_id or "",
        canonical_body_json=canonical_json(_body_mapping()),
    )


def _graph(*, synthetic_price: bool = False):
    endpoint, transport, route, control = _policies()
    body = _prepared_body(endpoint, route, control)
    tokens = OpenRouterTokenPolicy.from_prepared_body(body)
    if synthetic_price:
        pricing = OpenRouterPricingRecord(
            pricing_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            input_microusd_per_million_tokens=1_000_000,
            output_microusd_per_million_tokens=2_000_000,
            fixed_non_token_microusd=3,
            authority_reference="synthetic-test-only",
            source_name="synthetic-test-only",
            source_version="synthetic-pricing/v0",
            effective_version="synthetic-effective/v0",
            provenance_sha256=hashlib.sha256(
                b"socrateszero-openrouter-synthetic-pricing/v0"
            ).hexdigest(),
            unknown_line_items=(),
        )
        cost = OpenRouterCostBound(
            token_policy=tokens,
            pricing_record=pricing,
            unknown_line_items=(),
        )
    else:
        pricing = OpenRouterPricingRecord()
        cost = OpenRouterCostBound(token_policy=tokens, pricing_record=pricing)
    capability = OpenRouterCapabilitySnapshot(
        prepared_body_id=body.prepared_body_id or "",
        endpoint_policy=endpoint,
        transport_policy=transport,
        route_policy=route,
        control_policy=control,
        token_policy=tokens,
        pricing_record=pricing,
        cost_bound=cost,
    )
    return endpoint, transport, route, control, body, tokens, pricing, cost, capability


def _raw_payload(
    control: OpenRouterControlPolicy,
    tokens: OpenRouterTokenPolicy,
    *,
    assistant_text: str = _REFERENCE_ASSISTANT_TEXT,
) -> dict[str, object]:
    digest = (control.control_policy_id or "").split("_", 1)[-1]
    input_tokens = min(100, tokens.payload_input_token_upper_bound)
    return {
        "id": "canned-response-1",
        "provider": "openrouter",
        "model": OPENROUTER_MODEL_ID,
        "configuration_digest": digest,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": assistant_text},
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


def _raw(
    control: OpenRouterControlPolicy | None = None,
    tokens: OpenRouterTokenPolicy | None = None,
    *,
    assistant_text: str = _REFERENCE_ASSISTANT_TEXT,
) -> OpenRouterRawResponseEvidence:
    if control is None or tokens is None:
        _, _, _, control, _, tokens, _, _, _ = _graph()
    raw_bytes = canonical_json(
        _raw_payload(control, tokens, assistant_text=assistant_text)
    ).encode("utf-8")
    return OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(raw_bytes).decode("ascii"),
    )


def _identity(
    control: OpenRouterControlPolicy,
    raw: OpenRouterRawResponseEvidence | None = None,
    *,
    fallback_used: bool = False,
) -> OpenRouterIdentityEvidence:
    if raw is None:
        _, _, _, _, _, tokens, _, _, _ = _graph()
        raw = _raw(control, tokens)
    digest = (control.control_policy_id or "").split("_", 1)[-1]
    return OpenRouterIdentityEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        requested_configuration_digest=digest,
        actual_router_id="openrouter",
        actual_model_id=OPENROUTER_MODEL_ID,
        actual_configuration_digest=digest,
        router_identity_match=True,
        model_identity_match=True,
        configuration_identity_match=True,
        identity_match=True,
        exact_router_model_configuration_verified=True,
        source_raw_response_sha256=raw.reported_sha256,
        source_fields=OPENROUTER_IDENTITY_SOURCE_FIELDS,
        fallback_used=fallback_used,
    )


def _usage(
    tokens: OpenRouterTokenPolicy,
    raw: OpenRouterRawResponseEvidence | None = None,
) -> OpenRouterUsageEvidence:
    if raw is None:
        _, _, _, control, _, _, _, _, _ = _graph()
        raw = _raw(control, tokens)
    return OpenRouterUsageEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        token_completeness=OpenRouterUsageCompleteness.COMPLETE,
        token_policy=tokens,
        usage_source=OpenRouterUsageSource.PROVIDER_REPORTED,
        source_raw_response_sha256=raw.reported_sha256,
        raw_source_fields=OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS,
        input_tokens=min(100, tokens.payload_input_token_upper_bound),
        output_tokens=8,
        total_tokens=min(100, tokens.payload_input_token_upper_bound) + 8,
    )


def _receipt() -> OpenRouterAttemptReceipt:
    _, _, _, control, body, tokens, _, _, capability = _graph()
    raw = _raw(control, tokens)
    identity = _identity(control, raw)
    usage = _usage(tokens, raw)
    envelope = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="synthetic-attempt-1",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=usage,
        timeout_fired=False,
        cancellation_requested=False,
    )
    return OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED,
        semantic_request_id="synthetic-semantic-request-1",
        capability_snapshot=capability,
        prepared_body=body,
        canned_response_envelope=envelope,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=usage,
        canned_transport_invocations=1,
        application_fallback_used=False,
        explicit_retry_count=0,
        adapter_retry_count=0,
        hidden_transport_retry_count=0,
        stream_used=False,
        tool_calls=0,
    )


def _failed_receipt(
    *,
    failure_code: str,
    body: OpenRouterPreparedBody,
    capability: OpenRouterCapabilitySnapshot,
    raw: OpenRouterRawResponseEvidence | None = None,
    identity: OpenRouterIdentityEvidence | None = None,
    usage: OpenRouterUsageEvidence | None = None,
) -> OpenRouterAttemptReceipt:
    return OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.FAILED_CLOSED,
        semantic_request_id="synthetic-semantic-request-1",
        capability_snapshot=capability,
        prepared_body=body,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=usage,
        canned_transport_invocations=1,
        application_fallback_used=False,
        explicit_retry_count=0,
        adapter_retry_count=0,
        hidden_transport_retry_count=0,
        stream_used=False,
        tool_calls=0,
        failure_code=failure_code,
    )
def test_exact_audited_constants_and_truthful_policy_states() -> None:
    endpoint, transport, route, control = _policies()
    assert OPENROUTER_ENDPOINT_URL == "https://openrouter.ai/api/v1/chat/completions"
    assert OPENROUTER_MODEL_ID == "openai/gpt-4.1-mini"
    assert OPENROUTER_MAX_OUTPUT_TOKENS == 256
    assert OPENROUTER_TIMEOUT_MS == 5_000
    assert endpoint.redirects_allowed is False and endpoint.max_redirects == 0
    assert endpoint.method == "POST"
    assert endpoint.content_type == "application/json"
    assert endpoint.tls_required is True
    assert endpoint.header_policy.content_type_value == "application/json"
    assert endpoint.header_policy.http_referer_state == "ABSENT"
    assert endpoint.header_policy.x_title_state == "ABSENT"
    assert endpoint.header_policy.authorization_delivery == "OUT_OF_BAND_ONLY"
    assert endpoint.header_policy.authorization_in_artifacts_allowed is False
    assert endpoint.environment_proxy_allowed is False
    assert endpoint.alternate_endpoints == endpoint.telemetry_endpoints == ()
    assert endpoint.live_enforcement_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert transport.mode.value == "CANNED_ONLY"
    assert transport.external_network_allowed is False
    assert transport.credential_access_allowed is False
    assert transport.canned_raw_response_max_bytes == 65_536
    assert transport.canned_raw_response_max_bytes == OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES
    assert transport.canned_cancellation_grace_ms == OPENROUTER_CANNED_CANCELLATION_GRACE_MS == 50
    assert transport.canned_cleanup_rounds == OPENROUTER_CANNED_CLEANUP_ROUNDS == 2
    assert transport.live_connect_timeout_ms is None
    assert transport.live_read_timeout_ms is None
    assert transport.live_cancellation_grace_ms is None
    assert route.upstream_provider_id is None and route.upstream_route_id is None
    assert route.upstream_route_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert route.provider_side_fallback_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert control.max_output_tokens == 256
    assert control.output_cap_wire_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert control.seed_state is OpenRouterEvidenceState.PROVEN_UNSUPPORTED
    assert control.seed is None
    assert control.sdk_internal_retry_state is OpenRouterEvidenceState.NOT_APPLICABLE
    assert control.sdk_internal_retry_limit is None
    assert control.fallback_allowed is control.stream is False
    assert control.tools == ()


@pytest.mark.parametrize(
    ("contract", "id_field"),
    (
        (OpenRouterEndpointPolicy(), "endpoint_policy_id"),
        (OpenRouterTransportPolicy(), "transport_policy_id"),
        (OpenRouterRoutePolicy(), "route_policy_id"),
        (OpenRouterControlPolicy(), "control_policy_id"),
    ),
)
def test_base_policy_ids_are_deterministic_frozen_and_extra_forbid(
    contract, id_field: str
) -> None:
    rebuilt = type(contract).model_validate(contract.model_dump(mode="json"))
    assert rebuilt == contract
    assert getattr(rebuilt, id_field) == getattr(contract, id_field)
    with pytest.raises(ValidationError):
        type(contract).model_validate({**contract.model_dump(mode="json"), "extra": 1})
    with pytest.raises(ValidationError):
        setattr(contract, id_field, "tampered")


def test_endpoint_route_and_control_cannot_claim_unproved_live_behavior() -> None:
    with pytest.raises(ValidationError):
        OpenRouterEndpointPolicy(redirects_allowed=True)
    with pytest.raises(ValidationError):
        OpenRouterEndpointPolicy(alternate_endpoints=("https://elsewhere.invalid",))
    with pytest.raises(ValidationError):
        OpenRouterRoutePolicy(upstream_provider_id="openai")
    with pytest.raises(ValidationError):
        OpenRouterRoutePolicy(provider_side_fallback_state="SYNTHETIC_ONLY")
    with pytest.raises(ValidationError):
        OpenRouterControlPolicy(max_output_tokens=257)
    with pytest.raises(ValidationError):
        OpenRouterControlPolicy(hidden_transport_retry_limit=1)
    with pytest.raises(ValidationError):
        OpenRouterControlPolicy(tools=("web",))


def test_prepared_body_freezes_exact_bytes_digest_length_and_id() -> None:
    endpoint, _, route, control = _policies()
    body = _prepared_body(endpoint, route, control)
    expected = canonical_json(_body_mapping()).encode("utf-8")
    assert body.body_bytes == expected
    assert body.byte_length == len(expected)
    assert body.sha256 == hashlib.sha256(expected).hexdigest()
    assert body.payload_input_token_upper_bound == len(expected)
    assert body.evidence_state is OpenRouterEvidenceState.SYNTHETIC_ONLY
    assert body.live_wire_acceptance_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    rebuilt = OpenRouterPreparedBody.model_validate(body.model_dump(mode="json"))
    assert rebuilt.prepared_body_id == body.prepared_body_id


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"seed": 1}, "frozen shape"),
        ({"provider": {"order": ["openai"]}}, "frozen shape"),
        ({"Authorization": "Bearer canary"}, "frozen shape"),
        ({"session_id": "process-canary"}, "frozen shape"),
        ({"max_tokens": 257}, "max_tokens"),
        ({"stream": True}, "stream"),
        ({"tools": [{"type": "web"}]}, "tools"),
    ),
)
def test_prepared_body_rejects_unproved_or_out_of_band_fields(
    mutation: dict[str, object], message: str
) -> None:
    endpoint, _, route, control = _policies()
    payload = _body_mapping()
    payload.update(mutation)
    with pytest.raises(ValidationError, match=message):
        OpenRouterPreparedBody(
            endpoint_policy_id=endpoint.endpoint_policy_id or "",
            route_policy_id=route.route_policy_id or "",
            control_policy_id=control.control_policy_id or "",
            canonical_body_json=canonical_json(payload),
        )


def test_prepared_body_rejects_noncanonical_and_forged_byte_evidence() -> None:
    endpoint, _, route, control = _policies()
    pretty = json.dumps(_body_mapping(), ensure_ascii=False, sort_keys=False)
    kwargs = {
        "endpoint_policy_id": endpoint.endpoint_policy_id or "",
        "route_policy_id": route.route_policy_id or "",
        "control_policy_id": control.control_policy_id or "",
    }
    with pytest.raises(ValidationError, match="canonical JSON"):
        OpenRouterPreparedBody(canonical_body_json=pretty, **kwargs)
    with pytest.raises(ValidationError, match="sha256"):
        OpenRouterPreparedBody(
            canonical_body_json=canonical_json(_body_mapping()),
            sha256="f" * 64,
            **kwargs,
        )


def test_token_policy_uses_full_utf8_bytes_but_does_not_invent_provider_bound() -> None:
    _, _, _, _, body, tokens, _, _, _ = _graph()
    assert tokens.payload_input_bound_method == OPENROUTER_INPUT_BOUND_METHOD
    assert tokens.payload_input_token_upper_bound == len(body.body_bytes)
    assert tokens.payload_only_total_token_upper_bound == len(body.body_bytes) + 256
    assert tokens.provider_framing_overhead_tokens is None
    assert tokens.provider_input_token_bound_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert tokens.authoritative_provider_input_token_upper_bound is None
    assert tokens.authoritative_total_token_upper_bound is None
    with pytest.raises(ValidationError, match="must equal prepared body byte length"):
        OpenRouterTokenPolicy(
            prepared_body_id=body.prepared_body_id or "",
            prepared_body_sha256=body.sha256 or "",
            prepared_body_byte_length=body.byte_length or 0,
            payload_input_token_upper_bound=(body.byte_length or 0) - 1,
        )


def test_not_established_pricing_and_cost_never_encode_unknown_as_zero() -> None:
    _, _, _, _, _, _, pricing, cost, capability = _graph()
    assert pricing.pricing_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert pricing.input_microusd_per_million_tokens is None
    assert pricing.output_microusd_per_million_tokens is None
    assert pricing.fixed_non_token_microusd is None
    assert cost.cost_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert cost.maximum_total_cost_microusd is None
    assert cost.unknown_line_items == pricing.unknown_line_items
    assert capability.live_authorization_allowed is False
    with pytest.raises(ValidationError, match="cannot contain prices"):
        OpenRouterPricingRecord(input_microusd_per_million_tokens=0)
    with pytest.raises(ValidationError, match="cannot contain numeric maximums"):
        OpenRouterCostBound(
            token_policy=cost.token_policy,
            pricing_record=pricing,
            maximum_total_cost_microusd=0,
        )


def test_synthetic_pricing_tests_integer_ceiling_without_claiming_live_price() -> None:
    _, _, _, _, _, tokens, pricing, cost, capability = _graph(synthetic_price=True)
    assert pricing.pricing_state is OpenRouterEvidenceState.SYNTHETIC_ONLY
    assert pricing.authority_reference == "synthetic-test-only"
    assert pricing.source_name == "synthetic-test-only"
    assert pricing.source_version == "synthetic-pricing/v0"
    assert pricing.effective_version == "synthetic-effective/v0"
    assert pricing.calculation_rule == OPENROUTER_COST_CALCULATION_RULE
    assert pricing.provenance_sha256 == hashlib.sha256(
        b"socrateszero-openrouter-synthetic-pricing/v0"
    ).hexdigest()
    assert cost.maximum_input_cost_microusd == tokens.payload_input_token_upper_bound
    assert cost.maximum_output_cost_microusd == 512
    assert cost.maximum_fixed_cost_microusd == 3
    assert cost.maximum_total_cost_microusd == (
        tokens.payload_input_token_upper_bound + 515
    )
    assert capability.live_authorization_allowed is False
    with pytest.raises(ValidationError, match="synthetic-test-only"):
        OpenRouterPricingRecord(
            pricing_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            input_microusd_per_million_tokens=1,
            output_microusd_per_million_tokens=1,
            fixed_non_token_microusd=0,
            authority_reference="provider-price-claim",
            source_name="synthetic-test-only",
            source_version="synthetic-pricing/v0",
            effective_version="synthetic-effective/v0",
            provenance_sha256=hashlib.sha256(
                b"socrateszero-openrouter-synthetic-pricing/v0"
            ).hexdigest(),
            unknown_line_items=(),
        )


def test_cost_arithmetic_rejects_signed_64_bit_multiplication_and_sum_overflow() -> None:
    _, _, _, _, body, _, _, _, _ = _graph()
    tokens_payload = OpenRouterTokenPolicy.from_prepared_body(body).model_dump(mode="json")
    tokens_payload["token_policy_id"] = None
    tokens_payload["prepared_body_byte_length"] = MAX_SIGNED_64
    tokens_payload["payload_input_token_upper_bound"] = MAX_SIGNED_64
    tokens_payload["payload_only_total_token_upper_bound"] = None
    with pytest.raises(ValidationError, match="total-token bound.*overflows"):
        OpenRouterTokenPolicy.model_validate(tokens_payload)

    _, _, _, _, _, tokens, _, _, _ = _graph()
    pricing = OpenRouterPricingRecord(
        pricing_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        input_microusd_per_million_tokens=MAX_SIGNED_64,
        output_microusd_per_million_tokens=1,
        fixed_non_token_microusd=0,
        authority_reference="synthetic-test-only",
        source_name="synthetic-test-only",
        source_version="synthetic-pricing/v0",
        effective_version="synthetic-effective/v0",
        provenance_sha256=hashlib.sha256(
            b"socrateszero-openrouter-synthetic-pricing/v0"
        ).hexdigest(),
        unknown_line_items=(),
    )
    with pytest.raises(ValidationError, match="token-price product overflows"):
        OpenRouterCostBound(
            token_policy=tokens,
            pricing_record=pricing,
            unknown_line_items=(),
        )


def test_capability_snapshot_cross_links_every_policy_and_stays_non_authorizing() -> None:
    endpoint, transport, route, control, body, tokens, pricing, cost, cap = _graph()
    assert cap.prepared_body_id == body.prepared_body_id
    assert cap.endpoint_policy == endpoint
    assert cap.transport_policy == transport
    assert cap.route_policy == route
    assert cap.control_policy == control
    assert cap.token_policy == tokens
    assert cap.pricing_record == pricing
    assert cap.cost_bound == cost
    assert cap.upstream_route_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert cap.provider_fallback_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert cap.provider_input_bound_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert cap.output_cap_wire_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert cap.network_calls == cap.credential_accesses == cap.provider_calls == 0
    payload = cap.model_dump(mode="json")
    payload["prepared_body_id"] = "szorbody_wrong"
    payload["capability_snapshot_id"] = None
    with pytest.raises(ValidationError, match="prepared body link"):
        OpenRouterCapabilitySnapshot.model_validate(payload)


def test_raw_response_requires_canonical_bounded_bytes_and_exact_evidence() -> None:
    _, _, _, control, _, tokens, _, _, _ = _graph()
    expected = canonical_json(_raw_payload(control, tokens)).encode("utf-8")
    raw = _raw(control, tokens)
    assert OPENROUTER_REFERENCE_RAW_RESPONSE_MAX_BYTES == 65_536
    assert raw.raw_bytes == expected
    assert raw.reported_byte_length == len(expected)
    assert raw.reported_sha256 == hashlib.sha256(expected).hexdigest()
    assert raw.evidence_state is OpenRouterEvidenceState.SYNTHETIC_ONLY
    with pytest.raises(ValidationError, match="byte bound"):
        OpenRouterRawResponseEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            transport_status=OpenRouterTransportStatus.DELIVERED,
            raw_response_base64=base64.b64encode(
                b"x" * (OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES + 1)
            ).decode("ascii"),
        )
    with pytest.raises(ValidationError, match="SHA-256"):
        OpenRouterRawResponseEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            transport_status=OpenRouterTransportStatus.DELIVERED,
            raw_response_base64=base64.b64encode(expected).decode("ascii"),
            reported_sha256="f" * 64,
        )


def test_failed_raw_response_has_typed_error_and_no_fabricated_bytes() -> None:
    failed = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.TIMEOUT,
        transport_error_code="CANNED_TIMEOUT",
    )
    assert failed.raw_bytes is None
    assert failed.reported_sha256 is None
    assert failed.reported_byte_length is None
    with pytest.raises(ValidationError, match="typed error code"):
        OpenRouterRawResponseEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            transport_status=OpenRouterTransportStatus.ERROR,
        )


def test_canned_response_envelope_freezes_complete_transport_metadata() -> None:
    _, _, _, control, body, tokens, _, _, _ = _graph()
    raw = _raw(control, tokens)
    identity = _identity(control, raw)
    usage = _usage(tokens, raw)
    envelope = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="synthetic-attempt-1",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=usage,
        timeout_fired=False,
        cancellation_requested=False,
    )
    assert envelope.actual_router_id == "openrouter"
    assert envelope.actual_model_id == OPENROUTER_MODEL_ID
    assert envelope.actual_configuration_digest == identity.actual_configuration_digest
    assert envelope.fallback_used is False
    assert envelope.explicit_retry_count == envelope.adapter_retry_count == 0
    assert envelope.sdk_internal_retry_state is OpenRouterEvidenceState.NOT_APPLICABLE
    assert envelope.sdk_internal_retry_count is None
    assert envelope.hidden_transport_retry_count == 0
    assert envelope.stream_used is False and envelope.tool_calls == 0
    assert envelope.worker_terminated is True
    rebuilt = OpenRouterCannedResponseEnvelope.model_validate(
        envelope.model_dump(mode="json")
    )
    assert rebuilt.canned_response_envelope_id == envelope.canned_response_envelope_id


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"model": "other/model"}, "raw response identity"),
        ({"provider": "other-router"}, "raw response identity"),
        ({"configuration_digest": "f" * 64}, "raw response identity"),
        ({"fallback_used": True}, "fallback_used"),
        ({"explicit_retry_count": 1}, "explicit_retry_count"),
        ({"stream_used": True}, "stream_used"),
        ({"tool_calls": 1}, "tool_calls"),
        ({"usage": {"input_tokens": 1, "output_tokens": 8, "total_tokens": 9}}, "raw response usage"),
    ),
)
def test_canned_envelope_rejects_raw_metadata_side_evidence_mismatch(
    mutation: dict[str, object], message: str
) -> None:
    _, _, _, control, body, tokens, _, _, _ = _graph()
    payload = _raw_payload(control, tokens)
    payload.update(mutation)
    raw = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(
            canonical_json(payload).encode("utf-8")
        ).decode("ascii"),
    )
    with pytest.raises(ValidationError, match=message):
        OpenRouterCannedResponseEnvelope(
            transport_attempt_id="mismatch-attempt",
            prepared_body_id=body.prepared_body_id or "",
            transport_status=OpenRouterTransportStatus.DELIVERED,
            raw_response=raw,
            identity_evidence=_identity(
                control,
                raw,
                fallback_used=(
                    payload["fallback_used"]
                    if type(payload["fallback_used"]) is bool
                    else False
                ),
            ),
            usage_evidence=_usage(tokens, raw),
            timeout_fired=False,
            cancellation_requested=False,
        )


def test_canned_timeout_envelope_requires_cancellation_and_termination() -> None:
    _, _, _, _, body, _, _, _, _ = _graph()
    timeout = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="synthetic-timeout-1",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.TIMEOUT,
        timeout_fired=True,
        cancellation_requested=True,
        transport_error_code="CANNED_TIMEOUT",
    )
    assert timeout.worker_terminated is True
    assert timeout.raw_response is timeout.identity_evidence is timeout.usage_evidence is None
    with pytest.raises(ValidationError, match="timeout and cancellation"):
        OpenRouterCannedResponseEnvelope(
            transport_attempt_id="synthetic-timeout-2",
            prepared_body_id=body.prepared_body_id or "",
            transport_status=OpenRouterTransportStatus.TIMEOUT,
            timeout_fired=True,
            cancellation_requested=False,
            transport_error_code="CANNED_TIMEOUT",
        )


def test_authorization_and_credential_material_are_excluded_from_contracts() -> None:
    endpoint, _, route, control = _policies()
    payload = _body_mapping()
    payload["messages"][1]["content"] = "Bearer sk-secret-canary"  # type: ignore[index]
    with pytest.raises(ValidationError, match="forbidden credential material"):
        OpenRouterPreparedBody(
            endpoint_policy_id=endpoint.endpoint_policy_id or "",
            route_policy_id=route.route_policy_id or "",
            control_policy_id=control.control_policy_id or "",
            canonical_body_json=canonical_json(payload),
        )
    _, _, _, control, body, tokens, _, _, _ = _graph()
    opaque = _raw(
        control,
        tokens,
        assistant_text="Discuss authorization, api_key, Bearer, and sk- as opaque prose.",
    )
    identity = _identity(control, opaque)
    usage = _usage(tokens, opaque)
    accepted = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="opaque-content-attempt",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=opaque,
        identity_evidence=identity,
        usage_evidence=usage,
        timeout_fired=False,
        cancellation_requested=False,
    )
    assert "authorization" in accepted.raw_response.raw_bytes.decode("utf-8").lower()

    structured = _raw_payload(control, tokens)
    structured["headers"] = {"Authorization": "Bearer sk-secret-canary"}
    structured_raw = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(
            canonical_json(structured).encode("utf-8")
        ).decode("ascii"),
    )
    structured_identity = _identity(control, structured_raw)
    structured_usage = _usage(tokens, structured_raw)
    with pytest.raises(ValidationError, match="frozen shape"):
        OpenRouterCannedResponseEnvelope(
            transport_attempt_id="structured-secret-attempt",
            prepared_body_id=body.prepared_body_id or "",
            transport_status=OpenRouterTransportStatus.DELIVERED,
            raw_response=structured_raw,
            identity_evidence=structured_identity,
            usage_evidence=structured_usage,
            timeout_fired=False,
            cancellation_requested=False,
        )
    receipt_payload = _receipt().model_dump(mode="json")
    receipt_payload["attempt_receipt_id"] = None
    receipt_payload["semantic_request_id"] = "sk-secret-semantic-link"
    with pytest.raises(ValidationError, match="forbidden credential material"):
        OpenRouterAttemptReceipt.model_validate(receipt_payload)


def test_identity_never_conflates_router_model_with_upstream_route() -> None:
    control = OpenRouterControlPolicy()
    identity = _identity(control)
    assert identity.exact_router_model_configuration_verified is True
    assert identity.actual_router_id == "openrouter"
    assert identity.actual_model_id == OPENROUTER_MODEL_ID
    assert identity.canonicalization_rule_id == "EXACT_CODEPOINT_EQUALITY_V0"
    assert identity.router_identity_match is True
    assert identity.model_identity_match is True
    assert identity.configuration_identity_match is True
    assert identity.identity_match is True
    assert identity.upstream_provider_id is identity.upstream_route_id is None
    assert identity.upstream_route_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    with pytest.raises(ValidationError, match="exactly match"):
        OpenRouterIdentityEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            requested_configuration_digest=(control.control_policy_id or "").split("_", 1)[-1],
            actual_router_id="openrouter",
            actual_model_id="other/model",
            actual_configuration_digest=(control.control_policy_id or "").split("_", 1)[-1],
            router_identity_match=True,
            model_identity_match=False,
            configuration_identity_match=True,
            identity_match=False,
            exact_router_model_configuration_verified=True,
        )


def test_usage_is_complete_and_bounded_but_cost_remains_unknown() -> None:
    _, _, _, _, _, tokens, _, _, _ = _graph()
    usage = _usage(tokens)
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens
    assert usage.cost_state is OpenRouterEvidenceState.NOT_ESTABLISHED
    assert usage.cost_microusd is None and usage.cost_bound_id is None
    with pytest.raises(ValidationError, match="total tokens"):
        OpenRouterUsageEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            token_completeness=OpenRouterUsageCompleteness.COMPLETE,
            token_policy=tokens,
            input_tokens=1,
            output_tokens=1,
            total_tokens=3,
        )
    usage_payload = usage.model_dump(mode="json")
    usage_payload["usage_evidence_id"] = None
    usage_payload["cost_microusd"] = 0
    with pytest.raises(ValidationError, match="unknown cost"):
        OpenRouterUsageEvidence.model_validate(usage_payload)


def test_attempt_receipt_is_one_shot_immutable_linked_and_non_authorizing() -> None:
    receipt = _receipt()
    assert receipt.outcome is OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED
    assert receipt.attempt_ordinal == 1
    assert receipt.canned_transport_invocations == 1
    assert receipt.application_fallback_used is False
    assert receipt.provider_fallback_used is None
    assert receipt.semantic_request_id == "synthetic-semantic-request-1"
    assert receipt.canned_response_envelope is not None
    assert (
        receipt.explicit_retry_count,
        receipt.adapter_retry_count,
        receipt.hidden_transport_retry_count,
    ) == (0, 0, 0)
    assert receipt.sdk_internal_retry_state is OpenRouterEvidenceState.NOT_APPLICABLE
    assert receipt.sdk_internal_retry_count is None
    assert receipt.external_network_calls == receipt.credential_accesses == 0
    assert receipt.live_provider_calls == receipt.model_executions == 0
    assert receipt.ced_applications == 0
    assert receipt.live_authorization_allowed is False
    rebuilt = OpenRouterAttemptReceipt.model_validate(receipt.model_dump(mode="json"))
    assert rebuilt.attempt_receipt_id == receipt.attempt_receipt_id
    with pytest.raises(ValidationError):
        receipt.canned_transport_invocations = 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("canned_transport_invocations", 0, "exactly one"),
        ("application_fallback_used", True, "fallback false"),
        ("explicit_retry_count", 1, "retry counts zero"),
        ("stream_used", True, "no stream or tools"),
        ("tool_calls", 1, "no stream or tools"),
    ),
)
def test_attempt_receipt_rejects_replay_fallback_retry_stream_and_tool_claims(
    field: str, value: object, message: str
) -> None:
    payload = _receipt().model_dump(mode="json")
    payload["attempt_receipt_id"] = None
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        OpenRouterAttemptReceipt.model_validate(payload)


def test_failed_attempt_requires_typed_failure_and_never_invents_live_activity() -> None:
    *_, body, _, _, _, capability = _graph()
    receipt = OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.FAILED_CLOSED,
        semantic_request_id="synthetic-semantic-request-1",
        capability_snapshot=capability,
        prepared_body=body,
        canned_transport_invocations=0,
        failure_code="CAPABILITY_NOT_ESTABLISHED",
    )
    assert receipt.failure_code == "CAPABILITY_NOT_ESTABLISHED"
    assert receipt.external_network_calls == receipt.live_provider_calls == 0
    with pytest.raises(ValidationError, match="typed failure code"):
        OpenRouterAttemptReceipt(
            outcome=OpenRouterAttemptOutcome.FAILED_CLOSED,
            semantic_request_id="synthetic-semantic-request-1",
            capability_snapshot=capability,
            prepared_body=body,
            canned_transport_invocations=0,
        )


def test_malformed_failure_preserves_raw_bytes_but_cannot_fabricate_derivations() -> None:
    _, _, _, control, body, tokens, _, _, capability = _graph()
    malformed_bytes = b"not-json-but-retained"
    malformed = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(malformed_bytes).decode("ascii"),
    )
    receipt = _failed_receipt(
        failure_code="MALFORMED_RESPONSE_ENVELOPE",
        body=body,
        capability=capability,
        raw=malformed,
    )
    assert receipt.raw_response is not None
    assert receipt.raw_response.raw_bytes == malformed_bytes
    assert receipt.raw_response.retention_state is (
        OpenRouterRawRetentionState.INLINE_RAW_BYTES_RETAINED
    )
    assert receipt.identity_evidence is receipt.usage_evidence is None
    assert receipt.response_validation_state is (
        OpenRouterResponseValidationState.TRANSPORT_BYTES_CAPTURED
    )

    fabricated_identity = _identity(control, malformed)
    fabricated_usage = _usage(tokens, malformed)
    with pytest.raises(ValidationError, match="canonical captured raw bytes"):
        _failed_receipt(
            failure_code="MALFORMED_RESPONSE_ENVELOPE",
            body=body,
            capability=capability,
            raw=malformed,
            identity=fabricated_identity,
        )
    with pytest.raises(ValidationError, match="canonical captured raw bytes"):
        _failed_receipt(
            failure_code="MALFORMED_RESPONSE_ENVELOPE",
            body=body,
            capability=capability,
            raw=malformed,
            identity=fabricated_identity,
            usage=fabricated_usage,
        )

    valid_raw = _raw(control, tokens)
    with pytest.raises(ValidationError, match="beyond its derivation stage"):
        _failed_receipt(
            failure_code="MALFORMED_RESPONSE_ENVELOPE",
            body=body,
            capability=capability,
            raw=valid_raw,
            identity=_identity(control, valid_raw),
        )


def test_failed_receipt_accepts_only_raw_linked_evidence_at_completed_stage() -> None:
    _, _, _, control, body, tokens, _, _, capability = _graph()
    payload = _raw_payload(control, tokens)
    payload["fallback_used"] = True
    raw = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(
            canonical_json(payload).encode("utf-8")
        ).decode("ascii"),
    )
    identity = _identity(control, raw, fallback_used=True)
    usage = _usage(tokens, raw)
    receipt = _failed_receipt(
        failure_code="FALLBACK_ACTIVATED",
        body=body,
        capability=capability,
        raw=raw,
        identity=identity,
    )
    assert receipt.finish_reason is OpenRouterFinishReason.STOP
    assert receipt.response_validation_state is (
        OpenRouterResponseValidationState.IDENTITY_DERIVED
    )
    assert receipt.identity_evidence.fallback_used is True

    with pytest.raises(ValidationError, match="beyond its derivation stage"):
        _failed_receipt(
            failure_code="FALLBACK_ACTIVATED",
            body=body,
            capability=capability,
            raw=raw,
            identity=identity,
            usage=usage,
        )

    forged_identity_payload = identity.model_dump(mode="json")
    forged_identity_payload["identity_evidence_id"] = None
    forged_identity_payload["source_raw_response_sha256"] = "f" * 64
    forged_identity = OpenRouterIdentityEvidence.model_validate(
        forged_identity_payload
    )
    with pytest.raises(ValidationError, match="not derived from captured raw bytes"):
        _failed_receipt(
            failure_code="FALLBACK_ACTIVATED",
            body=body,
            capability=capability,
            raw=raw,
            identity=forged_identity,
        )

    valid_raw = _raw(control, tokens)
    valid_identity = _identity(control, valid_raw)
    valid_usage = _usage(tokens, valid_raw)
    fully_derived = _failed_receipt(
        failure_code="RECEIPT_MISMATCH",
        body=body,
        capability=capability,
        raw=valid_raw,
        identity=valid_identity,
        usage=valid_usage,
    )
    assert fully_derived.response_validation_state is (
        OpenRouterResponseValidationState.USAGE_DERIVED
    )
    forged_usage_payload = valid_usage.model_dump(mode="json")
    forged_usage_payload["usage_evidence_id"] = None
    forged_usage_payload["source_raw_response_sha256"] = "f" * 64
    forged_usage = OpenRouterUsageEvidence.model_validate(forged_usage_payload)
    with pytest.raises(ValidationError, match="not derived from captured raw bytes"):
        _failed_receipt(
            failure_code="RECEIPT_MISMATCH",
            body=body,
            capability=capability,
            raw=valid_raw,
            identity=valid_identity,
            usage=forged_usage,
        )


def test_finish_privacy_and_retention_facts_are_typed_immutable_and_linked() -> None:
    receipt = _receipt()
    raw = receipt.raw_response
    assert raw is not None
    assert raw.privacy_classification is (
        OpenRouterPrivacyClassification.SYNTHETIC_CANNED_OBSERVATION
    )
    assert raw.retention_state is OpenRouterRawRetentionState.INLINE_RAW_BYTES_RETAINED
    assert raw.credential_material_retained is False
    assert raw.sensitive_headers_retained is False
    assert raw.assistant_content_treatment == "OPAQUE_NO_SEMANTIC_EVALUATION"
    assert receipt.finish_reason is OpenRouterFinishReason.STOP
    assert receipt.canned_response_envelope.finish_reason is OpenRouterFinishReason.STOP
    assert receipt.response_validation_state is (
        OpenRouterResponseValidationState.ADAPTER_RESPONSE_VALIDATED
    )
    assert receipt.identity_evidence.source_raw_response_sha256 == raw.reported_sha256
    assert receipt.usage_evidence.source_raw_response_sha256 == raw.reported_sha256
    assert receipt.identity_evidence.source_fields == OPENROUTER_IDENTITY_SOURCE_FIELDS
    assert receipt.usage_evidence.raw_source_fields == (
        OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS
    )
    with pytest.raises(ValidationError):
        raw.retention_state = OpenRouterRawRetentionState.NO_RAW_BYTES_CAPTURED

    payload = receipt.model_dump(mode="json")
    payload["attempt_receipt_id"] = None
    payload["finish_reason"] = "length"
    with pytest.raises(ValidationError):
        OpenRouterAttemptReceipt.model_validate(payload)


def test_usage_source_is_explicit_provider_reported_or_frozen_local_derivation() -> None:
    _, _, _, control, _, tokens, _, _, _ = _graph()
    raw = _raw(control, tokens)
    provider_usage = _usage(tokens, raw)
    assert provider_usage.usage_source is OpenRouterUsageSource.PROVIDER_REPORTED
    assert provider_usage.locally_derived_fields == ()
    assert provider_usage.derivation_rule_id is None

    locally_derived = OpenRouterUsageEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        token_completeness=OpenRouterUsageCompleteness.COMPLETE,
        token_policy=tokens,
        usage_source=OpenRouterUsageSource.LOCALLY_DERIVED,
        source_raw_response_sha256=raw.reported_sha256,
        raw_source_fields=OPENROUTER_LOCALLY_DERIVED_USAGE_SOURCE_FIELDS,
        locally_derived_fields=OPENROUTER_LOCALLY_DERIVED_USAGE_FIELDS,
        derivation_rule_id="TOTAL_EQUALS_INPUT_PLUS_OUTPUT_V0",
        input_tokens=4,
        output_tokens=3,
        total_tokens=7,
    )
    assert locally_derived.usage_source is OpenRouterUsageSource.LOCALLY_DERIVED
    invalid = locally_derived.model_dump(mode="json")
    invalid["usage_evidence_id"] = None
    invalid["derivation_rule_id"] = "MUTABLE_LATEST"
    with pytest.raises(ValidationError, match="frozen derivation rule"):
        OpenRouterUsageEvidence.model_validate(invalid)

    unknown = OpenRouterUsageEvidence(
        evidence_state=OpenRouterEvidenceState.NOT_ESTABLISHED,
        token_completeness=OpenRouterUsageCompleteness.UNKNOWN,
        token_policy=tokens,
    )
    assert unknown.usage_source is OpenRouterUsageSource.UNKNOWN
    unknown_payload = unknown.model_dump(mode="json")
    unknown_payload["usage_evidence_id"] = None
    unknown_payload["input_tokens"] = 0
    with pytest.raises(ValidationError, match="unknown usage cannot contain token counts"):
        OpenRouterUsageEvidence.model_validate(unknown_payload)


@pytest.mark.parametrize(
    "forbidden_state",
    (
        OpenRouterEvidenceState.PROVEN_UNSUPPORTED,
        OpenRouterEvidenceState.NOT_APPLICABLE,
    ),
)
def test_pricing_and_cost_reject_non_arithmetic_evidence_state_loopholes(
    forbidden_state: OpenRouterEvidenceState,
) -> None:
    _, _, _, _, _, _, pricing, cost, _ = _graph(synthetic_price=True)
    pricing_payload = pricing.model_dump(mode="json")
    pricing_payload["pricing_record_id"] = None
    pricing_payload["pricing_state"] = forbidden_state.value
    with pytest.raises(ValidationError):
        OpenRouterPricingRecord.model_validate(pricing_payload)

    cost_payload = cost.model_dump(mode="json")
    cost_payload["cost_bound_id"] = None
    cost_payload["cost_state"] = forbidden_state.value
    with pytest.raises(ValidationError):
        OpenRouterCostBound.model_validate(cost_payload)


def test_cost_arithmetic_zero_rounding_bounds_and_record_integrity_matrix() -> None:
    assert calculate_openrouter_cost_line_microusd(0, MAX_SIGNED_64) == 0
    assert calculate_openrouter_cost_line_microusd(MAX_SIGNED_64, 0) == 0
    assert calculate_openrouter_cost_line_microusd(1, 1) == 1
    assert calculate_openrouter_cost_line_microusd(1_000_000, 7) == 7
    assert calculate_openrouter_cost_line_microusd(1_000_001, 1) == 2
    assert calculate_openrouter_cost_line_microusd(
        MAX_SIGNED_64, 1
    ) == (MAX_SIGNED_64 + 999_999) // 1_000_000
    with pytest.raises(ContractValidationError, match="signed 64-bit domain"):
        calculate_openrouter_cost_line_microusd(1, -1)
    with pytest.raises(ContractValidationError, match="exact integers"):
        calculate_openrouter_cost_line_microusd(True, 1)

    _, _, _, _, _, tokens, pricing, _, _ = _graph(synthetic_price=True)
    for field_name, wrong_value in (
        ("currency", "EUR"),
        ("model_id", "other/model"),
        ("source_version", "latest"),
        ("effective_version", "latest"),
    ):
        payload = pricing.model_dump(mode="json")
        payload["pricing_record_id"] = None
        payload[field_name] = wrong_value
        with pytest.raises(ValidationError):
            OpenRouterPricingRecord.model_validate(payload)

    forged = pricing.model_dump(mode="json")
    forged["pricing_record_id"] = "szorprice_" + "0" * 64
    with pytest.raises(ValidationError, match="does not match contract content"):
        OpenRouterPricingRecord.model_validate(forged)
    with pytest.raises(ValidationError):
        pricing.effective_version = "latest"
    with pytest.raises(ValidationError):
        OpenRouterPricingRecord(
            pricing_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            input_microusd_per_million_tokens=-1,
            output_microusd_per_million_tokens=0,
            fixed_non_token_microusd=0,
            authority_reference="synthetic-test-only",
            source_name="synthetic-test-only",
            source_version="synthetic-pricing/v0",
            effective_version="synthetic-effective/v0",
            provenance_sha256=hashlib.sha256(
                b"socrateszero-openrouter-synthetic-pricing/v0"
            ).hexdigest(),
            unknown_line_items=(),
        )

    unknown_pricing = OpenRouterPricingRecord()
    with pytest.raises(ValidationError, match="cost state must equal pricing state"):
        OpenRouterCostBound(
            token_policy=tokens,
            pricing_record=unknown_pricing,
            cost_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            unknown_line_items=(),
        )

    overflowing_total_pricing = OpenRouterPricingRecord(
        pricing_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        input_microusd_per_million_tokens=1,
        output_microusd_per_million_tokens=0,
        fixed_non_token_microusd=MAX_SIGNED_64,
        authority_reference="synthetic-test-only",
        source_name="synthetic-test-only",
        source_version="synthetic-pricing/v0",
        effective_version="synthetic-effective/v0",
        provenance_sha256=hashlib.sha256(
            b"socrateszero-openrouter-synthetic-pricing/v0"
        ).hexdigest(),
        unknown_line_items=(),
    )
    with pytest.raises(ValidationError, match="maximum total cost overflows"):
        OpenRouterCostBound(
            token_policy=tokens,
            pricing_record=overflowing_total_pricing,
            unknown_line_items=(),
        )


def test_usage_cost_value_is_exactly_linked_to_frozen_synthetic_bound() -> None:
    _, _, _, control, body, tokens, pricing, cost, capability = _graph(
        synthetic_price=True
    )
    raw = _raw(control, tokens)
    identity = _identity(control, raw)
    input_tokens = min(100, tokens.payload_input_token_upper_bound)
    output_tokens = 8
    exact_cost = (
        calculate_openrouter_cost_line_microusd(
            input_tokens, pricing.input_microusd_per_million_tokens
        )
        + calculate_openrouter_cost_line_microusd(
            output_tokens, pricing.output_microusd_per_million_tokens
        )
        + pricing.fixed_non_token_microusd
    )
    usage = OpenRouterUsageEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        token_completeness=OpenRouterUsageCompleteness.COMPLETE,
        token_policy=tokens,
        usage_source=OpenRouterUsageSource.PROVIDER_REPORTED,
        source_raw_response_sha256=raw.reported_sha256,
        raw_source_fields=OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        cost_bound_id=cost.cost_bound_id,
        cost_microusd=exact_cost,
    )
    envelope = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="synthetic-cost-attempt",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=usage,
        timeout_fired=False,
        cancellation_requested=False,
    )
    receipt = OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED,
        semantic_request_id="synthetic-semantic-request-1",
        capability_snapshot=capability,
        prepared_body=body,
        canned_response_envelope=envelope,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=usage,
        canned_transport_invocations=1,
        application_fallback_used=False,
        explicit_retry_count=0,
        adapter_retry_count=0,
        hidden_transport_retry_count=0,
        stream_used=False,
        tool_calls=0,
    )
    assert receipt.usage_evidence.cost_microusd == exact_cost

    wrong_usage_payload = usage.model_dump(mode="json")
    wrong_usage_payload["usage_evidence_id"] = None
    wrong_usage_payload["cost_microusd"] = exact_cost + 1
    wrong_usage = OpenRouterUsageEvidence.model_validate(wrong_usage_payload)
    wrong_envelope = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="synthetic-cost-attempt",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=raw,
        identity_evidence=identity,
        usage_evidence=wrong_usage,
        timeout_fired=False,
        cancellation_requested=False,
    )
    with pytest.raises(ValidationError, match="does not link to capability cost bound"):
        OpenRouterAttemptReceipt(
            outcome=OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED,
            semantic_request_id="synthetic-semantic-request-1",
            capability_snapshot=capability,
            prepared_body=body,
            canned_response_envelope=wrong_envelope,
            raw_response=raw,
            identity_evidence=identity,
            usage_evidence=wrong_usage,
            canned_transport_invocations=1,
            application_fallback_used=False,
            explicit_retry_count=0,
            adapter_retry_count=0,
            hidden_transport_retry_count=0,
            stream_used=False,
            tool_calls=0,
        )

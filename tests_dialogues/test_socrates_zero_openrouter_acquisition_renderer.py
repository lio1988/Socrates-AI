from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.acquisition_contracts import (
    AcquisitionProviderModelBinding,
    AcquisitionRequestConfiguration,
    AcquisitionSeedSetting,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    AcquisitionTransportAttempt,
    ProviderVisibleRequestBytes,
)
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_acquisition_contracts import (
    OPENROUTER_MAX_OUTPUT_TOKENS,
    OPENROUTER_MODEL_ID,
    OPENROUTER_PROVIDER_ID,
    OpenRouterControlPolicy,
    OpenRouterEndpointPolicy,
    OpenRouterRoutePolicy,
)
from backend.dialogues.socrates_zero.openrouter_acquisition_renderer import (
    OPENROUTER_ACQUISITION_RENDERER_VERSION,
    render_openrouter_application_body,
)


_ACTION_ID = "szaction_renderer_fixture"


def _logical_body(
    *,
    system_content: str = "Ask one concise opening Socratic question.",
    user_content: str = "What is knowledge?",
    max_output_tokens: int = OPENROUTER_MAX_OUTPUT_TOKENS,
) -> dict[str, object]:
    return {
        "max_output_tokens": max_output_tokens,
        "messages": [
            {"content": system_content, "role": "system"},
            {"content": user_content, "role": "user"},
        ],
        "metadata": {},
        "response_format": {"type": "text"},
        "temperature": 0.0,
        "tools": [],
    }


def _semantic_request(
    body: dict[str, object] | None = None,
) -> AcquisitionSemanticRequest:
    logical = _logical_body() if body is None else body
    visible = ProviderVisibleRequestBytes(
        rendering_version="socrateszero-canonical-json-utf8/v0",
        canonical_request_json=canonical_json(logical),
    )
    seed = AcquisitionSeedSetting(status=AcquisitionSeedStatus.UNSUPPORTED)
    configuration = AcquisitionRequestConfiguration(
        temperature=0.0,
        seed=seed,
        max_output_tokens=int(logical.get("max_output_tokens", 256)),
        timeout_ms=5_000,
        provider_visible_metadata_digest=visible.sha256 or "",
    )
    binding = AcquisitionProviderModelBinding(
        provider_id=OPENROUTER_PROVIDER_ID,
        model_id=OPENROUTER_MODEL_ID,
        configuration_digest=configuration.configuration_digest or "",
    )
    return AcquisitionSemanticRequest(
        source_capsule_id="renderer-source-capsule",
        source_execution_id="renderer-source-execution",
        root_state_v1_id="renderer-root-state",
        pending_transition_id="renderer-pending-transition",
        canonical_task_identity_id="renderer-task-identity",
        action_id=_ACTION_ID,
        complete_legal_action_ids=(_ACTION_ID,),
        requested_binding=binding,
        capability_snapshot_id="renderer-acquisition-capability",
        control_policy_id="renderer-acquisition-control-policy",
        request_configuration=configuration,
        provider_visible_request=visible,
    )


def _render(request: AcquisitionSemanticRequest):
    return render_openrouter_application_body(
        request,
        OpenRouterControlPolicy(),
        endpoint_policy=OpenRouterEndpointPolicy(),
        route_policy=OpenRouterRoutePolicy(),
    )


def test_renderer_emits_exact_canonical_semantic_only_body() -> None:
    request = _semantic_request()
    prepared = _render(request)
    expected_payload = {
        "max_tokens": 256,
        "messages": [
            {
                "content": "Ask one concise opening Socratic question.",
                "role": "system",
            },
            {"content": "What is knowledge?", "role": "user"},
        ],
        "model": "openai/gpt-4.1-mini",
        "response_format": {"type": "text"},
        "stream": False,
        "temperature": 0.0,
        "tools": [],
    }
    expected_bytes = canonical_json(expected_payload).encode("utf-8")

    assert prepared.renderer_version == OPENROUTER_ACQUISITION_RENDERER_VERSION
    assert prepared.canonical_body_json == canonical_json(expected_payload)
    assert prepared.body_bytes == expected_bytes
    assert prepared.byte_length == len(expected_bytes)
    assert prepared.payload_input_token_upper_bound == len(expected_bytes)
    assert prepared.sha256 == hashlib.sha256(expected_bytes).hexdigest()

    parsed = json.loads(prepared.body_bytes)
    assert set(parsed) == {
        "max_tokens",
        "messages",
        "model",
        "response_format",
        "stream",
        "temperature",
        "tools",
    }
    assert "seed" not in parsed
    assert "provider" not in parsed
    assert "route" not in parsed
    assert "Authorization" not in prepared.canonical_body_json
    assert request.source_execution_id not in prepared.canonical_body_json


def test_renderer_is_sibling_invariant_and_attempt_metadata_is_out_of_band() -> None:
    request = _semantic_request()
    sibling_a = AcquisitionTransportAttempt(
        semantic_request_id=request.semantic_request_id or "",
        experiment_id="renderer-experiment",
        branch_id="renderer-sibling-a",
        attempt_ordinal=0,
    )
    sibling_b = AcquisitionTransportAttempt(
        semantic_request_id=request.semantic_request_id or "",
        experiment_id="renderer-experiment",
        branch_id="renderer-sibling-b",
        attempt_ordinal=0,
    )
    assert sibling_a.transport_attempt_id != sibling_b.transport_attempt_id

    first = _render(request)
    second = _render(request)
    assert first.body_bytes == second.body_bytes
    assert first.sha256 == second.sha256
    assert first.prepared_body_id == second.prepared_body_id
    assert sibling_a.branch_id.encode() not in first.body_bytes
    assert sibling_b.branch_id.encode() not in first.body_bytes


def test_renderer_recursively_nfc_normalizes_semantically_equal_content() -> None:
    decomposed = _semantic_request(
        _logical_body(user_content="Cafe\u0301 and inquiry")
    )
    composed = _semantic_request(_logical_body(user_content="Caf\u00e9 and inquiry"))
    assert decomposed.semantic_request_id != composed.semantic_request_id

    first = _render(decomposed)
    second = _render(composed)
    assert first.body_bytes == second.body_bytes
    assert first.sha256 == second.sha256
    assert "Caf\u00e9" in first.canonical_body_json
    assert "Cafe\u0301" not in first.canonical_body_json


@pytest.mark.parametrize(
    "forbidden_key",
    ("Authorization", "apiKey", "branchId", "headers", "provider", "route", "seed"),
)
def test_renderer_rejects_forbidden_entropy_secret_header_and_route_keys(
    forbidden_key: str,
) -> None:
    body = _logical_body()
    body[forbidden_key] = "must-not-enter-wire-bytes"
    with pytest.raises(ContractValidationError, match="forbidden provider-visible key"):
        _render(_semantic_request(body))


def test_renderer_rejects_nested_forbidden_keys_and_nfc_key_collisions() -> None:
    nested = _logical_body()
    nested["response_format"] = {
        "type": "text",
        "transport": {"request_headers": {"X-Title": "forbidden"}},
    }
    with pytest.raises(ContractValidationError, match="forbidden provider-visible key"):
        _render(_semantic_request(nested))

    collision = _logical_body()
    collision["Cafe\u0301"] = 1
    collision["Caf\u00e9"] = 2
    with pytest.raises(ContractValidationError, match="NFC normalization caused a duplicate"):
        _render(_semantic_request(collision))


def test_renderer_revalidates_source_digest_length_and_configuration_link() -> None:
    digest_tamper = _semantic_request()
    object.__setattr__(
        digest_tamper.provider_visible_request,
        "sha256",
        "0" * 64,
    )
    with pytest.raises(ContractValidationError, match="byte evidence does not match"):
        _render(digest_tamper)

    link_tamper = _semantic_request()
    object.__setattr__(
        link_tamper.request_configuration,
        "provider_visible_metadata_digest",
        "f" * 64,
    )
    with pytest.raises(ContractValidationError, match="does not link visible bytes"):
        _render(link_tamper)


def test_renderer_fails_closed_on_output_cap_drift() -> None:
    request = _semantic_request(_logical_body(max_output_tokens=255))
    with pytest.raises(ContractValidationError, match="output-token cap changed"):
        _render(request)


def test_prepared_body_is_immutable() -> None:
    prepared = _render(_semantic_request())
    with pytest.raises(ValidationError, match="frozen"):
        prepared.canonical_body_json = "{}"  # type: ignore[misc]


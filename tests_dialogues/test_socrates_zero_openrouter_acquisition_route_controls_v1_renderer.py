from __future__ import annotations

import hashlib
import json

import pytest

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_contracts import (
    FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1,
    FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
    OPENROUTER_ROUTE_RENDERER_VERSION,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_renderer import (
    prepare_openrouter_route_request_v1,
)


def _body() -> dict[str, object]:
    return json.loads(FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1)


def _headers() -> dict[str, str]:
    return json.loads(FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1)


def test_renderer_emits_exact_body_and_semantic_header_application_bytes() -> None:
    prepared = prepare_openrouter_route_request_v1()
    body = json.loads(prepared.body_bytes)
    headers = json.loads(prepared.header_bytes)

    assert prepared.renderer_version == OPENROUTER_ROUTE_RENDERER_VERSION
    assert prepared.canonical_body_json == FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1
    assert prepared.canonical_semantic_headers_json == (
        FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1
    )
    assert body == {
        "max_tokens": 256,
        "messages": [
            {
                "content": (
                    "Ask one concise opening Socratic question without answering "
                    "the user's question."
                ),
                "role": "system",
            },
            {
                "content": "Is knowledge merely justified true belief?",
                "role": "user",
            },
        ],
        "model": "openai/gpt-4.1-mini",
        "provider": {
            "allow_fallbacks": False,
            "only": ["azure/swedencentral"],
            "order": ["azure/swedencentral"],
            "require_parameters": True,
        },
        "response_format": {"type": "text"},
        "stream": False,
        "temperature": 0.0,
        "tools": [],
    }
    assert "models" not in body
    assert "max_price" not in body["provider"]
    assert "tool_choice" not in body
    assert headers == {
        "Content-Type": "application/json",
        "X-OpenRouter-Cache": "false",
        "X-OpenRouter-Metadata": "enabled",
    }
    assert prepared.body_sha256 == (
        "35a119b1e35f9f8ce05baf57009d787358bf086aaae4055ef56fcfedade514a1"
    )
    assert prepared.body_length == 447
    assert prepared.header_sha256 == (
        "1c688da6c6494631d6922fcb89a56b126e0900327dd865c2483d84f3c9f58149"
    )
    assert prepared.header_length == 98


def test_renderer_is_deterministic_and_sibling_process_metadata_stays_out_of_band() -> None:
    first = prepare_openrouter_route_request_v1()
    second = prepare_openrouter_route_request_v1()
    assert first == second
    assert first.body_bytes == second.body_bytes
    assert first.header_bytes == second.header_bytes
    assert first.route_intent_id == second.route_intent_id
    assert first.request_intent_receipt == second.request_intent_receipt
    serialized = first.body_bytes + first.header_bytes
    for forbidden in (
        b"branch_id",
        b"transport_id",
        b"experiment_id",
        b"receipt_id",
        b"timestamp",
        b"nonce",
        b"process_id",
        b"artifact_path",
        b"Authorization",
        b"credential",
    ):
        assert forbidden not in serialized


def _mutate_body(path: str, value: object) -> dict[str, object]:
    body = _body()
    if path == "model_missing":
        body.pop("model")
    elif path == "models":
        body["models"] = value
    elif path == "provider_missing":
        body.pop("provider")
    elif path.startswith("provider."):
        provider = body["provider"]
        assert isinstance(provider, dict)
        name = path.split(".", 1)[1]
        if value is _MISSING:
            provider.pop(name)
        else:
            provider[name] = value
    else:
        body[path] = value
    return body


_MISSING = object()


@pytest.mark.parametrize(
    ("path", "value"),
    (
        ("model_missing", _MISSING),
        ("model", "openai/gpt-4.1"),
        ("models", ["openai/gpt-4.1-mini"]),
        ("provider_missing", _MISSING),
        ("provider.only", []),
        ("provider.only", ["azure/swedencentral", "openai"]),
        ("provider.only", ["openai"]),
        ("provider.order", ["openai"]),
        ("provider.order", ["azure/swedencentral", "openai"]),
        ("provider.allow_fallbacks", True),
        ("provider.allow_fallbacks", _MISSING),
        ("provider.require_parameters", False),
        ("provider.require_parameters", _MISSING),
        ("provider.max_price", {"prompt": 0.1}),
        ("stream", True),
        ("tools", [{"type": "function"}]),
        ("tool_choice", "none"),
        ("max_tokens", 256.0),
        ("stream", 0),
    ),
)
def test_renderer_fails_closed_on_route_body_mutations(path: str, value: object) -> None:
    with pytest.raises(ContractValidationError, match="frozen v1 request intent"):
        prepare_openrouter_route_request_v1(_mutate_body(path, value))


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("X-OpenRouter-Metadata", None),
        ("X-OpenRouter-Metadata", "true"),
        ("X-OpenRouter-Cache", None),
        ("X-OpenRouter-Cache", "true"),
        ("Content-Type", "text/plain"),
    ),
)
def test_renderer_fails_closed_on_header_mutations(
    name: str, value: str | None
) -> None:
    headers = _headers()
    if value is None:
        headers.pop(name)
    else:
        headers[name] = value
    with pytest.raises(ContractValidationError, match="header intent"):
        prepare_openrouter_route_request_v1(semantic_headers=headers)


@pytest.mark.parametrize(
    "forbidden_key",
    (
        "Authorization",
        "apiKey",
        "branchId",
        "transport_request_id",
        "experimentId",
        "timestamp",
        "artifactPath",
        "machineName",
    ),
)
def test_recursive_entropy_firewall_rejects_process_and_secret_keys(
    forbidden_key: str,
) -> None:
    body = _body()
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    response_format[forbidden_key] = "must-not-enter-provider-visible-bytes"
    with pytest.raises(ContractValidationError, match="forbidden provider-visible key"):
        prepare_openrouter_route_request_v1(body)


def test_entropy_firewall_rejects_headers_and_credential_value_markers() -> None:
    headers = _headers()
    headers["X-Branch-ID"] = "sibling-a"
    with pytest.raises(ContractValidationError, match="forbidden provider-visible key"):
        prepare_openrouter_route_request_v1(semantic_headers=headers)

    body = _body()
    messages = body["messages"]
    assert isinstance(messages, list)
    messages[1]["content"] = "Bearer secret-placeholder"
    with pytest.raises(ContractValidationError, match="credential material"):
        prepare_openrouter_route_request_v1(body)


def test_non_json_inputs_and_nfc_key_collisions_fail_closed() -> None:
    body = _body()
    body[1] = "not a string key"  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="non-string JSON key"):
        prepare_openrouter_route_request_v1(body)

    body = _body()
    body["Cafe\u0301"] = 1
    body["Caf\u00e9"] = 2
    with pytest.raises(ContractValidationError, match="duplicate key"):
        prepare_openrouter_route_request_v1(body)


def test_caller_mutation_after_preparation_cannot_change_prepared_bytes() -> None:
    body = _body()
    headers = _headers()
    prepared = prepare_openrouter_route_request_v1(body, headers)
    original_body = prepared.body_bytes
    original_headers = prepared.header_bytes
    original_id = prepared.route_intent_id

    body["model"] = "mutated/after-preparation"
    headers["X-OpenRouter-Cache"] = "true"
    assert prepared.body_bytes == original_body
    assert prepared.header_bytes == original_headers
    assert prepared.route_intent_id == original_id
    assert hashlib.sha256(original_body).hexdigest() == prepared.body_sha256
    assert hashlib.sha256(original_headers).hexdigest() == prepared.header_sha256


def test_renderer_uses_canonical_sorted_compact_utf8_json_only() -> None:
    prepared = prepare_openrouter_route_request_v1(_body(), _headers())
    assert canonical_json(json.loads(prepared.body_bytes)) == prepared.canonical_body_json
    assert canonical_json(json.loads(prepared.header_bytes)) == (
        prepared.canonical_semantic_headers_json
    )
    assert b"\n" not in prepared.body_bytes
    assert b"\n" not in prepared.header_bytes

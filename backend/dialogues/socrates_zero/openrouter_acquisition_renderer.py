"""Pure canonical renderer for the network-inert OpenRouter acquisition adapter.

Only the already-frozen provider-visible logical request and immutable adapter
controls may influence the returned application body.  This module has no
credential, environment, transport, provider-SDK, model, or runtime imports.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from .acquisition_contracts import AcquisitionSeedStatus, AcquisitionSemanticRequest
from .contracts import ContractValidationError, canonical_json
from .openrouter_acquisition_contracts import (
    OPENROUTER_MAX_OUTPUT_TOKENS,
    OPENROUTER_MODEL_ID,
    OPENROUTER_PROVIDER_ID,
    OpenRouterControlPolicy,
    OpenRouterEndpointPolicy,
    OpenRouterEvidenceState,
    OpenRouterPreparedBody,
    OpenRouterRoutePolicy,
)


OPENROUTER_ACQUISITION_RENDERER_VERSION = (
    "socrateszero-openrouter-renderer/v0"
)

_SOURCE_TOP_LEVEL_KEYS = frozenset(
    {
        "max_output_tokens",
        "messages",
        "metadata",
        "response_format",
        "temperature",
        "tools",
    }
)
_EXACT_FORBIDDEN_KEYS = frozenset(
    {
        "acquisition_attempt_id",
        "agent_id",
        "api_key",
        "attempt_id",
        "attempt_index",
        "attempt_no",
        "attempt_number",
        "attempt_ordinal",
        "attempt_order",
        "authorization",
        "branch_id",
        "branch_order",
        "commit_id",
        "cookie",
        "cookies",
        "created_at",
        "credential",
        "credentials",
        "cwd",
        "dispatch_order",
        "evaluated_at",
        "evaluation_order",
        "executed_at",
        "execution_order",
        "experiment_id",
        "experiment_label",
        "experiment_order",
        "experiment_outcome",
        "experiment_result",
        "file_path",
        "finished_at",
        "headers",
        "invocation_order",
        "local_path",
        "memory_address",
        "memory_state",
        "nonce",
        "pid",
        "process_id",
        "process_state",
        "provider",
        "receipt_id",
        "repository_path",
        "response_id",
        "round_index",
        "route",
        "routes",
        "run_order",
        "seed",
        "session_id",
        "set_cookie",
        "sibling_branch_id",
        "sibling_id",
        "sibling_order",
        "sibling_state",
        "slot_index",
        "started_at",
        "task_id",
        "timestamp",
        "transport_id",
        "transport_attempt_id",
        "transport_order",
        "transport_request_id",
        "updated_at",
        "uuid",
        "working_directory",
        "workspace_path",
    }
)
_SECRET_PARTS = frozenset(
    {
        "authorization",
        "credential",
        "credentials",
        "password",
        "secret",
        "secrets",
    }
)
_TOKEN_QUALIFIERS = frozenset(
    {"access", "api", "auth", "authentication", "bearer", "credential", "secret"}
)
_KEY_QUALIFIERS = frozenset(
    {"access", "api", "auth", "authentication", "credential", "private", "secret"}
)
_PROCESS_QUALIFIERS = frozenset(
    {
        "agent",
        "attempt",
        "branch",
        "commit",
        "experiment",
        "process",
        "receipt",
        "round",
        "session",
        "slot",
        "task",
        "transport",
    }
)


def _normalized_key_parts(key: str) -> tuple[str, tuple[str, ...], str]:
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower()
    parts = tuple(part for part in normalized.split("_") if part)
    return normalized, parts, "".join(parts)


def _forbidden_key(key: str) -> bool:
    normalized, parts, compact = _normalized_key_parts(key)
    part_set = frozenset(parts)
    if normalized in _EXACT_FORBIDDEN_KEYS:
        return True
    if part_set.intersection({"header", "headers", "cookie", "cookies"}):
        return True
    if part_set.intersection(_SECRET_PARTS):
        return True
    if "token" in part_set and part_set.intersection(_TOKEN_QUALIFIERS):
        return True
    if "key" in part_set and part_set.intersection(_KEY_QUALIFIERS):
        return True
    if compact in {"apikey", "bearertoken", "privatekey", "setcookie"}:
        return True
    if part_set.intersection(
        {"id", "index", "no", "number", "ordinal", "order"}
    ) and part_set.intersection(_PROCESS_QUALIFIERS):
        return True
    if part_set.intersection({"timestamp", "nonce", "uuid", "pid"}):
        return True
    if "path" in part_set and part_set.intersection(
        {"cwd", "file", "filesystem", "local", "repo", "repository", "working", "workspace"}
    ):
        return True
    if "experiment" in part_set and part_set.intersection(
        {"label", "outcome", "result"}
    ):
        return True
    if "process" in part_set and part_set.intersection({"memory", "state"}):
        return True
    if "memory" in part_set and part_set.intersection({"address", "state"}):
        return True
    if "sibling" in part_set and part_set.intersection({"branch", "state"}):
        return True
    return False


def _normalize_semantic_json(value: object, path: str = "$") -> object:
    """Return a recursively NFC-normalized JSON value or fail closed."""

    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise ContractValidationError(f"non-string JSON key at {path}")
            key = unicodedata.normalize("NFC", raw_key)
            if _forbidden_key(key):
                raise ContractValidationError(
                    f"forbidden provider-visible key {key!r} at {path}"
                )
            if key in normalized:
                raise ContractValidationError(
                    f"NFC normalization caused a duplicate key {key!r} at {path}"
                )
            normalized[key] = _normalize_semantic_json(child, f"{path}.{key}")
        return normalized
    if isinstance(value, list):
        return [
            _normalize_semantic_json(child, f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int, float):
        return value
    raise ContractValidationError(f"non-JSON value at {path}")


def _validated_source_body(request: AcquisitionSemanticRequest) -> dict[str, object]:
    visible = request.provider_visible_request
    try:
        raw = visible.canonical_request_json.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractValidationError("provider-visible request is not UTF-8") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if visible.byte_length != len(raw) or visible.sha256 != digest:
        raise ContractValidationError("provider-visible byte evidence does not match")
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError("provider-visible request is not JSON") from exc
    if not isinstance(parsed, dict) or canonical_json(parsed).encode("utf-8") != raw:
        raise ContractValidationError("provider-visible request is not canonical JSON")
    normalized = _normalize_semantic_json(parsed)
    if not isinstance(normalized, dict):
        raise ContractValidationError("provider-visible request must be an object")
    unknown = frozenset(normalized) - _SOURCE_TOP_LEVEL_KEYS
    if unknown:
        raise ContractValidationError(
            "unsupported provider-visible fields: " + ", ".join(sorted(unknown))
        )
    return normalized


def _strict_zero(value: object, field_name: str) -> None:
    if type(value) not in (int, float) or value != 0:
        raise ContractValidationError(f"{field_name} must be exactly zero")


def _application_payload(
    request: AcquisitionSemanticRequest,
    control_policy: OpenRouterControlPolicy,
) -> dict[str, object]:
    source = _validated_source_body(request)
    messages = source.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ContractValidationError("provider-visible messages must contain system and user")
    for index, (message, expected_role) in enumerate(
        zip(messages, ("system", "user"))
    ):
        if not isinstance(message, dict) or set(message) != {"content", "role"}:
            raise ContractValidationError(
                f"provider-visible message {index} must contain only role and content"
            )
        if not isinstance(message["role"], str) or not message["role"].strip():
            raise ContractValidationError(f"provider-visible message {index} has no role")
        if message["role"] != expected_role:
            raise ContractValidationError(
                f"provider-visible message {index} role is not {expected_role}"
            )
        if not isinstance(message["content"], str) or not message["content"].strip():
            raise ContractValidationError(f"provider-visible message {index} has no content")
    response_format = source.get("response_format")
    if not isinstance(response_format, dict) or not response_format:
        raise ContractValidationError("provider-visible response_format must be an object")
    if source.get("metadata", {}) != {}:
        raise ContractValidationError("provider-visible metadata must remain empty")
    if source.get("tools") != list(control_policy.tools):
        raise ContractValidationError("provider-visible tools must remain empty")
    _strict_zero(source.get("temperature"), "provider-visible temperature")
    if type(source.get("max_output_tokens")) is not int or source.get(
        "max_output_tokens"
    ) != control_policy.max_output_tokens:
        raise ContractValidationError("provider-visible output-token cap changed")

    # All duplicated links and controls must agree before bytes are prepared.
    if request.requested_binding.provider_id != OPENROUTER_PROVIDER_ID:
        raise ContractValidationError("semantic request provider differs from OpenRouter")
    if request.requested_binding.model_id != OPENROUTER_MODEL_ID:
        raise ContractValidationError("semantic request model differs from frozen model")
    if request.request_configuration.max_output_tokens != control_policy.max_output_tokens:
        raise ContractValidationError("semantic request output-token cap changed")
    _strict_zero(request.request_configuration.temperature, "request temperature")
    if request.request_configuration.temperature != control_policy.temperature:
        raise ContractValidationError("request and adapter temperatures differ")
    if request.request_configuration.fallback_allowed != control_policy.fallback_allowed:
        raise ContractValidationError("request and adapter fallback controls differ")
    if (
        request.request_configuration.explicit_retry_limit
        != control_policy.explicit_retry_limit
        or request.request_configuration.adapter_retry_limit
        != control_policy.adapter_retry_limit
        or request.request_configuration.hidden_transport_retry_limit
        != control_policy.hidden_transport_retry_limit
    ):
        raise ContractValidationError("request and adapter retry controls differ")
    if (
        request.request_configuration.sdk_internal_retry_limit != 0
        or control_policy.sdk_internal_retry_state
        is not OpenRouterEvidenceState.NOT_APPLICABLE
        or control_policy.sdk_internal_retry_limit is not None
    ):
        raise ContractValidationError("SDK retry non-applicability changed")
    if request.request_configuration.tools_allowed or control_policy.tools:
        raise ContractValidationError("request and adapter tools must remain disabled")
    if (
        request.request_configuration.seed.status is not AcquisitionSeedStatus.UNSUPPORTED
        or request.request_configuration.seed.value is not None
        or control_policy.seed_state is not OpenRouterEvidenceState.PROVEN_UNSUPPORTED
        or control_policy.seed is not None
    ):
        raise ContractValidationError("seed must be unsupported and absent")
    if request.request_configuration.provider_visible_metadata_digest != (
        request.provider_visible_request.sha256 or ""
    ):
        raise ContractValidationError("request configuration does not link visible bytes")
    if response_format != {"type": control_policy.response_format}:
        raise ContractValidationError("request and adapter response formats differ")

    return {
        "max_tokens": control_policy.max_output_tokens,
        "messages": messages,
        "model": OPENROUTER_MODEL_ID,
        "response_format": response_format,
        "stream": control_policy.stream,
        "temperature": control_policy.temperature,
        "tools": list(control_policy.tools),
    }


def render_openrouter_application_body(
    request: AcquisitionSemanticRequest,
    control_policy: OpenRouterControlPolicy,
    *,
    endpoint_policy: OpenRouterEndpointPolicy | None = None,
    route_policy: OpenRouterRoutePolicy | None = None,
) -> OpenRouterPreparedBody:
    """Render exact OpenRouter bytes from semantic input plus frozen controls."""

    if type(request) is not AcquisitionSemanticRequest:
        raise ContractValidationError("request must use the exact frozen semantic type")
    if type(control_policy) is not OpenRouterControlPolicy:
        raise ContractValidationError("control policy must use the exact frozen type")
    endpoint = endpoint_policy or OpenRouterEndpointPolicy()
    route = route_policy or OpenRouterRoutePolicy()
    if type(endpoint) is not OpenRouterEndpointPolicy:
        raise ContractValidationError("endpoint policy must use the exact frozen type")
    if type(route) is not OpenRouterRoutePolicy:
        raise ContractValidationError("route policy must use the exact frozen type")
    if route.router_id != OPENROUTER_PROVIDER_ID or route.requested_model_id != OPENROUTER_MODEL_ID:
        raise ContractValidationError("route policy binding differs from frozen binding")
    if route.upstream_provider_id is not None or route.upstream_route_id is not None:
        raise ContractValidationError("unestablished upstream route cannot enter rendering")

    payload = _application_payload(request, control_policy)
    canonical_body_json = canonical_json(payload)
    return OpenRouterPreparedBody(
        renderer_version=OPENROUTER_ACQUISITION_RENDERER_VERSION,
        control_policy_id=control_policy.control_policy_id or "",
        endpoint_policy_id=endpoint.endpoint_policy_id or "",
        route_policy_id=route.route_policy_id or "",
        canonical_body_json=canonical_body_json,
    )


render_openrouter_application_body_v0 = render_openrouter_application_body


__all__ = [
    "OPENROUTER_ACQUISITION_RENDERER_VERSION",
    "render_openrouter_application_body",
    "render_openrouter_application_body_v0",
]

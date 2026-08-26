"""Pure canonical renderer for OpenRouter route-controls v1.

The renderer consumes only a frozen policy plus explicit semantic mappings and
returns immutable prepared application bytes.  It never reconstructs bytes at
dispatch time and imports no credential, transport, provider, model, tool, or
CED runtime.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path

from .contracts import ContractValidationError, canonical_json
from .openrouter_route_controls_contracts import (
    EXPECTED_OPENROUTER_ROUTE_BODY_V1,
    EXPECTED_OPENROUTER_SEMANTIC_HEADERS_V1,
    OPENROUTER_ROUTE_RENDERER_VERSION,
    OpenRouterPreparedRouteRequestV1,
    OpenRouterRouteControlPolicyV1,
    default_openrouter_route_control_policy_v1,
    verify_openrouter_spec_manifest_v1,
)


_FORBIDDEN_EXACT_KEYS_V1 = frozenset(
    {
        "acquisition_attempt_id",
        "agent_id",
        "api_key",
        "artifact_path",
        "attempt_id",
        "attempt_index",
        "attempt_number",
        "authorization",
        "branch_id",
        "commit_id",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "cwd",
        "evaluated_at",
        "evaluation_result",
        "experiment_id",
        "file_path",
        "headers",
        "local_path",
        "machine_name",
        "nonce",
        "pid",
        "process_id",
        "receipt_id",
        "repository_path",
        "response_id",
        "session_id",
        "set_cookie",
        "sibling_branch_id",
        "task_id",
        "timestamp",
        "transport_id",
        "transport_request_id",
        "uuid",
        "working_directory",
        "workspace_path",
    }
)
_SECRET_PARTS_V1 = frozenset(
    {"authorization", "credential", "credentials", "password", "secret", "secrets"}
)
_TOKEN_QUALIFIERS_V1 = frozenset(
    {"access", "api", "auth", "authentication", "bearer", "credential", "secret"}
)
_KEY_QUALIFIERS_V1 = frozenset(
    {"access", "api", "auth", "authentication", "credential", "private", "secret"}
)
_PROCESS_QUALIFIERS_V1 = frozenset(
    {
        "agent",
        "attempt",
        "branch",
        "commit",
        "experiment",
        "process",
        "receipt",
        "session",
        "task",
        "transport",
    }
)
_FORBIDDEN_VALUE_MARKERS_V1 = (
    "authorization:",
    "bearer ",
    "openrouter_api_key",
    "sk-",
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
    if normalized in _FORBIDDEN_EXACT_KEYS_V1:
        return True
    if part_set.intersection({"header", "headers", "cookie", "cookies"}):
        return True
    if part_set.intersection(_SECRET_PARTS_V1):
        return True
    if "token" in part_set and part_set.intersection(_TOKEN_QUALIFIERS_V1):
        return True
    if "key" in part_set and part_set.intersection(_KEY_QUALIFIERS_V1):
        return True
    if compact in {"apikey", "bearertoken", "privatekey", "setcookie"}:
        return True
    if part_set.intersection({"id", "index", "number", "ordinal", "order"}) and (
        part_set.intersection(_PROCESS_QUALIFIERS_V1)
    ):
        return True
    if part_set.intersection({"timestamp", "nonce", "uuid", "pid"}):
        return True
    if "path" in part_set and part_set.intersection(
        {
            "artifact",
            "cwd",
            "file",
            "filesystem",
            "local",
            "repo",
            "repository",
            "working",
            "workspace",
        }
    ):
        return True
    if "machine" in part_set and "name" in part_set:
        return True
    if "evaluation" in part_set and part_set.intersection(
        {"expected", "label", "outcome", "result"}
    ):
        return True
    return False


def _normalize_semantic_json(value: object, path: str = "$") -> object:
    """Return an NFC-normalized JSON value after the entropy firewall."""

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
    if isinstance(value, (list, tuple)):
        return [
            _normalize_semantic_json(child, f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    if isinstance(value, str):
        normalized_string = unicodedata.normalize("NFC", value)
        lowered = normalized_string.lower()
        if any(marker in lowered for marker in _FORBIDDEN_VALUE_MARKERS_V1):
            raise ContractValidationError(
                f"forbidden credential material in provider-visible value at {path}"
            )
        return normalized_string
    if value is None or type(value) in (bool, int, float):
        return value
    raise ContractValidationError(f"non-JSON value at {path}")


def _mutable_expected_body(policy: OpenRouterRouteControlPolicyV1) -> dict[str, object]:
    return policy.route_intent.application_body()


def _mutable_expected_headers(
    policy: OpenRouterRouteControlPolicyV1,
) -> dict[str, str]:
    return policy.header_policy.semantic_headers()


def prepare_openrouter_route_request_v1(
    source_body: Mapping[str, object] | None = None,
    semantic_headers: Mapping[str, object] | None = None,
    *,
    policy: OpenRouterRouteControlPolicyV1 | None = None,
    repository_root: Path | None = None,
) -> OpenRouterPreparedRouteRequestV1:
    """Prepare exact canonical body/header bytes for the frozen v1 route intent."""

    verified_binding = verify_openrouter_spec_manifest_v1(repository_root)
    route_policy = policy or default_openrouter_route_control_policy_v1(
        specification_binding=verified_binding
    )
    if type(route_policy) is not OpenRouterRouteControlPolicyV1:
        raise ContractValidationError("policy must use the exact frozen v1 type")
    if route_policy.specification_binding != verified_binding:
        raise ContractValidationError(
            "route policy does not bind the verified specification manifest"
        )

    body_input: object = (
        _mutable_expected_body(route_policy) if source_body is None else source_body
    )
    header_input: object = (
        _mutable_expected_headers(route_policy)
        if semantic_headers is None
        else semantic_headers
    )
    body = _normalize_semantic_json(body_input)
    headers = _normalize_semantic_json(header_input)
    if not isinstance(body, dict):
        raise ContractValidationError("provider-visible body must be a JSON object")
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in headers.items()
    ):
        raise ContractValidationError(
            "semantic headers must be a string-to-string JSON object"
        )
    expected_body = _mutable_expected_body(route_policy)
    expected_headers = _mutable_expected_headers(route_policy)
    if canonical_json(body) != canonical_json(expected_body):
        raise ContractValidationError(
            "provider-visible body differs from the frozen v1 request intent"
        )
    if canonical_json(headers) != canonical_json(expected_headers):
        raise ContractValidationError(
            "semantic headers differ from the frozen v1 header intent"
        )
    return OpenRouterPreparedRouteRequestV1(
        renderer_version=OPENROUTER_ROUTE_RENDERER_VERSION,
        route_control_policy=route_policy,
        canonical_body_json=canonical_json(body),
        canonical_semantic_headers_json=canonical_json(headers),
    )


render_openrouter_route_request_v1 = prepare_openrouter_route_request_v1
prepare_openrouter_application_request_v1 = prepare_openrouter_route_request_v1


__all__ = [
    "EXPECTED_OPENROUTER_ROUTE_BODY_V1",
    "EXPECTED_OPENROUTER_SEMANTIC_HEADERS_V1",
    "OPENROUTER_ROUTE_RENDERER_VERSION",
    "prepare_openrouter_application_request_v1",
    "prepare_openrouter_route_request_v1",
    "render_openrouter_route_request_v1",
]

"""Immutable, network-inert OpenRouter acquisition-control contracts.

This module freezes only the additive Phase 8.5B adapter-control evidence
surface.  It does not import the production OpenRouter adapter, inspect the
environment, retrieve credentials, open a socket, invoke a provider/model/tool,
or apply an observation to CED.

The repository can prove deterministic canned behavior offline.  It cannot yet
prove OpenRouter's upstream route, provider-side fallback behavior, billed
input-token framing, output-cap wire support, pricing, or a real HTTP boundary.
Those facts are represented explicitly as ``NOT_ESTABLISHED``; they are never
coerced to false or numeric zero.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from enum import Enum
from typing import Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id


OPENROUTER_ACQUISITION_ADAPTER_ID = (
    "socrateszero-openrouter-acquisition-adapter-controls/v0"
)
OPENROUTER_PROVIDER_ID = "openrouter"
OPENROUTER_MODEL_ID = "openai/gpt-4.1-mini"
OPENROUTER_ENDPOINT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_ENDPOINT_SCHEME = "https"
OPENROUTER_ENDPOINT_HOST = "openrouter.ai"
OPENROUTER_ENDPOINT_PORT = 443
OPENROUTER_ENDPOINT_PATH = "/api/v1/chat/completions"
OPENROUTER_MAX_OUTPUT_TOKENS = 256
OPENROUTER_TIMEOUT_MS = 5_000
OPENROUTER_CANNED_CANCELLATION_GRACE_MS = 50
OPENROUTER_CANNED_CLEANUP_ROUNDS = 2
OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES = 65_536
# Compatibility name retained inside this additive branch; it now denotes the
# honest canned transport bound rather than the 57-byte reference fixture size.
OPENROUTER_REFERENCE_RAW_RESPONSE_MAX_BYTES = OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES
OPENROUTER_INPUT_BOUND_METHOD = "FULL_REQUEST_UTF8_BYTE_COUNT_V0"
OPENROUTER_HTTP_DEPENDENCY_SPEC = "aiohttp>=3.9.0"
OPENROUTER_RESPONSE_FORMAT = "text"
OPENROUTER_COST_CALCULATION_RULE = "INTEGER_CEILING_PER_LINE_THEN_SUM_V0"
OPENROUTER_IDENTITY_CANONICALIZATION_RULE_ID = "EXACT_CODEPOINT_EQUALITY_V0"
MAX_SIGNED_64 = 9_223_372_036_854_775_807

ENDPOINT_POLICY_SCHEMA_VERSION = "socrateszero-openrouter-endpoint-policy/v0"
TRANSPORT_POLICY_SCHEMA_VERSION = "socrateszero-openrouter-transport-policy/v0"
ROUTE_POLICY_SCHEMA_VERSION = "socrateszero-openrouter-route-policy/v0"
CONTROL_POLICY_SCHEMA_VERSION = "socrateszero-openrouter-control-policy/v0"
PREPARED_BODY_SCHEMA_VERSION = "socrateszero-openrouter-prepared-body/v0"
TOKEN_POLICY_SCHEMA_VERSION = "socrateszero-openrouter-token-policy/v0"
PRICING_RECORD_SCHEMA_VERSION = "socrateszero-openrouter-pricing-record/v0"
COST_BOUND_SCHEMA_VERSION = "socrateszero-openrouter-cost-bound/v0"
CAPABILITY_SNAPSHOT_SCHEMA_VERSION = (
    "socrateszero-openrouter-capability-snapshot/v0"
)
RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION = (
    "socrateszero-openrouter-raw-response-evidence/v0"
)
IDENTITY_EVIDENCE_SCHEMA_VERSION = (
    "socrateszero-openrouter-identity-evidence/v0"
)
USAGE_EVIDENCE_SCHEMA_VERSION = "socrateszero-openrouter-usage-evidence/v0"
ATTEMPT_RECEIPT_SCHEMA_VERSION = "socrateszero-openrouter-attempt-receipt/v0"
HEADER_POLICY_SCHEMA_VERSION = "socrateszero-openrouter-header-policy/v0"
CANNED_RESPONSE_ENVELOPE_SCHEMA_VERSION = (
    "socrateszero-openrouter-canned-response-envelope/v0"
)

_HEX64_PATTERN = r"^[0-9a-f]{64}$"
_UNKNOWN_PRICING_ITEMS = (
    "input_token_price",
    "output_token_price",
    "route_or_non_token_price",
)
OPENROUTER_IDENTITY_SOURCE_FIELDS = tuple(
    sorted(("configuration_digest", "fallback_used", "model", "provider"))
)
OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS = tuple(
    sorted(("usage.input_tokens", "usage.output_tokens", "usage.total_tokens"))
)
OPENROUTER_LOCALLY_DERIVED_USAGE_SOURCE_FIELDS = tuple(
    sorted(("usage.input_tokens", "usage.output_tokens"))
)
OPENROUTER_LOCALLY_DERIVED_USAGE_FIELDS = ("usage.total_tokens",)
OPENROUTER_USAGE_TOTAL_DERIVATION_RULE_ID = "TOTAL_EQUALS_INPUT_PLUS_OUTPUT_V0"
_PREPARED_BODY_KEYS = frozenset(
    {
        "model",
        "messages",
        "temperature",
        "max_tokens",
        "stream",
        "tools",
        "response_format",
    }
)
_CANNED_RESPONSE_KEYS = frozenset(
    {
        "id",
        "provider",
        "model",
        "configuration_digest",
        "choices",
        "fallback_used",
        "explicit_retry_count",
        "adapter_retry_count",
        "sdk_internal_retry_count",
        "hidden_transport_retry_count",
        "stream_used",
        "tool_calls",
        "usage",
    }
)
_TYPED_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_FORBIDDEN_SECRET_MARKERS = (
    b"authorization",
    b"bearer ",
    b"api_key",
    b"apikey",
    b"openrouter_api_key",
    b"sk-",
)


class OpenRouterEvidenceState(str, Enum):
    """The only truthful evidence states available on this offline branch."""

    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    PROVEN_UNSUPPORTED = "PROVEN_UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OpenRouterTransportMode(str, Enum):
    CANNED_ONLY = "CANNED_ONLY"


class OpenRouterProxyMode(str, Enum):
    DISABLED = "DISABLED"


class OpenRouterTransportStatus(str, Enum):
    DELIVERED = "DELIVERED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class OpenRouterUsageCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    UNKNOWN = "UNKNOWN"


class OpenRouterAttemptOutcome(str, Enum):
    CANNED_OBSERVATION_CAPTURED = "CANNED_OBSERVATION_CAPTURED"
    FAILED_CLOSED = "FAILED_CLOSED"


class OpenRouterFinishReason(str, Enum):
    STOP = "stop"


class OpenRouterPrivacyClassification(str, Enum):
    SYNTHETIC_CANNED_OBSERVATION = "SYNTHETIC_CANNED_OBSERVATION"


class OpenRouterRawRetentionState(str, Enum):
    INLINE_RAW_BYTES_RETAINED = "INLINE_RAW_BYTES_RETAINED"
    NO_RAW_BYTES_CAPTURED = "NO_RAW_BYTES_CAPTURED"


class OpenRouterUsageSource(str, Enum):
    UNKNOWN = "UNKNOWN"
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    LOCALLY_DERIVED = "LOCALLY_DERIVED"


class OpenRouterResponseValidationState(str, Enum):
    NO_TRANSPORT_BYTES = "NO_TRANSPORT_BYTES"
    TRANSPORT_BYTES_CAPTURED = "TRANSPORT_BYTES_CAPTURED"
    IDENTITY_DERIVED = "IDENTITY_DERIVED"
    USAGE_DERIVED = "USAGE_DERIVED"
    ADAPTER_RESPONSE_VALIDATED = "ADAPTER_RESPONSE_VALIDATED"


class _FrozenOpenRouterContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _canonical_strings(values: Tuple[str, ...], field_name: str) -> Tuple[str, ...]:
    ordered = tuple(sorted(values))
    if any(not item.strip() for item in ordered):
        raise ContractValidationError(f"{field_name} must not contain blanks")
    if len(ordered) != len(set(ordered)):
        raise ContractValidationError(f"{field_name} must not contain duplicates")
    return ordered


def _freeze_id(
    instance: BaseModel,
    *,
    field_name: str,
    prefix: str,
    payload: object,
) -> None:
    expected = stable_contract_id(prefix, payload)
    supplied = getattr(instance, field_name)
    if supplied is not None and supplied != expected:
        raise ContractValidationError(f"{field_name} does not match contract content")
    object.__setattr__(instance, field_name, expected)


def _canonical_base64(value: str) -> bytes:
    try:
        encoded = value.encode("ascii")
        raw = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise ContractValidationError("raw_response_base64 must be canonical Base64") from exc
    if base64.b64encode(raw).decode("ascii") != value:
        raise ContractValidationError("raw_response_base64 must be canonical Base64")
    return raw


def _ceil_microusd(tokens: int, rate_per_million: int) -> int:
    product = _checked_multiply(tokens, rate_per_million, "token-price product")
    quotient, remainder = divmod(product, 1_000_000)
    return _checked_add(
        quotient,
        1 if remainder else 0,
        "ceiling-rounded micro-USD line item",
    )


def calculate_openrouter_cost_line_microusd(
    tokens: int, rate_per_million: int
) -> int:
    """Return one ceiling-rounded micro-USD line using exact integer inputs."""

    if type(tokens) is not int or type(rate_per_million) is not int:
        raise ContractValidationError("cost-line inputs must be exact integers")
    return _ceil_microusd(tokens, rate_per_million)


def _checked_multiply(left: int, right: int, field_name: str) -> int:
    if left < 0 or right < 0 or left > MAX_SIGNED_64 or right > MAX_SIGNED_64:
        raise ContractValidationError(f"{field_name} is outside signed 64-bit domain")
    if left and right > MAX_SIGNED_64 // left:
        raise ContractValidationError(f"{field_name} overflows signed 64-bit domain")
    return left * right


def _checked_add(left: int, right: int, field_name: str) -> int:
    if left < 0 or right < 0 or left > MAX_SIGNED_64 or right > MAX_SIGNED_64:
        raise ContractValidationError(f"{field_name} is outside signed 64-bit domain")
    if right > MAX_SIGNED_64 - left:
        raise ContractValidationError(f"{field_name} overflows signed 64-bit domain")
    return left + right


def _typed_code(value: str) -> str:
    _nonblank(value)
    if _TYPED_CODE_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a typed uppercase code")
    return value


def _assert_no_secret_material(value: object, field_name: str) -> None:
    if isinstance(value, bytes):
        raw = value.lower()
    elif isinstance(value, str):
        raw = value.encode("utf-8").lower()
    elif isinstance(value, Mapping):
        for key, child in value.items():
            _assert_no_secret_material(str(key), field_name)
            _assert_no_secret_material(child, field_name)
        return
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_secret_material(child, field_name)
        return
    else:
        return
    if any(marker in raw for marker in _FORBIDDEN_SECRET_MARKERS):
        raise ContractValidationError(f"{field_name} contains forbidden credential material")


class OpenRouterHeaderPolicy(_FrozenOpenRouterContract):
    """Semantic headers only; credentials remain out-of-band and unretained."""

    schema_version: Literal[HEADER_POLICY_SCHEMA_VERSION] = HEADER_POLICY_SCHEMA_VERSION
    header_policy_id: Optional[str] = None
    content_type_name: Literal["Content-Type"] = "Content-Type"
    content_type_value: Literal["application/json"] = "application/json"
    http_referer_state: Literal["ABSENT"] = "ABSENT"
    x_title_state: Literal["ABSENT"] = "ABSENT"
    authorization_delivery: Literal["OUT_OF_BAND_ONLY"] = "OUT_OF_BAND_ONLY"
    authorization_in_semantic_body_allowed: Literal[False] = False
    authorization_in_ids_allowed: Literal[False] = False
    authorization_in_artifacts_allowed: Literal[False] = False
    credential_material_allowed: Literal[False] = False
    optional_attribution_headers: Tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterHeaderPolicy":
        headers = _canonical_strings(
            self.optional_attribution_headers, "optional_attribution_headers"
        )
        if headers:
            raise ContractValidationError("optional attribution headers must be absent")
        object.__setattr__(self, "optional_attribution_headers", headers)
        _freeze_id(
            self,
            field_name="header_policy_id",
            prefix="szorheaders",
            payload=self.model_dump(mode="json", exclude={"header_policy_id"}),
        )
        return self


class OpenRouterEndpointPolicy(_FrozenOpenRouterContract):
    schema_version: Literal[ENDPOINT_POLICY_SCHEMA_VERSION] = ENDPOINT_POLICY_SCHEMA_VERSION
    endpoint_policy_id: Optional[str] = None
    url: Literal[OPENROUTER_ENDPOINT_URL] = OPENROUTER_ENDPOINT_URL
    scheme: Literal[OPENROUTER_ENDPOINT_SCHEME] = OPENROUTER_ENDPOINT_SCHEME
    host: Literal[OPENROUTER_ENDPOINT_HOST] = OPENROUTER_ENDPOINT_HOST
    port: Literal[OPENROUTER_ENDPOINT_PORT] = OPENROUTER_ENDPOINT_PORT
    path: Literal[OPENROUTER_ENDPOINT_PATH] = OPENROUTER_ENDPOINT_PATH
    method: Literal["POST"] = "POST"
    content_type: Literal["application/json"] = "application/json"
    tls_required: Literal[True] = True
    header_policy: OpenRouterHeaderPolicy = Field(
        default_factory=OpenRouterHeaderPolicy
    )
    userinfo: Literal[""] = ""
    query: Literal[""] = ""
    fragment: Literal[""] = ""
    redirects_allowed: Literal[False] = False
    max_redirects: Literal[0] = 0
    proxy_mode: Literal[OpenRouterProxyMode.DISABLED] = OpenRouterProxyMode.DISABLED
    environment_proxy_allowed: Literal[False] = False
    alternate_endpoints: Tuple[str, ...] = ()
    telemetry_endpoints: Tuple[str, ...] = ()
    live_enforcement_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterEndpointPolicy":
        alternates = _canonical_strings(self.alternate_endpoints, "alternate_endpoints")
        telemetry = _canonical_strings(self.telemetry_endpoints, "telemetry_endpoints")
        if alternates or telemetry:
            raise ContractValidationError("alternate and telemetry endpoints must be empty")
        object.__setattr__(self, "alternate_endpoints", alternates)
        object.__setattr__(self, "telemetry_endpoints", telemetry)
        if self.header_policy.content_type_value != self.content_type:
            raise ContractValidationError("endpoint and header content types must match")
        _freeze_id(
            self,
            field_name="endpoint_policy_id",
            prefix="szorendpoint",
            payload=self.model_dump(mode="json", exclude={"endpoint_policy_id"}),
        )
        return self


class OpenRouterTransportPolicy(_FrozenOpenRouterContract):
    schema_version: Literal[TRANSPORT_POLICY_SCHEMA_VERSION] = TRANSPORT_POLICY_SCHEMA_VERSION
    transport_policy_id: Optional[str] = None
    mode: Literal[OpenRouterTransportMode.CANNED_ONLY] = OpenRouterTransportMode.CANNED_ONLY
    http_dependency_spec: Literal[
        OPENROUTER_HTTP_DEPENDENCY_SPEC
    ] = OPENROUTER_HTTP_DEPENDENCY_SPEC
    http_dependency_pin_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    external_network_allowed: Literal[False] = False
    credential_access_allowed: Literal[False] = False
    provider_sdk_allowed: Literal[False] = False
    model_execution_allowed: Literal[False] = False
    max_canned_transport_invocations: Literal[1] = 1
    total_timeout_ms: Literal[OPENROUTER_TIMEOUT_MS] = OPENROUTER_TIMEOUT_MS
    canned_cancellation_grace_ms: Literal[
        OPENROUTER_CANNED_CANCELLATION_GRACE_MS
    ] = OPENROUTER_CANNED_CANCELLATION_GRACE_MS
    canned_cleanup_rounds: Literal[
        OPENROUTER_CANNED_CLEANUP_ROUNDS
    ] = OPENROUTER_CANNED_CLEANUP_ROUNDS
    canned_cleanup_policy: Literal[
        "CANCEL_ACK_THEN_TWO_BOUNDED_CLEANUP_ROUNDS_V0"
    ] = "CANCEL_ACK_THEN_TWO_BOUNDED_CLEANUP_ROUNDS_V0"
    canned_worker_termination_required: Literal[True] = True
    canned_raw_response_max_bytes: Literal[
        OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES
    ] = OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES
    live_connect_timeout_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_connect_timeout_ms: Literal[None] = None
    live_read_timeout_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_read_timeout_ms: Literal[None] = None
    live_cancellation_grace_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_cancellation_grace_ms: Literal[None] = None
    live_worker_termination_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_response_byte_limit_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_response_max_bytes: Literal[None] = None
    live_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterTransportPolicy":
        _freeze_id(
            self,
            field_name="transport_policy_id",
            prefix="szortransport",
            payload=self.model_dump(mode="json", exclude={"transport_policy_id"}),
        )
        return self


class OpenRouterRoutePolicy(_FrozenOpenRouterContract):
    schema_version: Literal[ROUTE_POLICY_SCHEMA_VERSION] = ROUTE_POLICY_SCHEMA_VERSION
    route_policy_id: Optional[str] = None
    router_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    requested_model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    upstream_route_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    upstream_provider_id: Literal[None] = None
    upstream_route_id: Literal[None] = None
    provider_side_fallback_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    application_fallback_allowed: Literal[False] = False
    adapter_fallback_allowed: Literal[False] = False
    fallback_endpoints: Tuple[str, ...] = ()
    live_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRoutePolicy":
        endpoints = _canonical_strings(self.fallback_endpoints, "fallback_endpoints")
        if endpoints:
            raise ContractValidationError("fallback endpoints must be empty")
        object.__setattr__(self, "fallback_endpoints", endpoints)
        _freeze_id(
            self,
            field_name="route_policy_id",
            prefix="szorroute",
            payload=self.model_dump(mode="json", exclude={"route_policy_id"}),
        )
        return self


class OpenRouterControlPolicy(_FrozenOpenRouterContract):
    schema_version: Literal[CONTROL_POLICY_SCHEMA_VERSION] = CONTROL_POLICY_SCHEMA_VERSION
    control_policy_id: Optional[str] = None
    temperature: Literal[0.0] = 0.0
    seed_state: Literal[
        OpenRouterEvidenceState.PROVEN_UNSUPPORTED
    ] = OpenRouterEvidenceState.PROVEN_UNSUPPORTED
    seed: Literal[None] = None
    max_output_tokens: Literal[
        OPENROUTER_MAX_OUTPUT_TOKENS
    ] = OPENROUTER_MAX_OUTPUT_TOKENS
    output_cap_wire_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    explicit_retry_limit: Literal[0] = 0
    adapter_retry_limit: Literal[0] = 0
    sdk_internal_retry_state: Literal[
        OpenRouterEvidenceState.NOT_APPLICABLE
    ] = OpenRouterEvidenceState.NOT_APPLICABLE
    sdk_internal_retry_limit: Literal[None] = None
    hidden_transport_retry_limit: Literal[0] = 0
    fallback_allowed: Literal[False] = False
    stream: Literal[False] = False
    stream_wire_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    tools: Tuple[str, ...] = ()
    tools_wire_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    response_format: Literal[OPENROUTER_RESPONSE_FORMAT] = OPENROUTER_RESPONSE_FORMAT
    response_format_wire_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterControlPolicy":
        tools = _canonical_strings(self.tools, "tools")
        if tools:
            raise ContractValidationError("tools must be empty")
        object.__setattr__(self, "tools", tools)
        _freeze_id(
            self,
            field_name="control_policy_id",
            prefix="szorcontrol",
            payload=self.model_dump(mode="json", exclude={"control_policy_id"}),
        )
        return self


class OpenRouterPreparedBody(_FrozenOpenRouterContract):
    """Exact candidate OpenRouter application bytes; canned evidence only."""

    schema_version: Literal[PREPARED_BODY_SCHEMA_VERSION] = PREPARED_BODY_SCHEMA_VERSION
    prepared_body_id: Optional[str] = None
    renderer_version: str = "socrateszero-openrouter-renderer/v0"
    endpoint_policy_id: str
    route_policy_id: str
    control_policy_id: str
    evidence_state: Literal[
        OpenRouterEvidenceState.SYNTHETIC_ONLY
    ] = OpenRouterEvidenceState.SYNTHETIC_ONLY
    canonical_body_json: str
    byte_length: Optional[int] = Field(
        default=None, ge=1, le=MAX_SIGNED_64, strict=True
    )
    sha256: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    payload_input_token_upper_bound: Optional[int] = Field(
        default=None, ge=1, le=MAX_SIGNED_64, strict=True
    )
    live_wire_acceptance_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED

    _nonblank_fields = field_validator(
        "renderer_version",
        "endpoint_policy_id",
        "route_policy_id",
        "control_policy_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_bytes_and_identify(self) -> "OpenRouterPreparedBody":
        try:
            parsed = json.loads(self.canonical_body_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError("prepared body must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ContractValidationError("prepared body must be a JSON object")
        if canonical_json(parsed) != self.canonical_body_json:
            raise ContractValidationError("prepared body must use canonical JSON")
        if set(parsed) != _PREPARED_BODY_KEYS:
            raise ContractValidationError("prepared body fields do not match frozen shape")
        _assert_no_secret_material(parsed, "prepared body")
        if parsed.get("model") != OPENROUTER_MODEL_ID:
            raise ContractValidationError("prepared body model is not the frozen model")
        temperature = parsed.get("temperature")
        if type(temperature) not in (int, float) or temperature != 0.0:
            raise ContractValidationError("prepared body temperature must be numeric zero")
        if type(parsed.get("max_tokens")) is not int or parsed["max_tokens"] != 256:
            raise ContractValidationError("prepared body max_tokens must be exactly 256")
        if type(parsed.get("stream")) is not bool or parsed["stream"] is not False:
            raise ContractValidationError("prepared body stream must be false")
        if parsed.get("tools") != []:
            raise ContractValidationError("prepared body tools must be an empty list")
        if parsed.get("response_format") != {"type": OPENROUTER_RESPONSE_FORMAT}:
            raise ContractValidationError("prepared body response_format is not frozen")
        messages = parsed.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            raise ContractValidationError("prepared body requires exactly two messages")
        for index, (message, role) in enumerate(zip(messages, ("system", "user"))):
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ContractValidationError(f"message {index} shape is invalid")
            if message.get("role") != role:
                raise ContractValidationError(f"message {index} role is invalid")
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ContractValidationError(f"message {index} content must be nonblank")
        raw = self.canonical_body_json.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        if self.byte_length is not None and self.byte_length != len(raw):
            raise ContractValidationError("prepared body byte_length does not match")
        if self.sha256 is not None and self.sha256 != digest:
            raise ContractValidationError("prepared body sha256 does not match")
        if (
            self.payload_input_token_upper_bound is not None
            and self.payload_input_token_upper_bound != len(raw)
        ):
            raise ContractValidationError(
                "payload input-token bound must equal full UTF-8 byte length"
            )
        object.__setattr__(self, "byte_length", len(raw))
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(self, "payload_input_token_upper_bound", len(raw))
        _freeze_id(
            self,
            field_name="prepared_body_id",
            prefix="szorbody",
            payload={
                "schema_version": self.schema_version,
                "renderer_version": self.renderer_version,
                "endpoint_policy_id": self.endpoint_policy_id,
                "route_policy_id": self.route_policy_id,
                "control_policy_id": self.control_policy_id,
                "evidence_state": self.evidence_state.value,
                "byte_length": len(raw),
                "sha256": digest,
                "payload_input_token_upper_bound": len(raw),
                "live_wire_acceptance_state": self.live_wire_acceptance_state.value,
            },
        )
        return self

    @property
    def body_bytes(self) -> bytes:
        return self.canonical_body_json.encode("utf-8")


class OpenRouterTokenPolicy(_FrozenOpenRouterContract):
    schema_version: Literal[TOKEN_POLICY_SCHEMA_VERSION] = TOKEN_POLICY_SCHEMA_VERSION
    token_policy_id: Optional[str] = None
    prepared_body_id: str
    prepared_body_sha256: str = Field(pattern=_HEX64_PATTERN)
    prepared_body_byte_length: int = Field(ge=1, le=MAX_SIGNED_64, strict=True)
    payload_input_bound_method: Literal[
        OPENROUTER_INPUT_BOUND_METHOD
    ] = OPENROUTER_INPUT_BOUND_METHOD
    payload_input_token_upper_bound: int = Field(
        ge=1, le=MAX_SIGNED_64, strict=True
    )
    provider_framing_overhead_tokens: Literal[None] = None
    provider_input_token_bound_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    authoritative_provider_input_token_upper_bound: Literal[None] = None
    max_output_tokens: Literal[
        OPENROUTER_MAX_OUTPUT_TOKENS
    ] = OPENROUTER_MAX_OUTPUT_TOKENS
    output_cap_wire_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    payload_only_total_token_upper_bound: Optional[int] = Field(
        default=None, ge=1, le=MAX_SIGNED_64, strict=True
    )
    authoritative_total_token_upper_bound: Literal[None] = None
    live_authorization_allowed: Literal[False] = False

    _prepared_body_id_nonblank = field_validator("prepared_body_id")(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterTokenPolicy":
        if self.payload_input_token_upper_bound != self.prepared_body_byte_length:
            raise ContractValidationError(
                "payload input-token bound must equal prepared body byte length"
            )
        total = _checked_add(
            self.payload_input_token_upper_bound,
            OPENROUTER_MAX_OUTPUT_TOKENS,
            "payload-only total-token bound",
        )
        if (
            self.payload_only_total_token_upper_bound is not None
            and self.payload_only_total_token_upper_bound != total
        ):
            raise ContractValidationError("payload-only total-token bound does not match")
        object.__setattr__(self, "payload_only_total_token_upper_bound", total)
        _freeze_id(
            self,
            field_name="token_policy_id",
            prefix="szortokens",
            payload=self.model_dump(mode="json", exclude={"token_policy_id"}),
        )
        return self

    @classmethod
    def from_prepared_body(cls, body: OpenRouterPreparedBody) -> "OpenRouterTokenPolicy":
        return cls(
            prepared_body_id=body.prepared_body_id or "",
            prepared_body_sha256=body.sha256 or "",
            prepared_body_byte_length=body.byte_length or 0,
            payload_input_token_upper_bound=body.payload_input_token_upper_bound or 0,
        )


class OpenRouterPricingRecord(_FrozenOpenRouterContract):
    schema_version: Literal[
        PRICING_RECORD_SCHEMA_VERSION
    ] = PRICING_RECORD_SCHEMA_VERSION
    pricing_record_id: Optional[str] = None
    provider_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    pricing_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED,
        OpenRouterEvidenceState.SYNTHETIC_ONLY,
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    currency: Literal["USD"] = "USD"
    unit: Literal["MICRO_USD_PER_MILLION_TOKENS"] = (
        "MICRO_USD_PER_MILLION_TOKENS"
    )
    input_microusd_per_million_tokens: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    output_microusd_per_million_tokens: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    fixed_non_token_microusd: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    authority_reference: Optional[str] = None
    source_name: Optional[str] = None
    source_version: Optional[str] = None
    effective_version: Optional[str] = None
    provenance_sha256: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    calculation_rule: Literal[
        OPENROUTER_COST_CALCULATION_RULE
    ] = OPENROUTER_COST_CALCULATION_RULE
    unknown_line_items: Tuple[str, ...] = _UNKNOWN_PRICING_ITEMS
    live_authorization_allowed: Literal[False] = False

    @field_validator(
        "authority_reference", "source_name", "source_version", "effective_version"
    )
    @classmethod
    def optional_authority_nonblank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            _nonblank(value)
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterPricingRecord":
        unknown = _canonical_strings(self.unknown_line_items, "unknown_line_items")
        object.__setattr__(self, "unknown_line_items", unknown)
        prices = (
            self.input_microusd_per_million_tokens,
            self.output_microusd_per_million_tokens,
            self.fixed_non_token_microusd,
        )
        provenance = (
            self.source_name,
            self.source_version,
            self.effective_version,
            self.provenance_sha256,
        )
        if self.pricing_state is OpenRouterEvidenceState.NOT_ESTABLISHED:
            if (
                any(value is not None for value in prices)
                or self.authority_reference is not None
                or any(value is not None for value in provenance)
            ):
                raise ContractValidationError(
                    "NOT_ESTABLISHED pricing cannot contain prices or provenance"
                )
            if unknown != _UNKNOWN_PRICING_ITEMS:
                raise ContractValidationError(
                    "NOT_ESTABLISHED pricing must retain every frozen unknown line item"
                )
        else:
            if any(value is None for value in prices):
                raise ContractValidationError("SYNTHETIC_ONLY pricing requires all prices")
            if self.authority_reference != "synthetic-test-only":
                raise ContractValidationError(
                    "synthetic pricing authority must be synthetic-test-only"
                )
            if self.source_name != "synthetic-test-only":
                raise ContractValidationError(
                    "synthetic pricing source must be synthetic-test-only"
                )
            if self.source_version != "synthetic-pricing/v0":
                raise ContractValidationError(
                    "synthetic pricing source version must be frozen"
                )
            if self.effective_version != "synthetic-effective/v0":
                raise ContractValidationError(
                    "synthetic pricing effective version must be frozen"
                )
            expected_provenance = hashlib.sha256(
                b"socrateszero-openrouter-synthetic-pricing/v0"
            ).hexdigest()
            if self.provenance_sha256 != expected_provenance:
                raise ContractValidationError(
                    "synthetic pricing provenance digest must be frozen"
                )
            if unknown:
                raise ContractValidationError(
                    "complete synthetic arithmetic cannot retain unknown line items"
                )
        _freeze_id(
            self,
            field_name="pricing_record_id",
            prefix="szorprice",
            payload=self.model_dump(mode="json", exclude={"pricing_record_id"}),
        )
        return self


class OpenRouterCostBound(_FrozenOpenRouterContract):
    schema_version: Literal[COST_BOUND_SCHEMA_VERSION] = COST_BOUND_SCHEMA_VERSION
    cost_bound_id: Optional[str] = None
    token_policy: OpenRouterTokenPolicy
    pricing_record: OpenRouterPricingRecord
    cost_state: Optional[
        Literal[
            OpenRouterEvidenceState.NOT_ESTABLISHED,
            OpenRouterEvidenceState.SYNTHETIC_ONLY,
        ]
    ] = None
    maximum_input_cost_microusd: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    maximum_output_cost_microusd: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    maximum_fixed_cost_microusd: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    maximum_total_cost_microusd: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    unknown_line_items: Tuple[str, ...] = _UNKNOWN_PRICING_ITEMS
    live_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def calculate_and_identify(self) -> "OpenRouterCostBound":
        state = self.cost_state or self.pricing_record.pricing_state
        if state is not self.pricing_record.pricing_state:
            raise ContractValidationError("cost state must equal pricing state")
        object.__setattr__(self, "cost_state", state)
        unknown = _canonical_strings(self.unknown_line_items, "unknown_line_items")
        object.__setattr__(self, "unknown_line_items", unknown)
        cost_fields = (
            self.maximum_input_cost_microusd,
            self.maximum_output_cost_microusd,
            self.maximum_fixed_cost_microusd,
            self.maximum_total_cost_microusd,
        )
        if state is OpenRouterEvidenceState.NOT_ESTABLISHED:
            if any(value is not None for value in cost_fields):
                raise ContractValidationError(
                    "NOT_ESTABLISHED cost cannot contain numeric maximums"
                )
            if unknown != self.pricing_record.unknown_line_items:
                raise ContractValidationError("cost unknown line items must match pricing")
        else:
            if unknown:
                raise ContractValidationError("synthetic cost cannot retain unknown items")
            input_rate = self.pricing_record.input_microusd_per_million_tokens
            output_rate = self.pricing_record.output_microusd_per_million_tokens
            fixed = self.pricing_record.fixed_non_token_microusd
            if input_rate is None or output_rate is None or fixed is None:
                raise ContractValidationError("synthetic pricing is incomplete")
            input_cost = _ceil_microusd(
                self.token_policy.payload_input_token_upper_bound, input_rate
            )
            output_cost = _ceil_microusd(
                self.token_policy.max_output_tokens, output_rate
            )
            total = _checked_add(
                _checked_add(input_cost, output_cost, "token cost subtotal"),
                fixed,
                "maximum total cost",
            )
            supplied = cost_fields
            expected = (input_cost, output_cost, fixed, total)
            if any(value is not None for value in supplied) and supplied != expected:
                raise ContractValidationError("synthetic maximum cost does not match")
            object.__setattr__(self, "maximum_input_cost_microusd", input_cost)
            object.__setattr__(self, "maximum_output_cost_microusd", output_cost)
            object.__setattr__(self, "maximum_fixed_cost_microusd", fixed)
            object.__setattr__(self, "maximum_total_cost_microusd", total)
        _freeze_id(
            self,
            field_name="cost_bound_id",
            prefix="szorcost",
            payload=self.model_dump(mode="json", exclude={"cost_bound_id"}),
        )
        return self


class OpenRouterCapabilitySnapshot(_FrozenOpenRouterContract):
    schema_version: Literal[
        CAPABILITY_SNAPSHOT_SCHEMA_VERSION
    ] = CAPABILITY_SNAPSHOT_SCHEMA_VERSION
    capability_snapshot_id: Optional[str] = None
    adapter_id: Literal[
        OPENROUTER_ACQUISITION_ADAPTER_ID
    ] = OPENROUTER_ACQUISITION_ADAPTER_ID
    provider_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    prepared_body_id: str
    endpoint_policy: OpenRouterEndpointPolicy
    transport_policy: OpenRouterTransportPolicy
    route_policy: OpenRouterRoutePolicy
    control_policy: OpenRouterControlPolicy
    token_policy: OpenRouterTokenPolicy
    pricing_record: OpenRouterPricingRecord
    cost_bound: OpenRouterCostBound
    offline_canned_contract_state: Literal[
        OpenRouterEvidenceState.SYNTHETIC_ONLY
    ] = OpenRouterEvidenceState.SYNTHETIC_ONLY
    upstream_route_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    provider_fallback_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    provider_input_bound_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    output_cap_wire_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    seed_state: Literal[
        OpenRouterEvidenceState.PROVEN_UNSUPPORTED
    ] = OpenRouterEvidenceState.PROVEN_UNSUPPORTED
    sdk_internal_retry_state: Literal[
        OpenRouterEvidenceState.NOT_APPLICABLE
    ] = OpenRouterEvidenceState.NOT_APPLICABLE
    endpoint_enforcement_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    live_authorization_allowed: Literal[False] = False
    network_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    tool_calls: Literal[0] = 0
    ced_applications: Literal[0] = 0

    _prepared_body_nonblank = field_validator("prepared_body_id")(_nonblank)

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "OpenRouterCapabilitySnapshot":
        if self.prepared_body_id != self.token_policy.prepared_body_id:
            raise ContractValidationError("capability prepared body link does not match")
        if self.route_policy.requested_model_id != self.model_id:
            raise ContractValidationError("capability route model does not match")
        if self.route_policy.router_id != self.provider_id:
            raise ContractValidationError("capability router does not match")
        if self.token_policy.max_output_tokens != self.control_policy.max_output_tokens:
            raise ContractValidationError("capability output-token controls do not match")
        if self.cost_bound.token_policy != self.token_policy:
            raise ContractValidationError("capability cost/token policy link does not match")
        if self.cost_bound.pricing_record != self.pricing_record:
            raise ContractValidationError("capability cost/pricing link does not match")
        if self.upstream_route_state is not self.route_policy.upstream_route_state:
            raise ContractValidationError("capability route state does not match")
        if (
            self.provider_fallback_state
            is not self.route_policy.provider_side_fallback_state
        ):
            raise ContractValidationError("capability fallback state does not match")
        if (
            self.provider_input_bound_state
            is not self.token_policy.provider_input_token_bound_state
        ):
            raise ContractValidationError("capability input-bound state does not match")
        if self.output_cap_wire_state is not self.control_policy.output_cap_wire_state:
            raise ContractValidationError("capability output-cap state does not match")
        if self.seed_state is not self.control_policy.seed_state:
            raise ContractValidationError("capability seed state does not match")
        if self.sdk_internal_retry_state is not self.control_policy.sdk_internal_retry_state:
            raise ContractValidationError("capability SDK-retry state does not match")
        if (
            self.endpoint_enforcement_state
            is not self.endpoint_policy.live_enforcement_state
        ):
            raise ContractValidationError("capability endpoint state does not match")
        _freeze_id(
            self,
            field_name="capability_snapshot_id",
            prefix="szorcap",
            payload=self.model_dump(mode="json", exclude={"capability_snapshot_id"}),
        )
        return self


class OpenRouterRawResponseEvidence(_FrozenOpenRouterContract):
    schema_version: Literal[
        RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION
    ] = RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION
    raw_response_evidence_id: Optional[str] = None
    evidence_state: OpenRouterEvidenceState
    transport_status: OpenRouterTransportStatus
    raw_response_base64: Optional[str] = None
    reported_sha256: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    reported_byte_length: Optional[int] = Field(default=None, ge=0, strict=True)
    maximum_byte_length: Literal[
        OPENROUTER_REFERENCE_RAW_RESPONSE_MAX_BYTES
    ] = OPENROUTER_REFERENCE_RAW_RESPONSE_MAX_BYTES
    truncated: Literal[False] = False
    transport_error_code: Optional[str] = None
    privacy_classification: Literal[
        OpenRouterPrivacyClassification.SYNTHETIC_CANNED_OBSERVATION
    ] = OpenRouterPrivacyClassification.SYNTHETIC_CANNED_OBSERVATION
    retention_state: Optional[OpenRouterRawRetentionState] = None
    credential_material_retained: Literal[False] = False
    sensitive_headers_retained: Literal[False] = False
    assistant_content_treatment: Literal[
        "OPAQUE_NO_SEMANTIC_EVALUATION"
    ] = "OPAQUE_NO_SEMANTIC_EVALUATION"

    @field_validator("transport_error_code")
    @classmethod
    def optional_error_nonblank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            _nonblank(value)
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRawResponseEvidence":
        raw: Optional[bytes]
        if self.raw_response_base64 is None:
            raw = None
        else:
            raw = _canonical_base64(self.raw_response_base64)
        if self.transport_status is OpenRouterTransportStatus.DELIVERED:
            if self.evidence_state is not OpenRouterEvidenceState.SYNTHETIC_ONLY:
                raise ContractValidationError("delivered canned raw evidence is synthetic only")
            if raw is None or not raw:
                raise ContractValidationError("delivered response requires nonempty raw bytes")
            if self.transport_error_code is not None:
                raise ContractValidationError("delivered response cannot contain transport error")
        else:
            if raw is not None:
                raise ContractValidationError("failed transport cannot retain raw response bytes")
            if self.transport_error_code is None:
                raise ContractValidationError("failed transport requires a typed error code")
        digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
        length = len(raw) if raw is not None else None
        if length is not None and length > self.maximum_byte_length:
            raise ContractValidationError("raw response exceeds canned byte bound")
        if self.reported_sha256 is not None and self.reported_sha256 != digest:
            raise ContractValidationError("raw response SHA-256 does not match")
        if (
            self.reported_byte_length is not None
            and self.reported_byte_length != length
        ):
            raise ContractValidationError("raw response byte length does not match")
        if raw is None and (
            self.reported_sha256 is not None or self.reported_byte_length is not None
        ):
            raise ContractValidationError("absent raw response cannot report digest or length")
        retention_state = (
            OpenRouterRawRetentionState.INLINE_RAW_BYTES_RETAINED
            if raw is not None
            else OpenRouterRawRetentionState.NO_RAW_BYTES_CAPTURED
        )
        if self.retention_state is not None and self.retention_state is not retention_state:
            raise ContractValidationError("raw retention state does not match captured bytes")
        object.__setattr__(self, "reported_sha256", digest)
        object.__setattr__(self, "reported_byte_length", length)
        object.__setattr__(self, "retention_state", retention_state)
        _freeze_id(
            self,
            field_name="raw_response_evidence_id",
            prefix="szorraw",
            payload={
                **self.model_dump(
                    mode="json",
                    exclude={"raw_response_evidence_id", "raw_response_base64"},
                ),
                "reported_sha256": digest,
                "reported_byte_length": length,
            },
        )
        return self

    @property
    def raw_bytes(self) -> Optional[bytes]:
        if self.raw_response_base64 is None:
            return None
        return _canonical_base64(self.raw_response_base64)


class OpenRouterIdentityEvidence(_FrozenOpenRouterContract):
    schema_version: Literal[
        IDENTITY_EVIDENCE_SCHEMA_VERSION
    ] = IDENTITY_EVIDENCE_SCHEMA_VERSION
    identity_evidence_id: Optional[str] = None
    evidence_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED,
        OpenRouterEvidenceState.SYNTHETIC_ONLY,
    ]
    requested_router_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    requested_model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    requested_configuration_digest: str = Field(pattern=_HEX64_PATTERN)
    canonicalization_rule_id: Literal[
        OPENROUTER_IDENTITY_CANONICALIZATION_RULE_ID
    ] = OPENROUTER_IDENTITY_CANONICALIZATION_RULE_ID
    actual_router_id: Optional[str] = None
    actual_model_id: Optional[str] = None
    actual_configuration_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    router_identity_match: bool = Field(strict=True)
    model_identity_match: bool = Field(strict=True)
    configuration_identity_match: bool = Field(strict=True)
    identity_match: bool = Field(strict=True)
    exact_router_model_configuration_verified: bool = Field(strict=True)
    source_raw_response_sha256: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    source_fields: Tuple[str, ...] = ()
    fallback_used: Optional[bool] = Field(default=None, strict=True)
    upstream_provider_id: Literal[None] = None
    upstream_route_id: Literal[None] = None
    upstream_route_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED

    _optional_actual_nonblank = field_validator(
        "actual_router_id", "actual_model_id"
    )(lambda value: _nonblank(value) if value is not None else value)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterIdentityEvidence":
        source_fields = _canonical_strings(self.source_fields, "source_fields")
        object.__setattr__(self, "source_fields", source_fields)
        actual = (
            self.actual_router_id,
            self.actual_model_id,
            self.actual_configuration_digest,
        )
        if self.evidence_state is OpenRouterEvidenceState.NOT_ESTABLISHED:
            if any(value is not None for value in actual):
                raise ContractValidationError(
                    "NOT_ESTABLISHED identity cannot contain actual identity"
                )
            if any(
                (
                    self.router_identity_match,
                    self.model_identity_match,
                    self.configuration_identity_match,
                    self.identity_match,
                    self.exact_router_model_configuration_verified,
                )
            ):
                raise ContractValidationError("unknown identity cannot be verified")
            if (
                self.source_raw_response_sha256 is not None
                or source_fields
                or self.fallback_used is not None
            ):
                raise ContractValidationError(
                    "NOT_ESTABLISHED identity cannot claim raw-source metadata"
                )
        else:
            expected = (
                self.requested_router_id,
                self.requested_model_id,
                self.requested_configuration_digest,
            )
            exact_matches = tuple(
                actual_value == expected_value
                for actual_value, expected_value in zip(actual, expected)
            )
            if actual != expected:
                raise ContractValidationError(
                    "synthetic actual identity must exactly match requested identity"
                )
            if (
                self.router_identity_match,
                self.model_identity_match,
                self.configuration_identity_match,
            ) != exact_matches:
                raise ContractValidationError(
                    "identity match booleans must equal exact codepoint comparisons"
                )
            if self.identity_match is not all(exact_matches):
                raise ContractValidationError("identity_match must combine exact matches")
            if self.exact_router_model_configuration_verified is not self.identity_match:
                raise ContractValidationError("matching synthetic identity must be verified")
            if self.source_raw_response_sha256 is None:
                raise ContractValidationError(
                    "synthetic identity requires source raw-response digest"
                )
            if source_fields != OPENROUTER_IDENTITY_SOURCE_FIELDS:
                raise ContractValidationError(
                    "synthetic identity requires every frozen raw source field"
                )
            if self.fallback_used is None:
                raise ContractValidationError(
                    "synthetic identity requires a typed fallback result"
                )
        _freeze_id(
            self,
            field_name="identity_evidence_id",
            prefix="szoridentity",
            payload=self.model_dump(mode="json", exclude={"identity_evidence_id"}),
        )
        return self


class OpenRouterUsageEvidence(_FrozenOpenRouterContract):
    schema_version: Literal[
        USAGE_EVIDENCE_SCHEMA_VERSION
    ] = USAGE_EVIDENCE_SCHEMA_VERSION
    usage_evidence_id: Optional[str] = None
    evidence_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED,
        OpenRouterEvidenceState.SYNTHETIC_ONLY,
    ]
    token_completeness: OpenRouterUsageCompleteness
    token_policy: OpenRouterTokenPolicy
    usage_source: OpenRouterUsageSource = OpenRouterUsageSource.UNKNOWN
    source_raw_response_sha256: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    raw_source_fields: Tuple[str, ...] = ()
    locally_derived_fields: Tuple[str, ...] = ()
    derivation_rule_id: Optional[str] = None
    input_tokens: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    output_tokens: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    total_tokens: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    cost_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED,
        OpenRouterEvidenceState.SYNTHETIC_ONLY,
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    cost_bound_id: Optional[str] = None
    cost_microusd: Optional[int] = Field(
        default=None, ge=0, le=MAX_SIGNED_64, strict=True
    )
    live_authorization_allowed: Literal[False] = False

    @field_validator("cost_bound_id", "derivation_rule_id")
    @classmethod
    def optional_cost_bound_nonblank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            _nonblank(value)
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterUsageEvidence":
        source_fields = _canonical_strings(
            self.raw_source_fields, "raw_source_fields"
        )
        derived_fields = _canonical_strings(
            self.locally_derived_fields, "locally_derived_fields"
        )
        object.__setattr__(self, "raw_source_fields", source_fields)
        object.__setattr__(self, "locally_derived_fields", derived_fields)
        token_values = (self.input_tokens, self.output_tokens, self.total_tokens)
        if self.evidence_state is OpenRouterEvidenceState.NOT_ESTABLISHED:
            if self.token_completeness is not OpenRouterUsageCompleteness.UNKNOWN:
                raise ContractValidationError("unknown usage must use UNKNOWN completeness")
            if any(value is not None for value in token_values):
                raise ContractValidationError("unknown usage cannot contain token counts")
            if self.usage_source is not OpenRouterUsageSource.UNKNOWN:
                raise ContractValidationError("unknown usage must retain UNKNOWN source")
            if (
                self.source_raw_response_sha256 is not None
                or source_fields
                or derived_fields
                or self.derivation_rule_id is not None
            ):
                raise ContractValidationError(
                    "unknown usage cannot claim raw or derived source fields"
                )
        else:
            if self.token_completeness is not OpenRouterUsageCompleteness.COMPLETE:
                raise ContractValidationError("synthetic usage must be complete")
            if any(value is None for value in token_values):
                raise ContractValidationError("complete usage requires every token count")
            input_tokens, output_tokens, total_tokens = token_values
            assert input_tokens is not None
            assert output_tokens is not None
            assert total_tokens is not None
            if total_tokens != input_tokens + output_tokens:
                raise ContractValidationError("total tokens must equal input plus output")
            if input_tokens > self.token_policy.payload_input_token_upper_bound:
                raise ContractValidationError("synthetic input usage exceeds payload bound")
            if output_tokens > self.token_policy.max_output_tokens:
                raise ContractValidationError("synthetic output usage exceeds output cap")
            if self.source_raw_response_sha256 is None:
                raise ContractValidationError(
                    "synthetic usage requires source raw-response digest"
                )
            if self.usage_source is OpenRouterUsageSource.PROVIDER_REPORTED:
                if source_fields != OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS:
                    raise ContractValidationError(
                        "provider-reported usage requires every frozen raw source field"
                    )
                if derived_fields or self.derivation_rule_id is not None:
                    raise ContractValidationError(
                        "provider-reported usage cannot claim local derivation"
                    )
            elif self.usage_source is OpenRouterUsageSource.LOCALLY_DERIVED:
                if source_fields != OPENROUTER_LOCALLY_DERIVED_USAGE_SOURCE_FIELDS:
                    raise ContractValidationError(
                        "locally derived usage requires input/output raw source fields"
                    )
                if derived_fields != OPENROUTER_LOCALLY_DERIVED_USAGE_FIELDS:
                    raise ContractValidationError(
                        "locally derived usage must identify total_tokens"
                    )
                if (
                    self.derivation_rule_id
                    != OPENROUTER_USAGE_TOTAL_DERIVATION_RULE_ID
                ):
                    raise ContractValidationError(
                        "locally derived usage requires the frozen derivation rule"
                    )
            else:
                raise ContractValidationError(
                    "synthetic usage source must be provider-reported or locally derived"
                )
        if self.cost_state is OpenRouterEvidenceState.NOT_ESTABLISHED:
            if self.cost_bound_id is not None or self.cost_microusd is not None:
                raise ContractValidationError("unknown cost cannot contain ID or numeric zero")
        else:
            if self.evidence_state is not OpenRouterEvidenceState.SYNTHETIC_ONLY:
                raise ContractValidationError("synthetic cost requires synthetic token usage")
            if self.cost_bound_id is None or self.cost_microusd is None:
                raise ContractValidationError("synthetic cost requires bound ID and value")
        _freeze_id(
            self,
            field_name="usage_evidence_id",
            prefix="szorusage",
            payload=self.model_dump(mode="json", exclude={"usage_evidence_id"}),
        )
        return self


class OpenRouterCannedResponseEnvelope(_FrozenOpenRouterContract):
    """One immutable canned transport outcome; never evidence of a live call."""

    schema_version: Literal[
        CANNED_RESPONSE_ENVELOPE_SCHEMA_VERSION
    ] = CANNED_RESPONSE_ENVELOPE_SCHEMA_VERSION
    canned_response_envelope_id: Optional[str] = None
    evidence_state: Literal[
        OpenRouterEvidenceState.SYNTHETIC_ONLY
    ] = OpenRouterEvidenceState.SYNTHETIC_ONLY
    transport_attempt_id: str
    prepared_body_id: str
    transport_status: OpenRouterTransportStatus
    canned_transport_invocations: Literal[1] = 1
    raw_response: Optional[OpenRouterRawResponseEvidence] = None
    identity_evidence: Optional[OpenRouterIdentityEvidence] = None
    usage_evidence: Optional[OpenRouterUsageEvidence] = None
    actual_router_id: Optional[str] = None
    actual_model_id: Optional[str] = None
    actual_configuration_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    finish_reason: Optional[OpenRouterFinishReason] = None
    fallback_used: Literal[False] = False
    explicit_retry_count: Literal[0] = 0
    adapter_retry_count: Literal[0] = 0
    sdk_internal_retry_state: Literal[
        OpenRouterEvidenceState.NOT_APPLICABLE
    ] = OpenRouterEvidenceState.NOT_APPLICABLE
    sdk_internal_retry_count: Literal[None] = None
    hidden_transport_retry_count: Literal[0] = 0
    stream_used: Literal[False] = False
    tool_calls: Literal[0] = 0
    timeout_fired: bool = Field(strict=True)
    cancellation_requested: bool = Field(strict=True)
    worker_terminated: Literal[True] = True
    transport_error_code: Optional[str] = None
    live_authorization_allowed: Literal[False] = False

    _nonblank_links = field_validator("transport_attempt_id", "prepared_body_id")(
        _nonblank
    )
    _optional_actual_nonblank = field_validator(
        "actual_router_id", "actual_model_id"
    )(lambda value: _nonblank(value) if value is not None else value)

    @field_validator("transport_error_code")
    @classmethod
    def optional_typed_error(cls, value: Optional[str]) -> Optional[str]:
        return _typed_code(value) if value is not None else value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterCannedResponseEnvelope":
        _assert_no_secret_material(self.transport_attempt_id, "transport_attempt_id")
        if self.transport_status is OpenRouterTransportStatus.DELIVERED:
            if self.timeout_fired or self.cancellation_requested:
                raise ContractValidationError(
                    "delivered envelope cannot report timeout or cancellation"
                )
            if self.transport_error_code is not None:
                raise ContractValidationError(
                    "delivered envelope cannot contain transport error"
                )
            if (
                self.raw_response is None
                or self.identity_evidence is None
                or self.usage_evidence is None
            ):
                raise ContractValidationError(
                    "delivered envelope requires raw, identity and usage evidence"
                )
            if self.raw_response.transport_status is not OpenRouterTransportStatus.DELIVERED:
                raise ContractValidationError("envelope/raw transport status does not match")
            identity = self.identity_evidence
            if identity.evidence_state is not OpenRouterEvidenceState.SYNTHETIC_ONLY:
                raise ContractValidationError("delivered identity must be synthetic-only")
            if not identity.exact_router_model_configuration_verified:
                raise ContractValidationError("delivered identity must be exactly verified")
            if (
                identity.source_raw_response_sha256
                != self.raw_response.reported_sha256
            ):
                raise ContractValidationError(
                    "identity source digest does not match raw response"
                )
            actual = (
                identity.actual_router_id,
                identity.actual_model_id,
                identity.actual_configuration_digest,
            )
            supplied = (
                self.actual_router_id,
                self.actual_model_id,
                self.actual_configuration_digest,
            )
            if any(value is not None for value in supplied) and supplied != actual:
                raise ContractValidationError("envelope actual identity does not match")
            object.__setattr__(self, "actual_router_id", actual[0])
            object.__setattr__(self, "actual_model_id", actual[1])
            object.__setattr__(self, "actual_configuration_digest", actual[2])
            if self.usage_evidence.evidence_state is not OpenRouterEvidenceState.SYNTHETIC_ONLY:
                raise ContractValidationError("delivered usage must be synthetic-only")
            if (
                self.usage_evidence.source_raw_response_sha256
                != self.raw_response.reported_sha256
            ):
                raise ContractValidationError(
                    "usage source digest does not match raw response"
                )
            raw_bytes = self.raw_response.raw_bytes
            if raw_bytes is None:
                raise ContractValidationError("delivered envelope requires raw bytes")
            try:
                raw_text = raw_bytes.decode("utf-8")
                parsed = json.loads(raw_text)
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
                raise ContractValidationError(
                    "canned OpenRouter response must be canonical UTF-8 JSON"
                ) from exc
            if not isinstance(parsed, dict) or canonical_json(parsed) != raw_text:
                raise ContractValidationError(
                    "canned OpenRouter response must be canonical UTF-8 JSON"
                )
            if set(parsed) != _CANNED_RESPONSE_KEYS:
                raise ContractValidationError(
                    "canned OpenRouter response fields do not match frozen shape"
                )
            response_id = parsed.get("id")
            if not isinstance(response_id, str) or not response_id.strip():
                raise ContractValidationError("canned response id must be nonblank")
            raw_identity = (
                parsed.get("provider"),
                parsed.get("model"),
                parsed.get("configuration_digest"),
            )
            if raw_identity != actual:
                raise ContractValidationError(
                    "raw response identity does not match identity evidence"
                )
            raw_controls = {
                "fallback_used": self.fallback_used,
                "explicit_retry_count": self.explicit_retry_count,
                "adapter_retry_count": self.adapter_retry_count,
                "sdk_internal_retry_count": self.sdk_internal_retry_count,
                "hidden_transport_retry_count": self.hidden_transport_retry_count,
                "stream_used": self.stream_used,
                "tool_calls": self.tool_calls,
            }
            for field_name, expected_value in raw_controls.items():
                raw_value = parsed.get(field_name)
                if type(raw_value) is not type(expected_value) or raw_value != expected_value:
                    raise ContractValidationError(
                        f"raw response {field_name} does not match envelope evidence"
                    )
            choices = parsed.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ContractValidationError("canned response requires one completion choice")
            choice = choices[0]
            if not isinstance(choice, dict) or set(choice) != {"finish_reason", "message"}:
                raise ContractValidationError("canned completion choice shape is invalid")
            try:
                raw_finish_reason = OpenRouterFinishReason(choice.get("finish_reason"))
            except (TypeError, ValueError) as exc:
                raise ContractValidationError(
                    "canned finish reason must be a supported typed value"
                ) from exc
            if (
                self.finish_reason is not None
                and self.finish_reason is not raw_finish_reason
            ):
                raise ContractValidationError(
                    "finish reason does not match raw response"
                )
            object.__setattr__(self, "finish_reason", raw_finish_reason)
            if raw_finish_reason is not OpenRouterFinishReason.STOP:
                raise ContractValidationError("canned finish reason must be stop")
            message = choice.get("message")
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ContractValidationError("canned assistant message shape is invalid")
            if message.get("role") != "assistant" or not isinstance(
                message.get("content"), str
            ):
                raise ContractValidationError("canned assistant message is invalid")
            raw_usage = parsed.get("usage")
            if not isinstance(raw_usage, dict) or set(raw_usage) != {
                "input_tokens",
                "output_tokens",
                "total_tokens",
            }:
                raise ContractValidationError("raw response usage shape is invalid")
            expected_usage = {
                "input_tokens": self.usage_evidence.input_tokens,
                "output_tokens": self.usage_evidence.output_tokens,
                "total_tokens": self.usage_evidence.total_tokens,
            }
            if any(type(value) is not int for value in raw_usage.values()):
                raise ContractValidationError("raw response usage must use exact integers")
            if raw_usage != expected_usage:
                raise ContractValidationError(
                    "raw response usage does not match usage evidence"
                )
            if identity.fallback_used is not parsed.get("fallback_used"):
                raise ContractValidationError(
                    "identity fallback result does not match raw response"
                )
            if (
                self.usage_evidence.usage_source
                is not OpenRouterUsageSource.PROVIDER_REPORTED
            ):
                raise ContractValidationError(
                    "complete canned usage must be classified provider-reported"
                )
        else:
            if self.raw_response is not None or self.identity_evidence is not None or self.usage_evidence is not None:
                raise ContractValidationError(
                    "failed envelope cannot fabricate raw, identity or usage evidence"
                )
            if any(
                value is not None
                for value in (
                    self.actual_router_id,
                    self.actual_model_id,
                    self.actual_configuration_digest,
                )
            ):
                raise ContractValidationError(
                    "failed envelope cannot fabricate actual identity"
                )
            if self.finish_reason is not None:
                raise ContractValidationError(
                    "failed transport envelope cannot fabricate finish reason"
                )
            if self.transport_error_code is None:
                raise ContractValidationError("failed envelope requires typed error code")
            if self.transport_status is OpenRouterTransportStatus.TIMEOUT:
                if not self.timeout_fired or not self.cancellation_requested:
                    raise ContractValidationError(
                        "timeout envelope requires timeout and cancellation evidence"
                    )
            elif self.timeout_fired or self.cancellation_requested:
                raise ContractValidationError(
                    "non-timeout error cannot report timeout or cancellation"
                )
        _freeze_id(
            self,
            field_name="canned_response_envelope_id",
            prefix="szorenvelope",
            payload=self.model_dump(
                mode="json", exclude={"canned_response_envelope_id"}
            ),
        )
        return self


_RESPONSE_VALIDATION_RANK = {
    OpenRouterResponseValidationState.NO_TRANSPORT_BYTES: 0,
    OpenRouterResponseValidationState.TRANSPORT_BYTES_CAPTURED: 1,
    OpenRouterResponseValidationState.IDENTITY_DERIVED: 2,
    OpenRouterResponseValidationState.USAGE_DERIVED: 3,
    OpenRouterResponseValidationState.ADAPTER_RESPONSE_VALIDATED: 4,
}
_FAILURE_MAX_VALIDATION_STATE = {
    "CANNED_TRANSPORT_ERROR": OpenRouterResponseValidationState.NO_TRANSPORT_BYTES,
    "TRANSPORT_TIMEOUT": OpenRouterResponseValidationState.NO_TRANSPORT_BYTES,
    "MISSING_RAW_RESPONSE": OpenRouterResponseValidationState.NO_TRANSPORT_BYTES,
    "RAW_DIGEST_OR_LENGTH_MISMATCH": OpenRouterResponseValidationState.TRANSPORT_BYTES_CAPTURED,
    "MALFORMED_RESPONSE_ENVELOPE": OpenRouterResponseValidationState.TRANSPORT_BYTES_CAPTURED,
    "ACTUAL_PROVIDER_MISMATCH": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "ACTUAL_MODEL_MISSING": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "ACTUAL_MODEL_MISMATCH": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "ACTUAL_CONFIGURATION_MISMATCH": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "FALLBACK_ACTIVATED": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "RETRY_ACTIVATED": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "STREAMING_RESPONSE_DETECTED": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "TOOL_ACTIVATED": OpenRouterResponseValidationState.IDENTITY_DERIVED,
    "USAGE_INCOMPLETE": OpenRouterResponseValidationState.USAGE_DERIVED,
    "USAGE_INCONSISTENT": OpenRouterResponseValidationState.USAGE_DERIVED,
    "REPORTED_USAGE_EXCEEDS_BOUND": OpenRouterResponseValidationState.USAGE_DERIVED,
    "CANNED_INVOCATION_COUNT_MISMATCH": OpenRouterResponseValidationState.USAGE_DERIVED,
    "WORKER_NOT_TERMINATED": OpenRouterResponseValidationState.USAGE_DERIVED,
    "LATE_MUTATION_DETECTED": OpenRouterResponseValidationState.USAGE_DERIVED,
    "RECEIPT_MISMATCH": OpenRouterResponseValidationState.USAGE_DERIVED,
}


def _canonical_raw_response_mapping(
    raw_response: OpenRouterRawResponseEvidence,
) -> Optional[dict[str, object]]:
    raw_bytes = raw_response.raw_bytes
    if raw_bytes is None:
        return None
    try:
        raw_text = raw_bytes.decode("utf-8")
        parsed = json.loads(raw_text)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict) or canonical_json(parsed) != raw_text:
        return None
    return parsed


def _raw_finish_reason(
    parsed: Optional[dict[str, object]],
) -> Optional[OpenRouterFinishReason]:
    if parsed is None:
        return None
    choices = parsed.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return None
    choice = choices[0]
    if not isinstance(choice, dict):
        return None
    try:
        return OpenRouterFinishReason(choice.get("finish_reason"))
    except (TypeError, ValueError):
        return None


class OpenRouterAttemptReceipt(_FrozenOpenRouterContract):
    schema_version: Literal[
        ATTEMPT_RECEIPT_SCHEMA_VERSION
    ] = ATTEMPT_RECEIPT_SCHEMA_VERSION
    attempt_receipt_id: Optional[str] = None
    outcome: OpenRouterAttemptOutcome
    attempt_ordinal: Literal[1] = 1
    semantic_request_id: str
    capability_snapshot: OpenRouterCapabilitySnapshot
    prepared_body: OpenRouterPreparedBody
    canned_response_envelope: Optional[OpenRouterCannedResponseEnvelope] = None
    raw_response: Optional[OpenRouterRawResponseEvidence] = None
    identity_evidence: Optional[OpenRouterIdentityEvidence] = None
    usage_evidence: Optional[OpenRouterUsageEvidence] = None
    finish_reason: Optional[OpenRouterFinishReason] = None
    response_validation_state: Optional[OpenRouterResponseValidationState] = None
    canned_transport_invocations: int = Field(ge=0, le=1, strict=True)
    application_fallback_used: Optional[bool] = Field(default=None, strict=True)
    provider_fallback_used: Literal[None] = None
    explicit_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    adapter_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    sdk_internal_retry_state: Literal[
        OpenRouterEvidenceState.NOT_APPLICABLE
    ] = OpenRouterEvidenceState.NOT_APPLICABLE
    sdk_internal_retry_count: Literal[None] = None
    hidden_transport_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    stream_used: Optional[bool] = Field(default=None, strict=True)
    tool_calls: Optional[int] = Field(default=None, ge=0, strict=True)
    failure_code: Optional[str] = None
    external_network_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    live_provider_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    ced_applications: Literal[0] = 0
    live_authorization_allowed: Literal[False] = False

    _semantic_request_nonblank = field_validator("semantic_request_id")(_nonblank)

    @field_validator("failure_code")
    @classmethod
    def optional_failure_nonblank(cls, value: Optional[str]) -> Optional[str]:
        return _typed_code(value) if value is not None else value

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "OpenRouterAttemptReceipt":
        capability = self.capability_snapshot
        body = self.prepared_body
        _assert_no_secret_material(self.semantic_request_id, "semantic_request_id")
        if capability.prepared_body_id != body.prepared_body_id:
            raise ContractValidationError("receipt prepared body link does not match")
        if body.endpoint_policy_id != capability.endpoint_policy.endpoint_policy_id:
            raise ContractValidationError("receipt endpoint policy link does not match")
        if body.route_policy_id != capability.route_policy.route_policy_id:
            raise ContractValidationError("receipt route policy link does not match")
        if body.control_policy_id != capability.control_policy.control_policy_id:
            raise ContractValidationError("receipt control policy link does not match")
        token_policy = capability.token_policy
        if (
            token_policy.prepared_body_sha256 != body.sha256
            or token_policy.prepared_body_byte_length != body.byte_length
            or token_policy.payload_input_token_upper_bound
            != body.payload_input_token_upper_bound
        ):
            raise ContractValidationError("receipt token/body evidence does not match")
        if self.outcome is OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED:
            if self.failure_code is not None:
                raise ContractValidationError("captured receipt cannot contain failure code")
            if self.canned_transport_invocations != 1:
                raise ContractValidationError("captured receipt requires exactly one invocation")
            if self.canned_response_envelope is None:
                raise ContractValidationError("captured receipt requires canned envelope")
            envelope = self.canned_response_envelope
            if envelope.prepared_body_id != body.prepared_body_id:
                raise ContractValidationError("receipt envelope/body link does not match")
            if envelope.transport_status is not OpenRouterTransportStatus.DELIVERED:
                raise ContractValidationError("captured envelope must be delivered")
            if self.raw_response is None or self.identity_evidence is None or self.usage_evidence is None:
                raise ContractValidationError("captured receipt requires raw, identity and usage")
            if (
                envelope.raw_response != self.raw_response
                or envelope.identity_evidence != self.identity_evidence
                or envelope.usage_evidence != self.usage_evidence
            ):
                raise ContractValidationError("receipt evidence must match canned envelope")
            if self.raw_response.transport_status is not OpenRouterTransportStatus.DELIVERED:
                raise ContractValidationError("captured receipt requires delivered raw response")
            if self.identity_evidence.evidence_state is not OpenRouterEvidenceState.SYNTHETIC_ONLY:
                raise ContractValidationError("captured identity must be synthetic-only evidence")
            if not self.identity_evidence.exact_router_model_configuration_verified:
                raise ContractValidationError("captured identity must be exactly verified")
            if (
                self.identity_evidence.requested_configuration_digest
                != capability.control_policy.control_policy_id.split("_", 1)[-1]
            ):
                raise ContractValidationError("captured configuration digest does not match")
            if self.usage_evidence.token_policy != token_policy:
                raise ContractValidationError("captured usage token policy does not match")
            if self.usage_evidence.evidence_state is not OpenRouterEvidenceState.SYNTHETIC_ONLY:
                raise ContractValidationError("captured usage must be synthetic-only evidence")
            if self.application_fallback_used is not False:
                raise ContractValidationError("captured receipt requires application fallback false")
            retry_counts = (
                self.explicit_retry_count,
                self.adapter_retry_count,
                self.hidden_transport_retry_count,
            )
            if retry_counts != (0, 0, 0):
                raise ContractValidationError(
                    "captured receipt requires explicit, adapter and hidden retry counts zero"
                )
            if self.sdk_internal_retry_state is not OpenRouterEvidenceState.NOT_APPLICABLE:
                raise ContractValidationError("direct HTTP adapter has no SDK retry layer")
            if self.stream_used is not False or self.tool_calls != 0:
                raise ContractValidationError("captured receipt requires no stream or tools")
            if (
                self.identity_evidence.source_raw_response_sha256
                != self.raw_response.reported_sha256
                or self.usage_evidence.source_raw_response_sha256
                != self.raw_response.reported_sha256
            ):
                raise ContractValidationError(
                    "captured derived evidence must link to raw response digest"
                )
            finish_reason = envelope.finish_reason
            if finish_reason is None:
                raise ContractValidationError("captured receipt requires finish reason")
            if self.finish_reason is not None and self.finish_reason is not finish_reason:
                raise ContractValidationError(
                    "receipt finish reason does not match canned envelope"
                )
            object.__setattr__(self, "finish_reason", finish_reason)
            validation_state = OpenRouterResponseValidationState.ADAPTER_RESPONSE_VALIDATED
        else:
            if self.failure_code is None:
                raise ContractValidationError("failed receipt requires a typed failure code")
            if self.canned_response_envelope is not None:
                envelope = self.canned_response_envelope
                if envelope.prepared_body_id != body.prepared_body_id:
                    raise ContractValidationError("failed envelope/body link does not match")
                if envelope.transport_status is OpenRouterTransportStatus.DELIVERED:
                    raise ContractValidationError("failed receipt cannot contain delivered envelope")
                if any(
                    evidence is not None
                    for evidence in (
                        self.raw_response,
                        self.identity_evidence,
                        self.usage_evidence,
                    )
                ):
                    raise ContractValidationError(
                        "failed transport envelope cannot carry derived response evidence"
                    )
            if self.raw_response is None:
                if self.identity_evidence is not None or self.usage_evidence is not None:
                    raise ContractValidationError(
                        "failed receipt cannot fabricate identity or usage without raw bytes"
                    )
                parsed = None
                validation_state = OpenRouterResponseValidationState.NO_TRANSPORT_BYTES
            else:
                if (
                    self.raw_response.transport_status
                    is not OpenRouterTransportStatus.DELIVERED
                    or self.raw_response.raw_bytes is None
                ):
                    raise ContractValidationError(
                        "captured failure raw evidence must retain delivered bytes"
                    )
                parsed = _canonical_raw_response_mapping(self.raw_response)
                validation_state = (
                    OpenRouterResponseValidationState.TRANSPORT_BYTES_CAPTURED
                )
            if self.identity_evidence is not None:
                if parsed is None:
                    raise ContractValidationError(
                        "failed identity evidence requires canonical captured raw bytes"
                    )
                identity = self.identity_evidence
                raw_fallback = parsed.get("fallback_used")
                if (
                    identity.evidence_state
                    is not OpenRouterEvidenceState.SYNTHETIC_ONLY
                    or not identity.exact_router_model_configuration_verified
                    or identity.requested_configuration_digest
                    != capability.control_policy.control_policy_id.split("_", 1)[-1]
                    or identity.source_raw_response_sha256
                    != self.raw_response.reported_sha256
                    or type(raw_fallback) is not bool
                    or identity.fallback_used is not raw_fallback
                    or (
                        identity.actual_router_id,
                        identity.actual_model_id,
                        identity.actual_configuration_digest,
                    )
                    != (
                        parsed.get("provider"),
                        parsed.get("model"),
                        parsed.get("configuration_digest"),
                    )
                ):
                    raise ContractValidationError(
                        "failed identity evidence is not derived from captured raw bytes"
                    )
                validation_state = OpenRouterResponseValidationState.IDENTITY_DERIVED
            if self.usage_evidence is not None:
                if self.identity_evidence is None or parsed is None:
                    raise ContractValidationError(
                        "failed usage evidence requires linked derived identity"
                    )
                usage = self.usage_evidence
                raw_usage = parsed.get("usage")
                if (
                    usage.evidence_state
                    is not OpenRouterEvidenceState.SYNTHETIC_ONLY
                    or usage.source_raw_response_sha256
                    != self.raw_response.reported_sha256
                    or usage.token_policy != token_policy
                    or not isinstance(raw_usage, dict)
                    or set(raw_usage)
                    != {"input_tokens", "output_tokens", "total_tokens"}
                    or any(type(value) is not int for value in raw_usage.values())
                    or (
                        usage.input_tokens,
                        usage.output_tokens,
                        usage.total_tokens,
                    )
                    != (
                        raw_usage.get("input_tokens"),
                        raw_usage.get("output_tokens"),
                        raw_usage.get("total_tokens"),
                    )
                ):
                    raise ContractValidationError(
                        "failed usage evidence is not derived from captured raw bytes"
                    )
                validation_state = OpenRouterResponseValidationState.USAGE_DERIVED
            maximum_state = _FAILURE_MAX_VALIDATION_STATE.get(
                self.failure_code,
                OpenRouterResponseValidationState.NO_TRANSPORT_BYTES,
            )
            if (
                _RESPONSE_VALIDATION_RANK[validation_state]
                > _RESPONSE_VALIDATION_RANK[maximum_state]
            ):
                raise ContractValidationError(
                    "failure code cannot claim evidence beyond its derivation stage"
                )
            finish_reason = _raw_finish_reason(parsed)
            if (
                self.finish_reason is not None
                and self.finish_reason is not finish_reason
            ):
                raise ContractValidationError(
                    "failed receipt finish reason is not derived from raw bytes"
                )
            object.__setattr__(self, "finish_reason", finish_reason)
        if (
            self.response_validation_state is not None
            and self.response_validation_state is not validation_state
        ):
            raise ContractValidationError(
                "response validation state does not match retained evidence"
            )
        object.__setattr__(self, "response_validation_state", validation_state)
        if self.usage_evidence is not None:
            if self.usage_evidence.cost_state is OpenRouterEvidenceState.SYNTHETIC_ONLY:
                pricing = capability.pricing_record
                input_rate = pricing.input_microusd_per_million_tokens
                output_rate = pricing.output_microusd_per_million_tokens
                fixed_cost = pricing.fixed_non_token_microusd
                input_tokens = self.usage_evidence.input_tokens
                output_tokens = self.usage_evidence.output_tokens
                if (
                    input_rate is None
                    or output_rate is None
                    or fixed_cost is None
                    or input_tokens is None
                    or output_tokens is None
                ):
                    raise ContractValidationError(
                        "usage synthetic cost requires complete pricing and usage"
                    )
                exact_usage_cost = _checked_add(
                    _checked_add(
                        _ceil_microusd(input_tokens, input_rate),
                        _ceil_microusd(output_tokens, output_rate),
                        "reported token cost subtotal",
                    ),
                    fixed_cost,
                    "reported total cost",
                )
                if (
                    self.usage_evidence.cost_bound_id
                    != capability.cost_bound.cost_bound_id
                    or capability.cost_bound.cost_state
                    is not OpenRouterEvidenceState.SYNTHETIC_ONLY
                    or self.usage_evidence.cost_microusd is None
                    or self.usage_evidence.cost_microusd != exact_usage_cost
                    or capability.cost_bound.maximum_total_cost_microusd is None
                    or self.usage_evidence.cost_microusd
                    > capability.cost_bound.maximum_total_cost_microusd
                ):
                    raise ContractValidationError(
                        "usage synthetic cost does not link to capability cost bound"
                    )
        _freeze_id(
            self,
            field_name="attempt_receipt_id",
            prefix="szorattempt",
            payload=self.model_dump(mode="json", exclude={"attempt_receipt_id"}),
        )
        return self


__all__ = [
    "ATTEMPT_RECEIPT_SCHEMA_VERSION",
    "CAPABILITY_SNAPSHOT_SCHEMA_VERSION",
    "CANNED_RESPONSE_ENVELOPE_SCHEMA_VERSION",
    "CONTROL_POLICY_SCHEMA_VERSION",
    "COST_BOUND_SCHEMA_VERSION",
    "ENDPOINT_POLICY_SCHEMA_VERSION",
    "HEADER_POLICY_SCHEMA_VERSION",
    "IDENTITY_EVIDENCE_SCHEMA_VERSION",
    "OPENROUTER_ACQUISITION_ADAPTER_ID",
    "OPENROUTER_CANNED_CANCELLATION_GRACE_MS",
    "OPENROUTER_CANNED_CLEANUP_ROUNDS",
    "OPENROUTER_CANNED_RAW_RESPONSE_MAX_BYTES",
    "OPENROUTER_COST_CALCULATION_RULE",
    "OPENROUTER_ENDPOINT_HOST",
    "OPENROUTER_ENDPOINT_PATH",
    "OPENROUTER_ENDPOINT_PORT",
    "OPENROUTER_ENDPOINT_SCHEME",
    "OPENROUTER_ENDPOINT_URL",
    "OPENROUTER_HTTP_DEPENDENCY_SPEC",
    "OPENROUTER_IDENTITY_SOURCE_FIELDS",
    "OPENROUTER_INPUT_BOUND_METHOD",
    "OPENROUTER_IDENTITY_CANONICALIZATION_RULE_ID",
    "OPENROUTER_MAX_OUTPUT_TOKENS",
    "OPENROUTER_MODEL_ID",
    "OPENROUTER_LOCALLY_DERIVED_USAGE_FIELDS",
    "OPENROUTER_LOCALLY_DERIVED_USAGE_SOURCE_FIELDS",
    "OPENROUTER_PROVIDER_ID",
    "OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS",
    "OPENROUTER_REFERENCE_RAW_RESPONSE_MAX_BYTES",
    "OPENROUTER_RESPONSE_FORMAT",
    "OPENROUTER_TIMEOUT_MS",
    "OPENROUTER_USAGE_TOTAL_DERIVATION_RULE_ID",
    "MAX_SIGNED_64",
    "PREPARED_BODY_SCHEMA_VERSION",
    "PRICING_RECORD_SCHEMA_VERSION",
    "RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION",
    "ROUTE_POLICY_SCHEMA_VERSION",
    "TOKEN_POLICY_SCHEMA_VERSION",
    "TRANSPORT_POLICY_SCHEMA_VERSION",
    "USAGE_EVIDENCE_SCHEMA_VERSION",
    "OpenRouterAttemptOutcome",
    "OpenRouterAttemptReceipt",
    "OpenRouterCapabilitySnapshot",
    "OpenRouterCannedResponseEnvelope",
    "OpenRouterControlPolicy",
    "OpenRouterCostBound",
    "OpenRouterEndpointPolicy",
    "OpenRouterEvidenceState",
    "OpenRouterFinishReason",
    "OpenRouterIdentityEvidence",
    "OpenRouterHeaderPolicy",
    "OpenRouterPreparedBody",
    "OpenRouterPrivacyClassification",
    "OpenRouterPricingRecord",
    "OpenRouterProxyMode",
    "OpenRouterRawResponseEvidence",
    "OpenRouterRawRetentionState",
    "OpenRouterResponseValidationState",
    "OpenRouterRoutePolicy",
    "OpenRouterTokenPolicy",
    "OpenRouterTransportMode",
    "OpenRouterTransportPolicy",
    "OpenRouterTransportStatus",
    "OpenRouterUsageCompleteness",
    "OpenRouterUsageEvidence",
    "OpenRouterUsageSource",
    "calculate_openrouter_cost_line_microusd",
]

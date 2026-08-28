"""Reduced $8 GPT-5 Mini Flex benchmark safety profile.

This module is additive benchmark wiring, not a new CED contract.  It freezes
the operator-approved route and P19 arithmetic, validates one fresh exact
endpoint listing without consulting the model-level capability union, and
provides a pre-dispatch body guard.  Importing it performs no network or
credential access.  The optional endpoint fetch helper performs one public GET
with no retry when explicitly called by the approved runner.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import ssl
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id
from .openrouter_live_session_v1 import (
    PICODOLLARS_PER_USD,
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterRenderedTurnV1,
    conservative_turn_cost_bound_v1,
)

REDUCED_MODEL_V1 = "openai/gpt-5-mini"
REDUCED_PROVIDER_SELECTOR_V1 = "openai/flex"
REDUCED_PROVIDER_DISPLAY_NAME_V1 = "OpenAI"
REDUCED_DATED_ENDPOINT_MODEL_V1 = "openai/gpt-5-mini-2025-08-07"
REDUCED_ENDPOINT_PATH_V1 = "/api/v1/models/openai/gpt-5-mini/endpoints"
REDUCED_PRIOR_ENDPOINT_LISTING_SHA256_V1 = (
    "cc7a04e4d33727be91bad54d2aba5c5e70993d1823f8ef4fd92c9b84b757108d"
)

REDUCED_MAX_INPUT_TOKENS_V1 = 400_000
REDUCED_MAX_OUTPUT_TOKENS_V1 = 1_024
REDUCED_MAX_CALLS_V1 = 151
REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1 = 8 * PICODOLLARS_PER_USD
REDUCED_PROMPT_CEILING_USD_PER_MILLION_V1 = "0.125"
REDUCED_COMPLETION_CEILING_USD_PER_MILLION_V1 = "1"
REDUCED_REQUEST_CEILING_USD_V1 = "0"
REDUCED_SEED_V1 = 0
REDUCED_AUTOMATIC_RETRIES_V1 = 0
REDUCED_REASONING_EFFORT_V1: None = None

REDUCED_PER_CALL_BOUND_PICODOLLARS_V1 = 51_024_000_000
REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1 = 7_704_624_000_000

WORKER_ALIASES_V1: Tuple[str, ...] = ("Alpha", "Beta", "Gamma", "Delta")
WORKER_PROVIDER_IDS_V1: Tuple[str, ...] = tuple(
    f"worker_{alias.lower()}" for alias in WORKER_ALIASES_V1
)

_REQUIRED_FLEX_PARAMETERS_V1 = frozenset(
    {"max_tokens", "response_format", "seed", "structured_outputs"}
)
_MAX_ENDPOINT_RESPONSE_BYTES_V1 = 1_048_576


class _FrozenReducedContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _decimal_text(value: object, label: str) -> Decimal:
    if type(value) is not str or not value or value.strip() != value:
        raise ContractValidationError(f"{label} must be an exact decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ContractValidationError(f"{label} is malformed") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ContractValidationError(f"{label} must be finite and nonnegative")
    return parsed


class OpenRouterFlexEndpointEvidenceV1(_FrozenReducedContractV1):
    """Validated facts for the one exact ``openai/flex`` endpoint record."""

    schema_version: Literal[
        "socrateszero-openrouter-flex-endpoint-evidence/v1"
    ] = "socrateszero-openrouter-flex-endpoint-evidence/v1"
    requested_model: Literal[REDUCED_MODEL_V1] = REDUCED_MODEL_V1
    provider_selector: Literal[
        REDUCED_PROVIDER_SELECTOR_V1
    ] = REDUCED_PROVIDER_SELECTOR_V1
    endpoint_model_id: Literal[REDUCED_MODEL_V1] = REDUCED_MODEL_V1
    dated_endpoint_model: Literal[
        REDUCED_DATED_ENDPOINT_MODEL_V1
    ] = REDUCED_DATED_ENDPOINT_MODEL_V1
    endpoint_name: str = Field(min_length=1)
    provider_display_name: Literal[
        REDUCED_PROVIDER_DISPLAY_NAME_V1
    ] = REDUCED_PROVIDER_DISPLAY_NAME_V1
    status: Literal[0] = 0
    context_length: int = Field(ge=REDUCED_MAX_INPUT_TOKENS_V1)
    max_prompt_tokens_observed: Optional[int] = Field(default=None, gt=0)
    maximum_output_tokens: int = Field(ge=REDUCED_MAX_OUTPUT_TOKENS_V1)
    output_limit_parameter: Literal["max_tokens"] = "max_tokens"
    supported_parameters: Tuple[str, ...]
    temperature_supported: bool
    prompt_price_usd_per_token: str
    completion_price_usd_per_token: str
    request_price_usd: Optional[str] = None
    request_price_state: Literal["ABSENT_UNKNOWN", "EXPLICIT_ZERO"]
    fresh_listing_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fresh_listing_length: int = Field(gt=0)
    prior_listing_sha256: Literal[
        REDUCED_PRIOR_ENDPOINT_LISTING_SHA256_V1
    ] = REDUCED_PRIOR_ENDPOINT_LISTING_SHA256_V1
    evidence_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterFlexEndpointEvidenceV1":
        parameters = set(self.supported_parameters)
        missing = _REQUIRED_FLEX_PARAMETERS_V1 - parameters
        if missing:
            raise ContractValidationError(
                f"Flex endpoint lacks required parameters: {sorted(missing)}"
            )
        if self.temperature_supported != ("temperature" in parameters):
            raise ContractValidationError("temperature capability evidence disagrees")
        prompt = _decimal_text(
            self.prompt_price_usd_per_token, "endpoint prompt price"
        )
        completion = _decimal_text(
            self.completion_price_usd_per_token, "endpoint completion price"
        )
        if prompt > Decimal("0.000000125"):
            raise ContractValidationError("Flex prompt price exceeds operator ceiling")
        if completion > Decimal("0.000001"):
            raise ContractValidationError(
                "Flex completion price exceeds operator ceiling"
            )
        if self.request_price_usd is None:
            if self.request_price_state != "ABSENT_UNKNOWN":
                raise ContractValidationError(
                    "absent request pricing must remain explicitly unknown"
                )
        else:
            request = _decimal_text(
                self.request_price_usd, "endpoint request price"
            )
            if request > 0 or self.request_price_state != "EXPLICIT_ZERO":
                raise ContractValidationError(
                    "a stated request price must be explicit zero"
                )
        expected = stable_contract_id(
            "szorflexendpointevidencev1",
            self.model_dump(mode="json", exclude={"evidence_id"}),
        )
        if self.evidence_id not in (None, expected):
            raise ContractValidationError("Flex endpoint evidence ID mismatch")
        object.__setattr__(self, "evidence_id", expected)
        return self


def validate_flex_endpoint_listing_v1(
    raw_bytes: bytes,
) -> OpenRouterFlexEndpointEvidenceV1:
    """Validate a fresh exact endpoint listing; never use model-level unions."""

    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise ContractValidationError("fresh Flex endpoint evidence is required")
    if len(raw_bytes) > _MAX_ENDPOINT_RESPONSE_BYTES_V1:
        raise ContractValidationError("Flex endpoint evidence exceeds byte cap")
    try:
        payload = json.loads(raw_bytes.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractValidationError(
            "Flex endpoint evidence is not UTF-8 JSON"
        ) from exc
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping) or data.get("id") != REDUCED_MODEL_V1:
        raise ContractValidationError("endpoint listing is for another model")
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list):
        raise ContractValidationError("endpoint listing lacks endpoint records")
    matches = [
        item
        for item in endpoints
        if isinstance(item, Mapping)
        and item.get("tag") == REDUCED_PROVIDER_SELECTOR_V1
        and item.get("model_id") == REDUCED_MODEL_V1
    ]
    if len(matches) != 1:
        raise ContractValidationError("exact Flex endpoint record is not unique")
    endpoint = matches[0]
    if type(endpoint.get("status")) is not int or endpoint["status"] != 0:
        raise ContractValidationError("exact Flex endpoint is not healthy")

    endpoint_name = endpoint.get("name")
    if not isinstance(endpoint_name, str) or not endpoint_name.strip():
        raise ContractValidationError("Flex endpoint name is absent")
    if REDUCED_DATED_ENDPOINT_MODEL_V1 not in endpoint_name:
        raise ContractValidationError("dated Flex endpoint identity drifted")
    provider_name = endpoint.get("provider_name")
    if provider_name != REDUCED_PROVIDER_DISPLAY_NAME_V1:
        raise ContractValidationError("Flex provider display identity drifted")

    parameters = endpoint.get("supported_parameters")
    if not isinstance(parameters, list) or not all(
        isinstance(item, str) and item for item in parameters
    ):
        raise ContractValidationError("Flex endpoint parameter list is malformed")
    missing = _REQUIRED_FLEX_PARAMETERS_V1 - set(parameters)
    if missing:
        raise ContractValidationError(
            f"Flex endpoint lacks required parameters: {sorted(missing)}"
        )

    context = endpoint.get("context_length")
    if type(context) is not int or context < REDUCED_MAX_INPUT_TOKENS_V1:
        raise ContractValidationError("Flex context is below the 400k P19 bound")
    maximum_output = endpoint.get("max_completion_tokens")
    if (
        type(maximum_output) is not int
        or maximum_output < REDUCED_MAX_OUTPUT_TOKENS_V1
    ):
        raise ContractValidationError("Flex output maximum is below 1024")
    max_prompt = endpoint.get("max_prompt_tokens")
    if max_prompt is not None and (type(max_prompt) is not int or max_prompt <= 0):
        raise ContractValidationError("Flex max_prompt_tokens is malformed")

    pricing = endpoint.get("pricing")
    if not isinstance(pricing, Mapping):
        raise ContractValidationError("Flex endpoint pricing is absent")
    prompt_text = pricing.get("prompt")
    completion_text = pricing.get("completion")
    prompt = _decimal_text(prompt_text, "endpoint prompt price")
    completion = _decimal_text(completion_text, "endpoint completion price")
    if prompt > Decimal("0.000000125"):
        raise ContractValidationError("Flex prompt price exceeds operator ceiling")
    if completion > Decimal("0.000001"):
        raise ContractValidationError("Flex completion price exceeds operator ceiling")

    request_text = pricing.get("request")
    if request_text is None:
        request_state = "ABSENT_UNKNOWN"
    else:
        request = _decimal_text(request_text, "endpoint request price")
        if request > 0:
            raise ContractValidationError("Flex request price exceeds zero ceiling")
        request_state = "EXPLICIT_ZERO"

    return OpenRouterFlexEndpointEvidenceV1(
        endpoint_name=endpoint_name,
        provider_display_name=provider_name,
        context_length=context,
        max_prompt_tokens_observed=max_prompt,
        maximum_output_tokens=maximum_output,
        supported_parameters=tuple(sorted(set(parameters))),
        temperature_supported="temperature" in parameters,
        prompt_price_usd_per_token=prompt_text,
        completion_price_usd_per_token=completion_text,
        request_price_usd=request_text,
        request_price_state=request_state,
        fresh_listing_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        fresh_listing_length=len(raw_bytes),
    )


def flex_profile_from_evidence_v1(
    evidence: OpenRouterFlexEndpointEvidenceV1,
) -> OpenRouterEndpointCapabilityProfileV1:
    if type(evidence) is not OpenRouterFlexEndpointEvidenceV1:
        raise ContractValidationError("exact Flex endpoint evidence is required")
    return OpenRouterEndpointCapabilityProfileV1(
        provider_selector=REDUCED_PROVIDER_SELECTOR_V1,
        canonical_model_observed=REDUCED_DATED_ENDPOINT_MODEL_V1,
        supported_parameters=evidence.supported_parameters,
        output_limit_parameter="max_tokens",
        evidence_sha256=evidence.fresh_listing_sha256,
    )


def build_reduced_flex_policy_v1() -> OpenRouterFrozenExecutionPolicyV1:
    """Build the exact approved Flex wire policy; temperature/reasoning omitted."""

    policy = OpenRouterFrozenExecutionPolicyV1(
        model=REDUCED_MODEL_V1,
        provider_only=(REDUCED_PROVIDER_SELECTOR_V1,),
        provider_order=(REDUCED_PROVIDER_SELECTOR_V1,),
        output_limit_tokens=REDUCED_MAX_OUTPUT_TOKENS_V1,
        temperature=None,
        seed=REDUCED_SEED_V1,
        max_price_prompt_usd_per_million=(
            REDUCED_PROMPT_CEILING_USD_PER_MILLION_V1
        ),
        max_price_completion_usd_per_million=(
            REDUCED_COMPLETION_CEILING_USD_PER_MILLION_V1
        ),
        max_price_request_usd=REDUCED_REQUEST_CEILING_USD_V1,
        bounded_timeout_seconds=120,
    )
    bound = conservative_turn_cost_bound_v1(
        policy, REDUCED_MAX_INPUT_TOKENS_V1
    )
    if bound != REDUCED_PER_CALL_BOUND_PICODOLLARS_V1:
        raise ContractValidationError("reduced P19 per-call arithmetic drifted")
    if bound * REDUCED_MAX_CALLS_V1 != (
        REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1
    ):
        raise ContractValidationError("reduced P19 session arithmetic drifted")
    if REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1 > (
        REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
    ):
        raise ContractValidationError("reduced run exceeds the $8 hard ceiling")
    return policy


def build_reduced_session_authorization_v1(
    policy: OpenRouterFrozenExecutionPolicyV1,
    profile: OpenRouterEndpointCapabilityProfileV1,
    *,
    session_id: str,
) -> OpenRouterLiveTestSessionAuthorizationV1:
    """Bind the approved 151-call/$8 envelope to the fresh exact profile."""

    expected = build_reduced_flex_policy_v1()
    if policy != expected:
        raise ContractValidationError("reduced execution policy drifted")
    if profile.provider_selector != REDUCED_PROVIDER_SELECTOR_V1:
        raise ContractValidationError("reduced endpoint profile drifted")
    if profile.output_limit_parameter != "max_tokens":
        raise ContractValidationError("Flex output parameter is not max_tokens")
    return OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Operator approved reduced 151-call Socrates benchmark with an "
            "$8.00 hard total session ceiling and zero retries."
        ),
        policy_id=policy.policy_id or "",
        profile_id=profile.profile_id or "",
        model=REDUCED_MODEL_V1,
        provider_selector=REDUCED_PROVIDER_SELECTOR_V1,
        maximum_calls=REDUCED_MAX_CALLS_V1,
        maximum_total_spend_picodollars=(
            REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
        ),
        maximum_per_call_spend_picodollars=(
            REDUCED_PER_CALL_BOUND_PICODOLLARS_V1
        ),
        session_id=session_id,
    )


def make_worker_payload_projector_v1(
    *,
    provider_aliases: Optional[Mapping[str, str]] = None,
) -> Callable[
    [Dict[str, Any], Dict[str, Any]],
    Tuple[Mapping[str, Any], Mapping[str, Any]],
]:
    """Project worker-bound task/state copies without mutating CED authority.

    CED's internal commitments intentionally retain authoritative ``model_id``
    values for model-independence rules.  This projector operates only on the
    detached dictionaries about to be serialized into provider-visible message
    content.  Seat provider IDs become Alpha/Beta/Gamma/Delta; model/company and
    route identities become explicit anonymous labels.
    """

    aliases = dict(
        provider_aliases
        or dict(zip(WORKER_PROVIDER_IDS_V1, WORKER_ALIASES_V1, strict=True))
    )
    if set(aliases.values()) != set(WORKER_ALIASES_V1):
        raise ContractValidationError(
            "worker projection must bind Alpha/Beta/Gamma/Delta exactly once"
        )
    if not all(
        isinstance(key, str) and key.strip()
        and isinstance(value, str) and value in WORKER_ALIASES_V1
        for key, value in aliases.items()
    ):
        raise ContractValidationError("worker alias projection is malformed")

    text_replacements = {
        REDUCED_DATED_ENDPOINT_MODEL_V1: "anonymous-model",
        REDUCED_MODEL_V1: "anonymous-model",
        REDUCED_PROVIDER_SELECTOR_V1: "anonymous-provider",
        REDUCED_PROVIDER_DISPLAY_NAME_V1: "anonymous-provider",
        **aliases,
    }
    ordered_replacements = tuple(
        sorted(text_replacements.items(), key=lambda pair: len(pair[0]), reverse=True)
    )

    def replace_text(value: str) -> str:
        result = value
        for source, target in ordered_replacements:
            result = result.replace(source, target)
        return result

    def project(value: Any, parent_key: Optional[str] = None) -> Any:
        key = (parent_key or "").lower()
        if isinstance(value, Mapping):
            return {
                str(nested_key): project(nested_value, str(nested_key))
                for nested_key, nested_value in value.items()
            }
        if isinstance(value, list):
            return [project(item, parent_key) for item in value]
        if isinstance(value, tuple):
            return [project(item, parent_key) for item in value]
        if isinstance(value, str):
            replaced = replace_text(value)
            if "model" in key and replaced not in WORKER_ALIASES_V1:
                return "anonymous-model"
            if "company" in key:
                return "anonymous-provider"
            if key in {
                "provider",
                "provider_id",
                "raised_by",
                "verifier_provider_id",
            }:
                return aliases.get(value, replaced or "anonymous-provider")
            return replaced
        return value

    def projector(
        task_payload: Dict[str, Any], state_payload: Dict[str, Any]
    ) -> Tuple[Mapping[str, Any], Mapping[str, Any]]:
        if not isinstance(task_payload, Mapping) or not isinstance(
            state_payload, Mapping
        ):
            raise ContractValidationError(
                "worker projection requires detached task/state objects"
            )
        return project(task_payload), project(state_payload)

    return projector


def assert_reduced_flex_rendered_turn_v1(
    rendered: OpenRouterRenderedTurnV1,
    *,
    expected_output_limit_tokens: int = REDUCED_MAX_OUTPUT_TOKENS_V1,
    forbidden_values: Sequence[str] = (),
    forbidden_json_keys: Sequence[str] = (),
) -> None:
    """Final body-byte guard immediately before a claim/socket boundary."""

    if type(rendered) is not OpenRouterRenderedTurnV1:
        raise ContractValidationError("exact rendered-turn contract is required")
    if (
        type(expected_output_limit_tokens) is not int
        or expected_output_limit_tokens <= 0
    ):
        raise ContractValidationError("expected output limit must be positive")
    try:
        body = json.loads(rendered.canonical_body_json)
    except ValueError as exc:  # model validation already guards this; fail closed
        raise ContractValidationError("rendered turn is not JSON") from exc
    if body.get("model") != REDUCED_MODEL_V1:
        raise ContractValidationError("rendered model drifted")
    if body.get("max_tokens") != expected_output_limit_tokens:
        raise ContractValidationError("rendered output bound drifted")
    if body.get("seed") != REDUCED_SEED_V1:
        raise ContractValidationError("rendered deterministic seed drifted")
    for forbidden_parameter in (
        "temperature",
        "reasoning",
        "reasoning_effort",
        "include_reasoning",
        "tools",
        "tool_choice",
    ):
        if forbidden_parameter in body:
            raise ContractValidationError(
                f"forbidden wire parameter emitted: {forbidden_parameter}"
            )
    provider = body.get("provider")
    if not isinstance(provider, Mapping):
        raise ContractValidationError("rendered provider controls are absent")
    expected_provider = {
        "allow_fallbacks": False,
        "max_price": {
            "completion": REDUCED_COMPLETION_CEILING_USD_PER_MILLION_V1,
            "prompt": REDUCED_PROMPT_CEILING_USD_PER_MILLION_V1,
            "request": REDUCED_REQUEST_CEILING_USD_V1,
        },
        "only": [REDUCED_PROVIDER_SELECTOR_V1],
        "order": [REDUCED_PROVIDER_SELECTOR_V1],
        "require_parameters": True,
    }
    if provider != expected_provider:
        raise ContractValidationError("rendered Flex provider controls drifted")
    if body.get("stream") is not False:
        raise ContractValidationError("rendered stream control drifted")
    response_format = body.get("response_format")
    json_schema = (
        response_format.get("json_schema")
        if isinstance(response_format, Mapping)
        else None
    )
    schema = json_schema.get("schema") if isinstance(json_schema, Mapping) else None
    if (
        not isinstance(response_format, Mapping)
        or response_format.get("type") != "json_schema"
        or not isinstance(json_schema, Mapping)
        or json_schema.get("strict") is not True
        or not isinstance(schema, Mapping)
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        raise ContractValidationError("rendered response_format is not strict")

    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ContractValidationError("rendered worker message array drifted")
    worker_visible = "\n".join(
        str(message.get("content") or "")
        for message in messages
        if isinstance(message, Mapping)
    )
    for hidden_identity in (
        REDUCED_MODEL_V1,
        REDUCED_DATED_ENDPOINT_MODEL_V1,
        REDUCED_PROVIDER_SELECTOR_V1,
        REDUCED_PROVIDER_DISPLAY_NAME_V1,
    ):
        if hidden_identity in worker_visible:
            raise ContractValidationError(
                "authoritative model/provider identity reached worker messages"
            )

    canonical = rendered.canonical_body_json
    for value in forbidden_values:
        if not isinstance(value, str) or not value:
            raise ContractValidationError("forbidden evaluator values must be nonblank")
        if value in canonical:
            raise ContractValidationError("hidden evaluator value reached provider body")

    forbidden_keys = set()
    for key in forbidden_json_keys:
        if not isinstance(key, str) or not key:
            raise ContractValidationError("forbidden evaluator keys must be nonblank")
        forbidden_keys.add(key)

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            collision = forbidden_keys.intersection(str(key) for key in value)
            if collision:
                raise ContractValidationError(
                    f"hidden evaluator key reached provider body: {sorted(collision)}"
                )
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(body)


def make_hidden_evaluator_guard_v1(
    *,
    forbidden_values: Sequence[str] = (),
    forbidden_json_keys: Sequence[str] = (),
) -> Callable[[object, OpenRouterRenderedTurnV1], None]:
    values = tuple(forbidden_values)
    keys = tuple(forbidden_json_keys)

    def guard(_task: object, rendered: OpenRouterRenderedTurnV1) -> None:
        assert_reduced_flex_rendered_turn_v1(
            rendered,
            forbidden_values=values,
            forbidden_json_keys=keys,
        )

    return guard


@dataclass(frozen=True)
class OpenRouterFlexEndpointFetchResultV1:
    http_status: int
    raw_response_body: bytes
    latency_ms: float


_flex_fetch_consumed_v1 = False


def fetch_flex_endpoint_listing_once_v1(
    *, bounded_timeout_seconds: int = 30
) -> OpenRouterFlexEndpointFetchResultV1:
    """Perform the one public, uncredentialed JIT endpoint GET; never retry."""

    global _flex_fetch_consumed_v1
    if _flex_fetch_consumed_v1:
        raise ContractValidationError("Flex endpoint JIT GET already consumed")
    _flex_fetch_consumed_v1 = True  # burn before opening the socket
    started = time.perf_counter()
    connection = http.client.HTTPSConnection(
        "openrouter.ai",
        timeout=bounded_timeout_seconds,
        context=ssl.create_default_context(),
    )
    try:
        connection.request(
            "GET",
            REDUCED_ENDPOINT_PATH_V1,
            headers={"Accept": "application/json"},
        )
        response = connection.getresponse()
        raw = response.read(_MAX_ENDPOINT_RESPONSE_BYTES_V1 + 1)
        if len(raw) > _MAX_ENDPOINT_RESPONSE_BYTES_V1:
            raise ContractValidationError("Flex endpoint GET exceeded byte cap")
        return OpenRouterFlexEndpointFetchResultV1(
            http_status=int(response.status),
            raw_response_body=raw,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
    finally:
        connection.close()


__all__ = [
    "OpenRouterFlexEndpointEvidenceV1",
    "OpenRouterFlexEndpointFetchResultV1",
    "REDUCED_AUTOMATIC_RETRIES_V1",
    "REDUCED_COMPLETION_CEILING_USD_PER_MILLION_V1",
    "REDUCED_CONSERVATIVE_SESSION_BOUND_PICODOLLARS_V1",
    "REDUCED_DATED_ENDPOINT_MODEL_V1",
    "REDUCED_ENDPOINT_PATH_V1",
    "REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1",
    "REDUCED_MAX_CALLS_V1",
    "REDUCED_MAX_INPUT_TOKENS_V1",
    "REDUCED_MAX_OUTPUT_TOKENS_V1",
    "REDUCED_MODEL_V1",
    "REDUCED_PER_CALL_BOUND_PICODOLLARS_V1",
    "REDUCED_PRIOR_ENDPOINT_LISTING_SHA256_V1",
    "REDUCED_PROMPT_CEILING_USD_PER_MILLION_V1",
    "REDUCED_PROVIDER_DISPLAY_NAME_V1",
    "REDUCED_PROVIDER_SELECTOR_V1",
    "REDUCED_REASONING_EFFORT_V1",
    "REDUCED_REQUEST_CEILING_USD_V1",
    "REDUCED_SEED_V1",
    "WORKER_ALIASES_V1",
    "WORKER_PROVIDER_IDS_V1",
    "assert_reduced_flex_rendered_turn_v1",
    "build_reduced_flex_policy_v1",
    "build_reduced_session_authorization_v1",
    "fetch_flex_endpoint_listing_once_v1",
    "flex_profile_from_evidence_v1",
    "make_hidden_evaluator_guard_v1",
    "make_worker_payload_projector_v1",
    "validate_flex_endpoint_listing_v1",
]

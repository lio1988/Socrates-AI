"""Exact additive OpenRouter live-candidate request overlay v2.

S6 sealed a request whose ``provider.max_price`` status was deliberately
``DEFERRED_NOT_RENDERED``.  This module leaves that evidence untouched.  It
binds an explicit operator price-ceiling record to the exact S6 prepared
request and deterministically renders a *new* request whose only body change is
the documented ``ProviderPreferences.max_price`` object with the complete
text-request charge set: ``prompt``, ``completion`` and ``request``.

Money enters only as decimal text and is normalized before either arithmetic
or identity.  Integer picodollars are rounded upward, so conversion cannot
understate an operator ceiling.  No production price is defined here: callers
must explicitly distinguish synthetic fixture authority from live-operator
authority and supply all three values, including an explicit ``"0"`` when the
per-request ceiling is zero.

Importing this module performs no filesystem, network, credential, provider,
model, tool, CED, or background-process activity.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_live_request_overlay_v1 import (
    OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1,
    TOKENS_PER_MILLION,
)
from .openrouter_pre_live_safety_v1 import (
    OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
    PICODOLLARS_PER_USD,
    OpenRouterRequestModalityProofV1,
    derive_openrouter_request_modality_proof_v1,
)
from .openrouter_route_controls_contracts import (
    FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1,
    FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_ROUTE_MODEL_V1,
    OpenRouterPreparedRouteRequestV1,
    OpenRouterRequestIntentReceiptV1,
)


OPENROUTER_OPERATOR_PRICE_CEILING_SCHEMA_V1 = (
    "socrateszero-openrouter-operator-price-ceiling/v1"
)
OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V2 = (
    "socrateszero-openrouter-live-request-overlay/v2"
)
OPENROUTER_LIVE_REQUEST_RENDERER_VERSION_V2 = (
    "socrateszero-openrouter-live-request-renderer/v2"
)
OPENROUTER_RENDERED_LIVE_REQUEST_SCHEMA_V2 = (
    "socrateszero-openrouter-rendered-live-request/v2"
)
OPENROUTER_OUTPUT_BOUND_EVIDENCE_SCHEMA_V2 = (
    "socrateszero-openrouter-output-bound-evidence/v2"
)
OPENROUTER_LIVE_REQUEST_MODALITY_BINDING_SCHEMA_V1 = (
    "socrateszero-openrouter-live-request-modality-binding/v1"
)

OPENROUTER_PROMPT_PRICE_UNIT_V1 = "USD_PER_MILLION_PROMPT_TOKENS"
OPENROUTER_COMPLETION_PRICE_UNIT_V1 = "USD_PER_MILLION_COMPLETION_TOKENS"
OPENROUTER_REQUEST_PRICE_UNIT_V1 = "USD_PER_REQUEST"
OPENROUTER_MAX_SAFE_PICODOLLARS_V1 = 10**24
OPENROUTER_MAX_DECIMAL_TEXT_LENGTH_V1 = 128
OPENROUTER_MAX_DECIMAL_EXPONENT_MAGNITUDE_V1 = 30

OPENROUTER_LIVE_MAX_PRICE_COMPONENTS_V2: Tuple[str, ...] = (
    "prompt",
    "completion",
    "request",
)

_DECIMAL_TEXT_V1 = re.compile(
    r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$"
)
_FROZEN_PARENT_BODY_BYTES_V1 = FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1.encode(
    "utf-8"
)
_FROZEN_PARENT_HEADER_BYTES_V1 = (
    FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1.encode("utf-8")
)
_FROZEN_PARENT_BODY_SHA256_V1 = hashlib.sha256(
    _FROZEN_PARENT_BODY_BYTES_V1
).hexdigest()
_FROZEN_PARENT_HEADER_SHA256_V1 = hashlib.sha256(
    _FROZEN_PARENT_HEADER_BYTES_V1
).hexdigest()


class OpenRouterOperatorScopeV1(str, Enum):
    """Whose authority a monetary record represents.

    Synthetic fixtures can exercise every local invariant, but a future live
    preflight must separately require ``LIVE_OPERATOR``.  Merely setting
    ``authorized=True`` never promotes a fixture into production authority.
    """

    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    LIVE_OPERATOR = "LIVE_OPERATOR"


class _FrozenLiveRequestContractV2(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        revalidate_instances="always",
    )


def _canonical_object_v2(value: str, field_name: str) -> dict[str, object]:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be exact JSON text")
    try:
        raw = value.encode("utf-8")
        parsed = json.loads(raw)
        rendered = canonical_json(parsed).encode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise ContractValidationError(f"{field_name} must be UTF-8 JSON") from exc
    if not isinstance(parsed, dict) or rendered != raw:
        raise ContractValidationError(f"{field_name} must be canonical JSON")
    return parsed


def _normalize_decimal_money_v1(value: str, field_name: str) -> Tuple[str, Decimal]:
    """Normalize finite non-negative decimal text without unbounded expansion."""

    if type(value) is not str:
        raise ContractValidationError(
            f"{field_name} must be a decimal string; binary float money is not "
            "an authority"
        )
    if not value or value != value.strip():
        raise ContractValidationError(
            f"{field_name} must be nonblank decimal text without whitespace"
        )
    if len(value) > OPENROUTER_MAX_DECIMAL_TEXT_LENGTH_V1:
        raise ContractValidationError(f"{field_name} decimal text is too long")
    if _DECIMAL_TEXT_V1.fullmatch(value) is None:
        raise ContractValidationError(
            f"{field_name} must be finite non-negative decimal text"
        )
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ContractValidationError(f"{field_name} is not a valid decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ContractValidationError(
            f"{field_name} must be a finite non-negative decimal"
        )
    exponent = parsed.as_tuple().exponent
    if not isinstance(exponent, int) or (
        abs(exponent) > OPENROUTER_MAX_DECIMAL_EXPONENT_MAGNITUDE_V1
        or abs(parsed.adjusted()) > OPENROUTER_MAX_DECIMAL_EXPONENT_MAGNITUDE_V1
    ):
        raise ContractValidationError(
            f"{field_name} exponent exceeds the safe arithmetic domain"
        )
    if parsed == 0:
        return "0", Decimal(0)
    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if not normalized:
        normalized = "0"
    return normalized, parsed


def _picodollars_per_token_ceiling_v2(
    usd_per_million: Decimal, field_name: str
) -> int:
    with localcontext() as context:
        context.prec = 80
        scaled = (
            usd_per_million * PICODOLLARS_PER_USD / TOKENS_PER_MILLION
        ).to_integral_value(rounding=ROUND_CEILING)
    if scaled < 0 or scaled > OPENROUTER_MAX_SAFE_PICODOLLARS_V1:
        raise ContractValidationError(
            f"{field_name} exceeds the safe picodollar arithmetic domain"
        )
    return int(scaled)


def _picodollars_per_request_ceiling_v2(usd: Decimal, field_name: str) -> int:
    with localcontext() as context:
        context.prec = 80
        scaled = (usd * PICODOLLARS_PER_USD).to_integral_value(
            rounding=ROUND_CEILING
        )
    if scaled < 0 or scaled > OPENROUTER_MAX_SAFE_PICODOLLARS_V1:
        raise ContractValidationError(
            f"{field_name} exceeds the safe picodollar arithmetic domain"
        )
    return int(scaled)


def _revalidate_prepared_parent_v2(
    prepared_request: OpenRouterPreparedRouteRequestV1,
) -> OpenRouterPreparedRouteRequestV1:
    if type(prepared_request) is not OpenRouterPreparedRouteRequestV1:
        raise ContractValidationError(
            "live request v2 requires the exact OpenRouterPreparedRouteRequestV1 "
            "type"
        )
    validated = OpenRouterPreparedRouteRequestV1.model_validate(
        prepared_request.model_dump(mode="python")
    )
    receipt = validated.request_intent_receipt
    if type(receipt) is not OpenRouterRequestIntentReceiptV1:
        raise ContractValidationError("prepared parent lacks its exact intent receipt")
    if validated.canonical_body_json != FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1:
        raise ContractValidationError(
            "prepared parent body differs from the sealed S6 request bytes"
        )
    if (
        validated.canonical_semantic_headers_json
        != FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1
    ):
        raise ContractValidationError(
            "prepared parent headers differ from the sealed S6 semantic headers"
        )
    if (
        validated.body_sha256 != _FROZEN_PARENT_BODY_SHA256_V1
        or validated.body_length != len(_FROZEN_PARENT_BODY_BYTES_V1)
        or validated.semantic_headers_sha256 != _FROZEN_PARENT_HEADER_SHA256_V1
        or validated.semantic_headers_length != len(_FROZEN_PARENT_HEADER_BYTES_V1)
    ):
        raise ContractValidationError(
            "prepared parent byte evidence differs from the sealed S6 request"
        )
    if (
        receipt.body_sha256 != validated.body_sha256
        or receipt.body_length != validated.body_length
        or receipt.semantic_headers_sha256 != validated.semantic_headers_sha256
        or receipt.semantic_headers_length != validated.semantic_headers_length
        or receipt.route_intent_id != validated.route_intent_id
    ):
        raise ContractValidationError(
            "prepared parent receipt does not bind its exact body and headers"
        )
    body = _canonical_object_v2(validated.canonical_body_json, "parent body")
    provider = body.get("provider")
    if not isinstance(provider, dict) or "max_price" in provider:
        raise ContractValidationError(
            "sealed parent must have a provider object with max_price absent"
        )
    return validated


class OpenRouterOperatorPriceCeilingV1(_FrozenLiveRequestContractV2):
    """Complete, exact operator component ceilings for one sealed parent request."""

    schema_version: Literal[
        OPENROUTER_OPERATOR_PRICE_CEILING_SCHEMA_V1
    ] = OPENROUTER_OPERATOR_PRICE_CEILING_SCHEMA_V1
    operator_scope: OpenRouterOperatorScopeV1
    authorized: bool
    authorization_evidence_id: Optional[str] = Field(
        default=None,
        pattern=r"^szoroperatorpricegrantv1_[0-9a-f]{64}$",
    )

    parent_prepared_request_id: str = Field(
        pattern=r"^szorpreparedroutev1_[0-9a-f]{64}$"
    )
    parent_request_intent_receipt_id: str = Field(
        pattern=r"^szorrouteintentreceiptv1_[0-9a-f]{64}$"
    )
    parent_route_intent_id: str = Field(pattern=r"^szorrouteintent_[0-9a-f]{64}$")
    parent_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_body_length: int = Field(ge=1)
    parent_semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_semantic_headers_length: int = Field(ge=1)
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1

    max_price_schema_path: Literal[
        OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1
    ] = OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1
    currency: Literal["USD"] = "USD"
    prompt_unit: Literal[
        OPENROUTER_PROMPT_PRICE_UNIT_V1
    ] = OPENROUTER_PROMPT_PRICE_UNIT_V1
    completion_unit: Literal[
        OPENROUTER_COMPLETION_PRICE_UNIT_V1
    ] = OPENROUTER_COMPLETION_PRICE_UNIT_V1
    request_unit: Literal[
        OPENROUTER_REQUEST_PRICE_UNIT_V1
    ] = OPENROUTER_REQUEST_PRICE_UNIT_V1

    # Required strings: ``None`` and omission are never converted to zero.
    prompt_usd_per_million_tokens: str
    completion_usd_per_million_tokens: str
    request_usd: str
    prompt_picodollars_per_token: Optional[int] = Field(default=None, ge=0)
    completion_picodollars_per_token: Optional[int] = Field(default=None, ge=0)
    request_picodollars: Optional[int] = Field(default=None, ge=0)
    price_policy_id: Optional[str] = Field(
        default=None, pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="before")
    @classmethod
    def refuse_implicit_authority(cls, data):
        if isinstance(data, dict):
            for field_name in (
                "prompt_usd_per_million_tokens",
                "completion_usd_per_million_tokens",
                "request_usd",
            ):
                if field_name in data and type(data[field_name]) is not str:
                    raise ContractValidationError(
                        f"{field_name} must be a required decimal string"
                    )
            if "authorized" in data and type(data["authorized"]) is not bool:
                raise ContractValidationError("authorized must be an exact boolean")
            for field_name in (
                "prompt_picodollars_per_token",
                "completion_picodollars_per_token",
                "request_picodollars",
            ):
                if (
                    field_name in data
                    and data[field_name] is not None
                    and type(data[field_name]) is not int
                ):
                    raise ContractValidationError(
                        f"{field_name} must be an exact integer"
                    )
        return data

    @model_validator(mode="after")
    def normalize_and_identify(self) -> "OpenRouterOperatorPriceCeilingV1":
        if self.authorized:
            evidence = self.authorization_evidence_id
            if evidence is None or evidence != evidence.strip():
                raise ContractValidationError(
                    "authorized operator policy requires nonblank authorization "
                    "evidence"
                )
        elif self.authorization_evidence_id is not None:
            raise ContractValidationError(
                "unauthorized operator policy cannot carry authorization evidence"
            )
        if self.operator_scope is OpenRouterOperatorScopeV1.LIVE_OPERATOR and not (
            self.authorized and self.authorization_evidence_id
        ):
            raise ContractValidationError(
                "LIVE_OPERATOR scope requires explicit operator authorization"
            )

        prompt_text, prompt_decimal = _normalize_decimal_money_v1(
            self.prompt_usd_per_million_tokens,
            "prompt_usd_per_million_tokens",
        )
        completion_text, completion_decimal = _normalize_decimal_money_v1(
            self.completion_usd_per_million_tokens,
            "completion_usd_per_million_tokens",
        )
        request_text, request_decimal = _normalize_decimal_money_v1(
            self.request_usd,
            "request_usd",
        )
        prompt_picos = _picodollars_per_token_ceiling_v2(
            prompt_decimal, "prompt_usd_per_million_tokens"
        )
        completion_picos = _picodollars_per_token_ceiling_v2(
            completion_decimal, "completion_usd_per_million_tokens"
        )
        request_picos = _picodollars_per_request_ceiling_v2(
            request_decimal, "request_usd"
        )
        for supplied, expected, field_name in (
            (
                self.prompt_picodollars_per_token,
                prompt_picos,
                "prompt_picodollars_per_token",
            ),
            (
                self.completion_picodollars_per_token,
                completion_picos,
                "completion_picodollars_per_token",
            ),
            (self.request_picodollars, request_picos, "request_picodollars"),
        ):
            if supplied is not None and supplied != expected:
                raise ContractValidationError(
                    f"{field_name} disagrees with its decimal ceiling"
                )
        object.__setattr__(self, "prompt_usd_per_million_tokens", prompt_text)
        object.__setattr__(
            self, "completion_usd_per_million_tokens", completion_text
        )
        object.__setattr__(self, "request_usd", request_text)
        object.__setattr__(self, "prompt_picodollars_per_token", prompt_picos)
        object.__setattr__(
            self, "completion_picodollars_per_token", completion_picos
        )
        object.__setattr__(self, "request_picodollars", request_picos)

        if (
            self.parent_body_sha256 != _FROZEN_PARENT_BODY_SHA256_V1
            or self.parent_body_length != len(_FROZEN_PARENT_BODY_BYTES_V1)
            or self.parent_semantic_headers_sha256
            != _FROZEN_PARENT_HEADER_SHA256_V1
            or self.parent_semantic_headers_length
            != len(_FROZEN_PARENT_HEADER_BYTES_V1)
        ):
            raise ContractValidationError(
                "operator price ceiling is not bound to the sealed parent bytes"
            )
        expected_id = stable_contract_id(
            "szoroperatorpriceceilingv1",
            self.model_dump(mode="json", exclude={"price_policy_id"}),
        )
        if self.price_policy_id not in (None, expected_id):
            raise ContractValidationError("operator price policy ID mismatch")
        object.__setattr__(self, "price_policy_id", expected_id)
        return self

    @property
    def has_complete_text_request_coverage(self) -> bool:
        return (
            self.prompt_picodollars_per_token is not None
            and self.completion_picodollars_per_token is not None
            and self.request_picodollars is not None
        )

    @property
    def is_live_operator_authority(self) -> bool:
        return (
            self.operator_scope is OpenRouterOperatorScopeV1.LIVE_OPERATOR
            and self.authorized
            and self.authorization_evidence_id is not None
        )


def _revalidate_price_policy_v1(
    policy: OpenRouterOperatorPriceCeilingV1,
) -> OpenRouterOperatorPriceCeilingV1:
    if type(policy) is not OpenRouterOperatorPriceCeilingV1:
        raise ContractValidationError(
            "price policy must use the exact OpenRouterOperatorPriceCeilingV1 type"
        )
    return OpenRouterOperatorPriceCeilingV1.model_validate(
        policy.model_dump(mode="python")
    )


def build_openrouter_operator_price_ceiling_v1(
    prepared_request: OpenRouterPreparedRouteRequestV1,
    *,
    operator_scope: OpenRouterOperatorScopeV1,
    authorized: bool,
    authorization_evidence_id: Optional[str],
    prompt_usd_per_million_tokens: str,
    completion_usd_per_million_tokens: str,
    request_usd: str,
) -> OpenRouterOperatorPriceCeilingV1:
    """Bind three explicit component ceilings to the exact sealed parent."""

    parent = _revalidate_prepared_parent_v2(prepared_request)
    if type(operator_scope) is not OpenRouterOperatorScopeV1:
        raise ContractValidationError(
            "operator_scope must use the exact OpenRouterOperatorScopeV1 enum"
        )
    if type(authorized) is not bool:
        raise ContractValidationError("authorized must be an exact boolean")
    receipt = parent.request_intent_receipt
    assert receipt is not None
    return OpenRouterOperatorPriceCeilingV1(
        operator_scope=operator_scope,
        authorized=authorized,
        authorization_evidence_id=authorization_evidence_id,
        parent_prepared_request_id=parent.prepared_request_id or "",
        parent_request_intent_receipt_id=receipt.receipt_id or "",
        parent_route_intent_id=parent.route_intent_id or "",
        parent_body_sha256=parent.body_sha256 or "",
        parent_body_length=parent.body_length or 0,
        parent_semantic_headers_sha256=parent.semantic_headers_sha256 or "",
        parent_semantic_headers_length=parent.semantic_headers_length or 0,
        prompt_usd_per_million_tokens=prompt_usd_per_million_tokens,
        completion_usd_per_million_tokens=completion_usd_per_million_tokens,
        request_usd=request_usd,
    )


class OpenRouterLiveRequestSafetyOverlayV2(_FrozenLiveRequestContractV2):
    """Complete price overlay over one exact S6 prepared request."""

    schema_version: Literal[
        OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V2
    ] = OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V2
    parent_prepared_request_id: str = Field(
        pattern=r"^szorpreparedroutev1_[0-9a-f]{64}$"
    )
    parent_request_intent_receipt_id: str = Field(
        pattern=r"^szorrouteintentreceiptv1_[0-9a-f]{64}$"
    )
    parent_route_control_policy_id: str = Field(min_length=1)
    parent_route_intent_id: str = Field(pattern=r"^szorrouteintent_[0-9a-f]{64}$")
    parent_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_body_length: int = Field(ge=1)
    parent_semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_semantic_headers_length: int = Field(ge=1)
    parent_request_modality_proof: OpenRouterRequestModalityProofV1
    parent_request_modality_proof_id: str = Field(
        pattern=r"^szorrequestmodalityv1_[0-9a-f]{64}$"
    )
    parent_message_count: int = Field(ge=1)

    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    exact_endpoint_selector: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    provider_only: Tuple[str, ...] = (OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,)
    provider_order: Tuple[str, ...] = (OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,)
    allow_fallbacks: Literal[False] = False
    require_parameters: Literal[True] = True
    stream: Literal[False] = False
    tools_enabled: Literal[False] = False
    metadata_enabled: Literal[True] = True
    response_cache_requested: Literal[False] = False
    max_output_tokens: Literal[
        OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    ] = OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1

    max_price_schema_path: Literal[
        OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1
    ] = OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1
    max_price_components: Tuple[str, ...] = OPENROUTER_LIVE_MAX_PRICE_COMPONENTS_V2
    image_charge_status: Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
    audio_charge_status: Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
    operator_price_ceiling: OpenRouterOperatorPriceCeilingV1
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    live_request_overlay_id: Optional[str] = Field(
        default=None, pattern=r"^szorliverequestoverlayv2_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterLiveRequestSafetyOverlayV2":
        policy = _revalidate_price_policy_v1(self.operator_price_ceiling)
        modality = OpenRouterRequestModalityProofV1.model_validate(
            self.parent_request_modality_proof.model_dump(mode="python")
        )
        object.__setattr__(self, "operator_price_ceiling", policy)
        object.__setattr__(self, "parent_request_modality_proof", modality)
        if self.provider_only != (self.exact_endpoint_selector,):
            raise ContractValidationError("overlay v2 must preserve provider.only")
        if self.provider_order != (self.exact_endpoint_selector,):
            raise ContractValidationError("overlay v2 must preserve provider.order")
        if self.max_price_components != OPENROUTER_LIVE_MAX_PRICE_COMPONENTS_V2:
            raise ContractValidationError(
                "overlay v2 max_price must contain prompt, completion and request"
            )
        if not policy.has_complete_text_request_coverage:
            raise ContractValidationError(
                "overlay v2 requires complete text-request price coverage"
            )
        if self.price_policy_id != policy.price_policy_id:
            raise ContractValidationError("overlay price policy ID mismatch")
        if (
            self.parent_prepared_request_id != policy.parent_prepared_request_id
            or self.parent_request_intent_receipt_id
            != policy.parent_request_intent_receipt_id
            or self.parent_route_intent_id != policy.parent_route_intent_id
            or self.parent_body_sha256 != policy.parent_body_sha256
            or self.parent_body_length != policy.parent_body_length
            or self.parent_semantic_headers_sha256
            != policy.parent_semantic_headers_sha256
            or self.parent_semantic_headers_length
            != policy.parent_semantic_headers_length
        ):
            raise ContractValidationError(
                "overlay and operator price policy bind different parent requests"
            )
        if (
            self.parent_body_sha256 != _FROZEN_PARENT_BODY_SHA256_V1
            or self.parent_body_length != len(_FROZEN_PARENT_BODY_BYTES_V1)
            or self.parent_semantic_headers_sha256
            != _FROZEN_PARENT_HEADER_SHA256_V1
            or self.parent_semantic_headers_length
            != len(_FROZEN_PARENT_HEADER_BYTES_V1)
        ):
            raise ContractValidationError("overlay v2 parent byte binding changed")
        if (
            modality.proof_id != self.parent_request_modality_proof_id
            or modality.body_sha256 != self.parent_body_sha256
            or modality.body_length != self.parent_body_length
            or modality.message_count != self.parent_message_count
        ):
            raise ContractValidationError(
                "overlay parent modality proof does not bind the parent bytes"
            )
        if (
            not modality.text_only
            or modality.image_parts != 0
            or modality.audio_parts != 0
        ):
            raise ContractValidationError(
                "image/audio can be NOT_APPLICABLE only for this text-only request"
            )
        expected_id = stable_contract_id(
            "szorliverequestoverlayv2",
            self.model_dump(mode="json", exclude={"live_request_overlay_id"}),
        )
        if self.live_request_overlay_id not in (None, expected_id):
            raise ContractValidationError("live request overlay v2 ID mismatch")
        if expected_id in (
            self.parent_prepared_request_id,
            self.parent_request_intent_receipt_id,
        ):
            raise ContractValidationError(
                "overlay v2 must have a new identity distinct from its parent"
            )
        object.__setattr__(self, "live_request_overlay_id", expected_id)
        return self

    @property
    def max_price_policy(self) -> OpenRouterOperatorPriceCeilingV1:
        return self.operator_price_ceiling

    @property
    def live_request_identity(self) -> str:
        return self.live_request_overlay_id or ""


def _revalidate_overlay_v2(
    overlay: OpenRouterLiveRequestSafetyOverlayV2,
) -> OpenRouterLiveRequestSafetyOverlayV2:
    if type(overlay) is not OpenRouterLiveRequestSafetyOverlayV2:
        raise ContractValidationError(
            "overlay must use the exact OpenRouterLiveRequestSafetyOverlayV2 type"
        )
    return OpenRouterLiveRequestSafetyOverlayV2.model_validate(
        overlay.model_dump(mode="python")
    )


def build_openrouter_live_request_safety_overlay_v2(
    prepared_request: OpenRouterPreparedRouteRequestV1,
    operator_price_ceiling: OpenRouterOperatorPriceCeilingV1,
) -> OpenRouterLiveRequestSafetyOverlayV2:
    """Create an immutable complete overlay over the exact prepared parent."""

    parent = _revalidate_prepared_parent_v2(prepared_request)
    policy = _revalidate_price_policy_v1(operator_price_ceiling)
    receipt = parent.request_intent_receipt
    assert receipt is not None
    if (
        policy.parent_prepared_request_id != parent.prepared_request_id
        or policy.parent_request_intent_receipt_id != receipt.receipt_id
        or policy.parent_route_intent_id != parent.route_intent_id
        or policy.parent_body_sha256 != parent.body_sha256
        or policy.parent_body_length != parent.body_length
        or policy.parent_semantic_headers_sha256 != parent.semantic_headers_sha256
        or policy.parent_semantic_headers_length != parent.semantic_headers_length
    ):
        raise ContractValidationError(
            "operator price policy belongs to a different prepared request"
        )
    modality = derive_openrouter_request_modality_proof_v1(parent.body_bytes)
    return OpenRouterLiveRequestSafetyOverlayV2(
        parent_prepared_request_id=parent.prepared_request_id or "",
        parent_request_intent_receipt_id=receipt.receipt_id or "",
        parent_route_control_policy_id=(
            parent.route_control_policy.route_control_policy_id or ""
        ),
        parent_route_intent_id=parent.route_intent_id or "",
        parent_body_sha256=parent.body_sha256 or "",
        parent_body_length=parent.body_length or 0,
        parent_semantic_headers_sha256=parent.semantic_headers_sha256 or "",
        parent_semantic_headers_length=parent.semantic_headers_length or 0,
        parent_request_modality_proof=modality,
        parent_request_modality_proof_id=modality.proof_id or "",
        parent_message_count=modality.message_count,
        operator_price_ceiling=policy,
        price_policy_id=policy.price_policy_id or "",
    )


# Short builder alias matching the established v1 naming surface.
build_openrouter_live_request_overlay_v2 = (
    build_openrouter_live_request_safety_overlay_v2
)


class OpenRouterRenderedLiveRequestV2(_FrozenLiveRequestContractV2):
    """Canonical bytes and identities for the newly rendered live candidate."""

    schema_version: Literal[
        OPENROUTER_RENDERED_LIVE_REQUEST_SCHEMA_V2
    ] = OPENROUTER_RENDERED_LIVE_REQUEST_SCHEMA_V2
    renderer_version: Literal[
        OPENROUTER_LIVE_REQUEST_RENDERER_VERSION_V2
    ] = OPENROUTER_LIVE_REQUEST_RENDERER_VERSION_V2
    live_request_overlay: OpenRouterLiveRequestSafetyOverlayV2
    live_request_overlay_id: str = Field(
        pattern=r"^szorliverequestoverlayv2_[0-9a-f]{64}$"
    )
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    parent_prepared_request_id: str = Field(
        pattern=r"^szorpreparedroutev1_[0-9a-f]{64}$"
    )
    parent_request_intent_receipt_id: str = Field(
        pattern=r"^szorrouteintentreceiptv1_[0-9a-f]{64}$"
    )
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    exact_endpoint_selector: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    max_output_tokens: Literal[
        OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    ] = OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    canonical_body_json: str
    canonical_semantic_headers_json: str
    body_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    body_length: Optional[int] = Field(default=None, ge=1)
    semantic_headers_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    semantic_headers_length: Optional[int] = Field(default=None, ge=1)
    request_modality_proof: OpenRouterRequestModalityProofV1
    request_modality_proof_id: Optional[str] = Field(
        default=None, pattern=r"^szorrequestmodalityv1_[0-9a-f]{64}$"
    )
    message_count: int = Field(ge=1)
    rendered_request_id: Optional[str] = Field(
        default=None, pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRenderedLiveRequestV2":
        overlay = _revalidate_overlay_v2(self.live_request_overlay)
        object.__setattr__(self, "live_request_overlay", overlay)
        if self.live_request_overlay_id != overlay.live_request_overlay_id:
            raise ContractValidationError("rendered request overlay ID mismatch")
        if self.price_policy_id != overlay.price_policy_id:
            raise ContractValidationError("rendered request price policy ID mismatch")
        if (
            self.parent_prepared_request_id != overlay.parent_prepared_request_id
            or self.parent_request_intent_receipt_id
            != overlay.parent_request_intent_receipt_id
        ):
            raise ContractValidationError("rendered request parent binding mismatch")

        body = _canonical_object_v2(self.canonical_body_json, "canonical_body_json")
        headers = _canonical_object_v2(
            self.canonical_semantic_headers_json,
            "canonical_semantic_headers_json",
        )
        base_body = _canonical_object_v2(
            FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1, "sealed parent body"
        )
        provider = base_body.get("provider")
        if not isinstance(provider, dict) or "max_price" in provider:
            raise ContractValidationError(
                "sealed parent provider must not already contain max_price"
            )
        policy = overlay.operator_price_ceiling
        expected_max_price = {
            "prompt": policy.prompt_usd_per_million_tokens,
            "completion": policy.completion_usd_per_million_tokens,
            "request": policy.request_usd,
        }
        provider["max_price"] = expected_max_price
        expected_body_json = canonical_json(base_body)
        if self.canonical_body_json != expected_body_json or body != base_body:
            raise ContractValidationError(
                "rendered body must add only provider.max_price prompt, completion "
                "and request"
            )
        rendered_provider = body.get("provider")
        if (
            not isinstance(rendered_provider, dict)
            or rendered_provider.get("max_price") != expected_max_price
            or set(expected_max_price) != set(OPENROUTER_LIVE_MAX_PRICE_COMPONENTS_V2)
        ):
            raise ContractValidationError("rendered max_price component set changed")
        if (
            self.canonical_semantic_headers_json
            != FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1
            or headers
            != _canonical_object_v2(
                FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
                "sealed parent semantic headers",
            )
        ):
            raise ContractValidationError(
                "live request v2 must preserve the exact semantic headers"
            )

        body_bytes = self.canonical_body_json.encode("utf-8")
        header_bytes = self.canonical_semantic_headers_json.encode("utf-8")
        body_sha256 = hashlib.sha256(body_bytes).hexdigest()
        header_sha256 = hashlib.sha256(header_bytes).hexdigest()
        for field_name, supplied, expected in (
            ("body_sha256", self.body_sha256, body_sha256),
            ("body_length", self.body_length, len(body_bytes)),
            (
                "semantic_headers_sha256",
                self.semantic_headers_sha256,
                header_sha256,
            ),
            (
                "semantic_headers_length",
                self.semantic_headers_length,
                len(header_bytes),
            ),
        ):
            if supplied is not None and supplied != expected:
                raise ContractValidationError(
                    f"{field_name} does not match rendered live request bytes"
                )
            object.__setattr__(self, field_name, expected)
        if body_sha256 == overlay.parent_body_sha256:
            raise ContractValidationError(
                "rendered live request must have a new body digest"
            )
        if header_sha256 != overlay.parent_semantic_headers_sha256:
            raise ContractValidationError(
                "rendered live request headers must remain bound to the parent"
            )

        expected_modality = derive_openrouter_request_modality_proof_v1(body_bytes)
        supplied_modality = OpenRouterRequestModalityProofV1.model_validate(
            self.request_modality_proof.model_dump(mode="python")
        )
        if supplied_modality != expected_modality:
            raise ContractValidationError(
                "rendered request modality proof does not bind its exact body"
            )
        if (
            supplied_modality.proof_id != self.request_modality_proof_id
            and self.request_modality_proof_id is not None
        ):
            raise ContractValidationError("rendered request modality proof ID mismatch")
        if supplied_modality.message_count != self.message_count:
            raise ContractValidationError("rendered request message count mismatch")
        if (
            not supplied_modality.text_only
            or supplied_modality.image_parts != 0
            or supplied_modality.audio_parts != 0
            or supplied_modality.message_count != overlay.parent_message_count
        ):
            raise ContractValidationError(
                "provider.max_price rendering must preserve text-only modality"
            )
        object.__setattr__(self, "request_modality_proof", supplied_modality)
        object.__setattr__(
            self, "request_modality_proof_id", supplied_modality.proof_id
        )

        expected_id = stable_contract_id(
            "szorrenderedliverequestv2",
            self.model_dump(mode="json", exclude={"rendered_request_id"}),
        )
        if self.rendered_request_id not in (None, expected_id):
            raise ContractValidationError("rendered live request v2 ID mismatch")
        if expected_id in (
            overlay.live_request_overlay_id,
            overlay.parent_prepared_request_id,
            overlay.parent_request_intent_receipt_id,
        ):
            raise ContractValidationError(
                "rendered live request identity must be new"
            )
        object.__setattr__(self, "rendered_request_id", expected_id)
        return self

    @property
    def body_bytes(self) -> bytes:
        return self.canonical_body_json.encode("utf-8")

    @property
    def semantic_header_bytes(self) -> bytes:
        return self.canonical_semantic_headers_json.encode("utf-8")

    @property
    def header_bytes(self) -> bytes:
        return self.semantic_header_bytes

    @property
    def header_sha256(self) -> str:
        return self.semantic_headers_sha256 or ""

    @property
    def header_length(self) -> int:
        return self.semantic_headers_length or 0

    @property
    def prepared_live_request_id(self) -> str:
        return self.rendered_request_id or ""

    @property
    def semantic_request_id(self) -> str:
        return self.rendered_request_id or ""


# Both names denote the exact same class, preserving exact-type checks.
OpenRouterPreparedLiveRequestV2 = OpenRouterRenderedLiveRequestV2


def _revalidate_rendered_request_v2(
    rendered_request: OpenRouterRenderedLiveRequestV2,
) -> OpenRouterRenderedLiveRequestV2:
    if type(rendered_request) is not OpenRouterRenderedLiveRequestV2:
        raise ContractValidationError(
            "rendered request must use the exact OpenRouterRenderedLiveRequestV2 type"
        )
    return OpenRouterRenderedLiveRequestV2.model_validate(
        rendered_request.model_dump(mode="python")
    )


def render_openrouter_live_request_v2(
    prepared_request: OpenRouterPreparedRouteRequestV1,
    overlay: OpenRouterLiveRequestSafetyOverlayV2,
) -> OpenRouterRenderedLiveRequestV2:
    """Render one deterministic v2 body by inserting only ``max_price``."""

    parent = _revalidate_prepared_parent_v2(prepared_request)
    validated_overlay = _revalidate_overlay_v2(overlay)
    receipt = parent.request_intent_receipt
    assert receipt is not None
    if (
        validated_overlay.parent_prepared_request_id != parent.prepared_request_id
        or validated_overlay.parent_request_intent_receipt_id != receipt.receipt_id
        or validated_overlay.parent_route_control_policy_id
        != parent.route_control_policy.route_control_policy_id
        or validated_overlay.parent_route_intent_id != parent.route_intent_id
        or validated_overlay.parent_body_sha256 != parent.body_sha256
        or validated_overlay.parent_body_length != parent.body_length
        or validated_overlay.parent_semantic_headers_sha256
        != parent.semantic_headers_sha256
        or validated_overlay.parent_semantic_headers_length
        != parent.semantic_headers_length
    ):
        raise ContractValidationError(
            "live request overlay belongs to a different prepared parent"
        )
    body = _canonical_object_v2(parent.canonical_body_json, "prepared parent body")
    provider = body.get("provider")
    if not isinstance(provider, dict) or "max_price" in provider:
        raise ContractValidationError(
            "prepared parent provider must have max_price absent before rendering"
        )
    policy = validated_overlay.operator_price_ceiling
    provider["max_price"] = {
        "prompt": policy.prompt_usd_per_million_tokens,
        "completion": policy.completion_usd_per_million_tokens,
        "request": policy.request_usd,
    }
    canonical_body = canonical_json(body)
    modality = derive_openrouter_request_modality_proof_v1(
        canonical_body.encode("utf-8")
    )
    return OpenRouterRenderedLiveRequestV2(
        live_request_overlay=validated_overlay,
        live_request_overlay_id=validated_overlay.live_request_overlay_id or "",
        price_policy_id=validated_overlay.price_policy_id,
        parent_prepared_request_id=parent.prepared_request_id or "",
        parent_request_intent_receipt_id=receipt.receipt_id or "",
        canonical_body_json=canonical_body,
        canonical_semantic_headers_json=parent.canonical_semantic_headers_json,
        request_modality_proof=modality,
        request_modality_proof_id=modality.proof_id,
        message_count=modality.message_count,
    )


prepare_openrouter_live_request_v2 = render_openrouter_live_request_v2
prepare_openrouter_live_request_overlay_v2 = render_openrouter_live_request_v2


class OpenRouterOutputBoundEvidenceV2(_FrozenLiveRequestContractV2):
    """The exact v2 rendered request's established ``max_tokens = 256`` bound."""

    schema_version: Literal[
        OPENROUTER_OUTPUT_BOUND_EVIDENCE_SCHEMA_V2
    ] = OPENROUTER_OUTPUT_BOUND_EVIDENCE_SCHEMA_V2
    status: Literal["ESTABLISHED"] = "ESTABLISHED"
    source_body_field: Literal["max_tokens"] = "max_tokens"
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    live_request_overlay_id: str = Field(
        pattern=r"^szorliverequestoverlayv2_[0-9a-f]{64}$"
    )
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(ge=1)
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    max_output_tokens: Literal[
        OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    ] = OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    output_bound_evidence_id: Optional[str] = Field(
        default=None, pattern=r"^szoroutputboundv2_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOutputBoundEvidenceV2":
        expected_id = stable_contract_id(
            "szoroutputboundv2",
            self.model_dump(mode="json", exclude={"output_bound_evidence_id"}),
        )
        if self.output_bound_evidence_id not in (None, expected_id):
            raise ContractValidationError("output bound evidence v2 ID mismatch")
        object.__setattr__(self, "output_bound_evidence_id", expected_id)
        return self

    @property
    def evidence_id(self) -> str:
        return self.output_bound_evidence_id or ""


def derive_openrouter_output_bound_evidence_v2(
    rendered_request: OpenRouterRenderedLiveRequestV2,
) -> OpenRouterOutputBoundEvidenceV2:
    request = _revalidate_rendered_request_v2(rendered_request)
    body = _canonical_object_v2(request.canonical_body_json, "rendered body")
    max_tokens = body.get("max_tokens")
    if type(max_tokens) is not int or (
        max_tokens != OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    ):
        raise ContractValidationError(
            "rendered live request must carry exact integer max_tokens = 256"
        )
    return OpenRouterOutputBoundEvidenceV2(
        rendered_request_id=request.rendered_request_id or "",
        live_request_overlay_id=request.live_request_overlay_id,
        price_policy_id=request.price_policy_id,
        body_sha256=request.body_sha256 or "",
        body_length=request.body_length or 0,
    )


# Concise alias for sibling proof builders.
derive_openrouter_output_bound_v2 = derive_openrouter_output_bound_evidence_v2


class OpenRouterLiveRequestModalityBindingV1(_FrozenLiveRequestContractV2):
    """Text/image/audio applicability bound to the exact new request bytes."""

    schema_version: Literal[
        OPENROUTER_LIVE_REQUEST_MODALITY_BINDING_SCHEMA_V1
    ] = OPENROUTER_LIVE_REQUEST_MODALITY_BINDING_SCHEMA_V1
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    live_request_overlay_id: str = Field(
        pattern=r"^szorliverequestoverlayv2_[0-9a-f]{64}$"
    )
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(ge=1)
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    request_modality_proof: OpenRouterRequestModalityProofV1
    request_modality_proof_id: str = Field(
        pattern=r"^szorrequestmodalityv1_[0-9a-f]{64}$"
    )
    message_count: int = Field(ge=1)
    image_parts: Literal[0] = 0
    audio_parts: Literal[0] = 0
    text_only: Literal[True] = True
    image_charge_status: Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
    audio_charge_status: Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
    modality_binding_id: Optional[str] = Field(
        default=None,
        pattern=r"^szorliverequestmodalitybindingv1_[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterLiveRequestModalityBindingV1":
        proof = OpenRouterRequestModalityProofV1.model_validate(
            self.request_modality_proof.model_dump(mode="python")
        )
        object.__setattr__(self, "request_modality_proof", proof)
        if (
            proof.proof_id != self.request_modality_proof_id
            or proof.body_sha256 != self.body_sha256
            or proof.body_length != self.body_length
            or proof.message_count != self.message_count
            or proof.image_parts != self.image_parts
            or proof.audio_parts != self.audio_parts
            or proof.text_only is not self.text_only
        ):
            raise ContractValidationError(
                "live request modality binding disagrees with its exact proof"
            )
        expected_id = stable_contract_id(
            "szorliverequestmodalitybindingv1",
            self.model_dump(mode="json", exclude={"modality_binding_id"}),
        )
        if self.modality_binding_id not in (None, expected_id):
            raise ContractValidationError("live request modality binding ID mismatch")
        object.__setattr__(self, "modality_binding_id", expected_id)
        return self


def derive_openrouter_live_request_modality_binding_v1(
    rendered_request: OpenRouterRenderedLiveRequestV2,
) -> OpenRouterLiveRequestModalityBindingV1:
    request = _revalidate_rendered_request_v2(rendered_request)
    proof = derive_openrouter_request_modality_proof_v1(request.body_bytes)
    if not proof.text_only or proof.image_parts != 0 or proof.audio_parts != 0:
        raise ContractValidationError(
            "the exact S7A live candidate must remain text-only"
        )
    return OpenRouterLiveRequestModalityBindingV1(
        rendered_request_id=request.rendered_request_id or "",
        live_request_overlay_id=request.live_request_overlay_id,
        price_policy_id=request.price_policy_id,
        body_sha256=request.body_sha256 or "",
        body_length=request.body_length or 0,
        request_modality_proof=proof,
        request_modality_proof_id=proof.proof_id or "",
        message_count=proof.message_count,
    )


__all__ = [
    "OPENROUTER_COMPLETION_PRICE_UNIT_V1",
    "OPENROUTER_LIVE_MAX_PRICE_COMPONENTS_V2",
    "OPENROUTER_LIVE_REQUEST_MODALITY_BINDING_SCHEMA_V1",
    "OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V2",
    "OPENROUTER_LIVE_REQUEST_RENDERER_VERSION_V2",
    "OPENROUTER_MAX_DECIMAL_EXPONENT_MAGNITUDE_V1",
    "OPENROUTER_MAX_DECIMAL_TEXT_LENGTH_V1",
    "OPENROUTER_MAX_SAFE_PICODOLLARS_V1",
    "OPENROUTER_OPERATOR_PRICE_CEILING_SCHEMA_V1",
    "OPENROUTER_OUTPUT_BOUND_EVIDENCE_SCHEMA_V2",
    "OPENROUTER_PROMPT_PRICE_UNIT_V1",
    "OPENROUTER_RENDERED_LIVE_REQUEST_SCHEMA_V2",
    "OPENROUTER_REQUEST_PRICE_UNIT_V1",
    "OpenRouterLiveRequestModalityBindingV1",
    "OpenRouterLiveRequestSafetyOverlayV2",
    "OpenRouterOperatorPriceCeilingV1",
    "OpenRouterOperatorScopeV1",
    "OpenRouterOutputBoundEvidenceV2",
    "OpenRouterPreparedLiveRequestV2",
    "OpenRouterRenderedLiveRequestV2",
    "build_openrouter_live_request_overlay_v2",
    "build_openrouter_live_request_safety_overlay_v2",
    "build_openrouter_operator_price_ceiling_v1",
    "derive_openrouter_live_request_modality_binding_v1",
    "derive_openrouter_output_bound_evidence_v2",
    "derive_openrouter_output_bound_v2",
    "prepare_openrouter_live_request_overlay_v2",
    "prepare_openrouter_live_request_v2",
    "render_openrouter_live_request_v2",
]

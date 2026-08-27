"""Additive live-request overlay and server-enforced unit-price ceiling.

The sealed Route Controls request does not render ``provider.max_price``; its
receipt records ``max_price_status: DEFERRED_NOT_RENDERED``.  That sealed
evidence is historical and is never rewritten.  Instead this module defines an
**additive overlay**: the sealed request intent plus an explicit price-ceiling
policy, producing a **new** future-live request identity that is distinct from
the sealed receipt identity and never replaces it.

Why the ceiling matters.  Exact actual endpoint pricing cannot be bound to the
exact request selector from retained evidence, because the pricing-bearing
endpoint record exposes only a broad provider display name and an undocumented
tag.  But ``provider.max_price`` is a documented **request-side** control that
the router enforces before selection, so it yields an independent pre-dispatch
upper bound on unit price without needing to read any endpoint's actual price.

Units are the trap.  ``max_price.prompt`` and ``max_price.completion`` are
documented as **USD per million tokens**, while the catalogue ``pricing`` fields
are USD **per token**.  Everything here converts explicitly and exactly; a factor
of a million is not a rounding error.

Import-inert.  Defines a mechanism, never a monetary policy: the operator
authorizes the actual ceiling values before S7, not this module.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id
from .openrouter_pre_live_safety_v1 import (
    OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
    PICODOLLARS_PER_USD,
)
from .openrouter_route_controls_contracts import (
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_ROUTE_MODEL_V1,
)

OPENROUTER_MAX_PRICE_POLICY_SCHEMA_V1 = "socrateszero-openrouter-max-price-policy/v1"
OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V1 = (
    "socrateszero-openrouter-live-request-overlay/v1"
)

#: Tokens per million.  ``max_price`` prompt/completion are per-million; the
#: catalogue ``pricing`` fields are per-token.  Never mix them.
TOKENS_PER_MILLION = 10**6

#: Every documented component of ``ProviderPreferences.max_price`` and its exact
#: unit, taken verbatim from the retained OpenAPI descriptions.  Nothing is
#: added: components absent from the retained contract do not exist here.
FROZEN_OPENROUTER_MAX_PRICE_COMPONENTS_V1: Tuple[Tuple[str, str], ...] = (
    ("prompt", "USD per million prompt tokens"),
    ("completion", "USD per million completion tokens"),
    ("request", "USD per request"),
    ("image", "USD per image"),
    ("audio", "USD per audio unit"),
)

#: The retained spec uses the name ``max_price`` for three unrelated things.
#: Only the middle one is the request-side ceiling audited here; the other two
#: would silently import the wrong semantics, the wrong units, or float money.
FROZEN_OPENROUTER_MAX_PRICE_NAME_SENSES_V1: Tuple[Tuple[str, str, str], ...] = (
    (
        "ParetoRouterPlugin.max_price",
        "NOT_USED",
        "A plugin cap: a float, input price only, enforced against price_source.",
    ),
    (
        "ProviderPreferences.max_price",
        "USED",
        "The request-side ceiling: an object of decimal strings, five components.",
    ),
    (
        "models-listing max_price query parameter",
        "NOT_USED",
        "A catalogue browse filter on a listing endpoint, not a request control.",
    ),
)

#: The audited routing semantics.  Each was proved separately against retained
#: evidence; see the phase document for the citation chain.
FROZEN_OPENROUTER_MAX_PRICE_SEMANTICS_V1: Tuple[Tuple[str, str], ...] = (
    ("EXCLUDED_BEFORE_SELECTION", "ESTABLISHED"),
    ("ONLY_LIST_CANNOT_OVERRIDE_CEILING", "ESTABLISHED"),
    ("UNSATISFIABLE_CEILING_FAILS_REQUEST", "ESTABLISHED"),
    ("FALLBACK_POLICY_CANNOT_OVERRIDE_CEILING", "ESTABLISHED"),
    ("INDEPENDENT_OF_RESPONSE_DISPLAY_GRANULARITY", "ESTABLISHED"),
)


class OpenRouterCeilingStatusV1(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class _FrozenOverlayContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _decimal_component(value: str, field: str) -> Decimal:
    """Parse a max_price component, refusing anything that is not exact money."""
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a decimal string")
    lowered = value.strip().lower()
    if any(token in lowered for token in ("nan", "inf")):
        raise ContractValidationError(f"{field} must be a finite decimal")
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ContractValidationError(f"{field} is not a valid decimal") from exc
    if not parsed.is_finite():
        raise ContractValidationError(f"{field} must be finite")
    if parsed < 0:
        raise ContractValidationError(f"{field} must not be negative")
    return parsed


def _picodollars_per_token_ceiling(per_million_usd: Decimal, field: str) -> int:
    """USD per million tokens -> picodollars per token, rounded up.

    ``usd_per_million / 1e6 * 1e12`` reduces to ``usd_per_million * 1e6``.
    Rounding is upward so a ceiling can overstate but never understate.
    """
    with localcontext() as context:
        context.prec = 60
        scaled = (
            per_million_usd * PICODOLLARS_PER_USD / TOKENS_PER_MILLION
        ).quantize(Decimal(1), rounding=ROUND_CEILING)
    if scaled > Decimal(10) ** 24:
        raise ContractValidationError(f"{field} exceeds the safe arithmetic domain")
    return int(scaled)


def _picodollars_ceiling(usd: Decimal, field: str) -> int:
    with localcontext() as context:
        context.prec = 60
        scaled = (usd * PICODOLLARS_PER_USD).quantize(
            Decimal(1), rounding=ROUND_CEILING
        )
    if scaled > Decimal(10) ** 24:
        raise ContractValidationError(f"{field} exceeds the safe arithmetic domain")
    return int(scaled)


class OpenRouterMaxPricePolicyV1(_FrozenOverlayContractV1):
    """An explicit ``provider.max_price`` policy, in documented units.

    Only the components the retained contract documents may be set, and each is
    a decimal string.  A float would be an unsafe monetary authority and the
    contract refuses one.
    """

    schema_version: Literal[
        OPENROUTER_MAX_PRICE_POLICY_SCHEMA_V1
    ] = OPENROUTER_MAX_PRICE_POLICY_SCHEMA_V1
    prompt_usd_per_million_tokens: Optional[str] = None
    completion_usd_per_million_tokens: Optional[str] = None
    request_usd: Optional[str] = None
    image_usd: Optional[str] = None
    audio_usd: Optional[str] = None
    prompt_picodollars_per_token: Optional[int] = Field(default=None, ge=0)
    completion_picodollars_per_token: Optional[int] = Field(default=None, ge=0)
    request_picodollars: Optional[int] = Field(default=None, ge=0)
    policy_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def refuse_non_string_money(cls, data):
        if isinstance(data, dict):
            for field in (
                "prompt_usd_per_million_tokens",
                "completion_usd_per_million_tokens",
                "request_usd",
                "image_usd",
                "audio_usd",
            ):
                value = data.get(field)
                if value is not None and not isinstance(value, str):
                    raise ContractValidationError(
                        f"{field} must be a decimal string, not "
                        f"{type(value).__name__}: float money is not an authority"
                    )
        return data

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterMaxPricePolicyV1":
        prompt = (
            _picodollars_per_token_ceiling(
                _decimal_component(
                    self.prompt_usd_per_million_tokens, "prompt"
                ),
                "prompt",
            )
            if self.prompt_usd_per_million_tokens is not None
            else None
        )
        completion = (
            _picodollars_per_token_ceiling(
                _decimal_component(
                    self.completion_usd_per_million_tokens, "completion"
                ),
                "completion",
            )
            if self.completion_usd_per_million_tokens is not None
            else None
        )
        request = (
            _picodollars_ceiling(
                _decimal_component(self.request_usd, "request"), "request"
            )
            if self.request_usd is not None
            else None
        )
        for declared, derived, name in (
            (self.prompt_picodollars_per_token, prompt, "prompt"),
            (self.completion_picodollars_per_token, completion, "completion"),
            (self.request_picodollars, request, "request"),
        ):
            if declared is not None and declared != derived:
                raise ContractValidationError(
                    f"{name} ceiling picodollars disagree with the decimal string"
                )
        object.__setattr__(self, "prompt_picodollars_per_token", prompt)
        object.__setattr__(self, "completion_picodollars_per_token", completion)
        object.__setattr__(self, "request_picodollars", request)
        expected = stable_contract_id(
            "szormaxpricepolicyv1",
            self.model_dump(mode="json", exclude={"policy_id"}),
        )
        if self.policy_id not in (None, expected):
            raise ContractValidationError("max price policy ID mismatch")
        object.__setattr__(self, "policy_id", expected)
        return self

    @property
    def bounds_token_prices(self) -> bool:
        """Both token unit prices are capped, which is what a cost bound needs."""
        return (
            self.prompt_picodollars_per_token is not None
            and self.completion_picodollars_per_token is not None
        )


class OpenRouterLiveRequestSafetyOverlayV1(_FrozenOverlayContractV1):
    """Sealed request intent + a price-ceiling policy = a new live request identity.

    Every frozen control is restated as a ``Literal`` so the overlay cannot
    quietly relax one, and the only thing it adds is the documented price
    ceiling.  ``live_request_identity`` is content addressed over the sealed
    receipt identity and the policy, and is deliberately a different value from
    the sealed receipt identity: this is a new request, not an edit of history.
    """

    schema_version: Literal[
        OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V1
    ] = OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V1
    sealed_request_intent_receipt_id: str = Field(min_length=1)
    sealed_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    # --- preserved frozen controls
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

    # --- the only addition
    max_price_policy: OpenRouterMaxPricePolicyV1

    live_request_identity: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveRequestSafetyOverlayV1":
        if self.provider_only != (self.exact_endpoint_selector,):
            raise ContractValidationError("overlay must preserve provider.only")
        if self.provider_order != (self.exact_endpoint_selector,):
            raise ContractValidationError("overlay must preserve provider.order")
        expected = stable_contract_id(
            "szorliverequestoverlayv1",
            {
                "schema_version": self.schema_version,
                "sealed_request_intent_receipt_id": (
                    self.sealed_request_intent_receipt_id
                ),
                "sealed_body_sha256": self.sealed_body_sha256,
                "max_price_policy_id": self.max_price_policy.policy_id,
            },
        )
        if self.live_request_identity not in (None, expected):
            raise ContractValidationError("live request identity mismatch")
        if expected == self.sealed_request_intent_receipt_id:
            raise ContractValidationError(
                "the live request identity must differ from the sealed receipt"
            )
        object.__setattr__(self, "live_request_identity", expected)
        return self


class OpenRouterUnitPriceCeilingV1(_FrozenOverlayContractV1):
    """A trusted, server-enforced upper bound on unit price.

    Distinct from an actual pricing record: this says "no more than", not "this
    much".  It is trusted because the router is documented to enforce it before
    selection, not because any endpoint's price was read.
    """

    status: OpenRouterCeilingStatusV1
    overlay_live_request_identity: str
    max_price_policy_id: str
    prompt_picodollars_per_token: Optional[int] = Field(default=None, ge=0)
    completion_picodollars_per_token: Optional[int] = Field(default=None, ge=0)
    request_picodollars: Optional[int] = Field(default=None, ge=0)
    ceiling_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterUnitPriceCeilingV1":
        established = self.status is OpenRouterCeilingStatusV1.ESTABLISHED
        if established and (
            self.prompt_picodollars_per_token is None
            or self.completion_picodollars_per_token is None
        ):
            raise ContractValidationError(
                "an established ceiling must cap both token unit prices"
            )
        expected = stable_contract_id(
            "szorunitpriceceilingv1",
            self.model_dump(mode="json", exclude={"ceiling_id"}),
        )
        if self.ceiling_id not in (None, expected):
            raise ContractValidationError("unit price ceiling ID mismatch")
        object.__setattr__(self, "ceiling_id", expected)
        return self


def derive_openrouter_unit_price_ceiling_v1(
    overlay: OpenRouterLiveRequestSafetyOverlayV1,
) -> OpenRouterUnitPriceCeilingV1:
    """Read the ceiling straight off the overlay's policy; invent nothing."""
    if type(overlay) is not OpenRouterLiveRequestSafetyOverlayV1:
        raise ContractValidationError("a ceiling requires the exact overlay contract")
    policy = overlay.max_price_policy
    established = policy.bounds_token_prices
    return OpenRouterUnitPriceCeilingV1(
        status=(
            OpenRouterCeilingStatusV1.ESTABLISHED
            if established
            else OpenRouterCeilingStatusV1.NOT_ESTABLISHED
        ),
        overlay_live_request_identity=overlay.live_request_identity or "",
        max_price_policy_id=policy.policy_id or "",
        prompt_picodollars_per_token=policy.prompt_picodollars_per_token,
        completion_picodollars_per_token=policy.completion_picodollars_per_token,
        request_picodollars=policy.request_picodollars,
    )


def endpoint_is_price_eligible_v1(
    ceiling: OpenRouterUnitPriceCeilingV1,
    prompt_picodollars_per_token: int,
    completion_picodollars_per_token: int,
) -> bool:
    """Whether a candidate endpoint survives the documented price filter.

    The retained guide says a request "will route to any provider with a price of
    <= $1/m prompt tokens, and <= $2/m completion tokens or less".  Both
    components must hold; exceeding either makes the endpoint ineligible, and no
    provider list or fallback setting can re-admit it.
    """
    if ceiling.status is not OpenRouterCeilingStatusV1.ESTABLISHED:
        return False
    return (
        prompt_picodollars_per_token <= (ceiling.prompt_picodollars_per_token or 0)
        and completion_picodollars_per_token
        <= (ceiling.completion_picodollars_per_token or 0)
    )


__all__ = [
    "endpoint_is_price_eligible_v1",
    "FROZEN_OPENROUTER_MAX_PRICE_COMPONENTS_V1",
    "FROZEN_OPENROUTER_MAX_PRICE_NAME_SENSES_V1",
    "FROZEN_OPENROUTER_MAX_PRICE_SEMANTICS_V1",
    "OPENROUTER_LIVE_REQUEST_OVERLAY_SCHEMA_V1",
    "OPENROUTER_MAX_PRICE_POLICY_SCHEMA_V1",
    "TOKENS_PER_MILLION",
    "OpenRouterCeilingStatusV1",
    "OpenRouterLiveRequestSafetyOverlayV1",
    "OpenRouterMaxPricePolicyV1",
    "OpenRouterUnitPriceCeilingV1",
    "derive_openrouter_unit_price_ceiling_v1",
]

"""Pre-live safety, budget and one-call authorization for OpenRouter, offline.

Two things are kept apart on purpose:

* **Structural safety** — properties this repository can prove now, offline:
  one local dispatch, fallback disabled, model and provider intent pinned,
  stream off, tools disabled, output token cap pinned, mapper available,
  causal binding available, timeout and worker termination bounded, receipt
  persistence available, CED authority disabled.
* **Fresh external preflight facts** — things that are only true at a moment and
  must be obtained immediately before the one live call, such as a trusted
  price.

Nothing here fetches anything.  S6 defines the contract; S7 would satisfy it.

Money is never a binary float.  Official prices arrive as decimal strings and are
carried as ``Decimal``, and every bound is expressed in integer picodollars
(1e-12 USD) rounded upward, so a cost bound can never be understated by rounding.

Import-inert.  No credential is read here, and none may ever enter an identity.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id
from .openrouter_pre_live_integration_v1 import OPENROUTER_MAX_LOCAL_DISPATCHES_V1
from .openrouter_route_controls_contracts import (
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_ROUTE_MODEL_V1,
)

OPENROUTER_PRE_LIVE_SAFETY_SCHEMA_V1 = (
    "socrateszero-openrouter-pre-live-safety-contract/v1"
)
OPENROUTER_INPUT_BOUND_SCHEMA_V1 = "socrateszero-openrouter-input-bound/v1"
OPENROUTER_OUTPUT_BOUND_SCHEMA_V1 = "socrateszero-openrouter-output-bound/v1"
OPENROUTER_PRICING_RECORD_SCHEMA_V1 = "socrateszero-openrouter-trusted-pricing/v1"
OPENROUTER_COST_BOUND_SCHEMA_V1 = "socrateszero-openrouter-cost-bound/v1"
OPENROUTER_OPERATOR_CEILING_SCHEMA_V1 = "socrateszero-openrouter-operator-ceiling/v1"
OPENROUTER_CREDENTIAL_ATTESTATION_SCHEMA_V1 = (
    "socrateszero-openrouter-credential-presence/v1"
)
OPENROUTER_LIVE_AUTHORIZATION_SCHEMA_V1 = (
    "socrateszero-openrouter-live-call-authorization/v1"
)

#: Picodollars per US dollar.  Integer money, no binary floats anywhere.
PICODOLLARS_PER_USD = 10**12

#: The output cap already pinned in the sealed Route Controls request body.
#: Recorded here as evidence; the sealed request is never modified by S6.
OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1 = 256

#: The sealed rendered request body size.  A byte cap, deliberately not renamed
#: a token cap: bytes are not tokens and the difference is the whole of P17.
OPENROUTER_SEALED_REQUEST_BODY_BYTES_V1 = 447

#: Pricing granularity audit, from the retained first-party endpoints schema.
#:
#: The request pins the exact provider selector ``azure/swedencentral``, which the
#: retained provider-selection guide describes as an exact provider slug naming a
#: region-specific endpoint.  The pricing-bearing endpoint record exposes
#: ``provider_name`` (a broad display name such as "OpenAI"), ``name`` (a display
#: string), and ``tag`` (a bare ``type: string`` with no description and no
#: documented namespace; the only retained example is ``openai``).  No retained
#: example anywhere carries a compound provider/region value, no endpoint-scoped
#: slug field exists on that record, and the retained ``endpoint_id`` examples are
#: UUIDs in a different namespace.  The documented way to obtain the exact slug is
#: a UI copy button, not an API field.
#:
#: So a pricing record cannot be bound unambiguously to the exact request
#: selector from retained evidence.  This is a structural blocker for P18, not a
#: freshness one.
OPENROUTER_PRICING_ENDPOINT_GRANULARITY_V1 = "BROAD_PROVIDER_ONLY"

#: Tokenizer family labels.  A family is not a tokenizer: it names a lineage, not
#: a pinned vocabulary, and may never stand in for one.
FROZEN_OPENROUTER_TOKENIZER_FAMILY_LABELS_V1: Tuple[str, ...] = (
    "Router",
    "Media",
    "Other",
    "GPT",
    "Claude",
    "Gemini",
    "Gemma",
    "Grok",
    "Cohere",
    "Nova",
    "Qwen",
)


class OpenRouterBoundStatusV1(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class OpenRouterInputBoundBasisV1(str, Enum):
    """How an input token upper bound was obtained, if at all.

    Byte length, character count, a chars-per-token heuristic, a tokenizer family
    label and post-call usage are all excluded by construction: none of them is a
    basis this enum can express.
    """

    PINNED_OFFICIAL_TOKENIZER = "PINNED_OFFICIAL_TOKENIZER"
    FIRST_PARTY_TOKEN_COUNT_FACILITY = "FIRST_PARTY_TOKEN_COUNT_FACILITY"
    NO_PINNED_TOKENIZER_AVAILABLE = "NO_PINNED_TOKENIZER_AVAILABLE"


class OpenRouterTokenizerBindingV1(str, Enum):
    """How firmly a tokenizer is bound to the exact model."""

    PINNED_IMPLEMENTATION = "PINNED_IMPLEMENTATION"
    FAMILY_LABEL_ONLY = "FAMILY_LABEL_ONLY"
    ABSENT = "ABSENT"


class OpenRouterPricingGranularityV1(str, Enum):
    """Whether a pricing record can name the exact request selector."""

    EXACT_SELECTOR_BINDABLE = "EXACT_SELECTOR_BINDABLE"
    BROAD_PROVIDER_ONLY = "BROAD_PROVIDER_ONLY"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class OpenRouterPricingSourceV1(str, Enum):
    """Acceptable authority for a trusted price.

    Only first-party OpenRouter surfaces documented in the retained v2r1
    OpenAPI qualify.  Endpoint-scoped pricing is preferred because the request
    pins a single provider endpoint and pricing may differ by route.
    """

    FIRST_PARTY_MODEL_ENDPOINTS = "FIRST_PARTY_MODEL_ENDPOINTS"
    FIRST_PARTY_MODELS_CATALOGUE = "FIRST_PARTY_MODELS_CATALOGUE"
    UNTRUSTED = "UNTRUSTED"


FROZEN_OPENROUTER_TRUSTED_PRICING_SOURCES_V1: Tuple[OpenRouterPricingSourceV1, ...] = (
    OpenRouterPricingSourceV1.FIRST_PARTY_MODEL_ENDPOINTS,
    OpenRouterPricingSourceV1.FIRST_PARTY_MODELS_CATALOGUE,
)


class OpenRouterPreflightFailureCodeV1(str, Enum):
    SAFETY_CONTRACT_MISMATCH = "SAFETY_CONTRACT_MISMATCH"
    TRANSPORT_NOT_READY = "TRANSPORT_NOT_READY"
    CREDENTIAL_ATTESTATION_MISSING = "CREDENTIAL_ATTESTATION_MISSING"
    REQUEST_INTENT_MISMATCH = "REQUEST_INTENT_MISMATCH"
    INPUT_BOUND_NOT_ESTABLISHED = "INPUT_BOUND_NOT_ESTABLISHED"
    INPUT_BYTE_CAP_EXCEEDED = "INPUT_BYTE_CAP_EXCEEDED"
    OUTPUT_BOUND_NOT_ESTABLISHED = "OUTPUT_BOUND_NOT_ESTABLISHED"
    OUTPUT_BOUND_NOT_SEALED_VALUE = "OUTPUT_BOUND_NOT_SEALED_VALUE"
    PRICING_NOT_ESTABLISHED = "PRICING_NOT_ESTABLISHED"
    PRICING_SOURCE_UNTRUSTED = "PRICING_SOURCE_UNTRUSTED"
    PRICING_MODEL_MISMATCH = "PRICING_MODEL_MISMATCH"
    PRICING_SELECTOR_MISMATCH = "PRICING_SELECTOR_MISMATCH"
    PRICING_GRANULARITY_INSUFFICIENT = "PRICING_GRANULARITY_INSUFFICIENT"
    PRICING_NOT_JIT_FRESH = "PRICING_NOT_JIT_FRESH"
    COST_ARITHMETIC_INVALID = "COST_ARITHMETIC_INVALID"
    COST_EXCEEDS_OPERATOR_CEILING = "COST_EXCEEDS_OPERATOR_CEILING"
    AUTHORIZATION_ALREADY_CONSUMED = "AUTHORIZATION_ALREADY_CONSUMED"


class OpenRouterPreflightVerdictV1(str, Enum):
    AUTHORIZED_FOR_ONE_CALL = "AUTHORIZED_FOR_ONE_CALL"
    REFUSED = "REFUSED"


FROZEN_OPENROUTER_PREFLIGHT_GUARD_ORDER_V1: Tuple[
    OpenRouterPreflightFailureCodeV1, ...
] = (
    OpenRouterPreflightFailureCodeV1.SAFETY_CONTRACT_MISMATCH,
    OpenRouterPreflightFailureCodeV1.TRANSPORT_NOT_READY,
    OpenRouterPreflightFailureCodeV1.CREDENTIAL_ATTESTATION_MISSING,
    OpenRouterPreflightFailureCodeV1.REQUEST_INTENT_MISMATCH,
    OpenRouterPreflightFailureCodeV1.INPUT_BYTE_CAP_EXCEEDED,
    OpenRouterPreflightFailureCodeV1.INPUT_BOUND_NOT_ESTABLISHED,
    OpenRouterPreflightFailureCodeV1.OUTPUT_BOUND_NOT_ESTABLISHED,
    OpenRouterPreflightFailureCodeV1.OUTPUT_BOUND_NOT_SEALED_VALUE,
    OpenRouterPreflightFailureCodeV1.PRICING_NOT_ESTABLISHED,
    OpenRouterPreflightFailureCodeV1.PRICING_SOURCE_UNTRUSTED,
    OpenRouterPreflightFailureCodeV1.PRICING_MODEL_MISMATCH,
    OpenRouterPreflightFailureCodeV1.PRICING_SELECTOR_MISMATCH,
    OpenRouterPreflightFailureCodeV1.PRICING_GRANULARITY_INSUFFICIENT,
    OpenRouterPreflightFailureCodeV1.PRICING_NOT_JIT_FRESH,
    OpenRouterPreflightFailureCodeV1.COST_ARITHMETIC_INVALID,
    OpenRouterPreflightFailureCodeV1.COST_EXCEEDS_OPERATOR_CEILING,
    OpenRouterPreflightFailureCodeV1.AUTHORIZATION_ALREADY_CONSUMED,
)
OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1 = stable_contract_id(
    "szorpreflightguardsv1",
    tuple(code.value for code in FROZEN_OPENROUTER_PREFLIGHT_GUARD_ORDER_V1),
)


class _FrozenSafetyContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _decimal_usd(value: str, field: str) -> Decimal:
    """Parse an official decimal price string, refusing anything unsafe."""
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a decimal string")
    lowered = value.strip().lower()
    if any(token in lowered for token in ("nan", "inf")):
        raise ContractValidationError(f"{field} must be a finite decimal")
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ContractValidationError(f"{field} is not a valid decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ContractValidationError(f"{field} must be finite and non-negative")
    return parsed


def _picodollars_ceiling(amount: Decimal, field: str) -> int:
    """Round a USD amount up to whole picodollars.

    Upward rounding only: a cost *upper* bound may overstate, never understate.
    """
    with localcontext() as context:
        context.prec = 60
        scaled = (amount * PICODOLLARS_PER_USD).quantize(
            Decimal(1), rounding=ROUND_CEILING
        )
    if scaled > Decimal(10) ** 24:
        raise ContractValidationError(f"{field} exceeds the safe arithmetic domain")
    return int(scaled)


class OpenRouterInputBoundEvidenceV1(_FrozenSafetyContractV1):
    """P17.  An upper bound on billed input tokens, or an honest absence.

    ``request_body_byte_cap`` is recorded separately and is a **byte** cap.  It
    is never presented as a token bound: no relationship between the two is
    established by the retained evidence.
    """

    schema_version: Literal[
        OPENROUTER_INPUT_BOUND_SCHEMA_V1
    ] = OPENROUTER_INPUT_BOUND_SCHEMA_V1
    status: OpenRouterBoundStatusV1
    basis: OpenRouterInputBoundBasisV1
    max_input_tokens: Optional[int] = Field(default=None, ge=0)
    request_body_byte_cap: int = Field(ge=0)
    bound_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chat_framing_overhead_bounded: bool = False
    tokenizer_binding: OpenRouterTokenizerBindingV1 = (
        OpenRouterTokenizerBindingV1.ABSENT
    )
    tokenizer_identity: Optional[str] = None
    model_tokenizer_binding_source: Optional[str] = None
    evidence_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterInputBoundEvidenceV1":
        established = self.status is OpenRouterBoundStatusV1.ESTABLISHED
        if established and self.max_input_tokens is None:
            raise ContractValidationError(
                "an established input bound must carry a token maximum"
            )
        if not established and self.max_input_tokens is not None:
            raise ContractValidationError(
                "an unestablished input bound must not carry a token maximum"
            )
        if established and not self.chat_framing_overhead_bounded:
            raise ContractValidationError(
                "an established input bound must also bound chat framing overhead"
            )
        if established and self.basis in (
            OpenRouterInputBoundBasisV1.NO_PINNED_TOKENIZER_AVAILABLE,
        ):
            raise ContractValidationError(
                "an established input bound requires a tokenizer or count facility"
            )
        if self.tokenizer_identity in FROZEN_OPENROUTER_TOKENIZER_FAMILY_LABELS_V1:
            raise ContractValidationError(
                "a tokenizer family label is not a tokenizer identity"
            )
        if established and self.basis is (
            OpenRouterInputBoundBasisV1.PINNED_OFFICIAL_TOKENIZER
        ):
            if self.tokenizer_binding is not (
                OpenRouterTokenizerBindingV1.PINNED_IMPLEMENTATION
            ):
                raise ContractValidationError(
                    "a tokenizer-based input bound requires a pinned implementation"
                )
            if not self.tokenizer_identity or not self.model_tokenizer_binding_source:
                raise ContractValidationError(
                    "a tokenizer-based input bound requires an identity and an "
                    "authoritative model-to-tokenizer binding source"
                )
        expected = stable_contract_id(
            "szorinputboundv1", self.model_dump(mode="json", exclude={"evidence_id"})
        )
        if self.evidence_id not in (None, expected):
            raise ContractValidationError("input bound evidence ID mismatch")
        object.__setattr__(self, "evidence_id", expected)
        return self


class OpenRouterOutputBoundEvidenceV1(_FrozenSafetyContractV1):
    """The output token cap, read from the sealed request body."""

    schema_version: Literal[
        OPENROUTER_OUTPUT_BOUND_SCHEMA_V1
    ] = OPENROUTER_OUTPUT_BOUND_SCHEMA_V1
    status: OpenRouterBoundStatusV1
    max_output_tokens: Optional[int] = Field(default=None, ge=0)
    bound_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOutputBoundEvidenceV1":
        established = self.status is OpenRouterBoundStatusV1.ESTABLISHED
        if established != (self.max_output_tokens is not None):
            raise ContractValidationError(
                "output bound status disagrees with the token maximum"
            )
        if established and self.max_output_tokens != (
            OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
        ):
            raise ContractValidationError(
                "the output bound must be the value sealed in the request body"
            )
        expected = stable_contract_id(
            "szoroutputboundv1", self.model_dump(mode="json", exclude={"evidence_id"})
        )
        if self.evidence_id not in (None, expected):
            raise ContractValidationError("output bound evidence ID mismatch")
        object.__setattr__(self, "evidence_id", expected)
        return self


class OpenRouterTrustedPricingRecordV1(_FrozenSafetyContractV1):
    """P18.  A price is only trusted while it is fresh and first-party.

    Freshness is expressed structurally rather than by wall clock:
    ``preflight_execution_id`` binds the record to the single bounded preflight
    that fetched it.  A record from another execution is not fresh, which keeps
    the rule deterministic and replayable offline.
    """

    schema_version: Literal[
        OPENROUTER_PRICING_RECORD_SCHEMA_V1
    ] = OPENROUTER_PRICING_RECORD_SCHEMA_V1
    source: OpenRouterPricingSourceV1
    source_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_execution_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    route_identity: Optional[str] = None
    route_identity_granularity: OpenRouterPricingGranularityV1 = (
        OpenRouterPricingGranularityV1.NOT_ESTABLISHED
    )
    currency: Literal["USD"] = "USD"
    price_unit: Literal["PER_TOKEN"] = "PER_TOKEN"
    prompt_price_usd: str
    completion_price_usd: str
    prompt_price_picodollars: Optional[int] = Field(default=None, ge=0)
    completion_price_picodollars: Optional[int] = Field(default=None, ge=0)
    record_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterTrustedPricingRecordV1":
        prompt = _picodollars_ceiling(
            _decimal_usd(self.prompt_price_usd, "prompt_price_usd"),
            "prompt_price_usd",
        )
        completion = _picodollars_ceiling(
            _decimal_usd(self.completion_price_usd, "completion_price_usd"),
            "completion_price_usd",
        )
        for declared, derived, field in (
            (self.prompt_price_picodollars, prompt, "prompt"),
            (self.completion_price_picodollars, completion, "completion"),
        ):
            if declared is not None and declared != derived:
                raise ContractValidationError(
                    f"{field} price picodollars disagree with the decimal string"
                )
        object.__setattr__(self, "prompt_price_picodollars", prompt)
        object.__setattr__(self, "completion_price_picodollars", completion)
        expected = stable_contract_id(
            "szorpricingrecordv1", self.model_dump(mode="json", exclude={"record_id"})
        )
        if self.record_id not in (None, expected):
            raise ContractValidationError("pricing record ID mismatch")
        object.__setattr__(self, "record_id", expected)
        return self

    @property
    def source_is_trusted(self) -> bool:
        return self.source in FROZEN_OPENROUTER_TRUSTED_PRICING_SOURCES_V1


class OpenRouterCostBoundV1(_FrozenSafetyContractV1):
    """P19.  Worst-case spend for one call, in whole picodollars.

    ``max_input_tokens * prompt_price + max_output_tokens * completion_price``,
    with no invented fees and none of the documented ones dropped.  Established
    only when both token bounds and the price are themselves trusted and bounded.
    """

    schema_version: Literal[
        OPENROUTER_COST_BOUND_SCHEMA_V1
    ] = OPENROUTER_COST_BOUND_SCHEMA_V1
    status: OpenRouterBoundStatusV1
    price_authority: Optional[
        Literal["ACTUAL_PRICING_RECORD", "SERVER_ENFORCED_CEILING"]
    ] = None
    price_authority_id: Optional[str] = None
    formula_ready: Literal[True] = True
    formula: Literal[
        "max_input_tokens * prompt_price + max_output_tokens * completion_price"
    ] = "max_input_tokens * prompt_price + max_output_tokens * completion_price"
    input_bound_evidence_id: str
    output_bound_evidence_id: str
    pricing_record_id: Optional[str] = None
    max_total_cost_picodollars: Optional[int] = Field(default=None, ge=0)
    bound_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterCostBoundV1":
        established = self.status is OpenRouterBoundStatusV1.ESTABLISHED
        if established != (self.max_total_cost_picodollars is not None):
            raise ContractValidationError("cost bound status disagrees with its value")
        if established and not (self.pricing_record_id or self.price_authority_id):
            raise ContractValidationError(
                "an established cost bound requires a price authority"
            )
        if established and self.price_authority is None:
            raise ContractValidationError(
                "an established cost bound must name its price authority"
            )
        expected = stable_contract_id(
            "szorcostboundv1", self.model_dump(mode="json", exclude={"bound_id"})
        )
        if self.bound_id not in (None, expected):
            raise ContractValidationError("cost bound ID mismatch")
        object.__setattr__(self, "bound_id", expected)
        return self


def compute_openrouter_cost_bound_v1(
    input_bound: OpenRouterInputBoundEvidenceV1,
    output_bound: OpenRouterOutputBoundEvidenceV1,
    pricing: Optional[OpenRouterTrustedPricingRecordV1],
) -> OpenRouterCostBoundV1:
    """Derive the worst-case cost, or report honestly that it is unbounded."""
    unbounded = (
        input_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED
        or output_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED
        or pricing is None
        or not pricing.source_is_trusted
        or pricing.route_identity_granularity
        is not OpenRouterPricingGranularityV1.EXACT_SELECTOR_BINDABLE
    )
    if unbounded:
        return OpenRouterCostBoundV1(
            status=OpenRouterBoundStatusV1.NOT_ESTABLISHED,
            input_bound_evidence_id=input_bound.evidence_id or "",
            output_bound_evidence_id=output_bound.evidence_id or "",
            pricing_record_id=pricing.record_id if pricing else None,
        )
    total = (input_bound.max_input_tokens or 0) * (
        pricing.prompt_price_picodollars or 0
    ) + (output_bound.max_output_tokens or 0) * (
        pricing.completion_price_picodollars or 0
    )
    if total < 0 or total > 10**24:
        raise ContractValidationError("cost bound exceeds the safe arithmetic domain")
    return OpenRouterCostBoundV1(
        status=OpenRouterBoundStatusV1.ESTABLISHED,
        price_authority="ACTUAL_PRICING_RECORD",
        price_authority_id=pricing.record_id,
        input_bound_evidence_id=input_bound.evidence_id or "",
        output_bound_evidence_id=output_bound.evidence_id or "",
        pricing_record_id=pricing.record_id,
        max_total_cost_picodollars=total,
    )


def compute_openrouter_ceiling_cost_bound_v1(
    input_bound: OpenRouterInputBoundEvidenceV1,
    output_bound: OpenRouterOutputBoundEvidenceV1,
    ceiling,
) -> OpenRouterCostBoundV1:
    """Worst-case cost from a server-enforced unit-price ceiling.

    A ceiling says "no more than", which is exactly what an upper bound needs.
    It does not say what the call will actually cost, and this function never
    pretends otherwise: the authority is recorded as SERVER_ENFORCED_CEILING.

    Still requires an input token bound.  A price ceiling caps the rate; it says
    nothing about how many tokens are billed.
    """
    from .openrouter_live_request_overlay_v1 import OpenRouterCeilingStatusV1

    unusable = (
        input_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED
        or output_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED
        or ceiling is None
        or ceiling.status is not OpenRouterCeilingStatusV1.ESTABLISHED
    )
    if unusable:
        return OpenRouterCostBoundV1(
            status=OpenRouterBoundStatusV1.NOT_ESTABLISHED,
            input_bound_evidence_id=input_bound.evidence_id or "",
            output_bound_evidence_id=output_bound.evidence_id or "",
        )
    total = (
        (input_bound.max_input_tokens or 0)
        * (ceiling.prompt_picodollars_per_token or 0)
        + (output_bound.max_output_tokens or 0)
        * (ceiling.completion_picodollars_per_token or 0)
        + (ceiling.request_picodollars or 0)
    )
    if total < 0 or total > 10**24:
        raise ContractValidationError("cost bound exceeds the safe arithmetic domain")
    return OpenRouterCostBoundV1(
        status=OpenRouterBoundStatusV1.ESTABLISHED,
        price_authority="SERVER_ENFORCED_CEILING",
        price_authority_id=ceiling.ceiling_id,
        input_bound_evidence_id=input_bound.evidence_id or "",
        output_bound_evidence_id=output_bound.evidence_id or "",
        max_total_cost_picodollars=total,
    )


class OpenRouterOperatorCeilingV1(_FrozenSafetyContractV1):
    """An independent operator spend ceiling for one call.

    Not a substitute for P18 or P19 — an additional firewall on top of them.  S6
    does not choose a monetary value; the operator authorizes one before S7.
    """

    schema_version: Literal[
        OPENROUTER_OPERATOR_CEILING_SCHEMA_V1
    ] = OPENROUTER_OPERATOR_CEILING_SCHEMA_V1
    authorized: bool
    max_spend_picodollars: Optional[int] = Field(default=None, ge=0)
    ceiling_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOperatorCeilingV1":
        if self.authorized != (self.max_spend_picodollars is not None):
            raise ContractValidationError(
                "operator ceiling authorization disagrees with its value"
            )
        expected = stable_contract_id(
            "szoroperatorceilingv1",
            self.model_dump(mode="json", exclude={"ceiling_id"}),
        )
        if self.ceiling_id not in (None, expected):
            raise ContractValidationError("operator ceiling ID mismatch")
        object.__setattr__(self, "ceiling_id", expected)
        return self


class OpenRouterCredentialPresenceAttestationV1(_FrozenSafetyContractV1):
    """That a credential exists — never which one.

    Only presence and the variable name are recorded.  No value, no prefix, no
    length, no digest of the secret: a digest of a short secret is a crackable
    secret, and none of it may enter a scientific identity.
    """

    schema_version: Literal[
        OPENROUTER_CREDENTIAL_ATTESTATION_SCHEMA_V1
    ] = OPENROUTER_CREDENTIAL_ATTESTATION_SCHEMA_V1
    credential_present: bool
    credential_variable_name: str = Field(min_length=1)
    attestation_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterCredentialPresenceAttestationV1":
        expected = stable_contract_id(
            "szorcredentialpresencev1",
            self.model_dump(mode="json", exclude={"attestation_id"}),
        )
        if self.attestation_id not in (None, expected):
            raise ContractValidationError("credential attestation ID mismatch")
        object.__setattr__(self, "attestation_id", expected)
        return self


class OpenRouterPreLiveSafetyContractV1(_FrozenSafetyContractV1):
    """Structural safety: what is provable offline, before any fresh fact."""

    schema_version: Literal[
        OPENROUTER_PRE_LIVE_SAFETY_SCHEMA_V1
    ] = OPENROUTER_PRE_LIVE_SAFETY_SCHEMA_V1
    max_local_dispatches: Literal[
        OPENROUTER_MAX_LOCAL_DISPATCHES_V1
    ] = OPENROUTER_MAX_LOCAL_DISPATCHES_V1
    automatic_retry_permitted: Literal[False] = False
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    exact_endpoint_selector: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    provider_fallback_permitted: Literal[False] = False
    model_fallback_permitted: Literal[False] = False
    require_parameters: Literal[True] = True
    stream: Literal[False] = False
    tools_enabled: Literal[False] = False
    response_cache_requested: Literal[False] = False
    max_output_tokens: Literal[
        OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    ] = OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
    mapper_available: bool = True
    causal_binding_available: bool = True
    raw_response_capture_available: bool = True
    receipt_persistence_available: bool = True
    timeout_bounded: bool = True
    worker_termination_bounded: bool = True
    credential_isolated_from_evidence: Literal[True] = True
    ced_authority_enabled: Literal[False] = False
    runtime_authority: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    guard_order_id: Literal[
        OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1
    ] = OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1
    contract_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreLiveSafetyContractV1":
        for name in (
            "mapper_available",
            "causal_binding_available",
            "raw_response_capture_available",
            "receipt_persistence_available",
            "timeout_bounded",
            "worker_termination_bounded",
        ):
            if getattr(self, name) is not True:
                raise ContractValidationError(
                    f"structural safety requires {name}"
                )
        expected = stable_contract_id(
            "szorprelivesafetyv1",
            self.model_dump(mode="json", exclude={"contract_id"}),
        )
        if self.contract_id not in (None, expected):
            raise ContractValidationError("pre-live safety contract ID mismatch")
        object.__setattr__(self, "contract_id", expected)
        return self


FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1 = OpenRouterPreLiveSafetyContractV1()
OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1 = (
    FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1.contract_id
)


class OpenRouterLiveCallAuthorizationV1(_FrozenSafetyContractV1):
    """Authorization for exactly one dispatch, consumable exactly once.

    Not a reusable boolean.  It is content addressed over the exact request
    intent, the exact pricing record, the exact bounds and the safety contract,
    so an authorization cannot drift onto a different request or a different
    price.
    """

    schema_version: Literal[
        OPENROUTER_LIVE_AUTHORIZATION_SCHEMA_V1
    ] = OPENROUTER_LIVE_AUTHORIZATION_SCHEMA_V1
    safety_contract_id: str
    request_intent_receipt_id: str
    input_bound_evidence_id: str
    output_bound_evidence_id: str
    pricing_record_id: str
    cost_bound_id: str
    operator_ceiling_id: str
    credential_attestation_id: str
    allowed_dispatches: Literal[
        OPENROUTER_MAX_LOCAL_DISPATCHES_V1
    ] = OPENROUTER_MAX_LOCAL_DISPATCHES_V1
    authorization_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveCallAuthorizationV1":
        expected = stable_contract_id(
            "szorliveauthorizationv1",
            self.model_dump(mode="json", exclude={"authorization_id"}),
        )
        if self.authorization_id not in (None, expected):
            raise ContractValidationError("live call authorization ID mismatch")
        object.__setattr__(self, "authorization_id", expected)
        return self


class OpenRouterPreflightResultV1(_FrozenSafetyContractV1):
    verdict: OpenRouterPreflightVerdictV1
    first_failure: Optional[OpenRouterPreflightFailureCodeV1] = None
    detail: Optional[str] = None
    authorization: Optional[OpenRouterLiveCallAuthorizationV1] = None

    @model_validator(mode="after")
    def consistent(self) -> "OpenRouterPreflightResultV1":
        authorized = self.verdict is OpenRouterPreflightVerdictV1.AUTHORIZED_FOR_ONE_CALL
        if authorized and (self.first_failure is not None or self.authorization is None):
            raise ContractValidationError(
                "an authorized preflight carries an authorization and no failure"
            )
        if not authorized and (
            self.first_failure is None or self.authorization is not None
        ):
            raise ContractValidationError(
                "a refused preflight carries a first failure and no authorization"
            )
        return self


def evaluate_live_preflight_v1(
    *,
    safety_contract: OpenRouterPreLiveSafetyContractV1,
    request_intent_receipt_id: str,
    expected_request_intent_receipt_id: str,
    expected_request_body_sha256: str,
    expected_request_body_length: int,
    transport_ready: bool,
    credential_attestation: Optional[OpenRouterCredentialPresenceAttestationV1],
    input_bound: OpenRouterInputBoundEvidenceV1,
    output_bound: OpenRouterOutputBoundEvidenceV1,
    pricing: Optional[OpenRouterTrustedPricingRecordV1],
    cost_bound: OpenRouterCostBoundV1,
    operator_ceiling: OpenRouterOperatorCeilingV1,
    preflight_execution_id: str,
    consumed_authorization_ids: Tuple[str, ...] = (),
) -> OpenRouterPreflightResultV1:
    """Decide whether exactly one live dispatch may proceed.

    Every failure below happens before any network could be touched, and the
    first failing guard is reported rather than a list.  This function performs
    no I/O of any kind.
    """

    def refuse(code: OpenRouterPreflightFailureCodeV1, detail: str):
        return OpenRouterPreflightResultV1(
            verdict=OpenRouterPreflightVerdictV1.REFUSED,
            first_failure=code,
            detail=detail,
        )

    if (
        type(safety_contract) is not OpenRouterPreLiveSafetyContractV1
        or safety_contract.contract_id != OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1
    ):
        return refuse(
            OpenRouterPreflightFailureCodeV1.SAFETY_CONTRACT_MISMATCH,
            "structural safety contract is not the frozen one",
        )
    if not transport_ready:
        return refuse(
            OpenRouterPreflightFailureCodeV1.TRANSPORT_NOT_READY,
            "transport is not ready for a single bounded dispatch",
        )
    if credential_attestation is None or not credential_attestation.credential_present:
        return refuse(
            OpenRouterPreflightFailureCodeV1.CREDENTIAL_ATTESTATION_MISSING,
            "no credential presence attestation",
        )
    if request_intent_receipt_id != expected_request_intent_receipt_id:
        return refuse(
            OpenRouterPreflightFailureCodeV1.REQUEST_INTENT_MISMATCH,
            "request intent receipt is not the authorized one",
        )
    if input_bound.bound_request_body_sha256 != expected_request_body_sha256:
        return refuse(
            OpenRouterPreflightFailureCodeV1.REQUEST_INTENT_MISMATCH,
            "input bound evidence was computed for a different request body",
        )
    if input_bound.request_body_byte_cap < expected_request_body_length:
        return refuse(
            OpenRouterPreflightFailureCodeV1.INPUT_BYTE_CAP_EXCEEDED,
            "the rendered request exceeds its declared byte cap",
        )
    if input_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED:
        return refuse(
            OpenRouterPreflightFailureCodeV1.INPUT_BOUND_NOT_ESTABLISHED,
            f"input token bound is not established ({input_bound.basis.value})",
        )
    if output_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED:
        return refuse(
            OpenRouterPreflightFailureCodeV1.OUTPUT_BOUND_NOT_ESTABLISHED,
            "output token bound is not established",
        )
    if output_bound.max_output_tokens != safety_contract.max_output_tokens:
        return refuse(
            OpenRouterPreflightFailureCodeV1.OUTPUT_BOUND_NOT_SEALED_VALUE,
            "output bound is not the sealed request value",
        )
    if pricing is None:
        return refuse(
            OpenRouterPreflightFailureCodeV1.PRICING_NOT_ESTABLISHED,
            "no trusted pricing record",
        )
    if not pricing.source_is_trusted:
        return refuse(
            OpenRouterPreflightFailureCodeV1.PRICING_SOURCE_UNTRUSTED,
            f"pricing source {pricing.source.value} is not first-party",
        )
    if pricing.model_id != safety_contract.exact_model:
        return refuse(
            OpenRouterPreflightFailureCodeV1.PRICING_MODEL_MISMATCH,
            "pricing record is for a different model",
        )
    if pricing.route_identity != safety_contract.exact_endpoint_selector:
        return refuse(
            OpenRouterPreflightFailureCodeV1.PRICING_SELECTOR_MISMATCH,
            "pricing record does not name the exact request endpoint selector",
        )
    if pricing.route_identity_granularity is not (
        OpenRouterPricingGranularityV1.EXACT_SELECTOR_BINDABLE
    ):
        return refuse(
            OpenRouterPreflightFailureCodeV1.PRICING_GRANULARITY_INSUFFICIENT,
            "pricing route identity is not bindable at exact-selector granularity",
        )
    if pricing.preflight_execution_id != preflight_execution_id:
        return refuse(
            OpenRouterPreflightFailureCodeV1.PRICING_NOT_JIT_FRESH,
            "pricing record was not obtained in this preflight execution",
        )
    if cost_bound.status is not OpenRouterBoundStatusV1.ESTABLISHED:
        return refuse(
            OpenRouterPreflightFailureCodeV1.COST_ARITHMETIC_INVALID,
            "worst-case cost is not bounded",
        )
    if not operator_ceiling.authorized:
        return refuse(
            OpenRouterPreflightFailureCodeV1.COST_EXCEEDS_OPERATOR_CEILING,
            "no operator spend ceiling authorized",
        )
    if (cost_bound.max_total_cost_picodollars or 0) > (
        operator_ceiling.max_spend_picodollars or 0
    ):
        return refuse(
            OpenRouterPreflightFailureCodeV1.COST_EXCEEDS_OPERATOR_CEILING,
            "worst-case cost exceeds the operator ceiling",
        )

    authorization = OpenRouterLiveCallAuthorizationV1(
        safety_contract_id=safety_contract.contract_id or "",
        request_intent_receipt_id=request_intent_receipt_id,
        input_bound_evidence_id=input_bound.evidence_id or "",
        output_bound_evidence_id=output_bound.evidence_id or "",
        pricing_record_id=pricing.record_id or "",
        cost_bound_id=cost_bound.bound_id or "",
        operator_ceiling_id=operator_ceiling.ceiling_id or "",
        credential_attestation_id=credential_attestation.attestation_id or "",
    )
    if authorization.authorization_id in consumed_authorization_ids:
        return refuse(
            OpenRouterPreflightFailureCodeV1.AUTHORIZATION_ALREADY_CONSUMED,
            "this one-call authorization has already been consumed",
        )
    return OpenRouterPreflightResultV1(
        verdict=OpenRouterPreflightVerdictV1.AUTHORIZED_FOR_ONE_CALL,
        authorization=authorization,
    )


__all__ = [
    "FROZEN_OPENROUTER_PREFLIGHT_GUARD_ORDER_V1",
    "FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1",
    "FROZEN_OPENROUTER_TRUSTED_PRICING_SOURCES_V1",
    "OPENROUTER_COST_BOUND_SCHEMA_V1",
    "OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1",
    "OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1",
    "OPENROUTER_PRE_LIVE_SAFETY_SCHEMA_V1",
    "OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1",
    "OPENROUTER_SEALED_REQUEST_BODY_BYTES_V1",
    "PICODOLLARS_PER_USD",
    "OpenRouterBoundStatusV1",
    "OpenRouterCostBoundV1",
    "OpenRouterCredentialPresenceAttestationV1",
    "OpenRouterInputBoundBasisV1",
    "OpenRouterInputBoundEvidenceV1",
    "OpenRouterLiveCallAuthorizationV1",
    "OpenRouterOperatorCeilingV1",
    "OpenRouterOutputBoundEvidenceV1",
    "OpenRouterPreLiveSafetyContractV1",
    "OpenRouterPreflightFailureCodeV1",
    "OpenRouterPreflightResultV1",
    "OpenRouterPreflightVerdictV1",
    "OPENROUTER_PRICING_ENDPOINT_GRANULARITY_V1",
    "FROZEN_OPENROUTER_TOKENIZER_FAMILY_LABELS_V1",
    "OpenRouterPricingGranularityV1",
    "OpenRouterPricingSourceV1",
    "OpenRouterTokenizerBindingV1",
    "OpenRouterTrustedPricingRecordV1",
    "compute_openrouter_ceiling_cost_bound_v1",
    "compute_openrouter_cost_bound_v1",
    "evaluate_live_preflight_v1",
]

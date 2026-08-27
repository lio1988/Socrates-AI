"""Complete local safety closure for one future OpenRouter shadow call.

This additive S7A module composes the exact rendered request-v2 and P17 proof
contracts with complete P19 charge coverage, an operator total-spend ceiling,
one-shot transport readiness, credential-presence isolation, immutable
single-use authorization, and a deterministic fail-closed preflight.

The module is import-inert.  It performs no network, provider, model, credential,
tool, CED, aggregate, or background work.  Synthetic records can exercise every
local invariant, but their scope can never be promoted to live authority.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_live_request_overlay_v2 import (
    OPENROUTER_MAX_SAFE_PICODOLLARS_V1,
    OpenRouterLiveRequestModalityBindingV1,
    OpenRouterOperatorPriceCeilingV1,
    OpenRouterOperatorScopeV1,
    OpenRouterOutputBoundEvidenceV2,
    OpenRouterRenderedLiveRequestV2,
)
from .openrouter_pre_live_integration_v1 import (
    OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1,
    OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1,
)
from .openrouter_pre_live_safety_v1 import (
    FROZEN_OPENROUTER_CHARGE_CLASS_TERMS_V1,
    OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1,
    OpenRouterChargeClassStateV1,
    OpenRouterChargeCoverageV1,
)
from .openrouter_raw_wire_mapping_v2 import (
    OPENROUTER_WIRE_GUARD_ORDER_ID_V2,
    OPENROUTER_WIRE_MAPPING_SCHEMA_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2,
)
from .openrouter_trusted_input_bound_v1 import (
    OpenRouterInputLimitSourceScopeV1,
    OpenRouterP17InputBoundProofV1,
    OpenRouterP17ProofAuthorityV1,
)


OPENROUTER_OPERATOR_TOTAL_SPEND_SCHEMA_V1 = (
    "socrateszero-openrouter-operator-total-spend-ceiling/v1"
)
OPENROUTER_P19_COST_COMPONENT_SCHEMA_V1 = (
    "socrateszero-openrouter-p19-cost-component/v1"
)
OPENROUTER_P19_COST_BOUND_SCHEMA_V1 = (
    "socrateszero-openrouter-p19-worst-case-cost-bound/v1"
)
OPENROUTER_ONE_SHOT_TRANSPORT_POLICY_SCHEMA_V1 = (
    "socrateszero-openrouter-one-shot-transport-policy/v1"
)
OPENROUTER_TRANSPORT_READINESS_SCHEMA_V1 = (
    "socrateszero-openrouter-transport-readiness/v1"
)
OPENROUTER_JIT_CREDENTIAL_PRESENCE_SCHEMA_V1 = (
    "socrateszero-openrouter-jit-credential-presence/v1"
)
OPENROUTER_S5_MAPPER_CAPABILITY_SCHEMA_V1 = (
    "socrateszero-openrouter-s5-mapper-capability/v1"
)
OPENROUTER_S6_INTEGRATION_CAPABILITY_SCHEMA_V1 = (
    "socrateszero-openrouter-s6-integration-capability/v1"
)
OPENROUTER_ONE_CALL_AUTHORIZATION_SCHEMA_V1 = (
    "socrateszero-openrouter-one-call-authorization/v1"
)
OPENROUTER_ONE_CALL_CONSUMPTION_SCHEMA_V1 = (
    "socrateszero-openrouter-one-call-consumption/v1"
)
OPENROUTER_ONE_LIVE_CALL_PREFLIGHT_RESULT_SCHEMA_V1 = (
    "socrateszero-openrouter-one-live-call-preflight-result/v1"
)

OPENROUTER_S6_SOURCE_HEAD_V1 = (
    "f58c2a6113a4840fc003751e3b209f31d46fab67"
)
OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_ID_V1 = (
    "szorpreliveartifactv1_"
    "4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779"
)
OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_SHA256_V1 = (
    "8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d"
)
OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1 = 256
OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1 = 1

FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1: Tuple[str, ...] = tuple(
    name for name, _ in FROZEN_OPENROUTER_CHARGE_CLASS_TERMS_V1
)
FROZEN_OPENROUTER_P19_FORMULA_TERMS_V1: Tuple[Tuple[str, str], ...] = (
    ("prompt", "max_input_tokens * prompt_price_ceiling"),
    ("completion", "256 * completion_price_ceiling"),
    ("request", "request_fee_ceiling"),
    ("image", "NOT_APPLICABLE"),
    ("audio", "NOT_APPLICABLE"),
)
OPENROUTER_P19_PROOF_METHOD_ID_V1 = stable_contract_id(
    "szorp19proofmethodv1",
    {
        "charge_classes": FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1,
        "formula_terms": FROZEN_OPENROUTER_P19_FORMULA_TERMS_V1,
        "money_unit": "PICODOLLAR",
        "rounding": "CEILING_AT_POLICY_PARSE_BOUNDARY",
    },
)


class OpenRouterLiveSafetyModeV1(str, Enum):
    SYNTHETIC_OFFLINE = "SYNTHETIC_OFFLINE"
    LIVE_JIT = "LIVE_JIT"


class OpenRouterP19AuthorityV1(str, Enum):
    LIVE_JIT_ESTABLISHED = "LIVE_JIT_ESTABLISHED"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
    NOT_ESTABLISHED_OVER_CEILING = "NOT_ESTABLISHED_OVER_CEILING"


class OpenRouterCredentialAvailabilityV1(str, Enum):
    YES = "YES"
    NO = "NO"


class OpenRouterAuthorizationScopeV1(str, Enum):
    LIVE_JIT = "LIVE_JIT"
    SYNTHETIC_OFFLINE_ONLY = "SYNTHETIC_OFFLINE_ONLY"


class OpenRouterOneLiveCallVerdictV1(str, Enum):
    AUTHORIZED_FOR_ONE_CALL = "AUTHORIZED_FOR_ONE_CALL"
    REFUSED = "REFUSED"


class OpenRouterOneLiveCallFailureCodeV1(str, Enum):
    SAFETY_CONTRACT_MISMATCH = "SAFETY_CONTRACT_MISMATCH"
    REQUEST_IDENTITY_MISMATCH = "REQUEST_IDENTITY_MISMATCH"
    MODALITY_PROOF_MISMATCH = "MODALITY_PROOF_MISMATCH"
    P17_SOURCE_UNTRUSTED = "P17_SOURCE_UNTRUSTED"
    P17_NOT_JIT_FRESH = "P17_NOT_JIT_FRESH"
    P17_MODEL_MISMATCH = "P17_MODEL_MISMATCH"
    P17_REQUEST_MISMATCH = "P17_REQUEST_MISMATCH"
    P17_NOT_ESTABLISHED = "P17_NOT_ESTABLISHED"
    OUTPUT_BOUND_NOT_ESTABLISHED = "OUTPUT_BOUND_NOT_ESTABLISHED"
    PRICE_POLICY_INCOMPLETE = "PRICE_POLICY_INCOMPLETE"
    PRICE_POLICY_NOT_AUTHORIZED = "PRICE_POLICY_NOT_AUTHORIZED"
    PRICE_POLICY_MISMATCH = "PRICE_POLICY_MISMATCH"
    COST_BOUND_MISMATCH = "COST_BOUND_MISMATCH"
    COST_ARITHMETIC_INVALID = "COST_ARITHMETIC_INVALID"
    TOTAL_SPEND_CEILING_MISSING = "TOTAL_SPEND_CEILING_MISSING"
    COST_EXCEEDS_TOTAL_SPEND_CEILING = "COST_EXCEEDS_TOTAL_SPEND_CEILING"
    CREDENTIAL_ATTESTATION_MISSING = "CREDENTIAL_ATTESTATION_MISSING"
    TRANSPORT_NOT_READY = "TRANSPORT_NOT_READY"
    TRANSPORT_DISPATCH_CAP_INVALID = "TRANSPORT_DISPATCH_CAP_INVALID"
    S5_MAPPER_UNAVAILABLE = "S5_MAPPER_UNAVAILABLE"
    S6_INTEGRATION_UNAVAILABLE = "S6_INTEGRATION_UNAVAILABLE"
    CED_AUTHORITY_ENABLED = "CED_AUTHORITY_ENABLED"
    AUTHORIZATION_ALREADY_CONSUMED = "AUTHORIZATION_ALREADY_CONSUMED"


FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1: Tuple[
    OpenRouterOneLiveCallFailureCodeV1, ...
] = tuple(OpenRouterOneLiveCallFailureCodeV1)
OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1 = stable_contract_id(
    "szorlivepreflightguardsv1",
    tuple(code.value for code in FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1),
)


class _FrozenLiveSafetyContractV1(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        revalidate_instances="always",
    )


def _exact_contract(value: object, expected_type, label: str):
    if type(value) is not expected_type:
        raise ContractValidationError(
            f"{label} must use the exact {expected_type.__name__} contract"
        )
    return expected_type.model_validate(value.model_dump(mode="python"))


def _nonblank(value: Optional[str], label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ContractValidationError(f"{label} must be nonblank canonical text")
    return value


def _checked_product(quantity: int, unit_price: int, label: str) -> int:
    if type(quantity) is not int or type(unit_price) is not int:
        raise ContractValidationError(f"{label} requires exact integer arithmetic")
    if quantity < 0 or unit_price < 0:
        raise ContractValidationError(f"{label} cannot be negative")
    if quantity and unit_price > OPENROUTER_MAX_SAFE_PICODOLLARS_V1 // quantity:
        raise ContractValidationError(f"{label} exceeds the safe arithmetic domain")
    return quantity * unit_price


def _checked_sum(values: Tuple[int, ...]) -> int:
    total = 0
    for value in values:
        if type(value) is not int or value < 0:
            raise ContractValidationError("cost terms must be non-negative integers")
        if value > OPENROUTER_MAX_SAFE_PICODOLLARS_V1 - total:
            raise ContractValidationError("cost sum exceeds the safe arithmetic domain")
        total += value
    return total


class OpenRouterOperatorTotalSpendCeilingV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_OPERATOR_TOTAL_SPEND_SCHEMA_V1
    ] = OPENROUTER_OPERATOR_TOTAL_SPEND_SCHEMA_V1
    operator_scope: OpenRouterOperatorScopeV1
    authorized: bool
    authorization_evidence_id: Optional[str] = Field(default=None, min_length=1)
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(strict=True, gt=0)
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    currency: Literal["USD"] = "USD"
    unit: Literal["PICODOLLAR"] = "PICODOLLAR"
    max_spend_picodollars: int = Field(strict=True, ge=0)
    ceiling_id: Optional[str] = Field(
        default=None, pattern=r"^szoroperatortotalspendv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="before")
    @classmethod
    def strict_authority_types(cls, data):
        if isinstance(data, dict):
            if "authorized" in data and type(data["authorized"]) is not bool:
                raise ContractValidationError("authorized must be an exact boolean")
            if (
                "max_spend_picodollars" in data
                and type(data["max_spend_picodollars"]) is not int
            ):
                raise ContractValidationError(
                    "operator total spend must be exact integer picodollars"
                )
        return data

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterOperatorTotalSpendCeilingV1":
        if self.authorized:
            _nonblank(self.authorization_evidence_id, "total-spend authorization")
        elif self.authorization_evidence_id is not None:
            raise ContractValidationError(
                "an unauthorized total-spend ceiling cannot carry grant evidence"
            )
        if self.operator_scope is OpenRouterOperatorScopeV1.LIVE_OPERATOR and not (
            self.authorized and self.authorization_evidence_id
        ):
            raise ContractValidationError(
                "LIVE_OPERATOR total spend requires explicit authorization"
            )
        if self.max_spend_picodollars > OPENROUTER_MAX_SAFE_PICODOLLARS_V1:
            raise ContractValidationError(
                "operator total spend exceeds the safe arithmetic domain"
            )
        expected = stable_contract_id(
            "szoroperatortotalspendv1",
            self.model_dump(mode="json", exclude={"ceiling_id"}),
        )
        if self.ceiling_id not in (None, expected):
            raise ContractValidationError("operator total-spend ceiling ID mismatch")
        object.__setattr__(self, "ceiling_id", expected)
        return self


def build_openrouter_operator_total_spend_ceiling_v1(
    rendered_request: OpenRouterRenderedLiveRequestV2,
    price_policy: OpenRouterOperatorPriceCeilingV1,
    *,
    operator_scope: OpenRouterOperatorScopeV1,
    authorized: bool,
    authorization_evidence_id: Optional[str],
    max_spend_picodollars: int,
) -> OpenRouterOperatorTotalSpendCeilingV1:
    request = _exact_contract(
        rendered_request, OpenRouterRenderedLiveRequestV2, "rendered request"
    )
    policy = _exact_contract(
        price_policy, OpenRouterOperatorPriceCeilingV1, "operator price policy"
    )
    if request.price_policy_id != policy.price_policy_id:
        raise ContractValidationError("total spend is bound to another price policy")
    if operator_scope is not policy.operator_scope:
        raise ContractValidationError(
            "component and total-spend operator scopes must agree"
        )
    return OpenRouterOperatorTotalSpendCeilingV1(
        operator_scope=operator_scope,
        authorized=authorized,
        authorization_evidence_id=authorization_evidence_id,
        rendered_request_id=request.rendered_request_id or "",
        body_sha256=request.body_sha256 or "",
        body_length=request.body_length or 0,
        price_policy_id=policy.price_policy_id or "",
        max_spend_picodollars=max_spend_picodollars,
    )


class OpenRouterP19CostComponentV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_P19_COST_COMPONENT_SCHEMA_V1
    ] = OPENROUTER_P19_COST_COMPONENT_SCHEMA_V1
    charge_class: Literal["prompt", "completion", "request", "image", "audio"]
    state: OpenRouterChargeClassStateV1
    quantity: Optional[int] = Field(default=None, strict=True, ge=0)
    quantity_unit: Optional[Literal["TOKEN", "REQUEST"]] = None
    ceiling_picodollars_per_unit: Optional[int] = Field(
        default=None, strict=True, ge=0
    )
    subtotal_picodollars: Optional[int] = Field(default=None, strict=True, ge=0)
    non_applicability_proof_id: Optional[str] = None
    component_id: Optional[str] = Field(
        default=None, pattern=r"^szorp19componentv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterP19CostComponentV1":
        if self.state is OpenRouterChargeClassStateV1.INCLUDED:
            if None in (
                self.quantity,
                self.quantity_unit,
                self.ceiling_picodollars_per_unit,
                self.subtotal_picodollars,
            ):
                raise ContractValidationError(
                    "an included charge requires quantity, unit, ceiling and subtotal"
                )
            if self.non_applicability_proof_id is not None:
                raise ContractValidationError(
                    "an included charge cannot carry non-applicability evidence"
                )
            assert self.quantity is not None
            assert self.ceiling_picodollars_per_unit is not None
            expected_subtotal = _checked_product(
                self.quantity,
                self.ceiling_picodollars_per_unit,
                self.charge_class,
            )
            if self.subtotal_picodollars != expected_subtotal:
                raise ContractValidationError(
                    "charge subtotal disagrees with exact integer multiplication"
                )
        elif self.state is OpenRouterChargeClassStateV1.NOT_APPLICABLE:
            if any(
                value is not None
                for value in (
                    self.quantity,
                    self.quantity_unit,
                    self.ceiling_picodollars_per_unit,
                    self.subtotal_picodollars,
                )
            ):
                raise ContractValidationError(
                    "a non-applicable charge cannot carry an arithmetic term"
                )
            _nonblank(
                self.non_applicability_proof_id, "charge non-applicability proof"
            )
        else:
            raise ContractValidationError(
                "S7A P19 authority cannot contain an unbounded charge class"
            )
        expected = stable_contract_id(
            "szorp19componentv1",
            self.model_dump(mode="json", exclude={"component_id"}),
        )
        if self.component_id not in (None, expected):
            raise ContractValidationError("P19 charge-component ID mismatch")
        object.__setattr__(self, "component_id", expected)
        return self


def render_openrouter_p19_formula_v1(
    components: Tuple[OpenRouterP19CostComponentV1, ...],
) -> str:
    names = tuple(component.charge_class for component in components)
    if names != FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1:
        raise ContractValidationError(
            "P19 components must name all five documented classes in order"
        )
    if any(
        component.state is not OpenRouterChargeClassStateV1.INCLUDED
        for component in components[:3]
    ) or any(
        component.state is not OpenRouterChargeClassStateV1.NOT_APPLICABLE
        for component in components[3:]
    ):
        raise ContractValidationError(
            "text-only P19 requires prompt/completion/request included and "
            "image/audio proven non-applicable"
        )
    return (
        "max_total_cost = max_input_tokens * prompt_price_ceiling + "
        "256 * completion_price_ceiling + request_fee_ceiling "
        "[image=NOT_APPLICABLE, audio=NOT_APPLICABLE]"
    )


class OpenRouterWorstCaseCostBoundV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_P19_COST_BOUND_SCHEMA_V1
    ] = OPENROUTER_P19_COST_BOUND_SCHEMA_V1
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(strict=True, gt=0)
    p17_proof_id: str = Field(pattern=r"^szorp17inputboundproofv1_[0-9a-f]{64}$")
    output_bound_evidence_id: str = Field(
        pattern=r"^szoroutputboundv2_[0-9a-f]{64}$"
    )
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    modality_binding_id: str = Field(
        pattern=r"^szorliverequestmodalitybindingv1_[0-9a-f]{64}$"
    )
    operator_total_spend_ceiling_id: str = Field(
        pattern=r"^szoroperatortotalspendv1_[0-9a-f]{64}$"
    )
    proof_method_id: Literal[
        OPENROUTER_P19_PROOF_METHOD_ID_V1
    ] = OPENROUTER_P19_PROOF_METHOD_ID_V1
    formula_structure: Literal["READY"] = "READY"
    applicable_charge_coverage: Literal[
        OpenRouterChargeCoverageV1.COMPLETE
    ] = OpenRouterChargeCoverageV1.COMPLETE
    charge_components: Tuple[OpenRouterP19CostComponentV1, ...]
    formula: str
    max_input_tokens: int = Field(strict=True, gt=0)
    max_output_tokens: Literal[OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1] = (
        OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1
    )
    max_total_cost_picodollars: int = Field(strict=True, ge=0)
    operator_total_spend_picodollars: int = Field(strict=True, ge=0)
    within_operator_ceiling: bool
    authority: OpenRouterP19AuthorityV1
    bound_id: Optional[str] = Field(
        default=None, pattern=r"^szorlivecostboundv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWorstCaseCostBoundV1":
        if tuple(c.charge_class for c in self.charge_components) != (
            FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1
        ):
            raise ContractValidationError(
                "P19 charge classes must appear exactly once in frozen order"
            )
        rendered_formula = render_openrouter_p19_formula_v1(self.charge_components)
        if self.formula != rendered_formula:
            raise ContractValidationError(
                "P19 formula disagrees with the canonical component set"
            )
        included = tuple(
            component
            for component in self.charge_components
            if component.state is OpenRouterChargeClassStateV1.INCLUDED
        )
        if any(component.subtotal_picodollars is None for component in included):
            raise ContractValidationError("an included P19 term lacks a subtotal")
        subtotals = tuple(
            component.subtotal_picodollars
            for component in included
            if component.subtotal_picodollars is not None
        )
        expected_total = _checked_sum(subtotals)
        if self.max_total_cost_picodollars != expected_total:
            raise ContractValidationError(
                "P19 total disagrees with the canonical component arithmetic"
            )
        expected_within = expected_total <= self.operator_total_spend_picodollars
        if self.within_operator_ceiling is not expected_within:
            raise ContractValidationError(
                "P19 operator-ceiling comparison is not derived"
            )
        established = self.authority in (
            OpenRouterP19AuthorityV1.LIVE_JIT_ESTABLISHED,
            OpenRouterP19AuthorityV1.SYNTHETIC_TEST_ONLY,
        )
        if established is not expected_within:
            raise ContractValidationError(
                "P19 authority requires an inclusive operator-ceiling pass"
            )
        expected = stable_contract_id(
            "szorlivecostboundv1",
            self.model_dump(mode="json", exclude={"bound_id"}),
        )
        if self.bound_id not in (None, expected):
            raise ContractValidationError("P19 worst-case cost-bound ID mismatch")
        object.__setattr__(self, "bound_id", expected)
        return self


def compute_openrouter_worst_case_cost_bound_v1(
    rendered_request: OpenRouterRenderedLiveRequestV2,
    p17_proof: OpenRouterP17InputBoundProofV1,
    output_bound: OpenRouterOutputBoundEvidenceV2,
    price_policy: OpenRouterOperatorPriceCeilingV1,
    modality_binding: OpenRouterLiveRequestModalityBindingV1,
    total_spend_ceiling: OpenRouterOperatorTotalSpendCeilingV1,
) -> OpenRouterWorstCaseCostBoundV1:
    request = _exact_contract(
        rendered_request, OpenRouterRenderedLiveRequestV2, "rendered request"
    )
    p17 = _exact_contract(p17_proof, OpenRouterP17InputBoundProofV1, "P17 proof")
    output = _exact_contract(
        output_bound, OpenRouterOutputBoundEvidenceV2, "output bound"
    )
    policy = _exact_contract(
        price_policy, OpenRouterOperatorPriceCeilingV1, "price policy"
    )
    modality = _exact_contract(
        modality_binding,
        OpenRouterLiveRequestModalityBindingV1,
        "modality binding",
    )
    ceiling = _exact_contract(
        total_spend_ceiling,
        OpenRouterOperatorTotalSpendCeilingV1,
        "operator total-spend ceiling",
    )
    request_id = request.rendered_request_id or ""
    if any(
        candidate != request_id
        for candidate in (
            p17.rendered_request_id,
            output.rendered_request_id,
            modality.rendered_request_id,
            ceiling.rendered_request_id,
        )
    ):
        raise ContractValidationError("P19 evidence is bound to a sibling request")
    if any(
        candidate != request.price_policy_id
        for candidate in (
            p17.provider_price_policy_id,
            output.price_policy_id,
            modality.price_policy_id,
            policy.price_policy_id,
            ceiling.price_policy_id,
        )
    ):
        raise ContractValidationError("P19 evidence is bound to another price policy")
    if (
        p17.request_body_sha256 != request.body_sha256
        or p17.request_body_length != request.body_length
        or output.body_sha256 != request.body_sha256
        or output.body_length != request.body_length
        or modality.body_sha256 != request.body_sha256
        or modality.body_length != request.body_length
    ):
        raise ContractValidationError("P19 evidence does not bind the exact body bytes")
    if p17.max_output_tokens != output.max_output_tokens or (
        output.max_output_tokens != OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1
    ):
        raise ContractValidationError("P19 output bound is not the exact 256-token cap")
    if not modality.text_only or modality.image_parts or modality.audio_parts:
        raise ContractValidationError(
            "image/audio non-applicability requires the exact text-only proof"
        )
    if not (policy.authorized and policy.has_complete_text_request_coverage):
        raise ContractValidationError(
            "P19 requires authorized prompt/completion/request ceilings"
        )
    if not ceiling.authorized:
        raise ContractValidationError("P19 requires an authorized total-spend ceiling")
    live = policy.operator_scope is OpenRouterOperatorScopeV1.LIVE_OPERATOR
    if ceiling.operator_scope is not policy.operator_scope:
        raise ContractValidationError("P19 operator scopes disagree")
    if live != (p17.authority is OpenRouterP17ProofAuthorityV1.LIVE_JIT_ESTABLISHED):
        raise ContractValidationError("P17 and operator authority scopes disagree")

    prompt_price = policy.prompt_picodollars_per_token
    completion_price = policy.completion_picodollars_per_token
    request_fee = policy.request_picodollars
    if prompt_price is None or completion_price is None or request_fee is None:
        raise ContractValidationError(
            "P19 never promotes an absent price component to zero"
        )
    prompt_subtotal = _checked_product(
        p17.max_input_tokens,
        prompt_price,
        "prompt charge",
    )
    completion_subtotal = _checked_product(
        OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1,
        completion_price,
        "completion charge",
    )
    request_subtotal = _checked_product(1, request_fee, "request charge")
    components = (
        OpenRouterP19CostComponentV1(
            charge_class="prompt",
            state=OpenRouterChargeClassStateV1.INCLUDED,
            quantity=p17.max_input_tokens,
            quantity_unit="TOKEN",
            ceiling_picodollars_per_unit=prompt_price,
            subtotal_picodollars=prompt_subtotal,
        ),
        OpenRouterP19CostComponentV1(
            charge_class="completion",
            state=OpenRouterChargeClassStateV1.INCLUDED,
            quantity=OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1,
            quantity_unit="TOKEN",
            ceiling_picodollars_per_unit=completion_price,
            subtotal_picodollars=completion_subtotal,
        ),
        OpenRouterP19CostComponentV1(
            charge_class="request",
            state=OpenRouterChargeClassStateV1.INCLUDED,
            quantity=1,
            quantity_unit="REQUEST",
            ceiling_picodollars_per_unit=request_fee,
            subtotal_picodollars=request_subtotal,
        ),
        OpenRouterP19CostComponentV1(
            charge_class="image",
            state=OpenRouterChargeClassStateV1.NOT_APPLICABLE,
            non_applicability_proof_id=modality.modality_binding_id,
        ),
        OpenRouterP19CostComponentV1(
            charge_class="audio",
            state=OpenRouterChargeClassStateV1.NOT_APPLICABLE,
            non_applicability_proof_id=modality.modality_binding_id,
        ),
    )
    total = _checked_sum((prompt_subtotal, completion_subtotal, request_subtotal))
    within = total <= ceiling.max_spend_picodollars
    return OpenRouterWorstCaseCostBoundV1(
        rendered_request_id=request_id,
        body_sha256=request.body_sha256 or "",
        body_length=request.body_length or 0,
        p17_proof_id=p17.proof_id or "",
        output_bound_evidence_id=output.output_bound_evidence_id or "",
        price_policy_id=policy.price_policy_id or "",
        modality_binding_id=modality.modality_binding_id or "",
        operator_total_spend_ceiling_id=ceiling.ceiling_id or "",
        charge_components=components,
        formula=render_openrouter_p19_formula_v1(components),
        max_input_tokens=p17.max_input_tokens,
        max_total_cost_picodollars=total,
        operator_total_spend_picodollars=ceiling.max_spend_picodollars,
        within_operator_ceiling=within,
        authority=(
            OpenRouterP19AuthorityV1.NOT_ESTABLISHED_OVER_CEILING
            if not within
            else (
                OpenRouterP19AuthorityV1.LIVE_JIT_ESTABLISHED
                if live
                else OpenRouterP19AuthorityV1.SYNTHETIC_TEST_ONLY
            )
        ),
    )


class OpenRouterOneShotTransportPolicyV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_ONE_SHOT_TRANSPORT_POLICY_SCHEMA_V1
    ] = OPENROUTER_ONE_SHOT_TRANSPORT_POLICY_SCHEMA_V1
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(strict=True, gt=0)
    semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_headers_length: int = Field(strict=True, gt=0)
    maximum_local_dispatches: Literal[
        OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1
    ] = OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1
    automatic_retries: Literal[False] = False
    retry_after_failure: Literal[False] = False
    dispatch_strategy: Literal["DIRECT_SINGLE_REQUEST"] = "DIRECT_SINGLE_REQUEST"
    bounded_timeout_seconds: int = Field(strict=True, gt=0, le=300)
    worker_termination_enforced: Literal[True] = True
    raw_response_capture_required: Literal[True] = True
    policy_id: Optional[str] = Field(
        default=None, pattern=r"^szoroneshottransportv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOneShotTransportPolicyV1":
        expected = stable_contract_id(
            "szoroneshottransportv1",
            self.model_dump(mode="json", exclude={"policy_id"}),
        )
        if self.policy_id not in (None, expected):
            raise ContractValidationError("one-shot transport policy ID mismatch")
        object.__setattr__(self, "policy_id", expected)
        return self


def build_openrouter_one_shot_transport_policy_v1(
    rendered_request: OpenRouterRenderedLiveRequestV2,
    *,
    bounded_timeout_seconds: int,
) -> OpenRouterOneShotTransportPolicyV1:
    request = _exact_contract(
        rendered_request, OpenRouterRenderedLiveRequestV2, "rendered request"
    )
    return OpenRouterOneShotTransportPolicyV1(
        rendered_request_id=request.rendered_request_id or "",
        body_sha256=request.body_sha256 or "",
        body_length=request.body_length or 0,
        semantic_headers_sha256=request.semantic_headers_sha256 or "",
        semantic_headers_length=request.semantic_headers_length or 0,
        bounded_timeout_seconds=bounded_timeout_seconds,
    )


class OpenRouterTransportReadinessAttestationV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_TRANSPORT_READINESS_SCHEMA_V1
    ] = OPENROUTER_TRANSPORT_READINESS_SCHEMA_V1
    preflight_execution_id: str = Field(min_length=1)
    transport_policy_id: str = Field(
        pattern=r"^szoroneshottransportv1_[0-9a-f]{64}$"
    )
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    ready: bool
    maximum_local_dispatches: Literal[
        OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1
    ] = OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1
    automatic_retries: Literal[False] = False
    attestation_id: Optional[str] = Field(
        default=None, pattern=r"^szortransportreadinessv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="before")
    @classmethod
    def strict_ready(cls, data):
        if isinstance(data, dict) and "ready" in data and type(data["ready"]) is not bool:
            raise ContractValidationError("transport readiness must be an exact boolean")
        return data

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterTransportReadinessAttestationV1":
        _nonblank(self.preflight_execution_id, "transport preflight execution")
        expected = stable_contract_id(
            "szortransportreadinessv1",
            self.model_dump(mode="json", exclude={"attestation_id"}),
        )
        if self.attestation_id not in (None, expected):
            raise ContractValidationError("transport-readiness attestation ID mismatch")
        object.__setattr__(self, "attestation_id", expected)
        return self


def attest_openrouter_transport_readiness_v1(
    transport_policy: OpenRouterOneShotTransportPolicyV1,
    *,
    preflight_execution_id: str,
    ready: bool,
) -> OpenRouterTransportReadinessAttestationV1:
    policy = _exact_contract(
        transport_policy, OpenRouterOneShotTransportPolicyV1, "transport policy"
    )
    return OpenRouterTransportReadinessAttestationV1(
        preflight_execution_id=preflight_execution_id,
        transport_policy_id=policy.policy_id or "",
        rendered_request_id=policy.rendered_request_id,
        ready=ready,
    )


class OpenRouterJitCredentialPresenceAttestationV1(_FrozenLiveSafetyContractV1):
    """Presence only; no credential material or derived secret property exists."""

    schema_version: Literal[
        OPENROUTER_JIT_CREDENTIAL_PRESENCE_SCHEMA_V1
    ] = OPENROUTER_JIT_CREDENTIAL_PRESENCE_SCHEMA_V1
    preflight_execution_id: str = Field(min_length=1)
    credential_available: OpenRouterCredentialAvailabilityV1
    attestation_id: Optional[str] = Field(
        default=None, pattern=r"^szorcredentialpresencejitv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterJitCredentialPresenceAttestationV1":
        _nonblank(self.preflight_execution_id, "credential preflight execution")
        expected = stable_contract_id(
            "szorcredentialpresencejitv1",
            self.model_dump(mode="json", exclude={"attestation_id"}),
        )
        if self.attestation_id not in (None, expected):
            raise ContractValidationError("credential-presence attestation ID mismatch")
        object.__setattr__(self, "attestation_id", expected)
        return self


class OpenRouterS5MapperCapabilityV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_S5_MAPPER_CAPABILITY_SCHEMA_V1
    ] = OPENROUTER_S5_MAPPER_CAPABILITY_SCHEMA_V1
    mapping_schema: Literal[
        OPENROUTER_WIRE_MAPPING_SCHEMA_V2
    ] = OPENROUTER_WIRE_MAPPING_SCHEMA_V2
    source_manifest_id: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    source_manifest_sha256: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    guard_order_id: Literal[
        OPENROUTER_WIRE_GUARD_ORDER_ID_V2
    ] = OPENROUTER_WIRE_GUARD_ORDER_ID_V2
    available: bool = True
    capability_id: Optional[str] = Field(
        default=None, pattern=r"^szors5mapperbindingv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterS5MapperCapabilityV1":
        expected = stable_contract_id(
            "szors5mapperbindingv1",
            self.model_dump(mode="json", exclude={"capability_id"}),
        )
        if self.capability_id not in (None, expected):
            raise ContractValidationError("S5 mapper capability ID mismatch")
        object.__setattr__(self, "capability_id", expected)
        return self


class OpenRouterS6IntegrationCapabilityV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_S6_INTEGRATION_CAPABILITY_SCHEMA_V1
    ] = OPENROUTER_S6_INTEGRATION_CAPABILITY_SCHEMA_V1
    source_head: Literal[
        OPENROUTER_S6_SOURCE_HEAD_V1
    ] = OPENROUTER_S6_SOURCE_HEAD_V1
    integration_schema: Literal[
        OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1
    ] = OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1
    integration_guard_order_id: Literal[
        OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1
    ] = OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1
    safety_contract_id: Literal[
        OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1
    ] = OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1
    authoritative_artifact_id: Literal[
        OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_ID_V1
    ] = OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_ID_V1
    authoritative_artifact_sha256: Literal[
        OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_SHA256_V1
    ] = OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_SHA256_V1
    available: bool = True
    capability_id: Optional[str] = Field(
        default=None, pattern=r"^szors6integrationbindingv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterS6IntegrationCapabilityV1":
        expected = stable_contract_id(
            "szors6integrationbindingv1",
            self.model_dump(mode="json", exclude={"capability_id"}),
        )
        if self.capability_id not in (None, expected):
            raise ContractValidationError("S6 integration capability ID mismatch")
        object.__setattr__(self, "capability_id", expected)
        return self


FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1 = OpenRouterS5MapperCapabilityV1()
OPENROUTER_S5_MAPPER_CAPABILITY_ID_V1 = (
    FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1.capability_id
)
FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1 = (
    OpenRouterS6IntegrationCapabilityV1()
)
OPENROUTER_S6_INTEGRATION_CAPABILITY_ID_V1 = (
    FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1.capability_id
)


class OpenRouterOneCallAuthorizationV1(_FrozenLiveSafetyContractV1):
    """Immutable semantic authorization for one exact local dispatch."""

    schema_version: Literal[
        OPENROUTER_ONE_CALL_AUTHORIZATION_SCHEMA_V1
    ] = OPENROUTER_ONE_CALL_AUTHORIZATION_SCHEMA_V1
    authorization_scope: OpenRouterAuthorizationScopeV1
    preflight_execution_id: str = Field(min_length=1)
    live_request_overlay_id: str = Field(
        pattern=r"^szorliverequestoverlayv2_[0-9a-f]{64}$"
    )
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(strict=True, gt=0)
    p17_proof_id: str = Field(pattern=r"^szorp17inputboundproofv1_[0-9a-f]{64}$")
    output_bound_evidence_id: str = Field(
        pattern=r"^szoroutputboundv2_[0-9a-f]{64}$"
    )
    price_policy_id: str = Field(
        pattern=r"^szoroperatorpriceceilingv1_[0-9a-f]{64}$"
    )
    p19_cost_bound_id: str = Field(
        pattern=r"^szorlivecostboundv1_[0-9a-f]{64}$"
    )
    operator_total_spend_ceiling_id: str = Field(
        pattern=r"^szoroperatortotalspendv1_[0-9a-f]{64}$"
    )
    transport_policy_id: str = Field(
        pattern=r"^szoroneshottransportv1_[0-9a-f]{64}$"
    )
    s5_mapper_capability_id: str = Field(
        pattern=r"^szors5mapperbindingv1_[0-9a-f]{64}$"
    )
    s6_integration_capability_id: str = Field(
        pattern=r"^szors6integrationbindingv1_[0-9a-f]{64}$"
    )
    operator_grant_binding_id: str = Field(
        pattern=r"^szoroperatorgrantbindingv1_[0-9a-f]{64}$"
    )
    allowed_local_dispatches: Literal[
        OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1
    ] = OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1
    automatic_retries: Literal[False] = False
    ced_authority_enabled: Literal[False] = False
    runtime_authority_enabled: Literal[False] = False
    authorization_state: Literal["FRESH"] = "FRESH"
    authorization_id: Optional[str] = Field(
        default=None, pattern=r"^szoronecallauthorizationv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOneCallAuthorizationV1":
        _nonblank(self.preflight_execution_id, "authorization preflight execution")
        # Credential presence is deliberately absent from both fields and ID.
        expected = stable_contract_id(
            "szoronecallauthorizationv1",
            self.model_dump(mode="json", exclude={"authorization_id"}),
        )
        if self.authorization_id not in (None, expected):
            raise ContractValidationError("one-call authorization ID mismatch")
        object.__setattr__(self, "authorization_id", expected)
        return self


def mint_openrouter_one_call_authorization_v1(
    *,
    mode: OpenRouterLiveSafetyModeV1,
    preflight_execution_id: str,
    rendered_request: OpenRouterRenderedLiveRequestV2,
    p17_proof: OpenRouterP17InputBoundProofV1,
    output_bound: OpenRouterOutputBoundEvidenceV2,
    price_policy: OpenRouterOperatorPriceCeilingV1,
    cost_bound: OpenRouterWorstCaseCostBoundV1,
    total_spend_ceiling: OpenRouterOperatorTotalSpendCeilingV1,
    transport_policy: OpenRouterOneShotTransportPolicyV1,
    s5_mapper: OpenRouterS5MapperCapabilityV1,
    s6_integration: OpenRouterS6IntegrationCapabilityV1,
) -> OpenRouterOneCallAuthorizationV1:
    request = _exact_contract(
        rendered_request, OpenRouterRenderedLiveRequestV2, "rendered request"
    )
    p17 = _exact_contract(p17_proof, OpenRouterP17InputBoundProofV1, "P17 proof")
    output = _exact_contract(
        output_bound, OpenRouterOutputBoundEvidenceV2, "output bound"
    )
    policy = _exact_contract(
        price_policy, OpenRouterOperatorPriceCeilingV1, "price policy"
    )
    cost = _exact_contract(
        cost_bound, OpenRouterWorstCaseCostBoundV1, "P19 cost bound"
    )
    total_ceiling = _exact_contract(
        total_spend_ceiling,
        OpenRouterOperatorTotalSpendCeilingV1,
        "operator total-spend ceiling",
    )
    transport = _exact_contract(
        transport_policy, OpenRouterOneShotTransportPolicyV1, "transport policy"
    )
    mapper = _exact_contract(s5_mapper, OpenRouterS5MapperCapabilityV1, "S5 mapper")
    integration = _exact_contract(
        s6_integration, OpenRouterS6IntegrationCapabilityV1, "S6 integration"
    )
    if type(mode) is not OpenRouterLiveSafetyModeV1:
        raise ContractValidationError("authorization mode must use the exact enum")
    if p17.preflight_execution_id != preflight_execution_id:
        raise ContractValidationError("P17 proof belongs to another preflight")
    request_id = request.rendered_request_id or ""
    if any(
        candidate != request_id
        for candidate in (
            p17.rendered_request_id,
            output.rendered_request_id,
            cost.rendered_request_id,
            total_ceiling.rendered_request_id,
            transport.rendered_request_id,
        )
    ):
        raise ContractValidationError("authorization evidence is request-mixed")
    if any(
        candidate != policy.price_policy_id
        for candidate in (
            p17.provider_price_policy_id,
            output.price_policy_id,
            cost.price_policy_id,
            total_ceiling.price_policy_id,
        )
    ):
        raise ContractValidationError("authorization evidence is policy-mixed")
    if cost.p17_proof_id != p17.proof_id or (
        cost.output_bound_evidence_id != output.output_bound_evidence_id
    ):
        raise ContractValidationError("authorization cost evidence is mismatched")
    if cost.operator_total_spend_ceiling_id != total_ceiling.ceiling_id:
        raise ContractValidationError("authorization total-spend evidence is mismatched")
    if not (mapper.available and integration.available):
        raise ContractValidationError("authorization requires S5 and S6 capabilities")
    if not cost.within_operator_ceiling:
        raise ContractValidationError("authorization cost exceeds operator total spend")
    live = mode is OpenRouterLiveSafetyModeV1.LIVE_JIT
    if live:
        if not (
            p17.authority is OpenRouterP17ProofAuthorityV1.LIVE_JIT_ESTABLISHED
            and policy.operator_scope is OpenRouterOperatorScopeV1.LIVE_OPERATOR
            and total_ceiling.operator_scope is OpenRouterOperatorScopeV1.LIVE_OPERATOR
            and cost.authority is OpenRouterP19AuthorityV1.LIVE_JIT_ESTABLISHED
        ):
            raise ContractValidationError("live authorization cannot use synthetic facts")
    else:
        if not (
            p17.authority is OpenRouterP17ProofAuthorityV1.SYNTHETIC_TEST_ONLY
            and policy.operator_scope is OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE
            and total_ceiling.operator_scope is OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE
            and cost.authority is OpenRouterP19AuthorityV1.SYNTHETIC_TEST_ONLY
        ):
            raise ContractValidationError("synthetic authorization cannot mix live facts")
    grant_binding_id = stable_contract_id(
        "szoroperatorgrantbindingv1",
        {
            "price_authorization_evidence_id": policy.authorization_evidence_id,
            "total_spend_authorization_evidence_id": (
                total_ceiling.authorization_evidence_id
            ),
            "price_policy_id": policy.price_policy_id,
            "total_spend_ceiling_id": total_ceiling.ceiling_id,
        },
    )
    return OpenRouterOneCallAuthorizationV1(
        authorization_scope=(
            OpenRouterAuthorizationScopeV1.LIVE_JIT
            if live
            else OpenRouterAuthorizationScopeV1.SYNTHETIC_OFFLINE_ONLY
        ),
        preflight_execution_id=preflight_execution_id,
        live_request_overlay_id=request.live_request_overlay_id,
        rendered_request_id=request_id,
        body_sha256=request.body_sha256 or "",
        body_length=request.body_length or 0,
        p17_proof_id=p17.proof_id or "",
        output_bound_evidence_id=output.output_bound_evidence_id or "",
        price_policy_id=policy.price_policy_id or "",
        p19_cost_bound_id=cost.bound_id or "",
        operator_total_spend_ceiling_id=total_ceiling.ceiling_id or "",
        transport_policy_id=transport.policy_id or "",
        s5_mapper_capability_id=mapper.capability_id or "",
        s6_integration_capability_id=integration.capability_id or "",
        operator_grant_binding_id=grant_binding_id,
    )


class OpenRouterOneCallConsumptionV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_ONE_CALL_CONSUMPTION_SCHEMA_V1
    ] = OPENROUTER_ONE_CALL_CONSUMPTION_SCHEMA_V1
    authorization_id: str = Field(
        pattern=r"^szoronecallauthorizationv1_[0-9a-f]{64}$"
    )
    rendered_request_id: str = Field(
        pattern=r"^szorrenderedliverequestv2_[0-9a-f]{64}$"
    )
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    transport_policy_id: str = Field(
        pattern=r"^szoroneshottransportv1_[0-9a-f]{64}$"
    )
    p19_cost_bound_id: str = Field(
        pattern=r"^szorlivecostboundv1_[0-9a-f]{64}$"
    )
    operator_grant_binding_id: str = Field(
        pattern=r"^szoroperatorgrantbindingv1_[0-9a-f]{64}$"
    )
    dispatch_ordinal: Literal[1] = 1
    consumed_before_network: Literal[True] = True
    failed_call_does_not_restore_authorization: Literal[True] = True
    consumption_state: Literal["CONSUMED"] = "CONSUMED"
    consumption_id: Optional[str] = Field(
        default=None, pattern=r"^szoronecallconsumptionv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterOneCallConsumptionV1":
        expected = stable_contract_id(
            "szoronecallconsumptionv1",
            self.model_dump(mode="json", exclude={"consumption_id"}),
        )
        if self.consumption_id not in (None, expected):
            raise ContractValidationError("one-call consumption ID mismatch")
        object.__setattr__(self, "consumption_id", expected)
        return self


def render_openrouter_one_call_consumption_v1(
    consumption: OpenRouterOneCallConsumptionV1,
) -> bytes:
    record = _exact_contract(
        consumption, OpenRouterOneCallConsumptionV1, "consumption record"
    )
    return canonical_json(record.model_dump(mode="json")).encode("utf-8") + b"\n"


def openrouter_authorization_claim_path_v1(
    claim_directory: Path, authorization_id: str
) -> Path:
    if type(authorization_id) is not str or not authorization_id.startswith(
        "szoronecallauthorizationv1_"
    ) or len(authorization_id) != len("szoronecallauthorizationv1_") + 64:
        raise ContractValidationError("invalid authorization ID for consumption")
    suffix = authorization_id.rsplit("_", 1)[-1]
    if any(character not in "0123456789abcdef" for character in suffix):
        raise ContractValidationError("invalid authorization ID digest")
    return Path(claim_directory) / f"{authorization_id}.consumed.json"


def openrouter_authorization_is_consumed_v1(
    claim_directory: Path, authorization_id: str
) -> bool:
    return openrouter_authorization_claim_path_v1(
        claim_directory, authorization_id
    ).exists()


def consume_openrouter_one_call_authorization_v1(
    authorization: OpenRouterOneCallAuthorizationV1,
    *,
    claim_directory: Path,
    rendered_request: OpenRouterRenderedLiveRequestV2,
    transport_policy: OpenRouterOneShotTransportPolicyV1,
) -> OpenRouterOneCallConsumptionV1:
    """Atomically burn one authorization before any future network attempt.

    Exclusive creation is intentionally non-idempotent: an existing claim is a
    refusal even when its bytes are identical.  A provider failure after this
    point does not remove or restore the claim.
    """

    auth = _exact_contract(
        authorization, OpenRouterOneCallAuthorizationV1, "authorization"
    )
    request = _exact_contract(
        rendered_request, OpenRouterRenderedLiveRequestV2, "rendered request"
    )
    transport = _exact_contract(
        transport_policy, OpenRouterOneShotTransportPolicyV1, "transport policy"
    )
    if (
        auth.rendered_request_id != request.rendered_request_id
        or auth.body_sha256 != request.body_sha256
        or auth.body_length != request.body_length
    ):
        raise ContractValidationError("authorization cannot consume a sibling request")
    if (
        auth.transport_policy_id != transport.policy_id
        or transport.rendered_request_id != request.rendered_request_id
    ):
        raise ContractValidationError("authorization cannot consume sibling transport")
    record = OpenRouterOneCallConsumptionV1(
        authorization_id=auth.authorization_id or "",
        rendered_request_id=auth.rendered_request_id,
        body_sha256=auth.body_sha256,
        transport_policy_id=auth.transport_policy_id,
        p19_cost_bound_id=auth.p19_cost_bound_id,
        operator_grant_binding_id=auth.operator_grant_binding_id,
    )
    target = openrouter_authorization_claim_path_v1(
        Path(claim_directory), auth.authorization_id or ""
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = render_openrouter_one_call_consumption_v1(record)
    try:
        with target.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise ContractValidationError(
            "authorization already consumed; no automatic retry is allowed"
        ) from exc
    return record


class OpenRouterOneLiveCallPreflightResultV1(_FrozenLiveSafetyContractV1):
    schema_version: Literal[
        OPENROUTER_ONE_LIVE_CALL_PREFLIGHT_RESULT_SCHEMA_V1
    ] = OPENROUTER_ONE_LIVE_CALL_PREFLIGHT_RESULT_SCHEMA_V1
    preflight_execution_id: str = Field(min_length=1)
    mode: OpenRouterLiveSafetyModeV1
    verdict: OpenRouterOneLiveCallVerdictV1
    first_failure_code: Optional[OpenRouterOneLiveCallFailureCodeV1] = None
    authorization: Optional[OpenRouterOneCallAuthorizationV1] = None
    authorization_id: Optional[str] = None
    network_dispatches: Literal[0] = 0
    result_id: Optional[str] = Field(
        default=None, pattern=r"^szoronecallpreflightresultv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterOneLiveCallPreflightResultV1":
        _nonblank(self.preflight_execution_id, "preflight execution")
        authorized = self.verdict is (
            OpenRouterOneLiveCallVerdictV1.AUTHORIZED_FOR_ONE_CALL
        )
        if authorized:
            if self.first_failure_code is not None or self.authorization is None:
                raise ContractValidationError(
                    "authorized preflight must carry exactly one authorization"
                )
            auth = _exact_contract(
                self.authorization,
                OpenRouterOneCallAuthorizationV1,
                "preflight authorization",
            )
            object.__setattr__(self, "authorization", auth)
            if self.authorization_id not in (None, auth.authorization_id):
                raise ContractValidationError("preflight authorization ID mismatch")
            object.__setattr__(self, "authorization_id", auth.authorization_id)
        elif (
            self.first_failure_code is None
            or self.authorization is not None
            or self.authorization_id is not None
        ):
            raise ContractValidationError(
                "refused preflight must carry one failure and no authorization"
            )
        expected = stable_contract_id(
            "szoronecallpreflightresultv1",
            self.model_dump(mode="json", exclude={"result_id"}),
        )
        if self.result_id not in (None, expected):
            raise ContractValidationError("one-call preflight result ID mismatch")
        object.__setattr__(self, "result_id", expected)
        return self


def _refused_preflight_v1(
    preflight_execution_id: str,
    mode: OpenRouterLiveSafetyModeV1,
    code: OpenRouterOneLiveCallFailureCodeV1,
) -> OpenRouterOneLiveCallPreflightResultV1:
    return OpenRouterOneLiveCallPreflightResultV1(
        preflight_execution_id=preflight_execution_id,
        mode=mode,
        verdict=OpenRouterOneLiveCallVerdictV1.REFUSED,
        first_failure_code=code,
    )


def evaluate_one_live_call_preflight_v1(
    *,
    mode: OpenRouterLiveSafetyModeV1,
    preflight_execution_id: str,
    rendered_request: OpenRouterRenderedLiveRequestV2,
    p17_proof: OpenRouterP17InputBoundProofV1,
    output_bound: OpenRouterOutputBoundEvidenceV2,
    price_policy: OpenRouterOperatorPriceCeilingV1,
    modality_binding: OpenRouterLiveRequestModalityBindingV1,
    cost_bound: OpenRouterWorstCaseCostBoundV1,
    total_spend_ceiling: OpenRouterOperatorTotalSpendCeilingV1,
    credential_presence: OpenRouterJitCredentialPresenceAttestationV1,
    transport_policy: OpenRouterOneShotTransportPolicyV1,
    transport_readiness: OpenRouterTransportReadinessAttestationV1,
    s5_mapper: OpenRouterS5MapperCapabilityV1,
    s6_integration: OpenRouterS6IntegrationCapabilityV1,
    claim_directory: Path,
    ced_authority_enabled: bool = False,
    runtime_authority_enabled: bool = False,
) -> OpenRouterOneLiveCallPreflightResultV1:
    """Return one authorization or the deterministic first refusal.

    Cost is evaluated before credential presence.  Every refusal returns with
    ``network_dispatches = 0``; this function has no dispatch capability.
    """

    if type(mode) is not OpenRouterLiveSafetyModeV1:
        raise ContractValidationError("preflight mode must use the exact enum")
    _nonblank(preflight_execution_id, "preflight execution")
    exact_inputs = (
        (rendered_request, OpenRouterRenderedLiveRequestV2),
        (p17_proof, OpenRouterP17InputBoundProofV1),
        (output_bound, OpenRouterOutputBoundEvidenceV2),
        (price_policy, OpenRouterOperatorPriceCeilingV1),
        (modality_binding, OpenRouterLiveRequestModalityBindingV1),
        (cost_bound, OpenRouterWorstCaseCostBoundV1),
        (total_spend_ceiling, OpenRouterOperatorTotalSpendCeilingV1),
        (credential_presence, OpenRouterJitCredentialPresenceAttestationV1),
        (transport_policy, OpenRouterOneShotTransportPolicyV1),
        (transport_readiness, OpenRouterTransportReadinessAttestationV1),
        (s5_mapper, OpenRouterS5MapperCapabilityV1),
        (s6_integration, OpenRouterS6IntegrationCapabilityV1),
    )
    if any(type(value) is not expected for value, expected in exact_inputs):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.SAFETY_CONTRACT_MISMATCH,
        )
    try:
        request = _exact_contract(
            rendered_request, OpenRouterRenderedLiveRequestV2, "rendered request"
        )
        p17 = _exact_contract(p17_proof, OpenRouterP17InputBoundProofV1, "P17 proof")
        output = _exact_contract(
            output_bound, OpenRouterOutputBoundEvidenceV2, "output bound"
        )
        policy = _exact_contract(
            price_policy, OpenRouterOperatorPriceCeilingV1, "price policy"
        )
        modality = _exact_contract(
            modality_binding,
            OpenRouterLiveRequestModalityBindingV1,
            "modality binding",
        )
        cost = _exact_contract(
            cost_bound, OpenRouterWorstCaseCostBoundV1, "P19 cost bound"
        )
        total_ceiling = _exact_contract(
            total_spend_ceiling,
            OpenRouterOperatorTotalSpendCeilingV1,
            "operator total-spend ceiling",
        )
        credential = _exact_contract(
            credential_presence,
            OpenRouterJitCredentialPresenceAttestationV1,
            "credential presence",
        )
        transport = _exact_contract(
            transport_policy,
            OpenRouterOneShotTransportPolicyV1,
            "transport policy",
        )
        readiness = _exact_contract(
            transport_readiness,
            OpenRouterTransportReadinessAttestationV1,
            "transport readiness",
        )
        mapper = _exact_contract(
            s5_mapper, OpenRouterS5MapperCapabilityV1, "S5 mapper"
        )
        integration = _exact_contract(
            s6_integration, OpenRouterS6IntegrationCapabilityV1, "S6 integration"
        )
    except (ContractValidationError, ValueError, TypeError):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.SAFETY_CONTRACT_MISMATCH,
        )

    request_id = request.rendered_request_id or ""
    if any(
        candidate != request_id
        for candidate in (
            p17.rendered_request_id,
            output.rendered_request_id,
            modality.rendered_request_id,
            cost.rendered_request_id,
            total_ceiling.rendered_request_id,
            transport.rendered_request_id,
            readiness.rendered_request_id,
        )
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.REQUEST_IDENTITY_MISMATCH,
        )
    if not modality.text_only or modality.image_parts or modality.audio_parts:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.MODALITY_PROOF_MISMATCH,
        )
    if p17.preflight_execution_id != preflight_execution_id:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.P17_NOT_JIT_FRESH,
        )
    live = mode is OpenRouterLiveSafetyModeV1.LIVE_JIT
    if live and p17.limit_record.source_scope is not (
        OpenRouterInputLimitSourceScopeV1.LIVE_JIT_SAME_PREFLIGHT
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.P17_SOURCE_UNTRUSTED,
        )
    if live != (p17.authority is OpenRouterP17ProofAuthorityV1.LIVE_JIT_ESTABLISHED):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.P17_NOT_ESTABLISHED,
        )
    if (
        output.max_output_tokens != OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1
        or output.body_sha256 != request.body_sha256
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.OUTPUT_BOUND_NOT_ESTABLISHED,
        )
    expected_scope = (
        OpenRouterOperatorScopeV1.LIVE_OPERATOR
        if live
        else OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE
    )
    if (
        policy.operator_scope is not expected_scope
        or not policy.authorized
        or not policy.has_complete_text_request_coverage
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.PRICE_POLICY_NOT_AUTHORIZED,
        )
    if any(
        candidate != policy.price_policy_id
        for candidate in (
            request.price_policy_id,
            p17.provider_price_policy_id,
            output.price_policy_id,
            modality.price_policy_id,
            cost.price_policy_id,
            total_ceiling.price_policy_id,
        )
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.PRICE_POLICY_MISMATCH,
        )
    if (
        cost.p17_proof_id != p17.proof_id
        or cost.output_bound_evidence_id != output.output_bound_evidence_id
        or cost.modality_binding_id != modality.modality_binding_id
        or cost.operator_total_spend_ceiling_id != total_ceiling.ceiling_id
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.COST_BOUND_MISMATCH,
        )
    if not total_ceiling.authorized or total_ceiling.operator_scope is not expected_scope:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.TOTAL_SPEND_CEILING_MISSING,
        )
    if not cost.within_operator_ceiling:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.COST_EXCEEDS_TOTAL_SPEND_CEILING,
        )
    if (
        credential.preflight_execution_id != preflight_execution_id
        or credential.credential_available is not OpenRouterCredentialAvailabilityV1.YES
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.CREDENTIAL_ATTESTATION_MISSING,
        )
    if (
        readiness.preflight_execution_id != preflight_execution_id
        or readiness.transport_policy_id != transport.policy_id
        or not readiness.ready
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.TRANSPORT_NOT_READY,
        )
    if transport.maximum_local_dispatches != 1 or transport.automatic_retries:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.TRANSPORT_DISPATCH_CAP_INVALID,
        )
    if not mapper.available or mapper.capability_id != (
        OPENROUTER_S5_MAPPER_CAPABILITY_ID_V1
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.S5_MAPPER_UNAVAILABLE,
        )
    if not integration.available or integration.capability_id != (
        OPENROUTER_S6_INTEGRATION_CAPABILITY_ID_V1
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.S6_INTEGRATION_UNAVAILABLE,
        )
    if type(ced_authority_enabled) is not bool or type(runtime_authority_enabled) is not bool:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.SAFETY_CONTRACT_MISMATCH,
        )
    if ced_authority_enabled or runtime_authority_enabled:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.CED_AUTHORITY_ENABLED,
        )
    try:
        authorization = mint_openrouter_one_call_authorization_v1(
            mode=mode,
            preflight_execution_id=preflight_execution_id,
            rendered_request=request,
            p17_proof=p17,
            output_bound=output,
            price_policy=policy,
            cost_bound=cost,
            total_spend_ceiling=total_ceiling,
            transport_policy=transport,
            s5_mapper=mapper,
            s6_integration=integration,
        )
    except ContractValidationError:
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.SAFETY_CONTRACT_MISMATCH,
        )
    if openrouter_authorization_is_consumed_v1(
        Path(claim_directory), authorization.authorization_id or ""
    ):
        return _refused_preflight_v1(
            preflight_execution_id,
            mode,
            OpenRouterOneLiveCallFailureCodeV1.AUTHORIZATION_ALREADY_CONSUMED,
        )
    return OpenRouterOneLiveCallPreflightResultV1(
        preflight_execution_id=preflight_execution_id,
        mode=mode,
        verdict=OpenRouterOneLiveCallVerdictV1.AUTHORIZED_FOR_ONE_CALL,
        authorization=authorization,
        authorization_id=authorization.authorization_id,
    )


__all__ = [
    "FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1",
    "FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1",
    "FROZEN_OPENROUTER_P19_FORMULA_TERMS_V1",
    "FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1",
    "FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1",
    "OPENROUTER_JIT_CREDENTIAL_PRESENCE_SCHEMA_V1",
    "OPENROUTER_MAX_AUTHORIZED_DISPATCHES_V1",
    "OPENROUTER_MAX_OUTPUT_TOKENS_LIVE_V1",
    "OPENROUTER_ONE_CALL_AUTHORIZATION_SCHEMA_V1",
    "OPENROUTER_ONE_CALL_CONSUMPTION_SCHEMA_V1",
    "OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1",
    "OPENROUTER_ONE_LIVE_CALL_PREFLIGHT_RESULT_SCHEMA_V1",
    "OPENROUTER_ONE_SHOT_TRANSPORT_POLICY_SCHEMA_V1",
    "OPENROUTER_OPERATOR_TOTAL_SPEND_SCHEMA_V1",
    "OPENROUTER_P19_COST_BOUND_SCHEMA_V1",
    "OPENROUTER_P19_COST_COMPONENT_SCHEMA_V1",
    "OPENROUTER_P19_PROOF_METHOD_ID_V1",
    "OPENROUTER_S5_MAPPER_CAPABILITY_ID_V1",
    "OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_ID_V1",
    "OPENROUTER_S6_AUTHORITATIVE_ARTIFACT_SHA256_V1",
    "OPENROUTER_S6_INTEGRATION_CAPABILITY_ID_V1",
    "OPENROUTER_S6_SOURCE_HEAD_V1",
    "OPENROUTER_TRANSPORT_READINESS_SCHEMA_V1",
    "OpenRouterAuthorizationScopeV1",
    "OpenRouterCredentialAvailabilityV1",
    "OpenRouterJitCredentialPresenceAttestationV1",
    "OpenRouterLiveSafetyModeV1",
    "OpenRouterOneCallAuthorizationV1",
    "OpenRouterOneCallConsumptionV1",
    "OpenRouterOneLiveCallFailureCodeV1",
    "OpenRouterOneLiveCallPreflightResultV1",
    "OpenRouterOneLiveCallVerdictV1",
    "OpenRouterOneShotTransportPolicyV1",
    "OpenRouterOperatorTotalSpendCeilingV1",
    "OpenRouterP19AuthorityV1",
    "OpenRouterP19CostComponentV1",
    "OpenRouterS5MapperCapabilityV1",
    "OpenRouterS6IntegrationCapabilityV1",
    "OpenRouterTransportReadinessAttestationV1",
    "OpenRouterWorstCaseCostBoundV1",
    "attest_openrouter_transport_readiness_v1",
    "build_openrouter_one_shot_transport_policy_v1",
    "build_openrouter_operator_total_spend_ceiling_v1",
    "compute_openrouter_worst_case_cost_bound_v1",
    "consume_openrouter_one_call_authorization_v1",
    "evaluate_one_live_call_preflight_v1",
    "mint_openrouter_one_call_authorization_v1",
    "openrouter_authorization_claim_path_v1",
    "openrouter_authorization_is_consumed_v1",
    "render_openrouter_one_call_consumption_v1",
    "render_openrouter_p19_formula_v1",
]

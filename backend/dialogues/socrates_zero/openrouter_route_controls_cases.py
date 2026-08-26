"""Frozen, data-only case design for OpenRouter route controls v1.

This module owns evaluator-side labels, first-guard precedence, declared
mutation vectors, and strict offline thresholds.  It deliberately imports no
renderer, parser, transport, provider, environment, credential, model, tool,
evaluation, or canonical-application path.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id


OPENROUTER_ROUTE_CONTROL_CASE_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-case/v1"
)
OPENROUTER_ROUTE_CONTROL_CASE_SET_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-case-set/v1"
)
OPENROUTER_ROUTE_CONTROL_GUARD_DESIGN_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-guard-design/v1"
)
OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-validation-order/v1"
)
OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-failure-taxonomy/v1"
)
OPENROUTER_ROUTE_CONTROL_MUTATION_VECTOR_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-mutation-vector/v1"
)
OPENROUTER_ROUTE_CONTROL_LITERAL_MUTATION_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-literal-mutation/v1"
)
OPENROUTER_ROUTE_CONTROL_THRESHOLDS_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-thresholds/v1"
)
OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1 = (
    "socrateszero-openrouter-route-control-harness/v1"
)
OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1 = (
    "socrateszero-openrouter-route-control-metrics/v1"
)
OPENROUTER_ROUTE_CONTROL_EVALUATOR_EXPECTATION_ROLE_V1 = (
    "EVALUATOR_ONLY_GROUND_TRUTH_NOT_CANDIDATE_AUTHORITY"
)
FIRST_ROUTE_CONTROL_GUARD_WINS_V1 = "FIRST_ROUTE_CONTROL_GUARD_WINS"


class _FrozenCaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MutationState(str, Enum):
    PRESERVED = "PRESERVED"
    INTENTIONALLY_CHANGED = "INTENTIONALLY_CHANGED"
    DEPENDENTLY_CHANGED = "DEPENDENTLY_CHANGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OpenRouterRouteControlCaseKind(str, Enum):
    POSITIVE_REQUEST = "POSITIVE_REQUEST"
    POSITIVE_RESPONSE = "POSITIVE_RESPONSE"
    ORTHOGONAL_REQUEST = "ORTHOGONAL_REQUEST"
    ORTHOGONAL_RESPONSE = "ORTHOGONAL_RESPONSE"
    PRECEDENCE = "PRECEDENCE"


class OpenRouterRouteControlExpectedOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class OpenRouterRouteControlGuardStage(str, Enum):
    PRE_DISPATCH = "PRE_DISPATCH"
    POST_RESPONSE = "POST_RESPONSE"


class OpenRouterRouteControlGuardId(str, Enum):
    G01_SPECIFICATION_MANIFEST_INTEGRITY = "G01_SPECIFICATION_MANIFEST_INTEGRITY"
    G02_ROUTE_POLICY_INTEGRITY = "G02_ROUTE_POLICY_INTEGRITY"
    G03_EXACT_MODEL = "G03_EXACT_MODEL"
    G04_MODELS_ABSENT = "G04_MODELS_ABSENT"
    G05_PROVIDER_OBJECT_SCHEMA = "G05_PROVIDER_OBJECT_SCHEMA"
    G06_EXACT_SINGLETON_ENDPOINT = "G06_EXACT_SINGLETON_ENDPOINT"
    G07_PROVIDER_ORDER_EXACT = "G07_PROVIDER_ORDER_EXACT"
    G08_PROVIDER_FALLBACK_FALSE = "G08_PROVIDER_FALLBACK_FALSE"
    G09_REQUIRE_PARAMETERS_TRUE = "G09_REQUIRE_PARAMETERS_TRUE"
    G10_MAX_PRICE_ABSENT = "G10_MAX_PRICE_ABSENT"
    G11_STREAM_FALSE = "G11_STREAM_FALSE"
    G12_TOOLS_DISABLED = "G12_TOOLS_DISABLED"
    G13_METADATA_HEADER = "G13_METADATA_HEADER"
    G14_CACHE_HEADER = "G14_CACHE_HEADER"
    G15_CANONICAL_BYTES = "G15_CANONICAL_BYTES"
    G16_ENTROPY_FIREWALL = "G16_ENTROPY_FIREWALL"
    G17_CANNED_REGISTRATION = "G17_CANNED_REGISTRATION"
    G18_TRANSPORT_COMPLETION = "G18_TRANSPORT_COMPLETION"
    G19_RAW_ENVELOPE_PRESENCE = "G19_RAW_ENVELOPE_PRESENCE"
    G20_METADATA_PRESENCE = "G20_METADATA_PRESENCE"
    G21_METADATA_SCHEMA = "G21_METADATA_SCHEMA"
    G22_CACHE_METADATA_AVAILABILITY = "G22_CACHE_METADATA_AVAILABILITY"
    G23_ATTEMPT_VALIDITY = "G23_ATTEMPT_VALIDITY"
    G24_ATTEMPT_ONE = "G24_ATTEMPT_ONE"
    G25_ACTUAL_MODEL_PRESENCE = "G25_ACTUAL_MODEL_PRESENCE"
    G26_ACTUAL_MODEL_MATCH = "G26_ACTUAL_MODEL_MATCH"
    G27_PROVIDER_PRESENCE = "G27_PROVIDER_PRESENCE"
    G28_PROVIDER_COMPATIBILITY = "G28_PROVIDER_COMPATIBILITY"
    G29_ATTEMPTS_CONSISTENCY = "G29_ATTEMPTS_CONSISTENCY"
    G30_FALLBACK_PIPELINE_ABSENCE = "G30_FALLBACK_PIPELINE_ABSENCE"
    G31_EXACT_ENDPOINT_CLAIM_FIREWALL = "G31_EXACT_ENDPOINT_CLAIM_FIREWALL"
    G32_RECEIPT_AND_CLAIMS_INTEGRITY = "G32_RECEIPT_AND_CLAIMS_INTEGRITY"

    # Parser-facing aliases preserve one frozen semantic value per guard.
    RC18_TRANSPORT_COMPLETION = G18_TRANSPORT_COMPLETION
    RC19_RAW_ENVELOPE_PRESENCE = G19_RAW_ENVELOPE_PRESENCE
    RC20_METADATA_PRESENCE = G20_METADATA_PRESENCE
    RC21_METADATA_SCHEMA = G21_METADATA_SCHEMA
    RC22_CACHE_METADATA_AVAILABILITY = G22_CACHE_METADATA_AVAILABILITY
    RC23_ATTEMPT_VALIDITY = G23_ATTEMPT_VALIDITY
    RC24_ATTEMPT_ONE = G24_ATTEMPT_ONE
    RC25_ACTUAL_MODEL_PRESENCE = G25_ACTUAL_MODEL_PRESENCE
    RC26_ACTUAL_MODEL_MATCH = G26_ACTUAL_MODEL_MATCH
    RC27_PROVIDER_PRESENCE = G27_PROVIDER_PRESENCE
    RC28_PROVIDER_COMPATIBILITY = G28_PROVIDER_COMPATIBILITY
    RC29_ATTEMPTS_CONSISTENCY = G29_ATTEMPTS_CONSISTENCY
    RC30_FALLBACK_ABSENCE = G30_FALLBACK_PIPELINE_ABSENCE
    RC31_EXACT_ENDPOINT_CLAIM_FIREWALL = G31_EXACT_ENDPOINT_CLAIM_FIREWALL
    RC32_RECEIPT_INTEGRITY = G32_RECEIPT_AND_CLAIMS_INTEGRITY


class OpenRouterRouteControlFailureCode(str, Enum):
    SPECIFICATION_MANIFEST_MISMATCH = "SPECIFICATION_MANIFEST_MISMATCH"
    ROUTE_POLICY_MISMATCH = "ROUTE_POLICY_MISMATCH"
    EXACT_MODEL_MISSING = "EXACT_MODEL_MISSING"
    EXACT_MODEL_MISMATCH = "EXACT_MODEL_MISMATCH"
    MODELS_FIELD_PRESENT = "MODELS_FIELD_PRESENT"
    PROVIDER_OBJECT_MISSING = "PROVIDER_OBJECT_MISSING"
    PROVIDER_SCHEMA_INVALID = "PROVIDER_SCHEMA_INVALID"
    ENDPOINT_RESTRICTION_MISSING = "ENDPOINT_RESTRICTION_MISSING"
    ENDPOINT_SELECTOR_NOT_SINGLETON = "ENDPOINT_SELECTOR_NOT_SINGLETON"
    ENDPOINT_SELECTOR_DUPLICATED = "ENDPOINT_SELECTOR_DUPLICATED"
    ENDPOINT_SELECTOR_MISMATCH = "ENDPOINT_SELECTOR_MISMATCH"
    ENDPOINT_SELECTOR_WILDCARD_FORBIDDEN = "ENDPOINT_SELECTOR_WILDCARD_FORBIDDEN"
    BASE_PROVIDER_SELECTOR_FORBIDDEN = "BASE_PROVIDER_SELECTOR_FORBIDDEN"
    PROVIDER_ORDER_MISSING = "PROVIDER_ORDER_MISSING"
    PROVIDER_ORDER_NOT_SINGLETON = "PROVIDER_ORDER_NOT_SINGLETON"
    PROVIDER_ORDER_MISMATCH = "PROVIDER_ORDER_MISMATCH"
    PROVIDER_FALLBACK_ENABLED = "PROVIDER_FALLBACK_ENABLED"
    PROVIDER_FALLBACK_POLICY_MISSING = "PROVIDER_FALLBACK_POLICY_MISSING"
    REQUIRE_PARAMETERS_FALSE = "REQUIRE_PARAMETERS_FALSE"
    REQUIRE_PARAMETERS_MISSING = "REQUIRE_PARAMETERS_MISSING"
    UNRESOLVED_SPEC_FIELD_FORBIDDEN = "UNRESOLVED_SPEC_FIELD_FORBIDDEN"
    STREAM_NOT_DISABLED = "STREAM_NOT_DISABLED"
    TOOLS_NOT_DISABLED = "TOOLS_NOT_DISABLED"
    METADATA_HEADER_MISSING = "METADATA_HEADER_MISSING"
    METADATA_HEADER_MALFORMED = "METADATA_HEADER_MALFORMED"
    CACHE_HEADER_MISSING = "CACHE_HEADER_MISSING"
    CACHE_NOT_DISABLED = "CACHE_NOT_DISABLED"
    NONCANONICAL_BODY = "NONCANONICAL_BODY"
    NONCANONICAL_HEADERS = "NONCANONICAL_HEADERS"
    REQUEST_DIGEST_OR_LENGTH_MISMATCH = "REQUEST_DIGEST_OR_LENGTH_MISMATCH"
    PREPARED_REQUEST_MUTATED = "PREPARED_REQUEST_MUTATED"
    FORBIDDEN_BODY_ENTROPY = "FORBIDDEN_BODY_ENTROPY"
    FORBIDDEN_HEADER_ENTROPY = "FORBIDDEN_HEADER_ENTROPY"
    CANNED_TRANSPORT_UNREGISTERED = "CANNED_TRANSPORT_UNREGISTERED"
    TRANSPORT_NOT_COMPLETE = "TRANSPORT_NOT_COMPLETE"
    RAW_ENVELOPE_MISSING = "RAW_ENVELOPE_MISSING"
    ROUTER_METADATA_MISSING = "ROUTER_METADATA_MISSING"
    ROUTER_METADATA_MALFORMED = "ROUTER_METADATA_MALFORMED"
    UNKNOWN_FIELD_AUTHORITY_OVERRIDE = "UNKNOWN_FIELD_AUTHORITY_OVERRIDE"
    CACHE_AFFECTED_METADATA_UNAVAILABLE = "CACHE_AFFECTED_METADATA_UNAVAILABLE"
    CACHE_HIT_RESPONSE_REJECTED = "CACHE_HIT_RESPONSE_REJECTED"
    ATTEMPT_MISSING = "ATTEMPT_MISSING"
    ATTEMPT_INVALID = "ATTEMPT_INVALID"
    MULTI_ATTEMPT_ROUTING_OBSERVED = "MULTI_ATTEMPT_ROUTING_OBSERVED"
    ACTUAL_MODEL_MISSING = "ACTUAL_MODEL_MISSING"
    ACTUAL_MODEL_SUBSTITUTION = "ACTUAL_MODEL_SUBSTITUTION"
    PROVIDER_MISSING = "PROVIDER_MISSING"
    PROVIDER_SUBSTITUTION = "PROVIDER_SUBSTITUTION"
    ATTEMPTS_LIST_MALFORMED = "ATTEMPTS_LIST_MALFORMED"
    ATTEMPTS_LIST_INCONSISTENT = "ATTEMPTS_LIST_INCONSISTENT"
    MULTIPLE_ATTEMPTS_REPORTED = "MULTIPLE_ATTEMPTS_REPORTED"
    FALLBACK_INDICATOR_PRESENT = "FALLBACK_INDICATOR_PRESENT"
    FORBIDDEN_PIPELINE_STAGE = "FORBIDDEN_PIPELINE_STAGE"
    FALSE_EXACT_ENDPOINT_ATTESTATION = "FALSE_EXACT_ENDPOINT_ATTESTATION"
    RECEIPT_MISMATCH = "RECEIPT_MISMATCH"
    ARTIFACT_CLAIM_FORBIDDEN = "ARTIFACT_CLAIM_FORBIDDEN"


class OpenRouterRouteControlMutationVectorV1(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_MUTATION_VECTOR_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_MUTATION_VECTOR_SCHEMA_V1
    spec_manifest_integrity: MutationState = MutationState.PRESERVED
    model_field: MutationState = MutationState.PRESERVED
    models_absence: MutationState = MutationState.PRESERVED
    endpoint_restriction: MutationState = MutationState.PRESERVED
    order: MutationState = MutationState.PRESERVED
    fallback: MutationState = MutationState.PRESERVED
    require_parameters: MutationState = MutationState.PRESERVED
    max_price_status: MutationState = MutationState.PRESERVED
    stream: MutationState = MutationState.PRESERVED
    tools: MutationState = MutationState.PRESERVED
    metadata_header: MutationState = MutationState.PRESERVED
    cache_header: MutationState = MutationState.PRESERVED
    body_bytes: MutationState = MutationState.PRESERVED
    header_bytes: MutationState = MutationState.PRESERVED
    metadata_presence: MutationState = MutationState.PRESERVED
    attempt: MutationState = MutationState.PRESERVED
    attempts_list: MutationState = MutationState.PRESERVED
    actual_model: MutationState = MutationState.PRESERVED
    provider: MutationState = MutationState.PRESERVED
    endpoint_attestation_claim: MutationState = MutationState.PRESERVED
    cache_state: MutationState = MutationState.PRESERVED
    receipt_identity: MutationState = MutationState.PRESERVED

    def count(self, state: MutationState) -> int:
        return sum(
            value == state
            for name, value in self.__dict__.items()
            if name != "schema_version"
        )


MUTATION_VECTOR_FIELD_NAMES_V1: Tuple[str, ...] = tuple(
    name
    for name in OpenRouterRouteControlMutationVectorV1.model_fields
    if name != "schema_version"
)


class OpenRouterRouteControlLiteralMutationV1(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_LITERAL_MUTATION_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_LITERAL_MUTATION_SCHEMA_V1
    path: str = Field(min_length=1)
    before_json: str
    after_json: str
    mutation_vector_field: str = Field(min_length=1)

    @field_validator("before_json", "after_json")
    @classmethod
    def canonical_value(cls, value: str) -> str:
        import json

        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError("mutation value must be valid JSON") from exc
        if canonical_json(parsed) != value:
            raise ContractValidationError("mutation value must be canonical JSON")
        return value

    @field_validator("mutation_vector_field")
    @classmethod
    def known_vector_field(cls, value: str) -> str:
        if value not in MUTATION_VECTOR_FIELD_NAMES_V1:
            raise ContractValidationError("mutation names an unknown vector field")
        return value

    @model_validator(mode="after")
    def changed(self) -> "OpenRouterRouteControlLiteralMutationV1":
        if self.before_json == self.after_json:
            raise ContractValidationError("literal mutation must change its value")
        return self


class OpenRouterRouteControlGuardDesignStepV1(_FrozenCaseContract):
    ordinal: int = Field(ge=1, le=32)
    guard_id: OpenRouterRouteControlGuardId
    stage: OpenRouterRouteControlGuardStage
    summary: str = Field(min_length=1)


class OpenRouterRouteControlValidationOrderV1(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_SCHEMA_V1
    validation_order_id: Optional[str] = None
    precedence_model: Literal[
        FIRST_ROUTE_CONTROL_GUARD_WINS_V1
    ] = FIRST_ROUTE_CONTROL_GUARD_WINS_V1
    steps: Tuple[OpenRouterRouteControlGuardDesignStepV1, ...] = Field(
        min_length=32, max_length=32
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteControlValidationOrderV1":
        if tuple(step.ordinal for step in self.steps) != tuple(range(1, 33)):
            raise ContractValidationError("guard ordinals must be exactly 1..32")
        if len({step.guard_id for step in self.steps}) != 32:
            raise ContractValidationError("guard IDs must be unique")
        if any(
            step.stage != OpenRouterRouteControlGuardStage.PRE_DISPATCH
            for step in self.steps[:17]
        ):
            raise ContractValidationError("guards 1..17 must be pre-dispatch")
        if any(
            step.stage != OpenRouterRouteControlGuardStage.POST_RESPONSE
            for step in self.steps[17:]
        ):
            raise ContractValidationError("guards 18..32 must be post-response")
        payload = self.model_dump(mode="json", exclude={"validation_order_id"})
        expected = stable_contract_id("szorrouteguardsv1", payload)
        if self.validation_order_id is not None and self.validation_order_id != expected:
            raise ContractValidationError("validation-order ID mismatch")
        object.__setattr__(self, "validation_order_id", expected)
        return self


class OpenRouterRouteControlFailureTaxonomyEntryV1(_FrozenCaseContract):
    failure_code: OpenRouterRouteControlFailureCode
    guard_id: OpenRouterRouteControlGuardId


class OpenRouterRouteControlFailureTaxonomyV1(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_SCHEMA_V1
    failure_taxonomy_id: Optional[str] = None
    entries: Tuple[OpenRouterRouteControlFailureTaxonomyEntryV1, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteControlFailureTaxonomyV1":
        codes = tuple(entry.failure_code for entry in self.entries)
        if len(codes) != len(set(codes)):
            raise ContractValidationError("failure taxonomy contains duplicate codes")
        if set(codes) != set(OpenRouterRouteControlFailureCode):
            raise ContractValidationError("failure taxonomy must cover every code")
        payload = self.model_dump(mode="json", exclude={"failure_taxonomy_id"})
        expected = stable_contract_id("szorroutefailuresv1", payload)
        if self.failure_taxonomy_id is not None and self.failure_taxonomy_id != expected:
            raise ContractValidationError("failure-taxonomy ID mismatch")
        object.__setattr__(self, "failure_taxonomy_id", expected)
        return self


_G = OpenRouterRouteControlGuardId
_PRE = OpenRouterRouteControlGuardStage.PRE_DISPATCH
_POST = OpenRouterRouteControlGuardStage.POST_RESPONSE


def _guard(
    ordinal: int,
    guard_id: OpenRouterRouteControlGuardId,
    stage: OpenRouterRouteControlGuardStage,
    summary: str,
) -> OpenRouterRouteControlGuardDesignStepV1:
    return OpenRouterRouteControlGuardDesignStepV1(
        ordinal=ordinal,
        guard_id=guard_id,
        stage=stage,
        summary=summary,
    )


_FROZEN_ROUTE_CONTROL_GUARD_STEPS_V1: Tuple[
    OpenRouterRouteControlGuardDesignStepV1, ...
] = (
    _guard(1, _G.G01_SPECIFICATION_MANIFEST_INTEGRITY, _PRE, "Frozen specification-manifest binding is exact."),
    _guard(2, _G.G02_ROUTE_POLICY_INTEGRITY, _PRE, "Frozen route-policy identity and fields are exact."),
    _guard(3, _G.G03_EXACT_MODEL, _PRE, "One exact model field is present and matches."),
    _guard(4, _G.G04_MODELS_ABSENT, _PRE, "The model-fallback models field is absent."),
    _guard(5, _G.G05_PROVIDER_OBJECT_SCHEMA, _PRE, "The provider object has the frozen schema."),
    _guard(6, _G.G06_EXACT_SINGLETON_ENDPOINT, _PRE, "Provider only is the exact singleton endpoint."),
    _guard(7, _G.G07_PROVIDER_ORDER_EXACT, _PRE, "Provider order is the same exact singleton."),
    _guard(8, _G.G08_PROVIDER_FALLBACK_FALSE, _PRE, "Provider fallback is explicitly false."),
    _guard(9, _G.G09_REQUIRE_PARAMETERS_TRUE, _PRE, "Require-parameters is explicitly true."),
    _guard(10, _G.G10_MAX_PRICE_ABSENT, _PRE, "Unresolved max-price is absent."),
    _guard(11, _G.G11_STREAM_FALSE, _PRE, "Streaming is explicitly false."),
    _guard(12, _G.G12_TOOLS_DISABLED, _PRE, "Tools are disabled using the frozen representation."),
    _guard(13, _G.G13_METADATA_HEADER, _PRE, "Router-metadata opt-in header is exact."),
    _guard(14, _G.G14_CACHE_HEADER, _PRE, "Cache-disable header is exact."),
    _guard(15, _G.G15_CANONICAL_BYTES, _PRE, "Canonical bytes, digests, and lengths are exact."),
    _guard(16, _G.G16_ENTROPY_FIREWALL, _PRE, "Provider-visible body and headers contain no forbidden entropy."),
    _guard(17, _G.G17_CANNED_REGISTRATION, _PRE, "The canned transport fixture is registered."),
    _guard(18, _G.G18_TRANSPORT_COMPLETION, _POST, "Canned transport completed exactly once."),
    _guard(19, _G.G19_RAW_ENVELOPE_PRESENCE, _POST, "Raw response envelope is present."),
    _guard(20, _G.G20_METADATA_PRESENCE, _POST, "Required router metadata is present."),
    _guard(21, _G.G21_METADATA_SCHEMA, _POST, "Documented metadata fields have valid shapes."),
    _guard(22, _G.G22_CACHE_METADATA_AVAILABILITY, _POST, "Cache state does not invalidate metadata authority."),
    _guard(23, _G.G23_ATTEMPT_VALIDITY, _POST, "Attempt is present and a positive integer."),
    _guard(24, _G.G24_ATTEMPT_ONE, _POST, "Attempt equals exactly one."),
    _guard(25, _G.G25_ACTUAL_MODEL_PRESENCE, _POST, "Actual model is present."),
    _guard(26, _G.G26_ACTUAL_MODEL_MATCH, _POST, "Actual model matches exactly."),
    _guard(27, _G.G27_PROVIDER_PRESENCE, _POST, "Provider attestation is present."),
    _guard(28, _G.G28_PROVIDER_COMPATIBILITY, _POST, "Provider matches at documented broad granularity."),
    _guard(29, _G.G29_ATTEMPTS_CONSISTENCY, _POST, "Optional attempts list is internally consistent."),
    _guard(30, _G.G30_FALLBACK_PIPELINE_ABSENCE, _POST, "No fallback indicator or forbidden pipeline stage appears."),
    _guard(31, _G.G31_EXACT_ENDPOINT_CLAIM_FIREWALL, _POST, "Broad metadata cannot claim exact endpoint attestation."),
    _guard(32, _G.G32_RECEIPT_AND_CLAIMS_INTEGRITY, _POST, "Receipt identity and deferred-claim firewalls are exact."),
)


FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1 = (
    OpenRouterRouteControlValidationOrderV1(steps=_FROZEN_ROUTE_CONTROL_GUARD_STEPS_V1)
)
FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1: Tuple[
    OpenRouterRouteControlGuardId, ...
] = tuple(step.guard_id for step in _FROZEN_ROUTE_CONTROL_GUARD_STEPS_V1)


_FAILURE_CODES_BY_GUARD_V1: dict[
    OpenRouterRouteControlGuardId, Tuple[OpenRouterRouteControlFailureCode, ...]
] = {
    _G.G01_SPECIFICATION_MANIFEST_INTEGRITY: (OpenRouterRouteControlFailureCode.SPECIFICATION_MANIFEST_MISMATCH,),
    _G.G02_ROUTE_POLICY_INTEGRITY: (OpenRouterRouteControlFailureCode.ROUTE_POLICY_MISMATCH,),
    _G.G03_EXACT_MODEL: (OpenRouterRouteControlFailureCode.EXACT_MODEL_MISSING, OpenRouterRouteControlFailureCode.EXACT_MODEL_MISMATCH),
    _G.G04_MODELS_ABSENT: (OpenRouterRouteControlFailureCode.MODELS_FIELD_PRESENT,),
    _G.G05_PROVIDER_OBJECT_SCHEMA: (OpenRouterRouteControlFailureCode.PROVIDER_OBJECT_MISSING, OpenRouterRouteControlFailureCode.PROVIDER_SCHEMA_INVALID),
    _G.G06_EXACT_SINGLETON_ENDPOINT: (
        OpenRouterRouteControlFailureCode.ENDPOINT_RESTRICTION_MISSING,
        OpenRouterRouteControlFailureCode.ENDPOINT_SELECTOR_NOT_SINGLETON,
        OpenRouterRouteControlFailureCode.ENDPOINT_SELECTOR_DUPLICATED,
        OpenRouterRouteControlFailureCode.ENDPOINT_SELECTOR_MISMATCH,
        OpenRouterRouteControlFailureCode.ENDPOINT_SELECTOR_WILDCARD_FORBIDDEN,
        OpenRouterRouteControlFailureCode.BASE_PROVIDER_SELECTOR_FORBIDDEN,
    ),
    _G.G07_PROVIDER_ORDER_EXACT: (
        OpenRouterRouteControlFailureCode.PROVIDER_ORDER_MISSING,
        OpenRouterRouteControlFailureCode.PROVIDER_ORDER_NOT_SINGLETON,
        OpenRouterRouteControlFailureCode.PROVIDER_ORDER_MISMATCH,
    ),
    _G.G08_PROVIDER_FALLBACK_FALSE: (OpenRouterRouteControlFailureCode.PROVIDER_FALLBACK_ENABLED, OpenRouterRouteControlFailureCode.PROVIDER_FALLBACK_POLICY_MISSING),
    _G.G09_REQUIRE_PARAMETERS_TRUE: (OpenRouterRouteControlFailureCode.REQUIRE_PARAMETERS_FALSE, OpenRouterRouteControlFailureCode.REQUIRE_PARAMETERS_MISSING),
    _G.G10_MAX_PRICE_ABSENT: (OpenRouterRouteControlFailureCode.UNRESOLVED_SPEC_FIELD_FORBIDDEN,),
    _G.G11_STREAM_FALSE: (OpenRouterRouteControlFailureCode.STREAM_NOT_DISABLED,),
    _G.G12_TOOLS_DISABLED: (OpenRouterRouteControlFailureCode.TOOLS_NOT_DISABLED,),
    _G.G13_METADATA_HEADER: (OpenRouterRouteControlFailureCode.METADATA_HEADER_MISSING, OpenRouterRouteControlFailureCode.METADATA_HEADER_MALFORMED),
    _G.G14_CACHE_HEADER: (OpenRouterRouteControlFailureCode.CACHE_HEADER_MISSING, OpenRouterRouteControlFailureCode.CACHE_NOT_DISABLED),
    _G.G15_CANONICAL_BYTES: (
        OpenRouterRouteControlFailureCode.NONCANONICAL_BODY,
        OpenRouterRouteControlFailureCode.NONCANONICAL_HEADERS,
        OpenRouterRouteControlFailureCode.REQUEST_DIGEST_OR_LENGTH_MISMATCH,
        OpenRouterRouteControlFailureCode.PREPARED_REQUEST_MUTATED,
    ),
    _G.G16_ENTROPY_FIREWALL: (OpenRouterRouteControlFailureCode.FORBIDDEN_BODY_ENTROPY, OpenRouterRouteControlFailureCode.FORBIDDEN_HEADER_ENTROPY),
    _G.G17_CANNED_REGISTRATION: (OpenRouterRouteControlFailureCode.CANNED_TRANSPORT_UNREGISTERED,),
    _G.G18_TRANSPORT_COMPLETION: (OpenRouterRouteControlFailureCode.TRANSPORT_NOT_COMPLETE,),
    _G.G19_RAW_ENVELOPE_PRESENCE: (OpenRouterRouteControlFailureCode.RAW_ENVELOPE_MISSING,),
    _G.G20_METADATA_PRESENCE: (OpenRouterRouteControlFailureCode.ROUTER_METADATA_MISSING,),
    _G.G21_METADATA_SCHEMA: (OpenRouterRouteControlFailureCode.ROUTER_METADATA_MALFORMED, OpenRouterRouteControlFailureCode.UNKNOWN_FIELD_AUTHORITY_OVERRIDE),
    _G.G22_CACHE_METADATA_AVAILABILITY: (OpenRouterRouteControlFailureCode.CACHE_AFFECTED_METADATA_UNAVAILABLE, OpenRouterRouteControlFailureCode.CACHE_HIT_RESPONSE_REJECTED),
    _G.G23_ATTEMPT_VALIDITY: (OpenRouterRouteControlFailureCode.ATTEMPT_MISSING, OpenRouterRouteControlFailureCode.ATTEMPT_INVALID),
    _G.G24_ATTEMPT_ONE: (OpenRouterRouteControlFailureCode.MULTI_ATTEMPT_ROUTING_OBSERVED,),
    _G.G25_ACTUAL_MODEL_PRESENCE: (OpenRouterRouteControlFailureCode.ACTUAL_MODEL_MISSING,),
    _G.G26_ACTUAL_MODEL_MATCH: (OpenRouterRouteControlFailureCode.ACTUAL_MODEL_SUBSTITUTION,),
    _G.G27_PROVIDER_PRESENCE: (OpenRouterRouteControlFailureCode.PROVIDER_MISSING,),
    _G.G28_PROVIDER_COMPATIBILITY: (OpenRouterRouteControlFailureCode.PROVIDER_SUBSTITUTION,),
    _G.G29_ATTEMPTS_CONSISTENCY: (
        OpenRouterRouteControlFailureCode.ATTEMPTS_LIST_MALFORMED,
        OpenRouterRouteControlFailureCode.ATTEMPTS_LIST_INCONSISTENT,
        OpenRouterRouteControlFailureCode.MULTIPLE_ATTEMPTS_REPORTED,
    ),
    _G.G30_FALLBACK_PIPELINE_ABSENCE: (OpenRouterRouteControlFailureCode.FALLBACK_INDICATOR_PRESENT, OpenRouterRouteControlFailureCode.FORBIDDEN_PIPELINE_STAGE),
    _G.G31_EXACT_ENDPOINT_CLAIM_FIREWALL: (OpenRouterRouteControlFailureCode.FALSE_EXACT_ENDPOINT_ATTESTATION,),
    _G.G32_RECEIPT_AND_CLAIMS_INTEGRITY: (OpenRouterRouteControlFailureCode.RECEIPT_MISMATCH, OpenRouterRouteControlFailureCode.ARTIFACT_CLAIM_FORBIDDEN),
}


FAILURE_GUARD_BY_CODE_V1: dict[
    OpenRouterRouteControlFailureCode, OpenRouterRouteControlGuardId
] = {
    code: guard_id
    for guard_id, codes in _FAILURE_CODES_BY_GUARD_V1.items()
    for code in codes
}


FROZEN_OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_V1 = (
    OpenRouterRouteControlFailureTaxonomyV1(
        entries=tuple(
            OpenRouterRouteControlFailureTaxonomyEntryV1(
                failure_code=code,
                guard_id=guard_id,
            )
            for guard_id in FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1
            for code in _FAILURE_CODES_BY_GUARD_V1[guard_id]
        )
    )
)


class OpenRouterRouteControlCaseV1(_FrozenCaseContract):
    """One frozen evaluator-only expectation and its declared mutation surface."""

    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_CASE_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_CASE_SCHEMA_V1
    case_id: str = Field(pattern=r"^orroutev1-(?:sr|ss|or|os|p)[0-9]{2}-[a-z0-9-]+$")
    case_fingerprint: Optional[str] = None
    kind: OpenRouterRouteControlCaseKind
    category: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evaluator_expectation_role: Literal[
        OPENROUTER_ROUTE_CONTROL_EVALUATOR_EXPECTATION_ROLE_V1
    ] = OPENROUTER_ROUTE_CONTROL_EVALUATOR_EXPECTATION_ROLE_V1
    expected_outcome: OpenRouterRouteControlExpectedOutcome
    expected_guard_id: Optional[OpenRouterRouteControlGuardId] = None
    expected_failure_code: Optional[OpenRouterRouteControlFailureCode] = None
    mutations: Tuple[OpenRouterRouteControlLiteralMutationV1, ...] = ()
    mutation_vector: OpenRouterRouteControlMutationVectorV1
    expected_canned_invocations: int = Field(ge=0, le=1)
    expected_complete_route_intent_receipts: int = Field(ge=0, le=2)
    expected_complete_metadata_receipts: int = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteControlCaseV1":
        positive = self.kind in {
            OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
            OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
        }
        orthogonal = self.kind in {
            OpenRouterRouteControlCaseKind.ORTHOGONAL_REQUEST,
            OpenRouterRouteControlCaseKind.ORTHOGONAL_RESPONSE,
        }
        intentional_count = self.mutation_vector.count(
            MutationState.INTENTIONALLY_CHANGED
        )

        if positive:
            if self.expected_outcome != OpenRouterRouteControlExpectedOutcome.ACCEPTED:
                raise ContractValidationError("positive case must be accepted")
            if self.expected_guard_id is not None or self.expected_failure_code is not None:
                raise ContractValidationError("positive case cannot declare a failure")
            if self.mutations or intentional_count != 0:
                raise ContractValidationError("positive case must declare zero mutations")
        else:
            if self.expected_outcome != OpenRouterRouteControlExpectedOutcome.REJECTED:
                raise ContractValidationError("probe must be rejected")
            if self.expected_guard_id is None or self.expected_failure_code is None:
                raise ContractValidationError("probe must declare guard and failure")
            if FAILURE_GUARD_BY_CODE_V1[self.expected_failure_code] != self.expected_guard_id:
                raise ContractValidationError("probe guard/failure alignment changed")
            if orthogonal and (len(self.mutations) != 1 or intentional_count != 1):
                raise ContractValidationError(
                    "orthogonal probe must declare exactly one intentional mutation"
                )
            if self.kind == OpenRouterRouteControlCaseKind.PRECEDENCE and (
                len(self.mutations) < 2 or intentional_count < 2
            ):
                raise ContractValidationError(
                    "precedence probe must declare at least two intentional mutations"
                )

        if len({mutation.path for mutation in self.mutations}) != len(self.mutations):
            raise ContractValidationError("case contains duplicate mutation paths")
        intentional_fields = {
            name
            for name, state in self.mutation_vector.__dict__.items()
            if name != "schema_version"
            and state == MutationState.INTENTIONALLY_CHANGED
        }
        if {mutation.mutation_vector_field for mutation in self.mutations} != intentional_fields:
            raise ContractValidationError(
                "literal mutations must exactly match intentional vector fields"
            )

        request_kinds = {
            OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
            OpenRouterRouteControlCaseKind.ORTHOGONAL_REQUEST,
        }
        response_kinds = {
            OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
            OpenRouterRouteControlCaseKind.ORTHOGONAL_RESPONSE,
        }
        if self.kind in request_kinds and self.expected_canned_invocations != 0:
            raise ContractValidationError("request case must not dispatch")
        if self.kind in response_kinds and self.expected_canned_invocations != 1:
            raise ContractValidationError("response case must dispatch exactly once")
        if self.kind == OpenRouterRouteControlCaseKind.PRECEDENCE:
            ordinal = FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1.index(
                self.expected_guard_id  # type: ignore[arg-type]
            ) + 1
            expected_invocations = 0 if ordinal <= 17 else 1
            if self.expected_canned_invocations != expected_invocations:
                raise ContractValidationError(
                    "precedence dispatch count must follow its winning guard"
                )

        if positive:
            if self.expected_complete_route_intent_receipts < 1:
                raise ContractValidationError("positive case must complete a route receipt")
            expected_metadata = int(
                self.kind == OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE
            )
            if self.expected_complete_metadata_receipts != expected_metadata:
                raise ContractValidationError("positive metadata receipt count changed")
        elif (
            self.expected_complete_route_intent_receipts != 0
            or self.expected_complete_metadata_receipts != 0
        ):
            raise ContractValidationError("rejected probe cannot claim a complete receipt")

        payload = self.model_dump(mode="json", exclude={"case_fingerprint"})
        expected = stable_contract_id("szorroutecasev1", payload)
        if self.case_fingerprint is not None and self.case_fingerprint != expected:
            raise ContractValidationError("case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


_I = MutationState.INTENTIONALLY_CHANGED
_D = MutationState.DEPENDENTLY_CHANGED
_N = MutationState.NOT_APPLICABLE
_ACCEPT = OpenRouterRouteControlExpectedOutcome.ACCEPTED
_REJECT = OpenRouterRouteControlExpectedOutcome.REJECTED
_K = OpenRouterRouteControlCaseKind
_F = OpenRouterRouteControlFailureCode


def _vector(**changes: MutationState) -> OpenRouterRouteControlMutationVectorV1:
    unknown = set(changes) - set(MUTATION_VECTOR_FIELD_NAMES_V1)
    if unknown:
        raise ContractValidationError(
            f"unknown mutation-vector fields: {sorted(unknown)!r}"
        )
    return OpenRouterRouteControlMutationVectorV1(**changes)


def _positive_request_vector() -> OpenRouterRouteControlMutationVectorV1:
    return _vector(
        metadata_presence=_N,
        attempt=_N,
        attempts_list=_N,
        actual_model=_N,
        provider=_N,
        endpoint_attestation_claim=_N,
        cache_state=_N,
    )


def _mutation(
    path: str,
    before: object,
    after: object,
    vector_field: str,
) -> OpenRouterRouteControlLiteralMutationV1:
    return OpenRouterRouteControlLiteralMutationV1(
        path=path,
        before_json=canonical_json(before),
        after_json=canonical_json(after),
        mutation_vector_field=vector_field,
    )


def _positive(
    case_id: str,
    kind: OpenRouterRouteControlCaseKind,
    category: str,
    summary: str,
    *,
    route_receipts: int = 1,
) -> OpenRouterRouteControlCaseV1:
    return OpenRouterRouteControlCaseV1(
        case_id=case_id,
        kind=kind,
        category=category,
        summary=summary,
        expected_outcome=_ACCEPT,
        mutation_vector=(
            _positive_request_vector()
            if kind == _K.POSITIVE_REQUEST
            else _vector()
        ),
        expected_canned_invocations=int(kind == _K.POSITIVE_RESPONSE),
        expected_complete_route_intent_receipts=route_receipts,
        expected_complete_metadata_receipts=int(kind == _K.POSITIVE_RESPONSE),
    )


def _probe(
    case_id: str,
    kind: OpenRouterRouteControlCaseKind,
    category: str,
    guard_id: OpenRouterRouteControlGuardId,
    failure_code: OpenRouterRouteControlFailureCode,
    summary: str,
    mutations: Tuple[OpenRouterRouteControlLiteralMutationV1, ...],
    mutation_vector: OpenRouterRouteControlMutationVectorV1,
) -> OpenRouterRouteControlCaseV1:
    expected_invocations = int(
        kind == _K.ORTHOGONAL_RESPONSE
        or (
            kind == _K.PRECEDENCE
            and FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1.index(guard_id) + 1 > 17
        )
    )
    return OpenRouterRouteControlCaseV1(
        case_id=case_id,
        kind=kind,
        category=category,
        summary=summary,
        expected_outcome=_REJECT,
        expected_guard_id=guard_id,
        expected_failure_code=failure_code,
        mutations=mutations,
        mutation_vector=mutation_vector,
        expected_canned_invocations=expected_invocations,
        expected_complete_route_intent_receipts=0,
        expected_complete_metadata_receipts=0,
    )


def _orthogonal_request_vector(
    intentional_field: str,
    **dependent_fields: MutationState,
) -> OpenRouterRouteControlMutationVectorV1:
    changes: dict[str, MutationState] = {
        "metadata_presence": _N,
        "attempt": _N,
        "attempts_list": _N,
        "actual_model": _N,
        "provider": _N,
        "endpoint_attestation_claim": _N,
        "cache_state": _N,
        intentional_field: _I,
        **dependent_fields,
    }
    return _vector(**changes)


def _orthogonal_response_vector(
    intentional_field: str,
    **dependent_fields: MutationState,
) -> OpenRouterRouteControlMutationVectorV1:
    return _vector(**{intentional_field: _I, **dependent_fields})


FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_REQUEST_CASES_V1: Tuple[
    OpenRouterRouteControlCaseV1, ...
] = (
    _positive(
        "orroutev1-sr01-canonical-route-body",
        _K.POSITIVE_REQUEST,
        "CANONICAL_ROUTE_BODY",
        "Exact model, absent models, singleton endpoint, no fallback, supported parameters, deferred max-price, no stream, and no tools.",
    ),
    _positive(
        "orroutev1-sr02-canonical-route-headers",
        _K.POSITIVE_REQUEST,
        "CANONICAL_ROUTE_HEADERS",
        "Exact non-secret content, metadata opt-in, and cache-disable semantic headers.",
    ),
    _positive(
        "orroutev1-sr03-sibling-intent-replay",
        _K.POSITIVE_REQUEST,
        "SIBLING_INTENT_REPLAY",
        "Sibling preparation and receipt replay yield identical body, header, and route-intent identities.",
        route_receipts=2,
    ),
)


FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_RESPONSE_CASES_V1: Tuple[
    OpenRouterRouteControlCaseV1, ...
] = (
    _positive(
        "orroutev1-ss01-metadata-attempts-absent",
        _K.POSITIVE_RESPONSE,
        "METADATA_ATTEMPTS_ABSENT",
        "Required metadata attests attempt one, exact model, and broad provider while the optional attempts list is absent.",
    ),
    _positive(
        "orroutev1-ss02-metadata-attempts-present",
        _K.POSITIVE_RESPONSE,
        "METADATA_ATTEMPTS_PRESENT",
        "The optional singleton attempts list is present and internally consistent with top-level metadata.",
    ),
    _positive(
        "orroutev1-ss03-forward-compatible-extras",
        _K.POSITIVE_RESPONSE,
        "FORWARD_COMPATIBLE_EXTRAS",
        "Opaque unknown metadata is retained without authority and exact endpoint attestation remains not established.",
    ),
)


FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_REQUEST_PROBES_V1: Tuple[
    OpenRouterRouteControlCaseV1, ...
] = (
    _probe("orroutev1-or01-missing-model", _K.ORTHOGONAL_REQUEST, "MISSING_MODEL", _G.G03_EXACT_MODEL, _F.EXACT_MODEL_MISSING, "Remove only the exact model field.", (_mutation("request.body.model", "openai/gpt-4.1-mini", {"state": "ABSENT"}, "model_field"),), _orthogonal_request_vector("model_field", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or02-wrong-model", _K.ORTHOGONAL_REQUEST, "WRONG_MODEL", _G.G03_EXACT_MODEL, _F.EXACT_MODEL_MISMATCH, "Substitute only the exact model value.", (_mutation("request.body.model", "openai/gpt-4.1-mini", "openai/gpt-4.1", "model_field"),), _orthogonal_request_vector("model_field", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or03-models-singleton-present", _K.ORTHOGONAL_REQUEST, "MODELS_SINGLETON_PRESENT", _G.G04_MODELS_ABSENT, _F.MODELS_FIELD_PRESENT, "Add a singleton model-fallback array.", (_mutation("request.body.models", {"state": "ABSENT"}, ["openai/gpt-4.1-mini"], "models_absence"),), _orthogonal_request_vector("models_absence", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or04-models-several-present", _K.ORTHOGONAL_REQUEST, "MODELS_SEVERAL_PRESENT", _G.G04_MODELS_ABSENT, _F.MODELS_FIELD_PRESENT, "Add a multi-model fallback array.", (_mutation("request.body.models", {"state": "ABSENT"}, ["openai/gpt-4.1-mini", "openai/gpt-4.1"], "models_absence"),), _orthogonal_request_vector("models_absence", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or05-provider-only-missing", _K.ORTHOGONAL_REQUEST, "PROVIDER_ONLY_MISSING", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_RESTRICTION_MISSING, "Remove only provider.only.", (_mutation("request.body.provider.only", ["azure/swedencentral"], {"state": "ABSENT"}, "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or06-only-empty", _K.ORTHOGONAL_REQUEST, "ONLY_EMPTY", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_NOT_SINGLETON, "Replace provider.only with an empty list.", (_mutation("request.body.provider.only", ["azure/swedencentral"], [], "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or07-only-multiple", _K.ORTHOGONAL_REQUEST, "ONLY_MULTIPLE", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_NOT_SINGLETON, "Add a second endpoint to provider.only.", (_mutation("request.body.provider.only", ["azure/swedencentral"], ["azure/swedencentral", "azure/eastus"], "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or08-only-duplicate", _K.ORTHOGONAL_REQUEST, "ONLY_DUPLICATE", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_DUPLICATED, "Duplicate the exact endpoint in provider.only.", (_mutation("request.body.provider.only", ["azure/swedencentral"], ["azure/swedencentral", "azure/swedencentral"], "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or09-wrong-endpoint", _K.ORTHOGONAL_REQUEST, "WRONG_ENDPOINT", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_MISMATCH, "Substitute a different endpoint selector.", (_mutation("request.body.provider.only", ["azure/swedencentral"], ["azure/eastus"], "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or10-wildcard-selector", _K.ORTHOGONAL_REQUEST, "WILDCARD_SELECTOR", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_WILDCARD_FORBIDDEN, "Replace the endpoint with a wildcard selector.", (_mutation("request.body.provider.only", ["azure/swedencentral"], ["azure/*"], "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or11-base-provider-selector", _K.ORTHOGONAL_REQUEST, "BASE_PROVIDER_SELECTOR", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.BASE_PROVIDER_SELECTOR_FORBIDDEN, "Use the base openai selector prohibited by the frozen exact-endpoint policy.", (_mutation("request.body.provider.only", ["azure/swedencentral"], ["openai"], "endpoint_restriction"),), _orthogonal_request_vector("endpoint_restriction", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or12-order-missing", _K.ORTHOGONAL_REQUEST, "ORDER_MISSING", _G.G07_PROVIDER_ORDER_EXACT, _F.PROVIDER_ORDER_MISSING, "Remove only provider.order.", (_mutation("request.body.provider.order", ["azure/swedencentral"], {"state": "ABSENT"}, "order"),), _orthogonal_request_vector("order", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or13-order-mismatch", _K.ORTHOGONAL_REQUEST, "ORDER_MISMATCH", _G.G07_PROVIDER_ORDER_EXACT, _F.PROVIDER_ORDER_MISMATCH, "Substitute a different endpoint in provider.order.", (_mutation("request.body.provider.order", ["azure/swedencentral"], ["azure/eastus"], "order"),), _orthogonal_request_vector("order", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or14-order-extra-endpoint", _K.ORTHOGONAL_REQUEST, "ORDER_EXTRA_ENDPOINT", _G.G07_PROVIDER_ORDER_EXACT, _F.PROVIDER_ORDER_NOT_SINGLETON, "Add a second endpoint to provider.order.", (_mutation("request.body.provider.order", ["azure/swedencentral"], ["azure/swedencentral", "azure/eastus"], "order"),), _orthogonal_request_vector("order", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or15-fallback-true", _K.ORTHOGONAL_REQUEST, "FALLBACK_TRUE", _G.G08_PROVIDER_FALLBACK_FALSE, _F.PROVIDER_FALLBACK_ENABLED, "Enable provider fallback.", (_mutation("request.body.provider.allow_fallbacks", False, True, "fallback"),), _orthogonal_request_vector("fallback", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or16-fallback-missing", _K.ORTHOGONAL_REQUEST, "FALLBACK_MISSING", _G.G08_PROVIDER_FALLBACK_FALSE, _F.PROVIDER_FALLBACK_POLICY_MISSING, "Remove provider fallback policy.", (_mutation("request.body.provider.allow_fallbacks", False, {"state": "ABSENT"}, "fallback"),), _orthogonal_request_vector("fallback", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or17-require-parameters-false", _K.ORTHOGONAL_REQUEST, "REQUIRE_PARAMETERS_FALSE", _G.G09_REQUIRE_PARAMETERS_TRUE, _F.REQUIRE_PARAMETERS_FALSE, "Disable require-parameters.", (_mutation("request.body.provider.require_parameters", True, False, "require_parameters"),), _orthogonal_request_vector("require_parameters", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or18-require-parameters-missing", _K.ORTHOGONAL_REQUEST, "REQUIRE_PARAMETERS_MISSING", _G.G09_REQUIRE_PARAMETERS_TRUE, _F.REQUIRE_PARAMETERS_MISSING, "Remove require-parameters.", (_mutation("request.body.provider.require_parameters", True, {"state": "ABSENT"}, "require_parameters"),), _orthogonal_request_vector("require_parameters", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or19-guessed-max-price", _K.ORTHOGONAL_REQUEST, "GUESSED_MAX_PRICE", _G.G10_MAX_PRICE_ABSENT, _F.UNRESOLVED_SPEC_FIELD_FORBIDDEN, "Add a guessed max-price schema despite its frozen deferral.", (_mutation("request.body.provider.max_price", {"state": "ABSENT"}, {"prompt": 1.0}, "max_price_status"),), _orthogonal_request_vector("max_price_status", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or20-stream-true", _K.ORTHOGONAL_REQUEST, "STREAM_TRUE", _G.G11_STREAM_FALSE, _F.STREAM_NOT_DISABLED, "Enable streaming.", (_mutation("request.body.stream", False, True, "stream"),), _orthogonal_request_vector("stream", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or21-tools-enabled", _K.ORTHOGONAL_REQUEST, "TOOLS_ENABLED", _G.G12_TOOLS_DISABLED, _F.TOOLS_NOT_DISABLED, "Add one tool declaration without silently adding a second tool-choice mutation.", (_mutation("request.body.tools", [], [{"name": "forbidden-tool"}], "tools"),), _orthogonal_request_vector("tools", body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or22-metadata-header-missing", _K.ORTHOGONAL_REQUEST, "METADATA_HEADER_MISSING", _G.G13_METADATA_HEADER, _F.METADATA_HEADER_MISSING, "Remove the router-metadata opt-in header.", (_mutation("request.headers.X-OpenRouter-Metadata", "enabled", {"state": "ABSENT"}, "metadata_header"),), _orthogonal_request_vector("metadata_header", header_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or23-metadata-header-malformed", _K.ORTHOGONAL_REQUEST, "METADATA_HEADER_MALFORMED", _G.G13_METADATA_HEADER, _F.METADATA_HEADER_MALFORMED, "Change the metadata opt-in value.", (_mutation("request.headers.X-OpenRouter-Metadata", "enabled", "true", "metadata_header"),), _orthogonal_request_vector("metadata_header", header_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or24-cache-header-missing", _K.ORTHOGONAL_REQUEST, "CACHE_HEADER_MISSING", _G.G14_CACHE_HEADER, _F.CACHE_HEADER_MISSING, "Remove the cache-disable header.", (_mutation("request.headers.X-OpenRouter-Cache", "false", {"state": "ABSENT"}, "cache_header"),), _orthogonal_request_vector("cache_header", header_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or25-cache-enabled", _K.ORTHOGONAL_REQUEST, "CACHE_ENABLED", _G.G14_CACHE_HEADER, _F.CACHE_NOT_DISABLED, "Enable router caching.", (_mutation("request.headers.X-OpenRouter-Cache", "false", "true", "cache_header"),), _orthogonal_request_vector("cache_header", header_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-or26-body-entropy", _K.ORTHOGONAL_REQUEST, "BODY_ENTROPY", _G.G16_ENTROPY_FIREWALL, _F.FORBIDDEN_BODY_ENTROPY, "Inject a branch identifier into the provider-visible body.", (_mutation("request.body.evaluator_metadata.branch_id", {"state": "ABSENT"}, "branch-a", "body_bytes"),), _orthogonal_request_vector("body_bytes", receipt_identity=_D)),
    _probe("orroutev1-or27-header-entropy", _K.ORTHOGONAL_REQUEST, "HEADER_ENTROPY", _G.G16_ENTROPY_FIREWALL, _F.FORBIDDEN_HEADER_ENTROPY, "Inject a transport identifier into semantic headers.", (_mutation("request.headers.X-Transport-ID", {"state": "ABSENT"}, "transport-a", "header_bytes"),), _orthogonal_request_vector("header_bytes", receipt_identity=_D)),
    _probe("orroutev1-or28-noncanonical-body", _K.ORTHOGONAL_REQUEST, "NONCANONICAL_BODY", _G.G15_CANONICAL_BYTES, _F.NONCANONICAL_BODY, "Change only JSON whitespace in the prepared body representation.", (_mutation("request.serialization.body", "CANONICAL", "NONCANONICAL_WHITESPACE", "body_bytes"),), _orthogonal_request_vector("body_bytes", receipt_identity=_D)),
    _probe("orroutev1-or29-post-prepare-mutation", _K.ORTHOGONAL_REQUEST, "POST_PREPARE_MUTATION", _G.G15_CANONICAL_BYTES, _F.PREPARED_REQUEST_MUTATED, "Mutate caller-owned request material after preparation.", (_mutation("request.prepared_bytes.seal_integrity", "MATCH", "MUTATED_AFTER_PREPARATION", "receipt_identity"),), _orthogonal_request_vector("receipt_identity", body_bytes=_D)),
)


FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_RESPONSE_PROBES_V1: Tuple[
    OpenRouterRouteControlCaseV1, ...
] = (
    _probe("orroutev1-os01-metadata-missing", _K.ORTHOGONAL_RESPONSE, "METADATA_MISSING", _G.G20_METADATA_PRESENCE, _F.ROUTER_METADATA_MISSING, "Remove required router metadata.", (_mutation("response.openrouter_metadata", {"state": "PRESENT"}, {"state": "ABSENT"}, "metadata_presence"),), _orthogonal_response_vector("metadata_presence", attempt=_D, attempts_list=_D, actual_model=_D, provider=_D, receipt_identity=_D)),
    _probe("orroutev1-os02-metadata-malformed", _K.ORTHOGONAL_RESPONSE, "METADATA_MALFORMED", _G.G21_METADATA_SCHEMA, _F.ROUTER_METADATA_MALFORMED, "Replace router metadata with a malformed scalar.", (_mutation("response.openrouter_metadata", {"state": "PRESENT"}, "malformed", "metadata_presence"),), _orthogonal_response_vector("metadata_presence", attempt=_D, attempts_list=_D, actual_model=_D, provider=_D, receipt_identity=_D)),
    _probe("orroutev1-os03-attempt-missing", _K.ORTHOGONAL_RESPONSE, "ATTEMPT_MISSING", _G.G23_ATTEMPT_VALIDITY, _F.ATTEMPT_MISSING, "Remove the top-level attempt field.", (_mutation("response.openrouter_metadata.attempt", 1, {"state": "ABSENT"}, "attempt"),), _orthogonal_response_vector("attempt", receipt_identity=_D)),
    _probe("orroutev1-os04-attempt-zero", _K.ORTHOGONAL_RESPONSE, "ATTEMPT_ZERO", _G.G23_ATTEMPT_VALIDITY, _F.ATTEMPT_INVALID, "Set the top-level attempt to zero.", (_mutation("response.openrouter_metadata.attempt", 1, 0, "attempt"),), _orthogonal_response_vector("attempt", receipt_identity=_D)),
    _probe("orroutev1-os05-attempt-greater-than-one", _K.ORTHOGONAL_RESPONSE, "ATTEMPT_GREATER_THAN_ONE", _G.G24_ATTEMPT_ONE, _F.MULTI_ATTEMPT_ROUTING_OBSERVED, "Set the top-level attempt to two.", (_mutation("response.openrouter_metadata.attempt", 1, 2, "attempt"),), _orthogonal_response_vector("attempt", receipt_identity=_D)),
    _probe("orroutev1-os06-wrong-actual-model", _K.ORTHOGONAL_RESPONSE, "WRONG_ACTUAL_MODEL", _G.G26_ACTUAL_MODEL_MATCH, _F.ACTUAL_MODEL_SUBSTITUTION, "Substitute the actual model with another exact model ID.", (_mutation("response.openrouter_metadata.actual_model", "openai/gpt-4.1-mini", "openai/gpt-4.1", "actual_model"),), _orthogonal_response_vector("actual_model", receipt_identity=_D)),
    _probe("orroutev1-os07-wrong-provider", _K.ORTHOGONAL_RESPONSE, "WRONG_PROVIDER", _G.G28_PROVIDER_COMPATIBILITY, _F.PROVIDER_SUBSTITUTION, "Substitute the broad provider attestation.", (_mutation("response.openrouter_metadata.provider", "azure", "google", "provider"),), _orthogonal_response_vector("provider", receipt_identity=_D)),
    _probe("orroutev1-os08-actual-model-missing", _K.ORTHOGONAL_RESPONSE, "ACTUAL_MODEL_MISSING", _G.G25_ACTUAL_MODEL_PRESENCE, _F.ACTUAL_MODEL_MISSING, "Remove the actual model field.", (_mutation("response.openrouter_metadata.actual_model", "openai/gpt-4.1-mini", {"state": "ABSENT"}, "actual_model"),), _orthogonal_response_vector("actual_model", receipt_identity=_D)),
    _probe("orroutev1-os09-provider-missing", _K.ORTHOGONAL_RESPONSE, "PROVIDER_MISSING", _G.G27_PROVIDER_PRESENCE, _F.PROVIDER_MISSING, "Remove the documented broad provider attestation.", (_mutation("response.openrouter_metadata.provider", "azure", {"state": "ABSENT"}, "provider"),), _orthogonal_response_vector("provider", receipt_identity=_D)),
    _probe("orroutev1-os10-attempts-inconsistent", _K.ORTHOGONAL_RESPONSE, "ATTEMPTS_INCONSISTENT", _G.G29_ATTEMPTS_CONSISTENCY, _F.ATTEMPTS_LIST_INCONSISTENT, "Substitute the model within the optional attempts list.", (_mutation("response.openrouter_metadata.attempts[0].model", "openai/gpt-4.1-mini", "openai/gpt-4.1", "attempts_list"),), _orthogonal_response_vector("attempts_list", receipt_identity=_D)),
    _probe("orroutev1-os11-several-attempts", _K.ORTHOGONAL_RESPONSE, "SEVERAL_ATTEMPTS", _G.G29_ATTEMPTS_CONSISTENCY, _F.MULTIPLE_ATTEMPTS_REPORTED, "Add a second record to the optional attempts list.", (_mutation("response.openrouter_metadata.attempts", [{"attempt": 1, "model": "openai/gpt-4.1-mini", "outcome": "success", "provider": "azure"}], [{"attempt": 1, "model": "openai/gpt-4.1-mini", "outcome": "success", "provider": "azure"}, {"attempt": 2, "model": "openai/gpt-4.1-mini", "outcome": "success", "provider": "azure"}], "attempts_list"),), _orthogonal_response_vector("attempts_list", receipt_identity=_D)),
    _probe("orroutev1-os12-attempts-top-level-contradiction", _K.ORTHOGONAL_RESPONSE, "ATTEMPTS_TOP_LEVEL_CONTRADICTION", _G.G29_ATTEMPTS_CONSISTENCY, _F.ATTEMPTS_LIST_INCONSISTENT, "Make the attempts-list ordinal contradict top-level attempt one.", (_mutation("response.openrouter_metadata.attempts[0].attempt", 1, 2, "attempts_list"),), _orthogonal_response_vector("attempts_list", receipt_identity=_D)),
    _probe("orroutev1-os13-cache-hit-metadata-unavailable", _K.ORTHOGONAL_RESPONSE, "CACHE_HIT_METADATA_UNAVAILABLE", _G.G20_METADATA_PRESENCE, _F.ROUTER_METADATA_MISSING, "Represent a possible cache path whose required router metadata is unavailable; missing metadata remains the primary failure and no cache hit is inferred as authority.", (_mutation("response.cache_state", {"state": "ABSENT"}, "POSSIBLE_HIT_METADATA_UNAVAILABLE", "cache_state"),), _orthogonal_response_vector("cache_state", metadata_presence=_D, attempt=_D, attempts_list=_D, actual_model=_D, provider=_D, receipt_identity=_D)),
    _probe("orroutev1-os14-fake-exact-endpoint-claim", _K.ORTHOGONAL_RESPONSE, "FAKE_EXACT_ENDPOINT_CLAIM", _G.G31_EXACT_ENDPOINT_CLAIM_FIREWALL, _F.FALSE_EXACT_ENDPOINT_ATTESTATION, "Inject an unsupported exact endpoint claim beside broad provider metadata.", (_mutation("response.openrouter_metadata.endpoint_slug", {"state": "ABSENT"}, "azure/swedencentral", "endpoint_attestation_claim"),), _orthogonal_response_vector("endpoint_attestation_claim", receipt_identity=_D)),
    _probe("orroutev1-os15-unknown-authority-override", _K.ORTHOGONAL_RESPONSE, "UNKNOWN_AUTHORITY_OVERRIDE", _G.G21_METADATA_SCHEMA, _F.UNKNOWN_FIELD_AUTHORITY_OVERRIDE, "Use an unknown field to attempt to override canonical authority.", (_mutation("response.openrouter_metadata.unknown_authority", {"state": "ABSENT"}, {"actual_model": "openai/gpt-4.1"}, "metadata_presence"),), _orthogonal_response_vector("metadata_presence", receipt_identity=_D)),
    _probe("orroutev1-os16-fallback-strategy", _K.ORTHOGONAL_RESPONSE, "FALLBACK_STRATEGY", _G.G30_FALLBACK_PIPELINE_ABSENCE, _F.FALLBACK_INDICATOR_PRESENT, "Replace the frozen local direct-strategy concept with an explicit fallback strategy.", (_mutation("response.openrouter_metadata.routing_strategy", "direct", "fallback", "fallback"),), _orthogonal_response_vector("fallback", receipt_identity=_D)),
    _probe("orroutev1-os17-alias-model-substitution", _K.ORTHOGONAL_RESPONSE, "ALIAS_MODEL_SUBSTITUTION", _G.G26_ACTUAL_MODEL_MATCH, _F.ACTUAL_MODEL_SUBSTITUTION, "Replace the actual model with an alias-like value.", (_mutation("response.openrouter_metadata.actual_model", "openai/gpt-4.1-mini", "openai/gpt-4.1-mini:latest", "actual_model"),), _orthogonal_response_vector("actual_model", receipt_identity=_D)),
    _probe("orroutev1-os18-provider-substitution", _K.ORTHOGONAL_RESPONSE, "PROVIDER_SUBSTITUTION", _G.G28_PROVIDER_COMPATIBILITY, _F.PROVIDER_SUBSTITUTION, "Replace the broad provider label with an alternate provider.", (_mutation("response.openrouter_metadata.provider", "azure", "openai", "provider"),), _orthogonal_response_vector("provider", receipt_identity=_D)),
    _probe("orroutev1-os19-forbidden-pipeline-stage", _K.ORTHOGONAL_RESPONSE, "FORBIDDEN_PIPELINE_STAGE", _G.G30_FALLBACK_PIPELINE_ABSENCE, _F.FORBIDDEN_PIPELINE_STAGE, "Add a pipeline stage indicating alternate-route traversal.", (_mutation("response.openrouter_metadata.pipeline", {"state": "ABSENT"}, [{"stage": "fallback"}], "fallback"),), _orthogonal_response_vector("fallback", receipt_identity=_D)),
    _probe("orroutev1-os20-cache-hit-with-metadata", _K.ORTHOGONAL_RESPONSE, "CACHE_HIT_WITH_METADATA", _G.G22_CACHE_METADATA_AVAILABILITY, _F.CACHE_HIT_RESPONSE_REJECTED, "Mark a metadata-bearing canned response as an explicit cache hit.", (_mutation("response.cache_state", {"state": "ABSENT"}, "HIT_WITH_METADATA", "cache_state"),), _orthogonal_response_vector("cache_state", receipt_identity=_D)),
)


FROZEN_OPENROUTER_ROUTE_CONTROL_PRECEDENCE_PROBES_V1: Tuple[
    OpenRouterRouteControlCaseV1, ...
] = (
    _probe("orroutev1-p01-manifest-mismatch-plus-malformed-route", _K.PRECEDENCE, "MANIFEST_MISMATCH_PLUS_MALFORMED_ROUTE", _G.G01_SPECIFICATION_MANIFEST_INTEGRITY, _F.SPECIFICATION_MANIFEST_MISMATCH, "Manifest mismatch precedes malformed route fields.", (_mutation("manifest.semantic_digest", "6f09a0f2", "00000000", "spec_manifest_integrity"), _mutation("request.body.provider.only", ["azure/swedencentral"], [], "endpoint_restriction")), _vector(spec_manifest_integrity=_I, endpoint_restriction=_I, body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-p02-wrong-model-plus-fallback-true", _K.PRECEDENCE, "WRONG_MODEL_PLUS_FALLBACK_TRUE", _G.G03_EXACT_MODEL, _F.EXACT_MODEL_MISMATCH, "Exact-model mismatch precedes enabled provider fallback.", (_mutation("request.body.model", "openai/gpt-4.1-mini", "openai/gpt-4.1", "model_field"), _mutation("request.body.provider.allow_fallbacks", False, True, "fallback")), _vector(model_field=_I, fallback=_I, body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-p03-cache-header-missing-plus-metadata-missing", _K.PRECEDENCE, "CACHE_HEADER_MISSING_PLUS_METADATA_MISSING", _G.G14_CACHE_HEADER, _F.CACHE_HEADER_MISSING, "Missing cache-disable header prevents dispatch before missing metadata can be evaluated.", (_mutation("request.headers.X-OpenRouter-Cache", "false", {"state": "ABSENT"}, "cache_header"), _mutation("response.openrouter_metadata", {"state": "PRESENT"}, {"state": "ABSENT"}, "metadata_presence")), _vector(cache_header=_I, metadata_presence=_I, header_bytes=_D, attempt=_D, attempts_list=_D, actual_model=_D, provider=_D, receipt_identity=_D)),
    _probe("orroutev1-p04-actual-model-missing-plus-provider-mismatch", _K.PRECEDENCE, "ACTUAL_MODEL_MISSING_PLUS_PROVIDER_MISMATCH", _G.G25_ACTUAL_MODEL_PRESENCE, _F.ACTUAL_MODEL_MISSING, "Missing actual-model evidence precedes a broad-provider mismatch in the same valid metadata object.", (_mutation("response.openrouter_metadata.actual_model", "openai/gpt-4.1-mini", {"state": "ABSENT"}, "actual_model"), _mutation("response.openrouter_metadata.provider", "azure", "google", "provider")), _vector(actual_model=_I, provider=_I, receipt_identity=_D)),
    _probe("orroutev1-p05-multi-attempt-plus-model-substitution", _K.PRECEDENCE, "MULTI_ATTEMPT_PLUS_MODEL_SUBSTITUTION", _G.G24_ATTEMPT_ONE, _F.MULTI_ATTEMPT_ROUTING_OBSERVED, "Multi-attempt observation precedes actual-model substitution.", (_mutation("response.openrouter_metadata.attempt", 1, 2, "attempt"), _mutation("response.openrouter_metadata.actual_model", "openai/gpt-4.1-mini", "openai/gpt-4.1", "actual_model")), _vector(attempt=_I, actual_model=_I, receipt_identity=_D)),
    _probe("orroutev1-p06-fallback-strategy-plus-fake-endpoint", _K.PRECEDENCE, "FALLBACK_STRATEGY_PLUS_FAKE_ENDPOINT", _G.G30_FALLBACK_PIPELINE_ABSENCE, _F.FALLBACK_INDICATOR_PRESENT, "A fallback strategy precedes an unsupported exact-endpoint claim in the same valid metadata object.", (_mutation("response.openrouter_metadata.routing_strategy", "direct", "fallback", "fallback"), _mutation("response.openrouter_metadata.endpoint_slug", {"state": "ABSENT"}, "azure/swedencentral", "endpoint_attestation_claim")), _vector(fallback=_I, endpoint_attestation_claim=_I, receipt_identity=_D)),
    _probe("orroutev1-p07-max-price-plus-wrong-endpoint", _K.PRECEDENCE, "MAX_PRICE_PLUS_WRONG_ENDPOINT", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_MISMATCH, "Wrong endpoint restriction precedes forbidden unresolved max-price.", (_mutation("request.body.provider.max_price", {"state": "ABSENT"}, {"prompt": 1.0}, "max_price_status"), _mutation("request.body.provider.only", ["azure/swedencentral"], ["azure/eastus"], "endpoint_restriction")), _vector(max_price_status=_I, endpoint_restriction=_I, body_bytes=_D, receipt_identity=_D)),
    _probe("orroutev1-p08-body-entropy-plus-wrong-endpoint", _K.PRECEDENCE, "BODY_ENTROPY_PLUS_WRONG_ENDPOINT", _G.G06_EXACT_SINGLETON_ENDPOINT, _F.ENDPOINT_SELECTOR_MISMATCH, "Wrong endpoint restriction precedes forbidden body entropy.", (_mutation("request.body.evaluator_metadata.branch_id", {"state": "ABSENT"}, "branch-a", "body_bytes"), _mutation("request.body.provider.only", ["azure/swedencentral"], ["azure/eastus"], "endpoint_restriction")), _vector(body_bytes=_I, endpoint_restriction=_I, receipt_identity=_D)),
)


FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_CASES_V1 = (
    FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_REQUEST_CASES_V1
    + FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_RESPONSE_CASES_V1
)
FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_PROBES_V1 = (
    FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_REQUEST_PROBES_V1
    + FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_RESPONSE_PROBES_V1
)
FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1: Tuple[
    OpenRouterRouteControlCaseV1, ...
] = (
    FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_CASES_V1
    + FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_PROBES_V1
    + FROZEN_OPENROUTER_ROUTE_CONTROL_PRECEDENCE_PROBES_V1
)


POSITIVE_REQUEST_CASE_IDS_V1 = tuple(
    case.case_id
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_REQUEST_CASES_V1
)
POSITIVE_RESPONSE_CASE_IDS_V1 = tuple(
    case.case_id
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_RESPONSE_CASES_V1
)
ORTHOGONAL_REQUEST_PROBE_IDS_V1 = tuple(
    case.case_id
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_REQUEST_PROBES_V1
)
ORTHOGONAL_RESPONSE_PROBE_IDS_V1 = tuple(
    case.case_id
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_RESPONSE_PROBES_V1
)
PRECEDENCE_PROBE_IDS_V1 = tuple(
    case.case_id for case in FROZEN_OPENROUTER_ROUTE_CONTROL_PRECEDENCE_PROBES_V1
)


class OpenRouterRouteControlThresholdsV1(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_THRESHOLDS_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_THRESHOLDS_SCHEMA_V1
    thresholds_id: Optional[str] = None
    cases_total: Literal[63] = 63
    positive_cases_total: Literal[6] = 6
    positive_request_cases_total: Literal[3] = 3
    positive_response_cases_total: Literal[3] = 3
    orthogonal_probes_total: Literal[49] = 49
    orthogonal_request_probes_total: Literal[29] = 29
    orthogonal_response_probes_total: Literal[20] = 20
    precedence_probes_total: Literal[8] = 8
    required_complete_route_intent_receipts: Literal[7] = 7
    required_complete_metadata_receipts: Literal[3] = 3
    required_orthogonal_exact_primary_results: Literal[49] = 49
    required_precedence_exact_primary_results: Literal[8] = 8
    required_canned_transport_invocations: Literal[26] = 26
    required_invalid_probe_constructions: Literal[0] = 0
    maximum_body_byte_mismatches: Literal[0] = 0
    maximum_header_byte_mismatches: Literal[0] = 0
    maximum_route_intent_mismatches: Literal[0] = 0
    maximum_primary_failure_mismatches: Literal[0] = 0
    maximum_entropy_violations: Literal[0] = 0
    maximum_endpoint_selector_violations_accepted: Literal[0] = 0
    maximum_fallback_intent_violations_accepted: Literal[0] = 0
    maximum_models_array_violations_accepted: Literal[0] = 0
    maximum_metadata_missing_violations_accepted: Literal[0] = 0
    maximum_cache_policy_violations_accepted: Literal[0] = 0
    maximum_multi_attempt_violations_accepted: Literal[0] = 0
    maximum_model_substitutions_accepted: Literal[0] = 0
    maximum_provider_substitutions_accepted: Literal[0] = 0
    maximum_false_exact_endpoint_attestations: Literal[0] = 0
    maximum_p17_closure_violations: Literal[0] = 0
    maximum_p18_closure_violations: Literal[0] = 0
    maximum_p19_closure_violations: Literal[0] = 0
    required_documentation_fetches: Literal[0] = 0
    required_external_network_attempts: Literal[0] = 0
    required_credential_access_attempts: Literal[0] = 0
    required_provider_calls: Literal[0] = 0
    required_model_executions: Literal[0] = 0
    required_tool_calls: Literal[0] = 0
    required_canonical_application_invocations: Literal[0] = 0
    required_source_mutations: Literal[0] = 0
    required_sibling_mutations: Literal[0] = 0
    required_production_mutations: Literal[0] = 0
    required_receipt_mismatches: Literal[0] = 0
    required_artifact_claim_violations: Literal[0] = 0
    required_historical_lock_mismatches: Literal[0] = 0
    required_core_lock_mismatches: Literal[0] = 0
    maximum_official_response_wire_mapping_violations: Literal[0] = 0
    live_enforcement: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    exact_endpoint_response_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"
    production_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRouteControlThresholdsV1":
        payload = self.model_dump(mode="json", exclude={"thresholds_id"})
        expected = stable_contract_id("szorroutethresholdsv1", payload)
        if self.thresholds_id is not None and self.thresholds_id != expected:
            raise ContractValidationError("thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1 = OpenRouterRouteControlThresholdsV1()


class OpenRouterRouteControlCaseSetV1(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_CASE_SET_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_CASE_SET_SCHEMA_V1
    case_set_id: Optional[str] = None
    harness_id: Literal[
        OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1
    metrics_id: Literal[
        OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1
    validation_order_id: str
    failure_taxonomy_id: str
    thresholds_id: str
    cases: Tuple[OpenRouterRouteControlCaseV1, ...] = Field(
        min_length=63, max_length=63
    )
    total_case_count: Literal[63] = 63
    total_positive_request_cases: Literal[3] = 3
    total_positive_response_cases: Literal[3] = 3
    total_orthogonal_request_probes: Literal[29] = 29
    total_orthogonal_response_probes: Literal[20] = 20
    total_precedence_probes: Literal[8] = 8
    total_complete_route_intent_receipts: Literal[7] = 7
    total_complete_metadata_receipts: Literal[3] = 3
    total_canned_transport_invocations: Literal[26] = 26

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteControlCaseSetV1":
        if self.validation_order_id != (
            FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.validation_order_id
        ):
            raise ContractValidationError("case-set validation-order link changed")
        if self.failure_taxonomy_id != (
            FROZEN_OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_V1.failure_taxonomy_id
        ):
            raise ContractValidationError("case-set failure-taxonomy link changed")
        if self.thresholds_id != FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1.thresholds_id:
            raise ContractValidationError("case-set thresholds link changed")
        if self.cases != FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1:
            raise ContractValidationError("case membership or order changed")
        case_ids = tuple(case.case_id for case in self.cases)
        fingerprints = tuple(case.case_fingerprint for case in self.cases)
        if len(set(case_ids)) != self.total_case_count:
            raise ContractValidationError("case IDs must be unique")
        if len(set(fingerprints)) != self.total_case_count:
            raise ContractValidationError("case fingerprints must be unique")
        counts = {
            kind: sum(case.kind == kind for case in self.cases)
            for kind in OpenRouterRouteControlCaseKind
        }
        expected_counts = {
            _K.POSITIVE_REQUEST: self.total_positive_request_cases,
            _K.POSITIVE_RESPONSE: self.total_positive_response_cases,
            _K.ORTHOGONAL_REQUEST: self.total_orthogonal_request_probes,
            _K.ORTHOGONAL_RESPONSE: self.total_orthogonal_response_probes,
            _K.PRECEDENCE: self.total_precedence_probes,
        }
        if counts != expected_counts:
            raise ContractValidationError("case-kind counts changed")
        if sum(case.expected_canned_invocations for case in self.cases) != self.total_canned_transport_invocations:
            raise ContractValidationError("canned invocation total changed")
        if sum(case.expected_complete_route_intent_receipts for case in self.cases) != self.total_complete_route_intent_receipts:
            raise ContractValidationError("route-intent receipt total changed")
        if sum(case.expected_complete_metadata_receipts for case in self.cases) != self.total_complete_metadata_receipts:
            raise ContractValidationError("metadata receipt total changed")
        intentional_coverage = {
            field_name
            for case in self.cases
            for field_name, state in case.mutation_vector.__dict__.items()
            if field_name != "schema_version"
            and state == MutationState.INTENTIONALLY_CHANGED
        }
        if intentional_coverage != set(MUTATION_VECTOR_FIELD_NAMES_V1):
            raise ContractValidationError(
                "mutation vectors must intentionally cover all 22 frozen fields"
            )
        payload = self.model_dump(mode="json", exclude={"case_set_id"})
        expected = stable_contract_id("szorroutecasesetv1", payload)
        if self.case_set_id is not None and self.case_set_id != expected:
            raise ContractValidationError("case-set ID mismatch")
        object.__setattr__(self, "case_set_id", expected)
        return self


FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1 = OpenRouterRouteControlCaseSetV1(
    validation_order_id=(
        FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.validation_order_id or ""
    ),
    failure_taxonomy_id=(
        FROZEN_OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_V1.failure_taxonomy_id
        or ""
    ),
    thresholds_id=FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1.thresholds_id or "",
    cases=FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1,
)


OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1 = (
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1.case_set_id or ""
)
OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1 = (
    FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1.thresholds_id or ""
)


def frozen_openrouter_route_control_case_set_sha256_v1() -> str:
    payload = FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1.model_dump(
        mode="json", exclude={"case_set_id"}
    )
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


__all__ = [
    "FAILURE_GUARD_BY_CODE_V1",
    "FIRST_ROUTE_CONTROL_GUARD_WINS_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_PROBES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_REQUEST_PROBES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_RESPONSE_PROBES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_CASES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_REQUEST_CASES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_RESPONSE_CASES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_PRECEDENCE_PROBES_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1",
    "FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1",
    "FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1",
    "MUTATION_VECTOR_FIELD_NAMES_V1",
    "OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1",
    "OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1",
    "OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1",
    "OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1",
    "ORTHOGONAL_REQUEST_PROBE_IDS_V1",
    "ORTHOGONAL_RESPONSE_PROBE_IDS_V1",
    "POSITIVE_REQUEST_CASE_IDS_V1",
    "POSITIVE_RESPONSE_CASE_IDS_V1",
    "PRECEDENCE_PROBE_IDS_V1",
    "MutationState",
    "OpenRouterRouteControlCaseKind",
    "OpenRouterRouteControlCaseSetV1",
    "OpenRouterRouteControlCaseV1",
    "OpenRouterRouteControlExpectedOutcome",
    "OpenRouterRouteControlFailureCode",
    "OpenRouterRouteControlGuardId",
    "OpenRouterRouteControlGuardStage",
    "OpenRouterRouteControlLiteralMutationV1",
    "OpenRouterRouteControlMutationVectorV1",
    "OpenRouterRouteControlThresholdsV1",
    "frozen_openrouter_route_control_case_set_sha256_v1",
]

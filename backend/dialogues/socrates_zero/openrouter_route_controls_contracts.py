"""Immutable request-side contracts for OpenRouter route controls v1.

This additive Phase 8.5D surface binds one frozen specification manifest to one
network-inert request intent.  It contains no transport, credential, provider,
model, tool, CED, pricing, cost, or tokenizer integration.  In particular,
request intent is kept distinct from response attestation and live enforcement.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id


OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION = (
    "socrateszero-openrouter-route-controls/v1"
)
OPENROUTER_ROUTE_INTENT_SCHEMA_VERSION = "socrateszero-openrouter-route-intent/v1"
OPENROUTER_ROUTE_RENDERER_VERSION = "socrateszero-openrouter-route-renderer/v1"
OPENROUTER_ROUTE_HEADERS_SCHEMA_VERSION = (
    "socrateszero-openrouter-route-headers/v1"
)
OPENROUTER_CACHE_POLICY_SCHEMA_VERSION = (
    "socrateszero-openrouter-cache-policy/v1"
)
OPENROUTER_METADATA_POLICY_SCHEMA_VERSION = (
    "socrateszero-openrouter-router-metadata-policy/v1"
)
OPENROUTER_SPECIFICATION_BINDING_SCHEMA_VERSION = (
    "socrateszero-openrouter-specification-binding/v1"
)
OPENROUTER_PREPARED_ROUTE_REQUEST_SCHEMA_VERSION = (
    "socrateszero-openrouter-prepared-route-request/v1"
)
OPENROUTER_REQUEST_INTENT_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-openrouter-request-intent-receipt/v1"
)

OPENROUTER_ROUTE_PROVIDER_V1 = "openrouter"
OPENROUTER_ROUTE_MODEL_V1 = "openai/gpt-4.1-mini"
OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1 = "azure/swedencentral"
OPENROUTER_ATTESTED_BASE_PROVIDER_V1 = "azure"
OPENROUTER_ROUTE_MAX_TOKENS_V1 = 256
OPENROUTER_ROUTE_RESPONSE_FORMAT_V1 = "text"
OPENROUTER_ROUTE_TEMPERATURE_V1 = 0.0

OPENROUTER_METADATA_HEADER_NAME_V1 = "X-OpenRouter-Metadata"
OPENROUTER_METADATA_HEADER_VALUE_V1 = "enabled"
OPENROUTER_CACHE_HEADER_NAME_V1 = "X-OpenRouter-Cache"
OPENROUTER_CACHE_HEADER_VALUE_V1 = "false"
OPENROUTER_CONTENT_TYPE_HEADER_NAME_V1 = "Content-Type"
OPENROUTER_CONTENT_TYPE_HEADER_VALUE_V1 = "application/json"

OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-spec-evidence-gate-v0/"
    "evidence/openrouter_official_specification_evidence_v0.json"
)
OPENROUTER_SPECIFICATION_MANIFEST_SCHEMA_V0 = (
    "socrateszero-openrouter-official-specification-evidence/v0"
)
OPENROUTER_SPECIFICATION_MANIFEST_ID_V1 = (
    "szorspecmanifestv0_"
    "6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03"
)
OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1 = (
    "6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03"
)
OPENROUTER_SPECIFICATION_DECISION_V1 = (
    "OPENROUTER_ROUTE_CONTROL_MILESTONE_ONLY_EARNED"
)

OPENROUTER_RELEVANT_FACT_DIGESTS_V1: Tuple[Tuple[str, str], ...] = (
    (
        "ORSPEC-F01",
        "d9705712623f504a2a0c6daa9de3d20c9d3630193828e9d3fb3bf5cc14418329",
    ),
    (
        "ORSPEC-F02",
        "d48518fa88753ad602140cb54e09f7f046a784b94edcd4938988c605f799a065",
    ),
    (
        "ORSPEC-F03",
        "2802827a00e66d202eae3e7a3e74c2c3650759cabdd3a3ccaa3b16005c732ace",
    ),
    (
        "ORSPEC-F04",
        "5c5e77e1b7257136a9059f7225dc106d59b5fc7dcb982059435f8a93bcdfbba5",
    ),
    (
        "ORSPEC-F05",
        "f7470d7a4aaa2848b93ee6fd3b20afe9c8f67f76826c6bb7201013414cea7190",
    ),
    (
        "ORSPEC-F10",
        "d4d00b06485a5f2bb2cff4a82cf67158e8179608593787ac549660440d607cab",
    ),
    (
        "ORSPEC-F13",
        "00653dc019d60c69d800e2acd59ab9897bce31fa874e15e5121abf971c383ca2",
    ),
)
OPENROUTER_RELEVANT_FACT_IDS_V1 = tuple(
    evidence_id for evidence_id, _ in OPENROUTER_RELEVANT_FACT_DIGESTS_V1
)

OPENROUTER_FROZEN_SYSTEM_MESSAGE_V1 = (
    "Ask one concise opening Socratic question without answering the user's question."
)
OPENROUTER_FROZEN_USER_MESSAGE_V1 = (
    "Is knowledge merely justified true belief?"
)


class OpenRouterDeferredStatusV1(str, Enum):
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    DEFERRED_NOT_RENDERED = "DEFERRED_NOT_RENDERED"


class OpenRouterOfflineProofStatusV1(str, Enum):
    PROVEN_OFFLINE = "PROVEN_OFFLINE"
    NOT_PROVEN = "NOT_PROVEN"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class _FrozenRouteContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


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


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class OpenRouterSpecificationFactBindingV1(_FrozenRouteContractV1):
    evidence_id: str = Field(pattern=r"^ORSPEC-F[0-9]{2}$")
    semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


_DEFAULT_FACT_BINDINGS_V1 = tuple(
    OpenRouterSpecificationFactBindingV1(
        evidence_id=evidence_id,
        semantic_sha256=semantic_sha256,
    )
    for evidence_id, semantic_sha256 in OPENROUTER_RELEVANT_FACT_DIGESTS_V1
)


class OpenRouterSpecificationManifestBindingV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_SPECIFICATION_BINDING_SCHEMA_VERSION
    ] = OPENROUTER_SPECIFICATION_BINDING_SCHEMA_VERSION
    binding_id: Optional[str] = None
    manifest_path: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    manifest_schema_version: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_SCHEMA_V0
    ] = OPENROUTER_SPECIFICATION_MANIFEST_SCHEMA_V0
    manifest_id: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    manifest_semantic_sha256: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    relevant_fact_bindings: Tuple[OpenRouterSpecificationFactBindingV1, ...] = (
        _DEFAULT_FACT_BINDINGS_V1
    )
    candidate_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    candidate_exact_provider_endpoint: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    specification_basis: Literal[
        "FROZEN_PHASE_8_5C_MANIFEST"
    ] = "FROZEN_PHASE_8_5C_MANIFEST"
    external_revalidation: Literal[
        "NOT_PERFORMED_IN_THIS_BRANCH"
    ] = "NOT_PERFORMED_IN_THIS_BRANCH"
    live_authorization: Literal[
        "REQUIRES_REVALIDATION_LATER"
    ] = "REQUIRES_REVALIDATION_LATER"

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterSpecificationManifestBindingV1":
        actual = tuple(
            (item.evidence_id, item.semantic_sha256)
            for item in self.relevant_fact_bindings
        )
        if actual != OPENROUTER_RELEVANT_FACT_DIGESTS_V1:
            raise ContractValidationError(
                "specification fact bindings differ from the frozen manifest evidence"
            )
        _freeze_id(
            self,
            field_name="binding_id",
            prefix="szorspecbindingv1",
            payload=self.model_dump(mode="json", exclude={"binding_id"}),
        )
        return self


class OpenRouterCachePolicyV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_CACHE_POLICY_SCHEMA_VERSION
    ] = OPENROUTER_CACHE_POLICY_SCHEMA_VERSION
    cache_policy_id: Optional[str] = None
    header_name: Literal[
        OPENROUTER_CACHE_HEADER_NAME_V1
    ] = OPENROUTER_CACHE_HEADER_NAME_V1
    header_value: Literal[
        OPENROUTER_CACHE_HEADER_VALUE_V1
    ] = OPENROUTER_CACHE_HEADER_VALUE_V1
    openrouter_response_cache_request_intent: Literal[
        "DISABLED"
    ] = "DISABLED"
    prompt_cache_control_state: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    missing_metadata_is_success: Literal[False] = False
    cache_hit_inferred_from_missing_metadata: Literal[False] = False

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterCachePolicyV1":
        _freeze_id(
            self,
            field_name="cache_policy_id",
            prefix="szorcachepolicyv1",
            payload=self.model_dump(mode="json", exclude={"cache_policy_id"}),
        )
        return self


class OpenRouterMetadataPolicyV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_METADATA_POLICY_SCHEMA_VERSION
    ] = OPENROUTER_METADATA_POLICY_SCHEMA_VERSION
    metadata_policy_id: Optional[str] = None
    header_name: Literal[
        OPENROUTER_METADATA_HEADER_NAME_V1
    ] = OPENROUTER_METADATA_HEADER_NAME_V1
    header_value: Literal[
        OPENROUTER_METADATA_HEADER_VALUE_V1
    ] = OPENROUTER_METADATA_HEADER_VALUE_V1
    response_metadata_required: Literal[True] = True
    successful_attempt_required: Literal[1] = 1
    attempts_list_policy: Literal["OPTIONAL_IF_ABSENT_VALIDATED_IF_PRESENT"] = (
        "OPTIONAL_IF_ABSENT_VALIDATED_IF_PRESENT"
    )
    actual_model_policy: Literal["EXACT_CODEPOINT_EQUALITY_REQUIRED"] = (
        "EXACT_CODEPOINT_EQUALITY_REQUIRED"
    )
    provider_attestation_granularity: Literal[
        "BROAD_OR_BASE_PROVIDER_ONLY"
    ] = "BROAD_OR_BASE_PROVIDER_ONLY"
    exact_endpoint_response_attestation: Literal[
        OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    ] = OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    unknown_fields_authority: Literal["OPAQUE_NON_AUTHORITATIVE"] = (
        "OPAQUE_NON_AUTHORITATIVE"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterMetadataPolicyV1":
        _freeze_id(
            self,
            field_name="metadata_policy_id",
            prefix="szormetadatapolicyv1",
            payload=self.model_dump(mode="json", exclude={"metadata_policy_id"}),
        )
        return self


class OpenRouterRouteHeaderPolicyV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_HEADERS_SCHEMA_VERSION
    ] = OPENROUTER_ROUTE_HEADERS_SCHEMA_VERSION
    header_policy_id: Optional[str] = None
    content_type_name: Literal[
        OPENROUTER_CONTENT_TYPE_HEADER_NAME_V1
    ] = OPENROUTER_CONTENT_TYPE_HEADER_NAME_V1
    content_type_value: Literal[
        OPENROUTER_CONTENT_TYPE_HEADER_VALUE_V1
    ] = OPENROUTER_CONTENT_TYPE_HEADER_VALUE_V1
    metadata_policy: OpenRouterMetadataPolicyV1 = Field(
        default_factory=OpenRouterMetadataPolicyV1
    )
    cache_policy: OpenRouterCachePolicyV1 = Field(
        default_factory=OpenRouterCachePolicyV1
    )
    canonical_casing_policy: Literal["EXACT_FROZEN_NAMES"] = "EXACT_FROZEN_NAMES"
    representation: Literal[
        "CANONICAL_APPLICATION_HEADER_JSON_NOT_HTTP_WIRE_BYTES"
    ] = "CANONICAL_APPLICATION_HEADER_JSON_NOT_HTTP_WIRE_BYTES"
    authorization_header_state: Literal["ABSENT"] = "ABSENT"
    credential_material_allowed: Literal[False] = False
    additional_headers: Tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteHeaderPolicyV1":
        if self.additional_headers:
            raise ContractValidationError("additional semantic headers must be absent")
        _freeze_id(
            self,
            field_name="header_policy_id",
            prefix="szorrouteheadersv1",
            payload=self.model_dump(mode="json", exclude={"header_policy_id"}),
        )
        return self

    def semantic_headers(self) -> dict[str, str]:
        return {
            self.content_type_name: self.content_type_value,
            self.cache_policy.header_name: self.cache_policy.header_value,
            self.metadata_policy.header_name: self.metadata_policy.header_value,
        }


class OpenRouterRouteIntentV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_INTENT_SCHEMA_VERSION
    ] = OPENROUTER_ROUTE_INTENT_SCHEMA_VERSION
    route_intent_contract_id: Optional[str] = None
    router_id: Literal[OPENROUTER_ROUTE_PROVIDER_V1] = OPENROUTER_ROUTE_PROVIDER_V1
    model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    models_field_status: Literal["ABSENT"] = "ABSENT"
    provider_only: Tuple[Literal[OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1], ...] = (
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    )
    provider_order: Tuple[Literal[OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1], ...] = (
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    )
    provider_order_semantics: Literal[
        "PREFERENCE_ONLY_WITH_ONLY_AS_HARD_RESTRICTION"
    ] = "PREFERENCE_ONLY_WITH_ONLY_AS_HARD_RESTRICTION"
    provider_allow_fallbacks: Literal[False] = False
    model_fallback_policy: Literal[
        "DISABLED_BY_EXACT_MODEL_AND_MODELS_ABSENT"
    ] = "DISABLED_BY_EXACT_MODEL_AND_MODELS_ABSENT"
    provider_require_parameters: Literal[True] = True
    max_price_status: Literal[
        OpenRouterDeferredStatusV1.DEFERRED_NOT_RENDERED
    ] = OpenRouterDeferredStatusV1.DEFERRED_NOT_RENDERED
    stream: Literal[False] = False
    tools: Tuple[()] = ()
    tool_choice_status: Literal["ABSENT"] = "ABSENT"
    temperature: Literal[OPENROUTER_ROUTE_TEMPERATURE_V1] = (
        OPENROUTER_ROUTE_TEMPERATURE_V1
    )
    max_tokens: Literal[OPENROUTER_ROUTE_MAX_TOKENS_V1] = (
        OPENROUTER_ROUTE_MAX_TOKENS_V1
    )
    response_format: Literal[OPENROUTER_ROUTE_RESPONSE_FORMAT_V1] = (
        OPENROUTER_ROUTE_RESPONSE_FORMAT_V1
    )
    system_message: Literal[
        OPENROUTER_FROZEN_SYSTEM_MESSAGE_V1
    ] = OPENROUTER_FROZEN_SYSTEM_MESSAGE_V1
    user_message: Literal[
        OPENROUTER_FROZEN_USER_MESSAGE_V1
    ] = OPENROUTER_FROZEN_USER_MESSAGE_V1

    @field_validator(
        "provider_allow_fallbacks",
        "provider_require_parameters",
        "stream",
        mode="before",
    )
    @classmethod
    def exact_boolean_types(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("route boolean controls must use exact JSON booleans")
        return value

    @field_validator("max_tokens", mode="before")
    @classmethod
    def exact_max_tokens_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("max_tokens must use an exact JSON integer")
        return value

    @field_validator("temperature", mode="before")
    @classmethod
    def exact_temperature_type(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("temperature must use the frozen JSON number form")
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteIntentV1":
        if self.provider_only != (OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,):
            raise ContractValidationError("provider.only must be the exact singleton")
        if self.provider_order != self.provider_only:
            raise ContractValidationError("provider.order must equal provider.only")
        if self.tools:
            raise ContractValidationError("tools must remain disabled")
        _freeze_id(
            self,
            field_name="route_intent_contract_id",
            prefix="szorrouteintentcontractv1",
            payload=self.model_dump(
                mode="json", exclude={"route_intent_contract_id"}
            ),
        )
        return self

    def application_body(self) -> dict[str, object]:
        return {
            "max_tokens": self.max_tokens,
            "messages": [
                {"content": self.system_message, "role": "system"},
                {"content": self.user_message, "role": "user"},
            ],
            "model": self.model,
            "provider": {
                "allow_fallbacks": self.provider_allow_fallbacks,
                "only": list(self.provider_only),
                "order": list(self.provider_order),
                "require_parameters": self.provider_require_parameters,
            },
            "response_format": {"type": self.response_format},
            "stream": self.stream,
            "temperature": self.temperature,
            "tools": list(self.tools),
        }


class OpenRouterRouteControlPolicyV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION
    ] = OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION
    route_control_policy_id: Optional[str] = None
    specification_binding: OpenRouterSpecificationManifestBindingV1 = Field(
        default_factory=OpenRouterSpecificationManifestBindingV1
    )
    route_intent: OpenRouterRouteIntentV1 = Field(
        default_factory=OpenRouterRouteIntentV1
    )
    header_policy: OpenRouterRouteHeaderPolicyV1 = Field(
        default_factory=OpenRouterRouteHeaderPolicyV1
    )
    request_intent_status: Literal[
        OpenRouterOfflineProofStatusV1.PROVEN_OFFLINE
    ] = OpenRouterOfflineProofStatusV1.PROVEN_OFFLINE
    live_server_enforcement: Literal[
        OpenRouterOfflineProofStatusV1.NOT_PROVEN
    ] = OpenRouterOfflineProofStatusV1.NOT_PROVEN
    exact_endpoint_response_attestation: Literal[
        OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    ] = OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    p17_input_token_bound: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    p18_pricing_record: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    p19_cost_bound: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"
    real_provider_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteControlPolicyV1":
        if (
            self.specification_binding.candidate_model
            != self.route_intent.model
            or self.specification_binding.candidate_exact_provider_endpoint
            != self.route_intent.provider_only[0]
        ):
            raise ContractValidationError(
                "route intent differs from its frozen specification binding"
            )
        if (
            self.header_policy.metadata_policy.exact_endpoint_response_attestation
            is not self.exact_endpoint_response_attestation
        ):
            raise ContractValidationError(
                "metadata and route-control endpoint attestations differ"
            )
        _freeze_id(
            self,
            field_name="route_control_policy_id",
            prefix="szorroutecontrolsv1",
            payload=self.model_dump(mode="json", exclude={"route_control_policy_id"}),
        )
        return self


class OpenRouterRequestIntentReceiptV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_REQUEST_INTENT_RECEIPT_SCHEMA_VERSION
    ] = OPENROUTER_REQUEST_INTENT_RECEIPT_SCHEMA_VERSION
    receipt_id: Optional[str] = None
    receipt_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    specification_manifest_id: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    specification_manifest_sha256: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    route_control_policy_id: str = Field(min_length=1)
    route_intent_contract_id: str = Field(min_length=1)
    route_intent_id: str = Field(pattern=r"^szorrouteintent_[0-9a-f]{64}$")
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    exact_endpoint_selector: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    model_fallback_policy: Literal[
        "DISABLED_BY_EXACT_MODEL_AND_MODELS_ABSENT"
    ] = "DISABLED_BY_EXACT_MODEL_AND_MODELS_ABSENT"
    provider_fallback_policy: Literal["DISABLED_REQUEST_INTENT"] = (
        "DISABLED_REQUEST_INTENT"
    )
    require_parameters: Literal[True] = True
    max_price_status: Literal[
        OpenRouterDeferredStatusV1.DEFERRED_NOT_RENDERED
    ] = OpenRouterDeferredStatusV1.DEFERRED_NOT_RENDERED
    stream: Literal[False] = False
    tools_status: Literal["DISABLED"] = "DISABLED"
    metadata_header_status: Literal["EXACT_ENABLED"] = "EXACT_ENABLED"
    cache_header_status: Literal["EXACT_DISABLED"] = "EXACT_DISABLED"
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(ge=1)
    semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_headers_length: int = Field(ge=1)
    frozen_evidence_record_ids: Tuple[str, ...] = OPENROUTER_RELEVANT_FACT_IDS_V1
    p17_input_token_bound: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    p18_pricing_record: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    p19_cost_bound: Literal[
        OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    ] = OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    live_server_enforcement: Literal[
        OpenRouterOfflineProofStatusV1.NOT_PROVEN
    ] = OpenRouterOfflineProofStatusV1.NOT_PROVEN
    exact_endpoint_response_attestation: Literal[
        OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    ] = OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    real_provider_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRequestIntentReceiptV1":
        if self.frozen_evidence_record_ids != OPENROUTER_RELEVANT_FACT_IDS_V1:
            raise ContractValidationError("receipt evidence-record binding changed")
        payload = self.model_dump(
            mode="json", exclude={"receipt_id", "receipt_sha256"}
        )
        expected_sha256 = _sha256(canonical_json(payload).encode("utf-8"))
        if self.receipt_sha256 is not None and self.receipt_sha256 != expected_sha256:
            raise ContractValidationError("receipt_sha256 does not match receipt content")
        object.__setattr__(self, "receipt_sha256", expected_sha256)
        expected_id = f"szorrouteintentreceiptv1_{expected_sha256}"
        if self.receipt_id is not None and self.receipt_id != expected_id:
            raise ContractValidationError("receipt_id does not match receipt content")
        object.__setattr__(self, "receipt_id", expected_id)
        return self


class OpenRouterPreparedRouteRequestV1(_FrozenRouteContractV1):
    schema_version: Literal[
        OPENROUTER_PREPARED_ROUTE_REQUEST_SCHEMA_VERSION
    ] = OPENROUTER_PREPARED_ROUTE_REQUEST_SCHEMA_VERSION
    prepared_request_id: Optional[str] = None
    renderer_version: Literal[
        OPENROUTER_ROUTE_RENDERER_VERSION
    ] = OPENROUTER_ROUTE_RENDERER_VERSION
    route_control_policy: OpenRouterRouteControlPolicyV1
    canonical_body_json: str
    canonical_semantic_headers_json: str
    body_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    body_length: Optional[int] = Field(default=None, ge=1)
    semantic_headers_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    semantic_headers_length: Optional[int] = Field(default=None, ge=1)
    route_intent_id: Optional[str] = Field(
        default=None, pattern=r"^szorrouteintent_[0-9a-f]{64}$"
    )
    request_intent_receipt: Optional[OpenRouterRequestIntentReceiptV1] = None

    @staticmethod
    def _validated_canonical_object(value: str, field_name: str) -> dict[str, object]:
        try:
            raw = value.encode("utf-8")
            parsed = json.loads(raw)
        except (UnicodeEncodeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractValidationError(f"{field_name} must be UTF-8 JSON") from exc
        if not isinstance(parsed, dict) or canonical_json(parsed).encode("utf-8") != raw:
            raise ContractValidationError(f"{field_name} must be canonical JSON")
        return parsed

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterPreparedRouteRequestV1":
        body = self._validated_canonical_object(
            self.canonical_body_json, "canonical_body_json"
        )
        headers = self._validated_canonical_object(
            self.canonical_semantic_headers_json,
            "canonical_semantic_headers_json",
        )
        expected_body = self.route_control_policy.route_intent.application_body()
        expected_headers = self.route_control_policy.header_policy.semantic_headers()
        if canonical_json(body) != canonical_json(expected_body):
            raise ContractValidationError(
                "prepared body differs from the frozen route-control policy"
            )
        if canonical_json(headers) != canonical_json(expected_headers):
            raise ContractValidationError(
                "prepared semantic headers differ from the frozen header policy"
            )

        body_bytes = self.canonical_body_json.encode("utf-8")
        header_bytes = self.canonical_semantic_headers_json.encode("utf-8")
        body_sha256 = _sha256(body_bytes)
        header_sha256 = _sha256(header_bytes)
        for field_name, supplied, expected in (
            ("body_sha256", self.body_sha256, body_sha256),
            ("body_length", self.body_length, len(body_bytes)),
            ("semantic_headers_sha256", self.semantic_headers_sha256, header_sha256),
            (
                "semantic_headers_length",
                self.semantic_headers_length,
                len(header_bytes),
            ),
        ):
            if supplied is not None and supplied != expected:
                raise ContractValidationError(
                    f"{field_name} does not match prepared request bytes"
                )
            object.__setattr__(self, field_name, expected)

        route_payload = {
            "body_length": len(body_bytes),
            "body_sha256": body_sha256,
            "route_control_policy_id": (
                self.route_control_policy.route_control_policy_id
            ),
            "semantic_headers_length": len(header_bytes),
            "semantic_headers_sha256": header_sha256,
            "specification_manifest_id": (
                self.route_control_policy.specification_binding.manifest_id
            ),
            "specification_manifest_sha256": (
                self.route_control_policy.specification_binding.manifest_semantic_sha256
            ),
        }
        expected_route_intent_id = stable_contract_id(
            "szorrouteintent", route_payload
        )
        if (
            self.route_intent_id is not None
            and self.route_intent_id != expected_route_intent_id
        ):
            raise ContractValidationError(
                "route_intent_id does not match body/header intent"
            )
        object.__setattr__(self, "route_intent_id", expected_route_intent_id)

        expected_receipt = OpenRouterRequestIntentReceiptV1(
            route_control_policy_id=(
                self.route_control_policy.route_control_policy_id or ""
            ),
            route_intent_contract_id=(
                self.route_control_policy.route_intent.route_intent_contract_id or ""
            ),
            route_intent_id=expected_route_intent_id,
            body_sha256=body_sha256,
            body_length=len(body_bytes),
            semantic_headers_sha256=header_sha256,
            semantic_headers_length=len(header_bytes),
        )
        if (
            self.request_intent_receipt is not None
            and self.request_intent_receipt != expected_receipt
        ):
            raise ContractValidationError(
                "request-intent receipt does not match prepared request"
            )
        object.__setattr__(self, "request_intent_receipt", expected_receipt)
        prepared_payload = self.model_dump(
            mode="json", exclude={"prepared_request_id"}
        )
        _freeze_id(
            self,
            field_name="prepared_request_id",
            prefix="szorpreparedroutev1",
            payload=prepared_payload,
        )
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


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def verify_openrouter_spec_manifest_v1(
    root: Path | None = None,
) -> OpenRouterSpecificationManifestBindingV1:
    """Verify the frozen Phase 8.5C manifest without any external access."""

    repository_root = _repository_root() if root is None else Path(root)
    path = repository_root / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractValidationError(
            "frozen OpenRouter specification manifest is unavailable"
        ) from exc
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError(
            "frozen OpenRouter specification manifest is not UTF-8 JSON"
        ) from exc
    if not isinstance(manifest, dict):
        raise ContractValidationError("specification manifest must be a JSON object")
    if manifest.get("schema_version") != OPENROUTER_SPECIFICATION_MANIFEST_SCHEMA_V0:
        raise ContractValidationError("specification manifest schema changed")
    if manifest.get("manifest_id") != OPENROUTER_SPECIFICATION_MANIFEST_ID_V1:
        raise ContractValidationError("specification manifest ID changed")
    if (
        manifest.get("manifest_semantic_sha256")
        != OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    ):
        raise ContractValidationError("specification manifest digest field changed")
    semantic_payload = {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_id", "manifest_semantic_sha256"}
    }
    if _sha256(canonical_json(semantic_payload).encode("utf-8")) != (
        OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    ):
        raise ContractValidationError("specification manifest semantic digest changed")
    if manifest.get("candidate_model") != OPENROUTER_ROUTE_MODEL_V1:
        raise ContractValidationError("specification candidate model changed")
    if (
        manifest.get("candidate_exact_provider_endpoint")
        != OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ):
        raise ContractValidationError("specification endpoint selector changed")
    if manifest.get("selected_decision") != OPENROUTER_SPECIFICATION_DECISION_V1:
        raise ContractValidationError("specification decision changed")
    if manifest.get("next_branch") != (
        "feature/socrates-zero-openrouter-route-controls-v1"
    ):
        raise ContractValidationError("specification next-branch authorization changed")
    if manifest.get("live_pilot_readiness") != "NOT_EARNED":
        raise ContractValidationError("specification live-readiness status changed")

    records = manifest.get("fact_records")
    if not isinstance(records, list):
        raise ContractValidationError("specification fact records are malformed")
    by_id: dict[str, Mapping[str, object]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("evidence_id"), str):
            raise ContractValidationError("specification fact record is malformed")
        evidence_id = record["evidence_id"]
        if evidence_id in by_id:
            raise ContractValidationError("specification fact IDs are not unique")
        by_id[evidence_id] = record
    for evidence_id, expected_digest in OPENROUTER_RELEVANT_FACT_DIGESTS_V1:
        record = by_id.get(evidence_id)
        if record is None:
            raise ContractValidationError(
                f"required specification fact {evidence_id} is absent"
            )
        normalized_fact = record.get("normalized_fact")
        if not isinstance(normalized_fact, str):
            raise ContractValidationError(
                f"required specification fact {evidence_id} is malformed"
            )
        if record.get("semantic_sha256") != expected_digest or _sha256(
            normalized_fact.encode("utf-8")
        ) != expected_digest:
            raise ContractValidationError(
                f"required specification fact {evidence_id} changed"
            )
    return OpenRouterSpecificationManifestBindingV1()


def default_openrouter_route_control_policy_v1(
    *,
    specification_binding: OpenRouterSpecificationManifestBindingV1 | None = None,
) -> OpenRouterRouteControlPolicyV1:
    binding = specification_binding or verify_openrouter_spec_manifest_v1()
    if type(binding) is not OpenRouterSpecificationManifestBindingV1:
        raise ContractValidationError(
            "specification binding must use the exact frozen v1 type"
        )
    return OpenRouterRouteControlPolicyV1(specification_binding=binding)


def _deep_read_only(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _deep_read_only(child) for key, child in value.items()}
        )
    if isinstance(value, list):
        return tuple(_deep_read_only(child) for child in value)
    return value


EXPECTED_OPENROUTER_ROUTE_BODY_V1 = _deep_read_only(
    OpenRouterRouteIntentV1().application_body()
)
EXPECTED_OPENROUTER_SEMANTIC_HEADERS_V1 = MappingProxyType(
    OpenRouterRouteHeaderPolicyV1().semantic_headers()
)
FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1 = canonical_json(
    OpenRouterRouteIntentV1().application_body()
)
FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1 = canonical_json(
    OpenRouterRouteHeaderPolicyV1().semantic_headers()
)


# Naming aliases used by sibling Phase 8.5D modules.
OPENROUTER_ROUTE_CONTROL_SCHEMA_VERSION = OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION
OPENROUTER_HEADER_POLICY_SCHEMA_VERSION = OPENROUTER_ROUTE_HEADERS_SCHEMA_VERSION
OPENROUTER_MODEL_ID_V1 = OPENROUTER_ROUTE_MODEL_V1
OPENROUTER_ENDPOINT_SELECTOR_V1 = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1


__all__ = [
    "EXPECTED_OPENROUTER_ROUTE_BODY_V1",
    "EXPECTED_OPENROUTER_SEMANTIC_HEADERS_V1",
    "FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1",
    "FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1",
    "OPENROUTER_ATTESTED_BASE_PROVIDER_V1",
    "OPENROUTER_CACHE_HEADER_NAME_V1",
    "OPENROUTER_CACHE_HEADER_VALUE_V1",
    "OPENROUTER_CACHE_POLICY_SCHEMA_VERSION",
    "OPENROUTER_CONTENT_TYPE_HEADER_NAME_V1",
    "OPENROUTER_CONTENT_TYPE_HEADER_VALUE_V1",
    "OPENROUTER_ENDPOINT_SELECTOR_V1",
    "OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1",
    "OPENROUTER_FROZEN_SYSTEM_MESSAGE_V1",
    "OPENROUTER_FROZEN_USER_MESSAGE_V1",
    "OPENROUTER_HEADER_POLICY_SCHEMA_VERSION",
    "OPENROUTER_METADATA_HEADER_NAME_V1",
    "OPENROUTER_METADATA_HEADER_VALUE_V1",
    "OPENROUTER_METADATA_POLICY_SCHEMA_VERSION",
    "OPENROUTER_MODEL_ID_V1",
    "OPENROUTER_PREPARED_ROUTE_REQUEST_SCHEMA_VERSION",
    "OPENROUTER_RELEVANT_FACT_DIGESTS_V1",
    "OPENROUTER_RELEVANT_FACT_IDS_V1",
    "OPENROUTER_REQUEST_INTENT_RECEIPT_SCHEMA_VERSION",
    "OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION",
    "OPENROUTER_ROUTE_CONTROL_SCHEMA_VERSION",
    "OPENROUTER_ROUTE_HEADERS_SCHEMA_VERSION",
    "OPENROUTER_ROUTE_INTENT_SCHEMA_VERSION",
    "OPENROUTER_ROUTE_MAX_TOKENS_V1",
    "OPENROUTER_ROUTE_MODEL_V1",
    "OPENROUTER_ROUTE_PROVIDER_V1",
    "OPENROUTER_ROUTE_RENDERER_VERSION",
    "OPENROUTER_ROUTE_RESPONSE_FORMAT_V1",
    "OPENROUTER_ROUTE_TEMPERATURE_V1",
    "OPENROUTER_SPECIFICATION_BINDING_SCHEMA_VERSION",
    "OPENROUTER_SPECIFICATION_DECISION_V1",
    "OPENROUTER_SPECIFICATION_MANIFEST_ID_V1",
    "OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1",
    "OPENROUTER_SPECIFICATION_MANIFEST_SCHEMA_V0",
    "OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1",
    "OpenRouterCachePolicyV1",
    "OpenRouterDeferredStatusV1",
    "OpenRouterMetadataPolicyV1",
    "OpenRouterOfflineProofStatusV1",
    "OpenRouterPreparedRouteRequestV1",
    "OpenRouterRequestIntentReceiptV1",
    "OpenRouterRouteControlPolicyV1",
    "OpenRouterRouteHeaderPolicyV1",
    "OpenRouterRouteIntentV1",
    "OpenRouterSpecificationFactBindingV1",
    "OpenRouterSpecificationManifestBindingV1",
    "default_openrouter_route_control_policy_v1",
    "verify_openrouter_spec_manifest_v1",
]

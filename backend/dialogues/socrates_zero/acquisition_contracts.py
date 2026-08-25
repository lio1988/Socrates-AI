"""Frozen contracts for the canned-only observation-acquisition boundary.

This module is deliberately runtime-inert.  It defines immutable identities,
evidence envelopes, receipts, and the frozen validation order for the
SocratesZero external-observation acquisition experiment.  It does not import a
provider, inspect credentials, open a network connection, parse response
content, or call the canonical CED application seam.

An acquired observation described here is explicitly unadmitted,
non-canonical, non-governing, and not applied.  A later, separately authorized
admission/application layer owns every canonical decision.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any, ClassVar, Dict, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import (
    ActionKind,
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


ACQUISITION_CONTRACT_ID = "socrateszero-external-observation-acquisition/v0"
ACQUISITION_CAPABILITY_SNAPSHOT_SCHEMA_VERSION = (
    "socrateszero-acquisition-capability-snapshot/v0"
)
ACQUISITION_CONTROL_POLICY_SCHEMA_VERSION = (
    "socrateszero-acquisition-control-policy/v0"
)
ACQUISITION_REQUEST_CONFIGURATION_SCHEMA_VERSION = (
    "socrateszero-acquisition-request-configuration/v0"
)
PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION = (
    "socrateszero-acquisition-provider-visible-request/v0"
)
ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION = (
    "socrateszero-acquisition-semantic-request/v0"
)
ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION = (
    "socrateszero-acquisition-transport-attempt/v0"
)
CANNED_TRANSPORT_ENVELOPE_SCHEMA_VERSION = "socrateszero-canned-transport/v0"
ACQUISITION_EXECUTION_USAGE_SCHEMA_VERSION = (
    "socrateszero-acquisition-execution-usage/v0"
)
ACQUISITION_HISTORICAL_USAGE_SCHEMA_VERSION = (
    "socrateszero-acquisition-historical-usage/v0"
)
UNADMITTED_OBSERVATION_SCHEMA_VERSION = "socrateszero-unadmitted-observation/v0"
ACQUISITION_ATTEMPT_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-acquisition-attempt-receipt/v0"
)
ACQUISITION_AGGREGATE_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-acquisition-aggregate-receipt/v0"
)
ACQUISITION_ISOLATION_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-acquisition-isolation-receipt/v0"
)
ACQUISITION_RETENTION_POLICY_SCHEMA_VERSION = (
    "socrateszero-acquisition-retention-policy/v0"
)
ACQUISITION_RETENTION_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-acquisition-retention-receipt/v0"
)
ACQUISITION_VALIDATION_ORDER_SCHEMA_VERSION = (
    "socrateszero-acquisition-validation-order/v0"
)
ACQUISITION_FAILURE_TAXONOMY_SCHEMA_VERSION = (
    "socrateszero-acquisition-failure-taxonomy/v0"
)
ACQUISITION_EXPERIMENT_ARTIFACT_SCHEMA_VERSION = (
    "socrateszero-acquisition-artifact/v0"
)

CANNED_TRANSPORT_ID = "socrateszero-canned-transport/v0"
SUPPORTED_ACTION_FAMILY = "ced-opening-socratic-question/v0"
FIRST_ACQUISITION_GUARD_WINS = "FIRST_ACQUISITION_GUARD_WINS"

_HEX64_PATTERN = r"^[0-9a-f]{64}$"


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _optional_nonblank(value: Optional[str]) -> Optional[str]:
    if value is not None:
        _nonblank(value)
    return value


def _semantic_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utf8_digest(value: str) -> str:
    try:
        payload = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractValidationError("text must be valid UTF-8") from exc
    return hashlib.sha256(payload).hexdigest()


def _canonical_strings(values: Tuple[str, ...], field_name: str) -> Tuple[str, ...]:
    ordered = tuple(sorted(values))
    if any(not item.strip() for item in ordered):
        raise ContractValidationError(f"{field_name} must not contain blanks")
    if len(set(ordered)) != len(ordered):
        raise ContractValidationError(f"{field_name} must not contain duplicates")
    return ordered


def _strict_optional_bool(value: object) -> object:
    if value is not None and type(value) is not bool:
        raise ValueError("value must be a strict boolean or null")
    return value


class _FrozenAcquisitionContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AcquisitionControlState(str, Enum):
    PROVEN_SUPPORTED = "PROVEN_SUPPORTED"
    PROVEN_DISABLED = "PROVEN_DISABLED"
    PROVEN_UNSUPPORTED = "PROVEN_UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class AcquisitionControlName(str, Enum):
    ACTUAL_PROVIDER_IDENTITY_VALIDATION = "actual_provider_identity_validation"
    ACTUAL_MODEL_IDENTITY_VALIDATION = "actual_model_identity_validation"
    ACTUAL_CONFIGURATION_IDENTITY_VALIDATION = (
        "actual_configuration_identity_validation"
    )
    FALLBACK = "fallback"
    EXPLICIT_RETRY = "explicit_retry"
    ADAPTER_RETRY = "adapter_retry"
    SDK_INTERNAL_RETRY = "sdk_internal_retry"
    HIDDEN_TRANSPORT_RETRY = "hidden_transport_retry"
    TOOLS = "tools"
    TEMPERATURE = "temperature"
    SEED = "seed"
    TIMEOUT = "timeout"
    TIMEOUT_WORKER_TERMINATION = "timeout_worker_termination"
    RAW_RESPONSE_CAPTURE = "raw_response_capture"
    NEW_USAGE_ACCOUNTING = "new_usage_accounting"
    TOKEN_REPORTING = "token_reporting"
    COST_REPORTING = "cost_reporting"
    EXTERNAL_WALL_TIME_REPORTING = "external_wall_time_reporting"
    EXTERNAL_NETWORK = "external_network"
    CREDENTIAL_ACCESS = "credential_access"
    CANNED_ONLY_TRANSPORT = "canned_only_transport"
    PROMPT_BYTE_DETERMINISM = "prompt_byte_determinism"
    TRANSPORT_METADATA_ISOLATION = "transport_metadata_isolation"


class AcquisitionTransportMode(str, Enum):
    CANNED_ONLY = "CANNED_ONLY"
    EXTERNAL = "EXTERNAL"


class AcquisitionSeedStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class ResourceKnowledgeState(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AcquisitionTransportStatus(str, Enum):
    DELIVERED = "DELIVERED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"
    REFUSED = "REFUSED"


class AcquisitionGuardStage(str, Enum):
    PRE_DISPATCH = "PRE_DISPATCH"
    POST_DISPATCH = "POST_DISPATCH"


class AcquisitionGuardState(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_REACHED = "NOT_REACHED"


class AcquisitionAttemptOutcome(str, Enum):
    ACQUIRED = "ACQUIRED"
    FAILED_CLOSED = "FAILED_CLOSED"


class AcquisitionFailureCode(str, Enum):
    INVALID_ACQUISITION_REQUEST = "INVALID_ACQUISITION_REQUEST"
    INVALID_SEMANTIC_IDENTITY = "INVALID_SEMANTIC_IDENTITY"
    IDENTITY_COLLISION = "IDENTITY_COLLISION"
    INVALID_CAPABILITY_SNAPSHOT = "INVALID_CAPABILITY_SNAPSHOT"
    REQUIRED_CONTROL_UNKNOWN = "REQUIRED_CONTROL_UNKNOWN"
    CANNED_ONLY_POLICY_VIOLATION = "CANNED_ONLY_POLICY_VIOLATION"
    EXTERNAL_NETWORK_FORBIDDEN = "EXTERNAL_NETWORK_FORBIDDEN"
    CREDENTIAL_ACCESS_FORBIDDEN = "CREDENTIAL_ACCESS_FORBIDDEN"
    EXACT_IDENTITY_VERIFICATION_UNAVAILABLE = (
        "EXACT_IDENTITY_VERIFICATION_UNAVAILABLE"
    )
    FALLBACK_CONTROL_UNPROVEN = "FALLBACK_CONTROL_UNPROVEN"
    RETRY_CONTROL_UNPROVEN = "RETRY_CONTROL_UNPROVEN"
    SDK_INTERNAL_RETRY_CONTROL_UNPROVEN = (
        "SDK_INTERNAL_RETRY_CONTROL_UNPROVEN"
    )
    TOOLS_NOT_DISABLED = "TOOLS_NOT_DISABLED"
    TIMEOUT_CANCELLATION_UNPROVEN = "TIMEOUT_CANCELLATION_UNPROVEN"
    RESOURCE_ACCOUNTING_INCOMPLETE = "RESOURCE_ACCOUNTING_INCOMPLETE"
    BUDGET_INCOMPLETE = "BUDGET_INCOMPLETE"
    PROMPT_ENTROPY_DETECTED = "PROMPT_ENTROPY_DETECTED"
    ISOLATION_PRECONDITION_FAILED = "ISOLATION_PRECONDITION_FAILED"
    CANNED_TRANSPORT_UNREGISTERED = "CANNED_TRANSPORT_UNREGISTERED"
    UNCOUNTED_CANNED_INVOCATION = "UNCOUNTED_CANNED_INVOCATION"
    TRANSPORT_TIMEOUT = "TRANSPORT_TIMEOUT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    TRANSPORT_WORKER_NOT_TERMINATED = "TRANSPORT_WORKER_NOT_TERMINATED"
    ACTUAL_PROVIDER_MISMATCH = "ACTUAL_PROVIDER_MISMATCH"
    ACTUAL_MODEL_MISMATCH = "ACTUAL_MODEL_MISMATCH"
    ACTUAL_CONFIGURATION_MISMATCH = "ACTUAL_CONFIGURATION_MISMATCH"
    FALLBACK_ACTIVATED = "FALLBACK_ACTIVATED"
    RETRY_ACTIVATED = "RETRY_ACTIVATED"
    TOOL_ACTIVATED = "TOOL_ACTIVATED"
    MISSING_RAW_OBSERVATION = "MISSING_RAW_OBSERVATION"
    INVALID_RESPONSE_DIGEST = "INVALID_RESPONSE_DIGEST"
    USAGE_INCOMPLETE = "USAGE_INCOMPLETE"
    RESOURCE_RECEIPT_MISMATCH = "RESOURCE_RECEIPT_MISMATCH"
    ISOLATION_FAILURE = "ISOLATION_FAILURE"
    RETENTION_POLICY_VIOLATION = "RETENTION_POLICY_VIOLATION"
    RECEIPT_MISMATCH = "RECEIPT_MISMATCH"


class AcquisitionGuardId(str, Enum):
    P01_REQUEST_INTEGRITY = "P01_REQUEST_INTEGRITY"
    P02_SEMANTIC_IDENTITY_INTEGRITY = "P02_SEMANTIC_IDENTITY_INTEGRITY"
    P03_CAPABILITY_SNAPSHOT_INTEGRITY = "P03_CAPABILITY_SNAPSHOT_INTEGRITY"
    P04_REQUIRED_CONTROL_COMPLETENESS = "P04_REQUIRED_CONTROL_COMPLETENESS"
    P05_CANNED_ONLY_TRANSPORT_MODE = "P05_CANNED_ONLY_TRANSPORT_MODE"
    P06_EXTERNAL_NETWORK_PROHIBITION = "P06_EXTERNAL_NETWORK_PROHIBITION"
    P07_CREDENTIAL_ACCESS_PROHIBITION = "P07_CREDENTIAL_ACCESS_PROHIBITION"
    P08_EXACT_IDENTITY_VERIFICATION = "P08_EXACT_IDENTITY_VERIFICATION"
    P09_FALLBACK_DISABLED = "P09_FALLBACK_DISABLED"
    P10_RETRY_DISABLED = "P10_RETRY_DISABLED"
    P11_SDK_INTERNAL_RETRY_DISABLED = "P11_SDK_INTERNAL_RETRY_DISABLED"
    P12_TOOLS_DISABLED = "P12_TOOLS_DISABLED"
    P13_TIMEOUT_WORKER_TERMINATION = "P13_TIMEOUT_WORKER_TERMINATION"
    P14_RESOURCE_ACCOUNTING = "P14_RESOURCE_ACCOUNTING"
    P15_BUDGET_SUFFICIENCY = "P15_BUDGET_SUFFICIENCY"
    P16_PROMPT_BYTE_DETERMINISM = "P16_PROMPT_BYTE_DETERMINISM"
    P17_ISOLATION_PRECONDITIONS = "P17_ISOLATION_PRECONDITIONS"
    P18_CANNED_TRANSPORT_REGISTRATION = "P18_CANNED_TRANSPORT_REGISTRATION"
    A01_CANNED_INVOCATION_COUNT = "A01_CANNED_INVOCATION_COUNT"
    A02_TRANSPORT_COMPLETION = "A02_TRANSPORT_COMPLETION"
    A03_TIMEOUT_WORKER_TERMINATION = "A03_TIMEOUT_WORKER_TERMINATION"
    A04_ACTUAL_PROVIDER_IDENTITY = "A04_ACTUAL_PROVIDER_IDENTITY"
    A05_ACTUAL_MODEL_IDENTITY = "A05_ACTUAL_MODEL_IDENTITY"
    A06_ACTUAL_CONFIGURATION_IDENTITY = "A06_ACTUAL_CONFIGURATION_IDENTITY"
    A07_FALLBACK_ACTIVATION = "A07_FALLBACK_ACTIVATION"
    A08_RETRY_ACTIVATION = "A08_RETRY_ACTIVATION"
    A09_TOOL_ACTIVATION = "A09_TOOL_ACTIVATION"
    A10_RAW_RESPONSE_PRESENCE = "A10_RAW_RESPONSE_PRESENCE"
    A11_RESPONSE_DIGEST_INTEGRITY = "A11_RESPONSE_DIGEST_INTEGRITY"
    A12_USAGE_COMPLETENESS = "A12_USAGE_COMPLETENESS"
    A13_RESOURCE_RECEIPT_INTEGRITY = "A13_RESOURCE_RECEIPT_INTEGRITY"
    A14_ISOLATION_INTEGRITY = "A14_ISOLATION_INTEGRITY"
    A15_RETENTION_PRIVACY_INTEGRITY = "A15_RETENTION_PRIVACY_INTEGRITY"
    A16_FINAL_RECEIPT_INTEGRITY = "A16_FINAL_RECEIPT_INTEGRITY"


class AcquisitionIsolationScope(str, Enum):
    SOURCE = "SOURCE"
    SIBLING = "SIBLING"
    PRODUCTION = "PRODUCTION"


class PromptRetentionMode(str, Enum):
    DIGEST_AND_REFERENCE = "DIGEST_AND_REFERENCE"


class ResponseRetentionMode(str, Enum):
    RAW_UTF8 = "RAW_UTF8"
    CONTENT_ADDRESSED_REFERENCE = "CONTENT_ADDRESSED_REFERENCE"


class AcquisitionDataClassification(str, Enum):
    NON_SENSITIVE_CANNED = "NON_SENSITIVE_CANNED"
    SENSITIVE = "SENSITIVE"
    UNKNOWN = "UNKNOWN"


class AcquisitionRedactionStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    UNKNOWN = "UNKNOWN"


class AcquisitionArtifactInclusionPolicy(str, Enum):
    DIGESTS_AND_REFERENCES = "DIGESTS_AND_REFERENCES"
    INCLUDE_RAW_NON_SENSITIVE_RESPONSE = "INCLUDE_RAW_NON_SENSITIVE_RESPONSE"
    EXCLUDE = "EXCLUDE"


class AcquisitionProviderModelBinding(_FrozenAcquisitionContract):
    provider_id: str
    model_id: str
    configuration_digest: str = Field(pattern=_HEX64_PATTERN)

    _nonblank_fields = field_validator("provider_id", "model_id")(_nonblank)

    def identity_payload(self) -> Dict[str, str]:
        return self.model_dump(mode="json")


class AcquisitionControlEvidence(_FrozenAcquisitionContract):
    name: AcquisitionControlName
    state: AcquisitionControlState
    evidence_id: str
    evidence_digest: str = Field(pattern=_HEX64_PATTERN)

    _evidence_id_nonblank = field_validator("evidence_id")(_nonblank)


class AcquisitionControlRequirement(_FrozenAcquisitionContract):
    name: AcquisitionControlName
    allowed_states: Tuple[AcquisitionControlState, ...]

    @model_validator(mode="after")
    def canonicalize(self) -> "AcquisitionControlRequirement":
        states = tuple(sorted(set(self.allowed_states), key=lambda item: item.value))
        if not states:
            raise ContractValidationError("allowed control states must not be empty")
        if AcquisitionControlState.UNKNOWN in states:
            raise ContractValidationError("required controls cannot allow UNKNOWN")
        object.__setattr__(self, "allowed_states", states)
        return self


_SUPPORTED = (AcquisitionControlState.PROVEN_SUPPORTED,)
_DISABLED = (AcquisitionControlState.PROVEN_DISABLED,)
_SEED_STATES = (
    AcquisitionControlState.PROVEN_SUPPORTED,
    AcquisitionControlState.PROVEN_UNSUPPORTED,
)

FROZEN_REQUIRED_CONTROL_STATES: Tuple[
    Tuple[AcquisitionControlName, Tuple[AcquisitionControlState, ...]], ...
] = tuple(
    sorted(
        (
            (AcquisitionControlName.ACTUAL_PROVIDER_IDENTITY_VALIDATION, _SUPPORTED),
            (AcquisitionControlName.ACTUAL_MODEL_IDENTITY_VALIDATION, _SUPPORTED),
            (
                AcquisitionControlName.ACTUAL_CONFIGURATION_IDENTITY_VALIDATION,
                _SUPPORTED,
            ),
            (AcquisitionControlName.FALLBACK, _DISABLED),
            (AcquisitionControlName.EXPLICIT_RETRY, _DISABLED),
            (AcquisitionControlName.ADAPTER_RETRY, _DISABLED),
            (AcquisitionControlName.SDK_INTERNAL_RETRY, _DISABLED),
            (AcquisitionControlName.HIDDEN_TRANSPORT_RETRY, _DISABLED),
            (AcquisitionControlName.TOOLS, _DISABLED),
            (AcquisitionControlName.TEMPERATURE, _SUPPORTED),
            (AcquisitionControlName.SEED, _SEED_STATES),
            (AcquisitionControlName.TIMEOUT, _SUPPORTED),
            (AcquisitionControlName.TIMEOUT_WORKER_TERMINATION, _SUPPORTED),
            (AcquisitionControlName.RAW_RESPONSE_CAPTURE, _SUPPORTED),
            (AcquisitionControlName.NEW_USAGE_ACCOUNTING, _SUPPORTED),
            (AcquisitionControlName.TOKEN_REPORTING, _SUPPORTED),
            (AcquisitionControlName.COST_REPORTING, _SUPPORTED),
            (AcquisitionControlName.EXTERNAL_WALL_TIME_REPORTING, _SUPPORTED),
            (AcquisitionControlName.EXTERNAL_NETWORK, _DISABLED),
            (AcquisitionControlName.CREDENTIAL_ACCESS, _DISABLED),
            (AcquisitionControlName.CANNED_ONLY_TRANSPORT, _SUPPORTED),
            (AcquisitionControlName.PROMPT_BYTE_DETERMINISM, _SUPPORTED),
            (AcquisitionControlName.TRANSPORT_METADATA_ISOLATION, _SUPPORTED),
        ),
        key=lambda item: item[0].value,
    )
)


class AcquisitionCapabilitySnapshot(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_CAPABILITY_SNAPSHOT_SCHEMA_VERSION
    ] = ACQUISITION_CAPABILITY_SNAPSHOT_SCHEMA_VERSION
    capability_snapshot_id: Optional[str] = None
    provider_id: str
    adapter_id: str
    adapter_version: str
    adapter_revision_digest: str = Field(pattern=_HEX64_PATTERN)
    requested_model_id: str
    transport_mode: AcquisitionTransportMode = AcquisitionTransportMode.CANNED_ONLY
    registered_canned_transport_ids: Tuple[str, ...]
    controls: Tuple[AcquisitionControlEvidence, ...]

    _nonblank_fields = field_validator(
        "provider_id", "adapter_id", "adapter_version", "requested_model_id"
    )(_nonblank)

    @model_validator(mode="after")
    def canonicalize_and_identify(self) -> "AcquisitionCapabilitySnapshot":
        transports = _canonical_strings(
            self.registered_canned_transport_ids,
            "registered_canned_transport_ids",
        )
        controls = tuple(sorted(self.controls, key=lambda item: item.name.value))
        names = tuple(item.name for item in controls)
        if len(set(names)) != len(names):
            raise ContractValidationError("capability control names must be unique")
        if set(names) != set(AcquisitionControlName):
            raise ContractValidationError(
                "capability snapshot must cover every audited acquisition control"
            )
        object.__setattr__(self, "registered_canned_transport_ids", transports)
        object.__setattr__(self, "controls", controls)
        expected = stable_contract_id("szacqcap", self.identity_payload())
        if (
            self.capability_snapshot_id is not None
            and self.capability_snapshot_id != expected
        ):
            raise ContractValidationError("capability_snapshot_id does not match")
        object.__setattr__(self, "capability_snapshot_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_id": self.provider_id,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "adapter_revision_digest": self.adapter_revision_digest,
            "requested_model_id": self.requested_model_id,
            "transport_mode": self.transport_mode.value,
            "registered_canned_transport_ids": list(
                self.registered_canned_transport_ids
            ),
            "controls": [item.model_dump(mode="json") for item in self.controls],
        }


class AcquisitionBudget(_FrozenAcquisitionContract):
    max_canned_transport_invocations: int = Field(ge=0, strict=True)
    max_external_network_attempts: Literal[0] = 0
    max_credential_access_attempts: Literal[0] = 0
    max_live_provider_calls: Literal[0] = 0
    max_provider_sdk_calls: Literal[0] = 0
    max_model_executions: Literal[0] = 0
    max_tool_calls: Literal[0] = 0
    max_new_tokens: Literal[0] = 0
    max_new_cost_microusd: Literal[0] = 0
    max_external_provider_wall_time_ms: Literal[0] = 0


class AcquisitionSeedSetting(_FrozenAcquisitionContract):
    status: AcquisitionSeedStatus
    value: Optional[int] = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def validate_status(self) -> "AcquisitionSeedSetting":
        if self.status is AcquisitionSeedStatus.SUPPORTED and self.value is None:
            raise ContractValidationError("supported seed requires a frozen value")
        if self.status is AcquisitionSeedStatus.UNSUPPORTED and self.value is not None:
            raise ContractValidationError("unsupported seed cannot contain a value")
        return self


class AcquisitionControlPolicy(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_CONTROL_POLICY_SCHEMA_VERSION
    ] = ACQUISITION_CONTROL_POLICY_SCHEMA_VERSION
    control_policy_id: Optional[str] = None
    transport_mode: Literal[
        AcquisitionTransportMode.CANNED_ONLY
    ] = AcquisitionTransportMode.CANNED_ONLY
    requirements: Tuple[AcquisitionControlRequirement, ...]
    temperature: float = Field(ge=0.0, le=2.0, strict=True)
    seed: AcquisitionSeedSetting
    max_output_tokens: int = Field(ge=1, strict=True)
    timeout_ms: int = Field(ge=1, strict=True)
    fallback_allowed: Literal[False] = False
    explicit_retry_limit: Literal[0] = 0
    adapter_retry_limit: Literal[0] = 0
    sdk_internal_retry_limit: Literal[0] = 0
    hidden_transport_retry_limit: Literal[0] = 0
    tools_allowed: Literal[False] = False
    budget: AcquisitionBudget

    @field_validator("temperature")
    @classmethod
    def finite_temperature(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("temperature must be finite")
        return value

    @model_validator(mode="after")
    def freeze_requirements_and_identify(self) -> "AcquisitionControlPolicy":
        requirements = tuple(
            sorted(self.requirements, key=lambda item: item.name.value)
        )
        if len({item.name for item in requirements}) != len(requirements):
            raise ContractValidationError("control requirements must be unique")
        actual = tuple((item.name, item.allowed_states) for item in requirements)
        if actual != FROZEN_REQUIRED_CONTROL_STATES:
            raise ContractValidationError("v0 required-control policy was weakened")
        object.__setattr__(self, "requirements", requirements)
        expected = stable_contract_id("szacqpolicy", self.identity_payload())
        if self.control_policy_id is not None and self.control_policy_id != expected:
            raise ContractValidationError("control_policy_id does not match")
        object.__setattr__(self, "control_policy_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "transport_mode": self.transport_mode.value,
            "requirements": [
                item.model_dump(mode="json") for item in self.requirements
            ],
            "temperature": self.temperature,
            "seed": self.seed.model_dump(mode="json"),
            "max_output_tokens": self.max_output_tokens,
            "timeout_ms": self.timeout_ms,
            "fallback_allowed": self.fallback_allowed,
            "explicit_retry_limit": self.explicit_retry_limit,
            "adapter_retry_limit": self.adapter_retry_limit,
            "sdk_internal_retry_limit": self.sdk_internal_retry_limit,
            "hidden_transport_retry_limit": self.hidden_transport_retry_limit,
            "tools_allowed": self.tools_allowed,
            "budget": self.budget.model_dump(mode="json"),
        }


class AcquisitionRequestConfiguration(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_REQUEST_CONFIGURATION_SCHEMA_VERSION
    ] = ACQUISITION_REQUEST_CONFIGURATION_SCHEMA_VERSION
    configuration_id: Optional[str] = None
    configuration_digest: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    temperature: float = Field(ge=0.0, le=2.0, strict=True)
    seed: AcquisitionSeedSetting
    max_output_tokens: int = Field(ge=1, strict=True)
    timeout_ms: int = Field(ge=1, strict=True)
    fallback_allowed: Literal[False] = False
    explicit_retry_limit: Literal[0] = 0
    adapter_retry_limit: Literal[0] = 0
    sdk_internal_retry_limit: Literal[0] = 0
    hidden_transport_retry_limit: Literal[0] = 0
    tools_allowed: Literal[False] = False
    provider_visible_metadata_digest: str = Field(pattern=_HEX64_PATTERN)

    @field_validator("temperature")
    @classmethod
    def finite_temperature(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("temperature must be finite")
        return value

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionRequestConfiguration":
        payload = self.identity_payload()
        digest = _semantic_digest(payload)
        expected_id = f"szacqconfig_{digest}"
        if self.configuration_digest is not None and self.configuration_digest != digest:
            raise ContractValidationError("configuration_digest does not match")
        if self.configuration_id is not None and self.configuration_id != expected_id:
            raise ContractValidationError("configuration_id does not match")
        object.__setattr__(self, "configuration_digest", digest)
        object.__setattr__(self, "configuration_id", expected_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "temperature": self.temperature,
            "seed": self.seed.model_dump(mode="json"),
            "max_output_tokens": self.max_output_tokens,
            "timeout_ms": self.timeout_ms,
            "fallback_allowed": self.fallback_allowed,
            "explicit_retry_limit": self.explicit_retry_limit,
            "adapter_retry_limit": self.adapter_retry_limit,
            "sdk_internal_retry_limit": self.sdk_internal_retry_limit,
            "hidden_transport_retry_limit": self.hidden_transport_retry_limit,
            "tools_allowed": self.tools_allowed,
            "provider_visible_metadata_digest": (
                self.provider_visible_metadata_digest
            ),
        }


class ProviderVisibleRequestBytes(_FrozenAcquisitionContract):
    """Exact canonical UTF-8 bytes of the provider-visible logical request."""

    schema_version: Literal[
        PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION
    ] = PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION
    provider_visible_request_id: Optional[str] = None
    rendering_version: str
    canonical_request_json: str
    byte_length: Optional[int] = Field(default=None, ge=0, strict=True)
    sha256: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)

    _rendering_version_nonblank = field_validator("rendering_version")(_nonblank)

    @model_validator(mode="after")
    def validate_bytes_and_identify(self) -> "ProviderVisibleRequestBytes":
        try:
            parsed = json.loads(self.canonical_request_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError(
                "provider-visible request must be valid canonical JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise ContractValidationError(
                "provider-visible request must be a JSON object"
            )
        if canonical_json(parsed) != self.canonical_request_json:
            raise ContractValidationError(
                "provider-visible request must use canonical JSON encoding"
            )
        raw = self.canonical_request_json.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        if self.byte_length is not None and self.byte_length != len(raw):
            raise ContractValidationError("provider-visible byte length does not match")
        if self.sha256 is not None and self.sha256 != digest:
            raise ContractValidationError("provider-visible SHA-256 does not match")
        object.__setattr__(self, "byte_length", len(raw))
        object.__setattr__(self, "sha256", digest)
        expected = stable_contract_id("szacqvisible", self.identity_payload())
        if (
            self.provider_visible_request_id is not None
            and self.provider_visible_request_id != expected
        ):
            raise ContractValidationError("provider_visible_request_id does not match")
        object.__setattr__(self, "provider_visible_request_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "rendering_version": self.rendering_version,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
        }


class AcquisitionSemanticRequest(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION
    ] = ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION
    acquisition_contract_id: Literal[ACQUISITION_CONTRACT_ID] = ACQUISITION_CONTRACT_ID
    semantic_request_id: Optional[str] = None
    source_capsule_id: str
    source_execution_id: str
    root_state_v1_id: str
    pending_transition_id: str
    canonical_task_identity_id: str
    supported_action_family: Literal[SUPPORTED_ACTION_FAMILY] = SUPPORTED_ACTION_FAMILY
    action_id: str
    action_kind: Literal[
        ActionKind.ASK_SOCRATIC_QUESTION
    ] = ActionKind.ASK_SOCRATIC_QUESTION
    complete_legal_action_ids: Tuple[str, ...]
    requested_binding: AcquisitionProviderModelBinding
    capability_snapshot_id: str
    control_policy_id: str
    request_configuration: AcquisitionRequestConfiguration
    provider_visible_request: ProviderVisibleRequestBytes

    _nonblank_fields = field_validator(
        "source_capsule_id",
        "source_execution_id",
        "root_state_v1_id",
        "pending_transition_id",
        "canonical_task_identity_id",
        "action_id",
        "capability_snapshot_id",
        "control_policy_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "AcquisitionSemanticRequest":
        legal_ids = _canonical_strings(
            self.complete_legal_action_ids,
            "complete_legal_action_ids",
        )
        if not legal_ids or self.action_id not in legal_ids:
            raise ContractValidationError(
                "selected action must belong to the supplied complete legal set"
            )
        if (
            self.requested_binding.configuration_digest
            != self.request_configuration.configuration_digest
        ):
            raise ContractValidationError(
                "requested binding and request configuration differ"
            )
        object.__setattr__(self, "complete_legal_action_ids", legal_ids)
        expected = stable_contract_id("szacqrequest", self.identity_payload())
        if self.semantic_request_id is not None and self.semantic_request_id != expected:
            raise ContractValidationError("semantic_request_id does not match")
        object.__setattr__(self, "semantic_request_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "acquisition_contract_id": self.acquisition_contract_id,
            "source_capsule_id": self.source_capsule_id,
            "source_execution_id": self.source_execution_id,
            "root_state_v1_id": self.root_state_v1_id,
            "pending_transition_id": self.pending_transition_id,
            "canonical_task_identity_id": self.canonical_task_identity_id,
            "supported_action_family": self.supported_action_family,
            "action_id": self.action_id,
            "action_kind": self.action_kind.value,
            "complete_legal_action_ids": list(self.complete_legal_action_ids),
            "requested_binding": self.requested_binding.identity_payload(),
            "capability_snapshot_id": self.capability_snapshot_id,
            "control_policy_id": self.control_policy_id,
            "request_configuration": self.request_configuration.identity_payload(),
            "provider_visible_request_id": (
                self.provider_visible_request.provider_visible_request_id
            ),
            "provider_visible_sha256": self.provider_visible_request.sha256,
            "provider_visible_byte_length": self.provider_visible_request.byte_length,
        }


class AcquisitionTransportAttempt(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION
    ] = ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION
    transport_attempt_id: Optional[str] = None
    semantic_request_id: str
    experiment_id: str
    branch_id: str
    attempt_ordinal: int = Field(ge=0, strict=True)
    canned_transport_id: str = CANNED_TRANSPORT_ID

    _nonblank_fields = field_validator(
        "semantic_request_id", "experiment_id", "branch_id", "canned_transport_id"
    )(_nonblank)

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionTransportAttempt":
        expected = stable_contract_id("szacqattempt", self.identity_payload())
        if self.transport_attempt_id is not None and self.transport_attempt_id != expected:
            raise ContractValidationError("transport_attempt_id does not match")
        object.__setattr__(self, "transport_attempt_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "semantic_request_id": self.semantic_request_id,
            "experiment_id": self.experiment_id,
            "branch_id": self.branch_id,
            "attempt_ordinal": self.attempt_ordinal,
            "canned_transport_id": self.canned_transport_id,
        }


class AcquisitionResourceQuantity(_FrozenAcquisitionContract):
    knowledge: ResourceKnowledgeState
    value: Optional[int] = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def validate_knowledge(self) -> "AcquisitionResourceQuantity":
        if self.knowledge is ResourceKnowledgeState.KNOWN and self.value is None:
            raise ContractValidationError("KNOWN resource quantity requires a value")
        if self.knowledge is not ResourceKnowledgeState.KNOWN and self.value is not None:
            raise ContractValidationError(
                "UNKNOWN/NOT_APPLICABLE resource quantity cannot contain a value"
            )
        return self

    @classmethod
    def known(cls, value: int) -> "AcquisitionResourceQuantity":
        return cls(knowledge=ResourceKnowledgeState.KNOWN, value=value)

    @classmethod
    def unknown(cls) -> "AcquisitionResourceQuantity":
        return cls(knowledge=ResourceKnowledgeState.UNKNOWN)

    @classmethod
    def not_applicable(cls) -> "AcquisitionResourceQuantity":
        return cls(knowledge=ResourceKnowledgeState.NOT_APPLICABLE)


class AcquisitionExecutionUsage(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_EXECUTION_USAGE_SCHEMA_VERSION
    ] = ACQUISITION_EXECUTION_USAGE_SCHEMA_VERSION
    execution_usage_id: Optional[str] = None
    canned_transport_invocations: AcquisitionResourceQuantity
    external_network_attempts: AcquisitionResourceQuantity
    credential_access_attempts: AcquisitionResourceQuantity
    live_provider_calls: AcquisitionResourceQuantity
    provider_sdk_calls: AcquisitionResourceQuantity
    model_executions: AcquisitionResourceQuantity
    tool_calls: AcquisitionResourceQuantity
    new_tokens: AcquisitionResourceQuantity
    new_cost_microusd: AcquisitionResourceQuantity
    external_provider_wall_time_ms: AcquisitionResourceQuantity

    _MEASURE_FIELDS: ClassVar[Tuple[str, ...]] = (
        "canned_transport_invocations",
        "external_network_attempts",
        "credential_access_attempts",
        "live_provider_calls",
        "provider_sdk_calls",
        "model_executions",
        "tool_calls",
        "new_tokens",
        "new_cost_microusd",
        "external_provider_wall_time_ms",
    )

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionExecutionUsage":
        expected = stable_contract_id("szacqusage", self.identity_payload())
        if self.execution_usage_id is not None and self.execution_usage_id != expected:
            raise ContractValidationError("execution_usage_id does not match")
        object.__setattr__(self, "execution_usage_id", expected)
        return self

    @property
    def complete(self) -> bool:
        return all(
            getattr(self, name).knowledge is ResourceKnowledgeState.KNOWN
            for name in self._MEASURE_FIELDS
        )

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            **{
                name: getattr(self, name).model_dump(mode="json")
                for name in self._MEASURE_FIELDS
            },
        }


class AcquisitionHistoricalUsage(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_HISTORICAL_USAGE_SCHEMA_VERSION
    ] = ACQUISITION_HISTORICAL_USAGE_SCHEMA_VERSION
    historical_usage_id: Optional[str] = None
    provenance_id: str
    source_observation_acquisitions: AcquisitionResourceQuantity
    source_model_calls: AcquisitionResourceQuantity
    source_tool_calls: AcquisitionResourceQuantity
    source_tokens: AcquisitionResourceQuantity
    source_cost_microusd: AcquisitionResourceQuantity
    source_external_wall_time_ms: AcquisitionResourceQuantity

    _provenance_nonblank = field_validator("provenance_id")(_nonblank)

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionHistoricalUsage":
        expected = stable_contract_id("szacqhistory", self.identity_payload())
        if self.historical_usage_id is not None and self.historical_usage_id != expected:
            raise ContractValidationError("historical_usage_id does not match")
        object.__setattr__(self, "historical_usage_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"historical_usage_id"})


FORBIDDEN_CANNED_ENVELOPE_FIELDS = frozenset(
    {
        "accepted",
        "benchmark_label",
        "canonical_rejection",
        "canonical_result",
        "expected_acceptance",
        "expected_failure",
        "expected_result",
        "expected_successor",
        "future_reward",
        "future_state",
        "ground_truth",
        "move_id",
        "reward",
        "successor",
        "value",
    }
)


class CannedTransportEnvelope(_FrozenAcquisitionContract):
    """Untrusted but immutable transport evidence; response content stays opaque."""

    schema_version: Literal[
        CANNED_TRANSPORT_ENVELOPE_SCHEMA_VERSION
    ] = CANNED_TRANSPORT_ENVELOPE_SCHEMA_VERSION
    envelope_id: Optional[str] = None
    transport_attempt_id: str
    transport_status: AcquisitionTransportStatus
    canned_transport_invocations: Optional[int] = Field(default=None, ge=0, strict=True)
    actual_binding: Optional[AcquisitionProviderModelBinding] = None
    raw_response_text: Optional[str] = None
    reported_raw_response_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    fallback_used: Optional[bool] = None
    explicit_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    adapter_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    sdk_internal_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    hidden_transport_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    tool_calls: Optional[int] = Field(default=None, ge=0, strict=True)
    timeout_fired: Optional[bool] = None
    cancellation_requested: Optional[bool] = None
    worker_terminated: Optional[bool] = None
    execution_usage: Optional[AcquisitionExecutionUsage] = None
    historical_usage: Optional[AcquisitionHistoricalUsage] = None
    source_provenance_id: Optional[str] = None
    transport_error_code: Optional[str] = None

    _transport_attempt_nonblank = field_validator("transport_attempt_id")(_nonblank)
    _optional_nonblank_fields = field_validator(
        "source_provenance_id", "transport_error_code"
    )(_optional_nonblank)
    _strict_bool_fields = field_validator(
        "fallback_used",
        "timeout_fired",
        "cancellation_requested",
        "worker_terminated",
        mode="before",
    )(_strict_optional_bool)

    @model_validator(mode="before")
    @classmethod
    def reject_ground_truth(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            forbidden = sorted(FORBIDDEN_CANNED_ENVELOPE_FIELDS & set(data))
            if forbidden:
                raise ContractValidationError(
                    "canned envelope contains forbidden evaluator/future fields: "
                    + ", ".join(forbidden)
                )
        return data

    @model_validator(mode="after")
    def identify_without_interpreting_content(self) -> "CannedTransportEnvelope":
        if self.raw_response_text is None:
            raw_digest = None
            raw_length = None
        else:
            raw_digest = _utf8_digest(self.raw_response_text)
            raw_length = len(self.raw_response_text.encode("utf-8"))
        expected = stable_contract_id(
            "szacqenvelope",
            {
                **self.model_dump(mode="json", exclude={"envelope_id", "raw_response_text"}),
                "computed_raw_response_digest": raw_digest,
                "computed_raw_response_length": raw_length,
            },
        )
        if self.envelope_id is not None and self.envelope_id != expected:
            raise ContractValidationError("envelope_id does not match")
        object.__setattr__(self, "envelope_id", expected)
        return self

    @property
    def computed_raw_response_digest(self) -> Optional[str]:
        return (
            _utf8_digest(self.raw_response_text)
            if self.raw_response_text is not None
            else None
        )


class AcquisitionIsolationFingerprint(_FrozenAcquisitionContract):
    scope: AcquisitionIsolationScope
    subject_id: str
    before_digest: str = Field(pattern=_HEX64_PATTERN)
    after_digest: str = Field(pattern=_HEX64_PATTERN)
    unchanged: Optional[bool] = None

    _subject_nonblank = field_validator("subject_id")(_nonblank)

    @model_validator(mode="after")
    def derive_unchanged(self) -> "AcquisitionIsolationFingerprint":
        expected = self.before_digest == self.after_digest
        if self.unchanged is not None and self.unchanged is not expected:
            raise ContractValidationError("isolation unchanged flag does not match")
        object.__setattr__(self, "unchanged", expected)
        return self


class AcquisitionIsolationReceipt(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_ISOLATION_RECEIPT_SCHEMA_VERSION
    ] = ACQUISITION_ISOLATION_RECEIPT_SCHEMA_VERSION
    isolation_receipt_id: Optional[str] = None
    semantic_request_id: str
    transport_attempt_id: str
    fingerprints: Tuple[AcquisitionIsolationFingerprint, ...]
    source_mutations: Optional[int] = Field(default=None, ge=0, strict=True)
    sibling_mutations: Optional[int] = Field(default=None, ge=0, strict=True)
    production_mutations: Optional[int] = Field(default=None, ge=0, strict=True)
    isolated: Optional[bool] = None

    _nonblank_fields = field_validator(
        "semantic_request_id", "transport_attempt_id"
    )(_nonblank)

    @model_validator(mode="after")
    def derive_counts_and_identify(self) -> "AcquisitionIsolationReceipt":
        rows = tuple(sorted(self.fingerprints, key=lambda item: item.scope.value))
        if len(rows) != len(AcquisitionIsolationScope) or {
            item.scope for item in rows
        } != set(AcquisitionIsolationScope):
            raise ContractValidationError(
                "isolation receipt requires one source, sibling, and production row"
            )
        counts = {
            scope: sum(item.scope is scope and not bool(item.unchanged) for item in rows)
            for scope in AcquisitionIsolationScope
        }
        expected_values = (
            counts[AcquisitionIsolationScope.SOURCE],
            counts[AcquisitionIsolationScope.SIBLING],
            counts[AcquisitionIsolationScope.PRODUCTION],
        )
        supplied_values = (
            self.source_mutations,
            self.sibling_mutations,
            self.production_mutations,
        )
        if any(
            supplied is not None and supplied != expected
            for supplied, expected in zip(supplied_values, expected_values)
        ):
            raise ContractValidationError("isolation mutation counts do not match")
        expected_isolated = sum(expected_values) == 0
        if self.isolated is not None and self.isolated is not expected_isolated:
            raise ContractValidationError("isolated flag does not match fingerprints")
        object.__setattr__(self, "fingerprints", rows)
        object.__setattr__(self, "source_mutations", expected_values[0])
        object.__setattr__(self, "sibling_mutations", expected_values[1])
        object.__setattr__(self, "production_mutations", expected_values[2])
        object.__setattr__(self, "isolated", expected_isolated)
        expected_id = stable_contract_id("szacqisolation", self.identity_payload())
        if (
            self.isolation_receipt_id is not None
            and self.isolation_receipt_id != expected_id
        ):
            raise ContractValidationError("isolation_receipt_id does not match")
        object.__setattr__(self, "isolation_receipt_id", expected_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"isolation_receipt_id"})


class AcquisitionRetentionPolicy(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_RETENTION_POLICY_SCHEMA_VERSION
    ] = ACQUISITION_RETENTION_POLICY_SCHEMA_VERSION
    retention_policy_id: Optional[str] = None
    prompt_retention_mode: Literal[
        PromptRetentionMode.DIGEST_AND_REFERENCE
    ] = PromptRetentionMode.DIGEST_AND_REFERENCE
    response_retention_mode: ResponseRetentionMode
    required_data_classification: Literal[
        AcquisitionDataClassification.NON_SENSITIVE_CANNED
    ] = AcquisitionDataClassification.NON_SENSITIVE_CANNED
    credential_inspection_allowed: Literal[False] = False
    credential_retention_allowed: Literal[False] = False
    personal_private_data_allowed: Literal[False] = False
    retention_classification: str
    retention_reason: str
    access_policy_id: str
    required_redaction_status: Literal[
        AcquisitionRedactionStatus.NOT_REQUIRED
    ] = AcquisitionRedactionStatus.NOT_REQUIRED
    artifact_inclusion_policy: AcquisitionArtifactInclusionPolicy

    _nonblank_fields = field_validator(
        "retention_classification",
        "retention_reason",
        "access_policy_id",
    )(_nonblank)

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionRetentionPolicy":
        expected = stable_contract_id("szacqretentionpolicy", self.identity_payload())
        if self.retention_policy_id is not None and self.retention_policy_id != expected:
            raise ContractValidationError("retention_policy_id does not match")
        object.__setattr__(self, "retention_policy_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"retention_policy_id"})


class AcquisitionRetentionReceipt(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_RETENTION_RECEIPT_SCHEMA_VERSION
    ] = ACQUISITION_RETENTION_RECEIPT_SCHEMA_VERSION
    retention_receipt_id: Optional[str] = None
    policy: AcquisitionRetentionPolicy
    retention_policy_id: str
    semantic_request_id: str
    transport_attempt_id: str
    provider_visible_prompt_digest: str = Field(pattern=_HEX64_PATTERN)
    provider_visible_prompt_length: int = Field(ge=0, strict=True)
    provider_visible_prompt_reference: str
    provider_visible_prompt_raw_retained: bool
    raw_response_digest: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    raw_response_length: Optional[int] = Field(default=None, ge=0, strict=True)
    raw_response_text: Optional[str] = None
    content_addressed_response_reference: Optional[str] = None
    data_classification: AcquisitionDataClassification
    credentials_inspected: bool
    credentials_retained: bool
    personal_private_data_present: bool
    redaction_status: AcquisitionRedactionStatus
    artifact_inclusion: AcquisitionArtifactInclusionPolicy
    violations: Tuple[str, ...] = ()
    policy_compliant: Optional[bool] = None

    _nonblank_fields = field_validator(
        "retention_policy_id",
        "semantic_request_id",
        "transport_attempt_id",
        "provider_visible_prompt_reference",
    )(_nonblank)
    _optional_ref_nonblank = field_validator(
        "content_addressed_response_reference"
    )(_optional_nonblank)
    _strict_bool_fields = field_validator(
        "provider_visible_prompt_raw_retained",
        "credentials_inspected",
        "credentials_retained",
        "personal_private_data_present",
        "policy_compliant",
        mode="before",
    )(_strict_optional_bool)

    @model_validator(mode="after")
    def derive_policy_result_and_identify(self) -> "AcquisitionRetentionReceipt":
        if self.retention_policy_id != self.policy.retention_policy_id:
            raise ContractValidationError("retention policy link does not match")
        violations = []
        if self.provider_visible_prompt_raw_retained:
            violations.append("provider_visible_prompt_raw_retained")
        if self.data_classification is not self.policy.required_data_classification:
            violations.append("data_classification")
        if self.credentials_inspected:
            violations.append("credentials_inspected")
        if self.credentials_retained:
            violations.append("credentials_retained")
        if self.personal_private_data_present:
            violations.append("personal_private_data_present")
        if self.redaction_status is not self.policy.required_redaction_status:
            violations.append("redaction_status")
        if self.artifact_inclusion is not self.policy.artifact_inclusion_policy:
            violations.append("artifact_inclusion")

        raw_present = self.raw_response_text is not None
        ref_present = self.content_addressed_response_reference is not None
        if self.policy.response_retention_mode is ResponseRetentionMode.RAW_UTF8:
            if not raw_present or ref_present:
                violations.append("raw_response_retention_shape")
        elif raw_present or not ref_present:
            violations.append("content_addressed_retention_shape")

        if raw_present:
            raw = (self.raw_response_text or "").encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()
            if self.raw_response_digest != digest:
                violations.append("raw_response_digest")
            if self.raw_response_length != len(raw):
                violations.append("raw_response_length")
        elif self.raw_response_digest is None or self.raw_response_length is None:
            violations.append("raw_response_reference_metadata")

        computed = tuple(sorted(set(violations)))
        supplied = tuple(sorted(set(self.violations)))
        if supplied and supplied != computed:
            raise ContractValidationError("retention violations do not match evidence")
        compliant = not computed
        if self.policy_compliant is not None and self.policy_compliant is not compliant:
            raise ContractValidationError("retention policy_compliant flag does not match")
        object.__setattr__(self, "violations", computed)
        object.__setattr__(self, "policy_compliant", compliant)
        expected = stable_contract_id("szacqretention", self.identity_payload())
        if self.retention_receipt_id is not None and self.retention_receipt_id != expected:
            raise ContractValidationError("retention_receipt_id does not match")
        object.__setattr__(self, "retention_receipt_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"retention_receipt_id"})


class AcquisitionValidationStep(_FrozenAcquisitionContract):
    guard_id: AcquisitionGuardId
    stage: AcquisitionGuardStage
    check_name: str
    allowed_failure_codes: Tuple[AcquisitionFailureCode, ...]

    _check_nonblank = field_validator("check_name")(_nonblank)

    @model_validator(mode="after")
    def validate_shape(self) -> "AcquisitionValidationStep":
        expected_stage = (
            AcquisitionGuardStage.PRE_DISPATCH
            if self.guard_id.value.startswith("P")
            else AcquisitionGuardStage.POST_DISPATCH
        )
        if self.stage is not expected_stage:
            raise ContractValidationError("guard ID and stage differ")
        codes = tuple(sorted(set(self.allowed_failure_codes), key=lambda item: item.value))
        if not codes:
            raise ContractValidationError("guard requires at least one failure code")
        object.__setattr__(self, "allowed_failure_codes", codes)
        return self


_VALIDATION_SPECS: Tuple[
    Tuple[
        AcquisitionGuardId,
        AcquisitionGuardStage,
        str,
        Tuple[AcquisitionFailureCode, ...],
    ],
    ...,
] = (
    (AcquisitionGuardId.P01_REQUEST_INTEGRITY, AcquisitionGuardStage.PRE_DISPATCH, "request integrity", (AcquisitionFailureCode.INVALID_ACQUISITION_REQUEST,)),
    (AcquisitionGuardId.P02_SEMANTIC_IDENTITY_INTEGRITY, AcquisitionGuardStage.PRE_DISPATCH, "semantic identity integrity", (AcquisitionFailureCode.INVALID_SEMANTIC_IDENTITY, AcquisitionFailureCode.IDENTITY_COLLISION)),
    (AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY, AcquisitionGuardStage.PRE_DISPATCH, "capability snapshot integrity", (AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT,)),
    (AcquisitionGuardId.P04_REQUIRED_CONTROL_COMPLETENESS, AcquisitionGuardStage.PRE_DISPATCH, "required-control completeness", (AcquisitionFailureCode.REQUIRED_CONTROL_UNKNOWN,)),
    (AcquisitionGuardId.P05_CANNED_ONLY_TRANSPORT_MODE, AcquisitionGuardStage.PRE_DISPATCH, "canned-only transport mode", (AcquisitionFailureCode.CANNED_ONLY_POLICY_VIOLATION,)),
    (AcquisitionGuardId.P06_EXTERNAL_NETWORK_PROHIBITION, AcquisitionGuardStage.PRE_DISPATCH, "external-network prohibition", (AcquisitionFailureCode.EXTERNAL_NETWORK_FORBIDDEN,)),
    (AcquisitionGuardId.P07_CREDENTIAL_ACCESS_PROHIBITION, AcquisitionGuardStage.PRE_DISPATCH, "credential-access prohibition", (AcquisitionFailureCode.CREDENTIAL_ACCESS_FORBIDDEN,)),
    (AcquisitionGuardId.P08_EXACT_IDENTITY_VERIFICATION, AcquisitionGuardStage.PRE_DISPATCH, "exact provider/model/configuration verification capability", (AcquisitionFailureCode.EXACT_IDENTITY_VERIFICATION_UNAVAILABLE,)),
    (AcquisitionGuardId.P09_FALLBACK_DISABLED, AcquisitionGuardStage.PRE_DISPATCH, "fallback disabled", (AcquisitionFailureCode.FALLBACK_CONTROL_UNPROVEN,)),
    (AcquisitionGuardId.P10_RETRY_DISABLED, AcquisitionGuardStage.PRE_DISPATCH, "explicit and adapter retries disabled", (AcquisitionFailureCode.RETRY_CONTROL_UNPROVEN,)),
    (AcquisitionGuardId.P11_SDK_INTERNAL_RETRY_DISABLED, AcquisitionGuardStage.PRE_DISPATCH, "SDK and hidden retries disabled", (AcquisitionFailureCode.SDK_INTERNAL_RETRY_CONTROL_UNPROVEN,)),
    (AcquisitionGuardId.P12_TOOLS_DISABLED, AcquisitionGuardStage.PRE_DISPATCH, "tools disabled", (AcquisitionFailureCode.TOOLS_NOT_DISABLED,)),
    (AcquisitionGuardId.P13_TIMEOUT_WORKER_TERMINATION, AcquisitionGuardStage.PRE_DISPATCH, "timeout and worker termination guarantee", (AcquisitionFailureCode.TIMEOUT_CANCELLATION_UNPROVEN,)),
    (AcquisitionGuardId.P14_RESOURCE_ACCOUNTING, AcquisitionGuardStage.PRE_DISPATCH, "resource-accounting completeness", (AcquisitionFailureCode.RESOURCE_ACCOUNTING_INCOMPLETE,)),
    (AcquisitionGuardId.P15_BUDGET_SUFFICIENCY, AcquisitionGuardStage.PRE_DISPATCH, "budget sufficiency", (AcquisitionFailureCode.BUDGET_INCOMPLETE,)),
    (AcquisitionGuardId.P16_PROMPT_BYTE_DETERMINISM, AcquisitionGuardStage.PRE_DISPATCH, "prompt-byte determinism", (AcquisitionFailureCode.PROMPT_ENTROPY_DETECTED,)),
    (AcquisitionGuardId.P17_ISOLATION_PRECONDITIONS, AcquisitionGuardStage.PRE_DISPATCH, "branch/isolation preconditions", (AcquisitionFailureCode.ISOLATION_PRECONDITION_FAILED,)),
    (AcquisitionGuardId.P18_CANNED_TRANSPORT_REGISTRATION, AcquisitionGuardStage.PRE_DISPATCH, "canned-transport registration", (AcquisitionFailureCode.CANNED_TRANSPORT_UNREGISTERED,)),
    (AcquisitionGuardId.A01_CANNED_INVOCATION_COUNT, AcquisitionGuardStage.POST_DISPATCH, "canned invocation count integrity", (AcquisitionFailureCode.UNCOUNTED_CANNED_INVOCATION,)),
    (AcquisitionGuardId.A02_TRANSPORT_COMPLETION, AcquisitionGuardStage.POST_DISPATCH, "transport completion", (AcquisitionFailureCode.TRANSPORT_TIMEOUT, AcquisitionFailureCode.TRANSPORT_ERROR)),
    (AcquisitionGuardId.A03_TIMEOUT_WORKER_TERMINATION, AcquisitionGuardStage.POST_DISPATCH, "timeout worker termination", (AcquisitionFailureCode.TRANSPORT_WORKER_NOT_TERMINATED,)),
    (AcquisitionGuardId.A04_ACTUAL_PROVIDER_IDENTITY, AcquisitionGuardStage.POST_DISPATCH, "actual provider identity", (AcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,)),
    (AcquisitionGuardId.A05_ACTUAL_MODEL_IDENTITY, AcquisitionGuardStage.POST_DISPATCH, "actual model identity", (AcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,)),
    (AcquisitionGuardId.A06_ACTUAL_CONFIGURATION_IDENTITY, AcquisitionGuardStage.POST_DISPATCH, "actual configuration identity", (AcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,)),
    (AcquisitionGuardId.A07_FALLBACK_ACTIVATION, AcquisitionGuardStage.POST_DISPATCH, "fallback activation", (AcquisitionFailureCode.FALLBACK_ACTIVATED,)),
    (AcquisitionGuardId.A08_RETRY_ACTIVATION, AcquisitionGuardStage.POST_DISPATCH, "retry activation", (AcquisitionFailureCode.RETRY_ACTIVATED,)),
    (AcquisitionGuardId.A09_TOOL_ACTIVATION, AcquisitionGuardStage.POST_DISPATCH, "tool activation", (AcquisitionFailureCode.TOOL_ACTIVATED,)),
    (AcquisitionGuardId.A10_RAW_RESPONSE_PRESENCE, AcquisitionGuardStage.POST_DISPATCH, "raw response presence", (AcquisitionFailureCode.MISSING_RAW_OBSERVATION,)),
    (AcquisitionGuardId.A11_RESPONSE_DIGEST_INTEGRITY, AcquisitionGuardStage.POST_DISPATCH, "response digest integrity", (AcquisitionFailureCode.INVALID_RESPONSE_DIGEST,)),
    (AcquisitionGuardId.A12_USAGE_COMPLETENESS, AcquisitionGuardStage.POST_DISPATCH, "usage completeness", (AcquisitionFailureCode.USAGE_INCOMPLETE,)),
    (AcquisitionGuardId.A13_RESOURCE_RECEIPT_INTEGRITY, AcquisitionGuardStage.POST_DISPATCH, "resource receipt integrity", (AcquisitionFailureCode.RESOURCE_RECEIPT_MISMATCH,)),
    (AcquisitionGuardId.A14_ISOLATION_INTEGRITY, AcquisitionGuardStage.POST_DISPATCH, "isolation integrity", (AcquisitionFailureCode.ISOLATION_FAILURE,)),
    (AcquisitionGuardId.A15_RETENTION_PRIVACY_INTEGRITY, AcquisitionGuardStage.POST_DISPATCH, "retention/privacy integrity", (AcquisitionFailureCode.RETENTION_POLICY_VIOLATION,)),
    (AcquisitionGuardId.A16_FINAL_RECEIPT_INTEGRITY, AcquisitionGuardStage.POST_DISPATCH, "final receipt integrity", (AcquisitionFailureCode.RECEIPT_MISMATCH,)),
)


class AcquisitionValidationOrder(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_VALIDATION_ORDER_SCHEMA_VERSION
    ] = ACQUISITION_VALIDATION_ORDER_SCHEMA_VERSION
    validation_order_id: Optional[str] = None
    precedence_model: Literal[
        FIRST_ACQUISITION_GUARD_WINS
    ] = FIRST_ACQUISITION_GUARD_WINS
    steps: Tuple[AcquisitionValidationStep, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionValidationOrder":
        actual = tuple(
            (item.guard_id, item.stage, item.check_name, item.allowed_failure_codes)
            for item in self.steps
        )
        normalized_specs = tuple(
            (guard, stage, name, tuple(sorted(codes, key=lambda item: item.value)))
            for guard, stage, name, codes in _VALIDATION_SPECS
        )
        if actual != normalized_specs:
            raise ContractValidationError("acquisition validation order changed")
        expected = stable_contract_id("szacqvalidationorder", self.identity_payload())
        if self.validation_order_id is not None and self.validation_order_id != expected:
            raise ContractValidationError("validation_order_id does not match")
        object.__setattr__(self, "validation_order_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"validation_order_id"})


FROZEN_ACQUISITION_VALIDATION_ORDER = AcquisitionValidationOrder(
    steps=tuple(
        AcquisitionValidationStep(
            guard_id=guard,
            stage=stage,
            check_name=name,
            allowed_failure_codes=codes,
        )
        for guard, stage, name, codes in _VALIDATION_SPECS
    )
)
ACQUISITION_GUARD_ORDER: Tuple[AcquisitionGuardId, ...] = tuple(
    item.guard_id for item in FROZEN_ACQUISITION_VALIDATION_ORDER.steps
)


class AcquisitionFailureTaxonomyEntry(_FrozenAcquisitionContract):
    code: AcquisitionFailureCode
    governing_guard_ids: Tuple[AcquisitionGuardId, ...]

    @model_validator(mode="after")
    def validate_guards(self) -> "AcquisitionFailureTaxonomyEntry":
        positions = {guard: index for index, guard in enumerate(ACQUISITION_GUARD_ORDER)}
        guards = tuple(sorted(set(self.governing_guard_ids), key=positions.__getitem__))
        if not guards:
            raise ContractValidationError("failure taxonomy entry requires a guard")
        object.__setattr__(self, "governing_guard_ids", guards)
        return self


class AcquisitionFailureTaxonomy(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_FAILURE_TAXONOMY_SCHEMA_VERSION
    ] = ACQUISITION_FAILURE_TAXONOMY_SCHEMA_VERSION
    failure_taxonomy_id: Optional[str] = None
    entries: Tuple[AcquisitionFailureTaxonomyEntry, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionFailureTaxonomy":
        entries = tuple(sorted(self.entries, key=lambda item: item.code.value))
        if len({item.code for item in entries}) != len(entries):
            raise ContractValidationError("failure taxonomy codes must be unique")
        if {item.code for item in entries} != set(AcquisitionFailureCode):
            raise ContractValidationError("failure taxonomy coverage is incomplete")
        object.__setattr__(self, "entries", entries)
        expected = stable_contract_id("szacqfailuretaxonomy", self.identity_payload())
        if self.failure_taxonomy_id is not None and self.failure_taxonomy_id != expected:
            raise ContractValidationError("failure_taxonomy_id does not match")
        object.__setattr__(self, "failure_taxonomy_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"failure_taxonomy_id"})


def _frozen_taxonomy_entries() -> Tuple[AcquisitionFailureTaxonomyEntry, ...]:
    guards_by_code: Dict[AcquisitionFailureCode, list[AcquisitionGuardId]] = {
        code: [] for code in AcquisitionFailureCode
    }
    for step in FROZEN_ACQUISITION_VALIDATION_ORDER.steps:
        for code in step.allowed_failure_codes:
            guards_by_code[code].append(step.guard_id)
    return tuple(
        AcquisitionFailureTaxonomyEntry(
            code=code,
            governing_guard_ids=tuple(guards_by_code[code]),
        )
        for code in AcquisitionFailureCode
    )


FROZEN_ACQUISITION_FAILURE_TAXONOMY = AcquisitionFailureTaxonomy(
    entries=_frozen_taxonomy_entries()
)


class AcquisitionGuardEvaluation(_FrozenAcquisitionContract):
    guard_id: AcquisitionGuardId
    stage: AcquisitionGuardStage
    state: AcquisitionGuardState
    failure_code: Optional[AcquisitionFailureCode] = None
    diagnostic_mismatches: Tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "AcquisitionGuardEvaluation":
        expected_stage = (
            AcquisitionGuardStage.PRE_DISPATCH
            if self.guard_id.value.startswith("P")
            else AcquisitionGuardStage.POST_DISPATCH
        )
        if self.stage is not expected_stage:
            raise ContractValidationError("guard evaluation stage does not match ID")
        if (self.state is AcquisitionGuardState.FAILED) != (
            self.failure_code is not None
        ):
            raise ContractValidationError(
                "failure code must be present exactly for a failed guard"
            )
        step = next(
            item
            for item in FROZEN_ACQUISITION_VALIDATION_ORDER.steps
            if item.guard_id is self.guard_id
        )
        if (
            self.failure_code is not None
            and self.failure_code not in step.allowed_failure_codes
        ):
            raise ContractValidationError("failure code is not owned by this guard")
        mismatches = _canonical_strings(
            self.diagnostic_mismatches,
            "diagnostic_mismatches",
        )
        object.__setattr__(self, "diagnostic_mismatches", mismatches)
        return self


class AcquisitionPrimaryResult(_FrozenAcquisitionContract):
    outcome: AcquisitionAttemptOutcome
    primary_guard_id: Optional[AcquisitionGuardId] = None
    failure_code: Optional[AcquisitionFailureCode] = None

    @model_validator(mode="after")
    def validate_shape(self) -> "AcquisitionPrimaryResult":
        failed = self.outcome is AcquisitionAttemptOutcome.FAILED_CLOSED
        if failed != (
            self.primary_guard_id is not None and self.failure_code is not None
        ):
            raise ContractValidationError(
                "failed result requires a primary guard and failure code; acquired does not"
            )
        return self


FORBIDDEN_UNADMITTED_OBSERVATION_FIELDS = frozenset(
    {
        "accepted",
        "benchmark_label",
        "canonical",
        "canonical_move_id",
        "canonical_rejection",
        "canonical_result",
        "expected_result",
        "future_reward",
        "future_state",
        "ground_truth",
        "move_id",
        "reward",
        "search_state",
        "search_state_value",
        "successor",
        "successor_state",
        "value",
    }
)


class UnadmittedAcquiredObservation(_FrozenAcquisitionContract):
    schema_version: Literal[
        UNADMITTED_OBSERVATION_SCHEMA_VERSION
    ] = UNADMITTED_OBSERVATION_SCHEMA_VERSION
    unadmitted_observation_id: Optional[str] = None
    semantic_request_id: str
    transport_attempt_id: str
    requested_binding: AcquisitionProviderModelBinding
    actual_binding: AcquisitionProviderModelBinding
    raw_response_digest: str = Field(pattern=_HEX64_PATTERN)
    raw_response_length: int = Field(ge=0, strict=True)
    raw_response_reference: str
    execution_usage_id: str
    historical_usage_id: str
    isolation_receipt_id: str
    retention_receipt_id: str
    admission_status: Literal["UNADMITTED"] = "UNADMITTED"
    canonical_status: Literal["NON_CANONICAL"] = "NON_CANONICAL"
    governing_status: Literal["NON_GOVERNING"] = "NON_GOVERNING"
    application_status: Literal["NOT_APPLIED"] = "NOT_APPLIED"

    _nonblank_fields = field_validator(
        "semantic_request_id",
        "transport_attempt_id",
        "raw_response_reference",
        "execution_usage_id",
        "historical_usage_id",
        "isolation_receipt_id",
        "retention_receipt_id",
    )(_nonblank)

    @model_validator(mode="before")
    @classmethod
    def reject_canonical_or_future_fields(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            forbidden = sorted(FORBIDDEN_UNADMITTED_OBSERVATION_FIELDS & set(data))
            if forbidden:
                raise ContractValidationError(
                    "unadmitted observation contains forbidden canonical/future fields: "
                    + ", ".join(forbidden)
                )
        return data

    @model_validator(mode="after")
    def identify(self) -> "UnadmittedAcquiredObservation":
        expected = stable_contract_id("szacqobservation", self.identity_payload())
        if (
            self.unadmitted_observation_id is not None
            and self.unadmitted_observation_id != expected
        ):
            raise ContractValidationError("unadmitted_observation_id does not match")
        object.__setattr__(self, "unadmitted_observation_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"unadmitted_observation_id"})


class AcquisitionAttemptReceipt(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_ATTEMPT_RECEIPT_SCHEMA_VERSION
    ] = ACQUISITION_ATTEMPT_RECEIPT_SCHEMA_VERSION
    receipt_id: Optional[str] = None
    receipt_hash: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    acquisition_contract_id: Literal[ACQUISITION_CONTRACT_ID] = ACQUISITION_CONTRACT_ID
    validation_order_id: str = (
        FROZEN_ACQUISITION_VALIDATION_ORDER.validation_order_id or ""
    )
    failure_taxonomy_id: str = (
        FROZEN_ACQUISITION_FAILURE_TAXONOMY.failure_taxonomy_id or ""
    )
    capability_snapshot_id: str
    control_policy_id: str
    semantic_request_id: str
    branch_id: str
    transport_attempt_id: str
    attempt_ordinal: int = Field(ge=0, strict=True)
    provider_visible_request_digest: str = Field(pattern=_HEX64_PATTERN)
    provider_visible_request_length: int = Field(ge=0, strict=True)
    canned_transport_id: str
    requested_binding: AcquisitionProviderModelBinding
    actual_binding: Optional[AcquisitionProviderModelBinding] = None
    guard_evaluations: Tuple[AcquisitionGuardEvaluation, ...]
    transport_status: Optional[AcquisitionTransportStatus] = None
    reported_raw_response_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    computed_raw_response_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    fallback_used: Optional[bool] = None
    explicit_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    adapter_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    sdk_internal_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    hidden_transport_retry_count: Optional[int] = Field(default=None, ge=0, strict=True)
    tool_calls: Optional[int] = Field(default=None, ge=0, strict=True)
    execution_usage: AcquisitionExecutionUsage
    historical_usage: AcquisitionHistoricalUsage
    isolation_receipt_id: str
    retention_receipt_id: str
    source_mutations: int = Field(ge=0, strict=True)
    sibling_mutations: int = Field(ge=0, strict=True)
    production_mutations: int = Field(ge=0, strict=True)
    retention_policy_compliant: bool
    prompt_byte_mismatch: bool
    unadmitted_observation_id: Optional[str] = None
    primary_result: AcquisitionPrimaryResult
    diagnostic_mismatches: Tuple[str, ...] = ()

    _nonblank_fields = field_validator(
        "validation_order_id",
        "failure_taxonomy_id",
        "capability_snapshot_id",
        "control_policy_id",
        "semantic_request_id",
        "branch_id",
        "transport_attempt_id",
        "canned_transport_id",
        "isolation_receipt_id",
        "retention_receipt_id",
    )(_nonblank)
    _optional_nonblank_fields = field_validator(
        "unadmitted_observation_id"
    )(_optional_nonblank)
    _strict_bool_fields = field_validator(
        "fallback_used",
        "retention_policy_compliant",
        "prompt_byte_mismatch",
        mode="before",
    )(_strict_optional_bool)

    @model_validator(mode="after")
    def validate_guard_precedence_and_identify(self) -> "AcquisitionAttemptReceipt":
        if self.validation_order_id != (
            FROZEN_ACQUISITION_VALIDATION_ORDER.validation_order_id
        ):
            raise ContractValidationError("attempt receipt validation order differs")
        if self.failure_taxonomy_id != (
            FROZEN_ACQUISITION_FAILURE_TAXONOMY.failure_taxonomy_id
        ):
            raise ContractValidationError("attempt receipt failure taxonomy differs")
        if tuple(item.guard_id for item in self.guard_evaluations) != ACQUISITION_GUARD_ORDER:
            raise ContractValidationError("attempt receipt guard coverage/order differs")

        failed = tuple(
            item for item in self.guard_evaluations
            if item.state is AcquisitionGuardState.FAILED
        )
        if self.primary_result.outcome is AcquisitionAttemptOutcome.ACQUIRED:
            if failed or any(
                item.state is not AcquisitionGuardState.PASSED
                for item in self.guard_evaluations
            ):
                raise ContractValidationError("acquired receipt requires every guard passed")
            if (
                self.unadmitted_observation_id is None
                or self.actual_binding is None
                or self.transport_status is not AcquisitionTransportStatus.DELIVERED
                or self.computed_raw_response_digest is None
            ):
                raise ContractValidationError(
                    "acquired receipt requires observation, actual identity, and raw response"
                )
        else:
            if len(failed) != 1:
                raise ContractValidationError(
                    "failed-closed receipt requires exactly one failed primary guard"
                )
            primary = failed[0]
            primary_index = ACQUISITION_GUARD_ORDER.index(primary.guard_id)
            expected_states = (
                (AcquisitionGuardState.PASSED,) * primary_index
                + (AcquisitionGuardState.FAILED,)
                + (AcquisitionGuardState.NOT_REACHED,)
                * (len(ACQUISITION_GUARD_ORDER) - primary_index - 1)
            )
            if tuple(item.state for item in self.guard_evaluations) != expected_states:
                raise ContractValidationError(
                    "failed receipt does not implement first acquisition guard wins"
                )
            if (
                self.primary_result.primary_guard_id is not primary.guard_id
                or self.primary_result.failure_code is not primary.failure_code
            ):
                raise ContractValidationError("primary result differs from first failed guard")
            if self.unadmitted_observation_id is not None:
                raise ContractValidationError(
                    "failed acquisition cannot publish an unadmitted observation"
                )

        diagnostics = _canonical_strings(
            self.diagnostic_mismatches,
            "diagnostic_mismatches",
        )
        object.__setattr__(self, "diagnostic_mismatches", diagnostics)
        payload = self.identity_payload()
        digest = _semantic_digest(payload)
        expected_id = f"szacqattemptreceipt_{digest}"
        if self.receipt_hash is not None and self.receipt_hash != digest:
            raise ContractValidationError("receipt_hash does not match")
        if self.receipt_id is not None and self.receipt_id != expected_id:
            raise ContractValidationError("receipt_id does not match")
        object.__setattr__(self, "receipt_hash", digest)
        object.__setattr__(self, "receipt_id", expected_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"receipt_id", "receipt_hash"})


class AcquisitionTripwireCounters(_FrozenAcquisitionContract):
    canned_transport_invocations: int = Field(ge=0, strict=True)
    external_network_attempts: int = Field(ge=0, strict=True)
    credential_access_attempts: int = Field(ge=0, strict=True)
    live_provider_calls: int = Field(ge=0, strict=True)
    provider_sdk_calls: int = Field(ge=0, strict=True)
    model_executions: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)
    canonical_application_calls: int = Field(ge=0, strict=True)


class AcquisitionFailureCount(_FrozenAcquisitionContract):
    failure_code: AcquisitionFailureCode
    count: int = Field(ge=1, strict=True)


class AcquisitionAggregateMetrics(_FrozenAcquisitionContract):
    attempts_total: int = Field(ge=0, strict=True)
    acquired_attempts: int = Field(ge=0, strict=True)
    failed_closed_attempts: int = Field(ge=0, strict=True)
    receipt_canned_transport_invocations: AcquisitionResourceQuantity
    observed_canned_transport_invocations: int = Field(ge=0, strict=True)
    uncounted_canned_invocations: AcquisitionResourceQuantity
    external_network_attempts: int = Field(ge=0, strict=True)
    credential_access_attempts: int = Field(ge=0, strict=True)
    live_provider_calls: int = Field(ge=0, strict=True)
    provider_sdk_calls: int = Field(ge=0, strict=True)
    model_executions: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)
    canonical_application_calls: int = Field(ge=0, strict=True)
    incomplete_usage_receipts: int = Field(ge=0, strict=True)
    identity_mismatches: int = Field(ge=0, strict=True)
    prompt_byte_mismatches: int = Field(ge=0, strict=True)
    source_mutations: int = Field(ge=0, strict=True)
    sibling_mutations: int = Field(ge=0, strict=True)
    production_mutations: int = Field(ge=0, strict=True)
    retention_violations: int = Field(ge=0, strict=True)
    receipt_mismatches: int = Field(ge=0, strict=True)
    failures_by_code: Tuple[AcquisitionFailureCount, ...]

    @model_validator(mode="after")
    def canonicalize(self) -> "AcquisitionAggregateMetrics":
        failures = tuple(
            sorted(self.failures_by_code, key=lambda item: item.failure_code.value)
        )
        if len({item.failure_code for item in failures}) != len(failures):
            raise ContractValidationError("aggregate failure codes must be unique")
        if self.acquired_attempts + self.failed_closed_attempts != self.attempts_total:
            raise ContractValidationError("aggregate attempt totals do not add up")
        object.__setattr__(self, "failures_by_code", failures)
        return self


_IDENTITY_FAILURES = frozenset(
    {
        AcquisitionFailureCode.INVALID_SEMANTIC_IDENTITY,
        AcquisitionFailureCode.IDENTITY_COLLISION,
        AcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,
        AcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
        AcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
    }
)


def _aggregate_metrics(
    receipts: Tuple[AcquisitionAttemptReceipt, ...],
    counters: AcquisitionTripwireCounters,
) -> AcquisitionAggregateMetrics:
    invocation_quantities = [
        item.execution_usage.canned_transport_invocations for item in receipts
    ]
    if all(
        item.knowledge is ResourceKnowledgeState.KNOWN
        for item in invocation_quantities
    ):
        receipt_total = sum(item.value or 0 for item in invocation_quantities)
        receipt_invocations = AcquisitionResourceQuantity.known(receipt_total)
        uncounted = AcquisitionResourceQuantity.known(
            abs(counters.canned_transport_invocations - receipt_total)
        )
    else:
        receipt_invocations = AcquisitionResourceQuantity.unknown()
        uncounted = AcquisitionResourceQuantity.unknown()

    failure_counts: Dict[AcquisitionFailureCode, int] = {}
    for receipt in receipts:
        code = receipt.primary_result.failure_code
        if code is not None:
            failure_counts[code] = failure_counts.get(code, 0) + 1
    failures_by_code = tuple(
        AcquisitionFailureCount(failure_code=code, count=count)
        for code, count in failure_counts.items()
    )
    return AcquisitionAggregateMetrics(
        attempts_total=len(receipts),
        acquired_attempts=sum(
            item.primary_result.outcome is AcquisitionAttemptOutcome.ACQUIRED
            for item in receipts
        ),
        failed_closed_attempts=sum(
            item.primary_result.outcome is AcquisitionAttemptOutcome.FAILED_CLOSED
            for item in receipts
        ),
        receipt_canned_transport_invocations=receipt_invocations,
        observed_canned_transport_invocations=counters.canned_transport_invocations,
        uncounted_canned_invocations=uncounted,
        external_network_attempts=counters.external_network_attempts,
        credential_access_attempts=counters.credential_access_attempts,
        live_provider_calls=counters.live_provider_calls,
        provider_sdk_calls=counters.provider_sdk_calls,
        model_executions=counters.model_executions,
        tool_calls=counters.tool_calls,
        canonical_application_calls=counters.canonical_application_calls,
        incomplete_usage_receipts=sum(
            not item.execution_usage.complete for item in receipts
        ),
        identity_mismatches=sum(
            item.primary_result.failure_code in _IDENTITY_FAILURES for item in receipts
        ),
        prompt_byte_mismatches=sum(item.prompt_byte_mismatch for item in receipts),
        source_mutations=sum(item.source_mutations for item in receipts),
        sibling_mutations=sum(item.sibling_mutations for item in receipts),
        production_mutations=sum(item.production_mutations for item in receipts),
        retention_violations=sum(
            not item.retention_policy_compliant for item in receipts
        ),
        receipt_mismatches=failure_counts.get(
            AcquisitionFailureCode.RECEIPT_MISMATCH, 0
        ),
        failures_by_code=failures_by_code,
    )


class AcquisitionAggregateReceipt(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_AGGREGATE_RECEIPT_SCHEMA_VERSION
    ] = ACQUISITION_AGGREGATE_RECEIPT_SCHEMA_VERSION
    aggregate_receipt_id: Optional[str] = None
    aggregate_receipt_hash: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    experiment_id: str
    case_set_id: str
    attempt_receipts: Tuple[AcquisitionAttemptReceipt, ...]
    observed_counters: AcquisitionTripwireCounters
    metrics: AcquisitionAggregateMetrics

    _nonblank_fields = field_validator("experiment_id", "case_set_id")(_nonblank)

    @model_validator(mode="after")
    def recompute_and_identify(self) -> "AcquisitionAggregateReceipt":
        receipts = tuple(
            sorted(self.attempt_receipts, key=lambda item: item.transport_attempt_id)
        )
        if len({item.receipt_id for item in receipts}) != len(receipts):
            raise ContractValidationError("aggregate receipt IDs must be unique")
        if len({item.transport_attempt_id for item in receipts}) != len(receipts):
            raise ContractValidationError("aggregate transport attempts must be unique")
        expected_metrics = _aggregate_metrics(receipts, self.observed_counters)
        if self.metrics != expected_metrics:
            raise ContractValidationError("aggregate metrics do not match receipts")
        object.__setattr__(self, "attempt_receipts", receipts)
        payload = self.identity_payload()
        digest = _semantic_digest(payload)
        expected_id = f"szacqaggregate_{digest}"
        if (
            self.aggregate_receipt_hash is not None
            and self.aggregate_receipt_hash != digest
        ):
            raise ContractValidationError("aggregate_receipt_hash does not match")
        if (
            self.aggregate_receipt_id is not None
            and self.aggregate_receipt_id != expected_id
        ):
            raise ContractValidationError("aggregate_receipt_id does not match")
        object.__setattr__(self, "aggregate_receipt_hash", digest)
        object.__setattr__(self, "aggregate_receipt_id", expected_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude={"aggregate_receipt_id", "aggregate_receipt_hash"},
        )


class AcquisitionExperimentArtifact(_FrozenAcquisitionContract):
    schema_version: Literal[
        ACQUISITION_EXPERIMENT_ARTIFACT_SCHEMA_VERSION
    ] = ACQUISITION_EXPERIMENT_ARTIFACT_SCHEMA_VERSION
    artifact_id: Optional[str] = None
    acquisition_contract_id: Literal[ACQUISITION_CONTRACT_ID] = ACQUISITION_CONTRACT_ID
    validation_order_id: str
    failure_taxonomy_id: str
    capability_snapshot_ids: Tuple[str, ...]
    control_policy_ids: Tuple[str, ...]
    semantic_request_ids: Tuple[str, ...]
    transport_attempt_ids: Tuple[str, ...]
    case_set_id: str
    harness_id: str
    metrics_id: str
    thresholds_id: str
    aggregate_receipt: AcquisitionAggregateReceipt
    attempt_receipt_ids: Tuple[str, ...]
    isolation_receipt_ids: Tuple[str, ...]
    retention_receipt_ids: Tuple[str, ...]
    provider_visible_prompt_digests: Tuple[str, ...]
    historical_hashes: Tuple[str, ...]
    hypothesis_status: Literal["SUPPORTED", "FALSIFIED"]
    production_authority: Literal["none"] = "none"

    _nonblank_fields = field_validator(
        "validation_order_id",
        "failure_taxonomy_id",
        "case_set_id",
        "harness_id",
        "metrics_id",
        "thresholds_id",
    )(_nonblank)

    @model_validator(mode="after")
    def canonicalize_and_identify(self) -> "AcquisitionExperimentArtifact":
        if self.validation_order_id != (
            FROZEN_ACQUISITION_VALIDATION_ORDER.validation_order_id
        ) or self.failure_taxonomy_id != (
            FROZEN_ACQUISITION_FAILURE_TAXONOMY.failure_taxonomy_id
        ):
            raise ContractValidationError("artifact methodology identity changed")
        for name in (
            "capability_snapshot_ids",
            "control_policy_ids",
            "semantic_request_ids",
            "transport_attempt_ids",
            "attempt_receipt_ids",
            "isolation_receipt_ids",
            "retention_receipt_ids",
            "provider_visible_prompt_digests",
            "historical_hashes",
        ):
            object.__setattr__(self, name, _canonical_strings(getattr(self, name), name))
        aggregate_ids = tuple(
            item.receipt_id or "" for item in self.aggregate_receipt.attempt_receipts
        )
        if tuple(sorted(aggregate_ids)) != self.attempt_receipt_ids:
            raise ContractValidationError(
                "artifact attempt receipt IDs differ from aggregate receipt"
            )
        expected = stable_contract_id(
            "szacqartifact",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id is not None and self.artifact_id != expected:
            raise ContractValidationError("artifact_id does not match")
        object.__setattr__(self, "artifact_id", expected)
        return self


__all__ = [
    "ACQUISITION_AGGREGATE_RECEIPT_SCHEMA_VERSION",
    "ACQUISITION_ATTEMPT_RECEIPT_SCHEMA_VERSION",
    "ACQUISITION_CAPABILITY_SNAPSHOT_SCHEMA_VERSION",
    "ACQUISITION_CONTRACT_ID",
    "ACQUISITION_CONTROL_POLICY_SCHEMA_VERSION",
    "ACQUISITION_EXECUTION_USAGE_SCHEMA_VERSION",
    "ACQUISITION_EXPERIMENT_ARTIFACT_SCHEMA_VERSION",
    "ACQUISITION_FAILURE_TAXONOMY_SCHEMA_VERSION",
    "ACQUISITION_GUARD_ORDER",
    "ACQUISITION_HISTORICAL_USAGE_SCHEMA_VERSION",
    "ACQUISITION_ISOLATION_RECEIPT_SCHEMA_VERSION",
    "ACQUISITION_REQUEST_CONFIGURATION_SCHEMA_VERSION",
    "ACQUISITION_RETENTION_POLICY_SCHEMA_VERSION",
    "ACQUISITION_RETENTION_RECEIPT_SCHEMA_VERSION",
    "ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION",
    "ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION",
    "ACQUISITION_VALIDATION_ORDER_SCHEMA_VERSION",
    "CANNED_TRANSPORT_ENVELOPE_SCHEMA_VERSION",
    "CANNED_TRANSPORT_ID",
    "FIRST_ACQUISITION_GUARD_WINS",
    "FORBIDDEN_CANNED_ENVELOPE_FIELDS",
    "FORBIDDEN_UNADMITTED_OBSERVATION_FIELDS",
    "FROZEN_ACQUISITION_FAILURE_TAXONOMY",
    "FROZEN_ACQUISITION_VALIDATION_ORDER",
    "FROZEN_REQUIRED_CONTROL_STATES",
    "PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION",
    "SUPPORTED_ACTION_FAMILY",
    "UNADMITTED_OBSERVATION_SCHEMA_VERSION",
    "AcquisitionAggregateMetrics",
    "AcquisitionAggregateReceipt",
    "AcquisitionArtifactInclusionPolicy",
    "AcquisitionAttemptOutcome",
    "AcquisitionAttemptReceipt",
    "AcquisitionBudget",
    "AcquisitionCapabilitySnapshot",
    "AcquisitionControlEvidence",
    "AcquisitionControlName",
    "AcquisitionControlPolicy",
    "AcquisitionControlRequirement",
    "AcquisitionControlState",
    "AcquisitionDataClassification",
    "AcquisitionExecutionUsage",
    "AcquisitionExperimentArtifact",
    "AcquisitionFailureCode",
    "AcquisitionFailureCount",
    "AcquisitionFailureTaxonomy",
    "AcquisitionFailureTaxonomyEntry",
    "AcquisitionGuardEvaluation",
    "AcquisitionGuardId",
    "AcquisitionGuardStage",
    "AcquisitionGuardState",
    "AcquisitionHistoricalUsage",
    "AcquisitionIsolationFingerprint",
    "AcquisitionIsolationReceipt",
    "AcquisitionIsolationScope",
    "AcquisitionPrimaryResult",
    "AcquisitionProviderModelBinding",
    "AcquisitionRedactionStatus",
    "AcquisitionRequestConfiguration",
    "AcquisitionResourceQuantity",
    "AcquisitionRetentionPolicy",
    "AcquisitionRetentionReceipt",
    "AcquisitionSeedSetting",
    "AcquisitionSeedStatus",
    "AcquisitionSemanticRequest",
    "AcquisitionTransportAttempt",
    "AcquisitionTransportMode",
    "AcquisitionTransportStatus",
    "AcquisitionTripwireCounters",
    "AcquisitionValidationOrder",
    "AcquisitionValidationStep",
    "CannedTransportEnvelope",
    "PromptRetentionMode",
    "ProviderVisibleRequestBytes",
    "ResourceKnowledgeState",
    "ResponseRetentionMode",
    "UnadmittedAcquiredObservation",
]

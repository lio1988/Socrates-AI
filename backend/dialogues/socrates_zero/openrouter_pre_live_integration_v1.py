"""Causal binding of the OpenRouter shadow pipeline, offline.

Four layers stay four layers:

    RequestIntentReceipt  ->  TransportExecutionRecord
                          ->  RawWireObservation
                          ->  RawWireMappingResult
                          ->  PreLiveIntegrationReceipt

The integration receipt is evidence *about* that chain.  It never replaces the
underlying evidence and never carries raw bytes: identities, digests and lengths
only.

The one rule that matters most here: request intent may be used to *match* and to
*compare*, never to *fill*.  If the response does not carry an authority, the S5
epistemic state survives untouched.  Nothing below derives an actual served model
from the requested model, a response provider from ``provider.only``, an exact
endpoint from any selector, a cache status from request cache configuration, or a
routing strategy from request fallback policy.

Import-inert.  Composes existing contracts; reimplements none of them.  Holds no
runtime authority and authorizes no call.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id
from .openrouter_raw_wire_mapping_v2 import (
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2,
    OpenRouterNormalizedWireMappingV2,
    OpenRouterRawWireObservationV2,
    OpenRouterWireCacheStatusV2,
    OpenRouterWireEpistemicStatusV2,
    OpenRouterWirePresenceV2,
)
from .openrouter_route_controls_contracts import OpenRouterRequestIntentReceiptV1

OPENROUTER_TRANSPORT_EXECUTION_SCHEMA_V1 = (
    "socrateszero-openrouter-transport-execution/v1"
)
OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1 = (
    "socrateszero-openrouter-pre-live-integration-receipt/v1"
)

#: Exactly one local dispatch is permitted for an accepted integration.  This is
#: a *local transport* count and is unrelated to OpenRouter's own routing
#: ``attempt`` / ``attempts[]`` evidence, which is reported by the server.
OPENROUTER_MAX_LOCAL_DISPATCHES_V1 = 1


class OpenRouterTransportRegistrationStateV1(str, Enum):
    UNREGISTERED = "UNREGISTERED"
    REGISTERED = "REGISTERED"


class OpenRouterTransportCompletionStateV1(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class OpenRouterModelConformanceV1(str, Enum):
    """Requested versus actual served model.

    ``MISMATCH`` is legitimate response evidence.  It fails candidate-policy
    conformance without making the causal binding invalid; the two verdicts are
    reported separately and never merged.
    """

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNAVAILABLE = "UNAVAILABLE"


class OpenRouterCacheConformanceV1(str, Enum):
    """Request cache intent versus response cache evidence.

    The request pins caching disabled.  A documented MISS is consistent.  A HIT
    is recorded as an anomaly rather than a violation: the retained evidence does
    not establish that a HIT is impossible under this request policy, and
    inventing that rule would be a repository convention.
    """

    NO_RESPONSE_AUTHORITY = "NO_RESPONSE_AUTHORITY"
    CONSISTENT_WITH_DISABLED_INTENT = "CONSISTENT_WITH_DISABLED_INTENT"
    ANOMALOUS_HIT_UNDER_DISABLED_INTENT = "ANOMALOUS_HIT_UNDER_DISABLED_INTENT"


class OpenRouterIntegrationFailureCodeV1(str, Enum):
    REQUEST_RECEIPT_INVALID = "REQUEST_RECEIPT_INVALID"
    TRANSPORT_NOT_REGISTERED = "TRANSPORT_NOT_REGISTERED"
    REGISTERED_BODY_MISMATCH = "REGISTERED_BODY_MISMATCH"
    REGISTERED_HEADERS_MISMATCH = "REGISTERED_HEADERS_MISMATCH"
    DISPATCH_COUNT_INVALID = "DISPATCH_COUNT_INVALID"
    TRANSPORT_NOT_COMPLETE = "TRANSPORT_NOT_COMPLETE"
    RESPONSE_ABSENT = "RESPONSE_ABSENT"
    RESPONSE_BODY_BINDING_MISMATCH = "RESPONSE_BODY_BINDING_MISMATCH"
    RESPONSE_HEADER_BINDING_MISMATCH = "RESPONSE_HEADER_BINDING_MISMATCH"
    RAW_OBSERVATION_ID_MISMATCH = "RAW_OBSERVATION_ID_MISMATCH"
    MAPPING_OBSERVATION_MISMATCH = "MAPPING_OBSERVATION_MISMATCH"
    MAPPING_MANIFEST_MISMATCH = "MAPPING_MANIFEST_MISMATCH"
    MAPPING_PROVENANCE_MISMATCH = "MAPPING_PROVENANCE_MISMATCH"


class OpenRouterIntegrationError(ContractValidationError):
    """An integration was refused, with the exact guard that refused it."""

    def __init__(self, code: OpenRouterIntegrationFailureCodeV1, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")


def _reject(code: OpenRouterIntegrationFailureCodeV1, detail: str) -> "NoReturn":  # noqa: F821
    raise OpenRouterIntegrationError(code, detail)


#: Guard order.  Frozen so a broken chain always reports the same first cause.
FROZEN_OPENROUTER_INTEGRATION_GUARD_ORDER_V1: Tuple[
    OpenRouterIntegrationFailureCodeV1, ...
] = (
    OpenRouterIntegrationFailureCodeV1.REQUEST_RECEIPT_INVALID,
    OpenRouterIntegrationFailureCodeV1.TRANSPORT_NOT_REGISTERED,
    OpenRouterIntegrationFailureCodeV1.REGISTERED_BODY_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.REGISTERED_HEADERS_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.DISPATCH_COUNT_INVALID,
    OpenRouterIntegrationFailureCodeV1.TRANSPORT_NOT_COMPLETE,
    OpenRouterIntegrationFailureCodeV1.RESPONSE_ABSENT,
    OpenRouterIntegrationFailureCodeV1.RESPONSE_BODY_BINDING_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.RESPONSE_HEADER_BINDING_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.RAW_OBSERVATION_ID_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.MAPPING_OBSERVATION_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.MAPPING_MANIFEST_MISMATCH,
    OpenRouterIntegrationFailureCodeV1.MAPPING_PROVENANCE_MISMATCH,
)
OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1 = stable_contract_id(
    "szorintegrationguardsv1",
    tuple(code.value for code in FROZEN_OPENROUTER_INTEGRATION_GUARD_ORDER_V1),
)


class _FrozenIntegrationContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterTransportExecutionRecordV1(_FrozenIntegrationContractV1):
    """What the transport layer independently registered, dispatched and received.

    An additive bridge rather than an edit to the acquisition contracts: those
    record a canned envelope and do not carry the *registered request* digests
    that request-byte equality needs.  This record carries no bytes at all, only
    what it observed about them.
    """

    schema_version: Literal[
        OPENROUTER_TRANSPORT_EXECUTION_SCHEMA_V1
    ] = OPENROUTER_TRANSPORT_EXECUTION_SCHEMA_V1
    registration_state: OpenRouterTransportRegistrationStateV1
    registered_body_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    registered_body_length: Optional[int] = Field(default=None, ge=0)
    registered_semantic_headers_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    registered_semantic_headers_length: Optional[int] = Field(default=None, ge=0)
    local_dispatch_count: int = Field(ge=0)
    completion_state: OpenRouterTransportCompletionStateV1
    response_present: bool = False
    response_body_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    response_body_length: Optional[int] = Field(default=None, ge=0)
    response_header_evidence_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    response_header_count: Optional[int] = Field(default=None, ge=0)
    timeout_fired: bool = False
    worker_terminated: bool = False
    record_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterTransportExecutionRecordV1":
        if self.response_present and self.response_body_sha256 is None:
            raise ContractValidationError(
                "a present response requires a response body digest"
            )
        if not self.response_present and self.response_body_sha256 is not None:
            raise ContractValidationError(
                "an absent response must not carry a response body digest"
            )
        expected = stable_contract_id(
            "szortransportexecutionv1",
            self.model_dump(mode="json", exclude={"record_id"}),
        )
        if self.record_id not in (None, expected):
            raise ContractValidationError("transport execution record ID mismatch")
        object.__setattr__(self, "record_id", expected)
        return self


class OpenRouterPreLiveIntegrationReceiptV1(_FrozenIntegrationContractV1):
    """Compact evidence about one bound chain.

    Content addressed over the four layer identities plus the safety-contract
    identity.  No wall clock, UUID, PID, path, username or randomness
    participates in the identity, and no raw body or header bytes are carried.
    """

    schema_version: Literal[
        OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1
    ] = OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1

    # --- the four bound layer identities
    request_intent_receipt_id: str
    transport_record_id: str
    raw_observation_id: str
    mapping_result_id: str
    safety_contract_id: str

    # --- bound digests, never bytes
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_header_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    # --- conformance, kept separate from causal validity
    requested_model: str
    actual_served_model: Optional[str] = None
    actual_served_model_status: OpenRouterWireEpistemicStatusV2
    model_conformance: OpenRouterModelConformanceV1
    requested_exact_endpoint_selector: str
    response_provider_display_names: Tuple[str, ...] = ()
    cache_conformance: OpenRouterCacheConformanceV1
    response_cache_status: Optional[OpenRouterWireCacheStatusV2] = None

    # --- local versus server-reported attempt evidence, never conflated
    local_dispatch_count: Literal[
        OPENROUTER_MAX_LOCAL_DISPATCHES_V1
    ] = OPENROUTER_MAX_LOCAL_DISPATCHES_V1
    response_attempt: Optional[int] = None
    response_attempts_presence: OpenRouterWirePresenceV2

    # --- firewalls that survive integration unchanged
    exact_endpoint_response_identity_status: Literal[
        OpenRouterWireEpistemicStatusV2.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    ] = OpenRouterWireEpistemicStatusV2.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    exact_endpoint_response_identity: None = None

    # --- provenance
    source_manifest_id: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    source_manifest_sha256: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    guard_order_id: Literal[
        OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1
    ] = OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1

    # --- shadow only
    runtime_authority: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    ced_application: Literal[0] = 0

    receipt_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreLiveIntegrationReceiptV1":
        if self.exact_endpoint_response_identity is not None:
            raise ContractValidationError(
                "exact endpoint response identity must carry no value"
            )
        if any("/" in name for name in self.response_provider_display_names):
            raise ContractValidationError(
                "response provider evidence must stay a display label, not a slug"
            )
        if (
            self.model_conformance is OpenRouterModelConformanceV1.UNAVAILABLE
        ) != (self.actual_served_model is None):
            raise ContractValidationError(
                "model conformance disagrees with the actual served model"
            )
        expected = stable_contract_id(
            "szorprelivereceiptv1",
            {
                "schema_version": self.schema_version,
                "request_intent_receipt_id": self.request_intent_receipt_id,
                "transport_record_id": self.transport_record_id,
                "raw_observation_id": self.raw_observation_id,
                "mapping_result_id": self.mapping_result_id,
                "safety_contract_id": self.safety_contract_id,
            },
        )
        if self.receipt_id not in (None, expected):
            raise ContractValidationError("pre-live integration receipt ID mismatch")
        object.__setattr__(self, "receipt_id", expected)
        return self


def _model_conformance(
    requested: str, mapping: OpenRouterNormalizedWireMappingV2
) -> OpenRouterModelConformanceV1:
    """Compare, never fill.

    The actual served model is whatever S5 read from the wire.  When it is
    absent the answer is UNAVAILABLE; the requested model is not promoted into
    the gap, and string equality is a comparison result rather than a derivation.
    """
    if mapping.actual_served_model is None:
        return OpenRouterModelConformanceV1.UNAVAILABLE
    return (
        OpenRouterModelConformanceV1.MATCH
        if mapping.actual_served_model == requested
        else OpenRouterModelConformanceV1.MISMATCH
    )


def _cache_conformance(
    mapping: OpenRouterNormalizedWireMappingV2,
) -> OpenRouterCacheConformanceV1:
    if mapping.cache_status is None:
        return OpenRouterCacheConformanceV1.NO_RESPONSE_AUTHORITY
    if mapping.cache_status is OpenRouterWireCacheStatusV2.HIT:
        return OpenRouterCacheConformanceV1.ANOMALOUS_HIT_UNDER_DISABLED_INTENT
    return OpenRouterCacheConformanceV1.CONSISTENT_WITH_DISABLED_INTENT


def bind_openrouter_pre_live_integration_v1(
    request_intent_receipt: OpenRouterRequestIntentReceiptV1,
    transport_record: OpenRouterTransportExecutionRecordV1,
    raw_observation: OpenRouterRawWireObservationV2,
    mapping_result: OpenRouterNormalizedWireMappingV2,
    safety_contract_id: str,
) -> OpenRouterPreLiveIntegrationReceiptV1:
    """Bind one causal chain, or refuse it fail-closed at the first broken link."""
    for value, expected_type in (
        (request_intent_receipt, OpenRouterRequestIntentReceiptV1),
        (transport_record, OpenRouterTransportExecutionRecordV1),
        (raw_observation, OpenRouterRawWireObservationV2),
        (mapping_result, OpenRouterNormalizedWireMappingV2),
    ):
        if type(value) is not expected_type:
            _reject(
                OpenRouterIntegrationFailureCodeV1.REQUEST_RECEIPT_INVALID,
                f"integration requires the exact {expected_type.__name__} contract",
            )
    if not request_intent_receipt.receipt_id:
        _reject(
            OpenRouterIntegrationFailureCodeV1.REQUEST_RECEIPT_INVALID,
            "request intent receipt carries no identity",
        )

    # --- transport registered the exact intended request bytes
    if (
        transport_record.registration_state
        is not OpenRouterTransportRegistrationStateV1.REGISTERED
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.TRANSPORT_NOT_REGISTERED,
            "transport was never registered for dispatch",
        )
    if (
        transport_record.registered_body_sha256
        != request_intent_receipt.body_sha256
        or transport_record.registered_body_length
        != request_intent_receipt.body_length
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.REGISTERED_BODY_MISMATCH,
            "registered request body does not equal the intended request body",
        )
    if (
        transport_record.registered_semantic_headers_sha256
        != request_intent_receipt.semantic_headers_sha256
        or transport_record.registered_semantic_headers_length
        != request_intent_receipt.semantic_headers_length
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.REGISTERED_HEADERS_MISMATCH,
            "registered semantic headers do not equal the intended headers",
        )

    # --- exactly one local dispatch, then completion, in that order
    if transport_record.local_dispatch_count != OPENROUTER_MAX_LOCAL_DISPATCHES_V1:
        _reject(
            OpenRouterIntegrationFailureCodeV1.DISPATCH_COUNT_INVALID,
            f"local dispatch count {transport_record.local_dispatch_count} is not "
            f"exactly {OPENROUTER_MAX_LOCAL_DISPATCHES_V1}",
        )
    if (
        transport_record.completion_state
        is not OpenRouterTransportCompletionStateV1.COMPLETED
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.TRANSPORT_NOT_COMPLETE,
            f"transport completion state is {transport_record.completion_state.value}",
        )
    if not transport_record.response_present:
        _reject(
            OpenRouterIntegrationFailureCodeV1.RESPONSE_ABSENT,
            "completed transport carries no response",
        )

    # --- the observation is the response this transport received
    if (
        transport_record.response_body_sha256 != raw_observation.raw_body_sha256
        or transport_record.response_body_length != raw_observation.raw_body_length
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.RESPONSE_BODY_BINDING_MISMATCH,
            "raw observation body is not the transport response body",
        )
    if (
        transport_record.response_header_evidence_sha256
        != raw_observation.header_evidence_sha256
        or transport_record.response_header_count != raw_observation.header_count
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.RESPONSE_HEADER_BINDING_MISMATCH,
            "raw observation header evidence is not the transport response headers",
        )
    if not raw_observation.observation_id:
        _reject(
            OpenRouterIntegrationFailureCodeV1.RAW_OBSERVATION_ID_MISMATCH,
            "raw observation carries no identity",
        )

    # --- the mapping is of that observation, under the pinned manifest
    if mapping_result.raw_observation_id != raw_observation.observation_id:
        _reject(
            OpenRouterIntegrationFailureCodeV1.MAPPING_OBSERVATION_MISMATCH,
            "mapping result points at a different raw observation",
        )
    if (
        mapping_result.source_manifest_id
        != OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
        or mapping_result.source_manifest_sha256
        != OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.MAPPING_MANIFEST_MISMATCH,
            "mapping result is not bound to the pinned wire manifest",
        )
    if (
        mapping_result.raw_body_sha256 != raw_observation.raw_body_sha256
        or mapping_result.header_evidence_sha256
        != raw_observation.header_evidence_sha256
    ):
        _reject(
            OpenRouterIntegrationFailureCodeV1.MAPPING_PROVENANCE_MISMATCH,
            "mapping result evidence digests disagree with the bound observation",
        )

    provider_display_names = tuple(
        candidate.provider_display_name
        for candidate in (
            mapping_result.endpoint_collection.available
            if mapping_result.endpoint_collection
            else ()
        )
    ) + tuple(record.provider_display_name for record in mapping_result.attempts)

    return OpenRouterPreLiveIntegrationReceiptV1(
        request_intent_receipt_id=request_intent_receipt.receipt_id,
        transport_record_id=transport_record.record_id or "",
        raw_observation_id=raw_observation.observation_id,
        mapping_result_id=mapping_result.mapping_id or "",
        safety_contract_id=safety_contract_id,
        request_body_sha256=request_intent_receipt.body_sha256,
        request_semantic_headers_sha256=request_intent_receipt.semantic_headers_sha256,
        response_body_sha256=raw_observation.raw_body_sha256 or "",
        response_header_evidence_sha256=raw_observation.header_evidence_sha256 or "",
        requested_model=request_intent_receipt.exact_model,
        actual_served_model=mapping_result.actual_served_model,
        actual_served_model_status=mapping_result.actual_served_model_status,
        model_conformance=_model_conformance(
            request_intent_receipt.exact_model, mapping_result
        ),
        requested_exact_endpoint_selector=(
            request_intent_receipt.exact_endpoint_selector
        ),
        response_provider_display_names=provider_display_names,
        cache_conformance=_cache_conformance(mapping_result),
        response_cache_status=mapping_result.cache_status,
        response_attempt=mapping_result.attempt,
        response_attempts_presence=mapping_result.attempts_presence,
    )


__all__ = [
    "FROZEN_OPENROUTER_INTEGRATION_GUARD_ORDER_V1",
    "OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1",
    "OPENROUTER_MAX_LOCAL_DISPATCHES_V1",
    "OPENROUTER_PRE_LIVE_INTEGRATION_RECEIPT_SCHEMA_V1",
    "OPENROUTER_TRANSPORT_EXECUTION_SCHEMA_V1",
    "OpenRouterCacheConformanceV1",
    "OpenRouterIntegrationError",
    "OpenRouterIntegrationFailureCodeV1",
    "OpenRouterModelConformanceV1",
    "OpenRouterPreLiveIntegrationReceiptV1",
    "OpenRouterTransportCompletionStateV1",
    "OpenRouterTransportExecutionRecordV1",
    "OpenRouterTransportRegistrationStateV1",
    "bind_openrouter_pre_live_integration_v1",
]

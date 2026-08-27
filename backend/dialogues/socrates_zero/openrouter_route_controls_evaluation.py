"""Authoritative offline evaluator for OpenRouter route controls v1.

The module is import-inert.  It performs no aggregate, filesystem write,
credential lookup, environment inspection, network access, provider call,
model execution, tool call, or CED application at import time.  The only
transport below is a one-shot in-memory canned byte transport.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .acquisition_tripwires import (
    AcquisitionBoundaryTripwireV0,
    assert_acquisition_artifact_tripwires_v0,
    require_clean_acquisition_boundary_tripwire_v0,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_provenance_boundary_v1 import (
    FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1,
    OPENROUTER_PROVENANCE_BOUNDARY_ID_V1,
    OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
    OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
    OpenRouterProvenanceRecordV1,
    openrouter_provenance_record_v1,
)
from .openrouter_route_controls_cases import (
    FIRST_ROUTE_CONTROL_GUARD_WINS_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1,
    FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1,
    OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1,
    OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1,
    OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1,
    OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1,
    MutationState,
    OpenRouterRouteControlCaseKind,
    OpenRouterRouteControlCaseV1,
    OpenRouterRouteControlCaseSetV1,
    OpenRouterRouteControlExpectedOutcome,
    OpenRouterRouteControlFailureCode,
    OpenRouterRouteControlGuardId,
    OpenRouterRouteControlMutationVectorV1,
    OpenRouterRouteControlThresholdsV1,
)
from .openrouter_route_controls_contracts import (
    FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1,
    FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
    OPENROUTER_ATTESTED_BASE_PROVIDER_V1,
    OPENROUTER_CACHE_HEADER_NAME_V1,
    OPENROUTER_CACHE_HEADER_VALUE_V1,
    OPENROUTER_CONTENT_TYPE_HEADER_NAME_V1,
    OPENROUTER_CONTENT_TYPE_HEADER_VALUE_V1,
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_METADATA_HEADER_NAME_V1,
    OPENROUTER_METADATA_HEADER_VALUE_V1,
    OPENROUTER_RELEVANT_FACT_IDS_V1,
    OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION,
    OPENROUTER_ROUTE_MODEL_V1,
    OPENROUTER_ROUTE_RENDERER_VERSION,
    OPENROUTER_SPECIFICATION_MANIFEST_ID_V1,
    OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1,
    OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1,
    OpenRouterPreparedRouteRequestV1,
    OpenRouterCachePolicyV1,
    OpenRouterMetadataPolicyV1,
    OpenRouterRequestIntentReceiptV1,
    OpenRouterRouteControlPolicyV1,
    OpenRouterRouteHeaderPolicyV1,
    OpenRouterSpecificationManifestBindingV1,
    default_openrouter_route_control_policy_v1,
    verify_openrouter_spec_manifest_v1,
)
from .openrouter_route_controls_parser import (
    NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION,
    ROUTER_METADATA_PARSER_SCHEMA_VERSION,
    AttemptsListStatusV1,
    OpenRouterRawResponseEvidenceV1,
    OpenRouterRouteControlParserError,
    OpenRouterRouteControlReceiptV1,
    OpenRouterRouteAttestationV1,
    OpenRouterRouterMetadataReceiptV1,
    build_reference_openrouter_route_response_v1,
    parse_openrouter_router_metadata_v1,
)
from .openrouter_route_controls_renderer import prepare_openrouter_route_request_v1


OPENROUTER_ROUTE_CONTROL_EVALUATION_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-evaluation/v1"
)
OPENROUTER_ROUTE_CONTROL_CASE_RESULT_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-case-result/v1"
)
OPENROUTER_ROUTE_CONTROL_METRICS_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-metrics/v1"
)
OPENROUTER_ROUTE_CONTROL_ARTIFACT_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-artifact/v1"
)
OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-replay-execution/v1"
)
OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-replay-lock/v1"
)
OPENROUTER_ROUTE_CONTROL_SCOPED_SNAPSHOT_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-scoped-snapshot/v1"
)
OPENROUTER_ROUTE_CONTROL_MUTATION_EVIDENCE_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-mutation-evidence/v1"
)
OPENROUTER_ROUTE_CONTROL_HISTORICAL_HASH_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-historical-hash/v1"
)
OPENROUTER_ROUTE_CONTROL_BOUNDARY_COUNTERS_SCHEMA_V1 = (
    "socrateszero-openrouter-route-control-boundary-counters/v1"
)
OPENROUTER_OFFICIAL_RESPONSE_WIRE_MAPPING_ASSESSMENT_SCHEMA_V1 = (
    "socrateszero-openrouter-official-response-wire-mapping-assessment/v1"
)

OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/"
    "artifacts/socrateszero_openrouter_route_controls_v1.json"
)
OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/"
    "artifacts/socrateszero_openrouter_route_controls_v1_replay_execution.json"
)
OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/"
    "artifacts/socrateszero_openrouter_route_controls_v1_replay_lock.json"
)
OPENROUTER_ROUTE_CONTROL_AGGREGATE_CLAIM_SUFFIX_V1 = ".aggregate-in-progress"
OPENROUTER_ROUTE_CONTROL_AGGREGATE_CONSUMED_SUFFIX_V1 = ".aggregate-consumed"
OPENROUTER_SPECIFICATION_MANIFEST_FILE_SHA256_V1 = (
    "818a1ec466bd37bd23dd86ef14fecf0fcc0049360bef7b5a16fdc2f575069e9f"
)
OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1 = (
    "NOT_ESTABLISHED_FROM_FROZEN_MANIFEST"
)
_OFFICIAL_RESPONSE_WIRE_SOURCE_LOCKS_V1 = (
    (
        "OR-S04-ROUTER-METADATA",
        "b1490dfb874fe0d90361f36f44e7e05be60135f0a258fe5dddb71725b0ecc529",
        "61e68dc8d131a7294b852de8c632f6f26687658de2e460771fce362085fae50f",
        None,
    ),
    (
        "OR-S08-OPENAPI",
        "085d6eaf00b93f03fe3dbb6f170fe438d76a408bb89096f74c4b418dfd6ca838",
        "db0408d86824292ee5ebb1630bd5fe53c5a84e242f964f7fed38ca2ec6ec0629",
        None,
    ),
)
_OFFICIAL_RESPONSE_WIRE_FACT_LOCKS_V1 = (
    (
        "ORSPEC-F04",
        "6d76893bbd59e54991f71ee1402634b3f5624cfe39cc1139a8d57e32fe5b2714",
        "5c5e77e1b7257136a9059f7225dc106d59b5fc7dcb982059435f8a93bcdfbba5",
    ),
    (
        "ORSPEC-F05",
        "603e8efa98c9d431389b291b92c90f17753f949c5c71a889465b75e7c053cdd7",
        "f7470d7a4aaa2848b93ee6fd3b20afe9c8f67f76826c6bb7201013414cea7190",
    ),
)
_LOCAL_NORMALIZED_RESPONSE_FIELD_NAMES_V1 = (
    "openrouter_metadata",
    "requested_model",
    "requested_provider_only",
    "routing_strategy",
    "actual_model",
    "attempt",
    "attempts",
    "provider",
    "pipeline",
)
_STRUCTURED_WIRE_SCHEMA_RECORD_KEYS_V1 = frozenset(
    {
        "field_types",
        "official_response_wire_schema",
        "official_wire_to_normalized_mapping",
        "properties",
        "response_wire_schema",
        "wire_schema",
    }
)


class _FrozenEvaluationContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterRouteControlHypothesisStatusV1(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class OpenRouterRouteControlArtifactClaimFirewallV1(_FrozenEvaluationContractV1):
    normalized_canned_schema_is_official_wire_schema: Literal[False] = False
    official_response_wire_mapping_status: Literal[
        OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1
    ] = OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1
    exact_endpoint_response_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    live_server_enforcement: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    live_no_fallback_proof: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"
    actual_openrouter_availability: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    real_provider_execution: Literal[False] = False
    production_authority: Literal["none"] = "none"


FROZEN_OPENROUTER_ROUTE_CONTROL_ARTIFACT_CLAIM_FIREWALL_V1 = (
    OpenRouterRouteControlArtifactClaimFirewallV1()
)


class OpenRouterOfficialResponseWireSourceObservationV1(
    _FrozenEvaluationContractV1
):
    source_id: str
    source_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_content_bytes: Optional[int] = Field(default=None, ge=1)


class OpenRouterOfficialResponseWireFactObservationV1(
    _FrozenEvaluationContractV1
):
    evidence_id: str = Field(pattern=r"^ORSPEC-F[0-9]{2}$")
    fact_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_fact: str
    semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_keys: Tuple[str, ...]

    @model_validator(mode="after")
    def validate_fact_digest(self) -> "OpenRouterOfficialResponseWireFactObservationV1":
        if _sha256_bytes(self.normalized_fact.encode("utf-8")) != self.semantic_sha256:
            raise ContractValidationError("wire-mapping fact semantic digest changed")
        if self.record_keys != tuple(sorted(self.record_keys)) or len(set(self.record_keys)) != len(
            self.record_keys
        ):
            raise ContractValidationError("wire-mapping fact record keys are not canonical")
        return self


def _contains_exact_manifest_token(value: str, token: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])",
        value,
    ) is not None


def _derive_wire_mapping_assessment_fields_v1(
    sources: Tuple[OpenRouterOfficialResponseWireSourceObservationV1, ...],
    facts: Tuple[OpenRouterOfficialResponseWireFactObservationV1, ...],
) -> Dict[str, object]:
    fact_text = "\n".join(item.normalized_fact for item in facts)
    retained = tuple(
        name
        for name in _LOCAL_NORMALIZED_RESPONSE_FIELD_NAMES_V1
        if _contains_exact_manifest_token(fact_text, name)
    )
    missing = tuple(
        name for name in _LOCAL_NORMALIZED_RESPONSE_FIELD_NAMES_V1 if name not in retained
    )
    source_content_length_metadata_complete = all(
        type(item.source_content_bytes) is int and item.source_content_bytes > 0
        for item in sources
    )
    structured_wire_schema_recorded = any(
        _STRUCTURED_WIRE_SCHEMA_RECORD_KEYS_V1.intersection(item.record_keys)
        for item in facts
    )
    complete_names = not missing
    complete_types = (
        source_content_length_metadata_complete and structured_wire_schema_recorded
    )
    mapping_retained = complete_names and complete_types
    status = (
        "ESTABLISHED_FROM_FROZEN_MANIFEST"
        if mapping_retained
        else OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1
    )
    return {
        "source_content_length_metadata_complete": (
            source_content_length_metadata_complete
        ),
        "retained_exact_local_normalized_field_names": retained,
        "missing_exact_local_normalized_field_names": missing,
        "complete_nested_wire_field_names_retained": complete_names,
        "complete_nested_wire_field_types_retained": complete_types,
        "structured_wire_schema_recorded": structured_wire_schema_recorded,
        "official_wire_to_local_normalized_mapping_retained": mapping_retained,
        "status": status,
        "violation_count": int(status != "ESTABLISHED_FROM_FROZEN_MANIFEST"),
    }


class OpenRouterOfficialResponseWireMappingAssessmentV1(
    _FrozenEvaluationContractV1
):
    schema_version: Literal[
        OPENROUTER_OFFICIAL_RESPONSE_WIRE_MAPPING_ASSESSMENT_SCHEMA_V1
    ] = OPENROUTER_OFFICIAL_RESPONSE_WIRE_MAPPING_ASSESSMENT_SCHEMA_V1
    assessment_id: Optional[str] = None
    audit_basis: Literal[
        "CONTENT_ADDRESSED_FROZEN_MANIFEST_RECORDS_ONLY"
    ] = "CONTENT_ADDRESSED_FROZEN_MANIFEST_RECORDS_ONLY"
    specification_manifest_path: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    specification_manifest_id: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    specification_manifest_semantic_sha256: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    specification_manifest_file_sha256: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_FILE_SHA256_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_FILE_SHA256_V1
    source_observations: Tuple[
        OpenRouterOfficialResponseWireSourceObservationV1, ...
    ]
    fact_observations: Tuple[
        OpenRouterOfficialResponseWireFactObservationV1, ...
    ]
    source_content_length_metadata_complete: bool = Field(strict=True)
    retained_exact_local_normalized_field_names: Tuple[str, ...]
    missing_exact_local_normalized_field_names: Tuple[str, ...]
    complete_nested_wire_field_names_retained: bool = Field(strict=True)
    complete_nested_wire_field_types_retained: bool = Field(strict=True)
    structured_wire_schema_recorded: bool = Field(strict=True)
    official_wire_to_local_normalized_mapping_retained: bool = Field(strict=True)
    status: Literal[
        "ESTABLISHED_FROM_FROZEN_MANIFEST",
        OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1,
    ]
    violation_count: int = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_and_identify(
        self,
    ) -> "OpenRouterOfficialResponseWireMappingAssessmentV1":
        source_identity = tuple(
            (
                item.source_id,
                item.source_record_sha256,
                item.source_content_sha256,
                item.source_content_bytes,
            )
            for item in self.source_observations
        )
        if source_identity != _OFFICIAL_RESPONSE_WIRE_SOURCE_LOCKS_V1:
            raise ContractValidationError(
                "official response wire source observations changed"
            )
        fact_identity = tuple(
            (item.evidence_id, item.fact_record_sha256, item.semantic_sha256)
            for item in self.fact_observations
        )
        if fact_identity != _OFFICIAL_RESPONSE_WIRE_FACT_LOCKS_V1:
            raise ContractValidationError(
                "official response wire fact observations changed"
            )
        expected = _derive_wire_mapping_assessment_fields_v1(
            self.source_observations,
            self.fact_observations,
        )
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ContractValidationError(
                    f"official response wire assessment field changed: {field_name}"
                )
        expected_id = stable_contract_id(
            "szorwiremappingassessmentv1",
            self.model_dump(mode="json", exclude={"assessment_id"}),
        )
        if self.assessment_id not in (None, expected_id):
            raise ContractValidationError("wire-mapping assessment ID mismatch")
        object.__setattr__(self, "assessment_id", expected_id)
        return self


class OpenRouterRouteControlCaseActualOutcomeV1(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INVALID_PROBE_CONSTRUCTION = "INVALID_PROBE_CONSTRUCTION"


class OpenRouterRouteControlCaseResultV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_CASE_RESULT_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_CASE_RESULT_SCHEMA_V1
    case_id: str
    case_fingerprint: str
    kind: OpenRouterRouteControlCaseKind
    mutation_vector: OpenRouterRouteControlMutationVectorV1
    construction_valid: bool = Field(strict=True)
    expected_outcome: OpenRouterRouteControlExpectedOutcome
    actual_outcome: OpenRouterRouteControlCaseActualOutcomeV1
    expected_guard_id: Optional[OpenRouterRouteControlGuardId]
    actual_guard_id: Optional[OpenRouterRouteControlGuardId]
    expected_failure_code: Optional[OpenRouterRouteControlFailureCode]
    actual_failure_code: Optional[OpenRouterRouteControlFailureCode]
    guard_trace: Tuple[OpenRouterRouteControlGuardId, ...]
    expected_canned_transport_invocations: int = Field(ge=0, le=1)
    expected_complete_route_intent_receipts: int = Field(ge=0, le=2)
    expected_complete_metadata_receipts: int = Field(ge=0, le=1)
    canned_transport_invocations: int = Field(ge=0, le=1)
    complete_route_intent_receipts: int = Field(ge=0, le=2)
    complete_metadata_receipts: int = Field(ge=0, le=1)
    candidate_request_evidence_id: str = Field(
        pattern=r"^szorroute(?:intentreceiptv1|candidateevidencev1)_[0-9a-f]{64}$"
    )
    request_intent_receipt_ids: Tuple[str, ...] = ()
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    route_intent_id: str
    metadata_receipt_id: Optional[str] = None
    route_attestation_id: Optional[str] = None
    raw_response_evidence: Optional[OpenRouterRawResponseEvidenceV1] = None
    metadata_receipt: Optional[OpenRouterRouterMetadataReceiptV1] = None
    route_attestation: Optional[OpenRouterRouteAttestationV1] = None
    response_exact_endpoint_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_server_enforcement: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    real_provider_execution: Literal[False] = False
    result_matches_expectation: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_result(self) -> "OpenRouterRouteControlCaseResultV1":
        accepted = self.actual_outcome is OpenRouterRouteControlCaseActualOutcomeV1.ACCEPTED
        rejected = self.actual_outcome is OpenRouterRouteControlCaseActualOutcomeV1.REJECTED
        invalid = self.actual_outcome is (
            OpenRouterRouteControlCaseActualOutcomeV1.INVALID_PROBE_CONSTRUCTION
        )
        if invalid:
            if self.construction_valid:
                raise ContractValidationError("valid construction cannot be INVALID")
            if self.actual_guard_id is not None or self.actual_failure_code is not None:
                raise ContractValidationError("invalid construction cannot claim a guard")
            if self.guard_trace or self.canned_transport_invocations:
                raise ContractValidationError("invalid construction cannot be scored")
        elif not self.construction_valid:
            raise ContractValidationError("invalid construction must not be scored")
        elif accepted:
            if self.actual_guard_id is not None or self.actual_failure_code is not None:
                raise ContractValidationError("accepted case cannot claim a failure")
            expected_trace = (
                FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1[:16]
                if self.kind is OpenRouterRouteControlCaseKind.POSITIVE_REQUEST
                else FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1
            )
            if self.guard_trace != expected_trace:
                raise ContractValidationError("accepted case guard trace changed")
        elif rejected:
            if self.actual_guard_id is None or self.actual_failure_code is None:
                raise ContractValidationError("rejected case requires guard and failure")
            if self.guard_trace != _guard_trace_through(self.actual_guard_id):
                raise ContractValidationError("rejected case guard trace changed")
        else:  # pragma: no cover - exhaustive enum firewall
            raise ContractValidationError("unknown case outcome")
        if self.complete_metadata_receipts and not accepted:
            raise ContractValidationError("rejected case cannot claim metadata receipt")
        if len(self.request_intent_receipt_ids) != self.complete_route_intent_receipts:
            raise ContractValidationError("route receipt count and identities disagree")
        if self.complete_metadata_receipts != int(self.metadata_receipt is not None):
            raise ContractValidationError("metadata receipt count and payload disagree")
        if self.metadata_receipt is not None:
            if (
                self.raw_response_evidence is None
                or self.route_attestation is None
                or self.metadata_receipt_id != self.metadata_receipt.receipt_id
                or self.route_attestation_id != self.route_attestation.attestation_id
                or self.metadata_receipt.raw_response_evidence_id
                != self.raw_response_evidence.evidence_id
                or self.metadata_receipt.raw_response_sha256
                != self.raw_response_evidence.raw_response_sha256
                or self.route_attestation.metadata_receipt_id
                != self.metadata_receipt.receipt_id
            ):
                raise ContractValidationError("case receipt evidence links changed")
        elif self.route_attestation is not None or self.route_attestation_id is not None:
            raise ContractValidationError("attestation requires metadata receipt")
        expected_actual = OpenRouterRouteControlCaseActualOutcomeV1(
            self.expected_outcome.value
        )
        derived_match = (
            self.construction_valid
            and self.actual_outcome is expected_actual
            and self.actual_guard_id == self.expected_guard_id
            and self.actual_failure_code == self.expected_failure_code
            and self.canned_transport_invocations
            == self.expected_canned_transport_invocations
            and self.complete_route_intent_receipts
            == self.expected_complete_route_intent_receipts
            and self.complete_metadata_receipts
            == self.expected_complete_metadata_receipts
        )
        if self.result_matches_expectation != derived_match:
            raise ContractValidationError("case expectation flag is not derived")
        return self


@dataclass
class _RouteCandidateV1:
    manifest_semantic_sha256: str
    route_control_policy_id: str
    body: Dict[str, object]
    headers: Dict[str, object]
    body_bytes: bytes
    header_bytes: bytes
    claimed_body_sha256: str
    claimed_body_length: int
    claimed_header_sha256: str
    claimed_header_length: int
    claimed_route_intent_id: str
    request_intent_receipt_id: str
    seal_integrity: bool
    transport_registered: bool
    transport_completed: bool
    raw_response_bytes: Optional[bytes]
    construction_valid: bool


@dataclass(frozen=True)
class _AuthoritativeAggregateClaimV1:
    artifact_path: Path
    claim_path: Path
    consumed_path: Path
    claim_sha256: str


class _OneShotCannedRouteTransportV1:
    """Private provider-agnostic in-memory byte transport."""

    def __init__(
        self,
        *,
        registered_body: bytes,
        registered_headers: bytes,
        raw_response: Optional[bytes],
        registered: bool,
        completed: bool,
    ) -> None:
        self._registered_body = registered_body
        self._registered_headers = registered_headers
        self._raw_response = raw_response
        self._registered = registered
        self._completed = completed
        self.invocations = 0

    @property
    def registered(self) -> bool:
        return self._registered

    @property
    def completed(self) -> bool:
        return self._completed

    def send(self, body_bytes: bytes, semantic_header_bytes: bytes) -> Optional[bytes]:
        if not self._registered:
            raise ContractValidationError("canned response is not registered")
        if body_bytes != self._registered_body or semantic_header_bytes != self._registered_headers:
            raise ContractValidationError("canned dispatch bytes differ from registration")
        if self.invocations:
            raise ContractValidationError("canned transport is strictly one-shot")
        self.invocations += 1
        return self._raw_response


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def assess_openrouter_official_response_wire_mapping_v1(
    root: Optional[Path] = None,
) -> OpenRouterOfficialResponseWireMappingAssessmentV1:
    """Derive the frozen manifest-only response-wire sufficiency finding."""

    repository_root = _repository_root() if root is None else Path(root)
    verify_openrouter_spec_manifest_v1(repository_root)
    manifest_path = (
        repository_root / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    )
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError(
            "frozen OpenRouter specification manifest is unavailable or malformed"
        ) from exc
    if _sha256_bytes(manifest_bytes) != OPENROUTER_SPECIFICATION_MANIFEST_FILE_SHA256_V1:
        raise ContractValidationError("specification manifest file digest changed")
    source_records = manifest.get("source_records")
    fact_records = manifest.get("fact_records")
    if not isinstance(source_records, list) or not isinstance(fact_records, list):
        raise ContractValidationError("specification evidence records are malformed")
    source_by_id = {
        record.get("source_id"): record
        for record in source_records
        if isinstance(record, dict) and isinstance(record.get("source_id"), str)
    }
    fact_by_id = {
        record.get("evidence_id"): record
        for record in fact_records
        if isinstance(record, dict) and isinstance(record.get("evidence_id"), str)
    }
    if len(source_by_id) != len(source_records) or len(fact_by_id) != len(fact_records):
        raise ContractValidationError("specification evidence IDs are not unique")
    sources = []
    for source_id, _, _, _ in _OFFICIAL_RESPONSE_WIRE_SOURCE_LOCKS_V1:
        record = source_by_id.get(source_id)
        if not isinstance(record, dict):
            raise ContractValidationError(
                f"required response-wire source is absent: {source_id}"
            )
        sources.append(
            OpenRouterOfficialResponseWireSourceObservationV1(
                source_id=source_id,
                source_record_sha256=_sha256_bytes(
                    canonical_json(record).encode("utf-8")
                ),
                source_content_sha256=record.get("source_content_sha256"),
                source_content_bytes=record.get("source_content_bytes"),
            )
        )
    facts = []
    for evidence_id, _, _ in _OFFICIAL_RESPONSE_WIRE_FACT_LOCKS_V1:
        record = fact_by_id.get(evidence_id)
        if not isinstance(record, dict):
            raise ContractValidationError(
                f"required response-wire fact is absent: {evidence_id}"
            )
        facts.append(
            OpenRouterOfficialResponseWireFactObservationV1(
                evidence_id=evidence_id,
                fact_record_sha256=_sha256_bytes(
                    canonical_json(record).encode("utf-8")
                ),
                normalized_fact=record.get("normalized_fact"),
                semantic_sha256=record.get("semantic_sha256"),
                record_keys=tuple(sorted(record)),
            )
        )
    source_observations = tuple(sources)
    fact_observations = tuple(facts)
    derived = _derive_wire_mapping_assessment_fields_v1(
        source_observations,
        fact_observations,
    )
    return OpenRouterOfficialResponseWireMappingAssessmentV1(
        source_observations=source_observations,
        fact_observations=fact_observations,
        **derived,
    )


def official_response_wire_mapping_violation_count_v1(
    assessment: OpenRouterOfficialResponseWireMappingAssessmentV1,
) -> int:
    if type(assessment) is not OpenRouterOfficialResponseWireMappingAssessmentV1:
        raise ContractValidationError(
            "wire-mapping assessment must use the exact frozen v1 type"
        )
    validated = OpenRouterOfficialResponseWireMappingAssessmentV1.model_validate(
        assessment.model_dump(mode="json")
    )
    if validated != assessment:
        raise ContractValidationError("wire-mapping assessment integrity changed")
    return validated.violation_count


def official_response_wire_mapping_gate_passes_v1(
    assessment: OpenRouterOfficialResponseWireMappingAssessmentV1,
    thresholds: OpenRouterRouteControlThresholdsV1 = (
        FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1
    ),
) -> bool:
    if thresholds != FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1:
        raise ContractValidationError("wire-mapping gate thresholds changed")
    return official_response_wire_mapping_violation_count_v1(assessment) <= (
        thresholds.maximum_official_response_wire_mapping_violations
    )


def _route_intent_id(
    prepared: OpenRouterPreparedRouteRequestV1,
    body_bytes: bytes,
    header_bytes: bytes,
) -> str:
    return stable_contract_id(
        "szorrouteintent",
        {
            "body_length": len(body_bytes),
            "body_sha256": _sha256_bytes(body_bytes),
            "route_control_policy_id": (
                prepared.route_control_policy.route_control_policy_id
            ),
            "semantic_headers_length": len(header_bytes),
            "semantic_headers_sha256": _sha256_bytes(header_bytes),
            "specification_manifest_id": OPENROUTER_SPECIFICATION_MANIFEST_ID_V1,
            "specification_manifest_sha256": OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1,
        },
    )


def _refresh_request_evidence(
    candidate: _RouteCandidateV1,
    prepared: OpenRouterPreparedRouteRequestV1,
) -> None:
    candidate.body_bytes = canonical_json(candidate.body).encode("utf-8")
    candidate.header_bytes = canonical_json(candidate.headers).encode("utf-8")
    candidate.claimed_body_sha256 = _sha256_bytes(candidate.body_bytes)
    candidate.claimed_body_length = len(candidate.body_bytes)
    candidate.claimed_header_sha256 = _sha256_bytes(candidate.header_bytes)
    candidate.claimed_header_length = len(candidate.header_bytes)
    candidate.claimed_route_intent_id = _route_intent_id(
        prepared, candidate.body_bytes, candidate.header_bytes
    )


def _refresh_request_evidence_identity(
    candidate: _RouteCandidateV1,
    prepared: OpenRouterPreparedRouteRequestV1,
) -> None:
    exact_prepared_evidence = (
        candidate.manifest_semantic_sha256
        == OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
        and candidate.route_control_policy_id
        == prepared.route_control_policy.route_control_policy_id
        and candidate.body_bytes == prepared.body_bytes
        and candidate.header_bytes == prepared.header_bytes
        and candidate.claimed_body_sha256 == prepared.body_sha256
        and candidate.claimed_body_length == prepared.body_length
        and candidate.claimed_header_sha256 == prepared.header_sha256
        and candidate.claimed_header_length == prepared.header_length
        and candidate.claimed_route_intent_id == prepared.route_intent_id
        and candidate.seal_integrity
    )
    if exact_prepared_evidence:
        candidate.request_intent_receipt_id = (
            prepared.request_intent_receipt.receipt_id or ""
        )
        return
    candidate.request_intent_receipt_id = stable_contract_id(
        "szorroutecandidateevidencev1",
        {
            "body_length": candidate.claimed_body_length,
            "body_sha256": candidate.claimed_body_sha256,
            "header_length": candidate.claimed_header_length,
            "header_sha256": candidate.claimed_header_sha256,
            "manifest_semantic_sha256": candidate.manifest_semantic_sha256,
            "route_control_policy_id": candidate.route_control_policy_id,
            "route_intent_id": candidate.claimed_route_intent_id,
            "seal_integrity": candidate.seal_integrity,
        },
    )


_ABSENT_VALUE_V1 = ("ABSENT",)
_METADATA_UNAVAILABLE_VALUE_V1 = ("METADATA_UNAVAILABLE",)
_NOT_APPLICABLE_VALUE_V1 = ("NOT_APPLICABLE",)


def _nested_value_v1(value: object, path: str) -> object:
    current = value
    for part in path.split(".") if path else ():
        match = re.fullmatch(r"([^\[]+)(?:\[([0-9]+)\])?", part)
        if match is None or not isinstance(current, dict):
            return _ABSENT_VALUE_V1
        key, raw_index = match.groups()
        if key not in current:
            return _ABSENT_VALUE_V1
        current = current[key]
        if raw_index is not None:
            index = int(raw_index)
            if not isinstance(current, list) or index >= len(current):
                return _ABSENT_VALUE_V1
            current = current[index]
    return deepcopy(current)


def _literal_probe_value_v1(
    path: str,
    candidate: _RouteCandidateV1,
    response: Mapping[str, object],
) -> object:
    if path == "manifest.semantic_digest":
        return candidate.manifest_semantic_sha256[:8]
    if path == "request.serialization.body":
        return (
            "CANONICAL"
            if canonical_json(candidate.body).encode("utf-8") == candidate.body_bytes
            else "NONCANONICAL_WHITESPACE"
        )
    if path == "request.prepared_bytes.seal_integrity":
        return "MATCH" if candidate.seal_integrity else "MUTATED_AFTER_PREPARATION"
    if path.startswith("request.body."):
        value = _nested_value_v1(candidate.body, path.removeprefix("request.body."))
    elif path.startswith("request.headers."):
        value = _nested_value_v1(
            candidate.headers, path.removeprefix("request.headers.")
        )
    elif path.startswith("response."):
        relative = path.removeprefix("response.")
        value = _nested_value_v1(response, relative)
        if relative == "openrouter_metadata" and isinstance(value, dict):
            return {"state": "PRESENT"}
    else:
        return _ABSENT_VALUE_V1
    return {"state": "ABSENT"} if value == _ABSENT_VALUE_V1 else value


def _metadata_projection_state_v1(response: Mapping[str, object]) -> object:
    if "openrouter_metadata" not in response:
        return _ABSENT_VALUE_V1
    metadata = response["openrouter_metadata"]
    if not isinstance(metadata, dict):
        return ("MALFORMED", type(metadata).__name__)
    if "unknown_authority" in metadata:
        return ("PRESENT_AUTHORITY_OVERRIDE",)
    return ("PRESENT",)


def _response_projection_value_v1(
    response: Mapping[str, object], key: str, *, availability_sensitive: bool = True
) -> object:
    metadata = response.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        return (
            _METADATA_UNAVAILABLE_VALUE_V1
            if availability_sensitive
            else _ABSENT_VALUE_V1
        )
    return deepcopy(metadata[key]) if key in metadata else _ABSENT_VALUE_V1


def _response_fallback_projection_v1(
    response: Mapping[str, object],
) -> object:
    metadata = response.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        return ()
    signals = []
    strategy = metadata.get("routing_strategy")
    if strategy not in (None, "direct"):
        signals.append(("routing_strategy", deepcopy(strategy)))
    if "fallback_observed" in metadata:
        signals.append(("fallback_observed", deepcopy(metadata["fallback_observed"])))
    pipeline = metadata.get("pipeline")
    if pipeline not in (None, []):
        signals.append(("pipeline", deepcopy(pipeline)))
    return tuple(signals)


def _mutation_projection_v1(
    case: OpenRouterRouteControlCaseV1,
    candidate: _RouteCandidateV1,
    response: Mapping[str, object],
) -> Dict[str, object]:
    provider = candidate.body.get("provider")
    provider_object = provider if isinstance(provider, dict) else {}
    response_applicable = case.kind not in {
        OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
        OpenRouterRouteControlCaseKind.ORTHOGONAL_REQUEST,
    }
    if response_applicable:
        metadata_presence = _metadata_projection_state_v1(response)
        attempt = _response_projection_value_v1(response, "attempt")
        attempts = _response_projection_value_v1(response, "attempts")
        actual_model = _response_projection_value_v1(response, "actual_model")
        attested_provider = _response_projection_value_v1(response, "provider")
        endpoint_claim = (
            _response_projection_value_v1(
                response, "endpoint_slug", availability_sensitive=False
            )
        )
        cache_state = tuple(
            (key, deepcopy(response[key]))
            for key in ("cache_state", "cache_hit", "cache_status")
            if key in response
        ) or _ABSENT_VALUE_V1
        response_identity = _sha256_bytes(_canonical_response_bytes(response))
        receipt_identity: object = stable_contract_id(
            "szorroutecandidatecombinedreceiptv1",
            {
                "request_evidence_id": candidate.request_intent_receipt_id,
                "response_sha256": response_identity,
            },
        )
        response_fallback = _response_fallback_projection_v1(response)
    else:
        metadata_presence = _NOT_APPLICABLE_VALUE_V1
        attempt = _NOT_APPLICABLE_VALUE_V1
        attempts = _NOT_APPLICABLE_VALUE_V1
        actual_model = _NOT_APPLICABLE_VALUE_V1
        attested_provider = _NOT_APPLICABLE_VALUE_V1
        endpoint_claim = _NOT_APPLICABLE_VALUE_V1
        cache_state = _NOT_APPLICABLE_VALUE_V1
        receipt_identity = candidate.request_intent_receipt_id
        response_fallback = _NOT_APPLICABLE_VALUE_V1
    return {
        "spec_manifest_integrity": candidate.manifest_semantic_sha256,
        "model_field": deepcopy(candidate.body.get("model", _ABSENT_VALUE_V1)),
        "models_absence": deepcopy(candidate.body.get("models", _ABSENT_VALUE_V1)),
        "endpoint_restriction": deepcopy(provider_object.get("only", _ABSENT_VALUE_V1)),
        "order": deepcopy(provider_object.get("order", _ABSENT_VALUE_V1)),
        "fallback": (
            deepcopy(provider_object.get("allow_fallbacks", _ABSENT_VALUE_V1)),
            response_fallback,
        ),
        "require_parameters": deepcopy(
            provider_object.get("require_parameters", _ABSENT_VALUE_V1)
        ),
        "max_price_status": deepcopy(
            provider_object.get("max_price", _ABSENT_VALUE_V1)
        ),
        "stream": deepcopy(candidate.body.get("stream", _ABSENT_VALUE_V1)),
        "tools": deepcopy(candidate.body.get("tools", _ABSENT_VALUE_V1)),
        "metadata_header": deepcopy(
            candidate.headers.get(OPENROUTER_METADATA_HEADER_NAME_V1, _ABSENT_VALUE_V1)
        ),
        "cache_header": deepcopy(
            candidate.headers.get(OPENROUTER_CACHE_HEADER_NAME_V1, _ABSENT_VALUE_V1)
        ),
        "body_bytes": candidate.body_bytes,
        "header_bytes": candidate.header_bytes,
        "metadata_presence": metadata_presence,
        "attempt": attempt,
        "attempts_list": attempts,
        "actual_model": actual_model,
        "provider": attested_provider,
        "endpoint_attestation_claim": endpoint_claim,
        "cache_state": cache_state,
        "receipt_identity": receipt_identity,
    }


def _realized_mutations_match_v1(
    case: OpenRouterRouteControlCaseV1,
    before_candidate: _RouteCandidateV1,
    before_response: Mapping[str, object],
    after_candidate: _RouteCandidateV1,
    after_response: Mapping[str, object],
) -> bool:
    for mutation in case.mutations:
        before = _literal_probe_value_v1(
            mutation.path, before_candidate, before_response
        )
        after = _literal_probe_value_v1(
            mutation.path, after_candidate, after_response
        )
        if (
            canonical_json(before) != mutation.before_json
            or canonical_json(after) != mutation.after_json
        ):
            return False
    before_vector = _mutation_projection_v1(case, before_candidate, before_response)
    after_vector = _mutation_projection_v1(case, after_candidate, after_response)
    for field_name, state in case.mutation_vector.__dict__.items():
        if field_name == "schema_version":
            continue
        before = before_vector[field_name]
        after = after_vector[field_name]
        if state is MutationState.NOT_APPLICABLE:
            if before != _NOT_APPLICABLE_VALUE_V1 or after != before:
                return False
        elif state is MutationState.PRESERVED:
            if before != after:
                return False
        elif before == after:
            return False
    return True


def _response_object(*, include_attempts: bool = False) -> Dict[str, object]:
    return json.loads(
        build_reference_openrouter_route_response_v1(
            include_attempts=include_attempts
        )
    )


def _canonical_response_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_json(value).encode("utf-8")


def _build_candidate_v1(
    case: OpenRouterRouteControlCaseV1,
    prepared: OpenRouterPreparedRouteRequestV1,
) -> _RouteCandidateV1:
    body = json.loads(prepared.canonical_body_json)
    headers = json.loads(prepared.canonical_semantic_headers_json)
    include_attempts = case.case_id in {
        "orroutev1-ss02-metadata-attempts-present",
        "orroutev1-os10-attempts-inconsistent",
        "orroutev1-os11-several-attempts",
        "orroutev1-os12-attempts-top-level-contradiction",
    }
    response = _response_object(include_attempts=include_attempts)
    if case.case_id == "orroutev1-ss03-forward-compatible-extras":
        response = json.loads(
            build_reference_openrouter_route_response_v1(
                metadata_extras={"future_field": {"opaque": "retained"}},
                envelope_extras={"future_envelope": ["opaque"]},
            )
        )
    candidate = _RouteCandidateV1(
        manifest_semantic_sha256=OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1,
        route_control_policy_id=(
            prepared.route_control_policy.route_control_policy_id or ""
        ),
        body=body,
        headers=headers,
        body_bytes=prepared.body_bytes,
        header_bytes=prepared.header_bytes,
        claimed_body_sha256=prepared.body_sha256 or "",
        claimed_body_length=prepared.body_length or 0,
        claimed_header_sha256=prepared.header_sha256,
        claimed_header_length=prepared.header_length,
        claimed_route_intent_id=prepared.route_intent_id or "",
        request_intent_receipt_id=(prepared.request_intent_receipt.receipt_id or ""),
        seal_integrity=True,
        transport_registered=True,
        transport_completed=True,
        raw_response_bytes=_canonical_response_bytes(response),
        construction_valid=True,
    )

    case_id = case.case_id
    frozen_case = next(
        (
            frozen
            for frozen in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
            if frozen.case_id == case_id
        ),
        None,
    )
    known_frozen_case = frozen_case is not None and frozen_case == case
    before_candidate = deepcopy(candidate)
    before_response = deepcopy(response)

    # Request mutations.  Each branch changes only the frozen causal dimension;
    # byte and receipt identities are recomputed as declared dependent changes.
    if case_id == "orroutev1-or01-missing-model":
        body.pop("model")
    elif case_id == "orroutev1-or02-wrong-model":
        body["model"] = "openai/gpt-4.1"
    elif case_id == "orroutev1-or03-models-singleton-present":
        body["models"] = [OPENROUTER_ROUTE_MODEL_V1]
    elif case_id == "orroutev1-or04-models-several-present":
        body["models"] = [OPENROUTER_ROUTE_MODEL_V1, "openai/gpt-4.1"]
    elif case_id == "orroutev1-or05-provider-only-missing":
        body["provider"].pop("only")  # type: ignore[union-attr]
    elif case_id == "orroutev1-or06-only-empty":
        body["provider"]["only"] = []  # type: ignore[index]
    elif case_id == "orroutev1-or07-only-multiple":
        body["provider"]["only"] = [OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1, "azure/eastus"]  # type: ignore[index]
    elif case_id == "orroutev1-or08-only-duplicate":
        body["provider"]["only"] = [OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1] * 2  # type: ignore[index]
    elif case_id == "orroutev1-or09-wrong-endpoint":
        body["provider"]["only"] = ["azure/eastus"]  # type: ignore[index]
    elif case_id == "orroutev1-or10-wildcard-selector":
        body["provider"]["only"] = ["azure/*"]  # type: ignore[index]
    elif case_id == "orroutev1-or11-base-provider-selector":
        body["provider"]["only"] = ["openai"]  # type: ignore[index]
    elif case_id == "orroutev1-or12-order-missing":
        body["provider"].pop("order")  # type: ignore[union-attr]
    elif case_id == "orroutev1-or13-order-mismatch":
        body["provider"]["order"] = ["azure/eastus"]  # type: ignore[index]
    elif case_id == "orroutev1-or14-order-extra-endpoint":
        body["provider"]["order"] = [OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1, "azure/eastus"]  # type: ignore[index]
    elif case_id == "orroutev1-or15-fallback-true":
        body["provider"]["allow_fallbacks"] = True  # type: ignore[index]
    elif case_id == "orroutev1-or16-fallback-missing":
        body["provider"].pop("allow_fallbacks")  # type: ignore[union-attr]
    elif case_id == "orroutev1-or17-require-parameters-false":
        body["provider"]["require_parameters"] = False  # type: ignore[index]
    elif case_id == "orroutev1-or18-require-parameters-missing":
        body["provider"].pop("require_parameters")  # type: ignore[union-attr]
    elif case_id == "orroutev1-or19-guessed-max-price":
        body["provider"]["max_price"] = {"prompt": 1.0}  # type: ignore[index]
    elif case_id == "orroutev1-or20-stream-true":
        body["stream"] = True
    elif case_id == "orroutev1-or21-tools-enabled":
        body["tools"] = [{"name": "forbidden-tool"}]
    elif case_id == "orroutev1-or22-metadata-header-missing":
        headers.pop(OPENROUTER_METADATA_HEADER_NAME_V1)
    elif case_id == "orroutev1-or23-metadata-header-malformed":
        headers[OPENROUTER_METADATA_HEADER_NAME_V1] = "true"
    elif case_id == "orroutev1-or24-cache-header-missing":
        headers.pop(OPENROUTER_CACHE_HEADER_NAME_V1)
    elif case_id == "orroutev1-or25-cache-enabled":
        headers[OPENROUTER_CACHE_HEADER_NAME_V1] = "true"
    elif case_id == "orroutev1-or26-body-entropy":
        body["evaluator_metadata"] = {"branch_id": "branch-a"}
    elif case_id == "orroutev1-or27-header-entropy":
        headers["X-Transport-ID"] = "transport-a"
    elif case_id == "orroutev1-or28-noncanonical-body":
        pass
    elif case_id == "orroutev1-or29-post-prepare-mutation":
        pass

    # Response mutations operate only on the local normalized canned concept
    # binding.  They are not assertions about unretained official wire paths.
    metadata = response.get("openrouter_metadata")
    if case_id == "orroutev1-os01-metadata-missing":
        response.pop("openrouter_metadata")
    elif case_id == "orroutev1-os02-metadata-malformed":
        response["openrouter_metadata"] = "malformed"
    elif case_id == "orroutev1-os03-attempt-missing":
        metadata.pop("attempt")  # type: ignore[union-attr]
    elif case_id == "orroutev1-os04-attempt-zero":
        metadata["attempt"] = 0  # type: ignore[index]
    elif case_id == "orroutev1-os05-attempt-greater-than-one":
        metadata["attempt"] = 2  # type: ignore[index]
    elif case_id == "orroutev1-os06-wrong-actual-model":
        metadata["actual_model"] = "openai/gpt-4.1"  # type: ignore[index]
    elif case_id == "orroutev1-os07-wrong-provider":
        metadata["provider"] = "google"  # type: ignore[index]
    elif case_id == "orroutev1-os08-actual-model-missing":
        metadata.pop("actual_model")  # type: ignore[union-attr]
    elif case_id == "orroutev1-os09-provider-missing":
        metadata.pop("provider")  # type: ignore[union-attr]
    elif case_id == "orroutev1-os10-attempts-inconsistent":
        metadata["attempts"][0]["model"] = "openai/gpt-4.1"  # type: ignore[index]
    elif case_id == "orroutev1-os11-several-attempts":
        metadata["attempts"].append(  # type: ignore[index,union-attr]
            {"attempt": 2, "model": OPENROUTER_ROUTE_MODEL_V1, "outcome": "success", "provider": OPENROUTER_ATTESTED_BASE_PROVIDER_V1}
        )
    elif case_id == "orroutev1-os12-attempts-top-level-contradiction":
        metadata["attempts"][0]["attempt"] = 2  # type: ignore[index]
    elif case_id == "orroutev1-os13-cache-hit-metadata-unavailable":
        response.pop("openrouter_metadata")
        response["cache_state"] = "POSSIBLE_HIT_METADATA_UNAVAILABLE"
    elif case_id == "orroutev1-os14-fake-exact-endpoint-claim":
        metadata["endpoint_slug"] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1  # type: ignore[index]
    elif case_id == "orroutev1-os15-unknown-authority-override":
        metadata["unknown_authority"] = {"actual_model": "openai/gpt-4.1"}  # type: ignore[index]
    elif case_id == "orroutev1-os16-fallback-strategy":
        metadata["routing_strategy"] = "fallback"  # type: ignore[index]
    elif case_id == "orroutev1-os17-alias-model-substitution":
        metadata["actual_model"] = "openai/gpt-4.1-mini:latest"  # type: ignore[index]
    elif case_id == "orroutev1-os18-provider-substitution":
        metadata["provider"] = "openai"  # type: ignore[index]
    elif case_id == "orroutev1-os19-forbidden-pipeline-stage":
        metadata["pipeline"] = [{"stage": "fallback"}]  # type: ignore[index]
    elif case_id == "orroutev1-os20-cache-hit-with-metadata":
        response["cache_state"] = "HIT_WITH_METADATA"

    # Dependency-aware precedence fixtures.
    if case_id == "orroutev1-p01-manifest-mismatch-plus-malformed-route":
        candidate.manifest_semantic_sha256 = "0" * 64
        body["provider"]["only"] = []  # type: ignore[index]
    elif case_id == "orroutev1-p02-wrong-model-plus-fallback-true":
        body["model"] = "openai/gpt-4.1"
        body["provider"]["allow_fallbacks"] = True  # type: ignore[index]
    elif case_id == "orroutev1-p03-cache-header-missing-plus-metadata-missing":
        headers.pop(OPENROUTER_CACHE_HEADER_NAME_V1)
        response.pop("openrouter_metadata")
    elif case_id == "orroutev1-p04-actual-model-missing-plus-provider-mismatch":
        metadata.pop("actual_model")  # type: ignore[union-attr]
        metadata["provider"] = "google"  # type: ignore[index]
    elif case_id == "orroutev1-p05-multi-attempt-plus-model-substitution":
        metadata["attempt"] = 2  # type: ignore[index]
        metadata["actual_model"] = "openai/gpt-4.1"  # type: ignore[index]
    elif case_id == "orroutev1-p06-fallback-strategy-plus-fake-endpoint":
        metadata["routing_strategy"] = "fallback"  # type: ignore[index]
        metadata["endpoint_slug"] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1  # type: ignore[index]
    elif case_id == "orroutev1-p07-max-price-plus-wrong-endpoint":
        body["provider"]["max_price"] = {"prompt": 1.0}  # type: ignore[index]
        body["provider"]["only"] = ["azure/eastus"]  # type: ignore[index]
    elif case_id == "orroutev1-p08-body-entropy-plus-wrong-endpoint":
        body["evaluator_metadata"] = {"branch_id": "branch-a"}
        body["provider"]["only"] = ["azure/eastus"]  # type: ignore[index]

    request_material_changed = any(
        mutation.path.startswith(("manifest.", "request."))
        for mutation in case.mutations
    )
    if request_material_changed:
        _refresh_request_evidence(candidate, prepared)
    if case_id == "orroutev1-or28-noncanonical-body":
        candidate.body_bytes = (" " + canonical_json(candidate.body)).encode("utf-8")
        candidate.claimed_body_sha256 = _sha256_bytes(candidate.body_bytes)
        candidate.claimed_body_length = len(candidate.body_bytes)
        candidate.claimed_route_intent_id = _route_intent_id(
            prepared, candidate.body_bytes, candidate.header_bytes
        )
    elif case_id == "orroutev1-or29-post-prepare-mutation":
        candidate.seal_integrity = False
        candidate.body_bytes = candidate.body_bytes + b" "
    _refresh_request_evidence_identity(candidate, prepared)
    candidate.raw_response_bytes = _canonical_response_bytes(response)
    candidate.construction_valid = known_frozen_case and _realized_mutations_match_v1(
        case,
        before_candidate,
        before_response,
        candidate,
        response,
    )
    return candidate


_ENTROPY_PARTS = frozenset(
    {
        "authorization", "branch", "credential", "experiment", "nonce",
        "password", "pid", "receipt", "secret", "session", "timestamp",
        "transport", "uuid", "workspace", "artifact", "evaluator",
    }
)


def _normalized_parts(key: str) -> frozenset[str]:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return frozenset(
        part for part in re.sub(r"[^0-9A-Za-z]+", "_", snake).lower().split("_") if part
    )


def _contains_forbidden_entropy(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            bool(_normalized_parts(str(key)).intersection(_ENTROPY_PARTS))
            or _contains_forbidden_entropy(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_entropy(child) for child in value)
    if isinstance(value, str):
        return bool(_normalized_parts(value).intersection(_ENTROPY_PARTS))
    return False


def _guard_trace_through(
    guard: OpenRouterRouteControlGuardId,
) -> Tuple[OpenRouterRouteControlGuardId, ...]:
    ordinal = FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1.index(guard)
    return FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1[: ordinal + 1]


def _case_result(
    case: OpenRouterRouteControlCaseV1,
    candidate: _RouteCandidateV1,
    *,
    actual_outcome: OpenRouterRouteControlCaseActualOutcomeV1,
    actual_guard: Optional[OpenRouterRouteControlGuardId],
    actual_failure: Optional[OpenRouterRouteControlFailureCode],
    invocations: int,
    route_receipts: int = 0,
    metadata_receipts: int = 0,
    parsed_receipt: Optional[OpenRouterRouteControlReceiptV1] = None,
    rejected_raw_evidence: Optional[OpenRouterRawResponseEvidenceV1] = None,
) -> OpenRouterRouteControlCaseResultV1:
    expected_actual = OpenRouterRouteControlCaseActualOutcomeV1(
        case.expected_outcome.value
    )
    matches = (
        candidate.construction_valid
        and actual_outcome is expected_actual
        and actual_guard == case.expected_guard_id
        and actual_failure == case.expected_failure_code
        and invocations == case.expected_canned_invocations
        and route_receipts == case.expected_complete_route_intent_receipts
        and metadata_receipts == case.expected_complete_metadata_receipts
    )
    metadata_receipt_id = None
    attestation_id = None
    if parsed_receipt is not None:
        metadata_receipt_id = parsed_receipt.metadata_receipt.receipt_id
        attestation_id = parsed_receipt.route_attestation.attestation_id
    return OpenRouterRouteControlCaseResultV1(
        case_id=case.case_id,
        case_fingerprint=case.case_fingerprint or "",
        kind=case.kind,
        mutation_vector=case.mutation_vector,
        construction_valid=candidate.construction_valid,
        expected_outcome=case.expected_outcome,
        actual_outcome=actual_outcome,
        expected_guard_id=case.expected_guard_id,
        actual_guard_id=actual_guard,
        expected_failure_code=case.expected_failure_code,
        actual_failure_code=actual_failure,
        expected_canned_transport_invocations=case.expected_canned_invocations,
        expected_complete_route_intent_receipts=(
            case.expected_complete_route_intent_receipts
        ),
        expected_complete_metadata_receipts=(
            case.expected_complete_metadata_receipts
        ),
        guard_trace=(
            ()
            if actual_outcome
            is OpenRouterRouteControlCaseActualOutcomeV1.INVALID_PROBE_CONSTRUCTION
            else (
                _guard_trace_through(actual_guard)
                if actual_guard is not None
                else (
                    FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1[:16]
                    if case.kind is OpenRouterRouteControlCaseKind.POSITIVE_REQUEST
                    else FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1
                )
            )
        ),
        canned_transport_invocations=invocations,
        complete_route_intent_receipts=route_receipts,
        complete_metadata_receipts=metadata_receipts,
        candidate_request_evidence_id=candidate.request_intent_receipt_id,
        request_intent_receipt_ids=(candidate.request_intent_receipt_id,) * route_receipts,
        request_body_sha256=_sha256_bytes(candidate.body_bytes),
        semantic_headers_sha256=_sha256_bytes(candidate.header_bytes),
        route_intent_id=candidate.claimed_route_intent_id,
        metadata_receipt_id=metadata_receipt_id,
        route_attestation_id=attestation_id,
        raw_response_evidence=(
            parsed_receipt.raw_response
            if parsed_receipt is not None
            else rejected_raw_evidence
        ),
        metadata_receipt=(
            parsed_receipt.metadata_receipt if parsed_receipt is not None else None
        ),
        route_attestation=(
            parsed_receipt.route_attestation if parsed_receipt is not None else None
        ),
        result_matches_expectation=matches,
    )


def _rejected(
    case: OpenRouterRouteControlCaseV1,
    candidate: _RouteCandidateV1,
    guard: OpenRouterRouteControlGuardId,
    failure: OpenRouterRouteControlFailureCode,
    *,
    invocations: int = 0,
) -> OpenRouterRouteControlCaseResultV1:
    rejected_raw_evidence = None
    if invocations and candidate.raw_response_bytes:
        try:
            raw_text = candidate.raw_response_bytes.decode("utf-8", errors="strict")
            rejected_raw_evidence = OpenRouterRawResponseEvidenceV1(
                raw_response_json=raw_text,
                raw_response_sha256=_sha256_bytes(candidate.raw_response_bytes),
                raw_response_length=len(candidate.raw_response_bytes),
            )
        except (UnicodeDecodeError, TypeError, ValueError):
            rejected_raw_evidence = None
    return _case_result(
        case,
        candidate,
        actual_outcome=OpenRouterRouteControlCaseActualOutcomeV1.REJECTED,
        actual_guard=guard,
        actual_failure=failure,
        invocations=invocations,
        rejected_raw_evidence=rejected_raw_evidence,
    )


def evaluate_openrouter_route_control_case_v1(
    case: OpenRouterRouteControlCaseV1,
    *,
    prepared_request: Optional[OpenRouterPreparedRouteRequestV1] = None,
) -> OpenRouterRouteControlCaseResultV1:
    """Evaluate one frozen case with deterministic first-guard-wins semantics."""

    require_clean_acquisition_boundary_tripwire_v0()
    if type(case) is not OpenRouterRouteControlCaseV1:
        raise ContractValidationError("case must use the exact frozen v1 type")
    try:
        validated_case = OpenRouterRouteControlCaseV1.model_validate(
            case.model_dump(mode="json")
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractValidationError("case contract integrity changed") from exc
    if validated_case != case:
        raise ContractValidationError("case contract integrity changed")
    prepared = prepared_request or prepare_openrouter_route_request_v1()
    if type(prepared) is not OpenRouterPreparedRouteRequestV1:
        raise ContractValidationError("prepared request must use the exact v1 type")
    try:
        validated_prepared = OpenRouterPreparedRouteRequestV1.model_validate(
            prepared.model_dump(mode="json")
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractValidationError("prepared request integrity changed") from exc
    if validated_prepared != prepared:
        raise ContractValidationError("prepared request integrity changed")
    candidate = _build_candidate_v1(case, prepared)
    if not candidate.construction_valid:
        return _case_result(
            case,
            candidate,
            actual_outcome=OpenRouterRouteControlCaseActualOutcomeV1.INVALID_PROBE_CONSTRUCTION,
            actual_guard=None,
            actual_failure=None,
            invocations=0,
        )

    G = OpenRouterRouteControlGuardId
    F = OpenRouterRouteControlFailureCode
    if candidate.manifest_semantic_sha256 != OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1:
        return _rejected(case, candidate, G.G01_SPECIFICATION_MANIFEST_INTEGRITY, F.SPECIFICATION_MANIFEST_MISMATCH)
    if candidate.route_control_policy_id != prepared.route_control_policy.route_control_policy_id:
        return _rejected(case, candidate, G.G02_ROUTE_POLICY_INTEGRITY, F.ROUTE_POLICY_MISMATCH)
    if "model" not in candidate.body:
        return _rejected(case, candidate, G.G03_EXACT_MODEL, F.EXACT_MODEL_MISSING)
    if candidate.body.get("model") != OPENROUTER_ROUTE_MODEL_V1:
        return _rejected(case, candidate, G.G03_EXACT_MODEL, F.EXACT_MODEL_MISMATCH)
    if "models" in candidate.body:
        return _rejected(case, candidate, G.G04_MODELS_ABSENT, F.MODELS_FIELD_PRESENT)
    provider = candidate.body.get("provider")
    if provider is None:
        return _rejected(case, candidate, G.G05_PROVIDER_OBJECT_SCHEMA, F.PROVIDER_OBJECT_MISSING)
    if not isinstance(provider, dict):
        return _rejected(case, candidate, G.G05_PROVIDER_OBJECT_SCHEMA, F.PROVIDER_SCHEMA_INVALID)
    only = provider.get("only")
    if only is None:
        return _rejected(case, candidate, G.G06_EXACT_SINGLETON_ENDPOINT, F.ENDPOINT_RESTRICTION_MISSING)
    if isinstance(only, list) and len(only) > 1 and len(set(map(str, only))) == 1:
        return _rejected(case, candidate, G.G06_EXACT_SINGLETON_ENDPOINT, F.ENDPOINT_SELECTOR_DUPLICATED)
    if not isinstance(only, list) or len(only) != 1:
        return _rejected(case, candidate, G.G06_EXACT_SINGLETON_ENDPOINT, F.ENDPOINT_SELECTOR_NOT_SINGLETON)
    if only[0] == "openai":
        return _rejected(case, candidate, G.G06_EXACT_SINGLETON_ENDPOINT, F.BASE_PROVIDER_SELECTOR_FORBIDDEN)
    if isinstance(only[0], str) and "*" in only[0]:
        return _rejected(case, candidate, G.G06_EXACT_SINGLETON_ENDPOINT, F.ENDPOINT_SELECTOR_WILDCARD_FORBIDDEN)
    if only != [OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1]:
        return _rejected(case, candidate, G.G06_EXACT_SINGLETON_ENDPOINT, F.ENDPOINT_SELECTOR_MISMATCH)
    order = provider.get("order")
    if order is None:
        return _rejected(case, candidate, G.G07_PROVIDER_ORDER_EXACT, F.PROVIDER_ORDER_MISSING)
    if not isinstance(order, list) or len(order) != 1:
        return _rejected(case, candidate, G.G07_PROVIDER_ORDER_EXACT, F.PROVIDER_ORDER_NOT_SINGLETON)
    if order != only:
        return _rejected(case, candidate, G.G07_PROVIDER_ORDER_EXACT, F.PROVIDER_ORDER_MISMATCH)
    if "allow_fallbacks" not in provider:
        return _rejected(case, candidate, G.G08_PROVIDER_FALLBACK_FALSE, F.PROVIDER_FALLBACK_POLICY_MISSING)
    if provider.get("allow_fallbacks") is not False:
        return _rejected(case, candidate, G.G08_PROVIDER_FALLBACK_FALSE, F.PROVIDER_FALLBACK_ENABLED)
    if "require_parameters" not in provider:
        return _rejected(case, candidate, G.G09_REQUIRE_PARAMETERS_TRUE, F.REQUIRE_PARAMETERS_MISSING)
    if provider.get("require_parameters") is not True:
        return _rejected(case, candidate, G.G09_REQUIRE_PARAMETERS_TRUE, F.REQUIRE_PARAMETERS_FALSE)
    if "max_price" in provider:
        return _rejected(case, candidate, G.G10_MAX_PRICE_ABSENT, F.UNRESOLVED_SPEC_FIELD_FORBIDDEN)
    if candidate.body.get("stream") is not False:
        return _rejected(case, candidate, G.G11_STREAM_FALSE, F.STREAM_NOT_DISABLED)
    if candidate.body.get("tools") != [] or "tool_choice" in candidate.body:
        return _rejected(case, candidate, G.G12_TOOLS_DISABLED, F.TOOLS_NOT_DISABLED)
    if OPENROUTER_METADATA_HEADER_NAME_V1 not in candidate.headers:
        return _rejected(case, candidate, G.G13_METADATA_HEADER, F.METADATA_HEADER_MISSING)
    if candidate.headers.get(OPENROUTER_METADATA_HEADER_NAME_V1) != OPENROUTER_METADATA_HEADER_VALUE_V1:
        return _rejected(case, candidate, G.G13_METADATA_HEADER, F.METADATA_HEADER_MALFORMED)
    if OPENROUTER_CACHE_HEADER_NAME_V1 not in candidate.headers:
        return _rejected(case, candidate, G.G14_CACHE_HEADER, F.CACHE_HEADER_MISSING)
    if candidate.headers.get(OPENROUTER_CACHE_HEADER_NAME_V1) != OPENROUTER_CACHE_HEADER_VALUE_V1:
        return _rejected(case, candidate, G.G14_CACHE_HEADER, F.CACHE_NOT_DISABLED)
    if not candidate.seal_integrity:
        return _rejected(case, candidate, G.G15_CANONICAL_BYTES, F.PREPARED_REQUEST_MUTATED)
    try:
        parsed_body = json.loads(candidate.body_bytes)
        parsed_headers = json.loads(candidate.header_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _rejected(case, candidate, G.G15_CANONICAL_BYTES, F.NONCANONICAL_BODY)
    if canonical_json(parsed_body).encode("utf-8") != candidate.body_bytes:
        return _rejected(case, candidate, G.G15_CANONICAL_BYTES, F.NONCANONICAL_BODY)
    if canonical_json(parsed_headers).encode("utf-8") != candidate.header_bytes:
        return _rejected(case, candidate, G.G15_CANONICAL_BYTES, F.NONCANONICAL_HEADERS)
    evidence_exact = all(
        (
            candidate.claimed_body_sha256 == _sha256_bytes(candidate.body_bytes),
            candidate.claimed_body_length == len(candidate.body_bytes),
            candidate.claimed_header_sha256 == _sha256_bytes(candidate.header_bytes),
            candidate.claimed_header_length == len(candidate.header_bytes),
            candidate.claimed_route_intent_id == _route_intent_id(
                prepared, candidate.body_bytes, candidate.header_bytes
            ),
        )
    )
    if not evidence_exact:
        return _rejected(case, candidate, G.G15_CANONICAL_BYTES, F.REQUEST_DIGEST_OR_LENGTH_MISMATCH)
    if _contains_forbidden_entropy(candidate.body):
        return _rejected(case, candidate, G.G16_ENTROPY_FIREWALL, F.FORBIDDEN_BODY_ENTROPY)
    if _contains_forbidden_entropy(candidate.headers):
        return _rejected(case, candidate, G.G16_ENTROPY_FIREWALL, F.FORBIDDEN_HEADER_ENTROPY)
    if canonical_json(candidate.body) != FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1:
        return _rejected(case, candidate, G.G16_ENTROPY_FIREWALL, F.FORBIDDEN_BODY_ENTROPY)
    if canonical_json(candidate.headers) != FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1:
        return _rejected(case, candidate, G.G16_ENTROPY_FIREWALL, F.FORBIDDEN_HEADER_ENTROPY)

    if case.kind is OpenRouterRouteControlCaseKind.POSITIVE_REQUEST:
        if case.case_id == "orroutev1-sr03-sibling-intent-replay":
            sibling = prepare_openrouter_route_request_v1()
            sibling_exact = (
                sibling.body_bytes == prepared.body_bytes
                and sibling.header_bytes == prepared.header_bytes
                and sibling.route_intent_id == prepared.route_intent_id
                and sibling.request_intent_receipt == prepared.request_intent_receipt
            )
            if not sibling_exact:
                return _rejected(case, candidate, G.G15_CANONICAL_BYTES, F.REQUEST_DIGEST_OR_LENGTH_MISMATCH)
        return _case_result(
            case,
            candidate,
            actual_outcome=OpenRouterRouteControlCaseActualOutcomeV1.ACCEPTED,
            actual_guard=None,
            actual_failure=None,
            invocations=0,
            route_receipts=case.expected_complete_route_intent_receipts,
        )

    transport = _OneShotCannedRouteTransportV1(
        registered_body=prepared.body_bytes,
        registered_headers=prepared.header_bytes,
        raw_response=candidate.raw_response_bytes,
        registered=candidate.transport_registered,
        completed=candidate.transport_completed,
    )
    if not transport.registered:
        return _rejected(case, candidate, G.G17_CANNED_REGISTRATION, F.CANNED_TRANSPORT_UNREGISTERED)
    raw_response = transport.send(candidate.body_bytes, candidate.header_bytes)
    if not transport.completed:
        return _rejected(case, candidate, G.G18_TRANSPORT_COMPLETION, F.TRANSPORT_NOT_COMPLETE, invocations=transport.invocations)
    try:
        parsed_receipt = parse_openrouter_router_metadata_v1(
            raw_response,
            prepared,
            transport_completed=transport.completed,
        )
    except OpenRouterRouteControlParserError as exc:
        return _rejected(
            case,
            candidate,
            OpenRouterRouteControlGuardId(exc.guard_id.value),
            OpenRouterRouteControlFailureCode(exc.failure_code.value),
            invocations=transport.invocations,
        )
    return _case_result(
        case,
        candidate,
        actual_outcome=OpenRouterRouteControlCaseActualOutcomeV1.ACCEPTED,
        actual_guard=None,
        actual_failure=None,
        invocations=transport.invocations,
        route_receipts=case.expected_complete_route_intent_receipts,
        metadata_receipts=case.expected_complete_metadata_receipts,
        parsed_receipt=parsed_receipt,
    )


class OpenRouterRouteControlMutationScopeV1(str, Enum):
    SOURCE = "SOURCE"
    SIBLING = "SIBLING"
    PRODUCTION = "PRODUCTION"


FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1: Tuple[
    Tuple[OpenRouterRouteControlMutationScopeV1, Tuple[str, ...]], ...
] = (
    (
        OpenRouterRouteControlMutationScopeV1.SOURCE,
        (
            "backend/dialogues/socrates_zero/openrouter_route_controls_contracts.py",
            "backend/dialogues/socrates_zero/openrouter_route_controls_renderer.py",
            "backend/dialogues/socrates_zero/openrouter_route_controls_parser.py",
            "backend/dialogues/socrates_zero/openrouter_route_controls_cases.py",
            "backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_contracts.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_renderer.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_parser.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_cases.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_route_controls_v1_evaluation.py",
            "docs/SOCRATES_ZERO_OPENROUTER_ROUTE_CONTROLS_V1.md",
            "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/README.md",
            "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/MEMORY.md",
            "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/PLAN.md",
            "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/PRESENT.md",
            "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/artifacts/README.md",
        ),
    ),
    (
        OpenRouterRouteControlMutationScopeV1.SIBLING,
        (
            "backend/dialogues/socrates_zero/__init__.py",
            "backend/dialogues/socrates_zero/contracts.py",
            "backend/dialogues/socrates_zero/acquisition.py",
            "backend/dialogues/socrates_zero/acquisition_contracts.py",
            "backend/dialogues/socrates_zero/acquisition_cases.py",
            "backend/dialogues/socrates_zero/acquisition_evaluation.py",
            "backend/dialogues/socrates_zero/acquisition_isolation_evidence.py",
            "backend/dialogues/socrates_zero/acquisition_tripwires.py",
            "backend/dialogues/socrates_zero/baseline.py",
            "backend/dialogues/socrates_zero/constitution.py",
            "backend/dialogues/socrates_zero/evaluation.py",
            "backend/dialogues/socrates_zero/evaluation_cases.py",
            "backend/dialogues/socrates_zero/evaluation_harness.py",
            "backend/dialogues/socrates_zero/policy.py",
            "backend/dialogues/socrates_zero/puct.py",
            "backend/dialogues/socrates_zero/strategy.py",
            "backend/dialogues/socrates_zero/value.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_contracts.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_renderer.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_adapter.py",
            OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
            "backend/dialogues/socrates_zero/openrouter_acquisition_evaluation.py",
            OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1,
            "tests_dialogues/conftest.py",
            "tests_dialogues/test_socrates_zero_acquisition_boundaries.py",
            "tests_dialogues/test_socrates_zero_acquisition_cases.py",
            "tests_dialogues/test_socrates_zero_acquisition_contracts.py",
            "tests_dialogues/test_socrates_zero_acquisition_evaluation.py",
            "tests_dialogues/test_socrates_zero_acquisition_isolation_evidence.py",
            "tests_dialogues/test_socrates_zero_acquisition_runtime.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_adapter.py",
            OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_contracts.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_evaluation.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_renderer.py",
        ),
    ),
    (
        OpenRouterRouteControlMutationScopeV1.PRODUCTION,
        (
            "backend/dialogues/openrouter_provider.py",
            "backend/dialogues/provider_registry.py",
            "backend/dialogues/agent.py",
            "backend/dialogues/ced.py",
            "backend/dialogues/ced_canonical_successor.py",
            "backend/dialogues/ced_search_observability_v1.py",
            "backend/dialogues/ced_search_projection.py",
            "backend/dialogues/ced_search_projection_v1.py",
            "backend/dialogues/ced_search_value_v1.py",
            "backend/dialogues/ced_search_value_v1_artifact.py",
            "backend/dialogues/ced_search_value_v1_bestofn.py",
            "backend/dialogues/ced_search_value_v1_bestofn_cases.py",
            "backend/dialogues/ced_search_value_v1_contracts.py",
            "backend/dialogues/ced_search_value_v1_evaluation.py",
            "backend/dialogues/ced_search_value_v1_evaluation_cases.py",
            "backend/dialogues/ced_canonical_successor_cases.py",
            "backend/dialogues/ced_canonical_successor_cases_v1.py",
            "backend/dialogues/ced_canonical_successor_cases_v2.py",
            "backend/dialogues/ced_canonical_successor_contracts.py",
            "backend/dialogues/ced_canonical_successor_evaluation.py",
            "backend/dialogues/ced_canonical_successor_evaluation_v2.py",
            "backend/dialogues/ced_canonical_successor_frozen_core_v2.py",
            "backend/dialogues/ced_canonical_successor_manifest.py",
            "backend/dialogues/ced_canonical_successor_recording.py",
            "backend/dialogues/ced_canonical_successor_recording_contracts.py",
            "backend/dialogues/ced_canonical_successor_recording_fixtures.py",
            "backend/dialogues/hybrid_authority.py",
            "backend/dialogues/hybrid_epistemic.py",
            "backend/dialogues/hybrid_shadow.py",
            "backend/dialogues/hybrid_support.py",
            "backend/dialogues/live_providers.py",
            "backend/dialogues/model_identity.py",
            "backend/dialogues/models.py",
            "backend/dialogues/providers.py",
            "backend/dialogues/reasoning_prompts.py",
            "backend/dialogues/role_assignment.py",
            "backend/dialogues/socratic.py",
            "backend/dialogues/task_checker.py",
            "backend/dialogues/topic.py",
        ),
    ),
)
FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1 = stable_contract_id(
    "szorroutepathinventoryv1",
    tuple(
        {"scope": scope.value, "relative_path": relative_path}
        for scope, paths in FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
        for relative_path in paths
    ),
)

# The sealed route-control experiment measured an inventory that still carried
# two raw predecessor paths.  That generation is history and is never
# re-derived from current code: it is pinned here as frozen literals so the
# sealed artifact keeps validating byte-for-byte while the current inventory
# above is free to evolve.
FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1 = (
    "szorroutepathinventoryv1_"
    "0ec9a8417d7cb91bb0e17fc0b402577032cf207ace89cddc32276390ec661e33"
)
FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1 = (
    "szorroutesnapshotv1_"
    "9ee38a257c992778102ca9b176e5ea99831aaae70ffbf4b016f2a3dbb7c4417b"
)
FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_ROW_COUNT_V1 = 90


_HISTORICAL_ARTIFACT_LOCKS_V1: Tuple[Tuple[str, str, str], ...] = (
    ("phase5-search-kernel", "docs/branches/feature-socrates-zero-search-v0/artifacts/socrateszero_search_kernel_benchmark_v0.json", "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"),
    ("phase7-value-primary", "docs/branches/feature-socrates-zero-heuristic-value-v1/artifacts/socrateszero_value_v1_primary_v0.json", "d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca"),
    ("phase7-bestofn", "docs/branches/feature-socrates-zero-heuristic-value-v1/artifacts/socrateszero_value_v1_bestofn_v0.json", "86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637"),
    ("phase8-v1-falsified", "docs/branches/feature-socrates-zero-canonical-successor-env-v0/artifacts/socrateszero_canonical_successor_parity_v1.json", "00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea"),
    ("phase8-v2", "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/artifacts/socrateszero_canonical_successor_parity_v2.json", "8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc"),
    ("phase8-v2-replay-lock", "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/artifacts/socrateszero_canonical_successor_parity_replay_lock_v2.json", "896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224"),
    ("acquisition-artifact", "docs/branches/feature-socrates-zero-live-acquisition-contract-v0/artifacts/socrateszero_external_observation_acquisition_v0.json", "2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255"),
    ("acquisition-replay-execution", "docs/branches/feature-socrates-zero-live-acquisition-contract-v0/artifacts/socrateszero_external_observation_acquisition_replay_execution_v0.json", "7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b"),
    ("acquisition-replay-lock", "docs/branches/feature-socrates-zero-live-acquisition-contract-v0/artifacts/socrateszero_external_observation_acquisition_replay_lock_v0.json", "335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c"),
    ("openrouter-adapter-controls-v0", "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/artifacts/socrateszero_openrouter_acquisition_adapter_controls_v0.json", "0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083"),
)
FROZEN_CORE_BLOB_LOCK_ID_V2 = (
    "cedcorebloblockv2_2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957"
)


class OpenRouterScopedPathDigestV1(_FrozenEvaluationContractV1):
    scope: OpenRouterRouteControlMutationScopeV1
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class OpenRouterScopedPathSnapshotV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_SCOPED_SNAPSHOT_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_SCOPED_SNAPSHOT_SCHEMA_V1
    inventory_id: Literal[
        FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1,
        FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1,
    ] = FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1
    rows: Tuple[OpenRouterScopedPathDigestV1, ...]
    snapshot_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterScopedPathSnapshotV1":
        historical = (
            self.inventory_id
            == FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1
        )
        if historical:
            if (
                len(self.rows)
                != FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_ROW_COUNT_V1
            ):
                raise ContractValidationError(
                    "historical scoped snapshot row count changed"
                )
        else:
            expected_membership = tuple(
                (scope, relative_path)
                for scope, paths in FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
                for relative_path in paths
            )
            observed_membership = tuple(
                (row.scope, row.relative_path) for row in self.rows
            )
            if observed_membership != expected_membership:
                raise ContractValidationError(
                    "scoped snapshot membership or order changed"
                )
        expected = stable_contract_id(
            "szorroutesnapshotv1",
            self.model_dump(mode="json", exclude={"snapshot_id"}),
        )
        if historical and expected != (
            FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1
        ):
            raise ContractValidationError(
                "historical scoped snapshot identity changed"
            )
        if self.snapshot_id not in (None, expected):
            raise ContractValidationError("scoped snapshot ID mismatch")
        object.__setattr__(self, "snapshot_id", expected)
        return self


class OpenRouterScopedPathMutationV1(_FrozenEvaluationContractV1):
    scope: OpenRouterRouteControlMutationScopeV1
    relative_path: str
    before_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def changed(self) -> "OpenRouterScopedPathMutationV1":
        if self.before_sha256 == self.after_sha256:
            raise ContractValidationError("scoped mutation digests must differ")
        return self


class OpenRouterScopedMutationEvidenceV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_MUTATION_EVIDENCE_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_MUTATION_EVIDENCE_SCHEMA_V1
    before_snapshot_id: str
    after_snapshot_id: str
    source_mutations: int = Field(ge=0)
    sibling_mutations: int = Field(ge=0)
    production_mutations: int = Field(ge=0)
    changed_paths: Tuple[str, ...] = ()
    mutations: Tuple[OpenRouterScopedPathMutationV1, ...] = ()
    evidence_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterScopedMutationEvidenceV1":
        expected_membership = tuple(
            (scope, relative_path)
            for scope, paths in FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
            for relative_path in paths
        )
        rank = {identity: index for index, identity in enumerate(expected_membership)}
        mutation_identities = tuple(
            (mutation.scope, mutation.relative_path) for mutation in self.mutations
        )
        if (
            len(set(mutation_identities)) != len(mutation_identities)
            or any(identity not in rank for identity in mutation_identities)
            or tuple(sorted(mutation_identities, key=rank.__getitem__))
            != mutation_identities
        ):
            raise ContractValidationError("scoped mutation membership changed")
        derived_paths = tuple(mutation.relative_path for mutation in self.mutations)
        derived_counts = {
            scope: sum(mutation.scope is scope for mutation in self.mutations)
            for scope in OpenRouterRouteControlMutationScopeV1
        }
        if (
            self.changed_paths != derived_paths
            or self.source_mutations
            != derived_counts[OpenRouterRouteControlMutationScopeV1.SOURCE]
            or self.sibling_mutations
            != derived_counts[OpenRouterRouteControlMutationScopeV1.SIBLING]
            or self.production_mutations
            != derived_counts[OpenRouterRouteControlMutationScopeV1.PRODUCTION]
        ):
            raise ContractValidationError("mutation counts and paths disagree")
        expected = stable_contract_id(
            "szorroutemutationevidencev1",
            self.model_dump(mode="json", exclude={"evidence_id"}),
        )
        if self.evidence_id not in (None, expected):
            raise ContractValidationError("mutation evidence ID mismatch")
        object.__setattr__(self, "evidence_id", expected)
        return self


class OpenRouterHistoricalHashEvidenceV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_HISTORICAL_HASH_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_HISTORICAL_HASH_SCHEMA_V1
    lock_name: str
    relative_path: str
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    matches: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_match(self) -> "OpenRouterHistoricalHashEvidenceV1":
        if self.matches != (self.expected_sha256 == self.observed_sha256):
            raise ContractValidationError("historical hash match flag is not derived")
        return self


class OpenRouterBoundaryCountersV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_BOUNDARY_COUNTERS_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_BOUNDARY_COUNTERS_SCHEMA_V1
    documentation_fetches: Literal[0] = 0
    dns_attempts: Literal[0] = 0
    socket_attempts: Literal[0] = 0
    http_attempts: Literal[0] = 0
    external_network_attempts: Literal[0] = 0
    credential_access_attempts: Literal[0] = 0
    live_provider_calls: Literal[0] = 0
    provider_sdk_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    tool_calls: Literal[0] = 0
    canonical_application_calls: Literal[0] = 0


class OpenRouterRouteControlMetricsV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_METRICS_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_METRICS_SCHEMA_V1
    metrics_id: Literal[
        OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1
    cases_total: int = Field(ge=0)
    positive_request_cases: int = Field(ge=0)
    positive_response_cases: int = Field(ge=0)
    positive_cases_passed: int = Field(ge=0)
    complete_route_intent_receipts: int = Field(ge=0)
    complete_metadata_receipts: int = Field(ge=0)
    orthogonal_probes: int = Field(ge=0)
    orthogonal_exact_primary_failures: int = Field(ge=0)
    precedence_probes: int = Field(ge=0)
    precedence_exact_primary_failures: int = Field(ge=0)
    invalid_probe_constructions: int = Field(ge=0)
    canned_transport_invocations: int = Field(ge=0)
    body_byte_mismatches: int = Field(ge=0)
    header_byte_mismatches: int = Field(ge=0)
    route_intent_mismatches: int = Field(ge=0)
    primary_failure_mismatches: int = Field(ge=0)
    entropy_violations: int = Field(ge=0)
    endpoint_selector_violations_accepted: int = Field(ge=0)
    fallback_intent_violations_accepted: int = Field(ge=0)
    models_array_violations_accepted: int = Field(ge=0)
    metadata_missing_violations_accepted: int = Field(ge=0)
    cache_policy_violations_accepted: int = Field(ge=0)
    multi_attempt_violations_accepted: int = Field(ge=0)
    model_substitutions_accepted: int = Field(ge=0)
    provider_substitutions_accepted: int = Field(ge=0)
    false_exact_endpoint_attestations: int = Field(ge=0)
    p17_closure_violations: int = Field(ge=0)
    p18_closure_violations: int = Field(ge=0)
    p19_closure_violations: int = Field(ge=0)
    documentation_fetches: int = Field(ge=0)
    external_network_attempts: int = Field(ge=0)
    credential_access_attempts: int = Field(ge=0)
    provider_calls: int = Field(ge=0)
    model_executions: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    ced_application_invocations: int = Field(ge=0)
    source_mutations: int = Field(ge=0)
    sibling_mutations: int = Field(ge=0)
    production_mutations: int = Field(ge=0)
    receipt_mismatches: int = Field(ge=0)
    artifact_claim_violations: int = Field(ge=0)
    historical_lock_mismatches: int = Field(ge=0)
    core_lock_mismatches: int = Field(ge=0)
    official_response_wire_mapping_violations: int = Field(ge=0)
    all_thresholds_pass: bool = Field(strict=True)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def capture_openrouter_route_control_scoped_snapshot_v1(
    root: Optional[Path] = None,
) -> OpenRouterScopedPathSnapshotV1:
    repository_root = _repository_root() if root is None else Path(root)
    rows = []
    for scope, paths in FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1:
        for relative_path in paths:
            provenance = openrouter_provenance_record_v1(
                relative_path,
                FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1,
            )
            if provenance is None:
                path = repository_root / relative_path
                if not path.is_file():
                    raise ContractValidationError(
                        f"frozen scoped path is absent: {relative_path}"
                    )
                digest = _sha256_bytes(path.read_bytes())
            else:
                digest = provenance.record_sha256
            rows.append(
                OpenRouterScopedPathDigestV1(
                    scope=scope,
                    relative_path=relative_path,
                    sha256=digest,
                )
            )
    return OpenRouterScopedPathSnapshotV1(rows=tuple(rows))


def compare_openrouter_route_control_scoped_snapshots_v1(
    before: OpenRouterScopedPathSnapshotV1,
    after: OpenRouterScopedPathSnapshotV1,
) -> OpenRouterScopedMutationEvidenceV1:
    before_by_path = {row.relative_path: row for row in before.rows}
    after_by_path = {row.relative_path: row for row in after.rows}
    if set(before_by_path) != set(after_by_path):
        raise ContractValidationError("scoped snapshot membership changed")
    changed = tuple(
        relative_path
        for relative_path in before_by_path
        if before_by_path[relative_path].sha256 != after_by_path[relative_path].sha256
    )
    mutation_rows = tuple(
        OpenRouterScopedPathMutationV1(
            scope=before_by_path[relative_path].scope,
            relative_path=relative_path,
            before_sha256=before_by_path[relative_path].sha256,
            after_sha256=after_by_path[relative_path].sha256,
        )
        for relative_path in changed
    )
    counts = {
        scope: sum(before_by_path[path].scope is scope for path in changed)
        for scope in OpenRouterRouteControlMutationScopeV1
    }
    return OpenRouterScopedMutationEvidenceV1(
        before_snapshot_id=before.snapshot_id or "",
        after_snapshot_id=after.snapshot_id or "",
        source_mutations=counts[OpenRouterRouteControlMutationScopeV1.SOURCE],
        sibling_mutations=counts[OpenRouterRouteControlMutationScopeV1.SIBLING],
        production_mutations=counts[OpenRouterRouteControlMutationScopeV1.PRODUCTION],
        changed_paths=changed,
        mutations=mutation_rows,
    )


def verify_openrouter_route_control_historical_hashes_v1(
    root: Optional[Path] = None,
) -> Tuple[OpenRouterHistoricalHashEvidenceV1, ...]:
    repository_root = _repository_root() if root is None else Path(root)
    evidence = []
    for lock_name, relative_path, expected in _HISTORICAL_ARTIFACT_LOCKS_V1:
        path = repository_root / relative_path
        if not path.is_file():
            raise ContractValidationError(f"historical artifact absent: {relative_path}")
        observed = _sha256_bytes(path.read_bytes())
        evidence.append(
            OpenRouterHistoricalHashEvidenceV1(
                lock_name=lock_name,
                relative_path=relative_path,
                expected_sha256=expected,
                observed_sha256=observed,
                matches=observed == expected,
            )
        )
    return tuple(evidence)


def _verify_core_lock_v1(root: Path) -> bool:
    path = root / _HISTORICAL_ARTIFACT_LOCKS_V1[4][1]
    try:
        artifact = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return (
        artifact.get("core_lock_id") == FROZEN_CORE_BLOB_LOCK_ID_V2
        and isinstance(artifact.get("core_lock"), dict)
        and artifact["core_lock"].get("lock_id") == FROZEN_CORE_BLOB_LOCK_ID_V2
    )


def _boundary_counters_v1() -> OpenRouterBoundaryCountersV1:
    snapshot = require_clean_acquisition_boundary_tripwire_v0()
    return OpenRouterBoundaryCountersV1(
        external_network_attempts=snapshot.external_network_attempts,
        credential_access_attempts=snapshot.credential_access_attempts,
        live_provider_calls=snapshot.live_provider_calls,
        provider_sdk_calls=snapshot.provider_sdk_calls,
        model_executions=snapshot.model_executions,
        tool_calls=snapshot.tool_calls,
        canonical_application_calls=snapshot.canonical_application_calls,
    )


def _accepted_violation_count(
    results: Sequence[OpenRouterRouteControlCaseResultV1],
    failure_codes: Iterable[OpenRouterRouteControlFailureCode],
) -> int:
    codes = frozenset(failure_codes)
    return sum(
        result.expected_failure_code in codes
        and result.actual_outcome is OpenRouterRouteControlCaseActualOutcomeV1.ACCEPTED
        for result in results
    )


def _build_metrics_v1(
    results: Tuple[OpenRouterRouteControlCaseResultV1, ...],
    boundary: OpenRouterBoundaryCountersV1,
    mutations: OpenRouterScopedMutationEvidenceV1,
    historical: Tuple[OpenRouterHistoricalHashEvidenceV1, ...],
    wire_mapping_assessment: OpenRouterOfficialResponseWireMappingAssessmentV1,
    *,
    core_lock_matches: bool,
    expected_route_intent_id: str,
) -> OpenRouterRouteControlMetricsV1:
    K = OpenRouterRouteControlCaseKind
    F = OpenRouterRouteControlFailureCode
    positives = tuple(r for r in results if r.kind in {K.POSITIVE_REQUEST, K.POSITIVE_RESPONSE})
    orthogonal = tuple(r for r in results if r.kind in {K.ORTHOGONAL_REQUEST, K.ORTHOGONAL_RESPONSE})
    precedence = tuple(r for r in results if r.kind is K.PRECEDENCE)
    values = dict(
        cases_total=len(results),
        positive_request_cases=sum(r.kind is K.POSITIVE_REQUEST for r in results),
        positive_response_cases=sum(r.kind is K.POSITIVE_RESPONSE for r in results),
        positive_cases_passed=sum(r.result_matches_expectation for r in positives),
        complete_route_intent_receipts=sum(r.complete_route_intent_receipts for r in results),
        complete_metadata_receipts=sum(r.complete_metadata_receipts for r in results),
        orthogonal_probes=len(orthogonal),
        orthogonal_exact_primary_failures=sum(r.result_matches_expectation for r in orthogonal),
        precedence_probes=len(precedence),
        precedence_exact_primary_failures=sum(r.result_matches_expectation for r in precedence),
        invalid_probe_constructions=sum(not r.construction_valid for r in results),
        canned_transport_invocations=sum(r.canned_transport_invocations for r in results),
        body_byte_mismatches=sum(
            r.request_body_sha256
            != _sha256_bytes(FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1.encode("utf-8"))
            for r in positives
        ),
        header_byte_mismatches=sum(
            r.semantic_headers_sha256
            != _sha256_bytes(FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1.encode("utf-8"))
            for r in positives
        ),
        route_intent_mismatches=sum(
            r.route_intent_id != expected_route_intent_id
            for r in positives
        ),
        primary_failure_mismatches=sum(not r.result_matches_expectation for r in results),
        entropy_violations=_accepted_violation_count(
            results,
            {F.FORBIDDEN_BODY_ENTROPY, F.FORBIDDEN_HEADER_ENTROPY},
        ),
        endpoint_selector_violations_accepted=_accepted_violation_count(results, {F.ENDPOINT_RESTRICTION_MISSING, F.ENDPOINT_SELECTOR_NOT_SINGLETON, F.ENDPOINT_SELECTOR_DUPLICATED, F.ENDPOINT_SELECTOR_MISMATCH, F.ENDPOINT_SELECTOR_WILDCARD_FORBIDDEN, F.BASE_PROVIDER_SELECTOR_FORBIDDEN}),
        fallback_intent_violations_accepted=_accepted_violation_count(results, {F.PROVIDER_FALLBACK_ENABLED, F.PROVIDER_FALLBACK_POLICY_MISSING, F.FALLBACK_INDICATOR_PRESENT}),
        models_array_violations_accepted=_accepted_violation_count(results, {F.MODELS_FIELD_PRESENT}),
        metadata_missing_violations_accepted=_accepted_violation_count(results, {F.ROUTER_METADATA_MISSING}),
        cache_policy_violations_accepted=_accepted_violation_count(results, {F.CACHE_HEADER_MISSING, F.CACHE_NOT_DISABLED, F.CACHE_AFFECTED_METADATA_UNAVAILABLE, F.CACHE_HIT_RESPONSE_REJECTED}),
        multi_attempt_violations_accepted=_accepted_violation_count(results, {F.MULTI_ATTEMPT_ROUTING_OBSERVED, F.MULTIPLE_ATTEMPTS_REPORTED}),
        model_substitutions_accepted=_accepted_violation_count(results, {F.ACTUAL_MODEL_SUBSTITUTION}),
        provider_substitutions_accepted=_accepted_violation_count(results, {F.PROVIDER_SUBSTITUTION}),
        false_exact_endpoint_attestations=sum(r.response_exact_endpoint_attestation != "NOT_ESTABLISHED" for r in results),
        p17_closure_violations=sum(r.p17_input_token_bound != "NOT_ESTABLISHED" for r in results),
        p18_closure_violations=sum(r.p18_pricing_record != "NOT_ESTABLISHED" for r in results),
        p19_closure_violations=sum(r.p19_cost_bound != "NOT_ESTABLISHED" for r in results),
        documentation_fetches=boundary.documentation_fetches,
        external_network_attempts=boundary.external_network_attempts,
        credential_access_attempts=boundary.credential_access_attempts,
        provider_calls=boundary.live_provider_calls + boundary.provider_sdk_calls,
        model_executions=boundary.model_executions,
        tool_calls=boundary.tool_calls,
        ced_application_invocations=boundary.canonical_application_calls,
        source_mutations=mutations.source_mutations,
        sibling_mutations=mutations.sibling_mutations,
        production_mutations=mutations.production_mutations,
        receipt_mismatches=_accepted_violation_count(results, {F.RECEIPT_MISMATCH}),
        artifact_claim_violations=sum(
            (
                r.response_exact_endpoint_attestation != "NOT_ESTABLISHED"
                or r.p17_input_token_bound != "NOT_ESTABLISHED"
                or r.p18_pricing_record != "NOT_ESTABLISHED"
                or r.p19_cost_bound != "NOT_ESTABLISHED"
                or r.live_server_enforcement != "NOT_PROVEN"
                or r.real_provider_execution is not False
            )
            for r in results
        ),
        historical_lock_mismatches=sum(not item.matches for item in historical),
        core_lock_mismatches=int(not core_lock_matches),
        official_response_wire_mapping_violations=(
            official_response_wire_mapping_violation_count_v1(
                wire_mapping_assessment
            )
        ),
    )
    thresholds = FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1
    passes = (
        values["cases_total"] == thresholds.cases_total
        and values["positive_request_cases"] == thresholds.positive_request_cases_total
        and values["positive_response_cases"] == thresholds.positive_response_cases_total
        and values["positive_cases_passed"] == thresholds.positive_cases_total
        and values["complete_route_intent_receipts"] == thresholds.required_complete_route_intent_receipts
        and values["complete_metadata_receipts"] == thresholds.required_complete_metadata_receipts
        and values["orthogonal_probes"] == thresholds.orthogonal_probes_total
        and values["orthogonal_exact_primary_failures"] == thresholds.required_orthogonal_exact_primary_results
        and values["precedence_probes"] == thresholds.precedence_probes_total
        and values["precedence_exact_primary_failures"] == thresholds.required_precedence_exact_primary_results
        and values["canned_transport_invocations"] == thresholds.required_canned_transport_invocations
        and values["official_response_wire_mapping_violations"]
        <= thresholds.maximum_official_response_wire_mapping_violations
        and all(value == 0 for key, value in values.items() if key not in {
            "cases_total", "positive_request_cases", "positive_response_cases",
            "positive_cases_passed", "complete_route_intent_receipts",
            "complete_metadata_receipts", "orthogonal_probes",
            "orthogonal_exact_primary_failures", "precedence_probes",
            "precedence_exact_primary_failures", "canned_transport_invocations",
            "official_response_wire_mapping_violations",
        })
    )
    return OpenRouterRouteControlMetricsV1(**values, all_thresholds_pass=passes)


def _validate_frozen_evidence_record_links_v1(
    frozen_evidence_record_ids: Tuple[str, ...],
    specification_binding: OpenRouterSpecificationManifestBindingV1,
    request_intent_receipt: OpenRouterRequestIntentReceiptV1,
) -> None:
    if (
        frozen_evidence_record_ids != OPENROUTER_RELEVANT_FACT_IDS_V1
        or frozen_evidence_record_ids
        != tuple(
            item.evidence_id
            for item in specification_binding.relevant_fact_bindings
        )
        or frozen_evidence_record_ids
        != request_intent_receipt.frozen_evidence_record_ids
    ):
        raise ContractValidationError("artifact frozen evidence links changed")


class OpenRouterRouteControlArtifactV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_ARTIFACT_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_ARTIFACT_SCHEMA_V1
    artifact_id: Optional[str] = None
    evaluation_schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_EVALUATION_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_EVALUATION_SCHEMA_V1
    route_controls_schema_version: Literal[
        OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION
    ] = OPENROUTER_ROUTE_CONTROLS_SCHEMA_VERSION
    renderer_version: Literal[
        OPENROUTER_ROUTE_RENDERER_VERSION
    ] = OPENROUTER_ROUTE_RENDERER_VERSION
    metadata_parser_version: Literal[
        ROUTER_METADATA_PARSER_SCHEMA_VERSION
    ] = ROUTER_METADATA_PARSER_SCHEMA_VERSION
    normalized_canned_response_schema_version: Literal[
        NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION
    ] = NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION
    normalized_canned_schema_is_official_wire_schema: Literal[False] = False
    official_response_wire_mapping_status: Literal[
        OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1
    ] = OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1
    official_response_wire_mapping_assessment: (
        OpenRouterOfficialResponseWireMappingAssessmentV1
    )
    specification_manifest_path: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    specification_manifest_id: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    specification_manifest_semantic_sha256: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    specification_manifest_file_sha256: Literal[
        OPENROUTER_SPECIFICATION_MANIFEST_FILE_SHA256_V1
    ] = OPENROUTER_SPECIFICATION_MANIFEST_FILE_SHA256_V1
    specification_binding: OpenRouterSpecificationManifestBindingV1
    source_evidence_records: Literal[16] = 16
    normalized_fact_records: Literal[13] = 13
    frozen_evidence_record_ids: Tuple[str, ...] = OPENROUTER_RELEVANT_FACT_IDS_V1
    route_control_policy_id: str
    route_intent_contract_id: str
    header_policy_id: str
    cache_policy_id: str
    metadata_policy_id: str
    route_policy_receipt: OpenRouterRouteControlPolicyV1
    header_policy_receipt: OpenRouterRouteHeaderPolicyV1
    cache_policy_receipt: OpenRouterCachePolicyV1
    metadata_policy_receipt: OpenRouterMetadataPolicyV1
    exact_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    models_field_status: Literal["ABSENT"] = "ABSENT"
    exact_endpoint_selector: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    provider_only: Tuple[
        Literal[OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1], ...
    ] = (OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,)
    provider_order: Tuple[
        Literal[OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1], ...
    ] = (OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,)
    provider_allow_fallbacks: Literal[False] = False
    provider_require_parameters: Literal[True] = True
    max_price_status: Literal["DEFERRED_NOT_RENDERED"] = "DEFERRED_NOT_RENDERED"
    stream: Literal[False] = False
    tools_status: Literal["DISABLED"] = "DISABLED"
    metadata_header: Literal["X-OpenRouter-Metadata: enabled"] = (
        "X-OpenRouter-Metadata: enabled"
    )
    cache_header: Literal["X-OpenRouter-Cache: false"] = (
        "X-OpenRouter-Cache: false"
    )
    canonical_body_json: str
    canonical_semantic_headers_json: str
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(ge=1)
    semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_headers_length: int = Field(ge=1)
    route_intent_id: str
    request_intent_receipt: OpenRouterRequestIntentReceiptV1
    case_set_id: Literal[
        OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1
    harness_id: Literal[
        OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_HARNESS_ID_V1
    metrics_id: Literal[
        OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_METRICS_ID_V1
    thresholds_id: Literal[
        OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1
    ] = OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1
    validation_order_id: str
    precedence_model: Literal[
        FIRST_ROUTE_CONTROL_GUARD_WINS_V1
    ] = FIRST_ROUTE_CONTROL_GUARD_WINS_V1
    case_set: OpenRouterRouteControlCaseSetV1
    thresholds: OpenRouterRouteControlThresholdsV1
    case_results: Tuple[OpenRouterRouteControlCaseResultV1, ...]
    metrics: OpenRouterRouteControlMetricsV1
    boundary_counters: OpenRouterBoundaryCountersV1
    scoped_before_snapshot: OpenRouterScopedPathSnapshotV1
    scoped_after_snapshot: OpenRouterScopedPathSnapshotV1
    scoped_mutation_evidence: OpenRouterScopedMutationEvidenceV1
    historical_hashes: Tuple[OpenRouterHistoricalHashEvidenceV1, ...]
    core_lock_id: Literal[FROZEN_CORE_BLOB_LOCK_ID_V2] = FROZEN_CORE_BLOB_LOCK_ID_V2
    predecessor_artifact_id: Literal[
        "szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f"
    ] = "szoracqevaluation_43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f"
    predecessor_artifact_sha256: Literal[
        "0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083"
    ] = "0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083"
    predecessor_status: Literal["FALSIFIED"] = "FALSIFIED"
    predecessor_replay: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    request_intent_status: Literal[
        "PROVEN_OFFLINE", "NOT_ESTABLISHED"
    ]
    canned_response_parser_status: Literal[
        "PROVEN_OFFLINE_LOCAL_NORMALIZED_CONTRACT_ONLY", "NOT_ESTABLISHED"
    ]
    response_provider_attestation: Literal[
        "LOCAL_NORMALIZED_PARTIAL_BROAD_PROVIDER_ONLY", "NOT_ESTABLISHED"
    ]
    exact_endpoint_response_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    live_server_enforcement: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    live_no_fallback_proof: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"
    actual_openrouter_availability: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    real_provider_execution: Literal[False] = False
    production_authority: Literal["none"] = "none"
    claim_firewall: OpenRouterRouteControlArtifactClaimFirewallV1 = (
        FROZEN_OPENROUTER_ROUTE_CONTROL_ARTIFACT_CLAIM_FIREWALL_V1
    )
    hypothesis_status: OpenRouterRouteControlHypothesisStatusV1

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterRouteControlArtifactV1":
        binding = self.specification_binding
        assessment = self.official_response_wire_mapping_assessment
        if (
            assessment.specification_manifest_path != self.specification_manifest_path
            or assessment.specification_manifest_id != self.specification_manifest_id
            or assessment.specification_manifest_semantic_sha256
            != self.specification_manifest_semantic_sha256
            or assessment.specification_manifest_file_sha256
            != self.specification_manifest_file_sha256
            or assessment.status != self.official_response_wire_mapping_status
        ):
            raise ContractValidationError(
                "artifact wire-mapping assessment binding changed"
            )
        expected_claim_firewall = OpenRouterRouteControlArtifactClaimFirewallV1(
            normalized_canned_schema_is_official_wire_schema=(
                self.normalized_canned_schema_is_official_wire_schema
            ),
            official_response_wire_mapping_status=(
                self.official_response_wire_mapping_status
            ),
            exact_endpoint_response_attestation=(
                self.exact_endpoint_response_attestation
            ),
            live_server_enforcement=self.live_server_enforcement,
            live_no_fallback_proof=self.live_no_fallback_proof,
            p17_input_token_bound=self.p17_input_token_bound,
            p18_pricing_record=self.p18_pricing_record,
            p19_cost_bound=self.p19_cost_bound,
            live_pilot_readiness=self.live_pilot_readiness,
            actual_openrouter_availability=self.actual_openrouter_availability,
            real_provider_execution=self.real_provider_execution,
            production_authority=self.production_authority,
        )
        if (
            self.claim_firewall != expected_claim_firewall
            or self.claim_firewall
            != FROZEN_OPENROUTER_ROUTE_CONTROL_ARTIFACT_CLAIM_FIREWALL_V1
        ):
            raise ContractValidationError("artifact claim firewall changed")
        policy = default_openrouter_route_control_policy_v1(
            specification_binding=binding
        )
        if (
            self.route_control_policy_id != policy.route_control_policy_id
            or self.route_intent_contract_id
            != policy.route_intent.route_intent_contract_id
            or self.header_policy_id != policy.header_policy.header_policy_id
            or self.cache_policy_id != policy.header_policy.cache_policy.cache_policy_id
            or self.metadata_policy_id
            != policy.header_policy.metadata_policy.metadata_policy_id
        ):
            raise ContractValidationError("artifact policy identities changed")
        if (
            self.route_policy_receipt != policy
            or self.header_policy_receipt != policy.header_policy
            or self.cache_policy_receipt != policy.header_policy.cache_policy
            or self.metadata_policy_receipt != policy.header_policy.metadata_policy
        ):
            raise ContractValidationError("artifact policy receipts changed")
        if (
            self.canonical_body_json != FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1
            or self.canonical_semantic_headers_json
            != FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1
        ):
            raise ContractValidationError("artifact canonical request bytes changed")
        body_bytes = self.canonical_body_json.encode("utf-8")
        header_bytes = self.canonical_semantic_headers_json.encode("utf-8")
        if (
            self.body_sha256 != _sha256_bytes(body_bytes)
            or self.body_length != len(body_bytes)
            or self.semantic_headers_sha256 != _sha256_bytes(header_bytes)
            or self.semantic_headers_length != len(header_bytes)
        ):
            raise ContractValidationError("artifact body/header byte evidence changed")
        expected_route_intent_id = stable_contract_id(
            "szorrouteintent",
            {
                "body_length": len(body_bytes),
                "body_sha256": _sha256_bytes(body_bytes),
                "route_control_policy_id": self.route_control_policy_id,
                "semantic_headers_length": len(header_bytes),
                "semantic_headers_sha256": _sha256_bytes(header_bytes),
                "specification_manifest_id": self.specification_manifest_id,
                "specification_manifest_sha256": (
                    self.specification_manifest_semantic_sha256
                ),
            },
        )
        if self.route_intent_id != expected_route_intent_id:
            raise ContractValidationError("artifact route-intent identity changed")
        request_receipt = self.request_intent_receipt
        _validate_frozen_evidence_record_links_v1(
            self.frozen_evidence_record_ids,
            binding,
            request_receipt,
        )
        if (
            request_receipt.route_control_policy_id != self.route_control_policy_id
            or request_receipt.route_intent_contract_id
            != self.route_intent_contract_id
            or request_receipt.route_intent_id != self.route_intent_id
            or request_receipt.body_sha256 != self.body_sha256
            or request_receipt.body_length != self.body_length
            or request_receipt.semantic_headers_sha256
            != self.semantic_headers_sha256
            or request_receipt.semantic_headers_length
            != self.semantic_headers_length
        ):
            raise ContractValidationError("artifact request receipt links changed")
        case_set = self.case_set
        if case_set != FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1:
            raise ContractValidationError("artifact case set changed")
        if self.thresholds != FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1:
            raise ContractValidationError("artifact thresholds changed")
        if self.validation_order_id != (
            FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.validation_order_id
        ):
            raise ContractValidationError("artifact validation order changed")
        expected_ids = tuple(case.case_id for case in case_set.cases)
        if tuple(result.case_id for result in self.case_results) != expected_ids:
            raise ContractValidationError("artifact case order or membership changed")
        for case, result in zip(case_set.cases, self.case_results):
            expected_actual = OpenRouterRouteControlCaseActualOutcomeV1(
                case.expected_outcome.value
            )
            derived_match = (
                result.construction_valid
                and result.case_fingerprint == case.case_fingerprint
                and result.kind is case.kind
                and result.expected_outcome is case.expected_outcome
                and result.expected_guard_id == case.expected_guard_id
                and result.expected_failure_code == case.expected_failure_code
                and result.actual_outcome is expected_actual
                and result.actual_guard_id == case.expected_guard_id
                and result.actual_failure_code == case.expected_failure_code
                and result.canned_transport_invocations
                == case.expected_canned_invocations
                and result.complete_route_intent_receipts
                == case.expected_complete_route_intent_receipts
                and result.complete_metadata_receipts
                == case.expected_complete_metadata_receipts
                and result.expected_canned_transport_invocations
                == case.expected_canned_invocations
                and result.expected_complete_route_intent_receipts
                == case.expected_complete_route_intent_receipts
                and result.expected_complete_metadata_receipts
                == case.expected_complete_metadata_receipts
                and result.mutation_vector == case.mutation_vector
                and result.guard_trace
                == (
                    _guard_trace_through(case.expected_guard_id)
                    if case.expected_guard_id is not None
                    else (
                        FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1[:16]
                        if case.kind
                        is OpenRouterRouteControlCaseKind.POSITIVE_REQUEST
                        else FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1
                    )
                )
            )
            if result.result_matches_expectation != derived_match:
                raise ContractValidationError(
                    f"artifact case result flag is not derived: {case.case_id}"
                )
            positive = case.kind in {
                OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
                OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
            }
            if positive and (
                result.request_body_sha256 != self.body_sha256
                or result.semantic_headers_sha256 != self.semantic_headers_sha256
                or result.route_intent_id != self.route_intent_id
                or result.candidate_request_evidence_id
                != request_receipt.receipt_id
                or result.request_intent_receipt_ids
                != (request_receipt.receipt_id,) * result.complete_route_intent_receipts
            ):
                raise ContractValidationError(
                    f"positive case request evidence changed: {case.case_id}"
                )
            if case.kind is OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE:
                raw_evidence = result.raw_response_evidence
                metadata_receipt = result.metadata_receipt
                route_attestation = result.route_attestation
                if (
                    raw_evidence is None
                    or metadata_receipt is None
                    or route_attestation is None
                    or
                    result.metadata_receipt_id != metadata_receipt.receipt_id
                    or result.route_attestation_id != route_attestation.attestation_id
                    or metadata_receipt.raw_response_evidence_id
                    != raw_evidence.evidence_id
                    or metadata_receipt.raw_response_sha256
                    != raw_evidence.raw_response_sha256
                    or route_attestation.metadata_receipt_id
                    != metadata_receipt.receipt_id
                    or route_attestation.route_intent_id != self.route_intent_id
                    or route_attestation.request_intent_receipt_id
                    != request_receipt.receipt_id
                ):
                    raise ContractValidationError(
                        f"positive metadata receipt links changed: {case.case_id}"
                    )
            elif result.canned_transport_invocations == 1:
                if (
                    result.raw_response_evidence is None
                    or result.metadata_receipt is not None
                    or result.route_attestation is not None
                    or result.metadata_receipt_id is not None
                    or result.route_attestation_id is not None
                ):
                    raise ContractValidationError(
                        f"rejected response raw-first evidence changed: {case.case_id}"
                    )
            elif any(
                value is not None
                for value in (
                    result.raw_response_evidence,
                    result.metadata_receipt,
                    result.route_attestation,
                    result.metadata_receipt_id,
                    result.route_attestation_id,
                )
            ):
                raise ContractValidationError(
                    f"non-dispatched case claims response evidence: {case.case_id}"
                )
        historical_identity = tuple(
            (item.lock_name, item.relative_path, item.expected_sha256)
            for item in self.historical_hashes
        )
        expected_historical_identity = tuple(
            (lock_name, relative_path, expected_sha256)
            for lock_name, relative_path, expected_sha256 in _HISTORICAL_ARTIFACT_LOCKS_V1
        )
        if historical_identity != expected_historical_identity:
            raise ContractValidationError("artifact historical lock membership changed")
        expected_mutation_evidence = (
            compare_openrouter_route_control_scoped_snapshots_v1(
                self.scoped_before_snapshot,
                self.scoped_after_snapshot,
            )
        )
        if self.scoped_mutation_evidence != expected_mutation_evidence:
            raise ContractValidationError("artifact scoped mutation evidence changed")
        expected_metrics = _build_metrics_v1(
            self.case_results,
            self.boundary_counters,
            self.scoped_mutation_evidence,
            self.historical_hashes,
            self.official_response_wire_mapping_assessment,
            core_lock_matches=next(
                item.matches
                for item in self.historical_hashes
                if item.lock_name == "phase8-v2"
            ),
            expected_route_intent_id=self.route_intent_id,
        )
        if self.metrics != expected_metrics:
            raise ContractValidationError("artifact metrics are not fully derived")
        request_control_supported = all(
            result.result_matches_expectation
            for result in self.case_results
            if result.kind
            in {
                OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
                OpenRouterRouteControlCaseKind.ORTHOGONAL_REQUEST,
                OpenRouterRouteControlCaseKind.PRECEDENCE,
            }
            and result.expected_canned_transport_invocations == 0
        )
        local_response_supported = all(
            result.result_matches_expectation
            for result in self.case_results
            if result.kind
            in {
                OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
                OpenRouterRouteControlCaseKind.ORTHOGONAL_RESPONSE,
                OpenRouterRouteControlCaseKind.PRECEDENCE,
            }
            and result.expected_canned_transport_invocations == 1
        )
        if self.request_intent_status != (
            "PROVEN_OFFLINE"
            if request_control_supported
            else "NOT_ESTABLISHED"
        ):
            raise ContractValidationError("request-intent status is not derived")
        expected_local_parser_status = (
            "PROVEN_OFFLINE_LOCAL_NORMALIZED_CONTRACT_ONLY"
            if local_response_supported
            else "NOT_ESTABLISHED"
        )
        if self.canned_response_parser_status != expected_local_parser_status:
            raise ContractValidationError("local parser status is not derived")
        expected_provider_attestation = (
            "LOCAL_NORMALIZED_PARTIAL_BROAD_PROVIDER_ONLY"
            if local_response_supported
            else "NOT_ESTABLISHED"
        )
        if self.response_provider_attestation != expected_provider_attestation:
            raise ContractValidationError("provider-attestation status is not derived")
        if (
            self.normalized_canned_schema_is_official_wire_schema is not False
            or self.official_response_wire_mapping_status
            != assessment.status
            or self.metrics.official_response_wire_mapping_violations
            != official_response_wire_mapping_violation_count_v1(assessment)
        ):
            raise ContractValidationError("official response mapping claim changed")
        supported = self.metrics.all_thresholds_pass and all(
            result.result_matches_expectation for result in self.case_results
        )
        expected_status = (
            OpenRouterRouteControlHypothesisStatusV1.SUPPORTED
            if supported
            else OpenRouterRouteControlHypothesisStatusV1.FALSIFIED
        )
        if self.hypothesis_status is not expected_status:
            raise ContractValidationError("artifact hypothesis status is not derived")
        if self.provider_only != self.provider_order or len(self.provider_only) != 1:
            raise ContractValidationError("artifact endpoint intent is not singleton exact")
        payload = self.model_dump(mode="json", exclude={"artifact_id"})
        expected_id = stable_contract_id("szorroutecontrolartifactv1", payload)
        if self.artifact_id not in (None, expected_id):
            raise ContractValidationError("route-control artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected_id)
        return self


def _build_route_control_artifact_v1(
    *,
    reverse_case_order: bool,
    root: Optional[Path] = None,
    authoritative_claim: Optional[_AuthoritativeAggregateClaimV1] = None,
) -> OpenRouterRouteControlArtifactV1:
    repository_root = _repository_root() if root is None else Path(root)
    if reverse_case_order:
        if authoritative_claim is not None:
            raise ContractValidationError(
                "reverse replay must not consume an authoritative forward claim"
            )
    else:
        _validate_authoritative_aggregate_claim_v1(
            repository_root,
            authoritative_claim,
        )
    require_clean_acquisition_boundary_tripwire_v0()
    before_snapshot = capture_openrouter_route_control_scoped_snapshot_v1(repository_root)
    historical_before = verify_openrouter_route_control_historical_hashes_v1(repository_root)
    if not all(item.matches for item in historical_before):
        raise ContractValidationError(
            "historical artifact mismatch requires immediate STOP"
        )
    core_lock_before = _verify_core_lock_v1(repository_root)
    if not core_lock_before:
        raise ContractValidationError("frozen Phase 8 v2 core lock mismatch")
    binding = verify_openrouter_spec_manifest_v1(repository_root)
    wire_mapping_assessment = assess_openrouter_official_response_wire_mapping_v1(
        repository_root
    )
    prepared = prepare_openrouter_route_request_v1(repository_root=repository_root)
    ordered_cases: Sequence[OpenRouterRouteControlCaseV1] = (
        tuple(reversed(FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1))
        if reverse_case_order
        else FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
    )
    evaluated = tuple(
        evaluate_openrouter_route_control_case_v1(
            case,
            prepared_request=prepared,
        )
        for case in ordered_cases
    )
    by_id = {result.case_id: result for result in evaluated}
    results = tuple(
        by_id[case.case_id] for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
    )
    historical_after = verify_openrouter_route_control_historical_hashes_v1(repository_root)
    if historical_before != historical_after or not all(
        item.matches for item in historical_after
    ):
        raise ContractValidationError("historical artifact evidence changed during evaluation")
    core_lock_after = _verify_core_lock_v1(repository_root)
    if not core_lock_after or core_lock_after != core_lock_before:
        raise ContractValidationError("frozen Phase 8 v2 core lock changed")
    after_snapshot = capture_openrouter_route_control_scoped_snapshot_v1(repository_root)
    mutations = compare_openrouter_route_control_scoped_snapshots_v1(
        before_snapshot, after_snapshot
    )
    boundary = _boundary_counters_v1()
    metrics = _build_metrics_v1(
        results,
        boundary,
        mutations,
        historical_after,
        wire_mapping_assessment,
        core_lock_matches=core_lock_after,
        expected_route_intent_id=prepared.route_intent_id or "",
    )
    manifest_bytes = (
        repository_root / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    ).read_bytes()
    manifest_object = json.loads(manifest_bytes)
    if (
        not isinstance(manifest_object.get("source_records"), list)
        or len(manifest_object["source_records"]) != 16
        or not isinstance(manifest_object.get("fact_records"), list)
        or len(manifest_object["fact_records"]) != 13
    ):
        raise ContractValidationError("specification manifest record counts changed")
    artifact = OpenRouterRouteControlArtifactV1(
        official_response_wire_mapping_assessment=wire_mapping_assessment,
        specification_manifest_file_sha256=_sha256_bytes(manifest_bytes),
        specification_binding=binding,
        route_control_policy_id=(
            prepared.route_control_policy.route_control_policy_id or ""
        ),
        route_intent_contract_id=(
            prepared.route_control_policy.route_intent.route_intent_contract_id or ""
        ),
        header_policy_id=(
            prepared.route_control_policy.header_policy.header_policy_id or ""
        ),
        cache_policy_id=(
            prepared.route_control_policy.header_policy.cache_policy.cache_policy_id
            or ""
        ),
        metadata_policy_id=(
            prepared.route_control_policy.header_policy.metadata_policy.metadata_policy_id
            or ""
        ),
        route_policy_receipt=prepared.route_control_policy,
        header_policy_receipt=prepared.route_control_policy.header_policy,
        cache_policy_receipt=(
            prepared.route_control_policy.header_policy.cache_policy
        ),
        metadata_policy_receipt=(
            prepared.route_control_policy.header_policy.metadata_policy
        ),
        canonical_body_json=prepared.canonical_body_json,
        canonical_semantic_headers_json=prepared.canonical_semantic_headers_json,
        body_sha256=prepared.body_sha256 or "",
        body_length=prepared.body_length or 0,
        semantic_headers_sha256=prepared.header_sha256,
        semantic_headers_length=prepared.header_length,
        route_intent_id=prepared.route_intent_id or "",
        request_intent_receipt=prepared.request_intent_receipt,
        validation_order_id=(
            FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.validation_order_id
            or ""
        ),
        case_set=FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1,
        thresholds=FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1,
        case_results=results,
        metrics=metrics,
        boundary_counters=boundary,
        scoped_before_snapshot=before_snapshot,
        scoped_after_snapshot=after_snapshot,
        scoped_mutation_evidence=mutations,
        historical_hashes=historical_after,
        hypothesis_status=(
            OpenRouterRouteControlHypothesisStatusV1.SUPPORTED
            if metrics.all_thresholds_pass
            else OpenRouterRouteControlHypothesisStatusV1.FALSIFIED
        ),
        request_intent_status=(
            "PROVEN_OFFLINE"
            if all(
                result.result_matches_expectation
                for result in results
                if result.kind
                in {
                    OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
                    OpenRouterRouteControlCaseKind.ORTHOGONAL_REQUEST,
                    OpenRouterRouteControlCaseKind.PRECEDENCE,
                }
                and result.expected_canned_transport_invocations == 0
            )
            else "NOT_ESTABLISHED"
        ),
        canned_response_parser_status=(
            "PROVEN_OFFLINE_LOCAL_NORMALIZED_CONTRACT_ONLY"
            if all(
                result.result_matches_expectation
                for result in results
                if result.kind
                in {
                    OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
                    OpenRouterRouteControlCaseKind.ORTHOGONAL_RESPONSE,
                    OpenRouterRouteControlCaseKind.PRECEDENCE,
                }
                and result.expected_canned_transport_invocations == 1
            )
            else "NOT_ESTABLISHED"
        ),
        response_provider_attestation=(
            "LOCAL_NORMALIZED_PARTIAL_BROAD_PROVIDER_ONLY"
            if all(
                result.result_matches_expectation
                for result in results
                if result.kind
                in {
                    OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
                    OpenRouterRouteControlCaseKind.ORTHOGONAL_RESPONSE,
                    OpenRouterRouteControlCaseKind.PRECEDENCE,
                }
                and result.expected_canned_transport_invocations == 1
            )
            else "NOT_ESTABLISHED"
        ),
    )
    final_snapshot = capture_openrouter_route_control_scoped_snapshot_v1(
        repository_root
    )
    if final_snapshot != after_snapshot:
        raise ContractValidationError(
            "scoped source changed during artifact validation"
        )
    if (
        verify_openrouter_route_control_historical_hashes_v1(repository_root)
        != historical_after
        or not _verify_core_lock_v1(repository_root)
    ):
        raise ContractValidationError(
            "historical evidence changed during artifact validation"
        )
    assert_acquisition_artifact_tripwires_v0(artifact.boundary_counters)
    return artifact


def render_openrouter_route_control_artifact_v1(
    artifact: OpenRouterRouteControlArtifactV1,
) -> bytes:
    if type(artifact) is not OpenRouterRouteControlArtifactV1:
        raise ContractValidationError("artifact must use the exact frozen v1 type")
    try:
        validated = OpenRouterRouteControlArtifactV1.model_validate(
            artifact.model_dump(mode="json")
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractValidationError("artifact integrity changed before render") from exc
    if validated != artifact:
        raise ContractValidationError("artifact integrity changed before render")
    return (
        canonical_json(validated.model_dump(mode="json")) + "\n"
    ).encode("utf-8")


def load_openrouter_route_control_artifact_v1(
    path: Path,
) -> OpenRouterRouteControlArtifactV1:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("route-control artifact is unavailable or malformed") from exc
    artifact = OpenRouterRouteControlArtifactV1.model_validate(value)
    if Path(path).read_bytes() != render_openrouter_route_control_artifact_v1(artifact):
        raise ContractValidationError("route-control artifact bytes are not canonical")
    return artifact


def _write_once(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(value)
    except FileExistsError as exc:
        raise ContractValidationError(f"write-once evidence already exists: {path}") from exc


def _authoritative_aggregate_claim_path_v1(artifact_path: Path) -> Path:
    path = Path(artifact_path)
    return path.with_name(path.name + OPENROUTER_ROUTE_CONTROL_AGGREGATE_CLAIM_SUFFIX_V1)


def _authoritative_aggregate_consumed_path_v1(artifact_path: Path) -> Path:
    path = Path(artifact_path)
    return path.with_name(
        path.name + OPENROUTER_ROUTE_CONTROL_AGGREGATE_CONSUMED_SUFFIX_V1
    )


def _authoritative_aggregate_claim_bytes_v1() -> bytes:
    return (
        canonical_json(
            {
                "artifact_path": OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1,
                "case_set_id": OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1,
                "manifest_id": OPENROUTER_SPECIFICATION_MANIFEST_ID_V1,
                "schema_version": (
                    "socrateszero-openrouter-route-control-authoritative-aggregate-claim/v1"
                ),
                "thresholds_id": OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1,
            }
        )
        + "\n"
    ).encode("utf-8")


def _acquire_authoritative_aggregate_claim_v1(
    artifact_path: Path,
) -> _AuthoritativeAggregateClaimV1:
    path = Path(artifact_path)
    claim_path = _authoritative_aggregate_claim_path_v1(path)
    consumed_path = _authoritative_aggregate_consumed_path_v1(path)
    if path.exists() or consumed_path.exists():
        raise ContractValidationError(f"write-once evidence already exists: {path}")
    claim_bytes = _authoritative_aggregate_claim_bytes_v1()
    _write_once(claim_path, claim_bytes)
    return _AuthoritativeAggregateClaimV1(
        artifact_path=path,
        claim_path=claim_path,
        consumed_path=consumed_path,
        claim_sha256=_sha256_bytes(claim_bytes),
    )


def _validate_authoritative_aggregate_claim_v1(
    repository_root: Path,
    claim: Optional[_AuthoritativeAggregateClaimV1],
) -> None:
    if type(claim) is not _AuthoritativeAggregateClaimV1:
        raise ContractValidationError(
            "forward authoritative aggregate requires an exclusive claim"
        )
    expected_artifact_path = (
        Path(repository_root) / OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    )
    expected_claim_path = _authoritative_aggregate_claim_path_v1(
        expected_artifact_path
    )
    expected_consumed_path = _authoritative_aggregate_consumed_path_v1(
        expected_artifact_path
    )
    expected_bytes = _authoritative_aggregate_claim_bytes_v1()
    try:
        actual_bytes = claim.claim_path.read_bytes()
    except OSError as exc:
        raise ContractValidationError(
            "authoritative aggregate claim is unavailable"
        ) from exc
    if (
        claim.artifact_path != expected_artifact_path
        or claim.claim_path != expected_claim_path
        or claim.consumed_path != expected_consumed_path
        or claim.claim_sha256 != _sha256_bytes(expected_bytes)
        or actual_bytes != expected_bytes
        or expected_artifact_path.exists()
        or expected_consumed_path.exists()
    ):
        raise ContractValidationError(
            "authoritative aggregate claim does not match the frozen operation"
        )
    try:
        claim.claim_path.rename(claim.consumed_path)
    except OSError as exc:
        raise ContractValidationError(
            "authoritative aggregate claim could not be consumed exactly once"
        ) from exc
    try:
        consumed_bytes = claim.consumed_path.read_bytes()
    except OSError as exc:
        raise ContractValidationError(
            "consumed authoritative aggregate claim is unavailable"
        ) from exc
    if consumed_bytes != expected_bytes:
        raise ContractValidationError(
            "consumed authoritative aggregate claim changed"
        )


def _publish_openrouter_route_control_artifact_once_v1(
    artifact: OpenRouterRouteControlArtifactV1,
    path: Path,
) -> str:
    require_clean_acquisition_boundary_tripwire_v0()
    assert_acquisition_artifact_tripwires_v0(artifact.boundary_counters)
    if Path(path).exists():
        raise ContractValidationError(f"write-once evidence already exists: {path}")
    value = render_openrouter_route_control_artifact_v1(artifact)
    _write_once(Path(path), value)
    return _sha256_bytes(value)


class OpenRouterRouteControlReplayExecutionV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_SCHEMA_V1
    replay_execution_id: Optional[str] = None
    case_evaluation_order: Literal["REVERSE_FROZEN_CASE_ORDER"] = (
        "REVERSE_FROZEN_CASE_ORDER"
    )
    ordered_case_ids: Tuple[str, ...] = Field(min_length=63, max_length=63)
    ordered_result_ids: Tuple[str, ...] = Field(min_length=63, max_length=63)
    ordered_result_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_artifact_id: str
    authoritative_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_artifact_id: str
    replay_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: Literal[True] = True
    artifact_id_equality: Literal[True] = True
    byte_identity: Literal[True] = True
    authoritative_artifact_bytes: int = Field(ge=1)
    replay_artifact_bytes: int = Field(ge=1)
    boundary_counters: OpenRouterBoundaryCountersV1

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRouteControlReplayExecutionV1":
        expected_order = tuple(
            case.case_id
            for case in reversed(FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1)
        )
        if self.ordered_case_ids != expected_order:
            raise ContractValidationError("replay case order is not exact reverse")
        if any(
            not re.fullmatch(r"szorroutecaseresultv1_[0-9a-f]{64}", result_id)
            for result_id in self.ordered_result_ids
        ):
            raise ContractValidationError("replay result trace identity malformed")
        expected_trace_sha256 = _sha256_bytes(
            canonical_json(
                tuple(zip(self.ordered_case_ids, self.ordered_result_ids))
            ).encode("utf-8")
        )
        if self.ordered_result_trace_sha256 != expected_trace_sha256:
            raise ContractValidationError("replay result trace digest mismatch")
        if self.authoritative_artifact_id != self.replay_artifact_id:
            raise ContractValidationError("replay artifact identity diverged")
        if self.authoritative_artifact_sha256 != self.replay_artifact_sha256:
            raise ContractValidationError("replay artifact bytes diverged")
        if self.authoritative_artifact_bytes != self.replay_artifact_bytes:
            raise ContractValidationError("replay artifact lengths diverged")
        expected = stable_contract_id(
            "szorroutereplayexecutionv1",
            self.model_dump(mode="json", exclude={"replay_execution_id"}),
        )
        if self.replay_execution_id not in (None, expected):
            raise ContractValidationError("replay execution ID mismatch")
        object.__setattr__(self, "replay_execution_id", expected)
        return self


class OpenRouterRouteControlReplayLockV1(_FrozenEvaluationContractV1):
    schema_version: Literal[
        OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_SCHEMA_V1
    ] = OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_SCHEMA_V1
    replay_lock_id: Optional[str] = None
    artifact_relative_path: Literal[
        OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    ] = OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    artifact_id: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_execution_relative_path: Literal[
        OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1
    ] = OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1
    replay_execution_id: str
    replay_execution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: Literal[True] = True
    artifact_id_equality: Literal[True] = True
    byte_identity: Literal[True] = True
    external_activity: Literal[0] = 0
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRouteControlReplayLockV1":
        expected = stable_contract_id(
            "szorroutereplaylockv1",
            self.model_dump(mode="json", exclude={"replay_lock_id"}),
        )
        if self.replay_lock_id not in (None, expected):
            raise ContractValidationError("replay lock ID mismatch")
        object.__setattr__(self, "replay_lock_id", expected)
        return self


def render_openrouter_route_control_replay_execution_v1(
    execution: OpenRouterRouteControlReplayExecutionV1,
) -> bytes:
    if type(execution) is not OpenRouterRouteControlReplayExecutionV1:
        raise ContractValidationError("replay execution must use the exact v1 type")
    try:
        validated = OpenRouterRouteControlReplayExecutionV1.model_validate(
            execution.model_dump(mode="json")
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractValidationError("replay execution integrity changed") from exc
    if validated != execution:
        raise ContractValidationError("replay execution integrity changed")
    return (canonical_json(validated.model_dump(mode="json")) + "\n").encode("utf-8")


def render_openrouter_route_control_replay_lock_v1(
    replay_lock: OpenRouterRouteControlReplayLockV1,
) -> bytes:
    if type(replay_lock) is not OpenRouterRouteControlReplayLockV1:
        raise ContractValidationError("replay lock must use the exact v1 type")
    try:
        validated = OpenRouterRouteControlReplayLockV1.model_validate(
            replay_lock.model_dump(mode="json")
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractValidationError("replay lock integrity changed") from exc
    if validated != replay_lock:
        raise ContractValidationError("replay lock integrity changed")
    return (canonical_json(validated.model_dump(mode="json")) + "\n").encode("utf-8")


def load_openrouter_route_control_replay_execution_v1(
    path: Path,
) -> OpenRouterRouteControlReplayExecutionV1:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("replay execution is unavailable or malformed") from exc
    execution = OpenRouterRouteControlReplayExecutionV1.model_validate(value)
    if raw != render_openrouter_route_control_replay_execution_v1(execution):
        raise ContractValidationError("replay execution bytes are not canonical")
    return execution


def load_openrouter_route_control_replay_lock_v1(
    path: Path,
) -> OpenRouterRouteControlReplayLockV1:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("replay lock is unavailable or malformed") from exc
    replay_lock = OpenRouterRouteControlReplayLockV1.model_validate(value)
    if raw != render_openrouter_route_control_replay_lock_v1(replay_lock):
        raise ContractValidationError("replay lock bytes are not canonical")
    return replay_lock


def _validate_replay_crosslinks_v1(
    authoritative_artifact: OpenRouterRouteControlArtifactV1,
    authoritative_bytes: bytes,
    execution: OpenRouterRouteControlReplayExecutionV1,
    replay_lock: OpenRouterRouteControlReplayLockV1,
) -> Tuple[bytes, bytes]:
    _require_supported_authoritative_artifact_for_replay_v1(
        authoritative_artifact
    )
    if authoritative_bytes != render_openrouter_route_control_artifact_v1(
        authoritative_artifact
    ):
        raise ContractValidationError("authoritative artifact bytes are not canonical")
    execution_bytes = render_openrouter_route_control_replay_execution_v1(execution)
    lock_bytes = render_openrouter_route_control_replay_lock_v1(replay_lock)
    artifact_sha256 = _sha256_bytes(authoritative_bytes)
    _validate_replay_result_trace_crosslink_v1(
        authoritative_artifact,
        execution,
    )
    if (
        execution.authoritative_artifact_id != authoritative_artifact.artifact_id
        or execution.replay_artifact_id != authoritative_artifact.artifact_id
        or execution.authoritative_artifact_sha256 != artifact_sha256
        or execution.replay_artifact_sha256 != artifact_sha256
        or execution.authoritative_artifact_bytes != len(authoritative_bytes)
        or execution.replay_artifact_bytes != len(authoritative_bytes)
        or replay_lock.artifact_id != authoritative_artifact.artifact_id
        or replay_lock.artifact_sha256 != artifact_sha256
        or replay_lock.replay_execution_id != execution.replay_execution_id
        or replay_lock.replay_execution_sha256 != _sha256_bytes(execution_bytes)
    ):
        raise ContractValidationError("replay evidence cross-link mismatch")
    return execution_bytes, lock_bytes


def _expected_replay_result_trace_v1(
    authoritative_artifact: OpenRouterRouteControlArtifactV1,
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    expected_case_ids = tuple(
        case.case_id for case in reversed(FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1)
    )
    result_by_id = {
        result.case_id: result for result in authoritative_artifact.case_results
    }
    expected_result_ids = tuple(
        stable_contract_id(
            "szorroutecaseresultv1",
            result_by_id[case_id].model_dump(mode="json"),
        )
        for case_id in expected_case_ids
    )
    return expected_case_ids, expected_result_ids


def _validate_replay_result_trace_crosslink_v1(
    authoritative_artifact: OpenRouterRouteControlArtifactV1,
    execution: OpenRouterRouteControlReplayExecutionV1,
) -> None:
    expected_case_ids, expected_result_ids = _expected_replay_result_trace_v1(
        authoritative_artifact
    )
    if (
        execution.ordered_case_ids != expected_case_ids
        or execution.ordered_result_ids != expected_result_ids
    ):
        raise ContractValidationError(
            "replay result trace is not derived from authoritative case results"
        )


def _require_supported_authoritative_artifact_for_replay_v1(
    authoritative_artifact: OpenRouterRouteControlArtifactV1,
) -> None:
    if type(authoritative_artifact) is not OpenRouterRouteControlArtifactV1:
        raise ContractValidationError(
            "authoritative artifact must use the exact frozen v1 type"
        )
    if (
        authoritative_artifact.hypothesis_status
        is not OpenRouterRouteControlHypothesisStatusV1.SUPPORTED
        or not authoritative_artifact.metrics.all_thresholds_pass
    ):
        raise ContractValidationError("replay is permitted only after complete support")


def build_independent_reverse_replay_v1(
    authoritative_artifact: OpenRouterRouteControlArtifactV1,
    authoritative_bytes: bytes,
    *,
    root: Optional[Path] = None,
) -> Tuple[OpenRouterRouteControlReplayExecutionV1, OpenRouterRouteControlReplayLockV1]:
    require_clean_acquisition_boundary_tripwire_v0()
    _require_supported_authoritative_artifact_for_replay_v1(
        authoritative_artifact
    )
    if authoritative_bytes != render_openrouter_route_control_artifact_v1(
        authoritative_artifact
    ):
        raise ContractValidationError("authoritative artifact bytes are not canonical")
    replay_artifact = _build_route_control_artifact_v1(
        reverse_case_order=True,
        root=root,
    )
    replay_bytes = render_openrouter_route_control_artifact_v1(replay_artifact)
    if replay_artifact != authoritative_artifact:
        raise ContractValidationError("reverse replay semantic equality failed")
    if replay_artifact.artifact_id != authoritative_artifact.artifact_id:
        raise ContractValidationError("reverse replay artifact ID equality failed")
    if replay_bytes != authoritative_bytes:
        raise ContractValidationError("reverse replay byte identity failed")
    boundary = _boundary_counters_v1()
    ordered_case_ids = tuple(
        case.case_id for case in reversed(FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1)
    )
    replay_results_by_id = {
        result.case_id: result for result in replay_artifact.case_results
    }
    ordered_result_ids = tuple(
        stable_contract_id(
            "szorroutecaseresultv1",
            replay_results_by_id[case_id].model_dump(mode="json"),
        )
        for case_id in ordered_case_ids
    )
    execution = OpenRouterRouteControlReplayExecutionV1(
        ordered_case_ids=ordered_case_ids,
        ordered_result_ids=ordered_result_ids,
        ordered_result_trace_sha256=_sha256_bytes(
            canonical_json(tuple(zip(ordered_case_ids, ordered_result_ids))).encode(
                "utf-8"
            )
        ),
        authoritative_artifact_id=authoritative_artifact.artifact_id or "",
        authoritative_artifact_sha256=_sha256_bytes(authoritative_bytes),
        replay_artifact_id=replay_artifact.artifact_id or "",
        replay_artifact_sha256=_sha256_bytes(replay_bytes),
        authoritative_artifact_bytes=len(authoritative_bytes),
        replay_artifact_bytes=len(replay_bytes),
        boundary_counters=boundary,
    )
    execution_bytes = render_openrouter_route_control_replay_execution_v1(execution)
    replay_lock = OpenRouterRouteControlReplayLockV1(
        artifact_id=authoritative_artifact.artifact_id or "",
        artifact_sha256=_sha256_bytes(authoritative_bytes),
        replay_execution_id=execution.replay_execution_id or "",
        replay_execution_sha256=_sha256_bytes(execution_bytes),
    )
    return execution, replay_lock


def publish_openrouter_route_control_replay_once_v1(
    authoritative_artifact: OpenRouterRouteControlArtifactV1,
    authoritative_bytes: bytes,
    execution: OpenRouterRouteControlReplayExecutionV1,
    replay_lock: OpenRouterRouteControlReplayLockV1,
    *,
    execution_path: Path,
    lock_path: Path,
) -> Tuple[str, str]:
    require_clean_acquisition_boundary_tripwire_v0()
    _require_supported_authoritative_artifact_for_replay_v1(
        authoritative_artifact
    )
    if Path(execution_path).exists() or Path(lock_path).exists():
        raise ContractValidationError("write-once replay evidence already exists")
    execution_bytes, lock_bytes = _validate_replay_crosslinks_v1(
        authoritative_artifact,
        authoritative_bytes,
        execution,
        replay_lock,
    )
    _write_once(Path(execution_path), execution_bytes)
    _write_once(Path(lock_path), lock_bytes)
    return _sha256_bytes(execution_bytes), _sha256_bytes(lock_bytes)


def _artifact_command(root: Path) -> int:
    artifact_path = root / OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    with AcquisitionBoundaryTripwireV0():
        claim = _acquire_authoritative_aggregate_claim_v1(artifact_path)
        artifact = _build_route_control_artifact_v1(
            reverse_case_order=False,
            root=root,
            authoritative_claim=claim,
        )
        artifact_sha256 = _publish_openrouter_route_control_artifact_once_v1(
            artifact, artifact_path
        )
        try:
            claim.consumed_path.unlink()
        except OSError as exc:
            raise ContractValidationError(
                "authoritative artifact published but aggregate claim could not close"
            ) from exc
    print(
        canonical_json(
            {
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact_sha256,
                "hypothesis_status": artifact.hypothesis_status.value,
            }
        )
    )
    return 0 if artifact.hypothesis_status is OpenRouterRouteControlHypothesisStatusV1.SUPPORTED else 1


def _replay_command(root: Path) -> int:
    artifact_path = root / OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    execution_path = root / OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1
    lock_path = root / OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_RELATIVE_PATH_V1
    with AcquisitionBoundaryTripwireV0():
        if execution_path.exists() or lock_path.exists():
            raise ContractValidationError("write-once replay evidence already exists")
        artifact_bytes = artifact_path.read_bytes()
        artifact = load_openrouter_route_control_artifact_v1(artifact_path)
        execution, replay_lock = build_independent_reverse_replay_v1(
            artifact,
            artifact_bytes,
            root=root,
        )
        execution_sha256, lock_sha256 = publish_openrouter_route_control_replay_once_v1(
            artifact,
            artifact_bytes,
            execution,
            replay_lock,
            execution_path=execution_path,
            lock_path=lock_path,
        )
    print(
        canonical_json(
            {
                "replay_execution_id": execution.replay_execution_id,
                "replay_execution_sha256": execution_sha256,
                "replay_lock_id": replay_lock.replay_lock_id,
                "replay_lock_sha256": lock_sha256,
            }
        )
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("artifact", "replay"))
    parser.add_argument("--root", type=Path, default=_repository_root())
    args = parser.parse_args(argv)
    return _artifact_command(args.root) if args.action == "artifact" else _replay_command(args.root)


if __name__ == "__main__":  # pragma: no cover - explicit scientific operation
    raise SystemExit(main())


__all__ = [
    "FROZEN_OPENROUTER_ROUTE_CONTROL_ARTIFACT_CLAIM_FIREWALL_V1",
    "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1",
    "FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1",
    "FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_ROW_COUNT_V1",
    "FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1",
    "FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1",
    "OPENROUTER_PROVENANCE_BOUNDARY_ID_V1",
    "OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1",
    "OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1",
    "OpenRouterProvenanceRecordV1",
    "openrouter_provenance_record_v1",
    "FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1",
    "OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1",
    "OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1",
    "OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_RELATIVE_PATH_V1",
    "OFFICIAL_RESPONSE_WIRE_MAPPING_STATUS_V1",
    "OpenRouterBoundaryCountersV1",
    "OpenRouterHistoricalHashEvidenceV1",
    "OpenRouterRouteControlArtifactClaimFirewallV1",
    "OpenRouterOfficialResponseWireFactObservationV1",
    "OpenRouterOfficialResponseWireMappingAssessmentV1",
    "OpenRouterOfficialResponseWireSourceObservationV1",
    "OpenRouterRouteControlArtifactV1",
    "OpenRouterRouteControlCaseActualOutcomeV1",
    "OpenRouterRouteControlCaseResultV1",
    "OpenRouterRouteControlHypothesisStatusV1",
    "OpenRouterRouteControlMetricsV1",
    "OpenRouterRouteControlReplayExecutionV1",
    "OpenRouterRouteControlReplayLockV1",
    "OpenRouterRouteControlMutationScopeV1",
    "OpenRouterScopedMutationEvidenceV1",
    "OpenRouterScopedPathMutationV1",
    "OpenRouterScopedPathSnapshotV1",
    "assess_openrouter_official_response_wire_mapping_v1",
    "build_independent_reverse_replay_v1",
    "capture_openrouter_route_control_scoped_snapshot_v1",
    "compare_openrouter_route_control_scoped_snapshots_v1",
    "evaluate_openrouter_route_control_case_v1",
    "load_openrouter_route_control_artifact_v1",
    "load_openrouter_route_control_replay_execution_v1",
    "load_openrouter_route_control_replay_lock_v1",
    "official_response_wire_mapping_gate_passes_v1",
    "official_response_wire_mapping_violation_count_v1",
    "publish_openrouter_route_control_replay_once_v1",
    "render_openrouter_route_control_artifact_v1",
    "render_openrouter_route_control_replay_execution_v1",
    "render_openrouter_route_control_replay_lock_v1",
    "verify_openrouter_route_control_historical_hashes_v1",
]

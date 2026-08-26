"""Content-addressed OpenRouter official wire-specification manifest v1.

The module is offline and import-inert.  It turns the already persisted frozen
source plan and retrieval log into typed source/fact/mapping evidence, evaluates
manifest sufficiency independently, and supports deterministic offline
revalidation.  It never retrieves documentation, calls a provider, parses a
provider response, or mutates CED/runtime state.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_wire_spec_source_v1 import (
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
    OpenRouterWireRetrievalLogV1,
    OpenRouterWireRetrievalStatusV1,
)


OPENROUTER_WIRE_SOURCE_EVIDENCE_RECORD_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-source-evidence-record/v1"
)
OPENROUTER_WIRE_FACT_RECORD_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-fact-record/v1"
)
OPENROUTER_WIRE_MAPPING_RECORD_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-mapping-record/v1"
)
OPENROUTER_WIRE_FIXTURE_BLUEPRINT_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-fixture-blueprint/v1"
)
OPENROUTER_WIRE_RELATIONSHIP_ASSESSMENT_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-relationship-assessment/v1"
)
OPENROUTER_WIRE_SPECIFICATION_MANIFEST_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-specification-manifest/v1"
)
OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-sufficiency-thresholds/v1"
)
OPENROUTER_WIRE_SUFFICIENCY_METRICS_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-sufficiency-metrics/v1"
)
OPENROUTER_WIRE_MANIFEST_VALIDATION_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-manifest-validation/v1"
)
OPENROUTER_WIRE_MANIFEST_REVALIDATION_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-manifest-revalidation/v1"
)

OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/openrouter_official_wire_specification_manifest_v1.json"
)
OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "artifacts/openrouter_wire_specification_manifest_validation_v1.json"
)
OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "artifacts/openrouter_wire_specification_manifest_revalidation_v1.json"
)

PREDECESSOR_MANIFEST_V0_ID = (
    "szorspecmanifestv0_6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03"
)
PREDECESSOR_MANIFEST_V0_FILE_SHA256 = (
    "818a1ec466bd37bd23dd86ef14fecf0fcc0049360bef7b5a16fdc2f575069e9f"
)
SEALED_ROUTE_CONTROLS_V1_ARTIFACT_ID = (
    "szorroutecontrolartifactv1_1a747011668f620b9db04cc2a42c57c5b23b59def879bcc978d37c3f94f0e2cd"
)
SEALED_ROUTE_CONTROLS_V1_SHA256 = (
    "61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661"
)


class _FrozenManifestContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterWireHypothesisStatusV1(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class OpenRouterWireEvidenceStatusV1(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class OpenRouterWireEvidenceStrengthV1(str, Enum):
    DIRECTLY_DOCUMENTED = "DIRECTLY_DOCUMENTED"
    DERIVED_LOSSLESSLY = "DERIVED_LOSSLESSLY"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class OpenRouterWireEnvelopeKindV1(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CACHE = "CACHE"
    CROSS_CUTTING = "CROSS_CUTTING"
    UNKNOWN = "UNKNOWN"


class OpenRouterWireJsonTypeV1(str, Enum):
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    NULL = "NULL"
    UNION = "UNION"
    UNKNOWN = "UNKNOWN"


class OpenRouterWirePresenceRuleV1(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class OpenRouterWireNullabilityV1(str, Enum):
    NON_NULL = "NON_NULL"
    NULLABLE = "NULLABLE"
    UNKNOWN = "UNKNOWN"


class OpenRouterWireProviderGranularityV1(str, Enum):
    EXACT_ENDPOINT_SLUG = "EXACT_ENDPOINT_SLUG"
    BASE_PROVIDER_SLUG = "BASE_PROVIDER_SLUG"
    PROVIDER_ORGANIZATION = "PROVIDER_ORGANIZATION"
    HUMAN_DISPLAY_NAME = "HUMAN_DISPLAY_NAME"
    OPAQUE_IDENTIFIER = "OPAQUE_IDENTIFIER"
    UNKNOWN = "UNKNOWN"


class OpenRouterWireRelationshipV1(str, Enum):
    SUCCESS_ENVELOPE_PLACEMENT = "SUCCESS_ENVELOPE_PLACEMENT"
    ERROR_ENVELOPE_PLACEMENT = "ERROR_ENVELOPE_PLACEMENT"
    CACHE_METADATA_ABSENCE = "CACHE_METADATA_ABSENCE"
    CACHE_ATTESTATION = "CACHE_ATTESTATION"
    ATTEMPT_SEMANTICS = "ATTEMPT_SEMANTICS"
    ATTEMPTS_LIST_SEMANTICS = "ATTEMPTS_LIST_SEMANTICS"
    ENDPOINT_COLLECTION = "ENDPOINT_COLLECTION"
    PROVIDER_GRANULARITY = "PROVIDER_GRANULARITY"
    SERVED_MODEL_PRECEDENCE = "SERVED_MODEL_PRECEDENCE"
    STRATEGY_SEMANTICS = "STRATEGY_SEMANTICS"
    PIPELINE_SEMANTICS = "PIPELINE_SEMANTICS"
    UNKNOWN_ADDITIVE_FIELD_POLICY = "UNKNOWN_ADDITIVE_FIELD_POLICY"
    EXACT_ENDPOINT_RESPONSE_IDENTITY = "EXACT_ENDPOINT_RESPONSE_IDENTITY"
    ACTUAL_SERVED_MODEL_IDENTITY = "ACTUAL_SERVED_MODEL_IDENTITY"


MANDATORY_RELATIONSHIPS_V1: Tuple[OpenRouterWireRelationshipV1, ...] = tuple(
    OpenRouterWireRelationshipV1
)


class OpenRouterWireSourceEvidenceRecordV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_SOURCE_EVIDENCE_RECORD_SCHEMA_V1
    ] = OPENROUTER_WIRE_SOURCE_EVIDENCE_RECORD_SCHEMA_V1
    source_evidence_id: Optional[str] = None
    source_key: str
    plan_record_id: str
    canonical_public_locator: str
    retrieval_event_id: str
    retrieval_status: OpenRouterWireRetrievalStatusV1
    retrieval_error_code: Optional[str] = None
    retained_snapshot_id: Optional[str] = None
    raw_source_path: Optional[str] = None
    raw_source_byte_length: Optional[int] = Field(default=None, ge=1)
    raw_source_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_extract_path: Optional[str] = None
    canonical_extract_byte_length: Optional[int] = Field(default=None, ge=1)
    canonical_extract_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    source_inspectable: bool

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireSourceEvidenceRecordV1":
        retained = self.retrieval_status is OpenRouterWireRetrievalStatusV1.RETAINED
        snapshot_fields = (
            self.retained_snapshot_id,
            self.raw_source_path,
            self.raw_source_byte_length,
            self.raw_source_sha256,
            self.canonical_extract_path,
            self.canonical_extract_byte_length,
            self.canonical_extract_sha256,
        )
        if retained:
            if any(value is None for value in snapshot_fields) or not self.source_inspectable:
                raise ContractValidationError("retained source evidence is incomplete")
            if self.retrieval_error_code is not None:
                raise ContractValidationError("retained source evidence carries an error")
        else:
            if any(value is not None for value in snapshot_fields) or self.source_inspectable:
                raise ContractValidationError("failed source evidence claims retained bytes")
            if not self.retrieval_error_code:
                raise ContractValidationError("failed source evidence lacks an error")
        expected = stable_contract_id(
            "szorwiresourceevidencev1",
            self.model_dump(mode="json", exclude={"source_evidence_id"}),
        )
        if self.source_evidence_id not in (None, expected):
            raise ContractValidationError("source evidence ID mismatch")
        object.__setattr__(self, "source_evidence_id", expected)
        return self


class OpenRouterWireFactRecordV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_FACT_RECORD_SCHEMA_V1
    ] = OPENROUTER_WIRE_FACT_RECORD_SCHEMA_V1
    fact_id: Optional[str] = None
    official_path: str = Field(min_length=1)
    envelope_kind: OpenRouterWireEnvelopeKindV1
    json_type: OpenRouterWireJsonTypeV1
    presence_rule: OpenRouterWirePresenceRuleV1
    nullability: OpenRouterWireNullabilityV1
    cardinality: str = Field(min_length=1)
    child_schema: str = Field(min_length=1)
    semantic_meaning: str = Field(min_length=1)
    source_evidence_ids: Tuple[str, ...]
    source_anchors: Tuple[str, ...]
    strength: OpenRouterWireEvidenceStrengthV1
    limitations: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireFactRecordV1":
        if not self.source_evidence_ids or not self.source_anchors:
            raise ContractValidationError("wire fact lacks source provenance")
        if self.strength is not OpenRouterWireEvidenceStrengthV1.NOT_ESTABLISHED and (
            self.json_type is OpenRouterWireJsonTypeV1.UNKNOWN
            or self.presence_rule is OpenRouterWirePresenceRuleV1.UNKNOWN
            or self.nullability is OpenRouterWireNullabilityV1.UNKNOWN
        ):
            raise ContractValidationError("positive wire fact has unknown schema semantics")
        expected = stable_contract_id(
            "szorwirefactv1",
            self.model_dump(mode="json", exclude={"fact_id"}),
        )
        if self.fact_id not in (None, expected):
            raise ContractValidationError("wire fact ID mismatch")
        object.__setattr__(self, "fact_id", expected)
        return self


class OpenRouterWireMappingRecordV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_MAPPING_RECORD_SCHEMA_V1
    ] = OPENROUTER_WIRE_MAPPING_RECORD_SCHEMA_V1
    mapping_id: Optional[str] = None
    official_path: str = Field(min_length=1)
    internal_target_field: str = Field(min_length=1)
    transformation_rule: str = Field(min_length=1)
    lossless: bool
    missing_field_behavior: str = Field(min_length=1)
    invalid_type_behavior: str = Field(min_length=1)
    unknown_field_behavior: str = Field(min_length=1)
    authority_scope: str = Field(min_length=1)
    source_fact_ids: Tuple[str, ...]
    strength: OpenRouterWireEvidenceStrengthV1

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireMappingRecordV1":
        if not self.source_fact_ids:
            raise ContractValidationError("wire mapping lacks source facts")
        if self.strength is OpenRouterWireEvidenceStrengthV1.DERIVED_LOSSLESSLY and not self.lossless:
            raise ContractValidationError("lossless mapping strength contradicts mapping")
        if self.strength is OpenRouterWireEvidenceStrengthV1.NOT_ESTABLISHED and self.lossless:
            raise ContractValidationError("unestablished mapping claims losslessness")
        expected = stable_contract_id(
            "szorwiremappingv1",
            self.model_dump(mode="json", exclude={"mapping_id"}),
        )
        if self.mapping_id not in (None, expected):
            raise ContractValidationError("wire mapping ID mismatch")
        object.__setattr__(self, "mapping_id", expected)
        return self


class OpenRouterWireFixtureBlueprintV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_FIXTURE_BLUEPRINT_SCHEMA_V1
    ] = OPENROUTER_WIRE_FIXTURE_BLUEPRINT_SCHEMA_V1
    fixture_blueprint_id: Optional[str] = None
    fixture_kind: str = Field(min_length=1)
    envelope_kind: OpenRouterWireEnvelopeKindV1
    source_evidence_ids: Tuple[str, ...]
    source_fact_ids: Tuple[str, ...]
    required_official_paths: Tuple[str, ...]
    provenance_rule: str = Field(min_length=1)
    status: OpenRouterWireEvidenceStatusV1
    limitation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireFixtureBlueprintV1":
        if self.status is OpenRouterWireEvidenceStatusV1.ESTABLISHED and (
            not self.source_evidence_ids
            or not self.source_fact_ids
            or not self.required_official_paths
        ):
            raise ContractValidationError("established fixture blueprint lacks provenance")
        expected = stable_contract_id(
            "szorwirefixtureblueprintv1",
            self.model_dump(mode="json", exclude={"fixture_blueprint_id"}),
        )
        if self.fixture_blueprint_id not in (None, expected):
            raise ContractValidationError("fixture blueprint ID mismatch")
        object.__setattr__(self, "fixture_blueprint_id", expected)
        return self


class OpenRouterWireRelationshipAssessmentV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_RELATIONSHIP_ASSESSMENT_SCHEMA_V1
    ] = OPENROUTER_WIRE_RELATIONSHIP_ASSESSMENT_SCHEMA_V1
    assessment_id: Optional[str] = None
    relationship: OpenRouterWireRelationshipV1
    status: OpenRouterWireEvidenceStatusV1
    source_evidence_ids: Tuple[str, ...] = ()
    source_fact_ids: Tuple[str, ...] = ()
    mapping_ids: Tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRelationshipAssessmentV1":
        if self.status is OpenRouterWireEvidenceStatusV1.ESTABLISHED and (
            not self.source_evidence_ids or not self.source_fact_ids
        ):
            raise ContractValidationError("established relationship lacks evidence")
        expected = stable_contract_id(
            "szorwirerelationshipv1",
            self.model_dump(mode="json", exclude={"assessment_id"}),
        )
        if self.assessment_id not in (None, expected):
            raise ContractValidationError("relationship assessment ID mismatch")
        object.__setattr__(self, "assessment_id", expected)
        return self


class OpenRouterWireSpecificationManifestV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_SPECIFICATION_MANIFEST_SCHEMA_V1
    ] = OPENROUTER_WIRE_SPECIFICATION_MANIFEST_SCHEMA_V1
    manifest_id: Optional[str] = None
    predecessor_manifest_v0_id: Literal[
        PREDECESSOR_MANIFEST_V0_ID
    ] = PREDECESSOR_MANIFEST_V0_ID
    predecessor_manifest_v0_file_sha256: Literal[
        PREDECESSOR_MANIFEST_V0_FILE_SHA256
    ] = PREDECESSOR_MANIFEST_V0_FILE_SHA256
    sealed_route_controls_v1_artifact_id: Literal[
        SEALED_ROUTE_CONTROLS_V1_ARTIFACT_ID
    ] = SEALED_ROUTE_CONTROLS_V1_ARTIFACT_ID
    sealed_route_controls_v1_sha256: Literal[
        SEALED_ROUTE_CONTROLS_V1_SHA256
    ] = SEALED_ROUTE_CONTROLS_V1_SHA256
    source_plan_id: Literal[
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    ] = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    retrieval_log_id: str
    retrieval_log_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_evidence_records: Tuple[OpenRouterWireSourceEvidenceRecordV1, ...]
    fact_records: Tuple[OpenRouterWireFactRecordV1, ...] = ()
    mapping_records: Tuple[OpenRouterWireMappingRecordV1, ...] = ()
    fixture_blueprints: Tuple[OpenRouterWireFixtureBlueprintV1, ...] = ()
    relationship_assessments: Tuple[OpenRouterWireRelationshipAssessmentV1, ...]
    provider_granularity: OpenRouterWireProviderGranularityV1
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    drift_policy: Literal[
        "SNAPSHOT_ONLY_REVALIDATE_BEFORE_FUTURE_AUTHORIZATION_FAIL_CLOSED_ON_DRIFT"
    ] = "SNAPSHOT_ONLY_REVALIDATE_BEFORE_FUTURE_AUTHORIZATION_FAIL_CLOSED_ON_DRIFT"
    authenticated_api_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    paid_requests: Literal[0] = 0
    ced_runtime_tool_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireSpecificationManifestV1":
        expected_keys = tuple(
            record.source_key
            for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
        )
        if tuple(item.source_key for item in self.source_evidence_records) != expected_keys:
            raise ContractValidationError("manifest sources do not follow frozen plan order")
        if len(self.source_evidence_records) != len(expected_keys):
            raise ContractValidationError("manifest does not cover the frozen source plan")
        if tuple(item.relationship for item in self.relationship_assessments) != (
            MANDATORY_RELATIONSHIPS_V1
        ):
            raise ContractValidationError("manifest relationship registry is incomplete")
        if len({item.fact_id for item in self.fact_records}) != len(self.fact_records):
            raise ContractValidationError("manifest fact IDs are duplicated")
        if len({item.mapping_id for item in self.mapping_records}) != len(self.mapping_records):
            raise ContractValidationError("manifest mapping IDs are duplicated")
        expected = stable_contract_id(
            "szorwirespecmanifestv1",
            self.model_dump(mode="json", exclude={"manifest_id"}),
        )
        if self.manifest_id not in (None, expected):
            raise ContractValidationError("wire specification manifest ID mismatch")
        object.__setattr__(self, "manifest_id", expected)
        return self


class OpenRouterWireSufficiencyThresholdsV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_SCHEMA_V1
    ] = OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_SCHEMA_V1
    thresholds_id: Optional[str] = None
    required_source_count: Literal[6] = 6
    required_retained_source_count: Literal[6] = 6
    required_relationship_count: Literal[14] = 14
    required_established_relationship_count: Literal[14] = 14
    maximum_failed_source_count: Literal[0] = 0
    maximum_not_established_relationship_count: Literal[0] = 0
    maximum_assumption_based_mapping_count: Literal[0] = 0
    require_exact_endpoint_response_identity: Literal[True] = True
    require_actual_served_model_identity: Literal[True] = True

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireSufficiencyThresholdsV1":
        expected = stable_contract_id(
            "szorwiresufficiencythresholdsv1",
            self.model_dump(mode="json", exclude={"thresholds_id"}),
        )
        if self.thresholds_id not in (None, expected):
            raise ContractValidationError("sufficiency thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1 = (
    OpenRouterWireSufficiencyThresholdsV1()
)


class OpenRouterWireSufficiencyMetricsV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_SUFFICIENCY_METRICS_SCHEMA_V1
    ] = OPENROUTER_WIRE_SUFFICIENCY_METRICS_SCHEMA_V1
    metrics_id: Optional[str] = None
    source_count: int = Field(ge=0)
    retained_source_count: int = Field(ge=0)
    failed_source_count: int = Field(ge=0)
    inspectable_source_count: int = Field(ge=0)
    fact_count: int = Field(ge=0)
    mapping_count: int = Field(ge=0)
    fixture_blueprint_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    established_relationship_count: int = Field(ge=0)
    not_established_relationship_count: int = Field(ge=0)
    assumption_based_mapping_count: int = Field(ge=0)
    exact_endpoint_response_identity_established: bool
    actual_served_model_identity_established: bool
    all_thresholds_pass: bool
    failure_reasons: Tuple[str, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireSufficiencyMetricsV1":
        if self.retained_source_count + self.failed_source_count != self.source_count:
            raise ContractValidationError("source metrics do not partition the manifest")
        if self.established_relationship_count + self.not_established_relationship_count != self.relationship_count:
            raise ContractValidationError("relationship metrics do not partition the manifest")
        if self.all_thresholds_pass == bool(self.failure_reasons):
            raise ContractValidationError("sufficiency pass flag contradicts failure reasons")
        expected = stable_contract_id(
            "szorwiresufficiencymetricsv1",
            self.model_dump(mode="json", exclude={"metrics_id"}),
        )
        if self.metrics_id not in (None, expected):
            raise ContractValidationError("sufficiency metrics ID mismatch")
        object.__setattr__(self, "metrics_id", expected)
        return self


class OpenRouterWireManifestValidationV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_MANIFEST_VALIDATION_SCHEMA_V1
    ] = OPENROUTER_WIRE_MANIFEST_VALIDATION_SCHEMA_V1
    validation_id: Optional[str] = None
    manifest_id: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_log_id: str
    retrieval_log_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    thresholds_id: Literal[
        FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1.thresholds_id
    ] = FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1.thresholds_id
    metrics: OpenRouterWireSufficiencyMetricsV1
    hypothesis_status: OpenRouterWireHypothesisStatusV1
    external_document_fetches: int = Field(ge=0, le=6)
    authenticated_api_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    paid_requests: Literal[0] = 0
    ced_runtime_tool_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireManifestValidationV1":
        expected_status = (
            OpenRouterWireHypothesisStatusV1.SUPPORTED
            if self.metrics.all_thresholds_pass
            else OpenRouterWireHypothesisStatusV1.FALSIFIED
        )
        if self.hypothesis_status is not expected_status:
            raise ContractValidationError("validation status contradicts sufficiency metrics")
        expected = stable_contract_id(
            "szorwiremanifestvalidationv1",
            self.model_dump(mode="json", exclude={"validation_id"}),
        )
        if self.validation_id not in (None, expected):
            raise ContractValidationError("manifest validation ID mismatch")
        object.__setattr__(self, "validation_id", expected)
        return self


class OpenRouterWireManifestRevalidationV1(_FrozenManifestContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_MANIFEST_REVALIDATION_SCHEMA_V1
    ] = OPENROUTER_WIRE_MANIFEST_REVALIDATION_SCHEMA_V1
    revalidation_id: Optional[str] = None
    source_manifest_id: str
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recomputed_manifest_id: str
    recomputed_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_validation_id: str
    source_validation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recomputed_validation_id: str
    recomputed_validation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: Literal[True] = True
    manifest_id_equality: Literal[True] = True
    validation_result_equality: Literal[True] = True
    manifest_byte_identity: Literal[True] = True
    validation_byte_identity: Literal[True] = True
    documentation_fetches: Literal[0] = 0
    authenticated_api_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    paid_requests: Literal[0] = 0
    ced_runtime_tool_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireManifestRevalidationV1":
        if (
            self.source_manifest_id != self.recomputed_manifest_id
            or self.source_manifest_sha256 != self.recomputed_manifest_sha256
            or self.source_validation_id != self.recomputed_validation_id
            or self.source_validation_sha256 != self.recomputed_validation_sha256
        ):
            raise ContractValidationError("manifest revalidation equality is false")
        expected = stable_contract_id(
            "szorwiremanifestrevalidationv1",
            self.model_dump(mode="json", exclude={"revalidation_id"}),
        )
        if self.revalidation_id not in (None, expected):
            raise ContractValidationError("manifest revalidation ID mismatch")
        object.__setattr__(self, "revalidation_id", expected)
        return self


def sha256_bytes_v1(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def render_contract_v1(value: BaseModel) -> bytes:
    return (canonical_json(value.model_dump(mode="json")) + "\n").encode("utf-8")


def build_source_evidence_records_v1(
    retrieval_log: OpenRouterWireRetrievalLogV1,
) -> Tuple[OpenRouterWireSourceEvidenceRecordV1, ...]:
    snapshots_by_id = {
        snapshot.snapshot_id: snapshot for snapshot in retrieval_log.snapshots
    }
    records: list[OpenRouterWireSourceEvidenceRecordV1] = []
    plan_by_id = {
        record.plan_record_id: record
        for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
    }
    for event in retrieval_log.events:
        plan = plan_by_id[event.plan_record_id]
        snapshot = snapshots_by_id.get(event.retained_snapshot_id)
        records.append(
            OpenRouterWireSourceEvidenceRecordV1(
                source_key=event.source_key,
                plan_record_id=event.plan_record_id,
                canonical_public_locator=plan.canonical_public_locator,
                retrieval_event_id=event.event_id or "",
                retrieval_status=event.status,
                retrieval_error_code=(
                    event.error_code.value if event.error_code is not None else None
                ),
                retained_snapshot_id=(snapshot.snapshot_id if snapshot else None),
                raw_source_path=(
                    snapshot.retained_raw_evidence_path if snapshot else None
                ),
                raw_source_byte_length=(
                    snapshot.raw_source_byte_length if snapshot else None
                ),
                raw_source_sha256=(snapshot.raw_source_sha256 if snapshot else None),
                canonical_extract_path=(
                    snapshot.retained_canonical_extract_path if snapshot else None
                ),
                canonical_extract_byte_length=(
                    snapshot.canonical_extract_byte_length if snapshot else None
                ),
                canonical_extract_sha256=(
                    snapshot.canonical_extract_sha256 if snapshot else None
                ),
                source_inspectable=snapshot is not None,
            )
        )
    return tuple(records)


def build_unestablished_relationship_assessments_v1(
    source_records: Tuple[OpenRouterWireSourceEvidenceRecordV1, ...],
) -> Tuple[OpenRouterWireRelationshipAssessmentV1, ...]:
    unavailable = tuple(
        item.source_key
        for item in source_records
        if item.retrieval_status is not OpenRouterWireRetrievalStatusV1.RETAINED
    )
    reason = (
        "OFFICIAL_SOURCE_SNAPSHOTS_UNAVAILABLE: " + ",".join(unavailable)
        if unavailable
        else "MANDATORY_TYPED_FACTS_AND_MAPPINGS_NOT_ESTABLISHED"
    )
    return tuple(
        OpenRouterWireRelationshipAssessmentV1(
            relationship=relationship,
            status=OpenRouterWireEvidenceStatusV1.NOT_ESTABLISHED,
            reason=reason,
        )
        for relationship in MANDATORY_RELATIONSHIPS_V1
    )


def build_openrouter_wire_specification_manifest_v1(
    *,
    retrieval_log: OpenRouterWireRetrievalLogV1,
    retrieval_log_sha256: str,
    fact_records: Tuple[OpenRouterWireFactRecordV1, ...] = (),
    mapping_records: Tuple[OpenRouterWireMappingRecordV1, ...] = (),
    fixture_blueprints: Tuple[OpenRouterWireFixtureBlueprintV1, ...] = (),
    relationship_assessments: Optional[
        Tuple[OpenRouterWireRelationshipAssessmentV1, ...]
    ] = None,
    provider_granularity: OpenRouterWireProviderGranularityV1 = (
        OpenRouterWireProviderGranularityV1.UNKNOWN
    ),
) -> OpenRouterWireSpecificationManifestV1:
    source_records = build_source_evidence_records_v1(retrieval_log)
    assessments = relationship_assessments or (
        build_unestablished_relationship_assessments_v1(source_records)
    )
    return OpenRouterWireSpecificationManifestV1(
        retrieval_log_id=retrieval_log.retrieval_log_id or "",
        retrieval_log_sha256=retrieval_log_sha256,
        source_evidence_records=source_records,
        fact_records=fact_records,
        mapping_records=mapping_records,
        fixture_blueprints=fixture_blueprints,
        relationship_assessments=assessments,
        provider_granularity=provider_granularity,
    )


def evaluate_openrouter_wire_manifest_sufficiency_v1(
    manifest: OpenRouterWireSpecificationManifestV1,
) -> OpenRouterWireSufficiencyMetricsV1:
    thresholds = FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1
    source_count = len(manifest.source_evidence_records)
    retained_source_count = sum(
        item.retrieval_status is OpenRouterWireRetrievalStatusV1.RETAINED
        for item in manifest.source_evidence_records
    )
    failed_source_count = source_count - retained_source_count
    inspectable_source_count = sum(
        item.source_inspectable for item in manifest.source_evidence_records
    )
    established_relationship_count = sum(
        item.status is OpenRouterWireEvidenceStatusV1.ESTABLISHED
        for item in manifest.relationship_assessments
    )
    not_established_relationship_count = sum(
        item.status is not OpenRouterWireEvidenceStatusV1.ESTABLISHED
        for item in manifest.relationship_assessments
    )
    assumption_based_mapping_count = sum(
        item.strength is OpenRouterWireEvidenceStrengthV1.NOT_ESTABLISHED
        or not item.lossless
        for item in manifest.mapping_records
    )
    assessment_by_relationship = {
        item.relationship: item for item in manifest.relationship_assessments
    }
    exact_endpoint = (
        assessment_by_relationship[
            OpenRouterWireRelationshipV1.EXACT_ENDPOINT_RESPONSE_IDENTITY
        ].status
        is OpenRouterWireEvidenceStatusV1.ESTABLISHED
    )
    actual_model = (
        assessment_by_relationship[
            OpenRouterWireRelationshipV1.ACTUAL_SERVED_MODEL_IDENTITY
        ].status
        is OpenRouterWireEvidenceStatusV1.ESTABLISHED
    )
    failures: list[str] = []
    if source_count != thresholds.required_source_count:
        failures.append("SOURCE_COUNT_MISMATCH")
    if retained_source_count != thresholds.required_retained_source_count:
        failures.append("OFFICIAL_SOURCE_SNAPSHOTS_INCOMPLETE")
    if failed_source_count > thresholds.maximum_failed_source_count:
        failures.append("OFFICIAL_DOCUMENT_RETRIEVAL_FAILED")
    if inspectable_source_count != thresholds.required_retained_source_count:
        failures.append("INSPECTABLE_SOURCE_BYTES_INCOMPLETE")
    if len(manifest.relationship_assessments) != thresholds.required_relationship_count:
        failures.append("RELATIONSHIP_REGISTRY_INCOMPLETE")
    if established_relationship_count != thresholds.required_established_relationship_count:
        failures.append("MANDATORY_RELATIONSHIPS_NOT_ESTABLISHED")
    if not_established_relationship_count > thresholds.maximum_not_established_relationship_count:
        failures.append("NOT_ESTABLISHED_RELATIONSHIPS_PRESENT")
    if assumption_based_mapping_count > thresholds.maximum_assumption_based_mapping_count:
        failures.append("UNSUPPORTED_OR_LOSSY_MAPPINGS_PRESENT")
    if thresholds.require_exact_endpoint_response_identity and not exact_endpoint:
        failures.append("EXACT_ENDPOINT_RESPONSE_IDENTITY_NOT_ESTABLISHED")
    if thresholds.require_actual_served_model_identity and not actual_model:
        failures.append("ACTUAL_SERVED_MODEL_IDENTITY_NOT_ESTABLISHED")
    return OpenRouterWireSufficiencyMetricsV1(
        source_count=source_count,
        retained_source_count=retained_source_count,
        failed_source_count=failed_source_count,
        inspectable_source_count=inspectable_source_count,
        fact_count=len(manifest.fact_records),
        mapping_count=len(manifest.mapping_records),
        fixture_blueprint_count=len(manifest.fixture_blueprints),
        relationship_count=len(manifest.relationship_assessments),
        established_relationship_count=established_relationship_count,
        not_established_relationship_count=not_established_relationship_count,
        assumption_based_mapping_count=assumption_based_mapping_count,
        exact_endpoint_response_identity_established=exact_endpoint,
        actual_served_model_identity_established=actual_model,
        all_thresholds_pass=not failures,
        failure_reasons=tuple(failures),
    )


def build_openrouter_wire_manifest_validation_v1(
    *,
    manifest: OpenRouterWireSpecificationManifestV1,
    manifest_sha256: str,
    retrieval_log: OpenRouterWireRetrievalLogV1,
) -> OpenRouterWireManifestValidationV1:
    metrics = evaluate_openrouter_wire_manifest_sufficiency_v1(manifest)
    status = (
        OpenRouterWireHypothesisStatusV1.SUPPORTED
        if metrics.all_thresholds_pass
        else OpenRouterWireHypothesisStatusV1.FALSIFIED
    )
    return OpenRouterWireManifestValidationV1(
        manifest_id=manifest.manifest_id or "",
        manifest_sha256=manifest_sha256,
        retrieval_log_id=retrieval_log.retrieval_log_id or "",
        retrieval_log_sha256=manifest.retrieval_log_sha256,
        metrics=metrics,
        hypothesis_status=status,
        external_document_fetches=retrieval_log.official_public_document_fetches,
    )


__all__ = [
    "FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1",
    "MANDATORY_RELATIONSHIPS_V1",
    "OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1",
    "OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1",
    "OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1",
    "OpenRouterWireEnvelopeKindV1",
    "OpenRouterWireEvidenceStatusV1",
    "OpenRouterWireEvidenceStrengthV1",
    "OpenRouterWireFactRecordV1",
    "OpenRouterWireFixtureBlueprintV1",
    "OpenRouterWireHypothesisStatusV1",
    "OpenRouterWireJsonTypeV1",
    "OpenRouterWireManifestRevalidationV1",
    "OpenRouterWireManifestValidationV1",
    "OpenRouterWireMappingRecordV1",
    "OpenRouterWireNullabilityV1",
    "OpenRouterWirePresenceRuleV1",
    "OpenRouterWireProviderGranularityV1",
    "OpenRouterWireRelationshipAssessmentV1",
    "OpenRouterWireRelationshipV1",
    "OpenRouterWireSourceEvidenceRecordV1",
    "OpenRouterWireSpecificationManifestV1",
    "OpenRouterWireSufficiencyMetricsV1",
    "OpenRouterWireSufficiencyThresholdsV1",
    "build_openrouter_wire_manifest_validation_v1",
    "build_openrouter_wire_specification_manifest_v1",
    "build_source_evidence_records_v1",
    "evaluate_openrouter_wire_manifest_sufficiency_v1",
    "render_contract_v1",
    "sha256_bytes_v1",
]

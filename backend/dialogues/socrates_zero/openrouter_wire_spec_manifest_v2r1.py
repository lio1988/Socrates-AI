"""Canonical OpenRouter wire-specification evidence manifest v2r1.

This module is offline and import-inert.  It defines one content-addressed
schema for six already-retained official OpenRouter source snapshots and for
the typed facts/mappings derived from them.  It performs no network access,
provider calls, credential access, parser execution, or CED mutation.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id

UPSTREAM_REPOSITORY_V2R1 = "OpenRouterTeam/docs"
UPSTREAM_COMMIT_V2R1 = "4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db"
BASE_BRANCH_HEAD_V2R1 = "a37e6c0068e3132ca49128295a5ef8453f91592c"
PREDECESSOR_MANIFEST_V1_ID = "szorwirespecmanifestv1_bb4919b28f1913de4484c54dadbece8f0e16876ce233aa12eaaf00eb506a3a41"
PREDECESSOR_VALIDATION_V1_ID = "szorwiremanifestvalidationv1_9a30a408ff6c4537319cfc8b1e3c62fec24e783f2d52db6a498612d10464fee2"
HISTORICAL_INVALID_V2_HEAD = "2bba0aa1ffac16d9c302cfc5e59431b0371a4817"

SOURCE_SCHEMA_V2R1 = "socrateszero-openrouter-wire-spec-source/v2r1"
FACT_SCHEMA_V2R1 = "socrateszero-openrouter-wire-spec-fact/v2r1"
MAPPING_SCHEMA_V2R1 = "socrateszero-openrouter-wire-spec-mapping/v2r1"
RELATIONSHIP_SCHEMA_V2R1 = "socrateszero-openrouter-wire-relationship/v2r1"
MANIFEST_SCHEMA_V2R1 = "socrateszero-openrouter-wire-specification-manifest/v2r1"
VALIDATION_SCHEMA_V2R1 = "socrateszero-openrouter-wire-specification-validation/v2r1"
REVALIDATION_SCHEMA_V2R1 = "socrateszero-openrouter-wire-specification-revalidation/v2r1"

BRANCH_DOC_ROOT_V2R1 = "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1"
SOURCE_ROOT_V2R1 = f"{BRANCH_DOC_ROOT_V2R1}/evidence/sources"
MANIFEST_RELATIVE_PATH_V2R1 = f"{BRANCH_DOC_ROOT_V2R1}/evidence/openrouter_official_wire_specification_manifest_v2r1.json"
VALIDATION_RELATIVE_PATH_V2R1 = f"{BRANCH_DOC_ROOT_V2R1}/artifacts/openrouter_wire_specification_manifest_validation_v2r1.json"
REVALIDATION_RELATIVE_PATH_V2R1 = f"{BRANCH_DOC_ROOT_V2R1}/artifacts/openrouter_wire_specification_manifest_revalidation_v2r1.json"


class _FrozenV2R1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceStrengthV2R1(str, Enum):
    DIRECTLY_DOCUMENTED = "DIRECTLY_DOCUMENTED"
    DERIVED_LOSSLESSLY = "DERIVED_LOSSLESSLY"


class EnvelopeKindV2R1(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CACHE = "CACHE"
    REQUEST = "REQUEST"
    CROSS_CUTTING = "CROSS_CUTTING"


class JsonTypeV2R1(str, Enum):
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    UNION = "UNION"


class PresenceV2R1(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"


class NullabilityV2R1(str, Enum):
    NON_NULL = "NON_NULL"
    NULLABLE = "NULLABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RelationshipStatusV2R1(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    UNAVAILABLE_BY_DOCUMENTED_CONTRACT = "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"


class ProviderGranularityV2R1(str, Enum):
    HUMAN_DISPLAY_NAME = "HUMAN_DISPLAY_NAME"
    UNKNOWN = "UNKNOWN"


class HypothesisStatusV2R1(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class RelationshipV2R1(str, Enum):
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


MANDATORY_RELATIONSHIPS_V2R1: Tuple[RelationshipV2R1, ...] = tuple(RelationshipV2R1)


def _identify(model: BaseModel, field: str, prefix: str) -> str:
    payload = model.model_dump(mode="json", exclude={field})
    return stable_contract_id(prefix, payload)


class SourceRecordV2R1(_FrozenV2R1):
    schema_version: Literal[SOURCE_SCHEMA_V2R1] = SOURCE_SCHEMA_V2R1
    source_id: Optional[str] = None
    source_key: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    repository: Literal[UPSTREAM_REPOSITORY_V2R1] = UPSTREAM_REPOSITORY_V2R1
    commit_sha: Literal[UPSTREAM_COMMIT_V2R1] = UPSTREAM_COMMIT_V2R1
    upstream_path: str = Field(min_length=1)
    evidence_path: str = Field(min_length=1)
    git_blob_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1)
    source_class: str = Field(min_length=1)
    limitations: Tuple[str, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "SourceRecordV2R1":
        for value in (self.upstream_path, self.evidence_path):
            p = PurePosixPath(value)
            if p.is_absolute() or ".." in p.parts or "\\" in value:
                raise ContractValidationError("source path is not canonical repo-relative")
        expected = _identify(self, "source_id", "szorwiresourcev2r1")
        if self.source_id not in (None, expected):
            raise ContractValidationError("source record ID mismatch")
        object.__setattr__(self, "source_id", expected)
        return self


class FactRecordV2R1(_FrozenV2R1):
    schema_version: Literal[FACT_SCHEMA_V2R1] = FACT_SCHEMA_V2R1
    fact_id: Optional[str] = None
    diagnostic_label: str = Field(min_length=1)
    official_path: str = Field(min_length=1)
    envelope_kind: EnvelopeKindV2R1
    json_type: JsonTypeV2R1
    presence: PresenceV2R1
    nullability: NullabilityV2R1
    cardinality: str = Field(min_length=1)
    semantic_meaning: str = Field(min_length=1)
    source_ids: Tuple[str, ...]
    source_anchors: Tuple[str, ...]
    strength: EvidenceStrengthV2R1
    limitations: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "FactRecordV2R1":
        if not self.source_ids or not self.source_anchors:
            raise ContractValidationError("fact record lacks source provenance")
        expected = _identify(self, "fact_id", "szorwirefactv2r1")
        if self.fact_id not in (None, expected):
            raise ContractValidationError("fact record ID mismatch")
        object.__setattr__(self, "fact_id", expected)
        return self


class MappingRecordV2R1(_FrozenV2R1):
    schema_version: Literal[MAPPING_SCHEMA_V2R1] = MAPPING_SCHEMA_V2R1
    mapping_id: Optional[str] = None
    official_path: str = Field(min_length=1)
    internal_target: str = Field(min_length=1)
    transformation: str = Field(min_length=1)
    lossless: Literal[True] = True
    missing_behavior: str = Field(min_length=1)
    invalid_type_behavior: str = Field(min_length=1)
    unknown_field_behavior: str = Field(min_length=1)
    authority_scope: str = Field(min_length=1)
    fact_ids: Tuple[str, ...]
    strength: EvidenceStrengthV2R1

    @model_validator(mode="after")
    def validate_and_identify(self) -> "MappingRecordV2R1":
        if not self.fact_ids:
            raise ContractValidationError("mapping record lacks fact provenance")
        if self.strength not in (
            EvidenceStrengthV2R1.DIRECTLY_DOCUMENTED,
            EvidenceStrengthV2R1.DERIVED_LOSSLESSLY,
        ):
            raise ContractValidationError("mapping strength is not authoritative")
        expected = _identify(self, "mapping_id", "szorwiremappingv2r1")
        if self.mapping_id not in (None, expected):
            raise ContractValidationError("mapping record ID mismatch")
        object.__setattr__(self, "mapping_id", expected)
        return self


class RelationshipAssessmentV2R1(_FrozenV2R1):
    schema_version: Literal[RELATIONSHIP_SCHEMA_V2R1] = RELATIONSHIP_SCHEMA_V2R1
    assessment_id: Optional[str] = None
    relationship: RelationshipV2R1
    status: RelationshipStatusV2R1
    source_ids: Tuple[str, ...]
    fact_ids: Tuple[str, ...] = ()
    mapping_ids: Tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "RelationshipAssessmentV2R1":
        if not self.source_ids:
            raise ContractValidationError("relationship assessment lacks provenance")
        expected = _identify(self, "assessment_id", "szorwirerelationshipv2r1")
        if self.assessment_id not in (None, expected):
            raise ContractValidationError("relationship assessment ID mismatch")
        object.__setattr__(self, "assessment_id", expected)
        return self


class ManifestV2R1(_FrozenV2R1):
    schema_version: Literal[MANIFEST_SCHEMA_V2R1] = MANIFEST_SCHEMA_V2R1
    manifest_id: Optional[str] = None
    predecessor_manifest_id: Literal[PREDECESSOR_MANIFEST_V1_ID] = PREDECESSOR_MANIFEST_V1_ID
    predecessor_validation_id: Literal[PREDECESSOR_VALIDATION_V1_ID] = PREDECESSOR_VALIDATION_V1_ID
    base_branch_head: Literal[BASE_BRANCH_HEAD_V2R1] = BASE_BRANCH_HEAD_V2R1
    historical_invalid_v2_head: Literal[HISTORICAL_INVALID_V2_HEAD] = HISTORICAL_INVALID_V2_HEAD
    official_repository: Literal[UPSTREAM_REPOSITORY_V2R1] = UPSTREAM_REPOSITORY_V2R1
    official_commit: Literal[UPSTREAM_COMMIT_V2R1] = UPSTREAM_COMMIT_V2R1
    source_records: Tuple[SourceRecordV2R1, ...]
    fact_records: Tuple[FactRecordV2R1, ...]
    mapping_records: Tuple[MappingRecordV2R1, ...]
    relationship_assessments: Tuple[RelationshipAssessmentV2R1, ...]
    provider_granularity: ProviderGranularityV2R1
    exact_endpoint_request_intent: Literal["ESTABLISHED"] = "ESTABLISHED"
    exact_endpoint_response_identity: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    actual_served_model_identity: Literal["ESTABLISHED"] = "ESTABLISHED"
    assumption_based_authoritative_mapping_count: Literal[0] = 0
    repository_convention_authoritative_mapping_count: Literal[0] = 0
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_total_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"

    @model_validator(mode="after")
    def validate_and_identify(self) -> "ManifestV2R1":
        if len(self.source_records) != 6:
            raise ContractValidationError("manifest must contain exactly six sources")
        source_ids = [item.source_id for item in self.source_records]
        if len(set(source_ids)) != len(source_ids):
            raise ContractValidationError("duplicate source record")
        if len({item.upstream_path for item in self.source_records}) != len(self.source_records):
            raise ContractValidationError("duplicate source path")
        source_set = set(source_ids)
        fact_ids = [item.fact_id for item in self.fact_records]
        if len(set(fact_ids)) != len(fact_ids):
            raise ContractValidationError("duplicate fact record")
        for fact in self.fact_records:
            if not set(fact.source_ids).issubset(source_set):
                raise ContractValidationError("fact has dangling source reference")
        fact_set = set(fact_ids)
        mapping_ids = [item.mapping_id for item in self.mapping_records]
        if len(set(mapping_ids)) != len(mapping_ids):
            raise ContractValidationError("duplicate mapping record")
        for mapping in self.mapping_records:
            if not set(mapping.fact_ids).issubset(fact_set):
                raise ContractValidationError("mapping has dangling fact reference")
        mapping_set = set(mapping_ids)
        relationships = [item.relationship for item in self.relationship_assessments]
        if tuple(relationships) != MANDATORY_RELATIONSHIPS_V2R1:
            raise ContractValidationError("relationship registry is incomplete or out of order")
        for assessment in self.relationship_assessments:
            if not set(assessment.source_ids).issubset(source_set):
                raise ContractValidationError("relationship has dangling source reference")
            if not set(assessment.fact_ids).issubset(fact_set):
                raise ContractValidationError("relationship has dangling fact reference")
            if not set(assessment.mapping_ids).issubset(mapping_set):
                raise ContractValidationError("relationship has dangling mapping reference")
        exact_endpoint = next(
            item for item in self.relationship_assessments
            if item.relationship is RelationshipV2R1.EXACT_ENDPOINT_RESPONSE_IDENTITY
        )
        if exact_endpoint.status is not RelationshipStatusV2R1.UNAVAILABLE_BY_DOCUMENTED_CONTRACT:
            raise ContractValidationError("exact endpoint response identity is overclaimed")
        actual_model = next(
            item for item in self.relationship_assessments
            if item.relationship is RelationshipV2R1.ACTUAL_SERVED_MODEL_IDENTITY
        )
        if actual_model.status is not RelationshipStatusV2R1.ESTABLISHED:
            raise ContractValidationError("actual served model identity is not established")
        expected = _identify(self, "manifest_id", "szorwirespecmanifestv2r1")
        if self.manifest_id not in (None, expected):
            raise ContractValidationError("manifest ID mismatch")
        object.__setattr__(self, "manifest_id", expected)
        return self


class ValidationV2R1(_FrozenV2R1):
    schema_version: Literal[VALIDATION_SCHEMA_V2R1] = VALIDATION_SCHEMA_V2R1
    validation_id: Optional[str] = None
    manifest_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_count: int = Field(ge=0)
    fact_count: int = Field(ge=0)
    mapping_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    established_relationship_count: int = Field(ge=0)
    documented_unavailable_relationship_count: int = Field(ge=0)
    source_snapshot_integrity: bool
    reference_integrity: bool
    authoritative_mapping_integrity: bool
    exact_endpoint_firewall: bool
    actual_model_authority: bool
    hypothesis_status: HypothesisStatusV2R1
    failure_reasons: Tuple[str, ...]
    authenticated_api_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    ced_application_invocations: Literal[0] = 0

    @model_validator(mode="after")
    def validate_and_identify(self) -> "ValidationV2R1":
        passed = (
            self.source_count == 6
            and self.relationship_count == len(MANDATORY_RELATIONSHIPS_V2R1)
            and self.source_snapshot_integrity
            and self.reference_integrity
            and self.authoritative_mapping_integrity
            and self.exact_endpoint_firewall
            and self.actual_model_authority
            and not self.failure_reasons
        )
        expected_status = HypothesisStatusV2R1.SUPPORTED if passed else HypothesisStatusV2R1.FALSIFIED
        if self.hypothesis_status is not expected_status:
            raise ContractValidationError("validation hypothesis status mismatch")
        expected = _identify(self, "validation_id", "szorwiremanifestvalidationv2r1")
        if self.validation_id not in (None, expected):
            raise ContractValidationError("validation ID mismatch")
        object.__setattr__(self, "validation_id", expected)
        return self


class RevalidationV2R1(_FrozenV2R1):
    schema_version: Literal[REVALIDATION_SCHEMA_V2R1] = REVALIDATION_SCHEMA_V2R1
    revalidation_id: Optional[str] = None
    source_manifest_id: str
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_validation_id: str
    source_validation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recomputed_manifest_id: str
    recomputed_validation_id: str
    semantic_equality: Literal[True] = True
    manifest_id_equality: Literal[True] = True
    validation_result_equality: Literal[True] = True
    manifest_byte_identity: Literal[True] = True
    validation_byte_identity: Literal[True] = True
    source_refetches: Literal[0] = 0

    @model_validator(mode="after")
    def validate_and_identify(self) -> "RevalidationV2R1":
        if self.source_manifest_id != self.recomputed_manifest_id:
            raise ContractValidationError("manifest identity diverged during revalidation")
        if self.source_validation_id != self.recomputed_validation_id:
            raise ContractValidationError("validation identity diverged during revalidation")
        expected = _identify(self, "revalidation_id", "szorwiremanifestrevalidationv2r1")
        if self.revalidation_id not in (None, expected):
            raise ContractValidationError("revalidation ID mismatch")
        object.__setattr__(self, "revalidation_id", expected)
        return self




def classify_worktree_bytes_against_canonical_v2r1(canonical_bytes: bytes, working_bytes: bytes) -> str:
    """Classify working-tree drift without treating CRLF checkout as content mutation."""
    if working_bytes == canonical_bytes:
        return "NONE"
    if working_bytes.replace(b"\r\n", b"\n") == canonical_bytes.replace(b"\r\n", b"\n"):
        return "CRLF_NORMALIZATION"
    return "CONTENT_MUTATION"

def sha256_bytes_v2r1(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_blob_sha1_v2r1(value: bytes) -> str:
    prefix = f"blob {len(value)}\0".encode("ascii")
    return hashlib.sha1(prefix + value).hexdigest()


def render_contract_v2r1(value: BaseModel) -> bytes:
    return (canonical_json(value.model_dump(mode="json")) + "\n").encode("utf-8")


def _source(
    key: str,
    role: str,
    upstream_path: str,
    filename: str,
    git_blob_sha: str,
    sha256: str,
    byte_length: int,
    source_class: str,
    limitations: Tuple[str, ...],
) -> SourceRecordV2R1:
    return SourceRecordV2R1(
        source_key=key,
        source_role=role,
        upstream_path=upstream_path,
        evidence_path=f"{SOURCE_ROOT_V2R1}/{filename}",
        git_blob_sha=git_blob_sha,
        sha256=sha256,
        byte_length=byte_length,
        source_class=source_class,
        limitations=limitations,
    )


SOURCES_V2R1: Tuple[SourceRecordV2R1, ...] = (
    _source("openapi", "machine-readable response schema", "openapi/openapi.yaml", "openapi.yaml", "62ebcd1e1ff13d671096954daee7d2229cd42238", "bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713", 1397709, "OFFICIAL_OPENAPI_SCHEMA", ("Behavioral semantics may also require official prose documentation.",)),
    _source("router_metadata", "router metadata behavior", "guides/features/router-metadata.mdx", "router-metadata.mdx", "224633ac1dc7b8e9b7dab36f0d6458afd85a7309", "4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6", 14038, "OFFICIAL_ROUTER_METADATA_DOCUMENTATION", ("Exact selected endpoint slug is not supplied by the documented response metadata.",)),
    _source("api_overview", "normalized response envelope", "api_reference/overview.mdx", "api-reference-overview.mdx", "72ec6e804f20127b16a83abb16a312ff8c56ce41", "8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e", 15698, "OFFICIAL_API_REFERENCE", ("OpenRouter normalizes response schemas across providers.",)),
    _source("response_cache", "response cache headers and behavior", "guides/features/response-caching.mdx", "response-caching.mdx", "437dc6abab221bb7bdcfbe6c4d3bdcb37df84b90", "89e423514f98c2bdc5e288d5ea17159e78df29ea6ff56ea82cd8b68da1302f3e", 16643, "OFFICIAL_RESPONSE_CACHE_DOCUMENTATION", ("Cache metadata is separate from provider-side prompt caching.",)),
    _source("provider_routing", "request-side provider routing controls", "guides/routing/provider-selection.mdx", "provider-selection.mdx", "7451e2ff9c5d898d642c9e1e6a516d1f3904ad01", "2781071f570c53040c0c01a9f1840097a43e6032ebd4e3d9ab2dfbeb01bb2252", 61399, "OFFICIAL_PROVIDER_ROUTING_DOCUMENTATION", ("Request selector slugs are request intent, not response attestation.",)),
    _source("model_fallbacks", "model fallback behavior", "guides/routing/model-fallbacks.mdx", "model-fallbacks.mdx", "473c202c4420bbd917f9d65452a3b8240fc00cbf", "6d77e3242812a2b669bf22f9c9c6ac59a5d838906271d1593b2fff864c6550c1", 6002, "OFFICIAL_MODEL_FALLBACK_DOCUMENTATION", ("The response model identifies the model ultimately used, not an exact endpoint.",)),
)

_SOURCE_BY_KEY = {item.source_key: item for item in SOURCES_V2R1}


def _fact(label: str, path: str, envelope: EnvelopeKindV2R1, kind: JsonTypeV2R1, presence: PresenceV2R1, nullability: NullabilityV2R1, cardinality: str, meaning: str, sources: Tuple[str, ...], anchors: Tuple[str, ...], limitations: str = "None beyond the cited official source scope.") -> FactRecordV2R1:
    return FactRecordV2R1(
        diagnostic_label=label,
        official_path=path,
        envelope_kind=envelope,
        json_type=kind,
        presence=presence,
        nullability=nullability,
        cardinality=cardinality,
        semantic_meaning=meaning,
        source_ids=tuple(_SOURCE_BY_KEY[key].source_id or "" for key in sources),
        source_anchors=anchors,
        strength=EvidenceStrengthV2R1.DIRECTLY_DOCUMENTED,
        limitations=limitations,
    )


FACTS_V2R1: Tuple[FactRecordV2R1, ...] = (
    _fact("success_metadata", "$.openrouter_metadata", EnvelopeKindV2R1.SUCCESS, JsonTypeV2R1.OBJECT, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Opt-in successful responses carry router metadata at top level alongside the response payload.", ("router_metadata",), ("successful responses include an `openrouter_metadata` object alongside",)),
    _fact("error_metadata", "$.openrouter_metadata", EnvelopeKindV2R1.ERROR, JsonTypeV2R1.OBJECT, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Opt-in error responses that have routing state carry router metadata at top level as a sibling of error; 500 and pre-router classes may omit it.", ("router_metadata",), ("**top level** of the error envelope", "Responses with a `500` status")),
    _fact("cache_metadata_absence", "$.openrouter_metadata", EnvelopeKindV2R1.CACHE, JsonTypeV2R1.OBJECT, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NOT_APPLICABLE, "ABSENT_ON_CACHE_HIT", "Response cache hits intentionally omit router metadata.", ("router_metadata",), ("Cache hits never include `openrouter_metadata`",)),
    _fact("requested", "$.openrouter_metadata.requested", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Client-requested model slug or alias.", ("router_metadata", "openapi"), ("`requested`", "requested:")),
    _fact("strategy", "$.openrouter_metadata.strategy", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Routing strategy used by OpenRouter.", ("router_metadata", "openapi"), ("Routing strategy used", "RoutingStrategy:")),
    _fact("region", "$.openrouter_metadata.region", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.UNION, PresenceV2R1.REQUIRED, NullabilityV2R1.NULLABLE, "ONE", "Edge region when available.", ("router_metadata", "openapi"), ("`region`", "type:\n            - 'string'\n            - 'null'")),
    _fact("summary", "$.openrouter_metadata.summary", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Human-readable routing-decision summary.", ("router_metadata", "openapi"), ("Human-readable one-liner", "summary:")),
    _fact("attempt", "$.openrouter_metadata.attempt", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.INTEGER, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "On success, a one-indexed attempt number; on error, zero means no provider reached and values at least one mean attempted providers failed.", ("router_metadata", "openapi"), ("1-indexed attempt number that succeeded", "`attempt` reflects how far the router got")),
    _fact("is_byok", "$.openrouter_metadata.is_byok", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.BOOLEAN, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Whether a Bring-Your-Own-Key provider key was used.", ("router_metadata", "openapi"), ("Whether the request used a Bring-Your-Own-Key", "is_byok:")),
    _fact("endpoints", "$.openrouter_metadata.endpoints", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.OBJECT, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Snapshot of endpoint candidates and selected flags.", ("router_metadata", "openapi"), ("Snapshot of endpoint candidates considered", "EndpointsMetadata:")),
    _fact("params", "$.openrouter_metadata.params", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.OBJECT, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Optional router-level parameters influencing selection.", ("router_metadata", "openapi"), ("Router-level parameters that influenced selection", "RouterParams:")),
    _fact("attempts", "$.openrouter_metadata.attempts", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.ARRAY, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_MORE", "Optional per-attempt provider/model/status details.", ("router_metadata", "openapi"), ("Per-attempt provider/model/status", "RouterAttempt:")),
    _fact("pipeline", "$.openrouter_metadata.pipeline", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.ARRAY, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_MORE", "Optional pipeline stages for plugins that materially affected the request or response.", ("router_metadata", "openapi"), ("`pipeline` array records every plugin that materially affected", "PipelineStage:")),
    _fact("endpoint_total", "$.openrouter_metadata.endpoints.total", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.INTEGER, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Count reported by endpoint metadata.", ("openapi",), ("EndpointsMetadata:", "total:")),
    _fact("endpoint_available", "$.openrouter_metadata.endpoints.available[]", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.ARRAY, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ZERO_OR_MORE", "Endpoint candidate records.", ("openapi",), ("EndpointsMetadata:", "available:")),
    _fact("endpoint_provider", "$.openrouter_metadata.endpoints.available[].provider", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Provider label in an endpoint candidate record.", ("openapi", "router_metadata"), ("provider: 'OpenAI'", "selected provider"), "The documented response value is a broad/display provider label, not an exact endpoint slug."),
    _fact("endpoint_model", "$.openrouter_metadata.endpoints.available[].model", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Model slug in an endpoint candidate record.", ("openapi",), ("model: 'openai/gpt-4o'",)),
    _fact("endpoint_selected", "$.openrouter_metadata.endpoints.available[].selected", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.BOOLEAN, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Whether the endpoint candidate served a successful response; failures mark no endpoint selected.", ("openapi", "router_metadata"), ("selected:", "No endpoint is marked `selected` on failure")),
    _fact("attempt_provider", "$.openrouter_metadata.attempts[].provider", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Provider label for an attempted route.", ("openapi",), ("RouterAttempt:", "provider:")),
    _fact("attempt_model", "$.openrouter_metadata.attempts[].model", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Model for an attempted route.", ("openapi",), ("RouterAttempt:", "model:")),
    _fact("attempt_status", "$.openrouter_metadata.attempts[].status", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.INTEGER, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Integer status recorded for an attempt.", ("openapi",), ("RouterAttempt:", "status:")),
    _fact("pipeline_type", "$.openrouter_metadata.pipeline[].type", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Categorical pipeline stage type.", ("openapi", "router_metadata"), ("PipelineStageType:", "Today's stage types include")),
    _fact("pipeline_name", "$.openrouter_metadata.pipeline[].name", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE_PER_ENTRY", "Pipeline plugin name that disambiguates a stage.", ("openapi", "router_metadata"), ("name:", "match on both `type === 'guardrail'` and `name === 'content-filter'`")),
    _fact("pipeline_data", "$.openrouter_metadata.pipeline[].data", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.OBJECT, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE_PER_ENTRY", "Free-form stage-specific data.", ("openapi",), ("additionalProperties: {}", "data:")),
    _fact("served_model", "$.model", EnvelopeKindV2R1.SUCCESS, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Model in the normalized response; model-fallback documentation states this is the model ultimately used.", ("api_overview", "model_fallbacks"), ("model: string;", "model that was ultimately used")),
    _fact("cache_status", "$headers.X-OpenRouter-Cache-Status", EnvelopeKindV2R1.CACHE, JsonTypeV2R1.STRING, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "HIT or MISS cache attestation header.", ("response_cache",), ("X-OpenRouter-Cache-Status", "HIT` or `MISS")),
    _fact("cache_age", "$headers.X-OpenRouter-Cache-Age", EnvelopeKindV2R1.CACHE, JsonTypeV2R1.INTEGER, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Age of cached response on HIT.", ("response_cache",), ("X-OpenRouter-Cache-Age",)),
    _fact("cache_ttl", "$headers.X-OpenRouter-Cache-TTL", EnvelopeKindV2R1.CACHE, JsonTypeV2R1.INTEGER, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Remaining/full cache TTL depending on HIT/MISS.", ("response_cache",), ("X-OpenRouter-Cache-TTL",)),
    _fact("cache_source", "$headers.X-OpenRouter-Cache-Source-Id", EnvelopeKindV2R1.CACHE, JsonTypeV2R1.STRING, PresenceV2R1.CONDITIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Generation ID that populated the cache entry on HIT.", ("response_cache",), ("X-OpenRouter-Cache-Source-Id",)),
    _fact("generation_id", "$headers.X-Generation-Id", EnvelopeKindV2R1.CROSS_CUTTING, JsonTypeV2R1.STRING, PresenceV2R1.REQUIRED, NullabilityV2R1.NON_NULL, "ONE", "Generation ID header present on every response; on cache hit it identifies the hit generation, not the source generation.", ("response_cache",), ("X-Generation-Id", "present on every response")),
    _fact("provider_only_request", "$.provider.only", EnvelopeKindV2R1.REQUEST, JsonTypeV2R1.ARRAY, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_MORE", "Request-side provider eligibility list using provider slugs.", ("provider_routing",), ("Ordering Specific Providers", "`only` | string[]")),
    _fact("provider_order_request", "$.provider.order", EnvelopeKindV2R1.REQUEST, JsonTypeV2R1.ARRAY, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_MORE", "Request-side prioritized provider slug list.", ("provider_routing",), ("`order`", "provider slugs to try in order")),
    _fact("provider_fallback_request", "$.provider.allow_fallbacks", EnvelopeKindV2R1.REQUEST, JsonTypeV2R1.BOOLEAN, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Request-side provider fallback control.", ("provider_routing",), ("allow_fallbacks",)),
    _fact("provider_require_parameters", "$.provider.require_parameters", EnvelopeKindV2R1.REQUEST, JsonTypeV2R1.BOOLEAN, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_ONE", "Request-side requirement that selected endpoints support request parameters.", ("provider_routing",), ("require_parameters",)),
    _fact("model_fallbacks_request", "$.models", EnvelopeKindV2R1.REQUEST, JsonTypeV2R1.ARRAY, PresenceV2R1.OPTIONAL, NullabilityV2R1.NON_NULL, "ZERO_OR_MORE", "Priority-ordered fallback model IDs.", ("model_fallbacks",), ("`models` parameter", "array of model IDs in priority order")),
)

_FACT_BY_LABEL = {item.diagnostic_label: item for item in FACTS_V2R1}


def _mapping(label: str, target: str, transformation: str = "IDENTITY", authority_scope: str = "OFFICIAL_RESPONSE_WIRE") -> MappingRecordV2R1:
    fact = _FACT_BY_LABEL[label]
    return MappingRecordV2R1(
        official_path=fact.official_path,
        internal_target=target,
        transformation=transformation,
        missing_behavior="PRESERVE_ABSENT_OR_FAIL_IF_OFFICIAL_REQUIRED",
        invalid_type_behavior="FAIL_CLOSED",
        unknown_field_behavior="PRESERVE_NON_AUTHORITATIVELY",
        authority_scope=authority_scope,
        fact_ids=(fact.fact_id or "",),
        strength=EvidenceStrengthV2R1.DERIVED_LOSSLESSLY,
    )


MAPPINGS_V2R1: Tuple[MappingRecordV2R1, ...] = (
    _mapping("requested", "router.requested"),
    _mapping("strategy", "router.strategy"),
    _mapping("region", "router.region"),
    _mapping("summary", "router.summary"),
    _mapping("attempt", "router.attempt"),
    _mapping("is_byok", "router.is_byok"),
    _mapping("endpoints", "router.endpoints"),
    _mapping("params", "router.params"),
    _mapping("attempts", "router.attempts"),
    _mapping("pipeline", "router.pipeline"),
    _mapping("served_model", "response.actual_served_model"),
    _mapping("cache_status", "response.cache_status", authority_scope="OFFICIAL_RESPONSE_HEADER"),
)

_MAPPING_BY_TARGET = {item.internal_target: item for item in MAPPINGS_V2R1}


def _relationship(rel: RelationshipV2R1, status: RelationshipStatusV2R1, source_keys: Tuple[str, ...], fact_labels: Tuple[str, ...], mapping_targets: Tuple[str, ...], reason: str) -> RelationshipAssessmentV2R1:
    return RelationshipAssessmentV2R1(
        relationship=rel,
        status=status,
        source_ids=tuple(_SOURCE_BY_KEY[key].source_id or "" for key in source_keys),
        fact_ids=tuple(_FACT_BY_LABEL[label].fact_id or "" for label in fact_labels),
        mapping_ids=tuple(_MAPPING_BY_TARGET[target].mapping_id or "" for target in mapping_targets),
        reason=reason,
    )


RELATIONSHIPS_V2R1: Tuple[RelationshipAssessmentV2R1, ...] = (
    _relationship(RelationshipV2R1.SUCCESS_ENVELOPE_PLACEMENT, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata",), ("success_metadata",), (), "Opt-in successful responses place openrouter_metadata at top level alongside the normal response."),
    _relationship(RelationshipV2R1.ERROR_ENVELOPE_PLACEMENT, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata",), ("error_metadata",), (), "Opt-in errors with routing state place metadata at top level; documented 500 and pre-router exceptions remain explicit."),
    _relationship(RelationshipV2R1.CACHE_METADATA_ABSENCE, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata",), ("cache_metadata_absence",), (), "Documented response cache hits omit openrouter_metadata."),
    _relationship(RelationshipV2R1.CACHE_ATTESTATION, RelationshipStatusV2R1.ESTABLISHED, ("response_cache",), ("cache_status", "cache_age", "cache_ttl", "cache_source", "generation_id"), ("response.cache_status",), "Dedicated response headers distinguish HIT from MISS; metadata absence alone is not used as cache proof."),
    _relationship(RelationshipV2R1.ATTEMPT_SEMANTICS, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata",), ("attempt",), ("router.attempt",), "Success attempt is one-indexed; error attempt documents zero-before-provider versus attempted-provider failures."),
    _relationship(RelationshipV2R1.ATTEMPTS_LIST_SEMANTICS, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata", "openapi"), ("attempts", "attempt_provider", "attempt_model", "attempt_status"), ("router.attempts",), "attempts is optional and, when present, contains typed provider/model/status records. Absence is preserved rather than synthesized."),
    _relationship(RelationshipV2R1.ENDPOINT_COLLECTION, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata", "openapi"), ("endpoints", "endpoint_total", "endpoint_available", "endpoint_provider", "endpoint_model", "endpoint_selected"), ("router.endpoints",), "EndpointsMetadata is typed and failure semantics explicitly state that no endpoint is selected on failure; no extra total==len invariant is invented."),
    _relationship(RelationshipV2R1.PROVIDER_GRANULARITY, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata", "provider_routing"), ("endpoint_provider", "provider_order_request", "provider_only_request"), (), "Response metadata examples/summary expose broad provider labels while request routing uses provider slugs; the two are not conflated."),
    _relationship(RelationshipV2R1.SERVED_MODEL_PRECEDENCE, RelationshipStatusV2R1.ESTABLISHED, ("api_overview", "model_fallbacks"), ("served_model",), ("response.actual_served_model",), "The top-level response model is required in the normalized response and fallback documentation states it is the model ultimately used."),
    _relationship(RelationshipV2R1.STRATEGY_SEMANTICS, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata", "openapi"), ("strategy",), ("router.strategy",), "RoutingStrategy has a documented enum in OpenAPI; response strategy is preserved as reported and is not used to infer request fallback controls."),
    _relationship(RelationshipV2R1.PIPELINE_SEMANTICS, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata", "openapi"), ("pipeline", "pipeline_type", "pipeline_name", "pipeline_data"), ("router.pipeline",), "Pipeline stages are additive records for material plugins; type/name are typed and stage-specific data is opaque/non-authoritative."),
    _relationship(RelationshipV2R1.UNKNOWN_ADDITIVE_FIELD_POLICY, RelationshipStatusV2R1.ESTABLISHED, ("router_metadata",), ("pipeline",), ("router.pipeline",), "Official metadata shape is additive; unknown optional fields/stage types are retained or ignored non-authoritatively and may not override known authority."),
    _relationship(RelationshipV2R1.EXACT_ENDPOINT_RESPONSE_IDENTITY, RelationshipStatusV2R1.UNAVAILABLE_BY_DOCUMENTED_CONTRACT, ("router_metadata", "provider_routing"), ("endpoint_provider", "provider_only_request"), (), "Response provider metadata does not supply the exact request endpoint selector/endpoint ID. Exact endpoint response identity therefore remains NOT_ESTABLISHED."),
    _relationship(RelationshipV2R1.ACTUAL_SERVED_MODEL_IDENTITY, RelationshipStatusV2R1.ESTABLISHED, ("api_overview", "model_fallbacks"), ("served_model",), ("response.actual_served_model",), "Top-level response model is authoritative for the model ultimately used; requested model must never substitute when actual model is absent."),
)

FROZEN_MANIFEST_V2R1 = ManifestV2R1(
    source_records=SOURCES_V2R1,
    fact_records=FACTS_V2R1,
    mapping_records=MAPPINGS_V2R1,
    relationship_assessments=RELATIONSHIPS_V2R1,
    provider_granularity=ProviderGranularityV2R1.HUMAN_DISPLAY_NAME,
)


def verify_source_snapshots_v2r1(repository_root: Path) -> Tuple[str, ...]:
    root = repository_root.resolve()
    failures: list[str] = []
    for source in SOURCES_V2R1:
        path = root / source.evidence_path
        try:
            path.resolve().relative_to(root)
        except ValueError:
            failures.append(f"SOURCE_PATH_ESCAPE:{source.source_key}")
            continue
        if not path.is_file():
            failures.append(f"SOURCE_MISSING:{source.source_key}")
            continue
        data = path.read_bytes()
        if len(data) != source.byte_length:
            failures.append(f"SOURCE_LENGTH_MISMATCH:{source.source_key}")
        if sha256_bytes_v2r1(data) != source.sha256:
            failures.append(f"SOURCE_SHA256_MISMATCH:{source.source_key}")
        if git_blob_sha1_v2r1(data) != source.git_blob_sha:
            failures.append(f"SOURCE_GIT_BLOB_MISMATCH:{source.source_key}")
    return tuple(failures)


def validate_fact_anchor_presence_v2r1(repository_root: Path) -> Tuple[str, ...]:
    root = repository_root.resolve()
    source_by_id = {item.source_id: item for item in SOURCES_V2R1}
    cache: dict[str, str] = {}
    failures: list[str] = []
    for fact in FACTS_V2R1:
        combined = "\n".join(
            cache.setdefault(
                source_id or "",
                (root / source_by_id[source_id].evidence_path).read_text(encoding="utf-8"),
            )
            for source_id in fact.source_ids
            if source_id in source_by_id
        )
        for anchor in fact.source_anchors:
            if anchor not in combined:
                failures.append(f"FACT_ANCHOR_MISSING:{fact.diagnostic_label}:{anchor[:32]}")
    return tuple(failures)


def build_validation_v2r1(repository_root: Path, manifest: ManifestV2R1 = FROZEN_MANIFEST_V2R1) -> ValidationV2R1:
    failures = list(verify_source_snapshots_v2r1(repository_root))
    failures.extend(validate_fact_anchor_presence_v2r1(repository_root))
    source_snapshot_integrity = not failures
    source_ids = {item.source_id for item in manifest.source_records}
    fact_ids = {item.fact_id for item in manifest.fact_records}
    mapping_ids = {item.mapping_id for item in manifest.mapping_records}
    reference_integrity = all(set(f.source_ids).issubset(source_ids) for f in manifest.fact_records) and all(set(m.fact_ids).issubset(fact_ids) for m in manifest.mapping_records) and all(set(r.source_ids).issubset(source_ids) and set(r.fact_ids).issubset(fact_ids) and set(r.mapping_ids).issubset(mapping_ids) for r in manifest.relationship_assessments)
    authoritative_mapping_integrity = manifest.assumption_based_authoritative_mapping_count == 0 and manifest.repository_convention_authoritative_mapping_count == 0 and all(m.lossless and m.strength in (EvidenceStrengthV2R1.DIRECTLY_DOCUMENTED, EvidenceStrengthV2R1.DERIVED_LOSSLESSLY) for m in manifest.mapping_records)
    exact_endpoint_firewall = manifest.exact_endpoint_response_identity == "NOT_ESTABLISHED" and next(r for r in manifest.relationship_assessments if r.relationship is RelationshipV2R1.EXACT_ENDPOINT_RESPONSE_IDENTITY).status is RelationshipStatusV2R1.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    actual_model_authority = manifest.actual_served_model_identity == "ESTABLISHED" and next(r for r in manifest.relationship_assessments if r.relationship is RelationshipV2R1.ACTUAL_SERVED_MODEL_IDENTITY).status is RelationshipStatusV2R1.ESTABLISHED
    if not reference_integrity:
        failures.append("REFERENCE_INTEGRITY_FAILED")
    if not authoritative_mapping_integrity:
        failures.append("AUTHORITATIVE_MAPPING_INTEGRITY_FAILED")
    if not exact_endpoint_firewall:
        failures.append("EXACT_ENDPOINT_FIREWALL_FAILED")
    if not actual_model_authority:
        failures.append("ACTUAL_MODEL_AUTHORITY_FAILED")
    status = HypothesisStatusV2R1.SUPPORTED if not failures else HypothesisStatusV2R1.FALSIFIED
    manifest_bytes = render_contract_v2r1(manifest)
    established = sum(r.status is RelationshipStatusV2R1.ESTABLISHED for r in manifest.relationship_assessments)
    unavailable = sum(r.status is RelationshipStatusV2R1.UNAVAILABLE_BY_DOCUMENTED_CONTRACT for r in manifest.relationship_assessments)
    return ValidationV2R1(
        manifest_id=manifest.manifest_id or "",
        manifest_sha256=sha256_bytes_v2r1(manifest_bytes),
        source_count=len(manifest.source_records),
        fact_count=len(manifest.fact_records),
        mapping_count=len(manifest.mapping_records),
        relationship_count=len(manifest.relationship_assessments),
        established_relationship_count=established,
        documented_unavailable_relationship_count=unavailable,
        source_snapshot_integrity=source_snapshot_integrity,
        reference_integrity=reference_integrity,
        authoritative_mapping_integrity=authoritative_mapping_integrity,
        exact_endpoint_firewall=exact_endpoint_firewall,
        actual_model_authority=actual_model_authority,
        hypothesis_status=status,
        failure_reasons=tuple(failures),
    )


__all__ = [
    "BASE_BRANCH_HEAD_V2R1",
    "FACTS_V2R1",
    "FROZEN_MANIFEST_V2R1",
    "HISTORICAL_INVALID_V2_HEAD",
    "MANIFEST_RELATIVE_PATH_V2R1",
    "MANDATORY_RELATIONSHIPS_V2R1",
    "MAPPINGS_V2R1",
    "PREDECESSOR_MANIFEST_V1_ID",
    "PREDECESSOR_VALIDATION_V1_ID",
    "RELATIONSHIPS_V2R1",
    "REVALIDATION_RELATIVE_PATH_V2R1",
    "SOURCES_V2R1",
    "SOURCE_ROOT_V2R1",
    "UPSTREAM_COMMIT_V2R1",
    "UPSTREAM_REPOSITORY_V2R1",
    "VALIDATION_RELATIVE_PATH_V2R1",
    "EvidenceStrengthV2R1",
    "EnvelopeKindV2R1",
    "FactRecordV2R1",
    "HypothesisStatusV2R1",
    "JsonTypeV2R1",
    "ManifestV2R1",
    "MappingRecordV2R1",
    "NullabilityV2R1",
    "PresenceV2R1",
    "ProviderGranularityV2R1",
    "RelationshipAssessmentV2R1",
    "RelationshipStatusV2R1",
    "RelationshipV2R1",
    "RevalidationV2R1",
    "SourceRecordV2R1",
    "ValidationV2R1",
    "build_validation_v2r1",
    "classify_worktree_bytes_against_canonical_v2r1",
    "git_blob_sha1_v2r1",
    "render_contract_v2r1",
    "sha256_bytes_v2r1",
    "validate_fact_anchor_presence_v2r1",
    "verify_source_snapshots_v2r1",
]

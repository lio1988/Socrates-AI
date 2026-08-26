"""Pinned official OpenRouter wire-specification evidence manifest v2.

This additive module is offline and import-inert. It records six official
OpenRouter documentation sources at one immutable upstream Git commit and maps
only directly documented response-wire fields. It does not call OpenRouter,
access credentials, parse a live response, modify CED, or alter the sealed v1
manifest/artifacts.

Unlike v1's network-bound source acquisition, v2 uses public, content-addressed
Git objects from the official OpenRouterTeam/docs repository. The exact
endpoint selected by OpenRouter is *not* attested by the documented response
wire; the manifest preserves that limitation rather than inventing a mapping.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id


UPSTREAM_REPOSITORY_V2 = "OpenRouterTeam/docs"
UPSTREAM_COMMIT_V2 = "4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db"
BASE_BRANCH_HEAD_V2 = "a37e6c0068e3132ca49128295a5ef8453f91592c"
PREDECESSOR_MANIFEST_V1_ID = (
    "szorwirespecmanifestv1_bb4919b28f1913de4484c54dadbece8f0e16876ce233aa12eaaf00eb506a3a41"
)
PREDECESSOR_VALIDATION_V1_ID = (
    "szorwiremanifestvalidationv1_9a30a408ff6c4537319cfc8b1e3c62fec24e783f2d52db6a498612d10464fee2"
)
PREDECESSOR_BRANCH_V1 = "feature/socrates-zero-openrouter-wire-spec-evidence-v1"

OPENROUTER_WIRE_SPEC_SOURCE_SCHEMA_V2 = "socrateszero-openrouter-wire-spec-source/v2"
OPENROUTER_WIRE_SPEC_FACT_SCHEMA_V2 = "socrateszero-openrouter-wire-spec-fact/v2"
OPENROUTER_WIRE_SPEC_MAPPING_SCHEMA_V2 = "socrateszero-openrouter-wire-spec-mapping/v2"
OPENROUTER_WIRE_RELATIONSHIP_SCHEMA_V2 = "socrateszero-openrouter-wire-relationship/v2"
OPENROUTER_WIRE_MANIFEST_SCHEMA_V2 = "socrateszero-openrouter-wire-specification-manifest/v2"
OPENROUTER_WIRE_VALIDATION_SCHEMA_V2 = "socrateszero-openrouter-wire-specification-validation/v2"
OPENROUTER_WIRE_REVALIDATION_SCHEMA_V2 = "socrateszero-openrouter-wire-specification-revalidation/v2"

MANIFEST_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2/"
    "evidence/openrouter_official_wire_specification_manifest_v2.json"
)
VALIDATION_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2/"
    "artifacts/openrouter_wire_specification_manifest_validation_v2.json"
)
REVALIDATION_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2/"
    "artifacts/openrouter_wire_specification_manifest_revalidation_v2.json"
)


class _FrozenV2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceStrengthV2(str, Enum):
    DIRECTLY_DOCUMENTED = "DIRECTLY_DOCUMENTED"
    DERIVED_LOSSLESSLY = "DERIVED_LOSSLESSLY"
    CONTRACT_ABSENCE_DIRECTLY_DOCUMENTED = "CONTRACT_ABSENCE_DIRECTLY_DOCUMENTED"


class EnvelopeKindV2(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CACHE = "CACHE"
    CROSS_CUTTING = "CROSS_CUTTING"
    REQUEST = "REQUEST"


class JsonTypeV2(str, Enum):
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    UNION = "UNION"


class PresenceV2(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"


class NullabilityV2(str, Enum):
    NON_NULL = "NON_NULL"
    NULLABLE = "NULLABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RelationshipStatusV2(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    UNAVAILABLE_BY_DOCUMENTED_CONTRACT = "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"


class ProviderGranularityV2(str, Enum):
    HUMAN_DISPLAY_NAME = "HUMAN_DISPLAY_NAME"


class HypothesisStatusV2(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class RelationshipV2(str, Enum):
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

    Actual_SERVED_MODDR_IDENTITY = "ACTUAL_SERVED_MODEL_IDENTITY"



MANDDATORY_RELATIONSHIPS_V2: Tuple[RelationshipV2, ...] = tuple(RelationshipV2)


class SourceRecordV2(_FrozenV2):
    schema_version: Literal[OPENROUTER_WIRE_SPEC_SOURCE_SCHEMA_V2] = OPENROUTER_WIRE_SPEC_SOURCE_SCHEMA_V2
    source_id: Optional[str] = None
    source_key: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    repository: Literal[UPSTREAM_REPOSITORY_V2] = UPSTREAM_REPOSITORY_V2
    commit_sha: Literal[UPSTREAM_COMMIT_V2] = UPSTREAM_COMMIT_V2
    path: str = Field(min_length=1)
    blob_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    byte_length: int = Field(ge=1)
    inspectable_url: str = Field(min_length=1)
    extraction_mode: Literal[
        "PINNED_GIT_BLOB_METADATA_ONLY",
        "PINNED_GIT_BLOB_WITH_STRUCTURED_FACT_EXTRACT",
    ]
    fact_anchor_names: Tuple[str, ...] = ()
    limitation: str = Field(min_length=1)

    @model_validator(mode="after")
    def identify(self) -> "SourceRecordV2":
        if not self.inspectable_url.startswith(
            f"https://github.com/{UPSTREAM_REPOSITORY_V2}/blob/{UPSTREAM_COMMIT_V2}/"
        ):
            raise ContractValidationError("source URL is not pinned to the official commit")
        expected = stable_contract_id(
            "szorwiresourcev2", self.model_dump(mode="json", exclude={"source_id"})
        )
        if self.source_id not in (None, expected):
            raise ContractValidationError("source record ID mismatch")
        object.__setattr__(self, "source_id", expected)
        return self


class FactRecordV2(_FrozenV2):
    schema_version: Literal[OPENROUTER_WIRE_SPEC_FACT_SCHEMA_V2] = OPENROUTER_WIRE_SPEC_FACT_SCHEMA_V2
    fact_id: Optional[str] = None
    official_path: str = Field(min_length=1)
    envelope_kind: EnvelopeKindV2
    json_type: JsonTypeV2
    presence: PresenceV2
    nullability: NullabilityV2
    cardinality: str = Field(min_length=1)
    semantic_meaning: str = Field(min_length=1)
    source_ids: Tuple[str, ...]
    anchors: Tuple[str, ...]
    strength: EvidenceStrengthV2
    limitations: str = Field(min_length=1)

    @model_validator(mode="after")
    def identify(self) -> "FactRecordV2":
        if not self.source_ids or not self.anchors:
            raise ContractValidationError("fact record lacks official provenance")
        expected = stable_contract_id(
            "szorwirefactv2", self.model_dump(mode="json", exclude={"fact_id"})
        )
        if self.fact_id not in (None, expected):
            raise ContractValidationError("fact record ID mismatch")
        object.__setattr__(self, "fact_id", expected)
        return self


class MappingRecordV2(_FrozenV2):
    schema_version: Literal[OPENROUTER_WIRE_SPEC_MAPPING_SCHEMA_V2] = OPENROUTER_WIRE_SPEC_MAPPING_SCHEMA_V2
    mapping_id: Optional[str] = None
    official_path: str = Field(min_length=1)
    internal_target: str = Field(min_length=1)
    transformation: str = Field(min_length=1)
    lossless: Literal[True] = True
    missing_behaviour: str = Field(min_length=1)
    invalid_type_behaviour: str = Field(min_length=1)
    unknown_field_policy: str = Field(min_length=1)
    authority_scope: str = Field(min_length=1)
    fact_ids: Tuple[str, ...]

    @model_validator(mode="after")
    def identify(self) -> "MappingRecordV2":
        if not self.fact_ids:
            raise ContractValidationError("mapping record lacks fact provenance")
        expected = stable_contract_id(
            "szorwiremappingv2", self.model_dump(mode="json", exclude={"mapping_id"})
        )
        if self.mapping_id not in (None, expected):
            raise ContractValidationError("mapping record ID mismatch")
        object.__setattr__(self, "mapping_id", expected)
        return self


class RelationshipAssessmentV2(_FrozenV2):
    schema_version: Literal[OPENROUTER_WIRE_RELATIONSHIP_SCHEMA_V2] = OPENROUTER_WIRE_RELATIONSHIP_SCHEMA_V2
    assessment_id: Optional[str] = None
    relationship: RelationshipV2   
    status: RelationshipStatusV2   
    source_ids: Tuple[str, ...]
    fact_ids: Tuple[str, ...] = ()
    mapping_ids: Tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def identify(self) -> "RelationshipAssessmentV2:"
        if not self.source_ids:
            raise ContractValidationError("relationship assessment lacks source provenance")
        expected = stable_contract_id(
            "szorwirerelationshipv2", self.model_dump(mode="json", exclude={"assessment_id"})
        )
        if self.assessment_id not in (None, expected):
            raise ContractValidationError("relationship assessment ID mismatch")
        object.__setattr__(self, "assessment_id", expected)
        return self


class ManifestV2(_FrozenV2):
    schema_version: Literal[OPENROUTER_WIRE_MANIFEST_SCHEMA_V2] = OPENROUTER_WIRE_MANIFEST_SCHEMA_V2
    manifest_id: Optional[str] = None
    predecessor_manifest_id: Literal[PREDECESSOR_MANIFES
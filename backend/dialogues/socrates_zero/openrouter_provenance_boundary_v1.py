"""Immutable scientific provenance boundary for OpenRouter route controls v1.

Route controls carry historical scientific provenance for a sealed predecessor
experiment.  That provenance used to be represented by raw predecessor source
and test paths held in the runtime scoped-path inventory, which kept a
predecessor path an active runtime dependency for a purely historical reason.

This module represents the same provenance through immutable identities:
semantic IDs, artifact IDs, artifact hashes, case-set and validation-order IDs,
sealed commit identities and Git object identities.  No raw predecessor source
or test path appears here, and none is needed.

The identities below are frozen literals.  They are deliberately *not* imported
from the predecessor modules they describe: importing predecessor semantics to
verify provenance would reintroduce exactly the dependency this boundary
removes.  The module is import-inert.  It performs no filesystem read, network
access, credential lookup, environment inspection, provider call, model
execution, tool call, or CED application.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id

OPENROUTER_PROVENANCE_RECORD_SCHEMA_V1 = (
    "socrateszero-openrouter-provenance-record/v1"
)
OPENROUTER_PROVENANCE_BOUNDARY_SCHEMA_V1 = (
    "socrateszero-openrouter-provenance-boundary/v1"
)

OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1 = (
    "provenance://socrateszero/openrouter-adapter-case-design/v0"
)
OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1 = (
    "provenance://socrateszero/openrouter-adapter-case-suite/v0"
)
OPENROUTER_PROVENANCE_REFERENCE_PREFIX_V1 = "provenance://"


class OpenRouterProvenanceScientificRoleV1(str, Enum):
    """Why a predecessor identity is retained at all."""

    PREDECESSOR_CASE_DESIGN = "PREDECESSOR_CASE_DESIGN"
    PREDECESSOR_CASE_SUITE = "PREDECESSOR_CASE_SUITE"


class _FrozenProvenanceContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterProvenanceRecordV1(_FrozenProvenanceContractV1):
    """One immutable historical scientific identity.

    ``record_id`` is content addressed over every identity field, so tampering
    with any of them - the artifact hash, the artifact ID, the case-set
    identity, the validation order, the sealed commit, the Git object, the
    semantic ID or the scientific role - changes the record digest.
    """

    schema_version: Literal[
        OPENROUTER_PROVENANCE_RECORD_SCHEMA_V1
    ] = OPENROUTER_PROVENANCE_RECORD_SCHEMA_V1
    reference_id: str
    semantic_id: str
    scientific_role: OpenRouterProvenanceScientificRoleV1
    artifact_id: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_set_id: str
    validation_order_id: str
    sealed_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    sealed_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_object_sha1: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    record_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterProvenanceRecordV1":
        if not self.reference_id.startswith(
            OPENROUTER_PROVENANCE_REFERENCE_PREFIX_V1
        ):
            raise ContractValidationError(
                "provenance reference must not be a repository path"
            )
        expected = stable_contract_id(
            "szorprovenancerecordv1",
            self.model_dump(mode="json", exclude={"record_id"}),
        )
        if self.record_id not in (None, expected):
            raise ContractValidationError("provenance record ID mismatch")
        object.__setattr__(self, "record_id", expected)
        return self

    @property
    def record_sha256(self) -> str:
        """The 64-hex content address of this record."""
        return (self.record_id or "").split("_", 1)[-1]


FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1: Tuple[OpenRouterProvenanceRecordV1, ...] = (
    OpenRouterProvenanceRecordV1(
        reference_id=OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
        semantic_id="socrateszero-openrouter-acquisition-case-set/v0",
        scientific_role=OpenRouterProvenanceScientificRoleV1.PREDECESSOR_CASE_DESIGN,
        artifact_id=(
            "szoracqevaluation_"
            "43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f"
        ),
        artifact_sha256=(
            "0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083"
        ),
        case_set_id=(
            "oracqcasesetv0_"
            "0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373"
        ),
        validation_order_id=(
            "oracqvalidationv0_"
            "137f7049f806222f1901f5e1790535f41b8d06558cb1ebb41aba4643f3782cf3"
        ),
        sealed_commit_sha="a79ca97777d1c8c9db4234399cd4c716d360ebd5",
        sealed_content_sha256=(
            "3268c64b6084871f8cb268b7c2fd44fd7318fe613f8d37b438416e07de3e46b8"
        ),
        git_object_sha1="7d3db1ac9a47ccb0dff1d6df2ab5b5e983abbda7",
    ),
    OpenRouterProvenanceRecordV1(
        reference_id=OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
        semantic_id="socrateszero-openrouter-acquisition-case-suite/v0",
        scientific_role=OpenRouterProvenanceScientificRoleV1.PREDECESSOR_CASE_SUITE,
        artifact_id=(
            "szoracqevaluation_"
            "43f2f35f8e2e1eae6ac63d9aa8a3d26ad4afe79526b44ee8e872c79f75a2795f"
        ),
        artifact_sha256=(
            "0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083"
        ),
        case_set_id=(
            "oracqcasesetv0_"
            "0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373"
        ),
        validation_order_id=(
            "oracqvalidationv0_"
            "137f7049f806222f1901f5e1790535f41b8d06558cb1ebb41aba4643f3782cf3"
        ),
        sealed_commit_sha="a79ca97777d1c8c9db4234399cd4c716d360ebd5",
        sealed_content_sha256=(
            "7268f5bb3dc24c0393e0d81ddd1b0d2498ea024538fd16e151e183b22a0d1273"
        ),
        git_object_sha1="4db44774e4c682074809e2012c75e474735b43bc",
    ),
)

OPENROUTER_PROVENANCE_BOUNDARY_ID_V1 = stable_contract_id(
    "szorprovenanceboundaryv1",
    {
        "schema_version": OPENROUTER_PROVENANCE_BOUNDARY_SCHEMA_V1,
        "records": [
            record.model_dump(mode="json")
            for record in FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1
        ],
    },
)

OPENROUTER_PROVENANCE_REFERENCE_IDS_V1: Tuple[str, ...] = tuple(
    record.reference_id for record in FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1
)


def openrouter_provenance_record_v1(
    reference_id: str,
    records: Tuple[OpenRouterProvenanceRecordV1, ...] = (
        FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1
    ),
) -> Optional[OpenRouterProvenanceRecordV1]:
    """Return the immutable record for ``reference_id``, or ``None``."""
    for record in records:
        if record.reference_id == reference_id:
            return record
    return None


__all__ = [
    "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1",
    "OPENROUTER_PROVENANCE_BOUNDARY_ID_V1",
    "OPENROUTER_PROVENANCE_BOUNDARY_SCHEMA_V1",
    "OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1",
    "OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1",
    "OPENROUTER_PROVENANCE_RECORD_SCHEMA_V1",
    "OPENROUTER_PROVENANCE_REFERENCE_IDS_V1",
    "OPENROUTER_PROVENANCE_REFERENCE_PREFIX_V1",
    "OpenRouterProvenanceRecordV1",
    "OpenRouterProvenanceScientificRoleV1",
    "openrouter_provenance_record_v1",
]

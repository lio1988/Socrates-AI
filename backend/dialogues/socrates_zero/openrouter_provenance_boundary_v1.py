"""Immutable scientific provenance boundary for OpenRouter route controls v1.

Route controls carry historical scientific provenance for a sealed predecessor
experiment.  That provenance used to be represented by raw predecessor source
and test paths held in the runtime scoped-path inventory, which kept a
predecessor path an active runtime dependency for a purely historical reason.

This module represents the same provenance through immutable identities:
semantic IDs, artifact IDs, artifact hashes, case-set and validation-order IDs,
sealed commit identities and Git object identities.  No raw predecessor source
or test path appears here, and none is needed.

It also defines the CURRENT scoped snapshot and mutation contracts.  These are
deliberately separate types from the sealed historical
``OpenRouterScopedPathSnapshotV1``: the historical contract describes what the
frozen experiment measured and is never widened to describe the repository as it
stands today.  Historical artifact verification and current mutation
verification are two different operations on two different contracts.

The identities below are frozen literals.  They are deliberately *not* imported
from the predecessor modules they describe: importing predecessor semantics to
verify provenance would reintroduce exactly the dependency this boundary
removes.  The module is import-inert.  It performs no filesystem read, network
access, credential lookup, environment inspection, provider call, model
execution, tool call, or CED application.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, stable_contract_id

OPENROUTER_PROVENANCE_RECORD_SCHEMA_V1 = (
    "socrateszero-openrouter-provenance-record/v1"
)
OPENROUTER_PROVENANCE_BOUNDARY_SCHEMA_V1 = (
    "socrateszero-openrouter-provenance-boundary/v1"
)
OPENROUTER_CURRENT_SCOPED_SNAPSHOT_SCHEMA_V1 = (
    "socrateszero-openrouter-current-scoped-snapshot/v1"
)
OPENROUTER_CURRENT_SCOPED_MUTATION_EVIDENCE_SCHEMA_V1 = (
    "socrateszero-openrouter-current-scoped-mutation-evidence/v1"
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
    records: Optional[Tuple[OpenRouterProvenanceRecordV1, ...]] = None,
) -> Optional[OpenRouterProvenanceRecordV1]:
    """Return the immutable record for ``reference_id``, or ``None``.

    The frozen boundary is resolved at call time rather than bound as a default
    so that a single substitution is seen consistently by every reader.
    """
    catalogue = (
        FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1 if records is None else records
    )
    for record in catalogue:
        if record.reference_id == reference_id:
            return record
    return None


# --------------------------------------------------------------- current -----
#
# Everything below describes the CURRENT repository generation.  It is a
# separate contract family from the sealed historical snapshot, with its own
# schema versions and its own identity prefixes, and the two must never be
# unified: the sealed generation is history, this one is today.


class OpenRouterCurrentScopeV1(str, Enum):
    """Mutation scope for the current generation.

    Mirrors the historical scope vocabulary by value so the two generations stay
    comparable, while remaining a distinct type so they cannot be interchanged.
    """

    SOURCE = "SOURCE"
    SIBLING = "SIBLING"
    PRODUCTION = "PRODUCTION"


class OpenRouterCurrentScopedDigestV1(_FrozenProvenanceContractV1):
    """One current scoped entry.

    ``reference`` is either a repository-relative path, digested from disk, or a
    provenance reference, digested by its immutable record identity.
    """

    scope: OpenRouterCurrentScopeV1
    reference: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def openrouter_current_scoped_inventory_id_v1(
    membership: Sequence[Tuple[OpenRouterCurrentScopeV1, str]],
) -> str:
    """Content address the current scoped membership, in order."""
    return stable_contract_id(
        "szorcurrentpathinventoryv1",
        tuple(
            {"scope": scope.value, "reference": reference}
            for scope, reference in membership
        ),
    )


class OpenRouterCurrentScopedSnapshotV1(_FrozenProvenanceContractV1):
    """The current scoped snapshot.

    Membership and order are bound to ``inventory_id`` by construction: the ID
    is recomputed from the rows and must match, so no row may be added, removed
    or reordered without changing it.  ``snapshot_id`` is always recomputed and
    a caller-declared value is never trusted.
    """

    schema_version: Literal[
        OPENROUTER_CURRENT_SCOPED_SNAPSHOT_SCHEMA_V1
    ] = OPENROUTER_CURRENT_SCOPED_SNAPSHOT_SCHEMA_V1
    inventory_id: str
    rows: Tuple[OpenRouterCurrentScopedDigestV1, ...]
    snapshot_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterCurrentScopedSnapshotV1":
        membership = tuple((row.scope, row.reference) for row in self.rows)
        if len(set(membership)) != len(membership):
            raise ContractValidationError(
                "current scoped snapshot has duplicate entries"
            )
        if self.inventory_id != openrouter_current_scoped_inventory_id_v1(membership):
            raise ContractValidationError(
                "current scoped snapshot membership or order changed"
            )
        digests = {row.reference: row.sha256 for row in self.rows}
        for record in FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1:
            if record.reference_id not in digests:
                raise ContractValidationError(
                    "current scoped snapshot is missing a provenance reference"
                )
            if digests[record.reference_id] != record.record_sha256:
                raise ContractValidationError(
                    "current scoped provenance digest is not the immutable "
                    "record identity"
                )
        expected = stable_contract_id(
            "szorcurrentsnapshotv1",
            self.model_dump(mode="json", exclude={"snapshot_id"}),
        )
        if self.snapshot_id not in (None, expected):
            raise ContractValidationError("current scoped snapshot ID mismatch")
        object.__setattr__(self, "snapshot_id", expected)
        return self


class OpenRouterCurrentScopedMutationV1(_FrozenProvenanceContractV1):
    scope: OpenRouterCurrentScopeV1
    reference: str
    before_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def changed(self) -> "OpenRouterCurrentScopedMutationV1":
        if self.before_sha256 == self.after_sha256:
            raise ContractValidationError(
                "current scoped mutation digests must differ"
            )
        return self


class OpenRouterCurrentScopedMutationEvidenceV1(_FrozenProvenanceContractV1):
    schema_version: Literal[
        OPENROUTER_CURRENT_SCOPED_MUTATION_EVIDENCE_SCHEMA_V1
    ] = OPENROUTER_CURRENT_SCOPED_MUTATION_EVIDENCE_SCHEMA_V1
    inventory_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    source_mutations: int = Field(ge=0)
    sibling_mutations: int = Field(ge=0)
    production_mutations: int = Field(ge=0)
    changed_references: Tuple[str, ...] = ()
    mutations: Tuple[OpenRouterCurrentScopedMutationV1, ...] = ()
    evidence_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterCurrentScopedMutationEvidenceV1":
        references = tuple(mutation.reference for mutation in self.mutations)
        if len(set(references)) != len(references):
            raise ContractValidationError(
                "current scoped mutation evidence repeats a reference"
            )
        counts = {
            scope: sum(mutation.scope is scope for mutation in self.mutations)
            for scope in OpenRouterCurrentScopeV1
        }
        if (
            self.changed_references != references
            or self.source_mutations != counts[OpenRouterCurrentScopeV1.SOURCE]
            or self.sibling_mutations != counts[OpenRouterCurrentScopeV1.SIBLING]
            or self.production_mutations
            != counts[OpenRouterCurrentScopeV1.PRODUCTION]
        ):
            raise ContractValidationError(
                "current scoped mutation evidence is not fully derived"
            )
        expected = stable_contract_id(
            "szorcurrentmutationevidencev1",
            self.model_dump(mode="json", exclude={"evidence_id"}),
        )
        if self.evidence_id not in (None, expected):
            raise ContractValidationError(
                "current scoped mutation evidence ID mismatch"
            )
        object.__setattr__(self, "evidence_id", expected)
        return self


def compare_openrouter_current_scoped_snapshots_v1(
    before: OpenRouterCurrentScopedSnapshotV1,
    after: OpenRouterCurrentScopedSnapshotV1,
) -> OpenRouterCurrentScopedMutationEvidenceV1:
    """Current mutation verification.

    Distinct from historical artifact verification, and it refuses any snapshot
    that is not the current contract.
    """
    for snapshot in (before, after):
        if type(snapshot) is not OpenRouterCurrentScopedSnapshotV1:
            raise ContractValidationError(
                "current scoped comparison requires the current snapshot contract"
            )
    if before.inventory_id != after.inventory_id:
        raise ContractValidationError("current scoped inventory generation changed")
    after_by_reference = {row.reference: row for row in after.rows}
    mutations = tuple(
        OpenRouterCurrentScopedMutationV1(
            scope=row.scope,
            reference=row.reference,
            before_sha256=row.sha256,
            after_sha256=after_by_reference[row.reference].sha256,
        )
        for row in before.rows
        if row.sha256 != after_by_reference[row.reference].sha256
    )
    counts = {
        scope: sum(mutation.scope is scope for mutation in mutations)
        for scope in OpenRouterCurrentScopeV1
    }
    return OpenRouterCurrentScopedMutationEvidenceV1(
        inventory_id=before.inventory_id,
        before_snapshot_id=before.snapshot_id or "",
        after_snapshot_id=after.snapshot_id or "",
        source_mutations=counts[OpenRouterCurrentScopeV1.SOURCE],
        sibling_mutations=counts[OpenRouterCurrentScopeV1.SIBLING],
        production_mutations=counts[OpenRouterCurrentScopeV1.PRODUCTION],
        changed_references=tuple(mutation.reference for mutation in mutations),
        mutations=mutations,
    )


__all__ = [
    "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1",
    "OPENROUTER_CURRENT_SCOPED_MUTATION_EVIDENCE_SCHEMA_V1",
    "OPENROUTER_CURRENT_SCOPED_SNAPSHOT_SCHEMA_V1",
    "OPENROUTER_PROVENANCE_BOUNDARY_ID_V1",
    "OPENROUTER_PROVENANCE_BOUNDARY_SCHEMA_V1",
    "OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1",
    "OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1",
    "OPENROUTER_PROVENANCE_RECORD_SCHEMA_V1",
    "OPENROUTER_PROVENANCE_REFERENCE_IDS_V1",
    "OPENROUTER_PROVENANCE_REFERENCE_PREFIX_V1",
    "OpenRouterCurrentScopeV1",
    "OpenRouterCurrentScopedDigestV1",
    "OpenRouterCurrentScopedMutationEvidenceV1",
    "OpenRouterCurrentScopedMutationV1",
    "OpenRouterCurrentScopedSnapshotV1",
    "OpenRouterProvenanceRecordV1",
    "OpenRouterProvenanceScientificRoleV1",
    "compare_openrouter_current_scoped_snapshots_v1",
    "openrouter_current_scoped_inventory_id_v1",
    "openrouter_provenance_record_v1",
]

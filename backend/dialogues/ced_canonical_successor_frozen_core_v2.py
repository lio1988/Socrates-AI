"""Frozen implementation and predecessor locks for successor parity v2.

This module is declarative only.  It performs no repository inspection,
subprocess execution, provider acquisition, transition application, or artifact
publication.  The Git blob identifiers were audited against the Phase 8
pre-result freeze, the sealed Phase 8 artifact commit, and the Phase 8R
decision-gate checkpoint before this contract was authored.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_SCHEMA_VERSION = (
    "ced-canonical-successor-core-blob-lock/v2"
)
CANONICAL_SUCCESSOR_CORE_BLOB_ENTRY_SCHEMA_VERSION = (
    "ced-canonical-successor-core-blob-entry/v2"
)
CANONICAL_SUCCESSOR_PREDECESSOR_LOCK_SCHEMA_VERSION = (
    "ced-canonical-successor-predecessor-lock/v2"
)
CANONICAL_SUCCESSOR_HISTORICAL_ARTIFACT_SHA_SCHEMA_VERSION = (
    "ced-canonical-successor-historical-artifact-sha256/v2"
)

SEALED_PHASE8_ARTIFACT_ID = (
    "cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0"
)
SEALED_PHASE8_ARTIFACT_SHA256 = (
    "00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea"
)
SEALED_PHASE8_ARTIFACT_COMMIT = (
    "07ec5ab14cd1599ffd6c8c4b6442d56d51129f11"
)

_GIT_BLOB_PATTERN = r"^[0-9a-f]{40}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _repository_path(value: str) -> str:
    _nonblank(value)
    if value.startswith(("/", "\\")) or "\\" in value or "//" in value:
        raise ValueError("repository path must be relative and use canonical slashes")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("repository path contains a non-canonical segment")
    return value


class _FrozenCoreContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FrozenCoreBlobEntry(_FrozenCoreContract):
    """One exact repository blob participating in frozen v2 semantics."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_CORE_BLOB_ENTRY_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_CORE_BLOB_ENTRY_SCHEMA_VERSION
    path: str
    git_blob_id: str = Field(pattern=_GIT_BLOB_PATTERN)
    role: str

    _path_is_canonical = field_validator("path")(_repository_path)
    _role_is_nonblank = field_validator("role")(_nonblank)

    def identity_payload(self) -> Dict[str, str]:
        return self.model_dump(mode="json")


class HistoricalArtifactSha256(_FrozenCoreContract):
    """One immutable scientific-artifact digest retained across Phase 8R/v2."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_HISTORICAL_ARTIFACT_SHA_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_HISTORICAL_ARTIFACT_SHA_SCHEMA_VERSION
    name: str
    sha256: str = Field(pattern=_SHA256_PATTERN)

    _name_is_nonblank = field_validator("name")(_nonblank)

    def identity_payload(self) -> Dict[str, str]:
        return self.model_dump(mode="json")


class SealedPhase8PredecessorLock(_FrozenCoreContract):
    """Exact evaluator and falsified artifact from the sealed v1 experiment."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PREDECESSOR_LOCK_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_PREDECESSOR_LOCK_SCHEMA_VERSION
    evaluator_path: str
    evaluator_git_blob_id: str = Field(pattern=_GIT_BLOB_PATTERN)
    artifact_path: str
    artifact_git_blob_id: str = Field(pattern=_GIT_BLOB_PATTERN)
    artifact_id: str
    artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    artifact_status: Literal["FALSIFIED"] = "FALSIFIED"
    artifact_commit: str = Field(pattern=_GIT_BLOB_PATTERN)

    _paths_are_canonical = field_validator("evaluator_path", "artifact_path")(
        _repository_path
    )
    _artifact_id_is_nonblank = field_validator("artifact_id")(_nonblank)

    def identity_payload(self) -> Dict[str, str]:
        return self.model_dump(mode="json")


class CanonicalSuccessorCoreBlobLockV2(_FrozenCoreContract):
    """Deterministic lock over the unchanged core and predecessor evidence."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_SCHEMA_VERSION
    lock_id: Optional[str] = None
    fingerprint: Optional[str] = Field(default=None, pattern=_SHA256_PATTERN)
    core_blobs: Tuple[FrozenCoreBlobEntry, ...]
    predecessor: SealedPhase8PredecessorLock
    historical_artifacts: Tuple[HistoricalArtifactSha256, ...]

    @model_validator(mode="after")
    def canonicalize_validate_and_identify(
        self,
    ) -> "CanonicalSuccessorCoreBlobLockV2":
        core = tuple(sorted(self.core_blobs, key=lambda item: item.path))
        if len(core) != 34:
            raise ContractValidationError("v2 frozen core must contain exactly 34 blobs")
        if len({item.path for item in core}) != len(core):
            raise ContractValidationError("v2 frozen core contains duplicate paths")
        object.__setattr__(self, "core_blobs", core)

        historical = tuple(
            sorted(self.historical_artifacts, key=lambda item: item.name)
        )
        if len(historical) != 4:
            raise ContractValidationError(
                "v2 frozen history must contain exactly four artifact digests"
            )
        if len({item.name for item in historical}) != len(historical):
            raise ContractValidationError(
                "v2 frozen history contains duplicate artifact names"
            )
        object.__setattr__(self, "historical_artifacts", historical)

        phase8 = next(
            (
                item
                for item in historical
                if item.name == "phase8_falsified_successor_parity_v1"
            ),
            None,
        )
        if phase8 is None or phase8.sha256 != self.predecessor.artifact_sha256:
            raise ContractValidationError(
                "Phase 8 historical digest does not match the predecessor artifact"
            )

        payload = self.identity_payload()
        expected_fingerprint = hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()
        expected_lock_id = stable_contract_id("cedcorebloblockv2", payload)
        if self.fingerprint is not None and self.fingerprint != expected_fingerprint:
            raise ContractValidationError("core blob lock fingerprint mismatch")
        if self.lock_id is not None and self.lock_id != expected_lock_id:
            raise ContractValidationError("core blob lock ID mismatch")
        object.__setattr__(self, "fingerprint", expected_fingerprint)
        object.__setattr__(self, "lock_id", expected_lock_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "core_blobs": [item.identity_payload() for item in self.core_blobs],
            "predecessor": self.predecessor.identity_payload(),
            "historical_artifacts": [
                item.identity_payload() for item in self.historical_artifacts
            ],
        }


_CORE_BLOBS = (
    FrozenCoreBlobEntry(
        path="backend/dialogues/agent.py",
        git_blob_id="65254fe5d9d2df2a8fc539020b0868078b3631fc",
        role="logical agent identity used by canonical root construction",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced.py",
        git_blob_id="9a1c7ab4610c0dcc5cf40b5211095afaa694d90f",
        role="CED-owned scheduling, task, response-application, and finalization seam",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor.py",
        git_blob_id="b93b5e8abcfb711ea577d5c4d622a58c9a09e4f2",
        role="canonical successor capture, preparation, replay, and isolation environment",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor_cases_v1.py",
        git_blob_id="84c317d094af865b97c6353fe704b4c8b8751597",
        role="immutable authoritative observation cases and parity references",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor_contracts.py",
        git_blob_id="187b35b83ae9b11ff9a79ccb38c3750348866633",
        role="capsule, task, pending, observation, result, receipt, and compatibility contracts",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor_manifest.py",
        git_blob_id="783212506b2dafcc25ae5ccbcd69777aab4a9bb3",
        role="exact authoritative observation manifest and authorization firewall",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor_recording.py",
        git_blob_id="f0a3435153cb6f525194153cfb37c9c332e3ad27",
        role="canonical observation capture and binding proof",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor_recording_contracts.py",
        git_blob_id="fbec816f5ddfc1f10f995235414f34abc033282d",
        role="capture receipt and manifest-entry linkage contracts",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_canonical_successor_recording_fixtures.py",
        git_blob_id="4fbda5736cfc578500406abee58e746d3b8969e2",
        role="deterministic offline recording root and provider profile",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_search_observability_v1.py",
        git_blob_id="89945d14ca0e6df7da8d08e91183f8a44b2d8d62",
        role="typed immutable SearchState-v1 observability contracts",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_search_projection.py",
        git_blob_id="3a49ce4c9642d5fb6d8ba43a2c713f51ba674227",
        role="trusted base SearchState projection",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_search_projection_v1.py",
        git_blob_id="de5caadb2adc8a60ad44dfae2d1dab8baf654b60",
        role="trusted SearchState-v1 projection",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_search_value_v1.py",
        git_blob_id="17b38f5b9ebf376600fed9d7c4be0ceaa1ea68a9",
        role="deterministic read-only heuristic Value-v1 estimator",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/ced_search_value_v1_contracts.py",
        git_blob_id="c051e0e17479f7b071d831d60039304b9d700369",
        role="Value-v1 rules, semantic identity, and audit contracts",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/hybrid_epistemic.py",
        git_blob_id="55e88b3c94910903d97a787859b7e70d8469e396",
        role="governing Hybrid record and support-state semantics consumed by projection and Value",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/hybrid_authority.py",
        git_blob_id="01608a67de8f24040ad6ac4d6d89d5e625ee98b6",
        role="Hybrid authority and canonical ownership boundary",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/hybrid_shadow.py",
        git_blob_id="5ac5db43aeec6c223a32c1d87e1e01b769bffb83",
        role="transitive governing Hybrid record contracts",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/hybrid_support.py",
        git_blob_id="96e6b7897ef7e8fbb929ead06625d27de8639f87",
        role="Hybrid H8 support semantics consumed by frozen projections",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/model_identity.py",
        git_blob_id="e83bab5544b0f618a8e3d806e52f5bee48379498",
        role="authoritative exact-model identity and independence semantics",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/models.py",
        git_blob_id="e36e0cfd0cb7b3f9b378a763a7a2a03a29e6db40",
        role="canonical task, move, response, session, log, and round data models",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/provider_registry.py",
        git_blob_id="743db717a4a7198fcda690a7d46ad8ad3373e34b",
        role="canonical parser, exact-model registry, and round finalization",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/providers.py",
        git_blob_id="75551d04b12b35554c740c766a2849e02db4a195",
        role="deterministic offline provider primitive used by detached roots",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/reasoning_prompts.py",
        git_blob_id="be7be5533f80e5062bf85781de7fa11d5636ee45",
        role="opening mandate, roster projection, and marker contract",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/role_assignment.py",
        git_blob_id="6a831a2701ea2e4251219be637ea31fdf4a17757",
        role="deterministic canonical agent and role scheduling",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socratic.py",
        git_blob_id="e3e420d3f5f701a19d40f40226c2fd7f5ae17bef",
        role="Socratic content, injection, commitment, and aporia semantics",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/baseline.py",
        git_blob_id="1def881b0c3ed350dbcba8d96fd0f9a27741ebb2",
        role="frozen canonical baseline adapter",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/constitution.py",
        git_blob_id="fec133c67715db39645a466a823159934eb2a449",
        role="hard-legal action generation and validation",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/contracts.py",
        git_blob_id="086de2a94614891939b2cf9d72896044840f15b6",
        role="canonical IDs, SearchState, action, budget, and receipt primitives",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/policy.py",
        git_blob_id="33b0a10cf814bf4bc5f908b878024c1eb0b74904",
        role="frozen deterministic Policy-v0 prior",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/puct.py",
        git_blob_id="576d939f214f50d1cd90bee964fa19bfa7482472",
        role="frozen bounded depth-one PUCT-v0 search",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/strategy.py",
        git_blob_id="eb36b9b771db13312f826a7a4b4a02d0e12d3662",
        role="frozen Greedy-v0 and BestOfN-v0 search strategies",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/socrates_zero/value.py",
        git_blob_id="eb34584219221ac15d3ef825941b7e5100915ccb",
        role="frozen deterministic Value-v0 estimator",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/task_checker.py",
        git_blob_id="c2174f9e98b49df0bedf62bfe053c62a26547508",
        role="task classification used by opening mandate and injection checks",
    ),
    FrozenCoreBlobEntry(
        path="backend/dialogues/topic.py",
        git_blob_id="615b8f828998cebdd87a25ec2c0149d015dcfed4",
        role="transitive deterministic provider and root dependency",
    ),
)


FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2 = CanonicalSuccessorCoreBlobLockV2(
    core_blobs=_CORE_BLOBS,
    predecessor=SealedPhase8PredecessorLock(
        evaluator_path="backend/dialogues/ced_canonical_successor_evaluation.py",
        evaluator_git_blob_id="8b855ac877f34e7595ced5857c8ece8e1ee365e4",
        artifact_path=(
            "docs/branches/feature-socrates-zero-canonical-successor-env-v0/"
            "artifacts/socrateszero_canonical_successor_parity_v1.json"
        ),
        artifact_git_blob_id="f2718b95651425d940ab61764fa421e0e90a8bdc",
        artifact_id=SEALED_PHASE8_ARTIFACT_ID,
        artifact_sha256=SEALED_PHASE8_ARTIFACT_SHA256,
        artifact_status="FALSIFIED",
        artifact_commit=SEALED_PHASE8_ARTIFACT_COMMIT,
    ),
    historical_artifacts=(
        HistoricalArtifactSha256(
            name="phase5_matched_compute_normalized",
            sha256=(
                "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"
            ),
        ),
        HistoricalArtifactSha256(
            name="phase7_value_v1_primary",
            sha256=(
                "d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca"
            ),
        ),
        HistoricalArtifactSha256(
            name="phase7_value_v1_bestofn",
            sha256=(
                "86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637"
            ),
        ),
        HistoricalArtifactSha256(
            name="phase8_falsified_successor_parity_v1",
            sha256=SEALED_PHASE8_ARTIFACT_SHA256,
        ),
    ),
)


__all__ = [
    "CANONICAL_SUCCESSOR_CORE_BLOB_ENTRY_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_HISTORICAL_ARTIFACT_SHA_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_PREDECESSOR_LOCK_SCHEMA_VERSION",
    "FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2",
    "SEALED_PHASE8_ARTIFACT_COMMIT",
    "SEALED_PHASE8_ARTIFACT_ID",
    "SEALED_PHASE8_ARTIFACT_SHA256",
    "CanonicalSuccessorCoreBlobLockV2",
    "FrozenCoreBlobEntry",
    "HistoricalArtifactSha256",
    "SealedPhase8PredecessorLock",
]

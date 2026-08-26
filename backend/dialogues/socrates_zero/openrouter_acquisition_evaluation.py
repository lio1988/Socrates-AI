"""Offline, fail-closed evaluation for OpenRouter acquisition controls v0.

This module is deliberately downstream of the frozen case design and the pure
contract/renderer layer.  It never imports a provider SDK, reads environment
state, opens a transport, or invokes the canonical application.  In the
current repository candidate, route authority is not established, so the
unmutated candidate stops at P08 before any canned transport can run.

Expected case labels are used only after an actual result has been derived
from the independent mutation-path taxonomy below.  They never enter a
renderer, adapter request, transport envelope, or attempt receipt.
"""

from __future__ import annotations

import hashlib
import json
import base64
from collections.abc import Mapping
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .acquisition_tripwires import active_acquisition_boundary_tripwire_v0
from .acquisition_cases import FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0
from .acquisition_contracts import (
    AcquisitionProviderModelBinding,
    AcquisitionRequestConfiguration,
    AcquisitionSeedSetting,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    ProviderVisibleRequestBytes,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_acquisition_cases import (
    FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0,
    FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0,
    FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0,
    FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0,
    FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0,
    FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0,
    FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0,
    FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0,
    OPENROUTER_ADAPTER_GUARD_ORDER_V0,
    OPENROUTER_ADAPTER_HARNESS_ID_V0,
    OPENROUTER_ADAPTER_ID_V0,
    OpenRouterAdapterAttemptOutcome,
    OpenRouterAdapterCaseClass,
    OpenRouterAdapterFailureCode,
    OpenRouterAdapterGuardExpectationV0,
    OpenRouterAdapterGuardId,
    OpenRouterAdapterGuardState,
    OpenRouterAdapterPositiveCaseV0,
    OpenRouterAdapterProbeV0,
    MutationState,
    frozen_openrouter_adapter_case_set_sha256_v0,
)
from .openrouter_acquisition_contracts import (
    OPENROUTER_ACQUISITION_ADAPTER_ID,
    OPENROUTER_COST_CALCULATION_RULE,
    OPENROUTER_ENDPOINT_PATH,
    OPENROUTER_IDENTITY_SOURCE_FIELDS,
    OPENROUTER_MAX_OUTPUT_TOKENS,
    OPENROUTER_MODEL_ID,
    OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS,
    OPENROUTER_PROVIDER_ID,
    PREPARED_BODY_SCHEMA_VERSION,
    MAX_SIGNED_64,
    OpenRouterAttemptOutcome,
    OpenRouterAttemptReceipt,
    OpenRouterCapabilitySnapshot,
    OpenRouterCannedResponseEnvelope,
    OpenRouterControlPolicy,
    OpenRouterCostBound,
    OpenRouterEndpointPolicy,
    OpenRouterEvidenceState,
    OpenRouterFinishReason,
    OpenRouterIdentityEvidence,
    OpenRouterPreparedBody,
    OpenRouterPricingRecord,
    OpenRouterRawResponseEvidence,
    OpenRouterRawRetentionState,
    OpenRouterRoutePolicy,
    OpenRouterTokenPolicy,
    OpenRouterTransportPolicy,
    OpenRouterTransportStatus,
    OpenRouterPrivacyClassification,
    OpenRouterUsageCompleteness,
    OpenRouterUsageEvidence,
    OpenRouterUsageSource,
)
from .openrouter_acquisition_adapter import (
    OPENROUTER_CANNED_TRANSPORT_ID,
    OpenRouterCannedInvocationOutcome,
    OpenRouterCannedInvocationRecordV0,
    OpenRouterCannedTransportDirectiveV0,
    OpenRouterCannedTransportV0,
)
from .openrouter_acquisition_renderer import (
    OPENROUTER_ACQUISITION_RENDERER_VERSION,
    render_openrouter_application_body,
)


OPENROUTER_EVALUATION_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-evaluation/v0"
)
OPENROUTER_CASE_RESULT_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-case-result/v0"
)
OPENROUTER_ARTIFACT_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-evaluation-artifact/v0"
)
OPENROUTER_HISTORICAL_HASH_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-historical-hash/v0"
)
OPENROUTER_EVALUATOR_VERSION_V0 = (
    "socrateszero-openrouter-acquisition-evaluator/v0"
)
OPENROUTER_ADAPTER_REQUEST_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-request/v0"
)
OPENROUTER_FIXTURE_MANIFEST_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-fixture-manifest/v0"
)
OPENROUTER_REFERENCE_RECEIPT_SUMMARY_SCHEMA_V0 = (
    "socrateszero-openrouter-reference-canned-receipt-summary/v0"
)
OPENROUTER_SCOPED_PATH_SNAPSHOT_SCHEMA_V0 = (
    "socrateszero-openrouter-scoped-path-snapshot/v0"
)
OPENROUTER_SCOPED_MUTATION_EVIDENCE_SCHEMA_V0 = (
    "socrateszero-openrouter-scoped-mutation-evidence/v0"
)
OPENROUTER_SCOPED_PATH_INVENTORY_SCHEMA_V0 = (
    "socrateszero-openrouter-scoped-path-inventory/v0"
)

FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0: Tuple[
    Tuple[str, Tuple[str, ...]], ...
] = (
    (
        "SOURCE",
        (
            "backend/dialogues/socrates_zero/openrouter_acquisition_contracts.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_renderer.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_adapter.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_cases.py",
            "backend/dialogues/socrates_zero/openrouter_acquisition_evaluation.py",
            "backend/dialogues/socrates_zero/acquisition_tripwires.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_contracts.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_renderer.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_adapter.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_cases.py",
            "tests_dialogues/test_socrates_zero_openrouter_acquisition_evaluation.py",
            "tests_dialogues/conftest.py",
            "tests_dialogues/test_socrates_zero_acquisition_boundaries.py",
            "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/MEMORY.md",
            "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/PLAN.md",
            "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/PRESENT.md",
            "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/README.md",
        ),
    ),
    (
        "SIBLING",
        (
            "backend/dialogues/socrates_zero/__init__.py",
            "backend/dialogues/socrates_zero/acquisition.py",
            "backend/dialogues/socrates_zero/acquisition_cases.py",
            "backend/dialogues/socrates_zero/acquisition_contracts.py",
            "backend/dialogues/socrates_zero/acquisition_evaluation.py",
            "backend/dialogues/socrates_zero/acquisition_isolation_evidence.py",
            "backend/dialogues/socrates_zero/baseline.py",
            "backend/dialogues/socrates_zero/constitution.py",
            "backend/dialogues/socrates_zero/contracts.py",
            "backend/dialogues/socrates_zero/evaluation.py",
            "backend/dialogues/socrates_zero/evaluation_cases.py",
            "backend/dialogues/socrates_zero/evaluation_harness.py",
            "backend/dialogues/socrates_zero/policy.py",
            "backend/dialogues/socrates_zero/puct.py",
            "backend/dialogues/socrates_zero/strategy.py",
            "backend/dialogues/socrates_zero/value.py",
        ),
    ),
    (
        "PRODUCTION",
        (
            "backend/dialogues/agent.py",
            "backend/dialogues/ced.py",
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
            "backend/dialogues/hybrid_authority.py",
            "backend/dialogues/hybrid_epistemic.py",
            "backend/dialogues/hybrid_shadow.py",
            "backend/dialogues/hybrid_support.py",
            "backend/dialogues/ced_canonical_successor.py",
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
            "backend/dialogues/openrouter_provider.py",
            "backend/dialogues/provider_registry.py",
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
FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_ID_V0 = stable_contract_id(
    "szorpathinventory",
    {
        "schema_version": OPENROUTER_SCOPED_PATH_INVENTORY_SCHEMA_V0,
        "paths": tuple(
            {"scope": scope, "relative_path": relative_path}
            for scope, paths in FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0
            for relative_path in paths
        ),
    },
)

_P08 = OpenRouterAdapterGuardId.P08_ROUTE_POLICY
_P09 = OpenRouterAdapterGuardId.P09_FALLBACK_INTENT
_P17 = OpenRouterAdapterGuardId.P17_INPUT_TOKEN_BOUND
_P18 = OpenRouterAdapterGuardId.P18_PRICING_RECORD
_P19 = OpenRouterAdapterGuardId.P19_COST_BOUND
_HISTORICAL_ARTIFACT_LOCKS: Tuple[Tuple[str, str, str], ...] = (
    (
        "phase5-search-kernel",
        "docs/branches/feature-socrates-zero-search-v0/artifacts/"
        "socrateszero_search_kernel_benchmark_v0.json",
        "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c",
    ),
    (
        "phase7-value-primary",
        "docs/branches/feature-socrates-zero-heuristic-value-v1/artifacts/"
        "socrateszero_value_v1_primary_v0.json",
        "d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca",
    ),
    (
        "phase7-bestofn",
        "docs/branches/feature-socrates-zero-heuristic-value-v1/artifacts/"
        "socrateszero_value_v1_bestofn_v0.json",
        "86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637",
    ),
    (
        "phase8-v1-falsified",
        "docs/branches/feature-socrates-zero-canonical-successor-env-v0/artifacts/"
        "socrateszero_canonical_successor_parity_v1.json",
        "00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea",
    ),
    (
        "phase8-v2",
        "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/"
        "artifacts/socrateszero_canonical_successor_parity_v2.json",
        "8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc",
    ),
    (
        "phase8-v2-replay-lock",
        "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/"
        "artifacts/socrateszero_canonical_successor_parity_replay_lock_v2.json",
        "896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224",
    ),
    (
        "acquisition-artifact",
        "docs/branches/feature-socrates-zero-live-acquisition-contract-v0/"
        "artifacts/socrateszero_external_observation_acquisition_v0.json",
        "2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255",
    ),
    (
        "acquisition-replay-execution",
        "docs/branches/feature-socrates-zero-live-acquisition-contract-v0/"
        "artifacts/socrateszero_external_observation_acquisition_replay_execution_v0.json",
        "7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b",
    ),
    (
        "acquisition-replay-lock",
        "docs/branches/feature-socrates-zero-live-acquisition-contract-v0/"
        "artifacts/socrateszero_external_observation_acquisition_replay_lock_v0.json",
        "335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c",
    ),
)
FROZEN_CORE_BLOB_LOCK_ID_V2 = (
    "cedcorebloblockv2_"
    "2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957"
)
FROZEN_CORE_BLOB_LOCK_SOURCE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/"
    "artifacts/socrateszero_canonical_successor_parity_v2.json"
)
FROZEN_CORE_BLOB_LOCK_SOURCE_SHA256_V2 = (
    "8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc"
)


class _FrozenEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProbeConstructionState(str, Enum):
    VALIDATED = "VALIDATED"
    BASELINE_MISMATCH = "BASELINE_MISMATCH"
    UNRESOLVED = "UNRESOLVED"


class OpenRouterHypothesisStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class OpenRouterMutationScope(str, Enum):
    SOURCE = "SOURCE"
    SIBLING = "SIBLING"
    PRODUCTION = "PRODUCTION"


def _canonical_scoped_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("scoped inventory path must be nonblank")
    if "\\" in value:
        raise ValueError("scoped inventory path must use forward slashes")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or PureWindowsPath(value).drive
        or path.parts in ((), (".",))
    ):
        raise ValueError("scoped inventory path must be relative")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("scoped inventory path contains an unsafe segment")
    canonical = path.as_posix()
    if canonical != value:
        raise ValueError("scoped inventory path is not canonical")
    return canonical


class OpenRouterScopedPathDigestV0(_FrozenEvaluationModel):
    scope: OpenRouterMutationScope
    relative_path: str
    present: bool = Field(strict=True)
    sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_path_and_presence(self) -> "OpenRouterScopedPathDigestV0":
        _canonical_scoped_relative_path(self.relative_path)
        if self.present is not (self.sha256 is not None):
            raise ContractValidationError("scoped path presence/digest evidence differs")
        return self


def _scoped_snapshot_id_v0(
    rows: Tuple[OpenRouterScopedPathDigestV0, ...],
) -> str:
    return stable_contract_id(
        "szorpathsnapshot",
        {
            "schema_version": OPENROUTER_SCOPED_PATH_SNAPSHOT_SCHEMA_V0,
            "rows": tuple(row.model_dump(mode="json") for row in rows),
        },
    )


class OpenRouterScopedPathSnapshotV0(_FrozenEvaluationModel):
    schema_version: Literal[
        OPENROUTER_SCOPED_PATH_SNAPSHOT_SCHEMA_V0
    ] = OPENROUTER_SCOPED_PATH_SNAPSHOT_SCHEMA_V0
    snapshot_id: Optional[str] = None
    rows: Tuple[OpenRouterScopedPathDigestV0, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterScopedPathSnapshotV0":
        identities = tuple((row.scope, row.relative_path) for row in self.rows)
        if len(set(identities)) != len(identities):
            raise ContractValidationError("scoped path snapshot contains duplicate rows")
        if {row.scope for row in self.rows} != set(OpenRouterMutationScope):
            raise ContractValidationError("scoped path snapshot misses a required category")
        expected = _scoped_snapshot_id_v0(self.rows)
        if self.snapshot_id not in (None, expected):
            raise ContractValidationError("scoped path snapshot ID mismatch")
        object.__setattr__(self, "snapshot_id", expected)
        return self


class OpenRouterScopedPathMutationV0(_FrozenEvaluationModel):
    scope: OpenRouterMutationScope
    relative_path: str
    before_present: bool = Field(strict=True)
    before_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    after_present: bool = Field(strict=True)
    after_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    matches: Optional[bool] = Field(default=None, strict=True)
    mutation_detected: Optional[bool] = Field(default=None, strict=True)

    @model_validator(mode="after")
    def derive_match_state(self) -> "OpenRouterScopedPathMutationV0":
        _canonical_scoped_relative_path(self.relative_path)
        if self.before_present is not (self.before_sha256 is not None):
            raise ContractValidationError("before path presence/digest evidence differs")
        if self.after_present is not (self.after_sha256 is not None):
            raise ContractValidationError("after path presence/digest evidence differs")
        matches = (
            self.before_present
            and self.after_present
            and self.before_sha256 == self.after_sha256
        )
        if self.matches not in (None, matches):
            raise ContractValidationError("scoped path match claim differs from digests")
        if self.mutation_detected not in (None, not matches):
            raise ContractValidationError("scoped path mutation claim differs from digests")
        object.__setattr__(self, "matches", matches)
        object.__setattr__(self, "mutation_detected", not matches)
        return self


def _scoped_inventory_id_from_mutations_v0(
    rows: Tuple[OpenRouterScopedPathMutationV0, ...],
) -> str:
    return stable_contract_id(
        "szorpathinventory",
        {
            "schema_version": OPENROUTER_SCOPED_PATH_INVENTORY_SCHEMA_V0,
            "paths": tuple(
                {"scope": row.scope.value, "relative_path": row.relative_path}
                for row in rows
            ),
        },
    )


class OpenRouterScopedMutationEvidenceV0(_FrozenEvaluationModel):
    """Endpoint snapshot mismatches over the explicit inventory, not a watcher."""

    schema_version: Literal[
        OPENROUTER_SCOPED_MUTATION_EVIDENCE_SCHEMA_V0
    ] = OPENROUTER_SCOPED_MUTATION_EVIDENCE_SCHEMA_V0
    evidence_id: Optional[str] = None
    inventory_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    rows: Tuple[OpenRouterScopedPathMutationV0, ...] = Field(min_length=3)
    source_mutations: Optional[int] = Field(default=None, ge=0, strict=True)
    sibling_mutations: Optional[int] = Field(default=None, ge=0, strict=True)
    production_mutations: Optional[int] = Field(default=None, ge=0, strict=True)
    all_paths_unchanged: Optional[bool] = Field(default=None, strict=True)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterScopedMutationEvidenceV0":
        identities = tuple((row.scope, row.relative_path) for row in self.rows)
        if len(set(identities)) != len(identities):
            raise ContractValidationError("scoped mutation evidence contains duplicate rows")
        if {row.scope for row in self.rows} != set(OpenRouterMutationScope):
            raise ContractValidationError("scoped mutation evidence misses a category")
        expected_inventory_id = _scoped_inventory_id_from_mutations_v0(self.rows)
        if self.inventory_id != expected_inventory_id:
            raise ContractValidationError("scoped mutation inventory ID mismatch")
        before_rows = tuple(
            OpenRouterScopedPathDigestV0(
                scope=row.scope,
                relative_path=row.relative_path,
                present=row.before_present,
                sha256=row.before_sha256,
            )
            for row in self.rows
        )
        after_rows = tuple(
            OpenRouterScopedPathDigestV0(
                scope=row.scope,
                relative_path=row.relative_path,
                present=row.after_present,
                sha256=row.after_sha256,
            )
            for row in self.rows
        )
        if self.before_snapshot_id != _scoped_snapshot_id_v0(before_rows):
            raise ContractValidationError("before snapshot link differs from path evidence")
        if self.after_snapshot_id != _scoped_snapshot_id_v0(after_rows):
            raise ContractValidationError("after snapshot link differs from path evidence")
        counts = {
            scope: sum(
                row.scope is scope and bool(row.mutation_detected)
                for row in self.rows
            )
            for scope in OpenRouterMutationScope
        }
        expected_counts = (
            counts[OpenRouterMutationScope.SOURCE],
            counts[OpenRouterMutationScope.SIBLING],
            counts[OpenRouterMutationScope.PRODUCTION],
        )
        supplied_counts = (
            self.source_mutations,
            self.sibling_mutations,
            self.production_mutations,
        )
        if any(
            supplied is not None and supplied != expected
            for supplied, expected in zip(supplied_counts, expected_counts)
        ):
            raise ContractValidationError("scoped mutation count claim differs")
        unchanged = sum(expected_counts) == 0
        if self.all_paths_unchanged not in (None, unchanged):
            raise ContractValidationError("scoped all-paths claim differs")
        object.__setattr__(self, "source_mutations", expected_counts[0])
        object.__setattr__(self, "sibling_mutations", expected_counts[1])
        object.__setattr__(self, "production_mutations", expected_counts[2])
        object.__setattr__(self, "all_paths_unchanged", unchanged)
        payload = self.model_dump(mode="json", exclude={"evidence_id"})
        expected_id = stable_contract_id("szormutationevidence", payload)
        if self.evidence_id not in (None, expected_id):
            raise ContractValidationError("scoped mutation evidence ID mismatch")
        object.__setattr__(self, "evidence_id", expected_id)
        return self


class OpenRouterTripwireCountersV0(_FrozenEvaluationModel):
    external_network_attempts: Literal[0] = 0
    credential_access_attempts: Literal[0] = 0
    live_provider_calls: Literal[0] = 0
    provider_sdk_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    tool_calls: Literal[0] = 0
    canonical_application_calls: Literal[0] = 0
    source_mutations: int = Field(default=0, ge=0, strict=True)
    sibling_mutations: int = Field(default=0, ge=0, strict=True)
    production_mutations: int = Field(default=0, ge=0, strict=True)


class OpenRouterReferenceCannedReceiptSummaryV0(_FrozenEvaluationModel):
    """Privacy-safe summary of the sealed canned fixture, never actual run evidence."""

    schema_version: Literal[
        OPENROUTER_REFERENCE_RECEIPT_SUMMARY_SCHEMA_V0
    ] = OPENROUTER_REFERENCE_RECEIPT_SUMMARY_SCHEMA_V0
    summary_id: Optional[str] = None
    reference_canned_fixture_only: Literal[True] = True
    attempt_receipt_id: str
    attempt_outcome: Literal[
        OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED
    ] = OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED
    response_validation_state: Literal["ADAPTER_RESPONSE_VALIDATED"] = (
        "ADAPTER_RESPONSE_VALIDATED"
    )
    reference_canned_transport_invocations: Literal[1] = 1
    canned_response_envelope_id: str
    transport_status: Literal[
        OpenRouterTransportStatus.DELIVERED
    ] = OpenRouterTransportStatus.DELIVERED
    finish_reason: Literal[OpenRouterFinishReason.STOP] = OpenRouterFinishReason.STOP
    raw_response_evidence_id: str
    raw_evidence_state: Literal[
        OpenRouterEvidenceState.SYNTHETIC_ONLY
    ] = OpenRouterEvidenceState.SYNTHETIC_ONLY
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_response_byte_length: int = Field(ge=1, strict=True)
    raw_response_maximum_byte_length: int = Field(ge=1, strict=True)
    raw_response_truncated: Literal[False] = False
    privacy_classification: Literal[
        OpenRouterPrivacyClassification.SYNTHETIC_CANNED_OBSERVATION
    ] = OpenRouterPrivacyClassification.SYNTHETIC_CANNED_OBSERVATION
    retention_state: Literal[
        OpenRouterRawRetentionState.INLINE_RAW_BYTES_RETAINED
    ] = OpenRouterRawRetentionState.INLINE_RAW_BYTES_RETAINED
    credential_material_retained: Literal[False] = False
    sensitive_headers_retained: Literal[False] = False
    assistant_content_treatment: Literal[
        "OPAQUE_NO_SEMANTIC_EVALUATION"
    ] = "OPAQUE_NO_SEMANTIC_EVALUATION"
    identity_evidence_id: str
    identity_evidence_state: Literal[
        OpenRouterEvidenceState.SYNTHETIC_ONLY
    ] = OpenRouterEvidenceState.SYNTHETIC_ONLY
    requested_router_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    requested_model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    requested_configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_router_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    actual_model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    actual_configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_router_model_configuration_verified: Literal[True] = True
    identity_source_raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fallback_used: Literal[False] = False
    upstream_route_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    provider_side_fallback_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    usage_evidence_id: str
    usage_evidence_state: Literal[
        OpenRouterEvidenceState.SYNTHETIC_ONLY
    ] = OpenRouterEvidenceState.SYNTHETIC_ONLY
    usage_completeness: Literal[
        OpenRouterUsageCompleteness.COMPLETE
    ] = OpenRouterUsageCompleteness.COMPLETE
    usage_source: Literal[
        OpenRouterUsageSource.PROVIDER_REPORTED
    ] = OpenRouterUsageSource.PROVIDER_REPORTED
    usage_source_raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)
    total_tokens: int = Field(ge=0, strict=True)
    usage_cost_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    usage_cost_bound_id: Literal[None] = None
    usage_cost_microusd: Literal[None] = None
    pricing_record_id: str
    pricing_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    pricing_authority_reference: Literal[None] = None
    pricing_source_name: Literal[None] = None
    pricing_source_version: Literal[None] = None
    pricing_effective_version: Literal[None] = None
    pricing_provenance_sha256: Literal[None] = None
    pricing_input_microusd_per_million_tokens: Literal[None] = None
    pricing_output_microusd_per_million_tokens: Literal[None] = None
    pricing_fixed_non_token_microusd: Literal[None] = None
    pricing_unknown_line_items: Tuple[str, ...]
    cost_bound_id: str
    cost_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    maximum_input_cost_microusd: Literal[None] = None
    maximum_output_cost_microusd: Literal[None] = None
    maximum_fixed_cost_microusd: Literal[None] = None
    maximum_total_cost_microusd: Literal[None] = None
    cost_unknown_line_items: Tuple[str, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterReferenceCannedReceiptSummaryV0":
        if self.raw_response_byte_length > self.raw_response_maximum_byte_length:
            raise ContractValidationError("reference raw response exceeds frozen bound")
        if not (
            self.raw_response_sha256
            == self.identity_source_raw_response_sha256
            == self.usage_source_raw_response_sha256
        ):
            raise ContractValidationError("reference derived evidence has a raw-digest mismatch")
        if not (
            self.requested_configuration_digest
            == self.actual_configuration_digest
        ):
            raise ContractValidationError("reference requested/actual configuration differs")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ContractValidationError("reference usage total is inconsistent")
        if self.pricing_unknown_line_items != self.cost_unknown_line_items:
            raise ContractValidationError("reference pricing/cost unknown lines differ")
        payload = self.model_dump(mode="json", exclude={"summary_id"})
        expected = stable_contract_id("szorrefreceipt", payload)
        if self.summary_id not in (None, expected):
            raise ContractValidationError("reference receipt summary ID mismatch")
        object.__setattr__(self, "summary_id", expected)
        return self


class OpenRouterCandidateEvidenceV0(_FrozenEvaluationModel):
    candidate_adapter_id: Literal[
        OPENROUTER_ACQUISITION_ADAPTER_ID
    ] = OPENROUTER_ACQUISITION_ADAPTER_ID
    case_design_adapter_id: Literal[
        OPENROUTER_ADAPTER_ID_V0
    ] = OPENROUTER_ADAPTER_ID_V0
    provider_id: Literal[OPENROUTER_PROVIDER_ID] = OPENROUTER_PROVIDER_ID
    model_id: Literal[OPENROUTER_MODEL_ID] = OPENROUTER_MODEL_ID
    semantic_request_id: str
    source_provider_visible_request_id: str
    source_provider_visible_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_provider_visible_byte_length: int = Field(ge=1, strict=True)
    endpoint_policy_id: str
    transport_policy_id: str
    route_policy_id: str
    control_policy_id: str
    capability_snapshot_id: str
    prepared_body_schema_version: Literal[
        PREPARED_BODY_SCHEMA_VERSION
    ] = PREPARED_BODY_SCHEMA_VERSION
    prepared_body_id: str
    canonical_body_json: str
    prepared_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prepared_body_byte_length: int = Field(ge=1, strict=True)
    token_policy_id: str
    payload_input_token_upper_bound: int = Field(ge=1, strict=True)
    max_output_tokens: Literal[
        OPENROUTER_MAX_OUTPUT_TOKENS
    ] = OPENROUTER_MAX_OUTPUT_TOKENS
    payload_only_total_token_upper_bound: int = Field(ge=1, strict=True)
    authoritative_provider_input_token_upper_bound: Literal[None] = None
    authoritative_total_token_upper_bound: Literal[None] = None
    pricing_record_id: str
    cost_bound_id: str
    raw_response_evidence_id: str
    identity_evidence_id: str
    usage_evidence_id: str
    canned_response_envelope_id: str
    attempt_receipt_id: str
    reference_receipt_summary: OpenRouterReferenceCannedReceiptSummaryV0
    reference_receipt_summary_id: str
    baseline_projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_manifest_id: str
    reference_canned_fixture_only: Literal[True] = True
    actual_canned_transport_invocations: Literal[0] = 0
    actual_attempt_receipt_id: Literal[None] = None
    actual_response_receipt: Literal[None] = None
    renderer_version: Literal[
        OPENROUTER_ACQUISITION_RENDERER_VERSION
    ] = OPENROUTER_ACQUISITION_RENDERER_VERSION
    route_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    provider_side_fallback_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    provider_input_bound_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    pricing_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    cost_state: Literal[
        OpenRouterEvidenceState.NOT_ESTABLISHED
    ] = OpenRouterEvidenceState.NOT_ESTABLISHED
    unresolved_mandatory_guards: Tuple[
        OpenRouterAdapterGuardId, ...
    ] = FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0
    live_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_fail_closed_state(self) -> "OpenRouterCandidateEvidenceV0":
        if (
            self.unresolved_mandatory_guards
            != FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0
        ):
            raise ContractValidationError("candidate unresolved guards changed")
        summary = self.reference_receipt_summary
        if self.reference_receipt_summary_id != summary.summary_id:
            raise ContractValidationError("candidate reference summary link changed")
        summary_links = (
            (self.raw_response_evidence_id, summary.raw_response_evidence_id),
            (self.identity_evidence_id, summary.identity_evidence_id),
            (self.usage_evidence_id, summary.usage_evidence_id),
            (self.canned_response_envelope_id, summary.canned_response_envelope_id),
            (self.attempt_receipt_id, summary.attempt_receipt_id),
            (self.pricing_record_id, summary.pricing_record_id),
            (self.cost_bound_id, summary.cost_bound_id),
        )
        if any(left != right for left, right in summary_links):
            raise ContractValidationError("candidate reference receipt links changed")
        if self.provider_side_fallback_state is not summary.provider_side_fallback_state:
            raise ContractValidationError("candidate provider-side fallback evidence changed")
        raw = self.canonical_body_json.encode("utf-8")
        try:
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractValidationError("candidate body is not canonical UTF-8 JSON") from exc
        if not isinstance(parsed, dict) or canonical_json(parsed).encode("utf-8") != raw:
            raise ContractValidationError("candidate body is not canonical UTF-8 JSON")
        if self.prepared_body_byte_length != len(raw):
            raise ContractValidationError("candidate body length evidence changed")
        if self.prepared_body_sha256 != hashlib.sha256(raw).hexdigest():
            raise ContractValidationError("candidate body digest evidence changed")
        if self.payload_input_token_upper_bound != len(raw):
            raise ContractValidationError("candidate payload bound differs from body bytes")
        if self.payload_only_total_token_upper_bound != (
            len(raw) + OPENROUTER_MAX_OUTPUT_TOKENS
        ):
            raise ContractValidationError("candidate payload-only total bound changed")
        messages = parsed.get("messages")
        if messages != [
            {
                "content": (
                    "Ask one concise opening Socratic question without answering "
                    "the user's question."
                ),
                "role": "system",
            },
            {
                "content": "Is knowledge merely justified true belief?",
                "role": "user",
            },
        ]:
            raise ContractValidationError("candidate did not render the frozen prompt")
        manifest_payload = {
            "schema_version": OPENROUTER_FIXTURE_MANIFEST_SCHEMA_V0,
            "candidate_adapter_id": self.candidate_adapter_id,
            "case_design_adapter_id": self.case_design_adapter_id,
            "semantic_request_id": self.semantic_request_id,
            "source_provider_visible_request_id": (
                self.source_provider_visible_request_id
            ),
            "source_provider_visible_sha256": self.source_provider_visible_sha256,
            "capability_snapshot_id": self.capability_snapshot_id,
            "endpoint_policy_id": self.endpoint_policy_id,
            "route_policy_id": self.route_policy_id,
            "control_policy_id": self.control_policy_id,
            "renderer_version": self.renderer_version,
            "prepared_body_id": self.prepared_body_id,
            "prepared_body_sha256": self.prepared_body_sha256,
            "transport_policy_id": self.transport_policy_id,
            "token_policy_id": self.token_policy_id,
            "pricing_record_id": self.pricing_record_id,
            "cost_bound_id": self.cost_bound_id,
            "raw_response_evidence_id": self.raw_response_evidence_id,
            "identity_evidence_id": self.identity_evidence_id,
            "usage_evidence_id": self.usage_evidence_id,
            "canned_response_envelope_id": self.canned_response_envelope_id,
            "attempt_receipt_id": self.attempt_receipt_id,
            "reference_receipt_summary_id": self.reference_receipt_summary_id,
            "baseline_projection_sha256": self.baseline_projection_sha256,
            "reference_canned_fixture_only": self.reference_canned_fixture_only,
            "actual_canned_transport_invocations": (
                self.actual_canned_transport_invocations
            ),
            "actual_attempt_receipt_id": self.actual_attempt_receipt_id,
            "actual_response_receipt": self.actual_response_receipt,
        }
        expected_manifest_id = stable_contract_id(
            "szorfixture", manifest_payload
        )
        if self.fixture_manifest_id != expected_manifest_id:
            raise ContractValidationError("candidate fixture manifest ID changed")
        return self


class OpenRouterMutationObservationV0(_FrozenEvaluationModel):
    path: str
    concrete_projection_paths: Tuple[str, ...]
    declared_before_json: str
    declared_after_json: str
    actual_before_json: Optional[str]
    baseline_source: Literal[
        "CONTRACT",
        "RENDERER",
        "EVALUATOR_REQUEST",
        "CANNED_CONTRACT",
        "UNRESOLVED",
    ]
    construction_state: ProbeConstructionState
    direct_vector_field: str
    independently_derived_guard_id: OpenRouterAdapterGuardId
    independently_derived_failure: OpenRouterAdapterFailureCode


class OpenRouterProbeConstructionEvidenceV0(_FrozenEvaluationModel):
    observations: Tuple[OpenRouterMutationObservationV0, ...]
    declared_intentionally_changed_fields: Tuple[str, ...]
    derived_intentionally_changed_fields: Tuple[str, ...]
    declared_dependently_changed_fields: Tuple[str, ...]
    derived_dependently_changed_fields: Tuple[str, ...]
    mutation_vector_exact: bool
    construction_fully_validated: bool
    construction_failure_code: Optional[
        Literal["INVALID_PROBE_CONSTRUCTION"]
    ] = None
    baseline_mismatch_count: int = Field(ge=0, strict=True)
    unresolved_path_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_counts(self) -> "OpenRouterProbeConstructionEvidenceV0":
        mismatches = sum(
            item.construction_state is ProbeConstructionState.BASELINE_MISMATCH
            for item in self.observations
        )
        unresolved = sum(
            item.construction_state is ProbeConstructionState.UNRESOLVED
            for item in self.observations
        )
        if self.baseline_mismatch_count != mismatches:
            raise ContractValidationError("probe baseline-mismatch count drifted")
        if self.unresolved_path_count != unresolved:
            raise ContractValidationError("probe unresolved-path count drifted")
        expected_full = mismatches == 0 and unresolved == 0
        if self.construction_fully_validated is not expected_full:
            raise ContractValidationError("probe construction status drifted")
        expected_failure = None if expected_full else "INVALID_PROBE_CONSTRUCTION"
        if self.construction_failure_code != expected_failure:
            raise ContractValidationError("probe construction failure code drifted")
        expected_vector = (
            self.declared_intentionally_changed_fields
            == self.derived_intentionally_changed_fields
            and self.declared_dependently_changed_fields
            == self.derived_dependently_changed_fields
        )
        if self.mutation_vector_exact is not expected_vector:
            raise ContractValidationError("probe mutation-vector status drifted")
        return self


class OpenRouterAttemptEvaluationReceiptV0(_FrozenEvaluationModel):
    attempt_receipt_id: Optional[str] = None
    case_id: str
    attempt_ordinal: int = Field(ge=1, le=2, strict=True)
    outcome: Literal[
        OpenRouterAdapterAttemptOutcome.REJECTED
    ] = OpenRouterAdapterAttemptOutcome.REJECTED
    failure_guard_id: OpenRouterAdapterGuardId
    failure_code: OpenRouterAdapterFailureCode
    canned_transport_invocations: Literal[0] = 0
    tripwire_counters: OpenRouterTripwireCountersV0 = Field(
        default_factory=OpenRouterTripwireCountersV0
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterAttemptEvaluationReceiptV0":
        payload = self.model_dump(mode="json", exclude={"attempt_receipt_id"})
        expected = stable_contract_id("szorevalattempt", payload)
        if self.attempt_receipt_id not in (None, expected):
            raise ContractValidationError("evaluation attempt receipt ID mismatch")
        object.__setattr__(self, "attempt_receipt_id", expected)
        return self


class OpenRouterCaseEvaluationV0(_FrozenEvaluationModel):
    schema_version: Literal[
        OPENROUTER_CASE_RESULT_SCHEMA_V0
    ] = OPENROUTER_CASE_RESULT_SCHEMA_V0
    case_id: str
    case_fingerprint: str
    case_class: OpenRouterAdapterCaseClass
    expected_outcome: OpenRouterAdapterAttemptOutcome
    expected_guard_id: Optional[OpenRouterAdapterGuardId]
    expected_primary_failure: Optional[OpenRouterAdapterFailureCode]
    actual_outcome: Literal[
        OpenRouterAdapterAttemptOutcome.REJECTED
    ] = OpenRouterAdapterAttemptOutcome.REJECTED
    actual_guard_id: OpenRouterAdapterGuardId
    actual_primary_failure: OpenRouterAdapterFailureCode
    actual_guard_trace: Tuple[OpenRouterAdapterGuardExpectationV0, ...]
    expected_canned_invocations: int = Field(ge=0, le=2, strict=True)
    evaluator_input_attempt_count: int = Field(ge=1, le=2, strict=True)
    expected_attempt_receipts: int = Field(ge=1, le=2, strict=True)
    observed_canned_invocations: Literal[0] = 0
    attempt_receipts: Tuple[OpenRouterAttemptEvaluationReceiptV0, ...]
    construction_evidence: Optional[OpenRouterProbeConstructionEvidenceV0]
    primary_result_exact: bool
    guard_trace_exact: bool
    invocation_count_exact: bool
    attempt_count_exact: bool
    scoring_eligible: bool
    case_passed: bool

    @model_validator(mode="after")
    def validate_result(self) -> "OpenRouterCaseEvaluationV0":
        if len(self.actual_guard_trace) != len(OPENROUTER_ADAPTER_GUARD_ORDER_V0):
            raise ContractValidationError("actual guard trace length changed")
        if any(
            receipt.case_id != self.case_id
            or receipt.failure_guard_id is not self.actual_guard_id
            or receipt.failure_code is not self.actual_primary_failure
            for receipt in self.attempt_receipts
        ):
            raise ContractValidationError("attempt receipt does not match case result")
        expected_primary = (
            self.expected_outcome is self.actual_outcome
            and self.expected_guard_id is self.actual_guard_id
            and self.expected_primary_failure is self.actual_primary_failure
        )
        if self.primary_result_exact is not expected_primary:
            raise ContractValidationError("primary-result comparison drifted")
        if self.invocation_count_exact is not (
            self.expected_canned_invocations == self.observed_canned_invocations
        ):
            raise ContractValidationError("invocation comparison drifted")
        if self.attempt_count_exact is not (
            self.expected_attempt_receipts == len(self.attempt_receipts)
        ):
            raise ContractValidationError("attempt-receipt comparison drifted")
        if len(self.attempt_receipts) != self.evaluator_input_attempt_count:
            raise ContractValidationError(
                "actual receipts differ from evaluator-owned attempt topology"
            )
        expected_pass = (
            self.scoring_eligible
            and
            self.primary_result_exact
            and self.guard_trace_exact
            and self.invocation_count_exact
            and self.attempt_count_exact
            and (
                self.construction_evidence is None
                or (
                    self.construction_evidence.construction_fully_validated
                    and self.construction_evidence.mutation_vector_exact
                )
            )
        )
        if self.case_passed is not expected_pass:
            raise ContractValidationError("case pass status drifted")
        expected_eligible = (
            self.construction_evidence is None
            or (
                self.construction_evidence.construction_fully_validated
                and self.construction_evidence.mutation_vector_exact
            )
        )
        if self.scoring_eligible is not expected_eligible:
            raise ContractValidationError("case scoring eligibility drifted")
        return self


class OpenRouterEvaluationMetricsV0(_FrozenEvaluationModel):
    schema_version: Literal[
        OPENROUTER_EVALUATION_SCHEMA_V0
    ] = OPENROUTER_EVALUATION_SCHEMA_V0
    metrics_id: Optional[str] = None
    cases_total: Literal[59] = 59
    positive_cases: Literal[7] = 7
    positive_complete_case_results: int = Field(ge=0, le=7, strict=True)
    positive_attempt_receipts: int = Field(ge=0, le=8, strict=True)
    exact_positive_receipts: int = Field(ge=0, le=8, strict=True)
    orthogonal_probes: Literal[44] = 44
    orthogonal_exact_primary_results: int = Field(ge=0, le=44, strict=True)
    precedence_probes: Literal[8] = 8
    precedence_exact_primary_results: int = Field(ge=0, le=8, strict=True)
    attempt_receipts_total: int = Field(ge=0, le=60, strict=True)
    canned_transport_invocations: int = Field(ge=0, le=34, strict=True)
    invalid_probe_constructions: int = Field(ge=0, le=52, strict=True)
    unexpected_failure_or_mismatch_count: int = Field(ge=0, le=59, strict=True)
    historical_lock_mismatches: int = Field(ge=0, le=9, strict=True)
    core_lock_mismatches: int = Field(ge=0, le=1, strict=True)
    body_byte_mismatch_results: int = Field(ge=0, le=59, strict=True)
    entropy_violation_results: int = Field(ge=0, le=59, strict=True)
    route_policy_unproven_results: int = Field(ge=0, le=59, strict=True)
    fallback_intent_control_failures: int = Field(ge=0, le=1, strict=True)
    token_bound_failures: int = Field(ge=0, le=1, strict=True)
    pricing_cost_evidence_failures: int = Field(ge=0, le=2, strict=True)
    timeout_worker_leaks: int = Field(ge=0, le=59, strict=True)
    multiple_transport_invocations: int = Field(ge=0, le=59, strict=True)
    raw_response_evidence_failures: int = Field(ge=0, le=59, strict=True)
    usage_incompleteness: int = Field(ge=0, le=59, strict=True)
    false_zero_violations: int = Field(ge=0, le=59, strict=True)
    identity_collisions: int = Field(ge=0, le=60, strict=True)
    credential_header_leakage: int = Field(ge=0, le=59, strict=True)
    body_byte_mismatches_accepted: int = Field(ge=0, le=59, strict=True)
    entropy_violations_accepted: int = Field(ge=0, le=59, strict=True)
    model_provider_configuration_mismatches_accepted: int = Field(
        ge=0, le=59, strict=True
    )
    fallback_activations_accepted: int = Field(ge=0, le=59, strict=True)
    retry_activations_accepted: int = Field(ge=0, le=59, strict=True)
    streaming_activations_accepted: int = Field(ge=0, le=59, strict=True)
    tool_activations_accepted: int = Field(ge=0, le=59, strict=True)
    receipt_mismatches_accepted: int = Field(ge=0, le=59, strict=True)
    receipt_mismatch_results: int = Field(ge=0, le=59, strict=True)
    external_network_attempts: Literal[0] = 0
    credential_access_attempts: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_sdk_calls: Literal[0] = 0
    model_calls: Literal[0] = 0
    tool_calls: Literal[0] = 0
    ced_application_invocations: Literal[0] = 0
    source_mutations: int = Field(default=0, ge=0, strict=True)
    sibling_mutations: int = Field(default=0, ge=0, strict=True)
    production_mutations: int = Field(default=0, ge=0, strict=True)
    accepted_control_violations: int = Field(ge=0, le=59, strict=True)
    accepted_identity_mismatches: int = Field(ge=0, le=59, strict=True)
    accepted_fallback_retry_stream_tool_activations: int = Field(
        ge=0, le=59, strict=True
    )
    accepted_token_pricing_cost_failures: int = Field(ge=0, le=59, strict=True)
    accepted_raw_usage_privacy_receipt_failures: int = Field(
        ge=0, le=59, strict=True
    )
    unexpected_multiple_transport_invocations: int = Field(
        ge=0, le=59, strict=True
    )
    surviving_tasks: int = Field(ge=0, le=59, strict=True)
    accepted_late_mutations: int = Field(ge=0, le=59, strict=True)
    pricing_status: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_model_pricing_status: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    thresholds_passed: Optional[bool] = Field(default=None, strict=True)
    threshold_failure_reasons: Tuple[str, ...] = ()

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterEvaluationMetricsV0":
        checks = {
            "CANNED_TRANSPORT_INVOCATIONS": (
                self.canned_transport_invocations
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.required_canned_transport_invocations
            ),
            "CORE_LOCKS": self.core_lock_mismatches == 0,
            "HISTORICAL_LOCKS": self.historical_lock_mismatches == 0,
            "INVALID_PROBE_CONSTRUCTIONS": self.invalid_probe_constructions == 0,
            "ORTHOGONAL_EXACT_PRIMARY_RESULTS": (
                self.orthogonal_exact_primary_results
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.required_orthogonal_exact_primary_results
            ),
            "POSITIVE_COMPLETE_CASE_RESULTS": (
                self.positive_complete_case_results
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.required_positive_complete_case_results
            ),
            "POSITIVE_RECEIPTS": (
                self.exact_positive_receipts
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.required_positive_attempt_receipts
            ),
            "PRECEDENCE_EXACT_PRIMARY_RESULTS": (
                self.precedence_exact_primary_results
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.required_precedence_exact_primary_results
            ),
            "PRICING_STATUS": (
                self.pricing_status
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.pricing_status
            ),
            "RECEIPT_TOTAL": (
                self.attempt_receipts_total
                == FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.required_attempt_receipts_total
            ),
            "UNEXPECTED_FAILURE_OR_MISMATCH": (
                self.unexpected_failure_or_mismatch_count == 0
            ),
            "UNRESOLVED_PRICING_OR_COST_CONTROL": (
                self.pricing_cost_evidence_failures == 0
            ),
            "UNRESOLVED_FALLBACK_INTENT_CONTROL": (
                self.fallback_intent_control_failures == 0
            ),
            "UNRESOLVED_TOKEN_BOUND_CONTROL": self.token_bound_failures == 0,
            "ZERO_ACCEPTED_VIOLATIONS": all(
                value == 0
                for value in (
                    self.accepted_control_violations,
                    self.accepted_identity_mismatches,
                    self.accepted_fallback_retry_stream_tool_activations,
                    self.accepted_token_pricing_cost_failures,
                    self.accepted_raw_usage_privacy_receipt_failures,
                    self.body_byte_mismatches_accepted,
                    self.entropy_violations_accepted,
                    self.model_provider_configuration_mismatches_accepted,
                    self.fallback_activations_accepted,
                    self.retry_activations_accepted,
                    self.streaming_activations_accepted,
                    self.tool_activations_accepted,
                    self.receipt_mismatches_accepted,
                )
            ),
            "ZERO_EXTERNAL_OR_CANONICAL_ACTIVITY": all(
                value == 0
                for value in (
                    self.external_network_attempts,
                    self.credential_access_attempts,
                    self.provider_calls,
                    self.provider_sdk_calls,
                    self.model_calls,
                    self.tool_calls,
                    self.ced_application_invocations,
                    self.source_mutations,
                    self.sibling_mutations,
                    self.production_mutations,
                )
            ),
        }
        reasons = tuple(sorted(name for name, passed in checks.items() if not passed))
        passed = not reasons
        if self.thresholds_passed not in (None, passed):
            raise ContractValidationError("threshold pass flag differs from evidence")
        if self.threshold_failure_reasons not in ((), reasons):
            raise ContractValidationError("threshold failure reasons differ from evidence")
        object.__setattr__(self, "thresholds_passed", passed)
        object.__setattr__(self, "threshold_failure_reasons", reasons)
        payload = self.model_dump(mode="json", exclude={"metrics_id"})
        expected = stable_contract_id("szoracqmetrics", payload)
        if self.metrics_id not in (None, expected):
            raise ContractValidationError("evaluation metrics ID mismatch")
        object.__setattr__(self, "metrics_id", expected)
        return self


class OpenRouterHistoricalHashEvidenceV0(_FrozenEvaluationModel):
    schema_version: Literal[
        OPENROUTER_HISTORICAL_HASH_SCHEMA_V0
    ] = OPENROUTER_HISTORICAL_HASH_SCHEMA_V0
    label: str
    repository_path: str
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    matches: bool

    @model_validator(mode="after")
    def validate_match(self) -> "OpenRouterHistoricalHashEvidenceV0":
        expected = self.observed_sha256 == self.expected_sha256
        if self.matches is not expected:
            raise ContractValidationError("historical hash match flag drifted")
        return self


class OpenRouterCoreBlobLockEvidenceV0(_FrozenEvaluationModel):
    repository_path: Literal[
        FROZEN_CORE_BLOB_LOCK_SOURCE_PATH_V2
    ] = FROZEN_CORE_BLOB_LOCK_SOURCE_PATH_V2
    source_artifact_expected_sha256: Literal[
        FROZEN_CORE_BLOB_LOCK_SOURCE_SHA256_V2
    ] = FROZEN_CORE_BLOB_LOCK_SOURCE_SHA256_V2
    source_artifact_observed_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    expected_lock_id: Literal[
        FROZEN_CORE_BLOB_LOCK_ID_V2
    ] = FROZEN_CORE_BLOB_LOCK_ID_V2
    actual_top_level_lock_id: Optional[str] = None
    actual_embedded_lock_id: Optional[str] = None
    actual_embedded_fingerprint: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    recomputed_embedded_lock_id: Optional[str] = None
    recomputed_embedded_fingerprint: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    matches: bool

    @model_validator(mode="after")
    def validate_match(self) -> "OpenRouterCoreBlobLockEvidenceV0":
        expected_fingerprint = FROZEN_CORE_BLOB_LOCK_ID_V2.removeprefix(
            "cedcorebloblockv2_"
        )
        expected = all(
            (
                self.source_artifact_observed_sha256
                == FROZEN_CORE_BLOB_LOCK_SOURCE_SHA256_V2,
                self.actual_top_level_lock_id == FROZEN_CORE_BLOB_LOCK_ID_V2,
                self.actual_embedded_lock_id == FROZEN_CORE_BLOB_LOCK_ID_V2,
                self.actual_embedded_fingerprint == expected_fingerprint,
                self.recomputed_embedded_lock_id == FROZEN_CORE_BLOB_LOCK_ID_V2,
                self.recomputed_embedded_fingerprint == expected_fingerprint,
            )
        )
        if self.matches is not expected:
            raise ContractValidationError("core blob-lock match flag drifted")
        return self


class OpenRouterEvaluationArtifactV0(_FrozenEvaluationModel):
    schema_version: Literal[
        OPENROUTER_ARTIFACT_SCHEMA_V0
    ] = OPENROUTER_ARTIFACT_SCHEMA_V0
    artifact_id: Optional[str] = None
    artifact_payload_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    evaluator_version: Literal[
        OPENROUTER_EVALUATOR_VERSION_V0
    ] = OPENROUTER_EVALUATOR_VERSION_V0
    authoritative: Literal[True] = True
    candidate_adapter_id: Literal[
        OPENROUTER_ACQUISITION_ADAPTER_ID
    ] = OPENROUTER_ACQUISITION_ADAPTER_ID
    case_design_adapter_id: Literal[
        OPENROUTER_ADAPTER_ID_V0
    ] = OPENROUTER_ADAPTER_ID_V0
    capability_snapshot_id: str
    endpoint_policy_id: str
    route_policy_id: str
    control_policy_id: str
    renderer_id: Literal[
        OPENROUTER_ACQUISITION_RENDERER_VERSION
    ] = OPENROUTER_ACQUISITION_RENDERER_VERSION
    transport_policy_id: str
    token_policy_id: str
    pricing_record_id: str
    cost_bound_id: str
    raw_response_evidence_id: str
    identity_evidence_id: str
    usage_evidence_id: str
    canned_response_envelope_id: str
    attempt_receipt_id: str
    reference_receipt_summary_id: str
    reference_receipt_summary: OpenRouterReferenceCannedReceiptSummaryV0
    reference_canned_fixture_only: Literal[True] = True
    actual_canned_transport_invocations: Literal[0] = 0
    actual_response_receipt: Literal[None] = None
    baseline_projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_manifest_id: str
    case_set_id: str
    harness_id: Literal[
        OPENROUTER_ADAPTER_HARNESS_ID_V0
    ] = OPENROUTER_ADAPTER_HARNESS_ID_V0
    metrics_id: str
    thresholds_id: str
    case_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_guard_rule: Literal[
        FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0
    ] = FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0
    candidate_evidence: OpenRouterCandidateEvidenceV0
    case_results: Tuple[OpenRouterCaseEvaluationV0, ...]
    metrics: OpenRouterEvaluationMetricsV0
    historical_hashes: Tuple[OpenRouterHistoricalHashEvidenceV0, ...] = Field(
        min_length=9, max_length=9
    )
    core_blob_lock: OpenRouterCoreBlobLockEvidenceV0
    tripwire_counters: OpenRouterTripwireCountersV0
    scoped_mutation_evidence: OpenRouterScopedMutationEvidenceV0
    hypothesis_status: Optional[OpenRouterHypothesisStatus] = None
    replay_lock_created: bool = Field(default=False, strict=True)
    production_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterEvaluationArtifactV0":
        if len(self.case_results) != 59:
            raise ContractValidationError("authoritative artifact requires 59 cases")
        if tuple(result.case_id for result in self.case_results) != tuple(
            [case.case_id for case in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0]
            + [probe.probe_id for probe in FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0]
            + [probe.probe_id for probe in FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0]
        ):
            raise ContractValidationError("artifact case order differs from frozen set")
        frozen_cases = (
            FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
            + FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
            + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
        )
        independently_recomputed = tuple(
            evaluate_openrouter_adapter_case_v0(case) for case in frozen_cases
        )
        if self.case_results != independently_recomputed:
            raise ContractValidationError(
                "artifact case evidence differs from independent evaluation"
            )
        if self.case_set_id != FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.case_set_id:
            raise ContractValidationError("artifact case-set ID differs from frozen set")
        if self.case_set_sha256 != frozen_openrouter_adapter_case_set_sha256_v0():
            raise ContractValidationError("artifact case-set hash differs from frozen set")
        frozen_history = tuple(
            (label, path.replace("\\", "/"), expected)
            for label, path, expected in _HISTORICAL_ARTIFACT_LOCKS
        )
        actual_history = tuple(
            (
                item.label,
                item.repository_path.replace("\\", "/"),
                item.expected_sha256,
            )
            for item in self.historical_hashes
        )
        if actual_history != frozen_history:
            raise ContractValidationError("artifact historical lock membership changed")
        if self.candidate_evidence != build_openrouter_candidate_evidence_v0():
            raise ContractValidationError(
                "artifact candidate evidence differs from frozen implementation"
            )
        if self.reference_receipt_summary != self.candidate_evidence.reference_receipt_summary:
            raise ContractValidationError("artifact reference receipt summary differs")
        if self.reference_canned_fixture_only is not True:
            raise ContractValidationError("artifact reference fixture classification changed")
        if self.actual_canned_transport_invocations != 0 or self.actual_response_receipt is not None:
            raise ContractValidationError("artifact conflates reference fixture with actual evidence")
        links = {
            "candidate_adapter_id": self.candidate_adapter_id,
            "case_design_adapter_id": self.case_design_adapter_id,
            "capability_snapshot_id": self.capability_snapshot_id,
            "endpoint_policy_id": self.endpoint_policy_id,
            "route_policy_id": self.route_policy_id,
            "control_policy_id": self.control_policy_id,
            "renderer_version": self.renderer_id,
            "transport_policy_id": self.transport_policy_id,
            "token_policy_id": self.token_policy_id,
            "pricing_record_id": self.pricing_record_id,
            "cost_bound_id": self.cost_bound_id,
            "raw_response_evidence_id": self.raw_response_evidence_id,
            "identity_evidence_id": self.identity_evidence_id,
            "usage_evidence_id": self.usage_evidence_id,
            "canned_response_envelope_id": self.canned_response_envelope_id,
            "attempt_receipt_id": self.attempt_receipt_id,
            "reference_receipt_summary_id": self.reference_receipt_summary_id,
            "baseline_projection_sha256": self.baseline_projection_sha256,
            "fixture_manifest_id": self.fixture_manifest_id,
        }
        candidate_links = {
            name: getattr(self.candidate_evidence, name)
            for name in links
        }
        if links != candidate_links:
            raise ContractValidationError("artifact candidate contract links differ")
        case_candidate_links = {
            "candidate_adapter_id": self.candidate_evidence.candidate_adapter_id,
            "fixture_manifest_id": self.candidate_evidence.fixture_manifest_id,
            "baseline_projection_sha256": (
                self.candidate_evidence.baseline_projection_sha256
            ),
            "semantic_request_id": self.candidate_evidence.semantic_request_id,
            "source_provider_visible_request_id": (
                self.candidate_evidence.source_provider_visible_request_id
            ),
            "capability_snapshot_id": self.candidate_evidence.capability_snapshot_id,
            "endpoint_policy_id": self.candidate_evidence.endpoint_policy_id,
            "route_policy_id": self.candidate_evidence.route_policy_id,
            "control_policy_id": self.candidate_evidence.control_policy_id,
            "prepared_body_id": self.candidate_evidence.prepared_body_id,
            "transport_policy_id": self.candidate_evidence.transport_policy_id,
            "token_policy_id": self.candidate_evidence.token_policy_id,
            "pricing_record_id": self.candidate_evidence.pricing_record_id,
            "cost_bound_id": self.candidate_evidence.cost_bound_id,
            "raw_response_evidence_id": (
                self.candidate_evidence.raw_response_evidence_id
            ),
            "identity_evidence_id": self.candidate_evidence.identity_evidence_id,
            "usage_evidence_id": self.candidate_evidence.usage_evidence_id,
            "canned_response_envelope_id": (
                self.candidate_evidence.canned_response_envelope_id
            ),
            "attempt_receipt_id": self.candidate_evidence.attempt_receipt_id,
        }
        frozen_case_links = {
            name: getattr(FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0, name)
            for name in case_candidate_links
        }
        if case_candidate_links != frozen_case_links:
            raise ContractValidationError("artifact case-set fixture graph differs")
        if (
            self.candidate_evidence.unresolved_mandatory_guards
            != FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.known_unresolved_mandatory_guards
        ):
            raise ContractValidationError("artifact unresolved guard links differ")
        if self.harness_id != FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.harness_id:
            raise ContractValidationError("artifact harness link differs")
        if self.thresholds_id != FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.thresholds_id:
            raise ContractValidationError("artifact thresholds link differs")
        if self.metrics_id != self.metrics.metrics_id:
            raise ContractValidationError("artifact metrics link differs")
        activity_links = {
            "external_network_attempts": "external_network_attempts",
            "credential_access_attempts": "credential_access_attempts",
            "provider_calls": "live_provider_calls",
            "provider_sdk_calls": "provider_sdk_calls",
            "model_calls": "model_executions",
            "tool_calls": "tool_calls",
            "ced_application_invocations": "canonical_application_calls",
            "source_mutations": "source_mutations",
            "sibling_mutations": "sibling_mutations",
            "production_mutations": "production_mutations",
        }
        if any(
            getattr(self.metrics, metric_name)
            != getattr(self.tripwire_counters, counter_name)
            for metric_name, counter_name in activity_links.items()
        ):
            raise ContractValidationError(
                "artifact activity metrics differ from tripwire counters"
            )
        _assert_frozen_scoped_mutation_accounting_v0(
            self.scoped_mutation_evidence,
            self.tripwire_counters,
            self.metrics,
        )
        expected_metrics = _metrics(
            self.case_results,
            self.historical_hashes,
            self.core_blob_lock,
            self.candidate_evidence,
            self.tripwire_counters,
        )
        if self.metrics != expected_metrics:
            raise ContractValidationError("artifact metrics differ from case evidence")
        derived_status = (
            OpenRouterHypothesisStatus.SUPPORTED
            if self.metrics.thresholds_passed
            and not self.candidate_evidence.unresolved_mandatory_guards
            else OpenRouterHypothesisStatus.FALSIFIED
        )
        if self.hypothesis_status not in (None, derived_status):
            raise ContractValidationError("hypothesis status differs from evidence")
        if self.replay_lock_created and derived_status is not OpenRouterHypothesisStatus.SUPPORTED:
            raise ContractValidationError("replay lock requires a complete pass")
        object.__setattr__(self, "hypothesis_status", derived_status)
        payload = self.model_dump(
            mode="json", exclude={"artifact_id", "artifact_payload_sha256"}
        )
        digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        artifact_id = stable_contract_id("szoracqevaluation", payload)
        if self.artifact_payload_sha256 not in (None, digest):
            raise ContractValidationError("artifact payload SHA-256 mismatch")
        if self.artifact_id not in (None, artifact_id):
            raise ContractValidationError("artifact ID mismatch")
        object.__setattr__(self, "artifact_payload_sha256", digest)
        object.__setattr__(self, "artifact_id", artifact_id)
        return self


CaseContractV0 = Union[OpenRouterAdapterPositiveCaseV0, OpenRouterAdapterProbeV0]


def _candidate_fixture() -> tuple[
    OpenRouterCandidateEvidenceV0, dict[str, tuple[object, str]]
]:
    endpoint = OpenRouterEndpointPolicy()
    transport = OpenRouterTransportPolicy()
    route = OpenRouterRoutePolicy()
    control = OpenRouterControlPolicy()
    visible = ProviderVisibleRequestBytes(
        rendering_version="socrateszero-canonical-json-utf8/v0",
        canonical_request_json=FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0.decode(
            "utf-8"
        ),
    )
    seed = AcquisitionSeedSetting(status=AcquisitionSeedStatus.UNSUPPORTED)
    request_configuration = AcquisitionRequestConfiguration(
        temperature=0.0,
        seed=seed,
        max_output_tokens=OPENROUTER_MAX_OUTPUT_TOKENS,
        timeout_ms=5_000,
        provider_visible_metadata_digest=visible.sha256 or "",
    )
    binding = AcquisitionProviderModelBinding(
        provider_id=OPENROUTER_PROVIDER_ID,
        model_id=OPENROUTER_MODEL_ID,
        configuration_digest=request_configuration.configuration_digest or "",
    )
    action_id = (
        "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
    )
    semantic_request = AcquisitionSemanticRequest(
        source_capsule_id=(
            "cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50"
        ),
        source_execution_id=(
            "cedexecution_c90d438f2737bcbe3aff9a349412a18671ac88bbf1c4afc743f854b9b09312f6"
        ),
        root_state_v1_id=(
            "szstatev1_a17ce47c27894a3aac4095d0c08da107142a54d2b773c10104fde2b250c2f20e"
        ),
        pending_transition_id=(
            "cedpending_3111a26bb87ea7b0fe5a1658ffc86a6313fa66b4ac2f167095c0393bea85c31a"
        ),
        canonical_task_identity_id=(
            "cedtasksemantic_b5ace018c4bb1369d62bb5004a99edcd8945e4dd0eef1e206570c96b1d71017a"
        ),
        action_id=action_id,
        complete_legal_action_ids=(action_id,),
        requested_binding=binding,
        capability_snapshot_id="socrateszero-openrouter-candidate-capability-input/v0",
        control_policy_id=control.control_policy_id or "",
        request_configuration=request_configuration,
        provider_visible_request=visible,
    )
    body = render_openrouter_application_body(
        semantic_request,
        control,
        endpoint_policy=endpoint,
        route_policy=route,
    )
    token = OpenRouterTokenPolicy.from_prepared_body(body)
    pricing = OpenRouterPricingRecord()
    cost = OpenRouterCostBound(token_policy=token, pricing_record=pricing)
    capability = OpenRouterCapabilitySnapshot(
        prepared_body_id=body.prepared_body_id or "",
        endpoint_policy=endpoint,
        transport_policy=transport,
        route_policy=route,
        control_policy=control,
        token_policy=token,
        pricing_record=pricing,
        cost_bound=cost,
    )
    configuration_digest = (control.control_policy_id or "").split("_", 1)[-1]
    input_tokens = min(10, token.payload_input_token_upper_bound)
    raw_payload = {
        "id": "canned-adapter-response-1",
        "provider": OPENROUTER_PROVIDER_ID,
        "model": OPENROUTER_MODEL_ID,
        "configuration_digest": configuration_digest,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "What do you mean by knowledge?",
                },
            }
        ],
        "fallback_used": False,
        "explicit_retry_count": 0,
        "adapter_retry_count": 0,
        "sdk_internal_retry_count": None,
        "hidden_transport_retry_count": 0,
        "stream_used": False,
        "tool_calls": 0,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": 8,
            "total_tokens": input_tokens + 8,
        },
    }
    raw_bytes = canonical_json(raw_payload).encode("utf-8")
    raw_response = OpenRouterRawResponseEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response_base64=base64.b64encode(raw_bytes).decode("ascii"),
    )
    identity = OpenRouterIdentityEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        requested_configuration_digest=configuration_digest,
        actual_router_id=OPENROUTER_PROVIDER_ID,
        actual_model_id=OPENROUTER_MODEL_ID,
        actual_configuration_digest=configuration_digest,
        router_identity_match=True,
        model_identity_match=True,
        configuration_identity_match=True,
        identity_match=True,
        exact_router_model_configuration_verified=True,
        source_raw_response_sha256=raw_response.reported_sha256,
        source_fields=OPENROUTER_IDENTITY_SOURCE_FIELDS,
        fallback_used=False,
    )
    usage = OpenRouterUsageEvidence(
        evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
        token_completeness=OpenRouterUsageCompleteness.COMPLETE,
        token_policy=token,
        usage_source=OpenRouterUsageSource.PROVIDER_REPORTED,
        source_raw_response_sha256=raw_response.reported_sha256,
        raw_source_fields=OPENROUTER_PROVIDER_REPORTED_USAGE_SOURCE_FIELDS,
        input_tokens=input_tokens,
        output_tokens=8,
        total_tokens=input_tokens + 8,
    )
    envelope = OpenRouterCannedResponseEnvelope(
        transport_attempt_id="openrouter-evaluation-attempt-1",
        prepared_body_id=body.prepared_body_id or "",
        transport_status=OpenRouterTransportStatus.DELIVERED,
        raw_response=raw_response,
        identity_evidence=identity,
        usage_evidence=usage,
        timeout_fired=False,
        cancellation_requested=False,
    )
    directive = OpenRouterCannedTransportDirectiveV0(envelope=envelope)
    invocation_record = OpenRouterCannedInvocationRecordV0(
        ordinal=1,
        transport_attempt_id=envelope.transport_attempt_id,
        received_body_bytes=body.body_bytes,
        received_body_sha256=body.sha256 or "",
        received_body_byte_length=body.byte_length or 0,
        outcome=OpenRouterCannedInvocationOutcome.RETURNED,
        cancellation_acknowledged=False,
        worker_terminated=True,
    )
    attempt_receipt = OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED,
        semantic_request_id=semantic_request.semantic_request_id or "",
        capability_snapshot=capability,
        prepared_body=body,
        canned_response_envelope=envelope,
        raw_response=raw_response,
        identity_evidence=identity,
        usage_evidence=usage,
        canned_transport_invocations=1,
        application_fallback_used=False,
        explicit_retry_count=0,
        adapter_retry_count=0,
        hidden_transport_retry_count=0,
        stream_used=False,
        tool_calls=0,
    )
    reference_summary = OpenRouterReferenceCannedReceiptSummaryV0(
        attempt_receipt_id=attempt_receipt.attempt_receipt_id or "",
        response_validation_state=(
            attempt_receipt.response_validation_state.value
            if attempt_receipt.response_validation_state is not None
            else ""
        ),
        canned_response_envelope_id=envelope.canned_response_envelope_id or "",
        finish_reason=(
            envelope.finish_reason
            if envelope.finish_reason is not None
            else OpenRouterFinishReason.STOP
        ),
        raw_response_evidence_id=raw_response.raw_response_evidence_id or "",
        raw_response_sha256=raw_response.reported_sha256 or "",
        raw_response_byte_length=raw_response.reported_byte_length or 0,
        raw_response_maximum_byte_length=raw_response.maximum_byte_length,
        raw_response_truncated=raw_response.truncated,
        privacy_classification=raw_response.privacy_classification,
        retention_state=raw_response.retention_state,
        credential_material_retained=raw_response.credential_material_retained,
        sensitive_headers_retained=raw_response.sensitive_headers_retained,
        assistant_content_treatment=raw_response.assistant_content_treatment,
        identity_evidence_id=identity.identity_evidence_id or "",
        requested_router_id=identity.requested_router_id,
        requested_model_id=identity.requested_model_id,
        requested_configuration_digest=identity.requested_configuration_digest,
        actual_router_id=identity.actual_router_id,
        actual_model_id=identity.actual_model_id,
        actual_configuration_digest=identity.actual_configuration_digest,
        exact_router_model_configuration_verified=(
            identity.exact_router_model_configuration_verified
        ),
        identity_source_raw_response_sha256=(
            identity.source_raw_response_sha256 or ""
        ),
        fallback_used=identity.fallback_used,
        upstream_route_state=identity.upstream_route_state,
        provider_side_fallback_state=route.provider_side_fallback_state,
        usage_evidence_id=usage.usage_evidence_id or "",
        usage_evidence_state=usage.evidence_state,
        usage_completeness=usage.token_completeness,
        usage_source=usage.usage_source,
        usage_source_raw_response_sha256=(
            usage.source_raw_response_sha256 or ""
        ),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        usage_cost_state=usage.cost_state,
        usage_cost_bound_id=usage.cost_bound_id,
        usage_cost_microusd=usage.cost_microusd,
        pricing_record_id=pricing.pricing_record_id or "",
        pricing_state=pricing.pricing_state,
        pricing_authority_reference=pricing.authority_reference,
        pricing_source_name=pricing.source_name,
        pricing_source_version=pricing.source_version,
        pricing_effective_version=pricing.effective_version,
        pricing_provenance_sha256=pricing.provenance_sha256,
        pricing_input_microusd_per_million_tokens=(
            pricing.input_microusd_per_million_tokens
        ),
        pricing_output_microusd_per_million_tokens=(
            pricing.output_microusd_per_million_tokens
        ),
        pricing_fixed_non_token_microusd=pricing.fixed_non_token_microusd,
        pricing_unknown_line_items=pricing.unknown_line_items,
        cost_bound_id=cost.cost_bound_id or "",
        cost_state=cost.cost_state,
        maximum_input_cost_microusd=cost.maximum_input_cost_microusd,
        maximum_output_cost_microusd=cost.maximum_output_cost_microusd,
        maximum_fixed_cost_microusd=cost.maximum_fixed_cost_microusd,
        maximum_total_cost_microusd=cost.maximum_total_cost_microusd,
        cost_unknown_line_items=cost.unknown_line_items,
    )
    projection: dict[str, tuple[object, str]] = {
        "request.schema_version": (OPENROUTER_ADAPTER_REQUEST_SCHEMA_V0, "EVALUATOR_REQUEST"),
        "evaluator_draft.semantic_input.process_id": (
            None,
            "EVALUATOR_REQUEST",
        ),
        "prepared_body.renderer_version": (
            body.renderer_version,
            "RENDERER",
        ),
        "evaluator_draft.prepared_body.metadata.process_id": (
            None,
            "RENDERER",
        ),
        "evaluator_draft.prepared_body.metadata.branch_id": (
            None,
            "RENDERER",
        ),
        "prepared_body.canonical_body_json": (
            body.canonical_body_json,
            "RENDERER",
        ),
        "route_policy.upstream_route_state": (
            route.upstream_route_state.value,
            "CONTRACT",
        ),
        "route_policy.provider_side_fallback_state": (
            route.provider_side_fallback_state.value,
            "CONTRACT",
        ),
        "evaluator_derived.supported_upstream_fallback_disable_field_emitted": (
            False,
            "RENDERER",
        ),
        "route_policy.application_fallback_allowed": (
            route.application_fallback_allowed,
            "CONTRACT",
        ),
        "route_policy.adapter_fallback_allowed": (
            route.adapter_fallback_allowed,
            "CONTRACT",
        ),
        "prepared_body.stream": (False, "RENDERER"),
        "prepared_body.tools": ([], "RENDERER"),
        "prepared_body.temperature": (0.0, "RENDERER"),
        "prepared_body.seed": (None, "RENDERER"),
        "prepared_body.max_tokens": (
            OPENROUTER_MAX_OUTPUT_TOKENS,
            "RENDERER",
        ),
        "token_policy.provider_input_token_bound_state": (
            token.provider_input_token_bound_state.value,
            "CONTRACT",
        ),
        "token_policy.payload_input_bound_method": (
            token.payload_input_bound_method,
            "CONTRACT",
        ),
        "token_policy.provider_framing_overhead_tokens": (
            token.provider_framing_overhead_tokens,
            "CONTRACT",
        ),
        "token_policy.authoritative_provider_input_token_upper_bound": (
            token.authoritative_provider_input_token_upper_bound,
            "CONTRACT",
        ),
        "token_policy.authoritative_total_token_upper_bound": (
            token.authoritative_total_token_upper_bound,
            "CONTRACT",
        ),
        "cost_bound.pricing_record.pricing_record_id": (
            pricing.pricing_record_id,
            "CONTRACT",
        ),
        "pricing_record.model_id": (pricing.model_id, "CONTRACT"),
        "pricing_record.provider_id": (pricing.provider_id, "CONTRACT"),
        "pricing_record.input_microusd_per_million_tokens": (
            pricing.input_microusd_per_million_tokens,
            "CONTRACT",
        ),
        "pricing_record.output_microusd_per_million_tokens": (
            pricing.output_microusd_per_million_tokens,
            "CONTRACT",
        ),
        "pricing_record.fixed_non_token_microusd": (
            pricing.fixed_non_token_microusd,
            "CONTRACT",
        ),
        "pricing_record.authority_reference": (
            pricing.authority_reference,
            "CONTRACT",
        ),
        "pricing_record.source_name": (pricing.source_name, "CONTRACT"),
        "pricing_record.source_version": (
            pricing.source_version,
            "CONTRACT",
        ),
        "pricing_record.effective_version": (
            pricing.effective_version,
            "CONTRACT",
        ),
        "pricing_record.provenance_sha256": (
            pricing.provenance_sha256,
            "CONTRACT",
        ),
        "pricing_record.calculation_rule": (
            pricing.calculation_rule,
            "CONTRACT",
        ),
        "pricing_record.unknown_line_items": (
            list(pricing.unknown_line_items),
            "CONTRACT",
        ),
        "endpoint_policy.path": (endpoint.path, "CONTRACT"),
        "endpoint_policy.redirects_allowed": (
            endpoint.redirects_allowed,
            "CONTRACT",
        ),
        "endpoint_policy.environment_proxy_allowed": (
            endpoint.environment_proxy_allowed,
            "CONTRACT",
        ),
        "transport_policy.canned_cancellation_grace_ms": (
            transport.canned_cancellation_grace_ms,
            "CONTRACT",
        ),
        "evaluator_draft.semantic_headers.authorization_presence": (
            "ABSENT",
            "CONTRACT",
        ),
        "evaluator_derived.canned_transport_registered": (
            OpenRouterCannedTransportV0.implementation_id
            == OPENROUTER_CANNED_TRANSPORT_ID,
            "CANNED_CONTRACT",
        ),
        "evaluator_derived.transport_invocation_count": (
            1,
            "CANNED_CONTRACT",
        ),
        "envelope.transport_status": (
            envelope.transport_status.value,
            "CANNED_CONTRACT",
        ),
        "invocation_record.worker_terminated": (
            invocation_record.worker_terminated,
            "CANNED_CONTRACT",
        ),
        "directive.attempt_late_mutation": (
            directive.attempt_late_mutation,
            "CANNED_CONTRACT",
        ),
        "envelope.raw_response.raw_response_evidence_id": (
            raw_response.raw_response_evidence_id,
            "CANNED_CONTRACT",
        ),
        "raw_response.reported_sha256": (
            raw_response.reported_sha256,
            "CANNED_CONTRACT",
        ),
        "evaluator_derived.envelope_parse_state": (
            "COMPLETE_TYPED_ENVELOPE",
            "CANNED_CONTRACT",
        ),
        "identity_evidence.actual_router_id": (
            identity.actual_router_id,
            "CANNED_CONTRACT",
        ),
        "identity_evidence.actual_model_id": (
            identity.actual_model_id,
            "CANNED_CONTRACT",
        ),
        "identity_evidence.actual_configuration_digest": (
            identity.actual_configuration_digest,
            "CANNED_CONTRACT",
        ),
        "identity_evidence.fallback_used": (
            identity.fallback_used,
            "CANNED_CONTRACT",
        ),
        "identity_evidence.requested_router_id": (
            identity.requested_router_id,
            "CANNED_CONTRACT",
        ),
        "identity_evidence.requested_model_id": (
            identity.requested_model_id,
            "CANNED_CONTRACT",
        ),
        "identity_evidence.requested_configuration_digest": (
            identity.requested_configuration_digest,
            "CANNED_CONTRACT",
        ),
        "envelope.adapter_retry_count": (
            envelope.adapter_retry_count,
            "CANNED_CONTRACT",
        ),
        "envelope.stream_used": (envelope.stream_used, "CANNED_CONTRACT"),
        "envelope.tool_calls": (envelope.tool_calls, "CANNED_CONTRACT"),
        "usage_evidence.token_completeness": (
            usage.token_completeness.value,
            "CANNED_CONTRACT",
        ),
        "usage_evidence.input_tokens": (
            usage.input_tokens,
            "CANNED_CONTRACT",
        ),
        "usage_evidence.output_tokens": (
            usage.output_tokens,
            "CANNED_CONTRACT",
        ),
        "usage_evidence.total_tokens": (
            usage.total_tokens,
            "CANNED_CONTRACT",
        ),
        "attempt_receipt.usage_evidence.cost_bound_id": (
            attempt_receipt.usage_evidence.cost_bound_id
            if attempt_receipt.usage_evidence is not None
            else None,
            "CANNED_CONTRACT",
        ),
        "attempt_receipt.attempt_receipt_id": (
            attempt_receipt.attempt_receipt_id,
            "CANNED_CONTRACT",
        ),
        "attempt_receipt.payload": (
            attempt_receipt.model_dump(mode="json"),
            "CANNED_CONTRACT",
        ),
        "capability_snapshot.prepared_body_id": (
            capability.prepared_body_id,
            "CONTRACT",
        ),
        "capability_snapshot.endpoint_policy.endpoint_policy_id": (
            capability.endpoint_policy.endpoint_policy_id,
            "CONTRACT",
        ),
        "capability_snapshot.route_policy.route_policy_id": (
            capability.route_policy.route_policy_id,
            "CONTRACT",
        ),
        "capability_snapshot.control_policy.control_policy_id": (
            capability.control_policy.control_policy_id,
            "CONTRACT",
        ),
        "prepared_body.prepared_body_id": (
            body.prepared_body_id,
            "CONTRACT",
        ),
        "prepared_body.endpoint_policy_id": (
            body.endpoint_policy_id,
            "CONTRACT",
        ),
        "prepared_body.route_policy_id": (
            body.route_policy_id,
            "CONTRACT",
        ),
        "prepared_body.control_policy_id": (
            body.control_policy_id,
            "CONTRACT",
        ),
        "semantic_request.requested_binding.provider_id": (
            semantic_request.requested_binding.provider_id,
            "CONTRACT",
        ),
        "semantic_request.requested_binding.model_id": (
            semantic_request.requested_binding.model_id,
            "CONTRACT",
        ),
        "semantic_request.requested_binding.configuration_digest": (
            semantic_request.requested_binding.configuration_digest,
            "CONTRACT",
        ),
        "semantic_request.request_configuration.configuration_digest": (
            semantic_request.request_configuration.configuration_digest,
            "CONTRACT",
        ),
        "semantic_request.request_configuration.temperature": (
            semantic_request.request_configuration.temperature,
            "CONTRACT",
        ),
        "semantic_request.request_configuration.max_output_tokens": (
            semantic_request.request_configuration.max_output_tokens,
            "CONTRACT",
        ),
        "semantic_request.request_configuration.timeout_ms": (
            semantic_request.request_configuration.timeout_ms,
            "CONTRACT",
        ),
        "semantic_request.request_configuration.seed_status": (
            semantic_request.request_configuration.seed.status.value,
            "CONTRACT",
        ),
        "semantic_request.request_configuration.seed_value": (
            semantic_request.request_configuration.seed.value,
            "CONTRACT",
        ),
        "semantic_request.control_policy_id": (
            semantic_request.control_policy_id,
            "CONTRACT",
        ),
        "capability_snapshot.provider_id": (
            capability.provider_id,
            "CONTRACT",
        ),
        "capability_snapshot.model_id": (
            capability.model_id,
            "CONTRACT",
        ),
        "_derived.control_policy_configuration_digest": (
            configuration_digest,
            "CONTRACT",
        ),
        "control_policy.explicit_retry_limit": (
            control.explicit_retry_limit,
            "CONTRACT",
        ),
        "control_policy.adapter_retry_limit": (
            control.adapter_retry_limit,
            "CONTRACT",
        ),
        "control_policy.hidden_transport_retry_limit": (
            control.hidden_transport_retry_limit,
            "CONTRACT",
        ),
        "control_policy.sdk_internal_retry_state": (
            control.sdk_internal_retry_state.value,
            "CONTRACT",
        ),
        "transport_policy.max_canned_transport_invocations": (
            transport.max_canned_transport_invocations,
            "CONTRACT",
        ),
        "control_policy.seed_state": (
            control.seed_state.value,
            "CONTRACT",
        ),
        "control_policy.seed": (control.seed, "CONTRACT"),
        "control_policy.temperature": (control.temperature, "CONTRACT"),
        "control_policy.max_output_tokens": (
            control.max_output_tokens,
            "CONTRACT",
        ),
        "pricing_record.pricing_state": (
            pricing.pricing_state.value,
            "CONTRACT",
        ),
        "cost_bound.cost_state": (cost.cost_state.value, "CONTRACT"),
        "cost_bound.token_policy.token_policy_id": (
            cost.token_policy.token_policy_id,
            "CONTRACT",
        ),
        "cost_bound.maximum_input_cost_microusd": (
            cost.maximum_input_cost_microusd,
            "CONTRACT",
        ),
        "cost_bound.maximum_output_cost_microusd": (
            cost.maximum_output_cost_microusd,
            "CONTRACT",
        ),
        "cost_bound.maximum_fixed_cost_microusd": (
            cost.maximum_fixed_cost_microusd,
            "CONTRACT",
        ),
        "cost_bound.maximum_total_cost_microusd": (
            cost.maximum_total_cost_microusd,
            "CONTRACT",
        ),
        "cost_bound.unknown_line_items": (
            list(cost.unknown_line_items),
            "CONTRACT",
        ),
        "_prepared_body.frozen_json": (body.canonical_body_json, "RENDERER"),
        "_endpoint.expected_path": (OPENROUTER_ENDPOINT_PATH, "CONTRACT"),
        "transport_policy.total_timeout_ms": (
            transport.total_timeout_ms,
            "CONTRACT",
        ),
        "raw_response.raw_response_base64": (
            raw_response.raw_response_base64,
            "CANNED_CONTRACT",
        ),
        "raw_response.reported_byte_length": (
            raw_response.reported_byte_length,
            "CANNED_CONTRACT",
        ),
        "token_policy.max_output_tokens": (
            token.max_output_tokens,
            "CANNED_CONTRACT",
        ),
        "token_policy.payload_input_token_upper_bound": (
            token.payload_input_token_upper_bound,
            "CANNED_CONTRACT",
        ),
        "token_policy.token_policy_id": (
            token.token_policy_id,
            "CANNED_CONTRACT",
        ),
        "pricing_record.pricing_record_id": (
            pricing.pricing_record_id,
            "CANNED_CONTRACT",
        ),
        "capability_snapshot.cost_bound.cost_bound_id": (
            capability.cost_bound.cost_bound_id,
            "CANNED_CONTRACT",
        ),
        "raw_response.credential_material_retained": (
            raw_response.credential_material_retained,
            "CANNED_CONTRACT",
        ),
        "raw_response.sensitive_headers_retained": (
            raw_response.sensitive_headers_retained,
            "CANNED_CONTRACT",
        ),
        "raw_response.privacy_classification": (
            raw_response.privacy_classification.value,
            "CANNED_CONTRACT",
        ),
        "raw_response.retention_state": (
            raw_response.retention_state.value
            if raw_response.retention_state is not None
            else None,
            "CANNED_CONTRACT",
        ),
        "raw_response.assistant_content_treatment": (
            raw_response.assistant_content_treatment,
            "CANNED_CONTRACT",
        ),
    }
    registered_paths = {
        item.path: item
        for item in FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
    }
    missing_paths = tuple(sorted(set(registered_paths) - set(projection)))
    if missing_paths:
        raise ContractValidationError(
            f"candidate projection misses frozen mutation paths: {missing_paths!r}"
        )
    baseline_drifts = tuple(
        path
        for path, spec in registered_paths.items()
        if canonical_json(projection[path][0]) != spec.baseline_json
    )
    if baseline_drifts:
        raise ContractValidationError(
            f"candidate projection differs from frozen baselines: {baseline_drifts!r}"
        )
    baseline_projection_payload = {
        path: {"value": value, "source": source}
        for path, (value, source) in projection.items()
    }
    baseline_projection_sha256 = hashlib.sha256(
        canonical_json(baseline_projection_payload).encode("utf-8")
    ).hexdigest()
    manifest_payload = {
        "schema_version": OPENROUTER_FIXTURE_MANIFEST_SCHEMA_V0,
        "candidate_adapter_id": OPENROUTER_ACQUISITION_ADAPTER_ID,
        "case_design_adapter_id": OPENROUTER_ADAPTER_ID_V0,
        "semantic_request_id": semantic_request.semantic_request_id or "",
        "source_provider_visible_request_id": (
            visible.provider_visible_request_id or ""
        ),
        "source_provider_visible_sha256": visible.sha256 or "",
        "capability_snapshot_id": capability.capability_snapshot_id or "",
        "endpoint_policy_id": endpoint.endpoint_policy_id or "",
        "route_policy_id": route.route_policy_id or "",
        "control_policy_id": control.control_policy_id or "",
        "renderer_version": OPENROUTER_ACQUISITION_RENDERER_VERSION,
        "prepared_body_id": body.prepared_body_id or "",
        "prepared_body_sha256": body.sha256 or "",
        "transport_policy_id": transport.transport_policy_id or "",
        "token_policy_id": token.token_policy_id or "",
        "pricing_record_id": pricing.pricing_record_id or "",
        "cost_bound_id": cost.cost_bound_id or "",
        "raw_response_evidence_id": raw_response.raw_response_evidence_id or "",
        "identity_evidence_id": identity.identity_evidence_id or "",
        "usage_evidence_id": usage.usage_evidence_id or "",
        "canned_response_envelope_id": (
            envelope.canned_response_envelope_id or ""
        ),
        "attempt_receipt_id": attempt_receipt.attempt_receipt_id or "",
        "reference_receipt_summary_id": reference_summary.summary_id or "",
        "baseline_projection_sha256": baseline_projection_sha256,
        "reference_canned_fixture_only": True,
        "actual_canned_transport_invocations": 0,
        "actual_attempt_receipt_id": None,
        "actual_response_receipt": None,
    }
    evidence = OpenRouterCandidateEvidenceV0(
        semantic_request_id=semantic_request.semantic_request_id or "",
        source_provider_visible_request_id=(
            visible.provider_visible_request_id or ""
        ),
        source_provider_visible_sha256=visible.sha256 or "",
        source_provider_visible_byte_length=visible.byte_length or 0,
        endpoint_policy_id=endpoint.endpoint_policy_id or "",
        transport_policy_id=transport.transport_policy_id or "",
        route_policy_id=route.route_policy_id or "",
        control_policy_id=control.control_policy_id or "",
        capability_snapshot_id=capability.capability_snapshot_id or "",
        prepared_body_id=body.prepared_body_id or "",
        canonical_body_json=body.canonical_body_json,
        prepared_body_sha256=body.sha256 or "",
        prepared_body_byte_length=body.byte_length or 0,
        token_policy_id=token.token_policy_id or "",
        payload_input_token_upper_bound=token.payload_input_token_upper_bound,
        payload_only_total_token_upper_bound=(
            token.payload_only_total_token_upper_bound or 0
        ),
        pricing_record_id=pricing.pricing_record_id or "",
        cost_bound_id=cost.cost_bound_id or "",
        raw_response_evidence_id=raw_response.raw_response_evidence_id or "",
        identity_evidence_id=identity.identity_evidence_id or "",
        usage_evidence_id=usage.usage_evidence_id or "",
        canned_response_envelope_id=envelope.canned_response_envelope_id or "",
        attempt_receipt_id=attempt_receipt.attempt_receipt_id or "",
        reference_receipt_summary=reference_summary,
        reference_receipt_summary_id=reference_summary.summary_id or "",
        baseline_projection_sha256=baseline_projection_sha256,
        fixture_manifest_id=stable_contract_id("szorfixture", manifest_payload),
    )
    return evidence, projection


def build_openrouter_candidate_evidence_v0() -> OpenRouterCandidateEvidenceV0:
    """Render and expose the exact frozen prompt candidate without dispatch."""

    evidence, _ = _candidate_fixture()
    return evidence


_PATH_RULES: dict[
    str,
    tuple[OpenRouterAdapterGuardId, OpenRouterAdapterFailureCode, str],
] = {
    "request.schema_version": (OpenRouterAdapterGuardId.P01_REQUEST_INTEGRITY, OpenRouterAdapterFailureCode.INVALID_ADAPTER_REQUEST, "request_integrity"),
    "evaluator_draft.semantic_input.process_id": (OpenRouterAdapterGuardId.P02_SEMANTIC_INPUT_INTEGRITY, OpenRouterAdapterFailureCode.INVALID_SEMANTIC_INPUT, "semantic_input"),
    "prepared_body.renderer_version": (OpenRouterAdapterGuardId.P04_RENDERER_VERSION, OpenRouterAdapterFailureCode.RENDERER_VERSION_MISMATCH, "renderer_version"),
    "prepared_body.canonical_body_json": (OpenRouterAdapterGuardId.P05_CANONICAL_BODY_INTEGRITY, OpenRouterAdapterFailureCode.BODY_DIGEST_OR_LENGTH_MISMATCH, "canonical_body"),
    "evaluator_draft.prepared_body.metadata.process_id": (OpenRouterAdapterGuardId.P06_ENTROPY_CREDENTIAL_FIREWALL, OpenRouterAdapterFailureCode.FORBIDDEN_ENTROPY, "entropy_credential_firewall"),
    "evaluator_draft.prepared_body.metadata.branch_id": (OpenRouterAdapterGuardId.P06_ENTROPY_CREDENTIAL_FIREWALL, OpenRouterAdapterFailureCode.FORBIDDEN_ENTROPY, "entropy_credential_firewall"),
    "evaluator_draft.semantic_headers.authorization_presence": (OpenRouterAdapterGuardId.P06_ENTROPY_CREDENTIAL_FIREWALL, OpenRouterAdapterFailureCode.CREDENTIAL_OR_HEADER_LEAKAGE, "entropy_credential_firewall"),
    "route_policy.upstream_route_state": (_P08, OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN, "route_policy"),
    "route_policy.application_fallback_allowed": (OpenRouterAdapterGuardId.P09_FALLBACK_INTENT, OpenRouterAdapterFailureCode.FALLBACK_INTENT_NOT_DISABLED, "fallback_intent"),
    "route_policy.adapter_fallback_allowed": (OpenRouterAdapterGuardId.P09_FALLBACK_INTENT, OpenRouterAdapterFailureCode.FALLBACK_INTENT_NOT_DISABLED, "fallback_intent"),
    "prepared_body.stream": (OpenRouterAdapterGuardId.P12_STREAM_POLICY, OpenRouterAdapterFailureCode.STREAM_NOT_DISABLED, "stream_policy"),
    "prepared_body.tools": (OpenRouterAdapterGuardId.P13_TOOL_POLICY, OpenRouterAdapterFailureCode.TOOLS_NOT_DISABLED, "tool_policy"),
    "prepared_body.temperature": (OpenRouterAdapterGuardId.P14_TEMPERATURE, OpenRouterAdapterFailureCode.TEMPERATURE_NOT_ZERO, "temperature"),
    "prepared_body.seed": (OpenRouterAdapterGuardId.P15_SEED, OpenRouterAdapterFailureCode.SEED_NOT_UNSUPPORTED_OR_EMITTED, "seed"),
    "prepared_body.max_tokens": (OpenRouterAdapterGuardId.P16_OUTPUT_TOKEN_CAP, OpenRouterAdapterFailureCode.OUTPUT_TOKEN_CAP_INVALID, "output_token_cap"),
    "token_policy.provider_input_token_bound_state": (_P17, OpenRouterAdapterFailureCode.INPUT_BOUND_UNPROVEN, "input_token_bound"),
    "cost_bound.pricing_record.pricing_record_id": (_P18, OpenRouterAdapterFailureCode.PRICING_NOT_ESTABLISHED, "pricing_record"),
    "pricing_record.model_id": (_P18, OpenRouterAdapterFailureCode.PRICING_BINDING_MISMATCH, "pricing_record"),
    "pricing_record.output_microusd_per_million_tokens": (OpenRouterAdapterGuardId.P19_COST_BOUND, OpenRouterAdapterFailureCode.COST_OVERFLOW, "cost_bound"),
    "endpoint_policy.path": (OpenRouterAdapterGuardId.P20_ENDPOINT_POLICY, OpenRouterAdapterFailureCode.ENDPOINT_MISMATCH, "endpoint_policy"),
    "endpoint_policy.redirects_allowed": (OpenRouterAdapterGuardId.P21_REDIRECT_POLICY, OpenRouterAdapterFailureCode.REDIRECTS_NOT_DISABLED, "redirect_policy"),
    "endpoint_policy.environment_proxy_allowed": (OpenRouterAdapterGuardId.P22_PROXY_POLICY, OpenRouterAdapterFailureCode.PROXY_INHERITANCE_NOT_DISABLED, "proxy_policy"),
    "transport_policy.canned_cancellation_grace_ms": (OpenRouterAdapterGuardId.P23_TIMEOUT_POLICY, OpenRouterAdapterFailureCode.TIMEOUT_POLICY_INCOMPLETE, "timeout_policy"),
    "evaluator_derived.canned_transport_registered": (OpenRouterAdapterGuardId.P24_CANNED_REGISTRATION, OpenRouterAdapterFailureCode.CANNED_TRANSPORT_UNREGISTERED, "canned_registration"),
    "evaluator_derived.transport_invocation_count": (OpenRouterAdapterGuardId.A01_INVOCATION_COUNT, OpenRouterAdapterFailureCode.MULTIPLE_TRANSPORT_INVOCATIONS, "invocation_count"),
    "envelope.transport_status": (OpenRouterAdapterGuardId.A02_TRANSPORT_COMPLETION, OpenRouterAdapterFailureCode.TRANSPORT_TIMEOUT, "transport_completion"),
    "invocation_record.worker_terminated": (OpenRouterAdapterGuardId.A03_WORKER_TERMINATION, OpenRouterAdapterFailureCode.WORKER_NOT_TERMINATED, "worker_termination"),
    "directive.attempt_late_mutation": (OpenRouterAdapterGuardId.A04_LATE_MUTATION, OpenRouterAdapterFailureCode.LATE_MUTATION_DETECTED, "late_mutation"),
    "envelope.raw_response.raw_response_evidence_id": (OpenRouterAdapterGuardId.A05_RAW_RESPONSE_PRESENCE, OpenRouterAdapterFailureCode.MISSING_RAW_RESPONSE, "raw_response_presence"),
    "raw_response.reported_sha256": (OpenRouterAdapterGuardId.A06_RAW_RESPONSE_INTEGRITY, OpenRouterAdapterFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH, "raw_response_integrity"),
    "evaluator_derived.envelope_parse_state": (OpenRouterAdapterGuardId.A07_ENVELOPE_PARSE, OpenRouterAdapterFailureCode.MALFORMED_RESPONSE_ENVELOPE, "envelope_parse"),
    "identity_evidence.actual_router_id": (OpenRouterAdapterGuardId.A08_ACTUAL_PROVIDER, OpenRouterAdapterFailureCode.ACTUAL_PROVIDER_MISMATCH, "actual_provider"),
    "identity_evidence.actual_model_id": (OpenRouterAdapterGuardId.A09_ACTUAL_MODEL, OpenRouterAdapterFailureCode.ACTUAL_MODEL_MISMATCH, "actual_model"),
    "identity_evidence.actual_configuration_digest": (OpenRouterAdapterGuardId.A10_ACTUAL_CONFIGURATION, OpenRouterAdapterFailureCode.ACTUAL_CONFIGURATION_MISMATCH, "actual_configuration"),
    "identity_evidence.fallback_used": (OpenRouterAdapterGuardId.A11_FALLBACK_STATUS, OpenRouterAdapterFailureCode.FALLBACK_ACTIVATED, "fallback_status"),
    "envelope.adapter_retry_count": (OpenRouterAdapterGuardId.A12_RETRY_STATUS, OpenRouterAdapterFailureCode.RETRY_ACTIVATED, "retry_status"),
    "envelope.stream_used": (OpenRouterAdapterGuardId.A13_STREAM_STATUS, OpenRouterAdapterFailureCode.STREAMING_RESPONSE_DETECTED, "stream_status"),
    "envelope.tool_calls": (OpenRouterAdapterGuardId.A14_TOOL_STATUS, OpenRouterAdapterFailureCode.TOOL_ACTIVATED, "tool_status"),
    "usage_evidence.token_completeness": (OpenRouterAdapterGuardId.A15_USAGE_COMPLETENESS, OpenRouterAdapterFailureCode.USAGE_INCOMPLETE, "usage_completeness"),
    "usage_evidence.input_tokens": (OpenRouterAdapterGuardId.A15_USAGE_COMPLETENESS, OpenRouterAdapterFailureCode.FALSE_ZERO_USAGE, "usage_completeness"),
    "usage_evidence.total_tokens": (OpenRouterAdapterGuardId.A16_USAGE_CONSISTENCY, OpenRouterAdapterFailureCode.USAGE_INCONSISTENT, "usage_consistency"),
    "usage_evidence.output_tokens": (OpenRouterAdapterGuardId.A17_TOKEN_BOUNDS, OpenRouterAdapterFailureCode.REPORTED_USAGE_EXCEEDS_BOUND, "token_bounds"),
    "attempt_receipt.usage_evidence.cost_bound_id": (OpenRouterAdapterGuardId.A18_COST_LINKAGE, OpenRouterAdapterFailureCode.COST_LINK_MISMATCH, "cost_linkage"),
    "attempt_receipt.attempt_receipt_id": (OpenRouterAdapterGuardId.A20_FINAL_RECEIPT_INTEGRITY, OpenRouterAdapterFailureCode.RECEIPT_MISMATCH, "receipt_identity"),
}

_PATH_DEPENDENT_VECTOR_FIELDS: dict[str, tuple[str, ...]] = {
    "evaluator_draft.prepared_body.metadata.process_id": ("canonical_body",),
    "evaluator_draft.prepared_body.metadata.branch_id": ("canonical_body",),
    "prepared_body.stream": ("canonical_body",),
    "prepared_body.tools": ("canonical_body",),
    "prepared_body.temperature": ("canonical_body",),
    "prepared_body.seed": ("canonical_body",),
    "prepared_body.max_tokens": ("canonical_body", "cost_bound"),
    "token_policy.provider_input_token_bound_state": ("cost_bound",),
    "cost_bound.pricing_record.pricing_record_id": ("cost_bound",),
    "pricing_record.model_id": ("cost_bound",),
    "envelope.transport_status": (
        "raw_response_presence",
        "raw_response_integrity",
    ),
    "envelope.raw_response.raw_response_evidence_id": (
        "raw_response_integrity",
        "envelope_parse",
    ),
    "usage_evidence.token_completeness": (
        "usage_consistency",
        "token_bounds",
        "cost_linkage",
    ),
    "usage_evidence.total_tokens": ("cost_linkage",),
    "usage_evidence.input_tokens": (
        "usage_consistency",
        "cost_linkage",
    ),
    "usage_evidence.output_tokens": ("usage_consistency", "cost_linkage"),
    "attempt_receipt.usage_evidence.cost_bound_id": ("receipt_identity",),
}

_REGISTERED_MUTATION_PATHS = {
    item.path: item
    for item in FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
}
if set(_PATH_RULES) != set(_REGISTERED_MUTATION_PATHS):
    raise ContractValidationError(
        "evaluator path rules differ from frozen mutation-path registry"
    )
if any(
    _PATH_RULES[path][0] is not spec.guard_id
    or _PATH_RULES[path][2] != spec.mutation_vector_field
    for path, spec in _REGISTERED_MUTATION_PATHS.items()
):
    raise ContractValidationError(
        "evaluator guard/vector mapping differs from frozen path registry"
    )


def _projected_cost_line_microusd(
    tokens: object,
    rate_per_million: object,
) -> tuple[Optional[int], bool]:
    """Return (value, overflow) for exact nonnegative signed-64 inputs."""

    if type(tokens) is not int or type(rate_per_million) is not int:
        return None, False
    if tokens < 0 or rate_per_million < 0:
        return None, False
    if tokens > MAX_SIGNED_64 or rate_per_million > MAX_SIGNED_64:
        return None, True
    if tokens and rate_per_million > MAX_SIGNED_64 // tokens:
        return None, True
    product = tokens * rate_per_million
    if product > MAX_SIGNED_64 - 999_999:
        return None, True
    return (product + 999_999) // 1_000_000, False


def _guard_predicate_failure(
    guard: OpenRouterAdapterGuardId,
    projection: dict[str, object],
) -> Optional[OpenRouterAdapterFailureCode]:
    """Run one actual guard predicate over an independently mutated projection."""

    g = OpenRouterAdapterGuardId
    f = OpenRouterAdapterFailureCode
    if guard is g.P01_REQUEST_INTEGRITY:
        return None if projection["request.schema_version"] == OPENROUTER_ADAPTER_REQUEST_SCHEMA_V0 else f.INVALID_ADAPTER_REQUEST
    if guard is g.P02_SEMANTIC_INPUT_INTEGRITY:
        return None if projection["evaluator_draft.semantic_input.process_id"] is None else f.INVALID_SEMANTIC_INPUT
    if guard is g.P03_CONTROL_SNAPSHOT_INTEGRITY:
        body_id = projection["prepared_body.prepared_body_id"]
        links = (
            projection["capability_snapshot.prepared_body_id"] == body_id,
            projection["capability_snapshot.endpoint_policy.endpoint_policy_id"]
            == projection["prepared_body.endpoint_policy_id"],
            projection["capability_snapshot.route_policy.route_policy_id"]
            == projection["prepared_body.route_policy_id"],
            projection["capability_snapshot.control_policy.control_policy_id"]
            == projection["prepared_body.control_policy_id"],
        )
        return None if all(links) else f.INVALID_CONTROL_SNAPSHOT
    if guard is g.P04_RENDERER_VERSION:
        return None if projection["prepared_body.renderer_version"] == OPENROUTER_ACQUISITION_RENDERER_VERSION else f.RENDERER_VERSION_MISMATCH
    if guard is g.P05_CANONICAL_BODY_INTEGRITY:
        candidate = projection["prepared_body.canonical_body_json"]
        if type(candidate) is not str:
            return f.BODY_DIGEST_OR_LENGTH_MISMATCH
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return f.BODY_DIGEST_OR_LENGTH_MISMATCH
        if canonical_json(parsed) != candidate:
            return f.NONCANONICAL_BODY
        return None if candidate == projection["_prepared_body.frozen_json"] else f.BODY_DIGEST_OR_LENGTH_MISMATCH
    if guard is g.P06_ENTROPY_CREDENTIAL_FIREWALL:
        if projection[
            "evaluator_draft.semantic_headers.authorization_presence"
        ] != "ABSENT":
            return f.CREDENTIAL_OR_HEADER_LEAKAGE
        if any(
            projection[path] is not None
            for path in (
                "evaluator_draft.prepared_body.metadata.process_id",
                "evaluator_draft.prepared_body.metadata.branch_id",
            )
        ):
            return f.FORBIDDEN_ENTROPY
        return None
    if guard is g.P07_REQUESTED_IDENTITY:
        requested = (
            projection["identity_evidence.requested_router_id"],
            projection["identity_evidence.requested_model_id"],
            projection["identity_evidence.requested_configuration_digest"],
        )
        expected = (
            projection["capability_snapshot.provider_id"],
            projection["capability_snapshot.model_id"],
            projection["_derived.control_policy_configuration_digest"],
        )
        control_policy_id = projection["semantic_request.control_policy_id"]
        control_bridge = (
            type(control_policy_id) is str
            and control_policy_id
            == projection[
                "capability_snapshot.control_policy.control_policy_id"
            ]
            == projection["prepared_body.control_policy_id"]
            and control_policy_id.split("_", 1)[-1]
            == projection["_derived.control_policy_configuration_digest"]
        )
        semantic_binding_consistent = (
            projection["semantic_request.requested_binding.provider_id"]
            == projection["capability_snapshot.provider_id"]
            and projection["semantic_request.requested_binding.model_id"]
            == projection["capability_snapshot.model_id"]
            and projection[
                "semantic_request.requested_binding.configuration_digest"
            ]
            == projection[
                "semantic_request.request_configuration.configuration_digest"
            ]
        )
        semantic_control_values_match = (
            projection["semantic_request.request_configuration.temperature"]
            == projection["control_policy.temperature"]
            and projection[
                "semantic_request.request_configuration.max_output_tokens"
            ]
            == projection["control_policy.max_output_tokens"]
            and projection["semantic_request.request_configuration.timeout_ms"]
            == projection["transport_policy.total_timeout_ms"]
            and projection["semantic_request.request_configuration.seed_status"]
            == "UNSUPPORTED"
            and projection["semantic_request.request_configuration.seed_value"] is None
            and projection["control_policy.seed_state"] == "PROVEN_UNSUPPORTED"
            and projection["control_policy.seed"] is None
        )
        return (
            None
            if (
                requested == expected
                and control_bridge
                and semantic_binding_consistent
                and semantic_control_values_match
            )
            else f.REQUESTED_IDENTITY_MISMATCH
        )
    if guard is g.P08_ROUTE_POLICY:
        return None if projection["route_policy.upstream_route_state"] == "PROVEN" else f.ROUTE_POLICY_UNPROVEN
    if guard is g.P09_FALLBACK_INTENT:
        disabled = (
            projection["route_policy.application_fallback_allowed"] is False
            and projection["route_policy.adapter_fallback_allowed"] is False
            and projection["route_policy.provider_side_fallback_state"] == "PROVEN"
            and projection[
                "evaluator_derived.supported_upstream_fallback_disable_field_emitted"
            ]
            is True
        )
        return None if disabled else f.FALLBACK_INTENT_NOT_DISABLED
    if guard is g.P10_RETRY_POLICY:
        retry_state = (
            projection["control_policy.explicit_retry_limit"],
            projection["control_policy.adapter_retry_limit"],
            projection["control_policy.hidden_transport_retry_limit"],
            projection["control_policy.sdk_internal_retry_state"],
        )
        return None if retry_state == (0, 0, 0, "NOT_APPLICABLE") else f.RETRY_POLICY_UNPROVEN
    if guard is g.P11_ONE_SHOT_POLICY:
        return None if projection["transport_policy.max_canned_transport_invocations"] == 1 else f.ATTEMPT_LIMIT_NOT_ONE
    if guard is g.P12_STREAM_POLICY:
        return None if projection["prepared_body.stream"] is False else f.STREAM_NOT_DISABLED
    if guard is g.P13_TOOL_POLICY:
        return None if projection["prepared_body.tools"] == [] else f.TOOLS_NOT_DISABLED
    if guard is g.P14_TEMPERATURE:
        value = projection["prepared_body.temperature"]
        return None if type(value) in (int, float) and value == 0 else f.TEMPERATURE_NOT_ZERO
    if guard is g.P15_SEED:
        seed_ok = projection["control_policy.seed_state"] == "PROVEN_UNSUPPORTED" and projection["prepared_body.seed"] is None
        return None if seed_ok else f.SEED_NOT_UNSUPPORTED_OR_EMITTED
    if guard is g.P16_OUTPUT_TOKEN_CAP:
        value = projection["prepared_body.max_tokens"]
        return None if type(value) is int and value == OPENROUTER_MAX_OUTPUT_TOKENS else f.OUTPUT_TOKEN_CAP_INVALID
    if guard is g.P17_INPUT_TOKEN_BOUND:
        payload = projection["token_policy.payload_input_token_upper_bound"]
        overhead = projection["token_policy.provider_framing_overhead_tokens"]
        provider_bound = projection[
            "token_policy.authoritative_provider_input_token_upper_bound"
        ]
        total_bound = projection[
            "token_policy.authoritative_total_token_upper_bound"
        ]
        complete = (
            projection["token_policy.provider_input_token_bound_state"]
            == "CONSERVATIVE_UPPER_BOUND"
            and type(payload) is int
            and type(overhead) is int
            and type(provider_bound) is int
            and type(total_bound) is int
            and 0 <= payload <= MAX_SIGNED_64
            and 0 <= overhead <= MAX_SIGNED_64
            and payload <= provider_bound <= MAX_SIGNED_64
            and provider_bound == payload + overhead
            and total_bound
            == provider_bound + projection["token_policy.max_output_tokens"]
            and total_bound <= MAX_SIGNED_64
        )
        return None if complete else f.INPUT_BOUND_UNPROVEN
    if guard is g.P18_PRICING_RECORD:
        pricing_id = projection["pricing_record.pricing_record_id"]
        linked_id = projection["cost_bound.pricing_record.pricing_record_id"]
        rates = (
            projection["pricing_record.input_microusd_per_million_tokens"],
            projection["pricing_record.output_microusd_per_million_tokens"],
            projection["pricing_record.fixed_non_token_microusd"],
        )
        provenance = hashlib.sha256(
            b"socrateszero-openrouter-synthetic-pricing/v0"
        ).hexdigest()
        complete = (
            projection["pricing_record.pricing_state"] == "SYNTHETIC_ONLY"
            and type(pricing_id) is str
            and bool(pricing_id)
            and type(linked_id) is str
            and bool(linked_id)
            and all(type(rate) is int and rate >= 0 for rate in rates)
            and projection["pricing_record.authority_reference"]
            == "synthetic-test-only"
            and projection["pricing_record.source_name"]
            == "synthetic-test-only"
            and projection["pricing_record.source_version"]
            == "synthetic-pricing/v0"
            and projection["pricing_record.effective_version"]
            == "synthetic-effective/v0"
            and projection["pricing_record.provenance_sha256"] == provenance
            and projection["pricing_record.calculation_rule"]
            == OPENROUTER_COST_CALCULATION_RULE
            and projection["pricing_record.unknown_line_items"] == []
        )
        if not complete:
            return f.PRICING_NOT_ESTABLISHED
        binding = (
            linked_id == pricing_id
            and projection["pricing_record.provider_id"]
            == OPENROUTER_PROVIDER_ID
            and projection["pricing_record.model_id"] == OPENROUTER_MODEL_ID
        )
        return None if binding else f.PRICING_BINDING_MISMATCH
    if guard is g.P19_COST_BOUND:
        input_cost, input_overflow = _projected_cost_line_microusd(
            projection[
                "token_policy.authoritative_provider_input_token_upper_bound"
            ],
            projection["pricing_record.input_microusd_per_million_tokens"],
        )
        output_cost, output_overflow = _projected_cost_line_microusd(
            projection["token_policy.max_output_tokens"],
            projection["pricing_record.output_microusd_per_million_tokens"],
        )
        fixed = projection["pricing_record.fixed_non_token_microusd"]
        if input_overflow or output_overflow or (
            type(fixed) is int and fixed > MAX_SIGNED_64
        ):
            return f.COST_OVERFLOW
        if (
            input_cost is None
            or output_cost is None
            or type(fixed) is not int
            or fixed < 0
        ):
            return f.COST_BOUND_INVALID
        subtotal = input_cost + output_cost
        if subtotal > MAX_SIGNED_64 or fixed > MAX_SIGNED_64 - subtotal:
            return f.COST_OVERFLOW
        expected = (input_cost, output_cost, fixed, subtotal + fixed)
        actual = (
            projection["cost_bound.maximum_input_cost_microusd"],
            projection["cost_bound.maximum_output_cost_microusd"],
            projection["cost_bound.maximum_fixed_cost_microusd"],
            projection["cost_bound.maximum_total_cost_microusd"],
        )
        complete = (
            projection["cost_bound.cost_state"] == "SYNTHETIC_ONLY"
            and projection["cost_bound.token_policy.token_policy_id"]
            == projection["token_policy.token_policy_id"]
            and projection["cost_bound.pricing_record.pricing_record_id"]
            == projection["pricing_record.pricing_record_id"]
            and projection["cost_bound.unknown_line_items"] == []
            and actual == expected
        )
        return None if complete else f.COST_BOUND_INVALID
    if guard is g.P20_ENDPOINT_POLICY:
        return None if projection["endpoint_policy.path"] == projection["_endpoint.expected_path"] else f.ENDPOINT_MISMATCH
    if guard is g.P21_REDIRECT_POLICY:
        return None if projection["endpoint_policy.redirects_allowed"] is False else f.REDIRECTS_NOT_DISABLED
    if guard is g.P22_PROXY_POLICY:
        return None if projection["endpoint_policy.environment_proxy_allowed"] is False else f.PROXY_INHERITANCE_NOT_DISABLED
    if guard is g.P23_TIMEOUT_POLICY:
        grace = projection["transport_policy.canned_cancellation_grace_ms"]
        timeout = projection["transport_policy.total_timeout_ms"]
        complete = type(grace) is int and grace > 0 and type(timeout) is int and timeout > 0
        return None if complete else f.TIMEOUT_POLICY_INCOMPLETE
    if guard is g.P24_CANNED_REGISTRATION:
        return None if projection["evaluator_derived.canned_transport_registered"] is True else f.CANNED_TRANSPORT_UNREGISTERED
    if guard is g.A01_INVOCATION_COUNT:
        return None if projection["evaluator_derived.transport_invocation_count"] == 1 else f.MULTIPLE_TRANSPORT_INVOCATIONS
    if guard is g.A02_TRANSPORT_COMPLETION:
        status = projection["envelope.transport_status"]
        if status == "DELIVERED":
            return None
        return f.TRANSPORT_TIMEOUT if status == "TIMEOUT" else f.TRANSPORT_ERROR
    if guard is g.A03_WORKER_TERMINATION:
        return None if projection["invocation_record.worker_terminated"] is True else f.WORKER_NOT_TERMINATED
    if guard is g.A04_LATE_MUTATION:
        return None if projection["directive.attempt_late_mutation"] is False else f.LATE_MUTATION_DETECTED
    if guard is g.A05_RAW_RESPONSE_PRESENCE:
        return None if projection["envelope.raw_response.raw_response_evidence_id"] is not None else f.MISSING_RAW_RESPONSE
    if guard is g.A06_RAW_RESPONSE_INTEGRITY:
        encoded = projection["raw_response.raw_response_base64"]
        if type(encoded) is not str:
            return f.RAW_DIGEST_OR_LENGTH_MISMATCH
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError):
            return f.RAW_DIGEST_OR_LENGTH_MISMATCH
        exact = (
            hashlib.sha256(raw).hexdigest()
            == projection["raw_response.reported_sha256"]
            and len(raw) == projection["raw_response.reported_byte_length"]
        )
        return None if exact else f.RAW_DIGEST_OR_LENGTH_MISMATCH
    if guard is g.A07_ENVELOPE_PARSE:
        return None if projection["evaluator_derived.envelope_parse_state"] == "COMPLETE_TYPED_ENVELOPE" else f.MALFORMED_RESPONSE_ENVELOPE
    if guard is g.A08_ACTUAL_PROVIDER:
        return None if projection["identity_evidence.actual_router_id"] == OPENROUTER_PROVIDER_ID else f.ACTUAL_PROVIDER_MISMATCH
    if guard is g.A09_ACTUAL_MODEL:
        actual_model = projection["identity_evidence.actual_model_id"]
        if actual_model is None:
            return f.ACTUAL_MODEL_MISSING
        return None if actual_model == OPENROUTER_MODEL_ID else f.ACTUAL_MODEL_MISMATCH
    if guard is g.A10_ACTUAL_CONFIGURATION:
        return None if projection["identity_evidence.actual_configuration_digest"] == projection["identity_evidence.requested_configuration_digest"] else f.ACTUAL_CONFIGURATION_MISMATCH
    if guard is g.A11_FALLBACK_STATUS:
        return None if projection["identity_evidence.fallback_used"] is False else f.FALLBACK_ACTIVATED
    if guard is g.A12_RETRY_STATUS:
        return None if projection["envelope.adapter_retry_count"] == 0 else f.RETRY_ACTIVATED
    if guard is g.A13_STREAM_STATUS:
        return None if projection["envelope.stream_used"] is False else f.STREAMING_RESPONSE_DETECTED
    if guard is g.A14_TOOL_STATUS:
        return None if projection["envelope.tool_calls"] == 0 else f.TOOL_ACTIVATED
    if guard is g.A15_USAGE_COMPLETENESS:
        if projection["usage_evidence.token_completeness"] != "COMPLETE":
            return f.USAGE_INCOMPLETE
        return None if projection["usage_evidence.input_tokens"] is not None else f.FALSE_ZERO_USAGE
    if guard is g.A16_USAGE_CONSISTENCY:
        total = projection["usage_evidence.total_tokens"]
        input_tokens = projection["usage_evidence.input_tokens"]
        output_tokens = projection["usage_evidence.output_tokens"]
        consistent = all(type(value) is int for value in (total, input_tokens, output_tokens)) and total == input_tokens + output_tokens
        return None if consistent else f.USAGE_INCONSISTENT
    if guard is g.A17_TOKEN_BOUNDS:
        input_tokens = projection["usage_evidence.input_tokens"]
        output_tokens = projection["usage_evidence.output_tokens"]
        within = (
            type(input_tokens) is int
            and type(output_tokens) is int
            and input_tokens
            <= projection["token_policy.payload_input_token_upper_bound"]
            and output_tokens <= projection["token_policy.max_output_tokens"]
        )
        return None if within else f.REPORTED_USAGE_EXCEEDS_BOUND
    if guard is g.A18_COST_LINKAGE:
        return None if projection["attempt_receipt.usage_evidence.cost_bound_id"] == projection["capability_snapshot.cost_bound.cost_bound_id"] else f.COST_LINK_MISMATCH
    if guard is g.A19_RETENTION_PRIVACY:
        clean = (
            projection["raw_response.credential_material_retained"] is False
            and projection["raw_response.sensitive_headers_retained"] is False
            and projection["raw_response.privacy_classification"]
            == "SYNTHETIC_CANNED_OBSERVATION"
            and projection["raw_response.retention_state"]
            == "INLINE_RAW_BYTES_RETAINED"
            and projection["raw_response.assistant_content_treatment"]
            == "OPAQUE_NO_SEMANTIC_EVALUATION"
        )
        return None if clean else f.RETENTION_OR_PRIVACY_VIOLATION
    if guard is g.A20_FINAL_RECEIPT_INTEGRITY:
        payload = projection["attempt_receipt.payload"]
        if not isinstance(payload, dict):
            return f.RECEIPT_MISMATCH
        receipt_payload = dict(payload)
        claimed = receipt_payload.pop("attempt_receipt_id", None)
        expected = stable_contract_id("szorattempt", receipt_payload)
        exact = (
            claimed == projection["attempt_receipt.attempt_receipt_id"]
            and claimed == expected
        )
        return None if exact else f.RECEIPT_MISMATCH
    raise ContractValidationError(f"missing evaluator predicate for guard {guard.value}")


def _first_projection_failure(
    projection: dict[str, object],
) -> tuple[OpenRouterAdapterGuardId, OpenRouterAdapterFailureCode]:
    for guard in OPENROUTER_ADAPTER_GUARD_ORDER_V0:
        failure = _guard_predicate_failure(guard, projection)
        if failure is not None:
            return guard, failure
    raise ContractValidationError("projection unexpectedly passed every mandatory guard")


def _rule_for_mutation(path: str, after_json: str) -> tuple[
    OpenRouterAdapterGuardId, OpenRouterAdapterFailureCode, str
]:
    if path == "prepared_body.canonical_body_json":
        try:
            wire_text = json.loads(after_json)
            parsed = json.loads(wire_text)
        except (TypeError, json.JSONDecodeError):
            return (
                OpenRouterAdapterGuardId.P05_CANONICAL_BODY_INTEGRITY,
                OpenRouterAdapterFailureCode.BODY_DIGEST_OR_LENGTH_MISMATCH,
                "canonical_body",
            )
        if canonical_json(parsed) != wire_text:
            failure = OpenRouterAdapterFailureCode.NONCANONICAL_BODY
        else:
            failure = OpenRouterAdapterFailureCode.BODY_DIGEST_OR_LENGTH_MISMATCH
        return OpenRouterAdapterGuardId.P05_CANONICAL_BODY_INTEGRITY, failure, "canonical_body"
    rule = _PATH_RULES.get(path)
    if rule is None:
        raise ContractValidationError(f"unmapped frozen mutation path: {path}")
    if path == "identity_evidence.actual_model_id" and json.loads(after_json) is None:
        return rule[0], OpenRouterAdapterFailureCode.ACTUAL_MODEL_MISSING, rule[2]
    return rule


def _guard_trace(failed_guard: OpenRouterAdapterGuardId) -> Tuple[
    OpenRouterAdapterGuardExpectationV0, ...
]:
    failure_index = OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(failed_guard)
    return tuple(
        OpenRouterAdapterGuardExpectationV0(
            guard_id=guard,
            state=(
                OpenRouterAdapterGuardState.PASSED
                if index < failure_index
                else OpenRouterAdapterGuardState.FAILED
                if index == failure_index
                else OpenRouterAdapterGuardState.NOT_REACHED
            ),
        )
        for index, guard in enumerate(OPENROUTER_ADAPTER_GUARD_ORDER_V0)
    )


def _case_path_baseline(
    case_path: str,
    projection: dict[str, tuple[object, str]],
) -> Optional[tuple[object, str]]:
    return projection.get(case_path)


def _apply_case_mutation(
    projection: dict[str, object],
    case_path: str,
    after_json: str,
) -> None:
    if case_path not in projection:
        raise ContractValidationError(
            f"frozen mutation path has no concrete projection: {case_path}"
        )
    projection[case_path] = json.loads(after_json)
    if case_path in {
        "usage_evidence.input_tokens",
        "usage_evidence.output_tokens",
    }:
        input_tokens = projection["usage_evidence.input_tokens"]
        output_tokens = projection["usage_evidence.output_tokens"]
        if type(input_tokens) is int and type(output_tokens) is int:
            projection["usage_evidence.total_tokens"] = input_tokens + output_tokens


def _probe_construction(
    probe: OpenRouterAdapterProbeV0,
    projection: dict[str, tuple[object, str]],
) -> OpenRouterProbeConstructionEvidenceV0:
    observations = []
    derived_fields = []
    for mutation in probe.literal_mutations:
        guard, failure, vector_field = _rule_for_mutation(
            mutation.path, mutation.after_json
        )
        derived_fields.append(vector_field)
        concrete_paths = (mutation.path,)
        baseline = _case_path_baseline(mutation.path, projection)
        if baseline is None:
            actual_before = None
            source = "UNRESOLVED"
            state = ProbeConstructionState.UNRESOLVED
        else:
            value, source = baseline
            actual_before = canonical_json(value)
            state = (
                ProbeConstructionState.VALIDATED
                if actual_before == mutation.before_json
                else ProbeConstructionState.BASELINE_MISMATCH
            )
        observations.append(
            OpenRouterMutationObservationV0(
                path=mutation.path,
                concrete_projection_paths=concrete_paths,
                declared_before_json=mutation.before_json,
                declared_after_json=mutation.after_json,
                actual_before_json=actual_before,
                baseline_source=source,
                construction_state=state,
                direct_vector_field=vector_field,
                independently_derived_guard_id=guard,
                independently_derived_failure=failure,
            )
        )
    declared = tuple(
        name
        for name, value in probe.mutation_vector
        if name != "schema_version" and value is MutationState.INTENTIONALLY_CHANGED
    )
    declared_dependent = tuple(
        name
        for name, value in probe.mutation_vector
        if name != "schema_version" and value is MutationState.DEPENDENTLY_CHANGED
    )
    derived = tuple(sorted(derived_fields))
    declared_sorted = tuple(sorted(declared))
    declared_dependent_sorted = tuple(sorted(declared_dependent))
    derived_dependent = tuple(
        sorted(
            {
                dependent
                for mutation in probe.literal_mutations
                for dependent in _PATH_DEPENDENT_VECTOR_FIELDS.get(
                    mutation.path, ()
                )
                if dependent not in derived
            }
        )
    )
    mismatches = sum(
        item.construction_state is ProbeConstructionState.BASELINE_MISMATCH
        for item in observations
    )
    unresolved = sum(
        item.construction_state is ProbeConstructionState.UNRESOLVED
        for item in observations
    )
    return OpenRouterProbeConstructionEvidenceV0(
        observations=tuple(observations),
        declared_intentionally_changed_fields=declared_sorted,
        derived_intentionally_changed_fields=derived,
        declared_dependently_changed_fields=declared_dependent_sorted,
        derived_dependently_changed_fields=derived_dependent,
        mutation_vector_exact=(
            declared_sorted == derived
            and declared_dependent_sorted == derived_dependent
        ),
        construction_fully_validated=(mismatches == 0 and unresolved == 0),
        construction_failure_code=(
            None if mismatches == 0 and unresolved == 0 else "INVALID_PROBE_CONSTRUCTION"
        ),
        baseline_mismatch_count=mismatches,
        unresolved_path_count=unresolved,
    )


def evaluate_openrouter_adapter_case_v0(
    case: CaseContractV0,
) -> OpenRouterCaseEvaluationV0:
    """Evaluate one frozen case without transport, history reads, or publication."""

    _, projection_evidence = _candidate_fixture()
    projection = {
        path: value_and_source[0]
        for path, value_and_source in projection_evidence.items()
    }
    construction = None
    if isinstance(case, OpenRouterAdapterProbeV0):
        construction = _probe_construction(case, projection_evidence)
        for mutation in case.literal_mutations:
            _apply_case_mutation(
                projection,
                mutation.path,
                mutation.after_json,
            )
    actual_guard, actual_failure = _first_projection_failure(projection)
    trace = _guard_trace(actual_guard)
    if isinstance(case, OpenRouterAdapterPositiveCaseV0):
        case_id = case.case_id
        fingerprint = case.case_fingerprint or ""
        case_class = OpenRouterAdapterCaseClass.POSITIVE
        expected_guard = None
        expected_failure = None
        attempts = case.evaluator_input_attempt_count
        expected_attempt_receipts = case.expected_attempt_receipts
        expected_invocations = case.expected_canned_invocations
        expected_trace = None
    else:
        case_id = case.probe_id
        fingerprint = case.probe_fingerprint or ""
        case_class = case.probe_class
        expected_guard = case.expected_guard_id
        expected_failure = case.expected_primary_failure
        attempts = case.evaluator_input_attempt_count
        expected_attempt_receipts = case.expected_attempt_receipts
        expected_invocations = case.expected_canned_invocations
        expected_trace = case.expected_guard_trace
    receipts = tuple(
        OpenRouterAttemptEvaluationReceiptV0(
            case_id=case_id,
            attempt_ordinal=ordinal,
            failure_guard_id=actual_guard,
            failure_code=actual_failure,
        )
        for ordinal in range(1, attempts + 1)
    )
    primary_exact = (
        case.expected_outcome is OpenRouterAdapterAttemptOutcome.REJECTED
        and expected_guard is actual_guard
        and expected_failure is actual_failure
    )
    trace_exact = expected_trace == trace if expected_trace is not None else False
    invocation_exact = expected_invocations == 0
    attempt_count_exact = expected_attempt_receipts == len(receipts)
    construction_ok = construction is None or (
        construction.construction_fully_validated and construction.mutation_vector_exact
    )
    return OpenRouterCaseEvaluationV0(
        case_id=case_id,
        case_fingerprint=fingerprint,
        case_class=case_class,
        expected_outcome=case.expected_outcome,
        expected_guard_id=expected_guard,
        expected_primary_failure=expected_failure,
        actual_guard_id=actual_guard,
        actual_primary_failure=actual_failure,
        actual_guard_trace=trace,
        expected_canned_invocations=expected_invocations,
        evaluator_input_attempt_count=attempts,
        expected_attempt_receipts=expected_attempt_receipts,
        attempt_receipts=receipts,
        construction_evidence=construction,
        primary_result_exact=primary_exact,
        guard_trace_exact=trace_exact,
        invocation_count_exact=invocation_exact,
        attempt_count_exact=attempt_count_exact,
        scoring_eligible=construction_ok,
        case_passed=(
            primary_exact
            and trace_exact
            and invocation_exact
            and attempt_count_exact
            and construction_ok
        ),
    )


def _normalize_scoped_path_inventory_v0(
    inventory: Tuple[Tuple[str, Tuple[str, ...]], ...],
) -> Tuple[Tuple[OpenRouterMutationScope, Tuple[str, ...]], ...]:
    expected_scopes = tuple(OpenRouterMutationScope)
    if len(inventory) != len(expected_scopes):
        raise ContractValidationError("scoped path inventory category count changed")
    normalized = []
    seen_paths = set()
    for (raw_scope, raw_paths), expected_scope in zip(inventory, expected_scopes):
        try:
            scope = OpenRouterMutationScope(raw_scope)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("scoped path inventory category is invalid") from exc
        if scope is not expected_scope:
            raise ContractValidationError("scoped path inventory category order changed")
        if not isinstance(raw_paths, tuple) or not raw_paths:
            raise ContractValidationError("scoped path inventory category is empty")
        paths = tuple(_canonical_scoped_relative_path(path) for path in raw_paths)
        if len(set(paths)) != len(paths):
            raise ContractValidationError("scoped path inventory contains duplicates")
        if not seen_paths.isdisjoint(paths):
            raise ContractValidationError("scoped path appears in multiple categories")
        seen_paths.update(paths)
        normalized.append((scope, paths))
    return tuple(normalized)


def capture_openrouter_scoped_path_snapshot_v0(
    repository_root: Path | str,
    inventory: Tuple[
        Tuple[str, Tuple[str, ...]], ...
    ] = FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0,
) -> OpenRouterScopedPathSnapshotV0:
    """Hash only the explicit inventory; never enumerate the repository."""

    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ContractValidationError("scoped path repository root is not a directory")
    normalized = _normalize_scoped_path_inventory_v0(inventory)
    rows = []
    for scope, paths in normalized:
        for relative_path in paths:
            relative = PurePosixPath(relative_path)
            target = (root / Path(*relative.parts)).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ContractValidationError(
                    "scoped inventory path resolves outside repository root"
                ) from exc
            raw: Optional[bytes]
            if target.is_file():
                try:
                    raw = target.read_bytes()
                except FileNotFoundError:
                    raw = None
            else:
                raw = None
            rows.append(
                OpenRouterScopedPathDigestV0(
                    scope=scope,
                    relative_path=relative_path,
                    present=raw is not None,
                    sha256=(hashlib.sha256(raw).hexdigest() if raw is not None else None),
                )
            )
    return OpenRouterScopedPathSnapshotV0(rows=tuple(rows))


def compare_openrouter_scoped_path_snapshots_v0(
    before: OpenRouterScopedPathSnapshotV0,
    after: OpenRouterScopedPathSnapshotV0,
) -> OpenRouterScopedMutationEvidenceV0:
    before = OpenRouterScopedPathSnapshotV0.model_validate(
        before.model_dump(mode="python")
    )
    after = OpenRouterScopedPathSnapshotV0.model_validate(
        after.model_dump(mode="python")
    )
    before_identities = tuple(
        (row.scope, row.relative_path) for row in before.rows
    )
    after_identities = tuple((row.scope, row.relative_path) for row in after.rows)
    if before_identities != after_identities:
        raise ContractValidationError("scoped before/after inventory coverage differs")
    rows = tuple(
        OpenRouterScopedPathMutationV0(
            scope=before_row.scope,
            relative_path=before_row.relative_path,
            before_present=before_row.present,
            before_sha256=before_row.sha256,
            after_present=after_row.present,
            after_sha256=after_row.sha256,
        )
        for before_row, after_row in zip(before.rows, after.rows)
    )
    return OpenRouterScopedMutationEvidenceV0(
        inventory_id=_scoped_inventory_id_from_mutations_v0(rows),
        before_snapshot_id=before.snapshot_id or "",
        after_snapshot_id=after.snapshot_id or "",
        rows=rows,
    )


def _assert_frozen_scoped_mutation_accounting_v0(
    evidence: OpenRouterScopedMutationEvidenceV0,
    counters: OpenRouterTripwireCountersV0,
    metrics: Optional[OpenRouterEvaluationMetricsV0] = None,
) -> None:
    validated_evidence = OpenRouterScopedMutationEvidenceV0.model_validate(
        evidence.model_dump(mode="python")
    )
    if validated_evidence != evidence:
        raise ContractValidationError("artifact scoped mutation evidence was not validated")
    validated_counters = OpenRouterTripwireCountersV0.model_validate(
        counters.model_dump(mode="python")
    )
    if validated_counters != counters:
        raise ContractValidationError("artifact mutation counters were not validated")
    if metrics is not None:
        validated_metrics = OpenRouterEvaluationMetricsV0.model_validate(
            metrics.model_dump(mode="python")
        )
        if validated_metrics != metrics:
            raise ContractValidationError("artifact mutation metrics were not validated")
    frozen_pairs = tuple(
        (OpenRouterMutationScope(scope), relative_path)
        for scope, paths in FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0
        for relative_path in paths
    )
    actual_pairs = tuple((row.scope, row.relative_path) for row in evidence.rows)
    if evidence.inventory_id != FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_ID_V0:
        raise ContractValidationError("artifact scoped inventory ID is not frozen")
    if actual_pairs != frozen_pairs:
        raise ContractValidationError("artifact scoped inventory membership changed")
    evidence_counts = (
        evidence.source_mutations,
        evidence.sibling_mutations,
        evidence.production_mutations,
    )
    counter_counts = (
        counters.source_mutations,
        counters.sibling_mutations,
        counters.production_mutations,
    )
    if evidence_counts != counter_counts:
        raise ContractValidationError("artifact mutation counters differ from path evidence")
    if metrics is not None and evidence_counts != (
        metrics.source_mutations,
        metrics.sibling_mutations,
        metrics.production_mutations,
    ):
        raise ContractValidationError("artifact mutation metrics differ from path evidence")


def _build_authoritative_artifact_under_scoped_guard_v0(
    repository_root: Path,
    before: OpenRouterScopedPathSnapshotV0,
    embedded_after: OpenRouterScopedPathSnapshotV0,
    artifact_builder: Callable[[], OpenRouterEvaluationArtifactV0],
) -> OpenRouterEvaluationArtifactV0:
    """Build and validate the artifact before closing the scoped hash window."""

    artifact = artifact_builder()
    final_postbuild = capture_openrouter_scoped_path_snapshot_v0(repository_root)
    if final_postbuild != embedded_after or final_postbuild != before:
        raise ContractValidationError(
            "scoped paths changed during authoritative artifact construction"
        )
    expected_evidence = compare_openrouter_scoped_path_snapshots_v0(
        before,
        embedded_after,
    )
    if artifact.scoped_mutation_evidence != expected_evidence:
        raise ContractValidationError(
            "artifact scoped evidence differs from authoritative capture window"
        )
    return artifact


def verify_historical_hashes_v0(
    repository_root: Path | str,
    locks: Tuple[Tuple[str, str, str], ...] = _HISTORICAL_ARTIFACT_LOCKS,
) -> Tuple[OpenRouterHistoricalHashEvidenceV0, ...]:
    """Read only the explicitly supplied historical paths and verify SHA-256."""

    root = Path(repository_root).resolve()
    evidence = []
    for label, repository_path, expected in locks:
        path = (root / repository_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ContractValidationError("historical path escapes repository root") from exc
        observed = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        evidence.append(
            OpenRouterHistoricalHashEvidenceV0(
                label=label,
                repository_path=repository_path,
                expected_sha256=expected,
                observed_sha256=observed,
                matches=observed == expected,
            )
        )
    return tuple(evidence)


def _project_core_lock_id(value: object) -> Optional[str]:
    if type(value) is not str or not value.startswith("cedcorebloblockv2_"):
        return None
    suffix = value.removeprefix("cedcorebloblockv2_")
    if len(suffix) != 64 or any(character not in "0123456789abcdef" for character in suffix):
        return None
    return value


def _project_hex64(value: object) -> Optional[str]:
    if type(value) is not str or len(value) != 64:
        return None
    if any(character not in "0123456789abcdef" for character in value):
        return None
    return value


def verify_core_blob_lock_v0(
    repository_root: Path | str,
) -> OpenRouterCoreBlobLockEvidenceV0:
    """Parse and recompute the sealed Phase-8 v2 core-lock identity."""

    root = Path(repository_root).resolve()
    path = (root / FROZEN_CORE_BLOB_LOCK_SOURCE_PATH_V2).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ContractValidationError("core-lock path escapes repository root") from exc
    observed_sha: Optional[str] = None
    top_level: Optional[str] = None
    embedded_id: Optional[str] = None
    embedded_fingerprint: Optional[str] = None
    recomputed_id: Optional[str] = None
    recomputed_fingerprint: Optional[str] = None
    if path.is_file():
        raw = path.read_bytes()
        observed_sha = hashlib.sha256(raw).hexdigest()
        try:
            artifact = json.loads(raw)
            if not isinstance(artifact, Mapping):
                raise TypeError("core-lock artifact must be an object")
            embedded = artifact.get("core_lock")
            if not isinstance(embedded, Mapping):
                raise TypeError("core-lock payload must be an object")
            top_level = _project_core_lock_id(artifact.get("core_lock_id"))
            embedded_id = _project_core_lock_id(embedded.get("lock_id"))
            embedded_fingerprint = _project_hex64(embedded.get("fingerprint"))
            identity_payload = {
                key: value
                for key, value in embedded.items()
                if key not in {"lock_id", "fingerprint"}
            }
            recomputed_fingerprint = hashlib.sha256(
                canonical_json(identity_payload).encode("utf-8")
            ).hexdigest()
            recomputed_id = stable_contract_id(
                "cedcorebloblockv2", identity_payload
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    expected_fingerprint = FROZEN_CORE_BLOB_LOCK_ID_V2.removeprefix(
        "cedcorebloblockv2_"
    )
    matches = all(
        (
            observed_sha == FROZEN_CORE_BLOB_LOCK_SOURCE_SHA256_V2,
            top_level == FROZEN_CORE_BLOB_LOCK_ID_V2,
            embedded_id == FROZEN_CORE_BLOB_LOCK_ID_V2,
            embedded_fingerprint == expected_fingerprint,
            recomputed_id == FROZEN_CORE_BLOB_LOCK_ID_V2,
            recomputed_fingerprint == expected_fingerprint,
        )
    )
    return OpenRouterCoreBlobLockEvidenceV0(
        source_artifact_observed_sha256=observed_sha,
        actual_top_level_lock_id=top_level,
        actual_embedded_lock_id=embedded_id,
        actual_embedded_fingerprint=embedded_fingerprint,
        recomputed_embedded_lock_id=recomputed_id,
        recomputed_embedded_fingerprint=recomputed_fingerprint,
        matches=matches,
    )


def _evaluate_frozen_case_set_v0() -> Tuple[OpenRouterCaseEvaluationV0, ...]:
    return tuple(
        evaluate_openrouter_adapter_case_v0(case)
        for case in (
            FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
            + FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
            + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
        )
    )


def _metrics(
    results: Tuple[OpenRouterCaseEvaluationV0, ...],
    historical: Tuple[OpenRouterHistoricalHashEvidenceV0, ...],
    core_blob_lock: OpenRouterCoreBlobLockEvidenceV0,
    candidate: OpenRouterCandidateEvidenceV0,
    tripwire_counters: OpenRouterTripwireCountersV0,
) -> OpenRouterEvaluationMetricsV0:
    positive = tuple(r for r in results if r.case_class is OpenRouterAdapterCaseClass.POSITIVE)
    orthogonal = tuple(r for r in results if r.case_class is OpenRouterAdapterCaseClass.ORTHOGONAL)
    precedence = tuple(r for r in results if r.case_class is OpenRouterAdapterCaseClass.PRECEDENCE)
    invalid = sum(
        r.construction_evidence is not None
        and (
            not r.construction_evidence.construction_fully_validated
            or not r.construction_evidence.mutation_vector_exact
        )
        for r in results
    )
    mismatch = sum(
        not (
            r.primary_result_exact
            and r.guard_trace_exact
            and r.invocation_count_exact
            and r.attempt_count_exact
        )
        for r in results
    )
    historical_mismatches = sum(not item.matches for item in historical)
    actual_failures = tuple(result.actual_primary_failure for result in results)
    accepted_violations = tuple(
        result
        for result in results
        if result.actual_outcome is OpenRouterAdapterAttemptOutcome.EVIDENCE_READY
        and result.case_class is not OpenRouterAdapterCaseClass.POSITIVE
    )
    accepted_failures = tuple(
        result.actual_primary_failure for result in accepted_violations
    )
    body_failures = {
        OpenRouterAdapterFailureCode.NONCANONICAL_BODY,
        OpenRouterAdapterFailureCode.BODY_DIGEST_OR_LENGTH_MISMATCH,
    }
    entropy_failures = {
        OpenRouterAdapterFailureCode.FORBIDDEN_ENTROPY,
        OpenRouterAdapterFailureCode.CREDENTIAL_OR_HEADER_LEAKAGE,
    }
    identity_failures = {
        OpenRouterAdapterFailureCode.REQUESTED_IDENTITY_MISMATCH,
        OpenRouterAdapterFailureCode.ACTUAL_PROVIDER_MISMATCH,
        OpenRouterAdapterFailureCode.ACTUAL_MODEL_MISSING,
        OpenRouterAdapterFailureCode.ACTUAL_MODEL_MISMATCH,
        OpenRouterAdapterFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
    }
    fallback_failures = {
        OpenRouterAdapterFailureCode.FALLBACK_INTENT_NOT_DISABLED,
        OpenRouterAdapterFailureCode.FALLBACK_ACTIVATED,
    }
    retry_failures = {
        OpenRouterAdapterFailureCode.RETRY_POLICY_UNPROVEN,
        OpenRouterAdapterFailureCode.RETRY_ACTIVATED,
    }
    stream_failures = {
        OpenRouterAdapterFailureCode.STREAM_NOT_DISABLED,
        OpenRouterAdapterFailureCode.STREAMING_RESPONSE_DETECTED,
    }
    tool_failures = {
        OpenRouterAdapterFailureCode.TOOLS_NOT_DISABLED,
        OpenRouterAdapterFailureCode.TOOL_ACTIVATED,
    }
    token_pricing_cost_failures = {
        OpenRouterAdapterFailureCode.INPUT_BOUND_UNPROVEN,
        OpenRouterAdapterFailureCode.PRICING_NOT_ESTABLISHED,
        OpenRouterAdapterFailureCode.PRICING_BINDING_MISMATCH,
        OpenRouterAdapterFailureCode.COST_BOUND_INVALID,
        OpenRouterAdapterFailureCode.COST_OVERFLOW,
        OpenRouterAdapterFailureCode.REPORTED_USAGE_EXCEEDS_BOUND,
        OpenRouterAdapterFailureCode.COST_LINK_MISMATCH,
    }
    raw_usage_privacy_receipt_failures = {
        OpenRouterAdapterFailureCode.MISSING_RAW_RESPONSE,
        OpenRouterAdapterFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH,
        OpenRouterAdapterFailureCode.MALFORMED_RESPONSE_ENVELOPE,
        OpenRouterAdapterFailureCode.USAGE_INCOMPLETE,
        OpenRouterAdapterFailureCode.FALSE_ZERO_USAGE,
        OpenRouterAdapterFailureCode.USAGE_INCONSISTENT,
        OpenRouterAdapterFailureCode.RETENTION_OR_PRIVACY_VIOLATION,
        OpenRouterAdapterFailureCode.RECEIPT_MISMATCH,
    }
    receipt_ids = tuple(
        receipt.attempt_receipt_id
        for result in results
        for receipt in result.attempt_receipts
    )
    return OpenRouterEvaluationMetricsV0(
        positive_complete_case_results=sum(r.case_passed for r in positive),
        positive_attempt_receipts=sum(len(r.attempt_receipts) for r in positive),
        exact_positive_receipts=sum(
            len(r.attempt_receipts) for r in positive if r.case_passed
        ),
        orthogonal_exact_primary_results=sum(
            r.primary_result_exact and r.scoring_eligible for r in orthogonal
        ),
        precedence_exact_primary_results=sum(
            r.primary_result_exact and r.scoring_eligible for r in precedence
        ),
        attempt_receipts_total=sum(len(r.attempt_receipts) for r in results),
        canned_transport_invocations=sum(r.observed_canned_invocations for r in results),
        invalid_probe_constructions=invalid,
        unexpected_failure_or_mismatch_count=mismatch,
        historical_lock_mismatches=historical_mismatches,
        core_lock_mismatches=int(not core_blob_lock.matches),
        body_byte_mismatch_results=sum(
            failure in body_failures for failure in actual_failures
        ),
        entropy_violation_results=sum(
            failure in entropy_failures for failure in actual_failures
        ),
        route_policy_unproven_results=sum(
            failure is OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN
            for failure in actual_failures
        ),
        fallback_intent_control_failures=int(
            _P09 in candidate.unresolved_mandatory_guards
            or candidate.provider_side_fallback_state
            is OpenRouterEvidenceState.NOT_ESTABLISHED
        ),
        receipt_mismatch_results=sum(
            failure is OpenRouterAdapterFailureCode.RECEIPT_MISMATCH
            for failure in actual_failures
        ),
        token_bound_failures=int(
            _P17 in candidate.unresolved_mandatory_guards
            or candidate.provider_input_bound_state
            is OpenRouterEvidenceState.NOT_ESTABLISHED
        ),
        pricing_cost_evidence_failures=sum(
            guard in candidate.unresolved_mandatory_guards
            for guard in (_P18, _P19)
        ),
        timeout_worker_leaks=sum(
            failure is OpenRouterAdapterFailureCode.WORKER_NOT_TERMINATED
            for failure in actual_failures
        ),
        multiple_transport_invocations=sum(
            failure is OpenRouterAdapterFailureCode.MULTIPLE_TRANSPORT_INVOCATIONS
            for failure in actual_failures
        ),
        raw_response_evidence_failures=sum(
            failure
            in {
                OpenRouterAdapterFailureCode.MISSING_RAW_RESPONSE,
                OpenRouterAdapterFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH,
                OpenRouterAdapterFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            }
            for failure in actual_failures
        ),
        usage_incompleteness=sum(
            failure is OpenRouterAdapterFailureCode.USAGE_INCOMPLETE
            for failure in actual_failures
        ),
        false_zero_violations=sum(
            failure is OpenRouterAdapterFailureCode.FALSE_ZERO_USAGE
            for failure in actual_failures
        ),
        identity_collisions=len(receipt_ids) - len(set(receipt_ids)),
        credential_header_leakage=sum(
            failure is OpenRouterAdapterFailureCode.CREDENTIAL_OR_HEADER_LEAKAGE
            for failure in actual_failures
        ),
        body_byte_mismatches_accepted=sum(
            failure in body_failures for failure in accepted_failures
        ),
        entropy_violations_accepted=sum(
            failure in entropy_failures for failure in accepted_failures
        ),
        model_provider_configuration_mismatches_accepted=sum(
            failure in identity_failures for failure in accepted_failures
        ),
        fallback_activations_accepted=sum(
            failure is OpenRouterAdapterFailureCode.FALLBACK_ACTIVATED
            for failure in accepted_failures
        ),
        retry_activations_accepted=sum(
            failure is OpenRouterAdapterFailureCode.RETRY_ACTIVATED
            for failure in accepted_failures
        ),
        streaming_activations_accepted=sum(
            failure is OpenRouterAdapterFailureCode.STREAMING_RESPONSE_DETECTED
            for failure in accepted_failures
        ),
        tool_activations_accepted=sum(
            failure is OpenRouterAdapterFailureCode.TOOL_ACTIVATED
            for failure in accepted_failures
        ),
        receipt_mismatches_accepted=sum(
            failure is OpenRouterAdapterFailureCode.RECEIPT_MISMATCH
            for failure in accepted_failures
        ),
        accepted_control_violations=len(accepted_violations),
        accepted_identity_mismatches=sum(
            failure in identity_failures for failure in accepted_failures
        ),
        accepted_fallback_retry_stream_tool_activations=sum(
            failure in (fallback_failures | retry_failures | stream_failures | tool_failures)
            for failure in accepted_failures
        ),
        accepted_token_pricing_cost_failures=sum(
            failure in token_pricing_cost_failures
            for failure in accepted_failures
        ),
        accepted_raw_usage_privacy_receipt_failures=sum(
            failure in raw_usage_privacy_receipt_failures
            for failure in accepted_failures
        ),
        unexpected_multiple_transport_invocations=sum(
            failure is OpenRouterAdapterFailureCode.MULTIPLE_TRANSPORT_INVOCATIONS
            for failure in actual_failures
        ),
        surviving_tasks=sum(
            failure is OpenRouterAdapterFailureCode.WORKER_NOT_TERMINATED
            for failure in actual_failures
        ),
        accepted_late_mutations=sum(
            failure is OpenRouterAdapterFailureCode.LATE_MUTATION_DETECTED
            for failure in accepted_failures
        ),
        external_network_attempts=tripwire_counters.external_network_attempts,
        credential_access_attempts=(
            tripwire_counters.credential_access_attempts
        ),
        provider_calls=tripwire_counters.live_provider_calls,
        provider_sdk_calls=tripwire_counters.provider_sdk_calls,
        model_calls=tripwire_counters.model_executions,
        tool_calls=tripwire_counters.tool_calls,
        ced_application_invocations=(
            tripwire_counters.canonical_application_calls
        ),
        source_mutations=tripwire_counters.source_mutations,
        sibling_mutations=tripwire_counters.sibling_mutations,
        production_mutations=tripwire_counters.production_mutations,
        pricing_status=candidate.pricing_state.value,
        live_model_pricing_status=candidate.pricing_state.value,
    )


def run_authoritative_openrouter_acquisition_evaluation_v0(
    *, repository_root: Optional[Path | str] = None
) -> OpenRouterEvaluationArtifactV0:
    """Build the one authoritative aggregate under an already-active tripwire.

    This function is intentionally not called at import time or by focused unit
    tests.  The root orchestrator may call it exactly once after the pre-result
    freeze gate.
    """

    tripwire = active_acquisition_boundary_tripwire_v0()
    tripwire.assert_clean()
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[3]
    )
    scoped_paths_before = capture_openrouter_scoped_path_snapshot_v0(root)
    historical_before = verify_historical_hashes_v0(root)
    core_blob_lock_before = verify_core_blob_lock_v0(root)
    results = _evaluate_frozen_case_set_v0()
    candidate, _ = _candidate_fixture()
    historical = verify_historical_hashes_v0(root)
    core_blob_lock = verify_core_blob_lock_v0(root)
    if historical != historical_before or core_blob_lock != core_blob_lock_before:
        raise ContractValidationError(
            "historical or core-lock evidence changed during evaluation"
        )
    scoped_paths_after = capture_openrouter_scoped_path_snapshot_v0(root)
    scoped_mutation_evidence = compare_openrouter_scoped_path_snapshots_v0(
        scoped_paths_before,
        scoped_paths_after,
    )
    counters = OpenRouterTripwireCountersV0(
        source_mutations=scoped_mutation_evidence.source_mutations,
        sibling_mutations=scoped_mutation_evidence.sibling_mutations,
        production_mutations=scoped_mutation_evidence.production_mutations,
    )
    metrics = _metrics(
        results,
        historical,
        core_blob_lock,
        candidate,
        counters,
    )
    def build_and_validate_artifact() -> OpenRouterEvaluationArtifactV0:
        artifact = OpenRouterEvaluationArtifactV0(
            capability_snapshot_id=candidate.capability_snapshot_id,
            endpoint_policy_id=candidate.endpoint_policy_id,
            route_policy_id=candidate.route_policy_id,
            control_policy_id=candidate.control_policy_id,
            transport_policy_id=candidate.transport_policy_id,
            token_policy_id=candidate.token_policy_id,
            pricing_record_id=candidate.pricing_record_id,
            cost_bound_id=candidate.cost_bound_id,
            raw_response_evidence_id=candidate.raw_response_evidence_id,
            identity_evidence_id=candidate.identity_evidence_id,
            usage_evidence_id=candidate.usage_evidence_id,
            canned_response_envelope_id=candidate.canned_response_envelope_id,
            attempt_receipt_id=candidate.attempt_receipt_id,
            reference_receipt_summary_id=candidate.reference_receipt_summary_id,
            reference_receipt_summary=candidate.reference_receipt_summary,
            reference_canned_fixture_only=candidate.reference_canned_fixture_only,
            actual_canned_transport_invocations=(
                candidate.actual_canned_transport_invocations
            ),
            actual_response_receipt=candidate.actual_response_receipt,
            baseline_projection_sha256=candidate.baseline_projection_sha256,
            fixture_manifest_id=candidate.fixture_manifest_id,
            case_set_id=FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.case_set_id or "",
            metrics_id=metrics.metrics_id or "",
            thresholds_id=(
                FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.thresholds_id or ""
            ),
            case_set_sha256=frozen_openrouter_adapter_case_set_sha256_v0(),
            candidate_evidence=candidate,
            case_results=results,
            metrics=metrics,
            historical_hashes=historical,
            core_blob_lock=core_blob_lock,
            tripwire_counters=counters,
            scoped_mutation_evidence=scoped_mutation_evidence,
        )
        tripwire.assert_artifact_counters(artifact.tripwire_counters)
        return artifact

    return _build_authoritative_artifact_under_scoped_guard_v0(
        root,
        scoped_paths_before,
        scoped_paths_after,
        build_and_validate_artifact,
    )


def render_openrouter_evaluation_artifact_v0(
    artifact: OpenRouterEvaluationArtifactV0,
) -> str:
    validated = OpenRouterEvaluationArtifactV0.model_validate_json(
        artifact.model_dump_json()
    )
    return canonical_json(validated.model_dump(mode="json")) + "\n"


def replay_openrouter_evaluation_artifact_v0(
    rendered: str,
) -> OpenRouterEvaluationArtifactV0:
    artifact = OpenRouterEvaluationArtifactV0.model_validate_json(rendered)
    if render_openrouter_evaluation_artifact_v0(artifact) != rendered:
        raise ContractValidationError("OpenRouter evaluation artifact is not canonical")
    return artifact


def openrouter_evaluation_artifact_sha256_v0(
    artifact: OpenRouterEvaluationArtifactV0,
) -> str:
    return hashlib.sha256(
        render_openrouter_evaluation_artifact_v0(artifact).encode("utf-8")
    ).hexdigest()


def publish_openrouter_evaluation_artifact_once_v0(
    destination: Path | str,
    artifact: OpenRouterEvaluationArtifactV0,
) -> str:
    """Publish canonical bytes once; never create a replay lock for FALSIFIED."""

    tripwire = active_acquisition_boundary_tripwire_v0()
    tripwire.assert_artifact_counters(artifact.tripwire_counters)
    if artifact.hypothesis_status is not OpenRouterHypothesisStatus.FALSIFIED:
        raise ContractValidationError("unexpected OpenRouter hypothesis state")
    if artifact.replay_lock_created:
        raise ContractValidationError("falsified evaluation cannot carry a replay lock")
    rendered = render_openrouter_evaluation_artifact_v0(artifact)
    replay_openrouter_evaluation_artifact_v0(rendered)
    payload = rendered.encode("utf-8")
    path = Path(destination)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ContractValidationError(
                "write-once destination already contains different bytes"
            )
    tripwire.assert_artifact_counters(artifact.tripwire_counters)
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "FROZEN_CORE_BLOB_LOCK_ID_V2",
    "FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_ID_V0",
    "FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0",
    "OPENROUTER_ARTIFACT_SCHEMA_V0",
    "OPENROUTER_CASE_RESULT_SCHEMA_V0",
    "OPENROUTER_EVALUATION_SCHEMA_V0",
    "OPENROUTER_EVALUATOR_VERSION_V0",
    "OPENROUTER_FIXTURE_MANIFEST_SCHEMA_V0",
    "OPENROUTER_REFERENCE_RECEIPT_SUMMARY_SCHEMA_V0",
    "OPENROUTER_SCOPED_MUTATION_EVIDENCE_SCHEMA_V0",
    "OPENROUTER_SCOPED_PATH_INVENTORY_SCHEMA_V0",
    "OPENROUTER_SCOPED_PATH_SNAPSHOT_SCHEMA_V0",
    "OpenRouterCandidateEvidenceV0",
    "OpenRouterCaseEvaluationV0",
    "OpenRouterCoreBlobLockEvidenceV0",
    "OpenRouterEvaluationArtifactV0",
    "OpenRouterEvaluationMetricsV0",
    "OpenRouterHistoricalHashEvidenceV0",
    "OpenRouterHypothesisStatus",
    "OpenRouterMutationObservationV0",
    "OpenRouterMutationScope",
    "OpenRouterProbeConstructionEvidenceV0",
    "OpenRouterReferenceCannedReceiptSummaryV0",
    "OpenRouterScopedMutationEvidenceV0",
    "OpenRouterScopedPathDigestV0",
    "OpenRouterScopedPathMutationV0",
    "OpenRouterScopedPathSnapshotV0",
    "OpenRouterTripwireCountersV0",
    "ProbeConstructionState",
    "build_openrouter_candidate_evidence_v0",
    "capture_openrouter_scoped_path_snapshot_v0",
    "compare_openrouter_scoped_path_snapshots_v0",
    "evaluate_openrouter_adapter_case_v0",
    "openrouter_evaluation_artifact_sha256_v0",
    "publish_openrouter_evaluation_artifact_once_v0",
    "render_openrouter_evaluation_artifact_v0",
    "replay_openrouter_evaluation_artifact_v0",
    "run_authoritative_openrouter_acquisition_evaluation_v0",
    "verify_core_blob_lock_v0",
    "verify_historical_hashes_v0",
]

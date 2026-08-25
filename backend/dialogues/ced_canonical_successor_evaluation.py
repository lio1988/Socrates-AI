"""Frozen Phase 8 v1 evaluator over authoritative recorded observations.

This module is the post-freeze aggregate harness, not an observation recorder.
It reconstructs pristine roots from the frozen corpus, prepares one legal
opening transition, and applies only the exact manifest-owned observation.
It never invokes a provider or regenerates evaluator-side reference truth.

The contracts, case set, parity fields, metrics, and thresholds are defined at
import time so they can be reviewed and committed before the first aggregate
execution. Calling :func:`build_canonical_successor_parity_artifact` is the
authoritative aggregate run and is intentionally left to the post-freeze gate.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Iterable, Literal, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .agent import SocraticAgent
from .ced import CEDOrchestrator
from .ced_canonical_successor import (
    CANONICAL_PROCESSOR_IDS,
    CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID,
    CanonicalSuccessorEnvironmentV0,
    CanonicalSuccessorUnavailable,
    canonical_capsule_semantic_snapshot,
    canonical_runtime_fingerprint,
)
from .ced_canonical_successor_cases_v1 import (
    CANONICAL_SUCCESSOR_CORPUS_VERSION,
    CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION,
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
    FROZEN_PARITY_FIELD_NAMES,
    AuthoritativeRecordedObservationCase,
    CanonicalSuccessorReferenceField,
    RecordedObservationFixtureRole,
    canonical_successor_reference_field_digests,
    frozen_corpus_v1_canonical_sha256,
)
from .ced_canonical_successor_contracts import (
    CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION,
    CANONICAL_SUCCESSOR_ENV_ID,
    CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION,
    CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION,
    CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION,
    PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION,
    RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION,
    SUPPORTED_ACTION_FAMILY,
    CanonicalTransitionReceipt,
    CanonicalTransitionResult,
    CanonicalTransitionStatus,
    LegalActionValidationStatus,
    NewExecutionUsage,
    RecordedCanonicalObservation,
    SuccessorUnavailableReason,
)
from .ced_canonical_successor_manifest import (
    FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST,
    verify_authoritative_recorded_observation,
)
from .ced_canonical_successor_recording_contracts import (
    CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION,
    CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID,
)
from .ced_canonical_successor_recording_fixtures import (
    CANONICAL_RECORDING_AGENT_IDS,
    CANONICAL_RECORDING_PROVIDER_MODELS,
    CanonicalSuccessorRecordingProvider,
    build_canonical_recording_root,
)
from .ced_search_observability_v1 import SearchStateV1
from .ced_search_value_v1 import HeuristicValueEstimatorV1
from .provider_registry import CouncilProviderRegistry
from .providers import FakeProvider
from .socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    SearchBudget,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_PARITY_HARNESS_ID = (
    "ced-canonical-successor-parity-harness/v1"
)
CANONICAL_SUCCESSOR_PARITY_CASE_RESULT_VERSION = (
    "ced-canonical-successor-parity-case-result/v1"
)
CANONICAL_SUCCESSOR_PARITY_EVALUATION_FAILURE_VERSION = (
    "ced-canonical-successor-parity-evaluation-failure/v1"
)
CANONICAL_SUCCESSOR_UNAVAILABLE_PROBE_VERSION = (
    "ced-canonical-successor-unavailable-probe/v1"
)
CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION = (
    "ced-canonical-successor-unavailable-case-result/v1"
)
CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION = (
    "ced-canonical-successor-parity-metrics/v1"
)
CANONICAL_SUCCESSOR_PARITY_CASE_SET_VERSION = (
    "ced-canonical-successor-parity-case-set/v1"
)
CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION = (
    "ced-canonical-successor-parity-thresholds/v1"
)
CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION = (
    "ced-canonical-successor-parity-artifact/v1"
)
CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION = (
    "ced-canonical-successor-parity-replay-lock/v1"
)
CANONICAL_TRANSITION_OWNER = "backend.dialogues.ced.CEDOrchestrator"

_HEX64_PATTERN = r"^[0-9a-f]{64}$"
_SUPPORTED_CASE_COUNT = 5
_ACCEPTED_CASE_COUNT = 1
_CANONICAL_REJECTION_CASE_COUNT = 4
_UNAVAILABLE_CASE_COUNT = 14
_PRODUCTION_CONTROL_CASE_NAME = "opening-scripted-mock"
_EVALUATOR_AUDIT_TIME = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _root_branch_id(capsule_id: str) -> str:
    return stable_contract_id(
        "cedbranch",
        {
            "env_id": CANONICAL_SUCCESSOR_ENV_ID,
            "capsule_id": capsule_id,
            "parent_branch_id": None,
            "transition_id": None,
            "observation_id": None,
            "origin": "root",
        },
    )


def _successor_branch_id(
    *,
    capsule_id: str,
    root_branch_id: str,
    transition_id: str,
    observation_id: str,
) -> str:
    return stable_contract_id(
        "cedbranch",
        {
            "env_id": CANONICAL_SUCCESSOR_ENV_ID,
            "capsule_id": capsule_id,
            "parent_branch_id": root_branch_id,
            "transition_id": transition_id,
            "observation_id": observation_id,
            "origin": "successor",
        },
    )


class _FrozenEvaluationContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class UnavailableProbeStage(str, Enum):
    CAPTURE = "capture"
    PREPARE = "prepare"
    APPLY = "apply"


class ParityEvaluationFailureStage(str, Enum):
    ROOT_RECONSTRUCTION = "root_reconstruction"
    OBSERVATION_MATERIALIZATION = "observation_materialization"
    OBSERVATION_APPLICATION = "observation_application"
    EVIDENCE_EXTRACTION = "evidence_extraction"


class ParityEvaluationFailureCode(str, Enum):
    ROOT_RECONSTRUCTION_FAILED = "root_reconstruction_failed"
    ROOT_LINEAGE_MISMATCH = "root_lineage_mismatch"
    OBSERVATION_MATERIALIZATION_FAILED = "observation_materialization_failed"
    OBSERVATION_APPLICATION_FAILED = "observation_application_failed"
    EVIDENCE_EXTRACTION_FAILED = "evidence_extraction_failed"


class CanonicalSuccessorUnavailableProbe(_FrozenEvaluationContract):
    """One exact, pre-result fail-closed probe in the v1 aggregate matrix."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_UNAVAILABLE_PROBE_VERSION
    ] = CANONICAL_SUCCESSOR_UNAVAILABLE_PROBE_VERSION
    probe_id: Optional[str] = None
    case_name: str
    stage: UnavailableProbeStage
    expected_reason: SuccessorUnavailableReason

    _case_name_nonblank = field_validator("case_name")(_nonblank)

    @model_validator(mode="after")
    def identify(self) -> "CanonicalSuccessorUnavailableProbe":
        expected = stable_contract_id(
            "cedunavailableprobe",
            self.model_dump(mode="json", exclude={"probe_id"}),
        )
        if self.probe_id is not None and self.probe_id != expected:
            raise ContractValidationError("unavailable probe ID mismatch")
        object.__setattr__(self, "probe_id", expected)
        return self


FROZEN_UNAVAILABLE_PROBES = tuple(
    sorted(
        (
            CanonicalSuccessorUnavailableProbe(
                case_name="budget-exhausted",
                stage=UnavailableProbeStage.PREPARE,
                expected_reason=SuccessorUnavailableReason.BUDGET_EXHAUSTED,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="caller-rebinding",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="future-label-forbidden",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="illegal-action",
                stage=UnavailableProbeStage.PREPARE,
                expected_reason=SuccessorUnavailableReason.ILLEGAL_ACTION,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="invalid-observation",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.INVALID_OBSERVATION,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="invalid-root",
                stage=UnavailableProbeStage.CAPTURE,
                expected_reason=SuccessorUnavailableReason.INVALID_ROOT,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="missing-observation",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.MISSING_OBSERVATION,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="tampered-observation-identity",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="unsupported-action-family",
                stage=UnavailableProbeStage.PREPARE,
                expected_reason=SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="wrong-configuration",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="wrong-model",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="wrong-provider",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="wrong-root-context",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
            ),
            CanonicalSuccessorUnavailableProbe(
                case_name="wrong-task",
                stage=UnavailableProbeStage.APPLY,
                expected_reason=SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
            ),
        ),
        key=lambda item: item.case_name,
    )
)

FROZEN_SUPPORTED_CASE_ORDER = tuple(
    case.case_name
    for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
)
FROZEN_UNAVAILABLE_CASE_ORDER = tuple(
    probe.case_name for probe in FROZEN_UNAVAILABLE_PROBES
)
FROZEN_REPLAY_SUPPORTED_CASE_ORDER = tuple(reversed(FROZEN_SUPPORTED_CASE_ORDER))
FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER = tuple(
    reversed(FROZEN_UNAVAILABLE_CASE_ORDER)
)


class CanonicalSuccessorParityCaseSet(_FrozenEvaluationContract):
    """Exact supported/reference and unavailable membership frozen pre-result."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_CASE_SET_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_CASE_SET_VERSION
    case_set_id: Optional[str] = None
    case_set_fingerprint: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    supported_case_ids: Tuple[str, ...]
    reference_ids: Tuple[str, ...]
    unavailable_probes: Tuple[CanonicalSuccessorUnavailableProbe, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "CanonicalSuccessorParityCaseSet":
        supported = tuple(sorted(self.supported_case_ids))
        references = tuple(sorted(self.reference_ids))
        unavailable = tuple(
            sorted(self.unavailable_probes, key=lambda item: item.case_name)
        )
        expected_supported = tuple(
            sorted(
                case.case_id or ""
                for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
            )
        )
        expected_references = tuple(
            sorted(
                case.reference.reference_id or ""
                for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
            )
        )
        expected_unavailable = tuple(
            sorted(FROZEN_UNAVAILABLE_PROBES, key=lambda item: item.case_name)
        )
        accepted_count = sum(
            case.reference.status is CanonicalTransitionStatus.APPLIED_ACCEPTED
            for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
        )
        rejection_count = sum(
            case.reference.status
            is CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION
            for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
        )
        if (
            len(supported) != _SUPPORTED_CASE_COUNT
            or len(set(supported)) != _SUPPORTED_CASE_COUNT
            or len(references) != _SUPPORTED_CASE_COUNT
            or len(set(references)) != _SUPPORTED_CASE_COUNT
            or len(unavailable) != _UNAVAILABLE_CASE_COUNT
            or len({item.probe_id for item in unavailable}) != _UNAVAILABLE_CASE_COUNT
            or supported != expected_supported
            or references != expected_references
            or unavailable != expected_unavailable
            or accepted_count != _ACCEPTED_CASE_COUNT
            or rejection_count != _CANONICAL_REJECTION_CASE_COUNT
        ):
            raise ContractValidationError("Phase 8 v1 case-set membership changed")
        object.__setattr__(self, "supported_case_ids", supported)
        object.__setattr__(self, "reference_ids", references)
        object.__setattr__(self, "unavailable_probes", unavailable)
        identity = {
            "schema_version": self.schema_version,
            "supported_case_ids": list(supported),
            "reference_ids": list(references),
            "unavailable_probe_ids": [item.probe_id for item in unavailable],
        }
        fingerprint = _digest(identity)
        identifier = stable_contract_id("cedparitycaseset", identity)
        if self.case_set_fingerprint is not None and self.case_set_fingerprint != fingerprint:
            raise ContractValidationError("case-set fingerprint mismatch")
        if self.case_set_id is not None and self.case_set_id != identifier:
            raise ContractValidationError("case-set ID mismatch")
        object.__setattr__(self, "case_set_fingerprint", fingerprint)
        object.__setattr__(self, "case_set_id", identifier)
        return self


FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET = CanonicalSuccessorParityCaseSet(
    supported_case_ids=tuple(
        case.case_id or ""
        for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
    ),
    reference_ids=tuple(
        case.reference.reference_id or ""
        for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
    ),
    unavailable_probes=FROZEN_UNAVAILABLE_PROBES,
)


class CanonicalSuccessorParityMetrics(_FrozenEvaluationContract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION
    cases_total: int = Field(ge=0, strict=True)
    supported_authoritative_cases: int = Field(ge=0, strict=True)
    accepted_reference_cases: int = Field(ge=0, strict=True)
    canonical_rejection_reference_cases: int = Field(ge=0, strict=True)
    unavailable_negative_cases: int = Field(ge=0, strict=True)
    accepted_parity: int = Field(ge=0, strict=True)
    canonical_rejection_parity: int = Field(ge=0, strict=True)
    unavailable_passed: int = Field(ge=0, strict=True)
    evaluation_failures: int = Field(ge=0, strict=True)
    unavailable_reason_mismatches: int = Field(ge=0, strict=True)
    status_mismatches: int = Field(ge=0, strict=True)
    canonical_rejection_reason_mismatches: int = Field(ge=0, strict=True)
    semantic_mismatches: int = Field(ge=0, strict=True)
    accepted_move_id_mismatches: int = Field(ge=0, strict=True)
    task_log_mismatches: int = Field(ge=0, strict=True)
    commitment_mismatches: int = Field(ge=0, strict=True)
    phase_role_mismatches: int = Field(ge=0, strict=True)
    search_state_v1_mismatches: int = Field(ge=0, strict=True)
    canonical_processor_mismatches: int = Field(ge=0, strict=True)
    observation_identity_mismatches: int = Field(ge=0, strict=True)
    context_binding_failures: int = Field(ge=0, strict=True)
    task_binding_failures: int = Field(ge=0, strict=True)
    provider_binding_failures: int = Field(ge=0, strict=True)
    model_binding_failures: int = Field(ge=0, strict=True)
    configuration_binding_failures: int = Field(ge=0, strict=True)
    source_isolation_failures: int = Field(ge=0, strict=True)
    sibling_isolation_failures: int = Field(ge=0, strict=True)
    production_mutations: int = Field(ge=0, strict=True)
    receipt_mismatches: int = Field(ge=0, strict=True)
    resource_accounting_mismatches: int = Field(ge=0, strict=True)
    value_v1_compatibility_mismatches: int = Field(ge=0, strict=True)
    idempotence_failures: int = Field(ge=0, strict=True)
    fabricated_observations: int = Field(ge=0, strict=True)
    future_label_violations: int = Field(ge=0, strict=True)
    historical_offline_fixture_dispatches: int = Field(ge=0, strict=True)
    aggregate_provider_dispatches: int = Field(ge=0, strict=True)
    live_calls: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)


class CanonicalSuccessorParityThresholds(_FrozenEvaluationContract):
    """Exact success/falsification boundary fixed before aggregate execution."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION
    thresholds_id: Optional[str] = None
    cases_total: Literal[19] = 19
    supported_authoritative_cases: Literal[5] = 5
    accepted_reference_cases: Literal[1] = 1
    canonical_rejection_reference_cases: Literal[4] = 4
    unavailable_negative_cases: Literal[14] = 14
    required_supported_parity_numerator: Literal[5] = 5
    required_supported_parity_denominator: Literal[5] = 5
    required_unavailable_passed: Literal[14] = 14
    required_historical_offline_fixture_dispatches: Literal[5] = 5
    maximum_evaluation_failures: Literal[0] = 0
    maximum_mismatch_or_failure_count: Literal[0] = 0
    required_aggregate_provider_dispatches: Literal[0] = 0
    required_live_calls: Literal[0] = 0
    required_tool_calls: Literal[0] = 0
    depth: Literal[1] = 1
    recursive_successor: Literal[False] = False

    @model_validator(mode="after")
    def identify(self) -> "CanonicalSuccessorParityThresholds":
        expected = stable_contract_id(
            "cedparitythresholds",
            self.model_dump(mode="json", exclude={"thresholds_id"}),
        )
        if self.thresholds_id is not None and self.thresholds_id != expected:
            raise ContractValidationError("parity thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self

    def supports(self, metrics: CanonicalSuccessorParityMetrics) -> bool:
        mismatches = (
            metrics.evaluation_failures,
            metrics.unavailable_reason_mismatches,
            metrics.status_mismatches,
            metrics.canonical_rejection_reason_mismatches,
            metrics.semantic_mismatches,
            metrics.accepted_move_id_mismatches,
            metrics.task_log_mismatches,
            metrics.commitment_mismatches,
            metrics.phase_role_mismatches,
            metrics.search_state_v1_mismatches,
            metrics.canonical_processor_mismatches,
            metrics.observation_identity_mismatches,
            metrics.context_binding_failures,
            metrics.task_binding_failures,
            metrics.provider_binding_failures,
            metrics.model_binding_failures,
            metrics.configuration_binding_failures,
            metrics.source_isolation_failures,
            metrics.sibling_isolation_failures,
            metrics.production_mutations,
            metrics.receipt_mismatches,
            metrics.resource_accounting_mismatches,
            metrics.value_v1_compatibility_mismatches,
            metrics.idempotence_failures,
            metrics.fabricated_observations,
            metrics.future_label_violations,
            metrics.aggregate_provider_dispatches,
            metrics.live_calls,
            metrics.tool_calls,
        )
        return all(
            (
                metrics.cases_total == self.cases_total,
                metrics.supported_authoritative_cases == self.supported_authoritative_cases,
                metrics.accepted_reference_cases == self.accepted_reference_cases,
                metrics.canonical_rejection_reference_cases
                == self.canonical_rejection_reference_cases,
                metrics.unavailable_negative_cases == self.unavailable_negative_cases,
                metrics.accepted_parity == self.accepted_reference_cases,
                metrics.canonical_rejection_parity
                == self.canonical_rejection_reference_cases,
                metrics.unavailable_passed == self.required_unavailable_passed,
                metrics.historical_offline_fixture_dispatches
                == self.required_historical_offline_fixture_dispatches,
                metrics.evaluation_failures == self.maximum_evaluation_failures,
                not any(mismatches),
            )
        )


FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS = CanonicalSuccessorParityThresholds()


class CanonicalSuccessorParityCaseResult(_FrozenEvaluationContract):
    """Auditable replay evidence for one authoritative v1 corpus case."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_CASE_RESULT_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_CASE_RESULT_VERSION
    case_result_id: Optional[str] = None
    case_id: str
    case_name: str
    fixture_role: RecordedObservationFixtureRole
    reference_id: str
    capture_receipt_id: str
    observation_id: str
    transition_id: str
    result_id: str
    receipt: CanonicalTransitionReceipt
    successor_capsule_id: Optional[str] = None
    successor_branch_id: Optional[str] = None
    successor_semantic_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    successor_search_state_v1: Optional[SearchStateV1] = None
    successor_search_state_v1_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    parity_field_digests: Tuple[CanonicalSuccessorReferenceField, ...] = ()
    source_capsule_id: str
    source_branch_id: str
    source_state_v1_id: str
    source_isolation_evidence_digest: str = Field(pattern=_HEX64_PATTERN)
    source_runtime_fingerprint_before: str = Field(pattern=_HEX64_PATTERN)
    source_runtime_fingerprint_after: str = Field(pattern=_HEX64_PATTERN)
    source_provider_dispatches_before: int = Field(ge=0, strict=True)
    source_provider_dispatches_after: int = Field(ge=0, strict=True)
    sibling_result_digest_before: str = Field(pattern=_HEX64_PATTERN)
    sibling_result_digest_after: str = Field(pattern=_HEX64_PATTERN)
    sibling_probe_observation_id: str
    sibling_probe_status: CanonicalTransitionStatus
    sibling_probe_unavailable_reason: Optional[SuccessorUnavailableReason] = None
    sibling_probe_result_id: str
    sibling_probe_receipt_id: str
    sibling_probe_outcome_digest: str = Field(pattern=_HEX64_PATTERN)
    sibling_probe_successor_created: bool
    sibling_isolation_evidence_digest: str = Field(pattern=_HEX64_PATTERN)
    primary_result_digest: str = Field(pattern=_HEX64_PATTERN)
    replay_result_digest: str = Field(pattern=_HEX64_PATTERN)
    replay_result_id: str
    replay_receipt_id: str
    production_control_capsule_id: str
    production_isolation_evidence_digest: str = Field(pattern=_HEX64_PATTERN)
    production_runtime_fingerprint_before: str = Field(pattern=_HEX64_PATTERN)
    production_runtime_fingerprint_after: str = Field(pattern=_HEX64_PATTERN)
    production_provider_dispatches_before: int = Field(ge=0, strict=True)
    production_provider_dispatches_after: int = Field(ge=0, strict=True)
    successor_created: bool
    status_parity: bool
    canonical_rejection_reason_parity: bool
    semantic_parity: bool
    search_state_v1_parity: bool
    move_id_parity: bool
    canonical_processor_parity: bool
    observation_identity_match: bool
    receipt_match: bool
    resource_accounting_match: bool
    source_unchanged: bool
    sibling_unchanged: bool
    production_unchanged: bool
    idempotent_replay: bool
    value_v1_read_only_compatible: bool
    value_v1_receipt_hash: str = Field(pattern=_HEX64_PATTERN)
    aggregate_provider_dispatches: int = Field(ge=0, strict=True)
    live_calls: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_evidence_and_identify(self) -> "CanonicalSuccessorParityCaseResult":
        try:
            case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(self.case_name)
        except KeyError as exc:
            raise ContractValidationError("unknown authoritative parity case") from exc
        reference = case.reference
        observation = case.observation
        capture = case.manifest_entry.capture_receipt
        if (
            self.case_id != case.case_id
            or self.fixture_role is not case.fixture_role
            or self.reference_id != reference.reference_id
            or self.capture_receipt_id != reference.capture_receipt_id
            or self.observation_id != observation.observation_id
        ):
            raise ContractValidationError("parity result changed frozen case lineage")
        fields = tuple(sorted(self.parity_field_digests, key=lambda item: item.name))
        applied = self.receipt.status in (
            CanonicalTransitionStatus.APPLIED_ACCEPTED,
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        )
        successor_values = (
            self.successor_capsule_id,
            self.successor_branch_id,
            self.successor_semantic_digest,
            self.successor_search_state_v1,
            self.successor_search_state_v1_digest,
        )
        if applied:
            if not all(value is not None for value in successor_values):
                raise ContractValidationError(
                    "applied parity evidence requires a complete successor"
                )
            if tuple(item.name for item in fields) != FROZEN_PARITY_FIELD_NAMES:
                raise ContractValidationError("parity result field set changed")
        elif any(value is not None for value in successor_values) or fields:
            raise ContractValidationError(
                "successor-unavailable parity evidence cannot invent a successor"
            )
        object.__setattr__(self, "parity_field_digests", fields)
        projected = self.successor_search_state_v1
        search_digest = (
            _digest(projected.model_dump(mode="json"))
            if projected is not None
            else None
        )
        if self.successor_search_state_v1_digest != search_digest:
            raise ContractValidationError("result SearchState-v1 digest mismatch")
        expected_root_branch_id = _root_branch_id(reference.source_capsule_id)
        if (
            self.source_capsule_id != reference.source_capsule_id
            or self.source_branch_id != expected_root_branch_id
            or self.source_state_v1_id != capture.source_search_state_v1_id
        ):
            raise ContractValidationError("parity source identity changed")
        if applied:
            assert self.successor_capsule_id is not None
            assert self.successor_branch_id is not None
            assert self.successor_semantic_digest is not None
            assert projected is not None
            expected_successor_branch_id = _successor_branch_id(
                capsule_id=self.successor_capsule_id,
                root_branch_id=expected_root_branch_id,
                transition_id=self.transition_id,
                observation_id=observation.observation_id or "",
            )
            if self.successor_branch_id != expected_successor_branch_id:
                raise ContractValidationError("successor branch lineage changed")
        expected_result_id = stable_contract_id(
            "cedresult",
            {
                "schema_version": CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION,
                "env_id": CANONICAL_SUCCESSOR_ENV_ID,
                "transition_id": self.transition_id,
                "status": self.receipt.status.value,
                "receipt_id": self.receipt.receipt_id,
                "successor_capsule_id": self.successor_capsule_id,
                "successor_branch_id": self.successor_branch_id,
                "successor_state_v1_id": (
                    projected.state_id if projected is not None else None
                ),
            },
        )
        if self.result_id != expected_result_id:
            raise ContractValidationError("parity result identity is not linked")
        source_unchanged = all(
            (
                self.source_runtime_fingerprint_before
                == self.source_runtime_fingerprint_after,
                self.source_provider_dispatches_before == 0,
                self.source_provider_dispatches_after == 0,
            )
        )
        expected_source_evidence = _digest(
            {
                "source_capsule_id": self.source_capsule_id,
                "source_branch_id": self.source_branch_id,
                "source_state_v1_id": self.source_state_v1_id,
                "runtime_fingerprint_before": self.source_runtime_fingerprint_before,
                "runtime_fingerprint_after": self.source_runtime_fingerprint_after,
                "provider_dispatches_before": self.source_provider_dispatches_before,
                "provider_dispatches_after": self.source_provider_dispatches_after,
            }
        )
        if self.source_isolation_evidence_digest != expected_source_evidence:
            raise ContractValidationError("source isolation evidence digest mismatch")
        production_unchanged = all(
            (
                self.production_runtime_fingerprint_before
                == self.production_runtime_fingerprint_after,
                self.production_provider_dispatches_before == 0,
                self.production_provider_dispatches_after == 0,
            )
        )
        expected_production_evidence = _digest(
            {
                "control_capsule_id": self.production_control_capsule_id,
                "runtime_fingerprint_before": (
                    self.production_runtime_fingerprint_before
                ),
                "runtime_fingerprint_after": (
                    self.production_runtime_fingerprint_after
                ),
                "provider_dispatches_before": (
                    self.production_provider_dispatches_before
                ),
                "provider_dispatches_after": (
                    self.production_provider_dispatches_after
                ),
            }
        )
        if self.production_isolation_evidence_digest != expected_production_evidence:
            raise ContractValidationError(
                "production isolation evidence digest mismatch"
            )
        sibling_unchanged = all(
            (
                self.sibling_result_digest_before
                == self.sibling_result_digest_after,
                self.sibling_probe_observation_id != observation.observation_id,
                self.sibling_probe_status
                is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
                self.sibling_probe_unavailable_reason
                is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
                not self.sibling_probe_successor_created,
            )
        )
        expected_sibling_evidence = _digest(
            {
                "primary_before": self.sibling_result_digest_before,
                "primary_after": self.sibling_result_digest_after,
                "probe_observation_id": self.sibling_probe_observation_id,
                "probe_status": self.sibling_probe_status.value,
                "probe_unavailable_reason": (
                    self.sibling_probe_unavailable_reason.value
                    if self.sibling_probe_unavailable_reason is not None
                    else None
                ),
                "probe_result_id": self.sibling_probe_result_id,
                "probe_receipt_id": self.sibling_probe_receipt_id,
                "probe_outcome_digest": self.sibling_probe_outcome_digest,
                "probe_successor_created": self.sibling_probe_successor_created,
            }
        )
        if self.sibling_isolation_evidence_digest != expected_sibling_evidence:
            raise ContractValidationError("sibling isolation evidence digest mismatch")
        idempotent_replay = all(
            (
                self.primary_result_digest == self.replay_result_digest,
                self.result_id == self.replay_result_id,
                self.receipt.receipt_id == self.replay_receipt_id,
            )
        )
        expected_flags = {
            "status_parity": self.receipt.status is reference.status,
            "canonical_rejection_reason_parity": (
                self.receipt.canonical_rejection_reason is reference.canonical_rejection_reason
            ),
            "semantic_parity": (
                applied
                and self.successor_semantic_digest
                == reference.successor_semantic_digest
                and self.field_parity("normalized_semantics")
            ),
            "search_state_v1_parity": (
                projected is not None
                and projected.state_id == reference.successor_search_state_v1_id
                and search_digest == reference.successor_search_state_v1_digest
                and self.field_parity("search_state_v1")
            ),
            "move_id_parity": self.receipt.resulting_move_id == reference.accepted_move_id,
            "canonical_processor_parity": (
                tuple(self.receipt.canonical_processor_ids)
                == tuple(sorted(reference.canonical_processor_ids))
            ),
            "observation_identity_match": all(
                (
                    verify_authoritative_recorded_observation(observation),
                    self.receipt.observation_id == observation.observation_id,
                    self.receipt.observation_digest == observation.raw_output_digest,
                )
            ),
            "receipt_match": self._receipt_matches_reference(case),
            "resource_accounting_match": self._resource_accounting_matches(case),
            "source_unchanged": source_unchanged,
            "sibling_unchanged": sibling_unchanged,
            "production_unchanged": production_unchanged,
            "idempotent_replay": idempotent_replay,
            "successor_created": applied,
        }
        for name, expected in expected_flags.items():
            if getattr(self, name) is not expected:
                raise ContractValidationError(f"inconsistent parity evidence: {name}")
        if projected is not None:
            value_ok, value_hash = _value_v1_compatibility(projected)
        else:
            value_ok, value_hash = False, _digest({"value_v1": "unavailable"})
        if (
            self.value_v1_read_only_compatible is not value_ok
            or self.value_v1_receipt_hash != value_hash
        ):
            raise ContractValidationError("Value-v1 compatibility evidence mismatch")
        expected_id = stable_contract_id(
            "cedparitycasev1",
            self.model_dump(mode="json", exclude={"case_result_id"}),
        )
        if self.case_result_id is not None and self.case_result_id != expected_id:
            raise ContractValidationError("parity case result ID mismatch")
        object.__setattr__(self, "case_result_id", expected_id)
        return self

    def field_digest(self, name: str) -> str:
        try:
            return next(
                item.semantic_digest
                for item in self.parity_field_digests
                if item.name == name
            )
        except StopIteration as exc:
            raise KeyError(name) from exc

    def field_parity(self, name: str) -> bool:
        case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(self.case_name)
        try:
            actual = self.field_digest(name)
        except KeyError:
            return False
        return actual == case.reference.field_digest(name)

    def _receipt_matches_reference(self, case: AuthoritativeRecordedObservationCase) -> bool:
        reference = case.reference
        observation = case.observation
        receipt = self.receipt
        capture = case.manifest_entry.capture_receipt
        projected = self.successor_search_state_v1
        if projected is None:
            return False
        return all(
            (
                receipt.transition_id == self.transition_id,
                receipt.root_capsule_id == reference.source_capsule_id,
                receipt.root_branch_id == self.source_branch_id,
                receipt.root_state_v1_id == capture.source_search_state_v1_id,
                receipt.branch_id == self.successor_branch_id,
                receipt.action_id == reference.action_id,
                receipt.observation_id == observation.observation_id,
                receipt.observation_digest == observation.raw_output_digest,
                receipt.status is reference.status,
                receipt.canonical_rejection_reason is reference.canonical_rejection_reason,
                receipt.resulting_move_id == reference.accepted_move_id,
                receipt.source_state_hash == reference.source_normalized_semantic_digest,
                receipt.successor_state_hash == self.successor_semantic_digest,
                receipt.successor_state_v1_id == projected.state_id,
                tuple(receipt.canonical_processor_ids)
                == tuple(sorted(CANONICAL_PROCESSOR_IDS)),
                receipt.budget == projected.base_state.budget,
                receipt.budget_before == BudgetUsage(nodes=1),
                receipt.budget_after == projected.base_state.budget_usage,
                receipt.legal_action_validation
                is LegalActionValidationStatus.PASSED,
                receipt.unavailable_reason is None,
                receipt.receipt_id is not None,
                self.result_id is not None,
            )
        )

    def _resource_accounting_matches(self, case: AuthoritativeRecordedObservationCase) -> bool:
        receipt = self.receipt
        projected = self.successor_search_state_v1
        if projected is None:
            return False
        expected = NewExecutionUsage()
        return all(
            (
                receipt.new_execution_usage == expected,
                receipt.budget_after == receipt.budget_before.plus(expected.budget_delta),
                expected.budget_delta.model_calls == 0,
                expected.budget_delta.tool_calls == 0,
                expected.budget_delta.tokens == 0,
                expected.budget_delta.cost_microusd == 0,
                expected.budget_delta.wall_time_ms == 0,
                receipt.recorded_historical_usage == case.observation.historical_usage,
                receipt.budget == projected.base_state.budget,
                receipt.budget_after == projected.base_state.budget_usage,
            )
        )

    @property
    def parity_passed(self) -> bool:
        return all(
            (
                self.status_parity,
                self.canonical_rejection_reason_parity,
                self.semantic_parity,
                self.search_state_v1_parity,
                self.move_id_parity,
                self.canonical_processor_parity,
                self.observation_identity_match,
                self.receipt_match,
                self.resource_accounting_match,
                self.source_unchanged,
                self.sibling_unchanged,
                self.production_unchanged,
                self.idempotent_replay,
                self.successor_created,
                self.value_v1_read_only_compatible,
                all(self.field_parity(name) for name in FROZEN_PARITY_FIELD_NAMES),
            )
        )


class CanonicalSuccessorParityEvaluationFailure(_FrozenEvaluationContract):
    """Deterministic evaluator-side evidence for one failed supported case.

    This record carries no synthetic transition receipt or successor.  Missing
    evidence is explicit and is conservatively counted as a mismatch by the
    aggregate metrics rather than being interpreted as a zero or a pass.
    """

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_EVALUATION_FAILURE_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_EVALUATION_FAILURE_VERSION
    case_result_id: Optional[str] = None
    failure_evidence_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    case_id: str
    case_name: str
    fixture_role: RecordedObservationFixtureRole
    reference_id: str
    capture_receipt_id: str
    observation_id: str
    stage: ParityEvaluationFailureStage
    failure_code: ParityEvaluationFailureCode
    exception_type: str
    source_capsule_id: Optional[str] = None
    source_branch_id: Optional[str] = None
    source_state_v1_id: Optional[str] = None
    source_runtime_fingerprint_before: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    source_runtime_fingerprint_after: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    source_provider_dispatches_before: int = Field(default=0, ge=0, strict=True)
    source_provider_dispatches_after: int = Field(default=0, ge=0, strict=True)
    production_control_capsule_id: Optional[str] = None
    production_runtime_fingerprint_before: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    production_runtime_fingerprint_after: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    production_provider_dispatches_before: int = Field(
        default=0, ge=0, strict=True
    )
    production_provider_dispatches_after: int = Field(
        default=0, ge=0, strict=True
    )
    successor_created: bool = False
    aggregate_provider_dispatches: int = Field(default=0, ge=0, strict=True)
    live_calls: int = Field(default=0, ge=0, strict=True)
    tool_calls: int = Field(default=0, ge=0, strict=True)
    parity_passed: Literal[False] = False

    _exception_type_nonblank = field_validator("exception_type")(_nonblank)

    @model_validator(mode="after")
    def validate_evidence_and_identify(
        self,
    ) -> "CanonicalSuccessorParityEvaluationFailure":
        try:
            case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
                self.case_name
            )
        except KeyError as exc:
            raise ContractValidationError("unknown failed parity case") from exc
        if (
            self.case_id != case.case_id
            or self.fixture_role is not case.fixture_role
            or self.reference_id != case.reference.reference_id
            or self.capture_receipt_id != case.reference.capture_receipt_id
            or self.observation_id != case.observation.observation_id
        ):
            raise ContractValidationError("failure record changed frozen case lineage")
        allowed_codes = {
            ParityEvaluationFailureStage.ROOT_RECONSTRUCTION: {
                ParityEvaluationFailureCode.ROOT_RECONSTRUCTION_FAILED,
                ParityEvaluationFailureCode.ROOT_LINEAGE_MISMATCH,
            },
            ParityEvaluationFailureStage.OBSERVATION_MATERIALIZATION: {
                ParityEvaluationFailureCode.OBSERVATION_MATERIALIZATION_FAILED,
            },
            ParityEvaluationFailureStage.OBSERVATION_APPLICATION: {
                ParityEvaluationFailureCode.OBSERVATION_APPLICATION_FAILED,
            },
            ParityEvaluationFailureStage.EVIDENCE_EXTRACTION: {
                ParityEvaluationFailureCode.EVIDENCE_EXTRACTION_FAILED,
            },
        }
        if self.failure_code not in allowed_codes[self.stage]:
            raise ContractValidationError("failure code does not match its stage")
        source_identity = (
            self.source_capsule_id,
            self.source_branch_id,
            self.source_state_v1_id,
        )
        if any(value is not None for value in source_identity) and not all(
            value is not None for value in source_identity
        ):
            raise ContractValidationError("partial source identity in failure record")
        expected_dispatches = (
            self.source_provider_dispatches_after
            + self.production_provider_dispatches_after
        )
        if self.aggregate_provider_dispatches != expected_dispatches:
            raise ContractValidationError("failure dispatch accounting mismatch")
        evidence_payload = self.model_dump(
            mode="json",
            exclude={"case_result_id", "failure_evidence_digest"},
        )
        evidence_digest = _digest(evidence_payload)
        if (
            self.failure_evidence_digest is not None
            and self.failure_evidence_digest != evidence_digest
        ):
            raise ContractValidationError("failure evidence digest mismatch")
        object.__setattr__(self, "failure_evidence_digest", evidence_digest)
        expected_id = stable_contract_id(
            "cedparityfailurev1",
            {
                **evidence_payload,
                "failure_evidence_digest": evidence_digest,
            },
        )
        if self.case_result_id is not None and self.case_result_id != expected_id:
            raise ContractValidationError("failure case-result ID mismatch")
        object.__setattr__(self, "case_result_id", expected_id)
        return self

    @property
    def source_unchanged(self) -> bool:
        return all(
            (
                self.source_runtime_fingerprint_before is not None,
                self.source_runtime_fingerprint_before
                == self.source_runtime_fingerprint_after,
                self.source_provider_dispatches_before == 0,
                self.source_provider_dispatches_after == 0,
            )
        )

    @property
    def production_unchanged(self) -> bool:
        return all(
            (
                self.production_runtime_fingerprint_before is not None,
                self.production_runtime_fingerprint_before
                == self.production_runtime_fingerprint_after,
                self.production_provider_dispatches_before == 0,
                self.production_provider_dispatches_after == 0,
            )
        )


CanonicalSuccessorParityEvidence = Union[
    CanonicalSuccessorParityCaseResult,
    CanonicalSuccessorParityEvaluationFailure,
]


class CanonicalSuccessorUnavailableCaseResult(_FrozenEvaluationContract):
    """One deterministic no-successor result from the frozen negative matrix."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION
    ] = CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION
    case_result_id: Optional[str] = None
    probe_id: str
    case_name: str
    stage: UnavailableProbeStage
    expected_reason: SuccessorUnavailableReason
    actual_reason: Optional[SuccessorUnavailableReason] = None
    actual_status: Optional[CanonicalTransitionStatus] = None
    replay_reason: Optional[SuccessorUnavailableReason] = None
    replay_status: Optional[CanonicalTransitionStatus] = None
    transition_id: Optional[str] = None
    result_id: Optional[str] = None
    receipt: Optional[CanonicalTransitionReceipt] = None
    replay_result_id: Optional[str] = None
    replay_receipt_id: Optional[str] = None
    successor_capsule_id: Optional[str] = None
    successor_branch_id: Optional[str] = None
    successor_state_v1_id: Optional[str] = None
    primary_outcome_digest: str = Field(pattern=_HEX64_PATTERN)
    replay_outcome_digest: str = Field(pattern=_HEX64_PATTERN)
    source_capsule_id: str
    source_branch_id: str
    source_state_v1_id: str
    source_isolation_evidence_digest: str = Field(pattern=_HEX64_PATTERN)
    source_runtime_fingerprint_before: str = Field(pattern=_HEX64_PATTERN)
    source_runtime_fingerprint_after: str = Field(pattern=_HEX64_PATTERN)
    source_provider_dispatches_before: int = Field(ge=0, strict=True)
    source_provider_dispatches_after: int = Field(ge=0, strict=True)
    production_control_capsule_id: str
    production_isolation_evidence_digest: str = Field(pattern=_HEX64_PATTERN)
    production_runtime_fingerprint_before: str = Field(pattern=_HEX64_PATTERN)
    production_runtime_fingerprint_after: str = Field(pattern=_HEX64_PATTERN)
    production_provider_dispatches_before: int = Field(ge=0, strict=True)
    production_provider_dispatches_after: int = Field(ge=0, strict=True)
    reason_match: bool
    replay_match: bool
    source_unchanged: bool
    production_unchanged: bool
    receipt_match: bool
    resource_accounting_match: bool
    successor_created: bool
    aggregate_provider_dispatches: int = Field(ge=0, strict=True)
    live_calls: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_evidence_and_identify(self) -> "CanonicalSuccessorUnavailableCaseResult":
        try:
            probe = next(
                item for item in FROZEN_UNAVAILABLE_PROBES if item.case_name == self.case_name
            )
        except StopIteration as exc:
            raise ContractValidationError("unknown unavailable probe") from exc
        if (
            self.probe_id != probe.probe_id
            or self.stage is not probe.stage
            or self.expected_reason is not probe.expected_reason
        ):
            raise ContractValidationError("unavailable result changed frozen probe")
        expected_reason_match = self.actual_reason is self.expected_reason
        expected_replay = all(
            (
                self.primary_outcome_digest == self.replay_outcome_digest,
                self.actual_reason is self.replay_reason,
                self.actual_status is self.replay_status,
                self.result_id == self.replay_result_id,
                (
                    self.receipt.receipt_id if self.receipt is not None else None
                )
                == self.replay_receipt_id,
            )
        )
        expected_root_branch = _root_branch_id(self.source_capsule_id)
        if self.source_branch_id != expected_root_branch:
            raise ContractValidationError("negative source branch identity changed")
        expected_source = all(
            (
                self.source_runtime_fingerprint_before
                == self.source_runtime_fingerprint_after,
                self.source_provider_dispatches_before == 0,
                self.source_provider_dispatches_after == 0,
            )
        )
        source_evidence = _digest(
            {
                "source_capsule_id": self.source_capsule_id,
                "source_branch_id": self.source_branch_id,
                "source_state_v1_id": self.source_state_v1_id,
                "runtime_fingerprint_before": self.source_runtime_fingerprint_before,
                "runtime_fingerprint_after": self.source_runtime_fingerprint_after,
                "provider_dispatches_before": self.source_provider_dispatches_before,
                "provider_dispatches_after": self.source_provider_dispatches_after,
            }
        )
        if self.source_isolation_evidence_digest != source_evidence:
            raise ContractValidationError("negative source evidence digest mismatch")
        expected_production = all(
            (
                self.production_runtime_fingerprint_before
                == self.production_runtime_fingerprint_after,
                self.production_provider_dispatches_before == 0,
                self.production_provider_dispatches_after == 0,
            )
        )
        production_evidence = _digest(
            {
                "control_capsule_id": self.production_control_capsule_id,
                "runtime_fingerprint_before": (
                    self.production_runtime_fingerprint_before
                ),
                "runtime_fingerprint_after": (
                    self.production_runtime_fingerprint_after
                ),
                "provider_dispatches_before": (
                    self.production_provider_dispatches_before
                ),
                "provider_dispatches_after": (
                    self.production_provider_dispatches_after
                ),
            }
        )
        if self.production_isolation_evidence_digest != production_evidence:
            raise ContractValidationError(
                "negative production evidence digest mismatch"
            )
        successor_values = (
            self.successor_capsule_id,
            self.successor_branch_id,
            self.successor_state_v1_id,
        )
        successor_created = self.actual_status in (
            CanonicalTransitionStatus.APPLIED_ACCEPTED,
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        )
        if successor_created != all(value is not None for value in successor_values):
            raise ContractValidationError("negative successor evidence is incomplete")
        if not successor_created and any(value is not None for value in successor_values):
            raise ContractValidationError("negative probe invented successor identity")
        if self.receipt is None:
            receipt_match = all(
                (
                    self.actual_status is None,
                    self.transition_id is None,
                    self.result_id is None,
                    not successor_created,
                )
            )
            resource_match = receipt_match
        else:
            if self.actual_status is None or self.transition_id is None:
                raise ContractValidationError("negative result linkage is incomplete")
            expected_result_id = stable_contract_id(
                "cedresult",
                {
                    "schema_version": CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION,
                    "env_id": CANONICAL_SUCCESSOR_ENV_ID,
                    "transition_id": self.transition_id,
                    "status": self.actual_status.value,
                    "receipt_id": self.receipt.receipt_id,
                    "successor_capsule_id": self.successor_capsule_id,
                    "successor_branch_id": self.successor_branch_id,
                    "successor_state_v1_id": self.successor_state_v1_id,
                },
            )
            if self.result_id != expected_result_id:
                raise ContractValidationError("negative result identity is not linked")
            receipt_match = all(
                (
                    self.receipt.transition_id == self.transition_id,
                    self.receipt.root_capsule_id == self.source_capsule_id,
                    self.receipt.root_branch_id == self.source_branch_id,
                    self.receipt.root_state_v1_id == self.source_state_v1_id,
                    self.receipt.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
                    self.receipt.unavailable_reason is self.actual_reason,
                    self.receipt.successor_state_hash is None,
                    self.receipt.successor_state_v1_id is None,
                    self.receipt.branch_id is None,
                    self.receipt.receipt_id is not None,
                    not successor_created,
                )
            )
            resource_match = all(
                (
                    self.receipt.new_execution_usage == NewExecutionUsage.not_applied(),
                    self.receipt.budget_after == self.receipt.budget_before,
                )
            )
        expected_flags = {
            "reason_match": expected_reason_match,
            "replay_match": expected_replay,
            "source_unchanged": expected_source,
            "production_unchanged": expected_production,
            "receipt_match": receipt_match,
            "resource_accounting_match": resource_match,
            "successor_created": successor_created,
        }
        for name, expected in expected_flags.items():
            if getattr(self, name) is not expected:
                raise ContractValidationError(f"inconsistent unavailable evidence: {name}")
        expected_id = stable_contract_id(
            "cedunavailablecasev1",
            self.model_dump(mode="json", exclude={"case_result_id"}),
        )
        if self.case_result_id is not None and self.case_result_id != expected_id:
            raise ContractValidationError("unavailable case result ID mismatch")
        object.__setattr__(self, "case_result_id", expected_id)
        return self

    @property
    def unavailable_passed(self) -> bool:
        return all(
            (
                self.reason_match,
                self.replay_match,
                self.source_unchanged,
                self.production_unchanged,
                self.receipt_match,
                self.resource_accounting_match,
                not self.successor_created,
            )
        )


class CanonicalSuccessorParityArtifact(_FrozenEvaluationContract):
    """Canonical, timestamp-free Phase 8 v1 machine-readable evidence."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION
    artifact_id: Optional[str] = None
    harness_id: Literal[
        CANONICAL_SUCCESSOR_PARITY_HARNESS_ID
    ] = CANONICAL_SUCCESSOR_PARITY_HARNESS_ID
    environment_id: Literal[CANONICAL_SUCCESSOR_ENV_ID] = CANONICAL_SUCCESSOR_ENV_ID
    branch_capsule_id: Literal[
        CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION
    ] = CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION
    pending_transition_id: Literal[
        PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION
    ] = PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION
    recording_contract_id: Literal[
        CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID
    ] = CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID
    capture_manifest_schema_id: Literal[
        CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION
    capture_manifest_id: str
    task_semantic_identity_id: Literal[
        CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION
    ] = CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION
    recorded_observation_id: Literal[
        RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
    ] = RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
    reference_schema_id: Literal[
        CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION
    transition_result_id: Literal[
        CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION
    ] = CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION
    transition_receipt_id: Literal[
        CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION
    ] = CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION
    parity_definition_id: Literal[
        CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID
    ] = CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID
    supported_action_family: Literal[SUPPORTED_ACTION_FAMILY] = SUPPORTED_ACTION_FAMILY
    canonical_transition_owner: Literal[
        CANONICAL_TRANSITION_OWNER
    ] = CANONICAL_TRANSITION_OWNER
    canonical_processor_ids: Tuple[str, ...] = CANONICAL_PROCESSOR_IDS
    corpus_version: Literal[
        CANONICAL_SUCCESSOR_CORPUS_VERSION
    ] = CANONICAL_SUCCESSOR_CORPUS_VERSION
    corpus_id: str
    corpus_canonical_sha256: str = Field(pattern=_HEX64_PATTERN)
    case_set_id: str
    case_set_fingerprint: str = Field(pattern=_HEX64_PATTERN)
    thresholds_id: str
    case_set: CanonicalSuccessorParityCaseSet
    thresholds: CanonicalSuccessorParityThresholds
    parity_cases: Tuple[CanonicalSuccessorParityEvidence, ...]
    unavailable_cases: Tuple[CanonicalSuccessorUnavailableCaseResult, ...]
    metrics: CanonicalSuccessorParityMetrics
    depth: Literal[1] = 1
    recursive_successor: Literal[False] = False
    production_authority: Literal["none"] = "none"
    hypothesis_status: Literal["SUPPORTED", "FALSIFIED"]

    @model_validator(mode="after")
    def validate_evidence_and_identify(self) -> "CanonicalSuccessorParityArtifact":
        parity = tuple(sorted(self.parity_cases, key=lambda item: item.case_name))
        unavailable = tuple(sorted(self.unavailable_cases, key=lambda item: item.case_name))
        object.__setattr__(self, "parity_cases", parity)
        object.__setattr__(self, "unavailable_cases", unavailable)
        corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
        if (
            self.capture_manifest_id != FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.manifest_id
            or self.corpus_id != corpus.corpus_id
            or self.corpus_canonical_sha256 != frozen_corpus_v1_canonical_sha256()
            or self.case_set != FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET
            or self.case_set_id != self.case_set.case_set_id
            or self.case_set_fingerprint != self.case_set.case_set_fingerprint
            or self.thresholds != FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS
            or self.thresholds_id != self.thresholds.thresholds_id
            or tuple(self.canonical_processor_ids) != tuple(sorted(CANONICAL_PROCESSOR_IDS))
        ):
            raise ContractValidationError("artifact frozen lineage changed")
        if (
            len(parity) != _SUPPORTED_CASE_COUNT
            or len({item.case_id for item in parity}) != _SUPPORTED_CASE_COUNT
            or len({item.case_name for item in parity}) != _SUPPORTED_CASE_COUNT
            or {item.case_id for item in parity}
            != set(self.case_set.supported_case_ids)
        ):
            raise ContractValidationError("artifact supported case membership changed")
        if (
            len(unavailable) != _UNAVAILABLE_CASE_COUNT
            or len({item.probe_id for item in unavailable}) != _UNAVAILABLE_CASE_COUNT
            or len({item.case_name for item in unavailable})
            != _UNAVAILABLE_CASE_COUNT
            or {item.probe_id for item in unavailable}
            != {item.probe_id for item in self.case_set.unavailable_probes}
        ):
            raise ContractValidationError("artifact unavailable membership changed")
        expected_metrics = _calculate_metrics(parity, unavailable)
        if self.metrics != expected_metrics:
            raise ContractValidationError("artifact metrics do not match evidence")
        supported = self.thresholds.supports(expected_metrics)
        if self.hypothesis_status != ("SUPPORTED" if supported else "FALSIFIED"):
            raise ContractValidationError("artifact hypothesis status is inconsistent")
        expected_id = stable_contract_id(
            "cedparityartifactv1",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id is not None and self.artifact_id != expected_id:
            raise ContractValidationError("parity artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected_id)
        return self


class CanonicalSuccessorParityReplayLock(_FrozenEvaluationContract):
    """Serialization returned by the artifact comparator, not self-attestation."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION
    ] = CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION
    replay_lock_id: Optional[str] = None
    authoritative_artifact_id: str
    replay_artifact_id: str
    authoritative_sha256: str = Field(pattern=_HEX64_PATTERN)
    replay_sha256: str = Field(pattern=_HEX64_PATTERN)
    authoritative_supported_order: Tuple[str, ...] = FROZEN_SUPPORTED_CASE_ORDER
    authoritative_unavailable_order: Tuple[str, ...] = FROZEN_UNAVAILABLE_CASE_ORDER
    replay_supported_order: Tuple[str, ...] = FROZEN_REPLAY_SUPPORTED_CASE_ORDER
    replay_unavailable_order: Tuple[str, ...] = FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER
    semantic_equality: Literal[True] = True
    artifact_id_equality: Literal[True] = True
    byte_identity: Literal[True] = True

    _nonblank_ids = field_validator(
        "authoritative_artifact_id", "replay_artifact_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "CanonicalSuccessorParityReplayLock":
        if (
            self.authoritative_supported_order != FROZEN_SUPPORTED_CASE_ORDER
            or self.authoritative_unavailable_order != FROZEN_UNAVAILABLE_CASE_ORDER
            or self.replay_supported_order != FROZEN_REPLAY_SUPPORTED_CASE_ORDER
            or self.replay_unavailable_order != FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER
        ):
            raise ContractValidationError("replay lock execution orders changed")
        if self.replay_supported_order != tuple(
            reversed(self.authoritative_supported_order)
        ) or self.replay_unavailable_order != tuple(
            reversed(self.authoritative_unavailable_order)
        ):
            raise ContractValidationError("replay lock is not exact reverse order")
        if self.authoritative_artifact_id != self.replay_artifact_id:
            raise ContractValidationError("replay artifact ID differs")
        if self.authoritative_sha256 != self.replay_sha256:
            raise ContractValidationError("replay artifact bytes differ")
        expected = stable_contract_id(
            "cedparityreplaylockv1",
            self.model_dump(mode="json", exclude={"replay_lock_id"}),
        )
        if self.replay_lock_id is not None and self.replay_lock_id != expected:
            raise ContractValidationError("replay-lock ID mismatch")
        object.__setattr__(self, "replay_lock_id", expected)
        return self


def _budget(**updates: int) -> SearchBudget:
    values = {
        "max_nodes": 4,
        "max_expansions": 3,
        "max_model_calls": 0,
        "max_tool_calls": 0,
        "max_tokens": 0,
        "max_cost_microusd": 0,
        "max_wall_time_ms": 0,
        "max_depth": 1,
    }
    values.update(updates)
    return SearchBudget(**values)


def _provider_dispatches(adapters: Iterable[object]) -> int:
    return sum(int(getattr(adapter, "generate_calls", 0)) for adapter in adapters)


def _failure_runtime_fingerprint(
    ced: Optional[CEDOrchestrator],
) -> Optional[str]:
    if ced is None:
        return None
    try:
        return canonical_runtime_fingerprint(ced)
    except Exception:  # failure evidence must remain serializable
        return None


def _failure_provider_dispatches(adapters: Iterable[object]) -> int:
    try:
        return _provider_dispatches(adapters)
    except Exception:  # the evaluation-failure metric preserves the uncertainty
        return 0


def _normalize_root_audit_clock(state) -> None:
    """Stabilize only timestamps already excluded from Phase 8 semantics."""

    state.created_at = _EVALUATOR_AUDIT_TIME
    state.updated_at = _EVALUATOR_AUDIT_TIME


def _build_custom_root(
    case: AuthoritativeRecordedObservationCase,
    *,
    agent_ids: Tuple[str, ...] = CANONICAL_RECORDING_AGENT_IDS,
    provider_models: Tuple[Tuple[str, str], ...] = CANONICAL_RECORDING_PROVIDER_MODELS,
    provider_timeout_seconds: Optional[float] = None,
):
    """Construct metadata-only negative roots; adapters are never dispatched."""

    provider = FakeProvider()
    registry_kwargs = {}
    if provider_timeout_seconds is not None:
        registry_kwargs["provider_timeout_seconds"] = provider_timeout_seconds
    registry = CouncilProviderRegistry(**registry_kwargs)
    adapters = tuple(
        CanonicalSuccessorRecordingProvider(
            provider_id,
            model_id=model_id,
            recorded_raw_text=case.raw_text or "",
        )
        for provider_id, model_id in provider_models
    )
    for adapter in adapters:
        registry.register(adapter)
    ced = CEDOrchestrator(
        [SocraticAgent(agent_id, provider) for agent_id in agent_ids],
        provider,
        registry=registry,
        phase_retry=False,
    )
    state = ced.create_session(case.recorded_question, session_id=case.recorded_session_id)
    _normalize_root_audit_clock(state)
    return ced, state, adapters


def _build_standard_root(case: AuthoritativeRecordedObservationCase):
    ced, state, adapters = build_canonical_recording_root(
        question=case.recorded_question,
        raw_text=case.raw_text or "",
        session_id=case.recorded_session_id,
    )
    _normalize_root_audit_clock(state)
    return ced, state, adapters


def _capture_and_prepare(
    case: AuthoritativeRecordedObservationCase,
    *,
    budget: Optional[SearchBudget] = None,
    usage: Optional[BudgetUsage] = None,
    root_builder: Optional[Callable[[], tuple]] = None,
):
    selected_budget = budget or _budget()
    selected_usage = usage or BudgetUsage(nodes=1)
    ced, state, adapters = root_builder() if root_builder is not None else _build_standard_root(case)
    env = CanonicalSuccessorEnvironmentV0()
    capsule = env.capture_capsule(
        ced, state, budget=selected_budget, budget_usage=selected_usage
    )
    pending = env.prepare_transition(
        capsule,
        LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
        selected_budget,
    )
    return env, ced, state, adapters, capsule, pending


def _canonical_result_evidence(
    result: CanonicalTransitionResult,
) -> Tuple[str, Optional[Dict[str, object]], Optional[SearchStateV1]]:
    """Hash contract-owned outcome identity plus the canonical semantic snapshot."""

    successor = result.successor_capsule
    projected = result.successor_search_state_v1
    semantic: Optional[Dict[str, object]] = None
    if successor is not None:
        if projected is None:
            raise ContractValidationError("successor capsule has no SearchState-v1")
        rebuilt_semantic, rebuilt_projection = canonical_capsule_semantic_snapshot(
            successor
        )
        if rebuilt_projection != projected:
            raise ContractValidationError(
                "result does not reproduce its canonical SearchState-v1 projection"
            )
        semantic = rebuilt_semantic
    elif projected is not None:
        raise ContractValidationError("SearchState-v1 exists without a successor capsule")
    evidence = {
        "result_identity": result.identity_payload(),
        "receipt_identity": result.receipt.identity_payload(),
        "successor_semantics": semantic,
        "successor_search_state_v1": (
            projected.model_dump(mode="json") if projected is not None else None
        ),
    }
    return _digest(evidence), semantic, projected


def _tool_calls(results: Iterable[Optional[CanonicalTransitionResult]]) -> int:
    return sum(
        result.receipt.new_execution_usage.budget_delta.tool_calls
        for result in results
        if result is not None
    )


def _live_calls(adapters: Iterable[object]) -> int:
    return sum(
        int(getattr(adapter, "generate_calls", 0))
        for adapter in adapters
        if not isinstance(adapter, CanonicalSuccessorRecordingProvider)
    )


def _failure_live_calls(adapters: Iterable[object]) -> int:
    try:
        return _live_calls(adapters)
    except Exception:  # evaluation failure remains the conservative gate
        return 0


def _isolation_evidence_digest(
    *,
    capsule_id: str,
    branch_id: Optional[str],
    state_v1_id: Optional[str],
    runtime_before: str,
    runtime_after: str,
    dispatches_before: int,
    dispatches_after: int,
) -> str:
    return _digest(
        {
            "source_capsule_id" if branch_id is not None else "control_capsule_id": (
                capsule_id
            ),
            **({"source_branch_id": branch_id} if branch_id is not None else {}),
            **({"source_state_v1_id": state_v1_id} if state_v1_id is not None else {}),
            "runtime_fingerprint_before": runtime_before,
            "runtime_fingerprint_after": runtime_after,
            "provider_dispatches_before": dispatches_before,
            "provider_dispatches_after": dispatches_after,
        }
    )


def _value_v1_compatibility(state: SearchStateV1) -> Tuple[bool, str]:
    before = canonical_json(state.model_dump(mode="json"))
    first = HeuristicValueEstimatorV1().evaluate(state)
    second = HeuristicValueEstimatorV1().evaluate(state)
    after = canonical_json(state.model_dump(mode="json"))
    compatible = all(
        (
            before == after,
            first == second,
            first.state_id == state.state_id,
            first.base_state_id == state.base_state.state_id,
        )
    )
    return compatible, first.receipt_hash


def _build_production_control(
    *,
    budget: SearchBudget,
    usage: BudgetUsage,
):
    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        _PRODUCTION_CONTROL_CASE_NAME
    )
    ced, state, adapters = _build_standard_root(case)
    capsule = CanonicalSuccessorEnvironmentV0().capture_capsule(
        ced,
        state,
        budget=budget,
        budget_usage=usage,
    )
    if capsule.capsule_id != case.reference.source_capsule_id:
        raise ContractValidationError("production-control root changed frozen identity")
    return ced, adapters, capsule


def _unmanifested_sibling_observation(
    observation: RecordedCanonicalObservation,
) -> RecordedCanonicalObservation:
    payload = observation.model_dump(mode="python")
    payload.update(
        observation_id=None,
        raw_text=(
            '{"content":{"epistemic_marker":"open_uncertainty",'
            '"operator":"expose_premise","question":"Which premise should '
            'this unmanifested sibling probe examine?"},"confidence":0.5}'
        ),
        raw_output_digest=None,
    )
    sibling = RecordedCanonicalObservation.model_validate(payload)
    if sibling.observation_id == observation.observation_id:
        raise ContractValidationError("sibling probe did not create a distinct identity")
    if verify_authoritative_recorded_observation(sibling):
        raise ContractValidationError("sibling probe unexpectedly entered the manifest")
    return sibling


def _evaluation_failure(
    case: AuthoritativeRecordedObservationCase,
    *,
    stage: ParityEvaluationFailureStage,
    failure_code: ParityEvaluationFailureCode,
    error: Exception,
    source_ced: Optional[CEDOrchestrator] = None,
    source_adapters: Iterable[object] = (),
    source_capsule: object = None,
    source_runtime_before: Optional[str] = None,
    source_dispatches_before: int = 0,
    production_ced: Optional[CEDOrchestrator] = None,
    production_adapters: Iterable[object] = (),
    production_capsule: object = None,
    production_runtime_before: Optional[str] = None,
    production_dispatches_before: int = 0,
    result: Optional[CanonicalTransitionResult] = None,
) -> CanonicalSuccessorParityEvaluationFailure:
    source_adapters = tuple(source_adapters)
    production_adapters = tuple(production_adapters)
    source_identity = (
        getattr(source_capsule, "capsule_id", None),
        getattr(source_capsule, "branch_id", None),
        getattr(source_capsule, "search_state_v1_id", None),
    )
    if not all(value is not None for value in source_identity):
        source_identity = (None, None, None)
    source_after = (
        _failure_runtime_fingerprint(source_ced)
        if source_runtime_before is not None
        else None
    )
    production_after = (
        _failure_runtime_fingerprint(production_ced)
        if production_runtime_before is not None
        else None
    )
    source_dispatches_after = (
        _failure_provider_dispatches(source_adapters) if source_adapters else 0
    )
    production_dispatches_after = (
        _failure_provider_dispatches(production_adapters)
        if production_adapters
        else 0
    )
    return CanonicalSuccessorParityEvaluationFailure(
        case_id=case.case_id or "",
        case_name=case.case_name,
        fixture_role=case.fixture_role,
        reference_id=case.reference.reference_id or "",
        capture_receipt_id=case.reference.capture_receipt_id,
        observation_id=case.observation.observation_id or "",
        stage=stage,
        failure_code=failure_code,
        exception_type=type(error).__name__,
        source_capsule_id=source_identity[0],
        source_branch_id=source_identity[1],
        source_state_v1_id=source_identity[2],
        source_runtime_fingerprint_before=source_runtime_before,
        source_runtime_fingerprint_after=source_after,
        source_provider_dispatches_before=source_dispatches_before,
        source_provider_dispatches_after=source_dispatches_after,
        production_control_capsule_id=getattr(
            production_capsule, "capsule_id", None
        ),
        production_runtime_fingerprint_before=production_runtime_before,
        production_runtime_fingerprint_after=production_after,
        production_provider_dispatches_before=production_dispatches_before,
        production_provider_dispatches_after=production_dispatches_after,
        successor_created=(
            result is not None and result.successor_capsule is not None
        ),
        aggregate_provider_dispatches=(
            source_dispatches_after + production_dispatches_after
        ),
        live_calls=(
            _failure_live_calls(source_adapters)
            + _failure_live_calls(production_adapters)
        ),
        tool_calls=_tool_calls((result,)),
    )


def _evaluate_parity_case_strict(
    case: AuthoritativeRecordedObservationCase,
    context: Dict[str, object],
) -> CanonicalSuccessorParityEvidence:
    budget = _budget()
    usage = BudgetUsage(nodes=1)
    context["stage"] = ParityEvaluationFailureStage.ROOT_RECONSTRUCTION
    env, source_ced, _, source_adapters, capsule, pending = _capture_and_prepare(
        case, budget=budget, usage=usage
    )
    context.update(
        source_ced=source_ced,
        source_adapters=source_adapters,
        source_capsule=capsule,
    )
    reference = case.reference
    capture = case.manifest_entry.capture_receipt
    if (
        capsule.capsule_id != reference.source_capsule_id
        or capsule.source_execution_id != reference.source_execution_id
        or capsule.normalized_semantic_digest != reference.source_normalized_semantic_digest
        or capsule.configuration_digest != capture.source_configuration_digest
        or capsule.canonical_task.task_identity_id != reference.task_identity_id
        or pending.selected_action.action_id != reference.action_id
    ):
        context["failure_code"] = ParityEvaluationFailureCode.ROOT_LINEAGE_MISMATCH
        raise ContractValidationError("reconstructed root differs from capture lineage")
    context["stage"] = ParityEvaluationFailureStage.OBSERVATION_MATERIALIZATION
    observation = case.materialize(pending)
    context["stage"] = ParityEvaluationFailureStage.EVIDENCE_EXTRACTION
    source_before = canonical_runtime_fingerprint(source_ced)
    source_dispatch_before = _provider_dispatches(source_adapters)
    context.update(
        source_runtime_before=source_before,
        source_dispatches_before=source_dispatch_before,
    )
    production_ced, production_adapters, production_capsule = (
        _build_production_control(budget=budget, usage=usage)
    )
    production_before = canonical_runtime_fingerprint(production_ced)
    production_dispatch_before = _provider_dispatches(production_adapters)
    context.update(
        production_ced=production_ced,
        production_adapters=production_adapters,
        production_capsule=production_capsule,
        production_runtime_before=production_before,
        production_dispatches_before=production_dispatch_before,
    )

    context["stage"] = ParityEvaluationFailureStage.OBSERVATION_APPLICATION
    result = env.apply_observation(pending, observation)
    context["result"] = result
    context["stage"] = ParityEvaluationFailureStage.EVIDENCE_EXTRACTION
    primary_digest, semantic, projected = _canonical_result_evidence(result)
    sibling_before, _, _ = _canonical_result_evidence(result)
    sibling_observation = _unmanifested_sibling_observation(observation)
    sibling_result = env.apply_observation(pending, sibling_observation)
    sibling_digest, _, _ = _canonical_result_evidence(sibling_result)
    sibling_after, _, _ = _canonical_result_evidence(result)
    replay = env.apply_observation(pending, observation)
    replay_digest, _, _ = _canonical_result_evidence(replay)

    fields = (
        canonical_successor_reference_field_digests(semantic)
        if semantic is not None
        else ()
    )
    successor = result.successor_capsule
    search_digest = (
        _digest(projected.model_dump(mode="json"))
        if projected is not None
        else None
    )
    if projected is not None:
        value_ok, value_hash = _value_v1_compatibility(projected)
    else:
        value_ok, value_hash = False, _digest({"value_v1": "unavailable"})
    receipt = result.receipt
    receipt_match = projected is not None and all(
        (
            receipt.transition_id == result.transition_id,
            receipt.root_capsule_id == reference.source_capsule_id,
            receipt.root_branch_id == capsule.branch_id,
            receipt.root_state_v1_id
            == case.manifest_entry.capture_receipt.source_search_state_v1_id,
            receipt.branch_id == (successor.branch_id if successor is not None else None),
            receipt.action_id == reference.action_id,
            receipt.observation_id == observation.observation_id,
            receipt.observation_digest == observation.raw_output_digest,
            receipt.status is reference.status,
            receipt.canonical_rejection_reason is reference.canonical_rejection_reason,
            receipt.resulting_move_id == reference.accepted_move_id,
            receipt.source_state_hash == reference.source_normalized_semantic_digest,
            receipt.successor_state_hash
            == (successor.normalized_semantic_digest if successor is not None else None),
            receipt.successor_state_v1_id == projected.state_id,
            tuple(receipt.canonical_processor_ids)
            == tuple(sorted(CANONICAL_PROCESSOR_IDS)),
            receipt.budget == projected.base_state.budget,
            receipt.budget_before == BudgetUsage(nodes=1),
            receipt.budget_after == projected.base_state.budget_usage,
            receipt.legal_action_validation is LegalActionValidationStatus.PASSED,
            receipt.unavailable_reason is None,
            receipt.receipt_id is not None,
            result.result_id is not None,
        )
    )
    expected_usage = NewExecutionUsage()
    resource_match = projected is not None and all(
        (
            receipt.new_execution_usage == expected_usage,
            receipt.budget_after
            == receipt.budget_before.plus(expected_usage.budget_delta),
            expected_usage.budget_delta.model_calls == 0,
            expected_usage.budget_delta.tool_calls == 0,
            expected_usage.budget_delta.tokens == 0,
            expected_usage.budget_delta.cost_microusd == 0,
            expected_usage.budget_delta.wall_time_ms == 0,
            receipt.recorded_historical_usage == observation.historical_usage,
            receipt.budget == projected.base_state.budget,
            receipt.budget_after == projected.base_state.budget_usage,
        )
    )
    field_map = {item.name: item.semantic_digest for item in fields}
    source_after = canonical_runtime_fingerprint(source_ced)
    production_after = canonical_runtime_fingerprint(production_ced)
    source_dispatch_after = _provider_dispatches(source_adapters)
    production_dispatch_after = _provider_dispatches(production_adapters)
    source_evidence = _isolation_evidence_digest(
        capsule_id=capsule.capsule_id or "",
        branch_id=capsule.branch_id,
        state_v1_id=capsule.search_state_v1_id,
        runtime_before=source_before,
        runtime_after=source_after,
        dispatches_before=source_dispatch_before,
        dispatches_after=source_dispatch_after,
    )
    production_evidence = _isolation_evidence_digest(
        capsule_id=production_capsule.capsule_id or "",
        branch_id=None,
        state_v1_id=None,
        runtime_before=production_before,
        runtime_after=production_after,
        dispatches_before=production_dispatch_before,
        dispatches_after=production_dispatch_after,
    )
    sibling_evidence = _digest(
        {
            "primary_before": sibling_before,
            "primary_after": sibling_after,
            "probe_observation_id": sibling_observation.observation_id,
            "probe_status": sibling_result.status.value,
            "probe_unavailable_reason": (
                sibling_result.receipt.unavailable_reason.value
                if sibling_result.receipt.unavailable_reason is not None
                else None
            ),
            "probe_result_id": sibling_result.result_id,
            "probe_receipt_id": sibling_result.receipt.receipt_id,
            "probe_outcome_digest": sibling_digest,
            "probe_successor_created": sibling_result.successor_capsule is not None,
        }
    )
    successor_created = successor is not None and projected is not None
    return CanonicalSuccessorParityCaseResult(
        case_id=case.case_id or "",
        case_name=case.case_name,
        fixture_role=case.fixture_role,
        reference_id=reference.reference_id or "",
        capture_receipt_id=reference.capture_receipt_id,
        observation_id=observation.observation_id or "",
        transition_id=result.transition_id,
        result_id=result.result_id or "",
        receipt=receipt,
        successor_capsule_id=successor.capsule_id if successor is not None else None,
        successor_branch_id=successor.branch_id if successor is not None else None,
        successor_semantic_digest=(
            successor.normalized_semantic_digest if successor is not None else None
        ),
        successor_search_state_v1=projected,
        successor_search_state_v1_digest=search_digest,
        parity_field_digests=fields,
        source_capsule_id=capsule.capsule_id or "",
        source_branch_id=capsule.branch_id or "",
        source_state_v1_id=capsule.search_state_v1_id,
        source_isolation_evidence_digest=source_evidence,
        source_runtime_fingerprint_before=source_before,
        source_runtime_fingerprint_after=source_after,
        source_provider_dispatches_before=source_dispatch_before,
        source_provider_dispatches_after=source_dispatch_after,
        sibling_result_digest_before=sibling_before,
        sibling_result_digest_after=sibling_after,
        sibling_probe_observation_id=sibling_observation.observation_id or "",
        sibling_probe_status=sibling_result.status,
        sibling_probe_unavailable_reason=sibling_result.receipt.unavailable_reason,
        sibling_probe_result_id=sibling_result.result_id or "",
        sibling_probe_receipt_id=sibling_result.receipt.receipt_id or "",
        sibling_probe_outcome_digest=sibling_digest,
        sibling_probe_successor_created=sibling_result.successor_capsule is not None,
        sibling_isolation_evidence_digest=sibling_evidence,
        primary_result_digest=primary_digest,
        replay_result_digest=replay_digest,
        replay_result_id=replay.result_id or "",
        replay_receipt_id=replay.receipt.receipt_id or "",
        production_control_capsule_id=production_capsule.capsule_id or "",
        production_isolation_evidence_digest=production_evidence,
        production_runtime_fingerprint_before=production_before,
        production_runtime_fingerprint_after=production_after,
        production_provider_dispatches_before=production_dispatch_before,
        production_provider_dispatches_after=production_dispatch_after,
        successor_created=successor_created,
        status_parity=result.status is reference.status,
        canonical_rejection_reason_parity=(
            result.receipt.canonical_rejection_reason is reference.canonical_rejection_reason
        ),
        semantic_parity=(
            successor is not None
            and successor.normalized_semantic_digest
            == reference.successor_semantic_digest
            and field_map.get("normalized_semantics")
            == reference.field_digest("normalized_semantics")
        ),
        search_state_v1_parity=(
            projected is not None
            and projected.state_id == reference.successor_search_state_v1_id
            and search_digest == reference.successor_search_state_v1_digest
            and field_map.get("search_state_v1")
            == reference.field_digest("search_state_v1")
        ),
        move_id_parity=receipt.resulting_move_id == reference.accepted_move_id,
        canonical_processor_parity=(
            tuple(receipt.canonical_processor_ids)
            == tuple(sorted(reference.canonical_processor_ids))
        ),
        observation_identity_match=all(
            (
                verify_authoritative_recorded_observation(observation),
                receipt.observation_id == observation.observation_id,
                receipt.observation_digest == observation.raw_output_digest,
            )
        ),
        receipt_match=receipt_match,
        resource_accounting_match=resource_match,
        source_unchanged=(
            source_before == source_after
            and source_dispatch_before == source_dispatch_after == 0
        ),
        sibling_unchanged=all(
            (
                sibling_before == sibling_after,
                sibling_result.status
                is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
                sibling_result.receipt.unavailable_reason
                is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
                sibling_result.successor_capsule is None,
            )
        ),
        production_unchanged=(
            production_before == production_after
            and production_dispatch_before == production_dispatch_after == 0
        ),
        idempotent_replay=all(
            (
                primary_digest == replay_digest,
                result.result_id == replay.result_id,
                receipt.receipt_id == replay.receipt.receipt_id,
            )
        ),
        value_v1_read_only_compatible=value_ok,
        value_v1_receipt_hash=value_hash,
        aggregate_provider_dispatches=source_dispatch_after + production_dispatch_after,
        live_calls=_live_calls(source_adapters) + _live_calls(production_adapters),
        tool_calls=_tool_calls((result, sibling_result, replay)),
    )


def _evaluate_parity_case(
    case: AuthoritativeRecordedObservationCase,
) -> CanonicalSuccessorParityEvidence:
    context: Dict[str, object] = {
        "stage": ParityEvaluationFailureStage.ROOT_RECONSTRUCTION,
    }
    try:
        return _evaluate_parity_case_strict(case, context)
    except Exception as error:
        stage = context.get("stage")
        if not isinstance(stage, ParityEvaluationFailureStage):
            stage = ParityEvaluationFailureStage.EVIDENCE_EXTRACTION
        default_codes = {
            ParityEvaluationFailureStage.ROOT_RECONSTRUCTION: (
                ParityEvaluationFailureCode.ROOT_RECONSTRUCTION_FAILED
            ),
            ParityEvaluationFailureStage.OBSERVATION_MATERIALIZATION: (
                ParityEvaluationFailureCode.OBSERVATION_MATERIALIZATION_FAILED
            ),
            ParityEvaluationFailureStage.OBSERVATION_APPLICATION: (
                ParityEvaluationFailureCode.OBSERVATION_APPLICATION_FAILED
            ),
            ParityEvaluationFailureStage.EVIDENCE_EXTRACTION: (
                ParityEvaluationFailureCode.EVIDENCE_EXTRACTION_FAILED
            ),
        }
        failure_code = context.get("failure_code", default_codes[stage])
        if not isinstance(failure_code, ParityEvaluationFailureCode):
            failure_code = default_codes[stage]
        return _evaluation_failure(
            case,
            stage=stage,
            failure_code=failure_code,
            error=error,
            source_ced=context.get("source_ced"),
            source_adapters=context.get("source_adapters", ()),
            source_capsule=context.get("source_capsule"),
            source_runtime_before=context.get("source_runtime_before"),
            source_dispatches_before=int(
                context.get("source_dispatches_before", 0)
            ),
            production_ced=context.get("production_ced"),
            production_adapters=context.get("production_adapters", ()),
            production_capsule=context.get("production_capsule"),
            production_runtime_before=context.get("production_runtime_before"),
            production_dispatches_before=int(
                context.get("production_dispatches_before", 0)
            ),
            result=(
                context.get("result")
                if isinstance(context.get("result"), CanonicalTransitionResult)
                else None
            ),
        )


def _replace_mapping(observation, **updates: object) -> Dict[str, object]:
    payload = observation.model_dump(mode="python")
    payload.update(updates)
    return payload


def _invoke_probe(
    operation: Callable[[], object],
) -> Tuple[
    Optional[SuccessorUnavailableReason],
    Optional[CanonicalTransitionStatus],
    Optional[CanonicalTransitionResult],
    str,
]:
    try:
        value = operation()
    except CanonicalSuccessorUnavailable as exc:
        return (
            exc.reason,
            None,
            None,
            _digest({"kind": "exception", "reason": exc.reason.value}),
        )
    if isinstance(value, CanonicalTransitionResult):
        digest, _, _ = _canonical_result_evidence(value)
        return value.receipt.unavailable_reason, value.status, value, digest
    payload = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else {"type": type(value).__name__}
    )
    return None, None, None, _digest({"kind": "unexpected-return", "value": payload})


def _negative_operation(probe: CanonicalSuccessorUnavailableProbe):
    baseline = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    )
    budget = _budget()
    usage = BudgetUsage(nodes=1)
    env, source_ced, source_state, source_adapters, capsule, pending = (
        _capture_and_prepare(baseline, budget=budget, usage=usage)
    )
    observation = baseline.materialize(pending)
    target_ced = source_ced
    target_adapters = source_adapters
    target_capsule = capsule
    if probe.case_name == "invalid-root":
        detached = source_state.model_copy(deep=True)
        operation = lambda: env.capture_capsule(
            source_ced, detached, budget=budget, budget_usage=usage
        )
    elif probe.case_name == "budget-exhausted":
        exhausted = _budget(max_nodes=1, max_expansions=0)
        exhausted_capsule = env.capture_capsule(
            source_ced,
            source_state,
            budget=exhausted,
            budget_usage=BudgetUsage(nodes=1),
        )
        operation = lambda: env.prepare_transition(
            exhausted_capsule,
            LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
            exhausted,
        )
        target_capsule = exhausted_capsule
    elif probe.case_name == "unsupported-action-family":
        operation = lambda: env.prepare_transition(
            capsule, LegalAction(kind=ActionKind.RUN_ELENCHUS), budget
        )
    elif probe.case_name == "illegal-action":
        operation = lambda: env.prepare_transition(
            capsule,
            LegalAction(
                kind=ActionKind.ASK_SOCRATIC_QUESTION,
                required_capabilities=("not-present-in-root",),
            ),
            budget,
        )
    elif probe.case_name == "missing-observation":
        operation = lambda: env.apply_observation(pending, None)
    elif probe.case_name == "invalid-observation":
        operation = lambda: env.apply_observation(
            pending, {"schema_version": RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION}
        )
    elif probe.case_name == "tampered-observation-identity":
        tampered = observation.model_copy(update={"raw_output_digest": "f" * 64})
        operation = lambda: env.apply_observation(pending, tampered)
    elif probe.case_name == "caller-rebinding":
        other = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
            "opening-empty-question"
        )
        other_env, other_ced, _, other_adapters, other_capsule, other_pending = (
            _capture_and_prepare(other)
        )
        rebound_payload = observation.model_dump(mode="python")
        rebound_payload.update(
            observation_id=None,
            source_capsule_id=other_pending.source_capsule_id,
            source_execution_id=other_pending.source_capsule.source_execution_id,
            source_configuration_digest=(
                other_pending.source_capsule.configuration_digest
            ),
            action_id=other_pending.selected_action.action_id,
            task_identity=other_pending.canonical_task,
            provider_id=other_pending.expected_provider_id,
            configured_model_id=other_pending.expected_model_id,
            actual_model_id=other_pending.expected_model_id,
            model_config_digest=other_pending.canonical_task.model_config_digest,
        )
        rebound = RecordedCanonicalObservation.model_validate(rebound_payload)
        if verify_authoritative_recorded_observation(rebound):
            raise ContractValidationError(
                "caller-rebinding probe unexpectedly entered the manifest"
            )
        operation = lambda: other_env.apply_observation(other_pending, rebound)
        target_ced = other_ced
        target_adapters = other_adapters
        target_capsule = other_capsule
    elif probe.case_name == "future-label-forbidden":
        labelled = _replace_mapping(observation)
        labelled["reward"] = 1
        operation = lambda: env.apply_observation(pending, labelled)
    elif probe.case_name == "wrong-root-context":
        other = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
            "opening-empty-question"
        )
        other_env, other_ced, _, other_adapters, other_capsule, other_pending = (
            _capture_and_prepare(other)
        )
        operation = lambda: other_env.apply_observation(other_pending, observation)
        target_ced = other_ced
        target_adapters = other_adapters
        target_capsule = other_capsule
    elif probe.case_name == "wrong-task":
        alternate_agents = tuple(
            f"phase8-recorded-alternate-agent-{index}" for index in range(4)
        )
        wrong_env, wrong_ced, _, wrong_adapters, wrong_capsule, wrong_pending = _capture_and_prepare(
            baseline,
            root_builder=lambda: _build_custom_root(baseline, agent_ids=alternate_agents),
        )
        operation = lambda: wrong_env.apply_observation(wrong_pending, observation)
        target_ced = wrong_ced
        target_adapters = wrong_adapters
        target_capsule = wrong_capsule
    elif probe.case_name == "wrong-provider":
        providers = tuple(
            (f"phase8-wrong-seat-{index}", model_id)
            for index, (_, model_id) in enumerate(CANONICAL_RECORDING_PROVIDER_MODELS)
        )
        wrong_env, wrong_ced, _, wrong_adapters, wrong_capsule, wrong_pending = _capture_and_prepare(
            baseline,
            root_builder=lambda: _build_custom_root(baseline, provider_models=providers),
        )
        operation = lambda: wrong_env.apply_observation(wrong_pending, observation)
        target_ced = wrong_ced
        target_adapters = wrong_adapters
        target_capsule = wrong_capsule
    elif probe.case_name == "wrong-model":
        models = tuple(
            (provider_id, f"phase8-wrong-model/{index}")
            for index, (provider_id, _) in enumerate(CANONICAL_RECORDING_PROVIDER_MODELS)
        )
        wrong_env, wrong_ced, _, wrong_adapters, wrong_capsule, wrong_pending = _capture_and_prepare(
            baseline,
            root_builder=lambda: _build_custom_root(baseline, provider_models=models),
        )
        operation = lambda: wrong_env.apply_observation(wrong_pending, observation)
        target_ced = wrong_ced
        target_adapters = wrong_adapters
        target_capsule = wrong_capsule
    elif probe.case_name == "wrong-configuration":
        timeout = CouncilProviderRegistry().provider_timeout_seconds + 1.0
        wrong_env, wrong_ced, _, wrong_adapters, wrong_capsule, wrong_pending = _capture_and_prepare(
            baseline,
            root_builder=lambda: _build_custom_root(
                baseline, provider_timeout_seconds=timeout
            ),
        )
        operation = lambda: wrong_env.apply_observation(wrong_pending, observation)
        target_ced = wrong_ced
        target_adapters = wrong_adapters
        target_capsule = wrong_capsule
    else:  # pragma: no cover - frozen probe contract guards this branch
        raise AssertionError(probe.case_name)
    return operation, target_ced, target_adapters, target_capsule


def _evaluate_unavailable_case(
    probe: CanonicalSuccessorUnavailableProbe,
) -> CanonicalSuccessorUnavailableCaseResult:
    operation, source_ced, source_adapters, source_capsule = _negative_operation(probe)
    source_before = canonical_runtime_fingerprint(source_ced)
    source_dispatch_before = _provider_dispatches(source_adapters)
    production_ced, production_adapters, production_capsule = (
        _build_production_control(budget=_budget(), usage=BudgetUsage(nodes=1))
    )
    production_before = canonical_runtime_fingerprint(production_ced)
    production_dispatch_before = _provider_dispatches(production_adapters)
    actual, actual_status, first, primary_digest = _invoke_probe(operation)
    replay_reason, replay_status, replay, replay_digest = _invoke_probe(operation)
    replay_match = all(
        (
            actual is replay_reason,
            actual_status is replay_status,
            primary_digest == replay_digest,
            (first.result_id if first is not None else None)
            == (replay.result_id if replay is not None else None),
            (
                first.receipt.receipt_id if first is not None else None
            )
            == (replay.receipt.receipt_id if replay is not None else None),
        )
    )
    first_receipt = first.receipt if first is not None else None
    receipt_match = (
        first is None
        or all(
            (
                first.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
                first.successor_capsule is None,
                first.successor_search_state_v1 is None,
                first_receipt is not None and first_receipt.unavailable_reason is actual,
            )
        )
    )
    resource_match = (
        first_receipt is None
        or all(
            (
                first_receipt.new_execution_usage == NewExecutionUsage.not_applied(),
                first_receipt.budget_after == first_receipt.budget_before,
            )
        )
    )
    source_after = canonical_runtime_fingerprint(source_ced)
    production_after = canonical_runtime_fingerprint(production_ced)
    source_dispatch_after = _provider_dispatches(source_adapters)
    production_dispatch_after = _provider_dispatches(production_adapters)
    source_evidence = _isolation_evidence_digest(
        capsule_id=source_capsule.capsule_id or "",
        branch_id=source_capsule.branch_id,
        state_v1_id=source_capsule.search_state_v1_id,
        runtime_before=source_before,
        runtime_after=source_after,
        dispatches_before=source_dispatch_before,
        dispatches_after=source_dispatch_after,
    )
    production_evidence = _isolation_evidence_digest(
        capsule_id=production_capsule.capsule_id or "",
        branch_id=None,
        state_v1_id=None,
        runtime_before=production_before,
        runtime_after=production_after,
        dispatches_before=production_dispatch_before,
        dispatches_after=production_dispatch_after,
    )
    successor = first.successor_capsule if first is not None else None
    projected = first.successor_search_state_v1 if first is not None else None
    successor_created = successor is not None and projected is not None
    return CanonicalSuccessorUnavailableCaseResult(
        probe_id=probe.probe_id or "",
        case_name=probe.case_name,
        stage=probe.stage,
        expected_reason=probe.expected_reason,
        actual_reason=actual,
        actual_status=actual_status,
        replay_reason=replay_reason,
        replay_status=replay_status,
        transition_id=first.transition_id if first is not None else None,
        result_id=first.result_id if first is not None else None,
        receipt=first_receipt,
        replay_result_id=replay.result_id if replay is not None else None,
        replay_receipt_id=(
            replay.receipt.receipt_id if replay is not None else None
        ),
        successor_capsule_id=successor.capsule_id if successor is not None else None,
        successor_branch_id=successor.branch_id if successor is not None else None,
        successor_state_v1_id=projected.state_id if projected is not None else None,
        primary_outcome_digest=primary_digest,
        replay_outcome_digest=replay_digest,
        source_capsule_id=source_capsule.capsule_id or "",
        source_branch_id=source_capsule.branch_id or "",
        source_state_v1_id=source_capsule.search_state_v1_id,
        source_isolation_evidence_digest=source_evidence,
        source_runtime_fingerprint_before=source_before,
        source_runtime_fingerprint_after=source_after,
        source_provider_dispatches_before=source_dispatch_before,
        source_provider_dispatches_after=source_dispatch_after,
        production_control_capsule_id=production_capsule.capsule_id or "",
        production_isolation_evidence_digest=production_evidence,
        production_runtime_fingerprint_before=production_before,
        production_runtime_fingerprint_after=production_after,
        production_provider_dispatches_before=production_dispatch_before,
        production_provider_dispatches_after=production_dispatch_after,
        reason_match=actual is probe.expected_reason,
        replay_match=replay_match,
        source_unchanged=(
            source_before == source_after
            and source_dispatch_before == source_dispatch_after == 0
        ),
        production_unchanged=(
            production_before == production_after
            and production_dispatch_before == production_dispatch_after == 0
        ),
        receipt_match=receipt_match,
        resource_accounting_match=resource_match,
        successor_created=successor_created,
        aggregate_provider_dispatches=source_dispatch_after + production_dispatch_after,
        live_calls=_live_calls(source_adapters) + _live_calls(production_adapters),
        tool_calls=_tool_calls((first, replay)),
    )


def _probe_failure(
    unavailable: Sequence[CanonicalSuccessorUnavailableCaseResult], case_name: str
) -> int:
    item = next(result for result in unavailable if result.case_name == case_name)
    return int(not item.unavailable_passed)


def _calculate_metrics(
    parity: Iterable[CanonicalSuccessorParityEvidence],
    unavailable: Iterable[CanonicalSuccessorUnavailableCaseResult],
) -> CanonicalSuccessorParityMetrics:
    parity_cases = tuple(parity)
    unavailable_cases = tuple(unavailable)
    all_cases: Tuple[object, ...] = parity_cases + unavailable_cases
    evaluation_failures = tuple(
        item
        for item in parity_cases
        if isinstance(item, CanonicalSuccessorParityEvaluationFailure)
    )

    def mismatch(item: CanonicalSuccessorParityEvidence, attribute: str) -> int:
        if isinstance(item, CanonicalSuccessorParityEvaluationFailure):
            return 1
        return int(not bool(getattr(item, attribute)))

    def field_mismatch(item: CanonicalSuccessorParityEvidence, name: str) -> int:
        if isinstance(item, CanonicalSuccessorParityEvaluationFailure):
            return 1
        return int(not item.field_parity(name))

    accepted = tuple(
        item
        for item in parity_cases
        if FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
            item.case_name
        ).reference.status
        is CanonicalTransitionStatus.APPLIED_ACCEPTED
    )
    rejected = tuple(
        item
        for item in parity_cases
        if FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
            item.case_name
        ).reference.status
        is CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION
    )
    return CanonicalSuccessorParityMetrics(
        cases_total=len(all_cases),
        supported_authoritative_cases=len(parity_cases),
        accepted_reference_cases=len(accepted),
        canonical_rejection_reference_cases=len(rejected),
        unavailable_negative_cases=len(unavailable_cases),
        accepted_parity=sum(item.parity_passed for item in accepted),
        canonical_rejection_parity=sum(item.parity_passed for item in rejected),
        unavailable_passed=sum(item.unavailable_passed for item in unavailable_cases),
        evaluation_failures=len(evaluation_failures),
        unavailable_reason_mismatches=sum(not item.reason_match for item in unavailable_cases),
        status_mismatches=sum(mismatch(item, "status_parity") for item in parity_cases),
        canonical_rejection_reason_mismatches=sum(
            mismatch(item, "canonical_rejection_reason_parity")
            for item in parity_cases
        ),
        semantic_mismatches=sum(
            mismatch(item, "semantic_parity") for item in parity_cases
        ),
        accepted_move_id_mismatches=sum(
            mismatch(item, "move_id_parity") for item in accepted
        ),
        task_log_mismatches=sum(
            field_mismatch(item, "task_log") for item in parity_cases
        ),
        commitment_mismatches=sum(
            field_mismatch(item, "commitments") for item in parity_cases
        ),
        phase_role_mismatches=sum(
            field_mismatch(item, "phase_role_cursor") for item in parity_cases
        ),
        search_state_v1_mismatches=sum(
            mismatch(item, "search_state_v1_parity") for item in parity_cases
        ),
        canonical_processor_mismatches=sum(
            mismatch(item, "canonical_processor_parity") for item in parity_cases
        ),
        observation_identity_mismatches=sum(
            mismatch(item, "observation_identity_match") for item in parity_cases
        ),
        context_binding_failures=_probe_failure(unavailable_cases, "wrong-root-context"),
        task_binding_failures=_probe_failure(unavailable_cases, "wrong-task"),
        provider_binding_failures=_probe_failure(unavailable_cases, "wrong-provider"),
        model_binding_failures=_probe_failure(unavailable_cases, "wrong-model"),
        configuration_binding_failures=_probe_failure(
            unavailable_cases, "wrong-configuration"
        ),
        source_isolation_failures=sum(
            (
                1
                if isinstance(item, CanonicalSuccessorParityEvaluationFailure)
                else int(not getattr(item, "source_unchanged"))
            )
            for item in all_cases
        ),
        sibling_isolation_failures=sum(
            mismatch(item, "sibling_unchanged") for item in parity_cases
        ),
        production_mutations=sum(
            (
                1
                if isinstance(item, CanonicalSuccessorParityEvaluationFailure)
                else int(not getattr(item, "production_unchanged"))
            )
            for item in all_cases
        ),
        receipt_mismatches=sum(
            (
                1
                if isinstance(item, CanonicalSuccessorParityEvaluationFailure)
                else int(not getattr(item, "receipt_match"))
            )
            for item in all_cases
        ),
        resource_accounting_mismatches=sum(
            (
                1
                if isinstance(item, CanonicalSuccessorParityEvaluationFailure)
                else int(not getattr(item, "resource_accounting_match"))
            )
            for item in all_cases
        ),
        value_v1_compatibility_mismatches=sum(
            mismatch(item, "value_v1_read_only_compatible")
            for item in parity_cases
        ),
        idempotence_failures=(
            sum(mismatch(item, "idempotent_replay") for item in parity_cases)
            + sum(not item.replay_match for item in unavailable_cases)
        ),
        fabricated_observations=_probe_failure(unavailable_cases, "caller-rebinding"),
        future_label_violations=_probe_failure(
            unavailable_cases, "future-label-forbidden"
        ),
        historical_offline_fixture_dispatches=sum(
            FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
                item.case_name
            ).reference.offline_fixture_dispatches
            for item in parity_cases
        ),
        aggregate_provider_dispatches=sum(
            getattr(item, "aggregate_provider_dispatches") for item in all_cases
        ),
        live_calls=sum(getattr(item, "live_calls") for item in all_cases),
        tool_calls=sum(getattr(item, "tool_calls") for item in all_cases),
    )


def _validated_order(
    supplied: Optional[Sequence[str]],
    expected: Sequence[str],
    *,
    name: str,
) -> Tuple[str, ...]:
    order = tuple(supplied) if supplied is not None else tuple(expected)
    if len(order) != len(expected) or set(order) != set(expected):
        raise ContractValidationError(f"{name} must contain the complete frozen set")
    return order


def _build_canonical_successor_parity_artifact_in_order(
    *,
    corpus_order: Sequence[str],
    unavailable_order: Sequence[str],
) -> CanonicalSuccessorParityArtifact:
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    corpus_names = tuple(item.case_name for item in corpus.cases)
    probe_names = tuple(item.case_name for item in FROZEN_UNAVAILABLE_PROBES)
    selected_corpus_order = _validated_order(corpus_order, corpus_names, name="corpus_order")
    selected_probe_order = _validated_order(
        unavailable_order, probe_names, name="unavailable_order"
    )
    parity = tuple(
        _evaluate_parity_case(corpus.case(case_name)) for case_name in selected_corpus_order
    )
    probes = {item.case_name: item for item in FROZEN_UNAVAILABLE_PROBES}
    unavailable = tuple(
        _evaluate_unavailable_case(probes[case_name]) for case_name in selected_probe_order
    )
    metrics = _calculate_metrics(parity, unavailable)
    supported = FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS.supports(metrics)
    return CanonicalSuccessorParityArtifact(
        capture_manifest_id=FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.manifest_id or "",
        corpus_id=corpus.corpus_id or "",
        corpus_canonical_sha256=frozen_corpus_v1_canonical_sha256(),
        case_set_id=FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET.case_set_id or "",
        case_set_fingerprint=(
            FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET.case_set_fingerprint or ""
        ),
        thresholds_id=FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS.thresholds_id or "",
        case_set=FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET,
        thresholds=FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS,
        parity_cases=parity,
        unavailable_cases=unavailable,
        metrics=metrics,
        hypothesis_status="SUPPORTED" if supported else "FALSIFIED",
    )


def build_canonical_successor_parity_artifact() -> CanonicalSuccessorParityArtifact:
    """Execute the authoritative aggregate after the pre-result freeze commit."""

    return _build_canonical_successor_parity_artifact_in_order(
        corpus_order=FROZEN_SUPPORTED_CASE_ORDER,
        unavailable_order=FROZEN_UNAVAILABLE_CASE_ORDER,
    )


def build_canonical_successor_parity_replay_artifact(
) -> CanonicalSuccessorParityArtifact:
    """Independently rebuild the aggregate in both exact reverse case orders."""

    return _build_canonical_successor_parity_artifact_in_order(
        corpus_order=FROZEN_REPLAY_SUPPORTED_CASE_ORDER,
        unavailable_order=FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER,
    )


def render_canonical_successor_parity_artifact(
    artifact: CanonicalSuccessorParityArtifact,
) -> str:
    """Return canonical sorted JSON with one final newline."""

    return canonical_json(artifact.model_dump(mode="json")) + "\n"


def replay_canonical_successor_parity_artifact(
    rendered: str,
) -> CanonicalSuccessorParityArtifact:
    """Validate artifact bytes; independent rerun remains a separate gate."""

    artifact = CanonicalSuccessorParityArtifact.model_validate_json(rendered)
    if render_canonical_successor_parity_artifact(artifact) != rendered:
        raise ContractValidationError("parity artifact bytes are not canonical")
    return artifact


def canonical_successor_parity_artifact_sha256(
    artifact: CanonicalSuccessorParityArtifact,
) -> str:
    return hashlib.sha256(
        render_canonical_successor_parity_artifact(artifact).encode("utf-8")
    ).hexdigest()


def create_canonical_successor_parity_replay_lock(
    authoritative: CanonicalSuccessorParityArtifact,
    replay: CanonicalSuccessorParityArtifact,
) -> CanonicalSuccessorParityReplayLock:
    """Require semantic, identity, and canonical-byte equality before locking."""

    if not isinstance(authoritative, CanonicalSuccessorParityArtifact) or not isinstance(
        replay, CanonicalSuccessorParityArtifact
    ):
        raise ContractValidationError(
            "replay locking requires both validated parity artifacts"
        )
    authoritative = CanonicalSuccessorParityArtifact.model_validate_json(
        authoritative.model_dump_json()
    )
    replay = CanonicalSuccessorParityArtifact.model_validate_json(
        replay.model_dump_json()
    )
    authoritative_bytes = render_canonical_successor_parity_artifact(authoritative)
    replay_bytes = render_canonical_successor_parity_artifact(replay)
    semantic_equality = authoritative.model_dump(mode="json") == replay.model_dump(
        mode="json"
    )
    artifact_id_equality = authoritative.artifact_id == replay.artifact_id
    byte_identity = authoritative_bytes == replay_bytes
    if not all((semantic_equality, artifact_id_equality, byte_identity)):
        raise ContractValidationError("independent parity replay did not lock")
    return CanonicalSuccessorParityReplayLock(
        authoritative_artifact_id=authoritative.artifact_id or "",
        replay_artifact_id=replay.artifact_id or "",
        authoritative_sha256=hashlib.sha256(
            authoritative_bytes.encode("utf-8")
        ).hexdigest(),
        replay_sha256=hashlib.sha256(replay_bytes.encode("utf-8")).hexdigest(),
    )


def render_canonical_successor_parity_replay_lock(
    replay_lock: CanonicalSuccessorParityReplayLock,
) -> str:
    """Serialize a lock record; this function does not attest its provenance."""

    return canonical_json(replay_lock.model_dump(mode="json")) + "\n"


def replay_canonical_successor_parity_replay_lock(
    rendered: str,
) -> CanonicalSuccessorParityReplayLock:
    """Parse canonical lock bytes for inspection, never for self-attestation."""

    replay_lock = CanonicalSuccessorParityReplayLock.model_validate_json(rendered)
    if render_canonical_successor_parity_replay_lock(replay_lock) != rendered:
        raise ContractValidationError("replay-lock bytes are not canonical")
    return replay_lock


def write_once_canonical_bytes(destination: Path | str, payload: bytes) -> str:
    """Create once; an exact repeated publication is idempotent, a conflict fails."""

    if not payload:
        raise ContractValidationError("write-once canonical payload must not be empty")
    path = Path(destination)
    digest = hashlib.sha256(payload).hexdigest()
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ContractValidationError(
                "write-once destination already contains different bytes"
            )
    return digest


def publish_canonical_successor_parity_artifact_once(
    destination: Path | str,
    artifact: CanonicalSuccessorParityArtifact,
) -> str:
    rendered = render_canonical_successor_parity_artifact(artifact)
    replay_canonical_successor_parity_artifact(rendered)
    return write_once_canonical_bytes(destination, rendered.encode("utf-8"))


def publish_canonical_successor_parity_replay_lock_once(
    destination: Path | str,
    authoritative: CanonicalSuccessorParityArtifact,
    replay: CanonicalSuccessorParityArtifact,
) -> str:
    """Compare both actual artifacts internally, then publish their replay lock."""

    replay_lock = create_canonical_successor_parity_replay_lock(
        authoritative,
        replay,
    )
    rendered = render_canonical_successor_parity_replay_lock(replay_lock)
    replay_canonical_successor_parity_replay_lock(rendered)
    return write_once_canonical_bytes(destination, rendered.encode("utf-8"))


__all__ = [
    "CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION",
    "CANONICAL_SUCCESSOR_PARITY_CASE_RESULT_VERSION",
    "CANONICAL_SUCCESSOR_PARITY_CASE_SET_VERSION",
    "CANONICAL_SUCCESSOR_PARITY_EVALUATION_FAILURE_VERSION",
    "CANONICAL_SUCCESSOR_PARITY_HARNESS_ID",
    "CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION",
    "CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION",
    "CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION",
    "CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION",
    "CANONICAL_SUCCESSOR_UNAVAILABLE_PROBE_VERSION",
    "CANONICAL_TRANSITION_OWNER",
    "FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET",
    "FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS",
    "FROZEN_REPLAY_SUPPORTED_CASE_ORDER",
    "FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER",
    "FROZEN_SUPPORTED_CASE_ORDER",
    "FROZEN_UNAVAILABLE_CASE_ORDER",
    "FROZEN_UNAVAILABLE_PROBES",
    "CanonicalSuccessorParityArtifact",
    "CanonicalSuccessorParityCaseResult",
    "CanonicalSuccessorParityCaseSet",
    "CanonicalSuccessorParityEvaluationFailure",
    "CanonicalSuccessorParityEvidence",
    "CanonicalSuccessorParityMetrics",
    "CanonicalSuccessorParityReplayLock",
    "CanonicalSuccessorParityThresholds",
    "CanonicalSuccessorUnavailableCaseResult",
    "CanonicalSuccessorUnavailableProbe",
    "ParityEvaluationFailureCode",
    "ParityEvaluationFailureStage",
    "UnavailableProbeStage",
    "build_canonical_successor_parity_artifact",
    "build_canonical_successor_parity_replay_artifact",
    "canonical_successor_parity_artifact_sha256",
    "create_canonical_successor_parity_replay_lock",
    "publish_canonical_successor_parity_artifact_once",
    "publish_canonical_successor_parity_replay_lock_once",
    "render_canonical_successor_parity_artifact",
    "render_canonical_successor_parity_replay_lock",
    "replay_canonical_successor_parity_artifact",
    "replay_canonical_successor_parity_replay_lock",
    "write_once_canonical_bytes",
]

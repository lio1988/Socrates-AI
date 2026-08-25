"""Frozen Phase 8 v2 evaluator for canonical-successor parity.

This module is additive and import-safe.  It reuses the sealed v1 supported-case
evaluator for the five immutable recorded observations and owns only the v2
probe-construction/evidence layer.  Expected primary results and invariant
vectors are consulted only by the validity gate and evidence comparison; they
are never captured by a runtime operation closure.

Calling :func:`build_canonical_successor_parity_artifact_v2` is the first
authoritative 23-case aggregate.  Importing this module, rendering contracts,
and validating schemas never execute that aggregate.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass, fields as dataclass_fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Literal, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .agent import SocraticAgent
from .ced import CEDOrchestrator
from .ced_canonical_successor import (
    CANONICAL_PROCESSOR_IDS,
    CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID,
    CanonicalSuccessorEnvironmentV0,
    CanonicalSuccessorUnavailable,
    canonical_runtime_fingerprint,
)
from .ced_canonical_successor_cases_v1 import (
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
    AuthoritativeRecordedObservationCase,
    frozen_corpus_v1_canonical_sha256,
)
from .ced_canonical_successor_cases_v2 import (
    FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1,
    FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1,
    FROZEN_CANONICAL_FAILURE_TAXONOMY_V1,
    FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2,
    FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2,
    FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1,
    FROZEN_CANONICAL_SUCCESSOR_PROBES_V2,
    FROZEN_CANONICAL_VALIDATION_ORDER_V2,
    ORTHOGONAL_PROBE_IDS,
    PRECEDENCE_PROBE_IDS,
    CanonicalSuccessorParityCaseSetV2,
    CanonicalSuccessorProbeV2,
    GuardEvaluation,
    GuardEvaluationState,
    InvariantState,
    ObservationSubmissionState,
    ProbeClass,
    ProbeInvariantVector,
    ProbeStage,
    frozen_corpus_v2_canonical_sha256,
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
    CanonicalBranchCapsule,
    CanonicalTransitionReceipt,
    CanonicalTransitionResult,
    CanonicalTransitionStatus,
    NewExecutionUsage,
    PendingCanonicalTransition,
    RecordedCanonicalObservation,
    SuccessorUnavailableReason,
)
from .ced_canonical_successor_frozen_core_v2 import (
    FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2,
    SEALED_PHASE8_ARTIFACT_COMMIT,
    SEALED_PHASE8_ARTIFACT_ID,
    SEALED_PHASE8_ARTIFACT_SHA256,
    CanonicalSuccessorCoreBlobLockV2,
)
from .ced_canonical_successor_evaluation import (
    CanonicalSuccessorParityCaseResult as V1CanonicalSuccessorParityCaseResult,
    CanonicalSuccessorParityEvaluationFailure as V1CanonicalSuccessorParityEvaluationFailure,
    _build_production_control as _build_v1_production_control,
    _canonical_result_evidence as _canonical_v1_result_evidence,
    _evaluate_parity_case as _evaluate_v1_parity_case,
    _normalize_root_audit_clock as _normalize_v1_root_audit_clock,
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
)
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


CANONICAL_SUCCESSOR_PARITY_HARNESS_ID_V2 = (
    "ced-canonical-successor-parity-harness/v2"
)
CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION_V2 = (
    "ced-canonical-successor-unavailable-case-result/v2"
)
CANONICAL_SUCCESSOR_UNAVAILABLE_RESULT_VERSION_V2 = (
    CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION_V2
)
CANONICAL_SUCCESSOR_PROBE_EVALUATION_FAILURE_VERSION_V2 = (
    "ced-canonical-successor-probe-evaluation-failure/v2"
)
CANONICAL_SUCCESSOR_PROBE_COMPONENT_SNAPSHOT_VERSION_V2 = (
    "ced-canonical-successor-probe-component-snapshot/v2"
)
CANONICAL_SUCCESSOR_PROBE_CONSTRUCTION_EVIDENCE_VERSION_V2 = (
    "ced-canonical-successor-probe-construction-evidence/v2"
)
CANONICAL_SUCCESSOR_COMPATIBILITY_DIAGNOSTIC_EVIDENCE_VERSION_V1 = (
    "ced-canonical-successor-compatibility-diagnostic-evidence/v1"
)
CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION_V2 = (
    "ced-canonical-successor-parity-metrics/v2"
)
CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION_V2 = (
    "ced-canonical-successor-parity-thresholds/v2"
)
CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION_V2 = (
    "ced-canonical-successor-parity-artifact/v2"
)
CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION_V2 = (
    "ced-canonical-successor-parity-replay-lock/v2"
)
CANONICAL_TRANSITION_OWNER = "backend.dialogues.ced.CEDOrchestrator"
V2_CHANGE_RATIONALE = "failure-precedence-and-probe-orthogonality"

_HEX64 = r"^[0-9a-f]{64}$"
_BASELINE_CASE_NAME = "opening-scripted-mock"
_OTHER_BINDING_CASE_NAME = "opening-empty-question"
_BASE_QUESTION = "Is knowledge merely justified true belief?"
_NEW_QUESTION = "What is knowledge?"
_ACTIVE_AGENT = "phase8-recorded-agent-1"
_RENAMED_ACTIVE_AGENT = "phase8-recorded-agent-1-v2"
_ACTIVE_PROVIDER = "phase8-recorded-seat-1"
_RENAMED_ACTIVE_MODEL = "phase8-recorded-model/1-v2-orthogonal"
_WRONG_PROVIDER_MODELS = (
    ("phase8-wrong-seat-0", "phase8-recorded-model/0"),
    ("phase8-wrong-seat-1", "phase8-recorded-model/1"),
)

FROZEN_SUPPORTED_CASE_ORDER_V2 = tuple(
    case.case_name for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
)
FROZEN_ORTHOGONAL_PROBE_ORDER_V2 = ORTHOGONAL_PROBE_IDS
FROZEN_PRECEDENCE_PROBE_ORDER_V2 = PRECEDENCE_PROBE_IDS
FROZEN_REPLAY_SUPPORTED_CASE_ORDER_V2 = tuple(reversed(FROZEN_SUPPORTED_CASE_ORDER_V2))
FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V2 = tuple(
    reversed(FROZEN_ORTHOGONAL_PROBE_ORDER_V2)
)
FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V2 = tuple(
    reversed(FROZEN_PRECEDENCE_PROBE_ORDER_V2)
)


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


class _FrozenV2Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProbeOutcomeKind(str, Enum):
    RAISED_UNAVAILABLE = "RAISED_UNAVAILABLE"
    RETURNED_UNAVAILABLE = "RETURNED_UNAVAILABLE"
    RETURNED_SUCCESSOR = "RETURNED_SUCCESSOR"
    RETURNED_NON_RESULT = "RETURNED_NON_RESULT"


class ProbeEvaluationFailureCode(str, Enum):
    CONSTRUCTION_FAILED = "CONSTRUCTION_FAILED"
    INVALID_PROBE_CONSTRUCTION = "INVALID_PROBE_CONSTRUCTION"
    GROUND_TRUTH_FIREWALL_FAILED = "GROUND_TRUTH_FIREWALL_FAILED"
    INVOCATION_FAILED = "INVOCATION_FAILED"
    EVIDENCE_EXTRACTION_FAILED = "EVIDENCE_EXTRACTION_FAILED"


class CanonicalSuccessorProbeComponentSnapshotV2(_FrozenV2Contract):
    """Measured component identities; ``None`` means genuinely not constructed."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_PROBE_COMPONENT_SNAPSHOT_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PROBE_COMPONENT_SNAPSHOT_VERSION_V2
    root_identity: Optional[str] = Field(default=None, pattern=_HEX64)
    capsule_identity: Optional[str] = Field(default=None, pattern=_HEX64)
    pending_identity: Optional[str] = Field(default=None, pattern=_HEX64)
    task_semantic_identity: Optional[str] = Field(default=None, pattern=_HEX64)
    public_context_digest: Optional[str] = Field(default=None, pattern=_HEX64)
    council_roster_digest: Optional[str] = Field(default=None, pattern=_HEX64)
    action_identity: Optional[str] = Field(default=None, pattern=_HEX64)
    observation_manifest_identity: Optional[str] = Field(default=None, pattern=_HEX64)
    observation_payload_digest: Optional[str] = Field(default=None, pattern=_HEX64)
    provider_binding: Optional[str] = Field(default=None, pattern=_HEX64)
    exact_model_binding: Optional[str] = Field(default=None, pattern=_HEX64)
    configuration_binding: Optional[str] = Field(default=None, pattern=_HEX64)
    lineage_binding: Optional[str] = Field(default=None, pattern=_HEX64)
    future_label_status: Optional[str] = Field(default=None, pattern=_HEX64)
    budget_status: Optional[str] = Field(default=None, pattern=_HEX64)


_INTENTIONAL_COMPONENTS: Dict[str, Tuple[str, ...]] = {
    "p8v2-o01-invalid-root-registration": ("root_identity",),
    "p8v2-o02-illegal-action-capability": ("action_identity",),
    "p8v2-o03-missing-observation": ("observation_manifest_identity",),
    "p8v2-o04-invalid-observation-schema": ("observation_payload_digest",),
    "p8v2-o05-tampered-raw-digest": ("observation_manifest_identity",),
    "p8v2-o06-wrong-task-agent": ("task_semantic_identity",),
    "p8v2-o07-wrong-root-question": ("root_identity",),
    "p8v2-o08-wrong-exact-model": ("exact_model_binding",),
    "p8v2-o09-wrong-runtime-timeout": ("configuration_binding",),
    "p8v2-o10-future-label": ("future_label_status",),
    "p8v2-o11-budget-exhausted": ("budget_status",),
    "p8v2-p01-unsupported-family-vs-legality": ("action_identity",),
    "p8v2-p02-provider-roster-context": ("council_roster_digest",),
    "p8v2-p03-root-plus-provider": (
        "root_identity",
        "council_roster_digest",
    ),
    "p8v2-p04-task-plus-model": (
        "task_semantic_identity",
        "exact_model_binding",
    ),
    "p8v2-p05-context-plus-tampered-digest": (
        "root_identity",
        "observation_manifest_identity",
    ),
    "p8v2-p06-illegal-plus-incompatible-observation": (
        "root_identity",
        "action_identity",
    ),
    "p8v2-p07-caller-rebinding-vs-manifest": (
        "root_identity",
        "capsule_identity",
        "pending_identity",
        "task_semantic_identity",
        "observation_manifest_identity",
        "provider_binding",
        "exact_model_binding",
        "lineage_binding",
    ),
}


def _derive_invariant_vector(
    probe_id: str,
    reference: CanonicalSuccessorProbeComponentSnapshotV2,
    candidate: CanonicalSuccessorProbeComponentSnapshotV2,
) -> ProbeInvariantVector:
    intentional = set(_INTENTIONAL_COMPONENTS[probe_id])
    values: Dict[str, InvariantState] = {}
    for name in ProbeInvariantVector.model_fields:
        before = getattr(reference, name)
        after = getattr(candidate, name)
        if after is None:
            values[name] = InvariantState.NOT_APPLICABLE
        elif before == after:
            values[name] = InvariantState.PRESERVED
        elif name in intentional:
            values[name] = InvariantState.INTENTIONALLY_CHANGED
        else:
            values[name] = InvariantState.DEPENDENTLY_CHANGED
    return ProbeInvariantVector(**values)


class CanonicalSuccessorProbeConstructionEvidenceV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PROBE_CONSTRUCTION_EVIDENCE_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PROBE_CONSTRUCTION_EVIDENCE_VERSION_V2
    construction_evidence_id: Optional[str] = None
    probe_id: str
    probe_fingerprint: str = Field(pattern=_HEX64)
    reference_snapshot: CanonicalSuccessorProbeComponentSnapshotV2
    candidate_snapshot: CanonicalSuccessorProbeComponentSnapshotV2
    measured_invariant_vector: ProbeInvariantVector
    observed_literal_mutations: Tuple[Tuple[str, str, str, bool], ...]
    literal_mutations_match: bool
    observation_submission: ObservationSubmissionState
    observed_stage: ProbeStage
    ground_truth_firewall_passed: bool
    validity_gate_passed: bool

    _probe_id_nonblank = field_validator("probe_id")(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "CanonicalSuccessorProbeConstructionEvidenceV2":
        probe = _probe_by_id(self.probe_id)
        if self.probe_fingerprint != probe.probe_fingerprint:
            raise ContractValidationError("construction evidence probe fingerprint changed")
        measured = _derive_invariant_vector(
            self.probe_id, self.reference_snapshot, self.candidate_snapshot
        )
        if self.measured_invariant_vector != measured:
            raise ContractValidationError("measured invariant vector is not snapshot-derived")
        if any(
            not path.strip()
            for path, _, _, _ in self.observed_literal_mutations
        ) or len({item[0] for item in self.observed_literal_mutations}) != len(
            self.observed_literal_mutations
        ):
            raise ContractValidationError("observed literal mutations are not canonical")
        expected_literals = tuple(
            (
                item.path,
                item.before_json,
                item.after_json,
                item.independent_authoritative_input,
            )
            for item in probe.literal_mutations
        )
        literal_match = self.observed_literal_mutations == expected_literals
        if self.literal_mutations_match is not literal_match:
            raise ContractValidationError("literal mutation match is not evidence-derived")
        expected_gate = all(
            (
                measured == probe.invariant_vector,
                literal_match,
                self.observation_submission is probe.observation_submission,
                self.observed_stage is probe.stage,
                self.ground_truth_firewall_passed,
            )
        )
        if self.validity_gate_passed is not expected_gate:
            raise ContractValidationError("probe validity gate is inconsistent")
        payload = self.model_dump(mode="json", exclude={"construction_evidence_id"})
        expected = stable_contract_id("cedprobeconstructionv2", payload)
        if self.construction_evidence_id is not None and self.construction_evidence_id != expected:
            raise ContractValidationError("construction evidence ID mismatch")
        object.__setattr__(self, "construction_evidence_id", expected)
        return self


class CanonicalSuccessorDiagnosticFieldComparisonV2(_FrozenV2Contract):
    name: str
    observed_digest: str = Field(pattern=_HEX64)
    required_digest: str = Field(pattern=_HEX64)

    _name_nonblank = field_validator("name")(_nonblank)

    @property
    def mismatch(self) -> bool:
        return self.observed_digest != self.required_digest


class CanonicalSuccessorCompatibilityDiagnosticEvidenceV1(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_COMPATIBILITY_DIAGNOSTIC_EVIDENCE_VERSION_V1
    ] = CANONICAL_SUCCESSOR_COMPATIBILITY_DIAGNOSTIC_EVIDENCE_VERSION_V1
    diagnostic_evidence_id: Optional[str] = None
    diagnostics_contract_id: str
    probe_id: str
    observation_submission: ObservationSubmissionState
    field_comparisons: Tuple[CanonicalSuccessorDiagnosticFieldComparisonV2, ...]
    immutable_inputs_digest: str = Field(pattern=_HEX64)
    expected_guard_id: str
    observed_guard_id: Optional[str] = None
    expected_primary_mismatch_fields: Tuple[str, ...]
    observed_primary_mismatch_fields: Tuple[str, ...]
    expected_advisory_or_dominated_mismatch_fields: Tuple[str, ...]
    observed_advisory_or_dominated_mismatch_fields: Tuple[str, ...]
    expected_guard_evaluations: Tuple[GuardEvaluation, ...]
    observed_guard_evaluations: Tuple[GuardEvaluation, ...]
    expected_unreachable_guard_ids: Tuple[str, ...]
    observed_unreachable_guard_ids: Tuple[str, ...]
    expected_structured_future_scan_reached: bool
    observed_structured_future_scan_reached: bool
    canonical_parser_reached: bool
    ced_application_reached: bool
    authoritative_for_primary_result: Literal[False] = False

    @field_validator(
        "expected_primary_mismatch_fields",
        "observed_primary_mismatch_fields",
        "expected_advisory_or_dominated_mismatch_fields",
        "observed_advisory_or_dominated_mismatch_fields",
    )
    @classmethod
    def canonical_fields(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ContractValidationError("diagnostic mismatch fields are not canonical")
        return value

    @field_validator(
        "expected_unreachable_guard_ids",
        "observed_unreachable_guard_ids",
    )
    @classmethod
    def unique_guards(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ContractValidationError("diagnostic guard list contains duplicates")
        return value

    @model_validator(mode="after")
    def validate_and_identify(
        self,
    ) -> "CanonicalSuccessorCompatibilityDiagnosticEvidenceV1":
        probe = _probe_by_id(self.probe_id)
        if self.diagnostics_contract_id != FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.diagnostics_id:
            raise ContractValidationError("diagnostic contract lineage changed")
        comparisons = tuple(sorted(self.field_comparisons, key=lambda item: item.name))
        if (
            len({item.name for item in comparisons}) != len(comparisons)
            or comparisons != self.field_comparisons
        ):
            raise ContractValidationError("diagnostic comparisons are not canonical")
        expected_inputs_digest = _digest(
            [item.model_dump(mode="json") for item in comparisons]
        )
        if self.immutable_inputs_digest != expected_inputs_digest:
            raise ContractValidationError("diagnostic input digest is not comparison-derived")
        measured_primary, measured_advisory = _classify_diagnostic_comparisons(
            observed_guard_id=self.observed_guard_id,
            observation_submission=self.observation_submission,
            comparisons=comparisons,
        )
        if (
            self.observed_primary_mismatch_fields != measured_primary
            or self.observed_advisory_or_dominated_mismatch_fields
            != measured_advisory
        ):
            raise ContractValidationError("observed diagnostic fields are not input-derived")
        if (
            self.expected_guard_id != probe.expected_guard_id
            or self.expected_primary_mismatch_fields
            != probe.expected_primary_mismatch_fields
            or self.expected_advisory_or_dominated_mismatch_fields
            != probe.advisory_or_dominated_mismatch_fields
            or self.expected_guard_evaluations != probe.guard_evaluations
            or self.expected_unreachable_guard_ids != probe.unreachable_guard_ids
            or self.expected_structured_future_scan_reached
            is not probe.structured_future_scan_reached
            or self.observation_submission is not probe.observation_submission
        ):
            raise ContractValidationError("diagnostic expectation differs from frozen probe law")
        observed_trace, observed_unreachable = _guard_trace_for_observed_outcome(
            self.observed_guard_id,
            stage=probe.stage,
        )
        if (
            self.observed_guard_evaluations != observed_trace
            or self.observed_unreachable_guard_ids != observed_unreachable
        ):
            raise ContractValidationError("observed guard trace is not independently derived")
        payload = self.model_dump(mode="json", exclude={"diagnostic_evidence_id"})
        expected = stable_contract_id("cedcompatdiagnosticevidence", payload)
        if self.diagnostic_evidence_id is not None and self.diagnostic_evidence_id != expected:
            raise ContractValidationError("diagnostic evidence ID mismatch")
        object.__setattr__(self, "diagnostic_evidence_id", expected)
        return self

    @property
    def diagnostic_match(self) -> bool:
        return all(
            (
                self.observed_guard_id == self.expected_guard_id,
                self.observed_primary_mismatch_fields
                == self.expected_primary_mismatch_fields,
                self.observed_advisory_or_dominated_mismatch_fields
                == self.expected_advisory_or_dominated_mismatch_fields,
                self.observed_guard_evaluations == self.expected_guard_evaluations,
                self.observed_unreachable_guard_ids
                == self.expected_unreachable_guard_ids,
                self.observed_structured_future_scan_reached
                is self.expected_structured_future_scan_reached,
                not self.canonical_parser_reached,
                not self.ced_application_reached,
            )
        )


def _probe_by_id(probe_id: str) -> CanonicalSuccessorProbeV2:
    try:
        return next(
            probe for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
            if probe.probe_id == probe_id
        )
    except StopIteration as exc:
        raise ContractValidationError("unknown v2 probe") from exc


class CanonicalSuccessorUnavailableCaseResultV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_UNAVAILABLE_RESULT_VERSION_V2
    ] = CANONICAL_SUCCESSOR_UNAVAILABLE_RESULT_VERSION_V2
    case_result_id: Optional[str] = None
    probe_id: str
    probe_fingerprint: str = Field(pattern=_HEX64)
    probe_class: ProbeClass
    stage: ProbeStage
    expected_primary_reason: SuccessorUnavailableReason
    actual_primary_reason: Optional[SuccessorUnavailableReason] = None
    outcome_kind: ProbeOutcomeKind
    actual_status: Optional[CanonicalTransitionStatus] = None
    observed_guard_id: Optional[str] = None
    construction_evidence: CanonicalSuccessorProbeConstructionEvidenceV2
    diagnostics: CanonicalSuccessorCompatibilityDiagnosticEvidenceV1
    transition_id: Optional[str] = None
    result_id: Optional[str] = None
    receipt: Optional[CanonicalTransitionReceipt] = None
    successor_capsule_id: Optional[str] = None
    successor_branch_id: Optional[str] = None
    successor_state_v1_id: Optional[str] = None
    replay_outcome_kind: ProbeOutcomeKind
    replay_primary_reason: Optional[SuccessorUnavailableReason] = None
    replay_status: Optional[CanonicalTransitionStatus] = None
    replay_transition_id: Optional[str] = None
    replay_result_id: Optional[str] = None
    replay_receipt_id: Optional[str] = None
    replay_successor_capsule_id: Optional[str] = None
    replay_successor_branch_id: Optional[str] = None
    replay_successor_state_v1_id: Optional[str] = None
    primary_outcome_digest: str = Field(pattern=_HEX64)
    replay_outcome_digest: str = Field(pattern=_HEX64)
    source_capsule_id: str
    source_runtime_fingerprint_before: str = Field(pattern=_HEX64)
    source_runtime_fingerprint_after: str = Field(pattern=_HEX64)
    source_provider_dispatches_before: int = Field(ge=0, strict=True)
    source_provider_dispatches_after: int = Field(ge=0, strict=True)
    sibling_control_capsule_id: str
    sibling_runtime_fingerprint_before: str = Field(pattern=_HEX64)
    sibling_runtime_fingerprint_after: str = Field(pattern=_HEX64)
    sibling_provider_dispatches_before: int = Field(ge=0, strict=True)
    sibling_provider_dispatches_after: int = Field(ge=0, strict=True)
    production_control_capsule_id: str
    production_runtime_fingerprint_before: str = Field(pattern=_HEX64)
    production_runtime_fingerprint_after: str = Field(pattern=_HEX64)
    production_provider_dispatches_before: int = Field(ge=0, strict=True)
    production_provider_dispatches_after: int = Field(ge=0, strict=True)
    primary_reason_match: bool
    guard_match: bool
    diagnostic_match: bool
    outcome_shape_match: bool
    replay_match: bool
    source_unchanged: bool
    sibling_unchanged: bool
    production_unchanged: bool
    receipt_match: bool
    resource_accounting_match: bool
    successor_created: bool
    negative_probe_dispatches: int = Field(ge=0, strict=True)
    aggregate_provider_dispatches: int = Field(ge=0, strict=True)
    live_calls: int = Field(ge=0, strict=True)
    primary_model_calls: int = Field(ge=0, strict=True)
    replay_model_calls: int = Field(ge=0, strict=True)
    model_calls: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_evidence_and_identify(
        self,
    ) -> "CanonicalSuccessorUnavailableCaseResultV2":
        probe = _probe_by_id(self.probe_id)
        if (
            self.probe_fingerprint != probe.probe_fingerprint
            or self.probe_class is not probe.probe_class
            or self.stage is not probe.stage
            or self.expected_primary_reason is not probe.expected_primary_reason
            or self.construction_evidence.probe_id != self.probe_id
            or not self.construction_evidence.validity_gate_passed
            or self.diagnostics.probe_id != self.probe_id
        ):
            raise ContractValidationError("v2 result changed frozen probe lineage")
        reason_match = self.actual_primary_reason is self.expected_primary_reason
        guard_match = self.observed_guard_id == probe.expected_guard_id
        diagnostic_match = self.diagnostics.diagnostic_match
        expected_kind = (
            ProbeOutcomeKind.RAISED_UNAVAILABLE
            if probe.stage in {ProbeStage.CAPTURE, ProbeStage.PREPARE}
            else ProbeOutcomeKind.RETURNED_UNAVAILABLE
        )
        outcome_shape_match = all(
            (
                self.outcome_kind is expected_kind,
                self.actual_status
                is (
                    None
                    if expected_kind is ProbeOutcomeKind.RAISED_UNAVAILABLE
                    else CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
                ),
            )
        )
        replay_match = all(
            (
                self.outcome_kind is self.replay_outcome_kind,
                self.actual_primary_reason is self.replay_primary_reason,
                self.actual_status is self.replay_status,
                self.primary_outcome_digest == self.replay_outcome_digest,
                self.transition_id == self.replay_transition_id,
                self.result_id == self.replay_result_id,
                (self.receipt.receipt_id if self.receipt is not None else None)
                == self.replay_receipt_id,
                self.successor_capsule_id == self.replay_successor_capsule_id,
                self.successor_branch_id == self.replay_successor_branch_id,
                self.successor_state_v1_id == self.replay_successor_state_v1_id,
            )
        )
        source_unchanged = all(
            (
                self.source_runtime_fingerprint_before
                == self.source_runtime_fingerprint_after,
                self.source_provider_dispatches_before
                == self.source_provider_dispatches_after
                == 0,
            )
        )
        sibling_unchanged = all(
            (
                self.sibling_control_capsule_id != self.source_capsule_id,
                self.sibling_runtime_fingerprint_before
                == self.sibling_runtime_fingerprint_after,
                self.sibling_provider_dispatches_before
                == self.sibling_provider_dispatches_after
                == 0,
            )
        )
        production_unchanged = all(
            (
                self.production_runtime_fingerprint_before
                == self.production_runtime_fingerprint_after,
                self.production_provider_dispatches_before
                == self.production_provider_dispatches_after
                == 0,
            )
        )
        measured_dispatches = (
            self.source_provider_dispatches_after
            + self.sibling_provider_dispatches_after
            + self.production_provider_dispatches_after
        )
        if (
            self.negative_probe_dispatches != measured_dispatches
            or self.aggregate_provider_dispatches != measured_dispatches
            or self.model_calls
            != max(
                self.primary_model_calls + self.replay_model_calls,
                measured_dispatches,
            )
        ):
            raise ContractValidationError("negative call accounting is inconsistent")
        if self.receipt is None:
            receipt_match = self.outcome_kind in {
                ProbeOutcomeKind.RAISED_UNAVAILABLE,
                ProbeOutcomeKind.RETURNED_NON_RESULT,
            } and all(
                value is None
                for value in (
                    self.transition_id,
                    self.result_id,
                    self.successor_capsule_id,
                    self.successor_branch_id,
                    self.successor_state_v1_id,
                )
            )
            resource_match = receipt_match
            successor_created = False
        else:
            common_receipt_match = all(
                (
                    self.receipt.status is self.actual_status,
                    self.receipt.transition_id == self.transition_id,
                    self.receipt.receipt_id is not None,
                )
            )
            if self.outcome_kind is ProbeOutcomeKind.RETURNED_UNAVAILABLE:
                receipt_match = common_receipt_match and all(
                    (
                        self.actual_status
                        is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
                        self.receipt.unavailable_reason is self.actual_primary_reason,
                        self.receipt.successor_state_hash is None,
                        self.receipt.successor_state_v1_id is None,
                        self.receipt.branch_id is None,
                        self.successor_capsule_id is None,
                        self.successor_branch_id is None,
                        self.successor_state_v1_id is None,
                    )
                )
            else:
                receipt_match = common_receipt_match and all(
                    (
                        self.outcome_kind is ProbeOutcomeKind.RETURNED_SUCCESSOR,
                        self.actual_status
                        in {
                            CanonicalTransitionStatus.APPLIED_ACCEPTED,
                            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                        },
                        self.receipt.unavailable_reason is None,
                        self.receipt.branch_id == self.successor_branch_id,
                        self.receipt.successor_state_v1_id
                        == self.successor_state_v1_id,
                        self.successor_capsule_id is not None,
                        self.successor_branch_id is not None,
                        self.successor_state_v1_id is not None,
                    )
                )
            resource_match = all(
                (
                    (
                        self.receipt.new_execution_usage
                        == NewExecutionUsage.not_applied()
                        and self.receipt.budget_before == self.receipt.budget_after
                    )
                    if self.outcome_kind is ProbeOutcomeKind.RETURNED_UNAVAILABLE
                    else self.receipt.new_execution_usage.applied,
                )
            )
            successor_created = self.outcome_kind is ProbeOutcomeKind.RETURNED_SUCCESSOR
        expected_flags = {
            "primary_reason_match": reason_match,
            "guard_match": guard_match,
            "diagnostic_match": diagnostic_match,
            "outcome_shape_match": outcome_shape_match,
            "replay_match": replay_match,
            "source_unchanged": source_unchanged,
            "sibling_unchanged": sibling_unchanged,
            "production_unchanged": production_unchanged,
            "receipt_match": receipt_match,
            "resource_accounting_match": resource_match,
            "successor_created": successor_created,
        }
        for name, expected in expected_flags.items():
            if getattr(self, name) is not expected:
                raise ContractValidationError(f"inconsistent v2 unavailable evidence: {name}")
        payload = self.model_dump(mode="json", exclude={"case_result_id"})
        expected_id = stable_contract_id("cedunavailablecasev2", payload)
        if self.case_result_id is not None and self.case_result_id != expected_id:
            raise ContractValidationError("v2 unavailable case-result ID mismatch")
        object.__setattr__(self, "case_result_id", expected_id)
        return self

    @property
    def unavailable_passed(self) -> bool:
        return all(
            (
                self.primary_reason_match,
                self.guard_match,
                self.diagnostic_match,
                self.outcome_shape_match,
                self.replay_match,
                self.source_unchanged,
                self.sibling_unchanged,
                self.production_unchanged,
                self.receipt_match,
                self.resource_accounting_match,
                not self.successor_created,
                self.negative_probe_dispatches == 0,
                self.aggregate_provider_dispatches == 0,
                self.live_calls == 0,
                self.model_calls == 0,
                self.tool_calls == 0,
            )
        )


class CanonicalSuccessorProbeEvaluationFailureV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PROBE_EVALUATION_FAILURE_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PROBE_EVALUATION_FAILURE_VERSION_V2
    case_result_id: Optional[str] = None
    probe_id: str
    probe_fingerprint: str = Field(pattern=_HEX64)
    probe_class: ProbeClass
    stage: ProbeStage
    failure_code: ProbeEvaluationFailureCode
    exception_type: str
    operation_invoked: bool
    construction_evidence: Optional[CanonicalSuccessorProbeConstructionEvidenceV2] = None
    source_capsule_id: Optional[str] = None
    source_runtime_fingerprint_before: Optional[str] = Field(default=None, pattern=_HEX64)
    source_runtime_fingerprint_after: Optional[str] = Field(default=None, pattern=_HEX64)
    source_provider_dispatches_before: int = Field(default=0, ge=0, strict=True)
    source_provider_dispatches_after: int = Field(default=0, ge=0, strict=True)
    sibling_control_capsule_id: Optional[str] = None
    sibling_runtime_fingerprint_before: Optional[str] = Field(default=None, pattern=_HEX64)
    sibling_runtime_fingerprint_after: Optional[str] = Field(default=None, pattern=_HEX64)
    sibling_provider_dispatches_before: int = Field(default=0, ge=0, strict=True)
    sibling_provider_dispatches_after: int = Field(default=0, ge=0, strict=True)
    production_control_capsule_id: Optional[str] = None
    production_runtime_fingerprint_before: Optional[str] = Field(default=None, pattern=_HEX64)
    production_runtime_fingerprint_after: Optional[str] = Field(default=None, pattern=_HEX64)
    production_provider_dispatches_before: int = Field(default=0, ge=0, strict=True)
    production_provider_dispatches_after: int = Field(default=0, ge=0, strict=True)
    successor_created: bool = False
    negative_probe_dispatches: int = Field(ge=0, strict=True)
    aggregate_provider_dispatches: int = Field(ge=0, strict=True)
    live_calls: int = Field(ge=0, strict=True)
    model_calls: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)

    _exception_nonblank = field_validator("exception_type")(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(
        self,
    ) -> "CanonicalSuccessorProbeEvaluationFailureV2":
        probe = _probe_by_id(self.probe_id)
        if (
            self.probe_fingerprint != probe.probe_fingerprint
            or self.probe_class is not probe.probe_class
            or self.stage is not probe.stage
        ):
            raise ContractValidationError("probe evaluation failure lineage changed")
        if self.construction_evidence is not None:
            if self.construction_evidence.probe_id != self.probe_id:
                raise ContractValidationError("failure construction evidence is unlinked")
            if (
                self.failure_code
                in {
                    ProbeEvaluationFailureCode.INVALID_PROBE_CONSTRUCTION,
                    ProbeEvaluationFailureCode.GROUND_TRUTH_FIREWALL_FAILED,
                }
                and self.construction_evidence.validity_gate_passed
            ):
                raise ContractValidationError("valid construction cannot be a gate failure")
        measured_dispatches = (
            self.source_provider_dispatches_after
            + self.sibling_provider_dispatches_after
            + self.production_provider_dispatches_after
        )
        if (
            self.negative_probe_dispatches != measured_dispatches
            or self.aggregate_provider_dispatches != measured_dispatches
            or self.model_calls < measured_dispatches
        ):
            raise ContractValidationError("probe-failure call accounting is inconsistent")
        payload = self.model_dump(mode="json", exclude={"case_result_id"})
        expected = stable_contract_id("cedprobeevaluationfailurev2", payload)
        if self.case_result_id is not None and self.case_result_id != expected:
            raise ContractValidationError("probe evaluation failure ID mismatch")
        object.__setattr__(self, "case_result_id", expected)
        return self

    @property
    def unavailable_passed(self) -> bool:
        return False


CanonicalSuccessorUnavailableEvidenceV2 = Union[
    CanonicalSuccessorUnavailableCaseResultV2,
    CanonicalSuccessorProbeEvaluationFailureV2,
]


class CanonicalSuccessorParityMetricsV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION_V2
    cases_total: int = Field(ge=0, strict=True)
    supported_authoritative_cases: int = Field(ge=0, strict=True)
    accepted_reference_cases: int = Field(ge=0, strict=True)
    canonical_rejection_reference_cases: int = Field(ge=0, strict=True)
    orthogonal_negative_cases: int = Field(ge=0, strict=True)
    precedence_negative_cases: int = Field(ge=0, strict=True)
    accepted_parity: int = Field(ge=0, strict=True)
    canonical_rejection_parity: int = Field(ge=0, strict=True)
    orthogonal_primary_classifications: int = Field(ge=0, strict=True)
    precedence_primary_classifications: int = Field(ge=0, strict=True)
    evaluation_failures: int = Field(ge=0, strict=True)
    validity_gate_failures: int = Field(ge=0, strict=True)
    invariant_vector_mismatches: int = Field(ge=0, strict=True)
    literal_mutation_mismatches: int = Field(ge=0, strict=True)
    ground_truth_firewall_failures: int = Field(ge=0, strict=True)
    primary_classification_mismatches: int = Field(ge=0, strict=True)
    guard_precedence_mismatches: int = Field(ge=0, strict=True)
    diagnostic_mismatches: int = Field(ge=0, strict=True)
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
    source_isolation_failures: int = Field(ge=0, strict=True)
    sibling_isolation_failures: int = Field(ge=0, strict=True)
    production_mutations: int = Field(ge=0, strict=True)
    receipt_mismatches: int = Field(ge=0, strict=True)
    resource_accounting_mismatches: int = Field(ge=0, strict=True)
    value_v1_compatibility_mismatches: int = Field(ge=0, strict=True)
    idempotence_failures: int = Field(ge=0, strict=True)
    negative_successors_created: int = Field(ge=0, strict=True)
    fabricated_observations: int = Field(ge=0, strict=True)
    future_label_violations: int = Field(ge=0, strict=True)
    historical_offline_fixture_dispatches: int = Field(ge=0, strict=True)
    negative_probe_dispatches: int = Field(ge=0, strict=True)
    aggregate_provider_dispatches: int = Field(ge=0, strict=True)
    live_calls: int = Field(ge=0, strict=True)
    model_calls: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)
    core_lock_mismatches: int = Field(ge=0, strict=True)
    predecessor_lock_mismatches: int = Field(ge=0, strict=True)


class CanonicalSuccessorParityThresholdsV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION_V2
    thresholds_id: Optional[str] = None
    cases_total: Literal[23] = 23
    supported_authoritative_cases: Literal[5] = 5
    accepted_reference_cases: Literal[1] = 1
    canonical_rejection_reference_cases: Literal[4] = 4
    orthogonal_negative_cases: Literal[11] = 11
    precedence_negative_cases: Literal[7] = 7
    required_supported_parity: Literal[5] = 5
    required_accepted_parity: Literal[1] = 1
    required_canonical_rejection_parity: Literal[4] = 4
    required_orthogonal_primary_classifications: Literal[11] = 11
    required_precedence_primary_classifications: Literal[7] = 7
    required_historical_offline_fixture_dispatches: Literal[5] = 5
    maximum_mismatch_or_failure_count: Literal[0] = 0
    required_negative_probe_dispatches: Literal[0] = 0
    required_aggregate_provider_dispatches: Literal[0] = 0
    required_live_calls: Literal[0] = 0
    required_model_calls: Literal[0] = 0
    required_tool_calls: Literal[0] = 0
    depth: Literal[1] = 1
    recursive_successor: Literal[False] = False

    @model_validator(mode="after")
    def identify(self) -> "CanonicalSuccessorParityThresholdsV2":
        payload = self.model_dump(mode="json", exclude={"thresholds_id"})
        expected = stable_contract_id("cedparitythresholdsv2", payload)
        if self.thresholds_id is not None and self.thresholds_id != expected:
            raise ContractValidationError("v2 thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self

    def supports(self, metrics: CanonicalSuccessorParityMetricsV2) -> bool:
        mismatches = (
            metrics.evaluation_failures,
            metrics.validity_gate_failures,
            metrics.invariant_vector_mismatches,
            metrics.literal_mutation_mismatches,
            metrics.ground_truth_firewall_failures,
            metrics.primary_classification_mismatches,
            metrics.guard_precedence_mismatches,
            metrics.diagnostic_mismatches,
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
            metrics.source_isolation_failures,
            metrics.sibling_isolation_failures,
            metrics.production_mutations,
            metrics.receipt_mismatches,
            metrics.resource_accounting_mismatches,
            metrics.value_v1_compatibility_mismatches,
            metrics.idempotence_failures,
            metrics.negative_successors_created,
            metrics.fabricated_observations,
            metrics.future_label_violations,
            metrics.core_lock_mismatches,
            metrics.predecessor_lock_mismatches,
        )
        return all(
            (
                metrics.cases_total == self.cases_total,
                metrics.supported_authoritative_cases
                == self.supported_authoritative_cases,
                metrics.accepted_reference_cases == self.accepted_reference_cases,
                metrics.canonical_rejection_reference_cases
                == self.canonical_rejection_reference_cases,
                metrics.orthogonal_negative_cases == self.orthogonal_negative_cases,
                metrics.precedence_negative_cases == self.precedence_negative_cases,
                metrics.accepted_parity == self.required_accepted_parity,
                metrics.canonical_rejection_parity
                == self.required_canonical_rejection_parity,
                metrics.accepted_parity + metrics.canonical_rejection_parity
                == self.required_supported_parity,
                metrics.orthogonal_primary_classifications
                == self.required_orthogonal_primary_classifications,
                metrics.precedence_primary_classifications
                == self.required_precedence_primary_classifications,
                metrics.historical_offline_fixture_dispatches
                == self.required_historical_offline_fixture_dispatches,
                not any(mismatches),
                metrics.negative_probe_dispatches
                == self.required_negative_probe_dispatches,
                metrics.aggregate_provider_dispatches
                == self.required_aggregate_provider_dispatches,
                metrics.live_calls == self.required_live_calls,
                metrics.model_calls == self.required_model_calls,
                metrics.tool_calls == self.required_tool_calls,
            )
        )


FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2 = (
    CanonicalSuccessorParityThresholdsV2()
)


CanonicalSuccessorParityEvidenceV1 = Union[
    V1CanonicalSuccessorParityCaseResult,
    V1CanonicalSuccessorParityEvaluationFailure,
]


class CanonicalSuccessorParityArtifactV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION_V2
    artifact_id: Optional[str] = None
    harness_id: Literal[
        CANONICAL_SUCCESSOR_PARITY_HARNESS_ID_V2
    ] = CANONICAL_SUCCESSOR_PARITY_HARNESS_ID_V2
    environment_id: Literal[CANONICAL_SUCCESSOR_ENV_ID] = CANONICAL_SUCCESSOR_ENV_ID
    branch_capsule_id: Literal[
        CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION
    ] = CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION
    pending_transition_id: Literal[
        PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION
    ] = PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION
    task_semantic_identity_id: Literal[
        CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION
    ] = CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION
    recorded_observation_id: Literal[
        RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
    ] = RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
    transition_result_id: Literal[
        CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION
    ] = CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION
    transition_receipt_id: Literal[
        CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION
    ] = CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION
    recording_contract_id: Literal[
        CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID
    ] = CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID
    capture_manifest_schema_id: Literal[
        CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION
    capture_manifest_id: str
    supported_action_family: Literal[SUPPORTED_ACTION_FAMILY] = SUPPORTED_ACTION_FAMILY
    parity_definition_id: Literal[
        CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID
    ] = CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID
    canonical_transition_owner: Literal[
        CANONICAL_TRANSITION_OWNER
    ] = CANONICAL_TRANSITION_OWNER
    canonical_processor_ids: Tuple[str, ...] = CANONICAL_PROCESSOR_IDS
    core_lock: CanonicalSuccessorCoreBlobLockV2
    core_lock_id: str
    predecessor_artifact_id: Literal[SEALED_PHASE8_ARTIFACT_ID] = SEALED_PHASE8_ARTIFACT_ID
    predecessor_artifact_sha256: Literal[
        SEALED_PHASE8_ARTIFACT_SHA256
    ] = SEALED_PHASE8_ARTIFACT_SHA256
    predecessor_artifact_commit: Literal[
        SEALED_PHASE8_ARTIFACT_COMMIT
    ] = SEALED_PHASE8_ARTIFACT_COMMIT
    predecessor_status: Literal["FALSIFIED"] = "FALSIFIED"
    change_rationale: Literal[V2_CHANGE_RATIONALE] = V2_CHANGE_RATIONALE
    validation_order_id: str
    failure_taxonomy_id: str
    failure_precedence_id: str
    compatibility_diagnostics_id: str
    probe_design_id: str
    case_set_id: str
    case_set: CanonicalSuccessorParityCaseSetV2
    corpus_id: str
    corpus_canonical_sha256: str = Field(pattern=_HEX64)
    thresholds_id: str
    thresholds: CanonicalSuccessorParityThresholdsV2
    parity_cases: Tuple[CanonicalSuccessorParityEvidenceV1, ...]
    orthogonal_cases: Tuple[CanonicalSuccessorUnavailableEvidenceV2, ...]
    precedence_cases: Tuple[CanonicalSuccessorUnavailableEvidenceV2, ...]
    metrics: CanonicalSuccessorParityMetricsV2
    depth: Literal[1] = 1
    recursive_successor: Literal[False] = False
    production_authority: Literal["none"] = "none"
    hypothesis_status: Literal["SUPPORTED", "FALSIFIED"]

    @model_validator(mode="after")
    def validate_evidence_and_identify(self) -> "CanonicalSuccessorParityArtifactV2":
        parity = tuple(sorted(self.parity_cases, key=lambda item: item.case_name))
        orthogonal = tuple(sorted(self.orthogonal_cases, key=lambda item: item.probe_id))
        precedence = tuple(sorted(self.precedence_cases, key=lambda item: item.probe_id))
        object.__setattr__(self, "parity_cases", parity)
        object.__setattr__(self, "orthogonal_cases", orthogonal)
        object.__setattr__(self, "precedence_cases", precedence)
        expected_lineage = all(
            (
                self.capture_manifest_id
                == FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.manifest_id,
                self.core_lock == FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2,
                self.core_lock_id == self.core_lock.lock_id,
                self.validation_order_id
                == FROZEN_CANONICAL_VALIDATION_ORDER_V2.validation_order_id,
                self.failure_taxonomy_id
                == FROZEN_CANONICAL_FAILURE_TAXONOMY_V1.taxonomy_id,
                self.failure_precedence_id
                == FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1.precedence_id,
                self.compatibility_diagnostics_id
                == FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.diagnostics_id,
                self.probe_design_id
                == FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.probe_design_id,
                self.case_set == FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2,
                self.case_set_id == self.case_set.case_set_id,
                self.corpus_id == FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2.corpus_id,
                self.corpus_canonical_sha256 == frozen_corpus_v2_canonical_sha256(),
                self.thresholds == FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2,
                self.thresholds_id == self.thresholds.thresholds_id,
                tuple(self.canonical_processor_ids) == tuple(sorted(CANONICAL_PROCESSOR_IDS)),
            )
        )
        if not expected_lineage:
            raise ContractValidationError("v2 artifact frozen lineage changed")
        if (
            len(parity) != 5
            or {item.case_name for item in parity}
            != set(FROZEN_SUPPORTED_CASE_ORDER_V2)
            or len(orthogonal) != 11
            or {item.probe_id for item in orthogonal} != set(ORTHOGONAL_PROBE_IDS)
            or any(item.probe_class is not ProbeClass.ORTHOGONAL for item in orthogonal)
            or len(precedence) != 7
            or {item.probe_id for item in precedence} != set(PRECEDENCE_PROBE_IDS)
            or any(item.probe_class is not ProbeClass.PRECEDENCE for item in precedence)
        ):
            raise ContractValidationError("v2 artifact case membership changed")
        expected_metrics = _calculate_metrics_v2(parity, orthogonal, precedence)
        if self.metrics != expected_metrics:
            raise ContractValidationError("v2 artifact metrics do not match evidence")
        supported = self.thresholds.supports(expected_metrics)
        if self.hypothesis_status != ("SUPPORTED" if supported else "FALSIFIED"):
            raise ContractValidationError("v2 artifact hypothesis status is inconsistent")
        payload = self.model_dump(mode="json", exclude={"artifact_id"})
        expected_id = stable_contract_id("cedparityartifactv2", payload)
        if self.artifact_id is not None and self.artifact_id != expected_id:
            raise ContractValidationError("v2 parity artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected_id)
        return self


class CanonicalSuccessorParityReplayLockV2(_FrozenV2Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION_V2
    ] = CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION_V2
    replay_lock_id: Optional[str] = None
    authoritative_artifact_id: str
    replay_artifact_id: str
    authoritative_sha256: str = Field(pattern=_HEX64)
    replay_sha256: str = Field(pattern=_HEX64)
    authoritative_supported_order: Tuple[str, ...] = FROZEN_SUPPORTED_CASE_ORDER_V2
    authoritative_orthogonal_order: Tuple[str, ...] = FROZEN_ORTHOGONAL_PROBE_ORDER_V2
    authoritative_precedence_order: Tuple[str, ...] = FROZEN_PRECEDENCE_PROBE_ORDER_V2
    replay_supported_order: Tuple[str, ...] = FROZEN_REPLAY_SUPPORTED_CASE_ORDER_V2
    replay_orthogonal_order: Tuple[str, ...] = FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V2
    replay_precedence_order: Tuple[str, ...] = FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V2
    semantic_equality: Literal[True] = True
    artifact_id_equality: Literal[True] = True
    byte_identity: Literal[True] = True

    _artifact_ids_nonblank = field_validator(
        "authoritative_artifact_id",
        "replay_artifact_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "CanonicalSuccessorParityReplayLockV2":
        if (
            self.authoritative_supported_order != FROZEN_SUPPORTED_CASE_ORDER_V2
            or self.authoritative_orthogonal_order
            != FROZEN_ORTHOGONAL_PROBE_ORDER_V2
            or self.authoritative_precedence_order
            != FROZEN_PRECEDENCE_PROBE_ORDER_V2
            or self.replay_supported_order
            != FROZEN_REPLAY_SUPPORTED_CASE_ORDER_V2
            or self.replay_orthogonal_order
            != FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V2
            or self.replay_precedence_order
            != FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V2
            or self.replay_supported_order
            != tuple(reversed(self.authoritative_supported_order))
            or self.replay_orthogonal_order
            != tuple(reversed(self.authoritative_orthogonal_order))
            or self.replay_precedence_order
            != tuple(reversed(self.authoritative_precedence_order))
            or self.authoritative_artifact_id != self.replay_artifact_id
            or self.authoritative_sha256 != self.replay_sha256
        ):
            raise ContractValidationError("v2 independent replay did not lock")
        payload = self.model_dump(mode="json", exclude={"replay_lock_id"})
        expected = stable_contract_id("cedparityreplaylockv2", payload)
        if self.replay_lock_id is not None and self.replay_lock_id != expected:
            raise ContractValidationError("v2 replay-lock ID mismatch")
        object.__setattr__(self, "replay_lock_id", expected)
        return self


@dataclass(frozen=True)
class _ProbeExecutionV2:
    probe_id: str
    invocation_stage: ProbeStage
    operation: Callable[[], object]
    source_ced: CEDOrchestrator
    source_adapters: Tuple[object, ...]
    source_capsule: CanonicalBranchCapsule
    reference_snapshot: CanonicalSuccessorProbeComponentSnapshotV2
    candidate_snapshot: CanonicalSuccessorProbeComponentSnapshotV2
    literal_values: Tuple[Tuple[str, str, str, bool], ...]
    observation_submission: ObservationSubmissionState
    target_capsule: Optional[CanonicalBranchCapsule]
    target_pending: Optional[PendingCanonicalTransition]
    target_action: LegalAction
    target_observation: object
    manifest_reference_observation: RecordedCanonicalObservation


@dataclass(frozen=True)
class _ProbeInvocationOutcomeV2:
    kind: ProbeOutcomeKind
    reason: Optional[SuccessorUnavailableReason]
    status: Optional[CanonicalTransitionStatus]
    result: Optional[CanonicalTransitionResult]
    outcome_digest: str


def _budget_v2(**updates: int) -> SearchBudget:
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


def _provider_dispatches_v2(adapters: Iterable[object]) -> int:
    return sum(int(getattr(adapter, "generate_calls", 0)) for adapter in adapters)


def _live_calls_v2(adapters: Iterable[object]) -> int:
    return sum(
        int(getattr(adapter, "generate_calls", 0))
        for adapter in adapters
        if not isinstance(adapter, CanonicalSuccessorRecordingProvider)
    )


def _tool_calls_v2(results: Iterable[Optional[CanonicalTransitionResult]]) -> int:
    return sum(
        result.receipt.new_execution_usage.budget_delta.tool_calls
        for result in results
        if result is not None
    )


def _build_probe_root_v2(
    case: AuthoritativeRecordedObservationCase,
    *,
    question: Optional[str] = None,
    agent_ids: Tuple[str, ...] = CANONICAL_RECORDING_AGENT_IDS,
    provider_models: Tuple[Tuple[str, str], ...] = CANONICAL_RECORDING_PROVIDER_MODELS,
    provider_timeout_seconds: Optional[float] = None,
) -> Tuple[CEDOrchestrator, object, Tuple[CanonicalSuccessorRecordingProvider, ...]]:
    """Build a metadata-only root.  Its recording adapters are never dispatched."""

    provider = FakeProvider()
    registry_kwargs: Dict[str, object] = {}
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
    state = ced.create_session(
        question if question is not None else case.recorded_question,
        session_id=case.recorded_session_id,
    )
    _normalize_v1_root_audit_clock(state)
    return ced, state, adapters


def _capture_probe_root_v2(
    case: AuthoritativeRecordedObservationCase,
    *,
    budget: Optional[SearchBudget] = None,
    usage: Optional[BudgetUsage] = None,
    question: Optional[str] = None,
    agent_ids: Tuple[str, ...] = CANONICAL_RECORDING_AGENT_IDS,
    provider_models: Tuple[Tuple[str, str], ...] = CANONICAL_RECORDING_PROVIDER_MODELS,
    provider_timeout_seconds: Optional[float] = None,
) -> Tuple[
    CanonicalSuccessorEnvironmentV0,
    CEDOrchestrator,
    object,
    Tuple[CanonicalSuccessorRecordingProvider, ...],
    CanonicalBranchCapsule,
    PendingCanonicalTransition,
]:
    selected_budget = budget or _budget_v2()
    selected_usage = usage or BudgetUsage(nodes=1)
    ced, state, adapters = _build_probe_root_v2(
        case,
        question=question,
        agent_ids=agent_ids,
        provider_models=provider_models,
        provider_timeout_seconds=provider_timeout_seconds,
    )
    env = CanonicalSuccessorEnvironmentV0()
    capsule = env.capture_capsule(
        ced,
        state,
        budget=selected_budget,
        budget_usage=selected_usage,
    )
    pending = env.prepare_transition(
        capsule,
        LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
        selected_budget,
    )
    return env, ced, state, adapters, capsule, pending


_OBSERVATION_IDENTITY_KEYS = (
    "schema_version",
    "observation_id",
    "capture_receipt_id",
    "source_capsule_id",
    "source_execution_id",
    "source_configuration_digest",
    "action_id",
    "task_identity",
    "provider_id",
    "configured_model_id",
    "actual_model_id",
    "model_config_digest",
    "transport_status",
    "transport_error_code",
    "raw_output_digest",
    "historical_usage",
    "provenance",
    "privacy_classification",
)


def _observation_mapping(value: object) -> Optional[Dict[str, object]]:
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _observation_manifest_component(
    value: object,
    *,
    absent_relation: bool = False,
) -> Optional[str]:
    if value is None:
        return _digest({"manifest_relation": "absent"}) if absent_relation else None
    mapping = _observation_mapping(value)
    if mapping is None or any(
        key not in mapping
        for key in (
            "observation_id",
            "capture_receipt_id",
            "task_identity",
            "raw_output_digest",
        )
    ):
        return None
    return _digest({key: mapping.get(key) for key in _OBSERVATION_IDENTITY_KEYS})


def _observation_payload_component(value: object) -> Optional[str]:
    if value is None:
        return None
    mapping = _observation_mapping(value)
    if mapping is None:
        return _digest({"runtime_type": type(value).__name__})
    if "raw_text" in mapping or "transport_status" in mapping:
        return _digest(
            {
                "transport_status": mapping.get("transport_status"),
                "transport_error_code": mapping.get("transport_error_code"),
                "raw_text": mapping.get("raw_text"),
            }
        )
    return _digest(mapping)


def _future_fields(value: object) -> Tuple[str, ...]:
    forbidden_names = {
        "accepted_move_id",
        "branch_id",
        "canonical_rejection_reason",
        "canonical_transition_status",
        "evaluation_result",
        "final_answer",
        "is_terminal",
        "label",
        "next_state",
        "outcome",
        "rejection_reason",
        "result",
        "resulting_move_id",
        "reward",
        "successor",
        "successor_capsule",
        "successor_search_state_v1",
        "successor_state",
        "successor_state_v1_id",
        "terminal_status",
        "transition_receipt",
        "transition_result",
        "unavailable_reason",
        "verification_result",
    }
    found = set()

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if str(key) in forbidden_names:
                    found.add(str(key))
                visit(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)

    mapping = _observation_mapping(value)
    if mapping is not None:
        visit(mapping)
    return tuple(sorted(found))


def _active_binding(capsule: CanonicalBranchCapsule):
    return next(
        item
        for item in capsule.provider_bindings
        if item.agent_id == capsule.canonical_task.agent_id
    )


def _component_snapshot_v2(
    *,
    capsule: Optional[CanonicalBranchCapsule],
    pending: Optional[PendingCanonicalTransition],
    action: LegalAction,
    observation: object,
    absent_observation_relation: bool = False,
    root_identity_override: Optional[str] = None,
    preserved_fallback: Optional[CanonicalSuccessorProbeComponentSnapshotV2] = None,
) -> CanonicalSuccessorProbeComponentSnapshotV2:
    if capsule is None:
        if preserved_fallback is None:
            raise ContractValidationError("a capsule-free snapshot requires measured fallback")
        return preserved_fallback.model_copy(
            update={
                "root_identity": root_identity_override,
                "capsule_identity": None,
                "pending_identity": None,
                "lineage_binding": None,
            }
        )
    binding = _active_binding(capsule)
    roster = tuple(sorted({item.provider_id for item in capsule.provider_bindings}))
    return CanonicalSuccessorProbeComponentSnapshotV2(
        root_identity=root_identity_override or _digest(
            {
                "source_execution_id": capsule.source_execution_id,
                "search_state_v1_id": capsule.search_state_v1_id,
            }
        ),
        capsule_identity=_digest({"capsule_id": capsule.capsule_id}),
        pending_identity=(
            _digest({"transition_id": pending.transition_id})
            if pending is not None
            else None
        ),
        task_semantic_identity=_digest(
            {"task_identity_id": capsule.canonical_task.task_identity_id}
        ),
        public_context_digest=_digest(
            {"context_digest": capsule.canonical_task.context_digest}
        ),
        council_roster_digest=_digest({"public_provider_ids": roster}),
        action_identity=_digest({"action_id": action.action_id}),
        observation_manifest_identity=_observation_manifest_component(
            observation,
            absent_relation=absent_observation_relation,
        ),
        observation_payload_digest=_observation_payload_component(observation),
        provider_binding=_digest({"active_provider_id": binding.provider_id}),
        exact_model_binding=_digest({"active_exact_model_id": binding.model_id}),
        configuration_binding=_digest(
            {
                "source_configuration_digest": capsule.configuration_digest,
                "task_model_config_digest": capsule.canonical_task.model_config_digest,
            }
        ),
        lineage_binding=_digest(
            {
                "source_execution_id": capsule.source_execution_id,
                "branch_id": capsule.branch_id,
            }
        ),
        future_label_status=_digest({"forbidden_fields": _future_fields(observation)}),
        budget_status=_digest(
            {
                "budget": capsule.budget.model_dump(mode="json"),
                "usage": capsule.budget_usage.model_dump(mode="json"),
            }
        ),
    )


def _literal_values(
    *items: Tuple[str, object, object]
) -> Tuple[Tuple[str, str, str, bool], ...]:
    return tuple(
        (path, canonical_json(before), canonical_json(after), True)
        for path, before, after in items
    )


def _literal_mutations_match(
    probe: CanonicalSuccessorProbeV2,
    actual: Tuple[Tuple[str, str, str, bool], ...],
) -> bool:
    expected = tuple(
        (
            item.path,
            item.before_json,
            item.after_json,
            item.independent_authoritative_input,
        )
        for item in probe.literal_mutations
    )
    return actual == expected


def _ground_truth_firewall_passed(operation: Callable[[], object]) -> bool:
    forbidden_types = (
        CanonicalSuccessorProbeV2,
        ProbeInvariantVector,
        GuardEvaluation,
        ProbeClass,
        GuardEvaluationState,
        ProbeOutcomeKind,
        ProbeEvaluationFailureCode,
        CanonicalTransitionStatus,
        SuccessorUnavailableReason,
        AuthoritativeRecordedObservationCase,
    )
    banned_names = {
        "probe",
        "expected",
        "expected_reason",
        "expected_result",
        "invariant_vector",
        "guard_evaluations",
        "literal_mutations",
    }
    allowed_runtime_expected_names = {
        "expected_provider_id",
        "expected_model_id",
    }
    forbidden_strings = {
        *(item.value for item in SuccessorUnavailableReason),
        *(item.value for item in ProbeClass),
        *(item.value for item in InvariantState),
        *(item.value for item in GuardEvaluationState),
        *(item.value for item in ObservationSubmissionState),
        *(item.value for item in ProbeStage),
        *(item.value for item in ProbeOutcomeKind),
        *(item.value for item in ProbeEvaluationFailureCode),
        *(item.value for item in CanonicalTransitionStatus),
        *(step.guard_id for step in FROZEN_CANONICAL_VALIDATION_ORDER_V2.steps),
    }
    visited: set[int] = set()

    def banned_name(value: object) -> bool:
        name = str(value)
        return name in banned_names or (
            name.startswith("expected_")
            and name not in allowed_runtime_expected_names
        )

    def forbidden(value: object) -> bool:
        if isinstance(value, forbidden_types):
            return True
        if isinstance(value, str) and value in forbidden_strings:
            return True
        if value is None or isinstance(value, (str, bytes, int, float, bool)):
            return False
        identity = id(value)
        if identity in visited:
            return False
        visited.add(identity)
        if isinstance(value, Mapping):
            return any(
                banned_name(key) or forbidden(key) or forbidden(nested)
                for key, nested in value.items()
            )
        if isinstance(value, (tuple, list, set, frozenset)):
            return any(forbidden(item) for item in value)
        if isinstance(value, BaseModel):
            return forbidden(value.model_dump(mode="json"))
        if is_dataclass(value) and not isinstance(value, type):
            return any(
                banned_name(item.name) or forbidden(getattr(value, item.name))
                for item in dataclass_fields(value)
            )
        if inspect.isfunction(value) or inspect.ismethod(value):
            try:
                nested_parameter_names = tuple(inspect.signature(value).parameters)
                nested_closure = inspect.getclosurevars(value)
            except (TypeError, ValueError):
                return True
            if any(banned_name(name) for name in nested_parameter_names):
                return True
            nested_defaults = tuple(getattr(value, "__defaults__", ()) or ())
            nested_keyword_defaults = tuple(
                (getattr(value, "__kwdefaults__", {}) or {}).values()
            )
            if any(
                forbidden(item)
                for item in nested_defaults + nested_keyword_defaults
            ):
                return True
            if any(banned_name(name) for name in nested_closure.nonlocals):
                return True
            if any(forbidden(item) for item in nested_closure.nonlocals.values()):
                return True
            if any(banned_name(name) for name in nested_closure.globals):
                return True
            if any(forbidden(item) for item in nested_closure.globals.values()):
                return True
        slot_names = set()
        for base in type(value).__mro__:
            declared = base.__dict__.get("__slots__", ())
            if isinstance(declared, str):
                declared = (declared,)
            slot_names.update(str(name) for name in declared)
        for name in slot_names - {"__dict__", "__weakref__"}:
            if banned_name(name):
                return True
            try:
                nested = getattr(value, name)
            except AttributeError:
                continue
            if forbidden(nested):
                return True
        try:
            attributes = vars(value)
        except TypeError:
            return True
        return any(
            banned_name(name) or forbidden(nested)
            for name, nested in attributes.items()
        )

    try:
        closure = inspect.getclosurevars(operation)
    except (TypeError, ValueError):
        return False
    try:
        parameter_names = tuple(inspect.signature(operation).parameters)
    except (TypeError, ValueError):
        return False
    if any(
        banned_name(name)
        for name in parameter_names
    ):
        return False
    if forbidden(operation):
        return False
    if any(banned_name(name) for name in closure.nonlocals):
        return False
    if any(forbidden(value) for value in closure.nonlocals.values()):
        return False
    if any(banned_name(name) for name in closure.globals):
        return False
    if any(forbidden(value) for value in closure.globals.values()):
        return False
    defaults = tuple(getattr(operation, "__defaults__", ()) or ())
    keyword_defaults = tuple((getattr(operation, "__kwdefaults__", {}) or {}).values())
    return not any(forbidden(value) for value in defaults + keyword_defaults)


def _build_probe_execution_v2(probe_id: str) -> _ProbeExecutionV2:
    """Literal construction switch; accepts no expected result or vector metadata."""

    baseline = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        _BASELINE_CASE_NAME
    )
    budget = _budget_v2()
    usage = BudgetUsage(nodes=1)
    (
        baseline_env,
        baseline_ced,
        baseline_state,
        baseline_adapters,
        baseline_capsule,
        baseline_pending,
    ) = _capture_probe_root_v2(baseline, budget=budget, usage=usage)
    baseline_observation = baseline.materialize(baseline_pending)
    if not verify_authoritative_recorded_observation(baseline_observation):
        raise ContractValidationError("baseline observation left the frozen manifest")
    baseline_action = baseline_pending.selected_action
    reference = _component_snapshot_v2(
        capsule=baseline_capsule,
        pending=baseline_pending,
        action=baseline_action,
        observation=baseline_observation,
    )

    source_ced = baseline_ced
    source_adapters: Tuple[object, ...] = tuple(baseline_adapters)
    source_capsule = baseline_capsule
    target_capsule: Optional[CanonicalBranchCapsule] = baseline_capsule
    target_pending: Optional[PendingCanonicalTransition] = baseline_pending
    target_action = baseline_action
    target_observation: object = baseline_observation
    submission = ObservationSubmissionState.SUBMITTED

    invocation_stage = ProbeStage.APPLY
    if probe_id == "p8v2-o01-invalid-root-registration":
        invocation_stage = ProbeStage.CAPTURE
        detached_state = baseline_state.model_copy(deep=True)
        operation = lambda: baseline_env.capture_capsule(
            baseline_ced,
            detached_state,
            budget=budget,
            budget_usage=usage,
        )
        target_capsule = None
        target_pending = None
        submission = ObservationSubmissionState.NOT_APPLICABLE
        candidate = _component_snapshot_v2(
            capsule=None,
            pending=None,
            action=target_action,
            observation=target_observation,
            root_identity_override=_digest(
                {
                    "registration": "detached_deep_copy",
                    "session_id": detached_state.session_id,
                }
            ),
            preserved_fallback=reference,
        )
        literals = _literal_values(
            (
                "root.object_registration",
                "registered_canonical_object",
                "detached_deep_copy",
            )
        )
    elif probe_id == "p8v2-o02-illegal-action-capability":
        invocation_stage = ProbeStage.PREPARE
        target_action = LegalAction(
            kind=ActionKind.ASK_SOCRATIC_QUESTION,
            required_capabilities=("not-present-in-root",),
        )
        target_pending = None
        submission = ObservationSubmissionState.NOT_APPLICABLE
        operation = lambda: baseline_env.prepare_transition(
            baseline_capsule,
            target_action,
            budget,
        )
        candidate = _component_snapshot_v2(
            capsule=baseline_capsule,
            pending=None,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            (
                "action.required_capabilities",
                [],
                ["not-present-in-root"],
            )
        )
    elif probe_id == "p8v2-o03-missing-observation":
        target_observation = None
        submission = ObservationSubmissionState.NOT_SUBMITTED
        operation = lambda: baseline_env.apply_observation(
            baseline_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=baseline_capsule,
            pending=baseline_pending,
            action=target_action,
            observation=target_observation,
            absent_observation_relation=True,
        )
        literals = _literal_values(
            ("observation", "exact_manifest_observation", None)
        )
    elif probe_id == "p8v2-o04-invalid-observation-schema":
        target_observation = {
            "schema_version": RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
        }
        operation = lambda: baseline_env.apply_observation(
            baseline_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=baseline_capsule,
            pending=baseline_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            (
                "observation",
                "exact_manifest_observation",
                {"schema_version": RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION},
            )
        )
    elif probe_id == "p8v2-o05-tampered-raw-digest":
        target_observation = baseline_observation.model_copy(
            update={"raw_output_digest": "f" * 64}
        )
        operation = lambda: baseline_env.apply_observation(
            baseline_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=baseline_capsule,
            pending=baseline_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            (
                "observation.raw_output_digest",
                baseline_observation.raw_output_digest,
                "f" * 64,
            )
        )
    elif probe_id == "p8v2-o06-wrong-task-agent":
        renamed_agents = tuple(
            _RENAMED_ACTIVE_AGENT if item == _ACTIVE_AGENT else item
            for item in CANONICAL_RECORDING_AGENT_IDS
        )
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            agent_ids=renamed_agents,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("root.active_agent_id", _ACTIVE_AGENT, _RENAMED_ACTIVE_AGENT)
        )
    elif probe_id == "p8v2-o07-wrong-root-question":
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            question=_NEW_QUESTION,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(("root.question", _BASE_QUESTION, _NEW_QUESTION))
    elif probe_id == "p8v2-o08-wrong-exact-model":
        changed_models = tuple(
            (
                provider_id,
                _RENAMED_ACTIVE_MODEL if provider_id == _ACTIVE_PROVIDER else model_id,
            )
            for provider_id, model_id in CANONICAL_RECORDING_PROVIDER_MODELS
        )
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            provider_models=changed_models,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            (
                "root.active_model_id",
                "phase8-recorded-model/1",
                _RENAMED_ACTIVE_MODEL,
            )
        )
    elif probe_id == "p8v2-o09-wrong-runtime-timeout":
        baseline_timeout = CouncilProviderRegistry().provider_timeout_seconds
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            provider_timeout_seconds=31.0,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("runtime.provider_timeout_seconds", baseline_timeout, 31.0)
        )
    elif probe_id == "p8v2-o10-future-label":
        target_observation = baseline_observation.model_dump(mode="json")
        target_observation["reward"] = 1
        operation = lambda: baseline_env.apply_observation(
            baseline_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=baseline_capsule,
            pending=baseline_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(("observation.reward", None, 1))
    elif probe_id == "p8v2-o11-budget-exhausted":
        invocation_stage = ProbeStage.PREPARE
        exhausted_budget = _budget_v2(max_nodes=1)
        target_ced, target_state, target_adapters = _build_probe_root_v2(baseline)
        target_env = CanonicalSuccessorEnvironmentV0()
        target_capsule = target_env.capture_capsule(
            target_ced,
            target_state,
            budget=exhausted_budget,
            budget_usage=usage,
        )
        target_pending = None
        target_action = LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION)
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        submission = ObservationSubmissionState.NOT_APPLICABLE
        operation = lambda: target_env.prepare_transition(
            target_capsule,
            target_action,
            exhausted_budget,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=None,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(("budget.max_nodes", budget.max_nodes, 1))
    elif probe_id == "p8v2-p01-unsupported-family-vs-legality":
        invocation_stage = ProbeStage.PREPARE
        target_action = LegalAction(kind=ActionKind.RUN_ELENCHUS)
        target_pending = None
        submission = ObservationSubmissionState.NOT_APPLICABLE
        operation = lambda: baseline_env.prepare_transition(
            baseline_capsule,
            target_action,
            budget,
        )
        candidate = _component_snapshot_v2(
            capsule=baseline_capsule,
            pending=None,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("action.action_family", "OPENING", "RUN_ELENCHUS")
        )
    elif probe_id in {
        "p8v2-p02-provider-roster-context",
        "p8v2-p03-root-plus-provider",
    }:
        question = (
            _NEW_QUESTION
            if probe_id == "p8v2-p03-root-plus-provider"
            else _BASE_QUESTION
        )
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            question=question,
            provider_models=_WRONG_PROVIDER_MODELS,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        provider_literals: Tuple[Tuple[str, object, object], ...] = (
            (
                "root.provider_catalog[0].provider_id",
                CANONICAL_RECORDING_PROVIDER_MODELS[0][0],
                _WRONG_PROVIDER_MODELS[0][0],
            ),
            (
                "root.provider_catalog[1].provider_id",
                CANONICAL_RECORDING_PROVIDER_MODELS[1][0],
                _WRONG_PROVIDER_MODELS[1][0],
            ),
        )
        question_literals: Tuple[Tuple[str, object, object], ...] = (
            (("root.question", _BASE_QUESTION, _NEW_QUESTION),)
            if probe_id == "p8v2-p03-root-plus-provider"
            else ()
        )
        literals = _literal_values(*question_literals, *provider_literals)
    elif probe_id == "p8v2-p04-task-plus-model":
        renamed_agents = tuple(
            _RENAMED_ACTIVE_AGENT if item == _ACTIVE_AGENT else item
            for item in CANONICAL_RECORDING_AGENT_IDS
        )
        changed_models = tuple(
            (
                provider_id,
                _RENAMED_ACTIVE_MODEL if provider_id == _ACTIVE_PROVIDER else model_id,
            )
            for provider_id, model_id in CANONICAL_RECORDING_PROVIDER_MODELS
        )
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            agent_ids=renamed_agents,
            provider_models=changed_models,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("root.active_agent_id", _ACTIVE_AGENT, _RENAMED_ACTIVE_AGENT),
            (
                "root.active_model_id",
                "phase8-recorded-model/1",
                _RENAMED_ACTIVE_MODEL,
            ),
        )
    elif probe_id == "p8v2-p05-context-plus-tampered-digest":
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            question=_NEW_QUESTION,
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        target_observation = baseline_observation.model_copy(
            update={"raw_output_digest": "f" * 64}
        )
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("root.question", _BASE_QUESTION, _NEW_QUESTION),
            (
                "observation.raw_output_digest",
                baseline_observation.raw_output_digest,
                "f" * 64,
            ),
        )
    elif probe_id == "p8v2-p06-illegal-plus-incompatible-observation":
        invocation_stage = ProbeStage.PREPARE
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            _,
        ) = _capture_probe_root_v2(
            baseline,
            budget=budget,
            usage=usage,
            question=_NEW_QUESTION,
        )
        target_pending = None
        target_action = LegalAction(
            kind=ActionKind.ASK_SOCRATIC_QUESTION,
            required_capabilities=("not-present-in-root",),
        )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        submission = ObservationSubmissionState.NOT_SUBMITTED
        operation = lambda: target_env.prepare_transition(
            target_capsule,
            target_action,
            budget,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=None,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("root.question", _BASE_QUESTION, _NEW_QUESTION),
            (
                "action.required_capabilities",
                [],
                ["not-present-in-root"],
            ),
        )
    elif probe_id == "p8v2-p07-caller-rebinding-vs-manifest":
        other = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
            _OTHER_BINDING_CASE_NAME
        )
        (
            target_env,
            target_ced,
            _,
            target_adapters,
            target_capsule,
            target_pending,
        ) = _capture_probe_root_v2(other, budget=budget, usage=usage)
        rebound_payload = baseline_observation.model_dump(mode="python")
        rebound_payload.update(
            observation_id=None,
            source_capsule_id=target_pending.source_capsule_id,
            source_execution_id=target_pending.source_capsule.source_execution_id,
            source_configuration_digest=target_pending.source_capsule.configuration_digest,
            action_id=target_pending.selected_action.action_id,
            task_identity=target_pending.canonical_task,
            provider_id=target_pending.expected_provider_id,
            configured_model_id=target_pending.expected_model_id,
            actual_model_id=target_pending.expected_model_id,
            model_config_digest=target_pending.canonical_task.model_config_digest,
        )
        target_observation = RecordedCanonicalObservation.model_validate(rebound_payload)
        if verify_authoritative_recorded_observation(target_observation):
            raise ContractValidationError(
                "caller-rebinding probe unexpectedly entered the frozen manifest"
            )
        source_ced = target_ced
        source_adapters = tuple(target_adapters)
        source_capsule = target_capsule
        target_action = target_pending.selected_action
        operation = lambda: target_env.apply_observation(
            target_pending,
            target_observation,
        )
        candidate = _component_snapshot_v2(
            capsule=target_capsule,
            pending=target_pending,
            action=target_action,
            observation=target_observation,
        )
        literals = _literal_values(
            ("caller.binding_case", _BASELINE_CASE_NAME, _OTHER_BINDING_CASE_NAME)
        )
    else:
        raise ContractValidationError(f"unknown literal v2 probe: {probe_id}")

    return _ProbeExecutionV2(
        probe_id=probe_id,
        invocation_stage=invocation_stage,
        operation=operation,
        source_ced=source_ced,
        source_adapters=source_adapters,
        source_capsule=source_capsule,
        reference_snapshot=reference,
        candidate_snapshot=candidate,
        literal_values=literals,
        observation_submission=submission,
        target_capsule=target_capsule,
        target_pending=target_pending,
        target_action=target_action,
        target_observation=target_observation,
        manifest_reference_observation=baseline_observation,
    )


def _guard_trace_for_observed_outcome(
    observed_guard_id: Optional[str],
    *,
    stage: ProbeStage,
) -> Tuple[Tuple[GuardEvaluation, ...], Tuple[str, ...]]:
    steps = FROZEN_CANONICAL_VALIDATION_ORDER_V2.steps
    positions = {step.guard_id: index for index, step in enumerate(steps)}
    if observed_guard_id is not None and observed_guard_id not in positions:
        raise ContractValidationError("observed guard is absent from frozen order")
    target_index = positions.get(observed_guard_id)
    stage_rank = {
        ProbeStage.CAPTURE: 0,
        ProbeStage.PREPARE: 1,
        ProbeStage.APPLY: 2,
    }
    evaluations = []
    for index, step in enumerate(steps):
        if target_index is None:
            state = (
                GuardEvaluationState.EVALUATED_PASSED
                if stage_rank[step.stage] <= stage_rank[stage]
                else GuardEvaluationState.NOT_CONSTRUCTED
            )
        elif index < target_index:
            state = GuardEvaluationState.EVALUATED_PASSED
        elif index == target_index:
            state = GuardEvaluationState.EVALUATED_FAILED
        elif step.stage == steps[target_index].stage:
            state = GuardEvaluationState.NOT_EVALUATED
        else:
            state = GuardEvaluationState.NOT_CONSTRUCTED
        evaluations.append(GuardEvaluation(guard_id=step.guard_id, state=state))
    trace = tuple(evaluations)
    unreachable = tuple(
        item.guard_id
        for item in trace
        if item.state
        in {
            GuardEvaluationState.NOT_EVALUATED,
            GuardEvaluationState.NOT_CONSTRUCTED,
        }
    )
    return trace, unreachable


def _round_trips_as_observation(value: object) -> bool:
    try:
        if isinstance(value, RecordedCanonicalObservation):
            RecordedCanonicalObservation.model_validate_json(value.model_dump_json())
        else:
            RecordedCanonicalObservation.model_validate(value)
    except Exception:
        return False
    return True


def _observed_guard_id(
    execution: _ProbeExecutionV2,
    outcome: _ProbeInvocationOutcomeV2,
) -> Optional[str]:
    reason = outcome.reason
    if reason is None:
        return None
    if reason is SuccessorUnavailableReason.INVALID_ROOT:
        return {
            ProbeStage.CAPTURE: "C1",
            ProbeStage.PREPARE: "P1",
            ProbeStage.APPLY: "A1",
        }[execution.invocation_stage]
    if reason is SuccessorUnavailableReason.ILLEGAL_ACTION:
        return "P8"
    if reason is SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY:
        return "P7"
    if reason is SuccessorUnavailableReason.BUDGET_EXHAUSTED:
        return (
            "C2"
            if execution.invocation_stage is ProbeStage.CAPTURE
            else "P9"
        )
    if reason is SuccessorUnavailableReason.MISSING_OBSERVATION:
        return "A3"
    if reason is SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN:
        return "A4"
    if reason is SuccessorUnavailableReason.INVALID_OBSERVATION:
        return "A5"
    if reason is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY:
        return "A7" if _round_trips_as_observation(execution.target_observation) else "A5"
    return {
        SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH: "A8",
        SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH: "A9",
        SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH: "A10",
        SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH: "A11",
        SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH: "A12",
        SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED: "A14",
    }.get(reason)


def _compatibility_mismatch_groups(
    execution: _ProbeExecutionV2,
) -> Dict[str, Tuple[str, ...]]:
    capsule = execution.target_capsule
    observation = execution.target_observation
    if capsule is None or not isinstance(observation, RecordedCanonicalObservation):
        return {
            guard: () for guard in ("A8", "A9", "A10", "A11", "A12", "A13")
        }
    task = capsule.canonical_task
    observed = observation.task_identity
    root_values = {
        "source_session_semantic_id": (
            observed.source_session_semantic_id,
            task.source_session_semantic_id,
        ),
        "context_digest": (observed.context_digest, task.context_digest),
        "request_semantic_digest": (
            observed.request_semantic_digest,
            task.request_semantic_digest,
        ),
    }
    task_values = {
        "phase": (observed.phase, task.phase),
        "round_number": (observed.round_number, task.round_number),
        "slot_index": (observed.slot_index, task.slot_index),
        "attempt_index": (observed.attempt_index, task.attempt_index),
        "agent_id": (observed.agent_id, task.agent_id),
        "role": (observed.role, task.role),
        "task_kind": (observed.task_kind, task.task_kind),
        "task_semantic_digest": (
            observed.task_semantic_digest,
            task.task_semantic_digest,
        ),
        "action_id": (observation.action_id, execution.target_action.action_id),
    }
    binding = _active_binding(capsule)
    provider_values = {
        "provider_id": (observation.provider_id, binding.provider_id),
    }
    model_values = {
        "configured_model_id": (observation.configured_model_id, binding.model_id),
        "actual_model_id": (observation.actual_model_id, binding.model_id),
    }
    config_values = {
        "source_configuration_digest": (
            observation.source_configuration_digest,
            capsule.configuration_digest,
        ),
        "model_config_digest": (
            observation.model_config_digest,
            task.model_config_digest,
        ),
        "task_model_config_digest": (
            observed.model_config_digest,
            task.model_config_digest,
        ),
    }
    lineage_values = {
        "source_capsule_id": (observation.source_capsule_id, capsule.capsule_id),
        "source_execution_id": (
            observation.source_execution_id,
            capsule.source_execution_id,
        ),
    }

    def mismatches(values: Mapping[str, Tuple[object, object]]) -> Tuple[str, ...]:
        return tuple(sorted(name for name, pair in values.items() if pair[0] != pair[1]))

    return {
        "A8": mismatches(root_values),
        "A9": mismatches(task_values),
        "A10": mismatches(provider_values),
        "A11": mismatches(model_values),
        "A12": mismatches(config_values),
        "A13": mismatches(lineage_values),
    }


def _manifest_rebinding_mismatches(
    reference: RecordedCanonicalObservation,
    candidate: object,
) -> Tuple[str, ...]:
    if not isinstance(candidate, RecordedCanonicalObservation):
        return ()
    reference_task = reference.task_identity
    candidate_task = candidate.task_identity
    values = {
        "source_session_semantic_id": (
            reference_task.source_session_semantic_id,
            candidate_task.source_session_semantic_id,
        ),
        "context_digest": (reference_task.context_digest, candidate_task.context_digest),
        "request_semantic_digest": (
            reference_task.request_semantic_digest,
            candidate_task.request_semantic_digest,
        ),
        "agent_id": (reference_task.agent_id, candidate_task.agent_id),
        "task_semantic_digest": (
            reference_task.task_semantic_digest,
            candidate_task.task_semantic_digest,
        ),
        "provider_id": (reference.provider_id, candidate.provider_id),
        "configured_model_id": (
            reference.configured_model_id,
            candidate.configured_model_id,
        ),
        "actual_model_id": (reference.actual_model_id, candidate.actual_model_id),
        "source_configuration_digest": (
            reference.source_configuration_digest,
            candidate.source_configuration_digest,
        ),
        "model_config_digest": (
            reference.model_config_digest,
            candidate.model_config_digest,
        ),
        "task_model_config_digest": (
            reference_task.model_config_digest,
            candidate_task.model_config_digest,
        ),
        "source_capsule_id": (
            reference.source_capsule_id,
            candidate.source_capsule_id,
        ),
        "source_execution_id": (
            reference.source_execution_id,
            candidate.source_execution_id,
        ),
    }
    return tuple(sorted(name for name, pair in values.items() if pair[0] != pair[1]))


_ROOT_DIAGNOSTIC_FIELDS = frozenset(
    {"source_session_semantic_id", "context_digest", "request_semantic_digest"}
)
_TASK_DIAGNOSTIC_FIELDS = frozenset(
    {
        "phase",
        "round_number",
        "slot_index",
        "attempt_index",
        "agent_id",
        "role",
        "task_kind",
        "task_semantic_digest",
        "action_id",
    }
)
_PROVIDER_DIAGNOSTIC_FIELDS = frozenset({"provider_id"})
_MODEL_DIAGNOSTIC_FIELDS = frozenset(
    {"configured_model_id", "actual_model_id"}
)
_CONFIG_DIAGNOSTIC_FIELDS = frozenset(
    {
        "source_configuration_digest",
        "model_config_digest",
        "task_model_config_digest",
    }
)
_LINEAGE_DIAGNOSTIC_FIELDS = frozenset(
    {"source_capsule_id", "source_execution_id"}
)
_COMPATIBILITY_DIAGNOSTIC_FIELDS = (
    _ROOT_DIAGNOSTIC_FIELDS
    | _TASK_DIAGNOSTIC_FIELDS
    | _PROVIDER_DIAGNOSTIC_FIELDS
    | _MODEL_DIAGNOSTIC_FIELDS
    | _CONFIG_DIAGNOSTIC_FIELDS
    | _LINEAGE_DIAGNOSTIC_FIELDS
)


def _comparison(
    name: str,
    observed: object,
    required: object,
) -> CanonicalSuccessorDiagnosticFieldComparisonV2:
    return CanonicalSuccessorDiagnosticFieldComparisonV2(
        name=name,
        observed_digest=_digest(observed),
        required_digest=_digest(required),
    )


def _diagnostic_field_comparisons(
    execution: _ProbeExecutionV2,
) -> Tuple[CanonicalSuccessorDiagnosticFieldComparisonV2, ...]:
    pairs: Dict[str, Tuple[object, object]] = {
        "required_capabilities": (
            tuple(execution.target_action.required_capabilities),
            (),
        ),
        "action_family": (
            (
                "OPENING"
                if execution.target_action.kind is ActionKind.ASK_SOCRATIC_QUESTION
                else execution.target_action.kind.name
            ),
            "OPENING",
        ),
        "not_in_legal_set": (
            execution.target_action.action_id,
            execution.manifest_reference_observation.action_id,
        ),
        "max_nodes": (
            (
                execution.target_capsule.budget.max_nodes
                if execution.target_capsule is not None
                else _budget_v2().max_nodes
            ),
            _budget_v2().max_nodes,
        ),
        "reward": (_future_fields(execution.target_observation), ()),
        "manifest_exact_observation": (
            execution.candidate_snapshot.observation_manifest_identity,
            execution.reference_snapshot.observation_manifest_identity,
        ),
    }
    mapping = _observation_mapping(execution.target_observation)
    if mapping is not None and mapping.get("raw_text") is not None:
        raw_text = str(mapping["raw_text"])
        pairs["raw_output_digest"] = (
            mapping.get("raw_output_digest"),
            hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    capsule = execution.target_capsule
    observation = execution.target_observation
    if capsule is not None and isinstance(observation, RecordedCanonicalObservation):
        if execution.probe_id == "p8v2-p07-caller-rebinding-vs-manifest":
            required_observation = execution.manifest_reference_observation
            observed_task = observation.task_identity
            required_task = required_observation.task_identity
            pairs.update(
                {
                    "source_session_semantic_id": (
                        observed_task.source_session_semantic_id,
                        required_task.source_session_semantic_id,
                    ),
                    "context_digest": (
                        observed_task.context_digest,
                        required_task.context_digest,
                    ),
                    "request_semantic_digest": (
                        observed_task.request_semantic_digest,
                        required_task.request_semantic_digest,
                    ),
                    "phase": (observed_task.phase, required_task.phase),
                    "round_number": (
                        observed_task.round_number,
                        required_task.round_number,
                    ),
                    "slot_index": (observed_task.slot_index, required_task.slot_index),
                    "attempt_index": (
                        observed_task.attempt_index,
                        required_task.attempt_index,
                    ),
                    "agent_id": (observed_task.agent_id, required_task.agent_id),
                    "role": (observed_task.role, required_task.role),
                    "task_kind": (observed_task.task_kind, required_task.task_kind),
                    "task_semantic_digest": (
                        observed_task.task_semantic_digest,
                        required_task.task_semantic_digest,
                    ),
                    "action_id": (observation.action_id, required_observation.action_id),
                    "provider_id": (
                        observation.provider_id,
                        required_observation.provider_id,
                    ),
                    "configured_model_id": (
                        observation.configured_model_id,
                        required_observation.configured_model_id,
                    ),
                    "actual_model_id": (
                        observation.actual_model_id,
                        required_observation.actual_model_id,
                    ),
                    "source_configuration_digest": (
                        observation.source_configuration_digest,
                        required_observation.source_configuration_digest,
                    ),
                    "model_config_digest": (
                        observation.model_config_digest,
                        required_observation.model_config_digest,
                    ),
                    "task_model_config_digest": (
                        observed_task.model_config_digest,
                        required_task.model_config_digest,
                    ),
                    "source_capsule_id": (
                        observation.source_capsule_id,
                        required_observation.source_capsule_id,
                    ),
                    "source_execution_id": (
                        observation.source_execution_id,
                        required_observation.source_execution_id,
                    ),
                }
            )
        else:
            task = capsule.canonical_task
            observed_task = observation.task_identity
            binding = _active_binding(capsule)
            pairs.update(
                {
                    "source_session_semantic_id": (
                        observed_task.source_session_semantic_id,
                        task.source_session_semantic_id,
                    ),
                    "context_digest": (
                        observed_task.context_digest,
                        task.context_digest,
                    ),
                    "request_semantic_digest": (
                        observed_task.request_semantic_digest,
                        task.request_semantic_digest,
                    ),
                    "phase": (observed_task.phase, task.phase),
                    "round_number": (observed_task.round_number, task.round_number),
                    "slot_index": (observed_task.slot_index, task.slot_index),
                    "attempt_index": (
                        observed_task.attempt_index,
                        task.attempt_index,
                    ),
                    "agent_id": (observed_task.agent_id, task.agent_id),
                    "role": (observed_task.role, task.role),
                    "task_kind": (observed_task.task_kind, task.task_kind),
                    "task_semantic_digest": (
                        observed_task.task_semantic_digest,
                        task.task_semantic_digest,
                    ),
                    "action_id": (
                        observation.action_id,
                        execution.target_action.action_id,
                    ),
                    "provider_id": (observation.provider_id, binding.provider_id),
                    "configured_model_id": (
                        observation.configured_model_id,
                        binding.model_id,
                    ),
                    "actual_model_id": (
                        observation.actual_model_id,
                        binding.model_id,
                    ),
                    "source_configuration_digest": (
                        observation.source_configuration_digest,
                        capsule.configuration_digest,
                    ),
                    "model_config_digest": (
                        observation.model_config_digest,
                        task.model_config_digest,
                    ),
                    "task_model_config_digest": (
                        observed_task.model_config_digest,
                        task.model_config_digest,
                    ),
                    "source_capsule_id": (
                        observation.source_capsule_id,
                        capsule.capsule_id,
                    ),
                    "source_execution_id": (
                        observation.source_execution_id,
                        capsule.source_execution_id,
                    ),
                }
            )
    return tuple(
        _comparison(name, *pair) for name, pair in sorted(pairs.items())
    )


def _classify_diagnostic_comparisons(
    *,
    observed_guard_id: Optional[str],
    observation_submission: ObservationSubmissionState,
    comparisons: Sequence[CanonicalSuccessorDiagnosticFieldComparisonV2],
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    mismatches = {item.name for item in comparisons if item.mismatch}
    guard_fields = {
        "A8": _ROOT_DIAGNOSTIC_FIELDS,
        "A9": _TASK_DIAGNOSTIC_FIELDS,
        "A10": _PROVIDER_DIAGNOSTIC_FIELDS,
        "A11": _MODEL_DIAGNOSTIC_FIELDS,
        "A12": _CONFIG_DIAGNOSTIC_FIELDS,
        "A13": _LINEAGE_DIAGNOSTIC_FIELDS,
    }
    compatibility_order = ("A8", "A9", "A10", "A11", "A12", "A13")
    if observed_guard_id in compatibility_order:
        index = compatibility_order.index(observed_guard_id)
        primary = mismatches & guard_fields[observed_guard_id]
        later = set().union(
            *(guard_fields[guard] for guard in compatibility_order[index + 1 :])
        )
        return tuple(sorted(primary)), tuple(sorted(mismatches & later))
    if observed_guard_id == "P7":
        return (
            tuple(sorted(mismatches & {"action_family"})),
            tuple(sorted(mismatches & {"not_in_legal_set"})),
        )
    if observed_guard_id == "P8":
        advisory = (
            mismatches & _COMPATIBILITY_DIAGNOSTIC_FIELDS
            if observation_submission is ObservationSubmissionState.NOT_SUBMITTED
            else set()
        )
        return (
            tuple(sorted(mismatches & {"required_capabilities"})),
            tuple(sorted(advisory)),
        )
    if observed_guard_id == "P9":
        return tuple(sorted(mismatches & {"max_nodes"})), ()
    if observed_guard_id == "A4":
        return tuple(sorted(mismatches & {"reward"})), ()
    if observed_guard_id == "A5":
        return (
            tuple(sorted(mismatches & {"raw_output_digest"})),
            tuple(sorted(mismatches & _COMPATIBILITY_DIAGNOSTIC_FIELDS)),
        )
    if observed_guard_id == "A7":
        return (
            tuple(sorted(mismatches & {"manifest_exact_observation"})),
            tuple(sorted(mismatches & _COMPATIBILITY_DIAGNOSTIC_FIELDS)),
        )
    return (), ()


def _measured_diagnostic_fields(
    execution: _ProbeExecutionV2,
    observed_guard: Optional[str],
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    return _classify_diagnostic_comparisons(
        observed_guard_id=observed_guard,
        observation_submission=execution.observation_submission,
        comparisons=_diagnostic_field_comparisons(execution),
    )


def _observed_structured_scan(
    execution: _ProbeExecutionV2,
    observed_guard: Optional[str],
) -> bool:
    if execution.invocation_stage is not ProbeStage.APPLY:
        return False
    positions = {
        step.guard_id: index
        for index, step in enumerate(FROZEN_CANONICAL_VALIDATION_ORDER_V2.steps)
    }
    if observed_guard is None:
        return True
    return positions.get(observed_guard, -1) > positions["A6"]


def _construction_evidence_v2(
    probe: CanonicalSuccessorProbeV2,
    execution: _ProbeExecutionV2,
) -> CanonicalSuccessorProbeConstructionEvidenceV2:
    measured = _derive_invariant_vector(
        execution.probe_id,
        execution.reference_snapshot,
        execution.candidate_snapshot,
    )
    literal_match = _literal_mutations_match(probe, execution.literal_values)
    firewall = _ground_truth_firewall_passed(execution.operation)
    validity = all(
        (
            measured == probe.invariant_vector,
            literal_match,
            execution.observation_submission is probe.observation_submission,
            execution.invocation_stage is probe.stage,
            firewall,
        )
    )
    return CanonicalSuccessorProbeConstructionEvidenceV2(
        probe_id=probe.probe_id,
        probe_fingerprint=probe.probe_fingerprint,
        reference_snapshot=execution.reference_snapshot,
        candidate_snapshot=execution.candidate_snapshot,
        measured_invariant_vector=measured,
        observed_literal_mutations=execution.literal_values,
        literal_mutations_match=literal_match,
        observation_submission=execution.observation_submission,
        observed_stage=execution.invocation_stage,
        ground_truth_firewall_passed=firewall,
        validity_gate_passed=validity,
    )


def _invoke_probe_v2(operation: Callable[[], object]) -> _ProbeInvocationOutcomeV2:
    try:
        value = operation()
    except CanonicalSuccessorUnavailable as exc:
        return _ProbeInvocationOutcomeV2(
            kind=ProbeOutcomeKind.RAISED_UNAVAILABLE,
            reason=exc.reason,
            status=None,
            result=None,
            outcome_digest=_digest(
                {"kind": "exception", "reason": exc.reason.value}
            ),
        )
    if isinstance(value, CanonicalTransitionResult):
        digest, _, _ = _canonical_v1_result_evidence(value)
        successor = value.successor_capsule
        kind = (
            ProbeOutcomeKind.RETURNED_SUCCESSOR
            if successor is not None
            or value.status
            in {
                CanonicalTransitionStatus.APPLIED_ACCEPTED,
                CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
            }
            else ProbeOutcomeKind.RETURNED_UNAVAILABLE
        )
        return _ProbeInvocationOutcomeV2(
            kind=kind,
            reason=value.receipt.unavailable_reason,
            status=value.status,
            result=value,
            outcome_digest=digest,
        )
    payload = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else {"runtime_type": type(value).__name__}
    )
    return _ProbeInvocationOutcomeV2(
        kind=ProbeOutcomeKind.RETURNED_NON_RESULT,
        reason=None,
        status=None,
        result=None,
        outcome_digest=_digest({"kind": "non-result", "value": payload}),
    )


def _diagnostic_evidence_v2(
    probe: CanonicalSuccessorProbeV2,
    execution: _ProbeExecutionV2,
    outcome: _ProbeInvocationOutcomeV2,
) -> CanonicalSuccessorCompatibilityDiagnosticEvidenceV1:
    observed_guard = _observed_guard_id(execution, outcome)
    comparisons = _diagnostic_field_comparisons(execution)
    primary_fields, advisory_fields = _classify_diagnostic_comparisons(
        observed_guard_id=observed_guard,
        observation_submission=execution.observation_submission,
        comparisons=comparisons,
    )
    observed_trace, observed_unreachable = _guard_trace_for_observed_outcome(
        observed_guard,
        stage=execution.invocation_stage,
    )
    positions = {
        step.guard_id: index
        for index, step in enumerate(FROZEN_CANONICAL_VALIDATION_ORDER_V2.steps)
    }
    parser_reached = (
        outcome.kind is ProbeOutcomeKind.RETURNED_SUCCESSOR
        or (
            observed_guard is None
            and execution.invocation_stage is ProbeStage.APPLY
        )
        or (
            observed_guard is not None
            and positions.get(observed_guard, -1) >= positions["A16"]
        )
    )
    ced_application_reached = (
        outcome.kind is ProbeOutcomeKind.RETURNED_SUCCESSOR
        or (
            observed_guard is None
            and execution.invocation_stage is ProbeStage.APPLY
        )
        or (
            observed_guard is not None
            and positions.get(observed_guard, -1) >= positions["A17"]
        )
    )
    immutable_inputs_digest = _digest(
        [item.model_dump(mode="json") for item in comparisons]
    )
    return CanonicalSuccessorCompatibilityDiagnosticEvidenceV1(
        diagnostics_contract_id=(
            FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.diagnostics_id or ""
        ),
        probe_id=probe.probe_id,
        observation_submission=execution.observation_submission,
        field_comparisons=comparisons,
        immutable_inputs_digest=immutable_inputs_digest,
        expected_guard_id=probe.expected_guard_id,
        observed_guard_id=observed_guard,
        expected_primary_mismatch_fields=probe.expected_primary_mismatch_fields,
        observed_primary_mismatch_fields=primary_fields,
        expected_advisory_or_dominated_mismatch_fields=(
            probe.advisory_or_dominated_mismatch_fields
        ),
        observed_advisory_or_dominated_mismatch_fields=advisory_fields,
        expected_guard_evaluations=probe.guard_evaluations,
        observed_guard_evaluations=observed_trace,
        expected_unreachable_guard_ids=probe.unreachable_guard_ids,
        observed_unreachable_guard_ids=observed_unreachable,
        expected_structured_future_scan_reached=(
            probe.structured_future_scan_reached
        ),
        observed_structured_future_scan_reached=_observed_structured_scan(
            execution,
            observed_guard,
        ),
        canonical_parser_reached=parser_reached,
        ced_application_reached=ced_application_reached,
    )


def _safe_runtime_fingerprint(ced: Optional[CEDOrchestrator]) -> Optional[str]:
    if ced is None:
        return None
    try:
        return canonical_runtime_fingerprint(ced)
    except Exception:
        return None


def _safe_dispatches(adapters: Iterable[object]) -> int:
    try:
        return _provider_dispatches_v2(adapters)
    except Exception:
        return 0


def _build_sibling_control_v2(
    *,
    selected_source_capsule_id: str,
) -> Tuple[
    CEDOrchestrator,
    Tuple[object, ...],
    CanonicalBranchCapsule,
]:
    for case_name in (_OTHER_BINDING_CASE_NAME, _BASELINE_CASE_NAME):
        case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(case_name)
        _, ced, _, adapters, capsule, _ = _capture_probe_root_v2(
            case,
            budget=_budget_v2(),
            usage=BudgetUsage(nodes=1),
        )
        if capsule.capsule_id != selected_source_capsule_id:
            return ced, tuple(adapters), capsule
    raise ContractValidationError("negative sibling control is not branch-distinct")


def _probe_failure_v2(
    probe: CanonicalSuccessorProbeV2,
    *,
    failure_code: ProbeEvaluationFailureCode,
    error: Exception,
    operation_invoked: bool,
    execution: Optional[_ProbeExecutionV2] = None,
    construction_evidence: Optional[
        CanonicalSuccessorProbeConstructionEvidenceV2
    ] = None,
    source_before: Optional[str] = None,
    source_dispatch_before: int = 0,
    sibling_ced: Optional[CEDOrchestrator] = None,
    sibling_adapters: Iterable[object] = (),
    sibling_capsule: Optional[CanonicalBranchCapsule] = None,
    sibling_before: Optional[str] = None,
    sibling_dispatch_before: int = 0,
    production_ced: Optional[CEDOrchestrator] = None,
    production_adapters: Iterable[object] = (),
    production_capsule: Optional[CanonicalBranchCapsule] = None,
    production_before: Optional[str] = None,
    production_dispatch_before: int = 0,
    first_result: Optional[CanonicalTransitionResult] = None,
    replay_result: Optional[CanonicalTransitionResult] = None,
) -> CanonicalSuccessorProbeEvaluationFailureV2:
    source_adapters = execution.source_adapters if execution is not None else ()
    source_after = (
        _safe_runtime_fingerprint(execution.source_ced)
        if execution is not None and source_before is not None
        else source_before
    )
    source_dispatch_after = _safe_dispatches(source_adapters)
    sibling_adapters = tuple(sibling_adapters)
    production_adapters = tuple(production_adapters)
    sibling_after = (
        _safe_runtime_fingerprint(sibling_ced)
        if sibling_before is not None
        else sibling_before
    )
    production_after = (
        _safe_runtime_fingerprint(production_ced)
        if production_before is not None
        else production_before
    )
    sibling_dispatch_after = _safe_dispatches(sibling_adapters)
    production_dispatch_after = _safe_dispatches(production_adapters)
    negative_dispatches = (
        source_dispatch_after + sibling_dispatch_after + production_dispatch_after
    )
    results = (first_result, replay_result)
    return CanonicalSuccessorProbeEvaluationFailureV2(
        probe_id=probe.probe_id,
        probe_fingerprint=probe.probe_fingerprint,
        probe_class=probe.probe_class,
        stage=probe.stage,
        failure_code=failure_code,
        exception_type=type(error).__name__,
        operation_invoked=operation_invoked,
        construction_evidence=construction_evidence,
        source_capsule_id=(
            execution.source_capsule.capsule_id if execution is not None else None
        ),
        source_runtime_fingerprint_before=source_before,
        source_runtime_fingerprint_after=source_after,
        source_provider_dispatches_before=source_dispatch_before,
        source_provider_dispatches_after=source_dispatch_after,
        sibling_control_capsule_id=(
            sibling_capsule.capsule_id if sibling_capsule is not None else None
        ),
        sibling_runtime_fingerprint_before=sibling_before,
        sibling_runtime_fingerprint_after=sibling_after,
        sibling_provider_dispatches_before=sibling_dispatch_before,
        sibling_provider_dispatches_after=sibling_dispatch_after,
        production_control_capsule_id=(
            production_capsule.capsule_id if production_capsule is not None else None
        ),
        production_runtime_fingerprint_before=production_before,
        production_runtime_fingerprint_after=production_after,
        production_provider_dispatches_before=production_dispatch_before,
        production_provider_dispatches_after=production_dispatch_after,
        successor_created=any(
            result is not None and result.successor_capsule is not None
            for result in results
        ),
        negative_probe_dispatches=negative_dispatches,
        aggregate_provider_dispatches=negative_dispatches,
        live_calls=(
            _live_calls_v2(source_adapters)
            + _live_calls_v2(sibling_adapters)
            + _live_calls_v2(production_adapters)
        ),
        model_calls=max(
            sum(
                result.receipt.new_execution_usage.budget_delta.model_calls
                for result in results
                if result is not None
            ),
            negative_dispatches,
        ),
        tool_calls=_tool_calls_v2(results),
    )


def _evaluate_unavailable_probe_v2_strict(
    probe: CanonicalSuccessorProbeV2,
) -> CanonicalSuccessorUnavailableEvidenceV2:
    execution: Optional[_ProbeExecutionV2] = None
    construction: Optional[CanonicalSuccessorProbeConstructionEvidenceV2] = None
    try:
        execution = _build_probe_execution_v2(probe.probe_id)
        construction = _construction_evidence_v2(probe, execution)
    except Exception as exc:
        return _probe_failure_v2(
            probe,
            failure_code=ProbeEvaluationFailureCode.CONSTRUCTION_FAILED,
            error=exc,
            operation_invoked=False,
            execution=execution,
            construction_evidence=construction,
        )

    source_before = canonical_runtime_fingerprint(execution.source_ced)
    source_dispatch_before = _provider_dispatches_v2(execution.source_adapters)
    if not construction.validity_gate_passed:
        failure_code = (
            ProbeEvaluationFailureCode.GROUND_TRUTH_FIREWALL_FAILED
            if not construction.ground_truth_firewall_passed
            else ProbeEvaluationFailureCode.INVALID_PROBE_CONSTRUCTION
        )
        return _probe_failure_v2(
            probe,
            failure_code=failure_code,
            error=ContractValidationError("v2 probe validity gate failed"),
            operation_invoked=False,
            execution=execution,
            construction_evidence=construction,
            source_before=source_before,
            source_dispatch_before=source_dispatch_before,
        )

    sibling_ced: Optional[CEDOrchestrator] = None
    sibling_adapters: Tuple[object, ...] = ()
    sibling_capsule: Optional[CanonicalBranchCapsule] = None
    sibling_before: Optional[str] = None
    sibling_dispatch_before = 0
    production_ced: Optional[CEDOrchestrator] = None
    production_adapters: Tuple[object, ...] = ()
    production_capsule: Optional[CanonicalBranchCapsule] = None
    production_before: Optional[str] = None
    production_dispatch_before = 0
    first: Optional[_ProbeInvocationOutcomeV2] = None
    replay: Optional[_ProbeInvocationOutcomeV2] = None
    try:
        sibling_ced, sibling_adapters, sibling_capsule = _build_sibling_control_v2(
            selected_source_capsule_id=execution.source_capsule.capsule_id or "",
        )
        sibling_before = canonical_runtime_fingerprint(sibling_ced)
        sibling_dispatch_before = _provider_dispatches_v2(sibling_adapters)
        production_ced, production_adapters, production_capsule = (
            _build_v1_production_control(
                budget=_budget_v2(),
                usage=BudgetUsage(nodes=1),
            )
        )
        production_adapters = tuple(production_adapters)
        production_before = canonical_runtime_fingerprint(production_ced)
        production_dispatch_before = _provider_dispatches_v2(production_adapters)
        first = _invoke_probe_v2(execution.operation)
        replay = _invoke_probe_v2(execution.operation)
        diagnostics = _diagnostic_evidence_v2(probe, execution, first)
    except Exception as exc:
        return _probe_failure_v2(
            probe,
            failure_code=ProbeEvaluationFailureCode.INVOCATION_FAILED,
            error=exc,
            operation_invoked=first is not None,
            execution=execution,
            construction_evidence=construction,
            source_before=source_before,
            source_dispatch_before=source_dispatch_before,
            sibling_ced=sibling_ced,
            sibling_adapters=sibling_adapters,
            sibling_capsule=sibling_capsule,
            sibling_before=sibling_before,
            sibling_dispatch_before=sibling_dispatch_before,
            production_ced=production_ced,
            production_adapters=production_adapters,
            production_capsule=production_capsule,
            production_before=production_before,
            production_dispatch_before=production_dispatch_before,
            first_result=first.result if first is not None else None,
            replay_result=replay.result if replay is not None else None,
        )

    assert first is not None and replay is not None
    source_after = canonical_runtime_fingerprint(execution.source_ced)
    sibling_after = canonical_runtime_fingerprint(sibling_ced)
    production_after = canonical_runtime_fingerprint(production_ced)
    source_dispatch_after = _provider_dispatches_v2(execution.source_adapters)
    sibling_dispatch_after = _provider_dispatches_v2(sibling_adapters)
    production_dispatch_after = _provider_dispatches_v2(production_adapters)
    first_result = first.result
    replay_result = replay.result
    first_receipt = first_result.receipt if first_result is not None else None
    first_successor = (
        first_result.successor_capsule if first_result is not None else None
    )
    first_projection = (
        first_result.successor_search_state_v1 if first_result is not None else None
    )
    replay_successor = (
        replay_result.successor_capsule if replay_result is not None else None
    )
    replay_projection = (
        replay_result.successor_search_state_v1 if replay_result is not None else None
    )
    expected_kind = (
        ProbeOutcomeKind.RAISED_UNAVAILABLE
        if execution.invocation_stage in {ProbeStage.CAPTURE, ProbeStage.PREPARE}
        else ProbeOutcomeKind.RETURNED_UNAVAILABLE
    )
    outcome_shape_match = all(
        (
            first.kind is expected_kind,
            first.status
            is (
                None
                if expected_kind is ProbeOutcomeKind.RAISED_UNAVAILABLE
                else CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
            ),
        )
    )
    replay_match = all(
        (
            first.kind is replay.kind,
            first.reason is replay.reason,
            first.status is replay.status,
            first.outcome_digest == replay.outcome_digest,
            (first_result.transition_id if first_result is not None else None)
            == (replay_result.transition_id if replay_result is not None else None),
            (first_result.result_id if first_result is not None else None)
            == (replay_result.result_id if replay_result is not None else None),
            (first_receipt.receipt_id if first_receipt is not None else None)
            == (
                replay_result.receipt.receipt_id
                if replay_result is not None
                else None
            ),
            (first_successor.capsule_id if first_successor is not None else None)
            == (replay_successor.capsule_id if replay_successor is not None else None),
            (first_successor.branch_id if first_successor is not None else None)
            == (replay_successor.branch_id if replay_successor is not None else None),
            (first_projection.state_id if first_projection is not None else None)
            == (replay_projection.state_id if replay_projection is not None else None),
        )
    )
    if first_receipt is None:
        receipt_match = first.kind in {
            ProbeOutcomeKind.RAISED_UNAVAILABLE,
            ProbeOutcomeKind.RETURNED_NON_RESULT,
        }
        resource_match = receipt_match
    elif first.kind is ProbeOutcomeKind.RETURNED_UNAVAILABLE:
        receipt_match = all(
            (
                first_receipt.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
                first_receipt.unavailable_reason is first.reason,
                first_receipt.transition_id == first_result.transition_id,
                first_receipt.successor_state_hash is None,
                first_receipt.successor_state_v1_id is None,
                first_receipt.branch_id is None,
                first_successor is None,
                first_projection is None,
            )
        )
        resource_match = all(
            (
                first_receipt.new_execution_usage == NewExecutionUsage.not_applied(),
                first_receipt.budget_before == first_receipt.budget_after,
            )
        )
    else:
        receipt_match = all(
            (
                first.kind is ProbeOutcomeKind.RETURNED_SUCCESSOR,
                first_receipt.status is first.status,
                first_receipt.transition_id == first_result.transition_id,
                first_receipt.unavailable_reason is None,
                first_successor is not None,
                first_projection is not None,
                first_receipt.branch_id
                == (first_successor.branch_id if first_successor is not None else None),
                first_receipt.successor_state_v1_id
                == (first_projection.state_id if first_projection is not None else None),
            )
        )
        resource_match = first_receipt.new_execution_usage.applied
    negative_dispatches = (
        source_dispatch_after + sibling_dispatch_after + production_dispatch_after
    )
    results = (first_result, replay_result)
    return CanonicalSuccessorUnavailableCaseResultV2(
        probe_id=probe.probe_id,
        probe_fingerprint=probe.probe_fingerprint,
        probe_class=probe.probe_class,
        stage=probe.stage,
        expected_primary_reason=probe.expected_primary_reason,
        actual_primary_reason=first.reason,
        outcome_kind=first.kind,
        actual_status=first.status,
        observed_guard_id=diagnostics.observed_guard_id,
        construction_evidence=construction,
        diagnostics=diagnostics,
        transition_id=(first_result.transition_id if first_result is not None else None),
        result_id=(first_result.result_id if first_result is not None else None),
        receipt=first_receipt,
        successor_capsule_id=(
            first_successor.capsule_id if first_successor is not None else None
        ),
        successor_branch_id=(
            first_successor.branch_id if first_successor is not None else None
        ),
        successor_state_v1_id=(
            first_projection.state_id if first_projection is not None else None
        ),
        replay_outcome_kind=replay.kind,
        replay_primary_reason=replay.reason,
        replay_status=replay.status,
        replay_transition_id=(
            replay_result.transition_id if replay_result is not None else None
        ),
        replay_result_id=(replay_result.result_id if replay_result is not None else None),
        replay_receipt_id=(
            replay_result.receipt.receipt_id if replay_result is not None else None
        ),
        replay_successor_capsule_id=(
            replay_successor.capsule_id if replay_successor is not None else None
        ),
        replay_successor_branch_id=(
            replay_successor.branch_id if replay_successor is not None else None
        ),
        replay_successor_state_v1_id=(
            replay_projection.state_id if replay_projection is not None else None
        ),
        primary_outcome_digest=first.outcome_digest,
        replay_outcome_digest=replay.outcome_digest,
        source_capsule_id=execution.source_capsule.capsule_id or "",
        source_runtime_fingerprint_before=source_before,
        source_runtime_fingerprint_after=source_after,
        source_provider_dispatches_before=source_dispatch_before,
        source_provider_dispatches_after=source_dispatch_after,
        sibling_control_capsule_id=sibling_capsule.capsule_id or "",
        sibling_runtime_fingerprint_before=sibling_before,
        sibling_runtime_fingerprint_after=sibling_after,
        sibling_provider_dispatches_before=sibling_dispatch_before,
        sibling_provider_dispatches_after=sibling_dispatch_after,
        production_control_capsule_id=production_capsule.capsule_id or "",
        production_runtime_fingerprint_before=production_before,
        production_runtime_fingerprint_after=production_after,
        production_provider_dispatches_before=production_dispatch_before,
        production_provider_dispatches_after=production_dispatch_after,
        primary_reason_match=first.reason is probe.expected_primary_reason,
        guard_match=diagnostics.observed_guard_id == probe.expected_guard_id,
        diagnostic_match=diagnostics.diagnostic_match,
        outcome_shape_match=outcome_shape_match,
        replay_match=replay_match,
        source_unchanged=(
            source_before == source_after
            and source_dispatch_before == source_dispatch_after == 0
        ),
        sibling_unchanged=(
            sibling_before == sibling_after
            and sibling_dispatch_before == sibling_dispatch_after == 0
        ),
        production_unchanged=(
            production_before == production_after
            and production_dispatch_before == production_dispatch_after == 0
        ),
        receipt_match=receipt_match,
        resource_accounting_match=resource_match,
        successor_created=first_successor is not None or first_projection is not None,
        negative_probe_dispatches=negative_dispatches,
        aggregate_provider_dispatches=negative_dispatches,
        live_calls=(
            _live_calls_v2(execution.source_adapters)
            + _live_calls_v2(sibling_adapters)
            + _live_calls_v2(production_adapters)
        ),
        primary_model_calls=(
            first_result.receipt.new_execution_usage.budget_delta.model_calls
            if first_result is not None
            else 0
        ),
        replay_model_calls=(
            replay_result.receipt.new_execution_usage.budget_delta.model_calls
            if replay_result is not None
            else 0
        ),
        model_calls=max(
            sum(
                result.receipt.new_execution_usage.budget_delta.model_calls
                for result in results
                if result is not None
            ),
            negative_dispatches,
        ),
        tool_calls=_tool_calls_v2(results),
    )


def _evaluate_unavailable_probe_v2(
    probe: CanonicalSuccessorProbeV2,
) -> CanonicalSuccessorUnavailableEvidenceV2:
    """Preserve every unexpected evaluator defect as falsifying case evidence."""

    try:
        return _evaluate_unavailable_probe_v2_strict(probe)
    except Exception as exc:
        return _probe_failure_v2(
            probe,
            failure_code=ProbeEvaluationFailureCode.EVIDENCE_EXTRACTION_FAILED,
            error=exc,
            operation_invoked=True,
        )


def _repository_root_v2() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_blob_id(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _working_tree_git_blob_id(root: Path, repository_path: str) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "hash-object", "--", repository_path],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if len(value) == 40 else None


def _git_blob_at_revision(
    root: Path,
    revision: str,
    repository_path: str,
) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", f"{revision}:{repository_path}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if len(value) == 40 else None


def _actual_core_lock_mismatches() -> int:
    root = _repository_root_v2()
    mismatches = 0
    for entry in FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2.core_blobs:
        path = root / Path(entry.path)
        if not path.is_file():
            mismatches += 1
            continue
        actual = _working_tree_git_blob_id(root, entry.path)
        mismatches += int(actual != entry.git_blob_id)
    return mismatches


def _actual_predecessor_lock_mismatches() -> int:
    root = _repository_root_v2()
    lock = FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2.predecessor
    mismatches = 0
    try:
        (root / Path(lock.evaluator_path)).read_bytes()
    except OSError:
        mismatches += 1
    else:
        mismatches += int(
            _working_tree_git_blob_id(root, lock.evaluator_path)
            != lock.evaluator_git_blob_id
        )
    try:
        artifact_payload = (root / Path(lock.artifact_path)).read_bytes()
    except OSError:
        return mismatches + 1
    mismatches += int(
        _working_tree_git_blob_id(root, lock.artifact_path)
        != lock.artifact_git_blob_id
    )
    canonical_artifact_payload = artifact_payload.replace(b"\r\n", b"\n")
    mismatches += int(
        hashlib.sha256(canonical_artifact_payload).hexdigest()
        != lock.artifact_sha256
    )
    try:
        parsed = json.loads(canonical_artifact_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return mismatches + 1
    mismatches += int(parsed.get("artifact_id") != lock.artifact_id)
    mismatches += int(parsed.get("hypothesis_status") != lock.artifact_status)
    mismatches += int(
        _git_blob_at_revision(root, lock.artifact_commit, lock.evaluator_path)
        != lock.evaluator_git_blob_id
    )
    mismatches += int(
        _git_blob_at_revision(root, lock.artifact_commit, lock.artifact_path)
        != lock.artifact_git_blob_id
    )
    return mismatches


def _positive_mismatch(
    item: CanonicalSuccessorParityEvidenceV1,
    attribute: str,
) -> int:
    if isinstance(item, V1CanonicalSuccessorParityEvaluationFailure):
        return 1
    return int(not bool(getattr(item, attribute)))


def _positive_field_mismatch(
    item: CanonicalSuccessorParityEvidenceV1,
    name: str,
) -> int:
    if isinstance(item, V1CanonicalSuccessorParityEvaluationFailure):
        return 1
    return int(not item.field_parity(name))


def _negative_source_unchanged(item: CanonicalSuccessorUnavailableEvidenceV2) -> bool:
    if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2):
        return item.source_unchanged
    return all(
        (
            item.source_runtime_fingerprint_before is not None,
            item.source_runtime_fingerprint_before
            == item.source_runtime_fingerprint_after,
            item.source_provider_dispatches_before
            == item.source_provider_dispatches_after
            == 0,
        )
    )


def _negative_sibling_unchanged(item: CanonicalSuccessorUnavailableEvidenceV2) -> bool:
    if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2):
        return item.sibling_unchanged
    return all(
        (
            item.sibling_control_capsule_id is not None,
            item.sibling_control_capsule_id != item.source_capsule_id,
            item.sibling_runtime_fingerprint_before is not None,
            item.sibling_runtime_fingerprint_before
            == item.sibling_runtime_fingerprint_after,
            item.sibling_provider_dispatches_before
            == item.sibling_provider_dispatches_after
            == 0,
        )
    )


def _negative_production_unchanged(
    item: CanonicalSuccessorUnavailableEvidenceV2,
) -> bool:
    if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2):
        return item.production_unchanged
    return all(
        (
            item.production_runtime_fingerprint_before is not None,
            item.production_runtime_fingerprint_before
            == item.production_runtime_fingerprint_after,
            item.production_provider_dispatches_before
            == item.production_provider_dispatches_after
            == 0,
        )
    )


def _negative_case_failure(
    cases: Sequence[CanonicalSuccessorUnavailableEvidenceV2],
    probe_id: str,
) -> int:
    item = next(case for case in cases if case.probe_id == probe_id)
    return int(not item.unavailable_passed)


def _security_probe_violation(
    cases: Sequence[CanonicalSuccessorUnavailableEvidenceV2],
    *,
    probe_id: str,
    guard_id: str,
    reason: SuccessorUnavailableReason,
) -> int:
    item = next(case for case in cases if case.probe_id == probe_id)
    if not isinstance(item, CanonicalSuccessorUnavailableCaseResultV2):
        return 1
    exact_rejection = all(
        (
            item.actual_primary_reason is reason,
            item.observed_guard_id == guard_id,
            item.outcome_kind is ProbeOutcomeKind.RETURNED_UNAVAILABLE,
            item.actual_status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
            not item.successor_created,
            not item.diagnostics.canonical_parser_reached,
            not item.diagnostics.ced_application_reached,
        )
    )
    return int(not exact_rejection)


def _positive_model_calls(item: CanonicalSuccessorParityEvidenceV1) -> int:
    if isinstance(item, V1CanonicalSuccessorParityEvaluationFailure):
        return max(item.aggregate_provider_dispatches, item.live_calls)
    return max(
        item.receipt.new_execution_usage.budget_delta.model_calls,
        item.aggregate_provider_dispatches,
    )


def _calculate_metrics_v2(
    parity: Iterable[CanonicalSuccessorParityEvidenceV1],
    orthogonal: Iterable[CanonicalSuccessorUnavailableEvidenceV2],
    precedence: Iterable[CanonicalSuccessorUnavailableEvidenceV2],
) -> CanonicalSuccessorParityMetricsV2:
    parity_cases = tuple(parity)
    orthogonal_cases = tuple(orthogonal)
    precedence_cases = tuple(precedence)
    negative_cases = orthogonal_cases + precedence_cases
    all_cases: Tuple[object, ...] = parity_cases + negative_cases
    positive_failures = tuple(
        item
        for item in parity_cases
        if isinstance(item, V1CanonicalSuccessorParityEvaluationFailure)
    )
    negative_failures = tuple(
        item
        for item in negative_cases
        if isinstance(item, CanonicalSuccessorProbeEvaluationFailureV2)
    )
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

    def gate_failure(item: CanonicalSuccessorProbeEvaluationFailureV2) -> bool:
        return item.failure_code in {
            ProbeEvaluationFailureCode.INVALID_PROBE_CONSTRUCTION,
            ProbeEvaluationFailureCode.GROUND_TRUTH_FIREWALL_FAILED,
        }

    return CanonicalSuccessorParityMetricsV2(
        cases_total=len(all_cases),
        supported_authoritative_cases=len(parity_cases),
        accepted_reference_cases=len(accepted),
        canonical_rejection_reference_cases=len(rejected),
        orthogonal_negative_cases=len(orthogonal_cases),
        precedence_negative_cases=len(precedence_cases),
        accepted_parity=sum(item.parity_passed for item in accepted),
        canonical_rejection_parity=sum(item.parity_passed for item in rejected),
        orthogonal_primary_classifications=sum(
            isinstance(item, CanonicalSuccessorUnavailableCaseResultV2)
            and item.primary_reason_match
            and item.guard_match
            and item.outcome_shape_match
            for item in orthogonal_cases
        ),
        precedence_primary_classifications=sum(
            isinstance(item, CanonicalSuccessorUnavailableCaseResultV2)
            and item.primary_reason_match
            and item.guard_match
            and item.outcome_shape_match
            for item in precedence_cases
        ),
        evaluation_failures=len(positive_failures) + len(negative_failures),
        validity_gate_failures=sum(gate_failure(item) for item in negative_failures),
        invariant_vector_mismatches=sum(
            item.construction_evidence is None
            or item.construction_evidence.measured_invariant_vector
            != _probe_by_id(item.probe_id).invariant_vector
            for item in negative_failures
            if gate_failure(item)
        ),
        literal_mutation_mismatches=sum(
            item.construction_evidence is None
            or not item.construction_evidence.literal_mutations_match
            for item in negative_failures
            if gate_failure(item)
        ),
        ground_truth_firewall_failures=sum(
            item.construction_evidence is None
            or not item.construction_evidence.ground_truth_firewall_passed
            for item in negative_failures
            if item.failure_code
            is ProbeEvaluationFailureCode.GROUND_TRUTH_FIREWALL_FAILED
        ),
        primary_classification_mismatches=sum(
            not item.primary_reason_match
            for item in negative_cases
            if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2)
        ),
        guard_precedence_mismatches=sum(
            not item.guard_match
            for item in negative_cases
            if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2)
        ),
        diagnostic_mismatches=sum(
            not item.diagnostic_match
            for item in negative_cases
            if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2)
        ),
        status_mismatches=(
            sum(_positive_mismatch(item, "status_parity") for item in parity_cases)
            + sum(
                not item.outcome_shape_match
                for item in negative_cases
                if isinstance(item, CanonicalSuccessorUnavailableCaseResultV2)
            )
        ),
        canonical_rejection_reason_mismatches=sum(
            _positive_mismatch(item, "canonical_rejection_reason_parity")
            for item in parity_cases
        ),
        semantic_mismatches=sum(
            _positive_mismatch(item, "semantic_parity") for item in parity_cases
        ),
        accepted_move_id_mismatches=sum(
            _positive_mismatch(item, "move_id_parity") for item in accepted
        ),
        task_log_mismatches=sum(
            _positive_field_mismatch(item, "task_log") for item in parity_cases
        ),
        commitment_mismatches=sum(
            _positive_field_mismatch(item, "commitments") for item in parity_cases
        ),
        phase_role_mismatches=sum(
            _positive_field_mismatch(item, "phase_role_cursor") for item in parity_cases
        ),
        search_state_v1_mismatches=sum(
            _positive_mismatch(item, "search_state_v1_parity") for item in parity_cases
        ),
        canonical_processor_mismatches=sum(
            _positive_mismatch(item, "canonical_processor_parity") for item in parity_cases
        ),
        observation_identity_mismatches=sum(
            _positive_mismatch(item, "observation_identity_match") for item in parity_cases
        ),
        source_isolation_failures=(
            sum(_positive_mismatch(item, "source_unchanged") for item in parity_cases)
            + sum(not _negative_source_unchanged(item) for item in negative_cases)
        ),
        sibling_isolation_failures=(
            sum(_positive_mismatch(item, "sibling_unchanged") for item in parity_cases)
            + sum(not _negative_sibling_unchanged(item) for item in negative_cases)
        ),
        production_mutations=(
            sum(_positive_mismatch(item, "production_unchanged") for item in parity_cases)
            + sum(not _negative_production_unchanged(item) for item in negative_cases)
        ),
        receipt_mismatches=(
            sum(_positive_mismatch(item, "receipt_match") for item in parity_cases)
            + sum(
                1
                if isinstance(item, CanonicalSuccessorProbeEvaluationFailureV2)
                else int(not item.receipt_match)
                for item in negative_cases
            )
        ),
        resource_accounting_mismatches=(
            sum(
                _positive_mismatch(item, "resource_accounting_match")
                for item in parity_cases
            )
            + sum(
                1
                if isinstance(item, CanonicalSuccessorProbeEvaluationFailureV2)
                else int(not item.resource_accounting_match)
                for item in negative_cases
            )
        ),
        value_v1_compatibility_mismatches=sum(
            _positive_mismatch(item, "value_v1_read_only_compatible")
            for item in parity_cases
        ),
        idempotence_failures=(
            sum(_positive_mismatch(item, "idempotent_replay") for item in parity_cases)
            + sum(
                1
                if isinstance(item, CanonicalSuccessorProbeEvaluationFailureV2)
                else int(not item.replay_match)
                for item in negative_cases
            )
        ),
        negative_successors_created=sum(item.successor_created for item in negative_cases),
        fabricated_observations=_security_probe_violation(
            negative_cases,
            probe_id="p8v2-p07-caller-rebinding-vs-manifest",
            guard_id="A7",
            reason=SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
        ),
        future_label_violations=_security_probe_violation(
            negative_cases,
            probe_id="p8v2-o10-future-label",
            guard_id="A4",
            reason=SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN,
        ),
        historical_offline_fixture_dispatches=sum(
            FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
                item.case_name
            ).reference.offline_fixture_dispatches
            for item in parity_cases
        ),
        negative_probe_dispatches=sum(
            item.negative_probe_dispatches for item in negative_cases
        ),
        aggregate_provider_dispatches=sum(
            item.aggregate_provider_dispatches for item in all_cases
        ),
        live_calls=sum(item.live_calls for item in all_cases),
        model_calls=(
            sum(_positive_model_calls(item) for item in parity_cases)
            + sum(item.model_calls for item in negative_cases)
        ),
        tool_calls=sum(item.tool_calls for item in all_cases),
        core_lock_mismatches=_actual_core_lock_mismatches(),
        predecessor_lock_mismatches=_actual_predecessor_lock_mismatches(),
    )


def _validated_order_v2(
    supplied: Optional[Sequence[str]],
    expected: Sequence[str],
    *,
    name: str,
) -> Tuple[str, ...]:
    order = tuple(supplied) if supplied is not None else tuple(expected)
    if len(order) != len(expected) or set(order) != set(expected):
        raise ContractValidationError(f"{name} must contain the complete frozen set")
    return order


def _build_canonical_successor_parity_artifact_v2_in_order(
    *,
    supported_order: Sequence[str],
    orthogonal_order: Sequence[str],
    precedence_order: Sequence[str],
) -> CanonicalSuccessorParityArtifactV2:
    selected_supported = _validated_order_v2(
        supported_order,
        FROZEN_SUPPORTED_CASE_ORDER_V2,
        name="supported_order",
    )
    selected_orthogonal = _validated_order_v2(
        orthogonal_order,
        FROZEN_ORTHOGONAL_PROBE_ORDER_V2,
        name="orthogonal_order",
    )
    selected_precedence = _validated_order_v2(
        precedence_order,
        FROZEN_PRECEDENCE_PROBE_ORDER_V2,
        name="precedence_order",
    )
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    parity = tuple(
        _evaluate_v1_parity_case(corpus.case(case_name))
        for case_name in selected_supported
    )
    probes = {
        probe.probe_id: probe for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    }
    orthogonal = tuple(
        _evaluate_unavailable_probe_v2(probes[probe_id])
        for probe_id in selected_orthogonal
    )
    precedence = tuple(
        _evaluate_unavailable_probe_v2(probes[probe_id])
        for probe_id in selected_precedence
    )
    metrics = _calculate_metrics_v2(parity, orthogonal, precedence)
    supported = FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2.supports(metrics)
    return CanonicalSuccessorParityArtifactV2(
        capture_manifest_id=(
            FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.manifest_id or ""
        ),
        canonical_processor_ids=tuple(sorted(CANONICAL_PROCESSOR_IDS)),
        core_lock=FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2,
        core_lock_id=FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2.lock_id or "",
        validation_order_id=(
            FROZEN_CANONICAL_VALIDATION_ORDER_V2.validation_order_id or ""
        ),
        failure_taxonomy_id=(
            FROZEN_CANONICAL_FAILURE_TAXONOMY_V1.taxonomy_id or ""
        ),
        failure_precedence_id=(
            FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1.precedence_id or ""
        ),
        compatibility_diagnostics_id=(
            FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.diagnostics_id or ""
        ),
        probe_design_id=(
            FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.probe_design_id or ""
        ),
        case_set_id=(
            FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2.case_set_id or ""
        ),
        case_set=FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2,
        corpus_id=FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2.corpus_id or "",
        corpus_canonical_sha256=frozen_corpus_v2_canonical_sha256(),
        thresholds_id=(
            FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2.thresholds_id or ""
        ),
        thresholds=FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2,
        parity_cases=parity,
        orthogonal_cases=orthogonal,
        precedence_cases=precedence,
        metrics=metrics,
        hypothesis_status="SUPPORTED" if supported else "FALSIFIED",
    )


def build_canonical_successor_parity_artifact_v2() -> CanonicalSuccessorParityArtifactV2:
    """Execute the first authoritative 23-case v2 aggregate."""

    return _build_canonical_successor_parity_artifact_v2_in_order(
        supported_order=FROZEN_SUPPORTED_CASE_ORDER_V2,
        orthogonal_order=FROZEN_ORTHOGONAL_PROBE_ORDER_V2,
        precedence_order=FROZEN_PRECEDENCE_PROBE_ORDER_V2,
    )


def build_canonical_successor_parity_replay_artifact_v2(
    authoritative: CanonicalSuccessorParityArtifactV2,
) -> CanonicalSuccessorParityArtifactV2:
    """Run reverse-order replay only after the first aggregate is supported."""

    rendered = render_canonical_successor_parity_artifact_v2(authoritative)
    validated = replay_canonical_successor_parity_artifact_v2(rendered)
    if validated.hypothesis_status != "SUPPORTED":
        raise ContractValidationError(
            "reverse replay is forbidden until the authoritative artifact is SUPPORTED"
        )
    return _build_canonical_successor_parity_artifact_v2_in_order(
        supported_order=FROZEN_REPLAY_SUPPORTED_CASE_ORDER_V2,
        orthogonal_order=FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V2,
        precedence_order=FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V2,
    )


def render_canonical_successor_parity_artifact_v2(
    artifact: CanonicalSuccessorParityArtifactV2,
) -> str:
    validated = CanonicalSuccessorParityArtifactV2.model_validate_json(
        artifact.model_dump_json()
    )
    return canonical_json(validated.model_dump(mode="json")) + "\n"


def replay_canonical_successor_parity_artifact_v2(
    rendered: str,
) -> CanonicalSuccessorParityArtifactV2:
    artifact = CanonicalSuccessorParityArtifactV2.model_validate_json(rendered)
    canonical = canonical_json(artifact.model_dump(mode="json")) + "\n"
    if canonical != rendered:
        raise ContractValidationError("v2 parity artifact bytes are not canonical")
    return artifact


def canonical_successor_parity_artifact_sha256_v2(
    artifact: CanonicalSuccessorParityArtifactV2,
) -> str:
    return hashlib.sha256(
        render_canonical_successor_parity_artifact_v2(artifact).encode("utf-8")
    ).hexdigest()


def create_canonical_successor_parity_replay_lock_v2(
    authoritative: CanonicalSuccessorParityArtifactV2,
    replay: CanonicalSuccessorParityArtifactV2,
) -> CanonicalSuccessorParityReplayLockV2:
    """Validate and compare two actual artifacts internally; accept no caller lock."""

    if not isinstance(authoritative, CanonicalSuccessorParityArtifactV2) or not isinstance(
        replay, CanonicalSuccessorParityArtifactV2
    ):
        raise ContractValidationError("v2 replay lock requires two artifact contracts")
    authoritative_rendered = render_canonical_successor_parity_artifact_v2(
        authoritative
    )
    replay_rendered = render_canonical_successor_parity_artifact_v2(replay)
    authoritative_validated = replay_canonical_successor_parity_artifact_v2(
        authoritative_rendered
    )
    replay_validated = replay_canonical_successor_parity_artifact_v2(replay_rendered)
    if (
        authoritative_validated.hypothesis_status != "SUPPORTED"
        or replay_validated.hypothesis_status != "SUPPORTED"
    ):
        raise ContractValidationError("v2 replay lock requires two SUPPORTED artifacts")
    semantic_equality = (
        authoritative_validated.model_dump(mode="json")
        == replay_validated.model_dump(mode="json")
    )
    artifact_id_equality = (
        authoritative_validated.artifact_id == replay_validated.artifact_id
    )
    byte_identity = authoritative_rendered == replay_rendered
    if not all((semantic_equality, artifact_id_equality, byte_identity)):
        raise ContractValidationError("v2 independent reverse replay did not lock")
    return CanonicalSuccessorParityReplayLockV2(
        authoritative_artifact_id=authoritative_validated.artifact_id or "",
        replay_artifact_id=replay_validated.artifact_id or "",
        authoritative_sha256=hashlib.sha256(
            authoritative_rendered.encode("utf-8")
        ).hexdigest(),
        replay_sha256=hashlib.sha256(replay_rendered.encode("utf-8")).hexdigest(),
    )


def render_canonical_successor_parity_replay_lock_v2(
    replay_lock: CanonicalSuccessorParityReplayLockV2,
) -> str:
    validated = CanonicalSuccessorParityReplayLockV2.model_validate_json(
        replay_lock.model_dump_json()
    )
    return canonical_json(validated.model_dump(mode="json")) + "\n"


def replay_canonical_successor_parity_replay_lock_v2(
    rendered: str,
) -> CanonicalSuccessorParityReplayLockV2:
    replay_lock = CanonicalSuccessorParityReplayLockV2.model_validate_json(rendered)
    canonical = canonical_json(replay_lock.model_dump(mode="json")) + "\n"
    if canonical != rendered:
        raise ContractValidationError("v2 replay-lock bytes are not canonical")
    return replay_lock


def write_once_canonical_bytes_v2(destination: Path | str, payload: bytes) -> str:
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


def publish_canonical_successor_parity_artifact_once_v2(
    destination: Path | str,
    artifact: CanonicalSuccessorParityArtifactV2,
) -> str:
    rendered = render_canonical_successor_parity_artifact_v2(artifact)
    replay_canonical_successor_parity_artifact_v2(rendered)
    return write_once_canonical_bytes_v2(destination, rendered.encode("utf-8"))


def publish_canonical_successor_parity_replay_lock_once_v2(
    destination: Path | str,
    authoritative: CanonicalSuccessorParityArtifactV2,
    replay: CanonicalSuccessorParityArtifactV2,
) -> str:
    replay_lock = create_canonical_successor_parity_replay_lock_v2(
        authoritative,
        replay,
    )
    rendered = render_canonical_successor_parity_replay_lock_v2(replay_lock)
    replay_canonical_successor_parity_replay_lock_v2(rendered)
    return write_once_canonical_bytes_v2(destination, rendered.encode("utf-8"))


__all__ = [
    "CANONICAL_SUCCESSOR_COMPATIBILITY_DIAGNOSTIC_EVIDENCE_VERSION_V1",
    "CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION_V2",
    "CANONICAL_SUCCESSOR_PARITY_HARNESS_ID_V2",
    "CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION_V2",
    "CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION_V2",
    "CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION_V2",
    "CANONICAL_SUCCESSOR_PROBE_COMPONENT_SNAPSHOT_VERSION_V2",
    "CANONICAL_SUCCESSOR_PROBE_CONSTRUCTION_EVIDENCE_VERSION_V2",
    "CANONICAL_SUCCESSOR_PROBE_EVALUATION_FAILURE_VERSION_V2",
    "CANONICAL_SUCCESSOR_UNAVAILABLE_RESULT_VERSION_V2",
    "CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION_V2",
    "FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2",
    "FROZEN_ORTHOGONAL_PROBE_ORDER_V2",
    "FROZEN_PRECEDENCE_PROBE_ORDER_V2",
    "FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V2",
    "FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V2",
    "FROZEN_REPLAY_SUPPORTED_CASE_ORDER_V2",
    "FROZEN_SUPPORTED_CASE_ORDER_V2",
    "CanonicalSuccessorCompatibilityDiagnosticEvidenceV1",
    "CanonicalSuccessorParityArtifactV2",
    "CanonicalSuccessorParityMetricsV2",
    "CanonicalSuccessorParityReplayLockV2",
    "CanonicalSuccessorParityThresholdsV2",
    "CanonicalSuccessorProbeComponentSnapshotV2",
    "CanonicalSuccessorProbeConstructionEvidenceV2",
    "CanonicalSuccessorProbeEvaluationFailureV2",
    "CanonicalSuccessorUnavailableCaseResultV2",
    "CanonicalSuccessorUnavailableEvidenceV2",
    "ProbeEvaluationFailureCode",
    "ProbeOutcomeKind",
    "build_canonical_successor_parity_artifact_v2",
    "build_canonical_successor_parity_replay_artifact_v2",
    "canonical_successor_parity_artifact_sha256_v2",
    "create_canonical_successor_parity_replay_lock_v2",
    "publish_canonical_successor_parity_artifact_once_v2",
    "publish_canonical_successor_parity_replay_lock_once_v2",
    "render_canonical_successor_parity_artifact_v2",
    "render_canonical_successor_parity_replay_lock_v2",
    "replay_canonical_successor_parity_artifact_v2",
    "replay_canonical_successor_parity_replay_lock_v2",
    "write_once_canonical_bytes_v2",
]

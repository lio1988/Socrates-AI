"""Deterministic evaluator for External Observation Acquisition Contract v0.

The acquisition runtime owns guard execution and receipts.  This module owns
only frozen research fixtures, evaluator-side expected labels, mutation-vector
measurement, aggregate scoring, canonical artifacts, and replay locking.  It
has no provider, credential, network, CED, search, or production integration.

Nothing executes at import time.  In particular, importing this module never
enters the canned transport and never writes an artifact.  The authoritative
aggregate is an explicit caller action after the pre-result freeze.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from . import acquisition as _runtime
from .acquisition_cases import (
    ACQUISITION_HARNESS_ID_V0,
    AcquisitionCaseClass,
    AcquisitionLiteralMutationV0,
    AcquisitionMutationVectorV0,
    AcquisitionPositiveCaseV0,
    AcquisitionProbeV0,
    AcquisitionThresholdsV0,
    FROZEN_ACQUISITION_CASE_SET_V0,
    FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0,
    FROZEN_ACQUISITION_POSITIVE_CASES_V0,
    FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0,
    FROZEN_ACQUISITION_THRESHOLDS_V0,
    FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0,
    FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0,
    FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0,
    FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0,
    MUTATION_VECTOR_FIELD_NAMES,
    MutationState,
    frozen_acquisition_case_set_sha256_v0,
)
from .acquisition_contracts import (
    ACQUISITION_CONTRACT_ID,
    ACQUISITION_GUARD_ORDER,
    ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION,
    ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION,
    CANNED_TRANSPORT_ID,
    PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION,
    AcquisitionAggregateMetrics,
    AcquisitionAggregateReceipt,
    AcquisitionArtifactInclusionPolicy,
    AcquisitionAttemptOutcome,
    AcquisitionAttemptReceipt,
    AcquisitionBudget,
    AcquisitionCapabilitySnapshot,
    AcquisitionControlName,
    AcquisitionControlPolicy,
    AcquisitionControlRequirement,
    AcquisitionControlState,
    AcquisitionExecutionUsage,
    AcquisitionFailureCode,
    AcquisitionFailureCount,
    AcquisitionGuardId,
    AcquisitionGuardEvaluation,
    AcquisitionGuardState,
    AcquisitionHistoricalUsage,
    AcquisitionIsolationReceipt,
    AcquisitionPrimaryResult,
    AcquisitionProviderModelBinding,
    AcquisitionRequestConfiguration,
    AcquisitionResourceQuantity,
    AcquisitionRetentionPolicy,
    AcquisitionRetentionReceipt,
    AcquisitionSeedSetting,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    AcquisitionTransportAttempt,
    AcquisitionTransportStatus,
    AcquisitionTripwireCounters,
    CannedTransportEnvelope,
    FROZEN_ACQUISITION_FAILURE_TAXONOMY,
    FROZEN_ACQUISITION_VALIDATION_ORDER,
    FROZEN_REQUIRED_CONTROL_STATES,
    PromptRetentionMode,
    ResourceKnowledgeState,
    ResponseRetentionMode,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id


ACQUISITION_CASE_RESULT_SCHEMA_V0 = "socrateszero-acquisition-case-result/v0"
ACQUISITION_METRICS_SCHEMA_V0 = "socrateszero-acquisition-metrics/v0"
ACQUISITION_ARTIFACT_SCHEMA_V0 = "socrateszero-acquisition-artifact/v0"
ACQUISITION_REPLAY_LOCK_SCHEMA_V0 = "socrateszero-acquisition-replay-lock/v0"
ACQUISITION_HISTORICAL_HASH_SCHEMA_V0 = (
    "socrateszero-acquisition-historical-hash/v0"
)
ACQUISITION_FIXTURE_SET_SCHEMA_V0 = "socrateszero-acquisition-fixture-set/v0"
ACQUISITION_ATTEMPT_EVIDENCE_SCHEMA_V0 = (
    "socrateszero-acquisition-attempt-evidence/v0"
)
ACQUISITION_CONSTRUCTION_STATE_SCHEMA_V0 = (
    "socrateszero-acquisition-construction-state/v0"
)
ACQUISITION_MUTATION_OBSERVATION_SCHEMA_V0 = (
    "socrateszero-acquisition-mutation-observation/v0"
)
ACQUISITION_PROBE_CONSTRUCTION_SCHEMA_V0 = (
    "socrateszero-acquisition-probe-construction/v0"
)
ACQUISITION_REPLAY_EXECUTION_SCHEMA_V0 = (
    "socrateszero-acquisition-replay-execution/v0"
)
ACQUISITION_EXPERIMENT_ID_V0 = "socrateszero-live-acquisition-contract/v0"
ACQUISITION_PROVIDER_ID_V0 = "phase8-recorded-seat-1"
ACQUISITION_MODEL_ID_V0 = "phase8-recorded-model/1"
ACQUISITION_ADAPTER_ID_V0 = "socrateszero-canned-adapter/v0"
ACQUISITION_ADAPTER_VERSION_V0 = "0"
ACQUISITION_PROVIDER_VISIBLE_RENDERING_VERSION_V0 = (
    "socrateszero-canonical-json-utf8/v0"
)

_HEX64 = r"^[0-9a-f]{64}$"
_ACTION_ID = (
    "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
)
_SOURCE_CAPSULE_ID = (
    "cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50"
)
_SOURCE_EXECUTION_ID = (
    "cedexecution_c90d438f2737bcbe3aff9a349412a18671ac88bbf1c4afc743f854b9b09312f6"
)
_ROOT_STATE_V1_ID = (
    "szstatev1_a17ce47c27894a3aac4095d0c08da107142a54d2b773c10104fde2b250c2f20e"
)
_PENDING_TRANSITION_ID = (
    "cedpending_3111a26bb87ea7b0fe5a1658ffc86a6313fa66b4ac2f167095c0393bea85c31a"
)
_CANONICAL_TASK_ID = (
    "cedtasksemantic_b5ace018c4bb1369d62bb5004a99edcd8945e4dd0eef1e206570c96b1d71017a"
)
_HISTORICAL_PROVENANCE_ID = "fixture://socrateszero/acquisition/history-v0"
_RETENTION_CLASSIFICATION = "non-sensitive-canned-research-v0"
_RETENTION_REASON = "deterministic acquisition replay"
_RETENTION_ACCESS_POLICY_ID = "socrateszero-canned-fixture-access/v0"
_BASELINE_BRANCH_PREFIX = "acqv0-branch"
_FINGERPRINT_DIGESTS = {
    "source": hashlib.sha256(b"acquisition-source-v0").hexdigest(),
    "sibling": hashlib.sha256(b"acquisition-sibling-v0").hexdigest(),
    "production": hashlib.sha256(b"acquisition-production-v0").hexdigest(),
}

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
)


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must be nonblank")
    return value


def _canonical_strings(values: Tuple[str, ...], field_name: str) -> Tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise ContractValidationError(f"{field_name} contains a blank value")
    canonical = tuple(sorted(set(values)))
    if len(canonical) != len(values):
        raise ContractValidationError(f"{field_name} contains duplicates")
    return canonical


class _FrozenEvaluationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_json_string(value: str, field_name: str) -> str:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} is not JSON") from exc
    canonical = canonical_json(parsed)
    if value != canonical:
        raise ContractValidationError(f"{field_name} is not canonical JSON")
    return value


class AcquisitionCaseAttemptEvidenceV0(_FrozenEvaluationContract):
    """Aligned evaluator projection of one immutable runtime attempt receipt."""

    schema_version: Literal[
        ACQUISITION_ATTEMPT_EVIDENCE_SCHEMA_V0
    ] = ACQUISITION_ATTEMPT_EVIDENCE_SCHEMA_V0
    attempt_evidence_id: Optional[str] = None
    attempt_receipt_id: str
    transport_attempt_id: str
    semantic_request_id: str
    branch_id: str
    attempt_ordinal: int = Field(ge=0, strict=True)
    capability_snapshot_id: str
    control_policy_id: str
    provider_visible_prompt_digest: str = Field(pattern=_HEX64)
    isolation_receipt_id: str
    retention_receipt_id: str
    primary_result: AcquisitionPrimaryResult
    guard_evaluations: Tuple[AcquisitionGuardEvaluation, ...]
    tripwire_counters: AcquisitionTripwireCounters

    _nonblank_fields = field_validator(
        "attempt_receipt_id",
        "transport_attempt_id",
        "semantic_request_id",
        "branch_id",
        "capability_snapshot_id",
        "control_policy_id",
        "isolation_receipt_id",
        "retention_receipt_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionCaseAttemptEvidenceV0":
        if tuple(item.guard_id for item in self.guard_evaluations) != ACQUISITION_GUARD_ORDER:
            raise ContractValidationError("attempt evidence guard order changed")
        payload = self.model_dump(mode="json", exclude={"attempt_evidence_id"})
        expected_id = stable_contract_id("acqattemptevidencev0", payload)
        if (
            self.attempt_evidence_id is not None
            and self.attempt_evidence_id != expected_id
        ):
            raise ContractValidationError("attempt-evidence ID mismatch")
        object.__setattr__(self, "attempt_evidence_id", expected_id)
        return self


class AcquisitionConstructionStateV0(_FrozenEvaluationContract):
    """Canonical serialization of the concrete objects supplied to one runtime."""

    schema_version: Literal[
        ACQUISITION_CONSTRUCTION_STATE_SCHEMA_V0
    ] = ACQUISITION_CONSTRUCTION_STATE_SCHEMA_V0
    construction_state_id: Optional[str] = None
    capability_snapshot_id: str
    capability_snapshot_json: str
    control_policy_id: str
    control_policy_json: str
    semantic_request_id: str
    semantic_request_json: str
    semantic_request_contract_valid: bool
    transport_capability_snapshot_id: str
    implementation_profiles: Tuple[str, ...]
    directive_json: str
    isolation_runtime_digests: Tuple[Tuple[str, str], ...]
    future_label_candidate_rejected: bool = False

    _nonblank_fields = field_validator(
        "capability_snapshot_id",
        "control_policy_id",
        "semantic_request_id",
        "transport_capability_snapshot_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionConstructionStateV0":
        for name in (
            "capability_snapshot_json",
            "control_policy_json",
            "semantic_request_json",
            "directive_json",
        ):
            _canonical_json_string(getattr(self, name), name)
        capability = AcquisitionCapabilitySnapshot.model_validate_json(
            self.capability_snapshot_json
        )
        policy = AcquisitionControlPolicy.model_validate_json(self.control_policy_json)
        if (
            capability.capability_snapshot_id != self.capability_snapshot_id
            or policy.control_policy_id != self.control_policy_id
            or self.transport_capability_snapshot_id != self.capability_snapshot_id
        ):
            raise ContractValidationError("construction state object identity mismatch")
        request_valid = True
        try:
            request = AcquisitionSemanticRequest.model_validate_json(
                self.semantic_request_json
            )
        except ValidationError:
            request_valid = False
        else:
            if (
                request.semantic_request_id != self.semantic_request_id
                or request.capability_snapshot_id != self.capability_snapshot_id
                or request.control_policy_id != self.control_policy_id
            ):
                raise ContractValidationError("construction request links changed")
        if self.semantic_request_contract_valid is not request_valid:
            raise ContractValidationError("construction request-valid flag changed")
        profiles = _canonical_strings(
            tuple(self.implementation_profiles), "implementation_profiles"
        )
        if not profiles:
            raise ContractValidationError("construction state requires a profile")
        digests = tuple(sorted(self.isolation_runtime_digests))
        if tuple(item[0] for item in digests) != ("production", "sibling", "source"):
            raise ContractValidationError("construction isolation coverage changed")
        if any(
            not scope.strip() or len(digest) != 64
            for scope, digest in digests
        ):
            raise ContractValidationError("construction isolation digest changed")
        object.__setattr__(self, "implementation_profiles", profiles)
        object.__setattr__(self, "isolation_runtime_digests", digests)
        payload = self.model_dump(mode="json", exclude={"construction_state_id"})
        expected_id = stable_contract_id("acqconstructionstatev0", payload)
        if (
            self.construction_state_id is not None
            and self.construction_state_id != expected_id
        ):
            raise ContractValidationError("construction-state ID mismatch")
        object.__setattr__(self, "construction_state_id", expected_id)
        return self


class AcquisitionMutationObservationV0(_FrozenEvaluationContract):
    """One literal checked against a concrete baseline/probe construction pair."""

    schema_version: Literal[
        ACQUISITION_MUTATION_OBSERVATION_SCHEMA_V0
    ] = ACQUISITION_MUTATION_OBSERVATION_SCHEMA_V0
    mutation_observation_id: Optional[str] = None
    path: str
    authoritative_source: str
    literal_before_json: str
    literal_after_json: str
    observed_before_json: str
    observed_after_json: str
    concrete_before_json: str
    concrete_after_json: str
    literal_match: bool
    concrete_change_observed: bool

    _nonblank_fields = field_validator("path", "authoritative_source")(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionMutationObservationV0":
        for name in (
            "literal_before_json",
            "literal_after_json",
            "observed_before_json",
            "observed_after_json",
            "concrete_before_json",
            "concrete_after_json",
        ):
            _canonical_json_string(getattr(self, name), name)
        expected_match = (
            self.literal_before_json == self.observed_before_json
            and self.literal_after_json == self.observed_after_json
        )
        expected_change = self.concrete_before_json != self.concrete_after_json
        if self.literal_match is not expected_match:
            raise ContractValidationError("mutation literal-match flag changed")
        if self.concrete_change_observed is not expected_change:
            raise ContractValidationError("mutation concrete-change flag changed")
        payload = self.model_dump(mode="json", exclude={"mutation_observation_id"})
        expected_id = stable_contract_id("acqmutationobservationv0", payload)
        if (
            self.mutation_observation_id is not None
            and self.mutation_observation_id != expected_id
        ):
            raise ContractValidationError("mutation-observation ID mismatch")
        object.__setattr__(self, "mutation_observation_id", expected_id)
        return self


class AcquisitionProbeConstructionEvidenceV0(_FrozenEvaluationContract):
    """Immutable evidence that the scored probe was the constructed probe."""

    schema_version: Literal[
        ACQUISITION_PROBE_CONSTRUCTION_SCHEMA_V0
    ] = ACQUISITION_PROBE_CONSTRUCTION_SCHEMA_V0
    construction_evidence_id: Optional[str] = None
    probe_id: str
    baseline: AcquisitionConstructionStateV0
    probe: AcquisitionConstructionStateV0
    observations: Tuple[AcquisitionMutationObservationV0, ...]
    measured_mutation_vector: AcquisitionMutationVectorV0
    construction_errors: Tuple[str, ...] = ()
    construction_valid: bool

    _probe_id_nonblank = field_validator("probe_id")(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionProbeConstructionEvidenceV0":
        observations = tuple(sorted(self.observations, key=lambda item: item.path))
        if not observations or len({item.path for item in observations}) != len(
            observations
        ):
            raise ContractValidationError("construction observation membership changed")
        errors = _canonical_strings(tuple(self.construction_errors), "construction_errors")
        expected_valid = (
            not errors
            and all(item.literal_match for item in observations)
            and all(item.concrete_change_observed for item in observations)
        )
        if self.construction_valid is not expected_valid:
            raise ContractValidationError("construction-valid flag changed")
        expected_vector = _project_mutation_vector_from_paths_v0(
            tuple(item.path for item in observations)
        )
        if self.measured_mutation_vector != expected_vector:
            raise ContractValidationError("construction mutation vector changed")
        _validate_probe_construction_observations_v0(self)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "construction_errors", errors)
        payload = self.model_dump(mode="json", exclude={"construction_evidence_id"})
        expected_id = stable_contract_id("acqconstructionevidencev0", payload)
        if (
            self.construction_evidence_id is not None
            and self.construction_evidence_id != expected_id
        ):
            raise ContractValidationError("construction-evidence ID mismatch")
        object.__setattr__(self, "construction_evidence_id", expected_id)
        return self


class AcquisitionCaseResultV0(_FrozenEvaluationContract):
    """Evaluator-owned evidence for one frozen case or probe."""

    schema_version: Literal[
        ACQUISITION_CASE_RESULT_SCHEMA_V0
    ] = ACQUISITION_CASE_RESULT_SCHEMA_V0
    case_result_id: Optional[str] = None
    case_id: str
    case_fingerprint: str = Field(pattern=_HEX64)
    case_class: AcquisitionCaseClass
    attempt_evidence: Tuple[AcquisitionCaseAttemptEvidenceV0, ...]
    construction_evidence: Optional[AcquisitionProbeConstructionEvidenceV0] = None
    literal_mutations: Tuple[AcquisitionLiteralMutationV0, ...] = ()
    expected_mutation_vector: Optional[AcquisitionMutationVectorV0] = None
    measured_mutation_vector: Optional[AcquisitionMutationVectorV0] = None
    expected_outcome: AcquisitionAttemptOutcome
    expected_guard_id: Optional[AcquisitionGuardId] = None
    expected_failure_code: Optional[AcquisitionFailureCode] = None
    actual_primary_results: Tuple[AcquisitionPrimaryResult, ...]
    attempt_receipt_ids: Tuple[str, ...]
    transport_attempt_ids: Tuple[str, ...]
    semantic_request_ids: Tuple[str, ...]
    branch_ids: Tuple[str, ...]
    provider_visible_prompt_digests: Tuple[str, ...]
    isolation_receipt_ids: Tuple[str, ...]
    retention_receipt_ids: Tuple[str, ...]
    expected_canned_invocations: int = Field(ge=0, strict=True)
    observed_canned_invocations: int = Field(ge=0, strict=True)
    injected_negative_conditions: Tuple[str, ...] = ()
    accepted_violations: Tuple[str, ...] = ()
    fixture_construction_valid: bool
    mutation_vector_exact: bool
    primary_result_exact: bool
    guard_trace_exact: bool
    invocation_count_exact: bool
    receipt_count_exact: bool
    complete_receipts: bool
    case_passed: bool

    _case_id_nonblank = field_validator("case_id")(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionCaseResultV0":
        is_positive = self.case_class is AcquisitionCaseClass.POSITIVE
        if is_positive != (not self.literal_mutations):
            raise ContractValidationError(
                "positive results have no mutations; probes require mutations"
            )
        if is_positive:
            if any(
                value is not None
                for value in (
                    self.expected_mutation_vector,
                    self.measured_mutation_vector,
                    self.expected_guard_id,
                    self.expected_failure_code,
                )
            ):
                raise ContractValidationError(
                    "positive result cannot contain probe-only expectations"
                )
            if self.injected_negative_conditions:
                raise ContractValidationError(
                    "positive result cannot contain injected negative conditions"
                )
            if self.construction_evidence is not None:
                raise ContractValidationError(
                    "positive result cannot contain probe construction evidence"
                )
        else:
            if any(
                value is None
                for value in (
                    self.expected_mutation_vector,
                    self.measured_mutation_vector,
                    self.expected_guard_id,
                    self.expected_failure_code,
                )
            ):
                raise ContractValidationError(
                    "probe result requires mutation and primary-result expectations"
                )
            if (
                self.construction_evidence is None
                or self.construction_evidence.probe_id != self.case_id
            ):
                raise ContractValidationError(
                    "probe result requires matching construction evidence"
                )
        positive_case = next(
            (
                item
                for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0
                if item.case_id == self.case_id
            ),
            None,
        )
        probe_case = next(
            (
                item
                for item in (
                    FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
                    + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
                )
                if item.probe_id == self.case_id
            ),
            None,
        )
        if is_positive:
            if positive_case is None:
                raise ContractValidationError("unknown positive case result")
            expected_count = positive_case.attempt_count
            expected_trace = tuple(
                (guard_id, AcquisitionGuardState.PASSED)
                for guard_id in ACQUISITION_GUARD_ORDER
            )
        else:
            if probe_case is None:
                raise ContractValidationError("unknown probe result")
            expected_count = probe_case.expected_attempt_receipts
            expected_trace = tuple(
                (item.guard_id, item.state)
                for item in probe_case.expected_guard_trace
            )
        attempts = tuple(sorted(self.attempt_evidence, key=lambda item: item.attempt_ordinal))
        if len({item.attempt_ordinal for item in attempts}) != len(attempts):
            raise ContractValidationError("case attempt ordinals contain duplicates")
        object.__setattr__(self, "attempt_evidence", attempts)
        for name in (
            "attempt_receipt_ids",
            "transport_attempt_ids",
            "semantic_request_ids",
            "branch_ids",
            "provider_visible_prompt_digests",
            "isolation_receipt_ids",
            "retention_receipt_ids",
            "injected_negative_conditions",
            "accepted_violations",
        ):
            object.__setattr__(
                self,
                name,
                _canonical_strings(tuple(getattr(self, name)), name),
            )
        expected_primary = AcquisitionPrimaryResult(
            outcome=self.expected_outcome,
            primary_guard_id=self.expected_guard_id,
            failure_code=self.expected_failure_code,
        )
        derived_primary_results = tuple(item.primary_result for item in attempts)
        derived_receipt_ids = tuple(sorted(item.attempt_receipt_id for item in attempts))
        derived_transport_ids = tuple(
            sorted(item.transport_attempt_id for item in attempts)
        )
        derived_semantic_ids = tuple(sorted({item.semantic_request_id for item in attempts}))
        derived_branch_ids = tuple(sorted(item.branch_id for item in attempts))
        derived_prompt_digests = tuple(
            sorted({item.provider_visible_prompt_digest for item in attempts})
        )
        derived_isolation_ids = tuple(
            sorted(item.isolation_receipt_id for item in attempts)
        )
        derived_retention_ids = tuple(
            sorted(item.retention_receipt_id for item in attempts)
        )
        if any(
            (
                self.actual_primary_results != derived_primary_results,
                self.attempt_receipt_ids != derived_receipt_ids,
                self.transport_attempt_ids != derived_transport_ids,
                self.semantic_request_ids != derived_semantic_ids,
                self.branch_ids != derived_branch_ids,
                self.provider_visible_prompt_digests != derived_prompt_digests,
                self.isolation_receipt_ids != derived_isolation_ids,
                self.retention_receipt_ids != derived_retention_ids,
            )
        ):
            raise ContractValidationError("case result differs from aligned attempt evidence")
        derived_fixture_valid = (
            self.fixture_construction_valid
            if is_positive
            else bool(
                self.construction_evidence
                and self.construction_evidence.construction_valid
            )
        )
        derived_vector_exact = (
            True
            if is_positive
            else bool(
                self.construction_evidence
                and self.expected_mutation_vector
                == self.construction_evidence.measured_mutation_vector
                == self.measured_mutation_vector
            )
        )
        derived_primary_exact = (
            len(attempts) == expected_count
            and all(item.primary_result == expected_primary for item in attempts)
        )
        derived_guard_exact = len(attempts) == expected_count and all(
            tuple((row.guard_id, row.state) for row in item.guard_evaluations)
            == expected_trace
            for item in attempts
        )
        derived_observed_invocations = sum(
            item.tripwire_counters.canned_transport_invocations for item in attempts
        )
        derived_invocation_exact = (
            derived_observed_invocations == self.expected_canned_invocations
        )
        derived_receipt_count_exact = len(attempts) == expected_count
        claimed_and_derived = (
            (self.fixture_construction_valid, derived_fixture_valid),
            (self.mutation_vector_exact, derived_vector_exact),
            (self.primary_result_exact, derived_primary_exact),
            (self.guard_trace_exact, derived_guard_exact),
            (self.invocation_count_exact, derived_invocation_exact),
            (self.receipt_count_exact, derived_receipt_count_exact),
        )
        if any(claimed is not derived for claimed, derived in claimed_and_derived):
            raise ContractValidationError("case exactness flag differs from evidence")
        if self.observed_canned_invocations != derived_observed_invocations:
            raise ContractValidationError("case invocation count differs from evidence")
        derived_passed = all(
            (
                derived_fixture_valid,
                derived_vector_exact,
                derived_primary_exact,
                derived_guard_exact,
                derived_invocation_exact,
                derived_receipt_count_exact,
                self.complete_receipts,
                not self.accepted_violations,
            )
        )
        if self.case_passed is not derived_passed:
            raise ContractValidationError("case_passed differs from evaluator evidence")
        payload = self.model_dump(mode="json", exclude={"case_result_id"})
        expected_id = stable_contract_id("acqcaseresultv0", payload)
        if self.case_result_id is not None and self.case_result_id != expected_id:
            raise ContractValidationError("acquisition case-result ID mismatch")
        object.__setattr__(self, "case_result_id", expected_id)
        return self


class AcquisitionHistoricalHashEvidenceV0(_FrozenEvaluationContract):
    schema_version: Literal[
        ACQUISITION_HISTORICAL_HASH_SCHEMA_V0
    ] = ACQUISITION_HISTORICAL_HASH_SCHEMA_V0
    label: str
    repository_path: str
    expected_sha256: str = Field(pattern=_HEX64)
    actual_sha256: Optional[str] = Field(default=None, pattern=_HEX64)
    matches: bool

    _nonblank_fields = field_validator("label", "repository_path")(_nonblank)

    @model_validator(mode="after")
    def validate_match(self) -> "AcquisitionHistoricalHashEvidenceV0":
        frozen = {
            label: (repository_path.replace("\\", "/"), expected)
            for label, repository_path, expected in _HISTORICAL_ARTIFACT_LOCKS
        }
        if frozen.get(self.label) != (
            self.repository_path.replace("\\", "/"),
            self.expected_sha256,
        ):
            raise ContractValidationError("historical lock metadata changed")
        if self.matches is not (
            self.actual_sha256 is not None
            and self.actual_sha256 == self.expected_sha256
        ):
            raise ContractValidationError("historical hash match flag differs")
        return self


def _validate_historical_hash_membership_v0(
    historical_hashes: Sequence[AcquisitionHistoricalHashEvidenceV0],
) -> Tuple[AcquisitionHistoricalHashEvidenceV0, ...]:
    rows = tuple(sorted(historical_hashes, key=lambda item: item.label))
    expected = tuple(
        sorted(
            (
                label,
                repository_path.replace("\\", "/"),
                digest,
            )
            for label, repository_path, digest in _HISTORICAL_ARTIFACT_LOCKS
        )
    )
    actual = tuple(
        (item.label, item.repository_path.replace("\\", "/"), item.expected_sha256)
        for item in rows
    )
    if actual != expected:
        raise ContractValidationError("artifact historical-lock membership changed")
    return rows


class AcquisitionEvaluationMetricsV0(_FrozenEvaluationContract):
    schema_version: Literal[
        ACQUISITION_METRICS_SCHEMA_V0
    ] = ACQUISITION_METRICS_SCHEMA_V0
    metrics_id: Optional[str] = None
    cases_total: int = Field(ge=0, strict=True)
    positive_cases_total: int = Field(ge=0, strict=True)
    positive_complete_case_results: int = Field(ge=0, strict=True)
    positive_attempt_receipts: int = Field(ge=0, strict=True)
    orthogonal_probes_total: int = Field(ge=0, strict=True)
    orthogonal_exact_primary_results: int = Field(ge=0, strict=True)
    precedence_probes_total: int = Field(ge=0, strict=True)
    precedence_exact_primary_results: int = Field(ge=0, strict=True)
    attempt_receipts_total: int = Field(ge=0, strict=True)
    observed_canned_transport_invocations: int = Field(ge=0, strict=True)
    invalid_probe_constructions: int = Field(ge=0, strict=True)
    semantic_identity_collisions: int = Field(ge=0, strict=True)
    accepted_prompt_byte_mismatches: int = Field(ge=0, strict=True)
    external_network_attempts: int = Field(ge=0, strict=True)
    credential_access_attempts: int = Field(ge=0, strict=True)
    live_provider_calls: int = Field(ge=0, strict=True)
    provider_sdk_calls: int = Field(ge=0, strict=True)
    model_executions: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)
    canonical_application_invocations: int = Field(ge=0, strict=True)
    injected_uncounted_canned_invocations: int = Field(ge=0, strict=True)
    accepted_uncounted_canned_invocations: int = Field(ge=0, strict=True)
    accepted_successful_retry_activations: int = Field(ge=0, strict=True)
    accepted_successful_fallback_activations: int = Field(ge=0, strict=True)
    accepted_timeout_worker_leaks: int = Field(ge=0, strict=True)
    injected_source_mutations: int = Field(ge=0, strict=True)
    injected_sibling_mutations: int = Field(ge=0, strict=True)
    injected_production_mutations: int = Field(ge=0, strict=True)
    accepted_source_mutations: int = Field(ge=0, strict=True)
    accepted_sibling_mutations: int = Field(ge=0, strict=True)
    accepted_production_mutations: int = Field(ge=0, strict=True)
    injected_missing_raw_conditions: int = Field(ge=0, strict=True)
    accepted_missing_raw_observations: int = Field(ge=0, strict=True)
    injected_false_zero_usage_conditions: int = Field(ge=0, strict=True)
    accepted_false_zero_usage: int = Field(ge=0, strict=True)
    injected_incomplete_usage_conditions: int = Field(ge=0, strict=True)
    accepted_incomplete_attempt_receipts: int = Field(ge=0, strict=True)
    injected_retention_conditions: int = Field(ge=0, strict=True)
    accepted_retention_violations: int = Field(ge=0, strict=True)
    injected_receipt_mismatch_conditions: int = Field(ge=0, strict=True)
    accepted_receipt_mismatches: int = Field(ge=0, strict=True)
    injected_future_label_conditions: int = Field(ge=0, strict=True)
    accepted_future_label_violations: int = Field(ge=0, strict=True)
    new_tokens: int = Field(ge=0, strict=True)
    new_cost_microusd: int = Field(ge=0, strict=True)
    external_provider_wall_time_ms: int = Field(ge=0, strict=True)
    historical_lock_mismatches: int = Field(ge=0, strict=True)
    mismatch_or_failure_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionEvaluationMetricsV0":
        payload = self.model_dump(mode="json", exclude={"metrics_id"})
        expected_id = stable_contract_id("acqmetricsv0", payload)
        if self.metrics_id is not None and self.metrics_id != expected_id:
            raise ContractValidationError("acquisition metrics ID mismatch")
        object.__setattr__(self, "metrics_id", expected_id)
        return self


class AcquisitionFixtureSetV0(_FrozenEvaluationContract):
    """Frozen, validated positive fixture family used by the harness."""

    schema_version: Literal[
        ACQUISITION_FIXTURE_SET_SCHEMA_V0
    ] = ACQUISITION_FIXTURE_SET_SCHEMA_V0
    fixture_set_id: Optional[str] = None
    capability_snapshot: AcquisitionCapabilitySnapshot
    control_policy: AcquisitionControlPolicy
    semantic_request: AcquisitionSemanticRequest
    retention_policy: AcquisitionRetentionPolicy
    known_historical_usage: AcquisitionHistoricalUsage
    unknown_historical_usage: AcquisitionHistoricalUsage

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "AcquisitionFixtureSetV0":
        if (
            self.semantic_request.capability_snapshot_id
            != self.capability_snapshot.capability_snapshot_id
            or self.semantic_request.control_policy_id
            != self.control_policy.control_policy_id
        ):
            raise ContractValidationError("fixture semantic links do not match")
        payload = self.model_dump(mode="json", exclude={"fixture_set_id"})
        expected_id = stable_contract_id("acqfixturesv0", payload)
        if self.fixture_set_id is not None and self.fixture_set_id != expected_id:
            raise ContractValidationError("acquisition fixture-set ID mismatch")
        object.__setattr__(self, "fixture_set_id", expected_id)
        return self


class AcquisitionExperimentArtifactV0(_FrozenEvaluationContract):
    """Complete evaluator artifact required by mandate sections 65 and 67."""

    schema_version: Literal[
        ACQUISITION_ARTIFACT_SCHEMA_V0
    ] = ACQUISITION_ARTIFACT_SCHEMA_V0
    artifact_id: Optional[str] = None
    acquisition_contract_id: Literal[ACQUISITION_CONTRACT_ID] = ACQUISITION_CONTRACT_ID
    experiment_id: Literal[
        ACQUISITION_EXPERIMENT_ID_V0
    ] = ACQUISITION_EXPERIMENT_ID_V0
    semantic_request_schema_version: Literal[
        ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION
    ] = ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION
    semantic_request_id_scheme: Literal[
        "stable-contract-id:szacqrequest"
    ] = "stable-contract-id:szacqrequest"
    transport_attempt_schema_version: Literal[
        ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION
    ] = ACQUISITION_TRANSPORT_ATTEMPT_SCHEMA_VERSION
    transport_attempt_id_scheme: Literal[
        "stable-contract-id:szacqattempt"
    ] = "stable-contract-id:szacqattempt"
    provider_visible_request_schema_version: Literal[
        PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION
    ] = PROVIDER_VISIBLE_REQUEST_SCHEMA_VERSION
    provider_visible_renderer_version: Literal[
        ACQUISITION_PROVIDER_VISIBLE_RENDERING_VERSION_V0
    ] = ACQUISITION_PROVIDER_VISIBLE_RENDERING_VERSION_V0
    canned_runtime_version: Literal[
        "socrateszero-canned-acquisition-runtime/v0"
    ] = "socrateszero-canned-acquisition-runtime/v0"
    validation_order_id: str
    failure_taxonomy_id: str
    canned_transport_id: Literal[CANNED_TRANSPORT_ID] = CANNED_TRANSPORT_ID
    case_set_id: str
    case_set_sha256: str = Field(pattern=_HEX64)
    harness_id: Literal[ACQUISITION_HARNESS_ID_V0] = ACQUISITION_HARNESS_ID_V0
    thresholds_id: str
    thresholds: AcquisitionThresholdsV0
    fixture_set_id: str
    capability_snapshot_ids: Tuple[str, ...]
    control_policy_ids: Tuple[str, ...]
    semantic_request_ids: Tuple[str, ...]
    transport_attempt_ids: Tuple[str, ...]
    case_results: Tuple[AcquisitionCaseResultV0, ...]
    metrics_id: str
    metrics: AcquisitionEvaluationMetricsV0
    aggregate_receipt: AcquisitionAggregateReceipt
    attempt_receipt_ids: Tuple[str, ...]
    isolation_receipts: Tuple[AcquisitionIsolationReceipt, ...]
    retention_receipts: Tuple[AcquisitionRetentionReceipt, ...]
    provider_visible_prompt_digests: Tuple[str, ...]
    historical_hashes: Tuple[AcquisitionHistoricalHashEvidenceV0, ...]
    tripwire_counters: AcquisitionTripwireCounters
    hypothesis_status: Literal["SUPPORTED", "FALSIFIED"]
    production_authority: Literal["none"] = "none"

    _nonblank_fields = field_validator(
        "validation_order_id",
        "failure_taxonomy_id",
        "case_set_id",
        "thresholds_id",
        "fixture_set_id",
        "metrics_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionExperimentArtifactV0":
        results = tuple(sorted(self.case_results, key=lambda item: item.case_id))
        isolations = tuple(
            sorted(
                self.isolation_receipts,
                key=lambda item: item.isolation_receipt_id or "",
            )
        )
        retentions = tuple(
            sorted(
                self.retention_receipts,
                key=lambda item: item.retention_receipt_id or "",
            )
        )
        histories = _validate_historical_hash_membership_v0(self.historical_hashes)
        object.__setattr__(self, "case_results", results)
        object.__setattr__(self, "isolation_receipts", isolations)
        object.__setattr__(self, "retention_receipts", retentions)
        object.__setattr__(self, "historical_hashes", histories)
        for name in (
            "capability_snapshot_ids",
            "control_policy_ids",
            "semantic_request_ids",
            "transport_attempt_ids",
            "attempt_receipt_ids",
            "provider_visible_prompt_digests",
        ):
            object.__setattr__(
                self,
                name,
                _canonical_strings(tuple(getattr(self, name)), name),
            )
        if (
            self.validation_order_id
            != FROZEN_ACQUISITION_VALIDATION_ORDER.validation_order_id
            or self.failure_taxonomy_id
            != FROZEN_ACQUISITION_FAILURE_TAXONOMY.failure_taxonomy_id
            or self.case_set_id != FROZEN_ACQUISITION_CASE_SET_V0.case_set_id
            or self.case_set_sha256 != frozen_acquisition_case_set_sha256_v0()
            or self.thresholds != FROZEN_ACQUISITION_THRESHOLDS_V0
            or self.thresholds_id != self.thresholds.thresholds_id
            or self.fixture_set_id
            != build_frozen_acquisition_fixtures_v0().fixture_set_id
            or self.metrics_id != self.metrics.metrics_id
            or self.tripwire_counters != self.aggregate_receipt.observed_counters
            or self.aggregate_receipt.experiment_id != self.experiment_id
            or self.aggregate_receipt.case_set_id != self.case_set_id
        ):
            raise ContractValidationError("artifact frozen methodology changed")
        expected_case_ids = {
            item.case_id for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0
        } | {
            item.probe_id
            for item in (
                FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
                + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
            )
        }
        if len(results) != 49 or {item.case_id for item in results} != expected_case_ids:
            raise ContractValidationError("artifact case membership changed")
        _validate_case_results_against_frozen_v0(results)
        aggregate_receipt_ids = tuple(
            sorted(
                item.receipt_id or ""
                for item in self.aggregate_receipt.attempt_receipts
            )
        )
        if aggregate_receipt_ids != self.attempt_receipt_ids:
            raise ContractValidationError(
                "artifact attempt receipts differ from aggregate receipt"
            )
        _validate_case_result_receipt_links_v0(
            results,
            self.aggregate_receipt,
            isolations,
            retentions,
        )
        receipts = self.aggregate_receipt.attempt_receipts
        isolation_ids = tuple(sorted(item.isolation_receipt_id or "" for item in isolations))
        retention_ids = tuple(sorted(item.retention_receipt_id or "" for item in retentions))
        if (
            tuple(sorted(item.transport_attempt_id for item in receipts))
            != self.transport_attempt_ids
            or isolation_ids
            != tuple(sorted(item.isolation_receipt_id for item in receipts))
            or retention_ids
            != tuple(sorted(item.retention_receipt_id for item in receipts))
            or tuple(sorted({item.capability_snapshot_id for item in receipts}))
            != self.capability_snapshot_ids
            or tuple(sorted({item.control_policy_id for item in receipts}))
            != self.control_policy_ids
            or tuple(sorted({item.semantic_request_id for item in receipts}))
            != self.semantic_request_ids
            or tuple(sorted({item.provider_visible_request_digest for item in receipts}))
            != self.provider_visible_prompt_digests
        ):
            raise ContractValidationError("artifact receipt or attempt identity changed")
        expected_metrics = _calculate_evaluation_metrics_v0(
            results,
            self.aggregate_receipt,
            histories,
        )
        if self.metrics != expected_metrics:
            raise ContractValidationError("artifact metrics do not match evidence")
        supported = supports_acquisition_metrics_v0(self.metrics, self.thresholds)
        if self.hypothesis_status != ("SUPPORTED" if supported else "FALSIFIED"):
            raise ContractValidationError("artifact hypothesis status is inconsistent")
        payload = self.model_dump(mode="json", exclude={"artifact_id"})
        expected_id = stable_contract_id("acqartifactv0", payload)
        if self.artifact_id is not None and self.artifact_id != expected_id:
            raise ContractValidationError("acquisition artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected_id)
        return self


class AcquisitionReplayExecutionV0(_FrozenEvaluationContract):
    """Reverse-order run provenance kept outside byte-identical semantic artifact."""

    schema_version: Literal[
        ACQUISITION_REPLAY_EXECUTION_SCHEMA_V0
    ] = ACQUISITION_REPLAY_EXECUTION_SCHEMA_V0
    replay_execution_id: Optional[str] = None
    source_authoritative_artifact_id: str
    source_authoritative_sha256: str = Field(pattern=_HEX64)
    artifact: AcquisitionExperimentArtifactV0
    positive_order: Tuple[str, ...]
    orthogonal_order: Tuple[str, ...]
    precedence_order: Tuple[str, ...]
    ordered_case_ids: Tuple[str, ...]
    ordered_case_result_ids: Tuple[str, ...]
    ordered_transport_attempt_ids: Tuple[str, ...]
    execution_trace_sha256: Optional[str] = Field(default=None, pattern=_HEX64)
    execution_role: Literal["REVERSE_REPLAY"] = "REVERSE_REPLAY"

    _authoritative_id_nonblank = field_validator(
        "source_authoritative_artifact_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionReplayExecutionV0":
        if self.artifact.hypothesis_status != "SUPPORTED":
            raise ContractValidationError("replay execution requires a SUPPORTED artifact")
        artifact_sha = acquisition_experiment_artifact_sha256_v0(self.artifact)
        if (
            self.artifact.artifact_id != self.source_authoritative_artifact_id
            or artifact_sha != self.source_authoritative_sha256
        ):
            raise ContractValidationError("replay artifact differs from authoritative source")
        if (
            self.positive_order != FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0
            or self.orthogonal_order != FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0
            or self.precedence_order != FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0
        ):
            raise ContractValidationError("replay execution order is not frozen reverse order")
        expected_case_ids = (
            self.positive_order + self.orthogonal_order + self.precedence_order
        )
        if self.ordered_case_ids != expected_case_ids:
            raise ContractValidationError("replay ordered case evidence changed")
        results = {item.case_id: item for item in self.artifact.case_results}
        expected_result_ids = tuple(
            results[case_id].case_result_id or "" for case_id in expected_case_ids
        )
        expected_attempt_ids = tuple(
            attempt.transport_attempt_id
            for case_id in expected_case_ids
            for attempt in sorted(
                results[case_id].attempt_evidence,
                key=lambda item: item.attempt_ordinal,
            )
        )
        if (
            self.ordered_case_result_ids != expected_result_ids
            or self.ordered_transport_attempt_ids != expected_attempt_ids
        ):
            raise ContractValidationError("replay execution trace is not artifact-linked")
        trace_payload = {
            "execution_role": self.execution_role,
            "positive_order": list(self.positive_order),
            "orthogonal_order": list(self.orthogonal_order),
            "precedence_order": list(self.precedence_order),
            "ordered_case_ids": list(self.ordered_case_ids),
            "ordered_case_result_ids": list(self.ordered_case_result_ids),
            "ordered_transport_attempt_ids": list(self.ordered_transport_attempt_ids),
        }
        trace_sha = hashlib.sha256(
            canonical_json(trace_payload).encode("utf-8")
        ).hexdigest()
        if self.execution_trace_sha256 is not None and self.execution_trace_sha256 != trace_sha:
            raise ContractValidationError("replay execution-trace digest changed")
        object.__setattr__(self, "execution_trace_sha256", trace_sha)
        payload = self.model_dump(mode="json", exclude={"replay_execution_id"})
        expected_id = stable_contract_id("acqreplayexecutionv0", payload)
        if self.replay_execution_id is not None and self.replay_execution_id != expected_id:
            raise ContractValidationError("replay-execution ID mismatch")
        object.__setattr__(self, "replay_execution_id", expected_id)
        return self


class AcquisitionReplayLockV0(_FrozenEvaluationContract):
    schema_version: Literal[
        ACQUISITION_REPLAY_LOCK_SCHEMA_V0
    ] = ACQUISITION_REPLAY_LOCK_SCHEMA_V0
    replay_lock_id: Optional[str] = None
    authoritative_artifact_id: str
    replay_artifact_id: str
    replay_execution_id: str
    replay_execution_trace_sha256: str = Field(pattern=_HEX64)
    authoritative_sha256: str = Field(pattern=_HEX64)
    replay_sha256: str = Field(pattern=_HEX64)
    authoritative_positive_order: Tuple[str, ...]
    authoritative_orthogonal_order: Tuple[str, ...]
    authoritative_precedence_order: Tuple[str, ...]
    replay_positive_order: Tuple[str, ...]
    replay_orthogonal_order: Tuple[str, ...]
    replay_precedence_order: Tuple[str, ...]
    replay_ordered_case_ids: Tuple[str, ...]
    replay_ordered_case_result_ids: Tuple[str, ...]
    replay_ordered_transport_attempt_ids: Tuple[str, ...]
    semantic_equality: Literal[True] = True
    artifact_id_equality: Literal[True] = True
    byte_identity: Literal[True] = True

    _nonblank_fields = field_validator(
        "authoritative_artifact_id", "replay_artifact_id", "replay_execution_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionReplayLockV0":
        expected_replay_case_ids = (
            self.replay_positive_order
            + self.replay_orthogonal_order
            + self.replay_precedence_order
        )
        if (
            self.authoritative_positive_order != FROZEN_POSITIVE_CASE_ORDER_V0
            or self.authoritative_orthogonal_order
            != FROZEN_ORTHOGONAL_PROBE_ORDER_V0
            or self.authoritative_precedence_order
            != FROZEN_PRECEDENCE_PROBE_ORDER_V0
            or self.replay_positive_order
            != tuple(reversed(self.authoritative_positive_order))
            or self.replay_orthogonal_order
            != tuple(reversed(self.authoritative_orthogonal_order))
            or self.replay_precedence_order
            != tuple(reversed(self.authoritative_precedence_order))
            or self.authoritative_artifact_id != self.replay_artifact_id
            or self.authoritative_sha256 != self.replay_sha256
            or self.replay_ordered_case_ids != expected_replay_case_ids
            or len(self.replay_ordered_case_result_ids) != len(expected_replay_case_ids)
            or len(set(self.replay_ordered_case_result_ids))
            != len(self.replay_ordered_case_result_ids)
            or len(self.replay_ordered_transport_attempt_ids)
            != FROZEN_ACQUISITION_THRESHOLDS_V0.required_attempt_receipts_total
            or len(set(self.replay_ordered_transport_attempt_ids))
            != len(self.replay_ordered_transport_attempt_ids)
        ):
            raise ContractValidationError("independent acquisition replay did not lock")
        trace_payload = {
            "execution_role": "REVERSE_REPLAY",
            "positive_order": list(self.replay_positive_order),
            "orthogonal_order": list(self.replay_orthogonal_order),
            "precedence_order": list(self.replay_precedence_order),
            "ordered_case_ids": list(self.replay_ordered_case_ids),
            "ordered_case_result_ids": list(self.replay_ordered_case_result_ids),
            "ordered_transport_attempt_ids": list(
                self.replay_ordered_transport_attempt_ids
            ),
        }
        expected_trace_sha = hashlib.sha256(
            canonical_json(trace_payload).encode("utf-8")
        ).hexdigest()
        if self.replay_execution_trace_sha256 != expected_trace_sha:
            raise ContractValidationError("replay-lock execution trace changed")
        payload = self.model_dump(mode="json", exclude={"replay_lock_id"})
        expected_id = stable_contract_id("acqreplaylockv0", payload)
        if self.replay_lock_id is not None and self.replay_lock_id != expected_id:
            raise ContractValidationError("acquisition replay-lock ID mismatch")
        object.__setattr__(self, "replay_lock_id", expected_id)
        return self


_BASELINE_MUTATION_VALUES: Mapping[str, object] = {
    "request.schema_version": "socrateszero-acquisition-semantic-request/v0",
    "request.semantic_request_id": (
        "szacqrequest_b005c6c56dd4eeff795c7dd2427218ee01c28cba7cf6ea932a0d7b9a064c4ee1"
    ),
    "capability.actual_provider_identity_verification": "PROVEN_SUPPORTED",
    "capability.transport_mode": "CANNED_ONLY",
    "capability.external_network": "PROVEN_DISABLED",
    "capability.credential_access": "PROVEN_DISABLED",
    "capability.actual_model_identity_verification": "PROVEN_SUPPORTED",
    "capability.fallback": "PROVEN_DISABLED",
    "capability.retry": "PROVEN_DISABLED",
    "capability.sdk_internal_retry": "PROVEN_DISABLED",
    "capability.tools": "PROVEN_DISABLED",
    "capability.worker_termination": "PROVEN_SUPPORTED",
    "capability.cost_reporting": "PROVEN_SUPPORTED",
    "budget.max_canned_transport_invocations": 1,
    "renderer.entropy_source": "NONE",
    "transport_registry.baseline_canned.registered": True,
    "attempt_recorder.canned_transport_invocations": 1,
    "envelope.transport_status": "DELIVERED",
    "envelope.worker_terminated": True,
    "envelope.actual_provider_id": ACQUISITION_PROVIDER_ID_V0,
    "envelope.actual_model_id": ACQUISITION_MODEL_ID_V0,
    "envelope.actual_configuration_digest": (
        "c7cbccd7066a0d9c657932ce183f5e18821586fa1a7890f2f14d8efff0987d84"
    ),
    "envelope.fallback_used": False,
    "envelope.retry_count": 0,
    "envelope.tool_calls": 0,
    "envelope.raw_response_text": FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0.decode("utf-8"),
    "envelope.raw_response_sha256": FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0,
    "envelope.new_usage_completeness": "COMPLETE",
    "envelope.usage.tokens.knowledge": "KNOWN",
    "resource_receipt.canned_transport_invocations": 1,
    "isolation_probe.source.runtime_digest": _FINGERPRINT_DIGESTS["source"],
    "isolation_probe.sibling.runtime_digest": _FINGERPRINT_DIGESTS["sibling"],
    "isolation_probe.production.runtime_digest": _FINGERPRINT_DIGESTS["production"],
    "retention_receipt.artifact_inclusion": "INCLUDE_RAW_NON_SENSITIVE_RESPONSE",
    "attempt_recorder.final_receipt_integrity": True,
    "envelope.expected_canonical_acceptance": None,
}

# This projection is evaluator logic, not case metadata.  It maps an actually
# changed authoritative input to the independently observable relation that
# must result.  The frozen expected vector is compared only after measurement.
_MUTATION_IMPACTS: Mapping[str, Mapping[str, MutationState]] = {
    "request.schema_version": {"request_integrity": MutationState.INTENTIONALLY_CHANGED},
    "request.semantic_request_id": {
        "semantic_request_identity": MutationState.INTENTIONALLY_CHANGED
    },
    "capability.actual_provider_identity_verification": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "capability_controls": MutationState.INTENTIONALLY_CHANGED,
    },
    "capability.transport_mode": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "transport_mode": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.external_network": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "external_network": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.credential_access": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "credential_access": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.actual_model_identity_verification": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "capability_controls": MutationState.INTENTIONALLY_CHANGED,
    },
    "capability.fallback": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "fallback": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.retry": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "retry": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.sdk_internal_retry": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "sdk_internal_retry": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.tools": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "tools": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.worker_termination": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "worker_termination": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "capability.cost_reporting": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "usage_completeness": MutationState.INTENTIONALLY_CHANGED,
        "capability_controls": MutationState.DEPENDENTLY_CHANGED,
    },
    "budget.max_canned_transport_invocations": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "budget": MutationState.INTENTIONALLY_CHANGED
    },
    "renderer.entropy_source": {
        "prompt_bytes": MutationState.INTENTIONALLY_CHANGED
    },
    "transport_registry.baseline_canned.registered": {
        "semantic_request_identity": MutationState.DEPENDENTLY_CHANGED,
        "transport_registration": MutationState.INTENTIONALLY_CHANGED
    },
    "attempt_recorder.canned_transport_invocations": {
        "canned_invocation_accounting": MutationState.INTENTIONALLY_CHANGED,
        "receipt_identity": MutationState.DEPENDENTLY_CHANGED,
    },
    "envelope.transport_status": {
        "timeout": MutationState.INTENTIONALLY_CHANGED,
        "response_presence": MutationState.DEPENDENTLY_CHANGED,
        "response_digest": MutationState.NOT_APPLICABLE,
    },
    "envelope.worker_terminated": {
        "worker_termination": MutationState.INTENTIONALLY_CHANGED
    },
    "envelope.actual_provider_id": {
        "provider": MutationState.INTENTIONALLY_CHANGED
    },
    "envelope.actual_model_id": {"model": MutationState.INTENTIONALLY_CHANGED},
    "envelope.actual_configuration_digest": {
        "configuration": MutationState.INTENTIONALLY_CHANGED
    },
    "envelope.fallback_used": {"fallback": MutationState.INTENTIONALLY_CHANGED},
    "envelope.retry_count": {"retry": MutationState.INTENTIONALLY_CHANGED},
    "envelope.tool_calls": {"tools": MutationState.INTENTIONALLY_CHANGED},
    "envelope.raw_response_text": {
        "response_presence": MutationState.INTENTIONALLY_CHANGED,
        "response_digest": MutationState.NOT_APPLICABLE,
    },
    "envelope.raw_response_sha256": {
        "response_digest": MutationState.INTENTIONALLY_CHANGED
    },
    "envelope.new_usage_completeness": {
        "usage_completeness": MutationState.INTENTIONALLY_CHANGED
    },
    "envelope.usage.tokens.knowledge": {
        "usage_completeness": MutationState.INTENTIONALLY_CHANGED,
        "receipt_identity": MutationState.DEPENDENTLY_CHANGED,
    },
    "resource_receipt.canned_transport_invocations": {
        "resource_receipt": MutationState.INTENTIONALLY_CHANGED,
        "receipt_identity": MutationState.DEPENDENTLY_CHANGED,
    },
    "isolation_probe.source.runtime_digest": {
        "branch_isolation": MutationState.INTENTIONALLY_CHANGED
    },
    "isolation_probe.sibling.runtime_digest": {
        "branch_isolation": MutationState.INTENTIONALLY_CHANGED
    },
    "isolation_probe.production.runtime_digest": {
        "branch_isolation": MutationState.INTENTIONALLY_CHANGED
    },
    "retention_receipt.artifact_inclusion": {
        "retention": MutationState.INTENTIONALLY_CHANGED
    },
    "attempt_recorder.final_receipt_integrity": {
        "receipt_identity": MutationState.INTENTIONALLY_CHANGED
    },
    "envelope.expected_canonical_acceptance": {
        "future_label_status": MutationState.INTENTIONALLY_CHANGED
    },
}


def _project_mutation_vector_from_paths_v0(
    changed_paths: Sequence[str],
) -> AcquisitionMutationVectorV0:
    states: Dict[str, MutationState] = {
        name: MutationState.PRESERVED for name in MUTATION_VECTOR_FIELD_NAMES
    }
    for path in changed_paths:
        if path not in _MUTATION_IMPACTS:
            raise ContractValidationError(f"unknown mutation path: {path}")
        for field_name, state in _MUTATION_IMPACTS[path].items():
            previous = states[field_name]
            if previous is not MutationState.PRESERVED and previous is not state:
                raise ContractValidationError(
                    f"conflicting mutation relation for {field_name}"
                )
            states[field_name] = state
    return AcquisitionMutationVectorV0(**states)


def measure_probe_mutation_vector_v0(
    probe: AcquisitionProbeV0,
    construction_evidence: AcquisitionProbeConstructionEvidenceV0,
) -> Tuple[bool, AcquisitionMutationVectorV0, Tuple[str, ...]]:
    """Measure the vector from the exact concrete construction used by runtime."""

    paths = tuple(sorted(item.path for item in construction_evidence.observations))
    declared_paths = tuple(sorted(item.path for item in probe.literal_mutations))
    valid = all(
        (
            construction_evidence.probe_id == probe.probe_id,
            construction_evidence.construction_valid,
            paths == declared_paths,
            tuple(
                sorted(
                    (
                        item.path,
                        item.literal_before_json,
                        item.literal_after_json,
                    )
                    for item in construction_evidence.observations
                )
            )
            == tuple(
                sorted(
                    (item.path, item.before_json, item.after_json)
                    for item in probe.literal_mutations
                )
            ),
        )
    )
    return valid, construction_evidence.measured_mutation_vector, paths


def _resource_quantity(
    state: ResourceKnowledgeState,
    value: Optional[int] = None,
) -> AcquisitionResourceQuantity:
    return AcquisitionResourceQuantity(knowledge=state, value=value)


def _historical_usage(*, unknown: bool) -> AcquisitionHistoricalUsage:
    quantity = (
        _resource_quantity(ResourceKnowledgeState.UNKNOWN)
        if unknown
        else _resource_quantity(ResourceKnowledgeState.KNOWN, 0)
    )
    return AcquisitionHistoricalUsage(
        provenance_id=_HISTORICAL_PROVENANCE_ID,
        source_observation_acquisitions=quantity,
        source_model_calls=quantity,
        source_tool_calls=quantity,
        source_tokens=quantity,
        source_cost_microusd=quantity,
        source_external_wall_time_ms=quantity,
    )


def _adapter_revision_digest() -> str:
    return hashlib.sha256(b"socrateszero-canned-adapter/v0").hexdigest()


def build_frozen_acquisition_fixtures_v0() -> AcquisitionFixtureSetV0:
    """Build the fully validated, positive canned fixture family."""

    application_body = json.loads(FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0.decode("utf-8"))
    if not isinstance(application_body, dict):
        raise ContractValidationError("frozen provider-visible request is not an object")
    visible = _runtime.build_provider_visible_request(application_body)
    if (
        visible.canonical_request_json.encode("utf-8")
        != FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0
    ):
        raise ContractValidationError("runtime renderer changed frozen provider bytes")
    capability = _runtime.build_canned_capability_snapshot(
        ACQUISITION_PROVIDER_ID_V0,
        ACQUISITION_ADAPTER_ID_V0,
        ACQUISITION_ADAPTER_VERSION_V0,
        _adapter_revision_digest(),
        ACQUISITION_MODEL_ID_V0,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
    )
    requirements = tuple(
        AcquisitionControlRequirement(name=name, allowed_states=states)
        for name, states in FROZEN_REQUIRED_CONTROL_STATES
    )
    seed = AcquisitionSeedSetting(status=AcquisitionSeedStatus.UNSUPPORTED)
    policy = AcquisitionControlPolicy(
        requirements=requirements,
        temperature=0.0,
        seed=seed,
        max_output_tokens=256,
        timeout_ms=5000,
        budget=AcquisitionBudget(max_canned_transport_invocations=1),
    )
    configuration = AcquisitionRequestConfiguration(
        temperature=0.0,
        seed=seed,
        max_output_tokens=256,
        timeout_ms=5000,
        provider_visible_metadata_digest=visible.sha256 or "",
    )
    binding = AcquisitionProviderModelBinding(
        provider_id=ACQUISITION_PROVIDER_ID_V0,
        model_id=ACQUISITION_MODEL_ID_V0,
        configuration_digest=configuration.configuration_digest or "",
    )
    request = AcquisitionSemanticRequest(
        source_capsule_id=_SOURCE_CAPSULE_ID,
        source_execution_id=_SOURCE_EXECUTION_ID,
        root_state_v1_id=_ROOT_STATE_V1_ID,
        pending_transition_id=_PENDING_TRANSITION_ID,
        canonical_task_identity_id=_CANONICAL_TASK_ID,
        action_id=_ACTION_ID,
        complete_legal_action_ids=(_ACTION_ID,),
        requested_binding=binding,
        capability_snapshot_id=capability.capability_snapshot_id or "",
        control_policy_id=policy.control_policy_id or "",
        request_configuration=configuration,
        provider_visible_request=visible,
    )
    retention_policy = AcquisitionRetentionPolicy(
        prompt_retention_mode=PromptRetentionMode.DIGEST_AND_REFERENCE,
        response_retention_mode=ResponseRetentionMode.RAW_UTF8,
        retention_classification=_RETENTION_CLASSIFICATION,
        retention_reason=_RETENTION_REASON,
        access_policy_id=_RETENTION_ACCESS_POLICY_ID,
        artifact_inclusion_policy=(
            AcquisitionArtifactInclusionPolicy.INCLUDE_RAW_NON_SENSITIVE_RESPONSE
        ),
    )
    return AcquisitionFixtureSetV0(
        capability_snapshot=capability,
        control_policy=policy,
        semantic_request=request,
        retention_policy=retention_policy,
        known_historical_usage=_historical_usage(unknown=False),
        unknown_historical_usage=_historical_usage(unknown=True),
    )


def verify_frozen_historical_hashes_v0(
    repository_root: Optional[Path | str] = None,
) -> Tuple[AcquisitionHistoricalHashEvidenceV0, ...]:
    """Read and hash only the six frozen predecessor artifacts."""

    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[3]
    )
    evidence = []
    for label, repository_path, expected in _HISTORICAL_ARTIFACT_LOCKS:
        path = root / Path(repository_path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        evidence.append(
            AcquisitionHistoricalHashEvidenceV0(
                label=label,
                repository_path=repository_path.replace("\\", "/"),
                expected_sha256=expected,
                actual_sha256=actual,
                matches=actual == expected,
            )
        )
    return tuple(evidence)


@dataclass(frozen=True)
class _ExecutedAttempt:
    baseline_request: AcquisitionSemanticRequest
    baseline_attempt: AcquisitionTransportAttempt
    baseline_capability_snapshot: AcquisitionCapabilitySnapshot
    baseline_policy: AcquisitionControlPolicy
    baseline_directive: _runtime.CannedTransportDirective
    baseline_transport: _runtime.CannedAcquisitionTransport
    request: AcquisitionSemanticRequest
    attempt: AcquisitionTransportAttempt
    capability_snapshot: AcquisitionCapabilitySnapshot
    policy: AcquisitionControlPolicy
    directive: _runtime.CannedTransportDirective
    transport: _runtime.CannedAcquisitionTransport
    isolation_runtime_digests: Tuple[Tuple[str, str], ...]
    future_label_candidate_rejected: bool
    historical_usage: AcquisitionHistoricalUsage
    result: _runtime.AcquisitionRunResult


class _ScriptedIsolationProbe:
    def __init__(self, runtime_digests: Mapping[str, str]) -> None:
        self._runtime_digests = dict(runtime_digests)
        if set(self._runtime_digests) != {"source", "sibling", "production"}:
            raise ContractValidationError("isolation runtime digest coverage changed")
        self._calls = 0

    def __call__(self) -> _runtime.AcquisitionIsolationSnapshot:
        after = self._calls > 0
        self._calls += 1

        def digest(scope: str) -> str:
            if after:
                return self._runtime_digests[scope]
            return _FINGERPRINT_DIGESTS[scope]

        return _runtime.AcquisitionIsolationSnapshot(
            source=_runtime.IsolationSubjectSnapshot(
                _SOURCE_CAPSULE_ID, digest("source")
            ),
            sibling=_runtime.IsolationSubjectSnapshot(
                "socrateszero-acquisition-sibling-control/v0", digest("sibling")
            ),
            production=_runtime.IsolationSubjectSnapshot(
                "socrateszero-acquisition-production-control/v0",
                digest("production"),
            ),
        )


def _known_execution_usage(invocations: int) -> AcquisitionExecutionUsage:
    known_zero = AcquisitionResourceQuantity.known(0)
    return AcquisitionExecutionUsage(
        canned_transport_invocations=AcquisitionResourceQuantity.known(invocations),
        external_network_attempts=known_zero,
        credential_access_attempts=known_zero,
        live_provider_calls=known_zero,
        provider_sdk_calls=known_zero,
        model_executions=known_zero,
        tool_calls=known_zero,
        new_tokens=known_zero,
        new_cost_microusd=known_zero,
        external_provider_wall_time_ms=known_zero,
    )


def _incomplete_execution_usage(*, false_zero: bool) -> AcquisitionExecutionUsage:
    complete = _known_execution_usage(1)
    if false_zero:
        unknown = AcquisitionResourceQuantity.model_construct(
            knowledge=ResourceKnowledgeState.UNKNOWN,
            value=0,
        )
    else:
        unknown = AcquisitionResourceQuantity.unknown()
    values = {
        "canned_transport_invocations": complete.canned_transport_invocations,
        "external_network_attempts": complete.external_network_attempts,
        "credential_access_attempts": complete.credential_access_attempts,
        "live_provider_calls": complete.live_provider_calls,
        "provider_sdk_calls": complete.provider_sdk_calls,
        "model_executions": complete.model_executions,
        "tool_calls": complete.tool_calls,
        "new_tokens": unknown,
        "new_cost_microusd": complete.new_cost_microusd,
        "external_provider_wall_time_ms": complete.external_provider_wall_time_ms,
    }
    if false_zero:
        return AcquisitionExecutionUsage.model_construct(
            schema_version=complete.schema_version,
            execution_usage_id=None,
            **values,
        )
    return AcquisitionExecutionUsage(**values)


def _mutation_after(probe: AcquisitionProbeV0, path: str) -> object:
    for mutation in probe.literal_mutations:
        if mutation.path == path:
            return json.loads(mutation.after_json)
    raise KeyError(path)


def _has_mutation(probe: AcquisitionProbeV0, path: str) -> bool:
    return any(item.path == path for item in probe.literal_mutations)


def _profiles_for_probe(
    probe: AcquisitionProbeV0,
) -> Tuple[_runtime.CannedImplementationProfile, ...]:
    profiles = []
    for mutation in probe.literal_mutations:
        path = mutation.path
        after = json.loads(mutation.after_json)
        profile: Optional[_runtime.CannedImplementationProfile] = None
        if path == "capability.actual_provider_identity_verification":
            profile = _runtime.CannedImplementationProfile.REQUIRED_PROVIDER_IDENTITY_UNKNOWN
        elif path == "capability.transport_mode":
            profile = _runtime.CannedImplementationProfile.CANNED_ONLY_UNPROVEN
        elif path == "capability.external_network":
            profile = _runtime.CannedImplementationProfile.NETWORK_PROHIBITION_UNPROVEN
        elif path == "capability.credential_access":
            profile = _runtime.CannedImplementationProfile.CREDENTIAL_PROHIBITION_UNPROVEN
        elif path == "capability.actual_model_identity_verification":
            profile = _runtime.CannedImplementationProfile.IDENTITY_VERIFICATION_UNPROVEN
        elif path == "capability.fallback":
            profile = (
                _runtime.CannedImplementationProfile.FALLBACK_CONTROL_UNKNOWN
                if after == "UNKNOWN"
                else _runtime.CannedImplementationProfile.FALLBACK_DISABLE_UNPROVEN
            )
        elif path == "capability.retry":
            profile = _runtime.CannedImplementationProfile.RETRY_CONTROL_UNKNOWN
        elif path == "capability.sdk_internal_retry":
            profile = _runtime.CannedImplementationProfile.SDK_RETRY_CONTROL_UNKNOWN
        elif path == "capability.tools":
            profile = _runtime.CannedImplementationProfile.TOOLS_DISABLE_UNPROVEN
        elif path == "capability.worker_termination":
            profile = _runtime.CannedImplementationProfile.TERMINATION_CONTROL_UNKNOWN
        elif path == "capability.cost_reporting":
            profile = _runtime.CannedImplementationProfile.ACCOUNTING_UNPROVEN
        elif path == "budget.max_canned_transport_invocations":
            profile = _runtime.CannedImplementationProfile.BUDGET_RESERVATION_UNPROVEN
        elif path == "renderer.entropy_source":
            profile = _runtime.CannedImplementationProfile.PROMPT_ENTROPY_INJECTION
        elif path == "transport_registry.baseline_canned.registered":
            profile = _runtime.CannedImplementationProfile.REGISTRATION_UNPROVEN
        if profile is not None:
            profiles.append(profile)
    return tuple(sorted(set(profiles), key=lambda item: item.value))


def _probe_request(
    baseline: AcquisitionSemanticRequest,
    probe: AcquisitionProbeV0,
) -> AcquisitionSemanticRequest:
    request = baseline
    if _has_mutation(probe, "request.schema_version"):
        request = request.model_copy(
            update={
                "schema_version": _mutation_after(probe, "request.schema_version")
            }
        )
    if _has_mutation(probe, "request.semantic_request_id"):
        request = request.model_copy(
            update={
                "semantic_request_id": _mutation_after(
                    probe, "request.semantic_request_id"
                )
            }
        )
    return request


def _rebind_semantic_request(
    baseline: AcquisitionSemanticRequest,
    capability: AcquisitionCapabilitySnapshot,
    policy: AcquisitionControlPolicy,
) -> AcquisitionSemanticRequest:
    payload = baseline.model_dump(mode="python", exclude={"semantic_request_id"})
    payload["capability_snapshot_id"] = capability.capability_snapshot_id or ""
    payload["control_policy_id"] = policy.control_policy_id or ""
    return AcquisitionSemanticRequest.model_validate(payload)


def _policy_for_probe(
    baseline: AcquisitionControlPolicy,
    probe: Optional[AcquisitionProbeV0],
) -> AcquisitionControlPolicy:
    if probe is None or not _has_mutation(
        probe, "budget.max_canned_transport_invocations"
    ):
        return baseline
    payload = baseline.model_dump(mode="python", exclude={"control_policy_id"})
    budget_payload = baseline.budget.model_dump(mode="python")
    budget_payload["max_canned_transport_invocations"] = int(
        _mutation_after(probe, "budget.max_canned_transport_invocations")
    )
    payload["budget"] = AcquisitionBudget.model_validate(budget_payload)
    return AcquisitionControlPolicy.model_validate(payload)


def _envelope_and_directive(
    *,
    fixtures: AcquisitionFixtureSetV0,
    attempt: AcquisitionTransportAttempt,
    historical_usage: AcquisitionHistoricalUsage,
    raw_bytes: bytes,
    probe: Optional[AcquisitionProbeV0],
) -> Tuple[
    CannedTransportEnvelope,
    _runtime.CannedTransportDirective,
    bool,
]:
    raw_text: Optional[str] = raw_bytes.decode("utf-8")
    binding = fixtures.semantic_request.requested_binding
    provider_id = binding.provider_id
    model_id = binding.model_id
    configuration_digest = binding.configuration_digest
    transport_status = AcquisitionTransportStatus.DELIVERED
    reported_invocations = 1
    worker_terminated = True
    fallback_used = False
    explicit_retry_count = 0
    tool_calls = 0
    reported_digest: Optional[str] = hashlib.sha256(raw_bytes).hexdigest()
    usage = _known_execution_usage(1)
    resource_integrity = True
    retention_integrity = True
    final_receipt_integrity = True
    false_zero_usage = False

    if probe is not None:
        if _has_mutation(probe, "attempt_recorder.canned_transport_invocations"):
            reported_invocations = int(
                _mutation_after(
                    probe, "attempt_recorder.canned_transport_invocations"
                )
            )
        if _has_mutation(probe, "envelope.transport_status"):
            transport_status = AcquisitionTransportStatus.TIMEOUT
            raw_text = None
            reported_digest = None
        if _has_mutation(probe, "envelope.worker_terminated"):
            worker_terminated = bool(
                _mutation_after(probe, "envelope.worker_terminated")
            )
        if _has_mutation(probe, "envelope.actual_provider_id"):
            provider_id = str(_mutation_after(probe, "envelope.actual_provider_id"))
        if _has_mutation(probe, "envelope.actual_model_id"):
            model_id = str(_mutation_after(probe, "envelope.actual_model_id"))
        if _has_mutation(probe, "envelope.actual_configuration_digest"):
            configuration_digest = str(
                _mutation_after(probe, "envelope.actual_configuration_digest")
            )
        if _has_mutation(probe, "envelope.fallback_used"):
            fallback_used = bool(_mutation_after(probe, "envelope.fallback_used"))
        if _has_mutation(probe, "envelope.retry_count"):
            explicit_retry_count = int(
                _mutation_after(probe, "envelope.retry_count")
            )
        if _has_mutation(probe, "envelope.tool_calls"):
            tool_calls = int(_mutation_after(probe, "envelope.tool_calls"))
        if _has_mutation(probe, "envelope.raw_response_text"):
            raw_text = _mutation_after(probe, "envelope.raw_response_text")
            reported_digest = None
        if _has_mutation(probe, "envelope.raw_response_sha256"):
            reported_digest = str(
                _mutation_after(probe, "envelope.raw_response_sha256")
            )
        if _has_mutation(probe, "envelope.new_usage_completeness"):
            usage = _incomplete_execution_usage(false_zero=False)
        if _has_mutation(probe, "envelope.usage.tokens.knowledge"):
            usage = _incomplete_execution_usage(false_zero=False)
            false_zero_usage = True
        if _has_mutation(probe, "resource_receipt.canned_transport_invocations"):
            resource_integrity = False
        if _has_mutation(probe, "retention_receipt.artifact_inclusion"):
            retention_integrity = False
        if _has_mutation(probe, "attempt_recorder.final_receipt_integrity"):
            final_receipt_integrity = False

    actual_binding = AcquisitionProviderModelBinding(
        provider_id=provider_id,
        model_id=model_id,
        configuration_digest=configuration_digest,
    )
    envelope = CannedTransportEnvelope(
        transport_attempt_id=attempt.transport_attempt_id or "",
        transport_status=transport_status,
        canned_transport_invocations=reported_invocations,
        actual_binding=actual_binding,
        raw_response_text=raw_text,
        reported_raw_response_digest=reported_digest,
        fallback_used=fallback_used,
        explicit_retry_count=explicit_retry_count,
        adapter_retry_count=0,
        sdk_internal_retry_count=0,
        hidden_transport_retry_count=0,
        tool_calls=tool_calls,
        timeout_fired=transport_status is AcquisitionTransportStatus.TIMEOUT,
        cancellation_requested=transport_status is AcquisitionTransportStatus.TIMEOUT,
        worker_terminated=worker_terminated,
        execution_usage=usage,
        historical_usage=historical_usage,
        source_provenance_id=historical_usage.provenance_id,
    )
    if false_zero_usage:
        envelope = envelope.model_copy(
            update={"execution_usage": _incomplete_execution_usage(false_zero=True)}
        )
    future_label_candidate_rejected = False
    if probe is not None and _has_mutation(
        probe, "envelope.expected_canonical_acceptance"
    ):
        candidate = envelope.model_dump(mode="python")
        candidate["expected_canonical_acceptance"] = _mutation_after(
            probe, "envelope.expected_canonical_acceptance"
        )
        try:
            CannedTransportEnvelope.model_validate(candidate)
        except ValidationError:
            future_label_candidate_rejected = True
        else:
            raise ContractValidationError("future-label envelope was unexpectedly accepted")
        directive = _runtime.CannedTransportDirective(
            failure_code=AcquisitionFailureCode.TRANSPORT_ERROR
        )
    else:
        directive = _runtime.CannedTransportDirective(
            envelope=envelope,
            resource_integrity=resource_integrity,
            retention_integrity=retention_integrity,
            final_receipt_integrity=final_receipt_integrity,
        )
    return envelope, directive, future_label_candidate_rejected


async def _execute_attempt(
    *,
    fixtures: AcquisitionFixtureSetV0,
    case_id: str,
    ordinal: int,
    raw_bytes: bytes,
    historical_usage: AcquisitionHistoricalUsage,
    probe: Optional[AcquisitionProbeV0] = None,
) -> _ExecutedAttempt:
    branch_id = f"{_BASELINE_BRANCH_PREFIX}/{case_id}/{ordinal}"
    baseline_request = fixtures.semantic_request
    baseline_attempt = AcquisitionTransportAttempt(
        semantic_request_id=baseline_request.semantic_request_id or "",
        experiment_id=ACQUISITION_EXPERIMENT_ID_V0,
        branch_id=branch_id,
        attempt_ordinal=ordinal,
    )
    _, baseline_directive, _ = _envelope_and_directive(
        fixtures=fixtures,
        attempt=baseline_attempt,
        historical_usage=historical_usage,
        raw_bytes=raw_bytes,
        probe=None,
    )
    baseline_transport = _runtime.CannedAcquisitionTransport(
        (baseline_directive,),
        provider_id=ACQUISITION_PROVIDER_ID_V0,
        adapter_id=ACQUISITION_ADAPTER_ID_V0,
        adapter_version=ACQUISITION_ADAPTER_VERSION_V0,
        adapter_revision_digest=_adapter_revision_digest(),
        requested_model_id=ACQUISITION_MODEL_ID_V0,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
        implementation_profile=_runtime.CannedImplementationProfile.SAFE,
    )
    profiles = (
        (_runtime.CannedImplementationProfile.SAFE,)
        if probe is None
        else _profiles_for_probe(probe)
        or (_runtime.CannedImplementationProfile.SAFE,)
    )
    capability = _runtime.build_canned_capability_snapshot(
        ACQUISITION_PROVIDER_ID_V0,
        ACQUISITION_ADAPTER_ID_V0,
        ACQUISITION_ADAPTER_VERSION_V0,
        _adapter_revision_digest(),
        ACQUISITION_MODEL_ID_V0,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
        implementation_profile=profiles,
    )
    policy = _policy_for_probe(fixtures.control_policy, probe)
    request = _rebind_semantic_request(fixtures.semantic_request, capability, policy)
    if probe is not None:
        request = _probe_request(request, probe)
    attempt = AcquisitionTransportAttempt(
        semantic_request_id=request.semantic_request_id or "",
        experiment_id=ACQUISITION_EXPERIMENT_ID_V0,
        branch_id=branch_id,
        attempt_ordinal=ordinal,
    )
    _, directive, future_label_candidate_rejected = _envelope_and_directive(
        fixtures=fixtures,
        attempt=attempt,
        historical_usage=historical_usage,
        raw_bytes=raw_bytes,
        probe=probe,
    )
    transport = _runtime.CannedAcquisitionTransport(
        (directive,),
        provider_id=ACQUISITION_PROVIDER_ID_V0,
        adapter_id=ACQUISITION_ADAPTER_ID_V0,
        adapter_version=ACQUISITION_ADAPTER_VERSION_V0,
        adapter_revision_digest=_adapter_revision_digest(),
        requested_model_id=ACQUISITION_MODEL_ID_V0,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
        implementation_profile=profiles,
    )
    if transport.capabilities != capability:
        raise ContractValidationError("transport capability construction diverged")
    isolation_runtime_digests = dict(_FINGERPRINT_DIGESTS)
    if probe is not None:
        for scope in ("source", "sibling", "production"):
            path = f"isolation_probe.{scope}.runtime_digest"
            if _has_mutation(probe, path):
                isolation_runtime_digests[scope] = str(_mutation_after(probe, path))
    isolation_probe = _ScriptedIsolationProbe(isolation_runtime_digests)
    result = await _runtime.acquire_canned_observation(
        request,
        attempt,
        policy,
        fixtures.retention_policy,
        transport,
        historical_usage=historical_usage,
        isolation_probe=isolation_probe,
        capability_snapshot=capability,
    )
    return _ExecutedAttempt(
        baseline_request=baseline_request,
        baseline_attempt=baseline_attempt,
        baseline_capability_snapshot=fixtures.capability_snapshot,
        baseline_policy=fixtures.control_policy,
        baseline_directive=baseline_directive,
        baseline_transport=baseline_transport,
        request=request,
        attempt=attempt,
        capability_snapshot=capability,
        policy=policy,
        directive=directive,
        transport=transport,
        isolation_runtime_digests=tuple(sorted(isolation_runtime_digests.items())),
        future_label_candidate_rejected=future_label_candidate_rejected,
        historical_usage=historical_usage,
        result=result,
    )


def _contract_roundtrip(value: BaseModel) -> bool:
    try:
        return type(value).model_validate(value.model_dump(mode="python")) == value
    except Exception:
        return False


def _directive_payload(
    directive: _runtime.CannedTransportDirective,
) -> Mapping[str, object]:
    return {
        "envelope": (
            directive.envelope.model_dump(mode="json")
            if directive.envelope is not None
            else None
        ),
        "failure_code": (
            directive.failure_code.value if directive.failure_code is not None else None
        ),
        "wait_for_cancellation": directive.wait_for_cancellation,
        "completion_integrity": directive.completion_integrity,
        "resource_integrity": directive.resource_integrity,
        "retention_integrity": directive.retention_integrity,
        "final_receipt_integrity": directive.final_receipt_integrity,
    }


def _construction_state_v0(
    execution: _ExecutedAttempt,
    *,
    baseline: bool,
) -> AcquisitionConstructionStateV0:
    if baseline:
        capability = execution.baseline_capability_snapshot
        policy = execution.baseline_policy
        request = execution.baseline_request
        transport = execution.baseline_transport
        directive = execution.baseline_directive
        isolation_digests = tuple(sorted(_FINGERPRINT_DIGESTS.items()))
        future_label_rejected = False
    else:
        capability = execution.capability_snapshot
        policy = execution.policy
        request = execution.request
        transport = execution.transport
        directive = execution.directive
        isolation_digests = execution.isolation_runtime_digests
        future_label_rejected = execution.future_label_candidate_rejected
    return AcquisitionConstructionStateV0(
        capability_snapshot_id=capability.capability_snapshot_id or "",
        capability_snapshot_json=canonical_json(capability.model_dump(mode="json")),
        control_policy_id=policy.control_policy_id or "",
        control_policy_json=canonical_json(policy.model_dump(mode="json")),
        semantic_request_id=request.semantic_request_id or "",
        semantic_request_json=canonical_json(request.model_dump(mode="json")),
        semantic_request_contract_valid=_contract_roundtrip(request),
        transport_capability_snapshot_id=(
            transport.capabilities.capability_snapshot_id or ""
        ),
        implementation_profiles=tuple(
            item.value for item in transport.implementation_profiles
        ),
        directive_json=canonical_json(_directive_payload(directive)),
        isolation_runtime_digests=isolation_digests,
        future_label_candidate_rejected=future_label_rejected,
    )


_CONTROL_PATHS: Mapping[str, AcquisitionControlName] = {
    "capability.actual_provider_identity_verification": (
        AcquisitionControlName.ACTUAL_PROVIDER_IDENTITY_VALIDATION
    ),
    "capability.external_network": AcquisitionControlName.EXTERNAL_NETWORK,
    "capability.credential_access": AcquisitionControlName.CREDENTIAL_ACCESS,
    "capability.actual_model_identity_verification": (
        AcquisitionControlName.ACTUAL_MODEL_IDENTITY_VALIDATION
    ),
    "capability.fallback": AcquisitionControlName.FALLBACK,
    "capability.retry": AcquisitionControlName.EXPLICIT_RETRY,
    "capability.sdk_internal_retry": AcquisitionControlName.SDK_INTERNAL_RETRY,
    "capability.tools": AcquisitionControlName.TOOLS,
    "capability.worker_termination": AcquisitionControlName.TIMEOUT_WORKER_TERMINATION,
    "capability.cost_reporting": AcquisitionControlName.COST_REPORTING,
}


def _control_value(
    snapshot: AcquisitionCapabilitySnapshot,
    name: AcquisitionControlName,
) -> str:
    return next(item.state.value for item in snapshot.controls if item.name is name)


def _observed_mutation_value_v0(
    execution: _ExecutedAttempt,
    path: str,
    *,
    baseline: bool,
) -> Tuple[object, str, object]:
    request = execution.baseline_request if baseline else execution.request
    capability = (
        execution.baseline_capability_snapshot
        if baseline
        else execution.capability_snapshot
    )
    policy = execution.baseline_policy if baseline else execution.policy
    transport = execution.baseline_transport if baseline else execution.transport
    directive = execution.baseline_directive if baseline else execution.directive
    envelope = directive.envelope
    if path == "request.schema_version":
        return request.schema_version, "semantic_request.schema_version", request.schema_version
    if path == "request.semantic_request_id":
        return (
            request.semantic_request_id,
            "semantic_request.semantic_request_id",
            request.semantic_request_id,
        )
    if path in _CONTROL_PATHS:
        value = _control_value(capability, _CONTROL_PATHS[path])
        return value, "capability_snapshot.controls", value
    if path == "capability.transport_mode":
        value = capability.transport_mode.value
        return value, "capability_snapshot.transport_mode", value
    if path == "transport_registry.baseline_canned.registered":
        value = CANNED_TRANSPORT_ID in capability.registered_canned_transport_ids
        return value, "capability_snapshot.registered_canned_transport_ids", value
    if path == "budget.max_canned_transport_invocations":
        value = policy.budget.max_canned_transport_invocations
        return value, "control_policy.budget", value
    if path == "renderer.entropy_source":
        value = "BRANCH_ID" if transport.guarantees.prompt_entropy_injection else "NONE"
        return value, "transport.guarantees.prompt_entropy_injection", value
    if path.startswith("isolation_probe.") and path.endswith(".runtime_digest"):
        scope = path.split(".")[1]
        digests = (
            _FINGERPRINT_DIGESTS
            if baseline
            else dict(execution.isolation_runtime_digests)
        )
        value = digests[scope]
        return value, f"isolation_probe.{scope}", value
    if path == "attempt_recorder.final_receipt_integrity":
        value = directive.final_receipt_integrity
        return value, "canned_transport_directive.final_receipt_integrity", value
    if path == "envelope.expected_canonical_acceptance":
        value = (
            "ACCEPTED"
            if not baseline and execution.future_label_candidate_rejected
            else None
        )
        concrete = {
            "candidate_value": value,
            "contract_rejected": (
                execution.future_label_candidate_rejected if not baseline else False
            ),
        }
        return value, "candidate_envelope_contract_validation", concrete
    if envelope is None:
        raise ContractValidationError(f"mutation path has no constructed envelope: {path}")
    if path == "attempt_recorder.canned_transport_invocations":
        value = envelope.canned_transport_invocations
        return value, "canned_transport_envelope.canned_transport_invocations", value
    if path == "envelope.transport_status":
        value = envelope.transport_status.value
        return value, "canned_transport_envelope.transport_status", value
    if path == "envelope.worker_terminated":
        return envelope.worker_terminated, "canned_transport_envelope.worker_terminated", envelope.worker_terminated
    if path == "envelope.actual_provider_id":
        value = envelope.actual_binding.provider_id
        return value, "canned_transport_envelope.actual_binding.provider_id", value
    if path == "envelope.actual_model_id":
        value = envelope.actual_binding.model_id
        return value, "canned_transport_envelope.actual_binding.model_id", value
    if path == "envelope.actual_configuration_digest":
        value = envelope.actual_binding.configuration_digest
        return value, "canned_transport_envelope.actual_binding.configuration_digest", value
    if path == "envelope.fallback_used":
        return envelope.fallback_used, "canned_transport_envelope.fallback_used", envelope.fallback_used
    if path == "envelope.retry_count":
        value = envelope.explicit_retry_count
        return value, "canned_transport_envelope.explicit_retry_count", value
    if path == "envelope.tool_calls":
        return envelope.tool_calls, "canned_transport_envelope.tool_calls", envelope.tool_calls
    if path == "envelope.raw_response_text":
        return envelope.raw_response_text, "canned_transport_envelope.raw_response_text", envelope.raw_response_text
    if path == "envelope.raw_response_sha256":
        value = envelope.reported_raw_response_digest
        return value, "canned_transport_envelope.reported_raw_response_digest", value
    if path == "envelope.new_usage_completeness":
        value = "COMPLETE" if envelope.execution_usage.complete else "INCOMPLETE"
        return value, "canned_transport_envelope.execution_usage", value
    if path == "envelope.usage.tokens.knowledge":
        value = envelope.execution_usage.new_tokens.knowledge.value
        concrete = envelope.execution_usage.new_tokens.model_dump(mode="json")
        return value, "canned_transport_envelope.execution_usage.new_tokens", concrete
    if path == "resource_receipt.canned_transport_invocations":
        value = 1 if directive.resource_integrity else 0
        return value, "canned_transport_directive.resource_integrity", directive.resource_integrity
    if path == "retention_receipt.artifact_inclusion":
        value = (
            AcquisitionArtifactInclusionPolicy.INCLUDE_RAW_NON_SENSITIVE_RESPONSE.value
            if directive.retention_integrity
            else AcquisitionArtifactInclusionPolicy.DIGESTS_AND_REFERENCES.value
        )
        return value, "canned_transport_directive.retention_integrity", {
            "integrity": directive.retention_integrity,
            "artifact_inclusion": value,
        }
    raise ContractValidationError(f"unhandled concrete mutation path: {path}")


def _observed_construction_state_value_v0(
    state: AcquisitionConstructionStateV0,
    path: str,
) -> Tuple[object, str, object]:
    request_payload = json.loads(state.semantic_request_json)
    capability = AcquisitionCapabilitySnapshot.model_validate_json(
        state.capability_snapshot_json
    )
    policy = AcquisitionControlPolicy.model_validate_json(state.control_policy_json)
    directive = json.loads(state.directive_json)
    envelope = directive["envelope"]
    if path == "request.schema_version":
        value = request_payload["schema_version"]
        return value, "semantic_request.schema_version", value
    if path == "request.semantic_request_id":
        value = request_payload["semantic_request_id"]
        return value, "semantic_request.semantic_request_id", value
    if path in _CONTROL_PATHS:
        value = _control_value(capability, _CONTROL_PATHS[path])
        return value, "capability_snapshot.controls", value
    if path == "capability.transport_mode":
        value = capability.transport_mode.value
        return value, "capability_snapshot.transport_mode", value
    if path == "transport_registry.baseline_canned.registered":
        value = CANNED_TRANSPORT_ID in capability.registered_canned_transport_ids
        return value, "capability_snapshot.registered_canned_transport_ids", value
    if path == "budget.max_canned_transport_invocations":
        value = policy.budget.max_canned_transport_invocations
        return value, "control_policy.budget", value
    if path == "renderer.entropy_source":
        value = (
            "BRANCH_ID"
            if _runtime.CannedImplementationProfile.PROMPT_ENTROPY_INJECTION.value
            in state.implementation_profiles
            else "NONE"
        )
        return value, "transport.guarantees.prompt_entropy_injection", value
    if path.startswith("isolation_probe.") and path.endswith(".runtime_digest"):
        scope = path.split(".")[1]
        value = dict(state.isolation_runtime_digests)[scope]
        return value, f"isolation_probe.{scope}", value
    if path == "attempt_recorder.final_receipt_integrity":
        value = directive["final_receipt_integrity"]
        return value, "canned_transport_directive.final_receipt_integrity", value
    if path == "envelope.expected_canonical_acceptance":
        value = "ACCEPTED" if state.future_label_candidate_rejected else None
        concrete = {
            "candidate_value": value,
            "contract_rejected": state.future_label_candidate_rejected,
        }
        return value, "candidate_envelope_contract_validation", concrete
    if envelope is None:
        raise ContractValidationError(f"construction state has no envelope: {path}")
    if path == "attempt_recorder.canned_transport_invocations":
        value = envelope["canned_transport_invocations"]
        return value, "canned_transport_envelope.canned_transport_invocations", value
    if path == "envelope.transport_status":
        value = envelope["transport_status"]
        return value, "canned_transport_envelope.transport_status", value
    if path == "envelope.worker_terminated":
        value = envelope["worker_terminated"]
        return value, "canned_transport_envelope.worker_terminated", value
    if path == "envelope.actual_provider_id":
        value = envelope["actual_binding"]["provider_id"]
        return value, "canned_transport_envelope.actual_binding.provider_id", value
    if path == "envelope.actual_model_id":
        value = envelope["actual_binding"]["model_id"]
        return value, "canned_transport_envelope.actual_binding.model_id", value
    if path == "envelope.actual_configuration_digest":
        value = envelope["actual_binding"]["configuration_digest"]
        return value, "canned_transport_envelope.actual_binding.configuration_digest", value
    if path == "envelope.fallback_used":
        value = envelope["fallback_used"]
        return value, "canned_transport_envelope.fallback_used", value
    if path == "envelope.retry_count":
        value = envelope["explicit_retry_count"]
        return value, "canned_transport_envelope.explicit_retry_count", value
    if path == "envelope.tool_calls":
        value = envelope["tool_calls"]
        return value, "canned_transport_envelope.tool_calls", value
    if path == "envelope.raw_response_text":
        value = envelope["raw_response_text"]
        return value, "canned_transport_envelope.raw_response_text", value
    if path == "envelope.raw_response_sha256":
        value = envelope["reported_raw_response_digest"]
        return value, "canned_transport_envelope.reported_raw_response_digest", value
    if path == "envelope.new_usage_completeness":
        usage = AcquisitionExecutionUsage.model_validate(envelope["execution_usage"])
        value = "COMPLETE" if usage.complete else "INCOMPLETE"
        return value, "canned_transport_envelope.execution_usage", value
    if path == "envelope.usage.tokens.knowledge":
        concrete = envelope["execution_usage"]["new_tokens"]
        value = concrete["knowledge"]
        return value, "canned_transport_envelope.execution_usage.new_tokens", concrete
    if path == "resource_receipt.canned_transport_invocations":
        integrity = directive["resource_integrity"]
        value = 1 if integrity else 0
        return value, "canned_transport_directive.resource_integrity", integrity
    if path == "retention_receipt.artifact_inclusion":
        integrity = directive["retention_integrity"]
        value = (
            AcquisitionArtifactInclusionPolicy.INCLUDE_RAW_NON_SENSITIVE_RESPONSE.value
            if integrity
            else AcquisitionArtifactInclusionPolicy.DIGESTS_AND_REFERENCES.value
        )
        return value, "canned_transport_directive.retention_integrity", {
            "integrity": integrity,
            "artifact_inclusion": value,
        }
    raise ContractValidationError(f"unhandled serialized mutation path: {path}")


def _validate_probe_construction_observations_v0(
    evidence: AcquisitionProbeConstructionEvidenceV0,
) -> None:
    for observation in evidence.observations:
        before, before_source, concrete_before = (
            _observed_construction_state_value_v0(
                evidence.baseline, observation.path
            )
        )
        after, after_source, concrete_after = _observed_construction_state_value_v0(
            evidence.probe, observation.path
        )
        if before_source != after_source or observation.authoritative_source != after_source:
            raise ContractValidationError("construction authoritative source changed")
        expected_fields = {
            "observed_before_json": canonical_json(before),
            "observed_after_json": canonical_json(after),
            "concrete_before_json": canonical_json(concrete_before),
            "concrete_after_json": canonical_json(concrete_after),
        }
        if any(getattr(observation, name) != value for name, value in expected_fields.items()):
            raise ContractValidationError("mutation observation detached from construction")
        expected_match = (
            observation.literal_before_json == canonical_json(before)
            and observation.literal_after_json == canonical_json(after)
        )
        expected_change = concrete_before != concrete_after
        if (
            observation.literal_match is not expected_match
            or observation.concrete_change_observed is not expected_change
        ):
            raise ContractValidationError("mutation observation verdict changed")


def _build_probe_construction_evidence_v0(
    probe: AcquisitionProbeV0,
    execution: _ExecutedAttempt,
) -> AcquisitionProbeConstructionEvidenceV0:
    observations = []
    errors = []
    for mutation in probe.literal_mutations:
        try:
            before, source_before, concrete_before = _observed_mutation_value_v0(
                execution, mutation.path, baseline=True
            )
            after, source_after, concrete_after = _observed_mutation_value_v0(
                execution, mutation.path, baseline=False
            )
        except (ContractValidationError, KeyError, StopIteration) as exc:
            errors.append(f"{mutation.path}:{type(exc).__name__}")
            before = after = concrete_before = concrete_after = None
            source_before = source_after = "unavailable"
        literal_before = json.loads(mutation.before_json)
        literal_after = json.loads(mutation.after_json)
        if source_before != source_after:
            errors.append(f"{mutation.path}:authoritative_source_changed")
        literal_match = before == literal_before and after == literal_after
        concrete_change = concrete_before != concrete_after
        if not literal_match:
            errors.append(f"{mutation.path}:literal_mismatch")
        if not concrete_change:
            errors.append(f"{mutation.path}:no_concrete_change")
        observations.append(
            AcquisitionMutationObservationV0(
                path=mutation.path,
                authoritative_source=source_after,
                literal_before_json=mutation.before_json,
                literal_after_json=mutation.after_json,
                observed_before_json=canonical_json(before),
                observed_after_json=canonical_json(after),
                concrete_before_json=canonical_json(concrete_before),
                concrete_after_json=canonical_json(concrete_after),
                literal_match=literal_match,
                concrete_change_observed=concrete_change,
            )
        )
    expected_semantic_relation = probe.mutation_vector.semantic_request_identity
    semantic_changed = (
        execution.baseline_request.semantic_request_id != execution.request.semantic_request_id
    )
    if expected_semantic_relation is MutationState.DEPENDENTLY_CHANGED and not semantic_changed:
        errors.append("semantic_request_identity:dependent_change_missing")
    if expected_semantic_relation is MutationState.PRESERVED and semantic_changed:
        errors.append("semantic_request_identity:unexpected_change")
    if execution.transport.capabilities != execution.capability_snapshot:
        errors.append("capability_snapshot:transport_divergence")
    if execution.request.capability_snapshot_id != execution.capability_snapshot.capability_snapshot_id:
        errors.append("capability_snapshot:request_link_divergence")
    if execution.request.control_policy_id != execution.policy.control_policy_id:
        errors.append("control_policy:request_link_divergence")
    paths = tuple(item.path for item in observations)
    measured = _project_mutation_vector_from_paths_v0(paths)
    canonical_errors = tuple(sorted(set(errors)))
    return AcquisitionProbeConstructionEvidenceV0(
        probe_id=probe.probe_id,
        baseline=_construction_state_v0(execution, baseline=True),
        probe=_construction_state_v0(execution, baseline=False),
        observations=tuple(observations),
        measured_mutation_vector=measured,
        construction_errors=canonical_errors,
        construction_valid=not canonical_errors,
    )


def _accepted_violations(
    executions: Sequence[_ExecutedAttempt],
    probe: Optional[AcquisitionProbeV0],
) -> Tuple[str, ...]:
    violations = []
    for item in executions:
        receipt = item.result.attempt_receipt
        acquired = receipt.primary_result.outcome is AcquisitionAttemptOutcome.ACQUIRED
        if acquired:
            if receipt.prompt_byte_mismatch:
                violations.append("prompt_byte_mismatch")
            if receipt.source_mutations:
                violations.append("source_mutation")
            if receipt.sibling_mutations:
                violations.append("sibling_mutation")
            if receipt.production_mutations:
                violations.append("production_mutation")
            if not receipt.retention_policy_compliant:
                violations.append("retention_policy_violation")
            if not receipt.execution_usage.complete:
                violations.append("incomplete_execution_usage")
            if receipt.computed_raw_response_digest is None:
                violations.append("missing_raw_observation")
            if receipt.fallback_used:
                violations.append("fallback_activation")
            retry_values = (
                receipt.explicit_retry_count,
                receipt.adapter_retry_count,
                receipt.sdk_internal_retry_count,
                receipt.hidden_transport_retry_count,
            )
            if any(value for value in retry_values if value is not None):
                violations.append("retry_activation")
            if receipt.tool_calls:
                violations.append("tool_activation")
        counters = item.result.tripwire_counters
        if counters.external_network_attempts:
            violations.append("external_network_attempt")
        if counters.credential_access_attempts:
            violations.append("credential_access_attempt")
        if counters.live_provider_calls:
            violations.append("live_provider_call")
        if counters.provider_sdk_calls:
            violations.append("provider_sdk_call")
        if counters.model_executions:
            violations.append("model_execution")
        if counters.tool_calls:
            violations.append("tool_call")
        if counters.canonical_application_calls:
            violations.append("canonical_application")
    if probe is not None and any(
        item.result.outcome is AcquisitionAttemptOutcome.ACQUIRED for item in executions
    ):
        violations.extend(
            f"accepted_injected_condition:{mutation.path}"
            for mutation in probe.literal_mutations
        )
    return tuple(sorted(set(violations)))


def _receipts_complete(executions: Sequence[_ExecutedAttempt]) -> bool:
    return all(
        all(
            (
            _contract_roundtrip(item.result.attempt_receipt),
            _contract_roundtrip(item.result.isolation_receipt),
            _contract_roundtrip(item.result.retention_receipt),
            item.result.attempt_receipt.isolation_receipt_id
            == item.result.isolation_receipt.isolation_receipt_id,
            item.result.attempt_receipt.retention_receipt_id
            == item.result.retention_receipt.retention_receipt_id,
            )
        )
        for item in executions
    )


def _positive_assertions_valid(
    case: AcquisitionPositiveCaseV0,
    executions: Sequence[_ExecutedAttempt],
    fixtures: AcquisitionFixtureSetV0,
) -> bool:
    results = tuple(item.result for item in executions)
    receipts = tuple(item.attempt_receipt for item in results)
    common = all(
        all(
            (
            result.outcome is AcquisitionAttemptOutcome.ACQUIRED,
            result.observation is not None,
            result.tripwire_counters.external_network_attempts == 0,
            result.tripwire_counters.credential_access_attempts == 0,
            result.tripwire_counters.live_provider_calls == 0,
            result.tripwire_counters.provider_sdk_calls == 0,
            result.tripwire_counters.model_executions == 0,
            result.tripwire_counters.tool_calls == 0,
            result.tripwire_counters.canonical_application_calls == 0,
            )
        )
        for result in results
    )
    if not common:
        return False
    if case.case_id == "acqv0-s01-complete-deterministic":
        return all(
            (
                receipts[0].computed_raw_response_digest
                == FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0,
                receipts[0].execution_usage.complete,
                results[0].retention_receipt.raw_response_text
                == FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0.decode("utf-8"),
            )
        )
    if case.case_id == "acqv0-s02-content-opaque-invalid-json":
        return all(
            (
                receipts[0].computed_raw_response_digest
                == hashlib.sha256(FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0).hexdigest(),
                results[0].observation is not None,
                results[0].observation.application_status == "NOT_APPLIED",
            )
        )
    if case.case_id in {
        "acqv0-s03-sibling-byte-identity",
        "acqv0-s04-repeat-semantic-identity",
    }:
        return all(
            (
                len(executions) == 2,
                len({item.request.semantic_request_id for item in executions}) == 1,
                len({item.result.provider_visible_body for item in executions}) == 1,
                len({item.attempt.branch_id for item in executions}) == 2,
                len({item.attempt.transport_attempt_id for item in executions}) == 2,
            )
        )
    if case.case_id == "acqv0-s05-seed-explicitly-unsupported":
        seed_evidence = next(
            item
            for item in fixtures.capability_snapshot.controls
            if item.name is AcquisitionControlName.SEED
        )
        return all(
            (
                fixtures.control_policy.seed.status is AcquisitionSeedStatus.UNSUPPORTED,
                seed_evidence.state is AcquisitionControlState.PROVEN_UNSUPPORTED,
            )
        )
    if case.case_id == "acqv0-s06-historical-usage-unknown":
        historical = receipts[0].historical_usage
        historical_quantities = (
            historical.source_observation_acquisitions,
            historical.source_model_calls,
            historical.source_tool_calls,
            historical.source_tokens,
            historical.source_cost_microusd,
            historical.source_external_wall_time_ms,
        )
        return all(
            quantity.knowledge is ResourceKnowledgeState.UNKNOWN
            and quantity.value is None
            for quantity in historical_quantities
        ) and receipts[0].execution_usage.complete
    return False


def _case_result_common_values(
    executions: Sequence[_ExecutedAttempt],
) -> Mapping[str, object]:
    receipts = tuple(item.result.attempt_receipt for item in executions)
    attempt_evidence = tuple(
        AcquisitionCaseAttemptEvidenceV0(
            attempt_receipt_id=receipt.receipt_id or "",
            transport_attempt_id=receipt.transport_attempt_id,
            semantic_request_id=receipt.semantic_request_id,
            branch_id=receipt.branch_id,
            attempt_ordinal=receipt.attempt_ordinal,
            capability_snapshot_id=receipt.capability_snapshot_id,
            control_policy_id=receipt.control_policy_id,
            provider_visible_prompt_digest=receipt.provider_visible_request_digest,
            isolation_receipt_id=receipt.isolation_receipt_id,
            retention_receipt_id=receipt.retention_receipt_id,
            primary_result=receipt.primary_result,
            guard_evaluations=receipt.guard_evaluations,
            tripwire_counters=execution.result.tripwire_counters,
        )
        for execution, receipt in zip(executions, receipts)
    )
    return {
        "attempt_evidence": attempt_evidence,
        "actual_primary_results": tuple(item.primary_result for item in receipts),
        "attempt_receipt_ids": tuple(item.receipt_id or "" for item in receipts),
        "transport_attempt_ids": tuple(
            item.transport_attempt_id for item in receipts
        ),
        "semantic_request_ids": tuple(
            sorted({item.semantic_request_id for item in receipts})
        ),
        "branch_ids": tuple(item.branch_id for item in receipts),
        "provider_visible_prompt_digests": tuple(
            sorted({item.provider_visible_request_digest for item in receipts})
        ),
        "isolation_receipt_ids": tuple(
            item.isolation_receipt_id for item in receipts
        ),
        "retention_receipt_ids": tuple(
            item.retention_receipt_id for item in receipts
        ),
        "observed_canned_invocations": sum(
            item.result.tripwire_counters.canned_transport_invocations
            for item in executions
        ),
    }


async def _evaluate_positive_case(
    case: AcquisitionPositiveCaseV0,
    fixtures: AcquisitionFixtureSetV0,
) -> Tuple[AcquisitionCaseResultV0, Tuple[_ExecutedAttempt, ...]]:
    raw = (
        FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0
        if case.case_id == "acqv0-s02-content-opaque-invalid-json"
        else FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0
    )
    historical = (
        fixtures.unknown_historical_usage
        if case.case_id == "acqv0-s06-historical-usage-unknown"
        else fixtures.known_historical_usage
    )
    executions = tuple(
        [
            await _execute_attempt(
                fixtures=fixtures,
                case_id=case.case_id,
                ordinal=ordinal,
                raw_bytes=raw,
                historical_usage=historical,
            )
            for ordinal in range(case.attempt_count)
        ]
    )
    common = _case_result_common_values(executions)
    primary_exact = all(
        item.result.outcome is case.expected_outcome for item in executions
    )
    guard_exact = all(
        all(
            row.state is AcquisitionGuardState.PASSED
            for row in item.result.attempt_receipt.guard_evaluations
        )
        for item in executions
    )
    fixture_valid = _positive_assertions_valid(case, executions, fixtures)
    invocation_exact = (
        common["observed_canned_invocations"] == case.expected_canned_invocations
    )
    receipt_count_exact = len(executions) == case.attempt_count
    complete_receipts = _receipts_complete(executions)
    accepted = _accepted_violations(executions, None)
    passed = all(
        (
            fixture_valid,
            primary_exact,
            guard_exact,
            invocation_exact,
            receipt_count_exact,
            complete_receipts,
            not accepted,
        )
    )
    result = AcquisitionCaseResultV0(
        case_id=case.case_id,
        case_fingerprint=case.case_fingerprint or "",
        case_class=AcquisitionCaseClass.POSITIVE,
        expected_outcome=case.expected_outcome,
        expected_canned_invocations=case.expected_canned_invocations,
        injected_negative_conditions=(),
        accepted_violations=accepted,
        fixture_construction_valid=fixture_valid,
        mutation_vector_exact=True,
        primary_result_exact=primary_exact,
        guard_trace_exact=guard_exact,
        invocation_count_exact=invocation_exact,
        receipt_count_exact=receipt_count_exact,
        complete_receipts=complete_receipts,
        case_passed=passed,
        **common,
    )
    return result, executions


async def _evaluate_probe(
    probe: AcquisitionProbeV0,
    fixtures: AcquisitionFixtureSetV0,
) -> Tuple[AcquisitionCaseResultV0, Tuple[_ExecutedAttempt, ...]]:
    execution = await _execute_attempt(
        fixtures=fixtures,
        case_id=probe.probe_id,
        ordinal=0,
        raw_bytes=FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0,
        historical_usage=fixtures.known_historical_usage,
        probe=probe,
    )
    executions = (execution,)
    construction_evidence = _build_probe_construction_evidence_v0(probe, execution)
    construction_valid, measured_vector, changed_paths = (
        measure_probe_mutation_vector_v0(probe, construction_evidence)
    )
    receipt = execution.result.attempt_receipt
    expected_result = AcquisitionPrimaryResult(
        outcome=AcquisitionAttemptOutcome.FAILED_CLOSED,
        primary_guard_id=probe.expected_guard_id,
        failure_code=probe.expected_primary_failure,
    )
    primary_exact = receipt.primary_result == expected_result
    actual_trace = tuple(
        (item.guard_id, item.state) for item in receipt.guard_evaluations
    )
    expected_trace = tuple(
        (item.guard_id, item.state) for item in probe.expected_guard_trace
    )
    guard_exact = actual_trace == expected_trace
    common = _case_result_common_values(executions)
    invocation_exact = (
        common["observed_canned_invocations"] == probe.expected_canned_invocations
    )
    receipt_count_exact = len(executions) == probe.expected_attempt_receipts
    complete_receipts = _receipts_complete(executions)
    vector_exact = measured_vector == probe.mutation_vector
    accepted = _accepted_violations(executions, probe)
    passed = all(
        (
            construction_valid,
            vector_exact,
            primary_exact,
            guard_exact,
            invocation_exact,
            receipt_count_exact,
            complete_receipts,
            not accepted,
        )
    )
    result = AcquisitionCaseResultV0(
        case_id=probe.probe_id,
        case_fingerprint=probe.probe_fingerprint or "",
        case_class=probe.probe_class,
        construction_evidence=construction_evidence,
        literal_mutations=probe.literal_mutations,
        expected_mutation_vector=probe.mutation_vector,
        measured_mutation_vector=measured_vector,
        expected_outcome=AcquisitionAttemptOutcome.FAILED_CLOSED,
        expected_guard_id=probe.expected_guard_id,
        expected_failure_code=probe.expected_primary_failure,
        expected_canned_invocations=probe.expected_canned_invocations,
        injected_negative_conditions=changed_paths,
        accepted_violations=accepted,
        fixture_construction_valid=construction_valid,
        mutation_vector_exact=vector_exact,
        primary_result_exact=primary_exact,
        guard_trace_exact=guard_exact,
        invocation_count_exact=invocation_exact,
        receipt_count_exact=receipt_count_exact,
        complete_receipts=complete_receipts,
        case_passed=passed,
        **common,
    )
    return result, executions


def _validate_case_results_against_frozen_v0(
    results: Sequence[AcquisitionCaseResultV0],
) -> None:
    positives = {item.case_id: item for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0}
    probes = {
        item.probe_id: item
        for item in (
            FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
            + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
        )
    }
    for result in results:
        positive = positives.get(result.case_id)
        if positive is not None:
            if any(
                (
                    result.case_fingerprint != positive.case_fingerprint,
                    result.case_class is not AcquisitionCaseClass.POSITIVE,
                    result.expected_outcome is not positive.expected_outcome,
                    result.expected_canned_invocations
                    != positive.expected_canned_invocations,
                    len(result.attempt_receipt_ids) != positive.attempt_count,
                )
            ):
                raise ContractValidationError("positive result differs from frozen case")
            continue
        probe = probes.get(result.case_id)
        if probe is None or any(
            (
                result.case_fingerprint != probe.probe_fingerprint,
                result.case_class is not probe.probe_class,
                result.literal_mutations != probe.literal_mutations,
                result.expected_mutation_vector != probe.mutation_vector,
                result.expected_outcome is not AcquisitionAttemptOutcome.FAILED_CLOSED,
                result.expected_guard_id is not probe.expected_guard_id,
                result.expected_failure_code is not probe.expected_primary_failure,
                result.expected_canned_invocations
                != probe.expected_canned_invocations,
                len(result.attempt_receipt_ids) != probe.expected_attempt_receipts,
            )
        ):
            raise ContractValidationError("probe result differs from frozen case")


def _positive_receipt_assertions_valid_v0(
    case_id: str,
    receipts: Sequence[AcquisitionAttemptReceipt],
    retentions: Sequence[AcquisitionRetentionReceipt],
    fixtures: AcquisitionFixtureSetV0,
    rows: Sequence[AcquisitionCaseAttemptEvidenceV0],
) -> bool:
    common = all(
        receipt.primary_result.outcome is AcquisitionAttemptOutcome.ACQUIRED
        and receipt.unadmitted_observation_id is not None
        and receipt.execution_usage.complete
        and row.tripwire_counters.external_network_attempts == 0
        and row.tripwire_counters.credential_access_attempts == 0
        and row.tripwire_counters.live_provider_calls == 0
        and row.tripwire_counters.provider_sdk_calls == 0
        and row.tripwire_counters.model_executions == 0
        and row.tripwire_counters.tool_calls == 0
        and row.tripwire_counters.canonical_application_calls == 0
        for receipt, row in zip(receipts, rows)
    )
    if not common:
        return False
    if case_id == "acqv0-s01-complete-deterministic":
        return all(
            (
                len(receipts) == 1,
                receipts[0].computed_raw_response_digest
                == FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0,
                retentions[0].raw_response_text
                == FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0.decode("utf-8"),
            )
        )
    if case_id == "acqv0-s02-content-opaque-invalid-json":
        return all(
            (
                len(receipts) == 1,
                receipts[0].computed_raw_response_digest
                == hashlib.sha256(
                    FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0
                ).hexdigest(),
                retentions[0].raw_response_text
                == FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0.decode("utf-8"),
            )
        )
    if case_id in {
        "acqv0-s03-sibling-byte-identity",
        "acqv0-s04-repeat-semantic-identity",
    }:
        return all(
            (
                len(receipts) == 2,
                len({item.semantic_request_id for item in receipts}) == 1,
                len({item.provider_visible_request_digest for item in receipts}) == 1,
                len({item.branch_id for item in receipts}) == 2,
                len({item.transport_attempt_id for item in receipts}) == 2,
            )
        )
    if case_id == "acqv0-s05-seed-explicitly-unsupported":
        seed_evidence = next(
            item
            for item in fixtures.capability_snapshot.controls
            if item.name is AcquisitionControlName.SEED
        )
        return all(
            (
                len(receipts) == 1,
                fixtures.control_policy.seed.status is AcquisitionSeedStatus.UNSUPPORTED,
                seed_evidence.state is AcquisitionControlState.PROVEN_UNSUPPORTED,
            )
        )
    if case_id == "acqv0-s06-historical-usage-unknown":
        if len(receipts) != 1:
            return False
        historical = receipts[0].historical_usage
        quantities = (
            historical.source_observation_acquisitions,
            historical.source_model_calls,
            historical.source_tool_calls,
            historical.source_tokens,
            historical.source_cost_microusd,
            historical.source_external_wall_time_ms,
        )
        return all(
            item.knowledge is ResourceKnowledgeState.UNKNOWN and item.value is None
            for item in quantities
        )
    return False


def _validate_case_result_receipt_links_v0(
    results: Sequence[AcquisitionCaseResultV0],
    aggregate: AcquisitionAggregateReceipt,
    isolation_receipts: Sequence[AcquisitionIsolationReceipt],
    retention_receipts: Sequence[AcquisitionRetentionReceipt],
) -> None:
    """Independently link every evaluator claim to immutable runtime receipts."""

    receipt_by_id = {
        item.receipt_id or "": item for item in aggregate.attempt_receipts
    }
    if len(receipt_by_id) != len(aggregate.attempt_receipts):
        raise ContractValidationError("aggregate receipt identity collision")
    isolation_by_id = {
        item.isolation_receipt_id or "": item for item in isolation_receipts
    }
    retention_by_id = {
        item.retention_receipt_id or "": item for item in retention_receipts
    }
    if len(isolation_by_id) != len(tuple(isolation_receipts)):
        raise ContractValidationError("isolation receipt identity collision")
    if len(retention_by_id) != len(tuple(retention_receipts)):
        raise ContractValidationError("retention receipt identity collision")
    owned_receipt_ids = tuple(
        row.attempt_receipt_id
        for result in results
        for row in result.attempt_evidence
    )
    if (
        len(set(owned_receipt_ids)) != len(owned_receipt_ids)
        or set(owned_receipt_ids) != set(receipt_by_id)
    ):
        raise ContractValidationError("case receipt ownership is not exact")
    used_isolation_ids = set()
    used_retention_ids = set()
    frozen_fixtures = build_frozen_acquisition_fixtures_v0()
    all_attempt_rows = []
    for result in results:
        rows = tuple(sorted(result.attempt_evidence, key=lambda item: item.attempt_ordinal))
        linked_receipts = tuple(receipt_by_id[row.attempt_receipt_id] for row in rows)
        complete = True
        for row, receipt in zip(rows, linked_receipts):
            expected_branch = (
                f"{_BASELINE_BRANCH_PREFIX}/{result.case_id}/{row.attempt_ordinal}"
            )
            if any(
                (
                    receipt.transport_attempt_id != row.transport_attempt_id,
                    receipt.semantic_request_id != row.semantic_request_id,
                    receipt.branch_id != row.branch_id,
                    receipt.branch_id != expected_branch,
                    receipt.attempt_ordinal != row.attempt_ordinal,
                    receipt.capability_snapshot_id != row.capability_snapshot_id,
                    receipt.control_policy_id != row.control_policy_id,
                    receipt.provider_visible_request_digest
                    != row.provider_visible_prompt_digest,
                    receipt.isolation_receipt_id != row.isolation_receipt_id,
                    receipt.retention_receipt_id != row.retention_receipt_id,
                    receipt.primary_result != row.primary_result,
                    receipt.guard_evaluations != row.guard_evaluations,
                )
            ):
                raise ContractValidationError("case attempt evidence detached from receipt")
            isolation = isolation_by_id.get(row.isolation_receipt_id)
            retention = retention_by_id.get(row.retention_receipt_id)
            if isolation is None or retention is None:
                raise ContractValidationError("case receipt side-evidence link is missing")
            used_isolation_ids.add(row.isolation_receipt_id)
            used_retention_ids.add(row.retention_receipt_id)
            if any(
                (
                    isolation.semantic_request_id != receipt.semantic_request_id,
                    isolation.transport_attempt_id != receipt.transport_attempt_id,
                    retention.semantic_request_id != receipt.semantic_request_id,
                    retention.transport_attempt_id != receipt.transport_attempt_id,
                    retention.provider_visible_prompt_digest
                    != receipt.provider_visible_request_digest,
                    retention.retention_policy_id != retention.policy.retention_policy_id,
                    receipt.retention_policy_compliant != retention.policy_compliant,
                    receipt.source_mutations != isolation.source_mutations,
                    receipt.sibling_mutations != isolation.sibling_mutations,
                    receipt.production_mutations != isolation.production_mutations,
                )
            ):
                raise ContractValidationError("case side receipt detached from attempt")
            complete = complete and all(
                (
                    _contract_roundtrip(receipt),
                    _contract_roundtrip(isolation),
                    _contract_roundtrip(retention),
                )
            )
            all_attempt_rows.append(row)
        if result.complete_receipts is not complete:
            raise ContractValidationError("case receipt-completeness flag changed")
        if result.case_class is AcquisitionCaseClass.POSITIVE:
            if any(
                row.capability_snapshot_id
                != frozen_fixtures.capability_snapshot.capability_snapshot_id
                or row.control_policy_id
                != frozen_fixtures.control_policy.control_policy_id
                for row in rows
            ):
                raise ContractValidationError("positive case fixture identity changed")
            linked_retentions = tuple(
                retention_by_id[row.retention_receipt_id] for row in rows
            )
            expected_fixture_valid = _positive_receipt_assertions_valid_v0(
                result.case_id,
                linked_receipts,
                linked_retentions,
                frozen_fixtures,
                rows,
            )
            if result.fixture_construction_valid is not expected_fixture_valid:
                raise ContractValidationError("positive fixture-valid flag changed")
        else:
            evidence = result.construction_evidence
            if evidence is None:
                raise ContractValidationError("probe construction evidence is missing")
            if any(
                (
                    evidence.baseline.capability_snapshot_id
                    != frozen_fixtures.capability_snapshot.capability_snapshot_id,
                    evidence.baseline.control_policy_id
                    != frozen_fixtures.control_policy.control_policy_id,
                    evidence.baseline.semantic_request_id
                    != frozen_fixtures.semantic_request.semantic_request_id,
                )
            ):
                raise ContractValidationError("probe baseline construction changed")
            if any(
                row.capability_snapshot_id != evidence.probe.capability_snapshot_id
                or row.control_policy_id != evidence.probe.control_policy_id
                or row.semantic_request_id != evidence.probe.semantic_request_id
                for row in rows
            ):
                raise ContractValidationError("probe construction detached from receipt")
    if used_isolation_ids != set(isolation_by_id):
        raise ContractValidationError("artifact isolation receipt ownership is not exact")
    if used_retention_ids != set(retention_by_id):
        raise ContractValidationError("artifact retention receipt ownership is not exact")
    counters = AcquisitionTripwireCounters(
        **{
            name: sum(getattr(row.tripwire_counters, name) for row in all_attempt_rows)
            for name in AcquisitionTripwireCounters.model_fields
        }
    )
    if counters != aggregate.observed_counters:
        raise ContractValidationError("case tripwire evidence differs from aggregate")


_IDENTITY_FAILURES = frozenset(
    {
        AcquisitionFailureCode.INVALID_SEMANTIC_IDENTITY,
        AcquisitionFailureCode.IDENTITY_COLLISION,
        AcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,
        AcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
        AcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
    }
)


def _aggregate_metrics_v0(
    receipts: Tuple[AcquisitionAttemptReceipt, ...],
    counters: AcquisitionTripwireCounters,
) -> AcquisitionAggregateMetrics:
    quantities = tuple(
        receipt.execution_usage.canned_transport_invocations for receipt in receipts
    )
    if all(
        quantity.knowledge is ResourceKnowledgeState.KNOWN
        for quantity in quantities
    ):
        receipt_total = sum(quantity.value or 0 for quantity in quantities)
        receipt_invocations = AcquisitionResourceQuantity.known(receipt_total)
        uncounted = AcquisitionResourceQuantity.known(
            abs(counters.canned_transport_invocations - receipt_total)
        )
    else:
        receipt_invocations = AcquisitionResourceQuantity.unknown()
        uncounted = AcquisitionResourceQuantity.unknown()
    failure_counts: Dict[AcquisitionFailureCode, int] = {}
    for receipt in receipts:
        code = receipt.primary_result.failure_code
        if code is not None:
            failure_counts[code] = failure_counts.get(code, 0) + 1
    return AcquisitionAggregateMetrics(
        attempts_total=len(receipts),
        acquired_attempts=sum(
            receipt.primary_result.outcome is AcquisitionAttemptOutcome.ACQUIRED
            for receipt in receipts
        ),
        failed_closed_attempts=sum(
            receipt.primary_result.outcome is AcquisitionAttemptOutcome.FAILED_CLOSED
            for receipt in receipts
        ),
        receipt_canned_transport_invocations=receipt_invocations,
        observed_canned_transport_invocations=counters.canned_transport_invocations,
        uncounted_canned_invocations=uncounted,
        external_network_attempts=counters.external_network_attempts,
        credential_access_attempts=counters.credential_access_attempts,
        live_provider_calls=counters.live_provider_calls,
        provider_sdk_calls=counters.provider_sdk_calls,
        model_executions=counters.model_executions,
        tool_calls=counters.tool_calls,
        canonical_application_calls=counters.canonical_application_calls,
        incomplete_usage_receipts=sum(
            not receipt.execution_usage.complete for receipt in receipts
        ),
        identity_mismatches=sum(
            receipt.primary_result.failure_code in _IDENTITY_FAILURES
            for receipt in receipts
        ),
        prompt_byte_mismatches=sum(
            receipt.prompt_byte_mismatch for receipt in receipts
        ),
        source_mutations=sum(receipt.source_mutations for receipt in receipts),
        sibling_mutations=sum(receipt.sibling_mutations for receipt in receipts),
        production_mutations=sum(receipt.production_mutations for receipt in receipts),
        retention_violations=sum(
            not receipt.retention_policy_compliant for receipt in receipts
        ),
        receipt_mismatches=failure_counts.get(
            AcquisitionFailureCode.RECEIPT_MISMATCH, 0
        ),
        failures_by_code=tuple(
            AcquisitionFailureCount(failure_code=code, count=count)
            for code, count in failure_counts.items()
        ),
    )


def _sum_tripwire_counters(
    executions: Sequence[_ExecutedAttempt],
) -> AcquisitionTripwireCounters:
    fields = tuple(AcquisitionTripwireCounters.model_fields)
    return AcquisitionTripwireCounters(
        **{
            name: sum(getattr(item.result.tripwire_counters, name) for item in executions)
            for name in fields
        }
    )


def _build_aggregate_receipt_v0(
    executions: Sequence[_ExecutedAttempt],
) -> AcquisitionAggregateReceipt:
    receipts = tuple(item.result.attempt_receipt for item in executions)
    counters = _sum_tripwire_counters(executions)
    metrics = _aggregate_metrics_v0(receipts, counters)
    return AcquisitionAggregateReceipt(
        experiment_id=ACQUISITION_EXPERIMENT_ID_V0,
        case_set_id=FROZEN_ACQUISITION_CASE_SET_V0.case_set_id or "",
        attempt_receipts=receipts,
        observed_counters=counters,
        metrics=metrics,
    )


def _result_has_path(result: AcquisitionCaseResultV0, path: str) -> bool:
    return any(item.path == path for item in result.literal_mutations)


def _result_acquired(result: AcquisitionCaseResultV0) -> bool:
    return any(
        item.outcome is AcquisitionAttemptOutcome.ACQUIRED
        for item in result.actual_primary_results
    )


def _known_usage_total(
    receipts: Sequence[AcquisitionAttemptReceipt],
    field_name: str,
) -> int:
    values = []
    for receipt in receipts:
        quantity = getattr(receipt.execution_usage, field_name)
        if quantity.knowledge is not ResourceKnowledgeState.KNOWN:
            return 0
        values.append(quantity.value or 0)
    return sum(values)


def _calculate_evaluation_metrics_v0(
    case_results: Sequence[AcquisitionCaseResultV0],
    aggregate: AcquisitionAggregateReceipt,
    historical_hashes: Sequence[AcquisitionHistoricalHashEvidenceV0],
) -> AcquisitionEvaluationMetricsV0:
    results = tuple(case_results)
    historical_hashes = _validate_historical_hash_membership_v0(historical_hashes)
    receipts = aggregate.attempt_receipts
    positives = tuple(
        item for item in results if item.case_class is AcquisitionCaseClass.POSITIVE
    )
    orthogonal = tuple(
        item for item in results if item.case_class is AcquisitionCaseClass.ORTHOGONAL
    )
    precedence = tuple(
        item for item in results if item.case_class is AcquisitionCaseClass.PRECEDENCE
    )
    acquired_receipts = tuple(
        item
        for item in receipts
        if item.primary_result.outcome is AcquisitionAttemptOutcome.ACQUIRED
    )
    path_counts: Dict[str, int] = {}
    accepted_path_counts: Dict[str, int] = {}
    for result in results:
        for mutation in result.literal_mutations:
            path_counts[mutation.path] = path_counts.get(mutation.path, 0) + 1
            if _result_acquired(result):
                accepted_path_counts[mutation.path] = (
                    accepted_path_counts.get(mutation.path, 0) + 1
                )

    invalid_probe_constructions = sum(
        not item.fixture_construction_valid for item in orthogonal + precedence
    )
    historical_mismatches = sum(not item.matches for item in historical_hashes)
    accepted_source = sum(item.source_mutations for item in acquired_receipts)
    accepted_sibling = sum(item.sibling_mutations for item in acquired_receipts)
    accepted_production = sum(item.production_mutations for item in acquired_receipts)
    accepted_incomplete = sum(
        not item.execution_usage.complete for item in acquired_receipts
    )
    accepted_missing = sum(
        item.computed_raw_response_digest is None for item in acquired_receipts
    )
    accepted_retention = sum(
        not item.retention_policy_compliant for item in acquired_receipts
    )
    semantic_collisions = sum(
        item.primary_result.failure_code is AcquisitionFailureCode.IDENTITY_COLLISION
        for item in receipts
    )
    successful_retry = sum(
        sum(
            value or 0
            for value in (
                item.explicit_retry_count,
                item.adapter_retry_count,
                item.sdk_internal_retry_count,
                item.hidden_transport_retry_count,
            )
        )
        for item in acquired_receipts
    )
    successful_fallback = sum(bool(item.fallback_used) for item in acquired_receipts)
    timeout_worker_paths = (
        "envelope.worker_terminated",
        "capability.worker_termination",
    )
    accepted_worker_leaks = sum(
        count
        for path, count in accepted_path_counts.items()
        if path in timeout_worker_paths
    )
    accepted_uncounted = accepted_path_counts.get(
        "attempt_recorder.canned_transport_invocations", 0
    )
    accepted_false_zero = accepted_path_counts.get(
        "envelope.usage.tokens.knowledge", 0
    )
    accepted_receipt_mismatches = accepted_path_counts.get(
        "attempt_recorder.final_receipt_integrity", 0
    )
    accepted_future_labels = accepted_path_counts.get(
        "envelope.expected_canonical_acceptance", 0
    )

    preliminary = {
        "cases_total": len(results),
        "positive_cases_total": len(positives),
        "positive_complete_case_results": sum(item.case_passed for item in positives),
        "positive_attempt_receipts": sum(
            len(item.attempt_receipt_ids) for item in positives
        ),
        "orthogonal_probes_total": len(orthogonal),
        "orthogonal_exact_primary_results": sum(item.case_passed for item in orthogonal),
        "precedence_probes_total": len(precedence),
        "precedence_exact_primary_results": sum(item.case_passed for item in precedence),
        "attempt_receipts_total": len(receipts),
        "observed_canned_transport_invocations": (
            aggregate.observed_counters.canned_transport_invocations
        ),
        "invalid_probe_constructions": invalid_probe_constructions,
        "semantic_identity_collisions": semantic_collisions,
        "accepted_prompt_byte_mismatches": sum(
            item.prompt_byte_mismatch for item in acquired_receipts
        ),
        "external_network_attempts": aggregate.observed_counters.external_network_attempts,
        "credential_access_attempts": aggregate.observed_counters.credential_access_attempts,
        "live_provider_calls": aggregate.observed_counters.live_provider_calls,
        "provider_sdk_calls": aggregate.observed_counters.provider_sdk_calls,
        "model_executions": aggregate.observed_counters.model_executions,
        "tool_calls": aggregate.observed_counters.tool_calls,
        "canonical_application_invocations": (
            aggregate.observed_counters.canonical_application_calls
        ),
        "injected_uncounted_canned_invocations": path_counts.get(
            "attempt_recorder.canned_transport_invocations", 0
        ),
        "accepted_uncounted_canned_invocations": accepted_uncounted,
        "accepted_successful_retry_activations": successful_retry,
        "accepted_successful_fallback_activations": successful_fallback,
        "accepted_timeout_worker_leaks": accepted_worker_leaks,
        "injected_source_mutations": aggregate.metrics.source_mutations,
        "injected_sibling_mutations": aggregate.metrics.sibling_mutations,
        "injected_production_mutations": aggregate.metrics.production_mutations,
        "accepted_source_mutations": accepted_source,
        "accepted_sibling_mutations": accepted_sibling,
        "accepted_production_mutations": accepted_production,
        "injected_missing_raw_conditions": path_counts.get(
            "envelope.raw_response_text", 0
        ),
        "accepted_missing_raw_observations": accepted_missing,
        "injected_false_zero_usage_conditions": path_counts.get(
            "envelope.usage.tokens.knowledge", 0
        ),
        "accepted_false_zero_usage": accepted_false_zero,
        "injected_incomplete_usage_conditions": (
            path_counts.get("envelope.new_usage_completeness", 0)
            + path_counts.get("envelope.usage.tokens.knowledge", 0)
        ),
        "accepted_incomplete_attempt_receipts": accepted_incomplete,
        "injected_retention_conditions": path_counts.get(
            "retention_receipt.artifact_inclusion", 0
        ),
        "accepted_retention_violations": accepted_retention,
        "injected_receipt_mismatch_conditions": path_counts.get(
            "attempt_recorder.final_receipt_integrity", 0
        ),
        "accepted_receipt_mismatches": accepted_receipt_mismatches,
        "injected_future_label_conditions": path_counts.get(
            "envelope.expected_canonical_acceptance", 0
        ),
        "accepted_future_label_violations": accepted_future_labels,
        "new_tokens": _known_usage_total(receipts, "new_tokens"),
        "new_cost_microusd": _known_usage_total(receipts, "new_cost_microusd"),
        "external_provider_wall_time_ms": _known_usage_total(
            receipts, "external_provider_wall_time_ms"
        ),
        "historical_lock_mismatches": historical_mismatches,
    }
    mismatch_or_failure_count = sum(not item.case_passed for item in results)
    mismatch_or_failure_count += historical_mismatches
    mismatch_or_failure_count += sum(
        preliminary[name]
        for name in (
            "invalid_probe_constructions",
            "semantic_identity_collisions",
            "accepted_prompt_byte_mismatches",
            "external_network_attempts",
            "credential_access_attempts",
            "live_provider_calls",
            "provider_sdk_calls",
            "model_executions",
            "tool_calls",
            "canonical_application_invocations",
            "accepted_uncounted_canned_invocations",
            "accepted_successful_retry_activations",
            "accepted_successful_fallback_activations",
            "accepted_timeout_worker_leaks",
            "accepted_source_mutations",
            "accepted_sibling_mutations",
            "accepted_production_mutations",
            "accepted_missing_raw_observations",
            "accepted_false_zero_usage",
            "accepted_incomplete_attempt_receipts",
            "accepted_retention_violations",
            "accepted_receipt_mismatches",
            "accepted_future_label_violations",
            "new_tokens",
            "new_cost_microusd",
            "external_provider_wall_time_ms",
        )
    )
    mismatch_or_failure_count += sum(
        (
            preliminary["cases_total"] != 49,
            preliminary["positive_cases_total"] != 6,
            preliminary["positive_attempt_receipts"] != 8,
            preliminary["orthogonal_probes_total"] != 36,
            preliminary["precedence_probes_total"] != 7,
            preliminary["attempt_receipts_total"] != 51,
            preliminary["observed_canned_transport_invocations"] != 31,
        )
    )
    return AcquisitionEvaluationMetricsV0(
        **preliminary,
        mismatch_or_failure_count=mismatch_or_failure_count,
    )


def supports_acquisition_metrics_v0(
    metrics: AcquisitionEvaluationMetricsV0,
    thresholds: AcquisitionThresholdsV0 = FROZEN_ACQUISITION_THRESHOLDS_V0,
) -> bool:
    """Apply every frozen threshold; there is no soft or average pass."""

    return all(
        (
            metrics.cases_total == thresholds.cases_total,
            metrics.positive_cases_total == thresholds.positive_cases_total,
            metrics.positive_complete_case_results
            == thresholds.required_positive_complete_case_results,
            metrics.positive_attempt_receipts
            == thresholds.required_positive_attempt_receipts,
            metrics.orthogonal_probes_total == thresholds.orthogonal_probes_total,
            metrics.orthogonal_exact_primary_results
            == thresholds.required_orthogonal_exact_primary_results,
            metrics.precedence_probes_total == thresholds.precedence_probes_total,
            metrics.precedence_exact_primary_results
            == thresholds.required_precedence_exact_primary_results,
            metrics.attempt_receipts_total
            == thresholds.required_attempt_receipts_total,
            metrics.observed_canned_transport_invocations
            == thresholds.required_canned_transport_invocations,
            metrics.mismatch_or_failure_count
            == thresholds.maximum_mismatch_or_failure_count,
            metrics.invalid_probe_constructions
            == thresholds.required_invalid_probe_constructions,
            metrics.semantic_identity_collisions
            == thresholds.required_semantic_identity_collisions,
            metrics.accepted_prompt_byte_mismatches
            == thresholds.required_prompt_byte_mismatches,
            metrics.external_network_attempts
            == thresholds.required_external_network_attempts,
            metrics.credential_access_attempts
            == thresholds.required_credential_access_attempts,
            metrics.live_provider_calls == thresholds.required_live_provider_calls,
            metrics.provider_sdk_calls == 0,
            metrics.model_executions == thresholds.required_model_executions,
            metrics.tool_calls == thresholds.required_tool_calls,
            metrics.accepted_uncounted_canned_invocations
            == thresholds.required_uncounted_canned_invocations,
            metrics.accepted_successful_retry_activations
            == thresholds.required_successful_retry_activations,
            metrics.accepted_successful_fallback_activations
            == thresholds.required_successful_fallback_activations,
            metrics.accepted_timeout_worker_leaks
            == thresholds.required_timeout_worker_leaks,
            metrics.accepted_source_mutations == thresholds.required_source_mutations,
            metrics.accepted_sibling_mutations == thresholds.required_sibling_mutations,
            metrics.accepted_production_mutations
            == thresholds.required_production_mutations,
            metrics.accepted_missing_raw_observations
            == thresholds.required_accepted_missing_raw_observations,
            metrics.accepted_false_zero_usage
            == thresholds.required_accepted_false_zero_usage,
            metrics.accepted_incomplete_attempt_receipts
            == thresholds.required_incomplete_attempt_receipts,
            metrics.accepted_retention_violations
            == thresholds.required_retention_violations,
            metrics.accepted_receipt_mismatches
            == thresholds.required_receipt_mismatches,
            metrics.accepted_future_label_violations
            == thresholds.required_future_label_violations,
            metrics.canonical_application_invocations
            == thresholds.required_canonical_application_invocations,
            metrics.new_tokens == thresholds.required_new_tokens,
            metrics.new_cost_microusd == thresholds.required_new_cost_microusd,
            metrics.external_provider_wall_time_ms
            == thresholds.required_external_provider_wall_time_ms,
            metrics.historical_lock_mismatches
            == thresholds.required_historical_lock_mismatches,
        )
    )


FROZEN_POSITIVE_CASE_ORDER_V0: Tuple[str, ...] = tuple(
    item.case_id for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0
)
FROZEN_ORTHOGONAL_PROBE_ORDER_V0: Tuple[str, ...] = tuple(
    item.probe_id for item in FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
)
FROZEN_PRECEDENCE_PROBE_ORDER_V0: Tuple[str, ...] = tuple(
    item.probe_id for item in FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
)
FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0: Tuple[str, ...] = tuple(
    reversed(FROZEN_POSITIVE_CASE_ORDER_V0)
)
FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0: Tuple[str, ...] = tuple(
    reversed(FROZEN_ORTHOGONAL_PROBE_ORDER_V0)
)
FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0: Tuple[str, ...] = tuple(
    reversed(FROZEN_PRECEDENCE_PROBE_ORDER_V0)
)


def _validate_case_order(
    selected: Tuple[str, ...],
    frozen: Tuple[str, ...],
    *,
    name: str,
) -> Tuple[str, ...]:
    if len(selected) != len(frozen) or set(selected) != set(frozen):
        raise ContractValidationError(f"{name} is not an exact frozen permutation")
    return selected


async def _build_acquisition_experiment_artifact_in_order_v0(
    *,
    positive_order: Tuple[str, ...],
    orthogonal_order: Tuple[str, ...],
    precedence_order: Tuple[str, ...],
    repository_root: Optional[Path | str] = None,
) -> AcquisitionExperimentArtifactV0:
    selected_positive = _validate_case_order(
        positive_order,
        FROZEN_POSITIVE_CASE_ORDER_V0,
        name="positive_order",
    )
    selected_orthogonal = _validate_case_order(
        orthogonal_order,
        FROZEN_ORTHOGONAL_PROBE_ORDER_V0,
        name="orthogonal_order",
    )
    selected_precedence = _validate_case_order(
        precedence_order,
        FROZEN_PRECEDENCE_PROBE_ORDER_V0,
        name="precedence_order",
    )
    fixtures = build_frozen_acquisition_fixtures_v0()
    positive_by_id = {
        item.case_id: item for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0
    }
    probe_by_id = {
        item.probe_id: item
        for item in (
            FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
            + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
        )
    }
    case_results = []
    executions = []
    for case_id in selected_positive:
        case_result, case_executions = await _evaluate_positive_case(
            positive_by_id[case_id], fixtures
        )
        case_results.append(case_result)
        executions.extend(case_executions)
    for probe_id in selected_orthogonal + selected_precedence:
        case_result, case_executions = await _evaluate_probe(
            probe_by_id[probe_id], fixtures
        )
        case_results.append(case_result)
        executions.extend(case_executions)

    aggregate = _build_aggregate_receipt_v0(executions)
    historical_hashes = verify_frozen_historical_hashes_v0(repository_root)
    metrics = _calculate_evaluation_metrics_v0(
        case_results,
        aggregate,
        historical_hashes,
    )
    supported = supports_acquisition_metrics_v0(metrics)
    receipts = aggregate.attempt_receipts
    return AcquisitionExperimentArtifactV0(
        validation_order_id=(
            FROZEN_ACQUISITION_VALIDATION_ORDER.validation_order_id or ""
        ),
        failure_taxonomy_id=(
            FROZEN_ACQUISITION_FAILURE_TAXONOMY.failure_taxonomy_id or ""
        ),
        case_set_id=FROZEN_ACQUISITION_CASE_SET_V0.case_set_id or "",
        case_set_sha256=frozen_acquisition_case_set_sha256_v0(),
        thresholds_id=FROZEN_ACQUISITION_THRESHOLDS_V0.thresholds_id or "",
        thresholds=FROZEN_ACQUISITION_THRESHOLDS_V0,
        fixture_set_id=fixtures.fixture_set_id or "",
        capability_snapshot_ids=tuple(
            sorted({item.capability_snapshot_id for item in receipts})
        ),
        control_policy_ids=tuple(
            sorted({item.control_policy_id for item in receipts})
        ),
        semantic_request_ids=tuple(
            sorted({item.semantic_request_id for item in receipts})
        ),
        transport_attempt_ids=tuple(
            sorted(item.transport_attempt_id for item in receipts)
        ),
        case_results=tuple(case_results),
        metrics_id=metrics.metrics_id or "",
        metrics=metrics,
        aggregate_receipt=aggregate,
        attempt_receipt_ids=tuple(sorted(item.receipt_id or "" for item in receipts)),
        isolation_receipts=tuple(
            item.result.isolation_receipt for item in executions
        ),
        retention_receipts=tuple(
            item.result.retention_receipt for item in executions
        ),
        provider_visible_prompt_digests=tuple(
            sorted({item.provider_visible_request_digest for item in receipts})
        ),
        historical_hashes=historical_hashes,
        tripwire_counters=aggregate.observed_counters,
        hypothesis_status="SUPPORTED" if supported else "FALSIFIED",
    )


async def build_acquisition_experiment_artifact_v0_async(
    *,
    repository_root: Optional[Path | str] = None,
) -> AcquisitionExperimentArtifactV0:
    """Explicitly execute the frozen authoritative-order aggregate.

    Callers must enforce the repository's pre-result freeze before invoking this
    function.  Merely importing this module never calls it.
    """

    return await _build_acquisition_experiment_artifact_in_order_v0(
        positive_order=FROZEN_POSITIVE_CASE_ORDER_V0,
        orthogonal_order=FROZEN_ORTHOGONAL_PROBE_ORDER_V0,
        precedence_order=FROZEN_PRECEDENCE_PROBE_ORDER_V0,
        repository_root=repository_root,
    )


def _assert_no_running_loop() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise ContractValidationError(
        "synchronous acquisition builder cannot run inside an event loop; use async API"
    )


def build_acquisition_experiment_artifact_v0(
    *,
    repository_root: Optional[Path | str] = None,
) -> AcquisitionExperimentArtifactV0:
    _assert_no_running_loop()
    return asyncio.run(
        build_acquisition_experiment_artifact_v0_async(
            repository_root=repository_root
        )
    )


async def build_acquisition_replay_artifact_v0_async(
    authoritative: AcquisitionExperimentArtifactV0,
    *,
    repository_root: Optional[Path | str] = None,
) -> AcquisitionReplayExecutionV0:
    rendered = render_acquisition_experiment_artifact_v0(authoritative)
    validated = replay_acquisition_experiment_artifact_v0(rendered)
    if validated.hypothesis_status != "SUPPORTED":
        raise ContractValidationError(
            "reverse replay is forbidden until the authoritative artifact is SUPPORTED"
        )
    replay_artifact = await _build_acquisition_experiment_artifact_in_order_v0(
        positive_order=FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0,
        orthogonal_order=FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0,
        precedence_order=FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0,
        repository_root=repository_root,
    )
    if render_acquisition_experiment_artifact_v0(replay_artifact) != rendered:
        raise ContractValidationError("reverse replay artifact is not byte-identical")
    ordered_case_ids = (
        FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0
        + FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0
        + FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0
    )
    results = {item.case_id: item for item in replay_artifact.case_results}
    return AcquisitionReplayExecutionV0(
        source_authoritative_artifact_id=authoritative.artifact_id or "",
        source_authoritative_sha256=hashlib.sha256(
            rendered.encode("utf-8")
        ).hexdigest(),
        artifact=replay_artifact,
        positive_order=FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0,
        orthogonal_order=FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0,
        precedence_order=FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0,
        ordered_case_ids=ordered_case_ids,
        ordered_case_result_ids=tuple(
            results[case_id].case_result_id or "" for case_id in ordered_case_ids
        ),
        ordered_transport_attempt_ids=tuple(
            attempt.transport_attempt_id
            for case_id in ordered_case_ids
            for attempt in sorted(
                results[case_id].attempt_evidence,
                key=lambda item: item.attempt_ordinal,
            )
        ),
    )


def build_acquisition_replay_artifact_v0(
    authoritative: AcquisitionExperimentArtifactV0,
    *,
    repository_root: Optional[Path | str] = None,
) -> AcquisitionReplayExecutionV0:
    _assert_no_running_loop()
    return asyncio.run(
        build_acquisition_replay_artifact_v0_async(
            authoritative,
            repository_root=repository_root,
        )
    )


def render_acquisition_experiment_artifact_v0(
    artifact: AcquisitionExperimentArtifactV0,
) -> str:
    validated = AcquisitionExperimentArtifactV0.model_validate_json(
        artifact.model_dump_json()
    )
    return canonical_json(validated.model_dump(mode="json")) + "\n"


def replay_acquisition_experiment_artifact_v0(
    rendered: str,
) -> AcquisitionExperimentArtifactV0:
    artifact = AcquisitionExperimentArtifactV0.model_validate_json(rendered)
    canonical = canonical_json(artifact.model_dump(mode="json")) + "\n"
    if canonical != rendered:
        raise ContractValidationError("acquisition artifact bytes are not canonical")
    return artifact


def acquisition_experiment_artifact_sha256_v0(
    artifact: AcquisitionExperimentArtifactV0,
) -> str:
    return hashlib.sha256(
        render_acquisition_experiment_artifact_v0(artifact).encode("utf-8")
    ).hexdigest()


def render_acquisition_replay_execution_v0(
    replay_execution: AcquisitionReplayExecutionV0,
) -> str:
    validated = AcquisitionReplayExecutionV0.model_validate_json(
        replay_execution.model_dump_json()
    )
    return canonical_json(validated.model_dump(mode="json")) + "\n"


def replay_acquisition_replay_execution_v0(
    rendered: str,
) -> AcquisitionReplayExecutionV0:
    replay_execution = AcquisitionReplayExecutionV0.model_validate_json(rendered)
    canonical = canonical_json(replay_execution.model_dump(mode="json")) + "\n"
    if canonical != rendered:
        raise ContractValidationError("replay-execution bytes are not canonical")
    return replay_execution


def acquisition_replay_execution_sha256_v0(
    replay_execution: AcquisitionReplayExecutionV0,
) -> str:
    return hashlib.sha256(
        render_acquisition_replay_execution_v0(replay_execution).encode("utf-8")
    ).hexdigest()


def create_acquisition_replay_lock_v0(
    authoritative: AcquisitionExperimentArtifactV0,
    replay: AcquisitionReplayExecutionV0,
) -> AcquisitionReplayLockV0:
    if not isinstance(authoritative, AcquisitionExperimentArtifactV0) or not isinstance(
        replay, AcquisitionReplayExecutionV0
    ):
        raise ContractValidationError(
            "replay lock requires an artifact and reverse-execution evidence"
        )
    authoritative_rendered = render_acquisition_experiment_artifact_v0(authoritative)
    replay_serialized = render_acquisition_replay_execution_v0(replay)
    replay_validated_execution = replay_acquisition_replay_execution_v0(
        replay_serialized
    )
    replay_rendered = render_acquisition_experiment_artifact_v0(
        replay_validated_execution.artifact
    )
    authoritative_validated = replay_acquisition_experiment_artifact_v0(
        authoritative_rendered
    )
    replay_validated = replay_acquisition_experiment_artifact_v0(replay_rendered)
    if (
        authoritative_validated.hypothesis_status != "SUPPORTED"
        or replay_validated.hypothesis_status != "SUPPORTED"
    ):
        raise ContractValidationError("replay lock requires two SUPPORTED artifacts")
    semantic_equality = (
        authoritative_validated.model_dump(mode="json")
        == replay_validated.model_dump(mode="json")
    )
    artifact_id_equality = (
        authoritative_validated.artifact_id == replay_validated.artifact_id
    )
    byte_identity = authoritative_rendered == replay_rendered
    if not all((semantic_equality, artifact_id_equality, byte_identity)):
        raise ContractValidationError("independent reverse replay did not lock")
    return AcquisitionReplayLockV0(
        authoritative_artifact_id=authoritative_validated.artifact_id or "",
        replay_artifact_id=replay_validated.artifact_id or "",
        replay_execution_id=replay_validated_execution.replay_execution_id or "",
        replay_execution_trace_sha256=(
            replay_validated_execution.execution_trace_sha256 or ""
        ),
        authoritative_sha256=hashlib.sha256(
            authoritative_rendered.encode("utf-8")
        ).hexdigest(),
        replay_sha256=hashlib.sha256(replay_rendered.encode("utf-8")).hexdigest(),
        authoritative_positive_order=FROZEN_POSITIVE_CASE_ORDER_V0,
        authoritative_orthogonal_order=FROZEN_ORTHOGONAL_PROBE_ORDER_V0,
        authoritative_precedence_order=FROZEN_PRECEDENCE_PROBE_ORDER_V0,
        replay_positive_order=FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0,
        replay_orthogonal_order=FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0,
        replay_precedence_order=FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0,
        replay_ordered_case_ids=replay_validated_execution.ordered_case_ids,
        replay_ordered_case_result_ids=(
            replay_validated_execution.ordered_case_result_ids
        ),
        replay_ordered_transport_attempt_ids=(
            replay_validated_execution.ordered_transport_attempt_ids
        ),
    )


def render_acquisition_replay_lock_v0(replay_lock: AcquisitionReplayLockV0) -> str:
    validated = AcquisitionReplayLockV0.model_validate_json(
        replay_lock.model_dump_json()
    )
    return canonical_json(validated.model_dump(mode="json")) + "\n"


def replay_acquisition_replay_lock_v0(rendered: str) -> AcquisitionReplayLockV0:
    replay_lock = AcquisitionReplayLockV0.model_validate_json(rendered)
    canonical = canonical_json(replay_lock.model_dump(mode="json")) + "\n"
    if canonical != rendered:
        raise ContractValidationError("acquisition replay-lock bytes are not canonical")
    return replay_lock


def acquisition_replay_lock_sha256_v0(replay_lock: AcquisitionReplayLockV0) -> str:
    return hashlib.sha256(
        render_acquisition_replay_lock_v0(replay_lock).encode("utf-8")
    ).hexdigest()


def write_once_canonical_bytes_v0(destination: Path | str, payload: bytes) -> str:
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


def publish_acquisition_experiment_artifact_once_v0(
    destination: Path | str,
    artifact: AcquisitionExperimentArtifactV0,
) -> str:
    rendered = render_acquisition_experiment_artifact_v0(artifact)
    replay_acquisition_experiment_artifact_v0(rendered)
    return write_once_canonical_bytes_v0(destination, rendered.encode("utf-8"))


def publish_acquisition_replay_lock_once_v0(
    destination: Path | str,
    authoritative: AcquisitionExperimentArtifactV0,
    replay: AcquisitionReplayExecutionV0,
) -> str:
    replay_lock = create_acquisition_replay_lock_v0(authoritative, replay)
    rendered = render_acquisition_replay_lock_v0(replay_lock)
    replay_acquisition_replay_lock_v0(rendered)
    return write_once_canonical_bytes_v0(destination, rendered.encode("utf-8"))


__all__ = [
    "ACQUISITION_ARTIFACT_SCHEMA_V0",
    "ACQUISITION_ATTEMPT_EVIDENCE_SCHEMA_V0",
    "ACQUISITION_CASE_RESULT_SCHEMA_V0",
    "ACQUISITION_CONSTRUCTION_STATE_SCHEMA_V0",
    "ACQUISITION_EXPERIMENT_ID_V0",
    "ACQUISITION_FIXTURE_SET_SCHEMA_V0",
    "ACQUISITION_HISTORICAL_HASH_SCHEMA_V0",
    "ACQUISITION_METRICS_SCHEMA_V0",
    "ACQUISITION_MUTATION_OBSERVATION_SCHEMA_V0",
    "ACQUISITION_PROBE_CONSTRUCTION_SCHEMA_V0",
    "ACQUISITION_REPLAY_EXECUTION_SCHEMA_V0",
    "ACQUISITION_REPLAY_LOCK_SCHEMA_V0",
    "AcquisitionCaseAttemptEvidenceV0",
    "AcquisitionCaseResultV0",
    "AcquisitionConstructionStateV0",
    "AcquisitionEvaluationMetricsV0",
    "AcquisitionExperimentArtifactV0",
    "AcquisitionFixtureSetV0",
    "AcquisitionHistoricalHashEvidenceV0",
    "AcquisitionMutationObservationV0",
    "AcquisitionProbeConstructionEvidenceV0",
    "AcquisitionReplayExecutionV0",
    "AcquisitionReplayLockV0",
    "FROZEN_ORTHOGONAL_PROBE_ORDER_V0",
    "FROZEN_POSITIVE_CASE_ORDER_V0",
    "FROZEN_PRECEDENCE_PROBE_ORDER_V0",
    "FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0",
    "FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0",
    "FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0",
    "acquisition_experiment_artifact_sha256_v0",
    "acquisition_replay_execution_sha256_v0",
    "acquisition_replay_lock_sha256_v0",
    "build_acquisition_experiment_artifact_v0",
    "build_acquisition_experiment_artifact_v0_async",
    "build_acquisition_replay_artifact_v0",
    "build_acquisition_replay_artifact_v0_async",
    "build_frozen_acquisition_fixtures_v0",
    "create_acquisition_replay_lock_v0",
    "measure_probe_mutation_vector_v0",
    "publish_acquisition_experiment_artifact_once_v0",
    "publish_acquisition_replay_lock_once_v0",
    "render_acquisition_experiment_artifact_v0",
    "render_acquisition_replay_execution_v0",
    "render_acquisition_replay_lock_v0",
    "replay_acquisition_experiment_artifact_v0",
    "replay_acquisition_replay_execution_v0",
    "replay_acquisition_replay_lock_v0",
    "supports_acquisition_metrics_v0",
    "verify_frozen_historical_hashes_v0",
    "write_once_canonical_bytes_v0",
]

"""Immutable contracts for the Phase 8 canonical successor environment.

The contracts in this module do not execute CED, parse a model response, call a
provider, or choose an action.  They freeze the inputs and auditable outputs of
exactly one isolated opening transition.  Canonical transition semantics and
canonical ``move_id`` construction remain owned by :mod:`backend.dialogues.ced`.

Recorded historical acquisition usage is deliberately separate from the work
performed by a new offline replay.  Unknown historical values remain unknown;
they are never represented as zero.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, ClassVar, Dict, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ced_search_observability_v1 import (
    SEARCH_STATE_V1_PROJECTION_VERSION,
    SearchStateV1,
)
from .models import AgentRole, DialogPhase, TaskKind
from .socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    SearchBudget,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_ENV_ID = "ced-canonical-successor-env/v0"
CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION = "ced-canonical-branch-capsule/v0"
PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION = (
    "ced-pending-canonical-transition/v0"
)
RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION = "ced-recorded-observation/v0"
CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION = "ced-canonical-transition-result/v0"
CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION = (
    "ced-canonical-transition-receipt/v0"
)
SUPPORTED_ACTION_FAMILY = "ced-opening-socratic-question/v0"
OFFLINE_FIXTURE_PRIVACY_CLASSIFICATION = "offline_fixture"

_HEX64_PATTERN = r"^[0-9a-f]{64}$"


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _optional_nonblank(value: Optional[str]) -> Optional[str]:
    if value is not None:
        _nonblank(value)
    return value


def _semantic_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _raw_text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_tuple(values: Tuple[str, ...], field_name: str) -> Tuple[str, ...]:
    ordered = tuple(sorted(values))
    if any(not value.strip() for value in ordered):
        raise ContractValidationError(f"{field_name} must not contain blank values")
    if len(set(ordered)) != len(ordered):
        raise ContractValidationError(f"{field_name} must not contain duplicates")
    return ordered


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanonicalTaskIdentity(_FrozenContract):
    """Normalized CED task coordinates; random ``task_id`` is intentionally absent."""

    phase: DialogPhase
    round_number: int = Field(ge=0, strict=True)
    slot_index: int = Field(ge=0, strict=True)
    attempt_index: int = Field(ge=0, strict=True)
    agent_id: str
    role: AgentRole
    task_kind: TaskKind
    task_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    context_digest: str = Field(pattern=_HEX64_PATTERN)
    request_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    model_config_digest: str = Field(pattern=_HEX64_PATTERN)

    _agent_id_nonblank = field_validator("agent_id")(_nonblank)

    def identity_payload(self) -> Dict[str, object]:
        return {
            "phase": self.phase.value,
            "round_number": self.round_number,
            "slot_index": self.slot_index,
            "attempt_index": self.attempt_index,
            "agent_id": self.agent_id,
            "role": self.role.value,
            "task_kind": self.task_kind.value,
            "task_semantic_digest": self.task_semantic_digest,
            "context_digest": self.context_digest,
            "request_semantic_digest": self.request_semantic_digest,
            "model_config_digest": self.model_config_digest,
        }


class ProviderBindingIdentity(_FrozenContract):
    """Exact provider/model binding needed to replay one canonical seat."""

    agent_id: str
    provider_id: str
    model_id: str
    model_config_digest: str = Field(pattern=_HEX64_PATTERN)

    _nonblank_fields = field_validator("agent_id", "provider_id", "model_id")(
        _nonblank
    )

    def identity_payload(self) -> Dict[str, str]:
        return self.model_dump(mode="json")


class CanonicalSideLedgerKind(str, Enum):
    APORIA = "aporia"
    COMMITMENT = "commitment"
    SOCRATIC_AUDIT = "socratic_audit"
    PHASE_DISPATCH = "phase_dispatch"
    REGISTRY_RETRY = "registry_retry"
    CYCLE = "cycle"


class SideLedgerDigest(_FrozenContract):
    """Digest of one detached CED side ledger relevant to the opening transition."""

    name: CanonicalSideLedgerKind
    semantic_digest: str = Field(pattern=_HEX64_PATTERN)

    def identity_payload(self) -> Dict[str, str]:
        return {"name": self.name.value, "semantic_digest": self.semantic_digest}


class CanonicalBranchCapsule(_FrozenContract):
    """Detached, immutable serialization of one canonical branch state.

    ``source_snapshot_json`` is exact canonical JSON and is retained for lossless
    rehydration.  Its byte digest is an integrity fingerprint, not semantic
    identity: random task IDs and timestamps in the exact snapshot must not fork
    the semantic capsule identity.
    """

    schema_version: Literal[
        CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION
    ] = CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION
    env_id: Literal[CANONICAL_SUCCESSOR_ENV_ID] = CANONICAL_SUCCESSOR_ENV_ID
    capsule_id: Optional[str] = None
    branch_id: Optional[str] = None
    source_execution_id: Optional[str] = None

    session_id: str
    search_state_v1_id: str
    projection_version: Literal[
        SEARCH_STATE_V1_PROJECTION_VERSION
    ] = SEARCH_STATE_V1_PROJECTION_VERSION
    source_snapshot_json: str
    source_snapshot_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )
    normalized_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    configuration_digest: str = Field(pattern=_HEX64_PATTERN)
    canonical_task: CanonicalTaskIdentity
    provider_bindings: Tuple[ProviderBindingIdentity, ...]
    side_ledgers: Tuple[SideLedgerDigest, ...] = ()
    budget: SearchBudget
    budget_usage: BudgetUsage

    # Root capsules omit all lineage. Successor capsules supply all lineage.
    parent_branch_id: Optional[str] = None
    produced_by_transition_id: Optional[str] = None
    produced_by_observation_id: Optional[str] = None

    _nonblank_fields = field_validator("session_id", "search_state_v1_id")(
        _nonblank
    )
    _optional_nonblank_fields = field_validator(
        "parent_branch_id",
        "produced_by_transition_id",
        "produced_by_observation_id",
    )(_optional_nonblank)

    @model_validator(mode="after")
    def validate_integrity_and_identify(self) -> "CanonicalBranchCapsule":
        try:
            snapshot = json.loads(self.source_snapshot_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError(
                "source_snapshot_json must contain valid canonical JSON"
            ) from exc
        if not isinstance(snapshot, dict):
            raise ContractValidationError(
                "source_snapshot_json must contain a JSON object"
            )
        try:
            normalized_snapshot = canonical_json(snapshot)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "source_snapshot_json must contain finite canonical JSON values"
            ) from exc
        if normalized_snapshot != self.source_snapshot_json:
            raise ContractValidationError(
                "source_snapshot_json must use the canonical JSON encoding"
            )
        expected_snapshot_digest = _raw_text_digest(self.source_snapshot_json)
        if (
            self.source_snapshot_digest is not None
            and self.source_snapshot_digest != expected_snapshot_digest
        ):
            raise ContractValidationError(
                "source_snapshot_digest does not match source_snapshot_json"
            )
        object.__setattr__(self, "source_snapshot_digest", expected_snapshot_digest)

        bindings = tuple(sorted(self.provider_bindings, key=lambda item: item.agent_id))
        if not bindings:
            raise ContractValidationError("provider_bindings must not be empty")
        if len({item.agent_id for item in bindings}) != len(bindings):
            raise ContractValidationError("provider binding agent IDs must be unique")
        object.__setattr__(self, "provider_bindings", bindings)

        active_bindings = [
            item for item in bindings if item.agent_id == self.canonical_task.agent_id
        ]
        if not active_bindings:
            raise ContractValidationError(
                "canonical task agent must have an exact provider binding"
            )
        if (
            active_bindings[0].model_config_digest
            != self.canonical_task.model_config_digest
        ):
            raise ContractValidationError(
                "canonical task and provider binding model configuration differ"
            )

        ledgers = tuple(sorted(self.side_ledgers, key=lambda item: item.name.value))
        if len({item.name for item in ledgers}) != len(ledgers):
            raise ContractValidationError("side ledger kinds must be unique")
        object.__setattr__(self, "side_ledgers", ledgers)

        self.budget.enforce(self.budget_usage)

        lineage = (
            self.parent_branch_id,
            self.produced_by_transition_id,
            self.produced_by_observation_id,
        )
        if any(value is not None for value in lineage) and not all(
            value is not None for value in lineage
        ):
            raise ContractValidationError(
                "successor capsule lineage must be supplied as one complete tuple"
            )

        expected_execution_id = stable_contract_id(
            "cedexecution", self.source_execution_identity_payload()
        )
        if (
            self.source_execution_id is not None
            and self.source_execution_id != expected_execution_id
        ):
            raise ContractValidationError(
                "source_execution_id does not match canonical source semantics"
            )
        object.__setattr__(self, "source_execution_id", expected_execution_id)

        expected_capsule_id = stable_contract_id("cedcapsule", self.identity_payload())
        if self.capsule_id is not None and self.capsule_id != expected_capsule_id:
            raise ContractValidationError(
                "capsule_id does not match canonical capsule semantics"
            )
        object.__setattr__(self, "capsule_id", expected_capsule_id)

        expected_branch_id = stable_contract_id(
            "cedbranch",
            {
                "env_id": self.env_id,
                "capsule_id": expected_capsule_id,
                "parent_branch_id": self.parent_branch_id,
                "transition_id": self.produced_by_transition_id,
                "observation_id": self.produced_by_observation_id,
                "origin": "root" if self.parent_branch_id is None else "successor",
            },
        )
        if self.branch_id is not None and self.branch_id != expected_branch_id:
            raise ContractValidationError(
                "branch_id does not match capsule lineage"
            )
        object.__setattr__(self, "branch_id", expected_branch_id)
        return self

    def source_execution_identity_payload(self) -> Dict[str, object]:
        return {
            "env_id": self.env_id,
            "session_id": self.session_id,
            "search_state_v1_id": self.search_state_v1_id,
            "projection_version": self.projection_version,
            "normalized_semantic_digest": self.normalized_semantic_digest,
            "configuration_digest": self.configuration_digest,
            "canonical_task": self.canonical_task.identity_payload(),
            "provider_bindings": [
                item.identity_payload() for item in self.provider_bindings
            ],
            "side_ledgers": [item.identity_payload() for item in self.side_ledgers],
            "budget": self.budget.model_dump(mode="json"),
            "budget_usage": self.budget_usage.model_dump(mode="json"),
        }

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "env_id": self.env_id,
            "source_execution_id": self.source_execution_id,
            "projection_version": self.projection_version,
        }


class NewExecutionUsage(_FrozenContract):
    """Work charged by this replay, never the historical acquisition usage."""

    budget_delta: BudgetUsage = Field(
        default_factory=lambda: BudgetUsage(
            nodes=1,
            expansions=1,
            max_depth_observed=1,
        )
    )
    observation_applications: int = Field(default=1, ge=0, strict=True)
    successor_evaluations: int = Field(default=1, ge=0, strict=True)

    @model_validator(mode="after")
    def validate_v0_profile(self) -> "NewExecutionUsage":
        zero = BudgetUsage()
        applied = BudgetUsage(nodes=1, expansions=1, max_depth_observed=1)
        profile = (
            self.budget_delta,
            self.observation_applications,
            self.successor_evaluations,
        )
        if profile not in ((zero, 0, 0), (applied, 1, 1)):
            raise ContractValidationError(
                "new execution usage must be either the zero pre-application "
                "profile or exactly one offline successor evaluation"
            )
        return self

    @classmethod
    def not_applied(cls) -> "NewExecutionUsage":
        return cls(
            budget_delta=BudgetUsage(),
            observation_applications=0,
            successor_evaluations=0,
        )

    @property
    def applied(self) -> bool:
        return self.observation_applications == 1

    def identity_payload(self) -> Dict[str, object]:
        return {
            "budget_delta": self.budget_delta.model_dump(mode="json"),
            "observation_applications": self.observation_applications,
            "successor_evaluations": self.successor_evaluations,
        }


class PendingCanonicalTransition(_FrozenContract):
    """Validated reservation for one legal action; it applies no observation."""

    schema_version: Literal[
        PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION
    ] = PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION
    env_id: Literal[CANONICAL_SUCCESSOR_ENV_ID] = CANONICAL_SUCCESSOR_ENV_ID
    supported_action_family: Literal[SUPPORTED_ACTION_FAMILY] = SUPPORTED_ACTION_FAMILY
    transition_id: Optional[str] = None
    replay_task_id: Optional[str] = None

    source_capsule_id: str
    source_branch_id: str
    root_state_v1_id: str
    selected_action: LegalAction
    complete_legal_action_ids: Tuple[str, ...]
    canonical_task: CanonicalTaskIdentity
    expected_provider_id: str
    expected_model_id: str
    budget: SearchBudget
    budget_before: BudgetUsage
    reserved_usage: NewExecutionUsage = Field(default_factory=NewExecutionUsage)
    canonical_processor_ids: Tuple[str, ...]

    _nonblank_fields = field_validator(
        "source_capsule_id",
        "source_branch_id",
        "root_state_v1_id",
        "expected_provider_id",
        "expected_model_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_reservation_and_identify(self) -> "PendingCanonicalTransition":
        legal_ids = _canonical_tuple(
            self.complete_legal_action_ids, "complete_legal_action_ids"
        )
        if not legal_ids:
            raise ContractValidationError("complete legal action set must not be empty")
        object.__setattr__(self, "complete_legal_action_ids", legal_ids)
        if self.selected_action.action_id not in legal_ids:
            raise ContractValidationError(
                "selected action is absent from the complete hard-legal set"
            )

        action = self.selected_action
        if (
            action.kind is not ActionKind.ASK_SOCRATIC_QUESTION
            or action.target_kind is not None
            or action.target_id is not None
            or action.parameters
            or action.required_capabilities
        ):
            raise ContractValidationError(
                "Phase 8 supports only the targetless canonical opening "
                "ASK_SOCRATIC_QUESTION action"
            )
        task = self.canonical_task
        if (
            task.phase is not DialogPhase.OPENING
            or task.role is not AgentRole.SOCRATES
            or task.task_kind is not TaskKind.SOCRATIC_QUESTION
            or task.round_number != 0
            or task.slot_index != 0
            or task.attempt_index != 0
        ):
            raise ContractValidationError(
                "Phase 8 supports only opening/Socrates/Socratic-question "
                "round=0/slot=0/attempt=0"
            )
        if not self.reserved_usage.applied:
            raise ContractValidationError(
                "a pending transition must reserve one successor evaluation"
            )

        processors = _canonical_tuple(
            self.canonical_processor_ids, "canonical_processor_ids"
        )
        if not processors:
            raise ContractValidationError("canonical_processor_ids must not be empty")
        object.__setattr__(self, "canonical_processor_ids", processors)

        self.budget.enforce(
            self.budget_before.plus(self.reserved_usage.budget_delta)
        )

        expected_replay_task_id = stable_contract_id(
            "cedreplaytask",
            {
                "source_capsule_id": self.source_capsule_id,
                "canonical_task": task.identity_payload(),
            },
        )
        if (
            self.replay_task_id is not None
            and self.replay_task_id != expected_replay_task_id
        ):
            raise ContractValidationError(
                "replay_task_id does not match normalized canonical task"
            )
        object.__setattr__(self, "replay_task_id", expected_replay_task_id)

        expected_transition_id = stable_contract_id(
            "cedpending", self.identity_payload()
        )
        if (
            self.transition_id is not None
            and self.transition_id != expected_transition_id
        ):
            raise ContractValidationError(
                "transition_id does not match pending transition semantics"
            )
        object.__setattr__(self, "transition_id", expected_transition_id)
        return self

    @property
    def pending_id(self) -> str:
        """Compatibility name for the semantic pending-transition identity."""
        assert self.transition_id is not None
        return self.transition_id

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "env_id": self.env_id,
            "supported_action_family": self.supported_action_family,
            "source_capsule_id": self.source_capsule_id,
            "source_branch_id": self.source_branch_id,
            "root_state_v1_id": self.root_state_v1_id,
            "action_id": self.selected_action.action_id,
            "complete_legal_action_ids": list(self.complete_legal_action_ids),
            "canonical_task": self.canonical_task.identity_payload(),
            "expected_provider_id": self.expected_provider_id,
            "expected_model_id": self.expected_model_id,
            "budget": self.budget.model_dump(mode="json"),
            "budget_before": self.budget_before.model_dump(mode="json"),
            "reserved_usage": self.reserved_usage.identity_payload(),
            "canonical_processor_ids": list(self.canonical_processor_ids),
            "replay_task_id": self.replay_task_id,
        }


class ObservationTransportStatus(str, Enum):
    DELIVERED = "delivered"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"


class ObservationCaptureKind(str, Enum):
    CANONICAL_RECORDED_TRANSITION = "canonical_recorded_transition"
    OFFLINE_FIXTURE = "offline_fixture"
    SYNTHETIC_MALFORMED_TEST = "synthetic_malformed_test"


class HistoricalUsageKnowledge(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class RecordedHistoricalUsage(_FrozenContract):
    """Usage of the past acquisition; ``None`` means unknown, never zero."""

    knowledge: HistoricalUsageKnowledge
    model_calls: Optional[int] = Field(default=None, ge=0, strict=True)
    tool_calls: Optional[int] = Field(default=None, ge=0, strict=True)
    tokens: Optional[int] = Field(default=None, ge=0, strict=True)
    cost_microusd: Optional[int] = Field(default=None, ge=0, strict=True)
    wall_time_ms: Optional[int] = Field(default=None, ge=0, strict=True)
    observation_acquisitions: int = Field(default=1, ge=1, strict=True)

    _MEASURE_FIELDS: ClassVar[Tuple[str, ...]] = (
        "model_calls",
        "tool_calls",
        "tokens",
        "cost_microusd",
        "wall_time_ms",
    )

    @model_validator(mode="after")
    def validate_knowledge(self) -> "RecordedHistoricalUsage":
        known = tuple(getattr(self, name) is not None for name in self._MEASURE_FIELDS)
        if self.knowledge is HistoricalUsageKnowledge.COMPLETE and not all(known):
            raise ContractValidationError(
                "complete historical usage requires every measured value"
            )
        if self.knowledge is HistoricalUsageKnowledge.UNAVAILABLE and any(known):
            raise ContractValidationError(
                "unavailable historical usage must keep every measured value unknown"
            )
        if self.knowledge is HistoricalUsageKnowledge.PARTIAL and (
            not any(known) or all(known)
        ):
            raise ContractValidationError(
                "partial historical usage requires both known and unknown values"
            )
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json")


class RecordedObservationProvenance(_FrozenContract):
    """Immutable corpus provenance, independent of a local file path."""

    capture_kind: ObservationCaptureKind
    source_artifact_id: str
    source_artifact_digest: str = Field(pattern=_HEX64_PATTERN)
    source_revision: str
    provenance_digest: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)

    _nonblank_fields = field_validator("source_artifact_id", "source_revision")(
        _nonblank
    )

    @model_validator(mode="after")
    def identify(self) -> "RecordedObservationProvenance":
        expected = _semantic_digest(self.semantic_payload())
        if self.provenance_digest is not None and self.provenance_digest != expected:
            raise ContractValidationError(
                "provenance_digest does not match recorded provenance"
            )
        object.__setattr__(self, "provenance_digest", expected)
        return self

    def semantic_payload(self) -> Dict[str, str]:
        return {
            "capture_kind": self.capture_kind.value,
            "source_artifact_id": self.source_artifact_id,
            "source_artifact_digest": self.source_artifact_digest,
            "source_revision": self.source_revision,
        }

    def identity_payload(self) -> Dict[str, str]:
        return {**self.semantic_payload(), "provenance_digest": self.provenance_digest or ""}


FORBIDDEN_RECORDED_OBSERVATION_FIELDS = frozenset(
    {
        "accepted",
        "benchmark_label",
        "expected_acceptance",
        "expected_result",
        "expected_status",
        "final_response",
        "final_release",
        "future_state",
        "future_reward",
        "governing_outcome",
        "later_task_log",
        "later_governing_outcome",
        "metadata",
        "parsed_move",
        "resulting_move_id",
        "reward",
        "successor",
        "successor_state",
        "verification_result",
    }
)


class FutureLabelForbiddenError(ContractValidationError):
    """A recorded observation envelope contains future/control information."""


class RecordedCanonicalObservation(_FrozenContract):
    """Raw, replayable observation with no parsed or future-derived labels."""

    schema_version: Literal[
        RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
    ] = RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION
    observation_id: Optional[str] = None

    # Audit-only capture identifiers, excluded from semantic observation identity.
    capture_id: Optional[str] = None
    source_task_id: Optional[str] = None
    recorded_response_id: Optional[str] = None
    recorded_request_digest: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )

    action_id: str
    phase: DialogPhase
    round_number: int = Field(ge=0, strict=True)
    slot_index: int = Field(ge=0, strict=True)
    attempt_index: int = Field(ge=0, strict=True)
    agent_id: str
    role: AgentRole
    task_kind: TaskKind
    task_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    request_semantic_digest: str = Field(pattern=_HEX64_PATTERN)

    provider_id: str
    configured_model_id: str
    actual_model_id: Optional[str] = None
    model_config_digest: str = Field(pattern=_HEX64_PATTERN)

    transport_status: ObservationTransportStatus
    transport_error_code: Optional[str] = None
    raw_text: Optional[str] = None
    raw_output_digest: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)

    historical_usage: RecordedHistoricalUsage
    provenance: RecordedObservationProvenance
    privacy_classification: Literal[
        OFFLINE_FIXTURE_PRIVACY_CLASSIFICATION
    ] = OFFLINE_FIXTURE_PRIVACY_CLASSIFICATION

    _nonblank_fields = field_validator(
        "action_id",
        "agent_id",
        "provider_id",
        "configured_model_id",
    )(_nonblank)
    _optional_nonblank_fields = field_validator(
        "capture_id",
        "source_task_id",
        "recorded_response_id",
        "actual_model_id",
        "transport_error_code",
    )(_optional_nonblank)

    @model_validator(mode="before")
    @classmethod
    def reject_future_labels(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            forbidden = sorted(FORBIDDEN_RECORDED_OBSERVATION_FIELDS & set(data))
            if forbidden:
                raise FutureLabelForbiddenError(
                    "recorded observation contains forbidden future/control fields: "
                    + ", ".join(forbidden)
                )
        return data

    @model_validator(mode="after")
    def validate_transport_and_identify(self) -> "RecordedCanonicalObservation":
        if self.transport_status is ObservationTransportStatus.DELIVERED:
            if self.raw_text is None:
                raise ContractValidationError(
                    "a delivered observation requires exact raw_text"
                )
            if self.actual_model_id is None:
                raise ContractValidationError(
                    "a delivered observation requires exact actual_model_id"
                )
            if self.transport_error_code is not None:
                raise ContractValidationError(
                    "a delivered observation cannot contain a transport error code"
                )
            expected_raw_digest = _raw_text_digest(self.raw_text)
        else:
            if self.raw_text is not None:
                raise ContractValidationError(
                    "a non-delivered observation cannot contain raw_text"
                )
            if self.transport_error_code is None:
                raise ContractValidationError(
                    "a non-delivered observation requires a transport error code"
                )
            expected_raw_digest = _semantic_digest(
                {
                    "transport_status": self.transport_status.value,
                    "transport_error_code": self.transport_error_code,
                }
            )
        if (
            self.raw_output_digest is not None
            and self.raw_output_digest != expected_raw_digest
        ):
            raise ContractValidationError(
                "raw_output_digest does not match the recorded raw observation"
            )
        object.__setattr__(self, "raw_output_digest", expected_raw_digest)

        expected_observation_id = stable_contract_id(
            "cedobservation", self.identity_payload()
        )
        if (
            self.observation_id is not None
            and self.observation_id != expected_observation_id
        ):
            raise ContractValidationError(
                "observation_id does not match recorded observation semantics"
            )
        object.__setattr__(self, "observation_id", expected_observation_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "action_id": self.action_id,
            "phase": self.phase.value,
            "round_number": self.round_number,
            "slot_index": self.slot_index,
            "attempt_index": self.attempt_index,
            "agent_id": self.agent_id,
            "role": self.role.value,
            "task_kind": self.task_kind.value,
            "task_semantic_digest": self.task_semantic_digest,
            "request_semantic_digest": self.request_semantic_digest,
            "provider_id": self.provider_id,
            "configured_model_id": self.configured_model_id,
            "actual_model_id": self.actual_model_id,
            "model_config_digest": self.model_config_digest,
            "transport_status": self.transport_status.value,
            "transport_error_code": self.transport_error_code,
            "raw_output_digest": self.raw_output_digest,
            "historical_usage": self.historical_usage.identity_payload(),
            "provenance": self.provenance.identity_payload(),
            "privacy_classification": self.privacy_classification,
        }


class CanonicalTransitionStatus(str, Enum):
    APPLIED_ACCEPTED = "applied_accepted"
    APPLIED_CANONICAL_REJECTION = "applied_canonical_rejection"
    SUCCESSOR_UNAVAILABLE = "successor_unavailable"


class CanonicalRejectionReason(str, Enum):
    TRANSPORT_REJECTED = "transport_rejected"
    PARSER_REJECTED = "parser_rejected"
    SCHEMA_REJECTED = "schema_rejected"
    SOCRATIC_CONTENT_REJECTED = "socratic_content_rejected"
    ANSWER_INJECTION_REJECTED = "answer_injection_rejected"


class SuccessorUnavailableReason(str, Enum):
    INVALID_ROOT = "invalid_root"
    ILLEGAL_ACTION = "illegal_action"
    UNSUPPORTED_ACTION_FAMILY = "unsupported_action_family"
    MISSING_OBSERVATION = "missing_observation"
    OBSERVATION_TASK_MISMATCH = "observation_task_mismatch"
    OBSERVATION_PROVIDER_MISMATCH = "observation_provider_mismatch"
    INVALID_OBSERVATION_IDENTITY = "invalid_observation_identity"
    FUTURE_LABEL_FORBIDDEN = "future_label_forbidden"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANONICAL_PROCESSING_REJECTED = "canonical_processing_rejected"


class LegalActionValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class RecordedObservationCompatibilityError(ContractValidationError):
    """A valid observation contract is incompatible with this pending task."""

    def __init__(self, reason: SuccessorUnavailableReason, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}")


def validate_recorded_observation_compatibility(
    pending: PendingCanonicalTransition,
    observation: RecordedCanonicalObservation,
) -> None:
    """Fail closed unless a recorded observation belongs to ``pending``.

    Audit-only source task/capture/response IDs are intentionally not compared.
    They cannot create or destroy semantic compatibility.
    """

    task = pending.canonical_task
    task_values = {
        "phase": (observation.phase, task.phase),
        "round_number": (observation.round_number, task.round_number),
        "slot_index": (observation.slot_index, task.slot_index),
        "attempt_index": (observation.attempt_index, task.attempt_index),
        "agent_id": (observation.agent_id, task.agent_id),
        "role": (observation.role, task.role),
        "task_kind": (observation.task_kind, task.task_kind),
        "task_semantic_digest": (
            observation.task_semantic_digest,
            task.task_semantic_digest,
        ),
        "request_semantic_digest": (
            observation.request_semantic_digest,
            task.request_semantic_digest,
        ),
    }
    mismatches = [name for name, (actual, expected) in task_values.items() if actual != expected]
    if observation.action_id != pending.selected_action.action_id:
        mismatches.append("action_id")
    if mismatches:
        raise RecordedObservationCompatibilityError(
            SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
            "incompatible " + ", ".join(sorted(mismatches)),
        )

    provider_mismatches = []
    if observation.provider_id != pending.expected_provider_id:
        provider_mismatches.append("provider_id")
    if observation.configured_model_id != pending.expected_model_id:
        provider_mismatches.append("configured_model_id")
    if (
        observation.actual_model_id is not None
        and observation.actual_model_id != pending.expected_model_id
    ):
        provider_mismatches.append("actual_model_id")
    if observation.model_config_digest != task.model_config_digest:
        provider_mismatches.append("model_config_digest")
    if provider_mismatches:
        raise RecordedObservationCompatibilityError(
            SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH,
            "incompatible " + ", ".join(sorted(provider_mismatches)),
        )


class CanonicalTransitionReceipt(_FrozenContract):
    """Deterministic public receipt for one attempted canonical transition.

    ``source_state_hash`` and ``successor_state_hash`` are hashes of the
    predeclared normalized semantic snapshots.  Exact structural snapshots stay
    in their capsules under ``source_snapshot_digest`` because canonical CED
    timestamps and provisional rejected-move IDs are already non-semantic and
    may differ across isolated replays.
    """

    schema_version: Literal[
        CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION
    ] = CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION
    env_id: Literal[CANONICAL_SUCCESSOR_ENV_ID] = CANONICAL_SUCCESSOR_ENV_ID
    receipt_id: Optional[str] = None
    receipt_hash: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)

    transition_id: str
    root_capsule_id: str
    root_branch_id: str
    root_state_v1_id: str
    branch_id: Optional[str] = None
    action_id: str
    supported_action_family: Literal[SUPPORTED_ACTION_FAMILY] = SUPPORTED_ACTION_FAMILY
    observation_id: Optional[str] = None
    observation_digest: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)

    status: CanonicalTransitionStatus
    legal_action_validation: LegalActionValidationStatus
    canonical_rejection_reason: Optional[CanonicalRejectionReason] = None
    unavailable_reason: Optional[SuccessorUnavailableReason] = None
    resulting_move_id: Optional[str] = None

    source_state_hash: str = Field(pattern=_HEX64_PATTERN)
    successor_state_hash: Optional[str] = Field(default=None, pattern=_HEX64_PATTERN)
    successor_state_v1_id: Optional[str] = None
    canonical_processor_ids: Tuple[str, ...]

    budget: SearchBudget
    budget_before: BudgetUsage
    new_execution_usage: NewExecutionUsage
    budget_after: BudgetUsage
    recorded_historical_usage: Optional[RecordedHistoricalUsage] = None

    source_unchanged: Literal[True] = True
    sibling_branches_unchanged: Literal[True] = True
    production_unchanged: Literal[True] = True

    _nonblank_fields = field_validator(
        "transition_id",
        "root_capsule_id",
        "root_branch_id",
        "root_state_v1_id",
        "action_id",
    )(_nonblank)
    _optional_nonblank_fields = field_validator(
        "branch_id", "observation_id", "resulting_move_id", "successor_state_v1_id"
    )(_optional_nonblank)

    @model_validator(mode="after")
    def validate_links_resources_and_identify(self) -> "CanonicalTransitionReceipt":
        processors = _canonical_tuple(
            self.canonical_processor_ids, "canonical_processor_ids"
        )
        if not processors:
            raise ContractValidationError("canonical_processor_ids must not be empty")
        object.__setattr__(self, "canonical_processor_ids", processors)

        expected_after = self.budget_before.plus(
            self.new_execution_usage.budget_delta
        )
        if self.budget_after != expected_after:
            raise ContractValidationError(
                "budget_after does not equal budget_before plus new execution usage"
            )
        self.budget.enforce(self.budget_after)

        observation_present = self.observation_id is not None
        if observation_present != (self.observation_digest is not None):
            raise ContractValidationError(
                "observation_id and observation_digest must both be present or absent"
            )
        if observation_present != (self.recorded_historical_usage is not None):
            raise ContractValidationError(
                "recorded historical usage must be present exactly when an observation is"
            )

        applied = self.status in (
            CanonicalTransitionStatus.APPLIED_ACCEPTED,
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        )
        successor_values = (
            self.branch_id,
            self.successor_state_hash,
            self.successor_state_v1_id,
        )
        if applied:
            if self.legal_action_validation is not LegalActionValidationStatus.PASSED:
                raise ContractValidationError(
                    "an applied transition requires passed hard-legal validation"
                )
            if not observation_present:
                raise ContractValidationError(
                    "an applied transition requires a compatible recorded observation"
                )
            if not self.new_execution_usage.applied:
                raise ContractValidationError(
                    "an applied transition must charge one successor evaluation"
                )
            if not all(value is not None for value in successor_values):
                raise ContractValidationError(
                    "an applied transition requires a complete successor identity"
                )
            if self.unavailable_reason is not None:
                raise ContractValidationError(
                    "an applied transition cannot have an unavailable reason"
                )
        else:
            if any(value is not None for value in successor_values):
                raise ContractValidationError(
                    "successor-unavailable cannot create a branch or successor state"
                )
            if self.unavailable_reason is None:
                raise ContractValidationError(
                    "successor-unavailable requires a frozen failure reason"
                )

        if self.status is CanonicalTransitionStatus.APPLIED_ACCEPTED:
            if self.resulting_move_id is None:
                raise ContractValidationError(
                    "an accepted transition requires the exact CED move_id"
                )
            if self.canonical_rejection_reason is not None:
                raise ContractValidationError(
                    "an accepted transition cannot have a rejection reason"
                )
        elif self.status is CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION:
            if self.resulting_move_id is not None:
                raise ContractValidationError(
                    "a canonical rejection cannot contain an accepted move_id"
                )
            if self.canonical_rejection_reason is None:
                raise ContractValidationError(
                    "a canonical rejection requires its canonical rejection reason"
                )
        else:
            if self.resulting_move_id is not None:
                raise ContractValidationError(
                    "successor-unavailable cannot contain a move_id"
                )
            if self.canonical_rejection_reason is not None:
                raise ContractValidationError(
                    "successor-unavailable is distinct from canonical rejection"
                )

        if self.unavailable_reason is SuccessorUnavailableReason.ILLEGAL_ACTION:
            if self.legal_action_validation is not LegalActionValidationStatus.FAILED:
                raise ContractValidationError(
                    "illegal-action unavailability requires failed legal validation"
                )
        if self.unavailable_reason is SuccessorUnavailableReason.BUDGET_EXHAUSTED:
            if self.new_execution_usage.applied:
                raise ContractValidationError(
                    "budget exhaustion must fail before observation application"
                )
            one_transition = BudgetUsage(
                nodes=1, expansions=1, max_depth_observed=1
            )
            if self.budget.allows(self.budget_before.plus(one_transition)):
                raise ContractValidationError(
                    "budget-exhausted receipt still has capacity for one transition"
                )

        payload = self.identity_payload()
        expected_hash = _semantic_digest(payload)
        expected_id = f"cedreceipt_{expected_hash}"
        if self.receipt_hash is not None and self.receipt_hash != expected_hash:
            raise ContractValidationError("receipt_hash does not match receipt content")
        if self.receipt_id is not None and self.receipt_id != expected_id:
            raise ContractValidationError("receipt_id does not match receipt content")
        object.__setattr__(self, "receipt_hash", expected_hash)
        object.__setattr__(self, "receipt_id", expected_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "env_id": self.env_id,
            "transition_id": self.transition_id,
            "root_capsule_id": self.root_capsule_id,
            "root_branch_id": self.root_branch_id,
            "root_state_v1_id": self.root_state_v1_id,
            "branch_id": self.branch_id,
            "action_id": self.action_id,
            "supported_action_family": self.supported_action_family,
            "observation_id": self.observation_id,
            "observation_digest": self.observation_digest,
            "status": self.status.value,
            "legal_action_validation": self.legal_action_validation.value,
            "canonical_rejection_reason": (
                self.canonical_rejection_reason.value
                if self.canonical_rejection_reason is not None
                else None
            ),
            "unavailable_reason": (
                self.unavailable_reason.value
                if self.unavailable_reason is not None
                else None
            ),
            "resulting_move_id": self.resulting_move_id,
            "source_state_hash": self.source_state_hash,
            "successor_state_hash": self.successor_state_hash,
            "successor_state_v1_id": self.successor_state_v1_id,
            "canonical_processor_ids": list(self.canonical_processor_ids),
            "budget": self.budget.model_dump(mode="json"),
            "budget_before": self.budget_before.model_dump(mode="json"),
            "new_execution_usage": self.new_execution_usage.identity_payload(),
            "budget_after": self.budget_after.model_dump(mode="json"),
            "recorded_historical_usage": (
                self.recorded_historical_usage.identity_payload()
                if self.recorded_historical_usage is not None
                else None
            ),
            "source_unchanged": self.source_unchanged,
            "sibling_branches_unchanged": self.sibling_branches_unchanged,
            "production_unchanged": self.production_unchanged,
        }


class CanonicalTransitionResult(_FrozenContract):
    """Linked result envelope; only applied outcomes contain a successor."""

    schema_version: Literal[
        CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION
    ] = CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION
    env_id: Literal[CANONICAL_SUCCESSOR_ENV_ID] = CANONICAL_SUCCESSOR_ENV_ID
    result_id: Optional[str] = None
    transition_id: str
    status: CanonicalTransitionStatus
    receipt: CanonicalTransitionReceipt
    successor_capsule: Optional[CanonicalBranchCapsule] = None
    successor_search_state_v1: Optional[SearchStateV1] = None

    _transition_id_nonblank = field_validator("transition_id")(_nonblank)

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "CanonicalTransitionResult":
        if self.receipt.transition_id != self.transition_id:
            raise ContractValidationError(
                "result and receipt transition identities differ"
            )
        if self.receipt.status is not self.status:
            raise ContractValidationError("result and receipt statuses differ")

        applied = self.status in (
            CanonicalTransitionStatus.APPLIED_ACCEPTED,
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        )
        if applied:
            if self.successor_capsule is None or self.successor_search_state_v1 is None:
                raise ContractValidationError(
                    "an applied result requires its successor capsule and SearchState-v1"
                )
            capsule = self.successor_capsule
            state = self.successor_search_state_v1
            if capsule.branch_id != self.receipt.branch_id:
                raise ContractValidationError(
                    "successor capsule and receipt branch identities differ"
                )
            if capsule.search_state_v1_id != state.state_id:
                raise ContractValidationError(
                    "successor capsule and projected SearchState-v1 identities differ"
                )
            if capsule.normalized_semantic_digest \
                    != self.receipt.successor_state_hash:
                raise ContractValidationError(
                    "successor capsule and receipt semantic-state hashes differ"
                )
            if state.state_id != self.receipt.successor_state_v1_id:
                raise ContractValidationError(
                    "result and receipt successor SearchState-v1 identities differ"
                )
            if capsule.parent_branch_id != self.receipt.root_branch_id:
                raise ContractValidationError(
                    "successor capsule does not descend from the receipt root branch"
                )
            if capsule.produced_by_transition_id != self.transition_id:
                raise ContractValidationError(
                    "successor capsule has incompatible transition lineage"
                )
            if capsule.produced_by_observation_id != self.receipt.observation_id:
                raise ContractValidationError(
                    "successor capsule has incompatible observation lineage"
                )
        elif self.successor_capsule is not None or self.successor_search_state_v1 is not None:
            raise ContractValidationError(
                "successor-unavailable result cannot contain a successor"
            )

        expected_result_id = stable_contract_id("cedresult", self.identity_payload())
        if self.result_id is not None and self.result_id != expected_result_id:
            raise ContractValidationError("result_id does not match result content")
        object.__setattr__(self, "result_id", expected_result_id)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "env_id": self.env_id,
            "transition_id": self.transition_id,
            "status": self.status.value,
            "receipt_id": self.receipt.receipt_id,
            "successor_capsule_id": (
                self.successor_capsule.capsule_id
                if self.successor_capsule is not None
                else None
            ),
            "successor_branch_id": (
                self.successor_capsule.branch_id
                if self.successor_capsule is not None
                else None
            ),
            "successor_state_v1_id": (
                self.successor_search_state_v1.state_id
                if self.successor_search_state_v1 is not None
                else None
            ),
        }


# Concise public aliases used by the architecture prose.
PendingTransition = PendingCanonicalTransition
RecordedObservation = RecordedCanonicalObservation
Result = CanonicalTransitionResult
Receipt = CanonicalTransitionReceipt


__all__ = [
    "CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_ENV_ID",
    "CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION",
    "CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION",
    "FORBIDDEN_RECORDED_OBSERVATION_FIELDS",
    "OFFLINE_FIXTURE_PRIVACY_CLASSIFICATION",
    "PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION",
    "RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION",
    "SUPPORTED_ACTION_FAMILY",
    "CanonicalBranchCapsule",
    "CanonicalRejectionReason",
    "CanonicalSideLedgerKind",
    "CanonicalTaskIdentity",
    "CanonicalTransitionReceipt",
    "CanonicalTransitionResult",
    "CanonicalTransitionStatus",
    "FutureLabelForbiddenError",
    "HistoricalUsageKnowledge",
    "LegalActionValidationStatus",
    "NewExecutionUsage",
    "ObservationCaptureKind",
    "ObservationTransportStatus",
    "PendingCanonicalTransition",
    "PendingTransition",
    "ProviderBindingIdentity",
    "Receipt",
    "RecordedCanonicalObservation",
    "RecordedHistoricalUsage",
    "RecordedObservation",
    "RecordedObservationCompatibilityError",
    "RecordedObservationProvenance",
    "Result",
    "SideLedgerDigest",
    "SuccessorUnavailableReason",
    "validate_recorded_observation_compatibility",
]

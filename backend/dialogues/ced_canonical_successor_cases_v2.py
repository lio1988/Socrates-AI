"""Frozen Phase 8R canonical-successor validation and probe contracts.

This module is deliberately data-only.  Importing it constructs immutable
Pydantic contracts; it does not dispatch a provider, build an aggregate, or
exercise the successor runtime.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ced_canonical_successor_cases_v1 import (
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
    frozen_corpus_v1_canonical_sha256,
)
from .ced_canonical_successor_contracts import SuccessorUnavailableReason
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


FAILURE_TAXONOMY_SCHEMA_V1 = "ced-canonical-transition-failure-taxonomy/v1"
FAILURE_PRECEDENCE_SCHEMA_V1 = "ced-canonical-transition-failure-precedence/v1"
PROBE_DESIGN_SCHEMA_V1 = "ced-canonical-successor-probe-design/v1"
COMPATIBILITY_DIAGNOSTICS_SCHEMA_V1 = (
    "ced-canonical-successor-compatibility-diagnostics/v1"
)
UNAVAILABLE_PROBE_SCHEMA_V2 = "ced-canonical-successor-unavailable-probe/v2"
CASE_SET_SCHEMA_V2 = "ced-canonical-successor-parity-case-set/v2"
PARITY_CORPUS_SCHEMA_V2 = "ced-canonical-successor-parity-corpus/v2"
VALIDATION_ORDER_SCHEMA_V1 = "ced-canonical-successor-validation-order/v1"

EXPECTED_V1_CORPUS_ID = (
    "cedobscorpus_"
    "b5ebe4b46d2b3ae4fed3faded341c8a2d8ff5f5f254531f000e479bf66b7f8b7"
)
EXPECTED_V1_CORPUS_SHA256 = (
    "06c5eda5ee8c71992cb8b7427794f6d5ab6e44b4f92f0d6f71f4366d5729427c"
)

ORTHOGONAL_PROBE_IDS: Tuple[str, ...] = (
    "p8v2-o01-invalid-root-registration",
    "p8v2-o02-illegal-action-capability",
    "p8v2-o03-missing-observation",
    "p8v2-o04-invalid-observation-schema",
    "p8v2-o05-tampered-raw-digest",
    "p8v2-o06-wrong-task-agent",
    "p8v2-o07-wrong-root-question",
    "p8v2-o08-wrong-exact-model",
    "p8v2-o09-wrong-runtime-timeout",
    "p8v2-o10-future-label",
    "p8v2-o11-budget-exhausted",
)

PRECEDENCE_PROBE_IDS: Tuple[str, ...] = (
    "p8v2-p01-unsupported-family-vs-legality",
    "p8v2-p02-provider-roster-context",
    "p8v2-p03-root-plus-provider",
    "p8v2-p04-task-plus-model",
    "p8v2-p05-context-plus-tampered-digest",
    "p8v2-p06-illegal-plus-incompatible-observation",
    "p8v2-p07-caller-rebinding-vs-manifest",
)


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProbeClass(str, Enum):
    ORTHOGONAL = "ORTHOGONAL"
    PRECEDENCE = "PRECEDENCE"


class ProbeStage(str, Enum):
    CAPTURE = "CAPTURE"
    PREPARE = "PREPARE"
    APPLY = "APPLY"


class InvariantState(str, Enum):
    PRESERVED = "PRESERVED"
    INTENTIONALLY_CHANGED = "INTENTIONALLY_CHANGED"
    DEPENDENTLY_CHANGED = "DEPENDENTLY_CHANGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GuardEvaluationState(str, Enum):
    EVALUATED_PASSED = "EVALUATED_PASSED"
    EVALUATED_FAILED = "EVALUATED_FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_CONSTRUCTED = "NOT_CONSTRUCTED"


class ObservationSubmissionState(str, Enum):
    SUBMITTED = "SUBMITTED"
    NOT_SUBMITTED = "NOT_SUBMITTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FailureLayer(str, Enum):
    PREPARATION = "PREPARATION"
    OBSERVATION_BINDING = "OBSERVATION_BINDING"
    CANONICAL_PROCESSING = "CANONICAL_PROCESSING"
    APPLIED = "APPLIED"


class FailurePrecedenceModel(str, Enum):
    FIRST_CANONICAL_GUARD_WINS = "FIRST_CANONICAL_GUARD_WINS"


class ProbeInvariantVector(FrozenContract):
    """Exactly fifteen required relation states.

    These are identity/digest relations, not a second failure taxonomy.  Narrow
    runtime-guard pass/fail/not-reached evidence is kept separately in
    ``GuardEvaluation``.  In particular, a full ``task_semantic_identity`` may
    change as a declared dependency while an earlier narrower compatibility
    field remains preserved and is reported by the guard evidence.
    """

    root_identity: InvariantState
    capsule_identity: InvariantState
    pending_identity: InvariantState
    task_semantic_identity: InvariantState
    public_context_digest: InvariantState
    council_roster_digest: InvariantState
    action_identity: InvariantState
    observation_manifest_identity: InvariantState
    observation_payload_digest: InvariantState
    provider_binding: InvariantState
    exact_model_binding: InvariantState
    configuration_binding: InvariantState
    lineage_binding: InvariantState
    future_label_status: InvariantState
    budget_status: InvariantState


INVARIANT_FIELD_NAMES: Tuple[str, ...] = tuple(
    ProbeInvariantVector.model_fields.keys()
)


class GuardEvaluation(FrozenContract):
    guard_id: str = Field(min_length=2)
    state: GuardEvaluationState


class CanonicalValidationStep(FrozenContract):
    order_index: int = Field(ge=1)
    guard_id: str = Field(pattern=r"^(?:C|P|A)(?:[1-9]|1[0-9]|2[0-2])(?:[ab])?$")
    stage: ProbeStage
    check: str = Field(min_length=3)
    owner: str = Field(min_length=3)
    inputs: Tuple[str, ...] = Field(min_length=1)
    failure_result: str = Field(min_length=3)
    short_circuit_guard_ids: Tuple[str, ...]
    independently_probeable: bool
    source_ref: str = Field(min_length=3)

    @field_validator("inputs", "short_circuit_guard_ids")
    @classmethod
    def _unique_tuple(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ContractValidationError("validation-step tuple entries must be unique")
        return value


EXPECTED_GUARD_IDS: Tuple[str, ...] = (
    *(f"C{index}" for index in range(1, 12)),
    *(f"P{index}" for index in range(1, 11)),
    *(f"A{index}" for index in range(1, 15)),
    "A15a",
    "A15b",
    *(f"A{index}" for index in range(16, 23)),
)


class CanonicalValidationOrder(FrozenContract):
    schema_version: Literal[VALIDATION_ORDER_SCHEMA_V1] = VALIDATION_ORDER_SCHEMA_V1
    validation_order_id: str | None = None
    steps: Tuple[CanonicalValidationStep, ...] = Field(min_length=44, max_length=44)

    @model_validator(mode="after")
    def _validate_order(self) -> "CanonicalValidationOrder":
        guard_ids = tuple(step.guard_id for step in self.steps)
        if guard_ids != EXPECTED_GUARD_IDS:
            raise ContractValidationError("canonical validation order is not C1..A22 exact")
        if tuple(step.order_index for step in self.steps) != tuple(range(1, 45)):
            raise ContractValidationError("canonical validation indexes must be contiguous")
        positions = {guard_id: index for index, guard_id in enumerate(guard_ids)}
        for step in self.steps:
            for later_guard in step.short_circuit_guard_ids:
                if later_guard not in positions:
                    raise ContractValidationError("short-circuit guard is unknown")
                if positions[later_guard] <= positions[step.guard_id]:
                    raise ContractValidationError("short-circuit guard must be later")
        payload = self.model_dump(mode="json", exclude={"validation_order_id"})
        expected = stable_contract_id("cedvalidationorder", payload)
        if self.validation_order_id is None:
            object.__setattr__(self, "validation_order_id", expected)
        elif self.validation_order_id != expected:
            raise ContractValidationError("validation_order_id does not match payload")
        return self


_STEP_SPECS: Tuple[
    Tuple[str, ProbeStage, str, str, Tuple[str, ...], str, bool, str], ...
] = (
    ("C1", ProbeStage.CAPTURE, "source state is the exact registered CED session object", "successor environment", ("ced._sessions", "state_object_identity"), "INVALID_ROOT", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C2", ProbeStage.CAPTURE, "existing usage fits the capture budget", "budget contract", ("budget", "usage"), "BUDGET_EXHAUSTED", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C3", ProbeStage.CAPTURE, "registry exists and retry or unsupported mutable facilities are disabled", "successor environment", ("ced_runtime_configuration",), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C4", ProbeStage.CAPTURE, "provider catalog is nonempty, offline or fake, unique, available, and exact-model identified", "registry and successor environment", ("adapters", "provider_catalog"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C5", ProbeStage.CAPTURE, "session adapter order and bindings cover canonical agents exactly", "CED and successor environment", ("adapter_orders", "private_bindings", "agents"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C6", ProbeStage.CAPTURE, "snapshot, configuration, and session rehydrate exactly", "successor environment", ("snapshot", "configuration_digest", "session_id"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C7", ProbeStage.CAPTURE, "root is pristine round-zero opening with pristine agents, empty ledgers and failures, and one task", "CED and successor environment", ("state", "side_ledgers", "registry"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C8", ProbeStage.CAPTURE, "canonical task, context, request, and model-configuration identity derive", "CED task contract", ("state", "task_specification", "active_binding"), "INTERNAL_CONTRACT_ERROR", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C9", ProbeStage.CAPTURE, "root projects to the sole hard-legal opening Socratic action", "CED constitution", ("projected_root",), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C10", ProbeStage.CAPTURE, "new capsule snapshot, bindings, budget, lineage, and IDs are self-consistent", "capsule contract", ("full_capsule",), "CONTRACT_VALIDATION_ERROR_PROPAGATES", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("C11", ProbeStage.CAPTURE, "capture leaves source CED unchanged", "successor environment", ("before_fingerprint", "after_fingerprint"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"),
    ("P1", ProbeStage.PREPARE, "capsule schema and identity round-trip", "capsule contract", ("source_capsule",), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P2", ProbeStage.PREPARE, "root-only lineage, rehydration, pristine state, and active binding replay", "CED and successor environment", ("source_capsule", "rehydrated_root", "active_binding"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P3", ProbeStage.PREPARE, "rebuilt task equals the frozen canonical task", "CED and successor environment", ("root", "frozen_task", "binding_configuration"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P4", ProbeStage.PREPARE, "semantic root, SearchState-v1, and side-ledger identities replay", "projection and successor environment", ("source_capsule", "rehydrated_root", "side_ledgers"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P5", ProbeStage.PREPARE, "supplied budget equals the frozen root budget", "successor environment", ("supplied_budget", "source_capsule.budget"), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P6", ProbeStage.PREPARE, "action schema and identity round-trip", "action contract", ("action",), "ILLEGAL_ACTION", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P7", ProbeStage.PREPARE, "action family is supported by the canonical successor", "successor environment", ("action.action_family",), "UNSUPPORTED_ACTION_FAMILY", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P8", ProbeStage.PREPARE, "complete hard-legal set contains the selected action", "CED constitution", ("root", "complete_hard_legal_set", "selected_action"), "ILLEGAL_ACTION", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P9", ProbeStage.PREPARE, "one successor reservation fits the budget", "budget contract", ("before_usage", "reserved_usage", "budget"), "BUDGET_EXHAUSTED", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("P10", ProbeStage.PREPARE, "pending links root, action, task, provider, model, budget, legal set, and derived IDs", "pending transition contract", ("full_pending_transition",), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"),
    ("A1", ProbeStage.APPLY, "pending has no stored extras and round-trips", "pending contract and successor environment", ("pending_transition",), "INVALID_ROOT", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A2", ProbeStage.APPLY, "pending re-prepares identically from its embedded root", "successor environment and CED", ("pending.source_capsule", "pending.action", "pending.budget"), "INVALID_ROOT_OR_EARLIER_PREPARE_REASON", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A3", ProbeStage.APPLY, "recorded observation exists", "successor environment", ("caller_observation",), "MISSING_OBSERVATION", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0._validated_observation"),
    ("A4", ProbeStage.APPLY, "stored or mapping extras and future fields are absent", "successor environment", ("observation_object_structure",), "FUTURE_LABEL_FORBIDDEN_OR_INVALID_OBSERVATION_IDENTITY", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0._validated_observation"),
    ("A5", ProbeStage.APPLY, "observation schema, transport shape, raw digest, model-configuration relation, and identity validate", "observation contract", ("observation_fields", "raw_bytes"), "INVALID_OBSERVATION_OR_INVALID_OBSERVATION_IDENTITY", True, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0._validated_observation"),
    ("A6", ProbeStage.APPLY, "structured raw JSON contains no future or control fields", "successor environment", ("delivered_raw_json",), "FUTURE_LABEL_FORBIDDEN", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A7", ProbeStage.APPLY, "observation is an exact frozen manifest member", "capture-manifest authority", ("entire_observation", "frozen_manifest"), "INVALID_OBSERVATION_IDENTITY", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A8", ProbeStage.APPLY, "source-session, context, and request compatibility hold", "compatibility contract", ("source_session_semantic_id", "context_digest", "request_semantic_digest"), "ROOT_CONTEXT_MISMATCH", True, "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"),
    ("A9", ProbeStage.APPLY, "phase, round, slot, attempt, agent, role, kind, task digest, and action compatibility hold", "compatibility contract", ("task_coordinates", "agent_id", "role", "task_kind", "task_semantic_digest", "action_id"), "OBSERVATION_TASK_MISMATCH", True, "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"),
    ("A10", ProbeStage.APPLY, "private provider binding compatibility holds", "compatibility contract", ("observed_provider_id", "expected_provider_id"), "OBSERVATION_PROVIDER_MISMATCH", False, "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"),
    ("A11", ProbeStage.APPLY, "configured and actual model binding compatibility holds", "compatibility contract", ("configured_model_id", "actual_model_id"), "OBSERVATION_MODEL_MISMATCH", True, "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"),
    ("A12", ProbeStage.APPLY, "source and task or model configuration compatibility holds", "compatibility contract", ("source_configuration_digest", "model_config_digest"), "OBSERVATION_CONFIG_MISMATCH", True, "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"),
    ("A13", ProbeStage.APPLY, "residual capsule and source-execution lineage compatibility holds", "compatibility contract", ("source_capsule_id", "source_execution_id"), "ROOT_CONTEXT_MISMATCH", False, "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"),
    ("A14", ProbeStage.APPLY, "special REFUSED transport projection is rejected", "successor environment", ("observation.transport_status",), "CANONICAL_PROCESSING_REJECTED", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A15a", ProbeStage.APPLY, "source capsule rehydrates outside the broad processing catch", "successor environment and CED rehydration", ("pending.source_capsule",), "REHYDRATION_CONTRACT_ERROR_PROPAGATES", False, "ced_canonical_successor.py:_rehydrate"),
    ("A15b", ProbeStage.APPLY, "CED phase prelude, one specification, and rebuilt-task equality complete inside the processing catch", "successor environment and CED", ("rehydrated_root", "phase_prelude", "rebuilt_task"), "CANONICAL_PROCESSING_REJECTED", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A16", ProbeStage.APPLY, "JSON parse or repair and move, schema, and marker validation produce canonical provider status", "canonical parser", ("raw_text", "canonical_task"), "PARSER_OR_SCHEMA_PROVIDER_STATUS", False, "provider_registry.py:parse_and_validate_move"),
    ("A17", ProbeStage.APPLY, "Socratic content contract and injection firewall evaluate the parsed move", "CED", ("parsed_move", "rehydrated_state"), "CONTENT_OR_INJECTION_CANONICAL_REJECTION", False, "ced.py:CEDOrchestrator._screen_socratic_move"),
    ("A18", ProbeStage.APPLY, "move, task-log, and dispatch application or rejection classification completes", "CED", ("provider_response", "canonical_task", "rehydrated_state"), "APPLIED_ACCEPTED_OR_CANONICAL_REJECTION", False, "ced.py:CEDOrchestrator._apply_registry_response"),
    ("A19", ProbeStage.APPLY, "phase finalization, quorum, and registry-round append complete", "CED", ("response", "dispatch_record", "rehydrated_state"), "CANONICAL_PROCESSING_REJECTED_ON_EXCEPTION", False, "ced.py:CEDOrchestrator._finalize_registry_phase"),
    ("A20", ProbeStage.APPLY, "CED outcome projects to canonical successor outcome", "successor environment", ("ced_application_record",), "APPLIED_ACCEPTED_OR_APPLIED_CANONICAL_REJECTION", False, "ced_canonical_successor.py:canonical_transition_outcome"),
    ("A21", ProbeStage.APPLY, "successor configuration remains unchanged", "successor environment", ("before_configuration_digest", "after_configuration_digest"), "CANONICAL_PROCESSING_REJECTED", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
    ("A22", ProbeStage.APPLY, "successor, receipt, and result identities and lineage validate", "frozen contracts", ("applied_state", "canonical_outcome", "receipt", "result"), "CONTRACT_VALIDATION_ERROR", False, "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.apply_observation"),
)


def _validation_steps() -> Tuple[CanonicalValidationStep, ...]:
    guard_ids = tuple(spec[0] for spec in _STEP_SPECS)
    stages = {spec[0]: spec[1] for spec in _STEP_SPECS}
    steps = []
    for index, spec in enumerate(_STEP_SPECS):
        guard_id, stage, check, owner, inputs, failure, independent, source = spec
        later_ids = guard_ids[index + 1 :]
        if guard_id == "A16":
            short_circuit = ("A17",)
        elif guard_id in {"A17", "A18", "A20", "A22"}:
            short_circuit = ()
        elif guard_id in {"A19", "A21"}:
            short_circuit = later_ids
        else:
            short_circuit = tuple(
                later
                for later in later_ids
                if stages[later] == stage
                or (stage == ProbeStage.CAPTURE)
                or (stage == ProbeStage.PREPARE and stages[later] == ProbeStage.APPLY)
            )
        steps.append(
            CanonicalValidationStep(
                order_index=index + 1,
                guard_id=guard_id,
                stage=stage,
                check=check,
                owner=owner,
                inputs=inputs,
                failure_result=failure,
                short_circuit_guard_ids=short_circuit,
                independently_probeable=independent,
                source_ref=source,
            )
        )
    return tuple(steps)


FROZEN_CANONICAL_VALIDATION_ORDER_V2 = CanonicalValidationOrder(
    steps=_validation_steps()
)


class FailureTaxonomyEntry(FrozenContract):
    code: str = Field(min_length=3)
    layer: FailureLayer
    owner: str = Field(min_length=3)
    governing_guard_ids: Tuple[str, ...] = Field(min_length=1)
    meaning: str = Field(min_length=3)
    independently_reachable: bool


class FailureTaxonomyContract(FrozenContract):
    schema_version: Literal[FAILURE_TAXONOMY_SCHEMA_V1] = FAILURE_TAXONOMY_SCHEMA_V1
    taxonomy_id: str | None = None
    entries: Tuple[FailureTaxonomyEntry, ...] = Field(min_length=15)

    @model_validator(mode="after")
    def _validate_taxonomy(self) -> "FailureTaxonomyContract":
        codes = tuple(entry.code for entry in self.entries)
        if len(codes) != len(set(codes)):
            raise ContractValidationError("failure taxonomy codes must be unique")
        valid_guards = set(EXPECTED_GUARD_IDS)
        if any(
            guard not in valid_guards
            for entry in self.entries
            for guard in entry.governing_guard_ids
        ):
            raise ContractValidationError("taxonomy refers to an unknown guard")
        payload = self.model_dump(mode="json", exclude={"taxonomy_id"})
        expected = stable_contract_id("cedfailuretaxonomy", payload)
        if self.taxonomy_id is None:
            object.__setattr__(self, "taxonomy_id", expected)
        elif self.taxonomy_id != expected:
            raise ContractValidationError("taxonomy_id does not match payload")
        return self


def _taxonomy_entry(
    code: str,
    layer: FailureLayer,
    guards: Tuple[str, ...],
    meaning: str,
    independent: bool,
) -> FailureTaxonomyEntry:
    return FailureTaxonomyEntry(
        code=code,
        layer=layer,
        owner=(
            "CED canonical parser and application"
            if layer == FailureLayer.APPLIED
            else "CED and CanonicalSuccessorEnvironmentV0"
            if layer == FailureLayer.CANONICAL_PROCESSING
            else "CanonicalSuccessorEnvironmentV0 and frozen contracts"
        ),
        governing_guard_ids=guards,
        meaning=meaning,
        independently_reachable=independent,
    )


FROZEN_CANONICAL_FAILURE_TAXONOMY_V1 = FailureTaxonomyContract(
    entries=(
        _taxonomy_entry("INVALID_ROOT", FailureLayer.PREPARATION, ("C1", "C3", "C4", "C5", "C6", "C7", "C9", "C11", "P1", "P2", "P3", "P4", "P5", "P10", "A1", "A2"), "root, capsule, pending transition, or environment registration is invalid", True),
        _taxonomy_entry("ILLEGAL_ACTION", FailureLayer.PREPARATION, ("P6", "P8"), "action contract or complete hard-legal membership fails", True),
        _taxonomy_entry("UNSUPPORTED_ACTION_FAMILY", FailureLayer.PREPARATION, ("P7",), "action family has no canonical successor implementation", True),
        _taxonomy_entry("BUDGET_EXHAUSTED", FailureLayer.PREPARATION, ("C2", "P9"), "capture usage or one successor reservation exceeds the bounded budget", True),
        _taxonomy_entry("MISSING_OBSERVATION", FailureLayer.OBSERVATION_BINDING, ("A3",), "no recorded observation was submitted", True),
        _taxonomy_entry("INVALID_OBSERVATION", FailureLayer.OBSERVATION_BINDING, ("A5",), "recorded observation does not satisfy its structural contract", True),
        _taxonomy_entry("INVALID_OBSERVATION_IDENTITY", FailureLayer.OBSERVATION_BINDING, ("A4", "A5", "A7"), "stored extras, observation identity, raw digest, or manifest membership is not exact", True),
        _taxonomy_entry("FUTURE_LABEL_FORBIDDEN", FailureLayer.OBSERVATION_BINDING, ("A4", "A6"), "a forbidden future-derived label is present in the envelope or structured raw JSON", True),
        _taxonomy_entry("ROOT_CONTEXT_MISMATCH", FailureLayer.OBSERVATION_BINDING, ("A8", "A13"), "source-session/context/request binding or residual capsule/execution lineage differs", True),
        _taxonomy_entry("OBSERVATION_TASK_MISMATCH", FailureLayer.OBSERVATION_BINDING, ("A9",), "private agent or task-semantic binding differs", True),
        _taxonomy_entry("OBSERVATION_PROVIDER_MISMATCH", FailureLayer.OBSERVATION_BINDING, ("A10",), "defined private provider binding differs; this is conditional and is not an orthogonal probe", False),
        _taxonomy_entry("OBSERVATION_MODEL_MISMATCH", FailureLayer.OBSERVATION_BINDING, ("A11",), "exact configured or actual model binding differs", True),
        _taxonomy_entry("OBSERVATION_CONFIG_MISMATCH", FailureLayer.OBSERVATION_BINDING, ("A12",), "source configuration digest differs", True),
        _taxonomy_entry("CANONICAL_PROCESSING_REJECTED", FailureLayer.CANONICAL_PROCESSING, ("A14", "A15b", "A19", "A21"), "REFUSED transport, processor exception, or post-application configuration divergence prevents an applied result", False),
        _taxonomy_entry("APPLIED_CANONICAL_REJECTION", FailureLayer.APPLIED, ("A16", "A17", "A18", "A20"), "canonical parser, schema, transport, content, injection, or response application rejected the move", False),
        _taxonomy_entry("APPLIED_ACCEPTED", FailureLayer.APPLIED, ("A18", "A20"), "canonical CED application accepted and dispatched the move", False),
    )
)


class FailurePrecedenceContract(FrozenContract):
    schema_version: Literal[FAILURE_PRECEDENCE_SCHEMA_V1] = FAILURE_PRECEDENCE_SCHEMA_V1
    precedence_id: str | None = None
    selected_model: Literal[FailurePrecedenceModel.FIRST_CANONICAL_GUARD_WINS] = FailurePrecedenceModel.FIRST_CANONICAL_GUARD_WINS
    canonical_guard_order_id: str
    compatibility_guard_order: Tuple[str, ...]
    primary_rule: str
    advisory_rule: str
    runtime_semantic_change_required: Literal[False] = False

    @model_validator(mode="after")
    def _validate_precedence(self) -> "FailurePrecedenceContract":
        if self.compatibility_guard_order != ("A8", "A9", "A10", "A11", "A12", "A13"):
            raise ContractValidationError("compatibility order must remain root/task/provider/model/config/residual")
        if self.canonical_guard_order_id != FROZEN_CANONICAL_VALIDATION_ORDER_V2.validation_order_id:
            raise ContractValidationError("precedence must reference the frozen validation order")
        payload = self.model_dump(mode="json", exclude={"precedence_id"})
        expected = stable_contract_id("cedfailureprecedence", payload)
        if self.precedence_id is None:
            object.__setattr__(self, "precedence_id", expected)
        elif self.precedence_id != expected:
            raise ContractValidationError("precedence_id does not match payload")
        return self


FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1 = FailurePrecedenceContract(
    canonical_guard_order_id=FROZEN_CANONICAL_VALIDATION_ORDER_V2.validation_order_id,
    compatibility_guard_order=("A8", "A9", "A10", "A11", "A12", "A13"),
    primary_rule="The first failing canonical guard in the frozen execution order owns the primary result.",
    advisory_rule="Later or dominated mismatches may be recorded only as non-authoritative diagnostics and cannot replace the primary result.",
)


class CompatibilityDiagnosticsContract(FrozenContract):
    schema_version: Literal[COMPATIBILITY_DIAGNOSTICS_SCHEMA_V1] = COMPATIBILITY_DIAGNOSTICS_SCHEMA_V1
    diagnostics_id: str | None = None
    invariant_fields: Tuple[str, ...] = Field(min_length=15, max_length=15)
    root_context_guard_fields: Tuple[str, ...]
    task_semantic_guard_fields: Tuple[str, ...]
    authoritative_for_primary_result: Literal[False] = False
    can_override_first_failure: Literal[False] = False
    provider_mismatch_reachability: str
    root_context_mismatch_definition: str
    parser_boundary: str

    @model_validator(mode="after")
    def _validate_diagnostics(self) -> "CompatibilityDiagnosticsContract":
        if self.invariant_fields != INVARIANT_FIELD_NAMES:
            raise ContractValidationError("diagnostics must expose the exact fifteen-field vector")
        if self.root_context_guard_fields != (
            "source_session_semantic_id",
            "context_digest",
            "request_semantic_digest",
        ):
            raise ContractValidationError("root-context guard field slice changed")
        if self.task_semantic_guard_fields != (
            "phase",
            "round_number",
            "slot_index",
            "attempt_index",
            "agent_id",
            "role",
            "task_kind",
            "task_semantic_digest",
        ):
            raise ContractValidationError("task-semantic guard field slice changed")
        payload = self.model_dump(mode="json", exclude={"diagnostics_id"})
        expected = stable_contract_id("cedcompatdiagnostics", payload)
        if self.diagnostics_id is None:
            object.__setattr__(self, "diagnostics_id", expected)
        elif self.diagnostics_id != expected:
            raise ContractValidationError("diagnostics_id does not match payload")
        return self


FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1 = CompatibilityDiagnosticsContract(
    invariant_fields=INVARIANT_FIELD_NAMES,
    root_context_guard_fields=(
        "source_session_semantic_id",
        "context_digest",
        "request_semantic_digest",
    ),
    task_semantic_guard_fields=(
        "phase",
        "round_number",
        "slot_index",
        "attempt_index",
        "agent_id",
        "role",
        "task_kind",
        "task_semantic_digest",
    ),
    provider_mismatch_reachability="A10 is defined only when a private expected provider binding exists. Public provider-roster mutation is dominated by A8 root-context mismatch and is excluded from the orthogonal corpus.",
    root_context_mismatch_definition="A8 is reachable when any of source_session_semantic_id, context_digest, or request_semantic_digest differs after A1-A7 pass.",
    parser_boundary="The A6 future-field structural scan may call json.loads. A pre-A16 probe is never passed to canonical parse_and_validate_move or to CED application.",
)


class ProbeLiteralMutation(FrozenContract):
    path: str = Field(min_length=1)
    before_json: str
    after_json: str
    independent_authoritative_input: bool = True

    @field_validator("before_json", "after_json")
    @classmethod
    def _canonical_json_literal(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ContractValidationError("mutation literal must be JSON") from exc
        if canonical_json(parsed) != value:
            raise ContractValidationError("mutation literal must be canonical JSON")
        return value


class CanonicalSuccessorProbeV2(FrozenContract):
    schema_version: Literal[UNAVAILABLE_PROBE_SCHEMA_V2] = UNAVAILABLE_PROBE_SCHEMA_V2
    probe_id: str = Field(pattern=r"^p8v2-[op][0-9]{2}-[a-z0-9-]+$")
    probe_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    probe_class: ProbeClass
    stage: ProbeStage
    construction_rule: str = Field(min_length=3)
    literal_mutations: Tuple[ProbeLiteralMutation, ...] = Field(min_length=1)
    invariant_vector: ProbeInvariantVector
    expected_primary_reason: SuccessorUnavailableReason
    expected_guard_id: str
    expected_primary_mismatch_fields: Tuple[str, ...]
    advisory_or_dominated_mismatch_fields: Tuple[str, ...]
    guard_evaluations: Tuple[GuardEvaluation, ...] = Field(min_length=44, max_length=44)
    unreachable_guard_ids: Tuple[str, ...]
    observation_submission: ObservationSubmissionState
    structured_future_scan_reached: bool
    canonical_parser_reached: Literal[False] = False
    ced_application_reached: Literal[False] = False
    independently_probeable: bool

    @field_validator("expected_primary_mismatch_fields", "advisory_or_dominated_mismatch_fields")
    @classmethod
    def _sorted_unique_fields(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ContractValidationError("mismatch fields must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _validate_probe(self) -> "CanonicalSuccessorProbeV2":
        guard_ids = tuple(item.guard_id for item in self.guard_evaluations)
        if guard_ids != EXPECTED_GUARD_IDS:
            raise ContractValidationError("probe guard evaluation coverage must be exact")
        failed = tuple(
            item.guard_id
            for item in self.guard_evaluations
            if item.state == GuardEvaluationState.EVALUATED_FAILED
        )
        if failed != (self.expected_guard_id,):
            raise ContractValidationError("probe must identify exactly one primary failing guard")
        computed_unreachable = tuple(
            item.guard_id
            for item in self.guard_evaluations
            if item.state in {GuardEvaluationState.NOT_EVALUATED, GuardEvaluationState.NOT_CONSTRUCTED}
        )
        if self.unreachable_guard_ids != computed_unreachable:
            raise ContractValidationError("unreachable guard list differs from evaluation states")
        valid_ids = ORTHOGONAL_PROBE_IDS if self.probe_class == ProbeClass.ORTHOGONAL else PRECEDENCE_PROBE_IDS
        if self.probe_id not in valid_ids:
            raise ContractValidationError("probe ID is not in its frozen human-ID set")
        if self.expected_primary_reason == SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH:
            raise ContractValidationError("provider mismatch is excluded from the v2 probe corpus")
        payload = self.model_dump(mode="json", exclude={"probe_fingerprint"})
        expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        if self.probe_fingerprint is None:
            object.__setattr__(self, "probe_fingerprint", expected)
        elif self.probe_fingerprint != expected:
            raise ContractValidationError("probe_fingerprint does not match payload")
        return self


def _m(path: str, before: object, after: object, *, independent: bool = True) -> ProbeLiteralMutation:
    return ProbeLiteralMutation(
        path=path,
        before_json=canonical_json(before),
        after_json=canonical_json(after),
        independent_authoritative_input=independent,
    )


P = InvariantState.PRESERVED
I = InvariantState.INTENTIONALLY_CHANGED
D = InvariantState.DEPENDENTLY_CHANGED
N = InvariantState.NOT_APPLICABLE


def _v(
    root_identity: InvariantState,
    capsule_identity: InvariantState,
    pending_identity: InvariantState,
    task_semantic_identity: InvariantState,
    public_context_digest: InvariantState,
    council_roster_digest: InvariantState,
    action_identity: InvariantState,
    observation_manifest_identity: InvariantState,
    observation_payload_digest: InvariantState,
    provider_binding: InvariantState,
    exact_model_binding: InvariantState,
    configuration_binding: InvariantState,
    lineage_binding: InvariantState,
    future_label_status: InvariantState,
    budget_status: InvariantState,
) -> ProbeInvariantVector:
    return ProbeInvariantVector(
        root_identity=root_identity,
        capsule_identity=capsule_identity,
        pending_identity=pending_identity,
        task_semantic_identity=task_semantic_identity,
        public_context_digest=public_context_digest,
        council_roster_digest=council_roster_digest,
        action_identity=action_identity,
        observation_manifest_identity=observation_manifest_identity,
        observation_payload_digest=observation_payload_digest,
        provider_binding=provider_binding,
        exact_model_binding=exact_model_binding,
        configuration_binding=configuration_binding,
        lineage_binding=lineage_binding,
        future_label_status=future_label_status,
        budget_status=budget_status,
    )


def _guard_evaluations(target_guard: str) -> Tuple[GuardEvaluation, ...]:
    positions = {guard_id: index for index, guard_id in enumerate(EXPECTED_GUARD_IDS)}
    target_index = positions[target_guard]
    target_stage = FROZEN_CANONICAL_VALIDATION_ORDER_V2.steps[target_index].stage
    evaluations = []
    for index, step in enumerate(FROZEN_CANONICAL_VALIDATION_ORDER_V2.steps):
        if index < target_index:
            state = GuardEvaluationState.EVALUATED_PASSED
        elif index == target_index:
            state = GuardEvaluationState.EVALUATED_FAILED
        elif step.stage == target_stage:
            state = GuardEvaluationState.NOT_EVALUATED
        else:
            state = GuardEvaluationState.NOT_CONSTRUCTED
        evaluations.append(GuardEvaluation(guard_id=step.guard_id, state=state))
    return tuple(evaluations)


def _probe(
    *,
    probe_id: str,
    probe_class: ProbeClass,
    stage: ProbeStage,
    construction_rule: str,
    literal_mutations: Tuple[ProbeLiteralMutation, ...],
    vector: ProbeInvariantVector,
    reason: SuccessorUnavailableReason,
    guard: str,
    primary_fields: Tuple[str, ...] = (),
    advisory_fields: Tuple[str, ...] = (),
    observation_submission: ObservationSubmissionState = ObservationSubmissionState.SUBMITTED,
    structured_scan: bool = False,
    independently_probeable: bool = True,
) -> CanonicalSuccessorProbeV2:
    evaluations = _guard_evaluations(guard)
    return CanonicalSuccessorProbeV2(
        probe_id=probe_id,
        probe_class=probe_class,
        stage=stage,
        construction_rule=construction_rule,
        literal_mutations=literal_mutations,
        invariant_vector=vector,
        expected_primary_reason=reason,
        expected_guard_id=guard,
        expected_primary_mismatch_fields=tuple(sorted(primary_fields)),
        advisory_or_dominated_mismatch_fields=tuple(sorted(advisory_fields)),
        guard_evaluations=evaluations,
        unreachable_guard_ids=tuple(
            item.guard_id
            for item in evaluations
            if item.state in {GuardEvaluationState.NOT_EVALUATED, GuardEvaluationState.NOT_CONSTRUCTED}
        ),
        observation_submission=observation_submission,
        structured_future_scan_reached=structured_scan,
        independently_probeable=independently_probeable,
    )


_RAW_DIGEST = "912c229dca5ecb8d0ad0736b5e5241dae6e5a3a6ddf9151e323d1bc321d24f62"
_BASE_QUESTION = "Is knowledge merely justified true belief?"
_NEW_QUESTION = "What is knowledge?"
_AGENT = "phase8-recorded-agent-1"
_AGENT_RENAMED = "phase8-recorded-agent-1-v2"
_MODEL = "phase8-recorded-model/1"
_MODEL_RENAMED = "phase8-recorded-model/1-v2-orthogonal"


FROZEN_CANONICAL_SUCCESSOR_PROBES_V2: Tuple[CanonicalSuccessorProbeV2, ...] = (
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[0], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.CAPTURE, construction_rule="Deep-copy the accepted SessionState and pass the equal but unregistered object to CanonicalSuccessorEnvironmentV0.capture_capsule.", literal_mutations=(_m("root.object_registration", "registered_canonical_object", "detached_deep_copy"),), vector=_v(I, N, N, P, P, P, P, P, P, P, P, P, N, P, P), reason=SuccessorUnavailableReason.INVALID_ROOT, guard="C1", observation_submission=ObservationSubmissionState.NOT_APPLICABLE),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[1], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.PREPARE, construction_rule="Add only the unavailable capability not-present-in-root to the same-family accepted action; the complete hard-legal set no longer contains it.", literal_mutations=(_m("action.required_capabilities", [], ["not-present-in-root"]),), vector=_v(P, P, N, P, P, P, I, P, P, P, P, P, P, P, P), reason=SuccessorUnavailableReason.ILLEGAL_ACTION, guard="P8", primary_fields=("required_capabilities",), observation_submission=ObservationSubmissionState.NOT_APPLICABLE),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[2], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Apply the exact accepted pending transition with observation=None; the submitted manifest relation is intentionally changed to absent and no payload digest applies.", literal_mutations=(_m("observation", "exact_manifest_observation", None),), vector=_v(P, P, P, P, P, P, P, I, N, P, P, P, P, P, P), reason=SuccessorUnavailableReason.MISSING_OBSERVATION, guard="A3", observation_submission=ObservationSubmissionState.NOT_SUBMITTED),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[3], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Submit the frozen minimal malformed mapping containing only schema_version=ced-recorded-observation/v1.", literal_mutations=(_m("observation", "exact_manifest_observation", {"schema_version": "ced-recorded-observation/v1"}),), vector=_v(P, P, P, P, P, P, P, N, I, P, P, P, P, P, P), reason=SuccessorUnavailableReason.INVALID_OBSERVATION, guard="A5"),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[4], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Keep the accepted raw bytes and frozen observation ID but replace only its stored raw_output_digest with f repeated 64 times; payload bytes therefore remain exact while manifest identity is intentionally invalidated.", literal_mutations=(_m("observation.raw_output_digest", _RAW_DIGEST, "f" * 64),), vector=_v(P, P, P, P, P, P, P, I, P, P, P, P, P, P, P), reason=SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY, guard="A5", primary_fields=("raw_output_digest",)),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[5], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Rename only the active agent to phase8-recorded-agent-1-v2 while preserving its active provider seat and sorted rank; task-semantic identity is the intended changed relation, while full binding/configuration/lineage identities change dependently. Hold the accepted observation fixed.", literal_mutations=(_m("root.active_agent_id", _AGENT, _AGENT_RENAMED),), vector=_v(D, D, D, I, P, P, P, P, P, P, P, D, D, P, P), reason=SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH, guard="A9", primary_fields=("agent_id", "task_semantic_digest"), structured_scan=True),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[6], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Change only the root question to What is knowledge? while retaining the accepted session ID and exact observation; root identity is the intended changed relation, and the CED task context digest itself remains equal while session/request bindings change.", literal_mutations=(_m("root.question", _BASE_QUESTION, _NEW_QUESTION),), vector=_v(I, D, D, D, P, P, P, P, P, P, P, P, D, P, P), reason=SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH, guard="A8", primary_fields=("request_semantic_digest", "source_session_semantic_id"), structured_scan=True),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[7], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Change only the active agent's authoritative exact model from phase8-recorded-model/1 to phase8-recorded-model/1-v2-orthogonal while retaining the public display roster and narrow active provider seat; the two derived full ProviderBindingIdentity rows sharing that adapter change dependently.", literal_mutations=(_m("root.active_model_id", _MODEL, _MODEL_RENAMED),), vector=_v(D, D, D, D, P, P, P, P, P, P, I, D, D, P, P), reason=SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH, guard="A11", primary_fields=("actual_model_id", "configured_model_id"), structured_scan=True),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[8], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Change only provider_timeout_seconds from 30.0 to 31.0 and hold task-guard fields, provider, model, action, and observation fixed.", literal_mutations=(_m("runtime.provider_timeout_seconds", 30.0, 31.0),), vector=_v(D, D, D, P, P, P, P, P, P, P, P, I, D, P, P), reason=SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH, guard="A12", primary_fields=("source_configuration_digest",), structured_scan=True),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[9], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.APPLY, construction_rule="Copy observation.model_dump(mode='json') and add only the forbidden top-level observation-envelope field reward=1.", literal_mutations=(_m("observation.reward", None, 1),), vector=_v(P, P, P, P, P, P, P, P, P, P, P, P, P, I, P), reason=SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN, guard="A4", primary_fields=("reward",)),
    _probe(probe_id=ORTHOGONAL_PROBE_IDS[10], probe_class=ProbeClass.ORTHOGONAL, stage=ProbeStage.PREPARE, construction_rule="Change max_nodes only from 4 to 1; retain max_expansions=3 and every other input.", literal_mutations=(_m("budget.max_nodes", 4, 1),), vector=_v(D, D, N, P, P, P, P, P, P, P, P, P, D, P, I), reason=SuccessorUnavailableReason.BUDGET_EXHAUSTED, guard="P9", primary_fields=("max_nodes",), observation_submission=ObservationSubmissionState.NOT_APPLICABLE),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[0], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.PREPARE, construction_rule="Change only action_family from OPENING to RUN_ELENCHUS; that family is supported by no v0 successor path and is inherently absent from the complete hard-legal set, so P7 dominates P8.", literal_mutations=(_m("action.action_family", "OPENING", "RUN_ELENCHUS"),), vector=_v(P, P, N, P, P, P, I, P, P, P, P, P, P, P, P), reason=SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY, guard="P7", primary_fields=("action_family",), advisory_fields=("not_in_legal_set",), observation_submission=ObservationSubmissionState.NOT_APPLICABLE, independently_probeable=False),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[1], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.APPLY, construction_rule="Replace both public provider catalog seat IDs while preserving rank and active model; A8 context/request mismatch dominates conditional A10 provider binding.", literal_mutations=(_m("root.provider_catalog[0].provider_id", "phase8-recorded-seat-0", "phase8-wrong-seat-0"), _m("root.provider_catalog[1].provider_id", "phase8-recorded-seat-1", "phase8-wrong-seat-1")), vector=_v(D, D, D, D, D, I, P, P, P, D, P, D, D, P, P), reason=SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH, guard="A8", primary_fields=("context_digest", "request_semantic_digest"), advisory_fields=("provider_id",), structured_scan=True, independently_probeable=False),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[2], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.APPLY, construction_rule="Intentionally change the root question and both provider catalog seat IDs in one construction; root identity and council-roster identity record the two independent relations, and A8 owns the primary result before A10.", literal_mutations=(_m("root.question", _BASE_QUESTION, _NEW_QUESTION), _m("root.provider_catalog[0].provider_id", "phase8-recorded-seat-0", "phase8-wrong-seat-0"), _m("root.provider_catalog[1].provider_id", "phase8-recorded-seat-1", "phase8-wrong-seat-1")), vector=_v(I, D, D, D, D, I, P, P, P, D, P, D, D, P, P), reason=SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH, guard="A8", primary_fields=("context_digest", "request_semantic_digest", "source_session_semantic_id"), advisory_fields=("provider_id",), structured_scan=True, independently_probeable=False),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[3], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.APPLY, construction_rule="Intentionally rename the active agent and change its authoritative exact model while the public display roster and narrow active provider seat stay fixed; task-semantic and exact-model relations record both independent changes, and A9 dominates A11.", literal_mutations=(_m("root.active_agent_id", _AGENT, _AGENT_RENAMED), _m("root.active_model_id", _MODEL, _MODEL_RENAMED)), vector=_v(D, D, D, I, P, P, P, P, P, P, I, D, D, P, P), reason=SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH, guard="A9", primary_fields=("agent_id", "task_semantic_digest"), advisory_fields=("actual_model_id", "configured_model_id"), structured_scan=True, independently_probeable=False),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[4], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.APPLY, construction_rule="Intentionally use a different-question root and tamper stored raw_output_digest to f*64 while raw bytes stay exact; root and manifest relations record both independent changes, and A5 dominates A8 while public context digest stays equal.", literal_mutations=(_m("root.question", _BASE_QUESTION, _NEW_QUESTION), _m("observation.raw_output_digest", _RAW_DIGEST, "f" * 64)), vector=_v(I, D, D, D, P, P, P, I, P, P, P, P, D, P, P), reason=SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY, guard="A5", primary_fields=("raw_output_digest",), advisory_fields=("request_semantic_digest", "source_session_semantic_id"), independently_probeable=False),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[5], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.PREPARE, construction_rule="Intentionally use a different-question root and a same-family action requiring not-present-in-root; root and action relations record both independent changes, public context digest stays equal, and the exact accepted observation is held but not submitted because P8 ends preparation.", literal_mutations=(_m("root.question", _BASE_QUESTION, _NEW_QUESTION), _m("action.required_capabilities", [], ["not-present-in-root"])), vector=_v(I, D, N, D, P, P, I, P, P, P, P, P, D, P, P), reason=SuccessorUnavailableReason.ILLEGAL_ACTION, guard="P8", primary_fields=("required_capabilities",), advisory_fields=("request_semantic_digest", "source_session_semantic_id"), observation_submission=ObservationSubmissionState.NOT_SUBMITTED, independently_probeable=False),
    _probe(probe_id=PRECEDENCE_PROBE_IDS[6], probe_class=ProbeClass.PRECEDENCE, stage=ProbeStage.APPLY, construction_rule="Re-mint the opening-scripted-mock raw bytes against the opening-empty-question binding; exact manifest membership fails at A7. Public context, action identity, and full source configuration stay equal; provider/model/task-model-config and lineage differ. The A6 structural scan may json.loads, but the payload is never passed to canonical parse_and_validate_move or CED application.", literal_mutations=(_m("caller.binding_case", "opening-scripted-mock", "opening-empty-question"),), vector=_v(I, I, I, I, P, P, P, I, P, I, I, P, I, P, P), reason=SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY, guard="A7", primary_fields=("manifest_exact_observation",), advisory_fields=("agent_id", "configured_model_id", "provider_id", "task_semantic_digest"), structured_scan=True, independently_probeable=False),
)


class ProbeDesignContract(FrozenContract):
    schema_version: Literal[PROBE_DESIGN_SCHEMA_V1] = PROBE_DESIGN_SCHEMA_V1
    case_set_schema_version: Literal[CASE_SET_SCHEMA_V2] = CASE_SET_SCHEMA_V2
    probe_design_id: str | None = None
    probe_design_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    taxonomy_id: str
    precedence_id: str
    diagnostics_id: str
    validation_order_id: str
    baseline_case_name: Literal["opening-scripted-mock"] = "opening-scripted-mock"
    orthogonal_probe_ids: Tuple[str, ...]
    precedence_probe_ids: Tuple[str, ...]
    probes: Tuple[CanonicalSuccessorProbeV2, ...] = Field(min_length=18, max_length=18)
    provider_mismatch_probe_excluded: Literal[True] = True

    @model_validator(mode="after")
    def _validate_design(self) -> "ProbeDesignContract":
        if self.orthogonal_probe_ids != ORTHOGONAL_PROBE_IDS:
            raise ContractValidationError("orthogonal probe membership must be exact")
        if self.precedence_probe_ids != PRECEDENCE_PROBE_IDS:
            raise ContractValidationError("precedence probe membership must be exact")
        expected_ids = ORTHOGONAL_PROBE_IDS + PRECEDENCE_PROBE_IDS
        actual_ids = tuple(probe.probe_id for probe in self.probes)
        if actual_ids != expected_ids or len(set(actual_ids)) != 18:
            raise ContractValidationError("probe corpus must contain exactly eleven plus seven human IDs")
        if tuple(probe.probe_class for probe in self.probes[:11]) != (ProbeClass.ORTHOGONAL,) * 11:
            raise ContractValidationError("first eleven probes must be orthogonal")
        if tuple(probe.probe_class for probe in self.probes[11:]) != (ProbeClass.PRECEDENCE,) * 7:
            raise ContractValidationError("last seven probes must be precedence probes")
        if len({probe.probe_fingerprint for probe in self.probes}) != 18:
            raise ContractValidationError("probe fingerprints must be unique and separate from human IDs")
        if self.taxonomy_id != FROZEN_CANONICAL_FAILURE_TAXONOMY_V1.taxonomy_id:
            raise ContractValidationError("design taxonomy reference differs")
        if self.precedence_id != FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1.precedence_id:
            raise ContractValidationError("design precedence reference differs")
        if self.diagnostics_id != FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.diagnostics_id:
            raise ContractValidationError("design diagnostics reference differs")
        if self.validation_order_id != FROZEN_CANONICAL_VALIDATION_ORDER_V2.validation_order_id:
            raise ContractValidationError("design validation-order reference differs")
        payload = self.model_dump(mode="json", exclude={"probe_design_id", "probe_design_fingerprint"})
        fingerprint = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        identifier = stable_contract_id("cedprobedesign", payload)
        if self.probe_design_fingerprint is None:
            object.__setattr__(self, "probe_design_fingerprint", fingerprint)
        elif self.probe_design_fingerprint != fingerprint:
            raise ContractValidationError("probe_design_fingerprint differs")
        if self.probe_design_id is None:
            object.__setattr__(self, "probe_design_id", identifier)
        elif self.probe_design_id != identifier:
            raise ContractValidationError("probe_design_id differs")
        return self


FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1 = ProbeDesignContract(
    taxonomy_id=FROZEN_CANONICAL_FAILURE_TAXONOMY_V1.taxonomy_id,
    precedence_id=FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1.precedence_id,
    diagnostics_id=FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.diagnostics_id,
    validation_order_id=FROZEN_CANONICAL_VALIDATION_ORDER_V2.validation_order_id,
    orthogonal_probe_ids=ORTHOGONAL_PROBE_IDS,
    precedence_probe_ids=PRECEDENCE_PROBE_IDS,
    probes=FROZEN_CANONICAL_SUCCESSOR_PROBES_V2,
)


class FrozenV1ReferenceLink(FrozenContract):
    case_name: str
    case_id: str = Field(pattern=r"^cedobscasev1_[0-9a-f]{64}$")
    reference_id: str = Field(pattern=r"^cedsuccessorref_[0-9a-f]{64}$")


EXPECTED_V1_REFERENCE_LINKS: Tuple[FrozenV1ReferenceLink, ...] = (
    FrozenV1ReferenceLink(case_name="opening-empty-question", case_id="cedobscasev1_10d9781cb3a252ecd759449885081e8a6670996e5fdf7435f5242872c5218905", reference_id="cedsuccessorref_85abdbfec328b39cc43630a8cea70ca2696843cfed9e4e6d5ff9b13599072ef2"),
    FrozenV1ReferenceLink(case_name="opening-injection-question", case_id="cedobscasev1_bcd6517311b1a76644b3e533bfb5ca576e7afb84d3a3e05505f59db7c28c2ac6", reference_id="cedsuccessorref_33244c4894345a37f56088c6149f8262fbf2e146ccc3b3231ec1aa2535e43e61"),
    FrozenV1ReferenceLink(case_name="opening-invalid-json", case_id="cedobscasev1_e5ad44bc15348ea9f82d406afc785c9a70dab9b98582644c585c0216641b901c", reference_id="cedsuccessorref_128626044b00732b181d9658ecd5b4ea8b3a4e0855fc32c214109495e4b91f8f"),
    FrozenV1ReferenceLink(case_name="opening-schema-error", case_id="cedobscasev1_eba36c3c48cb05f8f7b63b66945ca91a5853da3feeb1bc35d44a0fefda4f0cf3", reference_id="cedsuccessorref_aa10387f33f114023cc263c2a8ba7cd721c9d46ebe860a63a61a1299de71e3d2"),
    FrozenV1ReferenceLink(case_name="opening-scripted-mock", case_id="cedobscasev1_7a7cefff8d5cb30ff35e70342016304a7c98835e7c575e2a39b07a4afdc4144a", reference_id="cedsuccessorref_6efccf0d4a43b1c96845eb71d57fd6fb5f6e5d6b43154e3f49cdaad6832dcc44"),
)


class CanonicalSuccessorParityCaseSetV2(FrozenContract):
    """Reference-only membership contract for the complete v2 experiment."""

    schema_version: Literal[CASE_SET_SCHEMA_V2] = CASE_SET_SCHEMA_V2
    case_set_id: str | None = None
    predecessor_corpus_id: str
    predecessor_canonical_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    positive_case_references: Tuple[FrozenV1ReferenceLink, ...] = Field(
        min_length=5, max_length=5
    )
    probe_design_id: str
    human_probe_ids: Tuple[str, ...] = Field(min_length=18, max_length=18)
    probe_fingerprints: Tuple[str, ...] = Field(min_length=18, max_length=18)
    positive_reference_count: Literal[5] = 5
    orthogonal_probe_count: Literal[11] = 11
    precedence_probe_count: Literal[7] = 7
    total_case_count: Literal[23] = 23

    @model_validator(mode="after")
    def _validate_case_set(self) -> "CanonicalSuccessorParityCaseSetV2":
        if self.predecessor_corpus_id != EXPECTED_V1_CORPUS_ID:
            raise ContractValidationError("case set must reference the exact v1 corpus")
        if self.predecessor_canonical_sha256 != EXPECTED_V1_CORPUS_SHA256:
            raise ContractValidationError("case set must reference the exact v1 SHA")
        if self.positive_case_references != EXPECTED_V1_REFERENCE_LINKS:
            raise ContractValidationError("case set must reference the exact five v1 case/reference IDs")
        expected_ids = ORTHOGONAL_PROBE_IDS + PRECEDENCE_PROBE_IDS
        if self.human_probe_ids != expected_ids or len(set(self.human_probe_ids)) != 18:
            raise ContractValidationError("case set requires the exact eleven plus seven human probe IDs")
        expected_fingerprints = tuple(
            probe.probe_fingerprint for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
        )
        if self.probe_fingerprints != expected_fingerprints:
            raise ContractValidationError("case set probe fingerprints differ")
        if len(set(self.probe_fingerprints)) != 18:
            raise ContractValidationError("case set probe fingerprints must be unique")
        if self.probe_design_id != FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.probe_design_id:
            raise ContractValidationError("case set must reference the frozen probe design")
        if 5 + 11 + 7 != self.total_case_count:
            raise ContractValidationError("case set membership must be exactly 23")
        payload = self.model_dump(mode="json", exclude={"case_set_id"})
        expected = stable_contract_id("cedparitycasesetv2", payload)
        if self.case_set_id is None:
            object.__setattr__(self, "case_set_id", expected)
        elif self.case_set_id != expected:
            raise ContractValidationError("case_set_id does not match payload")
        return self


FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2 = CanonicalSuccessorParityCaseSetV2(
    predecessor_corpus_id=EXPECTED_V1_CORPUS_ID,
    predecessor_canonical_sha256=EXPECTED_V1_CORPUS_SHA256,
    positive_case_references=EXPECTED_V1_REFERENCE_LINKS,
    probe_design_id=FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.probe_design_id,
    human_probe_ids=ORTHOGONAL_PROBE_IDS + PRECEDENCE_PROBE_IDS,
    probe_fingerprints=tuple(
        probe.probe_fingerprint for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    ),
)


class CanonicalSuccessorParityCorpusV2(FrozenContract):
    schema_version: Literal[PARITY_CORPUS_SCHEMA_V2] = PARITY_CORPUS_SCHEMA_V2
    corpus_id: str | None = None
    predecessor_schema_version: Literal["ced-canonical-successor-parity-corpus/v1"] = "ced-canonical-successor-parity-corpus/v1"
    predecessor_corpus_id: str
    predecessor_canonical_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_v1_references: Tuple[FrozenV1ReferenceLink, ...] = Field(min_length=5, max_length=5)
    case_set_id: str
    probe_design_id: str
    human_probe_ids: Tuple[str, ...] = Field(min_length=18, max_length=18)
    probe_fingerprints: Tuple[str, ...] = Field(min_length=18, max_length=18)
    positive_reference_count: Literal[5] = 5
    orthogonal_probe_count: Literal[11] = 11
    precedence_probe_count: Literal[7] = 7
    total_membership: Literal[23] = 23

    @model_validator(mode="after")
    def _validate_corpus(self) -> "CanonicalSuccessorParityCorpusV2":
        if self.predecessor_corpus_id != EXPECTED_V1_CORPUS_ID:
            raise ContractValidationError("v2 must reference the exact frozen v1 corpus ID")
        if self.predecessor_canonical_sha256 != EXPECTED_V1_CORPUS_SHA256:
            raise ContractValidationError("v2 must reference the exact frozen v1 canonical SHA")
        if self.frozen_v1_references != EXPECTED_V1_REFERENCE_LINKS:
            raise ContractValidationError("v2 must reference, not copy, the exact five v1 cases")
        if self.case_set_id != FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2.case_set_id:
            raise ContractValidationError("v2 corpus must reference the frozen v2 case set")
        expected_human_ids = ORTHOGONAL_PROBE_IDS + PRECEDENCE_PROBE_IDS
        if self.human_probe_ids != expected_human_ids or len(set(self.human_probe_ids)) != 18:
            raise ContractValidationError("v2 human probe membership is not exactly eleven plus seven")
        expected_fingerprints = tuple(
            probe.probe_fingerprint for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
        )
        if self.probe_fingerprints != expected_fingerprints:
            raise ContractValidationError("derived fingerprints must correspond to the human probes")
        if len(set(self.probe_fingerprints)) != 18:
            raise ContractValidationError("derived probe fingerprints must be unique")
        if self.probe_design_id != FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.probe_design_id:
            raise ContractValidationError("corpus must reference the frozen probe design")
        if 5 + 11 + 7 != self.total_membership:
            raise ContractValidationError("composite corpus membership must be exactly 23")
        actual_corpus_id = getattr(FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1, "corpus_id", None)
        if actual_corpus_id != self.predecessor_corpus_id:
            raise ContractValidationError("imported frozen v1 corpus ID differs from the reference")
        if frozen_corpus_v1_canonical_sha256() != self.predecessor_canonical_sha256:
            raise ContractValidationError("imported frozen v1 corpus SHA differs from the reference")
        actual_links = tuple(
            FrozenV1ReferenceLink(
                case_name=case.case_name,
                case_id=case.case_id,
                reference_id=case.reference.reference_id,
            )
            for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
        )
        if actual_links != self.frozen_v1_references:
            raise ContractValidationError("imported frozen v1 case/reference IDs differ")
        payload = self.model_dump(mode="json", exclude={"corpus_id"})
        expected = stable_contract_id("cedparitycorpusv2", payload)
        if self.corpus_id is None:
            object.__setattr__(self, "corpus_id", expected)
        elif self.corpus_id != expected:
            raise ContractValidationError("v2 corpus_id does not match payload")
        return self


FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2 = CanonicalSuccessorParityCorpusV2(
    predecessor_corpus_id=EXPECTED_V1_CORPUS_ID,
    predecessor_canonical_sha256=EXPECTED_V1_CORPUS_SHA256,
    frozen_v1_references=EXPECTED_V1_REFERENCE_LINKS,
    case_set_id=FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2.case_set_id,
    probe_design_id=FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.probe_design_id,
    human_probe_ids=ORTHOGONAL_PROBE_IDS + PRECEDENCE_PROBE_IDS,
    probe_fingerprints=tuple(
        probe.probe_fingerprint for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    ),
)


def frozen_corpus_v2_canonical_sha256() -> str:
    """Return the canonical digest of the immutable reference-only v2 corpus."""

    payload = FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2.model_dump(
        mode="json", exclude={"corpus_id"}
    )
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


__all__ = (
    "CanonicalSuccessorParityCorpusV2",
    "CanonicalSuccessorParityCaseSetV2",
    "CanonicalSuccessorProbeV2",
    "CanonicalValidationOrder",
    "CanonicalValidationStep",
    "CompatibilityDiagnosticsContract",
    "FailureLayer",
    "FailurePrecedenceContract",
    "FailurePrecedenceModel",
    "FailureTaxonomyContract",
    "FailureTaxonomyEntry",
    "FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1",
    "FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1",
    "FROZEN_CANONICAL_FAILURE_TAXONOMY_V1",
    "FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2",
    "FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2",
    "FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1",
    "FROZEN_CANONICAL_SUCCESSOR_PROBES_V2",
    "FROZEN_CANONICAL_VALIDATION_ORDER_V2",
    "FrozenV1ReferenceLink",
    "GuardEvaluation",
    "GuardEvaluationState",
    "InvariantState",
    "ObservationSubmissionState",
    "ORTHOGONAL_PROBE_IDS",
    "PRECEDENCE_PROBE_IDS",
    "ProbeClass",
    "ProbeDesignContract",
    "ProbeInvariantVector",
    "ProbeLiteralMutation",
    "ProbeStage",
    "frozen_corpus_v2_canonical_sha256",
)

"""Frozen evaluator-side case design for acquisition-contract v0.

This module is deliberately data-only.  It contains expected labels, mutation
vectors, case membership, and thresholds for the canned acquisition experiment.
The acquisition runtime must never import it.  Importing this module does not
invoke a transport, inspect credentials, access the network, call a provider,
apply an observation, build an aggregate, or publish an artifact.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from types import MappingProxyType
from typing import Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .acquisition_contracts import (
    ACQUISITION_GUARD_ORDER,
    AcquisitionAttemptOutcome,
    AcquisitionFailureCode,
    AcquisitionGuardId,
    AcquisitionGuardStage,
    AcquisitionGuardState,
    FROZEN_ACQUISITION_FAILURE_TAXONOMY,
    FROZEN_ACQUISITION_VALIDATION_ORDER,
)
from .acquisition_isolation_evidence import (
    FROZEN_ACQUISITION_ISOLATION_RUNTIME_DIGESTS_V0,
    acquisition_isolation_mutation_digest_v0,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id


ACQUISITION_MUTATION_VECTOR_SCHEMA_V0 = (
    "socrateszero-acquisition-mutation-vector/v0"
)
ACQUISITION_GUARD_DESIGN_SCHEMA_V0 = "socrateszero-acquisition-guard-design/v0"
ACQUISITION_LITERAL_MUTATION_SCHEMA_V0 = (
    "socrateszero-acquisition-literal-mutation/v0"
)
ACQUISITION_POSITIVE_CASE_SCHEMA_V0 = (
    "socrateszero-acquisition-positive-case/v0"
)
ACQUISITION_PROBE_SCHEMA_V0 = "socrateszero-acquisition-probe/v0"
ACQUISITION_CASE_SET_SCHEMA_V0 = "socrateszero-acquisition-canned-case-set/v0"
ACQUISITION_THRESHOLDS_SCHEMA_V0 = "socrateszero-acquisition-thresholds/v0"
ACQUISITION_HARNESS_ID_V0 = "socrateszero-acquisition-harness/v0"


class _FrozenCaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AcquisitionCaseClass(str, Enum):
    POSITIVE = "POSITIVE"
    ORTHOGONAL = "ORTHOGONAL"
    PRECEDENCE = "PRECEDENCE"


class MutationState(str, Enum):
    PRESERVED = "PRESERVED"
    INTENTIONALLY_CHANGED = "INTENTIONALLY_CHANGED"
    DEPENDENTLY_CHANGED = "DEPENDENTLY_CHANGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AcquisitionMutationVectorV0(_FrozenCaseContract):
    """Measured relations for one probe; this is not a failure taxonomy."""

    schema_version: Literal[
        ACQUISITION_MUTATION_VECTOR_SCHEMA_V0
    ] = ACQUISITION_MUTATION_VECTOR_SCHEMA_V0
    request_integrity: MutationState
    semantic_request_identity: MutationState
    prompt_bytes: MutationState
    provider: MutationState
    model: MutationState
    configuration: MutationState
    capability_controls: MutationState
    transport_mode: MutationState
    external_network: MutationState
    credential_access: MutationState
    fallback: MutationState
    retry: MutationState
    sdk_internal_retry: MutationState
    tools: MutationState
    timeout: MutationState
    worker_termination: MutationState
    budget: MutationState
    response_presence: MutationState
    response_digest: MutationState
    usage_completeness: MutationState
    resource_receipt: MutationState
    canned_invocation_accounting: MutationState
    transport_registration: MutationState
    branch_isolation: MutationState
    retention: MutationState
    receipt_identity: MutationState
    future_label_status: MutationState


MUTATION_VECTOR_FIELD_NAMES: Tuple[str, ...] = tuple(
    name
    for name in AcquisitionMutationVectorV0.model_fields
    if name != "schema_version"
)


class AcquisitionLiteralMutationV0(_FrozenCaseContract):
    schema_version: Literal[
        ACQUISITION_LITERAL_MUTATION_SCHEMA_V0
    ] = ACQUISITION_LITERAL_MUTATION_SCHEMA_V0
    path: str = Field(min_length=1)
    before_json: str
    after_json: str
    independent_authoritative_input: bool = True

    @field_validator("before_json", "after_json")
    @classmethod
    def canonical_json_literal(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ContractValidationError("mutation literal must be valid JSON") from exc
        if canonical_json(parsed) != value:
            raise ContractValidationError("mutation literal must be canonical JSON")
        return value


class AcquisitionGuardDesignStepV0(_FrozenCaseContract):
    schema_version: Literal[
        ACQUISITION_GUARD_DESIGN_SCHEMA_V0
    ] = ACQUISITION_GUARD_DESIGN_SCHEMA_V0
    order_index: int = Field(ge=1, le=34, strict=True)
    guard_id: AcquisitionGuardId
    stage: AcquisitionGuardStage
    check: str = Field(min_length=3)
    failure_codes: Tuple[AcquisitionFailureCode, ...] = Field(min_length=1)
    independently_probeable: bool

    @field_validator("failure_codes")
    @classmethod
    def unique_failure_codes(
        cls, value: Tuple[AcquisitionFailureCode, ...]
    ) -> Tuple[AcquisitionFailureCode, ...]:
        if len(value) != len(set(value)):
            raise ContractValidationError("guard failure codes must be unique")
        return value


class AcquisitionGuardExpectationV0(_FrozenCaseContract):
    guard_id: AcquisitionGuardId
    state: AcquisitionGuardState


def _guard(value: str) -> AcquisitionGuardId:
    return AcquisitionGuardId(value)


def _stage(value: str) -> AcquisitionGuardStage:
    return AcquisitionGuardStage(value)


def _state(value: str) -> AcquisitionGuardState:
    return AcquisitionGuardState(value)


def _failure(value: str) -> AcquisitionFailureCode:
    return AcquisitionFailureCode(value)


def _outcome(value: str) -> AcquisitionAttemptOutcome:
    return AcquisitionAttemptOutcome(value)


_GUARD_ROWS: Tuple[
    Tuple[str, str, str, Tuple[str, ...], bool], ...
] = (
    ("P01_REQUEST_INTEGRITY", "PRE_DISPATCH", "request integrity", ("INVALID_ACQUISITION_REQUEST",), True),
    ("P02_SEMANTIC_IDENTITY_INTEGRITY", "PRE_DISPATCH", "semantic identity integrity", ("INVALID_SEMANTIC_IDENTITY", "IDENTITY_COLLISION"), True),
    ("P03_CAPABILITY_SNAPSHOT_INTEGRITY", "PRE_DISPATCH", "capability snapshot integrity", ("INVALID_CAPABILITY_SNAPSHOT",), True),
    ("P04_REQUIRED_CONTROL_COMPLETENESS", "PRE_DISPATCH", "required-control completeness", ("REQUIRED_CONTROL_UNKNOWN",), True),
    ("P05_CANNED_ONLY_TRANSPORT_MODE", "PRE_DISPATCH", "canned-only transport mode", ("CANNED_ONLY_POLICY_VIOLATION",), True),
    ("P06_EXTERNAL_NETWORK_PROHIBITION", "PRE_DISPATCH", "external-network prohibition", ("EXTERNAL_NETWORK_FORBIDDEN",), True),
    ("P07_CREDENTIAL_ACCESS_PROHIBITION", "PRE_DISPATCH", "credential-access prohibition", ("CREDENTIAL_ACCESS_FORBIDDEN",), True),
    ("P08_EXACT_IDENTITY_VERIFICATION", "PRE_DISPATCH", "exact provider/model/configuration verification capability", ("EXACT_IDENTITY_VERIFICATION_UNAVAILABLE",), True),
    ("P09_FALLBACK_DISABLED", "PRE_DISPATCH", "fallback disabled", ("FALLBACK_CONTROL_UNPROVEN",), True),
    ("P10_RETRY_DISABLED", "PRE_DISPATCH", "explicit and adapter retries disabled", ("RETRY_CONTROL_UNPROVEN",), True),
    ("P11_SDK_INTERNAL_RETRY_DISABLED", "PRE_DISPATCH", "SDK and hidden retries disabled", ("SDK_INTERNAL_RETRY_CONTROL_UNPROVEN",), True),
    ("P12_TOOLS_DISABLED", "PRE_DISPATCH", "tools disabled", ("TOOLS_NOT_DISABLED",), True),
    ("P13_TIMEOUT_WORKER_TERMINATION", "PRE_DISPATCH", "timeout and worker termination guarantee", ("TIMEOUT_CANCELLATION_UNPROVEN",), True),
    ("P14_RESOURCE_ACCOUNTING", "PRE_DISPATCH", "resource-accounting completeness", ("RESOURCE_ACCOUNTING_INCOMPLETE",), True),
    ("P15_BUDGET_SUFFICIENCY", "PRE_DISPATCH", "budget sufficiency", ("BUDGET_INCOMPLETE",), True),
    ("P16_PROMPT_BYTE_DETERMINISM", "PRE_DISPATCH", "prompt-byte determinism", ("PROMPT_ENTROPY_DETECTED",), True),
    ("P17_ISOLATION_PRECONDITIONS", "PRE_DISPATCH", "branch/isolation preconditions", ("ISOLATION_PRECONDITION_FAILED",), True),
    ("P18_CANNED_TRANSPORT_REGISTRATION", "PRE_DISPATCH", "canned-transport registration", ("CANNED_TRANSPORT_UNREGISTERED",), True),
    ("A01_CANNED_INVOCATION_COUNT", "POST_DISPATCH", "canned invocation count integrity", ("UNCOUNTED_CANNED_INVOCATION",), True),
    ("A02_TRANSPORT_COMPLETION", "POST_DISPATCH", "transport completion", ("TRANSPORT_TIMEOUT", "TRANSPORT_ERROR"), True),
    ("A03_TIMEOUT_WORKER_TERMINATION", "POST_DISPATCH", "timeout worker termination", ("TRANSPORT_WORKER_NOT_TERMINATED",), True),
    ("A04_ACTUAL_PROVIDER_IDENTITY", "POST_DISPATCH", "actual provider identity", ("ACTUAL_PROVIDER_MISMATCH",), True),
    ("A05_ACTUAL_MODEL_IDENTITY", "POST_DISPATCH", "actual model identity", ("ACTUAL_MODEL_MISMATCH",), True),
    ("A06_ACTUAL_CONFIGURATION_IDENTITY", "POST_DISPATCH", "actual configuration identity", ("ACTUAL_CONFIGURATION_MISMATCH",), True),
    ("A07_FALLBACK_ACTIVATION", "POST_DISPATCH", "fallback activation", ("FALLBACK_ACTIVATED",), True),
    ("A08_RETRY_ACTIVATION", "POST_DISPATCH", "retry activation", ("RETRY_ACTIVATED",), True),
    ("A09_TOOL_ACTIVATION", "POST_DISPATCH", "tool activation", ("TOOL_ACTIVATED",), True),
    ("A10_RAW_RESPONSE_PRESENCE", "POST_DISPATCH", "raw response presence", ("MISSING_RAW_OBSERVATION",), True),
    ("A11_RESPONSE_DIGEST_INTEGRITY", "POST_DISPATCH", "response digest integrity", ("INVALID_RESPONSE_DIGEST",), True),
    ("A12_USAGE_COMPLETENESS", "POST_DISPATCH", "usage completeness and false-zero rejection", ("USAGE_INCOMPLETE",), True),
    ("A13_RESOURCE_RECEIPT_INTEGRITY", "POST_DISPATCH", "resource receipt integrity", ("RESOURCE_RECEIPT_MISMATCH",), True),
    ("A14_ISOLATION_INTEGRITY", "POST_DISPATCH", "isolation integrity", ("ISOLATION_FAILURE",), True),
    ("A15_RETENTION_PRIVACY_INTEGRITY", "POST_DISPATCH", "retention/privacy integrity", ("RETENTION_POLICY_VIOLATION",), True),
    ("A16_FINAL_RECEIPT_INTEGRITY", "POST_DISPATCH", "final receipt integrity", ("RECEIPT_MISMATCH",), True),
)


FROZEN_ACQUISITION_GUARD_DESIGN_V0: Tuple[
    AcquisitionGuardDesignStepV0, ...
] = tuple(
    AcquisitionGuardDesignStepV0(
        order_index=index,
        guard_id=_guard(guard_id),
        stage=_stage(stage),
        check=check,
        failure_codes=tuple(_failure(code) for code in failure_codes),
        independently_probeable=independent,
    )
    for index, (guard_id, stage, check, failure_codes, independent) in enumerate(
        _GUARD_ROWS, start=1
    )
)

EXPECTED_ACQUISITION_GUARD_IDS_V0: Tuple[AcquisitionGuardId, ...] = tuple(
    step.guard_id for step in FROZEN_ACQUISITION_GUARD_DESIGN_V0
)

if EXPECTED_ACQUISITION_GUARD_IDS_V0 != ACQUISITION_GUARD_ORDER:
    raise ContractValidationError("case design and acquisition guard order differ")
for designed, authoritative in zip(
    FROZEN_ACQUISITION_GUARD_DESIGN_V0,
    FROZEN_ACQUISITION_VALIDATION_ORDER.steps,
):
    if (
        designed.guard_id != authoritative.guard_id
        or designed.stage != authoritative.stage
        or set(designed.failure_codes) != set(authoritative.allowed_failure_codes)
    ):
        raise ContractValidationError(
            "case guard design differs from authoritative acquisition contracts"
        )
if {
    entry.code for entry in FROZEN_ACQUISITION_FAILURE_TAXONOMY.entries
} != set(AcquisitionFailureCode):
    raise ContractValidationError("authoritative acquisition taxonomy is incomplete")


P = MutationState.PRESERVED
I = MutationState.INTENTIONALLY_CHANGED
D = MutationState.DEPENDENTLY_CHANGED
N = MutationState.NOT_APPLICABLE


def _vector(**changes: MutationState) -> AcquisitionMutationVectorV0:
    unknown = set(changes) - set(MUTATION_VECTOR_FIELD_NAMES)
    if unknown:
        raise ContractValidationError(
            f"unknown acquisition mutation-vector fields: {sorted(unknown)!r}"
        )
    values = {name: P for name in MUTATION_VECTOR_FIELD_NAMES}
    values.update(changes)
    return AcquisitionMutationVectorV0(**values)


def _mutation(
    path: str,
    before: object,
    after: object,
    *,
    independent: bool = True,
) -> AcquisitionLiteralMutationV0:
    return AcquisitionLiteralMutationV0(
        path=path,
        before_json=canonical_json(before),
        after_json=canonical_json(after),
        independent_authoritative_input=independent,
    )


def _guard_trace(target: str) -> Tuple[AcquisitionGuardExpectationV0, ...]:
    target_id = _guard(target)
    positions = {
        step.guard_id: index
        for index, step in enumerate(FROZEN_ACQUISITION_GUARD_DESIGN_V0)
    }
    target_index = positions[target_id]
    trace = []
    for index, step in enumerate(FROZEN_ACQUISITION_GUARD_DESIGN_V0):
        if index < target_index:
            state = _state("PASSED")
        elif index == target_index:
            state = _state("FAILED")
        else:
            state = _state("NOT_REACHED")
        trace.append(AcquisitionGuardExpectationV0(guard_id=step.guard_id, state=state))
    return tuple(trace)


# Frozen safe research bytes.  These are a generic canned request fixture, not a
# reconstruction of a provider SDK request and not authority to contact one.
FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0 = canonical_json(
    {
        "max_output_tokens": 256,
        "messages": [
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
        ],
        "metadata": {},
        "response_format": {"type": "text"},
        "temperature": 0.0,
        "tools": [],
    }
).encode("utf-8")
FROZEN_PROVIDER_VISIBLE_REQUEST_SHA256_V0 = hashlib.sha256(
    FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0
).hexdigest()
FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0 = (
    b'{"kind":"canned","text":"What do you mean by knowledge?"}'
)
FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0 = hashlib.sha256(
    FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0
).hexdigest()
FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0 = (
    b"\x00\xff{not canonical Socratic JSON\x80"
)
FROZEN_OPAQUE_INVALID_RAW_RESPONSE_SHA256_V0 = hashlib.sha256(
    FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0
).hexdigest()

FROZEN_BASELINE_CAPABILITY_FIXTURE_V0: Mapping[str, object] = MappingProxyType({
    "transport_mode": "CANNED_ONLY",
    "external_network": "PROVEN_DISABLED",
    "credential_access": "PROVEN_DISABLED",
    "actual_provider_identity_verification": "PROVEN_SUPPORTED",
    "actual_model_identity_verification": "PROVEN_SUPPORTED",
    "fallback": "PROVEN_DISABLED",
    "retry": "PROVEN_DISABLED",
    "sdk_internal_retry": "PROVEN_DISABLED",
    "tools": "PROVEN_DISABLED",
    "timeout_cancellation": "PROVEN_SUPPORTED",
    "worker_termination": "PROVEN_SUPPORTED",
    "raw_response_capture": "PROVEN_SUPPORTED",
    "usage_reporting": "PROVEN_SUPPORTED",
    "token_reporting": "PROVEN_SUPPORTED",
    "cost_reporting": "PROVEN_SUPPORTED",
    "seed": "PROVEN_UNSUPPORTED",
})
FROZEN_BASELINE_CONTROL_POLICY_FIXTURE_V0: Mapping[str, object] = MappingProxyType({
    "fallback_activations": 0,
    "max_canned_transport_invocations_per_attempt": 1,
    "max_credential_access_attempts": 0,
    "max_external_network_attempts": 0,
    "max_live_provider_calls": 0,
    "max_model_executions": 0,
    "max_new_cost_microusd": 0,
    "max_new_tokens": 0,
    "max_tool_calls": 0,
    "retry_activations": 0,
    "timeout_ms": 5000,
})
FROZEN_BASELINE_SEMANTIC_REQUEST_FIXTURE_V0: Mapping[str, object] = MappingProxyType({
    "action_id": (
        "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
    ),
    "contract_version": "socrateszero-external-observation-acquisition/v0",
    "fallback_count": 0,
    "max_output_tokens": 256,
    "prompt_sha256": FROZEN_PROVIDER_VISIBLE_REQUEST_SHA256_V0,
    "requested_model_id": "phase8-recorded-model/1",
    "requested_provider_id": "phase8-recorded-seat-1",
    "retry_count": 0,
    "root_capsule_id": (
        "cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50"
    ),
    "seed_status": "PROVEN_UNSUPPORTED",
    "temperature": 0.0,
    "timeout_ms": 5000,
    "tools_enabled": False,
})


class AcquisitionPositiveCaseV0(_FrozenCaseContract):
    schema_version: Literal[
        ACQUISITION_POSITIVE_CASE_SCHEMA_V0
    ] = ACQUISITION_POSITIVE_CASE_SCHEMA_V0
    case_id: str = Field(pattern=r"^acqv0-s[0-9]{2}-[a-z0-9-]+$")
    case_fingerprint: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    purpose: str = Field(min_length=3)
    fixture_refs: Tuple[str, ...] = Field(min_length=1)
    attempt_count: int = Field(ge=1, le=2, strict=True)
    expected_canned_invocations: int = Field(ge=1, le=2, strict=True)
    expected_outcome: AcquisitionAttemptOutcome
    required_assertions: Tuple[str, ...] = Field(min_length=1)

    @field_validator("fixture_refs", "required_assertions")
    @classmethod
    def sorted_unique_nonblank(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ContractValidationError("positive-case strings must be nonblank")
        if value != tuple(sorted(set(value))):
            raise ContractValidationError("positive-case tuples must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionPositiveCaseV0":
        if self.expected_canned_invocations != self.attempt_count:
            raise ContractValidationError("every positive attempt invokes canned transport once")
        payload = self.model_dump(mode="json", exclude={"case_fingerprint"})
        expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        if self.case_fingerprint is not None and self.case_fingerprint != expected:
            raise ContractValidationError("positive case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


class AcquisitionProbeV0(_FrozenCaseContract):
    schema_version: Literal[ACQUISITION_PROBE_SCHEMA_V0] = ACQUISITION_PROBE_SCHEMA_V0
    probe_id: str = Field(pattern=r"^acqv0-[op][0-9]{2}-[a-z0-9-]+$")
    probe_fingerprint: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    probe_class: AcquisitionCaseClass
    stage: AcquisitionGuardStage
    construction_rule: str = Field(min_length=3)
    literal_mutations: Tuple[AcquisitionLiteralMutationV0, ...] = Field(min_length=1)
    mutation_vector: AcquisitionMutationVectorV0
    expected_primary_failure: AcquisitionFailureCode
    expected_guard_id: AcquisitionGuardId
    expected_guard_trace: Tuple[AcquisitionGuardExpectationV0, ...] = Field(
        min_length=34, max_length=34
    )
    expected_attempt_receipts: Literal[1] = 1
    expected_canned_invocations: Literal[0, 1]
    independently_probeable: bool

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionProbeV0":
        expected_class = (
            AcquisitionCaseClass.ORTHOGONAL
            if "-o" in self.probe_id
            else AcquisitionCaseClass.PRECEDENCE
        )
        if self.probe_class is not expected_class:
            raise ContractValidationError("probe ID and class differ")
        guard_step = next(
            step
            for step in FROZEN_ACQUISITION_GUARD_DESIGN_V0
            if step.guard_id == self.expected_guard_id
        )
        if self.stage != guard_step.stage:
            raise ContractValidationError("probe stage differs from expected guard stage")
        if self.expected_primary_failure not in guard_step.failure_codes:
            raise ContractValidationError("probe failure is not owned by expected guard")
        if tuple(item.guard_id for item in self.expected_guard_trace) != (
            EXPECTED_ACQUISITION_GUARD_IDS_V0
        ):
            raise ContractValidationError("probe guard-trace coverage is not exact")
        failed = tuple(
            item.guard_id
            for item in self.expected_guard_trace
            if item.state == _state("FAILED")
        )
        if failed != (self.expected_guard_id,):
            raise ContractValidationError("probe must freeze exactly one primary guard")
        expected_dispatches = 0 if self.stage == _stage("PRE_DISPATCH") else 1
        if self.expected_canned_invocations != expected_dispatches:
            raise ContractValidationError("probe canned invocation count contradicts stage")
        payload = self.model_dump(mode="json", exclude={"probe_fingerprint"})
        expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        if self.probe_fingerprint is not None and self.probe_fingerprint != expected:
            raise ContractValidationError("probe fingerprint mismatch")
        object.__setattr__(self, "probe_fingerprint", expected)
        return self


def _positive(
    case_id: str,
    purpose: str,
    *,
    attempts: int,
    fixture_refs: Tuple[str, ...],
    assertions: Tuple[str, ...],
) -> AcquisitionPositiveCaseV0:
    return AcquisitionPositiveCaseV0(
        case_id=case_id,
        purpose=purpose,
        fixture_refs=tuple(sorted(fixture_refs)),
        attempt_count=attempts,
        expected_canned_invocations=attempts,
        expected_outcome=_outcome("ACQUIRED"),
        required_assertions=tuple(sorted(assertions)),
    )


def _probe(
    probe_id: str,
    probe_class: AcquisitionCaseClass,
    guard_id: str,
    failure: str,
    construction_rule: str,
    mutations: Tuple[AcquisitionLiteralMutationV0, ...],
    vector: AcquisitionMutationVectorV0,
) -> AcquisitionProbeV0:
    stage = next(
        step.stage
        for step in FROZEN_ACQUISITION_GUARD_DESIGN_V0
        if step.guard_id == _guard(guard_id)
    )
    return AcquisitionProbeV0(
        probe_id=probe_id,
        probe_class=probe_class,
        stage=stage,
        construction_rule=construction_rule,
        literal_mutations=mutations,
        mutation_vector=vector,
        expected_primary_failure=_failure(failure),
        expected_guard_id=_guard(guard_id),
        expected_guard_trace=_guard_trace(guard_id),
        expected_canned_invocations=(0 if stage == _stage("PRE_DISPATCH") else 1),
        independently_probeable=(probe_class is AcquisitionCaseClass.ORTHOGONAL),
    )


FROZEN_ACQUISITION_POSITIVE_CASES_V0: Tuple[AcquisitionPositiveCaseV0, ...] = (
    _positive(
        "acqv0-s01-complete-deterministic",
        "one complete deterministic canned acquisition with exact identities and receipts",
        attempts=1,
        fixture_refs=("baseline-capability", "baseline-request", "complete-response"),
        assertions=("complete_receipt", "raw_bytes_recoverable", "resource_usage_complete"),
    ),
    _positive(
        "acqv0-s02-content-opaque-invalid-json",
        "parser-invalid raw content remains an acquisition success because content is opaque",
        attempts=1,
        fixture_refs=("baseline-capability", "baseline-request", "opaque-invalid-response"),
        assertions=("acquired", "canonical_application_not_invoked", "content_not_parsed"),
    ),
    _positive(
        "acqv0-s03-sibling-byte-identity",
        "two sibling branches preserve semantic and provider-visible byte identity",
        attempts=2,
        fixture_refs=("baseline-request", "complete-response", "sibling-a", "sibling-b"),
        assertions=("branch_ids_distinct", "prompt_bytes_equal", "semantic_request_ids_equal", "transport_attempt_ids_distinct"),
    ),
    _positive(
        "acqv0-s04-repeat-semantic-identity",
        "repeated semantic inputs reproduce the semantic request identity",
        attempts=2,
        fixture_refs=("baseline-request", "complete-response", "repeat-ordinal-0", "repeat-ordinal-1"),
        assertions=("prompt_bytes_equal", "semantic_request_ids_equal", "transport_attempt_ids_distinct"),
    ),
    _positive(
        "acqv0-s05-seed-explicitly-unsupported",
        "known unsupported seed state is accepted and never treated as UNKNOWN",
        attempts=1,
        fixture_refs=("baseline-capability", "baseline-request", "complete-response"),
        assertions=("required_controls_complete", "seed_explicitly_unsupported"),
    ),
    _positive(
        "acqv0-s06-historical-usage-unknown",
        "historical usage remains UNKNOWN while new canned usage is complete and known",
        attempts=1,
        fixture_refs=("baseline-request", "complete-response", "historical-usage-unknown"),
        assertions=("historical_usage_unknown", "new_usage_known_complete", "no_false_zero"),
    ),
)


O = AcquisitionCaseClass.ORTHOGONAL
X = AcquisitionCaseClass.PRECEDENCE
_BASE_SEMANTIC_ID = (
    "szacqrequest_b005c6c56dd4eeff795c7dd2427218ee01c28cba7cf6ea932a0d7b9a064c4ee1"
)
_BASE_CONFIG = "c7cbccd7066a0d9c657932ce183f5e18821586fa1a7890f2f14d8efff0987d84"
_WRONG_CONFIG = "3" * 64
_BASE_RAW_DIGEST = FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0
_ISOLATION_RUNTIME_DIGESTS = dict(
    FROZEN_ACQUISITION_ISOLATION_RUNTIME_DIGESTS_V0
)
_BASE_SOURCE_ISOLATION_DIGEST = _ISOLATION_RUNTIME_DIGESTS["source"]
_BASE_SIBLING_ISOLATION_DIGEST = _ISOLATION_RUNTIME_DIGESTS["sibling"]
_BASE_PRODUCTION_ISOLATION_DIGEST = _ISOLATION_RUNTIME_DIGESTS["production"]
_MUTATED_SOURCE_ISOLATION_DIGEST = acquisition_isolation_mutation_digest_v0(
    "source"
)
_MUTATED_SIBLING_ISOLATION_DIGEST = acquisition_isolation_mutation_digest_v0(
    "sibling"
)
_MUTATED_PRODUCTION_ISOLATION_DIGEST = acquisition_isolation_mutation_digest_v0(
    "production"
)


FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0: Tuple[AcquisitionProbeV0, ...] = (
    _probe("acqv0-o01-invalid-request", O, "P01_REQUEST_INTEGRITY", "INVALID_ACQUISITION_REQUEST", "Change only the request schema version.", (_mutation("request.schema_version", "socrateszero-acquisition-semantic-request/v0", "socrateszero-acquisition-semantic-request/v999"),), _vector(request_integrity=I)),
    _probe("acqv0-o02-semantic-id-tamper", O, "P02_SEMANTIC_IDENTITY_INTEGRITY", "INVALID_SEMANTIC_IDENTITY", "Tamper only the stored semantic request ID.", (_mutation("request.semantic_request_id", _BASE_SEMANTIC_ID, "szacqrequest_" + "0" * 64),), _vector(semantic_request_identity=I)),
    _probe("acqv0-o03-required-provider-verification-unknown", O, "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN", "Set only required actual-provider verification capability to UNKNOWN.", (_mutation("capability.actual_provider_identity_verification", "PROVEN_SUPPORTED", "UNKNOWN"),), _vector(semantic_request_identity=D, capability_controls=I)),
    _probe("acqv0-o04-non-canned-transport", O, "P05_CANNED_ONLY_TRANSPORT_MODE", "CANNED_ONLY_POLICY_VIOLATION", "Change only transport mode from CANNED_ONLY to EXTERNAL.", (_mutation("capability.transport_mode", "CANNED_ONLY", "EXTERNAL"),), _vector(semantic_request_identity=D, capability_controls=D, transport_mode=I)),
    _probe("acqv0-o05-external-network-enabled", O, "P06_EXTERNAL_NETWORK_PROHIBITION", "EXTERNAL_NETWORK_FORBIDDEN", "Keep canned mode but change only external-network control to enabled.", (_mutation("capability.external_network", "PROVEN_DISABLED", "PROVEN_SUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, external_network=I)),
    _probe("acqv0-o06-credential-access-enabled", O, "P07_CREDENTIAL_ACCESS_PROHIBITION", "CREDENTIAL_ACCESS_FORBIDDEN", "Change only credential-access control to enabled without reading a credential.", (_mutation("capability.credential_access", "PROVEN_DISABLED", "PROVEN_SUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, credential_access=I)),
    _probe("acqv0-o07-exact-model-verification-unsupported", O, "P08_EXACT_IDENTITY_VERIFICATION", "EXACT_IDENTITY_VERIFICATION_UNAVAILABLE", "Change only actual exact-model verification to explicitly unsupported.", (_mutation("capability.actual_model_identity_verification", "PROVEN_SUPPORTED", "PROVEN_UNSUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=I)),
    _probe("acqv0-o08-fallback-disablement-unknown", O, "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN", "Change only fallback control from proven disabled to UNKNOWN.", (_mutation("capability.fallback", "PROVEN_DISABLED", "UNKNOWN"),), _vector(semantic_request_identity=D, capability_controls=D, fallback=I)),
    _probe("acqv0-o09-retry-disablement-unknown", O, "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN", "Change only runner retry control from proven disabled to UNKNOWN.", (_mutation("capability.retry", "PROVEN_DISABLED", "UNKNOWN"),), _vector(semantic_request_identity=D, capability_controls=D, retry=I)),
    _probe("acqv0-o10-sdk-retry-disablement-unknown", O, "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN", "Change only SDK-internal retry control from proven disabled to UNKNOWN.", (_mutation("capability.sdk_internal_retry", "PROVEN_DISABLED", "UNKNOWN"),), _vector(semantic_request_identity=D, capability_controls=D, sdk_internal_retry=I)),
    _probe("acqv0-o11-tools-enabled", O, "P12_TOOLS_DISABLED", "TOOLS_NOT_DISABLED", "Change only the tool-exposure capability to enabled.", (_mutation("capability.tools", "PROVEN_DISABLED", "PROVEN_SUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, tools=I)),
    _probe("acqv0-o12-timeout-termination-unknown", O, "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN", "Change only worker-termination guarantee to UNKNOWN.", (_mutation("capability.worker_termination", "PROVEN_SUPPORTED", "UNKNOWN"),), _vector(semantic_request_identity=D, capability_controls=D, worker_termination=I)),
    _probe("acqv0-o13-resource-accounting-incomplete", O, "P14_RESOURCE_ACCOUNTING", "RESOURCE_ACCOUNTING_INCOMPLETE", "Change only cost-reporting capability to explicitly unsupported.", (_mutation("capability.cost_reporting", "PROVEN_SUPPORTED", "PROVEN_UNSUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, usage_completeness=I)),
    _probe("acqv0-o14-budget-insufficient", O, "P15_BUDGET_SUFFICIENCY", "BUDGET_INCOMPLETE", "Change only the per-attempt canned-invocation ceiling from one to zero.", (_mutation("budget.max_canned_transport_invocations", 1, 0),), _vector(semantic_request_identity=D, budget=I)),
    _probe("acqv0-o15-prompt-entropy", O, "P16_PROMPT_BYTE_DETERMINISM", "PROMPT_ENTROPY_DETECTED", "Inject only branch identity into rendered provider-visible bytes after semantic request freeze.", (_mutation("renderer.entropy_source", "NONE", "BRANCH_ID"),), _vector(prompt_bytes=I)),
    _probe("acqv0-o16-canned-transport-unregistered", O, "P18_CANNED_TRANSPORT_REGISTRATION", "CANNED_TRANSPORT_UNREGISTERED", "Remove only the exact canned transport registration.", (_mutation("transport_registry.baseline_canned.registered", True, False),), _vector(semantic_request_identity=D, transport_registration=I)),
    _probe("acqv0-o17-uncounted-canned-invocation", O, "A01_CANNED_INVOCATION_COUNT", "UNCOUNTED_CANNED_INVOCATION", "Preserve the transport entry count but omit it from the attempt recorder.", (_mutation("attempt_recorder.canned_transport_invocations", 1, 0),), _vector(canned_invocation_accounting=I, receipt_identity=D)),
    _probe("acqv0-o18-transport-timeout-worker-terminated", O, "A02_TRANSPORT_COMPLETION", "TRANSPORT_TIMEOUT", "Return a deterministic timeout terminal envelope with acknowledged worker termination.", (_mutation("envelope.transport_status", "DELIVERED", "TIMEOUT"),), _vector(timeout=I, response_presence=D, response_digest=N)),
    _probe("acqv0-o19-worker-not-terminated-after-completion", O, "A03_TIMEOUT_WORKER_TERMINATION", "TRANSPORT_WORKER_NOT_TERMINATED", "Keep transport completed but report one non-terminated worker.", (_mutation("envelope.worker_terminated", True, False),), _vector(worker_termination=I)),
    _probe("acqv0-o20-actual-provider-mismatch", O, "A04_ACTUAL_PROVIDER_IDENTITY", "ACTUAL_PROVIDER_MISMATCH", "Change only actual provider identity.", (_mutation("envelope.actual_provider_id", "phase8-recorded-seat-1", "phase8-wrong-seat-1"),), _vector(provider=I)),
    _probe("acqv0-o21-actual-model-mismatch", O, "A05_ACTUAL_MODEL_IDENTITY", "ACTUAL_MODEL_MISMATCH", "Change only actual exact-model identity.", (_mutation("envelope.actual_model_id", "phase8-recorded-model/1", "phase8-recorded-model/1-wrong"),), _vector(model=I)),
    _probe("acqv0-o22-actual-config-mismatch", O, "A06_ACTUAL_CONFIGURATION_IDENTITY", "ACTUAL_CONFIGURATION_MISMATCH", "Change only actual configuration digest.", (_mutation("envelope.actual_configuration_digest", _BASE_CONFIG, _WRONG_CONFIG),), _vector(configuration=I)),
    _probe("acqv0-o23-fallback-activated", O, "A07_FALLBACK_ACTIVATION", "FALLBACK_ACTIVATED", "Change only fallback-used from false to true.", (_mutation("envelope.fallback_used", False, True),), _vector(fallback=I)),
    _probe("acqv0-o24-retry-activated", O, "A08_RETRY_ACTIVATION", "RETRY_ACTIVATED", "Change only retry count from zero to one.", (_mutation("envelope.retry_count", 0, 1),), _vector(retry=I)),
    _probe("acqv0-o25-tool-activated", O, "A09_TOOL_ACTIVATION", "TOOL_ACTIVATED", "Change only tool-call count from zero to one.", (_mutation("envelope.tool_calls", 0, 1),), _vector(tools=I)),
    _probe("acqv0-o26-missing-raw", O, "A10_RAW_RESPONSE_PRESENCE", "MISSING_RAW_OBSERVATION", "Remove only the opaque response from an otherwise complete envelope without placing response bytes in evaluator metadata.", (_mutation("envelope.raw_response_presence", "PRESENT", "ABSENT"),), _vector(response_presence=I, response_digest=N)),
    _probe("acqv0-o27-raw-digest-mismatch", O, "A11_RESPONSE_DIGEST_INTEGRITY", "INVALID_RESPONSE_DIGEST", "Keep raw bytes exact and tamper only the stored digest.", (_mutation("envelope.raw_response_sha256", _BASE_RAW_DIGEST, "f" * 64),), _vector(response_digest=I)),
    _probe("acqv0-o28-usage-incomplete", O, "A12_USAGE_COMPLETENESS", "USAGE_INCOMPLETE", "Change only new-execution usage completeness to INCOMPLETE.", (_mutation("envelope.new_usage_completeness", "COMPLETE", "INCOMPLETE"),), _vector(usage_completeness=I)),
    _probe("acqv0-o29-false-zero-usage", O, "A12_USAGE_COMPLETENESS", "USAGE_INCOMPLETE", "Change only source token knowledge from KNOWN to UNKNOWN while the candidate receipt retains numeric zero.", (_mutation("envelope.usage.tokens.knowledge", "KNOWN", "UNKNOWN"),), _vector(usage_completeness=I, receipt_identity=D)),
    _probe("acqv0-o30-resource-receipt-mismatch", O, "A13_RESOURCE_RECEIPT_INTEGRITY", "RESOURCE_RECEIPT_MISMATCH", "Change only independently recomputed canned invocation total from one to zero.", (_mutation("resource_receipt.canned_transport_invocations", 1, 0),), _vector(resource_receipt=I, receipt_identity=D)),
    _probe("acqv0-o31-source-isolation-mismatch", O, "A14_ISOLATION_INTEGRITY", "ISOLATION_FAILURE", "Change only the test-owned source isolation runtime digest.", (_mutation("isolation_probe.source.runtime_digest", _BASE_SOURCE_ISOLATION_DIGEST, _MUTATED_SOURCE_ISOLATION_DIGEST),), _vector(branch_isolation=I)),
    _probe("acqv0-o32-sibling-isolation-mismatch", O, "A14_ISOLATION_INTEGRITY", "ISOLATION_FAILURE", "Change only the test-owned sibling isolation runtime digest.", (_mutation("isolation_probe.sibling.runtime_digest", _BASE_SIBLING_ISOLATION_DIGEST, _MUTATED_SIBLING_ISOLATION_DIGEST),), _vector(branch_isolation=I)),
    _probe("acqv0-o33-production-isolation-mismatch", O, "A14_ISOLATION_INTEGRITY", "ISOLATION_FAILURE", "Change only the detached production-control isolation runtime digest.", (_mutation("isolation_probe.production.runtime_digest", _BASE_PRODUCTION_ISOLATION_DIGEST, _MUTATED_PRODUCTION_ISOLATION_DIGEST),), _vector(branch_isolation=I)),
    _probe("acqv0-o34-retention-policy-violation", O, "A15_RETENTION_PRIVACY_INTEGRITY", "RETENTION_POLICY_VIOLATION", "Change only the retained artifact-inclusion receipt away from the frozen policy.", (_mutation("retention_receipt.artifact_inclusion", "INCLUDE_RAW_NON_SENSITIVE_RESPONSE", "DIGESTS_AND_REFERENCES"),), _vector(retention=I)),
    _probe("acqv0-o35-final-receipt-identity-mismatch", O, "A16_FINAL_RECEIPT_INTEGRITY", "RECEIPT_MISMATCH", "Change only the independently recomputed final-receipt integrity verdict.", (_mutation("attempt_recorder.final_receipt_integrity", True, False),), _vector(receipt_identity=I)),
    _probe("acqv0-o36-future-label-envelope", O, "A02_TRANSPORT_COMPLETION", "TRANSPORT_ERROR", "Add a forbidden evaluator/future label to the envelope, never to opaque raw response bytes.", (_mutation("envelope.expected_canonical_acceptance", None, "ACCEPTED"),), _vector(future_label_status=I)),
    _probe("acqv0-o37-missing-actual-model", O, "A05_ACTUAL_MODEL_IDENTITY", "ACTUAL_MODEL_MISMATCH", "Omit only the typed actual exact-model identity while preserving actual provider and configuration evidence.", (_mutation("envelope.actual_model_id", "phase8-recorded-model/1", None),), _vector(model=I)),
    _probe("acqv0-o38-fallback-known-adverse", O, "P09_FALLBACK_DISABLED", "FALLBACK_CONTROL_UNPROVEN", "Change only fallback control from proven disabled to the known-adverse supported state.", (_mutation("capability.fallback", "PROVEN_DISABLED", "PROVEN_SUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, fallback=I)),
    _probe("acqv0-o39-retry-known-adverse", O, "P10_RETRY_DISABLED", "RETRY_CONTROL_UNPROVEN", "Change only explicit-retry control from proven disabled to the known-adverse supported state.", (_mutation("capability.retry", "PROVEN_DISABLED", "PROVEN_SUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, retry=I)),
    _probe("acqv0-o40-sdk-hidden-retry-known-adverse", O, "P11_SDK_INTERNAL_RETRY_DISABLED", "SDK_INTERNAL_RETRY_CONTROL_UNPROVEN", "Change only SDK-internal retry control from proven disabled to the known-adverse supported state.", (_mutation("capability.sdk_internal_retry", "PROVEN_DISABLED", "PROVEN_SUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, sdk_internal_retry=I)),
    _probe("acqv0-o41-termination-known-adverse", O, "P13_TIMEOUT_WORKER_TERMINATION", "TIMEOUT_CANCELLATION_UNPROVEN", "Change only worker-termination control from proven supported to the known-adverse unsupported state.", (_mutation("capability.worker_termination", "PROVEN_SUPPORTED", "PROVEN_UNSUPPORTED"),), _vector(semantic_request_identity=D, capability_controls=D, worker_termination=I)),
    _probe("acqv0-o42-isolation-precondition-failed", O, "P17_ISOLATION_PRECONDITIONS", "ISOLATION_PRECONDITION_FAILED", "Change only the test-owned isolation probe precondition verdict before dispatch.", (_mutation("isolation_probe.preconditions_met", True, False),), _vector(branch_isolation=I)),
    _probe("acqv0-o43-valid-capability-snapshot-detached", O, "P03_CAPABILITY_SNAPSHOT_INTEGRITY", "INVALID_CAPABILITY_SNAPSHOT", "Supply a valid, request-linked capability snapshot that is intentionally distinct from the canned transport's immutable snapshot.", (_mutation("capability.snapshot_binding", "MATCHED", "DETACHED_VALID_SNAPSHOT"),), _vector(semantic_request_identity=D, capability_controls=I)),
)


FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0: Tuple[AcquisitionProbeV0, ...] = (
    _probe("acqv0-p01-invalid-request-plus-unknown-capability", X, "P01_REQUEST_INTEGRITY", "INVALID_ACQUISITION_REQUEST", "Change request schema and one required capability; request integrity wins.", (_mutation("request.schema_version", "socrateszero-acquisition-semantic-request/v0", "socrateszero-acquisition-semantic-request/v999"), _mutation("capability.actual_provider_identity_verification", "PROVEN_SUPPORTED", "UNKNOWN")), _vector(request_integrity=I, semantic_request_identity=D, capability_controls=I)),
    _probe("acqv0-p02-unknown-capability-plus-budget-gap", X, "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN", "Change one required capability to UNKNOWN and make the budget insufficient; completeness wins.", (_mutation("capability.actual_provider_identity_verification", "PROVEN_SUPPORTED", "UNKNOWN"), _mutation("budget.max_canned_transport_invocations", 1, 0)), _vector(semantic_request_identity=D, capability_controls=I, budget=I)),
    _probe("acqv0-p03-prompt-entropy-plus-fallback-policy", X, "P09_FALLBACK_DISABLED", "FALLBACK_CONTROL_UNPROVEN", "Enable fallback explicitly and inject prompt entropy; fallback guard wins before prompt determinism.", (_mutation("capability.fallback", "PROVEN_DISABLED", "PROVEN_SUPPORTED"), _mutation("renderer.entropy_source", "NONE", "BRANCH_ID")), _vector(semantic_request_identity=D, capability_controls=D, fallback=I, prompt_bytes=I)),
    _probe("acqv0-p04-actual-model-plus-fallback-activation", X, "A05_ACTUAL_MODEL_IDENTITY", "ACTUAL_MODEL_MISMATCH", "Change actual model and activate fallback; exact-model identity wins.", (_mutation("envelope.actual_model_id", "phase8-recorded-model/1", "phase8-recorded-model/1-wrong"), _mutation("envelope.fallback_used", False, True)), _vector(model=I, fallback=I)),
    _probe("acqv0-p05-missing-raw-plus-usage-incomplete", X, "A10_RAW_RESPONSE_PRESENCE", "MISSING_RAW_OBSERVATION", "Remove the opaque response and make usage incomplete; raw presence wins without placing response bytes in evaluator metadata.", (_mutation("envelope.raw_response_presence", "PRESENT", "ABSENT"), _mutation("envelope.new_usage_completeness", "COMPLETE", "INCOMPLETE")), _vector(response_presence=I, response_digest=N, usage_completeness=I)),
    _probe("acqv0-p06-network-plus-credential-policy", X, "P06_EXTERNAL_NETWORK_PROHIBITION", "EXTERNAL_NETWORK_FORBIDDEN", "Enable external-network and credential-access intent without executing either; network guard wins.", (_mutation("capability.external_network", "PROVEN_DISABLED", "PROVEN_SUPPORTED"), _mutation("capability.credential_access", "PROVEN_DISABLED", "PROVEN_SUPPORTED")), _vector(semantic_request_identity=D, capability_controls=D, external_network=I, credential_access=I)),
    _probe("acqv0-p07-timeout-plus-worker-nontermination", X, "A02_TRANSPORT_COMPLETION", "TRANSPORT_TIMEOUT", "Return timeout status and worker nontermination; transport completion wins.", (_mutation("envelope.transport_status", "DELIVERED", "TIMEOUT"), _mutation("envelope.worker_terminated", True, False)), _vector(timeout=I, worker_termination=I, response_presence=D, response_digest=N)),
)


POSITIVE_CASE_IDS_V0: Tuple[str, ...] = tuple(
    item.case_id for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0
)
ORTHOGONAL_PROBE_IDS_V0: Tuple[str, ...] = tuple(
    item.probe_id for item in FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
)
PRECEDENCE_PROBE_IDS_V0: Tuple[str, ...] = tuple(
    item.probe_id for item in FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
)


class AcquisitionThresholdsV0(_FrozenCaseContract):
    schema_version: Literal[
        ACQUISITION_THRESHOLDS_SCHEMA_V0
    ] = ACQUISITION_THRESHOLDS_SCHEMA_V0
    thresholds_id: Optional[str] = None
    cases_total: Literal[56] = 56
    positive_cases_total: Literal[6] = 6
    required_positive_complete_case_results: Literal[6] = 6
    required_positive_attempt_receipts: Literal[8] = 8
    orthogonal_probes_total: Literal[43] = 43
    required_orthogonal_exact_primary_results: Literal[43] = 43
    precedence_probes_total: Literal[7] = 7
    required_precedence_exact_primary_results: Literal[7] = 7
    required_attempt_receipts_total: Literal[58] = 58
    required_canned_transport_invocations: Literal[32] = 32
    maximum_mismatch_or_failure_count: Literal[0] = 0
    required_invalid_probe_constructions: Literal[0] = 0
    required_semantic_identity_collisions: Literal[0] = 0
    required_prompt_byte_mismatches: Literal[0] = 0
    required_external_network_attempts: Literal[0] = 0
    required_credential_access_attempts: Literal[0] = 0
    required_live_provider_calls: Literal[0] = 0
    required_model_executions: Literal[0] = 0
    required_tool_calls: Literal[0] = 0
    required_uncounted_canned_invocations: Literal[0] = 0
    required_successful_retry_activations: Literal[0] = 0
    required_successful_fallback_activations: Literal[0] = 0
    required_timeout_worker_leaks: Literal[0] = 0
    required_source_mutations: Literal[0] = 0
    required_sibling_mutations: Literal[0] = 0
    required_production_mutations: Literal[0] = 0
    required_accepted_missing_raw_observations: Literal[0] = 0
    required_accepted_false_zero_usage: Literal[0] = 0
    required_incomplete_attempt_receipts: Literal[0] = 0
    required_retention_violations: Literal[0] = 0
    required_receipt_mismatches: Literal[0] = 0
    required_future_label_violations: Literal[0] = 0
    required_canonical_application_invocations: Literal[0] = 0
    required_new_tokens: Literal[0] = 0
    required_new_cost_microusd: Literal[0] = 0
    required_external_provider_wall_time_ms: Literal[0] = 0
    required_historical_lock_mismatches: Literal[0] = 0
    required_core_blob_lock_mismatches: Literal[0] = 0
    production_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def identify(self) -> "AcquisitionThresholdsV0":
        payload = self.model_dump(mode="json", exclude={"thresholds_id"})
        expected = stable_contract_id("acqthresholdsv0", payload)
        if self.thresholds_id is not None and self.thresholds_id != expected:
            raise ContractValidationError("acquisition thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_ACQUISITION_THRESHOLDS_V0 = AcquisitionThresholdsV0()


class AcquisitionCaseSetV0(_FrozenCaseContract):
    schema_version: Literal[
        ACQUISITION_CASE_SET_SCHEMA_V0
    ] = ACQUISITION_CASE_SET_SCHEMA_V0
    case_set_id: Optional[str] = None
    harness_id: Literal[ACQUISITION_HARNESS_ID_V0] = ACQUISITION_HARNESS_ID_V0
    guard_ids: Tuple[AcquisitionGuardId, ...] = Field(min_length=34, max_length=34)
    positive_cases: Tuple[AcquisitionPositiveCaseV0, ...] = Field(min_length=6, max_length=6)
    orthogonal_probes: Tuple[AcquisitionProbeV0, ...] = Field(min_length=43, max_length=43)
    precedence_probes: Tuple[AcquisitionProbeV0, ...] = Field(min_length=7, max_length=7)
    thresholds_id: str
    positive_case_count: Literal[6] = 6
    orthogonal_probe_count: Literal[43] = 43
    precedence_probe_count: Literal[7] = 7
    total_case_count: Literal[56] = 56
    total_attempt_receipts: Literal[58] = 58
    total_canned_transport_invocations: Literal[32] = 32

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AcquisitionCaseSetV0":
        if self.guard_ids != EXPECTED_ACQUISITION_GUARD_IDS_V0:
            raise ContractValidationError("acquisition case-set guard order changed")
        if tuple(item.case_id for item in self.positive_cases) != POSITIVE_CASE_IDS_V0:
            raise ContractValidationError("positive case membership or order changed")
        if tuple(item.probe_id for item in self.orthogonal_probes) != ORTHOGONAL_PROBE_IDS_V0:
            raise ContractValidationError("orthogonal probe membership or order changed")
        if tuple(item.probe_id for item in self.precedence_probes) != PRECEDENCE_PROBE_IDS_V0:
            raise ContractValidationError("precedence probe membership or order changed")
        all_fingerprints = tuple(
            item.case_fingerprint for item in self.positive_cases
        ) + tuple(
            item.probe_fingerprint
            for item in self.orthogonal_probes + self.precedence_probes
        )
        if len(set(all_fingerprints)) != 56:
            raise ContractValidationError("all acquisition case fingerprints must be unique")
        attempts = sum(item.attempt_count for item in self.positive_cases) + len(
            self.orthogonal_probes
        ) + len(self.precedence_probes)
        canned = sum(
            item.expected_canned_invocations for item in self.positive_cases
        ) + sum(
            item.expected_canned_invocations
            for item in self.orthogonal_probes + self.precedence_probes
        )
        if attempts != self.total_attempt_receipts or canned != self.total_canned_transport_invocations:
            raise ContractValidationError("case-set attempt or canned-invocation totals changed")
        if self.thresholds_id != FROZEN_ACQUISITION_THRESHOLDS_V0.thresholds_id:
            raise ContractValidationError("case-set thresholds reference changed")
        payload = self.model_dump(mode="json", exclude={"case_set_id"})
        expected = stable_contract_id("acqcasesetv0", payload)
        if self.case_set_id is not None and self.case_set_id != expected:
            raise ContractValidationError("acquisition case-set ID mismatch")
        object.__setattr__(self, "case_set_id", expected)
        return self


FROZEN_ACQUISITION_CASE_SET_V0 = AcquisitionCaseSetV0(
    guard_ids=EXPECTED_ACQUISITION_GUARD_IDS_V0,
    positive_cases=FROZEN_ACQUISITION_POSITIVE_CASES_V0,
    orthogonal_probes=FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0,
    precedence_probes=FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0,
    thresholds_id=FROZEN_ACQUISITION_THRESHOLDS_V0.thresholds_id or "",
)


def frozen_acquisition_case_set_sha256_v0() -> str:
    payload = FROZEN_ACQUISITION_CASE_SET_V0.model_dump(
        mode="json", exclude={"case_set_id"}
    )
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


__all__ = [
    "ACQUISITION_CASE_SET_SCHEMA_V0",
    "ACQUISITION_GUARD_DESIGN_SCHEMA_V0",
    "ACQUISITION_HARNESS_ID_V0",
    "ACQUISITION_LITERAL_MUTATION_SCHEMA_V0",
    "ACQUISITION_MUTATION_VECTOR_SCHEMA_V0",
    "ACQUISITION_POSITIVE_CASE_SCHEMA_V0",
    "ACQUISITION_PROBE_SCHEMA_V0",
    "ACQUISITION_THRESHOLDS_SCHEMA_V0",
    "AcquisitionCaseClass",
    "AcquisitionCaseSetV0",
    "AcquisitionGuardDesignStepV0",
    "AcquisitionGuardExpectationV0",
    "AcquisitionLiteralMutationV0",
    "AcquisitionMutationVectorV0",
    "AcquisitionPositiveCaseV0",
    "AcquisitionProbeV0",
    "AcquisitionThresholdsV0",
    "EXPECTED_ACQUISITION_GUARD_IDS_V0",
    "FROZEN_ACQUISITION_CASE_SET_V0",
    "FROZEN_ACQUISITION_GUARD_DESIGN_V0",
    "FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0",
    "FROZEN_ACQUISITION_POSITIVE_CASES_V0",
    "FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0",
    "FROZEN_ACQUISITION_THRESHOLDS_V0",
    "FROZEN_BASELINE_CAPABILITY_FIXTURE_V0",
    "FROZEN_BASELINE_CONTROL_POLICY_FIXTURE_V0",
    "FROZEN_BASELINE_SEMANTIC_REQUEST_FIXTURE_V0",
    "FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0",
    "FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0",
    "FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0",
    "FROZEN_OPAQUE_INVALID_RAW_RESPONSE_SHA256_V0",
    "FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0",
    "FROZEN_PROVIDER_VISIBLE_REQUEST_SHA256_V0",
    "MUTATION_VECTOR_FIELD_NAMES",
    "MutationState",
    "ORTHOGONAL_PROBE_IDS_V0",
    "POSITIVE_CASE_IDS_V0",
    "PRECEDENCE_PROBE_IDS_V0",
    "frozen_acquisition_case_set_sha256_v0",
]

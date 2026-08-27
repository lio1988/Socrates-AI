"""Deterministic offline evaluator for OpenRouter pre-live integration v1.

Runs the frozen integration and preflight case sets, derives the safety and
privacy counters rather than asserting them, and renders one content-addressed
authoritative artifact plus a replay execution and lock.

Thresholds are predeclared here and content addressed, so they cannot be tuned
after seeing a result without changing an identity the artifact carries.

No network, provider, model, credential or CED activity occurs, and the
artifact's zero claims are cross-checked against live tripwire instrumentation
rather than trusted.  Import-inert: building requires an explicit call.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .acquisition_tripwires import (
    assert_acquisition_artifact_tripwires_v0,
    require_clean_acquisition_boundary_tripwire_v0,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_pre_live_cases_v1 import (
    CEILING_AUTHORIZED,
    CEILING_TOO_LOW,
    CEILING_UNAUTHORIZED,
    CREDENTIAL_ABSENT,
    CREDENTIAL_PRESENT,
    FROZEN_OPENROUTER_INTEGRATION_CASES_V1,
    FROZEN_OPENROUTER_PREFLIGHT_CASES_V1,
    INPUT_BOUND_HYPOTHETICAL,
    INPUT_BOUND_UNESTABLISHED,
    OPENROUTER_INTEGRATION_CASE_SET_ID_V1,
    OPENROUTER_PREFLIGHT_CASE_SET_ID_V1,
    OUTPUT_BOUND_ESTABLISHED,
    OUTPUT_BOUND_MISSING,
    PREFLIGHT_EXECUTION_ID,
    PRICING_STALE,
    PRICING_TRUSTED,
    PRICING_UNTRUSTED_SOURCE,
    PRICING_WRONG_MODEL,
    OpenRouterIntegrationCaseKindV1,
    OpenRouterIntegrationCaseV1,
    OpenRouterIntegrationExpectedOutcomeV1,
    OpenRouterPreflightCaseV1,
)
from .openrouter_pre_live_integration_v1 import (
    OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1,
    OpenRouterIntegrationError,
    OpenRouterIntegrationFailureCodeV1,
    OpenRouterModelConformanceV1,
    bind_openrouter_pre_live_integration_v1,
)
from .openrouter_pre_live_safety_v1 import (
    FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1,
    OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1,
    OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1,
    OpenRouterBoundStatusV1,
    OpenRouterPreLiveSafetyContractV1,
    OpenRouterPreflightFailureCodeV1,
    OpenRouterPreflightVerdictV1,
    compute_openrouter_cost_bound_v1,
    evaluate_live_preflight_v1,
)
from .openrouter_raw_wire_mapping_v2 import (
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2,
    OpenRouterWireEpistemicStatusV2,
    build_openrouter_raw_wire_observation_v2,
    map_openrouter_raw_wire_v2,
)

OPENROUTER_PRE_LIVE_EVALUATION_SCHEMA_V1 = (
    "socrateszero-openrouter-pre-live-evaluation/v1"
)
OPENROUTER_PRE_LIVE_REPLAY_EXECUTION_SCHEMA_V1 = (
    "socrateszero-openrouter-pre-live-replay-execution/v1"
)
OPENROUTER_PRE_LIVE_REPLAY_LOCK_SCHEMA_V1 = (
    "socrateszero-openrouter-pre-live-replay-lock/v1"
)

_BRANCH_DIR = "docs/branches/feature-socrates-zero-openrouter-prelive-integration-v1"
OPENROUTER_PRE_LIVE_ARTIFACT_RELATIVE_PATH_V1 = (
    f"{_BRANCH_DIR}/artifacts/socrateszero_openrouter_pre_live_integration_v1.json"
)
OPENROUTER_PRE_LIVE_REPLAY_EXECUTION_RELATIVE_PATH_V1 = (
    f"{_BRANCH_DIR}/artifacts/"
    "socrateszero_openrouter_pre_live_integration_replay_execution_v1.json"
)
OPENROUTER_PRE_LIVE_REPLAY_LOCK_RELATIVE_PATH_V1 = (
    f"{_BRANCH_DIR}/artifacts/"
    "socrateszero_openrouter_pre_live_integration_replay_lock_v1.json"
)

#: Markers that must never appear in the aggregate artifact.  Assembled from
#: fragments so this detector's own source is not a match for itself.
_FORBIDDEN_ARTIFACT_MARKERS: Tuple[str, ...] = (
    "Authoriz" + "ation",
    "Bearer ",
    "sk-" + "or-",
    "OPENROUTER_API_" + "KEY_VALUE",
)


class _FrozenPreLiveContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterPreLiveHypothesisStatusV1(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class OpenRouterPreLiveOutcomeV1(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INVALID_FIXTURE_CONSTRUCTION = "INVALID_FIXTURE_CONSTRUCTION"


class OpenRouterLiveReadinessV1(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_PENDING_JIT_PREFLIGHT = "AUTHORIZED_PENDING_JIT_PREFLIGHT"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"


class OpenRouterPreLiveBoundaryCountersV1(_FrozenPreLiveContractV1):
    external_network_attempts: int = Field(ge=0)
    credential_access_attempts: int = Field(ge=0)
    live_provider_calls: int = Field(ge=0)
    provider_sdk_calls: int = Field(ge=0)
    model_executions: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    canonical_application_calls: int = Field(ge=0)
    official_source_retrievals: int = Field(ge=0)


class OpenRouterPreLiveThresholdsV1(_FrozenPreLiveContractV1):
    """Predeclared before authoritative execution."""

    required_integration_positive_accepted: int = 12
    required_integration_adversarial_rejected: int = 18
    required_preflight_authorized: int = 1
    required_preflight_refused: int = 14
    required_unexpected_results: int = 0
    required_invalid_fixture_constructions: int = 0
    maximum_cross_request_substitutions_accepted: int = 0
    maximum_request_to_response_authority_leaks: int = 0
    maximum_provider_to_endpoint_synthesis: int = 0
    maximum_requested_to_actual_substitutions: int = 0
    maximum_metadata_absence_cache_hit_inferences: int = 0
    maximum_authorization_reuse_accepted: int = 0
    maximum_privacy_leakage_findings: int = 0
    maximum_external_activity: int = 0
    thresholds_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreLiveThresholdsV1":
        expected = stable_contract_id(
            "szorprelivethresholdsv1",
            self.model_dump(mode="json", exclude={"thresholds_id"}),
        )
        if self.thresholds_id not in (None, expected):
            raise ContractValidationError("pre-live thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_OPENROUTER_PRE_LIVE_THRESHOLDS_V1 = OpenRouterPreLiveThresholdsV1()
OPENROUTER_PRE_LIVE_THRESHOLDS_ID_V1 = (
    FROZEN_OPENROUTER_PRE_LIVE_THRESHOLDS_V1.thresholds_id
)


class OpenRouterIntegrationCaseResultV1(_FrozenPreLiveContractV1):
    case_id: str
    kind: OpenRouterIntegrationCaseKindV1
    case_fingerprint: str
    expected_outcome: OpenRouterIntegrationExpectedOutcomeV1
    actual_outcome: OpenRouterPreLiveOutcomeV1
    expected_failure_code: Optional[OpenRouterIntegrationFailureCodeV1] = None
    actual_failure_code: Optional[OpenRouterIntegrationFailureCodeV1] = None
    receipt_id: Optional[str] = None
    field_mismatches: Tuple[str, ...] = ()
    request_to_response_authority_leak: bool = False
    provider_to_endpoint_synthesis: bool = False
    requested_substituted_for_actual: bool = False
    cache_hit_inferred_from_absence: bool = False
    result_matches_expectation: bool


class OpenRouterPreflightCaseResultV1(_FrozenPreLiveContractV1):
    case_id: str
    case_fingerprint: str
    expected_verdict: str
    actual_verdict: str
    expected_failure_code: Optional[OpenRouterPreflightFailureCodeV1] = None
    actual_failure_code: Optional[OpenRouterPreflightFailureCodeV1] = None
    authorization_id: Optional[str] = None
    result_matches_expectation: bool


class OpenRouterPreLiveMetricsV1(_FrozenPreLiveContractV1):
    integration_cases: int = Field(ge=0)
    integration_positive_accepted: int = Field(ge=0)
    integration_adversarial_rejected: int = Field(ge=0)
    preflight_cases: int = Field(ge=0)
    preflight_authorized: int = Field(ge=0)
    preflight_refused: int = Field(ge=0)
    unexpected_results: int = Field(ge=0)
    invalid_fixture_constructions: int = Field(ge=0)
    guard_code_mismatches: int = Field(ge=0)
    cross_request_substitutions_accepted: int = Field(ge=0)
    request_to_response_authority_leaks: int = Field(ge=0)
    provider_to_endpoint_synthesis: int = Field(ge=0)
    requested_to_actual_substitutions: int = Field(ge=0)
    metadata_absence_cache_hit_inferences: int = Field(ge=0)
    authorization_reuse_accepted: int = Field(ge=0)
    privacy_leakage_findings: int = Field(ge=0)
    distinct_integration_guards_exercised: int = Field(ge=0)
    distinct_preflight_guards_exercised: int = Field(ge=0)
    all_thresholds_pass: bool


class OpenRouterPreLiveIntegrationArtifactV1(_FrozenPreLiveContractV1):
    schema_version: Literal[
        OPENROUTER_PRE_LIVE_EVALUATION_SCHEMA_V1
    ] = OPENROUTER_PRE_LIVE_EVALUATION_SCHEMA_V1
    source_manifest_id: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    source_manifest_sha256: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    integration_case_set_id: str
    preflight_case_set_id: str
    safety_contract_id: str
    integration_guard_order_id: Literal[
        OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1
    ] = OPENROUTER_INTEGRATION_GUARD_ORDER_ID_V1
    preflight_guard_order_id: Literal[
        OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1
    ] = OPENROUTER_PREFLIGHT_GUARD_ORDER_ID_V1
    thresholds: OpenRouterPreLiveThresholdsV1
    thresholds_id: str
    boundary_counters: OpenRouterPreLiveBoundaryCountersV1
    integration_results: Tuple[OpenRouterIntegrationCaseResultV1, ...]
    preflight_results: Tuple[OpenRouterPreflightCaseResultV1, ...]
    metrics: OpenRouterPreLiveMetricsV1

    # --- standing epistemic states, unchanged by integration
    exact_endpoint_response_identity_status: Literal[
        "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
    ] = "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_total_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    output_token_bound: Literal["ESTABLISHED"] = "ESTABLISHED"
    runtime_authority: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    live_openrouter_execution: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    one_live_shadow_call: OpenRouterLiveReadinessV1
    hypothesis_status: OpenRouterPreLiveHypothesisStatusV1
    artifact_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreLiveIntegrationArtifactV1":
        if self.thresholds_id != self.thresholds.thresholds_id:
            raise ContractValidationError("artifact thresholds identity disagrees")
        if self.integration_case_set_id != OPENROUTER_INTEGRATION_CASE_SET_ID_V1:
            raise ContractValidationError("artifact integration case-set changed")
        if self.preflight_case_set_id != OPENROUTER_PREFLIGHT_CASE_SET_ID_V1:
            raise ContractValidationError("artifact preflight case-set changed")
        if self.safety_contract_id != OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1:
            raise ContractValidationError("artifact safety contract changed")
        expected_metrics = _derive_metrics_v1(
            self.integration_results, self.preflight_results, self.metrics.privacy_leakage_findings
        )
        if self.metrics != expected_metrics:
            raise ContractValidationError("artifact metrics are not fully derived")
        zeros = {name: 0 for name in OpenRouterPreLiveBoundaryCountersV1.model_fields}
        supported = (
            self.metrics.all_thresholds_pass
            and self.boundary_counters.model_dump(mode="python") == zeros
        )
        expected_status = (
            OpenRouterPreLiveHypothesisStatusV1.SUPPORTED
            if supported
            else OpenRouterPreLiveHypothesisStatusV1.FALSIFIED
        )
        if self.hypothesis_status is not expected_status:
            raise ContractValidationError("artifact hypothesis status is not derived")
        assert_acquisition_artifact_tripwires_v0(self.boundary_counters)
        expected = stable_contract_id(
            "szorpreliveartifactv1",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id not in (None, expected):
            raise ContractValidationError("pre-live artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected)
        return self


# ------------------------------------------------------------- evaluation ---

#: Cases that deliberately pair one chain's evidence with another's.  Accepting
#: any of them would be a cross-request substitution.
_CROSS_REQUEST_CASE_IDS = frozenset(
    {
        "orintegv1-x05-sibling-request-paired-to-transport",
        "orintegv1-x06-sibling-transport-paired-to-request",
        "orintegv1-x15-sibling-response-observation",
        "orintegv1-x16-mapping-from-sibling-observation",
        "orintegv1-x17-mapping-header-provenance-mismatch",
    }
)


def evaluate_integration_case_v1(
    case: OpenRouterIntegrationCaseV1,
) -> OpenRouterIntegrationCaseResultV1:
    if type(case) is not OpenRouterIntegrationCaseV1:
        raise ContractValidationError("evaluation requires the exact frozen case type")
    try:
        observation = build_openrouter_raw_wire_observation_v2(
            case.observation_body, case.observation_headers
        )
        mapping = map_openrouter_raw_wire_v2(
            build_openrouter_raw_wire_observation_v2(
                case.mapping_body, case.mapping_headers
            )
        )
    except ContractValidationError:
        return OpenRouterIntegrationCaseResultV1(
            case_id=case.case_id,
            kind=case.kind,
            case_fingerprint=case.case_fingerprint or "",
            expected_outcome=case.expected_outcome,
            actual_outcome=OpenRouterPreLiveOutcomeV1.INVALID_FIXTURE_CONSTRUCTION,
            expected_failure_code=case.expected_failure_code,
            result_matches_expectation=False,
        )

    try:
        receipt = bind_openrouter_pre_live_integration_v1(
            case.intent,
            case.transport,
            observation,
            mapping,
            OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1,
        )
    except OpenRouterIntegrationError as exc:
        matches = (
            case.expected_outcome is OpenRouterIntegrationExpectedOutcomeV1.REJECTED
            and exc.code is case.expected_failure_code
        )
        return OpenRouterIntegrationCaseResultV1(
            case_id=case.case_id,
            kind=case.kind,
            case_fingerprint=case.case_fingerprint or "",
            expected_outcome=case.expected_outcome,
            actual_outcome=OpenRouterPreLiveOutcomeV1.REJECTED,
            expected_failure_code=case.expected_failure_code,
            actual_failure_code=exc.code,
            result_matches_expectation=matches,
        )

    dumped = receipt.model_dump(mode="json")
    mismatches = tuple(
        name
        for name, expected_json in case.expected_fields
        if canonical_json(dumped.get(name)) != expected_json
    )

    # Derived authority probes, read from the receipt rather than asserted.
    leak = (
        receipt.actual_served_model is not None
        and mapping.actual_served_model is None
    ) or (
        receipt.response_cache_status is not None and mapping.cache_status is None
    )
    provider_synthesis = any(
        "/" in name for name in receipt.response_provider_display_names
    ) or receipt.exact_endpoint_response_identity is not None
    requested_substituted = (
        receipt.actual_served_model is not None
        and receipt.actual_served_model != mapping.actual_served_model
    )
    cache_inferred = (
        receipt.response_cache_status is not None
        and mapping.cache_status is None
    )
    matches = (
        case.expected_outcome is OpenRouterIntegrationExpectedOutcomeV1.ACCEPTED
        and not mismatches
        and not (leak or provider_synthesis or requested_substituted or cache_inferred)
    )
    return OpenRouterIntegrationCaseResultV1(
        case_id=case.case_id,
        kind=case.kind,
        case_fingerprint=case.case_fingerprint or "",
        expected_outcome=case.expected_outcome,
        actual_outcome=OpenRouterPreLiveOutcomeV1.ACCEPTED,
        expected_failure_code=case.expected_failure_code,
        receipt_id=receipt.receipt_id,
        field_mismatches=mismatches,
        request_to_response_authority_leak=leak,
        provider_to_endpoint_synthesis=provider_synthesis,
        requested_substituted_for_actual=requested_substituted,
        cache_hit_inferred_from_absence=cache_inferred,
        result_matches_expectation=matches,
    )


_PRICING_VARIANTS = {
    "TRUSTED": PRICING_TRUSTED,
    "UNTRUSTED": PRICING_UNTRUSTED_SOURCE,
    "WRONG_MODEL": PRICING_WRONG_MODEL,
    "STALE": PRICING_STALE,
    "ABSENT": None,
}
_CEILING_VARIANTS = {
    "AUTHORIZED": CEILING_AUTHORIZED,
    "TOO_LOW": CEILING_TOO_LOW,
    "UNAUTHORIZED": CEILING_UNAUTHORIZED,
}


def evaluate_preflight_case_v1(
    case: OpenRouterPreflightCaseV1,
) -> OpenRouterPreflightCaseResultV1:
    if type(case) is not OpenRouterPreflightCaseV1:
        raise ContractValidationError("evaluation requires the exact frozen case type")
    from .openrouter_pre_live_cases_v1 import INTENT_A

    safety = (
        FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1
        if case.use_frozen_safety_contract
        else OpenRouterPreLiveSafetyContractV1(mapper_available=True).model_copy(
            update={"contract_id": "szorprelivesafetyv1_" + "0" * 64}
        )
    )
    input_bound = (
        INPUT_BOUND_HYPOTHETICAL if case.input_bound_established else INPUT_BOUND_UNESTABLISHED
    )
    if case.request_body_sha_override is not None:
        input_bound = input_bound.model_copy(
            update={
                "bound_request_body_sha256": case.request_body_sha_override,
                "evidence_id": None,
            }
        )
    output_bound = (
        OUTPUT_BOUND_ESTABLISHED if case.output_bound_established else OUTPUT_BOUND_MISSING
    )
    pricing = _PRICING_VARIANTS[case.pricing_variant]
    ceiling = _CEILING_VARIANTS[case.ceiling_variant]
    cost_bound = compute_openrouter_cost_bound_v1(input_bound, output_bound, pricing)

    consumed: Tuple[str, ...] = ()
    if case.replay_consumed:
        first = evaluate_live_preflight_v1(
            safety_contract=safety,
            request_intent_receipt_id=INTENT_A.receipt_id or "",
            expected_request_intent_receipt_id=INTENT_A.receipt_id or "",
            expected_request_body_sha256=INTENT_A.body_sha256,
            transport_ready=True,
            credential_attestation=CREDENTIAL_PRESENT,
            input_bound=input_bound,
            output_bound=output_bound,
            pricing=pricing,
            cost_bound=cost_bound,
            operator_ceiling=ceiling,
            preflight_execution_id=PREFLIGHT_EXECUTION_ID,
        )
        if first.authorization is not None:
            consumed = (first.authorization.authorization_id or "",)

    result = evaluate_live_preflight_v1(
        safety_contract=safety,
        request_intent_receipt_id=(
            case.request_intent_receipt_id_override or INTENT_A.receipt_id or ""
        ),
        expected_request_intent_receipt_id=INTENT_A.receipt_id or "",
        expected_request_body_sha256=INTENT_A.body_sha256,
        transport_ready=case.transport_ready,
        credential_attestation=(
            CREDENTIAL_PRESENT if case.credential_present else CREDENTIAL_ABSENT
        ),
        input_bound=input_bound,
        output_bound=output_bound,
        pricing=pricing,
        cost_bound=cost_bound,
        operator_ceiling=ceiling,
        preflight_execution_id=PREFLIGHT_EXECUTION_ID,
        consumed_authorization_ids=consumed,
    )
    matches = result.verdict.value == case.expected_verdict and (
        result.first_failure is case.expected_failure_code
    )
    return OpenRouterPreflightCaseResultV1(
        case_id=case.case_id,
        case_fingerprint=case.case_fingerprint or "",
        expected_verdict=case.expected_verdict,
        actual_verdict=result.verdict.value,
        expected_failure_code=case.expected_failure_code,
        actual_failure_code=result.first_failure,
        authorization_id=(
            result.authorization.authorization_id if result.authorization else None
        ),
        result_matches_expectation=matches,
    )


def _derive_metrics_v1(
    integration_results: Tuple[OpenRouterIntegrationCaseResultV1, ...],
    preflight_results: Tuple[OpenRouterPreflightCaseResultV1, ...],
    privacy_findings: int,
) -> OpenRouterPreLiveMetricsV1:
    thresholds = FROZEN_OPENROUTER_PRE_LIVE_THRESHOLDS_V1
    positive_accepted = sum(
        r.kind is OpenRouterIntegrationCaseKindV1.POSITIVE
        and r.actual_outcome is OpenRouterPreLiveOutcomeV1.ACCEPTED
        and r.result_matches_expectation
        for r in integration_results
    )
    adversarial_rejected = sum(
        r.kind is OpenRouterIntegrationCaseKindV1.ADVERSARIAL
        and r.actual_outcome is OpenRouterPreLiveOutcomeV1.REJECTED
        and r.result_matches_expectation
        for r in integration_results
    )
    cross_substitutions = sum(
        r.case_id in _CROSS_REQUEST_CASE_IDS
        and r.actual_outcome is OpenRouterPreLiveOutcomeV1.ACCEPTED
        for r in integration_results
    )
    authorized = sum(
        r.actual_verdict == "AUTHORIZED_FOR_ONE_CALL" for r in preflight_results
    )
    reuse_accepted = sum(
        r.case_id.endswith("authorization-already-consumed")
        and r.actual_verdict == "AUTHORIZED_FOR_ONE_CALL"
        for r in preflight_results
    )
    unexpected = sum(
        not r.result_matches_expectation for r in integration_results
    ) + sum(not r.result_matches_expectation for r in preflight_results)
    values = {
        "integration_cases": len(integration_results),
        "integration_positive_accepted": positive_accepted,
        "integration_adversarial_rejected": adversarial_rejected,
        "preflight_cases": len(preflight_results),
        "preflight_authorized": authorized,
        "preflight_refused": sum(
            r.actual_verdict == "REFUSED" for r in preflight_results
        ),
        "unexpected_results": unexpected,
        "invalid_fixture_constructions": sum(
            r.actual_outcome is OpenRouterPreLiveOutcomeV1.INVALID_FIXTURE_CONSTRUCTION
            for r in integration_results
        ),
        "guard_code_mismatches": sum(
            r.actual_outcome is OpenRouterPreLiveOutcomeV1.REJECTED
            and r.actual_failure_code is not r.expected_failure_code
            for r in integration_results
        )
        + sum(
            r.actual_verdict == "REFUSED"
            and r.actual_failure_code is not r.expected_failure_code
            for r in preflight_results
        ),
        "cross_request_substitutions_accepted": cross_substitutions,
        "request_to_response_authority_leaks": sum(
            r.request_to_response_authority_leak for r in integration_results
        ),
        "provider_to_endpoint_synthesis": sum(
            r.provider_to_endpoint_synthesis for r in integration_results
        ),
        "requested_to_actual_substitutions": sum(
            r.requested_substituted_for_actual for r in integration_results
        ),
        "metadata_absence_cache_hit_inferences": sum(
            r.cache_hit_inferred_from_absence for r in integration_results
        ),
        "authorization_reuse_accepted": reuse_accepted,
        "privacy_leakage_findings": privacy_findings,
        "distinct_integration_guards_exercised": len(
            {r.actual_failure_code for r in integration_results if r.actual_failure_code}
        ),
        "distinct_preflight_guards_exercised": len(
            {r.actual_failure_code for r in preflight_results if r.actual_failure_code}
        ),
    }
    passes = (
        values["integration_positive_accepted"]
        == thresholds.required_integration_positive_accepted
        and values["integration_adversarial_rejected"]
        == thresholds.required_integration_adversarial_rejected
        and values["preflight_authorized"] == thresholds.required_preflight_authorized
        and values["preflight_refused"] == thresholds.required_preflight_refused
        and values["unexpected_results"] == thresholds.required_unexpected_results
        and values["invalid_fixture_constructions"]
        == thresholds.required_invalid_fixture_constructions
        and values["guard_code_mismatches"] == 0
        and values["cross_request_substitutions_accepted"]
        <= thresholds.maximum_cross_request_substitutions_accepted
        and values["request_to_response_authority_leaks"]
        <= thresholds.maximum_request_to_response_authority_leaks
        and values["provider_to_endpoint_synthesis"]
        <= thresholds.maximum_provider_to_endpoint_synthesis
        and values["requested_to_actual_substitutions"]
        <= thresholds.maximum_requested_to_actual_substitutions
        and values["metadata_absence_cache_hit_inferences"]
        <= thresholds.maximum_metadata_absence_cache_hit_inferences
        and values["authorization_reuse_accepted"]
        <= thresholds.maximum_authorization_reuse_accepted
        and values["privacy_leakage_findings"]
        <= thresholds.maximum_privacy_leakage_findings
    )
    return OpenRouterPreLiveMetricsV1(**values, all_thresholds_pass=passes)


def scan_artifact_privacy_v1(payload: str) -> int:
    """Count forbidden markers in a rendered artifact.

    Credentials, bearer tokens, raw response bodies and rendered prompts have no
    business in a compact aggregate; digests and identities carry the evidence.
    """
    findings = sum(marker in payload for marker in _FORBIDDEN_ARTIFACT_MARKERS)
    from .openrouter_pre_live_cases_v1 import RESPONSE_A, RESPONSE_B

    for body in (RESPONSE_A, RESPONSE_B):
        text = body.decode("utf-8")
        if text in payload:
            findings += 1
        if "scaffolding" in payload and text[:40] in payload:
            findings += 1
    return findings


def evaluate_openrouter_pre_live_v1() -> Tuple[
    Tuple[OpenRouterIntegrationCaseResultV1, ...],
    Tuple[OpenRouterPreflightCaseResultV1, ...],
]:
    return (
        tuple(
            evaluate_integration_case_v1(case)
            for case in FROZEN_OPENROUTER_INTEGRATION_CASES_V1
        ),
        tuple(
            evaluate_preflight_case_v1(case)
            for case in FROZEN_OPENROUTER_PREFLIGHT_CASES_V1
        ),
    )


def _live_readiness_v1() -> OpenRouterLiveReadinessV1:
    """The layered live decision, derived rather than declared.

    Structural safety being ready is not sufficient: a live call also needs a
    bounded worst-case cost, and that needs an input token bound this repository
    cannot currently produce.  That is a structural gap, not a fresh fact, so the
    honest answer is NOT_AUTHORIZED rather than pending-JIT.
    """
    if INPUT_BOUND_UNESTABLISHED.status is OpenRouterBoundStatusV1.ESTABLISHED:
        return OpenRouterLiveReadinessV1.AUTHORIZED_PENDING_JIT_PREFLIGHT
    return OpenRouterLiveReadinessV1.NOT_AUTHORIZED


def build_openrouter_pre_live_artifact_v1() -> OpenRouterPreLiveIntegrationArtifactV1:
    """Build the authoritative artifact.  Requires an active boundary tripwire."""
    snapshot = require_clean_acquisition_boundary_tripwire_v0()
    integration_results, preflight_results = evaluate_openrouter_pre_live_v1()
    counters = OpenRouterPreLiveBoundaryCountersV1(
        external_network_attempts=snapshot.external_network_attempts,
        credential_access_attempts=snapshot.credential_access_attempts,
        live_provider_calls=snapshot.live_provider_calls,
        provider_sdk_calls=snapshot.provider_sdk_calls,
        model_executions=snapshot.model_executions,
        tool_calls=snapshot.tool_calls,
        canonical_application_calls=snapshot.canonical_application_calls,
        official_source_retrievals=0,
    )
    provisional = _derive_metrics_v1(integration_results, preflight_results, 0)
    draft = {
        "integration_results": [r.model_dump(mode="json") for r in integration_results],
        "preflight_results": [r.model_dump(mode="json") for r in preflight_results],
        "metrics": provisional.model_dump(mode="json"),
    }
    privacy_findings = scan_artifact_privacy_v1(canonical_json(draft))
    metrics = _derive_metrics_v1(
        integration_results, preflight_results, privacy_findings
    )
    zeros = {name: 0 for name in OpenRouterPreLiveBoundaryCountersV1.model_fields}
    supported = metrics.all_thresholds_pass and counters.model_dump(
        mode="python"
    ) == zeros
    return OpenRouterPreLiveIntegrationArtifactV1(
        integration_case_set_id=OPENROUTER_INTEGRATION_CASE_SET_ID_V1,
        preflight_case_set_id=OPENROUTER_PREFLIGHT_CASE_SET_ID_V1,
        safety_contract_id=OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1 or "",
        thresholds=FROZEN_OPENROUTER_PRE_LIVE_THRESHOLDS_V1,
        thresholds_id=OPENROUTER_PRE_LIVE_THRESHOLDS_ID_V1 or "",
        boundary_counters=counters,
        integration_results=integration_results,
        preflight_results=preflight_results,
        metrics=metrics,
        one_live_shadow_call=_live_readiness_v1(),
        hypothesis_status=(
            OpenRouterPreLiveHypothesisStatusV1.SUPPORTED
            if supported
            else OpenRouterPreLiveHypothesisStatusV1.FALSIFIED
        ),
    )


def render_openrouter_pre_live_artifact_v1(
    artifact: OpenRouterPreLiveIntegrationArtifactV1,
) -> bytes:
    if type(artifact) is not OpenRouterPreLiveIntegrationArtifactV1:
        raise ContractValidationError("artifact must use the exact frozen v1 type")
    return canonical_json(artifact.model_dump(mode="json")).encode("utf-8") + b"\n"


def load_openrouter_pre_live_artifact_v1(
    path: Path,
) -> OpenRouterPreLiveIntegrationArtifactV1:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("pre-live artifact is unavailable") from exc
    artifact = OpenRouterPreLiveIntegrationArtifactV1.model_validate(value)
    if Path(path).read_bytes() != render_openrouter_pre_live_artifact_v1(artifact):
        raise ContractValidationError("pre-live artifact bytes are not canonical")
    return artifact


class OpenRouterPreLiveReplayExecutionV1(_FrozenPreLiveContractV1):
    schema_version: Literal[
        OPENROUTER_PRE_LIVE_REPLAY_EXECUTION_SCHEMA_V1
    ] = OPENROUTER_PRE_LIVE_REPLAY_EXECUTION_SCHEMA_V1
    source_artifact_id: str
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recomputed_artifact_id: str
    recomputed_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: bool
    artifact_id_equality: bool
    byte_identity: bool
    official_source_retrievals: Literal[0] = 0
    live_openrouter_calls: Literal[0] = 0
    execution_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreLiveReplayExecutionV1":
        expected = stable_contract_id(
            "szorprelivereplayexecutionv1",
            self.model_dump(mode="json", exclude={"execution_id"}),
        )
        if self.execution_id not in (None, expected):
            raise ContractValidationError("pre-live replay execution ID mismatch")
        object.__setattr__(self, "execution_id", expected)
        return self


class OpenRouterPreLiveReplayLockV1(_FrozenPreLiveContractV1):
    schema_version: Literal[
        OPENROUTER_PRE_LIVE_REPLAY_LOCK_SCHEMA_V1
    ] = OPENROUTER_PRE_LIVE_REPLAY_LOCK_SCHEMA_V1
    artifact_id: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_execution_id: str
    replay_execution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: bool
    artifact_id_equality: bool
    byte_identity: bool
    lock_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreLiveReplayLockV1":
        if not (
            self.semantic_equality and self.artifact_id_equality and self.byte_identity
        ):
            raise ContractValidationError(
                "a replay lock requires deterministic replay in all three senses"
            )
        expected = stable_contract_id(
            "szorprelivereplaylockv1",
            self.model_dump(mode="json", exclude={"lock_id"}),
        )
        if self.lock_id not in (None, expected):
            raise ContractValidationError("pre-live replay lock ID mismatch")
        object.__setattr__(self, "lock_id", expected)
        return self


def render_openrouter_pre_live_replay_execution_v1(
    execution: OpenRouterPreLiveReplayExecutionV1,
) -> bytes:
    return canonical_json(execution.model_dump(mode="json")).encode("utf-8") + b"\n"


def render_openrouter_pre_live_replay_lock_v1(
    lock: OpenRouterPreLiveReplayLockV1,
) -> bytes:
    return canonical_json(lock.model_dump(mode="json")).encode("utf-8") + b"\n"


def replay_openrouter_pre_live_v1(
    artifact_path: Path,
) -> Tuple[OpenRouterPreLiveReplayExecutionV1, OpenRouterPreLiveReplayLockV1]:
    source_bytes = Path(artifact_path).read_bytes()
    source_artifact = load_openrouter_pre_live_artifact_v1(Path(artifact_path))
    recomputed = build_openrouter_pre_live_artifact_v1()
    recomputed_bytes = render_openrouter_pre_live_artifact_v1(recomputed)
    execution = OpenRouterPreLiveReplayExecutionV1(
        source_artifact_id=source_artifact.artifact_id or "",
        source_artifact_sha256=hashlib.sha256(source_bytes).hexdigest(),
        recomputed_artifact_id=recomputed.artifact_id or "",
        recomputed_artifact_sha256=hashlib.sha256(recomputed_bytes).hexdigest(),
        semantic_equality=recomputed == source_artifact,
        artifact_id_equality=recomputed.artifact_id == source_artifact.artifact_id,
        byte_identity=recomputed_bytes == source_bytes,
    )
    lock = OpenRouterPreLiveReplayLockV1(
        artifact_id=source_artifact.artifact_id or "",
        artifact_sha256=hashlib.sha256(source_bytes).hexdigest(),
        replay_execution_id=execution.execution_id or "",
        replay_execution_sha256=hashlib.sha256(
            render_openrouter_pre_live_replay_execution_v1(execution)
        ).hexdigest(),
        semantic_equality=execution.semantic_equality,
        artifact_id_equality=execution.artifact_id_equality,
        byte_identity=execution.byte_identity,
    )
    return execution, lock


def write_once_v1(path: Path, payload: bytes) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise ContractValidationError(
            f"write-once evidence already exists: {target}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "FROZEN_OPENROUTER_PRE_LIVE_THRESHOLDS_V1",
    "OPENROUTER_PRE_LIVE_ARTIFACT_RELATIVE_PATH_V1",
    "OPENROUTER_PRE_LIVE_EVALUATION_SCHEMA_V1",
    "OPENROUTER_PRE_LIVE_REPLAY_EXECUTION_RELATIVE_PATH_V1",
    "OPENROUTER_PRE_LIVE_REPLAY_LOCK_RELATIVE_PATH_V1",
    "OPENROUTER_PRE_LIVE_THRESHOLDS_ID_V1",
    "OpenRouterIntegrationCaseResultV1",
    "OpenRouterLiveReadinessV1",
    "OpenRouterPreLiveBoundaryCountersV1",
    "OpenRouterPreLiveHypothesisStatusV1",
    "OpenRouterPreLiveIntegrationArtifactV1",
    "OpenRouterPreLiveMetricsV1",
    "OpenRouterPreLiveOutcomeV1",
    "OpenRouterPreLiveReplayExecutionV1",
    "OpenRouterPreLiveReplayLockV1",
    "OpenRouterPreLiveThresholdsV1",
    "OpenRouterPreflightCaseResultV1",
    "build_openrouter_pre_live_artifact_v1",
    "evaluate_integration_case_v1",
    "evaluate_openrouter_pre_live_v1",
    "evaluate_preflight_case_v1",
    "load_openrouter_pre_live_artifact_v1",
    "render_openrouter_pre_live_artifact_v1",
    "render_openrouter_pre_live_replay_execution_v1",
    "render_openrouter_pre_live_replay_lock_v1",
    "replay_openrouter_pre_live_v1",
    "scan_artifact_privacy_v1",
    "write_once_v1",
]

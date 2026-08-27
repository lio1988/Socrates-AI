"""Deterministic offline evaluator for OpenRouter live-safety closure v1.

The evaluator executes the frozen 73-case S7A inventory against the additive
P17, request-overlay, P19 and one-call authorization contracts.  It records
only compact identities, outcomes and first-failure classifications: raw model
detail responses, rendered prompts, credentials and consumption paths never
enter the authoritative artifact.

Importing this module is inert.  The authoritative aggregate requires the
repository's active acquisition-boundary tripwire and performs no network,
credential, provider, model, tool, CED or live-dispatch activity.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing.process
import tempfile
import threading
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Literal, Optional, Tuple
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .acquisition_tripwires import (
    assert_acquisition_artifact_tripwires_v0,
    require_clean_acquisition_boundary_tripwire_v0,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_live_request_overlay_v1 import (
    OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1,
    build_openrouter_max_price_policy_v1,
)
from .openrouter_live_request_overlay_v2 import (
    OpenRouterLiveRequestModalityBindingV1,
    OpenRouterLiveRequestSafetyOverlayV2,
    OpenRouterOperatorPriceCeilingV1,
    OpenRouterOperatorScopeV1,
    OpenRouterOutputBoundEvidenceV2,
    OpenRouterRenderedLiveRequestV2,
    build_openrouter_live_request_overlay_v2,
    build_openrouter_operator_price_ceiling_v1,
    derive_openrouter_live_request_modality_binding_v1,
    derive_openrouter_output_bound_v2,
    render_openrouter_live_request_v2,
)
from .openrouter_live_safety_cases_v1 import (
    FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1,
    FROZEN_OPENROUTER_LIVE_SAFETY_REQUIREMENT_TAGS_V1,
    FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1,
    OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1,
    OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1,
    OpenRouterLiveSafetyCaseFamilyV1,
    OpenRouterLiveSafetyCaseKindV1,
    OpenRouterLiveSafetyCaseV1,
    OpenRouterLiveSafetyExpectedOutcomeV1,
    OpenRouterLiveSafetyHazardV1,
    OpenRouterLiveSafetyThresholdsV1,
)
from .openrouter_live_safety_closure_v1 import (
    FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1,
    FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1,
    FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
    FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1,
    OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1,
    OPENROUTER_P19_PROOF_METHOD_ID_V1,
    OpenRouterClaimStoreReadinessAttestationV1,
    OpenRouterCredentialAvailabilityV1,
    OpenRouterJitCredentialPresenceAttestationV1,
    OpenRouterLiveSafetyModeV1,
    OpenRouterOneCallAuthorizationV1,
    OpenRouterOneCallConsumptionV1,
    OpenRouterOneLiveCallFailureCodeV1,
    OpenRouterOneLiveCallPreflightResultV1,
    OpenRouterOneLiveCallVerdictV1,
    OpenRouterOneShotTransportPolicyV1,
    OpenRouterOperatorTotalSpendCeilingV1,
    OpenRouterP19CostComponentV1,
    OpenRouterS5MapperCapabilityV1,
    OpenRouterS6IntegrationCapabilityV1,
    OpenRouterTransportReadinessAttestationV1,
    OpenRouterWorstCaseCostBoundV1,
    attest_openrouter_claim_store_readiness_v1,
    attest_openrouter_transport_readiness_v1,
    build_openrouter_one_shot_transport_policy_v1,
    build_openrouter_operator_total_spend_ceiling_v1,
    compute_openrouter_worst_case_cost_bound_v1,
    consume_openrouter_one_call_authorization_v1,
    evaluate_one_live_call_preflight_v1,
    mint_openrouter_one_call_authorization_v1,
    openrouter_authorization_claim_path_v1,
)
from .openrouter_pre_live_safety_v1 import (
    OpenRouterChargeClassStateV1,
    OpenRouterChargeCoverageV1,
)
from .openrouter_route_controls_renderer import prepare_openrouter_route_request_v1
from .openrouter_route_controls_contracts import (
    FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1,
)
from .openrouter_trusted_input_bound_v1 import (
    OpenRouterInputLimitKindV1,
    OpenRouterInputLimitSourceScopeV1,
    OpenRouterP17InputBoundProofV1,
    OpenRouterP17ProofAuthorityV1,
    TrustedModelInputLimitRecordV1,
    build_openrouter_p17_input_bound_proof_v1,
    build_trusted_model_input_limit_record_from_response_v1,
)


OPENROUTER_LIVE_SAFETY_EVALUATION_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-evaluation/v1"
)
OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-replay-execution/v1"
)
OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-replay-lock/v1"
)
OPENROUTER_LIVE_SAFETY_PREDECESSOR_INTEGRITY_SCHEMA_V1 = (
    "socrateszero-openrouter-live-safety-predecessor-integrity/v1"
)

_BRANCH_DIR_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-live-safety-closure-v1"
)
OPENROUTER_LIVE_SAFETY_ARTIFACT_RELATIVE_PATH_V1 = (
    f"{_BRANCH_DIR_V1}/artifacts/"
    "socrateszero_openrouter_live_safety_closure_v1.json"
)
OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_RELATIVE_PATH_V1 = (
    f"{_BRANCH_DIR_V1}/artifacts/"
    "socrateszero_openrouter_live_safety_closure_replay_execution_v1.json"
)
OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_RELATIVE_PATH_V1 = (
    f"{_BRANCH_DIR_V1}/artifacts/"
    "socrateszero_openrouter_live_safety_closure_replay_lock_v1.json"
)

OPENROUTER_LIVE_SAFETY_EVALUATION_ID_V1 = "s7a-offline-evaluation-v1"
OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1 = (
    "s7a-synthetic-preflight-v1"
)
OPENROUTER_LIVE_SAFETY_SYNTHETIC_FIXTURE_ID_V1 = (
    "s7a-synthetic-model-limit-v1"
)
OPENROUTER_LIVE_SAFETY_SYNTHETIC_PRICE_GRANT_ID_V1 = stable_contract_id(
    "szoroperatorpricegrantv1", {"fixture": "s7a-price-grant-v1"}
)
OPENROUTER_LIVE_SAFETY_SYNTHETIC_TOTAL_GRANT_ID_V1 = stable_contract_id(
    "szoroperatortotalgrantv1", {"fixture": "s7a-total-grant-v1"}
)
OPENROUTER_LIVE_SAFETY_SYNTHETIC_CLAIM_STORE_EVIDENCE_ID_V1 = stable_contract_id(
    "szorclaimstorefixturev1", {"fixture": "s7a-claim-store-readiness-v1"}
)
_OPENROUTER_LIVE_SAFETY_ADVERSARIAL_LIVE_CLAIM_STORE_GRANT_ID_V1 = (
    stable_contract_id(
        "szorclaimstoregrantv1",
        {"adversarial_fixture": "s7a-live-claim-store-grant-shape-v1"},
    )
)

_SYNTHETIC_SECRET_SENTINEL_V1 = "s7a-" + "secret-sentinel-value"
_SYNTHETIC_SECRET_BASE64_V1 = (
    "czdhLX" + "NlY3JldC1zZW50aW5lbC12YWx1ZQ=="
)
_FORBIDDEN_ARTIFACT_MARKERS_V1: Tuple[str, ...] = (
    '"Authoriz' + 'ation":',
    "Bearer" + " ",
    "sk-" + "or-",
    _SYNTHETIC_SECRET_SENTINEL_V1,
    _SYNTHETIC_SECRET_BASE64_V1,
    "OPENROUTER_API_" + "KEY=",
)

_S6_SEMANTIC_PREDECESSORS_V1: Tuple[Tuple[str, str], ...] = (
    (
        "backend/dialogues/socrates_zero/openrouter_live_request_overlay_v1.py",
        "484ebfa8100e481a9c6092f983b01f51933fd007",
    ),
    (
        "backend/dialogues/socrates_zero/openrouter_pre_live_cases_v1.py",
        "6a0fc0563ad485332463149ec2c50a22156736aa",
    ),
    (
        "backend/dialogues/socrates_zero/openrouter_pre_live_evaluation_v1.py",
        "3733dd1153251d918434b9a6f63e5ea83b56ed7b",
    ),
    (
        "backend/dialogues/socrates_zero/openrouter_pre_live_integration_v1.py",
        "5f7fd8ad4c889cfee5fa019b421d83e615a9c61b",
    ),
    (
        "backend/dialogues/socrates_zero/openrouter_pre_live_safety_v1.py",
        "2c32cf14477d1d6a3a19978a915fb56d5b913d30",
    ),
)
_S6_ARTIFACT_PREDECESSORS_V1: Tuple[Tuple[str, str], ...] = (
    (
        "docs/branches/feature-socrates-zero-openrouter-prelive-integration-v1/"
        "artifacts/socrateszero_openrouter_pre_live_integration_replay_execution_v1.json",
        "ff40af69cccd5297c5c0b2d65c82f25448c2e16a0f8019048916d5976afb5c27",
    ),
    (
        "docs/branches/feature-socrates-zero-openrouter-prelive-integration-v1/"
        "artifacts/socrateszero_openrouter_pre_live_integration_replay_lock_v1.json",
        "256bf8eefe71c0c1e6b468d090ca55997ddfc105065594c16ec0aeee3cf15c8a",
    ),
    (
        "docs/branches/feature-socrates-zero-openrouter-prelive-integration-v1/"
        "artifacts/socrateszero_openrouter_pre_live_integration_v1.json",
        "8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d",
    ),
)


class _FrozenLiveSafetyEvaluationContractV1(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        revalidate_instances="always",
    )


class OpenRouterLiveSafetyHypothesisStatusV1(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class OpenRouterLiveSafetyActualOutcomeV1(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INVALID_FIXTURE_CONSTRUCTION = "INVALID_FIXTURE_CONSTRUCTION"


class OpenRouterLiveSafetyReadinessV1(str, Enum):
    AUTHORIZED_PENDING_JIT_PREFLIGHT = "AUTHORIZED_PENDING_JIT_PREFLIGHT"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"


class OpenRouterLiveSafetyBoundaryCountersV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    external_network_attempts: int = Field(ge=0)
    credential_access_attempts: int = Field(ge=0)
    live_provider_calls: int = Field(ge=0)
    provider_sdk_calls: int = Field(ge=0)
    model_executions: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    canonical_application_calls: int = Field(ge=0)
    official_source_retrievals: int = Field(ge=0)
    live_dispatches: int = Field(ge=0)
    background_thread_starts: int = Field(ge=0)
    background_process_starts: int = Field(ge=0)

    @property
    def total_external_activity(self) -> int:
        return sum(self.model_dump(mode="python").values())


class OpenRouterLiveSafetyCaseResultV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    case_id: str = Field(min_length=1)
    family: OpenRouterLiveSafetyCaseFamilyV1
    kind: OpenRouterLiveSafetyCaseKindV1
    case_fingerprint: str = Field(min_length=1)
    probe: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    expected_outcome: OpenRouterLiveSafetyExpectedOutcomeV1
    actual_outcome: OpenRouterLiveSafetyActualOutcomeV1
    expected_failure_code: Optional[str] = None
    actual_failure_code: Optional[str] = None
    core_signal: str = Field(min_length=1)
    evidence_ids: Tuple[str, ...] = ()
    result_matches_expectation: bool
    result_id: Optional[str] = Field(
        default=None, pattern=r"^szorlivesafetyresultv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterLiveSafetyCaseResultV1":
        accepted = self.actual_outcome is OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
        if accepted != (self.actual_failure_code is None):
            raise ContractValidationError(
                "live-safety actual outcome disagrees with its failure code"
            )
        if tuple(sorted(set(self.evidence_ids))) != self.evidence_ids:
            raise ContractValidationError(
                "live-safety evidence IDs must be unique and sorted"
            )
        expected_match = (
            self.actual_outcome.value == self.expected_outcome.value
            and self.actual_failure_code == self.expected_failure_code
        )
        if self.result_matches_expectation is not expected_match:
            raise ContractValidationError(
                "live-safety result expectation match is not derived"
            )
        expected_id = stable_contract_id(
            "szorlivesafetyresultv1",
            self.model_dump(mode="json", exclude={"result_id"}),
        )
        if self.result_id not in (None, expected_id):
            raise ContractValidationError("live-safety result ID mismatch")
        object.__setattr__(self, "result_id", expected_id)
        return self


class OpenRouterLiveSafetyPredecessorSurfaceV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    relative_path: str = Field(min_length=1)
    digest_algorithm: Literal["GIT_BLOB_SHA1", "SHA256"]
    expected_digest: str = Field(pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
    actual_digest: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$"
    )
    unchanged: bool

    @model_validator(mode="after")
    def derive_unchanged(self) -> "OpenRouterLiveSafetyPredecessorSurfaceV1":
        if self.unchanged is not (self.actual_digest == self.expected_digest):
            raise ContractValidationError(
                "predecessor unchanged status is not digest-derived"
            )
        return self


class OpenRouterLiveSafetyPredecessorIntegrityV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_PREDECESSOR_INTEGRITY_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_PREDECESSOR_INTEGRITY_SCHEMA_V1
    surfaces: Tuple[OpenRouterLiveSafetyPredecessorSurfaceV1, ...]
    unchanged_surfaces: int = Field(ge=0)
    all_unchanged: bool
    integrity_id: Optional[str] = Field(
        default=None, pattern=r"^szorlivepredecessorintegrityv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(
        self,
    ) -> "OpenRouterLiveSafetyPredecessorIntegrityV1":
        paths = tuple(surface.relative_path for surface in self.surfaces)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ContractValidationError(
                "predecessor surfaces must be unique and stably sorted"
            )
        count = sum(surface.unchanged for surface in self.surfaces)
        if self.unchanged_surfaces != count or self.all_unchanged is not (
            count == len(self.surfaces)
        ):
            raise ContractValidationError(
                "predecessor aggregate state is not digest-derived"
            )
        expected_id = stable_contract_id(
            "szorlivepredecessorintegrityv1",
            self.model_dump(mode="json", exclude={"integrity_id"}),
        )
        if self.integrity_id not in (None, expected_id):
            raise ContractValidationError("predecessor integrity ID mismatch")
        object.__setattr__(self, "integrity_id", expected_id)
        return self


class OpenRouterLiveSafetyMetricsV1(_FrozenLiveSafetyEvaluationContractV1):
    total_cases: int = Field(ge=0)
    positive_accepted: int = Field(ge=0)
    adversarial_rejected: int = Field(ge=0)
    p17_cases: int = Field(ge=0)
    p17_positive_accepted: int = Field(ge=0)
    p17_adversarial_rejected: int = Field(ge=0)
    p19_cases: int = Field(ge=0)
    p19_positive_accepted: int = Field(ge=0)
    p19_adversarial_rejected: int = Field(ge=0)
    authorization_cases: int = Field(ge=0)
    authorization_positive_accepted: int = Field(ge=0)
    authorization_adversarial_rejected: int = Field(ge=0)
    metamorphic_cases: int = Field(ge=0)
    metamorphic_holding: int = Field(ge=0)
    requirement_tags_covered: int = Field(ge=0)
    unexpected_results: int = Field(ge=0)
    invalid_fixture_constructions: int = Field(ge=0)
    guard_code_mismatches: int = Field(ge=0)
    heuristic_p17_authority_accepted: int = Field(ge=0)
    byte_to_token_substitutions_accepted: int = Field(ge=0)
    incomplete_charge_coverage_accepted: int = Field(ge=0)
    request_fee_omission_to_zero: int = Field(ge=0)
    hidden_monetary_terms: int = Field(ge=0)
    cross_request_substitutions_accepted: int = Field(ge=0)
    authorization_reuse_accepted: int = Field(ge=0)
    consumption_rollback_accepted: int = Field(ge=0)
    credential_leakage_findings: int = Field(ge=0)
    test_fixture_promotions: int = Field(ge=0)
    external_activity: int = Field(ge=0)
    s6_predecessor_surfaces_unchanged: int = Field(ge=0)
    all_thresholds_pass: bool


@dataclass(frozen=True)
class _ProbeObservationV1:
    outcome: OpenRouterLiveSafetyActualOutcomeV1
    failure_code: Optional[str]
    core_signal: str
    evidence_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _SafetyFixtureV1:
    prepared: object
    policy: OpenRouterOperatorPriceCeilingV1
    overlay: OpenRouterLiveRequestSafetyOverlayV2
    request: OpenRouterRenderedLiveRequestV2
    output: OpenRouterOutputBoundEvidenceV2
    modality: OpenRouterLiveRequestModalityBindingV1
    limit_record: TrustedModelInputLimitRecordV1
    p17: OpenRouterP17InputBoundProofV1
    total_ceiling: OpenRouterOperatorTotalSpendCeilingV1
    cost: OpenRouterWorstCaseCostBoundV1
    transport: OpenRouterOneShotTransportPolicyV1
    readiness: OpenRouterTransportReadinessAttestationV1
    credential: OpenRouterJitCredentialPresenceAttestationV1


class _BackgroundStartTripwireV1:
    """Measure and fail closed on starts absent from the shared tripwire."""

    def __init__(self) -> None:
        self.thread_starts = 0
        self.process_starts = 0
        self._patches = []

    def _thread_start(self, *_args, **_kwargs) -> None:
        self.thread_starts += 1
        raise ContractValidationError(
            "background thread start forbidden during S7A evaluation"
        )

    def _process_start(self, *_args, **_kwargs) -> None:
        self.process_starts += 1
        raise ContractValidationError(
            "background process start forbidden during S7A evaluation"
        )

    def __enter__(self) -> "_BackgroundStartTripwireV1":
        self._patches = [
            patch.object(threading.Thread, "start", self._thread_start),
            patch.object(
                multiprocessing.process.BaseProcess,
                "start",
                self._process_start,
            ),
        ]
        for patcher in self._patches:
            patcher.start()
        return self

    def __exit__(self, *_args) -> None:
        for patcher in reversed(self._patches):
            patcher.stop()


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def _model_detail_response_bytes_v1(
    *,
    returned_model: str = "openai/gpt-4.1-mini",
    canonical_model: str = "openai/gpt-4.1-mini",
    max_prompt_tokens: object = 4096,
    context_length: object = 8192,
    alias_target: object = None,
) -> bytes:
    per_request_limits: object = (
        None
        if max_prompt_tokens is None
        else {"prompt_tokens": max_prompt_tokens}
    )
    return canonical_json(
        {
            "data": {
                "alias_target": alias_target,
                "canonical_slug": canonical_model,
                "context_length": context_length,
                "id": returned_model,
                "per_request_limits": per_request_limits,
            }
        }
    ).encode("utf-8")


@lru_cache(maxsize=32)
def _build_fixture_v1(
    repository_root_text: str,
    request_usd: str = "0.000001",
    prompt_usd: str = "1",
    completion_usd: str = "2",
    max_prompt_tokens: Optional[int] = 4096,
    context_length: Optional[int] = 8192,
    max_spend_picodollars: Optional[int] = None,
) -> _SafetyFixtureV1:
    repository_root = Path(repository_root_text)
    prepared = prepare_openrouter_route_request_v1(
        repository_root=repository_root
    )
    policy = build_openrouter_operator_price_ceiling_v1(
        prepared,
        operator_scope=OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE,
        authorized=True,
        authorization_evidence_id=(
            OPENROUTER_LIVE_SAFETY_SYNTHETIC_PRICE_GRANT_ID_V1
        ),
        prompt_usd_per_million_tokens=prompt_usd,
        completion_usd_per_million_tokens=completion_usd,
        request_usd=request_usd,
    )
    overlay = build_openrouter_live_request_overlay_v2(prepared, policy)
    request = render_openrouter_live_request_v2(prepared, overlay)
    output = derive_openrouter_output_bound_v2(request)
    modality = derive_openrouter_live_request_modality_binding_v1(request)
    limit_record = build_trusted_model_input_limit_record_from_response_v1(
        raw_response_bytes=_model_detail_response_bytes_v1(
            max_prompt_tokens=max_prompt_tokens,
            context_length=context_length,
        ),
        preflight_execution_id=(
            OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
        ),
        source_scope=OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY,
        synthetic_fixture_id=OPENROUTER_LIVE_SAFETY_SYNTHETIC_FIXTURE_ID_V1,
    )
    p17 = build_openrouter_p17_input_bound_proof_v1(
        limit_record=limit_record,
        preflight_execution_id=(
            OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
        ),
        overlay=overlay,
        rendered_request=request,
        modality_binding=modality,
        output_bound=output,
        provider_policy=policy,
    )
    exact_total = (
        p17.max_input_tokens * (policy.prompt_picodollars_per_token or 0)
        + 256 * (policy.completion_picodollars_per_token or 0)
        + (policy.request_picodollars or 0)
    )
    ceiling = build_openrouter_operator_total_spend_ceiling_v1(
        request,
        policy,
        operator_scope=OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE,
        authorized=True,
        authorization_evidence_id=(
            OPENROUTER_LIVE_SAFETY_SYNTHETIC_TOTAL_GRANT_ID_V1
        ),
        max_spend_picodollars=(
            exact_total
            if max_spend_picodollars is None
            else max_spend_picodollars
        ),
    )
    cost = compute_openrouter_worst_case_cost_bound_v1(
        request, p17, output, policy, modality, ceiling
    )
    transport = build_openrouter_one_shot_transport_policy_v1(
        request, bounded_timeout_seconds=30
    )
    readiness = attest_openrouter_transport_readiness_v1(
        transport,
        preflight_execution_id=(
            OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
        ),
        ready=True,
    )
    credential = OpenRouterJitCredentialPresenceAttestationV1(
        preflight_execution_id=(
            OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
        ),
        credential_available=OpenRouterCredentialAvailabilityV1.YES,
    )
    return _SafetyFixtureV1(
        prepared=prepared,
        policy=policy,
        overlay=overlay,
        request=request,
        output=output,
        modality=modality,
        limit_record=limit_record,
        p17=p17,
        total_ceiling=ceiling,
        cost=cost,
        transport=transport,
        readiness=readiness,
        credential=credential,
    )


def _fixture_v1(
    repository_root: Path,
    **changes: object,
) -> _SafetyFixtureV1:
    arguments = {
        "repository_root_text": str(Path(repository_root).resolve()),
        "request_usd": "0.000001",
        "prompt_usd": "1",
        "completion_usd": "2",
        "max_prompt_tokens": 4096,
        "context_length": 8192,
        "max_spend_picodollars": None,
    }
    arguments.update(changes)
    return _build_fixture_v1(**arguments)  # type: ignore[arg-type]


def _ids_v1(*values: object) -> Tuple[str, ...]:
    identities = []
    for value in values:
        for field_name in (
            "price_policy_id",
            "live_request_overlay_id",
            "rendered_request_id",
            "output_bound_evidence_id",
            "modality_binding_id",
            "source_record_identity",
            "proof_id",
            "ceiling_id",
            "bound_id",
            "policy_id",
            "attestation_id",
            "authorization_id",
            "consumption_id",
            "result_id",
        ):
            candidate = getattr(value, field_name, None)
            if isinstance(candidate, str) and candidate:
                identities.append(candidate)
                break
    return tuple(sorted(set(identities)))


def _accepted_v1(
    condition: bool,
    core_signal: str,
    *evidence: object,
) -> _ProbeObservationV1:
    if condition:
        return _ProbeObservationV1(
            OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED,
            None,
            core_signal,
            _ids_v1(*evidence),
        )
    return _ProbeObservationV1(
        OpenRouterLiveSafetyActualOutcomeV1.REJECTED,
        "PROPERTY_NOT_HOLDING",
        core_signal,
        _ids_v1(*evidence),
    )


def _property_refused_v1(
    condition: bool,
    failure_code: str,
    core_signal: str,
    *evidence: object,
) -> _ProbeObservationV1:
    if condition:
        return _ProbeObservationV1(
            OpenRouterLiveSafetyActualOutcomeV1.REJECTED,
            failure_code,
            core_signal,
            _ids_v1(*evidence),
        )
    return _ProbeObservationV1(
        OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED,
        None,
        f"{core_signal}_UNEXPECTED_ACCEPTANCE",
        _ids_v1(*evidence),
    )


def _must_refuse_v1(
    operation: Callable[[], object],
    failure_code: str,
    core_signal: str = "CONTRACT_VALIDATION_REFUSAL",
) -> _ProbeObservationV1:
    try:
        operation()
    except (ContractValidationError, ValueError, TypeError, OSError):
        return _ProbeObservationV1(
            OpenRouterLiveSafetyActualOutcomeV1.REJECTED,
            failure_code,
            core_signal,
        )
    return _ProbeObservationV1(
        OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED,
        None,
        "UNEXPECTED_CONTRACT_ACCEPTANCE",
    )


def _claim_store_readiness_v1(
    claim_directory: Path,
    *,
    mode: OpenRouterLiveSafetyModeV1 = OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
    preflight_execution_id: str = OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1,
    ready: bool = True,
) -> OpenRouterClaimStoreReadinessAttestationV1:
    """Build path-bound test evidence; physical realization remains an S7B fact."""

    evidence_id: Optional[str]
    if not ready:
        evidence_id = None
    elif mode is OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE:
        evidence_id = (
            OPENROUTER_LIVE_SAFETY_SYNTHETIC_CLAIM_STORE_EVIDENCE_ID_V1
        )
    else:
        # This correctly scoped identifier is used only by the adversarial
        # fixture-promotion probe.  It is not live operator evidence.
        evidence_id = (
            _OPENROUTER_LIVE_SAFETY_ADVERSARIAL_LIVE_CLAIM_STORE_GRANT_ID_V1
        )
    return attest_openrouter_claim_store_readiness_v1(
        Path(claim_directory),
        preflight_execution_id=preflight_execution_id,
        mode=mode,
        ready=ready,
        authorization_evidence_id=evidence_id,
    )


def _preflight_v1(
    fixture: _SafetyFixtureV1,
    claim_directory: Path,
    *,
    mode: OpenRouterLiveSafetyModeV1 = OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
    preflight_execution_id: str = OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1,
    p17: Optional[OpenRouterP17InputBoundProofV1] = None,
    request: Optional[OpenRouterRenderedLiveRequestV2] = None,
    output: Optional[OpenRouterOutputBoundEvidenceV2] = None,
    policy: Optional[OpenRouterOperatorPriceCeilingV1] = None,
    modality: Optional[OpenRouterLiveRequestModalityBindingV1] = None,
    cost: Optional[OpenRouterWorstCaseCostBoundV1] = None,
    ceiling: Optional[OpenRouterOperatorTotalSpendCeilingV1] = None,
    credential: Optional[OpenRouterJitCredentialPresenceAttestationV1] = None,
    transport: Optional[OpenRouterOneShotTransportPolicyV1] = None,
    readiness: Optional[OpenRouterTransportReadinessAttestationV1] = None,
    mapper: Optional[OpenRouterS5MapperCapabilityV1] = None,
    integration: Optional[OpenRouterS6IntegrationCapabilityV1] = None,
    claim_store_readiness: Optional[
        OpenRouterClaimStoreReadinessAttestationV1
    ] = None,
    ced_authority_enabled: bool = False,
) -> OpenRouterOneLiveCallPreflightResultV1:
    store_readiness = claim_store_readiness or _claim_store_readiness_v1(
        claim_directory,
        mode=mode,
        preflight_execution_id=preflight_execution_id,
    )
    return evaluate_one_live_call_preflight_v1(
        mode=mode,
        preflight_execution_id=preflight_execution_id,
        rendered_request=request or fixture.request,
        p17_proof=p17 or fixture.p17,
        output_bound=output or fixture.output,
        price_policy=policy or fixture.policy,
        modality_binding=modality or fixture.modality,
        cost_bound=cost or fixture.cost,
        total_spend_ceiling=ceiling or fixture.total_ceiling,
        credential_presence=credential or fixture.credential,
        transport_policy=transport or fixture.transport,
        transport_readiness=readiness or fixture.readiness,
        s5_mapper=mapper or FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
        s6_integration=(
            integration or FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1
        ),
        claim_store_readiness=store_readiness,
        claim_directory=claim_directory,
        ced_authority_enabled=ced_authority_enabled,
        runtime_authority_enabled=False,
    )


def _mint_fixture_authorization_v1(
    fixture: _SafetyFixtureV1,
    claim_directory: Path,
    *,
    mode: OpenRouterLiveSafetyModeV1 = OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
    preflight_execution_id: str = OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1,
) -> OpenRouterOneCallAuthorizationV1:
    store_readiness = _claim_store_readiness_v1(
        claim_directory,
        mode=mode,
        preflight_execution_id=preflight_execution_id,
    )
    return mint_openrouter_one_call_authorization_v1(
        mode=mode,
        preflight_execution_id=preflight_execution_id,
        rendered_request=fixture.request,
        p17_proof=fixture.p17,
        output_bound=fixture.output,
        price_policy=fixture.policy,
        modality_binding=fixture.modality,
        cost_bound=fixture.cost,
        total_spend_ceiling=fixture.total_ceiling,
        transport_policy=fixture.transport,
        s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
        s6_integration=FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1,
        claim_store_readiness=store_readiness,
    )


def _authorized_preflight_v1(
    fixture: _SafetyFixtureV1,
    claim_directory: Path,
    *,
    claim_store_readiness: Optional[
        OpenRouterClaimStoreReadinessAttestationV1
    ] = None,
) -> OpenRouterOneLiveCallPreflightResultV1:
    result = _preflight_v1(
        fixture,
        claim_directory,
        claim_store_readiness=claim_store_readiness,
    )
    if (
        result.verdict is not OpenRouterOneLiveCallVerdictV1.AUTHORIZED_FOR_ONE_CALL
        or result.authorization is None
    ):
        raise ContractValidationError(
            "synthetic baseline did not produce one authorization"
        )
    return result


def _consume_authorized_preflight_v1(
    preflight_result: OpenRouterOneLiveCallPreflightResultV1,
    *,
    fixture: _SafetyFixtureV1,
    claim_directory: Path,
    rendered_request: OpenRouterRenderedLiveRequestV2,
    transport_policy: OpenRouterOneShotTransportPolicyV1,
) -> OpenRouterOneCallConsumptionV1:
    authorization = preflight_result.authorization
    if authorization is None:
        raise ContractValidationError(
            "consumption helper requires an authorizing preflight"
        )
    store_readiness = _claim_store_readiness_v1(
        claim_directory,
        mode=preflight_result.mode,
        preflight_execution_id=preflight_result.preflight_execution_id,
    )
    return consume_openrouter_one_call_authorization_v1(
        authorization,
        preflight_result=preflight_result,
        claim_directory=claim_directory,
        rendered_request=rendered_request,
        transport_policy=transport_policy,
        p17_proof=fixture.p17,
        output_bound=fixture.output,
        price_policy=fixture.policy,
        modality_binding=fixture.modality,
        cost_bound=fixture.cost,
        total_spend_ceiling=fixture.total_ceiling,
        credential_presence=fixture.credential,
        transport_readiness=fixture.readiness,
        s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
        s6_integration=FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1,
        claim_store_readiness=store_readiness,
    )


def _observe_preflight_v1(
    result: OpenRouterOneLiveCallPreflightResultV1,
) -> _ProbeObservationV1:
    if result.verdict is OpenRouterOneLiveCallVerdictV1.AUTHORIZED_FOR_ONE_CALL:
        return _ProbeObservationV1(
            OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED,
            None,
            "PREFLIGHT_AUTHORIZED_FOR_ONE_CALL",
            (),
        )
    code = result.first_failure_code
    return _ProbeObservationV1(
        OpenRouterLiveSafetyActualOutcomeV1.REJECTED,
        code.value if code is not None else "PREFLIGHT_REFUSED_WITHOUT_CODE",
        f"PREFLIGHT_{code.value if code is not None else 'MISSING_CODE'}",
        _ids_v1(result),
    )


def _revalidate_mutation_v1(
    value: BaseModel,
    contract_type,
    *,
    changes: Optional[Dict[str, object]] = None,
    remove: Tuple[str, ...] = (),
):
    payload = value.model_dump(mode="python")
    for field_name in remove:
        payload.pop(field_name, None)
    payload.update(changes or {})
    return contract_type.model_validate(payload)


def _evaluate_p17_probe_v1(
    probe: str, repository_root: Path
) -> _ProbeObservationV1:
    fixture = _fixture_v1(repository_root)
    record = fixture.limit_record

    if probe == "P17_VALID_TRUSTED_LIMIT":
        return _accepted_v1(
            fixture.p17.max_input_tokens == record.limit_tokens
            and fixture.p17.limit_kind is OpenRouterInputLimitKindV1.MAX_PROMPT_TOKENS
            and fixture.p17.authority
            is OpenRouterP17ProofAuthorityV1.SYNTHETIC_TEST_ONLY
            and fixture.p17.request_body_sha256 == fixture.request.body_sha256,
            "TRUSTED_LIMIT_BOUND_TO_EXACT_REQUEST",
            record,
            fixture.p17,
        )
    if probe == "P17_VALID_JIT_RECORD":
        context_fixture = _fixture_v1(
            repository_root,
            max_prompt_tokens=None,
            context_length=8192,
        )
        context_record = context_fixture.limit_record
        return _accepted_v1(
            context_record.limit_kind
            is OpenRouterInputLimitKindV1.MODEL_CONTEXT_LIMIT
            and context_record.limit_tokens == 8192
            and context_fixture.p17.max_input_tokens == 8192
            and context_record.preflight_execution_id
            == OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1,
            "STRUCTURALLY_FRESH_EXACT_MODEL_RECORD",
            context_record,
            context_fixture.p17,
        )
    if probe == "P17_BYTE_LENGTH":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"limit_tokens": fixture.request.body_length},
            ),
            "P17_METHOD_NOT_AUTHORITATIVE",
        )
    if probe == "P17_CHARACTER_COUNT":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={
                    "limit_tokens": len(fixture.request.canonical_body_json)
                },
            ),
            "P17_METHOD_NOT_AUTHORITATIVE",
        )
    if probe == "P17_CHARS_PER_TOKEN":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"limit_tokens": 256},
            ),
            "P17_METHOD_NOT_AUTHORITATIVE",
        )
    if probe == "P17_TOKENIZER_FAMILY":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"proof_method_version": "TOKENIZER_FAMILY_LABEL"},
            ),
            "P17_TOKENIZER_BINDING_INCOMPLETE",
        )
    if probe == "P17_TOKENIZER_VERSION_ABSENT":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                remove=("proof_method_version",),
            ),
            "P17_TOKENIZER_BINDING_INCOMPLETE",
        )
    if probe == "P17_TOKENIZER_DATA_ABSENT":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"tokenizer_data_identity": None},
            ),
            "P17_TOKENIZER_BINDING_INCOMPLETE",
        )
    if probe == "P17_MODEL_TOKENIZER_AUTHORITY_ABSENT":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"model_tokenizer_authority": None},
            ),
            "P17_TOKENIZER_BINDING_INCOMPLETE",
        )
    if probe == "P17_CHAT_FRAMING_UNBOUNDED":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"framing_coverage": "UNBOUNDED"},
            ),
            "P17_FRAMING_NOT_BOUNDED",
        )
    if probe == "P17_WRONG_MODEL":
        return _must_refuse_v1(
            lambda: build_trusted_model_input_limit_record_from_response_v1(
                raw_response_bytes=_model_detail_response_bytes_v1(
                    returned_model="openai/gpt-4.1"
                ),
                preflight_execution_id=(
                    OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                ),
                source_scope=(
                    OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY
                ),
                synthetic_fixture_id=(
                    OPENROUTER_LIVE_SAFETY_SYNTHETIC_FIXTURE_ID_V1
                ),
            ),
            "P17_MODEL_MISMATCH",
        )
    if probe == "P17_SIBLING_REQUEST":
        sibling = _fixture_v1(repository_root, request_usd="0.000001000001")
        return _must_refuse_v1(
            lambda: build_openrouter_p17_input_bound_proof_v1(
                limit_record=record,
                preflight_execution_id=(
                    OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                ),
                overlay=fixture.overlay,
                rendered_request=sibling.request,
                modality_binding=sibling.modality,
                output_bound=sibling.output,
                provider_policy=fixture.policy,
            ),
            "P17_REQUEST_MISMATCH",
        )
    if probe == "P17_MALFORMED_LIMIT":
        return _must_refuse_v1(
            lambda: build_trusted_model_input_limit_record_from_response_v1(
                raw_response_bytes=_model_detail_response_bytes_v1(
                    max_prompt_tokens="4096"
                ),
                preflight_execution_id=(
                    OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                ),
                source_scope=(
                    OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY
                ),
                synthetic_fixture_id=(
                    OPENROUTER_LIVE_SAFETY_SYNTHETIC_FIXTURE_ID_V1
                ),
            ),
            "P17_LIMIT_INVALID",
        )
    if probe == "P17_NEGATIVE_LIMIT":
        return _must_refuse_v1(
            lambda: build_trusted_model_input_limit_record_from_response_v1(
                raw_response_bytes=_model_detail_response_bytes_v1(
                    max_prompt_tokens=-1
                ),
                preflight_execution_id=(
                    OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                ),
                source_scope=(
                    OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY
                ),
                synthetic_fixture_id=(
                    OPENROUTER_LIVE_SAFETY_SYNTHETIC_FIXTURE_ID_V1
                ),
            ),
            "P17_LIMIT_INVALID",
        )
    if probe == "P17_ZERO_LIMIT":
        return _must_refuse_v1(
            lambda: build_trusted_model_input_limit_record_from_response_v1(
                raw_response_bytes=_model_detail_response_bytes_v1(
                    max_prompt_tokens=0
                ),
                preflight_execution_id=(
                    OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                ),
                source_scope=(
                    OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY
                ),
                synthetic_fixture_id=(
                    OPENROUTER_LIVE_SAFETY_SYNTHETIC_FIXTURE_ID_V1
                ),
            ),
            "P17_LIMIT_INVALID",
        )
    if probe == "P17_AMBIGUOUS_LIMIT_KIND":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"limit_kind": "AMBIGUOUS_MODEL_LIMIT"},
            ),
            "P17_LIMIT_KIND_AMBIGUOUS",
        )
    if probe == "P17_UNTRUSTED_SOURCE":
        with tempfile.TemporaryDirectory(prefix="s7a-p17-untrusted-") as temp:
            result = _preflight_v1(
                fixture,
                Path(temp),
                mode=OpenRouterLiveSafetyModeV1.LIVE_JIT,
            )
        return _observe_preflight_v1(result)
    if probe == "P17_SOURCE_DIGEST_MISMATCH":
        digest = record.source_evidence_digest
        replacement = ("0" if digest[0] != "0" else "1") + digest[1:]
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                record,
                TrustedModelInputLimitRecordV1,
                changes={"source_evidence_digest": replacement},
            ),
            "P17_SOURCE_DIGEST_MISMATCH",
        )
    if probe == "P17_STALE_JIT_RECORD":
        with tempfile.TemporaryDirectory(prefix="s7a-p17-stale-") as temp:
            result = _preflight_v1(
                fixture,
                Path(temp),
                preflight_execution_id="s7a-sibling-preflight-v1",
            )
        return _observe_preflight_v1(result)
    if probe == "P17_OUTPUT_BOUND_SUBSTITUTION":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.p17,
                OpenRouterP17InputBoundProofV1,
                changes={"max_input_tokens": fixture.output.max_output_tokens},
            ),
            "P17_METHOD_NOT_AUTHORITATIVE",
        )
    raise ContractValidationError(f"unknown P17 probe {probe}")


def _evaluate_p19_probe_v1(
    probe: str, repository_root: Path
) -> _ProbeObservationV1:
    fixture = _fixture_v1(repository_root)
    policy = fixture.policy

    if probe == "P19_COMPLETE_PRICE_POLICY":
        return _accepted_v1(
            policy.has_complete_text_request_coverage
            and policy.prompt_picodollars_per_token is not None
            and policy.completion_picodollars_per_token is not None
            and policy.request_picodollars is not None,
            "ALL_APPLICABLE_PRICE_COMPONENTS_BOUND",
            policy,
        )
    if probe == "P19_EXPLICIT_ZERO_REQUEST_FEE":
        zero = _fixture_v1(repository_root, request_usd="0")
        return _accepted_v1(
            zero.policy.request_usd == "0"
            and zero.policy.request_picodollars == 0
            and zero.policy.has_complete_text_request_coverage,
            "EXPLICIT_ZERO_PRESERVED_AS_BOUND",
            zero.policy,
            zero.cost,
        )
    if probe == "P19_POSITIVE_REQUEST_FEE_ONCE":
        request_components = tuple(
            component
            for component in fixture.cost.charge_components
            if component.charge_class == "request"
        )
        component = request_components[0]
        other_total = sum(
            candidate.subtotal_picodollars or 0
            for candidate in fixture.cost.charge_components
            if candidate.charge_class != "request"
        )
        return _accepted_v1(
            len(request_components) == 1
            and component.quantity == 1
            and component.subtotal_picodollars == policy.request_picodollars
            and fixture.cost.max_total_cost_picodollars
            == other_total + (policy.request_picodollars or 0),
            "REQUEST_FEE_INCLUDED_EXACTLY_ONCE",
            component,
            fixture.cost,
        )
    if probe == "P19_TEXT_ONLY_MODALITY":
        return _accepted_v1(
            fixture.modality.text_only
            and fixture.modality.image_parts == 0
            and fixture.modality.audio_parts == 0
            and tuple(
                component.state
                for component in fixture.cost.charge_components[-2:]
            )
            == (
                OpenRouterChargeClassStateV1.NOT_APPLICABLE,
                OpenRouterChargeClassStateV1.NOT_APPLICABLE,
            ),
            "EXACT_TEXT_ONLY_MODALITY_BOUND",
            fixture.modality,
            fixture.cost,
        )
    if probe == "P19_COMPLETE_COST_BOUND":
        return _accepted_v1(
            fixture.cost.applicable_charge_coverage
            is OpenRouterChargeCoverageV1.COMPLETE
            and tuple(
                component.charge_class
                for component in fixture.cost.charge_components
            )
            == FROZEN_OPENROUTER_P19_CHARGE_CLASSES_V1
            and fixture.cost.proof_method_id
            == OPENROUTER_P19_PROOF_METHOD_ID_V1,
            "CANONICAL_FIVE_CLASS_COST_BOUND",
            fixture.cost,
        )
    if probe == "P19_COST_EQUALS_TOTAL_CEILING":
        return _accepted_v1(
            fixture.cost.max_total_cost_picodollars
            == fixture.total_ceiling.max_spend_picodollars
            and fixture.cost.within_operator_ceiling,
            "INCLUSIVE_TOTAL_CEILING_EQUALITY",
            fixture.total_ceiling,
            fixture.cost,
        )

    if probe in {
        "P19_REQUEST_FEE_ABSENT",
        "P19_REQUEST_FEE_NONE",
        "P19_REQUEST_FEE_MALFORMED",
        "P19_REQUEST_FEE_NEGATIVE",
        "P19_REQUEST_FEE_FLOAT",
        "P19_PROMPT_CEILING_ABSENT",
        "P19_COMPLETION_CEILING_ABSENT",
    }:
        removals: Tuple[str, ...] = ()
        changes: Dict[str, object] = {}
        failure = "PRICE_POLICY_INCOMPLETE"
        if probe == "P19_REQUEST_FEE_ABSENT":
            removals = ("request_usd",)
        elif probe == "P19_REQUEST_FEE_NONE":
            changes = {"request_usd": None}
        elif probe == "P19_REQUEST_FEE_MALFORMED":
            changes = {"request_usd": "not-money"}
            failure = "PRICE_COMPONENT_INVALID"
        elif probe == "P19_REQUEST_FEE_NEGATIVE":
            changes = {"request_usd": "-0.01"}
            failure = "PRICE_COMPONENT_INVALID"
        elif probe == "P19_REQUEST_FEE_FLOAT":
            changes = {"request_usd": 0.01}
            failure = "PRICE_COMPONENT_INVALID"
        elif probe == "P19_PROMPT_CEILING_ABSENT":
            removals = ("prompt_usd_per_million_tokens",)
        else:
            removals = ("completion_usd_per_million_tokens",)
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                policy,
                OpenRouterOperatorPriceCeilingV1,
                changes=changes,
                remove=removals,
            ),
            failure,
        )
    if probe == "P19_APPLICABLE_CHARGE_UNBOUNDED":
        return _must_refuse_v1(
            lambda: OpenRouterP19CostComponentV1(
                charge_class="request",
                state=OpenRouterChargeClassStateV1.UNBOUNDED,
            ),
            "PRICE_POLICY_INCOMPLETE",
        )
    if probe == "P19_MEDIA_FALSE_NON_APPLICABILITY":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.modality,
                OpenRouterLiveRequestModalityBindingV1,
                changes={"image_parts": 1, "text_only": False},
            ),
            "MODALITY_PROOF_MISMATCH",
        )
    if probe == "P19_ARITHMETIC_OVERFLOW":
        return _must_refuse_v1(
            lambda: _fixture_v1(
                repository_root,
                prompt_usd="1000000000000000000",
                max_spend_picodollars=10**24,
            ),
            "COST_ARITHMETIC_INVALID",
        )
    if probe == "P19_PRICE_POLICY_ID_MISMATCH":
        policy_id = policy.price_policy_id or ""
        replacement = policy_id[:-1] + ("0" if policy_id[-1] != "0" else "1")
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                policy,
                OpenRouterOperatorPriceCeilingV1,
                changes={"price_policy_id": replacement},
            ),
            "PRICE_POLICY_MISMATCH",
        )
    if probe == "P19_SIBLING_OVERLAY":
        sibling = _fixture_v1(repository_root, request_usd="0.000001000001")
        return _must_refuse_v1(
            lambda: compute_openrouter_worst_case_cost_bound_v1(
                sibling.request,
                fixture.p17,
                fixture.output,
                fixture.policy,
                fixture.modality,
                fixture.total_ceiling,
            ),
            "REQUEST_MISMATCH",
        )
    if probe == "P19_WITHOUT_P17":
        return _must_refuse_v1(
            lambda: compute_openrouter_worst_case_cost_bound_v1(
                fixture.request,
                None,  # type: ignore[arg-type]
                fixture.output,
                fixture.policy,
                fixture.modality,
                fixture.total_ceiling,
            ),
            "P17_NOT_ESTABLISHED",
        )
    if probe == "P19_WITHOUT_TOTAL_SPEND":
        return _must_refuse_v1(
            lambda: compute_openrouter_worst_case_cost_bound_v1(
                fixture.request,
                fixture.p17,
                fixture.output,
                fixture.policy,
                fixture.modality,
                None,  # type: ignore[arg-type]
            ),
            "TOTAL_SPEND_CEILING_MISSING",
        )
    if probe == "P19_ONE_PICODOLLAR_OVER":
        below = _fixture_v1(
            repository_root,
            max_spend_picodollars=(
                fixture.cost.max_total_cost_picodollars - 1
            ),
        )
        return _property_refused_v1(
            not below.cost.within_operator_ceiling
            and below.cost.max_total_cost_picodollars
            == below.total_ceiling.max_spend_picodollars + 1,
            "COST_EXCEEDS_TOTAL_SPEND_CEILING",
            "ONE_PICODOLLAR_BOUNDARY_REFUSAL",
            below.total_ceiling,
            below.cost,
        )
    if probe == "P19_HIDDEN_TERM_FORMULA":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.cost,
                OpenRouterWorstCaseCostBoundV1,
                changes={
                    "formula": (
                        "max_total_cost = max_input_tokens * "
                        "prompt_price_ceiling + 256 * completion_price_ceiling"
                    )
                },
            ),
            "FORMULA_COMPONENT_MISMATCH",
        )
    if probe == "P19_HIDDEN_TERM_ARITHMETIC":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.cost,
                OpenRouterWorstCaseCostBoundV1,
                changes={
                    "max_total_cost_picodollars": (
                        fixture.cost.max_total_cost_picodollars
                        - (fixture.policy.request_picodollars or 0)
                    )
                },
            ),
            "FORMULA_COMPONENT_MISMATCH",
        )
    if probe == "P19_TEST_FIXTURE_PROMOTION":
        with tempfile.TemporaryDirectory(prefix="s7a-live-promotion-") as temp:
            claim_directory = Path(temp)
            store_readiness = _claim_store_readiness_v1(
                claim_directory,
                mode=OpenRouterLiveSafetyModeV1.LIVE_JIT,
            )
            return _must_refuse_v1(
                lambda: mint_openrouter_one_call_authorization_v1(
                    mode=OpenRouterLiveSafetyModeV1.LIVE_JIT,
                    preflight_execution_id=(
                        OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                    ),
                    rendered_request=fixture.request,
                    p17_proof=fixture.p17,
                    output_bound=fixture.output,
                    price_policy=fixture.policy,
                    modality_binding=fixture.modality,
                    cost_bound=fixture.cost,
                    total_spend_ceiling=fixture.total_ceiling,
                    transport_policy=fixture.transport,
                    s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
                    s6_integration=(
                        FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1
                    ),
                    claim_store_readiness=store_readiness,
                ),
                "TEST_FIXTURE_NOT_AUTHORIZED",
            )
    raise ContractValidationError(f"unknown P19 probe {probe}")


def _evaluate_authorization_probe_v1(
    probe: str, repository_root: Path
) -> _ProbeObservationV1:
    fixture = _fixture_v1(repository_root)
    sibling = _fixture_v1(repository_root, request_usd="0.000001000001")

    if probe == "AUTH_FRESH":
        with tempfile.TemporaryDirectory(prefix="s7a-fresh-auth-") as temp:
            preflight = _authorized_preflight_v1(fixture, Path(temp))
            authorization = preflight.authorization
            assert authorization is not None
            holds = (
                authorization.authorization_state == "FRESH"
                and authorization.allowed_local_dispatches == 1
                and authorization.automatic_retries is False
                and not hasattr(authorization, "credential_attestation_id")
            )
        return _accepted_v1(
            holds,
            "FRESH_CONTENT_ADDRESSED_ONE_CALL_AUTHORIZATION",
        )
    if probe == "AUTH_FIRST_CONSUMPTION":
        with tempfile.TemporaryDirectory(prefix="s7a-first-consumption-") as temp:
            claim_directory = Path(temp)
            preflight = _authorized_preflight_v1(fixture, claim_directory)
            authorization = preflight.authorization
            assert authorization is not None
            consumption = _consume_authorized_preflight_v1(
                preflight,
                fixture=fixture,
                claim_directory=claim_directory,
                rendered_request=fixture.request,
                transport_policy=fixture.transport,
            )
            claim = openrouter_authorization_claim_path_v1(
                claim_directory, authorization.authorization_id or ""
            )
            holds = (
                consumption.consumption_state == "CONSUMED"
                and consumption.dispatch_ordinal == 1
                and claim.exists()
            )
        return _accepted_v1(
            holds,
            "ATOMIC_FIRST_CONSUMPTION",
        )
    if probe == "AUTH_SYNTHETIC_PREFLIGHT":
        with tempfile.TemporaryDirectory(prefix="s7a-valid-preflight-") as temp:
            result = _preflight_v1(fixture, Path(temp))
        return _observe_preflight_v1(result)
    if probe == "AUTH_REUSED":
        with tempfile.TemporaryDirectory(prefix="s7a-auth-reuse-") as temp:
            claim_directory = Path(temp)
            preflight = _authorized_preflight_v1(fixture, claim_directory)
            _consume_authorized_preflight_v1(
                preflight,
                fixture=fixture,
                claim_directory=claim_directory,
                rendered_request=fixture.request,
                transport_policy=fixture.transport,
            )
            result = _preflight_v1(fixture, claim_directory)
        return _observe_preflight_v1(result)
    if probe == "AUTH_WRONG_REQUEST":
        with tempfile.TemporaryDirectory(prefix="s7a-auth-request-mix-") as temp:
            claim_directory = Path(temp)
            preflight = _authorized_preflight_v1(fixture, claim_directory)
            return _must_refuse_v1(
                lambda: _consume_authorized_preflight_v1(
                    preflight,
                    fixture=fixture,
                    claim_directory=claim_directory,
                    rendered_request=sibling.request,
                    transport_policy=sibling.transport,
                ),
                "AUTHORIZATION_REQUEST_MISMATCH",
            )
    if probe == "AUTH_STALE_P17":
        with tempfile.TemporaryDirectory(prefix="s7a-stale-auth-") as temp:
            stale_execution_id = "s7a-stale-authorization-v1"
            store_readiness = _claim_store_readiness_v1(
                Path(temp),
                preflight_execution_id=stale_execution_id,
            )
            return _must_refuse_v1(
                lambda: mint_openrouter_one_call_authorization_v1(
                    mode=OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
                    preflight_execution_id=stale_execution_id,
                    rendered_request=fixture.request,
                    p17_proof=fixture.p17,
                    output_bound=fixture.output,
                    price_policy=fixture.policy,
                    modality_binding=fixture.modality,
                    cost_bound=fixture.cost,
                    total_spend_ceiling=fixture.total_ceiling,
                    transport_policy=fixture.transport,
                    s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
                    s6_integration=(
                        FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1
                    ),
                    claim_store_readiness=store_readiness,
                ),
                "AUTHORIZATION_P17_MISMATCH",
            )
    if probe == "AUTH_WRONG_PRICE_POLICY":
        with tempfile.TemporaryDirectory(prefix="s7a-wrong-price-auth-") as temp:
            store_readiness = _claim_store_readiness_v1(Path(temp))
            return _must_refuse_v1(
                lambda: mint_openrouter_one_call_authorization_v1(
                    mode=OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
                    preflight_execution_id=(
                        OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                    ),
                    rendered_request=fixture.request,
                    p17_proof=fixture.p17,
                    output_bound=fixture.output,
                    price_policy=sibling.policy,
                    modality_binding=fixture.modality,
                    cost_bound=fixture.cost,
                    total_spend_ceiling=fixture.total_ceiling,
                    transport_policy=fixture.transport,
                    s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
                    s6_integration=(
                        FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1
                    ),
                    claim_store_readiness=store_readiness,
                ),
                "AUTHORIZATION_PRICE_POLICY_MISMATCH",
            )
    if probe == "AUTH_WRONG_TOTAL_SPEND":
        with tempfile.TemporaryDirectory(prefix="s7a-wrong-total-auth-") as temp:
            store_readiness = _claim_store_readiness_v1(Path(temp))
            return _must_refuse_v1(
                lambda: mint_openrouter_one_call_authorization_v1(
                    mode=OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
                    preflight_execution_id=(
                        OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                    ),
                    rendered_request=fixture.request,
                    p17_proof=fixture.p17,
                    output_bound=fixture.output,
                    price_policy=fixture.policy,
                    modality_binding=fixture.modality,
                    cost_bound=fixture.cost,
                    total_spend_ceiling=sibling.total_ceiling,
                    transport_policy=fixture.transport,
                    s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
                    s6_integration=(
                        FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1
                    ),
                    claim_store_readiness=store_readiness,
                ),
                "AUTHORIZATION_TOTAL_SPEND_MISMATCH",
            )
    if probe == "AUTH_DISPATCH_CAP_GT_ONE":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.transport,
                OpenRouterOneShotTransportPolicyV1,
                changes={"maximum_local_dispatches": 2},
            ),
            "AUTHORIZATION_DISPATCH_CAP_INVALID",
        )
    if probe == "AUTH_CED_ENABLED":
        with tempfile.TemporaryDirectory(prefix="s7a-ced-refusal-") as temp:
            result = _preflight_v1(
                fixture,
                Path(temp),
                ced_authority_enabled=True,
            )
        return _observe_preflight_v1(result)
    if probe == "AUTH_S5_MAPPER_ABSENT":
        unavailable = OpenRouterS5MapperCapabilityV1(available=False)
        with tempfile.TemporaryDirectory(prefix="s7a-s5-refusal-") as temp:
            result = _preflight_v1(
                fixture,
                Path(temp),
                mapper=unavailable,
            )
        return _observe_preflight_v1(result)
    if probe == "AUTH_S6_INTEGRATION_ABSENT":
        unavailable = OpenRouterS6IntegrationCapabilityV1(available=False)
        with tempfile.TemporaryDirectory(prefix="s7a-s6-refusal-") as temp:
            result = _preflight_v1(
                fixture,
                Path(temp),
                integration=unavailable,
            )
        return _observe_preflight_v1(result)
    if probe == "AUTH_CREDENTIAL_VALUE":
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.credential,
                OpenRouterJitCredentialPresenceAttestationV1,
                changes={"credential_value": _SYNTHETIC_SECRET_SENTINEL_V1},
            ),
            "CREDENTIAL_VALUE_FORBIDDEN",
        )
    if probe == "AUTH_ID_MUTATION":
        with tempfile.TemporaryDirectory(prefix="s7a-auth-id-") as temp:
            authorization = _mint_fixture_authorization_v1(
                fixture, Path(temp)
            )
            authorization_id = authorization.authorization_id or ""
            replacement = authorization_id[:-1] + (
                "0" if authorization_id[-1] != "0" else "1"
            )
            return _must_refuse_v1(
                lambda: _revalidate_mutation_v1(
                    authorization,
                    OpenRouterOneCallAuthorizationV1,
                    changes={"authorization_id": replacement},
                ),
                "AUTHORIZATION_ID_MISMATCH",
            )
    if probe == "AUTH_CONSUMPTION_ROLLBACK":
        with tempfile.TemporaryDirectory(prefix="s7a-rollback-refusal-") as temp:
            claim_directory = Path(temp)
            store_readiness = _claim_store_readiness_v1(claim_directory)
            preflight = _authorized_preflight_v1(
                fixture,
                claim_directory,
                claim_store_readiness=store_readiness,
            )
            authorization = preflight.authorization
            assert authorization is not None
            consumption = _consume_authorized_preflight_v1(
                preflight,
                fixture=fixture,
                claim_directory=claim_directory,
                rendered_request=fixture.request,
                transport_policy=fixture.transport,
            )
            claim = openrouter_authorization_claim_path_v1(
                claim_directory, authorization.authorization_id or ""
            )
            freshness_mutation = _must_refuse_v1(
                lambda: _revalidate_mutation_v1(
                    consumption,
                    OpenRouterOneCallConsumptionV1,
                    changes={"consumption_state": "FRESH"},
                ),
                "CONSUMPTION_ROLLBACK",
            )
            reuse = _must_refuse_v1(
                lambda: _consume_authorized_preflight_v1(
                    preflight,
                    fixture=fixture,
                    claim_directory=claim_directory,
                    rendered_request=fixture.request,
                    transport_policy=fixture.transport,
                ),
                "CONSUMPTION_ROLLBACK",
            )
            result = _preflight_v1(
                fixture,
                claim_directory,
                claim_store_readiness=store_readiness,
            )
            refused = (
                claim.exists()
                and consumption.failed_call_does_not_restore_authorization
                and authorization.claim_store_readiness_attestation_id
                == store_readiness.attestation_id
                and consumption.claim_store_readiness_attestation_id
                == store_readiness.attestation_id
                and freshness_mutation.outcome
                is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
                and reuse.outcome is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
                and result.first_failure_code
                is OpenRouterOneLiveCallFailureCodeV1.AUTHORIZATION_ALREADY_CONSUMED
            )
        return _property_refused_v1(
            refused,
            "CONSUMPTION_ROLLBACK",
            "ATTESTED_STORE_REJECTS_FRESHNESS_MUTATION_AND_REUSE",
            result,
        )
    if probe == "CROSS_P17_A_REQUEST_B":
        return _must_refuse_v1(
            lambda: compute_openrouter_worst_case_cost_bound_v1(
                sibling.request,
                fixture.p17,
                sibling.output,
                sibling.policy,
                sibling.modality,
                sibling.total_ceiling,
            ),
            "AUTHORIZATION_REQUEST_MISMATCH",
        )
    if probe == "CROSS_PRICE_A_REQUEST_B":
        return _must_refuse_v1(
            lambda: build_openrouter_operator_total_spend_ceiling_v1(
                sibling.request,
                fixture.policy,
                operator_scope=OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE,
                authorized=True,
                authorization_evidence_id=(
                    OPENROUTER_LIVE_SAFETY_SYNTHETIC_TOTAL_GRANT_ID_V1
                ),
                max_spend_picodollars=(
                    sibling.cost.max_total_cost_picodollars
                ),
            ),
            "AUTHORIZATION_PRICE_POLICY_MISMATCH",
        )
    if probe == "CROSS_COST_A_AUTH_B":
        with tempfile.TemporaryDirectory(prefix="s7a-cross-cost-auth-") as temp:
            store_readiness = _claim_store_readiness_v1(Path(temp))
            return _must_refuse_v1(
                lambda: mint_openrouter_one_call_authorization_v1(
                    mode=OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
                    preflight_execution_id=(
                        OPENROUTER_LIVE_SAFETY_PREFLIGHT_EXECUTION_ID_V1
                    ),
                    rendered_request=sibling.request,
                    p17_proof=sibling.p17,
                    output_bound=sibling.output,
                    price_policy=sibling.policy,
                    modality_binding=sibling.modality,
                    cost_bound=fixture.cost,
                    total_spend_ceiling=sibling.total_ceiling,
                    transport_policy=sibling.transport,
                    s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
                    s6_integration=(
                        FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1
                    ),
                    claim_store_readiness=store_readiness,
                ),
                "AUTHORIZATION_COST_BOUND_MISMATCH",
            )
    if probe == "CROSS_AUTH_A_TRANSPORT_B":
        with tempfile.TemporaryDirectory(prefix="s7a-cross-transport-") as temp:
            claim_directory = Path(temp)
            preflight = _authorized_preflight_v1(fixture, claim_directory)
            return _must_refuse_v1(
                lambda: _consume_authorized_preflight_v1(
                    preflight,
                    fixture=fixture,
                    claim_directory=claim_directory,
                    rendered_request=fixture.request,
                    transport_policy=sibling.transport,
                ),
                "AUTHORIZATION_TRANSPORT_MISMATCH",
            )
    if probe == "CROSS_CONSUMPTION_A_REQUEST_B":
        with tempfile.TemporaryDirectory(prefix="s7a-cross-consumption-") as temp:
            claim_directory = Path(temp)
            preflight = _authorized_preflight_v1(fixture, claim_directory)
            consumption = _consume_authorized_preflight_v1(
                preflight,
                fixture=fixture,
                claim_directory=claim_directory,
                rendered_request=fixture.request,
                transport_policy=fixture.transport,
            )
        return _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                consumption,
                OpenRouterOneCallConsumptionV1,
                changes={
                    "rendered_request_id": sibling.request.rendered_request_id
                },
            ),
            "AUTHORIZATION_REQUEST_MISMATCH",
        )
    raise ContractValidationError(f"unknown authorization probe {probe}")


def _evaluate_metamorphic_probe_v1(
    probe: str, repository_root: Path
) -> _ProbeObservationV1:
    fixture = _fixture_v1(repository_root)
    sibling = _fixture_v1(repository_root, request_usd="0.000001000001")

    if probe == "META_DETERMINISTIC_REBUILD":
        cases = tuple(
            case
            for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
            if case.probe != "META_DETERMINISTIC_REBUILD"
        )
        first = tuple(_evaluate_case_v1(case, repository_root) for case in cases)
        second = tuple(_evaluate_case_v1(case, repository_root) for case in cases)
        return _accepted_v1(
            first == second
            and tuple(result.result_id for result in first)
            == tuple(result.result_id for result in second),
            "TWO_SEMANTIC_REBUILDS_EQUAL",
        )
    if probe == "META_SAME_INPUTS_SAME_IDS":
        rebuilt_policy = OpenRouterOperatorPriceCeilingV1.model_validate(
            fixture.policy.model_dump(mode="python")
        )
        rebuilt_request = OpenRouterRenderedLiveRequestV2.model_validate(
            fixture.request.model_dump(mode="python")
        )
        rebuilt_p17 = OpenRouterP17InputBoundProofV1.model_validate(
            fixture.p17.model_dump(mode="python")
        )
        return _accepted_v1(
            rebuilt_policy.price_policy_id == fixture.policy.price_policy_id
            and rebuilt_request.rendered_request_id
            == fixture.request.rendered_request_id
            and rebuilt_p17.proof_id == fixture.p17.proof_id,
            "CONTENT_IDS_STABLE_FOR_EQUAL_INPUTS",
            rebuilt_policy,
            rebuilt_request,
            rebuilt_p17,
        )
    if probe == "META_EQUIVALENT_PRICE_TEXT":
        equivalent_policy = build_openrouter_operator_price_ceiling_v1(
            fixture.prepared,  # type: ignore[arg-type]
            operator_scope=OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE,
            authorized=True,
            authorization_evidence_id=(
                OPENROUTER_LIVE_SAFETY_SYNTHETIC_PRICE_GRANT_ID_V1
            ),
            prompt_usd_per_million_tokens="1.0",
            completion_usd_per_million_tokens="2.00",
            request_usd="0.0000010",
        )
        return _accepted_v1(
            equivalent_policy == fixture.policy
            and equivalent_policy.price_policy_id == fixture.policy.price_policy_id,
            "CANONICAL_DECIMAL_TEXT_NORMALIZATION",
            equivalent_policy,
            fixture.policy,
        )
    if probe == "META_ONE_PICODOLLAR_POLICY":
        return _accepted_v1(
            sibling.policy.request_picodollars
            == (fixture.policy.request_picodollars or 0) + 1
            and sibling.policy.price_policy_id != fixture.policy.price_policy_id
            and sibling.request.rendered_request_id
            != fixture.request.rendered_request_id,
            "ONE_PICODOLLAR_INVALIDATES_POLICY_ID",
            fixture.policy,
            sibling.policy,
        )
    if probe == "META_REQUEST_BYTES_INVALIDATE":
        with tempfile.TemporaryDirectory(prefix="s7a-meta-request-bytes-") as temp:
            claim_directory = Path(temp)
            authorization = _mint_fixture_authorization_v1(
                fixture, claim_directory
            )
            sibling_authorization = _mint_fixture_authorization_v1(
                sibling, claim_directory
            )
            refusal = _must_refuse_v1(
                lambda: compute_openrouter_worst_case_cost_bound_v1(
                    sibling.request,
                    fixture.p17,
                    sibling.output,
                    sibling.policy,
                    sibling.modality,
                    sibling.total_ceiling,
                ),
                "REQUEST_BYTES_INVALIDATE_OLD_AUTHORITY",
            )
            return _accepted_v1(
                refusal.outcome is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
                and sibling.request.body_sha256 != fixture.request.body_sha256
                and sibling_authorization.authorization_id
                != authorization.authorization_id,
                "REQUEST_BYTE_CHANGE_INVALIDATES_P17_AND_AUTHORIZATION",
                fixture.request,
                sibling.request,
            )
    if probe == "META_REQUEST_COMPONENT_IDENTITY":
        prepared = fixture.prepared
        return _accepted_v1(
            fixture.request.body_sha256 != getattr(prepared, "body_sha256")
            and fixture.request.body_length != getattr(prepared, "body_length")
            and fixture.request.rendered_request_id
            not in {
                getattr(prepared, "prepared_request_id"),
                getattr(prepared.request_intent_receipt, "receipt_id"),
            },
            "REQUEST_COMPONENT_CREATES_NEW_BYTE_AND_SEMANTIC_IDENTITY",
            fixture.request,
        )
    if probe == "META_NONE_TO_ZERO":
        incomplete_v1 = build_openrouter_max_price_policy_v1(
            OPENROUTER_MAX_PRICE_SCHEMA_PATH_V1,
            prompt_usd_per_million_tokens="1",
            completion_usd_per_million_tokens="2",
            request_usd=None,
        )
        zero = _fixture_v1(repository_root, request_usd="0")
        return _accepted_v1(
            incomplete_v1.request_picodollars is None
            and zero.policy.request_picodollars == 0
            and zero.policy.has_complete_text_request_coverage
            and incomplete_v1.policy_id != zero.policy.price_policy_id,
            "ABSENT_AND_EXPLICIT_ZERO_REMAIN_DISTINCT",
            incomplete_v1,
            zero.policy,
        )
    if probe == "META_MODEL_INVALIDATES_P17":
        refusal = _must_refuse_v1(
            lambda: _revalidate_mutation_v1(
                fixture.request,
                OpenRouterRenderedLiveRequestV2,
                changes={"exact_model": "openai/gpt-4.1"},
            ),
            "MODEL_CHANGE_INVALIDATES_P17",
        )
        return _accepted_v1(
            refusal.outcome is OpenRouterLiveSafetyActualOutcomeV1.REJECTED,
            "EXACT_MODEL_LITERAL_AND_CONTENT_ID_GUARD",
            fixture.p17,
        )
    if probe == "META_CONSUMPTION_NOT_FRESH":
        with tempfile.TemporaryDirectory(prefix="s7a-meta-consumption-") as temp:
            claim_directory = Path(temp)
            preflight = _authorized_preflight_v1(fixture, claim_directory)
            _consume_authorized_preflight_v1(
                preflight,
                fixture=fixture,
                claim_directory=claim_directory,
                rendered_request=fixture.request,
                transport_policy=fixture.transport,
            )
            replayed = _preflight_v1(fixture, claim_directory)
        return _accepted_v1(
            replayed.verdict is OpenRouterOneLiveCallVerdictV1.REFUSED
            and replayed.first_failure_code
            is OpenRouterOneLiveCallFailureCodeV1.AUTHORIZATION_ALREADY_CONSUMED,
            "CONSUMPTION_PREVENTS_FRESH_SEMANTIC_REPLAY",
            replayed,
        )
    raise ContractValidationError(f"unknown metamorphic probe {probe}")


_PROBE_FAMILY_DISPATCH_V1: Dict[
    OpenRouterLiveSafetyCaseFamilyV1,
    Callable[[str, Path], _ProbeObservationV1],
] = {
    OpenRouterLiveSafetyCaseFamilyV1.P17: _evaluate_p17_probe_v1,
    OpenRouterLiveSafetyCaseFamilyV1.P19: _evaluate_p19_probe_v1,
    OpenRouterLiveSafetyCaseFamilyV1.AUTHORIZATION: (
        _evaluate_authorization_probe_v1
    ),
    OpenRouterLiveSafetyCaseFamilyV1.METAMORPHIC: (
        _evaluate_metamorphic_probe_v1
    ),
}


def _evaluate_case_v1(
    case: OpenRouterLiveSafetyCaseV1,
    repository_root: Path,
) -> OpenRouterLiveSafetyCaseResultV1:
    try:
        observation = _PROBE_FAMILY_DISPATCH_V1[case.family](
            case.probe, repository_root
        )
    except Exception as exc:  # noqa: BLE001 - aggregate must record evaluator bugs
        observation = _ProbeObservationV1(
            OpenRouterLiveSafetyActualOutcomeV1.INVALID_FIXTURE_CONSTRUCTION,
            f"EVALUATOR_FIXTURE_ERROR_{type(exc).__name__}",
            "UNHANDLED_EVALUATOR_FIXTURE_ERROR",
        )
    matches = (
        observation.outcome.value == case.expected_outcome.value
        and observation.failure_code == case.expected_failure_code
    )
    return OpenRouterLiveSafetyCaseResultV1(
        case_id=case.case_id,
        family=case.family,
        kind=case.kind,
        case_fingerprint=case.case_fingerprint or "",
        probe=case.probe,
        expected_outcome=case.expected_outcome,
        actual_outcome=observation.outcome,
        expected_failure_code=case.expected_failure_code,
        actual_failure_code=observation.failure_code,
        core_signal=observation.core_signal,
        evidence_ids=observation.evidence_ids,
        result_matches_expectation=matches,
    )


def evaluate_openrouter_live_safety_case_v1(
    case: OpenRouterLiveSafetyCaseV1,
    *,
    repository_root: Optional[Path] = None,
) -> OpenRouterLiveSafetyCaseResultV1:
    if type(case) is not OpenRouterLiveSafetyCaseV1:
        raise ContractValidationError(
            "live-safety evaluator requires the exact frozen case type"
        )
    validated = OpenRouterLiveSafetyCaseV1.model_validate(
        case.model_dump(mode="python")
    )
    return _evaluate_case_v1(
        validated,
        Path(repository_root or _repository_root_v1()).resolve(),
    )


def evaluate_openrouter_live_safety_v1(
    *, repository_root: Optional[Path] = None
) -> Tuple[OpenRouterLiveSafetyCaseResultV1, ...]:
    root = Path(repository_root or _repository_root_v1()).resolve()
    results = tuple(
        _evaluate_case_v1(case, root)
        for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
    )
    if tuple(result.case_id for result in results) != tuple(
        case.case_id for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
    ):
        raise ContractValidationError("live-safety result order changed")
    return results


def _git_blob_sha1_v1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324 - Git identity


def evaluate_openrouter_live_safety_predecessor_integrity_v1(
    repository_root: Path,
) -> OpenRouterLiveSafetyPredecessorIntegrityV1:
    root = Path(repository_root).resolve()
    surfaces = []
    for relative_path, expected in _S6_SEMANTIC_PREDECESSORS_V1:
        try:
            payload = (root / relative_path).read_bytes()
            actual: Optional[str] = _git_blob_sha1_v1(payload)
        except OSError:
            actual = None
        surfaces.append(
            OpenRouterLiveSafetyPredecessorSurfaceV1(
                relative_path=relative_path,
                digest_algorithm="GIT_BLOB_SHA1",
                expected_digest=expected,
                actual_digest=actual,
                unchanged=actual == expected,
            )
        )
    for relative_path, expected in _S6_ARTIFACT_PREDECESSORS_V1:
        try:
            payload = (root / relative_path).read_bytes()
            actual = hashlib.sha256(payload).hexdigest()
        except OSError:
            actual = None
        surfaces.append(
            OpenRouterLiveSafetyPredecessorSurfaceV1(
                relative_path=relative_path,
                digest_algorithm="SHA256",
                expected_digest=expected,
                actual_digest=actual,
                unchanged=actual == expected,
            )
        )
    ordered = tuple(sorted(surfaces, key=lambda surface: surface.relative_path))
    unchanged = sum(surface.unchanged for surface in ordered)
    return OpenRouterLiveSafetyPredecessorIntegrityV1(
        surfaces=ordered,
        unchanged_surfaces=unchanged,
        all_unchanged=unchanged == len(ordered),
    )


def _known_prompt_fragments_v1() -> Tuple[str, ...]:
    try:
        body = json.loads(FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    messages = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(messages, list):
        return ()
    fragments = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and len(content) >= 24:
            fragments.append(content)
    return tuple(fragments)


def scan_openrouter_live_safety_artifact_privacy_v1(
    payload: str | bytes,
) -> int:
    """Count forbidden secret/raw-content markers in a compact aggregate."""

    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return 1
    elif isinstance(payload, str):
        text = payload
    else:
        raise ContractValidationError("privacy scan requires text or exact bytes")

    findings = sum(marker in text for marker in _FORBIDDEN_ARTIFACT_MARKERS_V1)
    for forbidden_key in (
        '"credential_hash":',
        '"credential_value":',
        '"raw_response_bytes":',
        '"canonical_body_json":',
        '"response_mutation_payload":',
        '"secret_environment_contents":',
    ):
        findings += forbidden_key in text
    raw_limit = _model_detail_response_bytes_v1().decode("utf-8")
    findings += raw_limit in text
    findings += FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1 in text
    for fragment in _known_prompt_fragments_v1():
        findings += fragment in text
    return findings


def _privacy_projection_v1(
    results: Tuple[OpenRouterLiveSafetyCaseResultV1, ...],
    predecessor: OpenRouterLiveSafetyPredecessorIntegrityV1,
) -> str:
    return canonical_json(
        {
            "results": [result.model_dump(mode="json") for result in results],
            "predecessor_integrity": predecessor.model_dump(mode="json"),
        }
    )


def _hazard_acceptance_counts_v1(
    results: Tuple[OpenRouterLiveSafetyCaseResultV1, ...],
) -> Dict[OpenRouterLiveSafetyHazardV1, int]:
    by_case = {case.case_id: case for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1}
    counts = {hazard: 0 for hazard in OpenRouterLiveSafetyHazardV1}
    for result in results:
        case = by_case.get(result.case_id)
        if (
            case is None
            or result.actual_outcome
            is not OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
        ):
            continue
        for hazard in case.hazards:
            counts[hazard] += 1
    return counts


def _derive_metrics_v1(
    results: Tuple[OpenRouterLiveSafetyCaseResultV1, ...],
    predecessor: OpenRouterLiveSafetyPredecessorIntegrityV1,
    boundary: OpenRouterLiveSafetyBoundaryCountersV1,
    privacy_findings: int,
) -> OpenRouterLiveSafetyMetricsV1:
    thresholds = FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1
    cases_by_id = {
        case.case_id: case for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
    }
    hazards = _hazard_acceptance_counts_v1(results)

    def family_results(
        family: OpenRouterLiveSafetyCaseFamilyV1,
    ) -> Tuple[OpenRouterLiveSafetyCaseResultV1, ...]:
        return tuple(result for result in results if result.family is family)

    p17 = family_results(OpenRouterLiveSafetyCaseFamilyV1.P17)
    p19 = family_results(OpenRouterLiveSafetyCaseFamilyV1.P19)
    authorization = family_results(OpenRouterLiveSafetyCaseFamilyV1.AUTHORIZATION)
    metamorphic = family_results(OpenRouterLiveSafetyCaseFamilyV1.METAMORPHIC)
    positive_accepted = sum(
        result.kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE
        and result.actual_outcome is OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
        for result in results
    )
    adversarial_rejected = sum(
        result.kind is OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL
        and result.actual_outcome is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
        for result in results
    )
    requirement_tags = {
        tag
        for result in results
        if result.case_id in cases_by_id
        for tag in cases_by_id[result.case_id].requirement_tags
    }
    guard_mismatches = sum(
        result.kind is OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL
        and result.actual_outcome is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
        and result.actual_failure_code != result.expected_failure_code
        for result in results
    )
    values = {
        "total_cases": len(results),
        "positive_accepted": positive_accepted,
        "adversarial_rejected": adversarial_rejected,
        "p17_cases": len(p17),
        "p17_positive_accepted": sum(
            result.kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE
            and result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
            for result in p17
        ),
        "p17_adversarial_rejected": sum(
            result.kind is OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL
            and result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
            for result in p17
        ),
        "p19_cases": len(p19),
        "p19_positive_accepted": sum(
            result.kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE
            and result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
            for result in p19
        ),
        "p19_adversarial_rejected": sum(
            result.kind is OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL
            and result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
            for result in p19
        ),
        "authorization_cases": len(authorization),
        "authorization_positive_accepted": sum(
            result.kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE
            and result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
            for result in authorization
        ),
        "authorization_adversarial_rejected": sum(
            result.kind is OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL
            and result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.REJECTED
            for result in authorization
        ),
        "metamorphic_cases": len(metamorphic),
        "metamorphic_holding": sum(
            result.actual_outcome is OpenRouterLiveSafetyActualOutcomeV1.ACCEPTED
            for result in metamorphic
        ),
        "requirement_tags_covered": len(requirement_tags),
        "unexpected_results": sum(
            not result.result_matches_expectation for result in results
        ),
        "invalid_fixture_constructions": sum(
            result.actual_outcome
            is OpenRouterLiveSafetyActualOutcomeV1.INVALID_FIXTURE_CONSTRUCTION
            for result in results
        ),
        "guard_code_mismatches": guard_mismatches,
        "heuristic_p17_authority_accepted": hazards[
            OpenRouterLiveSafetyHazardV1.HEURISTIC_P17_AUTHORITY
        ],
        "byte_to_token_substitutions_accepted": hazards[
            OpenRouterLiveSafetyHazardV1.BYTE_TO_TOKEN_SUBSTITUTION
        ],
        "incomplete_charge_coverage_accepted": hazards[
            OpenRouterLiveSafetyHazardV1.INCOMPLETE_CHARGE_COVERAGE
        ],
        "request_fee_omission_to_zero": hazards[
            OpenRouterLiveSafetyHazardV1.REQUEST_FEE_OMISSION_TO_ZERO
        ],
        "hidden_monetary_terms": hazards[
            OpenRouterLiveSafetyHazardV1.HIDDEN_MONETARY_TERM
        ],
        "cross_request_substitutions_accepted": hazards[
            OpenRouterLiveSafetyHazardV1.CROSS_REQUEST_SUBSTITUTION
        ],
        "authorization_reuse_accepted": hazards[
            OpenRouterLiveSafetyHazardV1.AUTHORIZATION_REUSE
        ],
        "consumption_rollback_accepted": hazards[
            OpenRouterLiveSafetyHazardV1.CONSUMPTION_ROLLBACK
        ],
        "credential_leakage_findings": privacy_findings
        + hazards[OpenRouterLiveSafetyHazardV1.CREDENTIAL_LEAKAGE],
        "test_fixture_promotions": hazards[
            OpenRouterLiveSafetyHazardV1.TEST_FIXTURE_PROMOTION
        ],
        "external_activity": boundary.total_external_activity,
        "s6_predecessor_surfaces_unchanged": predecessor.unchanged_surfaces,
    }
    passes = (
        values["total_cases"] == thresholds.required_total_cases
        and values["positive_accepted"]
        == thresholds.required_positive_accepted
        and values["adversarial_rejected"]
        == thresholds.required_adversarial_rejected
        and values["p17_cases"] == thresholds.required_p17_cases
        and values["p17_positive_accepted"]
        == thresholds.required_p17_positive_accepted
        and values["p17_adversarial_rejected"]
        == thresholds.required_p17_adversarial_rejected
        and values["p19_cases"] == thresholds.required_p19_cases
        and values["p19_positive_accepted"]
        == thresholds.required_p19_positive_accepted
        and values["p19_adversarial_rejected"]
        == thresholds.required_p19_adversarial_rejected
        and values["authorization_cases"]
        == thresholds.required_authorization_cases
        and values["authorization_positive_accepted"]
        == thresholds.required_authorization_positive_accepted
        and values["authorization_adversarial_rejected"]
        == thresholds.required_authorization_adversarial_rejected
        and values["metamorphic_cases"]
        == thresholds.required_metamorphic_cases
        and values["metamorphic_holding"]
        == thresholds.required_metamorphic_holding
        and values["requirement_tags_covered"]
        == thresholds.required_requirement_tags_covered
        and values["unexpected_results"]
        == thresholds.required_unexpected_results
        and values["invalid_fixture_constructions"]
        == thresholds.required_invalid_fixture_constructions
        and values["guard_code_mismatches"]
        == thresholds.required_guard_code_mismatches
        and values["heuristic_p17_authority_accepted"]
        <= thresholds.maximum_heuristic_p17_authority_accepted
        and values["byte_to_token_substitutions_accepted"]
        <= thresholds.maximum_byte_to_token_substitutions_accepted
        and values["incomplete_charge_coverage_accepted"]
        <= thresholds.maximum_incomplete_charge_coverage_accepted
        and values["request_fee_omission_to_zero"]
        <= thresholds.maximum_request_fee_omission_to_zero
        and values["hidden_monetary_terms"]
        <= thresholds.maximum_hidden_monetary_terms
        and values["cross_request_substitutions_accepted"]
        <= thresholds.maximum_cross_request_substitutions_accepted
        and values["authorization_reuse_accepted"]
        <= thresholds.maximum_authorization_reuse_accepted
        and values["consumption_rollback_accepted"]
        <= thresholds.maximum_consumption_rollback_accepted
        and values["credential_leakage_findings"]
        <= thresholds.maximum_credential_leakage_findings
        and values["test_fixture_promotions"]
        <= thresholds.maximum_test_fixture_promotions
        and values["external_activity"]
        <= thresholds.maximum_external_activity
        and values["s6_predecessor_surfaces_unchanged"]
        == thresholds.required_s6_predecessor_surfaces_unchanged
    )
    return OpenRouterLiveSafetyMetricsV1(
        **values,
        all_thresholds_pass=passes,
    )


class OpenRouterLiveSafetyArtifactV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_EVALUATION_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_EVALUATION_SCHEMA_V1
    evaluation_id: Literal[
        OPENROUTER_LIVE_SAFETY_EVALUATION_ID_V1
    ] = OPENROUTER_LIVE_SAFETY_EVALUATION_ID_V1
    case_set_id: Literal[
        OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1
    ] = OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1
    thresholds: OpenRouterLiveSafetyThresholdsV1
    thresholds_id: Literal[
        OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1
    ] = OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1
    preflight_guard_order_id: Literal[
        OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1
    ] = OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1
    preflight_guard_order: Tuple[OpenRouterOneLiveCallFailureCodeV1, ...]
    boundary_counters: OpenRouterLiveSafetyBoundaryCountersV1
    predecessor_integrity: OpenRouterLiveSafetyPredecessorIntegrityV1
    results: Tuple[OpenRouterLiveSafetyCaseResultV1, ...]
    metrics: OpenRouterLiveSafetyMetricsV1

    p17_proof_architecture: Literal["READY"] = "READY"
    p17_current_authority: Literal["JIT_PENDING"] = "JIT_PENDING"
    p19_formula_structure: Literal["READY"] = "READY"
    p19_applicable_charge_coverage: Literal["COMPLETE"] = "COMPLETE"
    p19_current_authority: Literal["JIT_PENDING"] = "JIT_PENDING"
    production_price_policy: Literal["JIT_PENDING"] = "JIT_PENDING"
    production_total_spend_ceiling: Literal["JIT_PENDING"] = "JIT_PENDING"
    claim_store_readiness_contract: Literal["READY"] = "READY"
    physical_claim_store_realization: Literal[
        "S7B_JIT_PENDING"
    ] = "S7B_JIT_PENDING"
    one_call_authorization: Literal["READY"] = "READY"
    jit_preflight: Literal["READY"] = "READY"
    runtime_authority: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    live_openrouter_execution: Literal["NOT_EXECUTED"] = "NOT_EXECUTED"
    one_live_shadow_call: OpenRouterLiveSafetyReadinessV1
    hypothesis_status: OpenRouterLiveSafetyHypothesisStatusV1
    artifact_id: Optional[str] = Field(
        default=None, pattern=r"^szorlivesafetyartifactv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterLiveSafetyArtifactV1":
        if self.thresholds != FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1:
            raise ContractValidationError("live-safety thresholds changed")
        if self.preflight_guard_order != (
            FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1
        ):
            raise ContractValidationError("live-safety preflight guard order changed")
        expected_cases = {
            case.case_id: case for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
        }
        result_ids = tuple(result.case_id for result in self.results)
        if result_ids != tuple(sorted(expected_cases)):
            raise ContractValidationError(
                "artifact does not contain the exact frozen result inventory"
            )
        for result in self.results:
            case = expected_cases[result.case_id]
            if (
                result.case_fingerprint != case.case_fingerprint
                or result.family is not case.family
                or result.kind is not case.kind
                or result.probe != case.probe
                or result.expected_outcome is not case.expected_outcome
                or result.expected_failure_code != case.expected_failure_code
            ):
                raise ContractValidationError(
                    "artifact result disagrees with its frozen case"
                )
        privacy = scan_openrouter_live_safety_artifact_privacy_v1(
            _privacy_projection_v1(self.results, self.predecessor_integrity)
        )
        expected_metrics = _derive_metrics_v1(
            self.results,
            self.predecessor_integrity,
            self.boundary_counters,
            privacy,
        )
        if self.metrics != expected_metrics:
            raise ContractValidationError("live-safety metrics are not fully derived")
        supported = self.metrics.all_thresholds_pass
        expected_status = (
            OpenRouterLiveSafetyHypothesisStatusV1.SUPPORTED
            if supported
            else OpenRouterLiveSafetyHypothesisStatusV1.FALSIFIED
        )
        if self.hypothesis_status is not expected_status:
            raise ContractValidationError(
                "live-safety hypothesis status is not threshold-derived"
            )
        expected_readiness = (
            OpenRouterLiveSafetyReadinessV1.AUTHORIZED_PENDING_JIT_PREFLIGHT
            if supported
            else OpenRouterLiveSafetyReadinessV1.NOT_AUTHORIZED
        )
        if self.one_live_shadow_call is not expected_readiness:
            raise ContractValidationError(
                "one-live-call readiness is not threshold-derived"
            )
        assert_acquisition_artifact_tripwires_v0(self.boundary_counters)
        expected_id = stable_contract_id(
            "szorlivesafetyartifactv1",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id not in (None, expected_id):
            raise ContractValidationError("live-safety artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected_id)
        return self


def build_openrouter_live_safety_artifact_v1(
    *, repository_root: Optional[Path] = None
) -> OpenRouterLiveSafetyArtifactV1:
    """Build one in-memory aggregate under the active canonical tripwire."""

    require_clean_acquisition_boundary_tripwire_v0()
    root = Path(repository_root or _repository_root_v1()).resolve()
    with _BackgroundStartTripwireV1() as background:
        results = evaluate_openrouter_live_safety_v1(repository_root=root)
        predecessor = (
            evaluate_openrouter_live_safety_predecessor_integrity_v1(root)
        )
        snapshot = require_clean_acquisition_boundary_tripwire_v0()
    boundary = OpenRouterLiveSafetyBoundaryCountersV1(
        external_network_attempts=snapshot.external_network_attempts,
        credential_access_attempts=snapshot.credential_access_attempts,
        live_provider_calls=snapshot.live_provider_calls,
        provider_sdk_calls=snapshot.provider_sdk_calls,
        model_executions=snapshot.model_executions,
        tool_calls=snapshot.tool_calls,
        canonical_application_calls=snapshot.canonical_application_calls,
        official_source_retrievals=0,
        live_dispatches=0,
        background_thread_starts=background.thread_starts,
        background_process_starts=background.process_starts,
    )
    privacy = scan_openrouter_live_safety_artifact_privacy_v1(
        _privacy_projection_v1(results, predecessor)
    )
    metrics = _derive_metrics_v1(results, predecessor, boundary, privacy)
    supported = metrics.all_thresholds_pass
    return OpenRouterLiveSafetyArtifactV1(
        thresholds=FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1,
        preflight_guard_order=FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1,
        boundary_counters=boundary,
        predecessor_integrity=predecessor,
        results=results,
        metrics=metrics,
        one_live_shadow_call=(
            OpenRouterLiveSafetyReadinessV1.AUTHORIZED_PENDING_JIT_PREFLIGHT
            if supported
            else OpenRouterLiveSafetyReadinessV1.NOT_AUTHORIZED
        ),
        hypothesis_status=(
            OpenRouterLiveSafetyHypothesisStatusV1.SUPPORTED
            if supported
            else OpenRouterLiveSafetyHypothesisStatusV1.FALSIFIED
        ),
    )


def render_openrouter_live_safety_artifact_v1(
    artifact: OpenRouterLiveSafetyArtifactV1,
) -> bytes:
    if type(artifact) is not OpenRouterLiveSafetyArtifactV1:
        raise ContractValidationError(
            "artifact must use the exact OpenRouterLiveSafetyArtifactV1 type"
        )
    validated = OpenRouterLiveSafetyArtifactV1.model_validate(
        artifact.model_dump(mode="python")
    )
    return canonical_json(validated.model_dump(mode="json")).encode("utf-8") + b"\n"


def load_openrouter_live_safety_artifact_v1(
    path: Path,
) -> OpenRouterLiveSafetyArtifactV1:
    try:
        payload = Path(path).read_bytes()
        decoded = json.loads(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ContractValidationError(
            "live-safety artifact is unavailable"
        ) from exc
    artifact = OpenRouterLiveSafetyArtifactV1.model_validate(decoded)
    if payload != render_openrouter_live_safety_artifact_v1(artifact):
        raise ContractValidationError(
            "live-safety artifact bytes are not canonical"
        )
    return artifact


class OpenRouterLiveSafetyReplayExecutionV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_SCHEMA_V1
    source_artifact_id: str = Field(min_length=1)
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recomputed_artifact_id: str = Field(min_length=1)
    recomputed_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: bool
    artifact_id_equality: bool
    byte_identity: bool
    official_source_retrievals: Literal[0] = 0
    live_openrouter_calls: Literal[0] = 0
    execution_id: Optional[str] = Field(
        default=None, pattern=r"^szorlivesafetyreplayexecutionv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveSafetyReplayExecutionV1":
        expected = stable_contract_id(
            "szorlivesafetyreplayexecutionv1",
            self.model_dump(mode="json", exclude={"execution_id"}),
        )
        if self.execution_id not in (None, expected):
            raise ContractValidationError("live-safety replay execution ID mismatch")
        object.__setattr__(self, "execution_id", expected)
        return self


class OpenRouterLiveSafetyReplayLockV1(
    _FrozenLiveSafetyEvaluationContractV1
):
    schema_version: Literal[
        OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_SCHEMA_V1
    ] = OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_SCHEMA_V1
    artifact_id: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_execution_id: str = Field(min_length=1)
    replay_execution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: bool
    artifact_id_equality: bool
    byte_identity: bool
    lock_id: Optional[str] = Field(
        default=None, pattern=r"^szorlivesafetyreplaylockv1_[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterLiveSafetyReplayLockV1":
        if not (
            self.semantic_equality
            and self.artifact_id_equality
            and self.byte_identity
        ):
            raise ContractValidationError(
                "live-safety replay lock requires semantic, ID and byte equality"
            )
        expected = stable_contract_id(
            "szorlivesafetyreplaylockv1",
            self.model_dump(mode="json", exclude={"lock_id"}),
        )
        if self.lock_id not in (None, expected):
            raise ContractValidationError("live-safety replay lock ID mismatch")
        object.__setattr__(self, "lock_id", expected)
        return self


def render_openrouter_live_safety_replay_execution_v1(
    execution: OpenRouterLiveSafetyReplayExecutionV1,
) -> bytes:
    validated = OpenRouterLiveSafetyReplayExecutionV1.model_validate(
        execution.model_dump(mode="python")
    )
    return canonical_json(validated.model_dump(mode="json")).encode("utf-8") + b"\n"


def render_openrouter_live_safety_replay_lock_v1(
    lock: OpenRouterLiveSafetyReplayLockV1,
) -> bytes:
    validated = OpenRouterLiveSafetyReplayLockV1.model_validate(
        lock.model_dump(mode="python")
    )
    return canonical_json(validated.model_dump(mode="json")).encode("utf-8") + b"\n"


def replay_openrouter_live_safety_v1(
    artifact_path: Path,
    *,
    repository_root: Optional[Path] = None,
) -> Tuple[
    OpenRouterLiveSafetyReplayExecutionV1,
    OpenRouterLiveSafetyReplayLockV1,
]:
    require_clean_acquisition_boundary_tripwire_v0()
    source_bytes = Path(artifact_path).read_bytes()
    source = load_openrouter_live_safety_artifact_v1(Path(artifact_path))
    recomputed = build_openrouter_live_safety_artifact_v1(
        repository_root=repository_root
    )
    recomputed_bytes = render_openrouter_live_safety_artifact_v1(recomputed)
    execution = OpenRouterLiveSafetyReplayExecutionV1(
        source_artifact_id=source.artifact_id or "",
        source_artifact_sha256=hashlib.sha256(source_bytes).hexdigest(),
        recomputed_artifact_id=recomputed.artifact_id or "",
        recomputed_artifact_sha256=hashlib.sha256(recomputed_bytes).hexdigest(),
        semantic_equality=source == recomputed,
        artifact_id_equality=source.artifact_id == recomputed.artifact_id,
        byte_identity=source_bytes == recomputed_bytes,
    )
    lock = OpenRouterLiveSafetyReplayLockV1(
        artifact_id=source.artifact_id or "",
        artifact_sha256=hashlib.sha256(source_bytes).hexdigest(),
        replay_execution_id=execution.execution_id or "",
        replay_execution_sha256=hashlib.sha256(
            render_openrouter_live_safety_replay_execution_v1(execution)
        ).hexdigest(),
        semantic_equality=execution.semantic_equality,
        artifact_id_equality=execution.artifact_id_equality,
        byte_identity=execution.byte_identity,
    )
    return execution, lock


def write_once_v1(path: Path, payload: bytes) -> str:
    if type(payload) is not bytes:
        raise ContractValidationError("write-once payload must use exact bytes")
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
    "FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1",
    "OPENROUTER_LIVE_SAFETY_ARTIFACT_RELATIVE_PATH_V1",
    "OPENROUTER_LIVE_SAFETY_EVALUATION_SCHEMA_V1",
    "OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_RELATIVE_PATH_V1",
    "OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_RELATIVE_PATH_V1",
    "OpenRouterLiveSafetyActualOutcomeV1",
    "OpenRouterLiveSafetyArtifactV1",
    "OpenRouterLiveSafetyBoundaryCountersV1",
    "OpenRouterLiveSafetyCaseResultV1",
    "OpenRouterLiveSafetyHypothesisStatusV1",
    "OpenRouterLiveSafetyMetricsV1",
    "OpenRouterLiveSafetyPredecessorIntegrityV1",
    "OpenRouterLiveSafetyPredecessorSurfaceV1",
    "OpenRouterLiveSafetyReadinessV1",
    "OpenRouterLiveSafetyReplayExecutionV1",
    "OpenRouterLiveSafetyReplayLockV1",
    "build_openrouter_live_safety_artifact_v1",
    "evaluate_openrouter_live_safety_case_v1",
    "evaluate_openrouter_live_safety_predecessor_integrity_v1",
    "evaluate_openrouter_live_safety_v1",
    "load_openrouter_live_safety_artifact_v1",
    "render_openrouter_live_safety_artifact_v1",
    "render_openrouter_live_safety_replay_execution_v1",
    "render_openrouter_live_safety_replay_lock_v1",
    "replay_openrouter_live_safety_v1",
    "scan_openrouter_live_safety_artifact_privacy_v1",
    "write_once_v1",
]

"""Focused execution tests for the hermetic canned acquisition boundary."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import pytest

from backend.dialogues.socrates_zero.acquisition import (
    AcquisitionIsolationSnapshot,
    CannedAcquisitionTransport,
    CannedImplementationProfile,
    CannedTransportDirective,
    IsolationSubjectSnapshot,
    acquire_canned_observation,
    build_canned_capability_snapshot,
    render_provider_visible_request,
)
from backend.dialogues.socrates_zero.acquisition_contracts import (
    ACQUISITION_GUARD_ORDER,
    CANNED_TRANSPORT_ID,
    AcquisitionAttemptOutcome,
    AcquisitionControlPolicy,
    AcquisitionControlName,
    AcquisitionControlState,
    AcquisitionExecutionUsage,
    AcquisitionFailureCode,
    AcquisitionGuardId,
    AcquisitionGuardState,
    AcquisitionProviderModelBinding,
    AcquisitionRequestConfiguration,
    AcquisitionResourceQuantity,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    AcquisitionTransportAttempt,
    AcquisitionTransportStatus,
    AcquisitionTransportMode,
    CannedTransportEnvelope,
)
from backend.dialogues.socrates_zero.acquisition_evaluation import (
    build_frozen_acquisition_fixtures_v0,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _known(value: int) -> AcquisitionResourceQuantity:
    return AcquisitionResourceQuantity.known(value)


def _new_execution_usage(invocations: int = 1) -> AcquisitionExecutionUsage:
    return AcquisitionExecutionUsage(
        canned_transport_invocations=_known(invocations),
        external_network_attempts=_known(0),
        credential_access_attempts=_known(0),
        live_provider_calls=_known(0),
        provider_sdk_calls=_known(0),
        model_executions=_known(0),
        tool_calls=_known(0),
        new_tokens=_known(0),
        new_cost_microusd=_known(0),
        external_provider_wall_time_ms=_known(0),
    )


def _isolation_probe(*, mutate_scope: str | None = None):
    calls = 0

    def probe() -> AcquisitionIsolationSnapshot:
        nonlocal calls
        calls += 1

        def subject(scope: str) -> IsolationSubjectSnapshot:
            suffix = ":mutated" if calls == 2 and scope == mutate_scope else ""
            return IsolationSubjectSnapshot(
                subject_id=f"acquisition-{scope}-subject",
                runtime_digest=_digest(f"acquisition-{scope}-state{suffix}"),
            )

        return AcquisitionIsolationSnapshot(
            source=subject("source"),
            sibling=subject("sibling"),
            production=subject("production"),
        )

    return probe


def _request_for_capability(
    request: AcquisitionSemanticRequest,
    capability_id: str,
) -> AcquisitionSemanticRequest:
    payload = request.model_dump(mode="json")
    payload["semantic_request_id"] = None
    payload["capability_snapshot_id"] = capability_id
    return AcquisitionSemanticRequest.model_validate(payload)


def _attempt(request: AcquisitionSemanticRequest, branch_id: str = "branch-a"):
    return AcquisitionTransportAttempt(
        semantic_request_id=request.semantic_request_id or "",
        experiment_id="socrateszero-acquisition-runtime-test/v0",
        branch_id=branch_id,
        attempt_ordinal=0,
    )


def _envelope(
    request: AcquisitionSemanticRequest,
    attempt: AcquisitionTransportAttempt,
    historical_usage: Any,
    *,
    raw_response_text: str | None = '{"kind":"canned"}',
    reported_digest: str | None = None,
    actual_binding: AcquisitionProviderModelBinding | None = None,
    fallback_used: bool | None = False,
    explicit_retry_count: int | None = 0,
    adapter_retry_count: int | None = 0,
    sdk_internal_retry_count: int | None = 0,
    hidden_transport_retry_count: int | None = 0,
    tool_calls: int | None = 0,
    worker_terminated: bool | None = True,
    execution_usage: AcquisitionExecutionUsage | None = None,
    transport_status: AcquisitionTransportStatus = AcquisitionTransportStatus.DELIVERED,
) -> CannedTransportEnvelope:
    if reported_digest is None and raw_response_text is not None:
        reported_digest = _digest(raw_response_text)
    return CannedTransportEnvelope(
        transport_attempt_id=attempt.transport_attempt_id or "",
        transport_status=transport_status,
        canned_transport_invocations=1,
        actual_binding=actual_binding or request.requested_binding,
        raw_response_text=raw_response_text,
        reported_raw_response_digest=reported_digest,
        fallback_used=fallback_used,
        explicit_retry_count=explicit_retry_count,
        adapter_retry_count=adapter_retry_count,
        sdk_internal_retry_count=sdk_internal_retry_count,
        hidden_transport_retry_count=hidden_transport_retry_count,
        tool_calls=tool_calls,
        timeout_fired=False,
        cancellation_requested=False,
        worker_terminated=worker_terminated,
        execution_usage=execution_usage or _new_execution_usage(),
        historical_usage=historical_usage,
        source_provenance_id=historical_usage.provenance_id,
    )


def _transport(script, request, *, profile=CannedImplementationProfile.SAFE):
    fixture = build_frozen_acquisition_fixtures_v0()
    capability = fixture.capability_snapshot
    return CannedAcquisitionTransport(
        script,
        provider_id=request.requested_binding.provider_id,
        adapter_id=capability.adapter_id,
        adapter_version=capability.adapter_version,
        adapter_revision_digest=capability.adapter_revision_digest,
        requested_model_id=request.requested_binding.model_id,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
        implementation_profile=profile,
    )


def _run(
    *,
    raw_response_text: str | None = '{"kind":"canned"}',
    profile=CannedImplementationProfile.SAFE,
    directive_kwargs: dict[str, Any] | None = None,
    envelope_kwargs: dict[str, Any] | None = None,
    mutate_scope: str | None = None,
):
    fixture = build_frozen_acquisition_fixtures_v0()
    base_request = fixture.semantic_request
    provisional_attempt = _attempt(base_request)
    provisional = _transport(
        [
            _envelope(
                base_request,
                provisional_attempt,
                fixture.known_historical_usage,
                raw_response_text=raw_response_text,
            )
        ],
        base_request,
        profile=profile,
    )
    request = _request_for_capability(
        base_request,
        provisional.capabilities.capability_snapshot_id or "",
    )
    attempt = _attempt(request)
    envelope_options = {"raw_response_text": raw_response_text}
    envelope_options.update(envelope_kwargs or {})
    envelope = _envelope(
        request,
        attempt,
        fixture.known_historical_usage,
        **envelope_options,
    )
    directive = CannedTransportDirective(
        envelope=envelope,
        **(directive_kwargs or {}),
    )
    transport = _transport([directive], request, profile=profile)
    return asyncio.run(
        acquire_canned_observation(
            request,
            attempt,
            fixture.control_policy,
            fixture.retention_policy,
            transport,
            historical_usage=fixture.known_historical_usage,
            isolation_probe=_isolation_probe(mutate_scope=mutate_scope),
            capability_snapshot=transport.capabilities,
        )
    )


def test_complete_canned_acquisition_is_opaque_unadmitted_and_hermetic() -> None:
    result = _run(raw_response_text="{not canonical Socratic JSON")
    assert result.outcome is AcquisitionAttemptOutcome.ACQUIRED
    assert result.failure_code is None
    assert result.observation is not None
    assert result.observation.admission_status == "UNADMITTED"
    assert result.observation.canonical_status == "NON_CANONICAL"
    assert result.observation.governing_status == "NON_GOVERNING"
    assert result.observation.application_status == "NOT_APPLIED"
    assert len(result.attempt_receipt.guard_evaluations) == 34
    assert all(
        row.state is AcquisitionGuardState.PASSED
        for row in result.attempt_receipt.guard_evaluations
    )
    counters = result.runtime_counters
    assert counters.canned_transport_invocations == 1
    assert (
        counters.external_network_attempts,
        counters.credential_reads,
        counters.provider_sdk_calls,
        counters.live_provider_calls,
        counters.model_calls,
        counters.tool_calls,
        counters.canonical_application_calls,
    ) == (0, 0, 0, 0, 0, 0, 0)


def test_provider_visible_bytes_are_exact_and_transport_identity_is_out_of_band() -> None:
    fixture = build_frozen_acquisition_fixtures_v0()
    request = fixture.semantic_request
    first = _attempt(request, "sibling-a")
    second = _attempt(request, "sibling-b")
    raw = render_provider_visible_request(request)
    assert first.transport_attempt_id != second.transport_attempt_id
    assert first.semantic_request_id == second.semantic_request_id
    assert raw == request.provider_visible_request.canonical_request_json.encode("utf-8")
    for canary in (
        first.branch_id,
        second.branch_id,
        first.transport_attempt_id or "",
        second.transport_attempt_id or "",
        first.experiment_id,
    ):
        assert canary.encode("utf-8") not in raw


@pytest.mark.parametrize(
    ("profile", "control", "state", "mode", "registered"),
    (
        (
            CannedImplementationProfile.REQUIRED_PROVIDER_IDENTITY_UNKNOWN,
            AcquisitionControlName.ACTUAL_PROVIDER_IDENTITY_VALIDATION,
            AcquisitionControlState.UNKNOWN,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
        ),
        (
            CannedImplementationProfile.NETWORK_PROHIBITION_UNPROVEN,
            AcquisitionControlName.EXTERNAL_NETWORK,
            AcquisitionControlState.PROVEN_SUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
        ),
        (
            CannedImplementationProfile.IDENTITY_VERIFICATION_UNPROVEN,
            AcquisitionControlName.ACTUAL_MODEL_IDENTITY_VALIDATION,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
        ),
        (
            CannedImplementationProfile.CANNED_ONLY_UNPROVEN,
            AcquisitionControlName.CANNED_ONLY_TRANSPORT,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
            AcquisitionTransportMode.EXTERNAL,
            True,
        ),
        (
            CannedImplementationProfile.REGISTRATION_UNPROVEN,
            AcquisitionControlName.CANNED_ONLY_TRANSPORT,
            AcquisitionControlState.PROVEN_SUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            False,
        ),
    ),
)
def test_negative_profiles_are_visible_in_immutable_capability_evidence(
    profile: CannedImplementationProfile,
    control: AcquisitionControlName,
    state: AcquisitionControlState,
    mode: AcquisitionTransportMode,
    registered: bool,
) -> None:
    fixture = build_frozen_acquisition_fixtures_v0()
    baseline = fixture.capability_snapshot
    mutated = build_canned_capability_snapshot(
        baseline.provider_id,
        baseline.adapter_id,
        baseline.adapter_version,
        baseline.adapter_revision_digest,
        baseline.requested_model_id,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
        implementation_profile=profile,
    )
    controls = {item.name: item.state for item in mutated.controls}
    assert mutated.capability_snapshot_id != baseline.capability_snapshot_id
    assert controls[control] is state
    assert mutated.transport_mode is mode
    assert (CANNED_TRANSPORT_ID in mutated.registered_canned_transport_ids) is registered


@pytest.mark.parametrize(
    ("profile", "guard", "failure"),
    (
        (
            CannedImplementationProfile.REQUIRED_PROVIDER_IDENTITY_UNKNOWN,
            AcquisitionGuardId.P04_REQUIRED_CONTROL_COMPLETENESS,
            AcquisitionFailureCode.REQUIRED_CONTROL_UNKNOWN,
        ),
        (
            CannedImplementationProfile.NETWORK_PROHIBITION_UNPROVEN,
            AcquisitionGuardId.P06_EXTERNAL_NETWORK_PROHIBITION,
            AcquisitionFailureCode.EXTERNAL_NETWORK_FORBIDDEN,
        ),
        (
            CannedImplementationProfile.CREDENTIAL_PROHIBITION_UNPROVEN,
            AcquisitionGuardId.P07_CREDENTIAL_ACCESS_PROHIBITION,
            AcquisitionFailureCode.CREDENTIAL_ACCESS_FORBIDDEN,
        ),
        (
            CannedImplementationProfile.IDENTITY_VERIFICATION_UNPROVEN,
            AcquisitionGuardId.P08_EXACT_IDENTITY_VERIFICATION,
            AcquisitionFailureCode.EXACT_IDENTITY_VERIFICATION_UNAVAILABLE,
        ),
        (
            CannedImplementationProfile.PROMPT_ENTROPY_INJECTION,
            AcquisitionGuardId.P16_PROMPT_BYTE_DETERMINISM,
            AcquisitionFailureCode.PROMPT_ENTROPY_DETECTED,
        ),
    ),
)
def test_predispatch_controls_fail_closed_without_canned_entry(
    profile: CannedImplementationProfile,
    guard: AcquisitionGuardId,
    failure: AcquisitionFailureCode,
) -> None:
    result = _run(profile=profile)
    assert result.outcome is AcquisitionAttemptOutcome.FAILED_CLOSED
    assert result.failure_code is failure
    assert result.attempt_receipt.primary_result.primary_guard_id is guard
    assert result.runtime_counters.canned_transport_invocations == 0
    position = ACQUISITION_GUARD_ORDER.index(guard)
    states = tuple(row.state for row in result.attempt_receipt.guard_evaluations)
    assert states == (
        (AcquisitionGuardState.PASSED,) * position
        + (AcquisitionGuardState.FAILED,)
        + (AcquisitionGuardState.NOT_REACHED,)
        * (len(ACQUISITION_GUARD_ORDER) - position - 1)
    )


@pytest.mark.parametrize(
    ("envelope_kwargs", "guard", "failure"),
    (
        (
            {"fallback_used": True},
            AcquisitionGuardId.A07_FALLBACK_ACTIVATION,
            AcquisitionFailureCode.FALLBACK_ACTIVATED,
        ),
        (
            {"explicit_retry_count": 1},
            AcquisitionGuardId.A08_RETRY_ACTIVATION,
            AcquisitionFailureCode.RETRY_ACTIVATED,
        ),
        (
            {"tool_calls": 1},
            AcquisitionGuardId.A09_TOOL_ACTIVATION,
            AcquisitionFailureCode.TOOL_ACTIVATED,
        ),
        (
            {"raw_response_text": None, "reported_digest": None},
            AcquisitionGuardId.A10_RAW_RESPONSE_PRESENCE,
            AcquisitionFailureCode.MISSING_RAW_OBSERVATION,
        ),
        (
            {"reported_digest": "f" * 64},
            AcquisitionGuardId.A11_RESPONSE_DIGEST_INTEGRITY,
            AcquisitionFailureCode.INVALID_RESPONSE_DIGEST,
        ),
        (
            {"worker_terminated": False},
            AcquisitionGuardId.A03_TIMEOUT_WORKER_TERMINATION,
            AcquisitionFailureCode.TRANSPORT_WORKER_NOT_TERMINATED,
        ),
    ),
)
def test_postdispatch_failures_are_counted_and_use_first_guard(
    envelope_kwargs: dict[str, Any],
    guard: AcquisitionGuardId,
    failure: AcquisitionFailureCode,
) -> None:
    result = _run(envelope_kwargs=envelope_kwargs)
    assert result.failure_code is failure
    assert result.attempt_receipt.primary_result.primary_guard_id is guard
    assert result.runtime_counters.canned_transport_invocations == 1
    assert result.observation is None


@pytest.mark.parametrize(
    ("directive_kwargs", "mutate_scope", "guard", "failure"),
    (
        (
            {"retention_integrity": False},
            None,
            AcquisitionGuardId.A15_RETENTION_PRIVACY_INTEGRITY,
            AcquisitionFailureCode.RETENTION_POLICY_VIOLATION,
        ),
        (
            {"final_receipt_integrity": False},
            None,
            AcquisitionGuardId.A16_FINAL_RECEIPT_INTEGRITY,
            AcquisitionFailureCode.RECEIPT_MISMATCH,
        ),
        (
            {},
            "source",
            AcquisitionGuardId.A14_ISOLATION_INTEGRITY,
            AcquisitionFailureCode.ISOLATION_FAILURE,
        ),
    ),
)
def test_retention_receipt_and_isolation_guards_fail_closed(
    directive_kwargs: dict[str, Any],
    mutate_scope: str | None,
    guard: AcquisitionGuardId,
    failure: AcquisitionFailureCode,
) -> None:
    result = _run(
        directive_kwargs=directive_kwargs,
        mutate_scope=mutate_scope,
    )
    assert result.failure_code is failure
    assert result.attempt_receipt.primary_result.primary_guard_id is guard
    assert result.observation is None


def test_real_canned_timeout_counts_entry_and_proves_cooperative_termination() -> None:
    fixture = build_frozen_acquisition_fixtures_v0()
    policy_payload = fixture.control_policy.model_dump(mode="json")
    policy_payload["control_policy_id"] = None
    policy_payload["timeout_ms"] = 5
    policy = AcquisitionControlPolicy.model_validate(policy_payload)

    configuration_payload = (
        fixture.semantic_request.request_configuration.model_dump(mode="json")
    )
    configuration_payload["configuration_id"] = None
    configuration_payload["configuration_digest"] = None
    configuration_payload["timeout_ms"] = 5
    configuration = AcquisitionRequestConfiguration.model_validate(
        configuration_payload
    )
    binding = AcquisitionProviderModelBinding(
        provider_id=fixture.semantic_request.requested_binding.provider_id,
        model_id=fixture.semantic_request.requested_binding.model_id,
        configuration_digest=configuration.configuration_digest or "",
    )
    request_payload = fixture.semantic_request.model_dump(mode="json")
    request_payload["semantic_request_id"] = None
    request_payload["control_policy_id"] = policy.control_policy_id
    request_payload["request_configuration"] = configuration.model_dump(mode="json")
    request_payload["requested_binding"] = binding.model_dump(mode="json")
    request = AcquisitionSemanticRequest.model_validate(request_payload)
    attempt = _attempt(request, "timeout-branch")
    transport = _transport(
        [CannedTransportDirective(wait_for_cancellation=True)],
        request,
    )
    result = asyncio.run(
        acquire_canned_observation(
            request,
            attempt,
            policy,
            fixture.retention_policy,
            transport,
            historical_usage=fixture.known_historical_usage,
            isolation_probe=_isolation_probe(),
            capability_snapshot=transport.capabilities,
        )
    )
    assert result.failure_code is AcquisitionFailureCode.TRANSPORT_TIMEOUT
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.A02_TRANSPORT_COMPLETION
    )
    assert result.runtime_counters.canned_transport_invocations == 1
    assert result.transport_record is not None
    assert result.transport_record.cancellation_acknowledged is True
    assert result.transport_record.worker_terminated is True
    assert transport.invocation_count == 1
    assert len(transport.invocation_records) == 1

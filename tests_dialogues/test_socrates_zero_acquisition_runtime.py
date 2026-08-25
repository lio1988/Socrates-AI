"""Focused execution tests for the hermetic canned acquisition boundary."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.acquisition import (
    _entropy_in_body,
    AcquisitionIsolationSnapshot,
    AcquisitionRuntimeError,
    CANNED_TIMEOUT_CLEANUP_GRACE_SECONDS,
    CANNED_TIMEOUT_CLEANUP_ROUNDS,
    CannedAcquisitionTransport,
    CannedImplementationProfile,
    CannedTransportDirective,
    IsolationSubjectSnapshot,
    acquire_canned_observation,
    build_canned_capability_snapshot,
    build_provider_visible_request,
    render_provider_visible_request,
)
from backend.dialogues.socrates_zero.acquisition_contracts import (
    ACQUISITION_GUARD_ORDER,
    CANNED_TRANSPORT_ID,
    AcquisitionAttemptOutcome,
    AcquisitionControlPolicy,
    AcquisitionControlName,
    AcquisitionControlState,
    AcquisitionDataClassification,
    AcquisitionExecutionUsage,
    AcquisitionFailureCode,
    AcquisitionGuardId,
    AcquisitionGuardState,
    AcquisitionProviderModelBinding,
    AcquisitionRequestConfiguration,
    AcquisitionResourceQuantity,
    AcquisitionRedactionStatus,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    AcquisitionTransportAttempt,
    AcquisitionTransportStatus,
    AcquisitionTransportMode,
    AcquisitionArtifactInclusionPolicy,
    CannedTransportEnvelope,
)
from backend.dialogues.socrates_zero.acquisition_evaluation import (
    build_frozen_acquisition_fixtures_v0,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_USE_REQUESTED_IDENTITY = object()


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
    raw_response_bytes: bytes | None = b'{"kind":"canned"}',
    reported_digest: str | None = None,
    reported_length: int | None = None,
    actual_binding: AcquisitionProviderModelBinding | None = None,
    actual_provider_id: str | None | object = _USE_REQUESTED_IDENTITY,
    actual_model_id: str | None | object = _USE_REQUESTED_IDENTITY,
    actual_configuration_digest: str | None | object = _USE_REQUESTED_IDENTITY,
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
    if reported_digest is None and raw_response_bytes is not None:
        reported_digest = hashlib.sha256(raw_response_bytes).hexdigest()
    if reported_length is None and raw_response_bytes is not None:
        reported_length = len(raw_response_bytes)
    binding = actual_binding or request.requested_binding
    provider_id = (
        binding.provider_id
        if actual_provider_id is _USE_REQUESTED_IDENTITY
        else actual_provider_id
    )
    model_id = (
        binding.model_id
        if actual_model_id is _USE_REQUESTED_IDENTITY
        else actual_model_id
    )
    configuration_digest = (
        binding.configuration_digest
        if actual_configuration_digest is _USE_REQUESTED_IDENTITY
        else actual_configuration_digest
    )
    return CannedTransportEnvelope(
        transport_attempt_id=attempt.transport_attempt_id or "",
        transport_status=transport_status,
        canned_transport_invocations=1,
        actual_provider_id=provider_id,
        actual_model_id=model_id,
        actual_configuration_digest=configuration_digest,
        raw_response_base64=(
            base64.b64encode(raw_response_bytes).decode("ascii")
            if raw_response_bytes is not None
            else None
        ),
        reported_raw_response_digest=reported_digest,
        reported_raw_response_length=reported_length,
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
    raw_response_bytes: bytes | None = b'{"kind":"canned"}',
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
                raw_response_bytes=raw_response_bytes,
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
    envelope_options = {"raw_response_bytes": raw_response_bytes}
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
    opaque = b"\x00\xff{not canonical Socratic JSON\x80"
    result = _run(raw_response_bytes=opaque)
    assert result.outcome is AcquisitionAttemptOutcome.ACQUIRED
    assert result.failure_code is None
    assert result.observation is not None
    assert result.observation.admission_status == "UNADMITTED"
    assert result.observation.canonical_status == "NON_CANONICAL"
    assert result.observation.governing_status == "NON_GOVERNING"
    assert result.observation.application_status == "NOT_APPLIED"
    assert result.retention_receipt.raw_response_base64 is not None
    assert base64.b64decode(
        result.retention_receipt.raw_response_base64, validate=True
    ) == opaque
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
    "forbidden_key",
    (
        "ExperimentID",
        "acquisition-attempt-number",
        "execution.order",
        "timeStamp",
        "random-nonce",
        "requestUUID",
        "processState",
        "memory-address",
        "localFilesystemPath",
        "SiblingState",
        "transportAttemptId",
        "credential_file",
        "X-API-Key",
        "AuthorizationHeader",
        "requestHeaders",
        "Cookie",
        "cookies",
    ),
)
def test_nested_out_of_band_key_variants_are_rejected_recursively(
    forbidden_key: str,
) -> None:
    body = {
        "messages": [
            {
                "role": "user",
                "content": {"safe": [{"details": {forbidden_key: "canary"}}]},
            }
        ]
    }
    with pytest.raises(AcquisitionRuntimeError, match="out-of-band key"):
        build_provider_visible_request(body)


def test_provider_key_firewall_does_not_reject_benign_semantic_keys() -> None:
    body = {
        "messages": [{"role": "user", "content": "reason carefully"}],
        "message_order": ("system", "user"),
        "attempted_solution": "candidate",
        "experiment_hypothesis": "semantic subject matter",
        "memory_safety_topic": "semantic subject matter",
        "filesystem_semantics": "semantic subject matter",
        "heading": "semantic subject matter",
        "max_tokens": 128,
    }
    visible = build_provider_visible_request(body)
    assert visible.canonical_request_json == json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def test_prompt_entropy_firewall_keeps_recursive_scalar_canary_scan() -> None:
    parsed = {
        "messages": [
            {"role": "user", "content": {"text": "prefix branch-a suffix"}}
        ]
    }
    assert _entropy_in_body(parsed, ("branch-a", "experiment/v0")) is True
    assert _entropy_in_body(parsed, ("sibling-b", "experiment/v0")) is False


def test_sibling_acquisition_is_order_independent_with_private_transport_state() -> None:
    async def execute_order(order: tuple[str, str]):
        fixture = build_frozen_acquisition_fixtures_v0()
        request = fixture.semantic_request
        raw_by_branch = {
            "sibling-a": b"\x00private-response-a\xff",
            "sibling-b": b"\x00private-response-b\xfe",
        }
        attempts = {branch: _attempt(request, branch) for branch in raw_by_branch}
        transports = {
            branch: _transport(
                [
                    _envelope(
                        request,
                        attempts[branch],
                        fixture.known_historical_usage,
                        raw_response_bytes=raw_by_branch[branch],
                    )
                ],
                request,
            )
            for branch in raw_by_branch
        }
        results = {}
        for branch in order:
            results[branch] = await acquire_canned_observation(
                request,
                attempts[branch],
                fixture.control_policy,
                fixture.retention_policy,
                transports[branch],
                historical_usage=fixture.known_historical_usage,
                isolation_probe=_isolation_probe(),
                capability_snapshot=transports[branch].capabilities,
            )
        return results, transports, attempts, raw_by_branch

    async def scenario():
        forward = await execute_order(("sibling-a", "sibling-b"))
        reverse = await execute_order(("sibling-b", "sibling-a"))
        return forward, reverse

    (forward, forward_transports, attempts, raw_by_branch), (
        reverse,
        reverse_transports,
        reverse_attempts,
        reverse_raw,
    ) = asyncio.run(scenario())

    assert attempts == reverse_attempts
    assert raw_by_branch == reverse_raw
    assert attempts["sibling-a"].transport_attempt_id != (
        attempts["sibling-b"].transport_attempt_id
    )
    assert {
        result.provider_visible_body for result in (*forward.values(), *reverse.values())
    } == {render_provider_visible_request(build_frozen_acquisition_fixtures_v0().semantic_request)}
    for branch in ("sibling-a", "sibling-b"):
        assert forward[branch].attempt_receipt == reverse[branch].attempt_receipt
        assert forward[branch].isolation_receipt == reverse[branch].isolation_receipt
        assert forward[branch].retention_receipt == reverse[branch].retention_receipt
        assert forward_transports[branch] is not forward_transports[
            "sibling-b" if branch == "sibling-a" else "sibling-a"
        ]
        assert forward_transports[branch].invocation_count == 1
        assert reverse_transports[branch].invocation_count == 1
        assert len(forward_transports[branch].invocation_records) == 1
        assert len(reverse_transports[branch].invocation_records) == 1
        assert forward[branch].attempt_receipt.computed_raw_response_digest == (
            hashlib.sha256(raw_by_branch[branch]).hexdigest()
        )
        retained = base64.b64decode(
            forward[branch].retention_receipt.raw_response_base64 or "",
            validate=True,
        )
        assert retained == raw_by_branch[branch]
        other = "sibling-b" if branch == "sibling-a" else "sibling-a"
        assert raw_by_branch[other] not in forward[branch].provider_visible_body
        assert forward[branch].transport_record is not None
        assert forward[branch].transport_record.transport_attempt_id == (
            attempts[branch].transport_attempt_id
        )


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
        (
            CannedImplementationProfile.FALLBACK_DISABLE_UNPROVEN,
            AcquisitionControlName.FALLBACK,
            AcquisitionControlState.PROVEN_SUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
        ),
        (
            CannedImplementationProfile.RETRY_DISABLE_UNPROVEN,
            AcquisitionControlName.EXPLICIT_RETRY,
            AcquisitionControlState.PROVEN_SUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
        ),
        (
            CannedImplementationProfile.SDK_RETRY_DISABLE_UNPROVEN,
            AcquisitionControlName.SDK_INTERNAL_RETRY,
            AcquisitionControlState.PROVEN_SUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
        ),
        (
            CannedImplementationProfile.TERMINATION_UNPROVEN,
            AcquisitionControlName.TIMEOUT_WORKER_TERMINATION,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
            AcquisitionTransportMode.CANNED_ONLY,
            True,
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
            CannedImplementationProfile.FALLBACK_DISABLE_UNPROVEN,
            AcquisitionGuardId.P09_FALLBACK_DISABLED,
            AcquisitionFailureCode.FALLBACK_CONTROL_UNPROVEN,
        ),
        (
            CannedImplementationProfile.RETRY_DISABLE_UNPROVEN,
            AcquisitionGuardId.P10_RETRY_DISABLED,
            AcquisitionFailureCode.RETRY_CONTROL_UNPROVEN,
        ),
        (
            CannedImplementationProfile.SDK_RETRY_DISABLE_UNPROVEN,
            AcquisitionGuardId.P11_SDK_INTERNAL_RETRY_DISABLED,
            AcquisitionFailureCode.SDK_INTERNAL_RETRY_CONTROL_UNPROVEN,
        ),
        (
            CannedImplementationProfile.TERMINATION_UNPROVEN,
            AcquisitionGuardId.P13_TIMEOUT_WORKER_TERMINATION,
            AcquisitionFailureCode.TIMEOUT_CANCELLATION_UNPROVEN,
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
            {
                "raw_response_bytes": None,
                "reported_digest": None,
                "reported_length": None,
            },
            AcquisitionGuardId.A10_RAW_RESPONSE_PRESENCE,
            AcquisitionFailureCode.MISSING_RAW_OBSERVATION,
        ),
        (
            {"reported_digest": "f" * 64},
            AcquisitionGuardId.A11_RESPONSE_DIGEST_INTEGRITY,
            AcquisitionFailureCode.INVALID_RESPONSE_DIGEST,
        ),
        (
            {"reported_length": 999},
            AcquisitionGuardId.A11_RESPONSE_DIGEST_INTEGRITY,
            AcquisitionFailureCode.INVALID_RESPONSE_DIGEST,
        ),
        (
            {"actual_model_id": None},
            AcquisitionGuardId.A05_ACTUAL_MODEL_IDENTITY,
            AcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
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


def test_missing_raw_response_does_not_fabricate_empty_retention_evidence() -> None:
    result = _run(raw_response_bytes=None)
    assert result.failure_code is AcquisitionFailureCode.MISSING_RAW_OBSERVATION
    receipt = result.retention_receipt
    assert receipt.raw_response_digest is None
    assert receipt.raw_response_length is None
    assert receipt.raw_response_base64 is None
    assert receipt.content_addressed_response_reference is None
    assert receipt.policy_compliant is True


def test_unallowlisted_secret_response_fails_closed_without_retaining_bytes() -> None:
    secret = b"sk-live-provider-secret-must-never-be-retained"
    result = _run(raw_response_bytes=secret)
    assert result.failure_code is AcquisitionFailureCode.RETENTION_POLICY_VIOLATION
    assert result.observation is None
    assert result.retention_receipt.policy_compliant is False
    assert "raw_response_non_sensitive_attestation" in (
        result.retention_receipt.violations
    )
    assert result.retention_receipt.raw_response_base64 is None
    assert result.retention_receipt.content_addressed_response_reference is None
    assert result.attempt_receipt.raw_response_base64 is None
    assert result.retention_receipt.data_classification is (
        AcquisitionDataClassification.UNKNOWN
    )
    assert result.retention_receipt.redaction_status is (
        AcquisitionRedactionStatus.NOT_APPLIED
    )
    assert result.retention_receipt.artifact_inclusion is (
        AcquisitionArtifactInclusionPolicy.EXCLUDE
    )
    assert result.retention_receipt.raw_response_digest == hashlib.sha256(secret).hexdigest()
    serialized = result.attempt_receipt.model_dump_json() + (
        result.retention_receipt.model_dump_json()
    )
    assert secret.decode("ascii") not in serialized


@pytest.mark.parametrize("field", ("actual_provider_id", "actual_model_id"))
def test_untrusted_actual_identity_metadata_is_redacted_from_failed_receipts(
    field: str,
) -> None:
    secret = "sk-live-identity-secret-must-never-be-retained"
    result = _run(envelope_kwargs={field: secret})
    expected_guard = (
        AcquisitionGuardId.A04_ACTUAL_PROVIDER_IDENTITY
        if field == "actual_provider_id"
        else AcquisitionGuardId.A05_ACTUAL_MODEL_IDENTITY
    )
    assert result.attempt_receipt.primary_result.primary_guard_id is expected_guard
    assert result.attempt_receipt.actual_binding is None
    assert result.attempt_receipt.raw_response_base64 is None
    assert result.retention_receipt.policy_compliant is False
    assert result.retention_receipt.data_classification is (
        AcquisitionDataClassification.UNKNOWN
    )
    assert result.retention_receipt.personal_private_data_present is True
    assert result.retention_receipt.artifact_inclusion is (
        AcquisitionArtifactInclusionPolicy.EXCLUDE
    )
    serialized = result.attempt_receipt.model_dump_json() + (
        result.retention_receipt.model_dump_json()
    )
    assert secret not in serialized


@pytest.mark.parametrize(
    ("request_tamper", "expected_guard", "expected_failure"),
    (
        (
            None,
            AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY,
            AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT,
        ),
        (
            "request",
            AcquisitionGuardId.P01_REQUEST_INTEGRITY,
            AcquisitionFailureCode.INVALID_ACQUISITION_REQUEST,
        ),
        (
            "semantic_identity",
            AcquisitionGuardId.P02_SEMANTIC_IDENTITY_INTEGRITY,
            AcquisitionFailureCode.INVALID_SEMANTIC_IDENTITY,
        ),
    ),
)
def test_hostile_transport_is_never_touched_before_its_winning_guard(
    request_tamper: str | None,
    expected_guard: AcquisitionGuardId,
    expected_failure: AcquisitionFailureCode,
) -> None:
    touched: list[str] = []

    class HostileTransport(CannedAcquisitionTransport):
        armed = False

        def __getattribute__(self, name):
            if type(self).armed:
                touched.append(name)
                raise AssertionError(f"hostile transport attribute touched: {name}")
            return super().__getattribute__(name)

        async def acquire(self, provider_visible_body, attempt):  # pragma: no cover
            touched.append("acquire")
            raise AssertionError("hostile acquire must never run")

    fixture = build_frozen_acquisition_fixtures_v0()
    base_request = fixture.semantic_request
    provisional = _transport(
        [
            _envelope(
                base_request,
                _attempt(base_request),
                fixture.known_historical_usage,
            )
        ],
        base_request,
    )
    request = _request_for_capability(
        base_request,
        provisional.capabilities.capability_snapshot_id or "",
    )
    attempt = _attempt(request)
    trusted_capability = provisional.capabilities
    transport = HostileTransport(
        [_envelope(request, attempt, fixture.known_historical_usage)],
        provider_id=request.requested_binding.provider_id,
        adapter_id=trusted_capability.adapter_id,
        adapter_version=trusted_capability.adapter_version,
        adapter_revision_digest=trusted_capability.adapter_revision_digest,
        requested_model_id=request.requested_binding.model_id,
        seed_status=AcquisitionSeedStatus.UNSUPPORTED,
    )
    HostileTransport.armed = True
    if request_tamper == "request":
        object.__setattr__(request, "action_id", "not-a-legal-action")
    elif request_tamper == "semantic_identity":
        object.__setattr__(request, "semantic_request_id", f"szacqrequest_{'f' * 64}")
    result = asyncio.run(
        acquire_canned_observation(
            request,
            attempt,
            fixture.control_policy,
            fixture.retention_policy,
            transport,
            historical_usage=fixture.known_historical_usage,
            isolation_probe=_isolation_probe(),
            capability_snapshot=trusted_capability,
        )
    )
    assert result.failure_code is expected_failure
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        expected_guard
    )
    assert result.tripwire_counters.canned_transport_invocations == 0
    assert result.transport_record is None
    assert touched == []


def _exact_transport_boundary_inputs():
    fixture = build_frozen_acquisition_fixtures_v0()
    base_request = fixture.semantic_request
    provisional = _transport(
        [_envelope(base_request, _attempt(base_request), fixture.known_historical_usage)],
        base_request,
    )
    request = _request_for_capability(
        base_request,
        provisional.capabilities.capability_snapshot_id or "",
    )
    attempt = _attempt(request)
    transport = _transport(
        [_envelope(request, attempt, fixture.known_historical_usage)],
        request,
    )
    return fixture, request, attempt, transport


def _run_exact_transport_boundary(
    fixture,
    request,
    attempt,
    transport,
):
    return asyncio.run(
        acquire_canned_observation(
            request,
            attempt,
            fixture.control_policy,
            fixture.retention_policy,
            transport,
            historical_usage=fixture.known_historical_usage,
            isolation_probe=_isolation_probe(),
            capability_snapshot=fixture.capability_snapshot,
        )
    )


@pytest.mark.parametrize(
    "poison_target",
    (
        "script",
        "ledger",
        "acquire_shadow",
        "script_equal_clone",
        "ledger_equal_clone",
        "records_equal_clone",
        "capabilities_equal_clone",
        "profiles_equal_clone",
    ),
)
def test_exact_transport_poison_is_rejected_without_executing_poison(
    poison_target: str,
) -> None:
    touched: list[str] = []

    class Poison:
        def __getattribute__(self, name):
            touched.append(name)
            raise AssertionError(f"poison touched: {name}")

        def __call__(self, *args, **kwargs):
            touched.append("call")
            raise AssertionError("poison called")

    fixture, request, attempt, transport = _exact_transport_boundary_inputs()
    if poison_target == "script":
        object.__setattr__(transport, "_script", (Poison(),))
    elif poison_target == "ledger":
        object.__setattr__(transport, "_ledger", Poison())
    elif poison_target == "acquire_shadow":
        object.__getattribute__(transport, "__dict__")["acquire"] = Poison()
    elif poison_target == "script_equal_clone":
        original = object.__getattribute__(transport, "_script")
        object.__setattr__(transport, "_script", tuple(list(original)))
    elif poison_target == "ledger_equal_clone":
        original = object.__getattribute__(transport, "_ledger")
        object.__setattr__(transport, "_ledger", type(original)())
    elif poison_target == "records_equal_clone":
        original = object.__getattribute__(transport, "_records")
        object.__setattr__(transport, "_records", list(original))
    elif poison_target == "capabilities_equal_clone":
        original = object.__getattribute__(transport, "capabilities")
        clone = type(original).model_validate(original.model_dump(mode="python"))
        object.__setattr__(transport, "capabilities", clone)
    else:
        original = object.__getattribute__(transport, "implementation_profiles")
        object.__setattr__(transport, "implementation_profiles", tuple(list(original)))

    result = _run_exact_transport_boundary(fixture, request, attempt, transport)
    assert result.failure_code is AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY
    )
    assert result.runtime_counters.canned_transport_invocations == 0
    assert result.transport_record is None
    assert touched == []


def test_poisoned_directive_boolean_is_rejected_without_truth_evaluation() -> None:
    touched: list[str] = []

    class EvilTruth:
        def __bool__(self):
            touched.append("bool")
            raise AssertionError("poisoned truth value evaluated")

    fixture, request, attempt, transport = _exact_transport_boundary_inputs()
    directive = object.__getattribute__(transport, "_script")[0]
    object.__setattr__(directive, "wait_for_cancellation", EvilTruth())
    result = _run_exact_transport_boundary(fixture, request, attempt, transport)
    assert result.failure_code is AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY
    )
    assert result.runtime_counters.canned_transport_invocations == 0
    assert touched == []


def test_transport_construction_rejects_regular_post_init_mutation() -> None:
    _fixture, _request, _attempt_value, transport = _exact_transport_boundary_inputs()
    with pytest.raises(AttributeError, match="construction is sealed"):
        transport._script = ()


def test_class_worker_monkeypatch_is_rejected_before_dispatch(monkeypatch) -> None:
    touched: list[str] = []
    fixture, request, attempt, transport = _exact_transport_boundary_inputs()

    async def hostile_acquire(self, provider_visible_body, attempt):  # pragma: no cover
        touched.append("acquire")
        raise AssertionError("monkeypatched acquire must never run")

    monkeypatch.setattr(CannedAcquisitionTransport, "acquire", hostile_acquire)
    result = _run_exact_transport_boundary(fixture, request, attempt, transport)
    assert result.failure_code is AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY
    )
    assert result.runtime_counters.canned_transport_invocations == 0
    assert touched == []


def test_ledger_worker_monkeypatch_is_rejected_before_dispatch(monkeypatch) -> None:
    touched: list[str] = []
    fixture, request, attempt, transport = _exact_transport_boundary_inputs()
    ledger = object.__getattribute__(transport, "_ledger")

    def hostile_enter(self):  # pragma: no cover
        touched.append("enter_transport")
        raise AssertionError("monkeypatched ledger must never run")

    monkeypatch.setattr(type(ledger), "enter_transport", hostile_enter)
    result = _run_exact_transport_boundary(fixture, request, attempt, transport)
    assert result.failure_code is AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY
    )
    assert result.runtime_counters.canned_transport_invocations == 0
    assert touched == []


def test_canned_transport_is_one_shot_and_reuse_fails_at_p03() -> None:
    fixture, request, attempt, transport = _exact_transport_boundary_inputs()
    first = _run_exact_transport_boundary(fixture, request, attempt, transport)
    assert first.outcome is AcquisitionAttemptOutcome.ACQUIRED
    second = _run_exact_transport_boundary(fixture, request, attempt, transport)
    assert second.failure_code is AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT
    assert second.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY
    )
    assert second.runtime_counters.canned_transport_invocations == 0
    assert second.transport_record is None


@pytest.mark.parametrize("hostile_kind", ("directive", "envelope"))
def test_transport_constructor_rejects_hostile_subtypes_without_touching_them(
    hostile_kind: str,
) -> None:
    touched: list[str] = []

    if hostile_kind == "directive":
        class Hostile(CannedTransportDirective):
            def __getattribute__(self, name):
                touched.append(name)
                raise AssertionError(f"hostile directive touched: {name}")
    else:
        class Hostile(CannedTransportEnvelope):
            def __getattribute__(self, name):
                touched.append(name)
                raise AssertionError(f"hostile envelope touched: {name}")

    hostile = object.__new__(Hostile)
    fixture = build_frozen_acquisition_fixtures_v0()
    with pytest.raises(TypeError, match="script entries"):
        _transport([hostile], fixture.semantic_request)
    assert touched == []


def test_directive_constructor_rejects_poisoned_truth_without_evaluating_it() -> None:
    touched: list[str] = []

    class EvilTruth:
        def __bool__(self):
            touched.append("bool")
            raise AssertionError("poisoned truth value evaluated")

    with pytest.raises(TypeError, match="exact booleans"):
        CannedTransportDirective(wait_for_cancellation=EvilTruth())
    assert touched == []


@pytest.mark.parametrize("tamper", ("actual_identity", "raw_digest", "retry", "tool"))
def test_rehashed_acquired_receipt_rejects_contradictory_evidence(tamper: str) -> None:
    receipt = _run().attempt_receipt
    payload = receipt.model_dump(mode="json")
    payload["receipt_id"] = None
    payload["receipt_hash"] = None
    if tamper == "actual_identity":
        payload["actual_model_id"] = "wrong-model"
        payload["actual_binding"]["model_id"] = "wrong-model"
    elif tamper == "raw_digest":
        payload["reported_raw_response_digest"] = "f" * 64
        payload["computed_raw_response_digest"] = "f" * 64
    elif tamper == "retry":
        payload["explicit_retry_count"] = 1
    else:
        payload["tool_calls"] = 1
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)


@pytest.mark.parametrize(
    ("envelope_kwargs", "repair"),
    (
        (
            {"actual_model_id": None},
            "actual_model",
        ),
        (
            {"reported_digest": "f" * 64},
            "raw_digest",
        ),
    ),
)
def test_rehashed_failed_receipt_cannot_keep_label_after_repairing_evidence(
    envelope_kwargs: dict[str, Any],
    repair: str,
) -> None:
    receipt = _run(envelope_kwargs=envelope_kwargs).attempt_receipt
    payload = receipt.model_dump(mode="json")
    payload["receipt_id"] = None
    payload["receipt_hash"] = None
    if repair == "actual_model":
        requested = payload["requested_binding"]
        payload["actual_model_id"] = requested["model_id"]
        payload["actual_binding"] = requested
    else:
        payload["reported_raw_response_digest"] = payload[
            "computed_raw_response_digest"
        ]
    with pytest.raises(ValidationError, match="contradicts"):
        type(receipt).model_validate(payload)


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


async def _run_timeout_scenario(*, resist_initial_cancellation: bool):
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
        [
            CannedTransportDirective(
                wait_for_cancellation=True,
                resist_initial_cancellation=resist_initial_cancellation,
            )
        ],
        request,
    )
    result = await acquire_canned_observation(
        request,
        attempt,
        policy,
        fixture.retention_policy,
        transport,
        historical_usage=fixture.known_historical_usage,
        isolation_probe=_isolation_probe(),
        capability_snapshot=transport.capabilities,
    )
    frozen_receipt = result.attempt_receipt.model_dump_json()
    frozen_records = transport.invocation_records
    frozen_count = transport.invocation_count
    for _turn in range(3):
        await asyncio.sleep(0)
    leaked = tuple(
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and task.get_name().startswith("socrates-zero-canned-acquisition-")
        and not task.done()
    )
    assert leaked == ()
    assert result.attempt_receipt.model_dump_json() == frozen_receipt
    assert transport.invocation_records == frozen_records
    assert transport.invocation_count == frozen_count
    return result, transport


def test_real_canned_timeout_counts_entry_and_proves_cooperative_termination() -> None:
    result, transport = asyncio.run(
        _run_timeout_scenario(resist_initial_cancellation=False)
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
    assert result.transport_record.cancellation_requests == 1
    assert result.transport_record.forced_cleanup is False


def test_cancellation_resistant_worker_is_forced_clean_without_late_effects() -> None:
    assert CANNED_TIMEOUT_CLEANUP_ROUNDS == 2
    assert 0 < CANNED_TIMEOUT_CLEANUP_GRACE_SECONDS <= 0.05
    result, transport = asyncio.run(
        _run_timeout_scenario(resist_initial_cancellation=True)
    )
    assert result.outcome is AcquisitionAttemptOutcome.FAILED_CLOSED
    assert result.failure_code is AcquisitionFailureCode.TRANSPORT_TIMEOUT
    assert result.attempt_receipt.primary_result.primary_guard_id is (
        AcquisitionGuardId.A02_TRANSPORT_COMPLETION
    )
    assert result.observation is None
    assert result.runtime_counters.canned_transport_invocations == 1
    assert result.attempt_receipt.execution_usage.canned_transport_invocations.value == 1
    assert result.transport_record is not None
    assert result.transport_record.outcome == "FORCED_CLEANUP"
    assert result.transport_record.cancellation_acknowledged is True
    assert result.transport_record.worker_terminated is True
    assert result.transport_record.cancellation_requests == 2
    assert result.transport_record.forced_cleanup is True
    assert transport.invocation_count == 1
    assert len(transport.invocation_records) == 1

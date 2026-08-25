"""Focused locks for the provider-agnostic acquisition-contract boundary."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.acquisition_contracts import (
    ACQUISITION_CONTRACT_ID,
    ACQUISITION_GUARD_ORDER,
    CANNED_TRANSPORT_ID,
    FIRST_ACQUISITION_GUARD_WINS,
    FROZEN_ACQUISITION_FAILURE_TAXONOMY,
    FROZEN_ACQUISITION_VALIDATION_ORDER,
    FROZEN_REQUIRED_CONTROL_STATES,
    AcquisitionArtifactInclusionPolicy,
    AcquisitionBudget,
    AcquisitionCapabilitySnapshot,
    AcquisitionControlEvidence,
    AcquisitionControlName,
    AcquisitionControlPolicy,
    AcquisitionControlRequirement,
    AcquisitionControlState,
    AcquisitionDataClassification,
    AcquisitionRedactionStatus,
    AcquisitionResourceQuantity,
    AcquisitionRequestConfiguration,
    AcquisitionRetentionPolicy,
    AcquisitionRetentionReceipt,
    AcquisitionSeedSetting,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    AcquisitionTransportAttempt,
    AcquisitionTransportMode,
    CannedTransportEnvelope,
    ProviderVisibleRequestBytes,
    ResourceKnowledgeState,
    ResponseRetentionMode,
    UnadmittedAcquiredObservation,
)
from backend.dialogues.socrates_zero.contracts import canonical_json


_ROOT_CAPSULE_ID = (
    "cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50"
)
_ROOT_STATE_ID = (
    "szstatev1_a17ce47c27894a3aac4095d0c08da107142a54d2b773c10104fde2b250c2f20e"
)
_PENDING_TRANSITION_ID = (
    "cedpending_3111a26bb87ea7b0fe5a1658ffc86a6313fa66b4ac2f167095c0393bea85c31a"
)
_CANONICAL_TASK_ID = (
    "cedtasksemantic_b5ace018c4bb1369d62bb5004a99edcd8945e4dd0eef1e206570c96b1d71017a"
)
_ACTION_ID = (
    "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
)
_PROVIDER_ID = "canned-research-provider"
_MODEL_ID = "canned-research-model/v0"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _control_state(name: AcquisitionControlName) -> AcquisitionControlState:
    disabled = {
        AcquisitionControlName.FALLBACK,
        AcquisitionControlName.EXPLICIT_RETRY,
        AcquisitionControlName.ADAPTER_RETRY,
        AcquisitionControlName.SDK_INTERNAL_RETRY,
        AcquisitionControlName.HIDDEN_TRANSPORT_RETRY,
        AcquisitionControlName.TOOLS,
        AcquisitionControlName.EXTERNAL_NETWORK,
        AcquisitionControlName.CREDENTIAL_ACCESS,
    }
    if name is AcquisitionControlName.SEED:
        return AcquisitionControlState.PROVEN_UNSUPPORTED
    if name in disabled:
        return AcquisitionControlState.PROVEN_DISABLED
    return AcquisitionControlState.PROVEN_SUPPORTED


def _capability() -> AcquisitionCapabilitySnapshot:
    return AcquisitionCapabilitySnapshot(
        provider_id=_PROVIDER_ID,
        adapter_id="hermetic-in-memory-canned-adapter",
        adapter_version="v0",
        adapter_revision_digest=_digest("hermetic-in-memory-canned-adapter/v0"),
        requested_model_id=_MODEL_ID,
        registered_canned_transport_ids=(CANNED_TRANSPORT_ID,),
        controls=tuple(
            AcquisitionControlEvidence(
                name=name,
                state=_control_state(name),
                evidence_id=f"implementation-bound:{name.value}",
                evidence_digest=_digest(f"{name.value}:{_control_state(name).value}"),
            )
            for name in AcquisitionControlName
        ),
    )


def _policy() -> AcquisitionControlPolicy:
    return AcquisitionControlPolicy(
        requirements=tuple(
            AcquisitionControlRequirement(name=name, allowed_states=states)
            for name, states in FROZEN_REQUIRED_CONTROL_STATES
        ),
        temperature=0.0,
        seed=AcquisitionSeedSetting(status=AcquisitionSeedStatus.UNSUPPORTED),
        max_output_tokens=256,
        timeout_ms=100,
        budget=AcquisitionBudget(max_canned_transport_invocations=1),
    )


def _request() -> AcquisitionSemanticRequest:
    capability = _capability()
    policy = _policy()
    visible_json = canonical_json(
        {
            "max_output_tokens": 256,
            "messages": [
                {
                    "content": (
                        "Ask one concise opening Socratic question without "
                        "answering the user's question."
                    ),
                    "role": "system",
                },
                {
                    "content": "Is knowledge merely justified true belief?",
                    "role": "user",
                },
            ],
            "model": _MODEL_ID,
            "response_format": {"type": "text"},
            "temperature": 0.0,
            "tools": [],
        }
    )
    configuration = AcquisitionRequestConfiguration(
        temperature=0.0,
        seed=AcquisitionSeedSetting(status=AcquisitionSeedStatus.UNSUPPORTED),
        max_output_tokens=256,
        timeout_ms=100,
        provider_visible_metadata_digest=_digest("no-provider-visible-metadata"),
    )
    from backend.dialogues.socrates_zero.acquisition_contracts import (
        AcquisitionProviderModelBinding,
    )

    binding = AcquisitionProviderModelBinding(
        provider_id=_PROVIDER_ID,
        model_id=_MODEL_ID,
        configuration_digest=configuration.configuration_digest or "",
    )
    return AcquisitionSemanticRequest(
        source_capsule_id=_ROOT_CAPSULE_ID,
        source_execution_id="cedexecution_frozen-acquisition-source-v0",
        root_state_v1_id=_ROOT_STATE_ID,
        pending_transition_id=_PENDING_TRANSITION_ID,
        canonical_task_identity_id=_CANONICAL_TASK_ID,
        action_id=_ACTION_ID,
        complete_legal_action_ids=(_ACTION_ID,),
        requested_binding=binding,
        capability_snapshot_id=capability.capability_snapshot_id or "",
        control_policy_id=policy.control_policy_id or "",
        request_configuration=configuration,
        provider_visible_request=ProviderVisibleRequestBytes(
            rendering_version="canonical-json-utf8/v0",
            canonical_request_json=visible_json,
        ),
    )


def test_frozen_methodology_has_exact_complete_order_and_taxonomy() -> None:
    assert ACQUISITION_CONTRACT_ID == (
        "socrateszero-external-observation-acquisition/v0"
    )
    assert FROZEN_ACQUISITION_VALIDATION_ORDER.precedence_model == (
        FIRST_ACQUISITION_GUARD_WINS
    )
    assert len(ACQUISITION_GUARD_ORDER) == 34
    assert len(set(ACQUISITION_GUARD_ORDER)) == 34
    assert tuple(
        step.guard_id for step in FROZEN_ACQUISITION_VALIDATION_ORDER.steps
    ) == ACQUISITION_GUARD_ORDER
    assert {
        entry.code for entry in FROZEN_ACQUISITION_FAILURE_TAXONOMY.entries
    } == {
        code
        for step in FROZEN_ACQUISITION_VALIDATION_ORDER.steps
        for code in step.allowed_failure_codes
    }


def test_capability_snapshot_is_complete_immutable_and_content_addressed() -> None:
    capability = _capability()
    assert {row.name for row in capability.controls} == set(AcquisitionControlName)
    assert all(row.state is not AcquisitionControlState.UNKNOWN for row in capability.controls)
    assert capability.capability_snapshot_id.startswith("szacqcap_")
    with pytest.raises(ValidationError):
        capability.provider_id = "mutated"  # type: ignore[misc]
    tampered = capability.model_dump(mode="json")
    tampered["provider_id"] = "mutated-provider"
    with pytest.raises(ValidationError, match="capability_snapshot_id"):
        AcquisitionCapabilitySnapshot.model_validate(tampered)


def test_unknown_is_never_numeric_zero_and_seed_unsupported_is_explicit() -> None:
    unknown = AcquisitionResourceQuantity.unknown()
    zero = AcquisitionResourceQuantity.known(0)
    assert unknown.knowledge is ResourceKnowledgeState.UNKNOWN
    assert unknown.value is None
    assert zero.knowledge is ResourceKnowledgeState.KNOWN
    assert zero.value == 0
    assert unknown != zero
    with pytest.raises(ValidationError):
        AcquisitionResourceQuantity(
            knowledge=ResourceKnowledgeState.UNKNOWN,
            value=0,
        )
    assert _policy().seed == AcquisitionSeedSetting(
        status=AcquisitionSeedStatus.UNSUPPORTED
    )


def test_retention_receipt_preserves_exact_no_response_as_all_none() -> None:
    request = _request()
    visible = request.provider_visible_request
    policy = AcquisitionRetentionPolicy(
        response_retention_mode=ResponseRetentionMode.RAW_BYTES_BASE64,
        retention_classification="non-sensitive-canned-research-v0",
        retention_reason="no response was produced",
        access_policy_id="socrateszero-canned-fixture-access/v0",
        artifact_inclusion_policy=(
            AcquisitionArtifactInclusionPolicy.INCLUDE_RAW_NON_SENSITIVE_RESPONSE
        ),
    )
    receipt = AcquisitionRetentionReceipt(
        policy=policy,
        retention_policy_id=policy.retention_policy_id or "",
        semantic_request_id=request.semantic_request_id or "",
        transport_attempt_id="szacqattempt_no_response_fixture",
        provider_visible_prompt_digest=visible.sha256 or "",
        provider_visible_prompt_length=visible.byte_length or 0,
        provider_visible_prompt_reference=visible.provider_visible_request_id or "",
        provider_visible_prompt_raw_retained=False,
        raw_response_digest=None,
        raw_response_length=None,
        raw_response_base64=None,
        content_addressed_response_reference=None,
        data_classification=AcquisitionDataClassification.NON_SENSITIVE_CANNED,
        credentials_inspected=False,
        credentials_retained=False,
        personal_private_data_present=False,
        redaction_status=AcquisitionRedactionStatus.NOT_REQUIRED,
        artifact_inclusion=(
            AcquisitionArtifactInclusionPolicy.INCLUDE_RAW_NON_SENSITIVE_RESPONSE
        ),
    )

    assert receipt.policy_compliant is True
    assert receipt.violations == ()
    assert (
        receipt.raw_response_digest,
        receipt.raw_response_length,
        receipt.raw_response_base64,
        receipt.content_addressed_response_reference,
    ) == (None, None, None, None)


def test_adverse_capability_and_zero_budget_are_representable_for_audit() -> None:
    capability_payload = _capability().model_dump(mode="json")
    capability_payload["capability_snapshot_id"] = None
    capability_payload["transport_mode"] = AcquisitionTransportMode.EXTERNAL.value
    capability_payload["registered_canned_transport_ids"] = []
    adverse = AcquisitionCapabilitySnapshot.model_validate(capability_payload)
    assert adverse.transport_mode is AcquisitionTransportMode.EXTERNAL
    assert adverse.registered_canned_transport_ids == ()
    budget = AcquisitionBudget(max_canned_transport_invocations=0)
    assert budget.max_canned_transport_invocations == 0


def test_semantic_identity_is_stable_while_transport_identity_is_branch_local() -> None:
    first_request = _request()
    second_request = AcquisitionSemanticRequest.model_validate(
        first_request.model_dump(mode="json")
    )
    assert first_request.semantic_request_id == second_request.semantic_request_id
    first_attempt = AcquisitionTransportAttempt(
        semantic_request_id=first_request.semantic_request_id or "",
        experiment_id="acquisition-contract-v0",
        branch_id="sibling-a",
        attempt_ordinal=0,
    )
    second_attempt = AcquisitionTransportAttempt(
        semantic_request_id=second_request.semantic_request_id or "",
        experiment_id="acquisition-contract-v0",
        branch_id="sibling-b",
        attempt_ordinal=0,
    )
    assert first_attempt.semantic_request_id == second_attempt.semantic_request_id
    assert first_attempt.transport_attempt_id != second_attempt.transport_attempt_id
    visible = first_request.provider_visible_request.canonical_request_json.encode("utf-8")
    for forbidden in (b"sibling-a", b"sibling-b", b"acquisition-contract-v0"):
        assert forbidden not in visible


def test_provider_visible_request_is_exact_canonical_utf8_without_newline() -> None:
    visible = _request().provider_visible_request
    raw = visible.canonical_request_json.encode("utf-8")
    assert raw.decode("utf-8") == visible.canonical_request_json
    assert not raw.endswith(b"\n")
    assert len(raw) == visible.byte_length
    assert hashlib.sha256(raw).hexdigest() == visible.sha256
    parsed = __import__("json").loads(visible.canonical_request_json)
    assert canonical_json(parsed) == visible.canonical_request_json


@pytest.mark.parametrize(
    "forbidden_field",
    ("expected_result", "future_state", "reward", "canonical_result"),
)
def test_canned_envelope_rejects_evaluator_and_future_fields(
    forbidden_field: str,
) -> None:
    payload = {
        "transport_attempt_id": "szacqattempt_fixture",
        "transport_status": "DELIVERED",
        forbidden_field: "malicious-canary",
    }
    with pytest.raises(ValidationError, match="forbidden"):
        CannedTransportEnvelope.model_validate(payload)


def test_unadmitted_observation_schema_rejects_canonical_authority_fields() -> None:
    payload = {
        "semantic_request_id": "szacqrequest_fixture",
        "transport_attempt_id": "szacqattempt_fixture",
        "requested_binding": {
            "provider_id": _PROVIDER_ID,
            "model_id": _MODEL_ID,
            "configuration_digest": "0" * 64,
        },
        "actual_binding": {
            "provider_id": _PROVIDER_ID,
            "model_id": _MODEL_ID,
            "configuration_digest": "0" * 64,
        },
        "raw_response_digest": "0" * 64,
        "raw_response_length": 0,
        "raw_response_reference": "canned-fixture:empty",
        "execution_usage_id": "szacqusage_fixture",
        "historical_usage_id": "szacqhistory_fixture",
        "isolation_receipt_id": "szacqisolation_fixture",
        "retention_receipt_id": "szacqretention_fixture",
        "successor_state": "forbidden",
    }
    with pytest.raises(ValidationError, match="forbidden"):
        UnadmittedAcquiredObservation.model_validate(payload)


def test_identity_fields_reject_rebinding_instead_of_trusting_caller_ids() -> None:
    request = _request()
    payload = request.model_dump(mode="json")
    payload["semantic_request_id"] = "szacqrequest_" + "0" * 64
    with pytest.raises(ValidationError, match="semantic_request_id"):
        AcquisitionSemanticRequest.model_validate(payload)

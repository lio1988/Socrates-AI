"""Pre-freeze locks for the deterministic acquisition evaluator.

Every frozen case is executed and discarded independently.  This module never
constructs the 50-case aggregate, an experiment artifact, or a replay artifact,
and it never invokes a publisher.  The only filesystem write is the explicitly
scoped write-once primitive test under pytest's temporary directory.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from backend.dialogues.socrates_zero import acquisition_evaluation as evaluation
from backend.dialogues.socrates_zero.acquisition_cases import (
    FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0,
    FROZEN_ACQUISITION_POSITIVE_CASES_V0,
    FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0,
    FROZEN_ACQUISITION_THRESHOLDS_V0,
    FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0,
    FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0,
    FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0,
    FROZEN_OPAQUE_INVALID_RAW_RESPONSE_SHA256_V0,
    FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0,
    FROZEN_PROVIDER_VISIBLE_REQUEST_SHA256_V0,
    AcquisitionCaseClass,
)
from backend.dialogues.socrates_zero.acquisition_contracts import (
    ACQUISITION_GUARD_ORDER,
    AcquisitionAttemptOutcome,
    AcquisitionGuardState,
    AcquisitionPrimaryResult,
    ResourceKnowledgeState,
)
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)


_EXPECTED_VISIBLE_BYTES = (
    b'{"max_output_tokens":256,"messages":[{"content":"Ask one concise opening '
    b'Socratic question without answering the user\'s question.","role":"system"},'
    b'{"content":"Is knowledge merely justified true belief?","role":"user"}],'
    b'"metadata":{},"response_format":{"type":"text"},"temperature":0.0,"tools":[]}'
)

_EXPECTED_HISTORICAL_LOCKS = (
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

_EXPECTED_PROBE_ROWS = (
    ("acqv0-o01-invalid-request", ("request.schema_version",), "P01_REQUEST_INTEGRITY", "INVALID_ACQUISITION_REQUEST"),
    ("acqv0-o02-semantic-id-tamper", ("request.semantic_request_id",), "P02_SEMANTIC_IDENTITY_INTEGRITY", "INVALID_SEMANTIC_IDENTITY"),
    ("acqv0-o03-required-provider-verification-unknown", ("capability.actual_provider_identity_verification",), "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN"),
    ("acqv0-o04-non-canned-transport", ("capability.transport_mode",), "P05_CANNED_ONLY_TRANSPORT_MODE", "CANNED_ONLY_POLICY_VIOLATION"),
    ("acqv0-o05-external-network-enabled", ("capability.external_network",), "P06_EXTERNAL_NETWORK_PROHIBITION", "EXTERNAL_NETWORK_FORBIDDEN"),
    ("acqv0-o06-credential-access-enabled", ("capability.credential_access",), "P07_CREDENTIAL_ACCESS_PROHIBITION", "CREDENTIAL_ACCESS_FORBIDDEN"),
    ("acqv0-o07-exact-model-verification-unsupported", ("capability.actual_model_identity_verification",), "P08_EXACT_IDENTITY_VERIFICATION", "EXACT_IDENTITY_VERIFICATION_UNAVAILABLE"),
    ("acqv0-o08-fallback-disablement-unknown", ("capability.fallback",), "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN"),
    ("acqv0-o09-retry-disablement-unknown", ("capability.retry",), "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN"),
    ("acqv0-o10-sdk-retry-disablement-unknown", ("capability.sdk_internal_retry",), "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN"),
    ("acqv0-o11-tools-enabled", ("capability.tools",), "P12_TOOLS_DISABLED", "TOOLS_NOT_DISABLED"),
    ("acqv0-o12-timeout-termination-unknown", ("capability.worker_termination",), "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN"),
    ("acqv0-o13-resource-accounting-incomplete", ("capability.cost_reporting",), "P14_RESOURCE_ACCOUNTING", "RESOURCE_ACCOUNTING_INCOMPLETE"),
    ("acqv0-o14-budget-insufficient", ("budget.max_canned_transport_invocations",), "P15_BUDGET_SUFFICIENCY", "BUDGET_INCOMPLETE"),
    ("acqv0-o15-prompt-entropy", ("renderer.entropy_source",), "P16_PROMPT_BYTE_DETERMINISM", "PROMPT_ENTROPY_DETECTED"),
    ("acqv0-o16-canned-transport-unregistered", ("transport_registry.baseline_canned.registered",), "P18_CANNED_TRANSPORT_REGISTRATION", "CANNED_TRANSPORT_UNREGISTERED"),
    ("acqv0-o17-uncounted-canned-invocation", ("attempt_recorder.canned_transport_invocations",), "A01_CANNED_INVOCATION_COUNT", "UNCOUNTED_CANNED_INVOCATION"),
    ("acqv0-o18-transport-timeout-worker-terminated", ("envelope.transport_status",), "A02_TRANSPORT_COMPLETION", "TRANSPORT_TIMEOUT"),
    ("acqv0-o19-worker-not-terminated-after-completion", ("envelope.worker_terminated",), "A03_TIMEOUT_WORKER_TERMINATION", "TRANSPORT_WORKER_NOT_TERMINATED"),
    ("acqv0-o20-actual-provider-mismatch", ("envelope.actual_provider_id",), "A04_ACTUAL_PROVIDER_IDENTITY", "ACTUAL_PROVIDER_MISMATCH"),
    ("acqv0-o21-actual-model-mismatch", ("envelope.actual_model_id",), "A05_ACTUAL_MODEL_IDENTITY", "ACTUAL_MODEL_MISMATCH"),
    ("acqv0-o22-actual-config-mismatch", ("envelope.actual_configuration_digest",), "A06_ACTUAL_CONFIGURATION_IDENTITY", "ACTUAL_CONFIGURATION_MISMATCH"),
    ("acqv0-o23-fallback-activated", ("envelope.fallback_used",), "A07_FALLBACK_ACTIVATION", "FALLBACK_ACTIVATED"),
    ("acqv0-o24-retry-activated", ("envelope.retry_count",), "A08_RETRY_ACTIVATION", "RETRY_ACTIVATED"),
    ("acqv0-o25-tool-activated", ("envelope.tool_calls",), "A09_TOOL_ACTIVATION", "TOOL_ACTIVATED"),
    ("acqv0-o26-missing-raw", ("envelope.raw_response_base64",), "A10_RAW_RESPONSE_PRESENCE", "MISSING_RAW_OBSERVATION"),
    ("acqv0-o27-raw-digest-mismatch", ("envelope.raw_response_sha256",), "A11_RESPONSE_DIGEST_INTEGRITY", "INVALID_RESPONSE_DIGEST"),
    ("acqv0-o28-usage-incomplete", ("envelope.new_usage_completeness",), "A12_USAGE_COMPLETENESS", "USAGE_INCOMPLETE"),
    ("acqv0-o29-false-zero-usage", ("envelope.usage.tokens.knowledge",), "A12_USAGE_COMPLETENESS", "USAGE_INCOMPLETE"),
    ("acqv0-o30-resource-receipt-mismatch", ("resource_receipt.canned_transport_invocations",), "A13_RESOURCE_RECEIPT_INTEGRITY", "RESOURCE_RECEIPT_MISMATCH"),
    ("acqv0-o31-source-isolation-mismatch", ("isolation_probe.source.runtime_digest",), "A14_ISOLATION_INTEGRITY", "ISOLATION_FAILURE"),
    ("acqv0-o32-sibling-isolation-mismatch", ("isolation_probe.sibling.runtime_digest",), "A14_ISOLATION_INTEGRITY", "ISOLATION_FAILURE"),
    ("acqv0-o33-production-isolation-mismatch", ("isolation_probe.production.runtime_digest",), "A14_ISOLATION_INTEGRITY", "ISOLATION_FAILURE"),
    ("acqv0-o34-retention-policy-violation", ("retention_receipt.artifact_inclusion",), "A15_RETENTION_PRIVACY_INTEGRITY", "RETENTION_POLICY_VIOLATION"),
    ("acqv0-o35-final-receipt-identity-mismatch", ("attempt_recorder.final_receipt_integrity",), "A16_FINAL_RECEIPT_INTEGRITY", "RECEIPT_MISMATCH"),
    ("acqv0-o36-future-label-envelope", ("envelope.expected_canonical_acceptance",), "A02_TRANSPORT_COMPLETION", "TRANSPORT_ERROR"),
    ("acqv0-o37-missing-actual-model", ("envelope.actual_model_id",), "A05_ACTUAL_MODEL_IDENTITY", "ACTUAL_MODEL_MISMATCH"),
    ("acqv0-p01-invalid-request-plus-unknown-capability", ("request.schema_version", "capability.actual_provider_identity_verification"), "P01_REQUEST_INTEGRITY", "INVALID_ACQUISITION_REQUEST"),
    ("acqv0-p02-unknown-capability-plus-budget-gap", ("capability.actual_provider_identity_verification", "budget.max_canned_transport_invocations"), "P04_REQUIRED_CONTROL_COMPLETENESS", "REQUIRED_CONTROL_UNKNOWN"),
    ("acqv0-p03-prompt-entropy-plus-fallback-policy", ("capability.fallback", "renderer.entropy_source"), "P09_FALLBACK_DISABLED", "FALLBACK_CONTROL_UNPROVEN"),
    ("acqv0-p04-actual-model-plus-fallback-activation", ("envelope.actual_model_id", "envelope.fallback_used"), "A05_ACTUAL_MODEL_IDENTITY", "ACTUAL_MODEL_MISMATCH"),
    ("acqv0-p05-missing-raw-plus-usage-incomplete", ("envelope.raw_response_base64", "envelope.new_usage_completeness"), "A10_RAW_RESPONSE_PRESENCE", "MISSING_RAW_OBSERVATION"),
    ("acqv0-p06-network-plus-credential-policy", ("capability.external_network", "capability.credential_access"), "P06_EXTERNAL_NETWORK_PROHIBITION", "EXTERNAL_NETWORK_FORBIDDEN"),
    ("acqv0-p07-timeout-plus-worker-nontermination", ("envelope.transport_status", "envelope.worker_terminated"), "A02_TRANSPORT_COMPLETION", "TRANSPORT_TIMEOUT"),
)

_EXPECTED_PROBE_DESIGN_SHA256 = (
    "49c0d0cca2c06dc01087ba667eb1c4e71d9173c04b2b26292b8ba3169a880e73"
)

_THRESHOLD_TO_METRIC_FIELDS = (
    ("cases_total", "cases_total"),
    ("positive_cases_total", "positive_cases_total"),
    ("required_positive_complete_case_results", "positive_complete_case_results"),
    ("required_positive_attempt_receipts", "positive_attempt_receipts"),
    ("orthogonal_probes_total", "orthogonal_probes_total"),
    ("required_orthogonal_exact_primary_results", "orthogonal_exact_primary_results"),
    ("precedence_probes_total", "precedence_probes_total"),
    ("required_precedence_exact_primary_results", "precedence_exact_primary_results"),
    ("required_attempt_receipts_total", "attempt_receipts_total"),
    ("required_canned_transport_invocations", "observed_canned_transport_invocations"),
    ("maximum_mismatch_or_failure_count", "mismatch_or_failure_count"),
    ("required_invalid_probe_constructions", "invalid_probe_constructions"),
    ("required_semantic_identity_collisions", "semantic_identity_collisions"),
    ("required_prompt_byte_mismatches", "accepted_prompt_byte_mismatches"),
    ("required_external_network_attempts", "external_network_attempts"),
    ("required_credential_access_attempts", "credential_access_attempts"),
    ("required_live_provider_calls", "live_provider_calls"),
    ("required_model_executions", "model_executions"),
    ("required_tool_calls", "tool_calls"),
    ("required_uncounted_canned_invocations", "accepted_uncounted_canned_invocations"),
    ("required_successful_retry_activations", "accepted_successful_retry_activations"),
    ("required_successful_fallback_activations", "accepted_successful_fallback_activations"),
    ("required_timeout_worker_leaks", "accepted_timeout_worker_leaks"),
    ("required_source_mutations", "accepted_source_mutations"),
    ("required_sibling_mutations", "accepted_sibling_mutations"),
    ("required_production_mutations", "accepted_production_mutations"),
    ("required_accepted_missing_raw_observations", "accepted_missing_raw_observations"),
    ("required_accepted_false_zero_usage", "accepted_false_zero_usage"),
    ("required_incomplete_attempt_receipts", "accepted_incomplete_attempt_receipts"),
    ("required_retention_violations", "accepted_retention_violations"),
    ("required_receipt_mismatches", "accepted_receipt_mismatches"),
    ("required_future_label_violations", "accepted_future_label_violations"),
    ("required_canonical_application_invocations", "canonical_application_invocations"),
    ("required_new_tokens", "new_tokens"),
    ("required_new_cost_microusd", "new_cost_microusd"),
    ("required_external_provider_wall_time_ms", "external_provider_wall_time_ms"),
    ("required_historical_lock_mismatches", "historical_lock_mismatches"),
    ("required_core_blob_lock_mismatches", "core_blob_lock_mismatches"),
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _canonical_roundtrip(value: object) -> None:
    model_type = type(value)
    rendered = canonical_json(value.model_dump(mode="json"))
    assert model_type.model_validate_json(rendered) == value
    assert canonical_json(model_type.model_validate_json(rendered).model_dump(mode="json")) == rendered


def test_exact_frozen_fixture_ids_bytes_and_resource_knowledge() -> None:
    fixtures = evaluation.build_frozen_acquisition_fixtures_v0()
    request = fixtures.semantic_request
    visible = request.provider_visible_request

    assert fixtures.fixture_set_id == (
        "acqfixturesv0_6571aefb7415a637d64e27ed9a372c1cc4ebc6abc7b19bf0931748549b123f59"
    )
    assert fixtures.capability_snapshot.capability_snapshot_id == (
        "szacqcap_d36f538978eae2158aaf94afa71fe09a211f33cf0acaa7c33d9d6dd6b62c9656"
    )
    assert fixtures.control_policy.control_policy_id == (
        "szacqpolicy_646029f9c7fc42fc9f29a75fe18ab8c5f6bf53efad0a0a9e6e47bf4f983a9eca"
    )
    assert request.semantic_request_id == (
        "szacqrequest_b005c6c56dd4eeff795c7dd2427218ee01c28cba7cf6ea932a0d7b9a064c4ee1"
    )
    assert request.request_configuration.configuration_id == (
        "szacqconfig_c7cbccd7066a0d9c657932ce183f5e18821586fa1a7890f2f14d8efff0987d84"
    )
    assert request.request_configuration.configuration_digest == (
        "c7cbccd7066a0d9c657932ce183f5e18821586fa1a7890f2f14d8efff0987d84"
    )
    assert visible.provider_visible_request_id == (
        "szacqvisible_ea8c396387199ef8911a21c013f4ea7cc92fb502afdb92a3a695eb8b3a9b4bab"
    )
    assert fixtures.retention_policy.retention_policy_id == (
        "szacqretentionpolicy_88e70a6baa9c5a51267e02a6a676650381fee2e54602cc14ff20f61d6e419c59"
    )
    assert FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0 == _EXPECTED_VISIBLE_BYTES
    assert visible.canonical_request_json.encode("utf-8") == _EXPECTED_VISIBLE_BYTES
    assert FROZEN_PROVIDER_VISIBLE_REQUEST_SHA256_V0 == (
        "e75582c3a6d50a27efaf6676cbcc7d3bbad4a3635568ec194345c1becd67d8c7"
    )
    assert visible.sha256 == FROZEN_PROVIDER_VISIBLE_REQUEST_SHA256_V0
    assert visible.byte_length == len(_EXPECTED_VISIBLE_BYTES)
    assert FROZEN_COMPLETE_RAW_RESPONSE_BYTES_V0 == (
        b'{"kind":"canned","text":"What do you mean by knowledge?"}'
    )
    assert FROZEN_COMPLETE_RAW_RESPONSE_SHA256_V0 == (
        "52695d9df7b354e29d2faef21f569f1d1972cfd17d3c5e70a30cedaa646bee31"
    )
    assert FROZEN_OPAQUE_INVALID_RAW_RESPONSE_BYTES_V0 == (
        b"\x00\xff{not canonical Socratic JSON\x80"
    )
    assert FROZEN_OPAQUE_INVALID_RAW_RESPONSE_SHA256_V0 == (
        "7f41b1a101c82abeb70e6cb3f27547a2bbb21027f4b554a44877d1fed854449a"
    )

    known = fixtures.known_historical_usage
    unknown = fixtures.unknown_historical_usage
    quantity_names = (
        "source_observation_acquisitions",
        "source_model_calls",
        "source_tool_calls",
        "source_tokens",
        "source_cost_microusd",
        "source_external_wall_time_ms",
    )
    assert all(
        getattr(known, name).knowledge is ResourceKnowledgeState.KNOWN
        and getattr(known, name).value == 0
        for name in quantity_names
    )
    assert all(
        getattr(unknown, name).knowledge is ResourceKnowledgeState.UNKNOWN
        and getattr(unknown, name).value is None
        for name in quantity_names
    )
    _canonical_roundtrip(fixtures)


def test_all_six_historical_artifact_hashes_are_exact() -> None:
    evidence = evaluation.verify_frozen_historical_hashes_v0(_repository_root())
    actual = tuple(
        (item.label, item.repository_path, item.expected_sha256)
        for item in evidence
    )
    assert actual == _EXPECTED_HISTORICAL_LOCKS
    assert len(evidence) == 6
    assert all(item.matches for item in evidence)
    assert all(item.actual_sha256 == item.expected_sha256 for item in evidence)
    assert evaluation._validate_historical_hash_membership_v0(evidence) == tuple(
        sorted(evidence, key=lambda item: item.label)
    )
    with pytest.raises(ContractValidationError, match="membership"):
        evaluation._validate_historical_hash_membership_v0(evidence[:-1])
    with pytest.raises(ContractValidationError, match="membership"):
        evaluation._validate_historical_hash_membership_v0(evidence + (evidence[0],))
    for item in evidence:
        locked_path = _repository_root() / item.repository_path
        assert hashlib.sha256(locked_path.read_bytes()).hexdigest() == item.expected_sha256
        _canonical_roundtrip(item)


def test_frozen_core_blob_lock_is_recomputed_from_sealed_phase8_v2_artifact() -> None:
    evidence = evaluation.verify_frozen_core_blob_lock_v0(_repository_root())
    expected = (
        "cedcorebloblockv2_"
        "2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957"
    )
    assert evidence.matches is True
    assert evidence.expected_lock_id == expected
    assert evidence.actual_top_level_lock_id == expected
    assert evidence.actual_embedded_lock_id == expected
    assert evidence.recomputed_embedded_lock_id == expected
    assert evidence.actual_embedded_fingerprint == expected.removeprefix(
        "cedcorebloblockv2_"
    )
    assert evidence.recomputed_embedded_fingerprint == (
        evidence.actual_embedded_fingerprint
    )
    _canonical_roundtrip(evidence)
    tampered = evidence.model_dump(mode="json")
    tampered["actual_embedded_lock_id"] = "cedcorebloblockv2_tampered"
    with pytest.raises(Exception, match="match flag differs"):
        type(evidence).model_validate(tampered)


def test_exact_probe_mutation_failure_and_trace_design_lock() -> None:
    probes = (
        FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
        + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
    )
    actual_rows = tuple(
        (
            probe.probe_id,
            tuple(mutation.path for mutation in probe.literal_mutations),
            probe.expected_guard_id.value,
            probe.expected_primary_failure.value,
        )
        for probe in probes
    )
    assert actual_rows == _EXPECTED_PROBE_ROWS

    exact_payload = [
        {
            "probe_id": probe.probe_id,
            "literal_mutations": [
                mutation.model_dump(mode="json")
                for mutation in probe.literal_mutations
            ],
            "expected_guard_id": probe.expected_guard_id.value,
            "expected_primary_failure": probe.expected_primary_failure.value,
            "expected_guard_trace": [
                row.model_dump(mode="json") for row in probe.expected_guard_trace
            ],
        }
        for probe in probes
    ]
    assert hashlib.sha256(canonical_json(exact_payload).encode("utf-8")).hexdigest() == (
        _EXPECTED_PROBE_DESIGN_SHA256
    )


@pytest.mark.parametrize(
    "case",
    FROZEN_ACQUISITION_POSITIVE_CASES_V0,
    ids=lambda case: case.case_id,
)
def test_each_frozen_positive_case_individually(case) -> None:
    fixtures = evaluation.build_frozen_acquisition_fixtures_v0()
    result, executions = asyncio.run(
        evaluation._evaluate_positive_case(case, fixtures)
    )

    assert result.case_id == case.case_id
    assert result.case_fingerprint == case.case_fingerprint
    assert result.case_class is AcquisitionCaseClass.POSITIVE
    assert result.expected_outcome is AcquisitionAttemptOutcome.ACQUIRED
    assert result.literal_mutations == ()
    assert result.expected_guard_id is None
    assert result.expected_failure_code is None
    assert result.injected_negative_conditions == ()
    assert result.accepted_violations == ()
    assert len(executions) == case.attempt_count
    assert len(result.attempt_receipt_ids) == case.attempt_count
    assert result.expected_canned_invocations == case.expected_canned_invocations
    assert result.observed_canned_invocations == case.expected_canned_invocations
    assert all(
        (
            result.fixture_construction_valid,
            result.mutation_vector_exact,
            result.primary_result_exact,
            result.guard_trace_exact,
            result.invocation_count_exact,
            result.receipt_count_exact,
            result.complete_receipts,
            result.case_passed,
        )
    )
    assert result.actual_primary_results == (
        AcquisitionPrimaryResult(outcome=AcquisitionAttemptOutcome.ACQUIRED),
    ) * case.attempt_count

    expected_branches = tuple(
        sorted(
            f"acqv0-branch/{case.case_id}/{ordinal}"
            for ordinal in range(case.attempt_count)
        )
    )
    assert result.branch_ids == expected_branches
    for executed in executions:
        receipt = executed.result.attempt_receipt
        assert tuple(
            (row.guard_id, row.state) for row in receipt.guard_evaluations
        ) == tuple(
            (guard_id, AcquisitionGuardState.PASSED)
            for guard_id in ACQUISITION_GUARD_ORDER
        )
        assert executed.result.tripwire_counters.canned_transport_invocations == 1
        assert sum(
            getattr(executed.result.tripwire_counters, field_name)
            for field_name in (
                "external_network_attempts",
                "credential_access_attempts",
                "live_provider_calls",
                "provider_sdk_calls",
                "model_executions",
                "tool_calls",
                "canonical_application_calls",
            )
        ) == 0
    _canonical_roundtrip(result)


@pytest.mark.parametrize(
    "probe",
    FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
    + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0,
    ids=lambda probe: probe.probe_id,
)
def test_each_frozen_probe_individually(probe) -> None:
    fixtures = evaluation.build_frozen_acquisition_fixtures_v0()
    result, executions = asyncio.run(evaluation._evaluate_probe(probe, fixtures))

    assert len(executions) == 1
    executed = executions[0]
    receipt = executed.result.attempt_receipt
    expected_primary = AcquisitionPrimaryResult(
        outcome=AcquisitionAttemptOutcome.FAILED_CLOSED,
        primary_guard_id=probe.expected_guard_id,
        failure_code=probe.expected_primary_failure,
    )
    expected_trace = tuple(
        (row.guard_id, row.state) for row in probe.expected_guard_trace
    )
    failed_index = ACQUISITION_GUARD_ORDER.index(probe.expected_guard_id)
    independently_derived_trace = tuple(
        (
            guard_id,
            AcquisitionGuardState.PASSED
            if index < failed_index
            else AcquisitionGuardState.FAILED
            if index == failed_index
            else AcquisitionGuardState.NOT_REACHED,
        )
        for index, guard_id in enumerate(ACQUISITION_GUARD_ORDER)
    )

    assert result.case_id == probe.probe_id
    assert result.case_fingerprint == probe.probe_fingerprint
    assert result.case_class is probe.probe_class
    assert result.literal_mutations == probe.literal_mutations
    assert result.expected_mutation_vector == probe.mutation_vector
    assert result.measured_mutation_vector == probe.mutation_vector
    assert result.expected_guard_id is probe.expected_guard_id
    assert result.expected_failure_code is probe.expected_primary_failure
    assert result.actual_primary_results == (expected_primary,)
    assert receipt.primary_result == expected_primary
    assert expected_trace == independently_derived_trace
    assert tuple(
        (row.guard_id, row.state) for row in receipt.guard_evaluations
    ) == expected_trace
    assert result.injected_negative_conditions == tuple(
        sorted(mutation.path for mutation in probe.literal_mutations)
    )
    assert (
        executed.capability_snapshot.capability_snapshot_id
        == executed.request.capability_snapshot_id
        == receipt.capability_snapshot_id
    )
    if any(
        mutation.path.startswith("capability.")
        for mutation in probe.literal_mutations
    ):
        assert executed.capability_snapshot != fixtures.capability_snapshot
        assert (
            executed.capability_snapshot.capability_snapshot_id
            != fixtures.capability_snapshot.capability_snapshot_id
        )
    assert result.accepted_violations == ()
    assert result.expected_canned_invocations == probe.expected_canned_invocations
    assert result.observed_canned_invocations == probe.expected_canned_invocations
    assert len(result.attempt_receipt_ids) == probe.expected_attempt_receipts == 1
    assert all(
        (
            result.fixture_construction_valid,
            result.mutation_vector_exact,
            result.primary_result_exact,
            result.guard_trace_exact,
            result.invocation_count_exact,
            result.receipt_count_exact,
            result.complete_receipts,
            result.case_passed,
        )
    )
    _canonical_roundtrip(result)


def test_one_attempt_local_metrics_and_all_synthetic_threshold_gates() -> None:
    fixtures = evaluation.build_frozen_acquisition_fixtures_v0()
    case = FROZEN_ACQUISITION_POSITIVE_CASES_V0[0]
    result, executions = asyncio.run(
        evaluation._evaluate_positive_case(case, fixtures)
    )
    assert len(executions) == 1

    local_aggregate = evaluation._build_aggregate_receipt_v0(executions)
    historical = evaluation.verify_frozen_historical_hashes_v0(_repository_root())
    core_blob_lock = evaluation.verify_frozen_core_blob_lock_v0(_repository_root())
    local_metrics = evaluation._calculate_evaluation_metrics_v0(
        (result,),
        local_aggregate,
        historical,
        core_blob_lock,
    )
    assert local_aggregate.aggregate_receipt_id == (
        "szacqaggregate_c056e560753eaf919c752c2dbc76c9449ba7c494d3267ddc437c9dc885553388"
    )
    assert local_metrics.metrics_id == (
        "acqmetricsv0_c693cdf57fff8b4b4756324f66f46928fb77849d7e3bba1e8cf9ea993e69b1db"
    )
    assert (
        local_metrics.cases_total,
        local_metrics.positive_cases_total,
        local_metrics.positive_complete_case_results,
        local_metrics.positive_attempt_receipts,
        local_metrics.attempt_receipts_total,
        local_metrics.observed_canned_transport_invocations,
        local_metrics.mismatch_or_failure_count,
    ) == (1, 1, 1, 1, 1, 1, 7)
    assert not evaluation.supports_acquisition_metrics_v0(local_metrics)

    supported_payload = local_metrics.model_dump(
        mode="python", exclude={"metrics_id"}
    )
    supported_payload.update(
        {
            "cases_total": 50,
            "positive_cases_total": 6,
            "positive_complete_case_results": 6,
            "positive_attempt_receipts": 8,
            "orthogonal_probes_total": 37,
            "orthogonal_exact_primary_results": 37,
            "precedence_probes_total": 7,
            "precedence_exact_primary_results": 7,
            "attempt_receipts_total": 52,
            "observed_canned_transport_invocations": 32,
            "mismatch_or_failure_count": 0,
        }
    )
    supported = evaluation.AcquisitionEvaluationMetricsV0(**supported_payload)
    assert evaluation.supports_acquisition_metrics_v0(supported)

    threshold_values = FROZEN_ACQUISITION_THRESHOLDS_V0.model_dump(mode="python")
    for threshold_field, metric_field in _THRESHOLD_TO_METRIC_FIELDS:
        assert getattr(supported, metric_field) == threshold_values[threshold_field]
        rejected_payload = supported.model_dump(
            mode="python", exclude={"metrics_id"}
        )
        rejected_payload[metric_field] += 1
        rejected = evaluation.AcquisitionEvaluationMetricsV0(**rejected_payload)
        assert not evaluation.supports_acquisition_metrics_v0(rejected), metric_field

    provider_sdk_payload = supported.model_dump(
        mode="python", exclude={"metrics_id"}
    )
    provider_sdk_payload["provider_sdk_calls"] = 1
    provider_sdk_violation = evaluation.AcquisitionEvaluationMetricsV0(
        **provider_sdk_payload
    )
    assert not evaluation.supports_acquisition_metrics_v0(provider_sdk_violation)
    _canonical_roundtrip(local_aggregate)
    _canonical_roundtrip(local_metrics)
    _canonical_roundtrip(supported)


def test_case_result_rejects_flags_that_contradict_stored_evidence() -> None:
    fixtures = evaluation.build_frozen_acquisition_fixtures_v0()
    positive, _ = asyncio.run(
        evaluation._evaluate_positive_case(
            FROZEN_ACQUISITION_POSITIVE_CASES_V0[0],
            fixtures,
        )
    )
    positive_payload = positive.model_dump(mode="python")
    positive_payload.update(
        case_result_id=None,
        primary_result_exact=False,
        case_passed=False,
    )
    with pytest.raises(ValueError, match="case exactness flag"):
        evaluation.AcquisitionCaseResultV0.model_validate(positive_payload)

    probe, _ = asyncio.run(
        evaluation._evaluate_probe(
            FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0[0],
            fixtures,
        )
    )
    probe_payload = probe.model_dump(mode="python")
    probe_payload.update(
        case_result_id=None,
        mutation_vector_exact=False,
        case_passed=False,
    )
    with pytest.raises(ValueError, match="case exactness flag"):
        evaluation.AcquisitionCaseResultV0.model_validate(probe_payload)


def test_local_case_to_aggregate_cross_link_tampering_is_rejected() -> None:
    fixtures = evaluation.build_frozen_acquisition_fixtures_v0()
    result, executions = asyncio.run(
        evaluation._evaluate_positive_case(
            FROZEN_ACQUISITION_POSITIVE_CASES_V0[0],
            fixtures,
        )
    )
    assert len(executions) == 1
    aggregate = evaluation._build_aggregate_receipt_v0(executions)
    isolations = tuple(item.result.isolation_receipt for item in executions)
    retentions = tuple(item.result.retention_receipt for item in executions)
    evaluation._validate_case_result_receipt_links_v0(
        (result,), aggregate, isolations, retentions
    )

    attempt = result.attempt_evidence[0]
    detached_attempt = attempt.model_copy(
        update={"attempt_receipt_id": "szacqreceipt_" + "0" * 64}
    )
    detached_result = result.model_copy(
        update={"attempt_evidence": (detached_attempt,)}
    )
    with pytest.raises(ContractValidationError, match="ownership"):
        evaluation._validate_case_result_receipt_links_v0(
            (detached_result,), aggregate, isolations, retentions
        )

    with pytest.raises(ContractValidationError, match="side-evidence"):
        evaluation._validate_case_result_receipt_links_v0(
            (result,), aggregate, (), retentions
        )


def test_synthetic_replay_lock_serializer_is_canonical() -> None:
    replay_case_ids = (
        evaluation.FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0
        + evaluation.FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0
        + evaluation.FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0
    )
    replay_case_result_ids = tuple(
        f"synthetic-case-result-{index:02d}"
        for index in range(len(replay_case_ids))
    )
    replay_transport_attempt_ids = tuple(
        f"synthetic-transport-attempt-{index:02d}"
        for index in range(
            FROZEN_ACQUISITION_THRESHOLDS_V0.required_attempt_receipts_total
        )
    )
    trace_payload = {
        "execution_role": "REVERSE_REPLAY",
        "positive_order": list(evaluation.FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0),
        "orthogonal_order": list(
            evaluation.FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0
        ),
        "precedence_order": list(
            evaluation.FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0
        ),
        "ordered_case_ids": list(replay_case_ids),
        "ordered_case_result_ids": list(replay_case_result_ids),
        "ordered_transport_attempt_ids": list(replay_transport_attempt_ids),
    }
    synthetic = evaluation.AcquisitionReplayLockV0(
        authoritative_artifact_id="synthetic-acquisition-artifact-v0",
        replay_artifact_id="synthetic-acquisition-artifact-v0",
        replay_execution_id="synthetic-reverse-execution-v0",
        replay_execution_trace_sha256=hashlib.sha256(
            canonical_json(trace_payload).encode("utf-8")
        ).hexdigest(),
        authoritative_sha256="a" * 64,
        replay_sha256="a" * 64,
        authoritative_positive_order=evaluation.FROZEN_POSITIVE_CASE_ORDER_V0,
        authoritative_orthogonal_order=evaluation.FROZEN_ORTHOGONAL_PROBE_ORDER_V0,
        authoritative_precedence_order=evaluation.FROZEN_PRECEDENCE_PROBE_ORDER_V0,
        replay_positive_order=evaluation.FROZEN_REPLAY_POSITIVE_CASE_ORDER_V0,
        replay_orthogonal_order=evaluation.FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V0,
        replay_precedence_order=evaluation.FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V0,
        replay_ordered_case_ids=replay_case_ids,
        replay_ordered_case_result_ids=replay_case_result_ids,
        replay_ordered_transport_attempt_ids=replay_transport_attempt_ids,
    )
    rendered = evaluation.render_acquisition_replay_lock_v0(synthetic)
    assert rendered == canonical_json(synthetic.model_dump(mode="json")) + "\n"
    assert evaluation.replay_acquisition_replay_lock_v0(rendered) == synthetic
    assert evaluation.acquisition_replay_lock_sha256_v0(synthetic) == hashlib.sha256(
        rendered.encode("utf-8")
    ).hexdigest()
    with pytest.raises(ContractValidationError, match="not canonical"):
        evaluation.replay_acquisition_replay_lock_v0(rendered + "\n")


def test_same_object_cannot_fake_independent_replay_lock() -> None:
    synthetic_artifact = evaluation.AcquisitionExperimentArtifactV0.model_construct()
    with pytest.raises(ContractValidationError):
        evaluation.create_acquisition_replay_lock_v0(
            synthetic_artifact,
            synthetic_artifact,
        )


def test_write_once_primitive_is_confined_to_tmp_path(tmp_path: Path) -> None:
    destination = tmp_path / "synthetic-canonical-payload.json"
    payload = b'{"kind":"synthetic-pre-freeze-smoke"}\n'
    expected_digest = hashlib.sha256(payload).hexdigest()

    assert evaluation.write_once_canonical_bytes_v0(destination, payload) == (
        expected_digest
    )
    assert destination.read_bytes() == payload
    assert evaluation.write_once_canonical_bytes_v0(destination, payload) == (
        expected_digest
    )
    with pytest.raises(ContractValidationError, match="different bytes"):
        evaluation.write_once_canonical_bytes_v0(
            destination,
            b'{"kind":"different"}\n',
        )
    assert destination.read_bytes() == payload
    with pytest.raises(ContractValidationError, match="must not be empty"):
        evaluation.write_once_canonical_bytes_v0(tmp_path / "empty.json", b"")

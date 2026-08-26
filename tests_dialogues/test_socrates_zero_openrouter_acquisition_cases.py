"""Pre-result locks for the data-only OpenRouter adapter case design."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import canonical_json
from backend.dialogues.socrates_zero.openrouter_acquisition_cases import (
    FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0,
    FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0,
    FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0,
    FROZEN_OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_V0,
    FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0,
    FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0,
    FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0,
    FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0,
    FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0,
    FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0,
    FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0,
    FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0,
    MUTATION_VECTOR_FIELD_NAMES_V0,
    OPENROUTER_ADAPTER_GUARD_ORDER_V0,
    OPENROUTER_ADAPTER_BASELINE_PROJECTION_SHA256_V0,
    OPENROUTER_ADAPTER_CANDIDATE_ADAPTER_ID_V0,
    OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0,
    OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_ID_V0,
    OPENROUTER_ADAPTER_HARNESS_ID_V0,
    OPENROUTER_ADAPTER_ID_V0,
    OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_ID_V0,
    OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0,
    OPENROUTER_SELECTED_MODEL_V0,
    OPENROUTER_SELECTED_PROVIDER_V0,
    OPENROUTER_SELECTED_PROVIDER_DISPLAY_V0,
    ORTHOGONAL_PROBE_IDS_V0,
    POSITIVE_CASE_IDS_V0,
    PRECEDENCE_PROBE_IDS_V0,
    MutationState,
    OpenRouterAdapterCaseClass,
    OpenRouterAdapterCaseSetV0,
    OpenRouterAdapterFailureCode,
    OpenRouterAdapterGuardId,
    OpenRouterAdapterGuardStage,
    OpenRouterAdapterGuardState,
    OpenRouterAdapterLiteralMutationV0,
    OpenRouterAdapterMutationPathKind,
    OpenRouterAdapterThresholdsV0,
    frozen_openrouter_adapter_case_set_sha256_v0,
)


_EXPECTED_GUARDS = (
    "P01_REQUEST_INTEGRITY",
    "P02_SEMANTIC_INPUT_INTEGRITY",
    "P03_CONTROL_SNAPSHOT_INTEGRITY",
    "P04_RENDERER_VERSION",
    "P05_CANONICAL_BODY_INTEGRITY",
    "P06_ENTROPY_CREDENTIAL_FIREWALL",
    "P07_REQUESTED_IDENTITY",
    "P08_ROUTE_POLICY",
    "P09_FALLBACK_INTENT",
    "P10_RETRY_POLICY",
    "P11_ONE_SHOT_POLICY",
    "P12_STREAM_POLICY",
    "P13_TOOL_POLICY",
    "P14_TEMPERATURE",
    "P15_SEED",
    "P16_OUTPUT_TOKEN_CAP",
    "P17_INPUT_TOKEN_BOUND",
    "P18_PRICING_RECORD",
    "P19_COST_BOUND",
    "P20_ENDPOINT_POLICY",
    "P21_REDIRECT_POLICY",
    "P22_PROXY_POLICY",
    "P23_TIMEOUT_POLICY",
    "P24_CANNED_REGISTRATION",
    "A01_INVOCATION_COUNT",
    "A02_TRANSPORT_COMPLETION",
    "A03_WORKER_TERMINATION",
    "A04_LATE_MUTATION",
    "A05_RAW_RESPONSE_PRESENCE",
    "A06_RAW_RESPONSE_INTEGRITY",
    "A07_ENVELOPE_PARSE",
    "A08_ACTUAL_PROVIDER",
    "A09_ACTUAL_MODEL",
    "A10_ACTUAL_CONFIGURATION",
    "A11_FALLBACK_STATUS",
    "A12_RETRY_STATUS",
    "A13_STREAM_STATUS",
    "A14_TOOL_STATUS",
    "A15_USAGE_COMPLETENESS",
    "A16_USAGE_CONSISTENCY",
    "A17_TOKEN_BOUNDS",
    "A18_COST_LINKAGE",
    "A19_RETENTION_PRIVACY",
    "A20_FINAL_RECEIPT_INTEGRITY",
)

_EXPECTED_POSITIVES = (
    "oracqv0-s01-deterministic-body",
    "oracqv0-s02-sibling-byte-equality",
    "oracqv0-s03-exact-identity-config",
    "oracqv0-s04-complete-usage-raw",
    "oracqv0-s05-opaque-content-retained",
    "oracqv0-s06-synthetic-cost-mechanism",
    "oracqv0-s07-cancellation-clean-success",
)

_EXPECTED_ORTHOGONAL = (
    ("oracqv0-o01-invalid-semantic-input", "P02_SEMANTIC_INPUT_INTEGRITY", "INVALID_SEMANTIC_INPUT", 0),
    ("oracqv0-o02-renderer-version-mismatch", "P04_RENDERER_VERSION", "RENDERER_VERSION_MISMATCH", 0),
    ("oracqv0-o03-process-metadata-entropy", "P06_ENTROPY_CREDENTIAL_FIREWALL", "FORBIDDEN_ENTROPY", 0),
    ("oracqv0-o04-branch-id-entropy", "P06_ENTROPY_CREDENTIAL_FIREWALL", "FORBIDDEN_ENTROPY", 0),
    ("oracqv0-o05-noncanonical-serialization", "P05_CANONICAL_BODY_INTEGRITY", "NONCANONICAL_BODY", 0),
    ("oracqv0-o06-prepared-body-mutated", "P05_CANONICAL_BODY_INTEGRITY", "BODY_DIGEST_OR_LENGTH_MISMATCH", 0),
    ("oracqv0-o07-route-control-unknown", "P08_ROUTE_POLICY", "ROUTE_POLICY_UNPROVEN", 0),
    ("oracqv0-o08-fallback-intent-enabled", "P09_FALLBACK_INTENT", "FALLBACK_INTENT_NOT_DISABLED", 0),
    ("oracqv0-o09-stream-request-enabled", "P12_STREAM_POLICY", "STREAM_NOT_DISABLED", 0),
    ("oracqv0-o10-tool-request-present", "P13_TOOL_POLICY", "TOOLS_NOT_DISABLED", 0),
    ("oracqv0-o11-temperature-mismatch", "P14_TEMPERATURE", "TEMPERATURE_NOT_ZERO", 0),
    ("oracqv0-o12-seed-emitted", "P15_SEED", "SEED_NOT_UNSUPPORTED_OR_EMITTED", 0),
    ("oracqv0-o13-output-cap-missing", "P16_OUTPUT_TOKEN_CAP", "OUTPUT_TOKEN_CAP_INVALID", 0),
    ("oracqv0-o14-input-bound-unsafe", "P17_INPUT_TOKEN_BOUND", "INPUT_BOUND_UNPROVEN", 0),
    ("oracqv0-o15-pricing-record-missing", "P18_PRICING_RECORD", "PRICING_NOT_ESTABLISHED", 0),
    ("oracqv0-o16-pricing-model-mismatch", "P18_PRICING_RECORD", "PRICING_BINDING_MISMATCH", 0),
    ("oracqv0-o17-cost-overflow", "P19_COST_BOUND", "COST_OVERFLOW", 0),
    ("oracqv0-o18-endpoint-mismatch", "P20_ENDPOINT_POLICY", "ENDPOINT_MISMATCH", 0),
    ("oracqv0-o19-redirect-enabled", "P21_REDIRECT_POLICY", "REDIRECTS_NOT_DISABLED", 0),
    ("oracqv0-o20-proxy-unknown", "P22_PROXY_POLICY", "PROXY_INHERITANCE_NOT_DISABLED", 0),
    ("oracqv0-o21-timeout-policy-incomplete", "P23_TIMEOUT_POLICY", "TIMEOUT_POLICY_INCOMPLETE", 0),
    ("oracqv0-o22-canned-transport-unregistered", "P24_CANNED_REGISTRATION", "CANNED_TRANSPORT_UNREGISTERED", 0),
    ("oracqv0-o23-credential-header-leakage", "P06_ENTROPY_CREDENTIAL_FIREWALL", "CREDENTIAL_OR_HEADER_LEAKAGE", 0),
    ("oracqv0-o24-second-transport-invocation", "A01_INVOCATION_COUNT", "MULTIPLE_TRANSPORT_INVOCATIONS", 2),
    ("oracqv0-o25-clean-transport-timeout", "A02_TRANSPORT_COMPLETION", "TRANSPORT_TIMEOUT", 1),
    ("oracqv0-o26-worker-not-terminated-after-delivery", "A03_WORKER_TERMINATION", "WORKER_NOT_TERMINATED", 1),
    ("oracqv0-o27-late-mutation-after-delivery", "A04_LATE_MUTATION", "LATE_MUTATION_DETECTED", 1),
    ("oracqv0-o28-raw-missing", "A05_RAW_RESPONSE_PRESENCE", "MISSING_RAW_RESPONSE", 1),
    ("oracqv0-o29-raw-digest-mismatch", "A06_RAW_RESPONSE_INTEGRITY", "RAW_DIGEST_OR_LENGTH_MISMATCH", 1),
    ("oracqv0-o30-malformed-envelope", "A07_ENVELOPE_PARSE", "MALFORMED_RESPONSE_ENVELOPE", 1),
    ("oracqv0-o31-provider-mismatch", "A08_ACTUAL_PROVIDER", "ACTUAL_PROVIDER_MISMATCH", 1),
    ("oracqv0-o32-model-mismatch", "A09_ACTUAL_MODEL", "ACTUAL_MODEL_MISMATCH", 1),
    ("oracqv0-o33-actual-model-missing", "A09_ACTUAL_MODEL", "ACTUAL_MODEL_MISSING", 1),
    ("oracqv0-o34-configuration-mismatch", "A10_ACTUAL_CONFIGURATION", "ACTUAL_CONFIGURATION_MISMATCH", 1),
    ("oracqv0-o35-fallback-used", "A11_FALLBACK_STATUS", "FALLBACK_ACTIVATED", 1),
    ("oracqv0-o36-retry-count-nonzero", "A12_RETRY_STATUS", "RETRY_ACTIVATED", 1),
    ("oracqv0-o37-stream-response-metadata", "A13_STREAM_STATUS", "STREAMING_RESPONSE_DETECTED", 1),
    ("oracqv0-o38-tool-response-present", "A14_TOOL_STATUS", "TOOL_ACTIVATED", 1),
    ("oracqv0-o39-usage-missing", "A15_USAGE_COMPLETENESS", "USAGE_INCOMPLETE", 1),
    ("oracqv0-o40-usage-inconsistent", "A16_USAGE_CONSISTENCY", "USAGE_INCONSISTENT", 1),
    ("oracqv0-o41-false-zero-usage", "A15_USAGE_COMPLETENESS", "FALSE_ZERO_USAGE", 1),
    ("oracqv0-o42-reported-tokens-exceed-bound", "A17_TOKEN_BOUNDS", "REPORTED_USAGE_EXCEEDS_BOUND", 1),
    ("oracqv0-o43-cost-link-mismatch", "A18_COST_LINKAGE", "COST_LINK_MISMATCH", 1),
    ("oracqv0-o44-final-receipt-mismatch", "A20_FINAL_RECEIPT_INTEGRITY", "RECEIPT_MISMATCH", 1),
)

_EXPECTED_PRECEDENCE = (
    ("oracqv0-p01-invalid-request-plus-entropy", "P01_REQUEST_INTEGRITY", "INVALID_ADAPTER_REQUEST", 0),
    ("oracqv0-p02-noncanonical-plus-entropy", "P05_CANONICAL_BODY_INTEGRITY", "NONCANONICAL_BODY", 0),
    ("oracqv0-p03-route-unknown-plus-fallback-enabled", "P08_ROUTE_POLICY", "ROUTE_POLICY_UNPROVEN", 0),
    ("oracqv0-p04-fallback-plus-stream-plus-tools", "P09_FALLBACK_INTENT", "FALLBACK_INTENT_NOT_DISABLED", 0),
    ("oracqv0-p05-timeout-plus-worker-leak-plus-late-mutation", "A02_TRANSPORT_COMPLETION", "TRANSPORT_TIMEOUT", 1),
    ("oracqv0-p06-missing-raw-plus-malformed-plus-identity", "A05_RAW_RESPONSE_PRESENCE", "MISSING_RAW_RESPONSE", 1),
    ("oracqv0-p07-provider-plus-model-plus-config-plus-fallback", "A08_ACTUAL_PROVIDER", "ACTUAL_PROVIDER_MISMATCH", 1),
    ("oracqv0-p08-usage-inconsistent-plus-cost-link-plus-receipt", "A16_USAGE_CONSISTENCY", "USAGE_INCONSISTENT", 1),
)


def _all_cases():
    return (
        FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
        + FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
        + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
    )


def test_exact_guard_order_stages_and_taxonomy_are_frozen() -> None:
    assert tuple(item.value for item in OPENROUTER_ADAPTER_GUARD_ORDER_V0) == (
        _EXPECTED_GUARDS
    )
    assert tuple(step.order_index for step in FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0) == tuple(
        range(1, 45)
    )
    assert all(
        step.stage is OpenRouterAdapterGuardStage.PRE_DISPATCH
        for step in FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0[:24]
    )
    assert all(
        step.stage is OpenRouterAdapterGuardStage.POST_RESPONSE
        for step in FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0[24:]
    )
    assert FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0.precedence_model == (
        FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0
    )
    taxonomy = FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0
    assert {item.code for item in taxonomy.entries} == set(OpenRouterAdapterFailureCode)
    by_code = {item.code: item for item in taxonomy.entries}
    for step in FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0:
        assert all(by_code[code].guard_id is step.guard_id for code in step.failure_codes)
        assert all(by_code[code].stage is step.stage for code in step.failure_codes)


def test_exact_case_membership_order_counts_and_activity_totals() -> None:
    assert POSITIVE_CASE_IDS_V0 == _EXPECTED_POSITIVES
    assert ORTHOGONAL_PROBE_IDS_V0 == tuple(item[0] for item in _EXPECTED_ORTHOGONAL)
    assert PRECEDENCE_PROBE_IDS_V0 == tuple(item[0] for item in _EXPECTED_PRECEDENCE)
    assert (len(POSITIVE_CASE_IDS_V0), len(ORTHOGONAL_PROBE_IDS_V0), len(PRECEDENCE_PROBE_IDS_V0)) == (
        7,
        44,
        8,
    )
    case_set = FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0
    assert (case_set.total_case_count, case_set.total_attempt_receipts) == (59, 60)
    assert case_set.total_canned_transport_invocations == 34
    assert sum(item.attempt_count for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0) == 8
    assert sum(item.expected_canned_invocations for item in _all_cases()) == 34


def test_exact_semantic_ids_case_sha_and_all_fingerprints_are_locked() -> None:
    assert OPENROUTER_ADAPTER_ID_V0 == "socrateszero-openrouter-acquisition-adapter/v0"
    assert OPENROUTER_ADAPTER_HARNESS_ID_V0 == "socrateszero-openrouter-acquisition-harness/v0"
    assert OPENROUTER_SELECTED_PROVIDER_V0 == "openrouter"
    assert OPENROUTER_SELECTED_PROVIDER_DISPLAY_V0 == "OpenRouter"
    assert OPENROUTER_SELECTED_MODEL_V0 == "openai/gpt-4.1-mini"
    assert FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0.validation_order_id == (
        "oracqvalidationv0_137f7049f806222f1901f5e1790535f41b8d06558cb1ebb41aba4643f3782cf3"
    )
    assert FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0.failure_taxonomy_id == (
        "oracqtaxonomyv0_5c0dc22b61545a3b6ea18c55d5b951c928264de794957678e0bd3e35874ef7ec"
    )
    assert FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.thresholds_id == (
        "oracqthresholdsv0_c2381ba4b0e844b97a9309c9b8f6204d6e40d52e77a1a10d03d1f8d152bce7d1"
    )
    assert FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.case_set_id == (
        "oracqcasesetv0_0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373"
    )
    assert frozen_openrouter_adapter_case_set_sha256_v0() == (
        "0ae905d5a5cd212e3576337338dfc2e55e99cf75ce66e87c0861c85e3bcd8373"
    )
    pairs = tuple(
        (
            getattr(item, "case_id", None) or item.probe_id,
            getattr(item, "case_fingerprint", None) or item.probe_fingerprint,
        )
        for item in _all_cases()
    )
    assert len({fingerprint for _, fingerprint in pairs}) == 59
    assert hashlib.sha256(canonical_json(pairs).encode("utf-8")).hexdigest() == (
        "7c0e659a4274aaf9497125cb7deeaf9e63010a7b1c76c19b14244a3d4910e155"
    )
    for item in _all_cases():
        field = "case_fingerprint" if hasattr(item, "case_id") else "probe_fingerprint"
        payload = item.model_dump(mode="json", exclude={field})
        assert getattr(item, field) == hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()


def test_positive_cases_freeze_exact_attempts_and_evidence_categories() -> None:
    attempts = tuple(item.attempt_count for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0)
    assert attempts == (1, 2, 1, 1, 1, 1, 1)
    assert tuple(
        item.evaluator_input_attempt_count
        for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
    ) == attempts
    assert tuple(
        item.expected_attempt_receipts
        for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
    ) == attempts
    assert all(item.expected_canned_invocations == item.attempt_count for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0)
    assert all(
        item.expectation_role == OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0
        and item.candidate_proof is False
        for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
    )
    assertions = {
        assertion
        for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
        for assertion in item.required_assertions
    }
    assert {
        "body_bytes_exact",
        "body_bytes_equal",
        "provider_match",
        "model_match",
        "configuration_match",
        "usage_complete",
        "raw_bytes_recoverable",
        "opaque_content_retained",
        "pricing_status_synthetic_only",
        "workers_terminated",
    } <= assertions


def test_fixture_registry_and_candidate_manifest_links_are_frozen() -> None:
    case_set = FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0
    assert case_set.candidate_adapter_id == OPENROUTER_ADAPTER_CANDIDATE_ADAPTER_ID_V0
    assert case_set.fixture_manifest_id == OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0
    assert case_set.baseline_projection_sha256 == (
        OPENROUTER_ADAPTER_BASELINE_PROJECTION_SHA256_V0
    )
    assert case_set.fixture_ref_registry_id == (
        OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_ID_V0
    )
    assert OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_ID_V0 == (
        "oracqfixtures_798b6da5cc85d1bdbd5b801a584c4504a75bd3637b34bc73918fb81a76cbcf75"
    )
    assert OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0 == (
        "szorfixture_8d2c355b7f8a3297be9c5e9de344c9bff03c2afbf4579bf93eaa136572598b77"
    )
    assert OPENROUTER_ADAPTER_BASELINE_PROJECTION_SHA256_V0 == (
        "63f28955c510351e8b5ef2606f116eb6ab22ab85177982ef0dcda000eacf3f22"
    )
    assert case_set.positive_case_semantics == (
        OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0
    )
    assert case_set.known_unresolved_mandatory_guards == (
        FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0
    )
    assert tuple(
        guard.value for guard in case_set.known_unresolved_mandatory_guards
    ) == (
        "P08_ROUTE_POLICY",
        "P09_FALLBACK_INTENT",
        "P17_INPUT_TOKEN_BOUND",
        "P18_PRICING_RECORD",
        "P19_COST_BOUND",
    )
    refs = {item.ref_name: item for item in FROZEN_OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_V0}
    assert len(refs) == 10
    assert all(
        item.fixture_manifest_id == OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0
        for item in refs.values()
    )
    referenced = {
        ref
        for case in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
        for ref in case.fixture_refs
    }
    assert referenced == set(refs)
    assert refs["synthetic-pricing"].availability.value == "EXPECTATION_ONLY"
    assert refs["cooperative-envelope"].availability.value == "EXPECTATION_ONLY"


def test_orthogonal_primary_results_stages_and_invocations_are_exact() -> None:
    actual = tuple(
        (
            item.probe_id,
            item.expected_guard_id.value,
            item.expected_primary_failure.value,
            item.expected_canned_invocations,
        )
        for item in FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
    )
    assert actual == _EXPECTED_ORTHOGONAL
    assert sum(item.stage is OpenRouterAdapterGuardStage.PRE_DISPATCH for item in FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0) == 23
    assert sum(item.stage is OpenRouterAdapterGuardStage.POST_RESPONSE for item in FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0) == 21


def test_precedence_primary_results_and_dependency_aware_timeout_are_exact() -> None:
    actual = tuple(
        (
            item.probe_id,
            item.expected_guard_id.value,
            item.expected_primary_failure.value,
            item.expected_canned_invocations,
        )
        for item in FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
    )
    assert actual == _EXPECTED_PRECEDENCE
    timeout = FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0[4]
    assert tuple(item.path for item in timeout.literal_mutations) == (
        "envelope.transport_status",
        "invocation_record.worker_terminated",
        "directive.attempt_late_mutation",
    )
    assert timeout.expected_guard_id is OpenRouterAdapterGuardId.A02_TRANSPORT_COMPLETION
    worker = FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0[25]
    assert worker.expected_guard_id is OpenRouterAdapterGuardId.A03_WORKER_TERMINATION


def test_every_probe_has_exact_first_guard_trace_and_measurable_vector() -> None:
    probes = (
        FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
        + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
    )
    for probe in probes:
        failed_at = OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(probe.expected_guard_id)
        assert tuple(item.state for item in probe.expected_guard_trace) == (
            (OpenRouterAdapterGuardState.PASSED,) * failed_at
            + (OpenRouterAdapterGuardState.FAILED,)
            + (OpenRouterAdapterGuardState.NOT_REACHED,)
            * (44 - failed_at - 1)
        )
        intended = tuple(
            name
            for name in MUTATION_VECTOR_FIELD_NAMES_V0
            if getattr(probe.mutation_vector, name) is MutationState.INTENTIONALLY_CHANGED
        )
        assert len(intended) == len(probe.literal_mutations)
        assert len({item.path for item in probe.literal_mutations}) == len(probe.literal_mutations)
        assert all(item.before_json != item.after_json for item in probe.literal_mutations)
        if probe.probe_class is OpenRouterAdapterCaseClass.ORTHOGONAL:
            assert len(probe.literal_mutations) == 1
            assert probe.independently_probeable is True
        else:
            assert len(probe.literal_mutations) >= 2
            assert probe.independently_probeable is False


def test_all_probe_paths_and_baselines_resolve_exact_frozen_registry() -> None:
    specs = {
        item.path: item
        for item in FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
    }
    assert len(specs) == 44
    assert OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_ID_V0 == (
        "oracqpaths_b861832d079de42991c063394a9c6aae7a7804d3cec83586188a330bddcb88cd"
    )
    probes = (
        FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
        + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
    )
    used_paths = {
        mutation.path
        for probe in probes
        for mutation in probe.literal_mutations
    }
    assert used_paths == set(specs)
    for probe in probes:
        assert probe.evaluator_input_attempt_count == 1
        for mutation in probe.literal_mutations:
            spec = specs[mutation.path]
            assert mutation.before_json == spec.baseline_json
            assert (
                getattr(probe.mutation_vector, spec.mutation_vector_field)
                is MutationState.INTENTIONALLY_CHANGED
            )

    committed_paths = {
        item.path
        for item in specs.values()
        if item.path_kind is OpenRouterAdapterMutationPathKind.COMMITTED_SURFACE
    }
    assert {
        "route_policy.upstream_route_state",
        "route_policy.application_fallback_allowed",
        "route_policy.adapter_fallback_allowed",
        "prepared_body.canonical_body_json",
        "invocation_record.worker_terminated",
        "directive.attempt_late_mutation",
        "raw_response.reported_sha256",
        "identity_evidence.actual_router_id",
        "envelope.adapter_retry_count",
        "usage_evidence.total_tokens",
        "attempt_receipt.usage_evidence.cost_bound_id",
        "attempt_receipt.attempt_receipt_id",
    } <= committed_paths
    legacy_aliases = {
        "renderer.version",
        "prepared.body_bytes",
        "route_policy.status",
        "route_policy.fallback_requested_disabled",
        "envelope.worker_terminated",
        "envelope.actual_provider",
        "envelope.retry_count",
        "response_receipt.receipt_id",
    }
    assert not legacy_aliases.intersection(used_paths)

    with pytest.raises(ValidationError, match="not in the frozen registry"):
        OpenRouterAdapterLiteralMutationV0(
            path="legacy.unknown",
            before_json="null",
            after_json="true",
        )
    with pytest.raises(ValidationError, match="baseline differs"):
        OpenRouterAdapterLiteralMutationV0(
            path="prepared_body.tools",
            before_json="null",
            after_json='[{"name":"forbidden-tool"}]',
        )


def test_strict_thresholds_distinguish_expected_injections_from_acceptance() -> None:
    values = FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.model_dump(mode="json")
    assert values["cases_total"] == 59
    assert values["required_positive_attempt_receipts"] == 8
    assert values["required_attempt_receipts_total"] == 60
    assert values["required_canned_transport_invocations"] == 34
    assert values["pricing_status"] == "SYNTHETIC_ONLY"
    assert values["live_model_pricing_status"] == "NOT_ESTABLISHED"
    assert values["live_pilot_readiness"] == "REQUIRES_REAUTHORIZATION"
    zero_fields = {
        name: value
        for name, value in values.items()
        if name.startswith(("maximum_", "required_external_", "required_credential_", "required_provider_", "required_model_", "required_tool_", "required_canonical_", "required_source_", "required_sibling_", "required_production_", "required_historical_", "required_core_"))
    }
    assert zero_fields
    assert all(value == 0 for value in zero_fields.values())


def test_content_addressed_contracts_reject_tampered_ids() -> None:
    thresholds = FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.model_dump(mode="python")
    thresholds["thresholds_id"] = "oracqthresholdsv0_" + "0" * 64
    with pytest.raises(ValidationError, match="thresholds ID mismatch"):
        OpenRouterAdapterThresholdsV0.model_validate(thresholds)

    case_set = FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.model_dump(mode="python")
    case_set["case_set_id"] = "oracqcasesetv0_" + "0" * 64
    with pytest.raises(ValidationError, match="case-set ID mismatch"):
        OpenRouterAdapterCaseSetV0.model_validate(case_set)


def test_expected_labels_are_evaluator_side_and_cases_module_is_data_only() -> None:
    root = Path(__file__).resolve().parents[1]
    source_path = (
        root
        / "backend"
        / "dialogues"
        / "socrates_zero"
        / "openrouter_acquisition_cases.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert imports <= {
        "__future__",
        "hashlib",
        "json",
        "enum",
        "typing",
        "pydantic",
        "contracts",
    }
    forbidden_source = (
        "openrouter_provider",
        "acquisition_evaluation",
        "aiohttp",
        "urllib",
        "socket",
        "os.getenv",
        "os.environ",
        "Authorization: Bearer",
        "sk-or-",
    )
    assert all(token not in source for token in forbidden_source)

    runtime_dir = source_path.parent
    for path in runtime_dir.glob("*.py"):
        if path.name in {
            "openrouter_acquisition_cases.py",
            "openrouter_acquisition_evaluation.py",
        }:
            continue
        assert "openrouter_acquisition_cases" not in path.read_text(encoding="utf-8")

    for probe in (
        FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
        + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
    ):
        mutation_payload = canonical_json(
            [item.model_dump(mode="json") for item in probe.literal_mutations]
        )
        assert probe.probe_id not in mutation_payload
        assert probe.expected_guard_id.value not in mutation_payload
        assert probe.expected_primary_failure.value not in mutation_payload

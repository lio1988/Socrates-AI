from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.openrouter_acquisition_cases import (
    FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0,
    FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0,
    FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0,
    FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0,
    OpenRouterAdapterFailureCode,
    OpenRouterAdapterGuardId,
    OpenRouterAdapterGuardState,
)
from backend.dialogues.socrates_zero.openrouter_acquisition_evaluation import (
    FROZEN_CORE_BLOB_LOCK_SOURCE_PATH_V2,
    FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_ID_V0,
    FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0,
    OpenRouterEvaluationMetricsV0,
    OpenRouterEvaluationArtifactV0,
    OpenRouterHistoricalHashEvidenceV0,
    OpenRouterTripwireCountersV0,
    OpenRouterMutationScope,
    OpenRouterScopedMutationEvidenceV0,
    OpenRouterScopedPathSnapshotV0,
    ProbeConstructionState,
    build_openrouter_candidate_evidence_v0,
    evaluate_openrouter_adapter_case_v0,
    verify_core_blob_lock_v0,
    verify_historical_hashes_v0,
    _candidate_fixture,
    _apply_case_mutation,
    _first_projection_failure,
    _guard_predicate_failure,
    _metrics,
    _assert_frozen_scoped_mutation_accounting_v0,
    _build_authoritative_artifact_under_scoped_guard_v0,
    capture_openrouter_scoped_path_snapshot_v0,
    compare_openrouter_scoped_path_snapshots_v0,
)
from backend.dialogues.socrates_zero.openrouter_acquisition_contracts import (
    OPENROUTER_MAX_OUTPUT_TOKENS,
    OPENROUTER_MODEL_ID,
)


def _orthogonal(number: int):
    return FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0[number - 1]


def _precedence(number: int):
    return FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0[number - 1]


_TEST_SCOPED_PATH_INVENTORY = (
    ("SOURCE", ("source.txt",)),
    ("SIBLING", ("sibling.txt",)),
    ("PRODUCTION", ("production.txt",)),
)


def _write_scoped_inventory(root, inventory, *, omitted=()) -> None:
    omitted_paths = set(omitted)
    for _, paths in inventory:
        for relative_path in paths:
            if relative_path in omitted_paths:
                continue
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((relative_path + "\n").encode("utf-8"))


def _fully_resolved_projection() -> dict[str, object]:
    _, evidence_projection = _candidate_fixture()
    projection = {
        path: value_and_source[0]
        for path, value_and_source in evidence_projection.items()
    }
    projection["route_policy.upstream_route_state"] = "PROVEN"
    projection["route_policy.provider_side_fallback_state"] = "PROVEN"
    projection[
        "evaluator_derived.supported_upstream_fallback_disable_field_emitted"
    ] = True
    payload = projection["token_policy.payload_input_token_upper_bound"]
    output_cap = projection["token_policy.max_output_tokens"]
    assert type(payload) is int
    assert type(output_cap) is int
    projection["token_policy.provider_input_token_bound_state"] = (
        "CONSERVATIVE_UPPER_BOUND"
    )
    projection["token_policy.provider_framing_overhead_tokens"] = 0
    projection[
        "token_policy.authoritative_provider_input_token_upper_bound"
    ] = payload
    projection["token_policy.authoritative_total_token_upper_bound"] = (
        payload + output_cap
    )
    projection["pricing_record.pricing_state"] = "SYNTHETIC_ONLY"
    projection["pricing_record.input_microusd_per_million_tokens"] = 1
    projection["pricing_record.output_microusd_per_million_tokens"] = 2
    projection["pricing_record.fixed_non_token_microusd"] = 3
    projection["pricing_record.authority_reference"] = "synthetic-test-only"
    projection["pricing_record.source_name"] = "synthetic-test-only"
    projection["pricing_record.source_version"] = "synthetic-pricing/v0"
    projection["pricing_record.effective_version"] = "synthetic-effective/v0"
    projection["pricing_record.provenance_sha256"] = hashlib.sha256(
        b"socrateszero-openrouter-synthetic-pricing/v0"
    ).hexdigest()
    projection["pricing_record.unknown_line_items"] = []
    projection["cost_bound.cost_state"] = "SYNTHETIC_ONLY"
    projection["cost_bound.unknown_line_items"] = []
    projection["cost_bound.maximum_input_cost_microusd"] = 1
    projection["cost_bound.maximum_output_cost_microusd"] = 1
    projection["cost_bound.maximum_fixed_cost_microusd"] = 3
    projection["cost_bound.maximum_total_cost_microusd"] = 5
    projection["attempt_receipt.usage_evidence.cost_bound_id"] = projection[
        "capability_snapshot.cost_bound.cost_bound_id"
    ]
    return projection


def test_positive_candidate_fails_closed_at_first_unresolved_route_guard() -> None:
    result = evaluate_openrouter_adapter_case_v0(
        FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0[0]
    )

    assert result.actual_guard_id is OpenRouterAdapterGuardId.P08_ROUTE_POLICY
    assert (
        result.actual_primary_failure
        is OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN
    )
    assert result.observed_canned_invocations == 0
    assert result.attempt_receipts[0].canned_transport_invocations == 0
    assert result.actual_guard_trace[6].state is OpenRouterAdapterGuardState.PASSED
    assert result.actual_guard_trace[7].state is OpenRouterAdapterGuardState.FAILED
    assert result.actual_guard_trace[8].state is OpenRouterAdapterGuardState.NOT_REACHED
    assert result.case_passed is False


def test_candidate_evidence_uses_actual_renderer_and_frozen_acquisition_prompt() -> None:
    evidence = build_openrouter_candidate_evidence_v0()
    body = evidence.canonical_body_json.encode("utf-8")

    assert '"model":"openai/gpt-4.1-mini"' in evidence.canonical_body_json
    assert "Ask one concise opening Socratic question without answering" in evidence.canonical_body_json
    assert "Is knowledge merely justified true belief?" in evidence.canonical_body_json
    assert evidence.model_id == OPENROUTER_MODEL_ID
    assert evidence.prepared_body_byte_length == len(body)
    assert evidence.prepared_body_sha256 == hashlib.sha256(body).hexdigest()
    assert evidence.payload_input_token_upper_bound == len(body)
    assert evidence.payload_only_total_token_upper_bound == len(body) + OPENROUTER_MAX_OUTPUT_TOKENS
    assert evidence.authoritative_provider_input_token_upper_bound is None
    assert evidence.authoritative_total_token_upper_bound is None
    assert evidence.route_state.value == "NOT_ESTABLISHED"
    assert evidence.provider_side_fallback_state.value == "NOT_ESTABLISHED"
    assert evidence.pricing_state.value == "NOT_ESTABLISHED"
    assert evidence.actual_canned_transport_invocations == 0
    assert evidence.actual_attempt_receipt_id is None
    assert evidence.actual_response_receipt is None
    summary = evidence.reference_receipt_summary
    assert summary.reference_canned_fixture_only is True
    assert summary.summary_id == evidence.reference_receipt_summary_id
    assert summary.raw_response_sha256 == summary.identity_source_raw_response_sha256
    assert summary.raw_response_sha256 == summary.usage_source_raw_response_sha256
    assert summary.raw_response_byte_length > 0
    assert summary.actual_router_id == evidence.provider_id
    assert summary.actual_model_id == evidence.model_id
    assert summary.finish_reason.value == "stop"
    assert summary.usage_completeness.value == "COMPLETE"
    assert summary.usage_source.value == "PROVIDER_REPORTED"
    assert summary.total_tokens == summary.input_tokens + summary.output_tokens
    assert summary.pricing_state.value == "NOT_ESTABLISHED"
    assert summary.pricing_source_name is None
    assert summary.maximum_total_cost_microusd is None
    assert summary.credential_material_retained is False
    assert summary.sensitive_headers_retained is False


@pytest.mark.parametrize(
    ("probe_number", "guard", "failure"),
    (
        (1, OpenRouterAdapterGuardId.P02_SEMANTIC_INPUT_INTEGRITY, OpenRouterAdapterFailureCode.INVALID_SEMANTIC_INPUT),
        (2, OpenRouterAdapterGuardId.P04_RENDERER_VERSION, OpenRouterAdapterFailureCode.RENDERER_VERSION_MISMATCH),
        (3, OpenRouterAdapterGuardId.P06_ENTROPY_CREDENTIAL_FIREWALL, OpenRouterAdapterFailureCode.FORBIDDEN_ENTROPY),
        (4, OpenRouterAdapterGuardId.P06_ENTROPY_CREDENTIAL_FIREWALL, OpenRouterAdapterFailureCode.FORBIDDEN_ENTROPY),
        (5, OpenRouterAdapterGuardId.P05_CANONICAL_BODY_INTEGRITY, OpenRouterAdapterFailureCode.NONCANONICAL_BODY),
        (6, OpenRouterAdapterGuardId.P05_CANONICAL_BODY_INTEGRITY, OpenRouterAdapterFailureCode.BODY_DIGEST_OR_LENGTH_MISMATCH),
        (7, OpenRouterAdapterGuardId.P08_ROUTE_POLICY, OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN),
        (23, OpenRouterAdapterGuardId.P06_ENTROPY_CREDENTIAL_FIREWALL, OpenRouterAdapterFailureCode.CREDENTIAL_OR_HEADER_LEAKAGE),
    ),
)
def test_earlier_or_equal_mutations_win_before_route_baseline(
    probe_number: int,
    guard: OpenRouterAdapterGuardId,
    failure: OpenRouterAdapterFailureCode,
) -> None:
    result = evaluate_openrouter_adapter_case_v0(_orthogonal(probe_number))

    assert result.actual_guard_id is guard
    assert result.actual_primary_failure is failure
    assert result.primary_result_exact is True
    assert result.guard_trace_exact is True


@pytest.mark.parametrize("probe_number", tuple(range(8, 23)) + tuple(range(24, 45)))
def test_later_orthogonal_mutations_are_masked_by_route_guard(
    probe_number: int,
) -> None:
    result = evaluate_openrouter_adapter_case_v0(_orthogonal(probe_number))

    assert result.actual_guard_id is OpenRouterAdapterGuardId.P08_ROUTE_POLICY
    assert (
        result.actual_primary_failure
        is OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN
    )
    assert result.observed_canned_invocations == 0


@pytest.mark.parametrize(
    ("probe_number", "guard"),
    (
        (1, OpenRouterAdapterGuardId.P01_REQUEST_INTEGRITY),
        (2, OpenRouterAdapterGuardId.P05_CANONICAL_BODY_INTEGRITY),
        (3, OpenRouterAdapterGuardId.P08_ROUTE_POLICY),
    ),
)
def test_early_precedence_mutations_obey_first_guard_wins(
    probe_number: int,
    guard: OpenRouterAdapterGuardId,
) -> None:
    result = evaluate_openrouter_adapter_case_v0(_precedence(probe_number))

    assert result.actual_guard_id is guard
    assert result.primary_result_exact is True


@pytest.mark.parametrize("probe_number", (4, 5, 6, 7, 8))
def test_later_precedence_expectations_are_masked_by_route_guard(
    probe_number: int,
) -> None:
    result = evaluate_openrouter_adapter_case_v0(_precedence(probe_number))

    assert result.actual_guard_id is OpenRouterAdapterGuardId.P08_ROUTE_POLICY
    assert result.primary_result_exact is False
    assert result.observed_canned_invocations == 0


def test_expected_labels_are_comparison_only_not_decision_inputs() -> None:
    probe = _orthogonal(1)
    relabelled = probe.model_copy(
        update={
            "expected_guard_id": OpenRouterAdapterGuardId.A20_FINAL_RECEIPT_INTEGRITY,
            "expected_primary_failure": OpenRouterAdapterFailureCode.RECEIPT_MISMATCH,
        }
    )

    result = evaluate_openrouter_adapter_case_v0(relabelled)

    assert result.actual_guard_id is OpenRouterAdapterGuardId.P02_SEMANTIC_INPUT_INTEGRITY
    assert result.actual_primary_failure is OpenRouterAdapterFailureCode.INVALID_SEMANTIC_INPUT
    assert result.primary_result_exact is False


def test_expected_receipt_label_cannot_change_actual_attempt_topology() -> None:
    probe = _orthogonal(1).model_copy(
        update={"expected_attempt_receipts": 2}
    )

    result = evaluate_openrouter_adapter_case_v0(probe)

    assert probe.evaluator_input_attempt_count == 1
    assert len(result.attempt_receipts) == 1
    assert result.evaluator_input_attempt_count == 1
    assert result.expected_attempt_receipts == 2
    assert result.attempt_count_exact is False


def test_expected_invocation_label_cannot_change_actual_dispatch_evidence() -> None:
    case = FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0[0]
    relabelled = case.model_copy(update={"expected_canned_invocations": 0})

    original = evaluate_openrouter_adapter_case_v0(case)
    result = evaluate_openrouter_adapter_case_v0(relabelled)

    assert original.observed_canned_invocations == 0
    assert result.observed_canned_invocations == 0
    assert original.actual_guard_id is result.actual_guard_id
    assert original.actual_primary_failure is result.actual_primary_failure
    assert original.invocation_count_exact is False
    assert result.invocation_count_exact is True


def test_declared_after_value_is_applied_before_guard_predicates() -> None:
    probe = _orthogonal(1)
    neutral_mutation = probe.literal_mutations[0].model_copy(
        update={"after_json": "null"}
    )
    neutral_probe = probe.model_copy(
        update={"literal_mutations": (neutral_mutation,)}
    )

    result = evaluate_openrouter_adapter_case_v0(neutral_probe)

    assert result.actual_guard_id is OpenRouterAdapterGuardId.P08_ROUTE_POLICY
    assert result.actual_primary_failure is OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN
    assert result.primary_result_exact is False


def test_every_frozen_guard_has_a_concrete_projection_predicate() -> None:
    _, evidence_projection = _candidate_fixture()
    projection = {
        path: value_and_source[0]
        for path, value_and_source in evidence_projection.items()
    }

    outcomes = {
        guard: _guard_predicate_failure(guard, projection)
        for guard in OpenRouterAdapterGuardId
    }

    assert len(outcomes) == 44
    assert outcomes[OpenRouterAdapterGuardId.P08_ROUTE_POLICY] is OpenRouterAdapterFailureCode.ROUTE_POLICY_UNPROVEN
    assert outcomes[OpenRouterAdapterGuardId.P09_FALLBACK_INTENT] is OpenRouterAdapterFailureCode.FALLBACK_INTENT_NOT_DISABLED
    assert outcomes[OpenRouterAdapterGuardId.P17_INPUT_TOKEN_BOUND] is OpenRouterAdapterFailureCode.INPUT_BOUND_UNPROVEN
    assert outcomes[OpenRouterAdapterGuardId.P18_PRICING_RECORD] is OpenRouterAdapterFailureCode.PRICING_NOT_ESTABLISHED
    assert outcomes[OpenRouterAdapterGuardId.P19_COST_BOUND] is OpenRouterAdapterFailureCode.COST_BOUND_INVALID


def test_cost_dependency_is_an_independent_unresolved_mandatory_guard() -> None:
    projection = _fully_resolved_projection()
    projection["cost_bound.cost_state"] = "NOT_ESTABLISHED"

    guard, failure = _first_projection_failure(projection)

    assert guard is OpenRouterAdapterGuardId.P19_COST_BOUND
    assert failure is OpenRouterAdapterFailureCode.COST_BOUND_INVALID


def test_state_labels_alone_cannot_satisfy_token_pricing_or_cost_guards() -> None:
    _, evidence_projection = _candidate_fixture()
    projection = {
        path: value_and_source[0]
        for path, value_and_source in evidence_projection.items()
    }
    projection["token_policy.provider_input_token_bound_state"] = (
        "CONSERVATIVE_UPPER_BOUND"
    )
    projection["pricing_record.pricing_state"] = "SYNTHETIC_ONLY"
    projection["cost_bound.cost_state"] = "SYNTHETIC_ONLY"

    assert (
        _guard_predicate_failure(
            OpenRouterAdapterGuardId.P17_INPUT_TOKEN_BOUND, projection
        )
        is OpenRouterAdapterFailureCode.INPUT_BOUND_UNPROVEN
    )
    assert (
        _guard_predicate_failure(
            OpenRouterAdapterGuardId.P18_PRICING_RECORD, projection
        )
        is OpenRouterAdapterFailureCode.PRICING_NOT_ESTABLISHED
    )
    assert (
        _guard_predicate_failure(OpenRouterAdapterGuardId.P19_COST_BOUND, projection)
        is OpenRouterAdapterFailureCode.COST_BOUND_INVALID
    )


def test_every_guard_is_reachable_after_explicitly_resolving_candidate_blockers() -> None:
    projection = _fully_resolved_projection()

    assert all(
        _guard_predicate_failure(guard, projection) is None
        for guard in OpenRouterAdapterGuardId
    )


@pytest.mark.parametrize("probe_number", tuple(range(1, 45)))
def test_each_orthogonal_target_is_independently_reachable(
    probe_number: int,
) -> None:
    probe = _orthogonal(probe_number)
    projection = _fully_resolved_projection()
    for mutation in probe.literal_mutations:
        _apply_case_mutation(projection, mutation.path, mutation.after_json)

    guard, failure = _first_projection_failure(projection)

    assert guard is probe.expected_guard_id
    assert failure is probe.expected_primary_failure


def test_probe_construction_records_tampered_renderer_baseline_drift() -> None:
    probe = _orthogonal(2)
    mutation = probe.literal_mutations[0].model_copy(
        update={
            "before_json": (
                '"socrateszero-openrouter-acquisition-request-renderer/v0"'
            )
        }
    )
    result = evaluate_openrouter_adapter_case_v0(
        probe.model_copy(update={"literal_mutations": (mutation,)})
    )
    evidence = result.construction_evidence

    assert evidence is not None
    assert evidence.mutation_vector_exact is True
    assert evidence.construction_fully_validated is False
    assert evidence.baseline_mismatch_count == 1
    observation = evidence.observations[0]
    assert observation.construction_state is ProbeConstructionState.BASELINE_MISMATCH
    assert observation.concrete_projection_paths == (
        "prepared_body.renderer_version",
    )
    assert observation.actual_before_json == '"socrateszero-openrouter-renderer/v0"'
    assert observation.declared_before_json != observation.actual_before_json


def test_post_response_provider_display_baseline_is_not_silently_normalized() -> None:
    probe = _orthogonal(31)
    mutation = probe.literal_mutations[0].model_copy(
        update={"before_json": '"OpenRouter"'}
    )
    result = evaluate_openrouter_adapter_case_v0(
        probe.model_copy(update={"literal_mutations": (mutation,)})
    )
    evidence = result.construction_evidence

    assert evidence is not None
    assert evidence.unresolved_path_count == 0
    assert evidence.baseline_mismatch_count == 1
    assert evidence.observations[0].construction_state is ProbeConstructionState.BASELINE_MISMATCH
    assert evidence.observations[0].declared_before_json == '"OpenRouter"'
    assert evidence.observations[0].actual_before_json == '"openrouter"'
    assert evidence.observations[0].concrete_projection_paths == (
        "identity_evidence.actual_router_id",
    )


def test_fixture_manifest_binds_exact_candidate_graph_and_projection() -> None:
    candidate, projection = _candidate_fixture()
    payload = {
        path: {"value": value, "source": source}
        for path, (value, source) in projection.items()
    }
    from backend.dialogues.socrates_zero.contracts import canonical_json

    assert candidate.baseline_projection_sha256 == hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    assert candidate.fixture_manifest_id.startswith("szorfixture_")
    assert candidate.raw_response_evidence_id.startswith("szorraw_")
    assert candidate.identity_evidence_id.startswith("szoridentity_")
    assert candidate.usage_evidence_id.startswith("szorusage_")
    assert candidate.canned_response_envelope_id.startswith("szorenvelope_")
    assert candidate.attempt_receipt_id.startswith("szorattempt_")


def test_route_and_fallback_cases_use_exact_contract_surfaces() -> None:
    route = evaluate_openrouter_adapter_case_v0(_orthogonal(7))
    fallback = evaluate_openrouter_adapter_case_v0(_orthogonal(8))

    assert route.construction_evidence is not None
    assert route.construction_evidence.observations[0].concrete_projection_paths == (
        "route_policy.upstream_route_state",
    )
    assert fallback.construction_evidence is not None
    assert fallback.construction_evidence.observations[0].concrete_projection_paths == (
        "route_policy.application_fallback_allowed",
    )


def test_candidate_projection_contains_every_frozen_exact_surface() -> None:
    _, projection = _candidate_fixture()
    registered = {
        item.path for item in FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
    }

    assert registered <= set(projection)
    assert {
        "invocation_record.worker_terminated",
        "directive.attempt_late_mutation",
        "identity_evidence.actual_router_id",
        "identity_evidence.actual_model_id",
        "identity_evidence.actual_configuration_digest",
        "envelope.adapter_retry_count",
        "envelope.stream_used",
        "envelope.tool_calls",
        "usage_evidence.input_tokens",
        "usage_evidence.output_tokens",
        "usage_evidence.total_tokens",
        "attempt_receipt.attempt_receipt_id",
    } <= set(projection)


def test_every_frozen_probe_path_has_an_independent_evaluator_rule() -> None:
    probes = (
        FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
        + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
    )

    results = tuple(evaluate_openrouter_adapter_case_v0(probe) for probe in probes)

    assert len(results) == 52
    assert all(result.construction_evidence is not None for result in results)
    assert all(
        len(result.construction_evidence.observations) == len(probe.literal_mutations)
        for result, probe in zip(results, probes)
        if result.construction_evidence is not None
    )
    assert all(
        result.construction_evidence.mutation_vector_exact
        for result in results
        if result.construction_evidence is not None
    )


def test_two_attempt_positive_still_has_zero_transport_and_distinct_receipts() -> None:
    result = evaluate_openrouter_adapter_case_v0(
        FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0[1]
    )

    assert len(result.attempt_receipts) == 2
    assert {item.canned_transport_invocations for item in result.attempt_receipts} == {0}
    assert result.attempt_receipts[0].attempt_receipt_id != result.attempt_receipts[1].attempt_receipt_id


def test_tripwire_counters_keep_external_zero_and_scoped_counts_strict() -> None:
    counters = OpenRouterTripwireCountersV0()

    assert set(counters.model_dump().values()) == {0}
    with pytest.raises(ValidationError):
        OpenRouterTripwireCountersV0(external_network_attempts=1)
    with pytest.raises(ValidationError):
        OpenRouterTripwireCountersV0(unexpected=0)
    with pytest.raises(ValidationError):
        counters.external_network_attempts = 0  # type: ignore[misc]
    scoped = OpenRouterTripwireCountersV0(
        source_mutations=1,
        sibling_mutations=2,
        production_mutations=3,
    )
    assert (
        scoped.source_mutations,
        scoped.sibling_mutations,
        scoped.production_mutations,
    ) == (1, 2, 3)
    with pytest.raises(ValidationError):
        scoped.source_mutations = 0  # type: ignore[misc]
    for field_name in (
        "source_mutations",
        "sibling_mutations",
        "production_mutations",
    ):
        for invalid in (True, 1.0, "1", -1):
            with pytest.raises(ValidationError):
                OpenRouterTripwireCountersV0(**{field_name: invalid})


def test_frozen_scoped_inventory_has_exact_membership_and_order() -> None:
    assert FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0 == (
        (
            "SOURCE",
            (
                "backend/dialogues/socrates_zero/openrouter_acquisition_contracts.py",
                "backend/dialogues/socrates_zero/openrouter_acquisition_renderer.py",
                "backend/dialogues/socrates_zero/openrouter_acquisition_adapter.py",
                "backend/dialogues/socrates_zero/openrouter_acquisition_cases.py",
                "backend/dialogues/socrates_zero/openrouter_acquisition_evaluation.py",
                "backend/dialogues/socrates_zero/acquisition_tripwires.py",
                "tests_dialogues/test_socrates_zero_openrouter_acquisition_contracts.py",
                "tests_dialogues/test_socrates_zero_openrouter_acquisition_renderer.py",
                "tests_dialogues/test_socrates_zero_openrouter_acquisition_adapter.py",
                "tests_dialogues/test_socrates_zero_openrouter_acquisition_cases.py",
                "tests_dialogues/test_socrates_zero_openrouter_acquisition_evaluation.py",
                "tests_dialogues/conftest.py",
                "tests_dialogues/test_socrates_zero_acquisition_boundaries.py",
                "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/MEMORY.md",
                "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/PLAN.md",
                "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/PRESENT.md",
                "docs/branches/feature-socrates-zero-provider-adapter-controls-v0/README.md",
            ),
        ),
        (
            "SIBLING",
            (
                "backend/dialogues/socrates_zero/__init__.py",
                "backend/dialogues/socrates_zero/acquisition.py",
                "backend/dialogues/socrates_zero/acquisition_cases.py",
                "backend/dialogues/socrates_zero/acquisition_contracts.py",
                "backend/dialogues/socrates_zero/acquisition_evaluation.py",
                "backend/dialogues/socrates_zero/acquisition_isolation_evidence.py",
                "backend/dialogues/socrates_zero/baseline.py",
                "backend/dialogues/socrates_zero/constitution.py",
                "backend/dialogues/socrates_zero/contracts.py",
                "backend/dialogues/socrates_zero/evaluation.py",
                "backend/dialogues/socrates_zero/evaluation_cases.py",
                "backend/dialogues/socrates_zero/evaluation_harness.py",
                "backend/dialogues/socrates_zero/policy.py",
                "backend/dialogues/socrates_zero/puct.py",
                "backend/dialogues/socrates_zero/strategy.py",
                "backend/dialogues/socrates_zero/value.py",
            ),
        ),
        (
            "PRODUCTION",
            (
                "backend/dialogues/agent.py",
                "backend/dialogues/ced.py",
                "backend/dialogues/ced_search_observability_v1.py",
                "backend/dialogues/ced_search_projection.py",
                "backend/dialogues/ced_search_projection_v1.py",
                "backend/dialogues/ced_search_value_v1.py",
                "backend/dialogues/ced_search_value_v1_artifact.py",
                "backend/dialogues/ced_search_value_v1_bestofn.py",
                "backend/dialogues/ced_search_value_v1_bestofn_cases.py",
                "backend/dialogues/ced_search_value_v1_contracts.py",
                "backend/dialogues/ced_search_value_v1_evaluation.py",
                "backend/dialogues/ced_search_value_v1_evaluation_cases.py",
                "backend/dialogues/hybrid_authority.py",
                "backend/dialogues/hybrid_epistemic.py",
                "backend/dialogues/hybrid_shadow.py",
                "backend/dialogues/hybrid_support.py",
                "backend/dialogues/ced_canonical_successor.py",
                "backend/dialogues/ced_canonical_successor_cases.py",
                "backend/dialogues/ced_canonical_successor_cases_v1.py",
                "backend/dialogues/ced_canonical_successor_cases_v2.py",
                "backend/dialogues/ced_canonical_successor_contracts.py",
                "backend/dialogues/ced_canonical_successor_evaluation.py",
                "backend/dialogues/ced_canonical_successor_evaluation_v2.py",
                "backend/dialogues/ced_canonical_successor_frozen_core_v2.py",
                "backend/dialogues/ced_canonical_successor_manifest.py",
                "backend/dialogues/ced_canonical_successor_recording.py",
                "backend/dialogues/ced_canonical_successor_recording_contracts.py",
                "backend/dialogues/ced_canonical_successor_recording_fixtures.py",
                "backend/dialogues/openrouter_provider.py",
                "backend/dialogues/provider_registry.py",
                "backend/dialogues/live_providers.py",
                "backend/dialogues/model_identity.py",
                "backend/dialogues/models.py",
                "backend/dialogues/providers.py",
                "backend/dialogues/reasoning_prompts.py",
                "backend/dialogues/role_assignment.py",
                "backend/dialogues/socratic.py",
                "backend/dialogues/task_checker.py",
                "backend/dialogues/topic.py",
            ),
        ),
    )
    assert tuple(
        (scope, len(paths))
        for scope, paths in FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0
    ) == (("SOURCE", 17), ("SIBLING", 16), ("PRODUCTION", 39))


def test_scoped_path_evidence_derives_zero_and_mismatch_counts(tmp_path) -> None:
    _write_scoped_inventory(tmp_path, _TEST_SCOPED_PATH_INVENTORY)
    before = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )
    unchanged_after = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )
    unchanged = compare_openrouter_scoped_path_snapshots_v0(
        before, unchanged_after
    )

    assert unchanged.all_paths_unchanged is True
    assert (
        unchanged.source_mutations,
        unchanged.sibling_mutations,
        unchanged.production_mutations,
    ) == (0, 0, 0)
    assert all(row.matches is True for row in unchanged.rows)

    (tmp_path / "source.txt").write_bytes(b"mutated\n")
    changed_after = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )
    changed = compare_openrouter_scoped_path_snapshots_v0(before, changed_after)

    assert changed.all_paths_unchanged is False
    assert (
        changed.source_mutations,
        changed.sibling_mutations,
        changed.production_mutations,
    ) == (1, 0, 0)
    source_row = changed.rows[0]
    assert source_row.before_sha256 != source_row.after_sha256
    assert source_row.matches is False
    assert source_row.mutation_detected is True


def test_scoped_capture_ignores_unlisted_files_without_enumeration(tmp_path) -> None:
    _write_scoped_inventory(tmp_path, _TEST_SCOPED_PATH_INVENTORY)
    unlisted = tmp_path / "unlisted" / "new.py"
    unlisted.parent.mkdir()
    unlisted.write_bytes(b"before\n")
    before = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )
    unlisted.write_bytes(b"after\n")
    after = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )

    evidence = compare_openrouter_scoped_path_snapshots_v0(before, after)

    assert evidence.all_paths_unchanged is True
    assert tuple(row.relative_path for row in evidence.rows) == (
        "source.txt",
        "sibling.txt",
        "production.txt",
    )


def test_scoped_path_evidence_treats_missing_frozen_paths_as_mutations(
    tmp_path,
) -> None:
    _write_scoped_inventory(
        tmp_path,
        _TEST_SCOPED_PATH_INVENTORY,
        omitted=("sibling.txt",),
    )
    before = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )
    after = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )

    evidence = compare_openrouter_scoped_path_snapshots_v0(before, after)

    assert evidence.sibling_mutations == 1
    missing = next(
        row for row in evidence.rows if row.scope is OpenRouterMutationScope.SIBLING
    )
    assert missing.before_present is False
    assert missing.after_present is False
    assert missing.before_sha256 is None
    assert missing.after_sha256 is None
    assert missing.matches is False


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "../outside.txt",
        "/absolute.txt",
        "nested/../../outside.txt",
        "C:/outside.txt",
        "C:outside.txt",
        "//server/share/outside.txt",
        r"\\server\share\outside.txt",
        r"\\?\C:\outside.txt",
        r"\\.\C:\outside.txt",
    ),
)
def test_scoped_inventory_rejects_escape_paths(tmp_path, unsafe_path: str) -> None:
    inventory = (
        ("SOURCE", (unsafe_path,)),
        ("SIBLING", ("sibling.txt",)),
        ("PRODUCTION", ("production.txt",)),
    )

    with pytest.raises((ValueError, ValidationError)):
        capture_openrouter_scoped_path_snapshot_v0(tmp_path, inventory)


def test_scoped_inventory_rejects_symlink_resolution_outside_root(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside\n")
    link = root / "source-link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("filesystem does not permit test symlinks")
    inventory = (
        ("SOURCE", ("source-link.txt",)),
        ("SIBLING", ("sibling.txt",)),
        ("PRODUCTION", ("production.txt",)),
    )

    with pytest.raises(ValueError):
        capture_openrouter_scoped_path_snapshot_v0(root, inventory)


def test_scoped_snapshot_comparison_rejects_category_tamper(tmp_path) -> None:
    _write_scoped_inventory(tmp_path, _TEST_SCOPED_PATH_INVENTORY)
    before = capture_openrouter_scoped_path_snapshot_v0(
        tmp_path, _TEST_SCOPED_PATH_INVENTORY
    )
    tampered_first = before.rows[0].model_copy(
        update={"scope": OpenRouterMutationScope.SIBLING}
    )
    tampered_after = before.model_copy(
        update={"rows": (tampered_first,) + before.rows[1:]}
    )

    with pytest.raises(ValidationError):
        compare_openrouter_scoped_path_snapshots_v0(before, tampered_after)


def test_artifact_scoped_claims_reject_zero_counter_and_category_tamper(
    tmp_path,
) -> None:
    _write_scoped_inventory(tmp_path, FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0)
    before = capture_openrouter_scoped_path_snapshot_v0(tmp_path)
    first_source_path = FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0[0][1][0]
    (tmp_path / first_source_path).write_bytes(b"mutated-source\n")
    after = capture_openrouter_scoped_path_snapshot_v0(tmp_path)
    evidence = compare_openrouter_scoped_path_snapshots_v0(before, after)

    assert evidence.inventory_id == FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_ID_V0
    assert evidence.source_mutations == 1
    with pytest.raises(ValueError):
        _assert_frozen_scoped_mutation_accounting_v0(
            evidence,
            OpenRouterTripwireCountersV0(),
        )

    matching_counters = OpenRouterTripwireCountersV0(source_mutations=1)
    _assert_frozen_scoped_mutation_accounting_v0(evidence, matching_counters)

    payload = evidence.model_dump(mode="python")
    payload["source_mutations"] = 0
    with pytest.raises(ValidationError):
        OpenRouterScopedMutationEvidenceV0.model_validate(payload)

    category_tampered = evidence.model_copy(
        update={
            "rows": (
                evidence.rows[0].model_copy(
                    update={"scope": OpenRouterMutationScope.SIBLING}
                ),
            )
            + evidence.rows[1:]
        }
    )
    with pytest.raises(ValueError):
        _assert_frozen_scoped_mutation_accounting_v0(
            category_tampered,
            matching_counters,
        )

    digest_poisoned = evidence.model_copy(
        update={
            "rows": (
                evidence.rows[0].model_copy(
                    update={"after_sha256": evidence.rows[0].before_sha256}
                ),
            )
            + evidence.rows[1:]
        }
    )
    with pytest.raises(ValidationError):
        _assert_frozen_scoped_mutation_accounting_v0(
            digest_poisoned,
            matching_counters,
        )


def test_final_postbuild_snapshot_detects_mutation_during_artifact_validation(
    tmp_path,
    monkeypatch,
) -> None:
    _write_scoped_inventory(tmp_path, FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0)
    before = capture_openrouter_scoped_path_snapshot_v0(tmp_path)
    embedded_after = capture_openrouter_scoped_path_snapshot_v0(tmp_path)
    expected_evidence = compare_openrouter_scoped_path_snapshots_v0(
        before,
        embedded_after,
    )

    class FakeArtifact:
        scoped_mutation_evidence = expected_evidence

    class FakeArtifactValidator:
        def validate_and_recompute(self):
            return FakeArtifact()

    validator = FakeArtifactValidator()
    original_validate = validator.validate_and_recompute
    first_source_path = FROZEN_OPENROUTER_SCOPED_PATH_INVENTORY_V0[0][1][0]

    def mutate_during_validation():
        artifact = original_validate()
        (tmp_path / first_source_path).write_bytes(b"validator-mutation\n")
        return artifact

    monkeypatch.setattr(
        validator,
        "validate_and_recompute",
        mutate_during_validation,
    )

    with pytest.raises(ValueError, match="artifact construction"):
        _build_authoritative_artifact_under_scoped_guard_v0(
            tmp_path,
            before,
            embedded_after,
            validator.validate_and_recompute,
        )


def test_historical_hash_verifier_uses_bytes_and_reports_mismatch(tmp_path) -> None:
    good = b"frozen-history\n"
    (tmp_path / "good.json").write_bytes(good)
    (tmp_path / "bad.json").write_bytes(b"different\n")
    expected = hashlib.sha256(good).hexdigest()
    locks = (
        ("good", "good.json", expected),
        ("bad", "bad.json", expected),
        ("missing", "missing.json", expected),
    )

    evidence = verify_historical_hashes_v0(tmp_path, locks)

    assert tuple(item.matches for item in evidence) == (True, False, False)
    assert evidence[0].observed_sha256 == expected
    assert evidence[2].observed_sha256 is None


def test_frozen_historical_inventory_has_all_nine_required_locks(tmp_path) -> None:
    evidence = verify_historical_hashes_v0(tmp_path)

    assert len(evidence) == 9
    assert tuple(item.label for item in evidence[-3:]) == (
        "acquisition-artifact",
        "acquisition-replay-execution",
        "acquisition-replay-lock",
    )
    assert all(item.observed_sha256 is None for item in evidence)
    assert all(item.matches is False for item in evidence)


def test_core_lock_verifier_parses_payload_instead_of_trusting_literal(tmp_path) -> None:
    path = tmp_path / FROZEN_CORE_BLOB_LOCK_SOURCE_PATH_V2
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"core_lock":{"fingerprint":"' + "0" * 64
        + '","lock_id":"cedcorebloblockv2_' + "0" * 64
        + '","payload":"changed"},"core_lock_id":"cedcorebloblockv2_'
        + "0" * 64 + '"}',
        encoding="utf-8",
    )

    evidence = verify_core_blob_lock_v0(tmp_path)

    assert evidence.matches is False
    assert evidence.actual_top_level_lock_id != evidence.expected_lock_id
    assert evidence.recomputed_embedded_lock_id != evidence.expected_lock_id


def test_metrics_schema_exposes_every_section_63_category() -> None:
    fields = set(OpenRouterEvaluationMetricsV0.model_fields)

    assert {
        "positive_cases",
        "exact_positive_receipts",
        "orthogonal_probes",
        "orthogonal_exact_primary_results",
        "precedence_probes",
        "precedence_exact_primary_results",
        "invalid_probe_constructions",
        "body_byte_mismatch_results",
        "entropy_violation_results",
        "model_provider_configuration_mismatches_accepted",
        "fallback_activations_accepted",
        "retry_activations_accepted",
        "streaming_activations_accepted",
        "tool_activations_accepted",
        "token_bound_failures",
        "pricing_cost_evidence_failures",
        "timeout_worker_leaks",
        "multiple_transport_invocations",
        "raw_response_evidence_failures",
        "usage_incompleteness",
        "false_zero_violations",
        "identity_collisions",
        "credential_header_leakage",
        "external_network_attempts",
        "credential_access_attempts",
        "provider_calls",
        "provider_sdk_calls",
        "model_calls",
        "tool_calls",
        "ced_application_invocations",
        "source_mutations",
        "sibling_mutations",
        "production_mutations",
        "receipt_mismatches_accepted",
        "receipt_mismatch_results",
    } <= fields


def test_threshold_failure_is_derived_from_unresolved_evidence() -> None:
    metrics = OpenRouterEvaluationMetricsV0(
        positive_complete_case_results=7,
        positive_attempt_receipts=8,
        exact_positive_receipts=8,
        orthogonal_exact_primary_results=44,
        precedence_exact_primary_results=8,
        attempt_receipts_total=60,
        canned_transport_invocations=34,
        invalid_probe_constructions=0,
        unexpected_failure_or_mismatch_count=0,
        historical_lock_mismatches=0,
        core_lock_mismatches=0,
        body_byte_mismatch_results=0,
        entropy_violation_results=0,
        route_policy_unproven_results=0,
        fallback_intent_control_failures=0,
        receipt_mismatch_results=0,
        token_bound_failures=0,
        pricing_cost_evidence_failures=0,
        timeout_worker_leaks=0,
        multiple_transport_invocations=0,
        raw_response_evidence_failures=0,
        usage_incompleteness=0,
        false_zero_violations=0,
        identity_collisions=0,
        credential_header_leakage=0,
        body_byte_mismatches_accepted=0,
        entropy_violations_accepted=0,
        model_provider_configuration_mismatches_accepted=0,
        fallback_activations_accepted=0,
        retry_activations_accepted=0,
        streaming_activations_accepted=0,
        tool_activations_accepted=0,
        receipt_mismatches_accepted=0,
        accepted_control_violations=0,
        accepted_identity_mismatches=0,
        accepted_fallback_retry_stream_tool_activations=0,
        accepted_token_pricing_cost_failures=0,
        accepted_raw_usage_privacy_receipt_failures=0,
        unexpected_multiple_transport_invocations=0,
        surviving_tasks=0,
        accepted_late_mutations=0,
    )

    assert metrics.thresholds_passed is False
    assert "PRICING_STATUS" in metrics.threshold_failure_reasons
    assert "UNRESOLVED_TOKEN_BOUND_CONTROL" not in metrics.threshold_failure_reasons
    assert "UNRESOLVED_PRICING_OR_COST_CONTROL" not in metrics.threshold_failure_reasons


def test_metric_control_failures_derive_from_candidate_and_activity_counters(
    tmp_path,
) -> None:
    candidate = build_openrouter_candidate_evidence_v0()
    counters = OpenRouterTripwireCountersV0(
        source_mutations=1,
        sibling_mutations=2,
        production_mutations=3,
    )
    core = verify_core_blob_lock_v0(tmp_path)

    metrics = _metrics((), (), core, candidate, counters)

    assert metrics.token_bound_failures == 1
    assert metrics.pricing_cost_evidence_failures == 2
    assert metrics.fallback_intent_control_failures == 1
    assert metrics.external_network_attempts == counters.external_network_attempts
    assert metrics.credential_access_attempts == counters.credential_access_attempts
    assert metrics.provider_calls == counters.live_provider_calls
    assert metrics.provider_sdk_calls == counters.provider_sdk_calls
    assert metrics.model_calls == counters.model_executions
    assert metrics.tool_calls == counters.tool_calls
    assert (
        metrics.ced_application_invocations
        == counters.canonical_application_calls
    )
    assert metrics.source_mutations == counters.source_mutations
    assert metrics.sibling_mutations == counters.sibling_mutations
    assert metrics.production_mutations == counters.production_mutations
    assert (
        "ZERO_EXTERNAL_OR_CANONICAL_ACTIVITY"
        in metrics.threshold_failure_reasons
    )


def test_metrics_count_receipts_vectors_and_all_comparison_mismatches(tmp_path) -> None:
    candidate = build_openrouter_candidate_evidence_v0()
    counters = OpenRouterTripwireCountersV0()
    core = verify_core_blob_lock_v0(tmp_path)
    results = tuple(
        evaluate_openrouter_adapter_case_v0(case)
        for case in (
            FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
            + FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
            + FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
        )
    )

    metrics = _metrics(results, (), core, candidate, counters)

    assert metrics.positive_attempt_receipts == 8
    assert metrics.exact_positive_receipts == 0
    assert metrics.attempt_receipts_total == 60
    assert metrics.canned_transport_invocations == 0
    assert metrics.invalid_probe_constructions == 0
    assert metrics.unexpected_failure_or_mismatch_count > 0
    assert metrics.credential_header_leakage == 1
    assert metrics.identity_collisions == 0

    base = results[7]
    assert base.construction_evidence is not None
    vector_tampered = base.model_copy(
        update={
            "construction_evidence": base.construction_evidence.model_copy(
                update={"mutation_vector_exact": False}
            )
        }
    )
    trace_tampered = base.model_copy(update={"guard_trace_exact": False})
    tampered = _metrics(
        (vector_tampered, trace_tampered), (), core, candidate, counters
    )

    assert tampered.invalid_probe_constructions == 1
    assert tampered.unexpected_failure_or_mismatch_count >= 1


def test_historical_hash_schema_rejects_false_match_flag() -> None:
    digest = "a" * 64
    with pytest.raises(ValidationError):
        OpenRouterHistoricalHashEvidenceV0(
            label="drift",
            repository_path="drift.json",
            expected_sha256=digest,
            observed_sha256=digest,
            matches=False,
        )


def test_authoritative_artifact_schema_cannot_claim_a_partial_case_set() -> None:
    with pytest.raises(ValidationError):
        OpenRouterEvaluationArtifactV0.model_validate(
            {
                "case_set_id": "partial",
                "case_set_sha256": "a" * 64,
                "candidate_evidence": {},
                "case_results": [],
                "metrics": {},
                "historical_hashes": [],
                "tripwire_counters": {},
            }
        )

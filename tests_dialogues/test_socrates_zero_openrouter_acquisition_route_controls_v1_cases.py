from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.openrouter_route_controls_cases import (
    FAILURE_GUARD_BY_CODE_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_REQUEST_PROBES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_RESPONSE_PROBES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_REQUEST_CASES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_RESPONSE_CASES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_PRECEDENCE_PROBES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1,
    FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1,
    MUTATION_VECTOR_FIELD_NAMES_V1,
    OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1,
    OpenRouterRouteControlCaseKind,
    OpenRouterRouteControlCaseV1,
    OpenRouterRouteControlExpectedOutcome,
    OpenRouterRouteControlFailureCode,
    OpenRouterRouteControlGuardStage,
    OpenRouterRouteControlThresholdsV1,
    MutationState,
    frozen_openrouter_route_control_case_set_sha256_v1,
)


def test_exact_frozen_membership_counts_and_dispatch_budget() -> None:
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1) == 63
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_REQUEST_CASES_V1) == 3
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_POSITIVE_RESPONSE_CASES_V1) == 3
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_REQUEST_PROBES_V1) == 29
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_ORTHOGONAL_RESPONSE_PROBES_V1) == 20
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_PRECEDENCE_PROBES_V1) == 8
    assert sum(case.expected_canned_invocations for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1) == 26
    assert sum(case.expected_complete_route_intent_receipts for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1) == 7
    assert sum(case.expected_complete_metadata_receipts for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1) == 3


def test_exact_case_id_sequence_is_frozen() -> None:
    expected = (
        "sr01-canonical-route-body sr02-canonical-route-headers sr03-sibling-intent-replay "
        "ss01-metadata-attempts-absent ss02-metadata-attempts-present ss03-forward-compatible-extras "
        "or01-missing-model or02-wrong-model or03-models-singleton-present or04-models-several-present "
        "or05-provider-only-missing or06-only-empty or07-only-multiple or08-only-duplicate or09-wrong-endpoint "
        "or10-wildcard-selector or11-base-provider-selector or12-order-missing or13-order-mismatch "
        "or14-order-extra-endpoint or15-fallback-true or16-fallback-missing or17-require-parameters-false "
        "or18-require-parameters-missing or19-guessed-max-price or20-stream-true or21-tools-enabled "
        "or22-metadata-header-missing or23-metadata-header-malformed or24-cache-header-missing "
        "or25-cache-enabled or26-body-entropy or27-header-entropy or28-noncanonical-body or29-post-prepare-mutation "
        "os01-metadata-missing os02-metadata-malformed os03-attempt-missing os04-attempt-zero "
        "os05-attempt-greater-than-one os06-wrong-actual-model os07-wrong-provider os08-actual-model-missing "
        "os09-provider-missing os10-attempts-inconsistent os11-several-attempts os12-attempts-top-level-contradiction "
        "os13-cache-hit-metadata-unavailable os14-fake-exact-endpoint-claim os15-unknown-authority-override "
        "os16-fallback-strategy os17-alias-model-substitution os18-provider-substitution "
        "os19-forbidden-pipeline-stage os20-cache-hit-with-metadata "
        "p01-manifest-mismatch-plus-malformed-route p02-wrong-model-plus-fallback-true "
        "p03-cache-header-missing-plus-metadata-missing p04-actual-model-missing-plus-provider-mismatch "
        "p05-multi-attempt-plus-model-substitution p06-fallback-strategy-plus-fake-endpoint "
        "p07-max-price-plus-wrong-endpoint p08-body-entropy-plus-wrong-endpoint"
    ).split()
    assert [case.case_id for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1] == [
        f"orroutev1-{suffix}" for suffix in expected
    ]


def test_guard_order_and_failure_taxonomy_are_complete_and_aligned() -> None:
    assert len(FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1) == 32
    assert len(set(FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1)) == 32
    steps = FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.steps
    assert all(step.stage == OpenRouterRouteControlGuardStage.PRE_DISPATCH for step in steps[:17])
    assert all(step.stage == OpenRouterRouteControlGuardStage.POST_RESPONSE for step in steps[17:])
    assert set(FAILURE_GUARD_BY_CODE_V1) == set(OpenRouterRouteControlFailureCode)
    assert len(FROZEN_OPENROUTER_ROUTE_CONTROL_FAILURE_TAXONOMY_V1.entries) == len(OpenRouterRouteControlFailureCode)
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1:
        if case.expected_failure_code is not None:
            assert FAILURE_GUARD_BY_CODE_V1[case.expected_failure_code] == case.expected_guard_id


def test_mutation_construction_and_complete_22_field_coverage() -> None:
    assert len(MUTATION_VECTOR_FIELD_NAMES_V1) == 22
    coverage: set[str] = set()
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1:
        intentional = {
            name
            for name in MUTATION_VECTOR_FIELD_NAMES_V1
            if getattr(case.mutation_vector, name) == MutationState.INTENTIONALLY_CHANGED
        }
        coverage.update(intentional)
        if case.kind in {OpenRouterRouteControlCaseKind.POSITIVE_REQUEST, OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE}:
            assert not intentional and not case.mutations
            assert case.expected_outcome == OpenRouterRouteControlExpectedOutcome.ACCEPTED
        elif case.kind == OpenRouterRouteControlCaseKind.PRECEDENCE:
            assert len(intentional) >= 2 and len(case.mutations) >= 2
        else:
            assert len(intentional) == 1 and len(case.mutations) == 1
        assert {mutation.mutation_vector_field for mutation in case.mutations} == intentional
    assert coverage == set(MUTATION_VECTOR_FIELD_NAMES_V1)


def test_mutation_paths_are_generic_nested_fixture_paths() -> None:
    permitted = (
        "manifest.",
        "policy.",
        "request.body.",
        "request.headers.",
        "request.serialization.",
        "request.prepared_bytes.",
        "response.",
    )
    for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1:
        for mutation in case.mutations:
            assert mutation.path.startswith(permitted)


def test_case_set_and_fingerprints_are_stable_and_unique() -> None:
    assert OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1.startswith("szorroutecasesetv1_")
    assert frozen_openrouter_route_control_case_set_sha256_v1() == OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1.removeprefix("szorroutecasesetv1_")
    assert len({case.case_fingerprint for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1}) == 63
    round_trip = type(FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1).model_validate_json(
        FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1.model_dump_json()
    )
    assert round_trip == FROZEN_OPENROUTER_ROUTE_CONTROL_CASE_SET_V1


def test_threshold_tampering_and_case_extra_fields_fail_closed() -> None:
    threshold_payload = FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1.model_dump(mode="json")
    threshold_payload["cases_total"] = 62
    with pytest.raises(ValidationError):
        OpenRouterRouteControlThresholdsV1.model_validate(threshold_payload)
    case_payload = FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1[0].model_dump(mode="json")
    case_payload["runtime_ground_truth"] = True
    with pytest.raises(ValidationError):
        OpenRouterRouteControlCaseV1.model_validate(case_payload)


def test_case_module_remains_data_only() -> None:
    source_path = Path(__file__).parents[1] / "backend/dialogues/socrates_zero/openrouter_route_controls_cases.py"
    source = source_path.read_text(encoding="utf-8")
    for forbidden_import in (
        "openrouter_route_controls_renderer",
        "openrouter_route_controls_runtime",
        "openrouter_route_controls_evaluation",
        "openrouter_provider",
        "acquisition_tripwires",
    ):
        assert forbidden_import not in source

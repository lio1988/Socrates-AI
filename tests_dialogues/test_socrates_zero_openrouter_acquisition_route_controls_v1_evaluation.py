from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_cases import (
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1,
    OpenRouterRouteControlCaseV1,
    OpenRouterRouteControlCaseKind,
    OpenRouterRouteControlFailureCode,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_renderer import (
    prepare_openrouter_route_request_v1,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_parser import (
    OpenRouterRouteAttestationV1,
    OpenRouterRouterMetadataReceiptV1,
)
from backend.dialogues.socrates_zero.openrouter_provenance_boundary_v1 import (
    FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1,
    openrouter_provenance_record_v1,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_evaluation import (
    FROZEN_OPENROUTER_ROUTE_CONTROL_ARTIFACT_CLAIM_FIREWALL_V1,
    FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1,
    OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1,
    OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1,
    OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_RELATIVE_PATH_V1,
    OpenRouterBoundaryCountersV1,
    OpenRouterRouteControlArtifactClaimFirewallV1,
    OpenRouterRouteControlArtifactV1,
    OpenRouterRouteControlCaseActualOutcomeV1,
    OpenRouterRouteControlCaseResultV1,
    OpenRouterRouteControlHypothesisStatusV1,
    OpenRouterRouteControlMetricsV1,
    OpenRouterRouteControlReplayExecutionV1,
    OpenRouterRouteControlReplayLockV1,
    _acquire_authoritative_aggregate_claim_v1,
    _build_route_control_artifact_v1,
    _validate_authoritative_aggregate_claim_v1,
    _validate_frozen_evidence_record_links_v1,
    _validate_replay_result_trace_crosslink_v1,
    assess_openrouter_official_response_wire_mapping_v1,
    build_independent_reverse_replay_v1,
    capture_openrouter_route_control_scoped_snapshot_v1,
    evaluate_openrouter_route_control_case_v1,
    load_openrouter_route_control_artifact_v1,
    load_openrouter_route_control_replay_execution_v1,
    load_openrouter_route_control_replay_lock_v1,
    official_response_wire_mapping_gate_passes_v1,
    official_response_wire_mapping_violation_count_v1,
    publish_openrouter_route_control_replay_once_v1,
    render_openrouter_route_control_artifact_v1,
    render_openrouter_route_control_replay_execution_v1,
    render_openrouter_route_control_replay_lock_v1,
    verify_openrouter_route_control_historical_hashes_v1,
)


ROOT = Path(__file__).resolve().parents[1]


def _syntactic_replay_evidence(
    *,
    ordered_result_ids: tuple[str, ...] | None = None,
) -> tuple[OpenRouterRouteControlReplayExecutionV1, OpenRouterRouteControlReplayLockV1]:
    artifact_id = "szorroutecontrolartifactv1_" + "1" * 64
    artifact_sha256 = "2" * 64
    artifact_bytes = 1
    ordered_case_ids = tuple(
        case.case_id for case in reversed(FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1)
    )
    if ordered_result_ids is None:
        ordered_result_ids = tuple(
            "szorroutecaseresultv1_" + f"{index:064x}"
            for index, _ in enumerate(ordered_case_ids, start=1)
        )
    execution = OpenRouterRouteControlReplayExecutionV1(
        ordered_case_ids=ordered_case_ids,
        ordered_result_ids=ordered_result_ids,
        ordered_result_trace_sha256=hashlib.sha256(
            canonical_json(tuple(zip(ordered_case_ids, ordered_result_ids))).encode(
                "utf-8"
            )
        ).hexdigest(),
        authoritative_artifact_id=artifact_id,
        authoritative_artifact_sha256=artifact_sha256,
        replay_artifact_id=artifact_id,
        replay_artifact_sha256=artifact_sha256,
        authoritative_artifact_bytes=artifact_bytes,
        replay_artifact_bytes=artifact_bytes,
        boundary_counters=OpenRouterBoundaryCountersV1(),
    )
    execution_bytes = render_openrouter_route_control_replay_execution_v1(execution)
    replay_lock = OpenRouterRouteControlReplayLockV1(
        artifact_id=artifact_id,
        artifact_sha256=artifact_sha256,
        replay_execution_id=execution.replay_execution_id or "",
        replay_execution_sha256=hashlib.sha256(execution_bytes).hexdigest(),
    )
    return execution, replay_lock


def _evaluate_frozen_cases():
    return tuple(
        evaluate_openrouter_route_control_case_v1(case)
        for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
    )


def test_all_frozen_case_results_match_predeclared_truth() -> None:
    results = _evaluate_frozen_cases()
    assert len(results) == 63
    assert all(result.construction_valid for result in results)
    assert all(result.result_matches_expectation for result in results)
    assert sum(result.canned_transport_invocations for result in results) == 26
    assert sum(result.complete_route_intent_receipts for result in results) == 7
    assert sum(result.complete_metadata_receipts for result in results) == 3


def test_positive_receipts_preserve_partial_attestation_and_deferred_claims() -> None:
    results = _evaluate_frozen_cases()
    positives = tuple(
        result
        for result in results
        if result.kind
        in {
            OpenRouterRouteControlCaseKind.POSITIVE_REQUEST,
            OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE,
        }
    )
    assert len(positives) == 6
    assert all(
        result.actual_outcome is OpenRouterRouteControlCaseActualOutcomeV1.ACCEPTED
        for result in positives
    )
    assert all(
        result.response_exact_endpoint_attestation == "NOT_ESTABLISHED"
        and result.live_server_enforcement == "NOT_PROVEN"
        and result.p17_input_token_bound == "NOT_ESTABLISHED"
        and result.p18_pricing_record == "NOT_ESTABLISHED"
        and result.p19_cost_bound == "NOT_ESTABLISHED"
        for result in positives
    )
    response_results = tuple(
        result
        for result in positives
        if result.kind is OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE
    )
    assert all(result.metadata_receipt is not None for result in response_results)
    assert all(
        result.route_attestation.response_exact_endpoint_attestation
        == "NOT_ESTABLISHED"
        for result in response_results
    )
    with pytest.raises(ValidationError, match="frozen"):
        response_results[0].route_attestation.live_pilot_readiness = "EARNED"


def test_rejected_dispatched_cases_retain_raw_first_evidence_only() -> None:
    results = _evaluate_frozen_cases()
    rejected_dispatches = tuple(
        result
        for result in results
        if result.actual_outcome is OpenRouterRouteControlCaseActualOutcomeV1.REJECTED
        and result.canned_transport_invocations == 1
    )
    assert len(rejected_dispatches) == 23
    assert all(result.raw_response_evidence is not None for result in rejected_dispatches)
    assert all(result.metadata_receipt is None for result in rejected_dispatches)
    assert all(result.route_attestation is None for result in rejected_dispatches)


def test_case_result_rejects_reidentified_raw_sha_crosslink_mismatch() -> None:
    source = next(
        evaluate_openrouter_route_control_case_v1(case)
        for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
        if case.kind is OpenRouterRouteControlCaseKind.POSITIVE_RESPONSE
    )
    assert source.metadata_receipt is not None
    assert source.route_attestation is not None
    metadata_payload = source.metadata_receipt.model_dump(mode="json")
    metadata_payload["raw_response_sha256"] = "0" * 64
    metadata_payload["receipt_id"] = None
    metadata = OpenRouterRouterMetadataReceiptV1.model_validate(metadata_payload)
    attestation_payload = source.route_attestation.model_dump(mode="json")
    attestation_payload["metadata_receipt_id"] = metadata.receipt_id
    attestation_payload["attestation_id"] = None
    attestation = OpenRouterRouteAttestationV1.model_validate(attestation_payload)
    payload = source.model_dump(mode="json")
    payload["metadata_receipt"] = metadata.model_dump(mode="json")
    payload["metadata_receipt_id"] = metadata.receipt_id
    payload["route_attestation"] = attestation.model_dump(mode="json")
    payload["route_attestation_id"] = attestation.attestation_id
    with pytest.raises(ValidationError, match="receipt evidence links changed"):
        OpenRouterRouteControlCaseResultV1.model_validate(payload)


def test_realized_request_mutation_changes_dependent_evidence_identity() -> None:
    prepared = prepare_openrouter_route_request_v1()
    case = next(
        case
        for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
        if case.case_id == "orroutev1-or02-wrong-model"
    )
    result = evaluate_openrouter_route_control_case_v1(
        case, prepared_request=prepared
    )
    assert result.construction_valid is True
    assert result.route_intent_id != prepared.route_intent_id
    assert result.candidate_request_evidence_id != (
        prepared.request_intent_receipt.receipt_id
    )
    assert result.request_intent_receipt_ids == ()


def test_unknown_but_well_formed_case_is_invalid_probe_construction() -> None:
    source = next(
        case
        for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
        if case.case_id == "orroutev1-or01-missing-model"
    )
    payload = source.model_dump(mode="json")
    payload["case_id"] = "orroutev1-or99-unknown-probe"
    payload["case_fingerprint"] = None
    unknown = OpenRouterRouteControlCaseV1.model_validate(payload)
    result = evaluate_openrouter_route_control_case_v1(unknown)
    assert result.construction_valid is False
    assert result.actual_outcome is (
        OpenRouterRouteControlCaseActualOutcomeV1.INVALID_PROBE_CONSTRUCTION
    )
    assert result.guard_trace == ()
    assert result.result_matches_expectation is False


def test_cache_missing_metadata_and_precedence_use_the_frozen_first_guard() -> None:
    by_id = {
        case.case_id: evaluate_openrouter_route_control_case_v1(case)
        for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
        if case.case_id
        in {
            "orroutev1-os13-cache-hit-metadata-unavailable",
            "orroutev1-p03-cache-header-missing-plus-metadata-missing",
            "orroutev1-p04-actual-model-missing-plus-provider-mismatch",
            "orroutev1-p05-multi-attempt-plus-model-substitution",
        }
    }
    assert by_id[
        "orroutev1-os13-cache-hit-metadata-unavailable"
    ].actual_failure_code is OpenRouterRouteControlFailureCode.ROUTER_METADATA_MISSING
    assert by_id[
        "orroutev1-p03-cache-header-missing-plus-metadata-missing"
    ].actual_failure_code is OpenRouterRouteControlFailureCode.CACHE_HEADER_MISSING
    assert by_id[
        "orroutev1-p04-actual-model-missing-plus-provider-mismatch"
    ].actual_failure_code is OpenRouterRouteControlFailureCode.ACTUAL_MODEL_MISSING
    assert by_id[
        "orroutev1-p05-multi-attempt-plus-model-substitution"
    ].actual_failure_code is OpenRouterRouteControlFailureCode.MULTI_ATTEMPT_ROUTING_OBSERVED


def test_frozen_thresholds_are_exact_and_not_soft() -> None:
    thresholds = FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1
    assert thresholds.cases_total == 63
    assert thresholds.positive_cases_total == 6
    assert thresholds.orthogonal_probes_total == 49
    assert thresholds.precedence_probes_total == 8
    assert thresholds.required_canned_transport_invocations == 26
    assert thresholds.required_invalid_probe_constructions == 0
    assert thresholds.live_enforcement == "NOT_PROVEN"
    assert thresholds.exact_endpoint_response_attestation == "NOT_ESTABLISHED"
    assert thresholds.p17_input_token_bound == "NOT_ESTABLISHED"
    assert thresholds.p18_pricing_record == "NOT_ESTABLISHED"
    assert thresholds.p19_cost_bound == "NOT_ESTABLISHED"
    assert thresholds.maximum_official_response_wire_mapping_violations == 0


def test_manifest_assessment_derives_wire_mapping_falsification_without_writes() -> None:
    assessment = assess_openrouter_official_response_wire_mapping_v1(ROOT)
    assert assessment.assessment_id == (
        "szorwiremappingassessmentv1_"
        "4837280cd07f68b98c73a84c48c59b44fc907b177f46fddfd6ece843f5a20b48"
    )
    assert tuple(item.source_id for item in assessment.source_observations) == (
        "OR-S04-ROUTER-METADATA",
        "OR-S08-OPENAPI",
    )
    assert all(
        item.source_content_bytes is None
        for item in assessment.source_observations
    )
    assert tuple(item.evidence_id for item in assessment.fact_observations) == (
        "ORSPEC-F04",
        "ORSPEC-F05",
    )
    assert assessment.complete_nested_wire_field_names_retained is False
    assert assessment.complete_nested_wire_field_types_retained is False
    assert assessment.official_wire_to_local_normalized_mapping_retained is False
    assert assessment.status == "NOT_ESTABLISHED_FROM_FROZEN_MANIFEST"
    assert official_response_wire_mapping_violation_count_v1(assessment) == 1
    assert official_response_wire_mapping_gate_passes_v1(assessment) is False
    all_other_thresholds_pass = True
    all_thresholds_pass = (
        all_other_thresholds_pass
        and official_response_wire_mapping_gate_passes_v1(assessment)
    )
    assert all_thresholds_pass is False
    hypothesis_status = (
        OpenRouterRouteControlHypothesisStatusV1.SUPPORTED
        if all_thresholds_pass
        else OpenRouterRouteControlHypothesisStatusV1.FALSIFIED
    )
    assert hypothesis_status is OpenRouterRouteControlHypothesisStatusV1.FALSIFIED

    payload = assessment.model_dump(mode="json")
    payload["source_observations"][0]["source_content_bytes"] = 1
    payload["assessment_id"] = None
    with pytest.raises(ValidationError, match="source observations changed"):
        type(assessment).model_validate(payload)


def test_artifact_claim_and_evidence_link_firewalls_are_pure() -> None:
    firewall = FROZEN_OPENROUTER_ROUTE_CONTROL_ARTIFACT_CLAIM_FIREWALL_V1
    forbidden_claims = {
        "live_server_enforcement": "PROVEN",
        "live_no_fallback_proof": "PROVEN",
        "exact_endpoint_response_attestation": "ESTABLISHED",
        "p17_input_token_bound": "ESTABLISHED",
        "p18_pricing_record": "ESTABLISHED",
        "p19_cost_bound": "ESTABLISHED",
        "live_pilot_readiness": "EARNED",
        "actual_openrouter_availability": "ESTABLISHED",
        "real_provider_execution": True,
    }
    for field, forbidden_value in forbidden_claims.items():
        payload = firewall.model_dump(mode="json")
        payload[field] = forbidden_value
        with pytest.raises(ValidationError):
            OpenRouterRouteControlArtifactClaimFirewallV1.model_validate(payload)

    prepared = prepare_openrouter_route_request_v1(repository_root=ROOT)
    binding = prepared.route_control_policy.specification_binding
    receipt = prepared.request_intent_receipt
    assert receipt is not None
    _validate_frozen_evidence_record_links_v1(
        receipt.frozen_evidence_record_ids,
        binding,
        receipt,
    )
    with pytest.raises(ContractValidationError, match="frozen evidence links changed"):
        _validate_frozen_evidence_record_links_v1(
            ("ORSPEC-F99",),
            binding,
            receipt,
        )


def test_scoped_inventory_is_complete_and_current() -> None:
    snapshot = capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    expected_count = sum(len(paths) for _, paths in FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1)
    assert len(snapshot.rows) == expected_count
    file_rows = tuple(
        row
        for row in snapshot.rows
        if openrouter_provenance_record_v1(row.reference) is None
    )
    provenance_rows = tuple(
        row
        for row in snapshot.rows
        if openrouter_provenance_record_v1(row.reference) is not None
    )
    assert len(provenance_rows) == len(FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1)
    assert len(file_rows) + len(provenance_rows) == expected_count
    assert all(row.sha256 == hashlib.sha256((ROOT / row.reference).read_bytes()).hexdigest() for row in file_rows)
    assert all(
        row.sha256 == openrouter_provenance_record_v1(row.reference).record_sha256
        for row in provenance_rows
    )
    inventoried = {row.reference for row in snapshot.rows}
    assert {
        "backend/dialogues/socrates_zero/baseline.py",
        "backend/dialogues/socrates_zero/puct.py",
        "backend/dialogues/socrates_zero/value.py",
        "backend/dialogues/ced_search_value_v1_bestofn.py",
        "backend/dialogues/ced_canonical_successor_frozen_core_v2.py",
        "backend/dialogues/ced_canonical_successor_recording_contracts.py",
    } <= inventoried


def test_all_ten_historical_hashes_and_core_source_are_exact() -> None:
    evidence = verify_openrouter_route_control_historical_hashes_v1(ROOT)
    assert len(evidence) == 10
    assert all(item.matches for item in evidence)


def test_evaluation_module_is_import_inert_and_has_no_production_adapter_wiring() -> None:
    path = (
        ROOT
        / "backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {
        "socket",
        "http.client",
        "urllib.request",
        "backend.dialogues.openrouter_provider",
        "backend.dialogues.ced",
    }
    assert imported.isdisjoint(forbidden)
    assert "OpenRouterProviderAdapter" not in source
    assert "Authorization" not in source
    assert "OPENROUTER_API_KEY" not in source


def test_authoritative_artifact_is_canonical_and_preserves_falsification_if_present() -> None:
    path = ROOT / OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    if not path.exists():
        pytest.skip("authoritative artifact is intentionally absent before freeze")
    artifact = load_openrouter_route_control_artifact_v1(path)
    assert path.read_bytes() == render_openrouter_route_control_artifact_v1(artifact)
    assert artifact.metrics.all_thresholds_pass is False
    assert artifact.hypothesis_status.value == "FALSIFIED"
    assert artifact.normalized_canned_schema_is_official_wire_schema is False
    assert artifact.official_response_wire_mapping_status == (
        "NOT_ESTABLISHED_FROM_FROZEN_MANIFEST"
    )
    assert artifact.metrics.official_response_wire_mapping_violations == 1

    forbidden_claims = {
        "live_server_enforcement": "PROVEN",
        "live_no_fallback_proof": "PROVEN",
        "exact_endpoint_response_attestation": "ESTABLISHED",
        "p17_input_token_bound": "ESTABLISHED",
        "p18_pricing_record": "ESTABLISHED",
        "p19_cost_bound": "ESTABLISHED",
        "live_pilot_readiness": "EARNED",
        "actual_openrouter_availability": "ESTABLISHED",
        "real_provider_execution": True,
    }
    for field, forbidden_value in forbidden_claims.items():
        payload = artifact.model_dump(mode="json")
        payload[field] = forbidden_value
        payload["artifact_id"] = None
        with pytest.raises(ValidationError):
            OpenRouterRouteControlArtifactV1.model_validate(payload)

    nested_mutations = []
    payload = artifact.model_dump(mode="json")
    payload["request_intent_receipt"]["p17_input_token_bound"] = "ESTABLISHED"
    nested_mutations.append(payload)
    payload = artifact.model_dump(mode="json")
    payload["route_policy_receipt"]["live_pilot_readiness"] = "EARNED"
    nested_mutations.append(payload)
    payload = artifact.model_dump(mode="json")
    payload["official_response_wire_mapping_assessment"]["source_observations"][0][
        "source_content_bytes"
    ] = 1
    payload["official_response_wire_mapping_assessment"]["assessment_id"] = None
    nested_mutations.append(payload)
    payload = artifact.model_dump(mode="json")
    response_result = next(
        result
        for result in payload["case_results"]
        if result["kind"] == "POSITIVE_RESPONSE"
    )
    response_result["route_attestation"]["live_pilot_readiness"] = "EARNED"
    nested_mutations.append(payload)
    for payload in nested_mutations:
        payload["artifact_id"] = None
        with pytest.raises(ValidationError):
            OpenRouterRouteControlArtifactV1.model_validate(payload)

    payload = artifact.model_dump(mode="json")
    payload["metrics"]["official_response_wire_mapping_violations"] = 0
    payload["metrics"]["all_thresholds_pass"] = True
    payload["hypothesis_status"] = "SUPPORTED"
    payload["artifact_id"] = None
    with pytest.raises(ValidationError):
        OpenRouterRouteControlArtifactV1.model_validate(payload)

    payload = artifact.model_dump(mode="json")
    payload["frozen_evidence_record_ids"] = ["ORSPEC-F99"]
    payload["artifact_id"] = None
    with pytest.raises(ValidationError, match="frozen evidence links changed"):
        OpenRouterRouteControlArtifactV1.model_validate(payload)


def test_authoritative_aggregate_claim_is_exclusive_before_evaluation(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    claim = _acquire_authoritative_aggregate_claim_v1(artifact_path)
    assert claim.claim_path.is_file()
    assert not artifact_path.exists()
    with pytest.raises(ContractValidationError, match="already exists"):
        _acquire_authoritative_aggregate_claim_v1(artifact_path)
    _validate_authoritative_aggregate_claim_v1(tmp_path, claim)
    assert not claim.claim_path.exists()
    assert claim.consumed_path.is_file()
    with pytest.raises(ContractValidationError, match="unavailable"):
        _validate_authoritative_aggregate_claim_v1(tmp_path, claim)
    with pytest.raises(ContractValidationError, match="already exists"):
        _acquire_authoritative_aggregate_claim_v1(artifact_path)

    with pytest.raises(ContractValidationError, match="exclusive claim"):
        _build_route_control_artifact_v1(
            reverse_case_order=False,
            root=ROOT,
        )


def test_falsified_artifact_cannot_build_or_publish_replay(
    tmp_path: Path,
) -> None:
    artifact = OpenRouterRouteControlArtifactV1.model_construct(
        hypothesis_status=OpenRouterRouteControlHypothesisStatusV1.FALSIFIED,
        metrics=OpenRouterRouteControlMetricsV1.model_construct(
            all_thresholds_pass=False
        ),
    )
    artifact_bytes = b"falsified-minimal-artifact"
    execution, replay_lock = _syntactic_replay_evidence()
    execution_path = tmp_path / "syntactic-execution.json"
    lock_path = tmp_path / "syntactic-lock.json"
    execution_path.write_bytes(
        render_openrouter_route_control_replay_execution_v1(execution)
    )
    lock_path.write_bytes(render_openrouter_route_control_replay_lock_v1(replay_lock))
    assert load_openrouter_route_control_replay_execution_v1(execution_path) == execution
    assert load_openrouter_route_control_replay_lock_v1(lock_path) == replay_lock

    with pytest.raises(ContractValidationError, match="complete support"):
        build_independent_reverse_replay_v1(
            artifact,
            artifact_bytes,
            root=ROOT,
        )
    publish_execution_path = tmp_path / "forbidden-execution.json"
    publish_lock_path = tmp_path / "forbidden-lock.json"
    with pytest.raises(ContractValidationError, match="complete support"):
        publish_openrouter_route_control_replay_once_v1(
            artifact,
            artifact_bytes,
            execution,
            replay_lock,
            execution_path=publish_execution_path,
            lock_path=publish_lock_path,
        )
    assert not publish_execution_path.exists()
    assert not publish_lock_path.exists()


def test_replay_trace_must_derive_from_authoritative_case_results() -> None:
    artifact = OpenRouterRouteControlArtifactV1.model_construct(
        case_results=_evaluate_frozen_cases()
    )
    arbitrary_result_ids = ("szorroutecaseresultv1_" + "0" * 64,) * 63
    execution, _ = _syntactic_replay_evidence(
        ordered_result_ids=arbitrary_result_ids,
    )
    with pytest.raises(ContractValidationError, match="not derived"):
        _validate_replay_result_trace_crosslink_v1(artifact, execution)


def test_replay_execution_and_lock_bind_canonical_artifact_if_present() -> None:
    artifact_path = ROOT / OPENROUTER_ROUTE_CONTROL_ARTIFACT_RELATIVE_PATH_V1
    execution_path = ROOT / OPENROUTER_ROUTE_CONTROL_REPLAY_EXECUTION_RELATIVE_PATH_V1
    lock_path = ROOT / OPENROUTER_ROUTE_CONTROL_REPLAY_LOCK_RELATIVE_PATH_V1
    if artifact_path.exists():
        artifact = load_openrouter_route_control_artifact_v1(artifact_path)
        if artifact.hypothesis_status.value == "FALSIFIED":
            assert not execution_path.exists()
            assert not lock_path.exists()
            return
    if not execution_path.exists() or not lock_path.exists():
        pytest.skip("replay evidence is intentionally absent before replay")
    execution_bytes = execution_path.read_bytes()
    execution = json.loads(execution_bytes)
    lock = json.loads(lock_path.read_bytes())
    assert execution["semantic_equality"] is True
    assert execution["artifact_id_equality"] is True
    assert execution["byte_identity"] is True
    assert lock["replay_execution_sha256"] == hashlib.sha256(execution_bytes).hexdigest()
    assert lock["semantic_equality"] is True
    assert lock["artifact_id_equality"] is True
    assert lock["byte_identity"] is True

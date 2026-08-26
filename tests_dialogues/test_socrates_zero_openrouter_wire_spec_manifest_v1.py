"""Offline tests for OpenRouter wire specification manifest v1."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import ContractValidationError, stable_contract_id
from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v1 import (
    FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1,
    MANDATORY_RELATIONSHIPS_V1,
    OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1,
    OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1,
    OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1,
    OpenRouterWireEnvelopeKindV1,
    OpenRouterWireEvidenceStatusV1,
    OpenRouterWireEvidenceStrengthV1,
    OpenRouterWireFactRecordV1,
    OpenRouterWireHypothesisStatusV1,
    OpenRouterWireJsonTypeV1,
    OpenRouterWireMappingRecordV1,
    OpenRouterWireNullabilityV1,
    OpenRouterWirePresenceRuleV1,
    OpenRouterWireProviderGranularityV1,
    OpenRouterWireRelationshipAssessmentV1,
    OpenRouterWireRelationshipV1,
    OpenRouterWireSpecificationManifestV1,
    build_openrouter_wire_manifest_validation_v1,
    build_openrouter_wire_specification_manifest_v1,
    evaluate_openrouter_wire_manifest_sufficiency_v1,
    render_contract_v1,
    sha256_bytes_v1,
)
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1,
    OpenRouterWireRetrievalLogV1,
)
from scripts.build_socrates_zero_openrouter_wire_spec_manifest_v1 import (
    PREDECESSOR_MANIFEST_V0_RELATIVE_PATH,
    SEALED_ROUTE_CONTROLS_V1_RELATIVE_PATH,
    build_manifest_and_validation,
    revalidate_manifest_evidence,
)


REPO = Path(__file__).resolve().parents[1]


def _load_log(root: Path = REPO) -> tuple[OpenRouterWireRetrievalLogV1, bytes]:
    rendered = (root / OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1).read_bytes()
    return OpenRouterWireRetrievalLogV1.model_validate_json(rendered), rendered


def _assert_id(value: object, field: str, prefix: str) -> None:
    payload = value.model_dump(mode="json")  # type: ignore[attr-defined]
    payload.pop(field)
    assert getattr(value, field) == stable_contract_id(prefix, payload)


def test_actual_failed_retrieval_builds_honest_falsified_manifest() -> None:
    log, log_bytes = _load_log()
    manifest = build_openrouter_wire_specification_manifest_v1(
        retrieval_log=log,
        retrieval_log_sha256=sha256_bytes_v1(log_bytes),
    )
    metrics = evaluate_openrouter_wire_manifest_sufficiency_v1(manifest)
    validation = build_openrouter_wire_manifest_validation_v1(
        manifest=manifest,
        manifest_sha256=sha256_bytes_v1(render_contract_v1(manifest)),
        retrieval_log=log,
    )

    assert len(manifest.source_evidence_records) == 6
    assert all(not item.source_inspectable for item in manifest.source_evidence_records)
    assert all(item.retrieval_error_code == "NETWORK_ERROR" for item in manifest.source_evidence_records)
    assert manifest.fact_records == ()
    assert manifest.mapping_records == ()
    assert manifest.fixture_blueprints == ()
    assert tuple(item.relationship for item in manifest.relationship_assessments) == MANDATORY_RELATIONSHIPS_V1
    assert all(
        item.status is OpenRouterWireEvidenceStatusV1.NOT_ESTABLISHED
        for item in manifest.relationship_assessments
    )
    assert manifest.provider_granularity is OpenRouterWireProviderGranularityV1.UNKNOWN
    assert metrics.source_count == 6
    assert metrics.retained_source_count == 0
    assert metrics.failed_source_count == 6
    assert metrics.established_relationship_count == 0
    assert metrics.not_established_relationship_count == 14
    assert not metrics.all_thresholds_pass
    assert "OFFICIAL_DOCUMENT_RETRIEVAL_FAILED" in metrics.failure_reasons
    assert "MANDATORY_RELATIONSHIPS_NOT_ESTABLISHED" in metrics.failure_reasons
    assert validation.hypothesis_status is OpenRouterWireHypothesisStatusV1.FALSIFIED
    assert validation.external_document_fetches == 6
    assert validation.authenticated_api_calls == 0
    assert validation.credential_accesses == 0
    assert validation.provider_inference_calls == 0
    assert validation.model_executions == 0
    assert validation.paid_requests == 0
    assert validation.ced_runtime_tool_calls == 0
    _assert_id(manifest, "manifest_id", "szorwirespecmanifestv1")
    _assert_id(metrics, "metrics_id", "szorwiresufficiencymetricsv1")
    _assert_id(validation, "validation_id", "szorwiremanifestvalidationv1")


def test_positive_fact_and_lossless_mapping_contracts_are_strict() -> None:
    fact = OpenRouterWireFactRecordV1(
        official_path="$.openrouter_metadata.attempt",
        envelope_kind=OpenRouterWireEnvelopeKindV1.SUCCESS,
        json_type=OpenRouterWireJsonTypeV1.INTEGER,
        presence_rule=OpenRouterWirePresenceRuleV1.OPTIONAL,
        nullability=OpenRouterWireNullabilityV1.NON_NULL,
        cardinality="ONE",
        child_schema="NONE",
        semantic_meaning="One documented attempt index.",
        source_evidence_ids=("szorwiresourceevidencev1_" + "1" * 64,),
        source_anchors=("Field Reference",),
        strength=OpenRouterWireEvidenceStrengthV1.DIRECTLY_DOCUMENTED,
        limitations="Synthetic contract test only.",
    )
    mapping = OpenRouterWireMappingRecordV1(
        official_path=fact.official_path,
        internal_target_field="attempt",
        transformation_rule="IDENTITY_INTEGER",
        lossless=True,
        missing_field_behavior="FAIL_CLOSED",
        invalid_type_behavior="FAIL_CLOSED",
        unknown_field_behavior="NON_AUTHORITATIVE",
        authority_scope="ROUTE_METADATA_ONLY",
        source_fact_ids=(fact.fact_id or "",),
        strength=OpenRouterWireEvidenceStrengthV1.DERIVED_LOSSLESSLY,
    )
    _assert_id(fact, "fact_id", "szorwirefactv1")
    _assert_id(mapping, "mapping_id", "szorwiremappingv1")

    payload = fact.model_dump(mode="json")
    payload["fact_id"] = None
    payload["json_type"] = OpenRouterWireJsonTypeV1.UNKNOWN.value
    with pytest.raises(ValidationError, match="positive wire fact has unknown"):
        OpenRouterWireFactRecordV1.model_validate(payload)

    payload = mapping.model_dump(mode="json")
    payload["mapping_id"] = None
    payload["lossless"] = False
    with pytest.raises(ValidationError, match="lossless mapping strength"):
        OpenRouterWireMappingRecordV1.model_validate(payload)


def test_manifest_rejects_missing_relationships_and_forged_ids() -> None:
    log, log_bytes = _load_log()
    manifest = build_openrouter_wire_specification_manifest_v1(
        retrieval_log=log,
        retrieval_log_sha256=sha256_bytes_v1(log_bytes),
    )
    payload = manifest.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["relationship_assessments"] = payload["relationship_assessments"][:-1]
    with pytest.raises(ValidationError, match="relationship registry is incomplete"):
        OpenRouterWireSpecificationManifestV1.model_validate(payload)

    payload = manifest.model_dump(mode="json")
    payload["manifest_id"] = "szorwirespecmanifestv1_" + "0" * 64
    with pytest.raises(ValidationError, match="manifest ID mismatch"):
        OpenRouterWireSpecificationManifestV1.model_validate(payload)


def test_thresholds_are_content_addressed_and_require_complete_evidence() -> None:
    thresholds = FROZEN_OPENROUTER_WIRE_SUFFICIENCY_THRESHOLDS_V1
    assert thresholds.required_source_count == 6
    assert thresholds.required_retained_source_count == 6
    assert thresholds.required_relationship_count == 14
    assert thresholds.required_established_relationship_count == 14
    assert thresholds.maximum_failed_source_count == 0
    assert thresholds.maximum_not_established_relationship_count == 0
    assert thresholds.maximum_assumption_based_mapping_count == 0
    assert thresholds.require_exact_endpoint_response_identity
    assert thresholds.require_actual_served_model_identity
    _assert_id(thresholds, "thresholds_id", "szorwiresufficiencythresholdsv1")


def _prepare_tmp_repo(tmp_path: Path) -> None:
    for relative in (
        PREDECESSOR_MANIFEST_V0_RELATIVE_PATH,
        SEALED_ROUTE_CONTROLS_V1_RELATIVE_PATH,
        OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1,
    ):
        source = REPO / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())


def test_write_once_build_and_offline_revalidation_are_byte_stable(tmp_path: Path) -> None:
    _prepare_tmp_repo(tmp_path)
    manifest, validation, manifest_sha, validation_sha = build_manifest_and_validation(
        tmp_path
    )
    assert validation.hypothesis_status is OpenRouterWireHypothesisStatusV1.FALSIFIED
    manifest_path = tmp_path / OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1
    validation_path = tmp_path / OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == manifest_sha
    assert hashlib.sha256(validation_path.read_bytes()).hexdigest() == validation_sha
    assert OpenRouterWireSpecificationManifestV1.model_validate_json(
        manifest_path.read_bytes()
    ) == manifest
    with pytest.raises(ContractValidationError, match="already exists"):
        build_manifest_and_validation(tmp_path)

    revalidation = revalidate_manifest_evidence(tmp_path)
    assert revalidation.semantic_equality
    assert revalidation.manifest_byte_identity
    assert revalidation.validation_byte_identity
    revalidation_path = tmp_path / OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1
    assert revalidation_path.is_file()
    with pytest.raises(ContractValidationError, match="already exists"):
        revalidate_manifest_evidence(tmp_path)


def test_published_manifest_validation_and_revalidation_are_canonical() -> None:
    manifest_path = REPO / OPENROUTER_WIRE_MANIFEST_RELATIVE_PATH_V1
    validation_path = REPO / OPENROUTER_WIRE_VALIDATION_RELATIVE_PATH_V1
    revalidation_path = REPO / OPENROUTER_WIRE_REVALIDATION_RELATIVE_PATH_V1
    assert manifest_path.is_file()
    assert validation_path.is_file()
    assert revalidation_path.is_file()

    manifest_bytes = manifest_path.read_bytes()
    validation_bytes = validation_path.read_bytes()
    manifest = OpenRouterWireSpecificationManifestV1.model_validate_json(
        manifest_bytes
    )
    from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v1 import (
        OpenRouterWireManifestRevalidationV1,
        OpenRouterWireManifestValidationV1,
    )

    validation = OpenRouterWireManifestValidationV1.model_validate_json(
        validation_bytes
    )
    revalidation = OpenRouterWireManifestRevalidationV1.model_validate_json(
        revalidation_path.read_bytes()
    )
    assert manifest_bytes == render_contract_v1(manifest)
    assert validation_bytes == render_contract_v1(validation)
    assert validation.hypothesis_status is OpenRouterWireHypothesisStatusV1.FALSIFIED
    assert revalidation.source_manifest_id == manifest.manifest_id
    assert revalidation.source_manifest_sha256 == hashlib.sha256(
        manifest_bytes
    ).hexdigest()
    assert revalidation.source_validation_id == validation.validation_id
    assert revalidation.source_validation_sha256 == hashlib.sha256(
        validation_bytes
    ).hexdigest()
    assert revalidation.semantic_equality
    assert revalidation.manifest_id_equality
    assert revalidation.validation_result_equality
    assert revalidation.manifest_byte_identity
    assert revalidation.validation_byte_identity
    assert revalidation.documentation_fetches == 0

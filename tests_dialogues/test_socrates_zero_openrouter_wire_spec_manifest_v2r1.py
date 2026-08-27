from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import ContractValidationError, stable_contract_id
from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v2r1 import (
    FACTS_V2R1,
    FROZEN_MANIFEST_V2R1,
    MANIFEST_RELATIVE_PATH_V2R1,
    MANDATORY_RELATIONSHIPS_V2R1,
    MAPPINGS_V2R1,
    RELATIONSHIPS_V2R1,
    REVALIDATION_RELATIVE_PATH_V2R1,
    SOURCES_V2R1,
    UPSTREAM_COMMIT_V2R1,
    UPSTREAM_REPOSITORY_V2R1,
    VALIDATION_RELATIVE_PATH_V2R1,
    EvidenceStrengthV2R1,
    HypothesisStatusV2R1,
    ManifestV2R1,
    RevalidationV2R1,
    ValidationV2R1,
    RelationshipStatusV2R1,
    RelationshipV2R1,
    SourceRecordV2R1,
    build_validation_v2r1,
    classify_worktree_bytes_against_canonical_v2r1,
    git_blob_sha1_v2r1,
    render_contract_v2r1,
    sha256_bytes_v2r1,
    verify_source_snapshots_v2r1,
)
from scripts.build_socrates_zero_openrouter_wire_spec_manifest_v2r1 import (
    build_manifest_and_validation_v2r1,
    revalidate_manifest_evidence_v2r1,
)

REPO = Path(__file__).resolve().parents[1]


def test_v2r1_is_exactly_six_pinned_official_sources() -> None:
    assert len(SOURCES_V2R1) == 6
    assert {s.repository for s in SOURCES_V2R1} == {UPSTREAM_REPOSITORY_V2R1}
    assert {s.commit_sha for s in SOURCES_V2R1} == {UPSTREAM_COMMIT_V2R1}
    assert len({s.upstream_path for s in SOURCES_V2R1}) == 6
    assert verify_source_snapshots_v2r1(REPO) == ()


def test_v2r1_source_sha256_and_git_blob_identity_are_recomputed() -> None:
    for source in SOURCES_V2R1:
        data = (REPO / source.evidence_path).read_bytes()
        assert len(data) == source.byte_length
        assert hashlib.sha256(data).hexdigest() == source.sha256
        assert git_blob_sha1_v2r1(data) == source.git_blob_sha


def test_v2r1_records_are_content_addressed() -> None:
    for item, field, prefix in [
        *[(s, "source_id", "szorwiresourcev2r1") for s in SOURCES_V2R1],
        *[(f, "fact_id", "szorwirefactv2r1") for f in FACTS_V2R1],
        *[(m, "mapping_id", "szorwiremappingv2r1") for m in MAPPINGS_V2R1],
        *[(r, "assessment_id", "szorwirerelationshipv2r1") for r in RELATIONSHIPS_V2R1],
    ]:
        payload = item.model_dump(mode="json")
        payload.pop(field)
        assert getattr(item, field) == stable_contract_id(prefix, payload)


def test_v2r1_manifest_has_no_assumption_or_repo_convention_authority() -> None:
    assert FROZEN_MANIFEST_V2R1.assumption_based_authoritative_mapping_count == 0
    assert FROZEN_MANIFEST_V2R1.repository_convention_authoritative_mapping_count == 0
    assert all(m.lossless for m in MAPPINGS_V2R1)
    assert all(
        m.strength in (
            EvidenceStrengthV2R1.DIRECTLY_DOCUMENTED,
            EvidenceStrengthV2R1.DERIVED_LOSSLESSLY,
        )
        for m in MAPPINGS_V2R1
    )


def test_v2r1_relationship_registry_is_complete_and_exact_endpoint_is_unavailable() -> None:
    assert tuple(r.relationship for r in RELATIONSHIPS_V2R1) == MANDATORY_RELATIONSHIPS_V2R1
    exact_endpoint = next(
        r for r in RELATIONSHIPS_V2R1
        if r.relationship is RelationshipV2R1.EXACT_ENDPOINT_RESPONSE_IDENTITY
    )
    assert exact_endpoint.status is RelationshipStatusV2R1.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    assert FROZEN_MANIFEST_V2R1.exact_endpoint_response_identity == "NOT_ESTABLISHED"


def test_v2r1_actual_model_is_grounded_in_response_model() -> None:
    fact = next(f for f in FACTS_V2R1 if f.diagnostic_label == "served_model")
    mapping = next(m for m in MAPPINGS_V2R1 if m.internal_target == "response.actual_served_model")
    assert fact.official_path == "$.model"
    assert mapping.official_path == "$.model"
    assert mapping.fact_ids == (fact.fact_id,)
    assert FROZEN_MANIFEST_V2R1.actual_served_model_identity == "ESTABLISHED"


def test_requested_model_cannot_substitute_for_actual_model() -> None:
    requested = next(f for f in FACTS_V2R1 if f.diagnostic_label == "requested")
    served = next(f for f in FACTS_V2R1 if f.diagnostic_label == "served_model")
    assert requested.official_path == "$.openrouter_metadata.requested"
    assert served.official_path == "$.model"
    assert requested.fact_id != served.fact_id
    assert all(m.official_path != requested.official_path for m in MAPPINGS_V2R1 if m.internal_target == "response.actual_served_model")


def test_cache_hit_is_not_inferred_from_metadata_absence() -> None:
    cache = next(r for r in RELATIONSHIPS_V2R1 if r.relationship is RelationshipV2R1.CACHE_ATTESTATION)
    assert cache.status is RelationshipStatusV2R1.ESTABLISHED
    assert "headers" in cache.reason.lower()
    assert "absence alone" in cache.reason.lower()


def test_attempts_absence_is_preserved_by_mapping_policy() -> None:
    mapping = next(m for m in MAPPINGS_V2R1 if m.internal_target == "router.attempts")
    assert mapping.transformation == "IDENTITY"
    assert "PRESERVE_ABSENT" in mapping.missing_behavior


def test_unknown_additive_fields_remain_non_authoritative() -> None:
    relation = next(r for r in RELATIONSHIPS_V2R1 if r.relationship is RelationshipV2R1.UNKNOWN_ADDITIVE_FIELD_POLICY)
    assert relation.status is RelationshipStatusV2R1.ESTABLISHED
    assert "non-authoritatively" in relation.reason
    assert all(m.unknown_field_behavior == "PRESERVE_NON_AUTHORITATIVELY" for m in MAPPINGS_V2R1)


def test_forged_source_identity_is_rejected() -> None:
    source = SOURCES_V2R1[0]
    payload = source.model_dump(mode="json")
    payload["source_id"] = "ORWIRE-F01"
    with pytest.raises(ValidationError, match="source record ID mismatch"):
        SourceRecordV2R1.model_validate(payload)


def test_wrong_source_blob_is_detected(tmp_path: Path) -> None:
    source = SOURCES_V2R1[0]
    payload = source.model_dump(mode="json")
    payload["source_id"] = None
    payload["git_blob_sha"] = "0" * 40
    forged = SourceRecordV2R1.model_validate(payload)
    assert forged.git_blob_sha != source.git_blob_sha


def test_manifest_rejects_missing_relationship() -> None:
    payload = FROZEN_MANIFEST_V2R1.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["relationship_assessments"] = payload["relationship_assessments"][:-1]
    with pytest.raises(ValidationError, match="relationship registry"):
        ManifestV2R1.model_validate(payload)


def test_manifest_rejects_exact_endpoint_overclaim() -> None:
    payload = FROZEN_MANIFEST_V2R1.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["exact_endpoint_response_identity"] = "ESTABLISHED"
    with pytest.raises(ValidationError):
        ManifestV2R1.model_validate(payload)


def test_manifest_rejects_dangling_fact_source() -> None:
    payload = FROZEN_MANIFEST_V2R1.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["fact_records"][0]["fact_id"] = None
    payload["fact_records"][0]["source_ids"] = ["missing"]
    with pytest.raises(ValidationError, match="dangling source"):
        ManifestV2R1.model_validate(payload)


def test_validation_is_supported_with_zero_external_activity() -> None:
    validation = build_validation_v2r1(REPO)
    assert validation.hypothesis_status is HypothesisStatusV2R1.SUPPORTED
    assert validation.failure_reasons == ()
    assert validation.source_count == 6
    assert validation.fact_count == len(FACTS_V2R1)
    assert validation.mapping_count == len(MAPPINGS_V2R1)
    assert validation.relationship_count == len(MANDATORY_RELATIONSHIPS_V2R1)
    assert validation.documented_unavailable_relationship_count == 1
    assert validation.authenticated_api_calls == 0
    assert validation.credential_accesses == 0
    assert validation.provider_inference_calls == 0
    assert validation.model_executions == 0
    assert validation.ced_application_invocations == 0


def test_crlf_is_classified_without_mutating_canonical_bytes() -> None:
    canonical = b"alpha\nbeta\n"
    crlf = b"alpha\r\nbeta\r\n"
    assert classify_worktree_bytes_against_canonical_v2r1(canonical, canonical) == "NONE"
    assert classify_worktree_bytes_against_canonical_v2r1(canonical, crlf) == "CRLF_NORMALIZATION"
    assert classify_worktree_bytes_against_canonical_v2r1(canonical, b"alpha\nchanged\n") == "CONTENT_MUTATION"


def _copy_v2r1_sources(tmp_path: Path) -> None:
    for source in SOURCES_V2R1:
        src = REPO / source.evidence_path
        dst = tmp_path / source.evidence_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())


def test_builder_and_revalidation_are_write_once_and_byte_stable(tmp_path: Path) -> None:
    _copy_v2r1_sources(tmp_path)
    manifest, validation, manifest_sha, validation_sha = build_manifest_and_validation_v2r1(tmp_path)
    assert validation.hypothesis_status is HypothesisStatusV2R1.SUPPORTED
    manifest_path = tmp_path / MANIFEST_RELATIVE_PATH_V2R1
    validation_path = tmp_path / VALIDATION_RELATIVE_PATH_V2R1
    assert manifest_path.read_bytes() == render_contract_v2r1(manifest)
    assert validation_path.read_bytes() == render_contract_v2r1(validation)
    assert sha256_bytes_v2r1(manifest_path.read_bytes()) == manifest_sha
    assert sha256_bytes_v2r1(validation_path.read_bytes()) == validation_sha
    with pytest.raises(ContractValidationError, match="already exists"):
        build_manifest_and_validation_v2r1(tmp_path)
    revalidation = revalidate_manifest_evidence_v2r1(tmp_path)
    assert revalidation.semantic_equality
    assert revalidation.manifest_id_equality
    assert revalidation.validation_result_equality
    assert revalidation.manifest_byte_identity
    assert revalidation.validation_byte_identity
    revalidation_path = tmp_path / REVALIDATION_RELATIVE_PATH_V2R1
    assert revalidation_path.read_bytes() == render_contract_v2r1(revalidation)
    with pytest.raises(ContractValidationError, match="already exists"):
        revalidate_manifest_evidence_v2r1(tmp_path)


def test_published_v2r1_artifacts_are_canonical_and_match_frozen_contracts() -> None:
    manifest_path = REPO / MANIFEST_RELATIVE_PATH_V2R1
    validation_path = REPO / VALIDATION_RELATIVE_PATH_V2R1
    revalidation_path = REPO / REVALIDATION_RELATIVE_PATH_V2R1
    assert manifest_path.is_file()
    assert validation_path.is_file()
    assert revalidation_path.is_file()

    manifest_bytes = manifest_path.read_bytes()
    validation_bytes = validation_path.read_bytes()
    revalidation_bytes = revalidation_path.read_bytes()

    persisted_manifest = ManifestV2R1.model_validate_json(manifest_bytes)
    persisted_validation = ValidationV2R1.model_validate_json(validation_bytes)
    persisted_revalidation = RevalidationV2R1.model_validate_json(revalidation_bytes)

    assert persisted_manifest == FROZEN_MANIFEST_V2R1
    assert manifest_bytes == render_contract_v2r1(FROZEN_MANIFEST_V2R1)

    recomputed_validation = build_validation_v2r1(REPO, FROZEN_MANIFEST_V2R1)
    assert persisted_validation == recomputed_validation
    assert validation_bytes == render_contract_v2r1(recomputed_validation)

    assert persisted_revalidation.source_manifest_id == FROZEN_MANIFEST_V2R1.manifest_id
    assert persisted_revalidation.source_manifest_sha256 == sha256_bytes_v2r1(manifest_bytes)
    assert persisted_revalidation.source_validation_id == recomputed_validation.validation_id
    assert persisted_revalidation.source_validation_sha256 == sha256_bytes_v2r1(validation_bytes)
    assert persisted_revalidation.recomputed_manifest_id == FROZEN_MANIFEST_V2R1.manifest_id
    assert persisted_revalidation.recomputed_validation_id == recomputed_validation.validation_id
    assert persisted_revalidation.semantic_equality
    assert persisted_revalidation.manifest_id_equality
    assert persisted_revalidation.validation_result_equality
    assert persisted_revalidation.manifest_byte_identity
    assert persisted_revalidation.validation_byte_identity
    assert revalidation_bytes == render_contract_v2r1(persisted_revalidation)

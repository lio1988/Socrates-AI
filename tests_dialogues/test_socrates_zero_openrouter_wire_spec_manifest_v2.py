from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_wire_spec_manifest_v2 import (
    FACTS_V2,
    FROZEN_MANIFEST_V2,
    FROZEN_VALIDATION_V2,
    FROZEN_REVALIDATION_V2,
    MANIFEST_RELATIVE_PATH_V2,
    MAPPINGS_V2,
    RELATIONSHIPS_V2,
    SOURCES_V2,
    VALIDATION_RELATIVE_PATH_V2,
    REVALIDATION_RELATIVE_PATH_V2,
    HypothesisStatusV2,
    ManifestV2,
    ProviderGranularityV2,
    RelationshipStatusV2,
    RelationshipV2,
    ValidationV2,
    RevalidationV2,
    build_validation_v2,
    build_revalidation_v2,
    render_contract_v2,
)
from scripts.build_socrates_zero_openrouter_wire_spec_manifest_v2 import publish


REPO = Path(__file__).resolve().parents[1]


def test_v2_preserves_exactly_six_pinned_official_source_roles() -> None:
    assert len(SOURCES_V2) == 6
    assert len({item.source_key for item in SOURCES_V2}) == 6
    assert all(item.repository == "OpenRouterTeam/docs" for item in SOURCES_V2)
    assert all(item.commit_sha == "4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db" for item in SOURCES_V2)
    assert all(item.inspectable_url.startswith("https://github.com/OpenRouterTeam/docs/blob/4a5a458") for item in SOURCES_V2)
    assert SOURCES_V2[0].path == "openapi/openapi.yaml"
    assert SOURCES_V2[0].extraction_mode == "PINNED_GIT_BLOB_METADATA_ONLY"
    assert all(item.byte_length > 0 for item in SOURCES_V2)


def test_wire_facts_cover_documented_official_paths_without_local_aliases() -> None:
    paths = {fact.official_path for fact in FACTS_V2}
    required = {
        "$.openrouter_metadata",
        "$.openrouter_metadata.requested",
        "$.openrouter_metadata.strategy",
        "$.openrouter_metadata.region",
        "$.openrouter_metadata.summary",
        "$.openrouter_metadata.attempt",
        "$.openrouter_metadata.is_byok",
        "$.openrouter_metadata.endpoints.total",
        "$.openrouter_metadata.endpoints.available[].provider",
        "$.openrouter_metadata.endpoints.available[].model",
        "$.openrouter_metadata.endpoints.available[].selected",
        "$.openrouter_metadata.params",
        "$.openrouter_metadata.attempts[].status",
        "$.openrouter_metadata.pipeline[].data",
        "$.model",
        "$headers.X-OpenRouter-Cache-Status",
    }
    assert required <= paths
    assert "$.openrouter_metadata.requested_model" not in paths
    assert "$.openrouter_metadata.actual_model" not in paths
    assert "$.openrouter_metadata.routing_strategy" not in paths
    assert "$.openrouter_metadata.fallback_observed" not in paths


def test_all_mappings_are_lossless_and_source_fact_bound() -> None:
    fact_ids = {fact.fact_id for fact in FACTS_V2}
    assert len(MAPPINGS_V2) == 12
    assert all(mapping.lossless for mapping in MAPPINGS_V2)
    assert all(mapping.source_fact_ids and set(mapping.source_fact_ids) <= fact_ids for mapping in MAPPINGS_V2)
    targets = {mapping.internal_target for mapping in MAPPINGS_V2}
    assert "actual_model" in targets
    assert "requested_provider_only" not in targets
    assert "exact_endpoint_response_id" not in targets


def test_relationship_registry_is_complete_and_honestly_limited() -> None:
    assert tuple(item.relationship for item in RELATIONSHIPS_V2) == tuple(RelationshipV2)
    assert sum(item.status is RelationshipStatusV2.ESTABLISHED for item in RELATIONSHIPS_V2) == 13
    exact = next(item for item in RELATIONSHIPS_V2 if item.relationship is RelationshipV2.EXACT_ENDPOINT_RESPONSE_IDENTITY)
    assert exact.status is RelationshipStatusV2.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    actual = next(item for item in RELATIONSHIPS_V2 if item.relationship is RelationshipV2.ACTUAL_SERVED_MODEL_IDENTITY)
    assert actual.status is RelationshipStatusV2.ESTABLISHED
    assert FROZEN_MANIFEST_V2.provider_granularity is ProviderGranularityV2.HUMAN_DISPLAY_NAME


def test_manifest_supports_wire_mapping_but_not_live_authorization() -> None:
    manifest = FROZEN_MANIFEST_V2
    validation = FROZEN_VALIDATION_V2
    assert manifest.wire_mapping_v2_authorization_earned
    assert manifest.live_pilot_readiness == "NOT_EARNED"
    assert manifest.p17_input_token_bound == "NOT_ESTABLISHED"
    assert manifest.p18_pricing_record == "NOT_ESTABLISHED"
    assert manifest.p19_cost_bound == "NOT_ESTABLISHED"
    assert validation.hypothesis_status is HypothesisStatusV2.SUPPORTED
    assert validation.all_mapping_requirements_pass
    assert validation.exact_endpoint_overclaim_count == 0
    assert validation.live_pilot_readiness == "NOT_EARNED"


def test_manifest_rejects_exact_endpoint_overclaim() -> None:
    payload = FROZEN_MANIFEST_V2.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["relationships"][-2]["status"] = RelationshipStatusV2.ESTABLISHED.value
    payload["exact_endpoint_response_identity"] = RelationshipStatusV2.ESTABLISHED.value
    with pytest.raises(ValidationError):
        ManifestV2.model_validate(payload)


def test_manifest_rejects_seventh_source_and_relationship_reordering() -> None:
    payload = FROZEN_MANIFEST_V2.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["sources"].append(payload["sources"][0])
    with pytest.raises(ValidationError, match="exactly six"):
        ManifestV2.model_validate(payload)

    payload = FROZEN_MANIFEST_V2.model_dump(mode="json")
    payload["manifest_id"] = None
    payload["relationships"][0], payload["relationships"][1] = payload["relationships"][1], payload["relationships"][0]
    with pytest.raises(ValidationError, match="registry"):
        ManifestV2.model_validate(payload)


def test_validation_is_recomputed_from_manifest_bytes() -> None:
    validation = build_validation_v2(FROZEN_MANIFEST_V2)
    assert validation == FROZEN_VALIDATION_V2
    assert validation.manifest_sha256 == hashlib.sha256(render_contract_v2(FROZEN_MANIFEST_V2)).hexdigest()
    assert ValidationV2.model_validate_json(render_contract_v2(validation)) == validation


def test_write_once_publication_and_published_files_are_canonical(tmp_path: Path) -> None:
    manifest_path, validation_path, revalidation_path = publish(tmp_path)
    assert manifest_path.read_bytes() == render_contract_v2(FROZEN_MANIFEST_V2)
    assert validation_path.read_bytes() == render_contract_v2(FROZEN_VALIDATION_V2)
    assert revalidation_path.read_bytes() == render_contract_v2(FROZEN_REVALIDATION_V2)
    with pytest.raises(ContractValidationError, match="already exists"):
        publish(tmp_path)

    published_manifest = REPO / MANIFEST_RELATIVE_PATH_V2
    published_validation = REPO / VALIDATION_RELATIVE_PATH_V2
    published_revalidation = REPO / REVALIDATION_RELATIVE_PATH_V2
    assert published_manifest.is_file()
    assert published_validation.is_file()
    assert published_revalidation.is_file()
    assert published_manifest.read_bytes() == render_contract_v2(FROZEN_MANIFEST_V2)
    assert published_validation.read_bytes() == render_contract_v2(FROZEN_VALIDATION_V2)
    assert published_revalidation.read_bytes() == render_contract_v2(FROZEN_REVALIDATION_V2)


def test_offline_revalidation_has_zero_additional_document_reads() -> None:
    revalidation = build_revalidation_v2(FROZEN_MANIFEST_V2, FROZEN_VALIDATION_V2)
    assert revalidation == FROZEN_REVALIDATION_V2
    assert revalidation.additional_public_document_reads == 0
    assert revalidation.semantic_equality
    assert revalidation.manifest_byte_identity
    assert revalidation.validation_byte_identity
    assert RevalidationV2.model_validate_json(render_contract_v2(revalidation)) == revalidation

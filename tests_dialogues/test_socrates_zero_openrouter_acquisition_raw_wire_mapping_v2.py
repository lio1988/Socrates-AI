"""Focused locks for OpenRouter raw wire-mapping v2.

The module name starts with ``test_socrates_zero_openrouter_acquisition`` so the
shared conftest wraps every test below in the acquisition boundary tripwire:
zero network, credential, provider, model, tool or CED activity.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_raw_wire_mapping_cases_v2 import (
    FROZEN_OPENROUTER_WIRE_CASES_V2,
    FROZEN_OPENROUTER_WIRE_CASE_SET_V2,
    OPENROUTER_WIRE_CASE_SET_ID_V2,
    OpenRouterWireCaseKindV2,
    OpenRouterWireExpectedOutcomeV2,
)
from backend.dialogues.socrates_zero.openrouter_raw_wire_mapping_v2 import (
    FROZEN_OPENROUTER_PIPELINE_STAGE_TYPE_ENUM_V2,
    FROZEN_OPENROUTER_ROUTING_STRATEGY_ENUM_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_RELATIVE_PATH_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2,
    OpenRouterNormalizedWireMappingV2,
    OpenRouterRawWireObservationV2,
    OpenRouterWireCacheStatusV2,
    OpenRouterWireEnvelopeKindV2,
    OpenRouterWireEpistemicStatusV2,
    OpenRouterWireFailureCodeV2,
    OpenRouterWireMappingError,
    OpenRouterWirePresenceV2,
    build_openrouter_raw_wire_observation_v2,
    map_openrouter_raw_wire_v2,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "backend" / "dialogues" / "socrates_zero"
MAPPER_SOURCE = RUNTIME_DIR / "openrouter_raw_wire_mapping_v2.py"
CASES_SOURCE = RUNTIME_DIR / "openrouter_raw_wire_mapping_cases_v2.py"

#: Fields that describe the raw observation rather than its meaning.  Two bodies
#: that differ only in whitespace or key order are semantically equal but carry
#: different byte evidence, so these are excluded from semantic comparison.
_RAW_EVIDENCE_FIELDS = frozenset(
    {
        "raw_observation_id",
        "raw_body_sha256",
        "raw_body_length",
        "header_evidence_sha256",
        "mapping_id",
    }
)


def _semantic(mapping: OpenRouterNormalizedWireMappingV2) -> dict:
    dumped = mapping.model_dump(mode="json")
    return {k: v for k, v in dumped.items() if k not in _RAW_EVIDENCE_FIELDS}


def _map(body: bytes, headers=()) -> OpenRouterNormalizedWireMappingV2:
    return map_openrouter_raw_wire_v2(
        build_openrouter_raw_wire_observation_v2(body, headers)
    )


def _success_metadata() -> dict:
    return {
        "requested": "openai/gpt-4.1-mini",
        "strategy": "direct",
        "region": "iad",
        "summary": "available=1",
        "attempt": 1,
        "is_byok": False,
        "endpoints": {
            "total": 1,
            "available": [
                {"provider": "Azure", "model": "openai/gpt-4.1-mini", "selected": True}
            ],
        },
    }


def _success(metadata=None, **extra) -> dict:
    body = {"model": "openai/gpt-4.1-mini", "object": "chat.completion"}
    if metadata is not None:
        body["openrouter_metadata"] = metadata
    body.update(extra)
    return body


# ------------------------------------------------------------- the case set --


@pytest.mark.parametrize(
    "case", FROZEN_OPENROUTER_WIRE_CASES_V2, ids=lambda case: case.case_id
)
def test_every_frozen_case_matches_its_predeclared_expectation(case) -> None:
    if case.expected_outcome is OpenRouterWireExpectedOutcomeV2.REJECTED:
        with pytest.raises(OpenRouterWireMappingError) as raised:
            _map(case.raw_body, case.headers)
        assert raised.value.code is case.expected_failure_code, case.case_id
        return
    mapping = _map(case.raw_body, case.headers)
    dumped = mapping.model_dump(mode="json")
    for name, expected_json in case.expected_fields:
        assert canonical_json(dumped[name]) == expected_json, (case.case_id, name)


def test_case_set_shape_is_frozen() -> None:
    cases = FROZEN_OPENROUTER_WIRE_CASES_V2
    assert len(cases) == 60
    assert sum(c.kind is OpenRouterWireCaseKindV2.POSITIVE for c in cases) == 17
    assert sum(c.kind is OpenRouterWireCaseKindV2.ADVERSARIAL for c in cases) == 43
    assert OPENROUTER_WIRE_CASE_SET_ID_V2 == FROZEN_OPENROUTER_WIRE_CASE_SET_V2.case_set_id
    assert OPENROUTER_WIRE_CASE_SET_ID_V2.startswith("szorwirecasesetv2_")
    assert all(case.authorizing_evidence for case in cases)
    assert all(case.case_fingerprint for case in cases)


def test_adversarial_cases_cover_every_reachable_guard() -> None:
    covered = {
        case.expected_failure_code
        for case in FROZEN_OPENROUTER_WIRE_CASES_V2
        if case.expected_failure_code is not None
    }
    # Every failure code except the observation-digest guard, which cannot be
    # reached through a well-formed case fixture and is locked separately below.
    expected = set(OpenRouterWireFailureCodeV2) - {
        OpenRouterWireFailureCodeV2.OBSERVATION_DIGEST_MISMATCH
    }
    assert expected - covered == set()


# ------------------------------------------------------ metamorphic invariants


def test_unknown_additive_field_does_not_alter_known_authority() -> None:
    baseline = _map(json.dumps(_success(_success_metadata())).encode("utf-8"))
    metadata = _success_metadata()
    metadata["a_new_optional_field"] = {"whatever": [1, 2, 3]}
    injected = _map(json.dumps(_success(metadata, extra_top_level=99)).encode("utf-8"))
    for field in (
        "envelope_kind",
        "actual_served_model",
        "actual_served_model_status",
        "requested_model",
        "routing_strategy",
        "attempt",
        "is_byok",
        "endpoint_collection",
        "cache_status",
        "exact_endpoint_response_identity",
    ):
        assert _semantic(baseline)[field] == _semantic(injected)[field], field
    assert injected.unknown_field_evidence, "unknown field must still be preserved"


def test_json_key_order_does_not_alter_semantics() -> None:
    metadata = _success_metadata()
    forward = json.dumps(_success(metadata), sort_keys=False).encode("utf-8")
    reverse = json.dumps(
        {k: v for k, v in reversed(list(_success(metadata).items()))}
    ).encode("utf-8")
    assert _semantic(_map(forward)) == _semantic(_map(reverse))


def test_whitespace_changes_byte_evidence_but_not_semantics() -> None:
    payload = _success(_success_metadata())
    compact = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    spaced = json.dumps(payload, indent=2).encode("utf-8")
    compact_mapping = _map(compact)
    spaced_mapping = _map(spaced)
    assert _semantic(compact_mapping) == _semantic(spaced_mapping)
    assert compact_mapping.raw_body_sha256 != spaced_mapping.raw_body_sha256
    assert compact_mapping.mapping_id != spaced_mapping.mapping_id


def test_header_name_case_does_not_alter_cache_mapping() -> None:
    body = json.dumps(_success()).encode("utf-8")
    upper = _map(body, (("X-OPENROUTER-CACHE-STATUS", "HIT"),))
    lower = _map(body, (("x-openrouter-cache-status", "HIT"),))
    assert upper.cache_status is OpenRouterWireCacheStatusV2.HIT
    assert lower.cache_status is OpenRouterWireCacheStatusV2.HIT
    assert _semantic(upper) == _semantic(lower)


def test_header_order_does_not_alter_semantics() -> None:
    body = json.dumps(_success()).encode("utf-8")
    forward = _map(
        body,
        (("X-OpenRouter-Cache-Status", "MISS"), ("X-Generation-Id", "gen-1")),
    )
    reverse = _map(
        body,
        (("X-Generation-Id", "gen-1"), ("X-OpenRouter-Cache-Status", "MISS")),
    )
    assert _semantic(forward) == _semantic(reverse)
    assert forward.header_evidence_sha256 != reverse.header_evidence_sha256


def test_identical_duplicate_authority_header_is_accepted() -> None:
    mapping = _map(
        json.dumps(_success()).encode("utf-8"),
        (
            ("X-OpenRouter-Cache-Status", "MISS"),
            ("X-OpenRouter-Cache-Status", "MISS"),
        ),
    )
    assert mapping.cache_status is OpenRouterWireCacheStatusV2.MISS


def test_requested_and_actual_model_never_collapse() -> None:
    metadata = _success_metadata()
    metadata["requested"] = "openai/gpt-4o"
    mapping = _map(
        json.dumps(_success(metadata, model="anthropic/claude-sonnet-4")).encode("utf-8")
    )
    assert mapping.requested_model == "openai/gpt-4o"
    assert mapping.actual_served_model == "anthropic/claude-sonnet-4"

    # Swapping them swaps the respective fields and nothing else.
    metadata["requested"] = "anthropic/claude-sonnet-4"
    swapped = _map(
        json.dumps(_success(metadata, model="openai/gpt-4o")).encode("utf-8")
    )
    assert swapped.requested_model == "anthropic/claude-sonnet-4"
    assert swapped.actual_served_model == "openai/gpt-4o"


def test_requested_model_never_fills_an_absent_actual_model() -> None:
    """An error envelope has no actual served model, whatever metadata says."""
    metadata = _success_metadata()
    metadata["requested"] = "openai/gpt-4.1-mini"
    mapping = _map(
        json.dumps({"error": {"code": 404}, "openrouter_metadata": metadata}).encode(
            "utf-8"
        )
    )
    assert mapping.requested_model == "openai/gpt-4.1-mini"
    assert mapping.actual_served_model is None
    assert mapping.actual_served_model_status is (
        OpenRouterWireEpistemicStatusV2.ABSENT_FROM_OBSERVATION
    )


@pytest.mark.parametrize(
    "injected",
    (
        {"endpoint_slug": "azure/swedencentral"},
        {"endpoint_id": "ep_98765"},
        {"exact_endpoint": "azure/swedencentral"},
        {"provider_slug": "azure"},
    ),
)
def test_endpoint_like_unknown_fields_never_grant_endpoint_authority(
    injected: dict,
) -> None:
    metadata = _success_metadata()
    metadata.update(injected)
    mapping = _map(json.dumps(_success(metadata)).encode("utf-8"))
    assert mapping.exact_endpoint_response_identity is None
    assert mapping.exact_endpoint_response_identity_status is (
        OpenRouterWireEpistemicStatusV2.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    )
    assert any(
        field.path.endswith(tuple(injected)) for field in mapping.unknown_field_evidence
    )


def test_provider_display_name_is_never_an_endpoint_slug() -> None:
    mapping = _map(json.dumps(_success(_success_metadata())).encode("utf-8"))
    candidate = mapping.endpoint_collection.available[0]
    assert candidate.provider_display_name == "Azure"
    assert "/" not in candidate.provider_display_name
    dumped = mapping.model_dump(mode="json")
    assert "azure/swedencentral" not in canonical_json(dumped)


def test_metadata_absence_alone_never_yields_a_cache_hit() -> None:
    mapping = _map(json.dumps(_success()).encode("utf-8"))
    assert mapping.router_metadata_presence is OpenRouterWirePresenceV2.ABSENT
    assert mapping.cache_status is None
    assert mapping.cache_status_presence is OpenRouterWirePresenceV2.ABSENT


def test_exact_endpoint_identity_cannot_be_given_a_value() -> None:
    mapping = _map(json.dumps(_success(_success_metadata())).encode("utf-8"))
    payload = mapping.model_dump(mode="json")
    payload.pop("mapping_id")
    payload["exact_endpoint_response_identity"] = "azure/swedencentral"
    with pytest.raises(ValidationError):
        OpenRouterNormalizedWireMappingV2.model_validate(payload)


def test_actual_model_status_cannot_overclaim() -> None:
    mapping = _map(json.dumps({"error": {"code": 500}}).encode("utf-8"))
    payload = mapping.model_dump(mode="json")
    payload.pop("mapping_id")
    payload["actual_served_model_status"] = "ESTABLISHED"
    with pytest.raises(ValidationError, match="claims more than the mapping carries"):
        OpenRouterNormalizedWireMappingV2.model_validate(payload)


# ------------------------------------------------------- observation identity


def test_observation_identity_detects_mutated_body_evidence() -> None:
    observation = build_openrouter_raw_wire_observation_v2(b'{"model": "m"}')
    payload = observation.model_dump(mode="python")
    payload["raw_body"] = b'{"model": "other"}'
    with pytest.raises(ValidationError, match="OBSERVATION_DIGEST_MISMATCH"):
        OpenRouterRawWireObservationV2.model_validate(payload)


def test_observation_identity_detects_mutated_header_evidence() -> None:
    observation = build_openrouter_raw_wire_observation_v2(
        b'{"model": "m"}', (("X-Generation-Id", "gen-1"),)
    )
    payload = observation.model_dump(mode="python")
    payload["headers"] = ({"name": "X-Generation-Id", "value": "gen-2"},)
    with pytest.raises(ValidationError, match="OBSERVATION_DIGEST_MISMATCH"):
        OpenRouterRawWireObservationV2.model_validate(payload)


def test_observation_refuses_credential_material() -> None:
    with pytest.raises(ValidationError, match="Authorization"):
        build_openrouter_raw_wire_observation_v2(
            b'{"model": "m"}', (("authorization", "Bearer sk-or-secret"),)
        )


def test_mapper_requires_the_exact_observation_contract() -> None:
    with pytest.raises(ContractValidationError, match="exact raw observation"):
        map_openrouter_raw_wire_v2({"raw_body": b"{}"})


# --------------------------------------------------------------- provenance --


def _imported_modules(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(("." * node.level) + (node.module or ""))
    return modules


def test_v2_does_not_depend_on_historical_canned_shapes() -> None:
    forbidden_reference = "openrouter_acquisition" + "_cases"
    for source_path in (MAPPER_SOURCE, CASES_SOURCE):
        modules = _imported_modules(source_path)
        assert not any(forbidden_reference in module for module in modules)
        assert not any("route_controls" in module for module in modules)
        assert not any("acquisition" in module for module in modules)
        source = source_path.read_text(encoding="utf-8")
        assert forbidden_reference not in source
        assert "FROZEN_OPENROUTER_ADAPTER" not in source
        assert "FROZEN_OPENROUTER_ROUTE_CONTROL" not in source


def test_mapper_imports_only_contract_infrastructure() -> None:
    assert _imported_modules(MAPPER_SOURCE) == {
        "__future__",
        "hashlib",
        "json",
        "math",
        "enum",
        "typing",
        "pydantic",
        ".contracts",
    }


def test_mapping_is_bound_to_the_retained_manifest() -> None:
    mapping = _map(json.dumps(_success(_success_metadata())).encode("utf-8"))
    assert mapping.source_manifest_id == OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    assert (
        mapping.source_manifest_sha256
        == OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    )
    manifest_path = ROOT / OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_RELATIVE_PATH_V2
    assert manifest_path.is_file()
    import hashlib

    assert (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        == OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    )


def test_documented_vocabulary_matches_the_retained_openapi() -> None:
    openapi = (
        ROOT
        / "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1"
        / "evidence/sources/openapi.yaml"
    ).read_text(encoding="utf-8")
    for value in FROZEN_OPENROUTER_ROUTING_STRATEGY_ENUM_V2:
        assert f"- '{value}'" in openapi, value
    for value in FROZEN_OPENROUTER_PIPELINE_STAGE_TYPE_ENUM_V2:
        assert f"- '{value}'" in openapi, value


def test_strategy_enum_is_closed_but_stage_type_enum_is_open() -> None:
    """The additive statement covers stage types, not strategy values."""
    metadata = _success_metadata()
    metadata["strategy"] = "not-a-documented-strategy"
    with pytest.raises(OpenRouterWireMappingError) as raised:
        _map(json.dumps(_success(metadata)).encode("utf-8"))
    assert raised.value.code is OpenRouterWireFailureCodeV2.STRATEGY_NOT_DOCUMENTED

    metadata = _success_metadata()
    metadata["pipeline"] = [{"type": "not-a-documented-stage", "name": "future"}]
    mapping = _map(json.dumps(_success(metadata)).encode("utf-8"))
    assert mapping.pipeline[0].stage_type_is_documented is False
    assert mapping.pipeline[0].stage_type == "not-a-documented-stage"


def test_error_envelope_metadata_is_not_held_to_the_strict_required_set() -> None:
    """The documented 404 example omits region, summary and is_byok."""
    partial = {"requested": "openai/gpt-4o-mini", "strategy": "direct", "attempt": 0}
    mapping = _map(
        json.dumps({"error": {"code": 404}, "openrouter_metadata": partial}).encode(
            "utf-8"
        )
    )
    assert mapping.envelope_kind is OpenRouterWireEnvelopeKindV2.ERROR
    assert mapping.region_presence is OpenRouterWirePresenceV2.ABSENT
    assert mapping.summary is None

    # The same object on a success envelope is refused.
    with pytest.raises(OpenRouterWireMappingError) as raised:
        _map(json.dumps(_success(partial)).encode("utf-8"))
    assert raised.value.code is (
        OpenRouterWireFailureCodeV2.METADATA_REQUIRED_FIELD_ABSENT
    )


def test_endpoint_total_is_reported_not_reconciled() -> None:
    """No total == len(available) invariant is invented."""
    metadata = _success_metadata()
    metadata["endpoints"] = {"total": 7, "available": []}
    mapping = _map(json.dumps(_success(metadata)).encode("utf-8"))
    assert mapping.endpoint_collection.total == 7
    assert mapping.endpoint_collection.available == ()

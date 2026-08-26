from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_contracts import (
    FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1,
    FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_RELEVANT_FACT_DIGESTS_V1,
    OPENROUTER_RELEVANT_FACT_IDS_V1,
    OPENROUTER_ROUTE_MODEL_V1,
    OPENROUTER_SPECIFICATION_MANIFEST_ID_V1,
    OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1,
    OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1,
    OpenRouterDeferredStatusV1,
    OpenRouterOfflineProofStatusV1,
    OpenRouterPreparedRouteRequestV1,
    OpenRouterRequestIntentReceiptV1,
    OpenRouterRouteControlPolicyV1,
    OpenRouterRouteIntentV1,
    default_openrouter_route_control_policy_v1,
    verify_openrouter_spec_manifest_v1,
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, object]:
    path = _repository_root() / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_specification_manifest_binding_verifies_exact_semantic_identity() -> None:
    binding = verify_openrouter_spec_manifest_v1()
    manifest = _manifest()
    semantic_payload = {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_id", "manifest_semantic_sha256"}
    }

    assert binding.manifest_id == OPENROUTER_SPECIFICATION_MANIFEST_ID_V1
    assert binding.manifest_semantic_sha256 == OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    assert hashlib.sha256(
        canonical_json(semantic_payload).encode("utf-8")
    ).hexdigest() == OPENROUTER_SPECIFICATION_MANIFEST_SHA256_V1
    assert tuple(
        (fact.evidence_id, fact.semantic_sha256)
        for fact in binding.relevant_fact_bindings
    ) == OPENROUTER_RELEVANT_FACT_DIGESTS_V1
    assert binding.candidate_model == OPENROUTER_ROUTE_MODEL_V1
    assert (
        binding.candidate_exact_provider_endpoint
        == OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda value: value.__setitem__("candidate_model", "alias/latest"), "semantic digest"),
        (lambda value: value.__setitem__("manifest_id", "forged"), "manifest ID"),
        (
            lambda value: value.__setitem__("manifest_semantic_sha256", "0" * 64),
            "digest field",
        ),
    ),
)
def test_manifest_verifier_fails_closed_on_identity_or_semantic_drift(
    tmp_path: Path, mutation, error: str
) -> None:
    manifest = _manifest()
    mutation(manifest)
    path = tmp_path / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ContractValidationError, match=error):
        verify_openrouter_spec_manifest_v1(tmp_path)


def test_manifest_verifier_rejects_changed_relevant_fact_even_if_fact_hash_is_forged(
    tmp_path: Path,
) -> None:
    # A changed fact necessarily changes the manifest digest.  This test also
    # demonstrates that fact digests are content-derived, not merely trusted.
    manifest = _manifest()
    facts = manifest["fact_records"]
    assert isinstance(facts, list)
    fact = next(item for item in facts if item["evidence_id"] == "ORSPEC-F04")
    fact["normalized_fact"] += " forged"
    fact["semantic_sha256"] = OPENROUTER_RELEVANT_FACT_DIGESTS_V1[3][1]
    path = tmp_path / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ContractValidationError, match="semantic digest changed"):
        verify_openrouter_spec_manifest_v1(tmp_path)


def test_manifest_verifier_requires_the_frozen_repository_relative_path(
    tmp_path: Path,
) -> None:
    source = _repository_root() / OPENROUTER_SPECIFICATION_MANIFEST_RELATIVE_PATH_V1
    shutil.copyfile(source, tmp_path / "renamed.json")
    with pytest.raises(ContractValidationError, match="manifest is unavailable"):
        verify_openrouter_spec_manifest_v1(tmp_path)


def test_default_policy_freezes_one_model_endpoint_order_and_all_deferrals() -> None:
    policy = default_openrouter_route_control_policy_v1()
    intent = policy.route_intent
    assert intent.model == "openai/gpt-4.1-mini"
    assert intent.models_field_status == "ABSENT"
    assert intent.provider_only == ("azure/swedencentral",)
    assert intent.provider_order == intent.provider_only
    assert intent.provider_allow_fallbacks is False
    assert intent.provider_require_parameters is True
    assert intent.max_price_status is OpenRouterDeferredStatusV1.DEFERRED_NOT_RENDERED
    assert intent.stream is False
    assert intent.tools == ()
    assert policy.live_server_enforcement is OpenRouterOfflineProofStatusV1.NOT_PROVEN
    assert policy.exact_endpoint_response_attestation is (
        OpenRouterOfflineProofStatusV1.NOT_ESTABLISHED
    )
    assert policy.p17_input_token_bound is OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    assert policy.p18_pricing_record is OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    assert policy.p19_cost_bound is OpenRouterDeferredStatusV1.NOT_ESTABLISHED
    assert policy.live_pilot_readiness == "NOT_EARNED"
    assert policy.real_provider_execution is False


@pytest.mark.parametrize(
    "field_and_value",
    (
        ("model", "openai/gpt-4.1"),
        ("provider_only", ("azure",)),
        ("provider_order", ()),
        ("provider_allow_fallbacks", True),
        ("provider_require_parameters", False),
        ("max_price_status", "NOT_ESTABLISHED"),
        ("stream", True),
        ("tools", ({"type": "function"},)),
        ("max_tokens", 255),
    ),
)
def test_route_intent_rejects_every_frozen_control_mutation(
    field_and_value: tuple[str, object],
) -> None:
    field_name, value = field_and_value
    with pytest.raises((ValidationError, ContractValidationError)):
        OpenRouterRouteIntentV1(**{field_name: value})


@pytest.mark.parametrize(
    "field_and_value",
    (
        ("provider_allow_fallbacks", 0),
        ("provider_require_parameters", 1),
        ("stream", 0),
        ("max_tokens", 256.0),
        ("temperature", 0),
    ),
)
def test_route_intent_rejects_json_type_coercion_loopholes(
    field_and_value: tuple[str, object],
) -> None:
    field_name, value = field_and_value
    with pytest.raises(ValidationError, match="exact JSON|frozen JSON"):
        OpenRouterRouteIntentV1(**{field_name: value})


def test_policy_and_receipt_ids_are_content_addressed_and_forgery_resistant() -> None:
    policy = default_openrouter_route_control_policy_v1()
    payload = policy.model_dump(mode="json")
    payload["route_control_policy_id"] = "szorroutecontrolsv1_" + "0" * 64
    with pytest.raises(ValidationError, match="does not match contract content"):
        OpenRouterRouteControlPolicyV1.model_validate(payload)

    receipt = OpenRouterRequestIntentReceiptV1(
        route_control_policy_id=policy.route_control_policy_id or "",
        route_intent_contract_id=policy.route_intent.route_intent_contract_id or "",
        route_intent_id="szorrouteintent_" + "1" * 64,
        body_sha256="2" * 64,
        body_length=447,
        semantic_headers_sha256="3" * 64,
        semantic_headers_length=98,
    )
    assert receipt.receipt_id == f"szorrouteintentreceiptv1_{receipt.receipt_sha256}"
    assert receipt.frozen_evidence_record_ids == OPENROUTER_RELEVANT_FACT_IDS_V1
    forged = receipt.model_dump(mode="json")
    forged["receipt_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="receipt_sha256"):
        OpenRouterRequestIntentReceiptV1.model_validate(forged)


def test_prepared_contract_revalidates_canonical_bytes_digests_and_receipt() -> None:
    policy = default_openrouter_route_control_policy_v1()
    prepared = OpenRouterPreparedRouteRequestV1(
        route_control_policy=policy,
        canonical_body_json=FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1,
        canonical_semantic_headers_json=FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
    )
    assert prepared.body_sha256 == hashlib.sha256(prepared.body_bytes).hexdigest()
    assert prepared.body_length == len(prepared.body_bytes)
    assert prepared.header_sha256 == hashlib.sha256(prepared.header_bytes).hexdigest()
    assert prepared.header_length == len(prepared.header_bytes)
    assert prepared.request_intent_receipt is not None
    assert prepared.request_intent_receipt.route_intent_id == prepared.route_intent_id
    assert prepared.request_intent_receipt.body_sha256 == prepared.body_sha256
    assert prepared.request_intent_receipt.semantic_headers_sha256 == (
        prepared.semantic_headers_sha256
    )

    with pytest.raises(ValidationError, match="canonical JSON"):
        OpenRouterPreparedRouteRequestV1(
            route_control_policy=policy,
            canonical_body_json=json.dumps(json.loads(FROZEN_OPENROUTER_ROUTE_BODY_JSON_V1)),
            canonical_semantic_headers_json=FROZEN_OPENROUTER_SEMANTIC_HEADERS_JSON_V1,
        )


def test_all_contracts_are_frozen_and_forbid_claim_escalation() -> None:
    policy = default_openrouter_route_control_policy_v1()
    with pytest.raises(ValidationError, match="frozen"):
        policy.live_pilot_readiness = "EARNED"  # type: ignore[misc]
    payload = policy.model_dump(mode="json")
    payload["p17_input_token_bound"] = "PROVEN_OFFLINE"
    with pytest.raises(ValidationError):
        OpenRouterRouteControlPolicyV1.model_validate(payload)

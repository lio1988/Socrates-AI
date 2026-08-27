"""Locks for OpenRouter pre-live integration v1.

Named so the shared conftest wraps every test in the acquisition boundary
tripwire: zero network, credential, provider, model, tool or CED activity.
"""

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
from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
    CREDENTIAL_PRESENT,
    FROZEN_OPENROUTER_INTEGRATION_CASES_V1,
    FROZEN_OPENROUTER_PREFLIGHT_CASES_V1,
    HEADERS_A,
    HEADERS_B,
    INTENT_A,
    INTENT_B,
    OPENROUTER_INTEGRATION_CASE_SET_ID_V1,
    OPENROUTER_PREFLIGHT_CASE_SET_ID_V1,
    RESPONSE_A,
    RESPONSE_B,
    OpenRouterIntegrationCaseKindV1,
    OpenRouterIntegrationExpectedOutcomeV1,
)
from backend.dialogues.socrates_zero.openrouter_pre_live_evaluation_v1 import (
    OpenRouterPreLiveOutcomeV1,
    evaluate_integration_case_v1,
    evaluate_openrouter_pre_live_v1,
    evaluate_preflight_case_v1,
    scan_artifact_privacy_v1,
)
from backend.dialogues.socrates_zero.openrouter_pre_live_integration_v1 import (
    OPENROUTER_MAX_LOCAL_DISPATCHES_V1,
    OpenRouterCacheConformanceV1,
    OpenRouterIntegrationError,
    OpenRouterIntegrationFailureCodeV1,
    OpenRouterModelConformanceV1,
    OpenRouterPreLiveIntegrationReceiptV1,
    OpenRouterTransportCompletionStateV1,
    OpenRouterTransportExecutionRecordV1,
    OpenRouterTransportRegistrationStateV1,
    bind_openrouter_pre_live_integration_v1,
)
from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
    OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1,
    OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
    FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1,
    OpenRouterBoundStatusV1,
    OpenRouterCredentialPresenceAttestationV1,
    OpenRouterInputBoundBasisV1,
    OpenRouterInputBoundEvidenceV1,
    OpenRouterTrustedPricingRecordV1,
    OpenRouterPricingSourceV1,
    compute_openrouter_cost_bound_v1,
)
from backend.dialogues.socrates_zero.openrouter_raw_wire_mapping_v2 import (
    OpenRouterWireEpistemicStatusV2,
    build_openrouter_raw_wire_observation_v2,
    map_openrouter_raw_wire_v2,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "backend" / "dialogues" / "socrates_zero"
S6_MODULES = (
    "openrouter_pre_live_integration_v1.py",
    "openrouter_pre_live_safety_v1.py",
    "openrouter_pre_live_cases_v1.py",
    "openrouter_pre_live_evaluation_v1.py",
)
SAFETY_ID = OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_ID_V1


def _chain(body: bytes, headers, intent=INTENT_A):
    observation = build_openrouter_raw_wire_observation_v2(body, headers)
    mapping = map_openrouter_raw_wire_v2(observation)
    header_payload = canonical_json([[n, v] for n, v in headers])
    transport = OpenRouterTransportExecutionRecordV1(
        registration_state=OpenRouterTransportRegistrationStateV1.REGISTERED,
        registered_body_sha256=intent.body_sha256,
        registered_body_length=intent.body_length,
        registered_semantic_headers_sha256=intent.semantic_headers_sha256,
        registered_semantic_headers_length=intent.semantic_headers_length,
        local_dispatch_count=1,
        completion_state=OpenRouterTransportCompletionStateV1.COMPLETED,
        response_present=True,
        response_body_sha256=hashlib.sha256(body).hexdigest(),
        response_body_length=len(body),
        response_header_evidence_sha256=hashlib.sha256(
            header_payload.encode("utf-8")
        ).hexdigest(),
        response_header_count=len(headers),
    )
    return intent, transport, observation, mapping


def _bind(body: bytes, headers, intent=INTENT_A):
    return bind_openrouter_pre_live_integration_v1(*_chain(body, headers, intent), SAFETY_ID)


# --------------------------------------------------------------- case sets --


@pytest.mark.parametrize(
    "case", FROZEN_OPENROUTER_INTEGRATION_CASES_V1, ids=lambda c: c.case_id
)
def test_every_integration_case_matches_expectation(case) -> None:
    result = evaluate_integration_case_v1(case)
    assert result.result_matches_expectation, (
        case.case_id,
        result.actual_outcome.value,
        result.actual_failure_code,
        result.field_mismatches,
    )


@pytest.mark.parametrize(
    "case", FROZEN_OPENROUTER_PREFLIGHT_CASES_V1, ids=lambda c: c.case_id
)
def test_every_preflight_case_matches_expectation(case) -> None:
    result = evaluate_preflight_case_v1(case)
    assert result.result_matches_expectation, (
        case.case_id,
        result.actual_verdict,
        result.actual_failure_code,
    )


def test_case_set_shape_is_frozen() -> None:
    cases = FROZEN_OPENROUTER_INTEGRATION_CASES_V1
    assert len(cases) == 30
    assert sum(c.kind is OpenRouterIntegrationCaseKindV1.POSITIVE for c in cases) == 12
    assert sum(c.kind is OpenRouterIntegrationCaseKindV1.ADVERSARIAL for c in cases) == 18
    assert len(FROZEN_OPENROUTER_PREFLIGHT_CASES_V1) == 25
    assert OPENROUTER_INTEGRATION_CASE_SET_ID_V1.startswith("szorintegrationcasesetv1_")
    assert OPENROUTER_PREFLIGHT_CASE_SET_ID_V1.startswith("szorpreflightcasesetv1_")


def test_chain_a_is_the_real_rendered_request() -> None:
    """The frozen request literals are bound to reality, not trusted."""
    from backend.dialogues.socrates_zero.openrouter_route_controls_renderer import (
        prepare_openrouter_route_request_v1,
    )

    prepared = prepare_openrouter_route_request_v1(repository_root=ROOT)
    real = prepared.request_intent_receipt
    assert INTENT_A.body_sha256 == real.body_sha256
    assert INTENT_A.body_length == real.body_length
    assert INTENT_A.semantic_headers_sha256 == real.semantic_headers_sha256
    assert INTENT_A.semantic_headers_length == real.semantic_headers_length
    assert INTENT_A.route_intent_id == real.route_intent_id
    assert INTENT_A.receipt_id == real.receipt_id


# ------------------------------------------------- cross-request substitution


def test_full_cross_request_substitution_matrix_fails_closed() -> None:
    """Every mix of chain A and chain B evidence must be refused."""
    a_intent, a_transport, a_obs, a_map = _chain(RESPONSE_A, HEADERS_A, INTENT_A)
    b_intent, b_transport, b_obs, b_map = _chain(RESPONSE_B, HEADERS_B, INTENT_B)

    # Each chain alone is valid.
    assert bind_openrouter_pre_live_integration_v1(
        a_intent, a_transport, a_obs, a_map, SAFETY_ID
    ).receipt_id
    assert bind_openrouter_pre_live_integration_v1(
        b_intent, b_transport, b_obs, b_map, SAFETY_ID
    ).receipt_id

    for label, args in (
        ("A request + B transport", (a_intent, b_transport, b_obs, b_map)),
        ("B request + A transport", (b_intent, a_transport, a_obs, a_map)),
        ("A transport + B response", (a_intent, a_transport, b_obs, b_map)),
        ("A response + B mapping", (a_intent, a_transport, a_obs, b_map)),
        ("B response + A mapping", (b_intent, b_transport, b_obs, a_map)),
    ):
        with pytest.raises(OpenRouterIntegrationError) as raised:
            bind_openrouter_pre_live_integration_v1(*args, SAFETY_ID)
        assert raised.value.code is not None, label


def test_receipt_identity_is_the_four_layers_plus_the_contract() -> None:
    receipt = _bind(RESPONSE_A, HEADERS_A)
    other = _bind(RESPONSE_B, HEADERS_B, INTENT_B)
    assert receipt.receipt_id != other.receipt_id
    # Same chain, same identity.
    assert _bind(RESPONSE_A, HEADERS_A).receipt_id == receipt.receipt_id


# --------------------------------------------------------- authority firewalls


def test_requested_model_never_fills_an_absent_actual_model() -> None:
    body = json.dumps({"error": {"code": 500, "message": "x"}}).encode("utf-8")
    receipt = _bind(body, HEADERS_A)
    assert receipt.actual_served_model is None
    assert receipt.model_conformance is OpenRouterModelConformanceV1.UNAVAILABLE
    assert receipt.requested_model == "openai/gpt-4.1-mini"
    assert receipt.actual_served_model_status is (
        OpenRouterWireEpistemicStatusV2.ABSENT_FROM_OBSERVATION
    )


def test_actual_model_mismatch_binds_but_fails_policy_conformance() -> None:
    body = json.dumps(
        {"model": "anthropic/claude-sonnet-4", "choices": []}
    ).encode("utf-8")
    receipt = _bind(body, HEADERS_A)
    assert receipt.receipt_id  # causally valid
    assert receipt.model_conformance is OpenRouterModelConformanceV1.MISMATCH
    assert receipt.actual_served_model == "anthropic/claude-sonnet-4"


def test_provider_selector_never_becomes_response_authority() -> None:
    receipt = _bind(RESPONSE_A, HEADERS_A)
    assert receipt.requested_exact_endpoint_selector == "azure/swedencentral"
    assert receipt.response_provider_display_names == ("Azure",)
    assert all("/" not in n for n in receipt.response_provider_display_names)
    assert receipt.exact_endpoint_response_identity is None


def test_receipt_refuses_a_provider_slug_in_response_evidence() -> None:
    receipt = _bind(RESPONSE_A, HEADERS_A)
    payload = receipt.model_dump(mode="json")
    payload.pop("receipt_id")
    payload["response_provider_display_names"] = ["azure/swedencentral"]
    with pytest.raises(ValidationError, match="display label"):
        OpenRouterPreLiveIntegrationReceiptV1.model_validate(payload)


def test_exact_endpoint_identity_cannot_be_given_a_value() -> None:
    receipt = _bind(RESPONSE_A, HEADERS_A)
    payload = receipt.model_dump(mode="json")
    payload.pop("receipt_id")
    payload["exact_endpoint_response_identity"] = "azure/swedencentral"
    with pytest.raises(ValidationError):
        OpenRouterPreLiveIntegrationReceiptV1.model_validate(payload)


def test_cache_authority_comes_only_from_the_response_header() -> None:
    no_header = _bind(RESPONSE_A, (("X-Generation-Id", "g"),))
    assert no_header.response_cache_status is None
    assert no_header.cache_conformance is (
        OpenRouterCacheConformanceV1.NO_RESPONSE_AUTHORITY
    )
    miss = _bind(RESPONSE_A, HEADERS_A)
    assert miss.cache_conformance is (
        OpenRouterCacheConformanceV1.CONSISTENT_WITH_DISABLED_INTENT
    )


def test_server_attempts_never_become_local_dispatches() -> None:
    body = json.dumps(
        {
            "model": "openai/gpt-4.1-mini",
            "choices": [],
            "openrouter_metadata": {
                "requested": "openai/gpt-4.1-mini",
                "strategy": "direct",
                "region": "iad",
                "summary": "s",
                "attempt": 3,
                "is_byok": False,
                "endpoints": {"total": 1, "available": []},
                "attempts": [
                    {"provider": "OpenAI", "model": "m", "status": 503},
                    {"provider": "Azure", "model": "m", "status": 200},
                ],
            },
        }
    ).encode("utf-8")
    receipt = _bind(body, HEADERS_A)
    assert receipt.response_attempt == 3
    assert receipt.local_dispatch_count == OPENROUTER_MAX_LOCAL_DISPATCHES_V1 == 1


# ------------------------------------------------------------- metamorphic --


def test_identical_chain_yields_identical_integration_identity() -> None:
    assert _bind(RESPONSE_A, HEADERS_A).receipt_id == _bind(
        RESPONSE_A, HEADERS_A
    ).receipt_id


def test_whitespace_variant_changes_wire_evidence_and_identity() -> None:
    spaced = json.dumps(json.loads(RESPONSE_A.decode()), indent=2).encode("utf-8")
    baseline = _bind(RESPONSE_A, HEADERS_A)
    variant = _bind(spaced, HEADERS_A)
    assert variant.receipt_id != baseline.receipt_id
    assert variant.response_body_sha256 != baseline.response_body_sha256
    # The semantic reading is unchanged even though the evidence differs.
    assert variant.actual_served_model == baseline.actual_served_model
    assert variant.model_conformance is baseline.model_conformance


def test_response_header_case_does_not_change_semantics() -> None:
    upper = _bind(RESPONSE_A, (("X-OPENROUTER-CACHE-STATUS", "MISS"),))
    lower = _bind(RESPONSE_A, (("x-openrouter-cache-status", "MISS"),))
    assert upper.response_cache_status == lower.response_cache_status
    assert upper.cache_conformance is lower.cache_conformance


def test_conflicting_authority_headers_cannot_reach_integration() -> None:
    from backend.dialogues.socrates_zero.openrouter_raw_wire_mapping_v2 import (
        OpenRouterWireMappingError,
    )

    with pytest.raises(OpenRouterWireMappingError):
        _bind(
            RESPONSE_A,
            (
                ("X-OpenRouter-Cache-Status", "HIT"),
                ("X-OpenRouter-Cache-Status", "MISS"),
            ),
        )


def test_unknown_response_field_does_not_move_policy_conformance() -> None:
    payload = json.loads(RESPONSE_A.decode())
    payload["openrouter_metadata"]["a_new_field"] = {"endpoint_slug": "azure/x"}
    variant = _bind(json.dumps(payload).encode("utf-8"), HEADERS_A)
    baseline = _bind(RESPONSE_A, HEADERS_A)
    assert variant.model_conformance is baseline.model_conformance
    assert variant.exact_endpoint_response_identity is None
    assert variant.response_provider_display_names == (
        baseline.response_provider_display_names
    )


def test_request_body_change_invalidates_the_previous_transport_binding() -> None:
    _, transport, observation, mapping = _chain(RESPONSE_A, HEADERS_A, INTENT_A)
    with pytest.raises(OpenRouterIntegrationError) as raised:
        bind_openrouter_pre_live_integration_v1(
            INTENT_B, transport, observation, mapping, SAFETY_ID
        )
    assert raised.value.code is (
        OpenRouterIntegrationFailureCodeV1.REGISTERED_BODY_MISMATCH
    )


# ------------------------------------------------------------------ privacy --


def test_receipt_carries_no_raw_bytes() -> None:
    receipt = _bind(RESPONSE_A, HEADERS_A)
    payload = canonical_json(receipt.model_dump(mode="json"))
    assert RESPONSE_A.decode("utf-8") not in payload
    assert "scaffolding" not in payload
    assert "Ask one concise opening Socratic question" not in payload
    for marker in ("Authorization", "Bearer ", "sk-or-"):
        assert marker not in payload


def test_privacy_scanner_detects_a_synthetic_credential_leak() -> None:
    """The scanner must not be vacuous."""
    assert scan_artifact_privacy_v1("nothing sensitive here") == 0
    assert scan_artifact_privacy_v1('{"h": "Authorization: Bearer sk-or-v1-secret"}') > 0
    assert scan_artifact_privacy_v1(RESPONSE_A.decode("utf-8")) > 0


def test_credential_attestation_records_presence_only() -> None:
    attestation = OpenRouterCredentialPresenceAttestationV1(
        credential_present=True, credential_variable_name="OPENROUTER_API_KEY"
    )
    payload = canonical_json(attestation.model_dump(mode="json"))
    assert "sk-or-" not in payload
    assert set(attestation.model_dump(mode="python")) == {
        "schema_version",
        "credential_present",
        "credential_variable_name",
        "attestation_id",
    }


# ------------------------------------------------------------ safety/budget --


def test_structural_safety_contract_pins_the_candidate_policy() -> None:
    contract = FROZEN_OPENROUTER_PRE_LIVE_SAFETY_CONTRACT_V1
    assert contract.max_local_dispatches == 1
    assert contract.automatic_retry_permitted is False
    assert contract.exact_model == "openai/gpt-4.1-mini"
    assert contract.exact_endpoint_selector == "azure/swedencentral"
    assert contract.provider_fallback_permitted is False
    assert contract.model_fallback_permitted is False
    assert contract.stream is False
    assert contract.tools_enabled is False
    assert contract.response_cache_requested is False
    assert contract.max_output_tokens == OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1 == 256
    assert contract.ced_authority_enabled is False
    assert contract.runtime_authority == "NOT_AUTHORIZED"


def test_p17_is_not_established_and_bytes_are_not_tokens() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        INPUT_BOUND_UNESTABLISHED,
    )

    assert INPUT_BOUND_UNESTABLISHED.status is OpenRouterBoundStatusV1.NOT_ESTABLISHED
    assert INPUT_BOUND_UNESTABLISHED.max_input_tokens is None
    assert INPUT_BOUND_UNESTABLISHED.request_body_byte_cap == 447
    assert INPUT_BOUND_UNESTABLISHED.basis is (
        OpenRouterInputBoundBasisV1.NO_PINNED_TOKENIZER_AVAILABLE
    )


def test_an_input_bound_cannot_be_claimed_without_a_tokenizer() -> None:
    with pytest.raises(ValidationError):
        OpenRouterInputBoundEvidenceV1(
            status=OpenRouterBoundStatusV1.ESTABLISHED,
            basis=OpenRouterInputBoundBasisV1.NO_PINNED_TOKENIZER_AVAILABLE,
            max_input_tokens=100,
            request_body_byte_cap=447,
            bound_request_body_sha256="a" * 64,
            chat_framing_overhead_bounded=True,
        )


def test_cost_bound_is_exact_integer_arithmetic() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        INPUT_BOUND_HYPOTHETICAL,
        OUTPUT_BOUND_ESTABLISHED,
        PRICING_TRUSTED,
    )

    bound = compute_openrouter_cost_bound_v1(
        INPUT_BOUND_HYPOTHETICAL, OUTPUT_BOUND_ESTABLISHED, PRICING_TRUSTED
    )
    assert bound.status is OpenRouterBoundStatusV1.ESTABLISHED
    # 512 * 400000 + 256 * 1600000, in picodollars, exactly.
    assert bound.max_total_cost_picodollars == 512 * 400000 + 256 * 1600000
    assert isinstance(bound.max_total_cost_picodollars, int)


def test_cost_bound_is_unestablished_without_an_input_bound() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        INPUT_BOUND_UNESTABLISHED,
        OUTPUT_BOUND_ESTABLISHED,
        PRICING_TRUSTED,
    )

    bound = compute_openrouter_cost_bound_v1(
        INPUT_BOUND_UNESTABLISHED, OUTPUT_BOUND_ESTABLISHED, PRICING_TRUSTED
    )
    assert bound.status is OpenRouterBoundStatusV1.NOT_ESTABLISHED
    assert bound.max_total_cost_picodollars is None


@pytest.mark.parametrize("bad", ("NaN", "Infinity", "-1", "abc", ""))
def test_pricing_refuses_unsafe_decimal_strings(bad: str) -> None:
    with pytest.raises(ValidationError):
        OpenRouterTrustedPricingRecordV1(
            source=OpenRouterPricingSourceV1.FIRST_PARTY_MODEL_ENDPOINTS,
            source_evidence_sha256="a" * 64,
            preflight_execution_id="pf",
            model_id="openai/gpt-4.1-mini",
            prompt_price_usd=bad,
            completion_price_usd="0.0000016",
        )


# ------------------------------------------------------------- inertness ----


def test_s6_modules_are_import_inert(tmp_path: Path) -> None:
    """Execute each module body again in a throwaway package-qualified namespace.

    Not ``importlib.reload``: that rebinds every contract class and breaks
    identity checks for every test that runs afterwards.
    """
    import importlib.util
    import sys

    from backend.dialogues.socrates_zero import acquisition_tripwires

    before = acquisition_tripwires.active_acquisition_boundary_tripwire_v0().snapshot()
    probe_names = []
    try:
        for name in S6_MODULES:
            probe_name = f"backend.dialogues.socrates_zero._s6_probe_{name[:-3]}"
            spec = importlib.util.spec_from_file_location(
                probe_name, RUNTIME_DIR / name
            )
            module = importlib.util.module_from_spec(spec)
            # Registered under the throwaway key only, so pydantic can resolve
            # the module's annotations while the canonical modules stay bound.
            sys.modules[probe_name] = module
            probe_names.append(probe_name)
            spec.loader.exec_module(module)
    finally:
        for probe_name in probe_names:
            sys.modules.pop(probe_name, None)
    after = acquisition_tripwires.active_acquisition_boundary_tripwire_v0().assert_clean()
    assert after.total_forbidden_attempts == before.total_forbidden_attempts == 0
    assert list(tmp_path.iterdir()) == []


def test_installed_s6_classes_are_not_rebound_by_the_probe() -> None:
    from backend.dialogues.socrates_zero import (
        openrouter_pre_live_integration_v1 as live,
    )

    assert (
        live.OpenRouterTransportExecutionRecordV1
        is OpenRouterTransportExecutionRecordV1
    )


def test_s6_modules_do_not_reimplement_predecessor_contracts() -> None:
    def imports(path: Path) -> set:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                found.add(("." * node.level) + (node.module or ""))
            elif isinstance(node, ast.Import):
                found.update(a.name for a in node.names)
        return found

    integration = imports(RUNTIME_DIR / "openrouter_pre_live_integration_v1.py")
    # It composes the existing request-intent and S5 mapping contracts.
    assert ".openrouter_route_controls_contracts" in integration
    assert ".openrouter_raw_wire_mapping_v2" in integration
    # And it does not reach into the predecessor evaluators.
    assert ".openrouter_route_controls_evaluation" not in integration
    assert ".openrouter_acquisition_evaluation" not in integration


# ------------------------------------------------- ruling-mandated locks -----


def test_output_bound_is_recorded_separately_from_p17() -> None:
    """max_tokens 256 is the OUTPUT bound. It is never called P17."""
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        OUTPUT_BOUND_ESTABLISHED,
    )
    from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
        OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
        OpenRouterOutputBoundEvidenceV1,
    )

    assert OUTPUT_BOUND_ESTABLISHED.status is OpenRouterBoundStatusV1.ESTABLISHED
    assert OUTPUT_BOUND_ESTABLISHED.max_output_tokens == 256
    assert OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1 == 256
    # The output bound contract has no input-token field at all.
    assert "input" not in " ".join(OpenRouterOutputBoundEvidenceV1.model_fields)


def test_output_bound_must_equal_the_sealed_value() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
        OpenRouterOutputBoundEvidenceV1,
    )

    with pytest.raises(ValidationError, match="sealed in the request body"):
        OpenRouterOutputBoundEvidenceV1(
            status=OpenRouterBoundStatusV1.ESTABLISHED,
            max_output_tokens=4096,
            bound_request_body_sha256="a" * 64,
        )


def test_tokenizer_family_label_is_not_a_tokenizer_identity() -> None:
    """ModelGroup names a lineage, not a pinned vocabulary."""
    from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
        FROZEN_OPENROUTER_TOKENIZER_FAMILY_LABELS_V1,
        OpenRouterTokenizerBindingV1,
    )

    assert "GPT" in FROZEN_OPENROUTER_TOKENIZER_FAMILY_LABELS_V1
    with pytest.raises(ValidationError, match="family label is not a tokenizer"):
        OpenRouterInputBoundEvidenceV1(
            status=OpenRouterBoundStatusV1.NOT_ESTABLISHED,
            basis=OpenRouterInputBoundBasisV1.NO_PINNED_TOKENIZER_AVAILABLE,
            request_body_byte_cap=447,
            bound_request_body_sha256="a" * 64,
            tokenizer_binding=OpenRouterTokenizerBindingV1.FAMILY_LABEL_ONLY,
            tokenizer_identity="GPT",
        )


def test_a_token_count_cannot_be_claimed_without_pinned_tokenizer_evidence() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
        OpenRouterTokenizerBindingV1,
    )

    # Basis says tokenizer, but nothing is pinned.
    with pytest.raises(ValidationError, match="pinned implementation"):
        OpenRouterInputBoundEvidenceV1(
            status=OpenRouterBoundStatusV1.ESTABLISHED,
            basis=OpenRouterInputBoundBasisV1.PINNED_OFFICIAL_TOKENIZER,
            max_input_tokens=128,
            request_body_byte_cap=447,
            bound_request_body_sha256="a" * 64,
            chat_framing_overhead_bounded=True,
            tokenizer_binding=OpenRouterTokenizerBindingV1.ABSENT,
        )
    # Pinned binding but no identity or authoritative model→tokenizer source.
    with pytest.raises(ValidationError, match="identity and an"):
        OpenRouterInputBoundEvidenceV1(
            status=OpenRouterBoundStatusV1.ESTABLISHED,
            basis=OpenRouterInputBoundBasisV1.PINNED_OFFICIAL_TOKENIZER,
            max_input_tokens=128,
            request_body_byte_cap=447,
            bound_request_body_sha256="a" * 64,
            chat_framing_overhead_bounded=True,
            tokenizer_binding=OpenRouterTokenizerBindingV1.PINNED_IMPLEMENTATION,
        )


def test_pricing_granularity_audit_is_broad_provider_only() -> None:
    """The retained first-party schema cannot name the exact request selector."""
    from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
        OPENROUTER_PRICING_ENDPOINT_GRANULARITY_V1,
    )

    assert OPENROUTER_PRICING_ENDPOINT_GRANULARITY_V1 == "BROAD_PROVIDER_ONLY"

    openapi = (
        ROOT
        / "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1"
        / "evidence/sources/openapi.yaml"
    ).read_text(encoding="utf-8")
    # The endpoint record carries a broad provider display name and an
    # undocumented tag; no retained example carries a compound provider/region.
    assert "provider_name: 'OpenAI'" in openapi
    assert "tag: 'openai'" in openapi
    assert "provider_name: 'azure/swedencentral'" not in openapi
    assert "tag: 'azure/swedencentral'" not in openapi


def test_broad_provider_pricing_cannot_stand_for_the_exact_selector() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        PRICING_BROAD_PROVIDER,
    )
    from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
        OpenRouterPricingGranularityV1,
    )

    assert PRICING_BROAD_PROVIDER.route_identity == "Azure"
    assert PRICING_BROAD_PROVIDER.route_identity_granularity is (
        OpenRouterPricingGranularityV1.BROAD_PROVIDER_ONLY
    )
    # And it cannot produce a cost bound.
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        INPUT_BOUND_HYPOTHETICAL,
        OUTPUT_BOUND_ESTABLISHED,
    )

    bound = compute_openrouter_cost_bound_v1(
        INPUT_BOUND_HYPOTHETICAL, OUTPUT_BOUND_ESTABLISHED, PRICING_BROAD_PROVIDER
    )
    assert bound.status is OpenRouterBoundStatusV1.NOT_ESTABLISHED


def test_p19_formula_is_ready_while_its_authority_is_not() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        INPUT_BOUND_UNESTABLISHED,
        OUTPUT_BOUND_ESTABLISHED,
        PRICING_TRUSTED,
    )

    bound = compute_openrouter_cost_bound_v1(
        INPUT_BOUND_UNESTABLISHED, OUTPUT_BOUND_ESTABLISHED, PRICING_TRUSTED
    )
    assert bound.formula_ready is True
    assert bound.formula == (
        "max_input_tokens * prompt_price + max_output_tokens * completion_price"
    )
    assert bound.status is OpenRouterBoundStatusV1.NOT_ESTABLISHED
    assert bound.max_total_cost_picodollars is None


def test_exponent_form_price_equals_plain_decimal_exactly() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        PRICING_EXPONENT_FORM,
        PRICING_TRUSTED,
    )

    assert (
        PRICING_EXPONENT_FORM.prompt_price_picodollars
        == PRICING_TRUSTED.prompt_price_picodollars
        == 400000
    )
    assert (
        PRICING_EXPONENT_FORM.completion_price_picodollars
        == PRICING_TRUSTED.completion_price_picodollars
        == 1600000
    )


def test_operator_ceiling_boundary_is_inclusive_and_one_unit_below_refuses() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        HYPOTHETICAL_COST_PICODOLLARS,
        INPUT_BOUND_HYPOTHETICAL,
        OUTPUT_BOUND_ESTABLISHED,
        PRICING_TRUSTED,
    )

    bound = compute_openrouter_cost_bound_v1(
        INPUT_BOUND_HYPOTHETICAL, OUTPUT_BOUND_ESTABLISHED, PRICING_TRUSTED
    )
    assert bound.max_total_cost_picodollars == HYPOTHETICAL_COST_PICODOLLARS
    # The equality and one-below cases are exercised end to end in the case set.
    ids = {c.case_id for c in FROZEN_OPENROUTER_PREFLIGHT_CASES_V1}
    assert "orpreflightv1-p02-operator-ceiling-equality-boundary" in ids
    assert "orpreflightv1-x18-operator-ceiling-one-unit-below" in ids


def test_cost_overflow_is_refused_not_wrapped() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_cases_v1 import (
        INPUT_BOUND_HYPOTHETICAL,
        OUTPUT_BOUND_ESTABLISHED,
        PRICING_OVERFLOW,
    )

    with pytest.raises(ContractValidationError, match="safe arithmetic domain"):
        compute_openrouter_cost_bound_v1(
            INPUT_BOUND_HYPOTHETICAL, OUTPUT_BOUND_ESTABLISHED, PRICING_OVERFLOW
        )


def test_live_readiness_is_not_authorized_while_p17_or_p18_is_structural() -> None:
    from backend.dialogues.socrates_zero.openrouter_pre_live_evaluation_v1 import (
        OpenRouterLiveReadinessV1,
        _live_readiness_v1,
    )

    assert _live_readiness_v1() is OpenRouterLiveReadinessV1.NOT_AUTHORIZED

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import canonical_json
from backend.dialogues.socrates_zero.openrouter_route_controls_contracts import (
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_ROUTE_MODEL_V1,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_parser import (
    AttemptsListStatusV1,
    OpenRouterRouteControlFailureCodeV1,
    OpenRouterRouteControlGuardV1,
    OpenRouterRouteControlParserError,
    OpenRouterRouteControlReceiptV1,
    build_reference_openrouter_route_response_v1,
    parse_openrouter_router_metadata_v1,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_renderer import (
    prepare_openrouter_route_request_v1,
)


def _prepared():
    return prepare_openrouter_route_request_v1()


def _mutated(raw: bytes, mutate) -> bytes:
    value = json.loads(raw)
    mutate(value)
    return canonical_json(value).encode("utf-8")


def _assert_failure(raw, code, guard, *, transport_completed=True) -> None:
    with pytest.raises(OpenRouterRouteControlParserError) as caught:
        parse_openrouter_router_metadata_v1(
            raw,
            _prepared(),
            transport_completed=transport_completed,
        )
    assert caught.value.failure_code is code
    assert caught.value.guard_id is guard
    if isinstance(raw, bytes) and raw:
        assert caught.value.raw_response_sha256 == hashlib.sha256(raw).hexdigest()


def test_raw_first_positive_partial_attestation_is_deterministic() -> None:
    raw = build_reference_openrouter_route_response_v1()
    first = parse_openrouter_router_metadata_v1(raw, _prepared())
    second = parse_openrouter_router_metadata_v1(raw, _prepared())

    assert first == second
    assert first.raw_response.raw_response_json.encode("utf-8") == raw
    assert first.raw_response.raw_response_sha256 == hashlib.sha256(raw).hexdigest()
    assert first.metadata_receipt.attempt == 1
    assert (
        first.metadata_receipt.attempts_list_status
        is AttemptsListStatusV1.ABSENT_ACCEPTED
    )
    assert first.metadata_receipt.actual_model == OPENROUTER_ROUTE_MODEL_V1
    assert first.metadata_receipt.attested_provider == "azure"
    assert first.metadata_receipt.requested_endpoint == OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    assert first.metadata_receipt.cache_metadata_status == (
        "METADATA_PRESENT_NO_CACHE_HIT_INFERENCE"
    )
    assert first.metadata_receipt.unknown_field_count == 0
    assert first.route_attestation.response_provider_attestation == (
        "PARTIAL_BROAD_PROVIDER"
    )
    assert first.route_attestation.response_exact_endpoint_attestation == (
        "NOT_ESTABLISHED"
    )
    assert first.live_enforcement == "NOT_PROVEN"
    assert (first.p17_status, first.p18_status, first.p19_status) == (
        "NOT_ESTABLISHED",
        "NOT_ESTABLISHED",
        "NOT_ESTABLISHED",
    )
    assert first.live_readiness == "NOT_EARNED"
    assert first.real_provider_execution is False


def test_optional_attempts_and_unknown_fields_are_honest_and_opaque() -> None:
    base = parse_openrouter_router_metadata_v1(
        build_reference_openrouter_route_response_v1(include_attempts=True),
        _prepared(),
    )
    extended = parse_openrouter_router_metadata_v1(
        build_reference_openrouter_route_response_v1(
            include_attempts=True,
            metadata_extras={"future_summary": {"revision": 2}},
        ),
        _prepared(),
    )

    assert base.metadata_receipt.attempts_list_status is (
        AttemptsListStatusV1.PRESENT_CONSISTENT
    )
    assert extended.metadata_receipt.unknown_field_count > 0
    assert extended.metadata_receipt.unknown_fields_sha256 != (
        base.metadata_receipt.unknown_fields_sha256
    )
    assert extended.route_attestation.model_dump(
        mode="json", exclude={"metadata_receipt_id", "attestation_id"}
    ) == base.route_attestation.model_dump(
        mode="json", exclude={"metadata_receipt_id", "attestation_id"}
    )


@pytest.mark.parametrize(
    ("mutate", "code", "guard"),
    [
        (
            lambda value: value.pop("openrouter_metadata"),
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MISSING,
            OpenRouterRouteControlGuardV1.METADATA_PRESENCE,
        ),
        (
            lambda value: value["openrouter_metadata"].pop("attempt"),
            OpenRouterRouteControlFailureCodeV1.ATTEMPT_MISSING,
            OpenRouterRouteControlGuardV1.ATTEMPT_PRESENT_AND_VALID,
        ),
        (
            lambda value: value["openrouter_metadata"].update(attempt=True),
            OpenRouterRouteControlFailureCodeV1.ATTEMPT_INVALID,
            OpenRouterRouteControlGuardV1.ATTEMPT_PRESENT_AND_VALID,
        ),
        (
            lambda value: value["openrouter_metadata"].update(attempt=2),
            OpenRouterRouteControlFailureCodeV1.MULTI_ATTEMPT_ROUTING_OBSERVED,
            OpenRouterRouteControlGuardV1.ATTEMPT_EQUALS_ONE,
        ),
        (
            lambda value: value["openrouter_metadata"].update(actual_model="other/model"),
            OpenRouterRouteControlFailureCodeV1.ACTUAL_MODEL_MISMATCH,
            OpenRouterRouteControlGuardV1.ACTUAL_MODEL_MATCH,
        ),
        (
            lambda value: value["openrouter_metadata"].update(provider="openai"),
            OpenRouterRouteControlFailureCodeV1.PROVIDER_MISMATCH,
            OpenRouterRouteControlGuardV1.PROVIDER_COMPATIBILITY,
        ),
    ],
)
def test_required_response_fields_fail_at_their_first_guard(mutate, code, guard) -> None:
    _assert_failure(
        _mutated(build_reference_openrouter_route_response_v1(), mutate),
        code,
        guard,
    )


def test_attempts_cache_fallback_and_pipeline_fail_closed() -> None:
    raw = build_reference_openrouter_route_response_v1(include_attempts=True)
    probes = (
        (
            lambda value: value["openrouter_metadata"]["attempts"].append(
                dict(value["openrouter_metadata"]["attempts"][0])
            ),
            OpenRouterRouteControlFailureCodeV1.MULTIPLE_ATTEMPTS_REPORTED,
            OpenRouterRouteControlGuardV1.ATTEMPTS_LIST_CONSISTENCY,
        ),
        (
            lambda value: value.update(cache_hit=True),
            OpenRouterRouteControlFailureCodeV1.CACHE_AFFECTED_OR_UNATTESTED,
            OpenRouterRouteControlGuardV1.CACHE_METADATA_AVAILABILITY,
        ),
        (
            lambda value: value["openrouter_metadata"].update(fallback_observed=True),
            OpenRouterRouteControlFailureCodeV1.FALLBACK_INDICATOR_OBSERVED,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
        ),
        (
            lambda value: value["openrouter_metadata"].update(
                pipeline=[{"stage": "fallback"}]
            ),
            OpenRouterRouteControlFailureCodeV1.FORBIDDEN_PIPELINE_STAGE,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
        ),
    )
    for mutate, code, guard in probes:
        _assert_failure(_mutated(raw, mutate), code, guard)

    forward = _mutated(
        raw,
        lambda value: value["openrouter_metadata"].update(
            pipeline=[{"stage": "future-observational-stage"}]
        ),
    )
    receipt = parse_openrouter_router_metadata_v1(forward, _prepared())
    assert receipt.metadata_receipt.unknown_field_count > 0


def test_strategy_and_nested_fallback_authority_fail_closed() -> None:
    raw = build_reference_openrouter_route_response_v1()
    for mutate in (
        lambda value: value["openrouter_metadata"].update(
            routing_strategy="fallback"
        ),
        lambda value: value["openrouter_metadata"].update(
            future={"fallback_observed": True}
        ),
    ):
        _assert_failure(
            _mutated(raw, mutate),
            OpenRouterRouteControlFailureCodeV1.FALLBACK_INDICATOR_OBSERVED,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
        )


def test_model_copy_cannot_forge_prepared_request_receipt_links() -> None:
    prepared = _prepared().model_copy(
        update={"route_intent_id": "szorrouteintent_" + "0" * 64}
    )
    with pytest.raises(OpenRouterRouteControlParserError) as caught:
        parse_openrouter_router_metadata_v1(
            build_reference_openrouter_route_response_v1(), prepared
        )
    assert caught.value.failure_code is (
        OpenRouterRouteControlFailureCodeV1.RECEIPT_INTEGRITY_FAILURE
    )
    assert caught.value.guard_id is (
        OpenRouterRouteControlGuardV1.RECEIPT_AND_CLAIMS_INTEGRITY
    )


def test_exact_endpoint_and_unknown_authority_claims_never_gain_authority() -> None:
    exact = _mutated(
        build_reference_openrouter_route_response_v1(),
        lambda value: value["openrouter_metadata"].update(
            endpoint_slug=OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
        ),
    )
    _assert_failure(
        exact,
        OpenRouterRouteControlFailureCodeV1.FALSE_EXACT_ENDPOINT_CLAIM,
        OpenRouterRouteControlGuardV1.NO_FALSE_EXACT_ENDPOINT_ATTESTATION,
    )
    override = build_reference_openrouter_route_response_v1(
        metadata_extras={"future": {"actual_model": "other/model"}}
    )
    _assert_failure(
        override,
        OpenRouterRouteControlFailureCodeV1.UNKNOWN_FIELD_AUTHORITY_OVERRIDE,
        OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
    )


def test_raw_envelope_transport_and_noncanonical_json_are_raw_first() -> None:
    _assert_failure(
        None,
        OpenRouterRouteControlFailureCodeV1.TRANSPORT_INCOMPLETE,
        OpenRouterRouteControlGuardV1.TRANSPORT_COMPLETION,
        transport_completed=False,
    )
    _assert_failure(
        None,
        OpenRouterRouteControlFailureCodeV1.RAW_RESPONSE_MISSING,
        OpenRouterRouteControlGuardV1.RAW_ENVELOPE_PRESENCE,
    )
    noncanonical = json.dumps(
        json.loads(build_reference_openrouter_route_response_v1()), indent=2
    ).encode("utf-8")
    receipt = parse_openrouter_router_metadata_v1(noncanonical, _prepared())
    assert receipt.raw_response.raw_response_json.encode("utf-8") == noncanonical
    assert receipt.raw_response.raw_response_sha256 == hashlib.sha256(
        noncanonical
    ).hexdigest()


def test_literal_claim_and_receipt_identity_firewalls_reject_overclaim() -> None:
    receipt = parse_openrouter_router_metadata_v1(
        build_reference_openrouter_route_response_v1(), _prepared()
    )
    payload = receipt.model_dump(mode="json")
    payload["route_attestation"]["response_exact_endpoint_attestation"] = "PROVEN"
    payload["route_attestation"]["p17_input_token_bound"] = "ESTABLISHED"
    payload["live_enforcement"] = "PROVEN"
    payload["receipt_id"] = None
    with pytest.raises(ValidationError):
        OpenRouterRouteControlReceiptV1.model_validate(payload)

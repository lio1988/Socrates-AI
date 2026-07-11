"""External Self-Consultation v1 — tamper-evident receipts and their store.

A receipt binds one canonical request digest to one canonical result digest.
Exact reruns are idempotent; a different content under the same request_id is
refused; the digest changes when either the request or the result changes; no
keys or hidden reasoning are stored.
"""

import asyncio

import pytest

from backend.dialogues.openclaw_consultation import (
    ConsultationError,
    ConsultationPolicy,
    ConsultationReceiptStore,
    ExternalConsultationRequest,
    ExternalConsultationService,
    MockConsultationProvider,
    build_receipt,
    verify_receipt,
)

_NOW = "2026-07-11T00:00:00Z"
_EXP = "2026-07-11T01:00:00Z"


def _request(**overrides):
    base = dict(
        request_id="req-receipt",
        requesting_agent_id="local_apprentice_001",
        mode="critic",
        consulted_provider="mock",
        consulted_model="mock-critic",
        consultation_relation="peer_model",
        question="Review this and list the biggest gaps.",
        purpose="find flaws",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at=_NOW,
        expires_at=_EXP,
        draft="A draft to review.",
    )
    base.update(overrides)
    return ExternalConsultationRequest(**base)


def _outcome(request, *, worker_id="test-worker"):
    service = ExternalConsultationService(
        ConsultationPolicy(), worker_id=worker_id, clock=lambda: _NOW)
    provider = MockConsultationProvider(provider_id="mock")
    return asyncio.run(service.consult(request, provider, now=_NOW))


# --------------------------------------------------------------------------- #
# build + verify
# --------------------------------------------------------------------------- #

def test_receipt_binds_request_and_result_digests():
    request = _request()
    outcome = _outcome(request)
    receipt = outcome.receipt
    assert receipt["request_digest"] == request.request_digest
    assert receipt["result_digest"] == outcome.result.response_digest
    assert verify_receipt(receipt)["receipt_digest"] == receipt["receipt_digest"]


def test_receipt_records_isolation_flags():
    receipt = _outcome(_request()).receipt
    assert receipt["isolated_session"] is True
    assert receipt["tools_disabled"] is True
    assert receipt["delegation_disabled"] is True


def test_receipt_stores_no_secrets_or_reasoning():
    receipt = _outcome(_request()).receipt
    blob = str(receipt).lower()
    for forbidden in ("api_key", "sk-ant", "bearer", "authorization",
                      "chain_of_thought", "reasoning", "raw_text"):
        assert forbidden not in blob


def test_build_receipt_refuses_result_from_a_different_request():
    request_a = _request(request_id="req-a")
    outcome_b = _outcome(_request(request_id="req-b", question="Different q."))
    with pytest.raises(ConsultationError, match="does not match its request"):
        build_receipt(request_a, outcome_b.result, worker_id="w",
                      started_at=_NOW, completed_at=_NOW)


def test_negative_token_usage_refused():
    request = _request()
    outcome = _outcome(request)
    with pytest.raises(ConsultationError, match="counts"):
        build_receipt(request, outcome.result, worker_id="w",
                      started_at=_NOW, completed_at=_NOW,
                      token_usage={"prompt_tokens": -1})


# --------------------------------------------------------------------------- #
# verify fails closed
# --------------------------------------------------------------------------- #

def test_verify_unknown_field_refused():
    receipt = dict(_outcome(_request()).receipt)
    receipt["backdoor"] = 1
    with pytest.raises(ConsultationError, match="missing or unknown"):
        verify_receipt(receipt)


def test_verify_tampered_digest_refused():
    receipt = dict(_outcome(_request()).receipt)
    receipt["provider"] = "someone_else"
    with pytest.raises(ConsultationError, match="digest mismatch"):
        verify_receipt(receipt)


# --------------------------------------------------------------------------- #
# store: idempotency + conflict refusal
# --------------------------------------------------------------------------- #

def test_exact_rerun_is_idempotent(tmp_path):
    receipt = _outcome(_request()).receipt
    store = ConsultationReceiptStore(tmp_path)
    first = store.save(receipt)
    second = store.save(receipt)               # identical content
    assert first == second
    assert store.load(receipt["request_id"])["receipt_digest"] == \
        receipt["receipt_digest"]


def test_conflicting_request_id_refused(tmp_path):
    store = ConsultationReceiptStore(tmp_path)
    original = _outcome(_request()).receipt
    store.save(original)
    # Same request_id, different content (different question => different digest).
    conflicting = _outcome(
        _request(question="A completely different question entirely.")).receipt
    assert conflicting["request_id"] == original["request_id"]
    assert conflicting["receipt_digest"] != original["receipt_digest"]
    with pytest.raises(ConsultationError, match="conflicting"):
        store.save(conflicting)


def test_receipt_digest_changes_when_request_changes():
    a = _outcome(_request()).receipt
    b = _outcome(_request(request_id="req-other")).receipt
    assert a["receipt_digest"] != b["receipt_digest"]


def test_receipt_digest_changes_when_result_changes():
    request = _request(mode="judge", draft=None,
                       candidates=("Answer A", "Answer B"),
                       consulted_model="mock-judge")
    # Different scripted verdict => different result digest => different receipt.
    from backend.dialogues.openclaw_consultation import (
        ConsultationRawResponse)

    def responder_tie(call):
        import json
        return ConsultationRawResponse(
            provider_status="ok",
            raw_text=json.dumps({"verdict": "tie",
                                 "criterion_scores": {"rigor": 5.0},
                                 "rationale": "even", "critical_difference":
                                 "no decisive gap"}))
    service = ExternalConsultationService(
        ConsultationPolicy(), worker_id="w", clock=lambda: _NOW)
    default = asyncio.run(service.consult(
        request, MockConsultationProvider(provider_id="mock"), now=_NOW))
    tie = asyncio.run(service.consult(
        request, MockConsultationProvider(provider_id="mock",
                                          responder=responder_tie), now=_NOW))
    assert default.result.response_digest != tie.result.response_digest
    assert default.receipt["receipt_digest"] != tie.receipt["receipt_digest"]


def test_store_load_missing_returns_none(tmp_path):
    assert ConsultationReceiptStore(tmp_path).load("nope") is None

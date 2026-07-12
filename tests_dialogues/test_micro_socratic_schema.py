"""Micro-Socratic Kernel v1 — request/check schema invariants.

Every construction path fails closed: unknown fields, NaN/Infinity, secret- and
authority/self-certification-shaped content, expired/invalid timestamps,
oversized strings, malformed hashes, inner_rounds!=1, tools/consultation flags,
path-like request ids, bool/int confusion, and per-mode payload/decision
coherence are all refused.
"""

import math
from decimal import Decimal

import pytest

from backend.dialogues.openclaw_socratic_kernel import (
    MAX_TASK_CHARS,
    MicroSocraticCheck,
    MicroSocraticError,
    MicroSocraticRequest,
    validate_check_payload,
)
from backend.dialogues.openclaw_socratic_kernel.schemas import (
    CHECK_VERSION,
    REQUEST_VERSION,
    clean_request_id,
)


def _request(**overrides):
    base = dict(
        request_id="kernel-001",
        agent_id="local_apprentice_001",
        mode="standard",
        provider="mock",
        model="mock-auditor",
        task="Prove the function is idempotent under retries.",
        draft="It is idempotent because writes are keyed by request id.",
        purpose="pre-final self-check",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at="2026-07-11T00:00:00Z",
        expires_at="2026-07-11T01:00:00Z",
    )
    base.update(overrides)
    return MicroSocraticRequest(**base)


_STANDARD_PAYLOAD = {
    "claim_summary": "The procedure is idempotent.",
    "assumptions": ["request_id is unique"],
    "strongest_challenges": ["concurrent writers may bypass the exists check"],
    "verification_requests": [{
        "kind": "code_test",
        "reason": "a concurrent regression test is needed",
        "priority": "required",
    }],
    "decision": "verify_with_tool",
    "revision_guidance": [],
}


# --------------------------------------------------------------------------- #
# valid construction per mode
# --------------------------------------------------------------------------- #

def test_valid_standard_request_roundtrips():
    request = _request()
    assert request.max_inner_rounds == 1
    assert request.tools_allowed is False and request.consultation_allowed is False
    record = request.to_record()
    assert record["schema_version"] == REQUEST_VERSION
    assert MicroSocraticRequest.from_record(record).request_digest == \
        request.request_digest


def test_light_and_high_risk_requests_valid():
    assert _request(mode="light").mode == "light"
    assert _request(mode="high_risk").mode == "high_risk"


def test_unknown_mode_refused():
    with pytest.raises(MicroSocraticError, match="unknown kernel mode"):
        _request(mode="paranoid")


# --------------------------------------------------------------------------- #
# hard invariants (strict typing)
# --------------------------------------------------------------------------- #

def test_inner_rounds_must_be_int_one():
    for bad in (2, 0, True, False, 1.0, "1", Decimal("1")):
        with pytest.raises(MicroSocraticError, match="max_inner_rounds"):
            _request(max_inner_rounds=bad)
    assert _request(max_inner_rounds=1).max_inner_rounds == 1


def test_tools_allowed_true_refused():
    with pytest.raises(MicroSocraticError, match="tools_allowed"):
        _request(tools_allowed=True)


def test_consultation_allowed_true_refused():
    with pytest.raises(MicroSocraticError, match="consultation_allowed"):
        _request(consultation_allowed=True)


# --------------------------------------------------------------------------- #
# bounded / hostile inputs fail closed
# --------------------------------------------------------------------------- #

def test_oversized_task_refused():
    with pytest.raises(MicroSocraticError, match="exceeds"):
        _request(task="x" * (MAX_TASK_CHARS + 1))


def test_oversized_draft_refused():
    with pytest.raises(MicroSocraticError, match="exceeds"):
        _request(draft="d" * 16001)


def test_secret_shaped_task_refused():
    with pytest.raises(MicroSocraticError, match="secret-shaped"):
        _request(task="use api_key = sk-ant-abcd1234efgh5678 now")


def test_nan_and_inf_timeout_refused():
    with pytest.raises(MicroSocraticError, match="finite"):
        _request(timeout_seconds=math.nan)
    with pytest.raises(MicroSocraticError, match="finite"):
        _request(timeout_seconds=math.inf)


def test_invalid_and_semantic_timestamps_refused():
    with pytest.raises(MicroSocraticError, match="ISO-8601"):
        _request(created_at="whenever")
    for stamp in ("2026-13-45T00:00:00Z", "2026-02-30T00:00:00Z",
                  "2026-01-01T25:00:00Z"):
        with pytest.raises(MicroSocraticError):
            _request(expires_at=stamp)


def test_expiry_not_after_creation_refused():
    with pytest.raises(MicroSocraticError, match="after created_at"):
        _request(created_at="2026-07-11T01:00:00Z",
                 expires_at="2026-07-11T00:00:00Z")


@pytest.mark.parametrize("evil", [
    "../../tmp/pwned", "..\\..\\pwned", "C:evil", "x:stream", "/abs", "a/b",
    ".", "..",
])
def test_path_like_request_ids_refused(evil):
    with pytest.raises(MicroSocraticError):
        clean_request_id(evil)
    with pytest.raises(MicroSocraticError):
        _request(request_id=evil)


# --------------------------------------------------------------------------- #
# from_record fails closed
# --------------------------------------------------------------------------- #

def test_from_record_unknown_field_refused():
    record = _request().to_record()
    record["backdoor"] = True
    with pytest.raises(MicroSocraticError, match="missing or unknown"):
        MicroSocraticRequest.from_record(record)


def test_from_record_tampered_hash_refused():
    record = _request().to_record()
    record["task"] = record["task"] + " (edited)"
    with pytest.raises(MicroSocraticError, match="task hash mismatch"):
        MicroSocraticRequest.from_record(record)


def test_from_record_tampered_digest_refused():
    record = _request().to_record()
    record["request_digest"] = "0" * 64
    with pytest.raises(MicroSocraticError, match="digest mismatch"):
        MicroSocraticRequest.from_record(record)


# --------------------------------------------------------------------------- #
# check construction + flag invariants
# --------------------------------------------------------------------------- #

def _check(**overrides):
    base = dict(
        request_id="kernel-001", request_digest="a" * 64,
        agent_id="local_apprentice_001", mode="standard", provider="mock",
        model="mock-auditor", provider_status="ok",
        structured_payload=dict(_STANDARD_PAYLOAD))
    base.update(overrides)
    return MicroSocraticCheck(**base)


def test_valid_check_roundtrips():
    check = _check()
    assert check.isolated_check and not check.tools_executed
    assert check.decision == "verify_with_tool"
    record = check.to_record()
    assert record["schema_version"] == CHECK_VERSION
    assert MicroSocraticCheck.from_record(record).response_digest == \
        check.response_digest


def test_check_from_nonok_status_refused():
    with pytest.raises(MicroSocraticError, match="OK provider status"):
        _check(provider_status="timeout")


def test_check_tools_executed_true_refused():
    with pytest.raises(MicroSocraticError, match="tools_executed"):
        _check(tools_executed=True)


def test_check_consultation_executed_true_refused():
    with pytest.raises(MicroSocraticError, match="consultation_executed"):
        _check(consultation_executed=True)


def test_check_inner_rounds_not_one_refused():
    with pytest.raises(MicroSocraticError, match="inner_rounds"):
        _check(inner_rounds=2)


# --------------------------------------------------------------------------- #
# mode-specific payload validation
# --------------------------------------------------------------------------- #

def test_light_exact_field_set():
    ok = {"claim_summary": "c", "strongest_challenges": ["x"],
          "decision": "accept", "revision_guidance": []}
    assert validate_check_payload("light", ok)["decision"] == "accept"
    with pytest.raises(MicroSocraticError, match="light payload"):
        validate_check_payload("light", dict(ok, assumptions=["y"]))


def test_standard_requires_assumptions_and_verifications():
    incomplete = dict(_STANDARD_PAYLOAD)
    del incomplete["assumptions"]
    with pytest.raises(MicroSocraticError, match="standard payload"):
        validate_check_payload("standard", incomplete)


def test_high_risk_requires_missing_evidence_and_uncertainties():
    payload = {
        "claim_summary": "dosage is right", "assumptions": ["mg units"],
        "strongest_challenges": ["units unstated"],
        "missing_evidence": ["no source"],
        "verification_requests": [{"kind": "calculator", "reason": "recompute",
                                   "priority": "required"}],
        "uncertainties": ["weight basis unclear"],
        "decision": "verify_with_tool", "revision_guidance": [],
    }
    assert validate_check_payload("high_risk", payload)["decision"] == \
        "verify_with_tool"
    bad = dict(payload)
    del bad["uncertainties"]
    with pytest.raises(MicroSocraticError, match="high_risk payload"):
        validate_check_payload("high_risk", bad)


def test_hidden_reasoning_fields_refused():
    for junk in ("chain_of_thought", "reasoning", "scratchpad",
                 "internal_monologue", "thoughts"):
        payload = dict(_STANDARD_PAYLOAD)
        payload[junk] = "secret thinking"
        with pytest.raises(MicroSocraticError, match="missing or unknown"):
            validate_check_payload("standard", payload)


def test_decision_enum_strict():
    with pytest.raises(MicroSocraticError, match="decision"):
        validate_check_payload("standard", dict(_STANDARD_PAYLOAD,
                                                decision="approve_agent"))


def test_light_cannot_pick_tool_or_consult_decisions():
    for d in ("verify_with_tool", "consult_external_model"):
        payload = {"claim_summary": "c", "strongest_challenges": ["x"],
                   "decision": d, "revision_guidance": []}
        with pytest.raises(MicroSocraticError, match="not permitted in light"):
            validate_check_payload("light", payload)


def test_verification_kind_and_priority_strict():
    bad_kind = dict(_STANDARD_PAYLOAD, verification_requests=[
        {"kind": "mind_reading", "reason": "r", "priority": "required"}])
    with pytest.raises(MicroSocraticError, match="verification kind"):
        validate_check_payload("standard", bad_kind)
    bad_pri = dict(_STANDARD_PAYLOAD, verification_requests=[
        {"kind": "web", "reason": "r", "priority": "urgent"}])
    with pytest.raises(MicroSocraticError, match="verification priority"):
        validate_check_payload("standard", bad_pri)


def test_authority_and_self_certification_claims_refused():
    for text in ("I approve this agent", "the agent is certified", "I executed "
                 "the tests", "you are approved as final authority"):
        payload = dict(_STANDARD_PAYLOAD)
        payload["claim_summary"] = text
        with pytest.raises(MicroSocraticError,
                           match="authority/tool/self-certification"):
            validate_check_payload("standard", payload)


# --------------------------------------------------------------------------- #
# decision <-> content coherence (kernel improvement)
# --------------------------------------------------------------------------- #

def test_accept_must_not_carry_revision_guidance():
    payload = dict(_STANDARD_PAYLOAD, decision="accept",
                   revision_guidance=["change X"])
    with pytest.raises(MicroSocraticError, match="accept"):
        validate_check_payload("standard", payload)


def test_revise_requires_revision_guidance():
    payload = dict(_STANDARD_PAYLOAD, decision="revise", revision_guidance=[])
    with pytest.raises(MicroSocraticError, match="revise"):
        validate_check_payload("standard", payload)


def test_verify_with_tool_requires_tool_request():
    payload = dict(_STANDARD_PAYLOAD, decision="verify_with_tool",
                   verification_requests=[{"kind": "user_clarification",
                                           "reason": "ask", "priority": "recommended"}])
    with pytest.raises(MicroSocraticError, match="verify_with_tool"):
        validate_check_payload("standard", payload)


def test_consult_external_model_requires_consultation_request():
    payload = dict(_STANDARD_PAYLOAD, decision="consult_external_model",
                   verification_requests=[{"kind": "web", "reason": "r",
                                           "priority": "recommended"}])
    with pytest.raises(MicroSocraticError, match="consult_external_model"):
        validate_check_payload("standard", payload)
    ok = dict(_STANDARD_PAYLOAD, decision="consult_external_model",
              verification_requests=[{"kind": "external_consultation",
                                      "reason": "second opinion",
                                      "priority": "recommended"}])
    assert validate_check_payload("standard", ok)["decision"] == \
        "consult_external_model"

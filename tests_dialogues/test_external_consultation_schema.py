"""External Self-Consultation v1 — request/result schema invariants.

Every construction path fails closed: unknown fields, NaN/Infinity, secret-
shaped content, expired/invalid timestamps, oversized strings, malformed
hashes, depth>1, tools_allowed, and per-mode draft/candidate rules are all
refused. Advice can never claim authority or tool execution.
"""

import math

import pytest

from backend.dialogues.openclaw_consultation import (
    MAX_QUESTION_CHARS,
    ConsultationError,
    ConsultationResult,
    ExternalConsultationRequest,
    validate_payload,
)
from backend.dialogues.openclaw_consultation.schemas import REQUEST_VERSION


# --------------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------------- #

def _request(**overrides):
    base = dict(
        request_id="req-001",
        requesting_agent_id="local_apprentice_001",
        mode="critic",
        consulted_provider="mock",
        consulted_model="mock-critic",
        consultation_relation="peer_model",
        question="Check this proof and find the biggest logical gap.",
        purpose="find flaws before finalizing",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at="2026-07-11T00:00:00Z",
        expires_at="2026-07-11T01:00:00Z",
        draft="Here is my draft solution: step one, step two.",
    )
    base.update(overrides)
    return ExternalConsultationRequest(**base)


_CRITIC_PAYLOAD = {
    "issues": [{
        "severity": "major",
        "category": "logic",
        "description": "conclusion does not follow",
        "affected_claim": "premise 2 implies the conclusion",
        "suggested_check": "state the missing bridging premise",
    }],
    "strengths": ["precise framing"],
    "missing_assumptions": ["sample is representative"],
    "recommended_checks": ["re-derive from premise 2"],
}


# --------------------------------------------------------------------------- #
# valid per-mode construction + relations
# --------------------------------------------------------------------------- #

def test_valid_critic_request_roundtrips():
    request = _request()
    assert request.consultation_depth == 1
    assert request.tools_allowed is False
    record = request.to_record()
    assert record["schema_version"] == REQUEST_VERSION
    assert ExternalConsultationRequest.from_record(record).request_digest == \
        request.request_digest


def test_independent_solver_forbids_draft_and_candidates():
    request = _request(mode="independent_solver", draft=None)
    assert request.draft is None and request.candidates == ()
    with pytest.raises(ConsultationError, match="forbids a draft"):
        _request(mode="independent_solver", draft="leaked draft")


def test_judge_requires_exactly_two_candidates():
    request = _request(mode="judge", draft=None,
                       candidates=("answer A", "answer B"))
    assert len(request.candidates) == 2
    with pytest.raises(ConsultationError, match="exactly two candidates"):
        _request(mode="judge", draft=None, candidates=("only one",))


def test_critic_requires_draft_and_forbids_candidates():
    with pytest.raises(ConsultationError, match="requires a draft"):
        _request(mode="critic", draft=None)
    with pytest.raises(ConsultationError, match="forbids candidates"):
        _request(mode="critic", candidates=("x", "y"))


def test_same_model_new_session_relation_accepted():
    request = _request(consultation_relation="same_model_new_session")
    assert request.consultation_relation == "same_model_new_session"


def test_peer_model_relation_accepted():
    assert _request(consultation_relation="peer_model").consultation_relation \
        == "peer_model"


def test_unknown_relation_refused():
    with pytest.raises(ConsultationError, match="unknown consultation relation"):
        _request(consultation_relation="browser_chatgpt")


# --------------------------------------------------------------------------- #
# hard invariants
# --------------------------------------------------------------------------- #

def test_depth_greater_than_one_refused():
    with pytest.raises(ConsultationError, match="consultation_depth"):
        _request(consultation_depth=2)


def test_tools_allowed_true_refused():
    with pytest.raises(ConsultationError, match="tools_allowed"):
        _request(tools_allowed=True)


def test_unknown_mode_refused():
    with pytest.raises(ConsultationError, match="unknown consultation mode"):
        _request(mode="oracle")


# --------------------------------------------------------------------------- #
# bounded / hostile inputs fail closed
# --------------------------------------------------------------------------- #

def test_oversized_question_refused():
    with pytest.raises(ConsultationError, match="exceeds"):
        _request(question="x" * (MAX_QUESTION_CHARS + 1))


def test_oversized_draft_refused():
    with pytest.raises(ConsultationError, match="exceeds"):
        _request(draft="d" * 16001)


def test_oversized_candidate_refused():
    with pytest.raises(ConsultationError, match="exceeds"):
        _request(mode="judge", draft=None,
                 candidates=("ok", "c" * 16001))


def test_secret_shaped_question_refused():
    with pytest.raises(ConsultationError, match="secret-shaped"):
        _request(question="please use api_key = sk-ant-abcd1234efgh5678 now")


def test_secret_shaped_draft_refused():
    with pytest.raises(ConsultationError, match="secret-shaped"):
        _request(draft="token: Bearer abcd1234efgh5678ijkl")


def test_nan_timeout_refused():
    with pytest.raises(ConsultationError, match="finite"):
        _request(timeout_seconds=math.nan)


def test_infinite_timeout_refused():
    with pytest.raises(ConsultationError, match="finite"):
        _request(timeout_seconds=math.inf)


def test_zero_max_tokens_refused():
    with pytest.raises(ConsultationError, match="positive integer"):
        _request(max_tokens=0)


def test_bool_max_tokens_refused():
    with pytest.raises(ConsultationError, match="positive integer"):
        _request(max_tokens=True)


def test_invalid_timestamp_refused():
    with pytest.raises(ConsultationError, match="ISO-8601"):
        _request(created_at="yesterday")


def test_expiry_not_after_creation_refused():
    with pytest.raises(ConsultationError, match="after created_at"):
        _request(created_at="2026-07-11T01:00:00Z",
                 expires_at="2026-07-11T00:00:00Z")


def test_too_many_evidence_references_refused():
    with pytest.raises(ConsultationError, match="exceeds"):
        _request(public_evidence_references=tuple(
            f"ref-{i}" for i in range(17)))


# --------------------------------------------------------------------------- #
# from_record fails closed on tampering
# --------------------------------------------------------------------------- #

def test_from_record_unknown_field_refused():
    record = _request().to_record()
    record["backdoor"] = True
    with pytest.raises(ConsultationError, match="missing or unknown"):
        ExternalConsultationRequest.from_record(record)


def test_from_record_missing_field_refused():
    record = _request().to_record()
    del record["purpose"]
    with pytest.raises(ConsultationError, match="missing or unknown"):
        ExternalConsultationRequest.from_record(record)


def test_from_record_tampered_question_hash_refused():
    record = _request().to_record()
    record["question"] = record["question"] + " (edited)"
    with pytest.raises(ConsultationError, match="hash mismatch"):
        ExternalConsultationRequest.from_record(record)


def test_from_record_tampered_digest_refused():
    record = _request().to_record()
    record["request_digest"] = "0" * 64
    with pytest.raises(ConsultationError, match="digest mismatch"):
        ExternalConsultationRequest.from_record(record)


def test_from_record_wrong_schema_version_refused():
    record = _request().to_record()
    record["schema_version"] = "openclaw_external_consultation_request_v2"
    with pytest.raises(ConsultationError, match="schema version"):
        ExternalConsultationRequest.from_record(record)


# --------------------------------------------------------------------------- #
# result payload validation
# --------------------------------------------------------------------------- #

def test_valid_result_roundtrips():
    result = ConsultationResult(
        request_id="req-001", request_digest="a" * 64, mode="critic",
        provider="mock", model="mock-critic", provider_status="ok",
        structured_payload=dict(_CRITIC_PAYLOAD))
    assert result.isolated_session is True
    record = result.to_record()
    assert ConsultationResult.from_record(record).response_digest == \
        result.response_digest


def test_result_from_nonok_status_refused():
    with pytest.raises(ConsultationError, match="OK provider status"):
        ConsultationResult(
            request_id="req-001", request_digest="a" * 64, mode="critic",
            provider="mock", model="mock-critic", provider_status="timeout",
            structured_payload=dict(_CRITIC_PAYLOAD))


def test_result_isolation_flag_false_refused():
    with pytest.raises(ConsultationError, match="tools_disabled must be true"):
        ConsultationResult(
            request_id="req-001", request_digest="a" * 64, mode="critic",
            provider="mock", model="mock-critic", provider_status="ok",
            structured_payload=dict(_CRITIC_PAYLOAD), tools_disabled=False)


def test_critic_payload_unknown_field_refused():
    payload = dict(_CRITIC_PAYLOAD, extra="nope")
    with pytest.raises(ConsultationError, match="missing or unknown"):
        validate_payload("critic", payload)


def test_critic_issue_missing_field_refused():
    payload = dict(_CRITIC_PAYLOAD)
    payload["issues"] = [{"severity": "major", "category": "logic",
                          "description": "x", "affected_claim": "y"}]
    with pytest.raises(ConsultationError, match="issue has missing or unknown"):
        validate_payload("critic", payload)


def test_critic_issue_bad_severity_refused():
    payload = dict(_CRITIC_PAYLOAD)
    payload["issues"] = [dict(_CRITIC_PAYLOAD["issues"][0], severity="fatal")]
    with pytest.raises(ConsultationError, match="unknown issue severity"):
        validate_payload("critic", payload)


def test_wrong_mode_payload_refused():
    # A judge payload is not a valid critic payload.
    judge_payload = {
        "verdict": "candidate_a", "criterion_scores": {"rigor": 7.0},
        "rationale": "because", "critical_difference": "A justifies its step",
    }
    with pytest.raises(ConsultationError, match="critic payload"):
        validate_payload("critic", judge_payload)


def test_judge_bad_verdict_refused():
    payload = {
        "verdict": "candidate_c", "criterion_scores": {"rigor": 7.0},
        "rationale": "x", "critical_difference": "y",
    }
    with pytest.raises(ConsultationError, match="unknown judge verdict"):
        validate_payload("judge", payload)


def test_judge_score_out_of_range_refused():
    payload = {
        "verdict": "tie", "criterion_scores": {"rigor": 42.0},
        "rationale": "x", "critical_difference": "y",
    }
    with pytest.raises(ConsultationError, match="criterion_scores"):
        validate_payload("judge", payload)


def test_judge_nan_score_refused():
    payload = {
        "verdict": "tie", "criterion_scores": {"rigor": math.nan},
        "rationale": "x", "critical_difference": "y",
    }
    with pytest.raises(ConsultationError, match="finite"):
        validate_payload("judge", payload)


def test_payload_authority_claim_refused():
    # A consulted model must not smuggle a tool-use / approval claim.
    payload = dict(_CRITIC_PAYLOAD)
    payload["strengths"] = ["I executed the test suite and I approve this"]
    with pytest.raises(ConsultationError, match="authority/tool-use claim"):
        validate_payload("critic", payload)


def test_independent_answer_authority_claim_refused():
    payload = {
        "independent_answer": "I invoked the calculator tool to verify.",
        "assumptions": [], "uncertainties": [],
        "recommended_verifications": [],
    }
    with pytest.raises(ConsultationError, match="authority/tool-use claim"):
        validate_payload("independent_solver", payload)


def test_payload_secret_shaped_refused():
    payload = dict(_CRITIC_PAYLOAD)
    payload["recommended_checks"] = ["set api_key = sk-ant-secretkey12345678"]
    with pytest.raises(ConsultationError, match="secret-shaped"):
        validate_payload("critic", payload)

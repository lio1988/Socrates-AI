"""External Self-Consultation v1 — policy gate (time-of-use checks).

The policy re-asserts the hard invariants and adds expiration, a provider
allow-list, and per-operator ceilings. Every violation fails closed with no
provider call.
"""

import pytest

from backend.dialogues.openclaw_consultation import (
    ConsultationError,
    ConsultationPolicy,
    ExternalConsultationRequest,
    enforce_policy,
)


def _request(**overrides):
    base = dict(
        request_id="req-policy",
        requesting_agent_id="local_apprentice_001",
        mode="independent_solver",
        consulted_provider="mock",
        consulted_model="mock-solver",
        consultation_relation="peer_model",
        question="Solve this independently.",
        purpose="independent cross-check",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at="2026-07-11T00:00:00Z",
        expires_at="2026-07-11T01:00:00Z",
    )
    base.update(overrides)
    return ExternalConsultationRequest(**base)


def test_valid_request_passes_before_expiry():
    enforce_policy(_request(), ConsultationPolicy(),
                   now="2026-07-11T00:30:00Z")


def test_expired_request_refused():
    with pytest.raises(ConsultationError, match="expired"):
        enforce_policy(_request(), ConsultationPolicy(),
                       now="2026-07-11T02:00:00Z")


def test_expiry_exactly_now_refused():
    with pytest.raises(ConsultationError, match="expired"):
        enforce_policy(_request(), ConsultationPolicy(),
                       now="2026-07-11T01:00:00Z")


def test_expiry_compares_across_offset_and_z_notation():
    # created/expires in Z; 'now' supplied with an explicit +00:00 offset.
    enforce_policy(_request(), ConsultationPolicy(),
                   now="2026-07-11T00:30:00+00:00")


def test_provider_not_allow_listed_refused():
    policy = ConsultationPolicy(allowed_providers=("trusted_peer",))
    with pytest.raises(ConsultationError, match="not allow-listed"):
        enforce_policy(_request(consulted_provider="mock"), policy,
                       now="2026-07-11T00:10:00Z")


def test_provider_allow_listed_passes():
    policy = ConsultationPolicy(allowed_providers=("mock",))
    enforce_policy(_request(consulted_provider="mock"), policy,
                   now="2026-07-11T00:10:00Z")


def test_request_tokens_over_policy_ceiling_refused():
    policy = ConsultationPolicy(max_tokens=512)
    with pytest.raises(ConsultationError, match="max_tokens exceeds"):
        enforce_policy(_request(max_tokens=1024), policy,
                       now="2026-07-11T00:10:00Z")


def test_request_timeout_over_policy_ceiling_refused():
    policy = ConsultationPolicy(max_timeout_seconds=10.0)
    with pytest.raises(ConsultationError, match="timeout exceeds"):
        enforce_policy(_request(timeout_seconds=60.0), policy,
                       now="2026-07-11T00:10:00Z")


def test_evidence_references_over_policy_limit_refused():
    policy = ConsultationPolicy(max_evidence_references=1)
    request = _request(public_evidence_references=("a", "b"))
    with pytest.raises(ConsultationError, match="evidence references exceed"):
        enforce_policy(request, policy, now="2026-07-11T00:10:00Z")


def test_policy_ceiling_may_not_exceed_schema_ceiling():
    with pytest.raises(ConsultationError, match="max_tokens out of range"):
        ConsultationPolicy(max_tokens=999999)
    with pytest.raises(ConsultationError, match="timeout"):
        ConsultationPolicy(max_timeout_seconds=999999.0)

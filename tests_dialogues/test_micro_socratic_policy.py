"""Micro-Socratic Kernel v1 — policy gate (time-of-use checks)."""

import pytest

from backend.dialogues.openclaw_socratic_kernel import (
    KernelPolicy,
    MicroSocraticError,
    MicroSocraticRequest,
    enforce_policy,
)


def _request(**overrides):
    base = dict(
        request_id="kernel-policy",
        agent_id="local_apprentice_001",
        mode="standard",
        provider="mock",
        model="mock-auditor",
        task="Check this reasoning for gaps.",
        draft="Here is my reasoning in three steps.",
        purpose="pre-final self-check",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at="2026-07-11T00:00:00Z",
        expires_at="2026-07-11T01:00:00Z",
    )
    base.update(overrides)
    return MicroSocraticRequest(**base)


def test_valid_request_passes_before_expiry():
    enforce_policy(_request(), KernelPolicy(), now="2026-07-11T00:30:00Z")


def test_expired_request_refused():
    with pytest.raises(MicroSocraticError, match="expired"):
        enforce_policy(_request(), KernelPolicy(), now="2026-07-11T02:00:00Z")


def test_expiry_compares_across_offset_and_z():
    enforce_policy(_request(), KernelPolicy(), now="2026-07-11T00:30:00+00:00")


def test_provider_not_allow_listed_refused():
    policy = KernelPolicy(allowed_providers=("trusted_auditor",))
    with pytest.raises(MicroSocraticError, match="not allow-listed"):
        enforce_policy(_request(provider="mock"), policy,
                       now="2026-07-11T00:10:00Z")


def test_provider_allow_listed_passes():
    policy = KernelPolicy(allowed_providers=("mock",))
    enforce_policy(_request(provider="mock"), policy, now="2026-07-11T00:10:00Z")


def test_tokens_over_policy_ceiling_refused():
    policy = KernelPolicy(max_tokens=512)
    with pytest.raises(MicroSocraticError, match="max_tokens exceeds"):
        enforce_policy(_request(max_tokens=1024), policy,
                       now="2026-07-11T00:10:00Z")


def test_timeout_over_policy_ceiling_refused():
    policy = KernelPolicy(max_timeout_seconds=10.0)
    with pytest.raises(MicroSocraticError, match="timeout exceeds"):
        enforce_policy(_request(timeout_seconds=60.0), policy,
                       now="2026-07-11T00:10:00Z")


def test_policy_ceiling_may_not_exceed_schema_ceiling():
    with pytest.raises(MicroSocraticError, match="max_tokens out of range"):
        KernelPolicy(max_tokens=999999)
    with pytest.raises(MicroSocraticError, match="timeout"):
        KernelPolicy(max_timeout_seconds=999999.0)

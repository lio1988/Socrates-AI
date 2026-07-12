"""Policy gate for External Self-Consultation v1.

The request schema already enforces the structural invariants (depth == 1,
tools_allowed == false, mode-specific draft/candidates, size ceilings). The
policy adds the TIME-of-USE checks a stored request needs before a provider
is ever contacted: expiration, an allow-list of providers, and per-operator
budget ceilings that may be stricter than the schema ceilings.

Fails closed: any violation raises ConsultationError and no provider call
happens.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional, Tuple

from .schemas import (
    MAX_TIMEOUT_SECONDS,
    MAX_TOKENS_CEILING,
    ConsultationError,
    ExternalConsultationRequest,
    clean_iso,
    iso_utc,
)


@dataclass(frozen=True)
class ConsultationPolicy:
    """Operator-configurable ceilings, never looser than the schema."""
    allowed_providers: Optional[Tuple[str, ...]] = None   # None = any provider
    max_tokens: int = MAX_TOKENS_CEILING
    max_timeout_seconds: float = MAX_TIMEOUT_SECONDS
    max_evidence_references: int = 16

    def __post_init__(self) -> None:
        if self.max_tokens < 1 or self.max_tokens > MAX_TOKENS_CEILING:
            raise ConsultationError("policy max_tokens out of range")
        if not 0.1 <= self.max_timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ConsultationError("policy max_timeout_seconds out of range")


def enforce_policy(
    request: ExternalConsultationRequest,
    policy: ConsultationPolicy,
    *,
    now: Optional[str] = None,
) -> None:
    """Raise ConsultationError unless the request may proceed right now."""
    # depth and tools are guaranteed by the schema, but re-assert here so the
    # policy gate is a complete, self-contained safety statement.
    if request.consultation_depth != 1:
        raise ConsultationError("policy refuses consultation_depth != 1")
    if request.tools_allowed is not False:
        raise ConsultationError("policy refuses tools_allowed")

    if policy.allowed_providers is not None and \
            request.consulted_provider not in policy.allowed_providers:
        raise ConsultationError(
            f"provider {request.consulted_provider!r} is not allow-listed")
    if request.max_tokens > policy.max_tokens:
        raise ConsultationError("request max_tokens exceeds policy ceiling")
    if request.timeout_seconds > policy.max_timeout_seconds:
        raise ConsultationError("request timeout exceeds policy ceiling")
    if len(request.public_evidence_references) > policy.max_evidence_references:
        raise ConsultationError("request evidence references exceed policy limit")

    reference = clean_iso(now, field="now") if now else \
        _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if iso_utc(reference) >= iso_utc(request.expires_at):
        raise ConsultationError("consultation request has expired")


__all__ = ["ConsultationPolicy", "enforce_policy"]

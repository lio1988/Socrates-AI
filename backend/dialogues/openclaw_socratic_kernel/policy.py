"""Policy gate for the Micro-Socratic Kernel v1.

The request schema already enforces the structural invariants (inner_rounds == 1,
tools_allowed == false, consultation_allowed == false, size ceilings). The policy
adds the TIME-of-USE checks a stored request needs before a provider is ever
contacted: expiration, an allow-list of providers, and per-operator budget
ceilings that may be stricter than the schema ceilings.

Fails closed: any violation raises MicroSocraticError and no provider call
happens.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional, Tuple

from .schemas import (
    MAX_TIMEOUT_SECONDS,
    MAX_TOKENS_CEILING,
    MicroSocraticError,
    MicroSocraticRequest,
    clean_iso,
    iso_utc,
)


@dataclass(frozen=True)
class KernelPolicy:
    """Operator-configurable ceilings, never looser than the schema."""
    allowed_providers: Optional[Tuple[str, ...]] = None   # None = any provider
    max_tokens: int = MAX_TOKENS_CEILING
    max_timeout_seconds: float = MAX_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.max_tokens < 1 or self.max_tokens > MAX_TOKENS_CEILING:
            raise MicroSocraticError("policy max_tokens out of range")
        if not 0.1 <= self.max_timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise MicroSocraticError("policy max_timeout_seconds out of range")


def enforce_policy(
    request: MicroSocraticRequest,
    policy: KernelPolicy,
    *,
    now: Optional[str] = None,
) -> None:
    """Raise MicroSocraticError unless the request may proceed right now."""
    # These are guaranteed by the schema, but re-asserted so the policy gate is
    # a complete, self-contained safety statement.
    if request.max_inner_rounds != 1:
        raise MicroSocraticError("policy refuses max_inner_rounds != 1")
    if request.tools_allowed is not False:
        raise MicroSocraticError("policy refuses tools_allowed")
    if request.consultation_allowed is not False:
        raise MicroSocraticError("policy refuses consultation_allowed")

    if policy.allowed_providers is not None and \
            request.provider not in policy.allowed_providers:
        raise MicroSocraticError(
            f"provider {request.provider!r} is not allow-listed")
    if request.max_tokens > policy.max_tokens:
        raise MicroSocraticError("request max_tokens exceeds policy ceiling")
    if request.timeout_seconds > policy.max_timeout_seconds:
        raise MicroSocraticError("request timeout exceeds policy ceiling")

    reference = clean_iso(now, field="now") if now else \
        _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if iso_utc(reference) >= iso_utc(request.expires_at):
        raise MicroSocraticError("kernel request has expired")


__all__ = ["KernelPolicy", "enforce_policy"]

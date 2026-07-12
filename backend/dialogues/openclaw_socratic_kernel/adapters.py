"""The clean adapter boundary for the Micro-Socratic Kernel.

The auditor model NEVER receives an ``AgentTask`` (council-internal) or any agent
state. It receives ONLY a ``KernelCall``: a freshly built system prompt, a single
user message, and the token/timeout budget. A ``KernelProvider`` turns that call
into raw text plus a provider status.

Every call is stateless by construction: no history, no Memory/Identity/Soul, no
scratchpad, no previous kernel checks, no credentials, no tools. The provider is
handed exactly one call and returns exactly one response.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable

from .schemas import MicroSocraticError


@dataclass(frozen=True)
class KernelCall:
    """The complete, isolated payload sent to the auditor model."""
    system_prompt: str
    user_prompt: str
    max_tokens: int
    timeout_seconds: float
    provider: str
    model: str
    request_id: str


@dataclass(frozen=True)
class KernelRawResponse:
    """What a provider returns: raw text + status + optional token usage.

    ``provider_status`` uses the same vocabulary as the council providers
    ("ok", "timeout", "error", ...). Anything other than "ok" makes the service
    fail closed with no accepted check.
    """
    provider_status: str
    raw_text: str = ""
    token_usage: Optional[Dict[str, int]] = None
    error_message: str = ""


@runtime_checkable
class KernelProvider(Protocol):
    provider_id: str

    async def check(self, call: KernelCall) -> KernelRawResponse:
        ...


# ── Deterministic mock adapter (tests + operator demo) ───────────────────────

class MockKernelProvider:
    """Records the EXACT call it received and returns a scripted response.

    Tests assert on ``self.calls`` to prove isolation: no prior history, no
    profile, no tools, no nested call - the provider only ever sees the
    ``KernelCall`` fields.
    """

    def __init__(
        self,
        provider_id: str = "mock",
        *,
        responder: Optional[Callable[[KernelCall], KernelRawResponse]] = None,
    ) -> None:
        self.provider_id = provider_id
        self._responder = responder or default_mock_responder
        self.calls: List[KernelCall] = []

    async def check(self, call: KernelCall) -> KernelRawResponse:
        self.calls.append(call)
        return self._responder(call)


class TimeoutKernelProvider:
    """Always times out - the service must produce no fabricated check."""

    provider_id = "mock_timeout"

    def __init__(self, provider_id: str = "mock_timeout") -> None:
        self.provider_id = provider_id
        self.calls: List[KernelCall] = []

    async def check(self, call: KernelCall) -> KernelRawResponse:
        self.calls.append(call)
        return KernelRawResponse(provider_status="timeout",
                                 error_message="kernel provider timed out")


def _mode_of(call: KernelCall) -> str:
    marker = "OPENCLAW_MICRO_SOCRATIC_MODE:"
    for line in call.system_prompt.splitlines():
        if line.startswith(marker):
            return line[len(marker):].strip()
    raise MicroSocraticError("mock responder cannot determine mode")


def default_mock_responder(call: KernelCall) -> KernelRawResponse:
    """Return schema-valid JSON per mode (no tools, no authority claims)."""
    import json

    mode = _mode_of(call)
    if mode == "light":
        payload = {
            "claim_summary": "The draft answers the task directly.",
            "strongest_challenges": [
                "One edge case is not addressed."],
            "decision": "accept",
            "revision_guidance": [],
        }
    elif mode == "standard":
        payload = {
            "claim_summary": "The proposed procedure is idempotent.",
            "assumptions": ["the request id is unique"],
            "strongest_challenges": [
                "two concurrent writers may bypass the exists check"],
            "verification_requests": [{
                "kind": "code_test",
                "reason": "a concurrent regression test is needed",
                "priority": "required",
            }],
            "decision": "verify_with_tool",
            "revision_guidance": [],
        }
    else:  # high_risk
        payload = {
            "claim_summary": "The dosage calculation is correct.",
            "assumptions": ["the units are milligrams"],
            "strongest_challenges": [
                "the unit assumption is not stated in the task"],
            "missing_evidence": ["no source for the conversion factor"],
            "verification_requests": [{
                "kind": "calculator",
                "reason": "the multi-step percentage needs recomputation",
                "priority": "required",
            }],
            "uncertainties": ["the patient weight basis is unclear"],
            "decision": "verify_with_tool",
            "revision_guidance": [],
        }
    return KernelRawResponse(
        provider_status="ok",
        raw_text=json.dumps(payload),
        token_usage={"prompt_tokens": 0, "completion_tokens": 0})


async def run_kernel_check(provider: KernelProvider,
                           call: KernelCall) -> KernelRawResponse:
    """One provider call, wrapped in the request's own timeout. A timeout is a
    clean non-OK status, never a raise into the service."""
    try:
        return await asyncio.wait_for(provider.check(call),
                                      timeout=call.timeout_seconds)
    except asyncio.TimeoutError:
        return KernelRawResponse(provider_status="timeout",
                                 error_message="kernel check exceeded timeout")
    except Exception as exc:                        # provider crash = fail closed
        return KernelRawResponse(
            provider_status="error",
            error_message=f"kernel provider error: {exc.__class__.__name__}")


__all__ = [
    "KernelCall", "KernelRawResponse", "KernelProvider",
    "MockKernelProvider", "TimeoutKernelProvider",
    "default_mock_responder", "run_kernel_check",
]

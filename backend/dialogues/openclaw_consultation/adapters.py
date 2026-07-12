"""The clean adapter boundary for External Self-Consultation.

The consulted model NEVER receives an ``AgentTask`` (that is council-internal
and carries roster/context an isolated advisor must not see). Instead a
``ConsultationCall`` carries ONLY a freshly built system prompt, a single user
message, and the token/timeout budget. A ``ConsultationProvider`` turns that
call into raw text plus a provider status.

This boundary is why a future Tool-PC or experimental browser-chat adapter can
be added without touching any schema, policy, or receipt contract: it just has
to satisfy ``ConsultationProvider``.

Every call is stateless by construction: the call object contains no history,
no profile, no scratchpad, no tools, and the provider is handed exactly one
call and returns exactly one response.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from .schemas import ConsultationError


@dataclass(frozen=True)
class ConsultationCall:
    """The complete, isolated payload sent to a consulted model."""
    system_prompt: str
    user_prompt: str
    max_tokens: int
    timeout_seconds: float
    provider: str
    model: str
    request_id: str


@dataclass(frozen=True)
class ConsultationRawResponse:
    """What a provider returns: raw text + status + optional token usage.

    ``provider_status`` uses the same vocabulary as the council providers
    ("ok", "timeout", "error", ...). Anything other than "ok" makes the
    service fail closed with no accepted result.
    """
    provider_status: str
    raw_text: str = ""
    token_usage: Optional[Dict[str, int]] = None
    error_message: str = ""


@runtime_checkable
class ConsultationProvider(Protocol):
    provider_id: str

    async def consult(self, call: ConsultationCall) -> ConsultationRawResponse:
        ...


# ── Deterministic mock adapter (tests + operator demo) ───────────────────────

class MockConsultationProvider:
    """Records the EXACT call it received and returns a scripted response.

    Tests assert on ``self.calls`` to prove isolation: no prior chat history,
    no hidden profile, no tools, no nested call - the provider only ever sees
    the ``ConsultationCall`` fields.
    """

    def __init__(
        self,
        provider_id: str = "mock",
        *,
        responder: Optional[Callable[[ConsultationCall],
                                     ConsultationRawResponse]] = None,
    ) -> None:
        self.provider_id = provider_id
        self._responder = responder or default_mock_responder
        self.calls: List[ConsultationCall] = []

    async def consult(self, call: ConsultationCall) -> ConsultationRawResponse:
        self.calls.append(call)
        return self._responder(call)


class TimeoutConsultationProvider:
    """Always times out - the service must produce no fabricated result."""

    provider_id = "mock_timeout"

    def __init__(self, provider_id: str = "mock_timeout") -> None:
        self.provider_id = provider_id
        self.calls: List[ConsultationCall] = []

    async def consult(self, call: ConsultationCall) -> ConsultationRawResponse:
        self.calls.append(call)
        return ConsultationRawResponse(
            provider_status="timeout",
            error_message="consulted provider timed out")


def _mode_of(call: ConsultationCall) -> str:
    marker = "OPENCLAW_CONSULTATION_MODE:"
    for line in call.system_prompt.splitlines():
        if line.startswith(marker):
            return line[len(marker):].strip()
    raise ConsultationError("mock responder cannot determine mode")


def default_mock_responder(call: ConsultationCall) -> ConsultationRawResponse:
    """Return schema-valid JSON per mode (no tools, no authority claims)."""
    import json

    mode = _mode_of(call)
    if mode == "critic":
        payload = {
            "issues": [{
                "severity": "major",
                "category": "logic",
                "description": "The conclusion does not follow from premise 2.",
                "affected_claim": "premise 2 implies the conclusion",
                "suggested_check": "state the missing bridging premise",
            }],
            "strengths": ["the framing of the question is precise"],
            "missing_assumptions": ["assumes the sample is representative"],
            "recommended_checks": ["re-derive the step from premise 2"],
        }
    elif mode == "independent_solver":
        payload = {
            "independent_answer": "A bounded independent answer to the task.",
            "assumptions": ["the task statement is complete"],
            "uncertainties": ["the domain boundary is unstated"],
            "recommended_verifications": ["confirm the domain boundary"],
        }
    else:  # judge
        payload = {
            "verdict": "candidate_a",
            "criterion_scores": {"rigor": 7.0, "clarity": 6.0},
            "rationale": "Candidate A grounds each step; candidate B asserts.",
            "critical_difference": "A justifies the load-bearing step, B omits it.",
        }
    return ConsultationRawResponse(
        provider_status="ok",
        raw_text=json.dumps(payload),
        token_usage={"prompt_tokens": 0, "completion_tokens": 0})


async def run_consultation(provider: ConsultationProvider,
                           call: ConsultationCall) -> ConsultationRawResponse:
    """One provider call, wrapped in the request's own timeout. A timeout is a
    clean non-OK status, never a raise into the service."""
    try:
        return await asyncio.wait_for(provider.consult(call),
                                      timeout=call.timeout_seconds)
    except asyncio.TimeoutError:
        return ConsultationRawResponse(
            provider_status="timeout",
            error_message="consultation exceeded its timeout")
    except Exception as exc:                       # provider crash = fail closed
        return ConsultationRawResponse(
            provider_status="error",
            error_message=f"consultation provider error: {exc.__class__.__name__}")


__all__ = [
    "ConsultationCall",
    "ConsultationRawResponse",
    "ConsultationProvider",
    "MockConsultationProvider",
    "TimeoutConsultationProvider",
    "default_mock_responder",
    "run_consultation",
]

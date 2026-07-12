"""ExternalConsultationService - the single v1 orchestration surface.

    request -> policy -> isolated prompt -> ONE provider call -> status check
    -> strict per-mode parse -> receipt -> (result, receipt)

The service NEVER touches SessionState, Memory, Identity, or Soul; never
creates or approves a proposal; never calls CED; never performs a second
provider call for repair; never nests a consultation. Exactly one provider
call happens per request, and any failure (policy, timeout, non-OK status,
malformed JSON, wrong payload) fails closed with no fabricated result.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional, Tuple

from .adapters import (
    ConsultationCall,
    ConsultationProvider,
    run_consultation,
)
from .parser import parse_structured_payload
from .policy import ConsultationPolicy, enforce_policy
from .prompting import build_system_prompt, build_user_prompt
from .receipts import build_receipt
from .schemas import (
    ConsultationError,
    ConsultationResult,
    ExternalConsultationRequest,
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ConsultationOutcome:
    result: ConsultationResult
    receipt: dict


class ExternalConsultationService:
    """Isolated advisory consultation. Advice only - never authority."""

    def __init__(
        self,
        policy: Optional[ConsultationPolicy] = None,
        *,
        worker_id: str = "consultation-worker",
        clock=_now_iso,
    ) -> None:
        self.policy = policy or ConsultationPolicy()
        self.worker_id = worker_id
        self._clock = clock

    async def consult(
        self,
        request: ExternalConsultationRequest,
        provider: ConsultationProvider,
        *,
        now: Optional[str] = None,
    ) -> ConsultationOutcome:
        # 1. policy (schema already validated the request on construction).
        enforce_policy(request, self.policy, now=now)

        # The provider must be the one the request names - a caller cannot
        # silently consult a different, unvetted provider.
        if getattr(provider, "provider_id", None) != request.consulted_provider:
            raise ConsultationError(
                "provider does not match the request's consulted_provider")

        # 2. build the isolated call (system + single user message only). The
        # prompt is fully determined by the canonical request (judge order is
        # request.candidate_order), so nothing outside the digest shapes it.
        call = ConsultationCall(
            system_prompt=build_system_prompt(request),
            user_prompt=build_user_prompt(request),
            max_tokens=request.max_tokens,
            timeout_seconds=request.timeout_seconds,
            provider=request.consulted_provider,
            model=request.consulted_model,
            request_id=request.request_id,
        )

        started_at = self._clock()
        # 3. exactly one provider call, bounded by the request timeout.
        raw = await run_consultation(provider, call)
        completed_at = self._clock()

        # 4. non-OK status fails closed - no accepted result, no repair call.
        if raw.provider_status != "ok":
            raise ConsultationError(
                f"consultation provider status {raw.provider_status!r} "
                "produced no accepted result")

        # 5. strict per-mode parse (never trust valid-looking JSON).
        payload = parse_structured_payload(request.mode, raw.raw_text)

        # 6. build the result (its own validation re-asserts every invariant).
        result = ConsultationResult(
            request_id=request.request_id,
            request_digest=request.request_digest,
            mode=request.mode,
            provider=request.consulted_provider,
            model=request.consulted_model,
            provider_status="ok",
            structured_payload=payload,
        )

        # 7. tamper-evident receipt binding request+result.
        receipt = build_receipt(
            request, result,
            worker_id=self.worker_id,
            started_at=started_at,
            completed_at=completed_at,
            token_usage=raw.token_usage,
        )
        return ConsultationOutcome(result=result, receipt=receipt)


# ── Runtime-inert integration seam (NOT wired into CED in v1) ────────────────

class ConsultationGateway:
    """A future phase may let a draft trigger a bounded self-consultation:

        draft -> bounded self-questioning -> request -> result -> optional
        revised draft

    This seam exists so that wiring can be added later WITHOUT importing the
    consultation package into the CED runtime (which would break the existing
    runtime-inert boundary, test-locked). In v1 it only exposes the service;
    it performs no automatic consultation and holds no CED reference.
    """

    def __init__(self, service: ExternalConsultationService) -> None:
        self._service = service

    @property
    def service(self) -> ExternalConsultationService:
        return self._service


__all__ = [
    "ExternalConsultationService",
    "ConsultationOutcome",
    "ConsultationGateway",
]

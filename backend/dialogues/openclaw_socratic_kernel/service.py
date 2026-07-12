"""MicroSocraticKernelService - the single v1 orchestration surface.

    request -> policy -> isolated prompt -> ONE provider call -> status check
    -> strict per-mode parse -> receipt -> (check, receipt)

The service NEVER touches SessionState, Memory, Identity, or Soul; never changes
the draft; never produces a final answer; never creates or approves a proposal;
never calls CED; never executes a tool; never opens a consultation; never
performs a second provider call for repair; never nests a self-check. Exactly one
provider call happens per request, and any failure (policy, timeout, non-OK
status, malformed JSON, wrong payload) fails closed with no fabricated check.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

from .adapters import KernelCall, KernelProvider, run_kernel_check
from .parser import parse_check_payload
from .policy import KernelPolicy, enforce_policy
from .prompting import build_system_prompt, build_user_prompt
from .receipts import build_receipt
from .schemas import (
    MicroSocraticCheck,
    MicroSocraticError,
    MicroSocraticRequest,
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class KernelOutcome:
    check: MicroSocraticCheck
    receipt: dict


class MicroSocraticKernelService:
    """A bounded local self-check. Recommendation only - never authority."""

    def __init__(
        self,
        policy: Optional[KernelPolicy] = None,
        *,
        worker_id: str = "kernel-worker",
        clock=_now_iso,
    ) -> None:
        self.policy = policy or KernelPolicy()
        self.worker_id = worker_id
        self._clock = clock

    async def check(
        self,
        request: MicroSocraticRequest,
        provider: KernelProvider,
        *,
        now: Optional[str] = None,
    ) -> KernelOutcome:
        # 1. policy (schema already validated the request on construction).
        enforce_policy(request, self.policy, now=now)

        # The provider must be the one the request names.
        if getattr(provider, "provider_id", None) != request.provider:
            raise MicroSocraticError(
                "provider does not match the request's provider")

        # 2. build the isolated call (system + single user message only). The
        # prompt is a pure function of the canonical request.
        call = KernelCall(
            system_prompt=build_system_prompt(request),
            user_prompt=build_user_prompt(request),
            max_tokens=request.max_tokens,
            timeout_seconds=request.timeout_seconds,
            provider=request.provider,
            model=request.model,
            request_id=request.request_id,
        )

        started_at = self._clock()
        # 3. exactly one provider call, bounded by the request timeout.
        raw = await run_kernel_check(provider, call)
        completed_at = self._clock()

        # 4. non-OK status fails closed - no accepted check, no repair call.
        if raw.provider_status != "ok":
            raise MicroSocraticError(
                f"kernel provider status {raw.provider_status!r} "
                "produced no accepted check")

        # 5. strict per-mode parse (never trust valid-looking JSON).
        payload = parse_check_payload(request.mode, raw.raw_text)

        # 6. build the check (its own validation re-asserts every invariant).
        check = MicroSocraticCheck(
            request_id=request.request_id,
            request_digest=request.request_digest,
            agent_id=request.agent_id,
            mode=request.mode,
            provider=request.provider,
            model=request.model,
            provider_status="ok",
            structured_payload=payload,
        )

        # 7. tamper-evident receipt binding request+check.
        receipt = build_receipt(
            request, check,
            worker_id=self.worker_id,
            started_at=started_at,
            completed_at=completed_at,
            token_usage=raw.token_usage,
        )
        return KernelOutcome(check=check, receipt=receipt)


# ── Runtime-inert integration seam (NOT wired into CED in v1) ────────────────

class KernelGateway:
    """A future phase may let a draft trigger a bounded self-check:

        draft -> Micro-Socratic Check -> caller evaluates decision -> optional
        governed tool/consultation request -> optional revision

    This seam exists so wiring can be added later WITHOUT importing the kernel
    package into the CED runtime (which would break the existing runtime-inert
    boundary). In v1 it only exposes the service; it performs no automatic
    check, opens no consultation, executes no tool, and holds no CED reference.

        Micro-Socratic Kernel recommends.
        External Consultation advises.
        CED / governance decides.
    """

    def __init__(self, service: MicroSocraticKernelService) -> None:
        self._service = service

    @property
    def service(self) -> MicroSocraticKernelService:
        return self._service


__all__ = [
    "MicroSocraticKernelService",
    "KernelOutcome",
    "KernelGateway",
]

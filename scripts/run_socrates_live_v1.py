"""Run one Socrates dialogue against the live OpenRouter route.

Entry point:

    run_socrates("any question here", max_calls=30, max_total_usd="2.00")

CED remains the transition authority. This only wires the proven live transport
in behind the existing provider seam, bounds the spend, and records what
happened. Nothing here decides a dialogue move.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import CouncilProviderRegistry
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1,
    FROZEN_LIVE_SEMANTIC_HEADERS_V1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
    consume_turn_claim_v1,
    render_dynamic_turn_v1,
)

CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero\openrouter-claim-store-v1"
)
#: The context-limit input bound the JIT preflight established. Deliberately
#: loose: no tighter token bound has been established by evidence.
MAX_INPUT_TOKENS = 1_047_576
PICO = 10**12


def build_execution_policy_v1() -> OpenRouterFrozenExecutionPolicyV1:
    """The proven route, with the operator's already-declared ceilings."""
    return OpenRouterFrozenExecutionPolicyV1(
        model="openai/gpt-4.1-mini",
        provider_only=("azure/swedencentral",),
        provider_order=("azure/swedencentral",),
        output_limit_tokens=256,
        max_price_prompt_usd_per_million="0.50",
        max_price_completion_usd_per_million="2.00",
        max_price_request_usd="0",
        bounded_timeout_seconds=30,
    )


@dataclass
class SocratesLiveRun:
    question: str
    baseline_text: Optional[str] = None
    baseline_usage: Dict[str, Any] = field(default_factory=dict)
    final: Any = None
    turn_rows: List[Dict[str, Any]] = field(default_factory=list)
    totals: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def _usd(picodollars: int) -> str:
    return f"${picodollars / PICO:.6f}"


def run_baseline_call(
    question: str,
    policy: OpenRouterFrozenExecutionPolicyV1,
    ledger: OpenRouterSessionLedgerV1,
    session: OpenRouterLiveTestSessionAuthorizationV1,
) -> Dict[str, Any]:
    """Arm B's control: one plain call, same route, same bounds.

    Deliberately not a council seat — a single model answering the question
    directly, so the comparison isolates the dialogue rather than the provider.
    """
    from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
        OpenRouterDynamicTurnRequestV1,
        mint_turn_claim_id_v1,
    )
    from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
        dispatch_openrouter_one_live_inference_v1,
    )

    turn = OpenRouterDynamicTurnRequestV1(
        system_prompt=(
            "Answer the user's question directly and carefully. Return a JSON "
            'object of the form {"answer": "...", "confidence": 0.0}.'
        ),
        user_content=question,
        role_seat="baseline",
        dialogue_id="baseline",
        turn_id="baseline-1",
        dialogue_phase="baseline",
    )
    rendered = render_dynamic_turn_v1(
        policy, FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1, turn
    )
    worst_case = conservative_turn_cost_bound_v1(policy, MAX_INPUT_TOKENS)
    ledger.check_admits(worst_case)
    consume_turn_claim_v1(CLAIM_STORE, mint_turn_claim_id_v1(session, rendered))
    ledger.record_dispatch(worst_case)

    started = time.perf_counter()
    result = dispatch_openrouter_one_live_inference_v1(
        body_bytes=rendered.canonical_body_json.encode("utf-8"),
        semantic_headers=dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1),
        bounded_timeout_seconds=policy.bounded_timeout_seconds,
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    out: Dict[str, Any] = {
        "http_status": result.completion.http_status,
        "latency_ms": latency_ms,
        "request_id": rendered.request_id,
    }
    if not result.completion.completed:
        out["failure"] = result.completion.failure_class
        return out
    payload = json.loads(result.raw_response_body.decode("utf-8"))
    usage = payload.get("usage") or {}
    if isinstance(usage.get("cost"), (int, float)):
        observed = int(round(float(usage["cost"]) * PICO))
        ledger.settle_observed(observed, worst_case)
        out["observed_cost_picodollars"] = observed
    out["prompt_tokens"] = usage.get("prompt_tokens")
    out["completion_tokens"] = usage.get("completion_tokens")
    choices = payload.get("choices") or []
    if choices:
        out["text"] = (choices[0].get("message") or {}).get("content")
    out["actual_model"] = payload.get("model")
    out["provider"] = payload.get("provider")
    return out


def run_socrates(
    question: str,
    *,
    max_calls: int = 30,
    max_total_usd: str = "2.00",
    max_per_call_usd: str = "0.60",
    seats: int = 2,
    include_baseline: bool = True,
    session_id: Optional[str] = None,
) -> SocratesLiveRun:
    """Run one complete Socrates dialogue live, within a bounded session."""
    from decimal import Decimal

    policy = build_execution_policy_v1()
    profile = FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1
    session_id = session_id or f"socrates-live-{int(time.time())}"

    session = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Operator-authorized bounded Socrates live test session"
        ),
        policy_id=policy.policy_id or "",
        profile_id=profile.profile_id or "",
        model=policy.model,
        provider_selector=profile.provider_selector,
        maximum_calls=int(max_calls),
        maximum_total_spend_picodollars=int(Decimal(max_total_usd) * PICO),
        maximum_per_call_spend_picodollars=int(Decimal(max_per_call_usd) * PICO),
        session_id=session_id,
    )
    ledger = OpenRouterSessionLedgerV1(session)
    run = SocratesLiveRun(question=question)

    if include_baseline:
        run.baseline_usage = run_baseline_call(question, policy, ledger, session)
        run.baseline_text = run.baseline_usage.get("text")

    adapters = [
        SocratesLiveOpenRouterAdapter(
            provider_id=f"live_seat_{index}",
            policy=policy,
            profile=profile,
            ledger=ledger,
            claim_directory=CLAIM_STORE,
            max_input_tokens=MAX_INPUT_TOKENS,
        )
        for index in range(seats)
    ]
    registry = CouncilProviderRegistry()
    for adapter in adapters:
        registry.register(adapter)

    from backend.dialogues.provider_registry import FakeProvider

    fallback = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", fallback) for i in range(4)]
    ced = CEDOrchestrator(agents, fallback, registry=registry)

    try:
        run.final = asyncio.run(
            ced.run_registry_session(question, session_id=session_id)
        )
    except Exception as exc:  # noqa: BLE001 - a bounded run failure is a result
        run.error = f"{type(exc).__name__}: {exc}"

    for adapter in adapters:
        run.turn_rows.extend(adapter.observability_rows())
    run.totals = {
        "calls_consumed": ledger.calls_consumed,
        "call_limit": session.maximum_calls,
        "settled_picodollars": ledger.settled_picodollars,
        "settled_usd": _usd(ledger.settled_picodollars),
        "unsettled_reserved_picodollars": ledger.unsettled_reserved_picodollars,
        "total_ceiling_usd": _usd(session.maximum_total_spend_picodollars),
        "session_id": session_id,
        "policy_id": policy.policy_id,
        "profile_id": profile.profile_id,
        "session_authorization_id": session.authorization_id,
    }
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one live Socrates dialogue")
    parser.add_argument("question")
    parser.add_argument("--max-calls", type=int, default=30)
    parser.add_argument("--max-total-usd", default="2.00")
    parser.add_argument("--seats", type=int, default=2)
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    run = run_socrates(
        args.question,
        max_calls=args.max_calls,
        max_total_usd=args.max_total_usd,
        seats=args.seats,
        include_baseline=not args.no_baseline,
    )
    payload = {
        "question": run.question,
        "baseline": run.baseline_usage,
        "turns": run.turn_rows,
        "totals": run.totals,
        "error": run.error,
        "final": (
            run.final.model_dump(mode="json")
            if hasattr(run.final, "model_dump")
            else str(run.final)
        ),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

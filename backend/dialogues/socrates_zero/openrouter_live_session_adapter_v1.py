"""A CouncilProviderRegistry adapter that runs on the proven live transport.

CED stays the transition authority. This is a worker: it takes whatever task and
agent state CED hands it, renders a dynamic turn against the frozen execution
policy, spends one bounded claim, dispatches exactly once, and returns the
model's text. Everything CED already does with that text is unchanged.

Prompt composition deliberately reuses the repository's own builders rather than
inventing a second prompt dialect, so the harness measures Socrates as it is.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..models import AgentState, AgentTask, ProviderResponse, ProviderStatus
from ..provider_registry import BaseProviderAdapter, parse_and_validate_move
from ..reasoning_prompts import build_reasoning_system_prompt
from .contracts import ContractValidationError, canonical_json
from .openrouter_live_session_v1 import (
    FROZEN_LIVE_SEMANTIC_HEADERS_V1,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterSessionLedgerV1,
    OpenRouterTurnRecordV1,
    conservative_turn_cost_bound_v1,
    consume_turn_claim_v1,
    mint_turn_claim_id_v1,
    render_dynamic_turn_v1,
    validate_policy_against_profile_v1,
)


def build_turn_user_content_v1(task: AgentTask, agent_state: AgentState) -> str:
    """Only canonical public task/state fields reach the provider."""
    payload: Dict[str, Any] = {
        "task": task.model_dump(mode="json", exclude_none=True),
        "agent_state": agent_state.model_dump(mode="json", exclude_none=True),
        "response_contract": {
            "format": "json_object",
            "required": ["content", "confidence"],
            "content_must_be_object": True,
        },
    }
    return (
        "You are one bounded Socratic council provider. Return exactly one JSON "
        "object and no markdown. Do not invent protocol authority.\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


class SocratesLiveOpenRouterAdapter(BaseProviderAdapter):
    """One council seat, served by the proven one-shot live transport."""

    provider_name = "OpenRouter (live harness)"
    is_fake = False

    def __init__(
        self,
        *,
        provider_id: str,
        policy: OpenRouterFrozenExecutionPolicyV1,
        profile: OpenRouterEndpointCapabilityProfileV1,
        ledger: OpenRouterSessionLedgerV1,
        claim_directory: Path,
        max_input_tokens: int,
        enabled: bool = True,
        dispatch: Optional[Callable[..., Any]] = None,
    ) -> None:
        # The credential is never read here; the transport owns the one read
        # site and only presence is ever observable from outside it.
        super().__init__(api_key=None, enabled=enabled)
        validate_policy_against_profile_v1(policy, profile)
        self.provider_id = str(provider_id).strip()
        if not self.provider_id:
            raise ValueError("provider_id is required")
        self.policy = policy
        self.profile = profile
        self.ledger = ledger
        self.claim_directory = Path(claim_directory)
        self.max_input_tokens = int(max_input_tokens)
        self.model = policy.model
        self.model_id = policy.model
        self._dispatch = dispatch
        self.turn_records: List[OpenRouterTurnRecordV1] = []
        self.last_raw_response: Optional[bytes] = None

    def is_available(self) -> bool:
        from .openrouter_one_live_shadow_v1 import (
            openrouter_credential_is_present_v1,
        )

        if self._dispatch is not None:
            return self.enabled
        return self.enabled and openrouter_credential_is_present_v1()

    def authoritative_model_id(self) -> Optional[str]:
        return self.model_id

    def _dispatcher(self) -> Callable[..., Any]:
        if self._dispatch is not None:
            return self._dispatch
        from .openrouter_one_live_shadow_v1 import (
            dispatch_openrouter_one_live_inference_v1,
        )

        return dispatch_openrouter_one_live_inference_v1

    async def _produce_raw_text(
        self, task: AgentTask, agent_state: AgentState
    ) -> str:
        """Render, budget-check, claim, dispatch once, map, record.

        Order matters: the budget is checked and the claim burned *before* any
        socket opens, so a crash under-executes rather than double-spending.
        """
        turn = OpenRouterDynamicTurnRequestV1(
            system_prompt=build_reasoning_system_prompt(
                task.role, task.phase, task.task_kind, model=self.policy.model
            ),
            user_content=build_turn_user_content_v1(task, agent_state),
            role_seat=str(getattr(task.role, "value", task.role) or "unknown"),
            dialogue_id=str(task.session_id),
            turn_id=str(task.task_id),
            dialogue_phase=str(getattr(task.phase, "value", task.phase) or "unknown"),
        )
        rendered = render_dynamic_turn_v1(self.policy, self.profile, turn)
        worst_case = conservative_turn_cost_bound_v1(
            self.policy, self.max_input_tokens
        )

        # Fails before the network if either session bound would break.
        self.ledger.check_admits(worst_case)

        claim_id = mint_turn_claim_id_v1(self.ledger.authorization, rendered)
        consume_turn_claim_v1(self.claim_directory, claim_id)

        started = time.perf_counter()
        # The budget is charged only once a dispatch is actually attempted. A
        # refusal raised before the socket spent nothing and left nothing
        # uncertain; the burnt claim already prevents this turn being retried.
        result = self._dispatcher()(
            body_bytes=rendered.canonical_body_json.encode("utf-8"),
            semantic_headers=dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1),
            bounded_timeout_seconds=self.policy.bounded_timeout_seconds,
            process_dispatch_limit=self.ledger.authorization.maximum_calls,
        )
        self.ledger.record_dispatch(worst_case)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        completion = result.completion
        self.last_raw_response = result.raw_response_body

        record_fields: Dict[str, Any] = dict(
            dialogue_id=turn.dialogue_id,
            turn_id=turn.turn_id,
            role_seat=turn.role_seat,
            dialogue_phase=turn.dialogue_phase,
            model=self.policy.model,
            provider_selector=self.profile.provider_selector,
            request_id=rendered.request_id or "",
            body_sha256=rendered.body_sha256,
            http_status=completion.http_status,
            transport_completed=completion.completed,
            latency_ms=latency_ms,
            worst_case_picodollars=worst_case,
            failure_class=completion.failure_class,
        )

        if not completion.completed:
            self.turn_records.append(OpenRouterTurnRecordV1(**record_fields))
            raise RuntimeError(f"transport_failed:{completion.failure_class}")

        text, extra = self._interpret(result, worst_case)
        record_fields.update(extra)
        self.turn_records.append(OpenRouterTurnRecordV1(**record_fields))

        if completion.http_status != 200:
            raise RuntimeError(f"http_{completion.http_status}")
        if text is None:
            raise RuntimeError("no_assistant_content")
        return text

    def _interpret(
        self, result, reserved_picodollars: int
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """Map through S5, bind through S6, and read usage. Never invents."""
        from .openrouter_one_live_shadow_runner_v1 import (
            s5_observation_from_live_v1,
        )
        from .openrouter_raw_wire_mapping_v2 import map_openrouter_raw_wire_v2

        extra: Dict[str, Any] = {}
        try:
            observation = s5_observation_from_live_v1(result)
            mapping = map_openrouter_raw_wire_v2(observation)
        except ContractValidationError:
            extra["s5_envelope_kind"] = "REFUSED"
            return None, extra

        extra["s5_envelope_kind"] = getattr(
            mapping.envelope_kind, "value", str(mapping.envelope_kind)
        )
        extra["actual_served_model"] = mapping.actual_served_model

        payload: Dict[str, Any] = {}
        try:
            payload = json.loads(result.raw_response_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None, extra

        extra["provider_display_name"] = payload.get("provider")
        usage = payload.get("usage")
        if isinstance(usage, dict):
            extra["prompt_tokens"] = usage.get("prompt_tokens")
            extra["completion_tokens"] = usage.get("completion_tokens")
            cost = usage.get("cost")
            if isinstance(cost, (int, float)):
                observed = int(round(float(cost) * 10**12))
                extra["observed_cost_picodollars"] = observed
                self.ledger.settle_observed(observed, reserved_picodollars)

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None, extra
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            extra["assistant_text_excerpt"] = content[:600]
            return content, extra
        return None, extra

    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState
    ) -> ProviderResponse:
        start = time.perf_counter()
        if not self.is_available():
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.MISSING_KEY,
                error_message="live provider unavailable",
            )
        try:
            raw = await self._produce_raw_text(task, agent_state)
        except Exception as exc:  # noqa: BLE001 - a bounded provider failure
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.ERROR,
                error_message=str(exc)[:200],
                latency_ms=round((time.perf_counter() - start) * 1000, 3),
            )
        meta: Dict[str, Any] = {}
        move, status, err = parse_and_validate_move(raw, task, meta=meta)
        accepted = status is ProviderStatus.OK
        if self.turn_records:
            last = self.turn_records[-1]
            self.turn_records[-1] = last.model_copy(
                update={
                    "ced_move_accepted": accepted,
                    "ced_rejection_reason": None if accepted else (err or status.value),
                    "record_id": None,
                }
            )
        return ProviderResponse(
            provider_id=self.provider_id,
            agent_id=task.agent_id,
            status=status,
            raw_text=raw,
            parsed_move=move,
            error_message=err,
            latency_ms=round((time.perf_counter() - start) * 1000, 3),
            repair_attempted=meta.get("repair_attempted", False),
            repair_succeeded=meta.get("repair_succeeded", False),
        )

    def observability_rows(self) -> List[Dict[str, Any]]:
        """Per-turn rows for a live view. No credentials, no reasoning traces."""
        return [
            record.model_dump(mode="json", exclude_none=False)
            for record in self.turn_records
        ]

    def session_totals(self) -> Dict[str, Any]:
        return {
            "calls_consumed": self.ledger.calls_consumed,
            "call_limit": self.ledger.authorization.maximum_calls,
            "settled_picodollars": self.ledger.settled_picodollars,
            "unsettled_reserved_picodollars": (
                self.ledger.unsettled_reserved_picodollars
            ),
            "observed_picodollars": self.ledger.observed_picodollars,
            "total_ceiling_picodollars": (
                self.ledger.authorization.maximum_total_spend_picodollars
            ),
        }


__all__ = [
    "SocratesLiveOpenRouterAdapter",
    "build_turn_user_content_v1",
]

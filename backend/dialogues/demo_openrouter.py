"""Opt-in OpenRouter smoke for the canonical provider adapter.

Environment:
  OPENROUTER_API_KEY   required
  OPENROUTER_MODEL     required exact OpenRouter model id, e.g. openai/gpt-4.1-mini

Run:
  python -m backend.dialogues.demo_openrouter
"""

from __future__ import annotations

import asyncio
import os

from .models import AgentRole, AgentState, AgentTask, DialogPhase, TaskKind
from .openrouter_provider import OpenRouterProviderAdapter


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


async def _run() -> int:
    model_id = _require("OPENROUTER_MODEL")
    _require("OPENROUTER_API_KEY")

    adapter = OpenRouterProviderAdapter(
        provider_id="openrouter_smoke",
        model_id=model_id,
    )
    task = AgentTask(
        task_id="openrouter_smoke_task",
        session_id="openrouter_smoke_session",
        agent_id="openrouter_smoke_agent",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.INITIAL_RESPONSE,
        task_kind=TaskKind.INITIAL_RESPONSE,
        question="Is justified true belief sufficient for knowledge?",
        context={"smoke": True},
        output_schema={},
    )
    state = AgentState(
        agent_id=task.agent_id,
        primary_role=AgentRole.SYNTHESIZER,
        assigned_role=AgentRole.SYNTHESIZER,
    )
    response = await adapter.generate_agent_move(task, state)

    print(f"provider_id={response.provider_id}")
    print(f"status={response.status.value}")
    print(f"parsed_move={'yes' if response.parsed_move is not None else 'no'}")
    receipt = adapter.last_receipt or {}
    print(f"requested_model={receipt.get('requested_model', model_id)}")
    print(f"returned_model={receipt.get('returned_model', '')}")
    print(f"verified_exact_model={receipt.get('verified_exact_model', False)}")
    if response.error_message:
        print(f"error={response.error_message}")
    if response.parsed_move is not None:
        print(f"content={response.parsed_move.content}")
    return 0 if response.status.value == "ok" else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())

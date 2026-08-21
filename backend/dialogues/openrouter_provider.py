"""Strict OpenRouter adapter for the canonical CouncilProviderRegistry.

Live use is opt-in. API keys are supplied by the caller or environment; this
module never reads .env files, prints secrets, or silently falls back to another
model. The requested model is pinned exactly and a response whose reported
model differs is rejected fail-closed.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional

import aiohttp

from .models import AgentState, AgentTask, ProviderResponse, ProviderStatus
from .provider_registry import BaseProviderAdapter, parse_and_validate_move

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _task_prompt(task: AgentTask, agent_state: AgentState) -> str:
    """Render only canonical public task/state fields into the provider prompt."""
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
        "object and no markdown. Do not invent protocol authority.\n" +
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


class OpenRouterProviderAdapter(BaseProviderAdapter):
    """Exact-model OpenRouter adapter with fail-closed model verification."""

    provider_name = "OpenRouter"
    is_fake = False

    def __init__(
        self,
        *,
        provider_id: str,
        model_id: str,
        api_key: Optional[str] = None,
        enabled: bool = True,
        timeout_seconds: float = 60.0,
        app_url: Optional[str] = None,
        app_title: Optional[str] = "Socrates-AI",
    ) -> None:
        super().__init__(api_key=api_key or os.getenv("OPENROUTER_API_KEY"), enabled=enabled)
        model_id = str(model_id).strip()
        provider_id = str(provider_id).strip()
        if not provider_id:
            raise ValueError("provider_id is required")
        if not model_id:
            raise ValueError("model_id is required")
        self.provider_id = provider_id
        self.model_id = model_id
        self.timeout_seconds = float(timeout_seconds)
        self.app_url = app_url
        self.app_title = app_title
        self.last_receipt: Optional[Dict[str, Any]] = None

    async def _request(self, task: AgentTask, agent_state: AgentState) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_url:
            headers["HTTP-Referer"] = self.app_url
        if self.app_title:
            headers["X-Title"] = self.app_title

        body = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": _task_prompt(task, agent_state)}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=body) as response:
                text = await response.text()
                if response.status == 429:
                    raise RuntimeError("rate_limited")
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"http_{response.status}")
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("invalid_openrouter_json") from exc
                if not isinstance(data, dict):
                    raise RuntimeError("invalid_openrouter_payload")
                return data

    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState,
    ) -> ProviderResponse:
        start = time.perf_counter()
        self.last_receipt = None
        if not self.is_available():
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.MISSING_KEY,
                error_message="OpenRouter unavailable (missing/placeholder key or disabled)",
            )
        try:
            data = await self._request(task, agent_state)
        except asyncio.TimeoutError:
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.TIMEOUT, error_message="OpenRouter request timed out",
            )
        except aiohttp.ClientError:
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.ERROR, error_message="OpenRouter network error",
            )
        except RuntimeError as exc:
            code = str(exc)
            status = ProviderStatus.RATE_LIMITED if code == "rate_limited" else ProviderStatus.ERROR
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=status, error_message=f"OpenRouter request failed: {code}",
            )

        returned_model = str(data.get("model") or "")
        if returned_model != self.model_id:
            self.last_receipt = {
                "requested_model": self.model_id,
                "returned_model": returned_model,
                "response_id": data.get("id"),
                "provider_id": self.provider_id,
                "verified_exact_model": False,
            }
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.ERROR,
                error_message="OpenRouter returned a different model than requested",
            )

        choices = data.get("choices")
        try:
            raw_text = choices[0]["message"]["content"]
        except (TypeError, KeyError, IndexError):
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.INVALID_JSON,
                error_message="OpenRouter response contained no assistant content",
            )
        if not isinstance(raw_text, str):
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.INVALID_JSON,
                error_message="OpenRouter assistant content was not text",
            )

        meta: Dict[str, Any] = {}
        move, status, err = parse_and_validate_move(raw_text, task, meta=meta)
        self.last_receipt = {
            "requested_model": self.model_id,
            "returned_model": returned_model,
            "response_id": data.get("id"),
            "provider_id": self.provider_id,
            "verified_exact_model": True,
            "usage": data.get("usage"),
        }
        return ProviderResponse(
            provider_id=self.provider_id,
            agent_id=task.agent_id,
            status=status,
            raw_text=raw_text,
            parsed_move=move,
            error_message=err,
            latency_ms=round((time.perf_counter() - start) * 1000, 3),
            repair_attempted=meta.get("repair_attempted", False),
            repair_succeeded=meta.get("repair_succeeded", False),
        )

"""
Phase 8A — Provider adapter contract + registry + safe-fallback skeleton.

This layer prepares the Socrates Dialogues architecture for real Claude / OpenAI /
Gemini / Grok providers WITHOUT making any real network calls yet. It adds:

  - a provider-adapter contract (`LLMProviderAdapter`) returning a `ProviderResponse`
  - deterministic mock providers for tests (no external APIs)
  - structured-output validation (raw text → JSON → AgentMove)
  - a `CouncilProviderRegistry` with availability checks, placeholder-key
    filtering, and quorum / minimum-provider enforcement

The existing `LLMProvider` ABC (`complete(...)`) and `ProviderRegistry` in
providers.py are left untouched; this is a parallel, additive layer.

Constraints: no real API calls, no reading/modifying `.env`, no printing keys.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import ValidationError

from .models import (
    AgentMove,
    AgentState,
    AgentTask,
    CouncilRoundResult,
    ProviderResponse,
    ProviderStatus,
)


# ── Council configuration (Phase 8A defaults) ─────────────────────────────────

MINIMUM_PROVIDERS = 2
QUORUM_FOR_ASSEMBLY = 2
PROVIDER_TIMEOUT_SECONDS = 30.0
JSON_REPAIR_ATTEMPTS = 1
ALLOW_FAKE_PROVIDER_IN_DEV = True

COUNCIL_UNAVAILABLE_WARNING = (
    "Council mode unavailable: at least {n} configured providers are required."
)

# Values that count as "no real key" — keys are never read from .env here; this
# helper only classifies a key string that a caller may pass in.
_PLACEHOLDER_KEYS = {
    "", "your_key_here", "your-api-key", "changeme", "change_me",
    "test", "todo", "placeholder", "none", "null", "xxx", "...",
}


def is_placeholder_key(api_key: Optional[str]) -> bool:
    """True if a key is missing or an obvious placeholder (case-insensitive)."""
    if api_key is None:
        return True
    return api_key.strip().lower() in _PLACEHOLDER_KEYS


# ── Structured-output validation (raw text → AgentMove) ───────────────────────

def parse_and_validate_move(raw_text: Optional[str], task: AgentTask):
    """
    Validate a provider's raw output into an AgentMove.

    Returns (move | None, status, error_message):
      - OK            : valid JSON that validates into an AgentMove
      - INVALID_JSON  : raw text is not parseable JSON
      - SCHEMA_ERROR  : JSON parsed but fails AgentMove schema validation
    """
    if raw_text is None:
        return None, ProviderStatus.INVALID_JSON, "empty response"
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, ProviderStatus.INVALID_JSON, f"json parse failed: {exc}"
    if not isinstance(data, dict):
        return None, ProviderStatus.SCHEMA_ERROR, "top-level JSON is not an object"
    try:
        move = AgentMove(
            task_id=task.task_id,
            agent_id=task.agent_id,
            role=task.role,
            phase=task.phase,
            content=data["content"],
            confidence=data.get("confidence", 0.7),
        )
    except (ValidationError, KeyError, TypeError) as exc:
        return None, ProviderStatus.SCHEMA_ERROR, f"schema validation failed: {exc}"
    return move, ProviderStatus.OK, None


# ── Provider adapter contract ─────────────────────────────────────────────────

@runtime_checkable
class LLMProviderAdapter(Protocol):
    provider_id: str
    provider_name: str

    def is_available(self) -> bool: ...

    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState,
    ) -> ProviderResponse: ...


class BaseProviderAdapter:
    """
    Shared adapter behaviour. Real adapters (later) subclass this and implement
    `_produce_raw_text`; the mock adapters below override `generate_agent_move`
    directly to simulate specific failure modes deterministically.
    """
    provider_id: str = "base"
    provider_name: str = "Base Provider"
    is_fake: bool = False

    def __init__(self, api_key: Optional[str] = None, enabled: bool = True) -> None:
        self.api_key = api_key
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled and not is_placeholder_key(self.api_key)

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        raise NotImplementedError

    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState,
    ) -> ProviderResponse:
        start = time.perf_counter()
        if not self.is_available():
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.MISSING_KEY,
                error_message="provider unavailable (missing/placeholder key or disabled)",
            )
        raw = await self._produce_raw_text(task, agent_state)
        move, status, err = parse_and_validate_move(raw, task)
        return ProviderResponse(
            provider_id=self.provider_id, agent_id=task.agent_id,
            status=status, raw_text=raw, parsed_move=move, error_message=err,
            latency_ms=round((time.perf_counter() - start) * 1000, 3),
        )


# ── Deterministic mock providers (tests only — no external APIs) ──────────────

class AlwaysOKProvider(BaseProviderAdapter):
    provider_id = "mock_ok"
    provider_name = "Mock OK"
    is_fake = True

    def __init__(self, api_key: Optional[str] = "sk-fake-ok", enabled: bool = True) -> None:
        super().__init__(api_key, enabled)

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        return json.dumps({
            "content": {"text": f"[{self.provider_id}] move for role={task.role.value}"},
            "confidence": 0.7,
        })


class TimeoutProvider(BaseProviderAdapter):
    provider_id = "mock_timeout"
    provider_name = "Mock Timeout"
    is_fake = True

    def __init__(self, api_key: Optional[str] = "sk-fake-timeout", enabled: bool = True) -> None:
        super().__init__(api_key, enabled)

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        # Simulated timeout — deterministic, no real sleep, no fake move.
        return ProviderResponse(
            provider_id=self.provider_id, agent_id=task.agent_id,
            status=ProviderStatus.TIMEOUT, error_message="simulated timeout",
        )


class InvalidJSONProvider(BaseProviderAdapter):
    provider_id = "mock_invalid_json"
    provider_name = "Mock Invalid JSON"
    is_fake = True

    def __init__(self, api_key: Optional[str] = "sk-fake-badjson", enabled: bool = True) -> None:
        super().__init__(api_key, enabled)

    async def _produce_raw_text(self, task, agent_state) -> str:
        return "<<< this is not valid json >>>"


class SchemaErrorProvider(BaseProviderAdapter):
    provider_id = "mock_schema_error"
    provider_name = "Mock Schema Error"
    is_fake = True

    def __init__(self, api_key: Optional[str] = "sk-fake-schema", enabled: bool = True) -> None:
        super().__init__(api_key, enabled)

    async def _produce_raw_text(self, task, agent_state) -> str:
        # Parseable JSON, but `content` must be an object → schema validation fails.
        return json.dumps({"content": "should-be-a-dict", "confidence": 0.7})


class RateLimitedProvider(BaseProviderAdapter):
    provider_id = "mock_rate_limited"
    provider_name = "Mock Rate Limited"
    is_fake = True

    def __init__(self, api_key: Optional[str] = "sk-fake-rl", enabled: bool = True) -> None:
        super().__init__(api_key, enabled)

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        return ProviderResponse(
            provider_id=self.provider_id, agent_id=task.agent_id,
            status=ProviderStatus.RATE_LIMITED, error_message="simulated 429 rate limit",
        )


class MissingKeyProvider(BaseProviderAdapter):
    provider_id = "mock_missing_key"
    provider_name = "Mock Missing Key"
    is_fake = True

    def __init__(self, api_key: Optional[str] = "your_key_here", enabled: bool = True) -> None:
        super().__init__(api_key, enabled)   # placeholder key → unavailable


# ── Council provider registry ─────────────────────────────────────────────────

class CouncilProviderRegistry:
    """
    Availability-aware registry for provider adapters. Filters out
    missing/placeholder-key providers, enforces a minimum provider count and an
    assembly quorum, and records the last round's failures for the audit summary.

    This does not read or modify `.env`; callers pass adapters (already
    configured with whatever key they hold) into `register(...)`.
    """

    def __init__(
        self,
        minimum_providers: int = MINIMUM_PROVIDERS,
        quorum_for_assembly: int = QUORUM_FOR_ASSEMBLY,
        provider_timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS,
        allow_fake_provider_in_dev: bool = ALLOW_FAKE_PROVIDER_IN_DEV,
    ) -> None:
        self.minimum_providers = minimum_providers
        self.quorum_for_assembly = quorum_for_assembly
        self.provider_timeout_seconds = provider_timeout_seconds
        self.allow_fake_provider_in_dev = allow_fake_provider_in_dev
        self._adapters: List[LLMProviderAdapter] = []
        self._last_failed: List[str] = []

    # -- registration / availability --
    def register(self, adapter: LLMProviderAdapter) -> None:
        self._adapters.append(adapter)

    def all_adapters(self) -> List[LLMProviderAdapter]:
        return list(self._adapters)

    def available_adapters(self) -> List[LLMProviderAdapter]:
        out = []
        for a in self._adapters:
            if not a.is_available():
                continue
            if getattr(a, "is_fake", False) and not self.allow_fake_provider_in_dev:
                continue
            out.append(a)
        return out

    def unavailable_adapters(self) -> List[LLMProviderAdapter]:
        avail = {id(a) for a in self.available_adapters()}
        return [a for a in self._adapters if id(a) not in avail]

    def assess_readiness(self):
        """Return (ready: bool, warning: str | None) for council execution."""
        available = self.available_adapters()
        if len(available) < self.minimum_providers:
            return False, COUNCIL_UNAVAILABLE_WARNING.format(n=self.minimum_providers)
        return True, None

    # -- per-adapter execution (timeout / failure safe; never crashes) --
    async def run_adapter(
        self, adapter: LLMProviderAdapter, task: AgentTask, agent_state: AgentState,
        timeout_seconds: Optional[float] = None,
    ) -> ProviderResponse:
        timeout = self.provider_timeout_seconds if timeout_seconds is None else timeout_seconds
        try:
            return await asyncio.wait_for(
                adapter.generate_agent_move(task, agent_state), timeout=timeout
            )
        except asyncio.TimeoutError:
            return ProviderResponse(
                provider_id=adapter.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.TIMEOUT, error_message="adapter exceeded timeout",
            )
        except Exception as exc:  # provider failure must never crash the CED
            return ProviderResponse(
                provider_id=adapter.provider_id, agent_id=task.agent_id,
                status=ProviderStatus.ERROR, error_message=str(exc),
            )

    def finalize_round(
        self, responses: List[ProviderResponse], quorum: Optional[int] = None,
    ) -> CouncilRoundResult:
        """Apply quorum/fallback rules to a set of responses (records failures)."""
        q = self.quorum_for_assembly if quorum is None else quorum
        ok_ids = [r.provider_id for r in responses if r.ok]
        failed_ids = [r.provider_id for r in responses if not r.ok]
        self._last_failed = list(failed_ids)
        proceed = len(ok_ids) >= q
        warning = None if proceed else COUNCIL_UNAVAILABLE_WARNING.format(n=q)
        return CouncilRoundResult(
            responses=responses, ok_provider_ids=ok_ids,
            failed_provider_ids=failed_ids, proceed=proceed, warning=warning,
        )

    # -- one council round: every available provider answers ONE task --
    async def gather_council_round(
        self, task: AgentTask, agent_state: AgentState,
        timeout_seconds: Optional[float] = None,
    ) -> CouncilRoundResult:
        adapters = self.available_adapters()
        responses = (
            list(await asyncio.gather(
                *(self.run_adapter(a, task, agent_state, timeout_seconds) for a in adapters)
            )) if adapters else []
        )
        return self.finalize_round(responses)

    # -- audit metadata (developer/user visible; never inserted into AgentState) --
    def status_summary(self) -> Dict[str, Any]:
        return {
            "available_providers": [a.provider_id for a in self.available_adapters()],
            "unavailable_providers": [a.provider_id for a in self.unavailable_adapters()],
            "failed_providers": list(self._last_failed),
            "minimum_providers": self.minimum_providers,
            "quorum_for_assembly": self.quorum_for_assembly,
        }

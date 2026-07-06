"""
Phase 26A — NVIDIA NIM provider adapter.

Adds a live-shaped NVIDIA NIM / OpenAI-compatible chat-completions adapter to the
same registry path used by the Socrates CED council. This file is intentionally
additive: it does not modify CED scoring, ratification, assembly, or prompt
semantics. It only translates a CED `AgentTask` into a provider request, extracts
provider text, and reuses `parse_and_validate_move`.

Hard guarantees:
  - no network call at import/build time;
  - config is passed by caller/env only (no .env reads/writes here);
  - keys are never printed and are redacted from error messages;
  - provider failures yield ProviderResponse with no fabricated AgentMove;
  - output validation stays in the existing registry pipeline.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .models import AgentState, AgentTask, DialogPhase, ProviderResponse, ProviderStatus, TaskKind
from .offline_provider_adapter import RoutingMeta
from .provider_registry import JSON_REPAIR_ATTEMPTS, BaseProviderAdapter, parse_and_validate_move
from .reasoning_prompts import build_reasoning_system_prompt


DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"
DEFAULT_NVIDIA_MAX_TOKENS = 4096
DEFAULT_NVIDIA_TIMEOUT = 180.0
DEFAULT_NVIDIA_RETRIES = 1
DEFAULT_NVIDIA_RETRY_DELAY = 2.0


# ── secret-safe redaction ─────────────────────────────────────────────────────

def _redact(text: Optional[str], key: Optional[str] = None) -> str:
    if not text:
        return text or ""
    if key:
        text = text.replace(key, "***REDACTED***")
    # NVIDIA keys are usually nvapi-…; keep generic bearer/key patterns masked too.
    text = re.sub(r"nvapi-[A-Za-z0-9_\-]{6,}", "***REDACTED***", text)
    text = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "***REDACTED***", text)
    return text


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


# ── transport errors ─────────────────────────────────────────────────────────

class NvidiaNIMError(Exception):
    """Base class for provider-level failures."""


class NvidiaNIMTimeout(NvidiaNIMError):
    """Provider request timed out."""


class NvidiaNIMRateLimit(NvidiaNIMError):
    """Provider returned 429 / rate limit."""


class NvidiaNIMAuthError(NvidiaNIMError):
    """Provider rejected authentication/authorization."""


class NvidiaNIMTransportError(NvidiaNIMError):
    """Network, HTTP, or envelope failure."""


# ── request / envelope helpers ───────────────────────────────────────────────

@dataclass
class NvidiaNIMRequest:
    """
    OpenAI-compatible chat-completions request for NVIDIA NIM.

    `routing` is CED-side metadata for tests/audit only; it is never sent to the
    provider. `system` carries the Phase 10 reasoning prompt, while `messages`
    carries only the CED-scoped user payload (question/context/schema).
    """

    model: str
    max_tokens: int
    system: str
    messages: List[Dict[str, Any]]
    base_url: str = DEFAULT_NVIDIA_BASE_URL
    temperature: float = 0.0
    routing: RoutingMeta = field(default_factory=RoutingMeta)

    def to_chat_completions_payload(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": self.system}, *list(self.messages)],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def chat_completions_url(self) -> str:
        return _join_url(self.base_url, "/chat/completions")


def nvidia_chat_envelope(text: str, *, model: str = DEFAULT_NVIDIA_MODEL) -> Dict[str, Any]:
    """Test helper: OpenAI-compatible chat-completions envelope carrying text."""
    return {
        "id": "nim_offline_fixture",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@runtime_checkable
class NvidiaNIMTransport(Protocol):
    """Optional test seam. Live mode leaves this as None and uses urllib lazily."""

    async def send(self, request: NvidiaNIMRequest, task: AgentTask, agent_state: AgentState) -> Dict[str, Any]: ...


class CannedNvidiaNIMTransport:
    """Deterministic no-network transport for tests."""

    def __init__(self, *, envelope: Optional[Dict[str, Any]] = None,
                 failure: Optional[NvidiaNIMError] = None) -> None:
        self.envelope = envelope
        self.failure = failure
        self.calls = 0

    async def send(self, request, task, agent_state):  # noqa: ANN001 (Protocol impl)
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if self.envelope is None:
            raise NvidiaNIMTransportError("no canned NVIDIA NIM envelope configured")
        return self.envelope


# ── adapter ──────────────────────────────────────────────────────────────────

class LiveNvidiaNIMAdapter(BaseProviderAdapter):
    """
    Live-shaped NVIDIA NIM council member.

    It targets NVIDIA's OpenAI-compatible chat-completions surface by default,
    but can be pointed at any compatible NIM base URL. Construction is inert; the
    network seam is called only inside `generate_agent_move`.
    """

    is_fake = False
    is_offline = False
    is_live = True
    provider_name = "NVIDIA NIM Live"

    RETRYABLE = frozenset({ProviderStatus.RATE_LIMITED, ProviderStatus.TIMEOUT})

    def __init__(
        self,
        provider_id: str,
        api_key: str,
        *,
        model: str = DEFAULT_NVIDIA_MODEL,
        base_url: str = DEFAULT_NVIDIA_BASE_URL,
        max_tokens: int = DEFAULT_NVIDIA_MAX_TOKENS,
        timeout: float = DEFAULT_NVIDIA_TIMEOUT,
        retries: int = DEFAULT_NVIDIA_RETRIES,
        retry_delay_seconds: float = DEFAULT_NVIDIA_RETRY_DELAY,
        transport: Optional[NvidiaNIMTransport] = None,
        enabled: bool = True,
        json_repair_attempts: int = JSON_REPAIR_ATTEMPTS,
    ) -> None:
        super().__init__(api_key=api_key, enabled=enabled)
        self.provider_id = provider_id
        self.provider_name = f"NVIDIA NIM Live ({model})"
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = int(max_tokens)
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.transport = transport
        self.json_repair_attempts = json_repair_attempts
        self.last_request: Optional[NvidiaNIMRequest] = None
        self.last_envelope: Optional[Dict[str, Any]] = None

    def _build_request(self, task: AgentTask, agent_state: AgentState) -> NvidiaNIMRequest:
        role_label = task.role.value if task.role else "council_member"
        system = build_reasoning_system_prompt(task.role, task.phase, task.task_kind, model=self.model)
        user_payload = {
            "question": task.question,
            "context": task.context,
            "output_schema": task.output_schema,
            "task_kind": task.task_kind.value if task.task_kind else None,
        }
        routing = RoutingMeta(
            session_id=task.session_id,
            task_id=task.task_id,
            task_kind=task.task_kind,
            agent_id=task.agent_id,
            role=role_label,
            phase=task.phase.value if isinstance(task.phase, DialogPhase) else str(task.phase),
        )
        return NvidiaNIMRequest(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": json.dumps(user_payload, sort_keys=True)}],
            base_url=self.base_url,
            routing=routing,
        )

    def _extract_text(self, envelope: Dict[str, Any]) -> str:
        if not isinstance(envelope, dict):
            raise NvidiaNIMTransportError("provider envelope is not an object")
        choices = envelope.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]
                # Some compatible servers use `text` rather than message.content.
                if isinstance(first.get("text"), str):
                    return first["text"]
        # Compatibility fallback for SDKs/proxies that return a flattened field.
        if isinstance(envelope.get("output_text"), str):
            return envelope["output_text"]
        raise NvidiaNIMTransportError("provider envelope has no assistant text")

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        response = await self._generate_once(task, agent_state)
        attempt = 0
        while response.status in self.RETRYABLE and attempt < self.retries:
            attempt += 1
            if self.retry_delay_seconds:
                await asyncio.sleep(self.retry_delay_seconds)
            response = await self._generate_once(task, agent_state)
        response.retry_count = attempt
        return response

    async def _generate_once(self, task, agent_state) -> ProviderResponse:
        start = time.perf_counter()

        def _ms() -> float:
            return round((time.perf_counter() - start) * 1000, 3)

        def _fail(status: ProviderStatus, message: str) -> ProviderResponse:
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=status,
                error_message=_redact(message, self.api_key),
                latency_ms=_ms(),
            )

        if not self.is_available():
            return _fail(ProviderStatus.MISSING_KEY, "NVIDIA NIM adapter unavailable (missing/placeholder key)")

        request = self._build_request(task, agent_state)
        self.last_request = request

        try:
            envelope = await self.transport.send(request, task, agent_state) if self.transport else await self._post_live(request)
        except NvidiaNIMRateLimit as exc:
            return _fail(ProviderStatus.RATE_LIMITED, str(exc))
        except NvidiaNIMTimeout as exc:
            return _fail(ProviderStatus.TIMEOUT, str(exc))
        except NvidiaNIMAuthError as exc:
            return _fail(ProviderStatus.ERROR, str(exc))
        except NvidiaNIMTransportError as exc:
            return _fail(ProviderStatus.ERROR, str(exc))
        except Exception as exc:
            return _fail(ProviderStatus.ERROR, str(exc))

        self.last_envelope = envelope
        try:
            raw = self._extract_text(envelope)
        except NvidiaNIMTransportError as exc:
            return _fail(ProviderStatus.ERROR, str(exc))

        meta: Dict[str, Any] = {}
        move, status, err = parse_and_validate_move(
            raw, task, repair_attempts=self.json_repair_attempts, meta=meta,
        )
        return ProviderResponse(
            provider_id=self.provider_id,
            agent_id=task.agent_id,
            status=status,
            raw_text=raw,
            parsed_move=move,
            error_message=err,
            latency_ms=_ms(),
            repair_attempted=meta.get("repair_attempted", False),
            repair_succeeded=meta.get("repair_succeeded", False),
        )

    async def _post_live(self, request: NvidiaNIMRequest) -> Dict[str, Any]:
        """Run the blocking urllib call in a worker thread; called only on live execution."""

        def _sync_post() -> Dict[str, Any]:
            payload = json.dumps(request.to_chat_completions_payload()).encode("utf-8")
            req = urllib.request.Request(
                request.chat_completions_url(),
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - configured API URL
                    body = resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8")
                except Exception:
                    pass
                msg = f"HTTP {exc.code}: {body[:500]}"
                if exc.code in (401, 403):
                    raise NvidiaNIMAuthError("authentication/authorization failed") from exc
                if exc.code == 429:
                    raise NvidiaNIMRateLimit("rate limited (429)") from exc
                if exc.code in (408, 504):
                    raise NvidiaNIMTimeout(f"request timed out via HTTP {exc.code}") from exc
                raise NvidiaNIMTransportError(msg) from exc
            except socket.timeout as exc:
                raise NvidiaNIMTimeout(f"request timed out after {self.timeout:g}s") from exc
            except urllib.error.URLError as exc:
                raise NvidiaNIMTransportError(f"connection error: {exc.reason}") from exc
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                raise NvidiaNIMTransportError(f"provider returned non-JSON envelope: {exc}") from exc

        return await asyncio.to_thread(_sync_post)

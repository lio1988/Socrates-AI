"""
Phase 9A — offline-first real-provider adapter (NO real API calls yet).

This module proves that a *real* provider adapter — shaped exactly like a live
Anthropic / OpenAI / Gemini adapter would be — can plug into the existing
`CouncilProviderRegistry` path without changing the CED protocol. It does so
**entirely offline**: no network, no real API key, no `.env` read/write. The
provider's "response" comes from a fixture / canned-response transport.

Real-adapter shape (the part that will be shared verbatim with the future live
adapter):

    _build_request(task, agent_state) -> ProviderRequest        # request construction
    transport.send(request, ...)      -> provider envelope (dict)  # the ONE seam that
                                                                    # swaps for a live client
    _extract_text(envelope)           -> str                    # provider-native parsing

The extracted text then flows through the EXISTING
`provider_registry.parse_and_validate_move`, so JSON repair, schema validation,
the no-fabrication rule, and the universal ``{"content": ..., "confidence": ...}``
move envelope are all preserved unchanged. The adapter never interprets scores
or verdicts — it returns provider output; CED governs.

Going live later is a one-line swap: implement an `LiveTransport.send` that calls
``client.messages.create(**request.to_messages_kwargs())`` (Anthropic SDK,
`claude-opus-4-8`, adaptive thinking) and parses the returned `Message`. The
request this adapter already builds is shaped for exactly that call. Until then,
every transport here is offline and deterministic.

Constraints (enforced): no real API calls · no real API key · no `.env`
read/write · fixtures/canned responses only · never prints keys.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .models import (
    AgentState,
    AgentTask,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    TaskKind,
)
from .provider_registry import (
    JSON_REPAIR_ATTEMPTS,
    BaseProviderAdapter,
    ScriptedMockProvider,
    parse_and_validate_move,
)
from .reasoning_prompts import build_reasoning_system_prompt

# ── Offline configuration ─────────────────────────────────────────────────────

# The model a live adapter would target (claude-api skill: default to opus-4-8).
DEFAULT_OFFLINE_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 4096

# A clearly-fake, non-placeholder sentinel so the adapter reads as "available"
# WITHOUT ever touching .env or a real secret. Never printed.
OFFLINE_FIXTURE_KEY = "sk-ant-offline-fixture-not-a-real-key"


def supports_adaptive_thinking(model: str) -> bool:
    """
    Adaptive thinking is an Opus-4.x capability. Other models (Haiku/Sonnet) reject
    `thinking: {"type": "adaptive"}` with a 400, so we omit it for them.
    """
    return model.startswith("claude-opus-4")

# Retry/rate-limit scaffolding (Phase 9A, step 3): which statuses a future retry
# policy MAY retry. This is metadata only — NO backoff loop is implemented here.
RETRYABLE_STATUSES = frozenset(
    {ProviderStatus.RATE_LIMITED, ProviderStatus.TIMEOUT, ProviderStatus.ERROR}
)


def is_retryable_status(status: ProviderStatus) -> bool:
    """True if a future, deterministic retry policy could retry this status."""
    return status in RETRYABLE_STATUSES


# ── Offline transport errors (offline analogues of live SDK exceptions) ───────
#
# A live Anthropic adapter would catch anthropic.RateLimitError (429),
# anthropic.APITimeoutError, a refusal stop_reason, etc. The offline transports
# raise these analogues so the adapter's status-mapping layer is exercised.

class OfflineProviderError(Exception):
    """Base for all simulated offline transport failures."""


class OfflineTimeout(OfflineProviderError):
    """Simulated request timeout (live analogue: anthropic.APITimeoutError)."""


class OfflineRateLimit(OfflineProviderError):
    """Simulated 429 (live analogue: anthropic.RateLimitError)."""

    def __init__(self, message: str = "simulated 429 rate limit",
                 retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class OfflineRefusal(OfflineProviderError):
    """Simulated safety refusal — HTTP 200 with stop_reason='refusal'."""


class OfflineTransportError(OfflineProviderError):
    """Generic transport/parse failure (live analogue: APIStatusError / 5xx)."""


class FixtureMiss(OfflineTransportError):
    """No canned response was configured for this task kind."""


# ── Provider-native (Anthropic Messages API) envelope helpers ─────────────────

def anthropic_text_envelope(
    text: str, *, model: str = DEFAULT_OFFLINE_MODEL, stop_reason: str = "end_turn",
) -> Dict[str, Any]:
    """
    Build a faithful Anthropic Messages-API response envelope whose single text
    block carries `text`. Mirrors the SDK `Message.to_dict()` shape so the live
    adapter's `_extract_text` will work on real responses unchanged.
    """
    return {
        "id": "msg_offline_fixture",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
    }


def anthropic_refusal_envelope(
    *, model: str = DEFAULT_OFFLINE_MODEL, category: str = "cyber",
) -> Dict[str, Any]:
    """A refusal envelope: HTTP-200 shape, empty content, stop_reason='refusal'."""
    return {
        "id": "msg_offline_refusal",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": "refusal",
        "stop_details": {"category": category, "explanation": None},
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


# ── Provider request (the adapter's internal representation of one API call) ───

@dataclass
class RoutingMeta:
    """
    CED-side routing/audit metadata that rides along with a request. A LIVE
    transport ignores this entirely (it only needs model/system/messages); the
    OFFLINE transports use `task_kind` to pick a canned response. Never sent to
    a real API and never contains scores or secrets.
    """
    session_id: str = ""
    task_id: str = ""
    task_kind: Optional[TaskKind] = None
    agent_id: str = ""
    role: str = ""
    phase: str = ""


@dataclass
class ProviderRequest:
    """
    Provider-native request the adapter builds from a CED task. `to_messages_kwargs`
    yields exactly the kwargs a live `client.messages.create(...)` call expects
    (Anthropic Messages API, adaptive thinking — no temperature/top_p/budget_tokens,
    matching claude-opus-4-8's surface).
    """
    model: str
    max_tokens: int
    system: str
    messages: List[Dict[str, Any]]
    # Adaptive thinking is an Opus-4.x capability; other models reject it (400).
    # None => the parameter is omitted from the live call entirely.
    thinking: Optional[Dict[str, Any]] = None
    routing: RoutingMeta = field(default_factory=RoutingMeta)

    def to_messages_kwargs(self) -> Dict[str, Any]:
        """The live-call payload (routing metadata is intentionally excluded;
        `thinking` is included only when set, so unsupported models aren't sent it)."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system,
            "messages": list(self.messages),
        }
        if self.thinking:
            kwargs["thinking"] = dict(self.thinking)
        return kwargs


# ── Offline transport contract ────────────────────────────────────────────────

@runtime_checkable
class OfflineTransport(Protocol):
    """
    The seam that swaps offline → live. `task`/`agent_state` are provided so
    offline transports can produce deterministic, task-shaped content; a live
    transport ignores them and calls the real client with `request` alone.
    """

    async def send(
        self, request: ProviderRequest, task: AgentTask, agent_state: AgentState,
    ) -> Dict[str, Any]: ...


class CannedResponseTransport:
    """
    Returns hand-authored Anthropic envelopes keyed by task kind — the literal
    "fixtures/canned responses only" path used by the focused adapter tests.

    `failures[kind]` (an OfflineProviderError) is raised instead of returning an
    envelope, to exercise honest failure mapping (timeout / rate-limit / refusal).
    """

    def __init__(
        self,
        *,
        by_task_kind: Optional[Dict[Optional[TaskKind], Dict[str, Any]]] = None,
        default: Optional[Dict[str, Any]] = None,
        failures: Optional[Dict[Optional[TaskKind], OfflineProviderError]] = None,
    ) -> None:
        self.by_task_kind = by_task_kind or {}
        self.default = default
        self.failures = failures or {}

    async def send(self, request, task, agent_state):  # noqa: ANN001 (Protocol impl)
        kind = request.routing.task_kind
        if kind in self.failures:
            raise self.failures[kind]
        envelope = self.by_task_kind.get(kind, self.default)
        if envelope is None:
            raise FixtureMiss(f"no canned response for task_kind={kind}")
        return envelope


class ScriptedOfflineTransport:
    """
    Generates a deterministic Anthropic envelope for ANY task kind by reusing the
    in-process `ScriptedMockProvider` content engine (FakeProvider — no network),
    then wrapping its `{"content": ..., "confidence": ...}` text in the envelope.

    This gives the offline real adapter full-session coverage (deliberation,
    move/section scoring, council ratification) while still exercising the real
    request-build → envelope → extract pipeline.
    """

    def __init__(
        self, provider_id: Optional[str] = None, *,
        model: str = DEFAULT_OFFLINE_MODEL, delay_seconds: float = 0.0,
    ) -> None:
        self.model = model
        self._scripted = ScriptedMockProvider(
            provider_id or "offline_scripted", delay_seconds=delay_seconds,
        )

    async def send(self, request, task, agent_state):  # noqa: ANN001 (Protocol impl)
        inner_text = await self._scripted._produce_raw_text(task, agent_state)
        return anthropic_text_envelope(inner_text, model=self.model)


# ── The offline-first real-provider adapter ───────────────────────────────────

class OfflineProviderAdapter(BaseProviderAdapter):
    """
    A real-shaped provider adapter executed in offline mode. Builds a faithful
    Messages-API request, sends it through a pluggable (offline) transport, parses
    the provider-native envelope, and validates the result through the existing
    registry pipeline.

    Marked `is_fake=True` ONLY so the dev registry (`allow_fake_provider_in_dev`)
    treats it as usable without a real key; `is_offline`/`is_real_shaped` record
    its true nature. It never reads `.env` and never makes a network call.
    """

    is_fake = True          # dev-gating only — offline mode has no real key
    is_offline = True
    is_real_shaped = True

    def __init__(
        self,
        provider_id: str,
        transport: OfflineTransport,
        *,
        provider_name: Optional[str] = None,
        model: str = DEFAULT_OFFLINE_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        api_key: Optional[str] = OFFLINE_FIXTURE_KEY,
        enabled: bool = True,
        json_repair_attempts: int = JSON_REPAIR_ATTEMPTS,
    ) -> None:
        super().__init__(api_key=api_key, enabled=enabled)
        self.provider_id = provider_id
        self.provider_name = provider_name or f"Offline Adapter ({provider_id})"
        self.transport = transport
        self.model = model
        self.max_tokens = max_tokens
        self.json_repair_attempts = json_repair_attempts
        # Captured for test assertions / audit (no secrets).
        self.last_request: Optional[ProviderRequest] = None
        self.last_envelope: Optional[Dict[str, Any]] = None

    # -- request construction (shared verbatim with the future live adapter) --
    def _build_request(self, task: AgentTask, agent_state: AgentState) -> ProviderRequest:
        """
        Translate a CED task into a Messages-API request. Minimal awareness: the
        request is derived ONLY from the task (whose context CED already scoped),
        never from agent internals or any scoreboard.
        """
        role_label = task.role.value if task.role else "council_member"
        # Full-reasoning system prompt (council identity + WHO THIS MODEL IS +
        # reasoning protocol + role + phase + whole-dialogue review for
        # deliberation / evaluation discipline for judging) at full power.
        system = build_reasoning_system_prompt(task.role, task.phase, task.task_kind,
                                               model=self.model)
        # The user turn carries only what the task provides (question + scoped context
        # + output schema). This is the same content a live model would receive.
        user_payload = {
            "question": task.question,
            "context": task.context,
            "output_schema": task.output_schema,
            "task_kind": task.task_kind.value if task.task_kind else None,
        }
        messages = [{"role": "user", "content": json.dumps(user_payload, sort_keys=True)}]
        routing = RoutingMeta(
            session_id=task.session_id,
            task_id=task.task_id,
            task_kind=task.task_kind,
            agent_id=task.agent_id,
            role=role_label,
            phase=task.phase.value if isinstance(task.phase, DialogPhase) else str(task.phase),
        )
        thinking = {"type": "adaptive"} if supports_adaptive_thinking(self.model) else None
        return ProviderRequest(
            model=self.model, max_tokens=self.max_tokens,
            system=system, messages=messages, thinking=thinking, routing=routing,
        )

    # -- provider-native envelope parsing (shared with the future live adapter) --
    def _extract_text(self, envelope: Dict[str, Any]) -> str:
        """Pull the first text block out of an Anthropic Messages envelope."""
        if not isinstance(envelope, dict):
            raise OfflineTransportError("provider envelope is not an object")
        if envelope.get("stop_reason") == "refusal":
            category = (envelope.get("stop_details") or {}).get("category")
            raise OfflineRefusal(f"safety refusal (category={category})")
        content = envelope.get("content")
        if not isinstance(content, list):
            raise OfflineTransportError("provider envelope has no content list")
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text
        raise OfflineTransportError("provider envelope has no text block")

    # -- one task → one ProviderResponse (honest status, never a fabricated move) --
    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState,
    ) -> ProviderResponse:
        start = time.perf_counter()

        def _elapsed_ms() -> float:
            return round((time.perf_counter() - start) * 1000, 3)

        def _fail(status: ProviderStatus, message: str, retry_count: int = 0) -> ProviderResponse:
            return ProviderResponse(
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=status, error_message=message,
                latency_ms=_elapsed_ms(), retry_count=retry_count,
            )

        if not self.is_available():
            return _fail(ProviderStatus.MISSING_KEY,
                         "offline adapter unavailable (disabled or placeholder key)")

        request = self._build_request(task, agent_state)
        self.last_request = request

        # Transport-level failures map to honest statuses (no fabricated move).
        try:
            envelope = await self.transport.send(request, task, agent_state)
        except OfflineRateLimit as exc:
            suffix = f" (retry_after={exc.retry_after}s)" if exc.retry_after is not None else ""
            return _fail(ProviderStatus.RATE_LIMITED, f"{exc}{suffix}")
        except OfflineTimeout as exc:
            return _fail(ProviderStatus.TIMEOUT, str(exc))
        except OfflineRefusal as exc:
            return _fail(ProviderStatus.ERROR, f"provider refusal: {exc}")
        except OfflineTransportError as exc:   # incl. FixtureMiss
            return _fail(ProviderStatus.ERROR, str(exc))

        self.last_envelope = envelope

        # Envelope parsing (refusal / malformed) → honest ERROR.
        try:
            raw = self._extract_text(envelope)
        except OfflineRefusal as exc:
            return _fail(ProviderStatus.ERROR, f"provider refusal: {exc}")
        except OfflineTransportError as exc:
            return _fail(ProviderStatus.ERROR, str(exc))

        # Reuse the EXISTING validation: JSON repair + schema → OK/INVALID_JSON/SCHEMA_ERROR.
        meta: Dict[str, Any] = {}
        move, status, err = parse_and_validate_move(
            raw, task, repair_attempts=self.json_repair_attempts, meta=meta,
        )
        return ProviderResponse(
            provider_id=self.provider_id, agent_id=task.agent_id,
            status=status, raw_text=raw, parsed_move=move, error_message=err,
            latency_ms=_elapsed_ms(),
            repair_attempted=meta.get("repair_attempted", False),
            repair_succeeded=meta.get("repair_succeeded", False),
        )


# ── Convenience builders (tests / demo) ───────────────────────────────────────

def offline_scripted_adapter(
    provider_id: str, *, model: str = DEFAULT_OFFLINE_MODEL, delay_seconds: float = 0.0,
) -> OfflineProviderAdapter:
    """An offline real adapter that can drive a FULL registry session deterministically."""
    transport = ScriptedOfflineTransport(provider_id, model=model, delay_seconds=delay_seconds)
    return OfflineProviderAdapter(provider_id, transport, model=model)


def offline_canned_adapter(
    provider_id: str, *,
    by_task_kind: Optional[Dict[Optional[TaskKind], Dict[str, Any]]] = None,
    default: Optional[Dict[str, Any]] = None,
    failures: Optional[Dict[Optional[TaskKind], OfflineProviderError]] = None,
    model: str = DEFAULT_OFFLINE_MODEL,
) -> OfflineProviderAdapter:
    """An offline real adapter backed by literal canned Anthropic envelopes."""
    transport = CannedResponseTransport(
        by_task_kind=by_task_kind, default=default, failures=failures,
    )
    return OfflineProviderAdapter(provider_id, transport, model=model)

"""
Phase 11 — Real-agent (live council) readiness.

This is the single switch that lets the WHOLE council (deliberation + ratification
+ peer scoring) run on real LLM agents — or stay fully offline/mock. It is the same
production-shaped path either way:

    ced, mode = build_council(env)          # mode == "live" or "mock"
    final = asyncio.run(ced.run_registry_session(question, session_id=...))

Real agents are engaged ONLY when doubly gated, exactly like the Phase 9B smoke:
  1. CED_ENABLE_LIVE_PROVIDERS == "1", and
  2. ANTHROPIC_API_KEY is a real (non-placeholder) key.
Otherwise `build_council` returns a deterministic **mock** council — the default.

Hard guarantees:
  - **No network call at build time.** Live adapters are constructed but never
    invoked here; the `anthropic` SDK is imported lazily, only on a real call.
  - Config comes from environment variables ONLY — never reads/writes `.env`,
    never hardcodes or prints a key.
  - All invariants are preserved: the live agents receive the full reasoning
    prompt (Phase 10), minimal awareness, peer scoring (judge-not-author), and the
    no-fabrication / quorum rules — the orchestration is unchanged.

This module is the council-grade home for live providers (multi-seat council).
`scripts/live_smoke_provider.py` is the separate, self-contained single-provider
smoke CLI (one provider, one task) and intentionally stands alone.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, List, Optional, Tuple

from .models import (
    AgentState, AgentTask, ProviderResponse, ProviderStatus,
)
from .provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, is_placeholder_key,
    parse_and_validate_move,
)
from .offline_provider_adapter import (
    DEFAULT_OFFLINE_MODEL, OfflineProviderAdapter, OfflineRefusal,
    OfflineTransportError,
)

# ── configuration (environment variables ONLY) ───────────────────────────────

FLAG_ENV = "CED_ENABLE_LIVE_PROVIDERS"     # must be "1" to engage real agents
KEY_ENV = "ANTHROPIC_API_KEY"              # provider key, loaded locally, never printed
MODELS_ENV = "CED_LIVE_MODELS"             # optional comma-separated per-seat models
MAXTOK_ENV = "CED_LIVE_MAX_TOKENS"         # optional
TIMEOUT_ENV = "CED_LIVE_TIMEOUT"           # optional per-provider call timeout (seconds)
RETRIES_ENV = "CED_LIVE_RETRIES"           # optional transient-failure retries per call

DEFAULT_LIVE_MODEL = DEFAULT_OFFLINE_MODEL  # "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 8192   # generous: rich (esp. Greek) reasoning JSON must not truncate
DEFAULT_REGISTRY_TIMEOUT = 180.0   # long: real reasoning responses can take a while
DEFAULT_RETRIES = 1                # ONE deterministic retry on rate-limit/timeout only
DEFAULT_RETRY_DELAY = 2.0          # fixed delay (no randomness/backoff)
DEFAULT_COUNCIL_SIZE = 4


# ── secret-safe redaction (shared with the smoke script) ──────────────────────

def _redact(text: Optional[str], key: Optional[str] = None) -> str:
    """Mask anything that could be a key (exact key value + sk-… patterns)."""
    if not text:
        return text or ""
    if key:
        text = text.replace(key, "***REDACTED***")
    return re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "***REDACTED***", text)


# ── gating (pure, env-driven; never reads .env, never calls) ─────────────────

def live_enabled(env) -> bool:
    return env.get(FLAG_ENV, "") == "1"


def resolve_key(env) -> Optional[str]:
    key = env.get(KEY_ENV, "")
    return None if is_placeholder_key(key) else key


def resolve_models(env, council_size: int) -> List[str]:
    raw = env.get(MODELS_ENV, "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return [DEFAULT_LIVE_MODEL] * council_size


def resolve_max_tokens(env) -> int:
    try:
        return int(env.get(MAXTOK_ENV) or DEFAULT_MAX_TOKENS)
    except (TypeError, ValueError):
        return DEFAULT_MAX_TOKENS


def resolve_timeout(env) -> float:
    try:
        return float(env.get(TIMEOUT_ENV) or DEFAULT_REGISTRY_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_REGISTRY_TIMEOUT


def resolve_retries(env) -> int:
    try:
        return max(0, int(env.get(RETRIES_ENV) if env.get(RETRIES_ENV) is not None
                          else DEFAULT_RETRIES))
    except (TypeError, ValueError):
        return DEFAULT_RETRIES


# ── the live Anthropic adapter (real agent behind the _produce_raw_text seam) ─

class _GuardTransport:
    """The live adapter calls the SDK directly in `_produce_raw_text`; the offline
    transport must never be used here."""

    async def send(self, request, task, agent_state):
        raise RuntimeError("live adapter must not use the offline transport")


class LiveAnthropicAdapter(OfflineProviderAdapter):
    """
    A real Anthropic council member. Reuses Phase 9A's request construction (now
    carrying the Phase 10 full-reasoning prompt) and envelope parsing, and
    implements the `_produce_raw_text` seam with one live
    `client.messages.create(...)`. The `anthropic` SDK is imported lazily inside
    `_produce_raw_text`, so importing this module makes no network call and needs
    no SDK installed.
    """

    is_fake = False
    is_offline = False
    is_live = True

    # Only transient failures are retried; deterministic failures (schema, auth,
    # invalid JSON, generic errors like "credit balance too low") are NOT — a
    # retry there wastes money without changing the outcome.
    RETRYABLE = frozenset({ProviderStatus.RATE_LIMITED, ProviderStatus.TIMEOUT})

    def __init__(self, provider_id: str, api_key: str, *,
                 model: str = DEFAULT_LIVE_MODEL,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 timeout: float = DEFAULT_REGISTRY_TIMEOUT,
                 retries: int = DEFAULT_RETRIES,
                 retry_delay_seconds: float = DEFAULT_RETRY_DELAY) -> None:
        super().__init__(
            provider_id, _GuardTransport(),
            provider_name=f"Anthropic Live ({model})",
            model=model, max_tokens=max_tokens, api_key=api_key,
        )
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        request = self._build_request(task, agent_state)
        self.last_request = request
        import anthropic  # lazy — ONLY here, ONLY on a real live call
        # Explicit SDK timeout aligned with the registry's per-call budget.
        async with anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout) as client:
            message = await client.messages.create(**request.to_messages_kwargs())
        envelope = message.to_dict()
        self.last_envelope = envelope
        return self._extract_text(envelope)

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        """One attempt + a bounded, deterministic retry on TRANSIENT failures only
        (rate limit / timeout). Fixed delay, no randomness; retry_count recorded."""
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
                provider_id=self.provider_id, agent_id=task.agent_id,
                status=status, error_message=message, latency_ms=_ms(),
            )

        if not self.is_available():
            return _fail(ProviderStatus.MISSING_KEY,
                         "live adapter unavailable (missing/placeholder key)")
        try:
            raw = await self._produce_raw_text(task, agent_state)
        except ImportError:
            return _fail(ProviderStatus.ERROR,
                         "anthropic SDK not installed (pip install anthropic)")
        except OfflineRefusal as exc:
            return _fail(ProviderStatus.ERROR, f"provider refusal: {exc}")
        except OfflineTransportError as exc:
            return _fail(ProviderStatus.ERROR, _redact(str(exc), self.api_key))
        except Exception as exc:  # map anthropic.* by name (no import in handler)
            name = type(exc).__name__
            if name == "RateLimitError":
                return _fail(ProviderStatus.RATE_LIMITED, "rate limited (429)")
            if name == "APITimeoutError":
                return _fail(ProviderStatus.TIMEOUT,
                             f"request timed out after {self.timeout:g}s — "
                             f"raise {TIMEOUT_ENV} or use a faster model")
            if name == "APIConnectionError":
                return _fail(ProviderStatus.ERROR,
                             "connection error reaching the API — check network / proxy / firewall")
            if name == "AuthenticationError":
                return _fail(ProviderStatus.ERROR, "authentication failed (check key)")
            return _fail(ProviderStatus.ERROR, _redact(str(exc), self.api_key))

        meta: dict = {}
        move, status, err = parse_and_validate_move(
            raw, task, repair_attempts=self.json_repair_attempts, meta=meta,
        )
        return ProviderResponse(
            provider_id=self.provider_id, agent_id=task.agent_id,
            status=status, raw_text=raw, parsed_move=move, error_message=err,
            latency_ms=_ms(),
            repair_attempted=meta.get("repair_attempted", False),
            repair_succeeded=meta.get("repair_succeeded", False),
        )


# ── the readiness switch: build a council registry / orchestrator ─────────────

def build_council_registry(
    env=None, *, council_size: int = DEFAULT_COUNCIL_SIZE,
) -> Tuple[CouncilProviderRegistry, str]:
    """
    Return (registry, mode). `mode == "live"` when doubly gated (flag + real key) —
    registers real `LiveAnthropicAdapter` seats (constructed, NOT called here);
    otherwise `mode == "mock"` and registers deterministic `ScriptedMockProvider`s
    (the offline default). Env-only; never reads `.env`; makes NO network call.
    """
    env = os.environ if env is None else env
    timeout = resolve_timeout(env)
    retries = resolve_retries(env)
    # The registry's per-task budget wraps the adapter's whole call INCLUDING its
    # internal retries, so it must cover every attempt (+ fixed delays + margin).
    budget = (retries + 1) * timeout + retries * DEFAULT_RETRY_DELAY + 5.0
    registry = CouncilProviderRegistry(provider_timeout_seconds=budget)

    key = resolve_key(env)
    if live_enabled(env) and key is not None:
        models = resolve_models(env, council_size)
        max_tokens = resolve_max_tokens(env)
        for i, model in enumerate(models):
            registry.register(LiveAnthropicAdapter(
                f"anthropic_seat{i}_{model}", key, model=model, max_tokens=max_tokens,
                timeout=timeout, retries=retries))
        return registry, "live"

    for i in range(council_size):
        registry.register(ScriptedMockProvider(f"mock_seat{i}"))
    return registry, "mock"


def build_council(
    env=None, *, council_size: int = DEFAULT_COUNCIL_SIZE, shadow_scoring_mode=None,
) -> Tuple[Any, str]:
    """
    A ready-to-run council orchestrator. Same code path real or mock — mock by
    default; live ONLY when gated + keyed. Returns (CEDOrchestrator, mode).

        ced, mode = build_council()                       # offline mock
        ced, mode = build_council(council_size=3)
        # with CED_ENABLE_LIVE_PROVIDERS=1 + ANTHROPIC_API_KEY set → mode == "live"
    """
    from .ced import CEDOrchestrator
    from .agent import SocraticAgent
    from .providers import FakeProvider

    registry, mode = build_council_registry(env, council_size=council_size)
    provider = FakeProvider()  # legacy self.agents slot — unused on the registry path
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(council_size)]
    kwargs = {} if shadow_scoring_mode is None else {"shadow_scoring_mode": shadow_scoring_mode}
    # Enable the assembly fallback so a live run still produces an answer even if
    # finicky real-model peer-scoring yields no valid section scores.
    ced = CEDOrchestrator(agents, provider, registry=registry, assembly_fallback=True, **kwargs)
    return ced, mode

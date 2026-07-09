"""
Phase 11 — Real-agent (live council) readiness.

This is the single switch that lets the WHOLE council (deliberation + ratification
+ peer scoring) run on real LLM agents — or stay fully offline/mock. It is the same
production-shaped path either way:

    ced, mode = build_council(env)          # mode == "live" or "mock"
    final = asyncio.run(ced.run_registry_session(question, session_id=...))

Real agents are engaged ONLY when gated, exactly like the Phase 9B smoke:
  1. CED_ENABLE_LIVE_PROVIDERS == "1", and
  2. the selected live provider family has a real (non-placeholder) key.
Otherwise `build_council` returns a deterministic **mock** council — the default.

Phase 26B adds an opt-in mixed-provider council surface:
  - old behavior is unchanged when CED_PROVIDER_FAMILIES is absent;
  - when present, seats can be `anthropic`, `nvidia`, or `mock`;
  - CED scoring/ratification/assembly semantics are untouched.

Hard guarantees:
  - **No network call at build time.** Live adapters are constructed but never
    invoked here; provider SDK/HTTP calls happen lazily, only on a real call.
  - Config comes from environment variables ONLY — never reads/writes `.env`,
    never hardcodes or prints a key.
  - All invariants are preserved: live agents receive the full reasoning prompt
    (Phase 10), minimal awareness, peer scoring (judge-not-author), and the
    no-fabrication / quorum rules — the orchestration is unchanged.

This module is the council-grade home for live providers (multi-seat council).
`scripts/live_smoke_provider.py` is the separate, self-contained single-provider
smoke CLI (one provider, one task) and intentionally stands alone.
"""

from __future__ import annotations

import asyncio
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
from .nvidia_nim_provider import (
    DEFAULT_NVIDIA_BASE_URL,
    DEFAULT_NVIDIA_MODEL,
    LiveNvidiaNIMAdapter,
)

# ── configuration (environment variables ONLY) ───────────────────────────────

FLAG_ENV = "CED_ENABLE_LIVE_PROVIDERS"     # must be "1" to engage real agents
KEY_ENV = "ANTHROPIC_API_KEY"              # provider key, loaded locally, never printed
MODELS_ENV = "CED_LIVE_MODELS"             # optional comma-separated Anthropic per-seat models
MAXTOK_ENV = "CED_LIVE_MAX_TOKENS"         # optional
TIMEOUT_ENV = "CED_LIVE_TIMEOUT"           # optional per-provider call timeout (seconds)
RETRIES_ENV = "CED_LIVE_RETRIES"           # optional transient-failure retries per call

# Phase 26B: optional mixed-provider surface. If PROVIDER_FAMILIES_ENV is absent,
# old Anthropic/mock behavior is preserved.
PROVIDER_FAMILIES_ENV = "CED_PROVIDER_FAMILIES"   # e.g. anthropic,nvidia,nvidia,mock
NVIDIA_KEY_ENV = "NVIDIA_API_KEY"
NVIDIA_MODELS_ENV = "CED_NVIDIA_MODELS"           # optional comma-separated NVIDIA per-seat models
NVIDIA_BASE_URL_ENV = "CED_NVIDIA_BASE_URL"       # optional NIM-compatible base URL

DEFAULT_LIVE_MODEL = DEFAULT_OFFLINE_MODEL  # "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 8192   # generous: rich (esp. Greek) reasoning JSON must not truncate
DEFAULT_REGISTRY_TIMEOUT = 180.0   # long: real reasoning responses can take a while
DEFAULT_RETRIES = 1                # ONE deterministic retry on rate-limit/timeout only
DEFAULT_RETRY_DELAY = 2.0          # fixed delay (no randomness/backoff)
DEFAULT_COUNCIL_SIZE = 4


# ── secret-safe redaction (shared with the smoke script) ──────────────────────

def _redact(text: Optional[str], key: Optional[str] = None) -> str:
    """Mask anything that could be a key (exact key value + sk-/nvapi- patterns)."""
    if not text:
        return text or ""
    if key:
        text = text.replace(key, "***REDACTED***")
    text = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "***REDACTED***", text)
    text = re.sub(r"nvapi-[A-Za-z0-9_\-]{6,}", "***REDACTED***", text)
    return text


def _safe_id_fragment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "model"


# ── gating (pure, env-driven; never reads .env, never calls) ─────────────────

def live_enabled(env) -> bool:
    return env.get(FLAG_ENV, "") == "1"


def resolve_key(env) -> Optional[str]:
    key = env.get(KEY_ENV, "")
    return None if is_placeholder_key(key) else key


def resolve_nvidia_key(env) -> Optional[str]:
    key = env.get(NVIDIA_KEY_ENV, "")
    return None if is_placeholder_key(key) else key


def _parse_csv(raw: str) -> List[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def resolve_provider_families(env, council_size: int) -> List[str]:
    """Empty list means: use the legacy Anthropic/mock behavior unchanged."""
    raw = env.get(PROVIDER_FAMILIES_ENV, "").strip()
    if not raw:
        return []
    values = [v.lower() for v in _parse_csv(raw)]
    return values or []


def resolve_models(env, council_size: int) -> List[str]:
    raw = env.get(MODELS_ENV, "").strip()
    if raw:
        return _parse_csv(raw)
    return [DEFAULT_LIVE_MODEL] * council_size


def resolve_nvidia_models(env, count: int) -> List[str]:
    raw = env.get(NVIDIA_MODELS_ENV, "").strip()
    if raw:
        return _parse_csv(raw)
    return [DEFAULT_NVIDIA_MODEL] * count


def resolve_nvidia_base_url(env) -> str:
    return (env.get(NVIDIA_BASE_URL_ENV, "") or DEFAULT_NVIDIA_BASE_URL).rstrip("/")


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


# ── registry builders ────────────────────────────────────────────────────────

def _mock_registry(council_size: int, budget: float) -> CouncilProviderRegistry:
    registry = CouncilProviderRegistry(provider_timeout_seconds=budget)
    for i in range(council_size):
        registry.register(ScriptedMockProvider(f"mock_seat{i}"))
    return registry


def _build_mixed_registry(env, families: List[str], *, timeout: float, retries: int,
                          budget: float, max_tokens: int) -> CouncilProviderRegistry:
    registry = CouncilProviderRegistry(provider_timeout_seconds=budget)
    anthropic_key = resolve_key(env)
    nvidia_key = resolve_nvidia_key(env)
    anthropic_models = resolve_models(env, families.count("anthropic") + families.count("claude"))
    nvidia_models = resolve_nvidia_models(env, families.count("nvidia") + families.count("nim"))
    nvidia_base_url = resolve_nvidia_base_url(env)
    a_i = 0
    n_i = 0

    for seat_i, family in enumerate(families):
        if family in ("mock", "fake", "scripted"):
            registry.register(ScriptedMockProvider(f"mock_seat{seat_i}"))
            continue
        if family in ("anthropic", "claude"):
            model = anthropic_models[a_i % max(1, len(anthropic_models))]
            a_i += 1
            registry.register(LiveAnthropicAdapter(
                f"anthropic_seat{seat_i}_{_safe_id_fragment(model)}",
                anthropic_key or "your_key_here", model=model, max_tokens=max_tokens,
                timeout=timeout, retries=retries,
            ))
            continue
        if family in ("nvidia", "nim"):
            model = nvidia_models[n_i % max(1, len(nvidia_models))]
            n_i += 1
            registry.register(LiveNvidiaNIMAdapter(
                f"nvidia_seat{seat_i}_{_safe_id_fragment(model)}",
                nvidia_key or "your_key_here", model=model, base_url=nvidia_base_url,
                max_tokens=max_tokens, timeout=timeout, retries=retries,
            ))
            continue
        raise ValueError(
            f"Unknown provider family {family!r}; supported: anthropic, nvidia, mock"
        )
    return registry


def build_council_registry(
    env=None, *, council_size: int = DEFAULT_COUNCIL_SIZE,
) -> Tuple[CouncilProviderRegistry, str]:
    """
    Return (registry, mode). Legacy behavior: `mode == "live"` only when the old
    Anthropic double gate is satisfied; otherwise deterministic mock. Mixed mode:
    when CED_PROVIDER_FAMILIES is set and the global live flag is enabled, seats
    are built from the requested provider families.
    """
    env = os.environ if env is None else env
    timeout = resolve_timeout(env)
    retries = resolve_retries(env)
    # The registry's per-task budget wraps the adapter's whole call INCLUDING its
    # internal retries, so it must cover every attempt (+ fixed delays + margin).
    budget = (retries + 1) * timeout + retries * DEFAULT_RETRY_DELAY + 5.0
    max_tokens = resolve_max_tokens(env)

    families = resolve_provider_families(env, council_size)
    if families:
        if live_enabled(env):
            return _build_mixed_registry(
                env, families, timeout=timeout, retries=retries,
                budget=budget, max_tokens=max_tokens,
            ), "mixed"
        return _mock_registry(len(families), budget), "mock"

    # Legacy Phase 11 behavior preserved when CED_PROVIDER_FAMILIES is absent.
    registry = CouncilProviderRegistry(provider_timeout_seconds=budget)
    key = resolve_key(env)
    if live_enabled(env) and key is not None:
        models = resolve_models(env, council_size)
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
    lesson_store=None, seat_health=None, ai_learning: bool = False, topic_skill=None,
    open_questions=None, calibration=None, ratification_repair: str = "runner_up",
    phase_retry: bool = True, training_corpus=None, score_weighting: str = "uniform",
    cohesion_margin: float = 0.0, openclaw_lessons=None, trace_capturer=None,
    tree_expansions: int = 0, tree_exploration: float = 0.5,
) -> Tuple[Any, str]:
    """
    A ready-to-run council orchestrator. Same code path real or mock — mock by
    default; live/mixed ONLY when gated + keyed. Returns (CEDOrchestrator, mode).

        ced, mode = build_council()                       # offline mock
        ced, mode = build_council(council_size=3)
        # with CED_ENABLE_LIVE_PROVIDERS=1 + ANTHROPIC_API_KEY set → mode == "live"
        # with CED_PROVIDER_FAMILIES=anthropic,nvidia,mock + flag → mode == "mixed"
    """
    from .ced import CEDOrchestrator
    from .agent import SocraticAgent
    from .providers import FakeProvider

    registry, mode = build_council_registry(env, council_size=council_size)
    provider = FakeProvider()  # legacy self.agents slot — unused on the registry path
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(len(registry.all_adapters()))]
    kwargs = {} if shadow_scoring_mode is None else {"shadow_scoring_mode": shadow_scoring_mode}
    # Enable the assembly fallback so a live run still produces an answer even if
    # finicky real-model peer-scoring yields no valid section scores.
    ced = CEDOrchestrator(agents, provider, registry=registry, assembly_fallback=True,
                          lesson_store=lesson_store, seat_health=seat_health,
                          ai_learning=ai_learning, topic_skill=topic_skill,
                          open_questions=open_questions, calibration=calibration,
                          ratification_repair=ratification_repair,
                          phase_retry=phase_retry, training_corpus=training_corpus,
                          score_weighting=score_weighting,
                          cohesion_margin=cohesion_margin,
                          openclaw_lessons=openclaw_lessons,
                          trace_capturer=trace_capturer,
                          tree_expansions=tree_expansions,
                          tree_exploration=tree_exploration, **kwargs)
    return ced, mode

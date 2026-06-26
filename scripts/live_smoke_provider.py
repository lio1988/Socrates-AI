"""
Phase 9B — one-provider LIVE smoke test (manual, opt-in, single provider).

This is the ONLY code path in the project that can make a real network call to a
provider. It is doubly gated and OFF by default:

    1. CED_ENABLE_LIVE_PROVIDERS must equal "1"   (else: do nothing, exit safely)
    2. ANTHROPIC_API_KEY must be a real (non-placeholder) key  (else: refuse, exit)

If either gate is not satisfied, NO network call is made and NO provider SDK is
even imported. The `anthropic` SDK is imported lazily, inside the live call only,
so the rest of the project stays import-clean and offline.

Hard rules (enforced here):
  - never hardcode an API key · never print an API key · never write a key to disk
  - load all configuration from environment variables only
  - default behaviour is offline / no-network
  - one provider, one task — NOT a full council

Run it manually (PowerShell):   $env:CED_ENABLE_LIVE_PROVIDERS=1; $env:ANTHROPIC_API_KEY="sk-..."; python scripts/live_smoke_provider.py
Or via the launchers:           run_live_smoke_provider.bat   /   run_live_smoke_provider.ps1
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import re
import sys
import time
import traceback
from collections import namedtuple
from typing import Optional

# Make `backend` importable when run as `python scripts/live_smoke_provider.py`.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.dialogues.models import (  # noqa: E402  (after sys.path setup)
    AgentRole, AgentState, AgentTask, DialogPhase, ProviderResponse,
    ProviderStatus, TaskKind,
)
from backend.dialogues.provider_registry import (  # noqa: E402
    is_placeholder_key, parse_and_validate_move,
)
from backend.dialogues.offline_provider_adapter import (  # noqa: E402
    DEFAULT_OFFLINE_MODEL, OfflineProviderAdapter, OfflineRefusal,
    OfflineTransportError,
)

# ── Configuration (environment variables ONLY) ───────────────────────────────

FLAG_ENV = "CED_ENABLE_LIVE_PROVIDERS"     # must be "1" to enable any live call
KEY_ENV = "ANTHROPIC_API_KEY"              # provider key, loaded locally, never printed
MODEL_ENV = "CED_LIVE_MODEL"               # optional override (default opus-4-8)
MAXTOK_ENV = "CED_LIVE_MAX_TOKENS"         # optional override
TIMEOUT_ENV = "CED_LIVE_TIMEOUT"           # optional per-request timeout (seconds)
DEBUG_ENV = "CED_LIVE_DEBUG"               # "1" -> print full key-redacted traceback

LIVE_PROVIDER_ID = "anthropic_live"
DEFAULT_LIVE_MODEL = DEFAULT_OFFLINE_MODEL  # "claude-opus-4-8"
DEFAULT_LIVE_MAX_TOKENS = 1024
DEFAULT_LIVE_TIMEOUT = 120.0               # generous, explicit, tunable (was: SDK default)

# Exit codes (every "didn't run" path is a SAFE exit, no network touched).
EXIT_OK = 0          # live smoke ran (status reported honestly)
EXIT_DISABLED = 0    # flag not set — default safe mode (intentional no-op)
EXIT_NO_KEY = 2      # flag set but key missing/placeholder — refused
EXIT_LIVE_ERROR = 3  # live call raised unexpectedly (message redacted)

SmokeResult = namedtuple("SmokeResult", "provider_id provider_name model response")


# ── Secret-safe helpers ───────────────────────────────────────────────────────

def _redact(text: Optional[str], key: Optional[str] = None) -> str:
    """Mask anything that could be a key (exact key value + sk-… patterns)."""
    if not text:
        return text or ""
    if key:
        text = text.replace(key, "***REDACTED***")
    return re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "***REDACTED***", text)


# ── Gate checks (pure, env-driven) ────────────────────────────────────────────

def live_enabled(env) -> bool:
    return env.get(FLAG_ENV, "") == "1"


def resolve_key(env) -> Optional[str]:
    """Return a usable key, or None if missing/placeholder (never raises/prints)."""
    key = env.get(KEY_ENV, "")
    return None if is_placeholder_key(key) else key


# ── The live Anthropic adapter (uses the _produce_raw_text seam) ──────────────

class _GuardTransport:
    """The live adapter calls the SDK directly in `_produce_raw_text`; the offline
    transport must never be used here."""

    async def send(self, request, task, agent_state):
        raise RuntimeError("live adapter must not use the offline transport")


class LiveAnthropicAdapter(OfflineProviderAdapter):
    """
    Real Anthropic adapter. Reuses Phase 9A's request-build + envelope-extract +
    validation, and implements the existing `_produce_raw_text` seam to make ONE
    live `client.messages.create(...)` call. The `anthropic` SDK is imported
    lazily inside `_produce_raw_text`, so importing this script makes no network
    call and needs no SDK installed.
    """

    is_fake = False
    is_offline = False
    is_live = True

    def __init__(self, provider_id: str, api_key: str, *,
                 model: str = DEFAULT_LIVE_MODEL,
                 max_tokens: int = DEFAULT_LIVE_MAX_TOKENS,
                 timeout: float = DEFAULT_LIVE_TIMEOUT) -> None:
        super().__init__(
            provider_id, _GuardTransport(),
            provider_name=f"Anthropic Live ({model})",
            model=model, max_tokens=max_tokens, api_key=api_key,
        )
        self.timeout = timeout

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        request = self._build_request(task, agent_state)
        self.last_request = request
        import anthropic  # lazy — ONLY here, ONLY on a real live call
        # Explicit, tunable timeout so a slow request fails predictably (and the
        # user can raise it) instead of relying on the SDK default.
        async with anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout) as client:
            message = await client.messages.create(**request.to_messages_kwargs())
        envelope = message.to_dict()
        self.last_envelope = envelope
        return self._extract_text(envelope)

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
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
                             f"raise {TIMEOUT_ENV} or use a faster {MODEL_ENV}")
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


# ── The single smoke task ─────────────────────────────────────────────────────

def build_smoke_task():
    task = AgentTask(
        session_id="live_smoke", agent_id="agent_0",
        role=AgentRole.SYNTHESIZER, phase=DialogPhase.INITIAL_RESPONSE,
        question=("Is water wet? Put your answer in `content` as a JSON OBJECT — for "
                  'example {"content": {"answer": "yes, water is wet"}, "confidence": 0.95}. '
                  "`content` must be an object, not a bare string."),
        task_kind=TaskKind.INITIAL_RESPONSE, output_schema={"_role": "synthesizer"},
    )
    state = AgentState(agent_id="agent_0", primary_role=AgentRole.SYNTHESIZER,
                       assigned_role=AgentRole.SYNTHESIZER)
    return task, state


def _run_live_smoke(key: str, *, model: str, max_tokens: int,
                    timeout: float = DEFAULT_LIVE_TIMEOUT) -> SmokeResult:
    """Build ONE live adapter, send ONE task, return the result. (The seam tests
    monkeypatch to assert it is never called when a gate fails.)"""
    adapter = LiveAnthropicAdapter(LIVE_PROVIDER_ID, key, model=model,
                                   max_tokens=max_tokens, timeout=timeout)
    task, state = build_smoke_task()
    response = asyncio.run(adapter.generate_agent_move(task, state))
    return SmokeResult(adapter.provider_id, adapter.provider_name, adapter.model, response)


def _debug_live_traceback(key: str, *, model: str, max_tokens: int, timeout: float) -> None:
    """
    Diagnostic ONLY (CED_LIVE_DEBUG=1): call the live seam directly so the raw
    exception's FULL traceback surfaces (the normal path catches it and reports a
    one-line status). The traceback is printed with the key redacted; it contains
    code frames + the underlying error, never the key.
    """
    adapter = LiveAnthropicAdapter(LIVE_PROVIDER_ID, key, model=model,
                                   max_tokens=max_tokens, timeout=timeout)
    task, state = build_smoke_task()
    try:
        asyncio.run(adapter._produce_raw_text(task, state))
        print("  DEBUG: live call returned with NO exception.")
    except BaseException:  # noqa: BLE001 — diagnostic: surface whatever was raised
        print("  DEBUG TRACEBACK (key redacted):")
        print(_redact(traceback.format_exc(), key))


# ── Safe summary (no secrets, ever) ───────────────────────────────────────────

def print_summary(result: SmokeResult) -> None:
    r = result.response
    print(f"  provider         : {result.provider_id} ({result.provider_name})")
    print(f"  model            : {result.model}")
    print(f"  provider_status  : {r.status.value}")
    print(f"  schema_valid     : {bool(r.ok)}")
    print(f"  response_length  : {len(r.raw_text or '')}")
    print(f"  repair_attempted : {r.repair_attempted} | repair_succeeded: {r.repair_succeeded}")
    if r.error_message:
        print(f"  note             : {_redact(r.error_message)}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env
    print("=" * 70)
    print("  PHASE 9B — ONE-PROVIDER LIVE SMOKE TEST")
    print("=" * 70)

    if not live_enabled(env):
        print("  LIVE PROVIDERS DISABLED (default safe mode) — no network call made.")
        print(f"  To enable: set {FLAG_ENV}=1 and {KEY_ENV}=<your key>, then re-run.")
        return EXIT_DISABLED

    key = resolve_key(env)
    if key is None:
        print(f"  {FLAG_ENV}=1 but {KEY_ENV} is missing/placeholder — refusing to run.")
        print(f"  No network call made. Set {KEY_ENV} locally (never commit it).")
        return EXIT_NO_KEY
    if not key.isascii():
        n = sum(1 for c in key if ord(c) > 127)
        print(f"  {KEY_ENV} contains {n} non-ASCII character(s) — almost certainly a")
        print(f"  copy/paste artifact (a real key is plain ASCII, sk-ant-...). Re-copy it")
        print(f"  cleanly and retry. No network call made. (Key never printed.)")
        return EXIT_NO_KEY

    model = env.get(MODEL_ENV) or DEFAULT_LIVE_MODEL
    try:
        max_tokens = int(env.get(MAXTOK_ENV) or DEFAULT_LIVE_MAX_TOKENS)
    except (TypeError, ValueError):
        max_tokens = DEFAULT_LIVE_MAX_TOKENS
    try:
        timeout = float(env.get(TIMEOUT_ENV) or DEFAULT_LIVE_TIMEOUT)
    except (TypeError, ValueError):
        timeout = DEFAULT_LIVE_TIMEOUT

    print(f"  LIVE CALL ENABLED — one provider, one task (model={model}, timeout={timeout:g}s).")
    print(f"  (key loaded from {KEY_ENV}; it is never printed.)")
    print("-" * 70)
    if env.get(DEBUG_ENV) == "1":
        _debug_live_traceback(key, model=model, max_tokens=max_tokens, timeout=timeout)
        print("-" * 70)
        return EXIT_OK
    try:
        result = _run_live_smoke(key, model=model, max_tokens=max_tokens, timeout=timeout)
    except Exception as exc:  # never leak; redact any key-shaped content
        print("  LIVE SMOKE FAILED:", _redact(str(exc), key))
        print("-" * 70)
        return EXIT_LIVE_ERROR
    print_summary(result)
    print("-" * 70)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

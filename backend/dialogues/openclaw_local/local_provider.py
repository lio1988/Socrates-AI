"""
OpenClaw Local LLM provider (Goal 10).

A local model as a council-shaped adapter — the intended first holder of the
`local_apprentice_001` identity profile. It targets any OpenAI-compatible
chat-completions endpoint served on the operator's own machine:

  - Ollama       (default: http://localhost:11434/v1)
  - LM Studio    (http://localhost:1234/v1)
  - llama.cpp / vLLM / any compatible server

The transport, retry, redaction, no-fabrication, and JSON-repair machinery is
INHERITED from the existing OpenAI-compatible adapter
(`LiveNvidiaNIMAdapter`) — one proven transport, two deployment flavors. The
local flavor differs in exactly three honest ways:

  1. No API key is required (local servers do not authenticate);
     ``is_available`` is availability of the adapter, not of a key.
  2. Its own explicit gate: ``CED_ENABLE_LOCAL_APPRENTICE=1`` plus
     ``CED_LOCAL_LLM_MODEL``. Local runs cost no credits, but reaching a
     server process is still an explicit operator decision — nothing here
     activates by default, and a missing gate is a clean skip with a
     helpful reason, never an error.
  3. Its first job is SHADOW: ``build_local_shadow_apprentice`` hands the
     adapter to the Goal 11 runner, where it observes, gets judged, and
     earns identity evidence — it cannot touch final answers before the
     Promotion Arena gate (Stage 2+).

Hard guarantees (inherited + kept):
  - no network call at import/build time; the endpoint is contacted only
    inside a running task (or the explicit ``probe_local_server`` helper)
  - env-only configuration, never reads ``.env``
  - provider failures yield honest ProviderResponse records, never a
    fabricated move; a dead server is a connection error, not a crash
  - keys (if an operator sets one for a proxy) are redacted from errors
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

from backend.dialogues.nvidia_nim_provider import LiveNvidiaNIMAdapter

#: Ollama's OpenAI-compatible surface — the most common local default.
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LOCAL_MAX_TOKENS = 2048
DEFAULT_LOCAL_TIMEOUT = 120.0

#: The design-target apprentice identity (SELF_IMPROVING_AGENT_IDENTITY.md).
DEFAULT_APPRENTICE_ID = "local_apprentice_001"

#: Env switches (checked on the env mapping the caller passes — never .env).
LOCAL_GATE_ENV = "CED_ENABLE_LOCAL_APPRENTICE"
LOCAL_URL_ENV = "CED_LOCAL_LLM_URL"
LOCAL_MODEL_ENV = "CED_LOCAL_LLM_MODEL"
LOCAL_TIMEOUT_ENV = "CED_LOCAL_LLM_TIMEOUT"
LOCAL_KEY_ENV = "CED_LOCAL_LLM_KEY"

#: Placeholder credential for servers that need none (not a secret).
NO_KEY = "local-no-key"


class LocalLLMAdapter(LiveNvidiaNIMAdapter):
    """A local OpenAI-compatible model as a council-shaped provider seat."""

    is_fake = False
    is_offline = False
    is_live = True
    is_local = True
    provider_name = "Local LLM"

    def __init__(
        self,
        provider_id: str = DEFAULT_APPRENTICE_ID,
        *,
        model: str,
        base_url: str = DEFAULT_LOCAL_BASE_URL,
        api_key: str = NO_KEY,
        max_tokens: int = DEFAULT_LOCAL_MAX_TOKENS,
        timeout: float = DEFAULT_LOCAL_TIMEOUT,
        retries: int = 0,
        transport=None,
        enabled: bool = True,
    ) -> None:
        if not model.strip():
            raise ValueError("LocalLLMAdapter requires a model name "
                             "(e.g. 'llama3.1:8b')")
        super().__init__(
            provider_id, api_key, model=model, base_url=base_url,
            max_tokens=max_tokens, timeout=timeout, retries=retries,
            transport=transport, enabled=enabled)
        self.provider_name = f"Local LLM ({model} @ {self.base_url})"

    def is_available(self) -> bool:
        """Local servers need no key: availability is just 'enabled'."""
        return self.enabled


# ── Gated, env-only resolution (clean skip, never a crash) ───────────────────

def resolve_local_adapter(
    env: Optional[Dict[str, str]] = None,
    *,
    provider_id: str = DEFAULT_APPRENTICE_ID,
) -> Tuple[Optional[LocalLLMAdapter], str]:
    """Return ``(adapter, reason)``. ``adapter`` is None unless the explicit
    gate is set AND a model is named — with the reason saying exactly what to
    do, so a missing local setup is a helpful skip, never an error."""
    env = dict(os.environ) if env is None else env
    if env.get(LOCAL_GATE_ENV, "").strip() != "1":
        return None, (f"local apprentice disabled "
                      f"(set {LOCAL_GATE_ENV}=1 to enable)")
    model = env.get(LOCAL_MODEL_ENV, "").strip()
    if not model:
        return None, (f"no local model named "
                      f"(set {LOCAL_MODEL_ENV}, e.g. llama3.1:8b)")
    base_url = env.get(LOCAL_URL_ENV, "").strip() or DEFAULT_LOCAL_BASE_URL
    try:
        timeout = float(env.get(LOCAL_TIMEOUT_ENV, "") or DEFAULT_LOCAL_TIMEOUT)
    except ValueError:
        return None, f"invalid {LOCAL_TIMEOUT_ENV} (must be a number)"
    api_key = env.get(LOCAL_KEY_ENV, "").strip() or NO_KEY
    adapter = LocalLLMAdapter(provider_id, model=model, base_url=base_url,
                              api_key=api_key, timeout=timeout)
    return adapter, f"enabled ({model} @ {base_url})"


# ── Preflight probe (explicit, injectable — never called by tests for real) ──

def probe_local_server(
    base_url: str = DEFAULT_LOCAL_BASE_URL,
    *,
    timeout: float = 3.0,
    opener: Optional[Callable[[str, float], str]] = None,
) -> Tuple[bool, str]:
    """Check the OpenAI-compatible ``/models`` endpoint. Returns
    ``(ok, message)`` — a dead server yields a helpful hint, never a raise.
    ``opener(url, timeout) -> body`` is the injectable transport seam."""
    url = f"{base_url.rstrip('/')}/models"

    def _default_opener(u: str, t: float) -> str:
        with urllib.request.urlopen(u, timeout=t) as resp:  # noqa: S310
            return resp.read().decode("utf-8")

    try:
        body = (opener or _default_opener)(url, timeout)
        json.loads(body)
        return True, f"local server responding at {base_url}"
    except Exception as exc:
        return False, (f"no local server at {base_url} ({exc.__class__.__name__}) "
                       "- is your local runtime (e.g. Ollama or LM Studio) "
                       "running?")


# ── The bridge: Goal 10 hosts Goal 11 ────────────────────────────────────────

def build_local_shadow_apprentice(
    env: Optional[Dict[str, str]] = None,
    *,
    judges,
    lessons=None,
    provider_id: str = DEFAULT_APPRENTICE_ID,
) -> Tuple[Optional[Any], str]:
    """Gated builder for the full Stage-1 setup: the local model as the
    Shadow Apprentice. Returns ``(runner, reason)`` — None + reason when the
    gate is off (clean skip). The runner observes and earns identity
    evidence; it cannot affect final answers (Goal 11 guarantees)."""
    adapter, reason = resolve_local_adapter(env, provider_id=provider_id)
    if adapter is None:
        return None, reason
    from backend.dialogues.openclaw_shadow import ShadowApprentice
    runner = ShadowApprentice(adapter, judges, lessons=lessons,
                              timeout_seconds=adapter.timeout)
    return runner, reason

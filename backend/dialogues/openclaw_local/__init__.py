"""
OpenClaw Local — the local LLM provider (Goal 10).

A local model (Ollama / LM Studio / any OpenAI-compatible localhost server)
as a council-shaped adapter, gated by CED_ENABLE_LOCAL_APPRENTICE=1 +
CED_LOCAL_LLM_MODEL. Its first job is the Goal 11 Shadow Apprentice: it
observes, gets judged, and earns identity evidence — it cannot touch final
answers before the Promotion Arena gate.

Runtime-inert toward the council: the CED core never imports this package
(test-locked). No network at import/build time; env-only config; no .env.
"""

from .local_provider import (
    DEFAULT_APPRENTICE_ID,
    DEFAULT_LOCAL_BASE_URL,
    LOCAL_GATE_ENV,
    LOCAL_KEY_ENV,
    LOCAL_MODEL_ENV,
    LOCAL_TIMEOUT_ENV,
    LOCAL_URL_ENV,
    NO_KEY,
    LocalLLMAdapter,
    build_local_shadow_apprentice,
    probe_local_server,
    resolve_local_adapter,
)

__all__ = [
    "DEFAULT_APPRENTICE_ID",
    "DEFAULT_LOCAL_BASE_URL",
    "LOCAL_GATE_ENV",
    "LOCAL_KEY_ENV",
    "LOCAL_MODEL_ENV",
    "LOCAL_TIMEOUT_ENV",
    "LOCAL_URL_ENV",
    "NO_KEY",
    "LocalLLMAdapter",
    "build_local_shadow_apprentice",
    "probe_local_server",
    "resolve_local_adapter",
]

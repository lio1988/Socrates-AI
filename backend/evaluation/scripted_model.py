"""Deterministic stand-in for an LLM, used by the CED Evaluation Harness.

ScriptedModel returns canned responses for prompts and NEVER performs any
network or live-model call. That is what keeps the harness deterministic and
CI-safe; a guard test asserts that no live model is ever invoked during a run.
"""

from __future__ import annotations

from typing import Dict, List


class ScriptedModel:
    """A non-live model. Responses are looked up, never generated."""

    # Marker so callers/tests can assert this is not a live provider.
    is_scripted = True

    def __init__(self, script: Dict[str, str] | None = None, default: str = "") -> None:
        self._script = dict(script or {})
        self._default = default
        self.calls: List[str] = []

    def respond(self, prompt: str) -> str:
        """Deterministic: exact key match, else first substring-key match, else default."""
        self.calls.append(prompt)
        if prompt in self._script:
            return self._script[prompt]
        for key, value in self._script.items():
            if key and key in prompt:
                return value
        return self._default

    async def _call_model(self, model_id: str, prompt: str) -> str:
        """Mirror DialogManager so this can stand in as session.manager. If the
        async pipeline ever calls it, it still returns a scripted (never live)
        response. v0.1 drives the engine directly and does not invoke this."""
        return self.respond(prompt)

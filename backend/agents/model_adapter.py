"""
Model Adapter
=============

A thin, provider-agnostic interface so the orchestrator never hard-codes a
single vendor (directive Principle 1: no permanent authority — that applies to
plumbing too). Real adapters (Anthropic, OpenAI, local) implement `complete`.
`MockModel` returns deterministic output so the epistemic machinery can be
developed and tested without network access or cost.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str


class ModelAdapter(ABC):
    name: str

    @abstractmethod
    def complete(self, messages: List[Message], temperature: float = 0.7,
                 max_tokens: int = 1024) -> str:
        ...


class MockModel(ModelAdapter):
    """Deterministic stand-in. Same input -> same output, so tests are stable."""

    def __init__(self, name: str, persona: str = "neutral") -> None:
        self.name = name
        self.persona = persona

    def complete(self, messages: List[Message], temperature: float = 0.7,
                 max_tokens: int = 1024) -> str:
        joined = "\n".join(m.content for m in messages)
        h = hashlib.sha256((self.name + joined).encode()).hexdigest()[:8]
        last_user = next((m.content for m in reversed(messages)
                          if m.role == "user"), "")
        return (f"[{self.name}|{self.persona}] response to "
                f"'{last_user[:60]}' (sig {h})")


class AnthropicAdapter(ModelAdapter):
    """Real adapter. Requires the `anthropic` package and an API key in config.
    Left thin on purpose; wire it up when moving past the MVP mock."""

    def __init__(self, name: str, model: str, api_key: Optional[str]) -> None:
        self.name = name
        self.model = model
        self._api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import anthropic  # noqa: imported lazily
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, messages: List[Message], temperature: float = 0.7,
                 max_tokens: int = 1024) -> str:
        client = self._ensure_client()
        system = "\n".join(m.content for m in messages if m.role == "system")
        convo = [{"role": m.role, "content": m.content}
                 for m in messages if m.role in ("user", "assistant")]
        resp = client.messages.create(
            model=self.model,
            system=system or None,
            messages=convo,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return "".join(block.text for block in resp.content
                       if getattr(block, "type", None) == "text")

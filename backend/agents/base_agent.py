"""
Base Agent
==========

An Agent wraps a ModelAdapter and a current Role. Roles rotate (directive §8);
no agent is permanently Socrates, judge, or synthesizer. The agent is a tool —
the Claim is the protagonist.
"""

from __future__ import annotations

from enum import Enum
from typing import List

from .model_adapter import ModelAdapter, Message


class Role(str, Enum):
    INTERLOCUTOR = "interlocutor"   # proposes / defends positions
    SOCRATES = "socrates"           # only questions, never asserts
    SYNTHESIZER = "synthesizer"     # weaves surviving claims (post-challenge)
    META = "meta"                   # evaluates the process, not the answer


class Agent:
    def __init__(self, agent_id: str, model: ModelAdapter,
                 role: Role = Role.INTERLOCUTOR) -> None:
        self.agent_id = agent_id
        self.model = model
        self.role = role

    def think(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self.model.complete(
            [Message("system", system), Message("user", user)],
            temperature=temperature,
        )

    def __repr__(self) -> str:
        return f"<Agent {self.agent_id} model={self.model.name} role={self.role.value}>"

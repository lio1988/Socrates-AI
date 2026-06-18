"""
Socratic Rotation
=================

Enforces directive Principle 1: no model is permanently the Socratic
questioner / authority. Each round, the Socratic role moves to the next agent
in a deterministic rotation. The class also records the history so tests (and
the Meta-Socrates evaluator) can prove rotation actually happened and no single
agent dominated.
"""

from __future__ import annotations

from collections import Counter
from typing import List

from ..agents.base_agent import Agent, Role


SOCRATES_PROMPT = """You are Socrates for this round.
Do not answer the problem directly.
Expose one hidden assumption, one possible contradiction, or one missing
definition. End with exactly one precise question that forces revision."""


class SocraticRotation:
    def __init__(self, agents: List[Agent]) -> None:
        if len(agents) < 2:
            raise ValueError("Socratic rotation needs at least two agents.")
        self.agents = agents
        self._round = 0
        self.history: List[str] = []   # agent_id that played Socrates each round

    def next_socrates(self) -> Agent:
        """Assign the Socratic role to the next agent, clearing it from others."""
        socrates = self.agents[self._round % len(self.agents)]
        for a in self.agents:
            a.role = Role.SOCRATES if a is socrates else Role.INTERLOCUTOR
        self.history.append(socrates.agent_id)
        self._round += 1
        return socrates

    def domination_report(self) -> dict:
        counts = Counter(self.history)
        total = sum(counts.values()) or 1
        max_share = max(counts.values()) / total if counts else 0.0
        return {
            "rounds": self._round,
            "socrates_counts": dict(counts),
            "max_share": round(max_share, 3),
            "balanced": max_share <= (1.0 / len(self.agents)) + 0.25,
        }

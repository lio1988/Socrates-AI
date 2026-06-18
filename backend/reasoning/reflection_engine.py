"""
Reflection Engine
=================

Every participating agent must reflect before final submission (directive §10).
The reflection is forced into four sections and ONLY the FINAL section is
eligible for claim extraction. This prevents premature, unexamined positions
from entering the Epistemic Graph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..agents.base_agent import Agent


REFLECTION_PROMPT = """Reason about the problem, then answer in EXACTLY this format:

INITIAL:
<your first position>

SELF_CRITICISM:
<weaknesses, missing evidence, possible bias in your initial position>

REVISION:
<how your position changes after self-criticism>

FINAL:
<your revised, final position>

PROBLEM: {problem}
"""

_SECTION_RE = {
    "initial": re.compile(r"INITIAL:\s*(.*?)(?:SELF_CRITICISM:|$)", re.S | re.I),
    "self_criticism": re.compile(r"SELF_CRITICISM:\s*(.*?)(?:REVISION:|$)", re.S | re.I),
    "revision": re.compile(r"REVISION:\s*(.*?)(?:FINAL:|$)", re.S | re.I),
    "final": re.compile(r"FINAL:\s*(.*)$", re.S | re.I),
}


@dataclass
class Reflection:
    agent_id: str
    initial: str
    self_criticism: str
    revision: str
    final: str
    raw: str

    @property
    def claim_text(self) -> str:
        """Only the FINAL section feeds claim extraction."""
        return self.final.strip()


class ReflectionEngine:
    def reflect(self, agent: Agent, problem: str) -> Reflection:
        raw = agent.think(
            system="You reason carefully and revise your own views.",
            user=REFLECTION_PROMPT.format(problem=problem),
            temperature=0.6,
        )
        return self._parse(agent.agent_id, raw)

    @staticmethod
    def _extract(pattern: re.Pattern, text: str) -> str:
        m = pattern.search(text)
        return (m.group(1).strip() if m else "").strip()

    def _parse(self, agent_id: str, raw: str) -> Reflection:
        initial = self._extract(_SECTION_RE["initial"], raw)
        final = self._extract(_SECTION_RE["final"], raw)
        # If the model (e.g. the mock) didn't honour the format, fall back to
        # treating the whole output as FINAL so the pipeline never crashes.
        if not final:
            final = raw.strip()
        return Reflection(
            agent_id=agent_id,
            initial=initial,
            self_criticism=self._extract(_SECTION_RE["self_criticism"], raw),
            revision=self._extract(_SECTION_RE["revision"], raw),
            final=final,
            raw=raw,
        )

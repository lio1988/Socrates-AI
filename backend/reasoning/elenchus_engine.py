"""
Elenchus Engine
===============

Socratic refutation. Every major claim must be challenged before it can advance
toward knowledge (directive §9, §18). This engine produces a structured
challenge report and applies the lifecycle consequence:

  * if falsification succeeds -> claim moves to CHALLENGED (then possibly
    REJECTED by the belief-revision engine)
  * if the claim survives      -> its stability_under_challenge increases

The challenge report is intentionally structured JSON-like data so downstream
engines (belief revision, knowledge emergence) can act on it programmatically
rather than parsing prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..agents.base_agent import Agent
from ..epistemic.claim import Claim
from ..epistemic.epistemic_state import EpistemicState


ELENCHUS_PROMPT = """Challenge the following claim as a rigorous skeptic.
Identify, separately:
1. Hidden assumptions that may be false.
2. Logical gaps or invalid inferences.
3. Weaknesses in the evidence.
4. Alternative explanations that fit equally well.
Then state whether the claim is FALSIFIED or SURVIVES, and whether revision is
required. Be specific; do not hedge.

CLAIM: {claim_text}
"""


@dataclass
class ChallengeReport:
    target_claim_id: str
    challenger: str
    challenged_assumptions: List[str] = field(default_factory=list)
    logic_gaps: List[str] = field(default_factory=list)
    evidence_issues: List[str] = field(default_factory=list)
    alternative_explanations: List[str] = field(default_factory=list)
    falsification_successful: bool = False
    revision_required: bool = True
    raw: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "target_claim_id": self.target_claim_id,
            "challenger": self.challenger,
            "challenged_assumptions": self.challenged_assumptions,
            "logic_gaps": self.logic_gaps,
            "evidence_issues": self.evidence_issues,
            "alternative_explanations": self.alternative_explanations,
            "falsification_successful": self.falsification_successful,
            "revision_required": self.revision_required,
        }


class ElenchusEngine:
    def __init__(self, parser=None) -> None:
        # `parser` converts raw model text into structured fields. For the MVP
        # we default to a heuristic parser; swap in an LLM-structured-output
        # parser later without touching callers.
        self._parse = parser or self._heuristic_parse

    def challenge(self, claim: Claim, challenger: Agent) -> ChallengeReport:
        prompt = ELENCHUS_PROMPT.format(claim_text=claim.text)
        raw = challenger.think(
            system="You are a precise, adversarial epistemic auditor.",
            user=prompt,
            temperature=0.3,
        )
        report = self._parse(claim, challenger, raw)

        # Apply the lifecycle consequence of the challenge.
        if claim.state in (EpistemicState.HYPOTHESIS, EpistemicState.SUPPORTED,
                           EpistemicState.VERIFIED, EpistemicState.REVISED,
                           EpistemicState.KNOWLEDGE):
            claim.transition(
                EpistemicState.CHALLENGED,
                actor=f"elenchus:{challenger.agent_id}",
                reason="Subjected to Socratic refutation.",
            )
        if report.falsification_successful:
            claim.adjust_confidence(
                claim.confidence * 0.5,
                actor=f"elenchus:{challenger.agent_id}",
                reason="Falsification arguments reduced confidence.",
            )
        else:
            claim.stability_under_challenge += 1
            claim.adjust_confidence(
                min(1.0, claim.confidence + 0.05),
                actor=f"elenchus:{challenger.agent_id}",
                reason="Claim survived challenge; stability increased.",
            )
        return report

    # A deliberately conservative heuristic for the MVP/mock path.
    @staticmethod
    def _heuristic_parse(claim: Claim, challenger: Agent, raw: str) -> ChallengeReport:
        lowered = raw.lower()
        falsified = "falsified" in lowered and "not falsified" not in lowered
        return ChallengeReport(
            target_claim_id=claim.claim_id,
            challenger=challenger.agent_id,
            challenged_assumptions=["(parsed from challenger output)"],
            falsification_successful=falsified,
            revision_required=not claim.stability_under_challenge >= 2,
            raw=raw,
        )

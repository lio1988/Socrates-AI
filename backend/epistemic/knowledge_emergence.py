"""
Knowledge Emergence Engine
==========================

Replaces "consensus = truth" with evidence-gated promotion (directive §12).
A claim is promoted to KNOWLEDGE only if it clears every threshold AND has
survived challenge. Consensus is neither necessary nor sufficient:

  * weak-evidence + everyone agrees  -> NOT promoted
  * strong-evidence + lone dissenter -> dissenter's claim stays visible

The engine never invents facts; it only re-rates and transitions existing claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .claim import Claim
from .epistemic_state import EpistemicState
from .epistemic_graph import EpistemicGraph
from ..config import EmergenceThresholds


@dataclass
class EmergenceDecision:
    claim_id: str
    promoted: bool
    reasons: List[str]


class KnowledgeEmergenceEngine:
    def __init__(self, thresholds: EmergenceThresholds) -> None:
        self.t = thresholds

    def evaluate(self, claim: Claim) -> EmergenceDecision:
        reasons: List[str] = []
        ok = True

        if not claim.has_been_challenged:
            ok = False
            reasons.append("Never survived challenge (Elenchus).")
        if claim.evidence_quality < self.t.evidence_quality:
            ok = False
            reasons.append(
                f"Evidence quality {claim.evidence_quality:.2f} "
                f"< {self.t.evidence_quality}.")
        if claim.confidence < self.t.confidence:
            ok = False
            reasons.append(
                f"Confidence {claim.confidence:.2f} < {self.t.confidence}.")
        if claim.independent_reviews < self.t.min_independent_reviews:
            ok = False
            reasons.append(
                f"Independent reviews {claim.independent_reviews} "
                f"< {self.t.min_independent_reviews}.")
        unresolved = [c for c in claim.contradictions]
        if unresolved:
            reasons.append(
                f"{len(unresolved)} contradiction(s) recorded "
                "(documented, kept visible).")

        if ok:
            # Route legally to VERIFIED first if not already there.
            if claim.state in (EpistemicState.SUPPORTED, EpistemicState.REVISED):
                claim.transition(EpistemicState.VERIFIED,
                                 actor="knowledge_emergence",
                                 reason="Cleared evidence + review thresholds.")
            if claim.state == EpistemicState.VERIFIED:
                claim.transition(EpistemicState.KNOWLEDGE,
                                 actor="knowledge_emergence",
                                 reason="Promoted: evidence over agreement.")
                reasons.append("Promoted to KNOWLEDGE.")
        return EmergenceDecision(claim.claim_id, claim.state == EpistemicState.KNOWLEDGE, reasons)

    def evaluate_all(self, graph: EpistemicGraph) -> List[EmergenceDecision]:
        return [self.evaluate(c) for c in list(graph.claims.values())]

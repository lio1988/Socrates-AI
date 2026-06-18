"""
Synthesis Engine
================

Builds the Current Best Explanation from claims that survived challenge. Crucial
constraint (directive §18): synthesis MUST NOT add new facts. This engine only
references existing claim_ids and their stored text; it cannot mint new claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..epistemic.claim import Claim
from ..epistemic.epistemic_state import EpistemicState
from ..epistemic.epistemic_graph import EpistemicGraph


@dataclass
class CurrentBestExplanation:
    question: str
    summary_claim_ids: List[str]
    strongest_claims: List[Dict]
    unresolved_disagreements: List[Dict]
    rejected_hypotheses: List[Dict]
    open_questions: List[str]
    confidence: float
    why_preferred: str
    reasoning_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": "Current Best Explanation",
            "question": self.question,
            "strongest_claims": self.strongest_claims,
            "unresolved_disagreements": self.unresolved_disagreements,
            "rejected_hypotheses": self.rejected_hypotheses,
            "open_questions": self.open_questions,
            "confidence": round(self.confidence, 3),
            "why_preferred": self.why_preferred,
            "reasoning_trace": self.reasoning_trace,
            "note": "This is a current best explanation, not final truth.",
        }


class SynthesisEngine:
    def synthesize(self, question: str, graph: EpistemicGraph,
                   trace: List[str]) -> CurrentBestExplanation:
        claims = list(graph.claims.values())

        strongest = sorted(
            [c for c in claims if c.state in (
                EpistemicState.KNOWLEDGE, EpistemicState.VERIFIED,
                EpistemicState.SUPPORTED)],
            key=lambda c: (c.evidence_quality, c.confidence),
            reverse=True,
        )
        rejected = [c for c in claims if c.state in (
            EpistemicState.REJECTED, EpistemicState.OBSOLETE)]
        disputed = [c for c in claims if c.state == EpistemicState.DISPUTED
                    or c.contradictions]

        # Confidence of the explanation = best supported claim's confidence,
        # discounted by unresolved disagreement. No new numbers invented.
        base = strongest[0].confidence if strongest else 0.0
        penalty = 0.05 * len(disputed)
        conf = max(0.0, base - penalty)

        return CurrentBestExplanation(
            question=question,
            summary_claim_ids=[c.claim_id for c in strongest[:3]],
            strongest_claims=[c.to_dict() for c in strongest[:3]],
            unresolved_disagreements=[
                {"claim_id": c.claim_id, "text": c.text,
                 "contradicts": c.contradictions} for c in disputed],
            rejected_hypotheses=[
                {"claim_id": c.claim_id, "text": c.text,
                 "state": c.state.value} for c in rejected],
            open_questions=[n.label for n in graph.nodes.values()
                            if n.node_type.value == "Question"],
            confidence=conf,
            why_preferred=(
                "Preferred because it rests on the highest-evidence claims that "
                "survived Socratic challenge; disagreements are listed, not hidden."
            ),
            reasoning_trace=trace,
        )

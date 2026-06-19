"""CED Graph v3 epistemic scoring engine.

Deterministically converts graph evidence, contradictions, uncertainty, revision
maturity, and source diversity into a claim confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_graph import EpistemicGraph
from backend.epistemic.epistemic_state import EpistemicState
from backend.orchestrator.structured_epistemic_parser import ParsedEpistemicAnswer


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _edge_type_value(edge) -> str:
    return getattr(edge.edge_type, "value", edge.edge_type)


@dataclass(frozen=True)
class EpistemicScoreBreakdown:
    claim_id: str
    score: float
    confidence_before: float
    confidence_after: float
    confidence_level: str
    evidence_quality: float
    evidence_count: int
    support_count: int
    support_score: float
    contradiction_count: int
    contradiction_edge_count: int
    contradiction_pressure: float
    uncertainty_score: float
    uncertainty_penalty: float
    evidence_gap_penalty: float
    revision_maturity: float
    source_diversity_bonus: float
    state_bonus: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "score": self.score,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "confidence_level": self.confidence_level,
            "evidence_quality": self.evidence_quality,
            "evidence_count": self.evidence_count,
            "support_count": self.support_count,
            "support_score": self.support_score,
            "contradiction_count": self.contradiction_count,
            "contradiction_edge_count": self.contradiction_edge_count,
            "contradiction_pressure": self.contradiction_pressure,
            "uncertainty_score": self.uncertainty_score,
            "uncertainty_penalty": self.uncertainty_penalty,
            "evidence_gap_penalty": self.evidence_gap_penalty,
            "revision_maturity": self.revision_maturity,
            "source_diversity_bonus": self.source_diversity_bonus,
            "state_bonus": self.state_bonus,
            "reasons": list(self.reasons),
        }


class EpistemicScoringEngine:
    """Score live claims without external model calls.

    The scoring formula is deliberately transparent and monotonic:
    support raises confidence; contradiction pressure, uncertainty, and evidence
    gaps lower it; revision maturity and source diversity add modest resilience.
    """

    VERSION = "v3"

    STATE_BONUS = {
        EpistemicState.HYPOTHESIS: 0.00,
        EpistemicState.SUPPORTED: 0.06,
        EpistemicState.CHALLENGED: -0.06,
        EpistemicState.DISPUTED: -0.10,
        EpistemicState.REVISED: 0.06,
        EpistemicState.VERIFIED: 0.14,
        EpistemicState.KNOWLEDGE: 0.20,
        EpistemicState.REJECTED: -0.30,
    }

    def apply_score(
        self,
        graph: EpistemicGraph,
        claim: Claim,
        parsed: ParsedEpistemicAnswer | None = None,
    ) -> EpistemicScoreBreakdown:
        breakdown = self.score(graph, claim, parsed)

        if abs(claim.confidence - breakdown.confidence_after) >= 0.005:
            claim.adjust_confidence(
                breakdown.confidence_after,
                actor="epistemic_scoring:v3",
                reason="CED Graph v3 confidence score applied.",
            )

        return breakdown

    def score(
        self,
        graph: EpistemicGraph,
        claim: Claim,
        parsed: ParsedEpistemicAnswer | None = None,
    ) -> EpistemicScoreBreakdown:
        evidence_count = len([ev for ev in claim.evidence if ev.supports])
        evidence_quality = round(claim.evidence_quality, 3)
        support_count = self._support_count(graph, claim.claim_id)
        contradiction_edge_count = self._contradiction_edge_count(graph, claim.claim_id)
        contradiction_count = len(claim.contradictions)

        support_score = round(
            min(0.18, (0.12 * evidence_quality) + (0.03 * min(support_count, 3))),
            3,
        )

        contradiction_pressure = round(
            min(0.35, (0.10 * contradiction_count) + (0.04 * contradiction_edge_count)),
            3,
        )

        uncertainty_score = round(self._uncertainty_score(graph, claim.claim_id, parsed), 3)
        uncertainty_penalty = round(min(0.22, uncertainty_score * 0.20), 3)
        evidence_gap_penalty = 0.14 if evidence_count == 0 else 0.0
        revision_maturity = round(self._revision_maturity(claim), 3)
        source_diversity_bonus = round(self._source_diversity_bonus(claim), 3)
        state_bonus = round(self.STATE_BONUS.get(claim.state, 0.0), 3)

        raw = (
            0.50
            + support_score
            + state_bonus
            + revision_maturity
            + source_diversity_bonus
            - contradiction_pressure
            - uncertainty_penalty
            - evidence_gap_penalty
        )

        score = round(_clamp(raw), 3)
        level = self._confidence_level(score)

        reasons = self._reasons(
            evidence_count=evidence_count,
            support_score=support_score,
            contradiction_pressure=contradiction_pressure,
            uncertainty_penalty=uncertainty_penalty,
            evidence_gap_penalty=evidence_gap_penalty,
            revision_maturity=revision_maturity,
            source_diversity_bonus=source_diversity_bonus,
            state_bonus=state_bonus,
        )

        return EpistemicScoreBreakdown(
            claim_id=claim.claim_id,
            score=score,
            confidence_before=round(claim.confidence, 3),
            confidence_after=score,
            confidence_level=level,
            evidence_quality=evidence_quality,
            evidence_count=evidence_count,
            support_count=support_count,
            support_score=support_score,
            contradiction_count=contradiction_count,
            contradiction_edge_count=contradiction_edge_count,
            contradiction_pressure=contradiction_pressure,
            uncertainty_score=uncertainty_score,
            uncertainty_penalty=uncertainty_penalty,
            evidence_gap_penalty=round(evidence_gap_penalty, 3),
            revision_maturity=revision_maturity,
            source_diversity_bonus=source_diversity_bonus,
            state_bonus=state_bonus,
            reasons=reasons,
        )

    def _support_count(self, graph: EpistemicGraph, claim_id: str) -> int:
        return sum(
            1
            for edge in graph.edges.values()
            if _edge_type_value(edge) == "supports" and edge.dst == claim_id
        )

    def _contradiction_edge_count(self, graph: EpistemicGraph, claim_id: str) -> int:
        return sum(
            1
            for edge in graph.edges.values()
            if _edge_type_value(edge) == "contradicts"
            and (edge.src == claim_id or edge.dst == claim_id)
        )

    def _uncertainty_score(
        self,
        graph: EpistemicGraph,
        claim_id: str,
        parsed: ParsedEpistemicAnswer | None,
    ) -> float:
        if parsed is not None:
            return parsed.uncertainty_score

        node = graph.nodes.get(claim_id)
        if node is None:
            return 0.5

        payload = node.payload or {}
        return float(payload.get("uncertainty_score", 0.5))

    def _revision_maturity(self, claim: Claim) -> float:
        return min(
            0.12,
            (0.015 * min(len(claim.revision_history), 4))
            + (0.03 * min(claim.stability_under_challenge, 2))
            + (0.02 * min(claim.independent_reviews, 2)),
        )

    def _source_diversity_bonus(self, claim: Claim) -> float:
        sources = {ev.source for ev in claim.evidence if ev.supports and ev.source}
        return min(0.08, 0.04 * max(0, len(sources) - 1))

    def _confidence_level(self, score: float) -> str:
        if score >= 0.75:
            return "strong"
        if score >= 0.55:
            return "supported"
        if score >= 0.35:
            return "tentative"
        return "weak"

    def _reasons(
        self,
        *,
        evidence_count: int,
        support_score: float,
        contradiction_pressure: float,
        uncertainty_penalty: float,
        evidence_gap_penalty: float,
        revision_maturity: float,
        source_diversity_bonus: float,
        state_bonus: float,
    ) -> list[str]:
        reasons: list[str] = []

        if evidence_count:
            reasons.append(f"support:+{support_score}")
        else:
            reasons.append(f"evidence_gap:-{evidence_gap_penalty}")

        if contradiction_pressure:
            reasons.append(f"contradiction_pressure:-{contradiction_pressure}")

        if uncertainty_penalty:
            reasons.append(f"uncertainty:-{uncertainty_penalty}")

        if revision_maturity:
            reasons.append(f"revision_maturity:+{revision_maturity}")

        if source_diversity_bonus:
            reasons.append(f"source_diversity:+{source_diversity_bonus}")

        if state_bonus:
            sign = "+" if state_bonus > 0 else ""
            reasons.append(f"state:{sign}{state_bonus}")

        return reasons

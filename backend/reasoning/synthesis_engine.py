"""
Synthesis Engine
================

Builds the Current Best Explanation from claims that survived challenge. Crucial
constraint (directive §18): synthesis MUST NOT add new facts. This engine only
references existing claim_ids and their stored text; it cannot mint new claims.

CED Graph v4 adds deterministic ranking: the CBE prefers claims by their v3
EpistemicScoringEngine score plus lifecycle/ranking signals, while still listing
unresolved disagreements instead of hiding them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..epistemic.claim import Claim
from ..epistemic.epistemic_state import EpistemicState
from ..epistemic.epistemic_graph import EpistemicGraph
from ..orchestrator.epistemic_scoring import EpistemicScoringEngine


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _node_type_value(node) -> str:
    return getattr(node.node_type, "value", node.node_type)


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
    ranked_claims: List[Dict] = field(default_factory=list)
    ranking_version: str = "v4"
    # v5: lineage metadata for the strongest claims (claim_id -> lineage summary).
    lineage_by_claim: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "label": "Current Best Explanation",
            "question": self.question,
            "summary_claim_ids": self.summary_claim_ids,
            "strongest_claims": self.strongest_claims,
            "ranked_claims": self.ranked_claims,
            "ranking_version": self.ranking_version,
            "unresolved_disagreements": self.unresolved_disagreements,
            "rejected_hypotheses": self.rejected_hypotheses,
            "open_questions": self.open_questions,
            "confidence": round(self.confidence, 3),
            "why_preferred": self.why_preferred,
            "reasoning_trace": self.reasoning_trace,
            "lineage": self.lineage_by_claim,
            "note": "This is a current best explanation, not final truth.",
        }


class SynthesisEngine:
    """Build a ranked Current Best Explanation from graph-native claims."""

    RANKING_VERSION = "v4"

    STRONG_CANDIDATE_STATES = {
        EpistemicState.KNOWLEDGE,
        EpistemicState.VERIFIED,
        EpistemicState.SUPPORTED,
        EpistemicState.REVISED,
    }

    EXCLUDED_RANKING_STATES = {
        EpistemicState.REJECTED,
        EpistemicState.OBSOLETE,
        EpistemicState.ARCHIVED,
    }

    CBE_STATE_BONUS = {
        EpistemicState.KNOWLEDGE: 0.12,
        EpistemicState.VERIFIED: 0.10,
        EpistemicState.SUPPORTED: 0.06,
        EpistemicState.REVISED: 0.05,
        EpistemicState.HYPOTHESIS: -0.03,
        EpistemicState.CHALLENGED: -0.08,
        EpistemicState.DISPUTED: -0.12,
        EpistemicState.UNKNOWN: -0.08,
    }

    def __init__(self, scorer: EpistemicScoringEngine | None = None) -> None:
        self.scorer = scorer or EpistemicScoringEngine()

    def synthesize(self, question: str, graph: EpistemicGraph,
                   trace: List[str]) -> CurrentBestExplanation:
        claims = list(graph.claims.values())
        ranked = self._rank_claims(graph, claims)

        strongest_rows = [
            row for claim, row in ranked
            if claim.state in self.STRONG_CANDIDATE_STATES
        ]

        # Fallback: when the graph is still early and no claim has reached a
        # strong state, expose the best live hypotheses as tentative candidates.
        if not strongest_rows:
            strongest_rows = [row for _claim, row in ranked[:3]]

        rejected = [c for c in claims if c.state in (
            EpistemicState.REJECTED, EpistemicState.OBSOLETE)]
        disputed = [c for c in claims if c.state == EpistemicState.DISPUTED
                    or c.contradictions]

        top_score = strongest_rows[0]["cbe_score"] if strongest_rows else 0.0
        disagreement_penalty = min(0.30, 0.05 * len(disputed))
        conf = max(0.0, top_score - disagreement_penalty)

        return CurrentBestExplanation(
            question=question,
            summary_claim_ids=[row["claim_id"] for row in strongest_rows[:3]],
            strongest_claims=[row["claim"] for row in strongest_rows[:3]],
            ranked_claims=[row["ranking"] for _claim, row in ranked],
            unresolved_disagreements=[
                {
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "state": c.state.value,
                    "contradicts": c.contradictions,
                    "cbe_score": self._ranking_score_for(ranked, c.claim_id),
                }
                for c in disputed
            ],
            rejected_hypotheses=[
                {"claim_id": c.claim_id, "text": c.text,
                 "state": c.state.value} for c in rejected],
            open_questions=[n.label for n in graph.nodes.values()
                            if _node_type_value(n) == "Question"],
            confidence=conf,
            why_preferred=(
                "Preferred by CED Graph v4 ranking: highest v3 epistemic score, "
                "strong lifecycle state, evidence/support strength, revision maturity, "
                "and source diversity, with penalties for uncertainty, open problems, "
                "and unresolved contradictions. Disagreements remain listed, not hidden."
            ),
            reasoning_trace=trace,
            ranking_version=self.RANKING_VERSION,
        )

    def _rank_claims(
        self,
        graph: EpistemicGraph,
        claims: List[Claim],
    ) -> List[Tuple[Claim, Dict]]:
        rows: List[Tuple[Claim, Dict]] = []
        for claim in claims:
            if claim.state in self.EXCLUDED_RANKING_STATES:
                continue

            score = self.scorer.score(graph, claim)
            state_bonus = round(self.CBE_STATE_BONUS.get(claim.state, 0.0), 3)
            open_problem_penalty = self._open_problem_penalty(graph, claim.claim_id)
            contradiction_penalty = round(min(0.10, 0.025 * len(claim.contradictions)), 3)

            cbe_score = round(
                _clamp(score.score + state_bonus - open_problem_penalty - contradiction_penalty),
                3,
            )

            ranking = {
                "rank": 0,  # filled after sorting
                "claim_id": claim.claim_id,
                "author_model": claim.author_model,
                "state": claim.state.value,
                "cbe_score": cbe_score,
                "epistemic_score": score.score,
                "confidence_level": score.confidence_level,
                "evidence_quality": score.evidence_quality,
                "evidence_count": score.evidence_count,
                "support_count": score.support_count,
                "contradiction_pressure": score.contradiction_pressure,
                "uncertainty_penalty": score.uncertainty_penalty,
                "open_problem_penalty": open_problem_penalty,
                "state_bonus": state_bonus,
                "reasons": list(score.reasons) + self._cbe_reasons(
                    state_bonus=state_bonus,
                    open_problem_penalty=open_problem_penalty,
                    contradiction_penalty=contradiction_penalty,
                ),
                "text": claim.text,
                "ranking_version": self.RANKING_VERSION,
            }

            claim_dict = claim.to_dict()
            claim_dict["cbe_ranking"] = {k: v for k, v in ranking.items() if k != "text"}

            rows.append((claim, {"ranking": ranking, "claim": claim_dict, "claim_id": claim.claim_id, "cbe_score": cbe_score}))

        rows.sort(
            key=lambda item: (
                item[1]["cbe_score"],
                item[1]["ranking"]["epistemic_score"],
                item[0].evidence_quality,
                item[0].confidence,
                -len(item[0].contradictions),
            ),
            reverse=True,
        )

        for idx, (_claim, row) in enumerate(rows, start=1):
            row["ranking"]["rank"] = idx
            row["claim"]["cbe_ranking"]["rank"] = idx

        return rows

    def _open_problem_penalty(self, graph: EpistemicGraph, claim_id: str) -> float:
        linked_open_problems = 0
        for edge in graph.edges.values():
            if edge.src != claim_id and edge.dst != claim_id:
                continue
            other_id = edge.dst if edge.src == claim_id else edge.src
            other = graph.nodes.get(other_id)
            if other is not None and _node_type_value(other) == "OpenProblem":
                linked_open_problems += 1
        return round(min(0.12, 0.03 * linked_open_problems), 3)

    def _cbe_reasons(
        self,
        *,
        state_bonus: float,
        open_problem_penalty: float,
        contradiction_penalty: float,
    ) -> List[str]:
        reasons: List[str] = []
        if state_bonus:
            sign = "+" if state_bonus > 0 else ""
            reasons.append(f"cbe_state:{sign}{state_bonus}")
        if open_problem_penalty:
            reasons.append(f"open_problems:-{open_problem_penalty}")
        if contradiction_penalty:
            reasons.append(f"cbe_contradictions:-{contradiction_penalty}")
        return reasons

    def _ranking_score_for(self, ranked: List[Tuple[Claim, Dict]], claim_id: str) -> float | None:
        for _claim, row in ranked:
            if row["claim_id"] == claim_id:
                return row["cbe_score"]
        return None

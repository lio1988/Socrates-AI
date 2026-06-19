"""
CED Graph v6 — Meta-Socrates / Process Evaluator
=================================================

This module evaluates the quality of the reasoning process itself, not only the
quality of individual claims. It is deliberately additive: it does not mutate
claims, does not create new facts, and does not alter CBE selection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from backend.epistemic.epistemic_graph import EpistemicGraph, EdgeType
from backend.orchestrator.knowledge_evolution_memory import (
    EVENT_CHALLENGED,
    EVENT_REVISED,
    EVENT_SUPPORTED_AFTER_REVISION,
    EVENT_USED_IN_CBE,
)

PROCESS_LEVELS = ("weak", "developing", "healthy", "rigorous")
_CREATED_AT = "1970-01-01T00:00:00+00:00"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _node_type_value(node) -> str:
    return getattr(node.node_type, "value", node.node_type)


def _edge_type_value(edge) -> str:
    return getattr(edge.edge_type, "value", edge.edge_type)


def _stable_id(metrics: Dict, score: float, level: str) -> str:
    payload = json.dumps(
        {"metrics": metrics, "score": round(score, 3), "level": level},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "process_eval_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


@dataclass
class ProcessEvaluation:
    """Meta-evaluation of the dialogue's epistemic process."""

    evaluation_id: str
    process_score: float
    process_level: str
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommended_next_actions: List[str] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    created_at: str = _CREATED_AT

    def to_dict(self) -> dict:
        data = asdict(self)
        data["process_score"] = round(float(self.process_score), 3)
        return data


def _level_for(score: float) -> str:
    if score >= 0.80:
        return "rigorous"
    if score >= 0.60:
        return "healthy"
    if score >= 0.35:
        return "developing"
    return "weak"


def _lineage_event_count(memory, event_type: str) -> int:
    if memory is None:
        return 0
    return sum(1 for event in getattr(memory, "events", []) if event.event_type == event_type)


def _lineage_event_count_any(memory, event_types) -> int:
    if memory is None:
        return 0
    wanted = set(event_types)
    return sum(1 for event in getattr(memory, "events", []) if event.event_type in wanted)


def _metrics(graph: EpistemicGraph, cbe=None, memory=None) -> Dict:
    claims = list(graph.claims.values())
    claim_count = len(claims)
    node_types = [_node_type_value(node) for node in graph.nodes.values()]
    edge_types = [_edge_type_value(edge) for edge in graph.edges.values()]

    evidence_node_count = sum(1 for t in node_types if t == "Evidence")
    evidence_object_count = sum(len(getattr(claim, "evidence", [])) for claim in claims)
    claims_with_evidence = sum(
        1 for claim in claims
        if len(getattr(claim, "evidence", [])) > 0 or getattr(claim, "evidence_quality", 0.0) > 0.0
    )
    challenged_count = sum(1 for claim in claims if getattr(claim, "has_been_challenged", False))
    revision_count = sum(len(getattr(claim, "revision_history", [])) for claim in claims)
    contradiction_count = sum(len(getattr(claim, "contradictions", [])) for claim in claims)
    contradiction_edge_count = sum(1 for t in edge_types if t == EdgeType.CONTRADICTS.value)
    contradiction_node_count = sum(1 for t in node_types if t == "Contradiction")
    open_problem_count = sum(1 for t in node_types if t == "OpenProblem")
    question_count = sum(1 for t in node_types if t == "Question")
    average_confidence = (
        sum(float(getattr(claim, "confidence", 0.0)) for claim in claims) / claim_count
        if claim_count else 0.0
    )
    average_evidence_quality = (
        sum(float(getattr(claim, "evidence_quality", 0.0)) for claim in claims) / claim_count
        if claim_count else 0.0
    )
    unsupported_claim_count = sum(
        1 for claim in claims
        if len(getattr(claim, "evidence", [])) == 0 and getattr(claim, "evidence_quality", 0.0) == 0.0
    )

    lineage_event_count = len(getattr(memory, "events", [])) if memory is not None else 0
    lineage_claim_count = len(getattr(memory, "events_by_claim", {})) if memory is not None else 0
    lineage_challenge_count = _lineage_event_count(memory, EVENT_CHALLENGED)
    lineage_revision_count = _lineage_event_count_any(
        memory, (EVENT_REVISED, EVENT_SUPPORTED_AFTER_REVISION)
    )
    lineage_cbe_use_count = _lineage_event_count(memory, EVENT_USED_IN_CBE)

    cbe_exists = cbe is not None
    cbe_confidence = round(float(getattr(cbe, "confidence", 0.0) or 0.0), 3)
    cbe_strongest_count = len(getattr(cbe, "strongest_claims", []) or []) if cbe_exists else 0
    cbe_unresolved_count = len(getattr(cbe, "unresolved_disagreements", []) or []) if cbe_exists else 0

    evidence_coverage = round(claims_with_evidence / claim_count, 3) if claim_count else 0.0
    challenge_coverage = round(challenged_count / claim_count, 3) if claim_count else 0.0
    unsupported_ratio = round(unsupported_claim_count / claim_count, 3) if claim_count else 0.0

    return {
        "claim_count": claim_count,
        "question_count": question_count,
        "evidence_node_count": evidence_node_count,
        "evidence_object_count": evidence_object_count,
        "claims_with_evidence": claims_with_evidence,
        "evidence_coverage": evidence_coverage,
        "average_evidence_quality": round(average_evidence_quality, 3),
        "challenged_claim_count": challenged_count,
        "challenge_coverage": challenge_coverage,
        "revision_count": revision_count,
        "contradiction_count": contradiction_count,
        "contradiction_edge_count": contradiction_edge_count,
        "contradiction_node_count": contradiction_node_count,
        "open_problem_count": open_problem_count,
        "average_confidence": round(average_confidence, 3),
        "unsupported_claim_count": unsupported_claim_count,
        "unsupported_ratio": unsupported_ratio,
        "lineage_event_count": lineage_event_count,
        "lineage_claim_count": lineage_claim_count,
        "lineage_challenge_count": lineage_challenge_count,
        "lineage_revision_count": lineage_revision_count,
        "lineage_cbe_use_count": lineage_cbe_use_count,
        "cbe_exists": cbe_exists,
        "cbe_confidence": cbe_confidence,
        "cbe_strongest_count": cbe_strongest_count,
        "cbe_unresolved_disagreement_count": cbe_unresolved_count,
    }


def _score(metrics: Dict) -> float:
    if metrics["claim_count"] == 0:
        return 0.0

    score = 0.18
    score += min(0.10, 0.025 * metrics["claim_count"])
    score += 0.16 * metrics["evidence_coverage"]
    score += min(0.08, 0.08 * metrics["average_evidence_quality"])
    score += 0.14 * metrics["challenge_coverage"]
    if metrics["revision_count"] > 0 or metrics["lineage_revision_count"] > 0:
        score += 0.14
    if metrics["cbe_exists"]:
        score += 0.10
        score += min(0.07, 0.07 * metrics["cbe_confidence"])
    if metrics["lineage_event_count"] > 0:
        score += min(0.10, 0.015 * metrics["lineage_event_count"])
    if metrics["question_count"] > 0:
        score += 0.05
    if metrics["cbe_unresolved_disagreement_count"] > 0 or metrics["contradiction_count"] > 0:
        score += 0.03  # disagreement surfaced instead of hidden

    if metrics["unsupported_ratio"] >= 0.75:
        score -= 0.12
    if metrics["challenged_claim_count"] == 0:
        score -= 0.12
    if metrics["revision_count"] == 0 and metrics["lineage_revision_count"] == 0:
        score -= 0.08
    if metrics["open_problem_count"] > 0:
        score -= min(0.10, 0.025 * metrics["open_problem_count"])
    if metrics["average_confidence"] < 0.45:
        score -= 0.05
    if (metrics["contradiction_count"] or metrics["contradiction_edge_count"]) and metrics["revision_count"] == 0:
        score -= 0.08

    return round(_clamp(score), 3)


def _strengths(metrics: Dict) -> List[str]:
    strengths: List[str] = []
    if metrics["claim_count"] >= 2:
        strengths.append("Multiple claims were compared instead of relying on one answer.")
    if metrics["evidence_coverage"] > 0:
        strengths.append("Some claims are connected to evidence or support signals.")
    if metrics["challenged_claim_count"] > 0 or metrics["lineage_challenge_count"] > 0:
        strengths.append("Claims were challenged through Elenchus rather than accepted passively.")
    if metrics["revision_count"] > 0 or metrics["lineage_revision_count"] > 0:
        strengths.append("Claims were revised after challenge, showing process learning.")
    if metrics["lineage_event_count"] > 0:
        strengths.append("Knowledge evolution memory preserved an ordered claim lineage.")
    if metrics["cbe_exists"]:
        strengths.append("A Current Best Explanation was produced from existing claim IDs.")
    if metrics["contradiction_count"] > 0 or metrics["cbe_unresolved_disagreement_count"] > 0:
        strengths.append("Disagreement was surfaced instead of hidden.")
    return strengths


def _weaknesses(metrics: Dict) -> List[str]:
    weaknesses: List[str] = []
    if metrics["claim_count"] == 0:
        weaknesses.append("No claims were available to evaluate.")
    if metrics["unsupported_ratio"] > 0.5:
        weaknesses.append("Evidence coverage is weak for many claims.")
    if metrics["challenged_claim_count"] == 0 and metrics["lineage_challenge_count"] == 0:
        weaknesses.append("No challenge phase tested the claims.")
    if metrics["revision_count"] == 0 and metrics["lineage_revision_count"] == 0:
        weaknesses.append("No revision followed the reasoning process.")
    if metrics["question_count"] == 0:
        weaknesses.append("No Socratic questions were recorded.")
    if metrics["open_problem_count"] > 0:
        weaknesses.append("Open problems or evidence gaps remain unresolved.")
    if metrics["average_confidence"] < 0.45 and metrics["claim_count"] > 0:
        weaknesses.append("Average confidence remains low.")
    if (metrics["contradiction_count"] or metrics["contradiction_edge_count"]) and metrics["revision_count"] == 0:
        weaknesses.append("Contradiction pressure exists without corresponding revision.")
    return weaknesses


def _actions(metrics: Dict, weaknesses: List[str]) -> List[str]:
    actions: List[str] = []
    if metrics["claim_count"] == 0:
        actions.append("Record at least one first-class claim before synthesis.")
    if metrics["unsupported_ratio"] > 0.5:
        actions.append("Ask for stronger evidence and source-grounded support for weak claims.")
    if metrics["challenged_claim_count"] == 0 and metrics["lineage_challenge_count"] == 0:
        actions.append("Run an Elenchus challenge pass against the strongest claim.")
    if metrics["revision_count"] == 0 and metrics["lineage_revision_count"] == 0:
        actions.append("Request revision of claims that survived or failed challenge.")
    if metrics["open_problem_count"] > 0:
        actions.append("Convert open problems into explicit follow-up questions.")
    if not actions:
        actions.append("Continue the dialogue with deeper evidence integration and fresh objections.")
    return actions


def evaluate_process(
    graph: EpistemicGraph,
    cbe=None,
    memory=None,
) -> ProcessEvaluation:
    """Evaluate epistemic health of the process behind a graph/CBE pair."""
    metrics = _metrics(graph, cbe=cbe, memory=memory)
    score = _score(metrics)
    level = _level_for(score)
    strengths = _strengths(metrics)
    weaknesses = _weaknesses(metrics)
    actions = _actions(metrics, weaknesses)
    return ProcessEvaluation(
        evaluation_id=_stable_id(metrics, score, level),
        process_score=score,
        process_level=level,
        strengths=strengths,
        weaknesses=weaknesses,
        recommended_next_actions=actions,
        metrics=metrics,
        created_at=_CREATED_AT,
    )


def evaluate_session(session) -> ProcessEvaluation:
    """Evaluate the live session and store the result additively."""
    graph = getattr(session, "epistemic_graph", EpistemicGraph())
    cbe = getattr(session, "current_best_explanation", None)
    memory = getattr(session, "knowledge_evolution_memory", None)
    evaluation = evaluate_process(graph, cbe=cbe, memory=memory)
    session.process_evaluation = evaluation
    return evaluation

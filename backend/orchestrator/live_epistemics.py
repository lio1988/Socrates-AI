"""Live CED integration helpers for the dialog pipeline.

This module makes the running dialog claim-centric. The old dialogue history is
kept as a trace, but the live source of truth becomes ``session.epistemic_graph``:

* Socratic questions become Question nodes.
* Substantive answers become first-class epistemic Claim objects immediately.
* Elenchus targets a concrete claim_id.
* Revisions update the targeted claim lifecycle.
* Synthesis is derived from the live EpistemicGraph as a CurrentBestExplanation.
"""

from __future__ import annotations

from typing import Optional

from backend.config import EmergenceThresholds
from backend.orchestrator.ced_live_writer import write_answer_to_graph
from backend.epistemic.claim import Claim as EpistemicClaim
from backend.epistemic.epistemic_graph import EpistemicGraph, EdgeType, NodeType
from backend.epistemic.epistemic_state import EpistemicState, IllegalTransition
from backend.epistemic.knowledge_emergence import KnowledgeEmergenceEngine
from backend.reasoning.synthesis_engine import CurrentBestExplanation, SynthesisEngine


def _sync_claim_node(graph: EpistemicGraph, claim: EpistemicClaim) -> None:
    """Keep the graph node mirror aligned with the live Claim object."""
    node = graph.nodes.get(claim.claim_id)
    if node is None:
        return
    node.label = claim.text
    payload = dict(node.payload or {})
    payload.update({
        "state": claim.state.value,
        "confidence": round(claim.confidence, 3),
        "evidence_count": len(claim.evidence),
        "evidence_quality": round(claim.evidence_quality, 3),
        "contradiction_count": len(claim.contradictions),
        "has_been_challenged": claim.has_been_challenged,
        "revision_count": len(claim.revision_history),
    })
    node.payload = payload


def ensure_live_epistemics(session) -> EpistemicGraph:
    """Attach live CED state to a session if it is not already present."""
    graph = getattr(session, "epistemic_graph", None)
    if graph is None:
        graph = EpistemicGraph()
        session.epistemic_graph = graph

    if not hasattr(session, "live_claim_ids_by_round"):
        session.live_claim_ids_by_round = {}
    if not hasattr(session, "live_claim_ids_by_turn"):
        session.live_claim_ids_by_turn = {}
    if not hasattr(session, "epistemic_trace"):
        session.epistemic_trace = []
    if not hasattr(session, "current_best_explanation"):
        session.current_best_explanation = None
    if not hasattr(session, "topic_question_node_id"):
        session.topic_question_node_id = graph.add_node(
            NodeType.QUESTION,
            session.config.topic,
            payload={"source": "user", "role": "root_question"},
        )
        session.epistemic_trace.append(f"Root question: {session.config.topic}")
    return graph


def record_epistemic_question(session, model_id: str, text: str, round_num: int) -> str:
    """Store a Socratic question as a Question node, not as a truth claim."""
    graph = ensure_live_epistemics(session)
    node_id = graph.add_node(
        NodeType.QUESTION,
        text[:400],
        payload={"model_id": model_id, "round": round_num, "role": "socrates"},
    )
    session.epistemic_trace.append(
        f"Round {round_num}: {model_id} asked a Socratic question ({node_id})."
    )
    return node_id


def record_epistemic_claim(session, model_id: str, text: str, round_num: int) -> str:
    """Store a substantive model response as a first-class CED Claim and enrich it live."""
    graph = ensure_live_epistemics(session)
    claim = EpistemicClaim(text=text[:400], author_model=model_id, confidence=0.5)
    graph.add_claim(claim)
    _sync_claim_node(graph, claim)

    write_result = write_answer_to_graph(session, claim.claim_id, model_id, text, round_num)
    _sync_claim_node(graph, claim)

    session.live_claim_ids_by_round[round_num] = claim.claim_id
    turn_index = len(getattr(session, "history", []))
    session.live_claim_ids_by_turn[(round_num, model_id, turn_index)] = claim.claim_id
    session.epistemic_trace.append(
        "Round {round}: {model} proposed claim {claim_id} "
        "(evidence={evidence}, gaps={gaps}, contradictions={contradictions}).".format(
            round=round_num,
            model=model_id,
            claim_id=claim.claim_id,
            evidence=write_result["evidence_count"],
            gaps=write_result["evidence_gap_count"],
            contradictions=write_result["contradiction_count"],
        )
    )
    return claim.claim_id


def latest_claim_id(session, round_num: Optional[int] = None) -> Optional[str]:
    """Return the latest live claim at or before ``round_num``."""
    ensure_live_epistemics(session)
    if not session.live_claim_ids_by_round:
        return None
    if round_num is None:
        round_num = max(session.live_claim_ids_by_round)
    candidates = [r for r in session.live_claim_ids_by_round if r <= round_num]
    if not candidates:
        return None
    return session.live_claim_ids_by_round[max(candidates)]


def get_claim_text(session, claim_id: Optional[str]) -> str:
    graph = ensure_live_epistemics(session)
    if not claim_id or claim_id not in graph.claims:
        return ""
    return graph.claims[claim_id].text


def get_claim_author(session, claim_id: Optional[str]) -> Optional[str]:
    graph = ensure_live_epistemics(session)
    if not claim_id or claim_id not in graph.claims:
        return None
    return graph.claims[claim_id].author_model


def apply_elenchus_to_claim(session, elenchus) -> None:
    """Apply a stored Elenchus result to its targeted live claim."""
    graph = ensure_live_epistemics(session)
    claim_id = getattr(elenchus, "target_claim_id", None)
    if not claim_id or claim_id not in graph.claims:
        return

    claim = graph.claims[claim_id]
    challenge_node = graph.add_node(
        NodeType.CONTRADICTION,
        f"Elenchus by {elenchus.challenger_model} (round {elenchus.round})",
        payload={
            "target_claim_id": claim_id,
            "falsified": elenchus.falsification_successful,
            "challenged_assumptions": elenchus.challenged_assumptions,
            "logic_gaps": elenchus.logic_gaps,
            "evidence_issues": elenchus.evidence_issues,
            "conclusion_issues": elenchus.conclusion_issues,
        },
    )
    graph.link(challenge_node, claim_id, EdgeType.CONTRADICTS)

    try:
        if claim.state in (
            EpistemicState.HYPOTHESIS,
            EpistemicState.SUPPORTED,
            EpistemicState.VERIFIED,
            EpistemicState.REVISED,
        ):
            claim.transition(
                EpistemicState.CHALLENGED,
                actor=f"elenchus:{elenchus.challenger_model}",
                reason="Live Elenchus targeted this claim.",
            )
        if elenchus.falsification_successful:
            claim.adjust_confidence(
                max(0.0, claim.confidence - 0.2),
                actor=f"elenchus:{elenchus.challenger_model}",
                reason="Falsification arguments reduced confidence.",
            )
        else:
            claim.stability_under_challenge += 1
            claim.independent_reviews += 1
            claim.adjust_confidence(
                min(1.0, claim.confidence + 0.05),
                actor=f"elenchus:{elenchus.challenger_model}",
                reason="Claim survived live Elenchus.",
            )
            if claim.state == EpistemicState.CHALLENGED:
                claim.transition(
                    EpistemicState.SUPPORTED,
                    actor="live_epistemics",
                    reason="Claim survived challenge intact.",
                )
        _sync_claim_node(graph, claim)
    except IllegalTransition as exc:
        session.constitution_violations.append(
            f"[CED] Illegal transition for {claim_id}: {exc}"
        )

    session.epistemic_trace.append(
        f"Round {elenchus.round}: Elenchus by {elenchus.challenger_model} targeted {claim_id}."
    )


def apply_revision_to_claim(session, claim_id: Optional[str], revision_text: str, actor: str) -> None:
    """Apply a revision to the concrete claim challenged by Elenchus.

    The revised text becomes the live claim text so the Current Best Explanation
    points at the best current version, not the pre-challenge draft.
    """
    graph = ensure_live_epistemics(session)
    if not claim_id or claim_id not in graph.claims:
        return
    claim = graph.claims[claim_id]
    try:
        previous_text = claim.text
        if claim.state == EpistemicState.CHALLENGED:
            claim.transition(EpistemicState.REVISED, actor=actor, reason="Revised after Elenchus.")
        claim.text = revision_text[:400]
        if claim.state == EpistemicState.REVISED:
            claim.transition(EpistemicState.SUPPORTED, actor=actor, reason="Revision accepted as supported.")
        claim.adjust_confidence(
            min(1.0, claim.confidence + 0.15),
            actor=actor,
            reason="Revision addressed the live challenge.",
        )
        revision_node = graph.add_node(
            NodeType.CLAIM,
            revision_text[:400],
            payload={
                "revises_claim_id": claim_id,
                "actor": actor,
                "previous_text": previous_text[:400],
                "role": "revision_snapshot",
            },
        )
        graph.link(revision_node, claim_id, EdgeType.REFINES)
        _sync_claim_node(graph, claim)
        session.epistemic_trace.append(f"Revision by {actor} refined claim {claim_id}.")
    except IllegalTransition as exc:
        session.constitution_violations.append(
            f"[CED] Illegal revision transition for {claim_id}: {exc}"
        )


def produce_current_best_explanation(session) -> CurrentBestExplanation:
    """Evaluate live knowledge emergence and synthesize the CBE from the graph."""
    graph = ensure_live_epistemics(session)
    for claim in graph.claims.values():
        _sync_claim_node(graph, claim)
    KnowledgeEmergenceEngine(EmergenceThresholds()).evaluate_all(graph)
    for claim in graph.claims.values():
        _sync_claim_node(graph, claim)
    cbe = SynthesisEngine().synthesize(
        session.config.topic,
        graph,
        list(session.epistemic_trace),
    )
    session.current_best_explanation = cbe
    return cbe


"""
Dialog → CED Epistemic Bridge
=============================

The live pipeline now writes directly into ``session.epistemic_graph``. This
bridge therefore first returns the live graph when it exists, and falls back to
legacy post-hoc replay for older sessions.
"""

from __future__ import annotations

from typing import List, Tuple

from ..config import EmergenceThresholds
from .claim import Claim
from .epistemic_state import EpistemicState
from .epistemic_graph import EpistemicGraph, NodeType, EdgeType
from .knowledge_emergence import KnowledgeEmergenceEngine
from ..reasoning.synthesis_engine import SynthesisEngine, CurrentBestExplanation


def _proposal_turns(session):
    """Substantive (non-Elenchus, non-reflection) turns are positions/claims."""
    return [t for t in session.history if not t.is_elenchus and not t.is_reflection]


def _find_target_claim(claims_by_round, round_num):
    """The claim a round-`round_num` Elenchus challenges: the latest proposal
    at or before that round."""
    candidates = [r for r in claims_by_round if r <= round_num]
    if not candidates:
        return None
    return claims_by_round[max(candidates)]


def _live_graph_if_available(session,
                             thresholds: EmergenceThresholds
                             ) -> Tuple[EpistemicGraph, CurrentBestExplanation] | None:
    graph = getattr(session, "epistemic_graph", None)
    if graph is None or not getattr(graph, "claims", None):
        return None

    # Re-evaluate emergence on the live graph before returning the read model.
    KnowledgeEmergenceEngine(thresholds).evaluate_all(graph)
    cbe = getattr(session, "current_best_explanation", None)
    if cbe is None:
        cbe = SynthesisEngine().synthesize(
            session.config.topic,
            graph,
            list(getattr(session, "epistemic_trace", [])),
        )
        session.current_best_explanation = cbe
    return graph, cbe


def build_epistemic_graph(session,
                          thresholds: EmergenceThresholds | None = None
                          ) -> Tuple[EpistemicGraph, CurrentBestExplanation]:
    thresholds = thresholds or EmergenceThresholds()

    live = _live_graph_if_available(session, thresholds)
    if live is not None:
        return live

    graph = EpistemicGraph()
    trace: List[str] = []
    topic = session.config.topic

    graph.add_node(NodeType.QUESTION, topic)
    trace.append(f"Question: {topic}")

    # 1. Each substantive turn becomes a CED claim (HYPOTHESIS).
    claims_by_round = {}
    for t in _proposal_turns(session):
        c = Claim(text=t.content[:400], author_model=t.model_id, confidence=0.5)
        graph.add_claim(c)
        claims_by_round.setdefault(t.round, c)
        trace.append(f"{t.model_id} proposed a position in round {t.round} "
                     f"({c.claim_id})")

    # 2. Replay every Elenchus as a state transition.
    for report in session.elenchus_history:
        target_id = getattr(report, "target_claim_id", None)
        target = graph.claims.get(target_id) if target_id else None
        if target is None:
            target = _find_target_claim(claims_by_round, report.round)
        if target is None:
            continue

        chal_node = graph.add_node(
            NodeType.CONTRADICTION,
            f"Elenchus by {report.challenger_model} (round {report.round})",
            payload={"falsified": report.falsification_successful},
        )
        graph.link(chal_node, target.claim_id, EdgeType.CONTRADICTS)

        if target.state in (EpistemicState.HYPOTHESIS, EpistemicState.SUPPORTED,
                             EpistemicState.VERIFIED, EpistemicState.REVISED):
            target.transition(EpistemicState.CHALLENGED,
                              actor=f"elenchus:{report.challenger_model}",
                              reason="Subjected to Socratic refutation.")

        if report.falsification_successful:
            target.adjust_confidence(
                max(0.0, target.confidence - 0.2),
                actor=f"elenchus:{report.challenger_model}",
                reason="Falsification arguments reduced confidence.")
            if report.revision_submitted:
                target.transition(EpistemicState.REVISED, actor="author",
                                  reason="Revised in response to Elenchus.")
                target.transition(EpistemicState.SUPPORTED, actor="author",
                                  reason="Revision survived; position holds.")
                target.adjust_confidence(min(1.0, target.confidence + 0.25),
                                         actor="author",
                                         reason="Strengthened via revision.")
            else:
                target.transition(EpistemicState.DISPUTED,
                                  actor="bridge",
                                  reason="Falsified without revision; kept visible.")
        else:
            if target.state == EpistemicState.CHALLENGED:
                target.transition(EpistemicState.SUPPORTED, actor="bridge",
                                  reason="Survived challenge intact.")
            target.stability_under_challenge += 1
            target.independent_reviews += 1
            target.adjust_confidence(min(1.0, target.confidence + 0.05),
                                     actor="bridge",
                                     reason="Stability under challenge increased.")

    # 3. Knowledge emergence (evidence-gated; dialogue alone won't hit KNOWLEDGE).
    KnowledgeEmergenceEngine(thresholds).evaluate_all(graph)
    trace.append("Knowledge emergence evaluated (evidence over agreement).")

    # 4. Current Best Explanation.
    cbe = SynthesisEngine().synthesize(topic, graph, trace)
    return graph, cbe

"""CED Graph v1 live writer.

Turns live debate output into graph-native epistemic objects:
agent answer -> claim
evidence markers -> evidence nodes
missing evidence -> evidence gap node
opposition -> contradiction edge
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from backend.epistemic.claim import Claim, Evidence
from backend.epistemic.epistemic_graph import EdgeType, EpistemicGraph, NodeType
from backend.epistemic.epistemic_state import EpistemicState, IllegalTransition


EVIDENCE_MARKERS = (
    "because",
    "according to",
    "evidence",
    "for example",
    "for instance",
    "data",
    "study",
    "source",
    "observed",
    "since ",
    "therefore",
)

OPPOSITION_MARKERS = (
    "not",
    "never",
    "no ",
    "false",
    "incorrect",
    "wrong",
    "disagree",
    "contradicts",
    "opposes",
)

OPPOSITION_PAIRS = (
    ("is", "is not"),
    ("are", "are not"),
    ("can", "cannot"),
    ("can", "can not"),
    ("should", "should not"),
    ("true", "false"),
    ("process", "final answer"),
    ("revisable", "fixed"),
    ("dynamic", "static"),
)


def write_answer_to_graph(session, claim_id: str, model_id: str, text: str, round_num: int) -> dict:
    """Attach evidence/gaps/contradictions for a freshly recorded live claim."""
    graph: EpistemicGraph = session.epistemic_graph
    claim = graph.claims[claim_id]

    evidence_count = 0
    for snippet in _extract_evidence_snippets(text):
        _attach_evidence(graph, claim, snippet, source=model_id, round_num=round_num)
        evidence_count += 1

    gap_count = 0
    if evidence_count == 0:
        _record_evidence_gap(graph, claim, model_id, round_num)
        gap_count = 1

    contradiction_count = _link_live_contradictions(graph, claim, model_id, round_num)

    _refresh_claim_payload(graph, claim)

    return {
        "claim_id": claim_id,
        "evidence_count": evidence_count,
        "evidence_gap_count": gap_count,
        "contradiction_count": contradiction_count,
    }


def _extract_evidence_snippets(text: str) -> list[str]:
    snippets: list[str] = []
    for sentence in _sentences(text):
        lower = sentence.lower()
        if any(marker in lower for marker in EVIDENCE_MARKERS):
            snippets.append(sentence[:320])
        if len(snippets) >= 3:
            break
    return snippets


def _sentences(text: str) -> Iterable[str]:
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentence = sentence.strip()
        if len(sentence) >= 20:
            yield sentence


def _stable_evidence_id(claim_id: str, summary: str, source: str) -> str:
    digest = hashlib.sha256(f"{claim_id}|{source}|{summary}".encode("utf-8")).hexdigest()[:12]
    return f"ev_{digest}"


def _attach_evidence(graph: EpistemicGraph, claim: Claim, summary: str, source: str, round_num: int) -> None:
    ev = Evidence(
        evidence_id=_stable_evidence_id(claim.claim_id, summary, source),
        summary=summary,
        source=source,
        quality=0.35,
        supports=True,
    )

    if all(existing.evidence_id != ev.evidence_id for existing in claim.evidence):
        claim.add_evidence(ev)

    evidence_node_id = graph.add_node(
        NodeType.EVIDENCE,
        summary[:320],
        payload={
            "claim_id": claim.claim_id,
            "source_model": source,
            "round": round_num,
            "quality": ev.quality,
            "supports": True,
            "evidence_id": ev.evidence_id,
        },
    )
    graph.link(evidence_node_id, claim.claim_id, EdgeType.SUPPORTS, weight=ev.quality)

    try:
        if claim.state == EpistemicState.HYPOTHESIS:
            claim.transition(
                EpistemicState.SUPPORTED,
                actor="ced_live_writer",
                reason="Live answer contained evidence/provenance marker.",
            )
    except IllegalTransition:
        pass


def _record_evidence_gap(graph: EpistemicGraph, claim: Claim, model_id: str, round_num: int) -> None:
    gap_node_id = graph.add_node(
        NodeType.OPEN_PROBLEM,
        f"Evidence gap for claim {claim.claim_id}",
        payload={
            "claim_id": claim.claim_id,
            "source_model": model_id,
            "round": round_num,
            "reason": "No explicit evidence/provenance marker detected in live answer.",
        },
    )
    graph.link(claim.claim_id, gap_node_id, EdgeType.DEPENDS_ON, weight=0.5)


def _link_live_contradictions(graph: EpistemicGraph, latest: Claim, model_id: str, round_num: int) -> int:
    linked = 0
    for previous in list(graph.claims.values()):
        if previous.claim_id == latest.claim_id:
            continue
        if previous.author_model == model_id:
            continue

        reason = _explain_if_contradiction(previous.text, latest.text)
        if not reason:
            continue
        if _has_contradiction_edge(graph, previous.claim_id, latest.claim_id):
            continue

        graph.record_contradiction(previous.claim_id, latest.claim_id)
        linked += 1

        contradiction_node_id = graph.add_node(
            NodeType.CONTRADICTION,
            reason,
            payload={
                "claim_a": previous.claim_id,
                "claim_b": latest.claim_id,
                "round": round_num,
                "detected_by": "ced_live_writer",
            },
        )
        graph.link(contradiction_node_id, latest.claim_id, EdgeType.CONTRADICTS, weight=0.7)

        try:
            if latest.state == EpistemicState.SUPPORTED:
                latest.transition(
                    EpistemicState.DISPUTED,
                    actor="ced_live_writer",
                    reason=reason,
                )
            elif latest.state == EpistemicState.HYPOTHESIS:
                latest.transition(
                    EpistemicState.CHALLENGED,
                    actor="ced_live_writer",
                    reason=reason,
                )
        except IllegalTransition:
            pass

    return linked


def _has_contradiction_edge(graph: EpistemicGraph, left: str, right: str) -> bool:
    pair = {left, right}
    for edge in graph.edges.values():
        edge_type = getattr(edge.edge_type, "value", edge.edge_type)
        if edge_type == "contradicts" and {edge.src, edge.dst} == pair:
            return True
    return False


def _explain_if_contradiction(text_a: str, text_b: str) -> str:
    a = _normalize(text_a)
    b = _normalize(text_b)

    for positive, negative in OPPOSITION_PAIRS:
        if _contains_word(a, positive) and _contains_phrase(b, negative):
            return f"Live opposition detected: '{positive}' vs '{negative}'."
        if _contains_phrase(a, negative) and _contains_word(b, positive):
            return f"Live opposition detected: '{negative}' vs '{positive}'."

    if any(marker in b for marker in OPPOSITION_MARKERS):
        overlap = _token_overlap(a, b)
        if overlap >= 0.18:
            return "Live answer appears to negate or dispute an earlier claim."

    return ""


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("n't", " not").split())


def _contains_phrase(text: str, phrase: str) -> bool:
    return phrase in text


def _contains_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _token_overlap(left: str, right: str) -> float:
    left_words = {w for w in re.findall(r"[a-zA-Z]{4,}", left)}
    right_words = {w for w in re.findall(r"[a-zA-Z]{4,}", right)}
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / max(len(left_words | right_words), 1)


def _refresh_claim_payload(graph: EpistemicGraph, claim: Claim) -> None:
    node = graph.nodes.get(claim.claim_id)
    if node is None:
        return
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

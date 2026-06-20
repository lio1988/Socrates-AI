"""Local, deterministic evidence fixtures for the Evidence Layer v0.1.

Turns plain fixture dicts into :class:`Evidence` objects and (optionally)
mirrors them into an :class:`EpistemicGraph` using ONLY existing graph
concepts: ``NodeType.EVIDENCE`` + ``EdgeType.SUPPORTS`` / ``EdgeType.CONTRADICTS``.

No web, no retrieval, no API calls, and no stance *detection* -- the stance is
declared by the fixture. ``verifiable`` is always ``False`` (fixtures only).
"""

from __future__ import annotations

from typing import Dict

from backend.epistemic.claim import Evidence, EvidenceStance
from backend.epistemic.evidence_scoring import effective_stance
from backend.epistemic.epistemic_graph import EpistemicGraph, NodeType, EdgeType

_STANCE_MAP = {
    "supporting": EvidenceStance.SUPPORTING,
    "contradicting": EvidenceStance.CONTRADICTING,
    "weak": EvidenceStance.WEAK,
}


def evidence_from_fixture(fx: Dict, *, index: int = 0) -> Evidence:
    """Build an :class:`Evidence` from a fixture dict.

    Keeps the legacy ``supports`` flag consistent with ``stance`` and keeps the
    legacy ``quality`` in sync with ``strength`` so that existing code paths
    (including ``Claim.evidence_quality``) keep working unchanged.
    """
    stance_raw = str(fx.get("stance", "supporting")).lower()
    stance = _STANCE_MAP.get(stance_raw, EvidenceStance.SUPPORTING)
    strength = float(fx.get("strength", fx.get("quality", 0.0)))
    eid = str(fx.get("evidence_id") or f"ev_{index:03d}")
    return Evidence(
        evidence_id=eid,
        summary=str(fx.get("summary", "")),
        source=fx.get("source"),
        quality=strength,  # keep legacy quality in sync with strength
        supports=(stance != EvidenceStance.CONTRADICTING),  # legacy flag consistent w/ stance
        stance=stance,
        strength=strength,
        source_label=str(fx.get("source_label", "fixture:unspecified")),
        source_type=str(fx.get("source_type", "testimonial")),
        verifiable=False,
    )


def attach_evidence(graph: EpistemicGraph, claim_id: str, ev: Evidence) -> str:
    """Attach evidence to a claim AND mirror it into the graph.

    Adds the Evidence to the Claim (``claim.add_evidence``) and creates a
    ``NodeType.EVIDENCE`` node linked to the claim. Edge direction uses existing
    types: ``CONTRADICTS`` for contradicting evidence, ``SUPPORTS`` otherwise.
    WEAK evidence uses a ``SUPPORTS`` edge for graph compatibility, but its WEAK
    stance is preserved in the Evidence metadata and in ``evidence_status``.

    Returns the new evidence node id.
    """
    claim = graph.claims[claim_id]
    claim.add_evidence(ev)

    stance = effective_stance(ev)
    node_id = graph.add_node(
        NodeType.EVIDENCE,
        label=ev.summary,
        payload={
            "stance": stance.value,
            "strength": ev.strength if ev.strength is not None else ev.quality,
            "source_label": ev.source_label,
            "source_type": ev.source_type,
            "verifiable": ev.verifiable,
            "claim_id": claim_id,
        },
    )
    edge_type = (
        EdgeType.CONTRADICTS
        if stance == EvidenceStance.CONTRADICTING
        else EdgeType.SUPPORTS
    )
    graph.link(node_id, claim_id, edge_type)
    return node_id

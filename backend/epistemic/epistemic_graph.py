"""
Epistemic Graph
===============

More than a knowledge graph: this stores the *evolution of reasoning*, not only
final facts. Nodes are typed epistemic entities (claims, hypotheses, evidence,
questions, contradictions, ...) and edges are typed reasoning relations
(supports, contradicts, refines, replaces, ...).

The graph is the substrate the orchestrator reads to build the Current Best
Explanation and to detect convergence / unresolved disagreement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .claim import Claim


class NodeType(str, Enum):
    CLAIM = "Claim"
    HYPOTHESIS = "Hypothesis"
    EVIDENCE = "Evidence"
    QUESTION = "Question"
    DEFINITION = "Definition"
    CONTRADICTION = "Contradiction"
    PREDICTION = "Prediction"
    THEORY = "Theory"
    PROCEDURE = "Procedure"
    OPEN_PROBLEM = "OpenProblem"


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFINES = "refines"
    REPLACES = "replaces"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    EXPLAINS = "explains"
    PREDICTS = "predicts"
    FALSIFIES = "falsifies"
    GENERALIZES = "generalizes"
    SPECIALIZES = "specializes"


def _now():
    return datetime.now(timezone.utc)


@dataclass
class Node:
    node_id: str
    node_type: NodeType
    label: str
    payload: Optional[dict] = None
    created_at: datetime = field(default_factory=_now)


@dataclass
class Edge:
    edge_id: str
    src: str
    dst: str
    edge_type: EdgeType
    weight: float = 1.0
    created_at: datetime = field(default_factory=_now)


class EpistemicGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.claims: Dict[str, Claim] = {}

    # ---- nodes -----------------------------------------------------------

    def add_claim(self, claim: Claim) -> str:
        self.claims[claim.claim_id] = claim
        self.nodes[claim.claim_id] = Node(
            node_id=claim.claim_id,
            node_type=NodeType.CLAIM,
            label=claim.text,
            payload={"state": claim.state.value},
        )
        return claim.claim_id

    def add_node(self, node_type: NodeType, label: str, payload: Optional[dict] = None) -> str:
        nid = f"{node_type.value.lower()}_{uuid.uuid4().hex[:10]}"
        self.nodes[nid] = Node(node_id=nid, node_type=node_type, label=label, payload=payload)
        return nid

    # ---- edges -----------------------------------------------------------

    def link(self, src: str, dst: str, edge_type: EdgeType, weight: float = 1.0) -> str:
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError("Both endpoints must exist before linking.")
        eid = f"edge_{uuid.uuid4().hex[:10]}"
        self.edges[eid] = Edge(eid, src, dst, edge_type, weight)
        return eid

    def record_contradiction(self, claim_a: str, claim_b: str) -> str:
        if claim_a in self.claims:
            self.claims[claim_a].add_contradiction(claim_b)
        if claim_b in self.claims:
            self.claims[claim_b].add_contradiction(claim_a)
        return self.link(claim_a, claim_b, EdgeType.CONTRADICTS)

    # ---- queries ---------------------------------------------------------

    def neighbors(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[str]:
        out = []
        for e in self.edges.values():
            if e.src == node_id and (edge_type is None or e.edge_type == edge_type):
                out.append(e.dst)
        return out

    def contradictions(self) -> List[Edge]:
        return [e for e in self.edges.values() if e.edge_type == EdgeType.CONTRADICTS]

    def active_claims(self) -> List[Claim]:
        return [c for c in self.claims.values() if c.is_active]

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "type": n.node_type.value,
                    "label": n.label,
                    "payload": n.payload,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "id": e.edge_id,
                    "src": e.src,
                    "dst": e.dst,
                    "type": e.edge_type.value,
                    "weight": e.weight,
                }
                for e in self.edges.values()
            ],
        }

"""
Argumentation harness (v0.1)
============================

Deterministic, local, no-live-call harness for the Abstract Dung grounded
labeling. It loads the sibling benchmark, builds a claim-only EpistemicGraph for
each case (symbolic names -> generated claim ids), applies REJECTED states and
attack edges, runs the read-only grounded labeling, and scores against gold.

No sessions, no models, no network -- it only touches the EpistemicGraph and the
argumentation framework.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.epistemic_graph import EpistemicGraph, EdgeType
from backend.epistemic.argumentation_framework import label_graph
from backend.evaluation import argumentation_metrics as AM

ARG_SCHEMA_VERSION = "ced_argumentation_eval_v0.1"
ARG_HARNESS_VERSION = "ced_argumentation_harness_v0.1"

_DATA = os.path.join(os.path.dirname(__file__), "data", "ced_argumentation_benchmark_v0.json")

_DISCLAIMER = (
    "Argumentation v0.1 (Abstract Dung, grounded semantics, local fixtures). "
    "Labels are structural acceptability, not truth guarantees; they do not "
    "promote or demote claims and do not change CBE ranking."
)


@dataclass
class ArgCase:
    id: str
    claims: List[str]
    attacks: List[dict]
    rejected: List[str] = field(default_factory=list)
    gold: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ArgCase":
        return cls(
            id=d["id"],
            claims=list(d.get("claims", [])),
            attacks=list(d.get("attacks", [])),
            rejected=list(d.get("rejected", [])),
            gold=dict(d.get("gold", {})),
        )


def load_arg_benchmark(path: str = _DATA) -> List[ArgCase]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    schema = data.get("schema_version")
    if schema != ARG_SCHEMA_VERSION:
        raise ValueError(
            f"Argumentation benchmark schema mismatch: expected "
            f"{ARG_SCHEMA_VERSION!r}, got {schema!r}"
        )
    return [ArgCase.from_dict(c) for c in data.get("cases", [])]


def _edge_type(kind: str) -> EdgeType:
    k = str(kind).lower()
    if k == "contradicts":
        return EdgeType.CONTRADICTS
    if k == "falsifies":
        return EdgeType.FALSIFIES
    raise ValueError(f"Unsupported attack type for v0.1: {kind!r}")


def build_graph(case: ArgCase) -> Tuple[EpistemicGraph, Dict[str, str]]:
    """Construct a claim-only graph for a case. Returns (graph, name->claim_id)."""
    graph = EpistemicGraph()
    name_to_cid: Dict[str, str] = {}
    for name in case.claims:
        claim = Claim(text=f"Claim {name}", author_model="bench")
        graph.add_claim(claim)
        name_to_cid[name] = claim.claim_id

    for name in case.rejected:
        graph.claims[name_to_cid[name]].transition(
            EpistemicState.REJECTED, actor="arg-bench", reason="benchmark rejected claim"
        )

    for atk in case.attacks:
        graph.link(
            name_to_cid[atk["src"]],
            name_to_cid[atk["dst"]],
            _edge_type(atk["type"]),
        )
    return graph, name_to_cid


def run_arg_case(case: ArgCase) -> AM.ArgCaseResult:
    graph, name_to_cid = build_graph(case)
    labeling = label_graph(graph)  # read-only
    return AM.score_arg_case(case, labeling, name_to_cid)


@dataclass
class ArgRunReport:
    schema_version: str
    harness: str
    case_count: int
    aggregate: Dict[str, float]
    cases: List[AM.ArgCaseResult]
    semantics: str = "grounded"
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "harness": self.harness,
            "semantics": self.semantics,
            "case_count": self.case_count,
            "aggregate": self.aggregate,
            "cases": [c.to_dict() for c in self.cases],
            "disclaimer": self.disclaimer,
        }


def run_arg_benchmark(path: str = _DATA) -> ArgRunReport:
    cases = load_arg_benchmark(path)
    results = [run_arg_case(c) for c in cases]
    return ArgRunReport(
        schema_version=ARG_SCHEMA_VERSION,
        harness=ARG_HARNESS_VERSION,
        case_count=len(results),
        aggregate=AM.aggregate(results),
        cases=results,
    )

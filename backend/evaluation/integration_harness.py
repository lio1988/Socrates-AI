"""
Integration harness (v0.1)
==========================

Deterministic, local, no-live-call harness for the CED Integration Report. For
each case it builds a claim graph (claims made solid so they surface in raw CBE),
attaches evidence fixtures (to drive evidence_status) and claim-to-claim attacks
(to drive the grounded argumentation label), produces the raw CBE, builds the
read-only integration report, and scores against gold.

It reuses the existing live bridge only to produce the raw CBE; it never calls a
live model (the ScriptedModel stand-in is never invoked).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.orchestrator.session import EnhancedDialogSession
from backend.orchestrator.live_epistemics import (
    ensure_live_epistemics,
    produce_current_best_explanation,
)
from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.epistemic_graph import EpistemicGraph, EdgeType
from backend.epistemic.evidence_fixtures import evidence_from_fixture, attach_evidence
from backend.reasoning.ced_integration_report import build_integration_report
from backend.evaluation.scripted_model import ScriptedModel
from backend.evaluation import integration_metrics as IM

INTEGRATION_SCHEMA_VERSION = "ced_integration_eval_v0.1"
INTEGRATION_HARNESS_VERSION = "ced_integration_harness_v0.1"

_DATA = os.path.join(os.path.dirname(__file__), "data", "ced_integration_benchmark_v0.json")

_DISCLAIMER = (
    "CED Integration Report v0.1 (local fixtures, deterministic). Combines raw "
    "CBE, evidence audit, and grounded argumentation labels into a read-only "
    "report; it does not change CBE ranking, evidence_quality, claim state, or "
    "promotion, and makes no web/API/live-model calls."
)


@dataclass
class IntegrationCase:
    id: str
    focus: Optional[str]
    claims: List[dict]
    attacks: List[dict] = field(default_factory=list)
    gold: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "IntegrationCase":
        return cls(
            id=d["id"],
            focus=d.get("focus"),
            claims=list(d.get("claims", [])),
            attacks=list(d.get("attacks", [])),
            gold=dict(d.get("gold", {})),
        )


def load_integration_benchmark(path: str = _DATA) -> List[IntegrationCase]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    schema = data.get("schema_version")
    if schema != INTEGRATION_SCHEMA_VERSION:
        raise ValueError(
            f"Integration benchmark schema mismatch: expected "
            f"{INTEGRATION_SCHEMA_VERSION!r}, got {schema!r}"
        )
    return [IntegrationCase.from_dict(c) for c in data.get("cases", [])]


def _build_session(case: IntegrationCase):
    cfg = DialogConfig(
        topic=f"integration {case.id}",
        rounds=2,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    session = EnhancedDialogSession(
        f"integ_{case.id}", cfg, {"claude": "x", "chatgpt": "y"}
    )
    session.manager = ScriptedModel({})  # non-live stand-in; never called
    session.enforced_rounds = 2
    ensure_live_epistemics(session)
    return session


def _edge_type(kind: str) -> EdgeType:
    k = str(kind).lower()
    if k == "contradicts":
        return EdgeType.CONTRADICTS
    if k == "falsifies":
        return EdgeType.FALSIFIES
    raise ValueError(f"Unsupported attack type for v0.1: {kind!r}")


def build_case_graph(case: IntegrationCase) -> Tuple[object, EpistemicGraph, Dict[str, str]]:
    """Build session + graph for a case. Returns (session, graph, name->claim_id).

    Claims are built directly and made solid (confidence/challenged/reviews) so
    they surface in raw CBE; evidence fixtures and claim-to-claim attacks are the
    only variables under test.
    """
    session = _build_session(case)
    graph = session.epistemic_graph
    name_to_cid: Dict[str, str] = {}

    for cspec in case.claims:
        name = cspec["name"]
        claim = Claim(text=cspec.get("text", f"Claim {name}"), author_model="bench")
        graph.add_claim(claim)
        name_to_cid[name] = claim.claim_id

        claim.adjust_confidence(
            float(cspec.get("confidence", 0.8)), actor="integ", reason="setup"
        )
        claim.independent_reviews = int(cspec.get("reviews", 3))
        if cspec.get("challenged", True):
            claim.transition(EpistemicState.CHALLENGED, actor="integ", reason="challenge")
            claim.transition(EpistemicState.SUPPORTED, actor="integ", reason="survived")

        for i, fx in enumerate(cspec.get("evidence", [])):
            ev = evidence_from_fixture(fx, index=i)
            attach_evidence(graph, claim.claim_id, ev)

    for atk in case.attacks:
        graph.link(name_to_cid[atk["src"]], name_to_cid[atk["dst"]], _edge_type(atk["type"]))

    return session, graph, name_to_cid


def run_integration_case(case: IntegrationCase) -> IM.IntegrationCaseResult:
    session, graph, name_to_cid = build_case_graph(case)
    raw_cbe = produce_current_best_explanation(session).to_dict()
    report = build_integration_report(raw_cbe, graph)  # read-only
    return IM.score_integration_case(case, report, name_to_cid)


@dataclass
class IntegrationRunReport:
    schema_version: str
    harness: str
    case_count: int
    aggregate: Dict[str, float]
    cases: List[IM.IntegrationCaseResult]
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "harness": self.harness,
            "case_count": self.case_count,
            "aggregate": self.aggregate,
            "cases": [c.to_dict() for c in self.cases],
            "disclaimer": self.disclaimer,
        }


def run_integration_benchmark(path: str = _DATA) -> IntegrationRunReport:
    cases = load_integration_benchmark(path)
    results = [run_integration_case(c) for c in cases]
    return IntegrationRunReport(
        schema_version=INTEGRATION_SCHEMA_VERSION,
        harness=INTEGRATION_HARNESS_VERSION,
        case_count=len(results),
        aggregate=IM.aggregate(results),
        cases=results,
    )

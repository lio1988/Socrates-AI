"""
CED Demo Report service v0.1 (deterministic, local fixtures, no live calls)
===========================================================================

A small demo/runner that makes the already-merged read-only Knowledge OS
pipeline visible end-to-end:

    question -> raw_cbe -> evidence_status -> argumentation_label
             -> final_epistemic_answer -> integration_report

``build_demo_report(case_id)`` is a PURE function returning a JSON-ready dict. It
builds a demo session/graph from local scripted fixtures, produces the raw CBE
with the existing machinery, and wraps it with the existing
``build_integration_report``. It changes nothing in the underlying layers and
makes no web / API / live-model calls. Claim ids are fixed per case so the output
is deterministic.

This module deliberately does NOT touch ``backend/app.py``; a FastAPI endpoint
(``GET /ced/demo-report``) is a trivial additive follow-up that can wrap this
function.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.orchestrator.session import EnhancedDialogSession
from backend.orchestrator.live_epistemics import (
    ensure_live_epistemics,
    produce_current_best_explanation,
)
from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.epistemic_graph import EdgeType
from backend.epistemic.evidence_fixtures import evidence_from_fixture, attach_evidence
from backend.reasoning.ced_integration_report import build_integration_report

DEMO_REPORT_SCHEMA = "ced_demo_report_v0.1"
DEMO_NOTE = "Demo uses scripted local fixtures; not a live answer."


# --------------------------------------------------------------------------- #
# Local scripted demo cases (deterministic). Each claim may carry evidence
# fixtures (drive evidence_status) and claim-to-claim attacks (drive the
# grounded argumentation label). "default" is the clean supported case.
# --------------------------------------------------------------------------- #
_DEMO_CASES: Dict[str, dict] = {
    "default": {
        "question": "Does spaced repetition improve long-term retention?",
        "focus": "A",
        "claims": [
            {
                "name": "A",
                "text": "Spaced repetition improves long-term retention.",
                "evidence": [
                    {"stance": "supporting", "strength": 0.9, "summary": "meta-analysis of spacing studies", "source_label": "fixture:meta"},
                    {"stance": "supporting", "strength": 0.85, "summary": "large classroom replication", "source_label": "fixture:replication"},
                ],
            }
        ],
        "attacks": [],
    },
    "supported_but_defeated": {
        "question": "Do practice hours alone reliably predict expertise?",
        "focus": "A",
        "claims": [
            {
                "name": "A",
                "text": "Deliberate-practice hours alone reliably predict expertise.",
                "evidence": [
                    {"stance": "supporting", "strength": 0.9, "summary": "early expertise study", "source_label": "fixture:study1"},
                    {"stance": "supporting", "strength": 0.85, "summary": "follow-up correlation", "source_label": "fixture:study2"},
                ],
            },
            {
                "name": "B",
                "text": "A meta-analysis finds practice explains only part of expertise variance.",
                "evidence": [],
            },
        ],
        "attacks": [{"type": "falsifies", "src": "B", "dst": "A"}],
    },
    "uncertain": {
        "question": "Does matching instruction to learning styles improve outcomes?",
        "focus": "A",
        "claims": [
            {
                "name": "A",
                "text": "Matching instruction to learning styles improves outcomes.",
                "evidence": [
                    {"stance": "weak", "strength": 0.5, "summary": "small self-report survey", "source_label": "fixture:survey"}
                ],
            },
            {
                "name": "B",
                "text": "Some educators report anecdotal benefits.",
                "evidence": [],
            },
        ],
        "attacks": [],
    },
}


def list_demo_cases() -> List[str]:
    """Available demo case ids, sorted (deterministic)."""
    return sorted(_DEMO_CASES.keys())


def _edge_type(kind: str) -> EdgeType:
    k = str(kind).lower()
    if k == "contradicts":
        return EdgeType.CONTRADICTS
    if k == "falsifies":
        return EdgeType.FALSIFIES
    raise ValueError(f"Unsupported attack type for demo v0.1: {kind!r}")


def _build_demo_graph(case_id: str, case: dict) -> Tuple[object, object, Dict[str, str]]:
    """Build a deterministic demo session + graph from a case spec.

    Claim ids are fixed (``demo_<case_id>_<name>``) so the report is
    reproducible. Claims are made solid (confidence/challenged/reviews) so they
    surface in raw CBE; evidence fixtures and attacks are the only variables.
    No model stand-in is needed (raw CBE generation does not call the manager).
    """
    cfg = DialogConfig(
        topic=case["question"],
        rounds=2,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    session = EnhancedDialogSession(
        f"demo_{case_id}", cfg, {"claude": "x", "chatgpt": "y"}
    )
    ensure_live_epistemics(session)
    graph = session.epistemic_graph

    name_to_cid: Dict[str, str] = {}
    for cspec in case["claims"]:
        name = cspec["name"]
        cid = f"demo_{case_id}_{name}"
        claim = Claim(text=cspec["text"], author_model="demo", claim_id=cid)
        graph.add_claim(claim)
        name_to_cid[name] = cid

        claim.adjust_confidence(
            float(cspec.get("confidence", 0.8)), actor="demo", reason="fixture"
        )
        claim.independent_reviews = int(cspec.get("reviews", 3))
        if cspec.get("challenged", True):
            claim.transition(EpistemicState.CHALLENGED, actor="demo", reason="challenge")
            claim.transition(EpistemicState.SUPPORTED, actor="demo", reason="survived")

        for i, fx in enumerate(cspec.get("evidence", [])):
            attach_evidence(graph, cid, evidence_from_fixture(fx, index=i))

    for atk in case.get("attacks", []):
        graph.link(name_to_cid[atk["src"]], name_to_cid[atk["dst"]], _edge_type(atk["type"]))

    return session, graph, name_to_cid


def _focus_view(report_dict: dict, focus_cid: Optional[str]) -> Optional[dict]:
    if not focus_cid:
        return None
    view = next((c for c in report_dict.get("claims", []) if c["claim_id"] == focus_cid), None)
    if view is None:
        return None
    return {
        "claim_id": view["claim_id"],
        "text": view["text"],
        "evidence_status": view["evidence_status"],
        "argumentation_label": view["argumentation_label"],
        "final_handling": view["final_handling"],
    }


def build_demo_report(case_id: str = "default") -> dict:
    """Build the demo report for ``case_id``. Pure, deterministic, no live calls.

    Raises ``ValueError`` for an unknown ``case_id``.
    """
    if case_id not in _DEMO_CASES:
        raise ValueError(
            f"Unknown demo case_id {case_id!r}. Available: {list_demo_cases()}"
        )
    case = _DEMO_CASES[case_id]

    session, graph, name_to_cid = _build_demo_graph(case_id, case)
    raw_cbe = produce_current_best_explanation(session).to_dict()
    report = build_integration_report(raw_cbe, graph)  # read-only
    report_dict = report.to_dict()

    focus = _focus_view(report_dict, name_to_cid.get(case.get("focus")))

    return {
        "schema_version": DEMO_REPORT_SCHEMA,
        "case_id": case_id,
        "question": case["question"],
        "raw_cbe": raw_cbe,
        "integration_report": report_dict,
        "summary": report.summary,
        "focus": focus,
        "note": DEMO_NOTE,
    }

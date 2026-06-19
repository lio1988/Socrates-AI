"""
CED epistemic API routes (directive §16).

Exposes the claim-centric view derived from a completed dialogue:
  GET /dialog/{id}/epistemic-graph          -> typed claim/contradiction graph
  GET /dialog/{id}/current-best-explanation  -> evidence-aware best explanation

These build on backend.epistemic.dialog_bridge, which replays the dialogue onto
the epistemic state machine.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.orchestrator.session import session_manager
from backend.epistemic.dialog_bridge import build_epistemic_graph
from backend.epistemic.epistemic_state import EpistemicState

router = APIRouter(tags=["CED — Claim-Centric Epistemics"])


@router.get("/dialog/{session_id}/epistemic-graph")
async def get_epistemic_graph(session_id: str):
    s = session_manager.require(session_id)
    graph, _ = build_epistemic_graph(s)
    # Summarise claim states for a quick read.
    state_counts = {}
    for c in graph.claims.values():
        state_counts[c.state.value] = state_counts.get(c.state.value, 0) + 1
    return {
        "session_id": session_id,
        "claim_state_counts": state_counts,
        "claims": [c.to_dict() for c in graph.claims.values()],
        "graph": graph.to_dict(),
    }


@router.get("/dialog/{session_id}/current-best-explanation")
async def get_current_best_explanation(session_id: str):
    s = session_manager.require(session_id)
    _, cbe = build_epistemic_graph(s)
    return cbe.to_dict()

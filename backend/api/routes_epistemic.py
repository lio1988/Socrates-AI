"""
CED epistemic API routes (directive §16).

Exposes the claim-centric view derived from a completed dialogue:
  GET /dialog/{id}/epistemic-graph          -> typed claim/contradiction graph
  GET /dialog/{id}/current-best-explanation  -> evidence-aware best explanation

These build on backend.epistemic.dialog_bridge, which replays the dialogue onto
the epistemic state machine.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from backend.orchestrator.session import session_manager
from backend.epistemic.dialog_bridge import build_epistemic_graph
from backend.epistemic.epistemic_state import EpistemicState
from backend.orchestrator.epistemic_replay import (
    REPLAY_VERSION,
    canonical_replay_json,
    export_audit_trail,
    export_epistemic_replay,
)

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

# ============================================================================
# CED Graph v8 — Epistemic Replay API / Download Endpoint
# ============================================================================

@router.get("/api/epistemic/replay/export/{session_id}", tags=["CED — Replay"])
async def get_epistemic_replay_export(session_id: str):
    """Return the full v7 epistemic replay export for a stored session.

    This endpoint is read-only: it does not create claims, alter CBE ranking,
    or modify the reasoning process.
    """
    s = session_manager.require(session_id)
    return export_epistemic_replay(s)


@router.get("/api/epistemic/replay/audit/{session_id}", tags=["CED — Replay"])
async def get_epistemic_audit_trail(session_id: str):
    """Return the compact audit-trail view for a stored session."""
    s = session_manager.require(session_id)
    return export_audit_trail(s)


@router.get("/api/epistemic/replay/export/{session_id}/canonical", tags=["CED — Replay"])
async def download_canonical_epistemic_replay(session_id: str):
    """Download the canonical deterministic replay JSON for a stored session."""
    s = session_manager.require(session_id)
    payload = canonical_replay_json(s)
    return Response(
        content=payload,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ced-replay-{session_id}.json"',
            "X-CED-Replay-Version": REPLAY_VERSION,
        },
    )


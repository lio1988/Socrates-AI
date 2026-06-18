"""API routes (graph). Extracted from main.py; @app -> APIRouter."""

from __future__ import annotations

import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse
try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:  # older sse-starlette
    from sse_starlette.responses import EventSourceResponse

from socrates_ai import DialogConfig
from backend.storage.models import *
from backend.constitution_guard import ConstitutionGuard, ConstitutionViolationError
from backend.orchestrator.router import classify_domain, select_synthesis_model, assess_complexity
from backend.orchestrator.session import (
    session_manager, get_api_keys, generate_session_id,
    mode_to_model, speed_to_model, summary_to_model,
)
from backend.orchestrator.dialog_pipeline import _run_dialog_pipeline

router = APIRouter()


@router.get("/dialog/{session_id}/contradiction-graph", tags=["Rule 7 — Contradiction Graph"])
async def get_contradiction_graph(session_id: str):
    """
    Rule 7: Contradiction Graph of claims.
    Nodes = claims, Edges = supports / contradicts / depends_on / refines.
    Preserves reasoning history, NOT chat history.
    """
    s = session_manager.require(session_id)
    g = s.contradiction_graph
    return {
        "nodes":         [n.dict() for n in g.nodes],
        "edges":         [e.dict() for e in g.edges],
        "contradictions": sum(1 for e in g.edges if e.edge_type == EdgeType.CONTRADICTS),
        "supports":       sum(1 for e in g.edges if e.edge_type == EdgeType.SUPPORTS),
        "refinements":    sum(1 for e in g.edges if e.edge_type == EdgeType.REFINES),
    }


# ── Rule 8: Knowledge Graph ───────────────────────────────────────────────────


@router.get("/dialog/{session_id}/knowledge-graph", tags=["Rule 8 — Knowledge Graph"])
async def get_knowledge_graph(session_id: str):
    """
    Rule 8: Knowledge Graph — only validated, non-opinion, non-hallucinated concepts.
    Unvalidated concepts are explicitly rejected and logged.
    """
    s = session_manager.require(session_id)
    kg = s.knowledge_graph
    return {
        "validated_concepts": len(kg.concepts),
        "relations":          len(kg.relations),
        "concepts":           [c.dict() for c in kg.concepts],
        "relations_data":     [r.dict() for r in kg.relations],
        "rule_note":          "Only validated=True, is_opinion=False concepts are stored.",
    }


# ── Rule 9: Consensus Memory ──────────────────────────────────────────────────



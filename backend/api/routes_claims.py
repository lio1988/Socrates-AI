"""API routes (claims). Extracted from main.py; @app -> APIRouter."""

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


@router.get("/dialog/{session_id}/claims", tags=["Rule 6 — Fact Verification"])
async def get_claims(
    session_id: str,
    status: Optional[ClaimStatus] = Query(None, description="Filter by status"),
):
    """
    Rule 6: All factual claims with evidence, confidence, source, and status.
    Optionally filter by verification status.
    """
    s = session_manager.require(session_id)
    claims = s.claims
    if status:
        claims = [c for c in claims if c.status == status]
    return {
        "total":       len(s.claims),
        "verified":    sum(1 for c in s.claims if c.status == ClaimStatus.VERIFIED),
        "unverified":  sum(1 for c in s.claims if c.status == ClaimStatus.UNVERIFIED),
        "contradicted": sum(1 for c in s.claims if c.status == ClaimStatus.CONTRADICTED),
        "claims":      [c.dict() for c in claims],
    }


# ── Rule 7: Contradiction Graph ───────────────────────────────────────────────


@router.get("/dialog/{session_id}/consensus", tags=["Rule 9 — Consensus Memory"])
async def get_consensus(session_id: str):
    """
    Rule 9: Consensus Memory.
    Stores ONLY verified conclusions, open questions, remaining disagreements.
    NOT complete conversations.
    """
    s = session_manager.require(session_id)
    cm = s.consensus_memory
    return {
        "verified_conclusions":    [i.dict() for i in cm.verified_conclusions],
        "open_questions":          [i.dict() for i in cm.open_questions],
        "remaining_disagreements": [i.dict() for i in cm.remaining_disagreements],
        "total_items":             cm.total_items,
        "rule_note":               "Complete conversations are NOT stored here.",
    }


# ── Rule 10: Complexity ───────────────────────────────────────────────────────


@router.get("/dialog/{session_id}/elenchus", tags=["Rule 3 — Elenchus"])
async def get_elenchus_history(session_id: str):
    """
    Rule 3: Full Elenchus (falsification) history.
    Shows every answer that was challenged and whether revision was required.
    """
    s = session_manager.require(session_id)
    return {
        "count":                 len(s.elenchus_history),
        "falsifications":        sum(1 for e in s.elenchus_history if e.falsification_successful),
        "revisions_required":    sum(1 for e in s.elenchus_history if e.revision_required),
        "revisions_submitted":   sum(1 for e in s.elenchus_history if e.revision_submitted),
        "elenchus_history":      [e.dict() for e in s.elenchus_history],
        "rule_satisfied":        len(s.elenchus_history) >= s.current_round,
    }


# ── Rule 5: Reflection ────────────────────────────────────────────────────────



"""API routes (export). Extracted from main.py; @app -> APIRouter."""

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


@router.get("/dialog/{session_id}/export", tags=["Dialog"])
async def export_dialog(session_id: str):
    """
    Full export: history, all engine states, Constitution compliance report.
    """
    s = session_manager.require(session_id)
    return {
        "session_id":             s.session_id,
        "topic":                  s.config.topic,
        "mode":                   s.config.mode.value,
        "rounds_completed":       s.current_round,
        "timestamp":              datetime.now().isoformat(),
        "complexity":             s.complexity.dict() if s.complexity else None,
        "convergence_score":      s.convergence_score,
        "consensus_stable":       s.consensus_stable,
        "socratic_rotation":      s.socratic_rotation,
        "history":                [t.dict() for t in s.history],
        "scores":                 s.scores,
        "claims":                 [c.dict() for c in s.claims],
        "contradiction_graph":    s.contradiction_graph.dict(),
        "knowledge_graph":        s.knowledge_graph.dict(),
        "consensus_memory":       s.consensus_memory.dict(),
        "elenchus_history":       [e.dict() for e in s.elenchus_history],
        "reflection_history":     [r.dict() for r in s.reflection_history],
        "synthesis":              s.synthesis_result.dict() if s.synthesis_result else None,
        "evolution_log":          [e.dict() for e in s.evolution_log],
        "constitution_violations": s.constitution_violations,
    }


# ── Pause / Resume / Stop ─────────────────────────────────────────────────────



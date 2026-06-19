"""API routes (dialog). Extracted from main.py; @app -> APIRouter."""

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
from backend.orchestrator.dialog_pipeline_ced import _run_dialog_pipeline

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    """System health — lists configured models"""
    api_keys = get_api_keys()
    return {
        "status":            "healthy",
        "configured_models": list(api_keys.keys()),
        "constitution":      "v0.1",
        "timestamp":         datetime.now().isoformat(),
    }


# ── Constitution (Rule 14: expose rules) ─────────────────────────────────────


@router.get("/constitution", tags=["System"])
async def get_constitution():
    """Return the Engineering Constitution v0.1 rules as structured data"""
    return {
        "version": "v0.1",
        "philosophy": "Truth through structured dialogue. NOT speed. NOT single-model performance.",
        "rules": [
            {"id": 1,  "name": "No Permanent Authority",     "summary": "Socratic role rotates every round"},
            {"id": 2,  "name": "Socratic Dialogue",          "summary": "Every round has a mandatory Socratic phase"},
            {"id": 3,  "name": "Elenchus",                   "summary": "Every answer is challenged via falsification"},
            {"id": 4,  "name": "Maieutic Emergence",         "summary": "Conclusion emerges from dialogue, not authority"},
            {"id": 5,  "name": "Reflection",                 "summary": "Every agent reflects before final submission"},
            {"id": 6,  "name": "Fact Verification",          "summary": "Claims carry evidence, confidence, source, status"},
            {"id": 7,  "name": "Contradiction Graph",        "summary": "All contradictions stored as graph edges"},
            {"id": 8,  "name": "Knowledge Graph",            "summary": "Only validated knowledge in long-term memory"},
            {"id": 9,  "name": "Consensus Memory",           "summary": "Stores conclusions, open questions, disagreements"},
            {"id": 10, "name": "Adaptive Deep Reasoning",    "summary": "Depth scales with topic complexity"},
            {"id": 11, "name": "Consensus Stability",        "summary": "Stops when consensus converges, not by fixed rounds"},
            {"id": 12, "name": "Dynamic Synthesis",          "summary": "Best model for domain performs synthesis"},
            {"id": 13, "name": "Explainability",             "summary": "Every answer includes reasoning, evidence, uncertainty"},
            {"id": 14, "name": "Evolution",                  "summary": "System improves routing and strategy over time"},
            {"id": 15, "name": "Modularity",                 "summary": "Every subsystem is independently replaceable"},
        ],
        "forbidden": [
            "Shortening the Socratic process for speed",
            "Replacing consensus with single-model decision",
            "Permanent authority for one agent",
            "Storing unverified data in the Knowledge Graph",
            "Hiding disagreements in synthesis",
            "Adding new facts during synthesis",
        ],
    }


# ── Start Dialog ─────────────────────────────────────────────────────────────


@router.post("/dialog/start", response_model=dict, tags=["Dialog"])
async def start_dialog(request: DialogStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new Socratic dialog session.

    Constitution enforcements:
    - Rule 10: Rounds may be increased based on complexity assessment
    - Rule 12: Synthesis model selected automatically from domain
    - Rule 1: Socratic rotation initialized
    """
    api_keys = get_api_keys()

    if not api_keys:
        raise HTTPException(500, "No API keys configured.")
    if len(api_keys) < 2:
        raise HTTPException(500, f"Need ≥2 models. Got: {list(api_keys.keys())}")

    # Rule 10: assess complexity → may override requested rounds
    complexity = assess_complexity(request.topic)
    enforced_rounds = ConstitutionGuard.assert_minimum_rounds(request.rounds, complexity)

    if enforced_rounds > request.rounds and not request.force_min_rounds:
        # Inform caller that rounds were increased
        pass

    # Rule 12: determine synthesis model
    domain, domain_reason = classify_domain(request.topic)

    config = DialogConfig(
        topic=request.topic,
        rounds=enforced_rounds,
        mode=mode_to_model(request.mode),
        speed=speed_to_model(request.speed),
        summary_mode=summary_to_model(request.summary_mode),
    )

    session_id = generate_session_id()
    session    = session_manager.create(session_id, config, api_keys)
    session.complexity       = complexity
    session.enforced_rounds  = enforced_rounds
    session.synthesis_domain = domain

    background_tasks.add_task(_run_dialog_pipeline, session_id)

    return {
        "session_id":        session_id,
        "status":            "started",
        "topic":             request.topic,
        "rounds_requested":  request.rounds,
        "rounds_enforced":   enforced_rounds,
        "rounds_increased":  enforced_rounds > request.rounds,
        "complexity":        complexity.dict(),
        "synthesis_domain":  domain.value,
        "synthesis_model":   select_synthesis_model(domain, list(api_keys.keys())),
        "domain_reason":     domain_reason,
        "message":           f"Session '{session_id}' started. Monitor at /dialog/{session_id}",
    }


# ── Status ───────────────────────────────────────────────────────────────────


@router.get("/dialog/{session_id}", response_model=DialogStatusResponse, tags=["Dialog"])
async def get_status(session_id: str):
    """Full session status including all engine states"""
    return session_manager.require(session_id).to_status_response()


# ── Stream (SSE) ─────────────────────────────────────────────────────────────


@router.get("/dialog/{session_id}/stream", tags=["Dialog"])
async def stream_dialog(session_id: str):
    """Real-time Server-Sent Events stream of dialogue progress"""
    session_manager.require(session_id)

    async def generator():
        last_len = 0
        while True:
            s = session_manager.get(session_id)
            if s is None:
                break

            if len(s.history) > last_len:
                for turn in s.history[last_len:]:
                    yield f"data: {json.dumps({'event': 'turn', 'turn': turn.dict()})}\n\n"
                last_len = len(s.history)

            yield f"data: {json.dumps({'event': 'status', 'status': s.status, 'scores': s.scores, 'convergence': s.convergence_score, 'consensus_stable': s.consensus_stable})}\n\n"

            if s.status in ("completed", "error", "stopped"):
                yield f"data: {json.dumps({'event': 'complete', 'status': s.status, 'violations': s.constitution_violations})}\n\n"
                break

            await asyncio.sleep(1)

    return EventSourceResponse(generator())


# ── Rule 1: Socratic Rotation ─────────────────────────────────────────────────


@router.get("/dialog/{session_id}/socratic-rotation", tags=["Rule 1 — No Permanent Authority"])
async def get_socratic_rotation(session_id: str):
    """
    Rule 1: View the Socratic rotation history.
    Proves that no single agent has held permanent authority.
    """
    s = session_manager.require(session_id)
    return {
        "rotation_order":     s.socratic_rotation,
        "current_socrates":   s.current_socrates,
        "rounds_as_socrates": s.rounds_as_socrates,
        "rule_satisfied":     len(set(s.socratic_rotation)) > 1 or s.current_round <= 1,
    }


# ── Rule 3: Elenchus ─────────────────────────────────────────────────────────


@router.get("/dialog/{session_id}/reflections", tags=["Rule 5 — Reflection"])
async def get_reflections(session_id: str):
    """
    Rule 5: Per-agent reflection steps.
    Shows initial reasoning → self-criticism → revision → final reasoning.
    """
    s = session_manager.require(session_id)
    return {
        "count":         len(s.reflection_history),
        "improved":      sum(1 for r in s.reflection_history if r.improved),
        "reflections":   [r.dict() for r in s.reflection_history],
    }


# ── Rule 6: Claims / Fact Verification ───────────────────────────────────────


@router.get("/dialog/{session_id}/complexity", tags=["Rule 10 — Adaptive Deep Reasoning"])
async def get_complexity(session_id: str):
    """Rule 10: Topic complexity assessment driving reasoning depth"""
    s = session_manager.require(session_id)
    if not s.complexity:
        raise HTTPException(404, "Complexity not yet assessed.")
    return s.complexity.dict()


# ── Rule 11: Convergence ─────────────────────────────────────────────────────


@router.get("/dialog/{session_id}/convergence", tags=["Rule 11 — Consensus Stability"])
async def get_convergence(session_id: str):
    """
    Rule 11: Convergence status.
    Dialog continues until consensus stabilises, not by fixed round count.
    """
    s = session_manager.require(session_id)
    return {
        "convergence_score":  s.convergence_score,
        "consensus_stable":   s.consensus_stable,
        "rounds_completed":   s.current_round,
        "rounds_planned":     s.enforced_rounds,
        "stopping_criterion": "convergence",
        "rule_note":          "Dialog stops when convergence ≥ 0.8, not by fixed rounds.",
    }


# ── Rule 12+13: Synthesis ─────────────────────────────────────────────────────


@router.get("/dialog/{session_id}/synthesis", tags=["Rule 12+13 — Dynamic Synthesis + Explainability"])
async def get_synthesis(session_id: str):
    """
    Rule 12: Synthesis performed by domain-best model.
    Rule 13: Full explainability — reasoning, evidence, uncertainty, confidence, alternatives.
    """
    s = session_manager.require(session_id)
    if not s.synthesis_result:
        raise HTTPException(404, "Synthesis not yet produced. Dialog may still be running.")
    return s.synthesis_result.dict()


def _serialize_current_best_explanation(cbe):
    if cbe is None:
        return None
    if hasattr(cbe, "to_dict"):
        return cbe.to_dict()
    if hasattr(cbe, "dict"):
        return cbe.dict()
    return cbe


def _serialize_live_ced_session(s):
    graph = getattr(s, "epistemic_graph", None)
    claims = []
    contradictions = []
    if graph is not None:
        claims = [claim.to_dict() for claim in getattr(graph, "claims", {}).values()]
        contradictions = [
            {
                "contradiction_id": edge.edge_id,
                "claim_a": edge.src,
                "claim_b": edge.dst,
                "type": edge.edge_type.value,
                "weight": edge.weight,
            }
            for edge in getattr(graph, "edges", {}).values()
            if getattr(edge.edge_type, "value", edge.edge_type) == "contradicts"
        ]
    return {
        "session_id": s.session_id,
        "question": s.config.topic,
        "dialogue": [turn.dict() for turn in s.history],
        "claims": claims,
        "contradictions": contradictions,
        "current_best_explanation": _serialize_current_best_explanation(getattr(s, "current_best_explanation", None)),
        "epistemic_events": list(getattr(s, "epistemic_trace", [])),
    }


@router.get("/dialog/{session_id}/ced", tags=["CED Graph v0"])
async def get_ced_response(session_id: str):
    """Return the claim-centric CED response without removing legacy dialogue."""
    s = session_manager.require(session_id)
    return _serialize_live_ced_session(s)


@router.get("/dialog/{session_id}/epistemic-graph", tags=["CED Graph v0"])
async def get_epistemic_graph(session_id: str):
    s = session_manager.require(session_id)
    graph = getattr(s, "epistemic_graph", None)
    if graph is None:
        return {"nodes": [], "edges": [], "claims": []}
    payload = graph.to_dict()
    payload["claims"] = [claim.to_dict() for claim in getattr(graph, "claims", {}).values()]
    return payload


@router.get("/dialog/{session_id}/current-best-explanation", tags=["CED Graph v0"])
async def get_current_best_explanation(session_id: str):
    s = session_manager.require(session_id)
    cbe = getattr(s, "current_best_explanation", None)
    if cbe is None:
        raise HTTPException(404, "Current Best Explanation not yet produced.")
    return _serialize_current_best_explanation(cbe)


# ── Rule 14: Evolution Log ────────────────────────────────────────────────────


@router.get("/dialog/{session_id}/evolution", tags=["Rule 14 — Evolution"])
async def get_evolution_log(session_id: str):
    s = session_manager.require(session_id)
    return {"entries": [e.dict() for e in s.evolution_log], "count": len(s.evolution_log)}


@router.get("/dialog/{session_id}/violations", tags=["Constitution"])
async def get_violations(session_id: str):
    s = session_manager.require(session_id)
    return {
        "count": len(s.constitution_violations),
        "violations": s.constitution_violations,
        "status": "clean" if not s.constitution_violations else "violations_detected",
    }


@router.post("/dialog/{session_id}/pause", tags=["Dialog"])
async def pause_dialog(session_id: str):
    s = session_manager.require(session_id)
    s._paused.clear()
    return {"session_id": session_id, "status": "paused"}


@router.post("/dialog/{session_id}/resume", tags=["Dialog"])
async def resume_dialog(session_id: str):
    s = session_manager.require(session_id)
    s._paused.set()
    return {"session_id": session_id, "status": "resumed"}


@router.post("/dialog/{session_id}/stop", tags=["Dialog"])
async def stop_dialog(session_id: str):
    s = session_manager.require(session_id)
    s._stop_requested = True
    s._paused.set()
    return {"session_id": session_id, "status": "stop_requested"}


@router.post("/dialog/{session_id}/inject", tags=["Dialog"])
async def inject_question(session_id: str, body: InjectQuestionRequest):
    s = session_manager.require(session_id)
    if s.status != "running":
        raise HTTPException(400, "Injection only possible while dialog is running.")
    s.pending_injection = body.question
    return {"session_id": session_id, "queued": body.question}


@router.get("/dialog/list/active", tags=["Dialog"])
async def list_sessions():
    return {"count": len(session_manager._sessions), "sessions": session_manager.list_all()}


@router.delete("/dialog/{session_id}", tags=["Dialog"])
async def delete_session(session_id: str):
    session_manager.require(session_id)
    session_manager.delete(session_id)
    return {"session_id": session_id, "status": "deleted"}



#!/usr/bin/env python3
"""
FastAPI backend for Socratic Dialog with Multiple LLM Models
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Optional, List
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.responses import EventSourceResponse

from socrates_ai import DialogManager, DialogConfig, DialogMode, DialogSpeed, SummaryMode


# ============================================================================
# Request/Response Models
# ============================================================================

class DialogModeEnum(str, Enum):
    """Dialog modes"""
    SOCRATIC = "socratic"
    DEBATE = "debate"
    CONSENSUS = "consensus"


class DialogSpeedEnum(str, Enum):
    """Speed levels"""
    VERY_SLOW = "very_slow"
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    VERY_FAST = "very_fast"


class SummaryModeEnum(str, Enum):
    """Summary modes"""
    NONE = "none"
    EVERY = "every"
    HALF = "half"


class DialogStartRequest(BaseModel):
    """Request to start a dialog session"""
    topic: str = Field(..., min_length=1, max_length=500)
    rounds: int = Field(default=8, ge=1, le=20)
    mode: DialogModeEnum = DialogModeEnum.SOCRATIC
    speed: DialogSpeedEnum = DialogSpeedEnum.NORMAL
    summary_mode: SummaryModeEnum = SummaryModeEnum.EVERY


class DialogTurnResponse(BaseModel):
    """A single turn in the dialog"""
    round: int
    model_id: str
    content: str
    is_socratic: bool
    timestamp: str


class DialogStatusResponse(BaseModel):
    """Current status of a dialog session"""
    session_id: str
    topic: str
    rounds: int
    mode: str
    current_round: int
    status: str  # "running", "completed", "error"
    history: List[DialogTurnResponse]
    scores: dict


class DialogExportResponse(BaseModel):
    """Exported dialog data"""
    topic: str
    mode: str
    rounds: int
    timestamp: str
    history: List[dict]
    scores: dict


# ============================================================================
# Global State Management
# ============================================================================

class DialogSessionManager:
    """Manages active dialog sessions"""
    
    def __init__(self):
        self.sessions = {}
        self.managers = {}
    
    def create_session(self, session_id: str, config: DialogConfig, api_keys: dict):
        """Create a new dialog session"""
        self.sessions[session_id] = {
            "config": config,
            "status": "initialized",
            "created_at": datetime.now(),
            "current_round": 0
        }
        self.managers[session_id] = DialogManager(config, api_keys)
    
    def get_session(self, session_id: str):
        """Get session info"""
        if session_id not in self.sessions:
            return None
        return self.sessions[session_id]
    
    def get_manager(self, session_id: str):
        """Get session's dialog manager"""
        return self.managers.get(session_id)
    
    def update_status(self, session_id: str, status: str):
        """Update session status"""
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = status
    
    def delete_session(self, session_id: str):
        """Delete a session"""
        self.sessions.pop(session_id, None)
        self.managers.pop(session_id, None)


session_manager = DialogSessionManager()


# ============================================================================
# FastAPI App Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle manager"""
    print("🏛️  Socratic Dialog API Server Starting...")
    yield
    print("🛑 Socratic Dialog API Server Shutting Down...")


app = FastAPI(
    title="Socratic Dialog API",
    description="Multi-LLM philosophical dialogue engine",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_api_keys() -> dict:
    """Retrieve configured API keys from environment"""
    api_keys = {
        "claude": os.getenv("ANTHROPIC_API_KEY", ""),
        "grok": os.getenv("XAI_API_KEY", ""),
        "gemini": os.getenv("GOOGLE_API_KEY", ""),
        "chatgpt": os.getenv("OPENAI_API_KEY", ""),
    }
    # Filter to only configured keys
    return {k: v for k, v in api_keys.items() if v}


def speed_enum_to_model(speed: DialogSpeedEnum) -> DialogSpeed:
    """Convert API enum to model enum"""
    mapping = {
        DialogSpeedEnum.VERY_SLOW: DialogSpeed.VERY_SLOW,
        DialogSpeedEnum.SLOW: DialogSpeed.SLOW,
        DialogSpeedEnum.NORMAL: DialogSpeed.NORMAL,
        DialogSpeedEnum.FAST: DialogSpeed.FAST,
        DialogSpeedEnum.VERY_FAST: DialogSpeed.VERY_FAST,
    }
    return mapping[speed]


def mode_enum_to_model(mode: DialogModeEnum) -> DialogMode:
    """Convert API enum to model enum"""
    mapping = {
        DialogModeEnum.SOCRATIC: DialogMode.SOCRATIC,
        DialogModeEnum.DEBATE: DialogMode.DEBATE,
        DialogModeEnum.CONSENSUS: DialogMode.CONSENSUS,
    }
    return mapping[mode]


def summary_enum_to_model(summary_mode: SummaryModeEnum) -> SummaryMode:
    """Convert API enum to model enum"""
    mapping = {
        SummaryModeEnum.NONE: SummaryMode.NONE,
        SummaryModeEnum.EVERY: SummaryMode.EVERY,
        SummaryModeEnum.HALF: SummaryMode.HALF,
    }
    return mapping[summary_mode]


import uuid


def generate_session_id() -> str:
    """Generate unique session ID"""
    return f"dialog_{uuid.uuid4().hex[:12]}"


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    api_keys = get_api_keys()
    return {
        "status": "healthy",
        "configured_models": list(api_keys.keys()),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Dialog Endpoints
# ============================================================================

@app.post("/dialog/start", response_model=dict)
async def start_dialog(request: DialogStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new Socratic dialog session
    
    Returns:
        - session_id: Unique identifier for this dialog
        - status: "started"
        - message: Confirmation message
    """
    api_keys = get_api_keys()
    
    if not api_keys:
        raise HTTPException(
            status_code=500,
            detail="No API keys configured. Set environment variables: ANTHROPIC_API_KEY, XAI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY"
        )
    
    if len(api_keys) < 2:
        raise HTTPException(
            status_code=500,
            detail=f"Need at least 2 models. Got {len(api_keys)}: {', '.join(api_keys.keys())}"
        )
    
    # Create session
    session_id = generate_session_id()
    config = DialogConfig(
        topic=request.topic,
        rounds=request.rounds,
        mode=mode_enum_to_model(request.mode),
        speed=speed_enum_to_model(request.speed),
        summary_mode=summary_enum_to_model(request.summary_mode)
    )
    
    session_manager.create_session(session_id, config, api_keys)
    
    # Schedule dialog to run in background
    background_tasks.add_task(run_dialog_background, session_id)
    
    return {
        "session_id": session_id,
        "status": "started",
        "topic": request.topic,
        "rounds": request.rounds,
        "mode": request.mode.value,
        "message": f"Dialog session {session_id} started. Use /dialog/{session_id} to monitor progress."
    }


async def run_dialog_background(session_id: str):
    """Run dialog in background"""
    try:
        manager = session_manager.get_manager(session_id)
        session_manager.update_status(session_id, "running")
        await manager.run_dialog()
        session_manager.update_status(session_id, "completed")
    except Exception as e:
        print(f"❌ Error in dialog {session_id}: {str(e)}")
        session_manager.update_status(session_id, "error")


@app.get("/dialog/{session_id}", response_model=DialogStatusResponse)
async def get_dialog_status(session_id: str):
    """
    Get the status and history of a dialog session
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    manager = session_manager.get_manager(session_id)
    
    return DialogStatusResponse(
        session_id=session_id,
        topic=session["config"].topic,
        rounds=session["config"].rounds,
        mode=session["config"].mode.value,
        current_round=len([t for t in manager.history if t.round > 0]),
        status=session["status"],
        history=[
            DialogTurnResponse(
                round=turn.round,
                model_id=turn.model_id,
                content=turn.content,
                is_socratic=turn.is_socratic,
                timestamp=turn.timestamp
            )
            for turn in manager.history
        ],
        scores=manager.scores
    )


@app.get("/dialog/{session_id}/stream")
async def stream_dialog(session_id: str):
    """
    Stream dialog updates via Server-Sent Events (SSE)
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    async def event_generator():
        """Generate SSE events for dialog progress"""
        last_history_len = 0
        
        while True:
            manager = session_manager.get_manager(session_id)
            current_session = session_manager.get_session(session_id)
            
            # Send new turns as events
            if len(manager.history) > last_history_len:
                for turn in manager.history[last_history_len:]:
                    yield f"data: {json.dumps({'event': 'turn', 'turn': turn.__dict__})}\n\n"
                last_history_len = len(manager.history)
            
            # Send status update
            yield f"data: {json.dumps({'event': 'status', 'status': current_session['status'], 'scores': manager.scores})}\n\n"
            
            # Break if completed or error
            if current_session["status"] in ["completed", "error"]:
                yield f"data: {json.dumps({'event': 'complete', 'status': current_session['status']})}\n\n"
                break
            
            await asyncio.sleep(1)
    
    return EventSourceResponse(event_generator())


@app.get("/dialog/{session_id}/export", response_model=DialogExportResponse)
async def export_dialog(session_id: str, format: str = "json"):
    """
    Export a completed dialog in the specified format
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    manager = session_manager.get_manager(session_id)
    
    data = {
        "topic": session["config"].topic,
        "mode": session["config"].mode.value,
        "rounds": session["config"].rounds,
        "timestamp": datetime.now().isoformat(),
        "history": [
            {
                "round": turn.round,
                "model_id": turn.model_id,
                "content": turn.content,
                "is_socratic": turn.is_socratic,
                "timestamp": turn.timestamp
            }
            for turn in manager.history
        ],
        "scores": manager.scores
    }
    
    return DialogExportResponse(**data)


@app.delete("/dialog/{session_id}")
async def delete_dialog(session_id: str):
    """
    Delete a dialog session
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    session_manager.delete_session(session_id)
    
    return {
        "session_id": session_id,
        "status": "deleted",
        "message": f"Dialog session {session_id} has been deleted"
    }


@app.get("/dialog/list/active")
async def list_active_dialogs():
    """
    List all active dialog sessions
    """
    sessions = []
    for session_id, session_data in session_manager.sessions.items():
        sessions.append({
            "session_id": session_id,
            "topic": session_data["config"].topic,
            "status": session_data["status"],
            "created_at": session_data["created_at"].isoformat(),
            "rounds": session_data["config"].rounds
        })
    
    return {
        "count": len(sessions),
        "sessions": sessions
    }


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

"""Minimal same-origin HTTP/SSE surface for the local public council bridge."""

from __future__ import annotations

import json
import re
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:  # pragma: no cover - compatibility with older sse-starlette
    from sse_starlette.responses import EventSourceResponse

from backend.dialogues.council_live import LocalCouncilManager


router = APIRouter(prefix="/api/council", tags=["local-council"])
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
_DISALLOWED_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class CouncilQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question

    @field_validator("question")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if _DISALLOWED_CONTROL.search(value):
            raise ValueError("question contains unsupported control characters")
        return value


def _manager(request: Request) -> LocalCouncilManager:
    return request.app.state.local_council_manager


def _run_or_404(request: Request, run_id: str):
    run = _manager(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Council run not found.")
    return run


@router.get("/health")
async def health() -> dict:
    return {
        "status": "available",
        "ced": "real",
        "providers": "offline_mock",
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_council(payload: CouncilQuestion, request: Request) -> dict:
    run = await _manager(request).start_run(payload.question)
    return {"run_id": run.run_id, "status": run.status}


@router.get("/{run_id}")
async def council_status(run_id: str, request: Request) -> dict:
    return _run_or_404(request, run_id).public_snapshot()


@router.get("/{run_id}/events")
async def council_events(
    run_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    run = _run_or_404(request, run_id)
    try:
        cursor = int(last_event_id) if last_event_id is not None else -1
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid event cursor.")
    if cursor < -1:
        raise HTTPException(status_code=400, detail="Invalid event cursor.")

    async def stream():
        async for event in run.subscribe(cursor):
            if await request.is_disconnected():
                break
            yield {
                "id": str(event["sequence"]),
                "event": event["type"],
                "data": json.dumps(event, ensure_ascii=False, separators=(",", ":")),
            }

    return EventSourceResponse(
        stream(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = ["router"]

"""Minimal same-origin HTTP/SSE surface for the local public council bridge."""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:  # pragma: no cover - compatibility with older sse-starlette
    from sse_starlette.responses import EventSourceResponse

from backend.dialogues.council_live import LocalCouncilManager
from backend.dialogues.normal_live import (
    NormalLiveCapacityError,
    NormalLiveCostBlockedError,
    NormalLiveCouncilManager,
    NormalLivePreflightConflictError,
    NormalLivePreflightExpiredError,
    NormalLivePreflightNotFoundError,
    NormalLiveUnavailableError,
)


router = APIRouter(prefix="/api/council", tags=["local-council"])
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
PrivatePreflightId = Annotated[
    str,
    StringConstraints(pattern=r"^nlpf_[a-f0-9]{36}$"),
]
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


class NormalLiveExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preflight_id: PrivatePreflightId = Field(repr=False)
    confirmed: Literal[True]


class NormalLiveCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preflight_id: PrivatePreflightId = Field(repr=False)


def _manager(request: Request) -> LocalCouncilManager:
    return request.app.state.local_council_manager


def _normal_manager(request: Request) -> NormalLiveCouncilManager:
    return request.app.state.normal_live_council_manager


def _run_or_404(request: Request, run_id: str):
    run = _manager(request).get_run(run_id)
    if run is None:
        run = _normal_manager(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Council run not found.")
    return run


def _raise_normal_live_http(error: Exception) -> None:
    if isinstance(error, NormalLiveUnavailableError):
        raise HTTPException(
            status_code=503,
            detail="Normal Live is not yet authorized for this build.",
        )
    if isinstance(error, NormalLiveCapacityError):
        raise HTTPException(
            status_code=503,
            detail="Normal Live is temporarily unavailable.",
        )
    if isinstance(error, NormalLiveCostBlockedError):
        raise HTTPException(
            status_code=403,
            detail="Normal Live exceeds the configured spending limit.",
        )
    if isinstance(error, NormalLivePreflightNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="Normal Live preflight was not found.",
        )
    if isinstance(error, NormalLivePreflightExpiredError):
        raise HTTPException(
            status_code=410,
            detail="Normal Live preflight has expired.",
        )
    if isinstance(error, NormalLivePreflightConflictError):
        raise HTTPException(
            status_code=409,
            detail="Normal Live preflight is no longer usable.",
        )
    raise HTTPException(
        status_code=503,
        detail="Normal Live is temporarily unavailable.",
    )


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


@router.post("/live/preflight")
async def normal_live_preflight(
    payload: CouncilQuestion,
    request: Request,
    response: Response,
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    try:
        return await _normal_manager(request).create_preflight(payload.question)
    except Exception as error:
        _raise_normal_live_http(error)


@router.post(
    "/live/execute",
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_normal_live_preflight(
    payload: NormalLiveExecuteRequest,
    request: Request,
) -> dict:
    try:
        run = await _normal_manager(request).start_run(payload.preflight_id)
    except Exception as error:
        _raise_normal_live_http(error)
    return {"run_id": run.run_id, "status": run.status}


@router.post(
    "/live/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def cancel_normal_live_preflight(
    payload: NormalLiveCancelRequest,
    request: Request,
) -> Response:
    try:
        await _normal_manager(request).cancel_preflight(payload.preflight_id)
    except Exception as error:
        _raise_normal_live_http(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


__all__ = [
    "CouncilQuestion",
    "NormalLiveCancelRequest",
    "NormalLiveExecuteRequest",
    "router",
]

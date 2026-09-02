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

from backend.dialogues.byok_live import (
    ByokCredentialRejectedError,
    ByokLiveCouncilManager,
    ByokRateLimitedError,
)
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
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    MAX_BEARER_CREDENTIAL_BYTES_V1,
)


router = APIRouter(prefix="/api/council", tags=["local-council"])
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
PrivatePreflightId = Annotated[
    str,
    StringConstraints(pattern=r"^nlpf_[a-f0-9]{36}$"),
]
_DISALLOWED_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
#: Loopback hosts that may use plain HTTP for BYOK. Everything else must be
#: HTTPS, because a BYOK request body carries the user's own credential.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"})


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


class ByokExecuteRequest(BaseModel):
    """The one request in the system that carries a user secret.

    ``repr=False`` on both private fields means a logged model, a traceback
    frame or a debugger line shows the field names and not their values. The
    application's validation handler returns a fixed message, so a rejected body
    is never echoed either.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    preflight_id: PrivatePreflightId = Field(repr=False)
    confirmed: Literal[True]
    openrouter_api_key: str = Field(
        repr=False,
        min_length=1,
        max_length=MAX_BEARER_CREDENTIAL_BYTES_V1,
    )


class ByokCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preflight_id: PrivatePreflightId = Field(repr=False)


def _manager(request: Request) -> LocalCouncilManager:
    return request.app.state.local_council_manager


def _normal_manager(request: Request) -> NormalLiveCouncilManager:
    return request.app.state.normal_live_council_manager


def _byok_manager(request: Request) -> ByokLiveCouncilManager:
    return request.app.state.byok_live_council_manager


def _hosted_config(request: Request):
    return getattr(request.app.state, "hosted_config", None)


def _require_enabled(request: Request, attribute: str) -> None:
    """A disabled mode is absent, not forbidden.

    404 rather than 403 on purpose: a public deployment that has not enabled
    operator-funded live has no reason to advertise that the route exists.
    """
    config = _hosted_config(request)
    if config is not None and not getattr(config, attribute):
        raise HTTPException(status_code=404, detail="Not found.")


def _client_identity(request: Request) -> str:
    """The direct connection, never a forwarded header.

    ``X-Forwarded-For`` is caller-controlled unless a specific proxy is known
    and configured, and a limiter keyed on a value the caller picks is not a
    limiter. Trusted-proxy support is a deliberate later configuration step.
    """
    client = request.client
    if client is None or not client.host:
        return "unknown"
    return str(client.host)


def _require_byok_transport_security(request: Request) -> None:
    """BYOK travels only over loopback HTTP or a genuinely secure origin.

    The deployment contract decides which of those two worlds this is; the
    request only decides whether it satisfied that world. A caller can never
    talk its way from hosted into local, because the mode was fixed at startup.
    """
    config = _hosted_config(request)
    host = (request.client.host if request.client else "") or ""
    scheme = (request.url.scheme or "").lower()
    is_loopback = host in _LOOPBACK_HOSTS
    hosted = bool(config is not None and config.https_required)

    if hosted:
        # Loopback is not an escape hatch once a public origin is declared.
        if scheme != "https":
            raise HTTPException(
                status_code=400,
                detail="A secure connection is required for this request.",
            )
        expected_origin = config.public_origin
    else:
        if not is_loopback and scheme != "https":
            raise HTTPException(
                status_code=400,
                detail="A secure connection is required for this request.",
            )
        expected_origin = f"{scheme}://{request.headers.get('host', '')}"

    origin = request.headers.get("origin")
    if origin is not None and origin != expected_origin:
        raise HTTPException(
            status_code=403,
            detail="Cross-origin requests are not accepted.",
        )


def _run_or_404(request: Request, run_id: str):
    run = _manager(request).get_run(run_id)
    if run is None:
        run = _normal_manager(request).get_run(run_id)
    if run is None:
        run = _byok_manager(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Council run not found.")
    return run


def _raise_normal_live_http(error: Exception) -> None:
    if isinstance(error, ByokRateLimitedError):
        raise HTTPException(
            status_code=429,
            detail="Capacity for this preview was temporarily reached.",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    if isinstance(error, ByokCredentialRejectedError):
        raise HTTPException(
            status_code=400,
            detail="The supplied OpenRouter key was rejected.",
        )
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
async def health(request: Request) -> dict:
    """Which modes this deployment offers, and nothing else.

    Two booleans, so the interface can stop guessing which controls to show.
    They say what is enabled, never why: no origin, no limits, no worker count,
    no authorization identity and no filesystem detail.
    """
    config = _hosted_config(request)
    return {
        "status": "available",
        "ced": "real",
        "providers": "offline_mock",
        "modes": {
            "byok": bool(config is None or config.enable_byok),
            "operator_normal_live": bool(
                config is not None and config.enable_operator_normal_live
            ),
        },
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
    _require_enabled(request, "enable_operator_normal_live")
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
    _require_enabled(request, "enable_operator_normal_live")
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
    _require_enabled(request, "enable_operator_normal_live")
    try:
        await _normal_manager(request).cancel_preflight(payload.preflight_id)
    except Exception as error:
        _raise_normal_live_http(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/byok/preflight")
async def byok_preflight(
    payload: CouncilQuestion,
    request: Request,
    response: Response,
) -> dict:
    """Plan a user-funded run. The credential is not an input to this route."""
    _require_enabled(request, "enable_byok")
    _require_byok_transport_security(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    try:
        return await _byok_manager(request).create_preflight(
            payload.question, client=_client_identity(request)
        )
    except Exception as error:
        _raise_normal_live_http(error)


@router.post("/byok/execute", status_code=status.HTTP_202_ACCEPTED)
async def byok_execute(
    payload: ByokExecuteRequest,
    request: Request,
    response: Response,
) -> dict:
    _require_enabled(request, "enable_byok")
    _require_byok_transport_security(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    try:
        run = await _byok_manager(request).start_run(
            payload.preflight_id,
            payload.openrouter_api_key,
            client=_client_identity(request),
        )
    except Exception as error:
        _raise_normal_live_http(error)
    # Only the public run identity is returned. The credential is not echoed,
    # acknowledged, fingerprinted or described.
    return {"run_id": run.run_id, "status": run.status}


@router.post(
    "/byok/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def byok_cancel(payload: ByokCancelRequest, request: Request) -> Response:
    _require_enabled(request, "enable_byok")
    _require_byok_transport_security(request)
    try:
        await _byok_manager(request).cancel_preflight(payload.preflight_id)
    except Exception as error:
        _raise_normal_live_http(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{run_id}")
async def council_status(run_id: str, request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
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
    "ByokCancelRequest",
    "ByokExecuteRequest",
    "CouncilQuestion",
    "NormalLiveCancelRequest",
    "NormalLiveExecuteRequest",
    "router",
]

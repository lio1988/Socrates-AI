"""Dedicated local-only composition root for Socrates UI V0.2.

It intentionally does not import the legacy application, load ``.env`` files,
enable CORS, or mount any private/debug router.

Hosting note: this root serves the static UI and the API from one origin on
purpose. BYOK sends a user credential in a request body, and a cross-origin
split would mean either CORS with credentials or a second trust boundary. One
origin removes the question.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes_council import router as council_router
from backend.dialogues.byok_live import ByokLiveCouncilManager, ByokRateLimiter
from backend.dialogues.council_live import LocalCouncilManager
from backend.dialogues.normal_live import NormalLiveCouncilManager
from backend.hosted_config import (
    HostedConfig,
    load_hosted_config,
    readiness_report,
)


#: Every API body in this application is a short JSON object. The largest
#: legitimate one is a question plus a credential, and 64 KiB is far above that
#: while keeping an unbounded upload from ever reaching a route.
MAX_REQUEST_BODY_BYTES = 64 * 1024

#: No inline script, no inline style and no inline handler exists in ``web/``,
#: so the policy needs no ``unsafe-inline`` escape. ``connect-src 'self'``
#: covers the SSE stream, which is same-origin by construction.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    )
)

#: Nothing in the product needs a camera, a microphone, a location or a payment
#: handler, and a page that accepts a credential should say so explicitly.
PERMISSIONS_POLICY = ", ".join(
    (
        "accelerometer=()",
        "camera=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "payment=()",
        "usb=()",
    )
)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"})

#: Static assets are versioned by content today only by their own bytes, so the
#: preview keeps them revalidated rather than pinned. Anything carrying run
#: state or a credential is never stored at all.
_STATIC_CACHE_CONTROL = "no-cache"
_SENSITIVE_PATH_PREFIXES = ("/api/",)


def _byok_manager_from_config(config: HostedConfig) -> ByokLiveCouncilManager:
    """One place where the deployment contract becomes runtime limits."""
    limiter = ByokRateLimiter(
        max_active_per_client=config.max_active_byok_runs_per_client,
        max_active_global=config.max_active_byok_runs_global,
        max_preflights_per_client=config.byok_preflights_per_10_min,
        max_executions_per_client=config.byok_executions_per_hour,
    )
    if config.run_root:
        return ByokLiveCouncilManager(
            rate_limiter=limiter, run_root=Path(config.run_root)
        )
    return ByokLiveCouncilManager(rate_limiter=limiter)


def create_local_ced_app(
    manager: Optional[LocalCouncilManager] = None,
    *,
    normal_live_manager: Optional[NormalLiveCouncilManager] = None,
    byok_live_manager: Optional[ByokLiveCouncilManager] = None,
    hosted_config: Optional[HostedConfig] = None,
    web_root: Optional[Path] = None,
) -> FastAPI:
    # Loading the contract can refuse outright. That is the intent: an unsafe
    # deployment should fail at startup, not on the first credential.
    config = hosted_config or load_hosted_config()
    local_manager = manager or LocalCouncilManager()
    normal_manager = normal_live_manager or NormalLiveCouncilManager()
    byok_manager = byok_live_manager or _byok_manager_from_config(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.hosted_config = config
        app.state.local_council_manager = local_manager
        app.state.normal_live_council_manager = normal_manager
        app.state.byok_live_council_manager = byok_manager
        try:
            yield
        finally:
            await local_manager.shutdown()
            await normal_manager.shutdown()
            await byok_manager.shutdown()

    app = FastAPI(
        title="Socrates AI Local CED",
        version="0.3",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def _public_validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        # Fixed text. A validation error on the BYOK route would otherwise be
        # the one place a rejected credential could be echoed back to a caller.
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid council request."},
        )

    @app.middleware("http")
    async def _bounded_body_and_security_headers(request: Request, call_next):
        # A disabled mode is refused before routing, so its endpoints are
        # genuinely absent rather than merely unhappy. Checking inside the route
        # would let body validation answer first, and a 422 tells a caller the
        # route exists and what shape it wants.
        path = request.url.path
        if path.startswith("/api/council/byok/") and not config.enable_byok:
            return JSONResponse(status_code=404, content={"detail": "Not found."})
        if (
            path.startswith("/api/council/live/")
            and not config.enable_operator_normal_live
        ):
            return JSONResponse(status_code=404, content={"detail": "Not found."})

        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid council request."}
                )
            if length > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413, content={"detail": "Request body is too large."}
                )

        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        host = (request.client.host if request.client else "") or ""
        # Two independent conditions, both required. The configuration says the
        # deployment is entitled to make the promise; the request says this call
        # actually arrived over TLS. Asserting HSTS from a loopback development
        # server would pin localhost to HTTPS in the developer's browser, which
        # is easy to do by accident and unpleasant to undo.
        if (
            config.may_emit_hsts
            and request.url.scheme == "https"
            and host not in _LOOPBACK_HOSTS
        ):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _SENSITIVE_PATH_PREFIXES):
            # Every API response either carries run state or is a refusal about
            # one. None of it should survive in a shared cache.
            response.headers["Cache-Control"] = "no-store"
            response.headers.setdefault("Pragma", "no-cache")
        else:
            response.headers.setdefault("Cache-Control", _STATIC_CACHE_CONTROL)
        return response

    @app.get("/health", include_in_schema=False)
    async def _health() -> JSONResponse:
        """Liveness only. It answers "is this process running" and nothing else."""
        return JSONResponse({"status": "ok"})

    @app.get("/ready", include_in_schema=False)
    async def _ready() -> JSONResponse:
        """Readiness from local state, with finite reason codes and no detail.

        Deliberately silent about source hashes, Git identities, authorization
        ids, filesystem paths and provider accounts. A readiness probe is an
        unauthenticated endpoint, so everything it says is public.
        """
        status, reasons = readiness_report(config)
        body = {"status": status, "mode": config.mode.value}
        if reasons:
            body["reasons"] = list(reasons)
        return JSONResponse(body, status_code=200 if status == "ok" else 503)

    app.state.hosted_config = config
    app.state.local_council_manager = local_manager
    app.state.normal_live_council_manager = normal_manager
    app.state.byok_live_council_manager = byok_manager
    app.include_router(council_router)

    static_root = web_root or (Path(__file__).resolve().parent.parent / "web")
    app.mount("/", StaticFiles(directory=static_root, html=True), name="socrates-ui")
    return app


app = create_local_ced_app()


__all__ = [
    "CONTENT_SECURITY_POLICY",
    "MAX_REQUEST_BODY_BYTES",
    "PERMISSIONS_POLICY",
    "app",
    "create_local_ced_app",
]

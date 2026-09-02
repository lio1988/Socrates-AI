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
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from backend.api.routes_council import router as council_router
from backend.dialogues.byok_live import ByokLiveCouncilManager, ByokRateLimiter
from backend.dialogues.council_live import LocalCouncilManager
from backend.dialogues.normal_live import NormalLiveCouncilManager
from backend.hosted_config import (
    HostedConfig,
    load_hosted_config,
    readiness_report,
)
from socrates.source_authorization import (
    VerifiedNormalLiveSourceAuthorizationV1,
    verify_production_normal_live_source_authorization_v1,
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


def _forwarded_values(
    headers: Sequence[Tuple[bytes, bytes]], name: bytes
) -> List[str]:
    """Every comma-separated entry of a forwarded header, in wire order."""
    values: List[str] = []
    for key, value in headers:
        if key.lower() != name:
            continue
        for part in value.decode("latin-1").split(","):
            candidate = part.strip()
            if candidate:
                values.append(candidate)
    return values


class _TrustedProxyNormalization:
    """Make a trusted platform proxy's forwarded headers *be* the request.

    This runs outside every other layer, so by the time the transport policy,
    the HSTS decision and the rate-limit identity look at the request, they are
    looking at the connection the public client actually made. That is why none
    of those three had to learn anything about proxies.

    The entry believed is the **last** one, not the first. A client may send its
    own ``X-Forwarded-For`` and the proxy appends the address it observed, so
    the rightmost value is the only one this process did not let the caller
    choose. Reading the leftmost instead would hand every user an unlimited
    supply of rate-limit identities.

    When the configuration does not establish a trust boundary this class is
    inert: the headers are left in place, unread, and the request keeps the
    scheme and peer that the socket actually had.
    """

    def __init__(self, app: Any, *, config: HostedConfig) -> None:
        self._app = app
        self._config = config

    def _peer_is_trusted(self, scope: Dict[str, Any]) -> bool:
        if self._config.trusts_any_peer:
            # The platform gives the service port no public route, so there is
            # no peer address to compare and the topology is the evidence.
            return True
        client = scope.get("client")
        if not client:
            return False
        return str(client[0]) in self._config.trusted_proxy_hosts

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or not self._config.may_trust_forwarded_headers:
            await self._app(scope, receive, send)
            return
        if not self._peer_is_trusted(scope):
            await self._app(scope, receive, send)
            return

        headers = scope.get("headers") or ()
        replacements: Dict[str, Any] = {}

        protocols = _forwarded_values(headers, b"x-forwarded-proto")
        if protocols:
            scheme = protocols[-1].lower()
            if scheme in {"http", "https"}:
                replacements["scheme"] = scheme

        forwarded_for = _forwarded_values(headers, b"x-forwarded-for")
        if forwarded_for:
            candidate = forwarded_for[-1]
            try:
                ip_address(candidate)
            except ValueError:
                # A malformed address is dropped rather than guessed at. The
                # peer stays as it was, which over-counts one platform address
                # instead of inventing a client that may not exist.
                pass
            else:
                existing = scope.get("client")
                port = existing[1] if existing else 0
                replacements["client"] = (candidate, port)

        if replacements:
            scope = {**scope, **replacements}
        await self._app(scope, receive, send)


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
    source_verifier: Optional[Callable[[], Any]] = None,
    web_root: Optional[Path] = None,
) -> FastAPI:
    # Loading the contract can refuse outright. That is the intent: an unsafe
    # deployment should fail at startup, not on the first credential.
    config = hosted_config or load_hosted_config()
    verifier = source_verifier or verify_production_normal_live_source_authorization_v1
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

    # The verifier shells out to Git across the whole authorized path universe,
    # and a platform health check runs every few seconds, so the answer is
    # computed once per process. That is not a staleness risk: this process
    # already holds the imported source, and the execute path re-verifies
    # authorization immediately before it constructs a runtime regardless.
    authorization_probe: Dict[str, bool] = {}

    def _source_is_authorized() -> bool:
        if "authorized" not in authorization_probe:
            try:
                receipt = verifier()
            except Exception:
                # Any failure at all means not authorized. The reason is
                # deliberately discarded here rather than narrowed: a readiness
                # probe is unauthenticated, and a verifier exception can name a
                # path, a digest or a Git object.
                authorization_probe["authorized"] = False
            else:
                # The same exact-type check the live managers make. A verifier
                # that returns something else has not verified anything.
                authorization_probe["authorized"] = (
                    type(receipt) is VerifiedNormalLiveSourceAuthorizationV1
                )
        return authorization_probe["authorized"]

    @app.get("/ready", include_in_schema=False)
    async def _ready() -> JSONResponse:
        """Readiness from local state, with finite reason codes and no detail.

        Deliberately silent about source hashes, Git identities, authorization
        ids, filesystem paths and provider accounts. A readiness probe is an
        unauthenticated endpoint, so everything it says is public.

        When a live mode is enabled this also answers the only question a load
        balancer actually cares about: can this build accept a BYOK preflight?
        An unauthorized build cannot, and used to say "ok" anyway.
        """
        authorized: Optional[bool] = None
        if config.requires_source_authorization:
            authorized = await run_in_threadpool(_source_is_authorized)
        status, reasons = readiness_report(config, source_authorized=authorized)
        body = {"status": status, "mode": config.mode.value}
        if reasons:
            body["reasons"] = list(reasons)
        return JSONResponse(body, status_code=200 if status == "ok" else 503)

    # Added last so it wraps everything above: Starlette applies the most
    # recently added middleware outermost. The security layer, the routes and
    # the rate limiter must all see an already-normalized request.
    app.add_middleware(_TrustedProxyNormalization, config=config)

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

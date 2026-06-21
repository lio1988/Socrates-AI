"""FastAPI application factory for Socrates AI.

Thin composition root: builds the app, applies middleware, and includes the
route modules. All business logic lives in the orchestrator / reasoning /
epistemic packages (directive §3, §15: each engine independent).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

# Load .env (if present) BEFORE anything reads os.environ for API keys.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv optional; env vars may be set externally
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse


class UTF8JSONResponse(JSONResponse):
    """JSONResponse with an explicit charset.

    Starlette's default JSONResponse sends `Content-Type: application/json`
    with NO charset. Without it, some HTTP clients (notably Windows
    PowerShell 5.1's Invoke-RestMethod) guess Latin-1/Windows-1252 instead of
    UTF-8, corrupting any non-ASCII content (Greek text, em-dashes, etc.) into
    mojibake on the client side. The bytes sent over the wire were always
    correct UTF-8; only the missing charset hint was the problem.
    """
    media_type = "application/json; charset=utf-8"

from backend.api.routes_dialog import router as dialog_router
from backend.api.routes_claims import router as claims_router
from backend.api.routes_graph import router as graph_router
from backend.api.routes_export import router as export_router
from backend.api.routes_epistemic import router as epistemic_router
from backend.api.routes_ced_demo import router as ced_demo_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🏛️  Socratic Dialog API — Constitution v0.1 — Starting...")
    yield
    print("🛑  Socratic Dialog API — Shutting Down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Socratic Dialog API",
        description=(
            "Multi-Agent Socratic Reasoning Engine. "
            "Optimizes for Truth through structured dialogue, "
            "NOT speed or single-model performance."
        ),
        version="2.0.0",
        lifespan=lifespan,
        default_response_class=UTF8JSONResponse,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dialog_router)
    app.include_router(claims_router)
    app.include_router(graph_router)
    app.include_router(export_router)
    app.include_router(epistemic_router)
    app.include_router(ced_demo_router)

    # Serve the bundled frontend at the site root, same-origin with the API.
    # Opening frontend.html via file:// triggers Chrome's "unique opaque
    # origin" restriction, which silently blocks fetch() to localhost:8000.
    # Serving it from this same FastAPI app sidesteps that entirely.
    # Only this single file is exposed -- NOT the whole repo (so .env stays
    # inaccessible regardless of what a client requests).
    frontend_path = Path(__file__).resolve().parent.parent / "frontend.html"

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_frontend():
        if not frontend_path.exists():
            return HTMLResponse("<h1>frontend.html not found</h1>", status_code=404)
        return HTMLResponse(frontend_path.read_text(encoding="utf-8"))

    return app


app = create_app()

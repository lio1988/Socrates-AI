"""FastAPI application factory for Socrates AI.

Thin composition root: builds the app, applies middleware, and includes the
route modules. All business logic lives in the orchestrator / reasoning /
epistemic packages (directive §3, §15: each engine independent).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_dialog import router as dialog_router
from backend.api.routes_claims import router as claims_router
from backend.api.routes_graph import router as graph_router
from backend.api.routes_export import router as export_router


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
    return app


app = create_app()

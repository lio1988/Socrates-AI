"""Dedicated local-only composition root for Socrates UI V0.2.

It intentionally does not import the legacy application, load ``.env`` files,
enable CORS, or mount any private/debug router.
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
from backend.dialogues.council_live import LocalCouncilManager
from backend.dialogues.normal_live import NormalLiveCouncilManager


def create_local_ced_app(
    manager: Optional[LocalCouncilManager] = None,
    *,
    normal_live_manager: Optional[NormalLiveCouncilManager] = None,
    web_root: Optional[Path] = None,
) -> FastAPI:
    local_manager = manager or LocalCouncilManager()
    normal_manager = normal_live_manager or NormalLiveCouncilManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.local_council_manager = local_manager
        app.state.normal_live_council_manager = normal_manager
        try:
            yield
        finally:
            await local_manager.shutdown()
            await normal_manager.shutdown()

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
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid council request."},
        )

    app.state.local_council_manager = local_manager
    app.state.normal_live_council_manager = normal_manager
    app.include_router(council_router)

    static_root = web_root or (Path(__file__).resolve().parent.parent / "web")
    app.mount("/", StaticFiles(directory=static_root, html=True), name="socrates-ui")
    return app


app = create_local_ced_app()


__all__ = ["app", "create_local_ced_app"]

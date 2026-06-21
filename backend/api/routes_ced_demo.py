"""
CED demo report API routes (read-only).

Exposes the deterministic demo report (raw CBE + CED Integration Report) over the
already-merged read-only Knowledge OS layers:

  GET /ced/demo-report?case_id=default   -> full demo report JSON for a case
  GET /ced/demo-cases                     -> available demo case ids

Thin wrapper over ``backend.demo.ced_demo_report.build_demo_report``. Scripted
local fixtures only -- no model/provider/web calls and no theory-core changes.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from backend.demo.ced_demo_report import build_demo_report, list_demo_cases

_PANEL_PATH = Path(__file__).resolve().parent.parent / "demo" / "demo_panel.html"

router = APIRouter(tags=["CED — Demo Report"])


@router.get("/ced/demo-report")
def get_demo_report(
    case_id: str = Query("default", description="Demo case id (see /ced/demo-cases)."),
) -> dict:
    """Deterministic demo report for ``case_id``. Scripted fixtures; not a live answer."""
    try:
        return build_demo_report(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/ced/demo-cases")
def get_demo_cases() -> dict:
    """List the available demo case ids."""
    return {"cases": list_demo_cases()}


@router.get("/ced/demo-panel", response_class=HTMLResponse, include_in_schema=False)
def get_demo_panel() -> HTMLResponse:
    """Serve the self-contained CED demo UI panel (static HTML).

    The panel is a single file with inline CSS + vanilla JS and no external
    assets; it fetches the existing ``/ced/demo-report`` endpoint client-side.
    Only this one file is exposed -- no other repo path is served.
    """
    if not _PANEL_PATH.exists():
        return HTMLResponse("<h1>demo_panel.html not found</h1>", status_code=404)
    return HTMLResponse(_PANEL_PATH.read_text(encoding="utf-8"))

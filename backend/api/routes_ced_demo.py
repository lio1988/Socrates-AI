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

from fastapi import APIRouter, HTTPException, Query

from backend.demo.ced_demo_report import build_demo_report, list_demo_cases

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

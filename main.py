#!/usr/bin/env python3
"""Socratic Dialog API — thin entrypoint.

The monolith was refactored into the `backend/` package (directive §3, §15, §18):
  backend/storage/models.py        — data models + enums
  backend/constitution_guard.py    — 15-rule runtime enforcement
  backend/orchestrator/            — router, convergence, session, dialog_pipeline
  backend/api/                     — routes_dialog / routes_claims / routes_graph / routes_export
  backend/app.py                   — FastAPI factory (create_app)

Run:  uvicorn backend.app:app --reload
  or: python main.py
"""

from backend.app import app  # re-exported so `uvicorn main:app` still works

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)

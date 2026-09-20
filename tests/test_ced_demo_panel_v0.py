"""
Tests for the CED demo UI panel (GET /ced/demo-panel).

Verifies the panel route serves the self-contained HTML with the required hooks
(case selector, the three case ids, a client-side fetch to /ced/demo-report, and
the pipeline field names), that it carries no external assets, that the existing
demo routes and root route are unaffected, and that serving the panel makes no
live model/provider calls.
"""

import pytest

from fastapi.testclient import TestClient

from backend.app import create_app

client = TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 50000))


@pytest.fixture(scope="module")
def panel_html() -> str:
    r = client.get("/ced/demo-panel")
    assert r.status_code == 200
    return r.text


def test_demo_panel_returns_200():
    assert client.get("/ced/demo-panel").status_code == 200


def test_demo_panel_media_type_is_html():
    r = client.get("/ced/demo-panel")
    assert r.headers["content-type"].startswith("text/html")


def test_panel_contains_case_selector(panel_html):
    assert "caseSelector" in panel_html
    assert "Demo case" in panel_html


def test_panel_contains_all_three_case_ids(panel_html):
    assert "default" in panel_html
    assert "supported_but_defeated" in panel_html
    assert "uncertain" in panel_html


def test_panel_fetches_demo_report_endpoint(panel_html):
    assert "/ced/demo-report" in panel_html
    assert "fetch(" in panel_html


def test_panel_contains_pipeline_field_hooks(panel_html):
    for hook in ("Question", "Raw CBE", "evidence_status", "argumentation_label", "final_handling"):
        assert hook in panel_html


def test_panel_handles_both_verdict_branches(panel_html):
    # both the clean-primary and the humble no-clean-answer paths are wired
    assert "has_clean_primary" in panel_html
    assert "no_clean_answer" in panel_html


def test_panel_has_no_external_assets(panel_html):
    # self-contained: no external scripts, styles, fonts, or CDN references
    lowered = panel_html.lower()
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "src=" not in lowered          # no external <script src>/<img src>
    assert "cdn" not in lowered
    assert "fonts.googleapis" not in lowered
    assert "@import" not in lowered


def test_existing_demo_report_route_unaffected():
    r = client.get("/ced/demo-report?case_id=default")
    assert r.status_code == 200
    assert r.json()["schema_version"] == "ced_demo_report_v0.1"


def test_existing_demo_cases_route_unaffected():
    r = client.get("/ced/demo-cases")
    assert r.status_code == 200
    assert "default" in r.json()["cases"]


def test_existing_root_route_unaffected():
    assert client.get("/").status_code == 200


def test_panel_makes_no_live_calls(monkeypatch):
    import socrates_ai

    def boom(*a, **k):
        raise AssertionError("live model call while serving demo panel")

    for m in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, m):
            monkeypatch.setattr(socrates_ai.DialogManager, m, boom, raising=False)

    assert client.get("/ced/demo-panel").status_code == 200

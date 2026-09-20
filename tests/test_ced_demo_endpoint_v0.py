"""
Tests for the CED demo report FastAPI endpoint (GET /ced/demo-report).

Verifies the endpoint returns the deterministic demo report JSON for each case,
handles an unknown case_id with a 400, lists cases, exposes the full pipeline
output, leaves existing routes intact, and makes no live model calls.
"""

from fastapi.testclient import TestClient

from backend.app import create_app

client = TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 50000))


def test_demo_report_default():
    r = client.get("/ced/demo-report")
    assert r.status_code == 200
    d = r.json()
    assert d["schema_version"] == "ced_demo_report_v0.1"
    assert d["case_id"] == "default"
    assert d["summary"]["has_clean_primary"] is True
    assert d["focus"]["final_handling"] == "primary_candidate"


def test_demo_report_supported_but_defeated():
    r = client.get("/ced/demo-report", params={"case_id": "supported_but_defeated"})
    assert r.status_code == 200
    d = r.json()
    assert d["focus"]["final_handling"] == "well_supported_but_defeated"
    assert d["summary"]["has_clean_primary"] is False


def test_demo_report_uncertain():
    r = client.get("/ced/demo-report?case_id=uncertain")
    assert r.status_code == 200
    d = r.json()
    assert d["summary"]["has_clean_primary"] is False
    assert d["summary"]["no_clean_answer"]


def test_demo_report_unknown_case_id_returns_400():
    r = client.get("/ced/demo-report?case_id=does_not_exist")
    assert r.status_code == 400
    assert "Unknown demo case_id" in r.json()["detail"]


def test_demo_cases_endpoint_lists_cases():
    r = client.get("/ced/demo-cases")
    assert r.status_code == 200
    cases = set(r.json()["cases"])
    assert {"default", "supported_but_defeated", "uncertain"} <= cases


def test_response_includes_full_pipeline_parts():
    d = client.get("/ced/demo-report").json()
    for key in ("question", "raw_cbe", "integration_report", "summary"):
        assert key in d
    claims = d["integration_report"]["claims"]
    assert claims
    first = claims[0]
    assert "evidence_status" in first
    assert "argumentation_label" in first
    assert "final_handling" in first


def test_existing_route_intact_and_new_routes_added():
    # Existing frontend route still served -> the additive change didn't break
    # the app's existing routing.
    assert client.get("/").status_code == 200
    # New CED demo routes are present and working alongside the existing ones.
    assert client.get("/ced/demo-report").status_code == 200
    assert client.get("/ced/demo-cases").status_code == 200


def test_endpoint_makes_no_live_calls(monkeypatch):
    import socrates_ai

    def boom(*a, **k):
        raise AssertionError("live model call via demo endpoint")

    for m in ("_call_model", "_call_claude", "_call_openai", "_call_grok", "_call_gemini"):
        if hasattr(socrates_ai.DialogManager, m):
            monkeypatch.setattr(socrates_ai.DialogManager, m, boom, raising=False)

    r = client.get("/ced/demo-report")
    assert r.status_code == 200

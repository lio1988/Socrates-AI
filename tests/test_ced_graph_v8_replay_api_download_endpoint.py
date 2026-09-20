"""CED Graph v8 — Epistemic Replay API / Download Endpoint tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.orchestrator.epistemic_replay import canonical_replay_json
from backend.orchestrator.live_epistemics import (
    apply_elenchus_to_claim,
    apply_revision_to_claim,
    produce_current_best_explanation,
    record_epistemic_claim,
    record_epistemic_question,
)
from backend.orchestrator.session import session_manager


def _client():
    return TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 50000))


def _session(topic="Is knowledge a process or a final answer?"):
    return SimpleNamespace(
        config=SimpleNamespace(topic=topic),
        constitution_violations=[],
        history=[],
    )


def _elenchus(claim_id, challenger="grok", round_num=1, falsified=True):
    return SimpleNamespace(
        target_claim_id=claim_id,
        challenger_model=challenger,
        round=round_num,
        falsification_successful=falsified,
        challenged_assumptions=["assumes certainty is stable"],
        logic_gaps=["unsupported universal conclusion"] if falsified else [],
        evidence_issues=[],
        conclusion_issues=[],
    )


def _rich_session():
    s = _session()
    record_epistemic_question(s, "socrates", "What would make this claim false?", 1)
    c1 = record_epistemic_claim(
        s,
        "claude",
        "Knowledge is a revisable process because evidence can change what is justified.",
        1,
    )
    record_epistemic_claim(
        s,
        "chatgpt",
        "A final answer can still be provisional when stronger evidence appears.",
        1,
    )
    apply_elenchus_to_claim(s, _elenchus(c1, falsified=True))
    apply_revision_to_claim(
        s,
        c1,
        "Knowledge is a revisable process, but the reliability of revision also matters.",
        actor="claude",
    )
    produce_current_best_explanation(s)
    return s


def _register(session):
    session_id = f"v8-{uuid4().hex}"
    session.session_id = session_id
    session_manager._sessions[session_id] = session
    return session_id


def _remove(session_id):
    session_manager._sessions.pop(session_id, None)


def test_openapi_exposes_v8_replay_routes():
    client = _client()
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/epistemic/replay/export/{session_id}" in paths
    assert "/api/epistemic/replay/audit/{session_id}" in paths
    assert "/api/epistemic/replay/export/{session_id}/canonical" in paths


def test_replay_export_endpoint_returns_full_payload():
    session = _rich_session()
    session_id = _register(session)
    try:
        response = _client().get(f"/api/epistemic/replay/export/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["replay_version"] == "v7"
        assert payload["metadata"]["claim_count"] >= 2
        assert payload["graph"]["nodes"]
        assert payload["claim_timeline"]
        assert payload["current_best_explanation"] is not None
        assert payload["process_evaluation"] is not None
        assert payload["audit_checks"]["cbe_invents_no_new_claims"] is True
    finally:
        _remove(session_id)


def test_audit_endpoint_returns_compact_payload():
    session = _rich_session()
    session_id = _register(session)
    try:
        response = _client().get(f"/api/epistemic/replay/audit/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["replay_version"] == "v7"
        assert "metadata" in payload
        assert "audit_checks" in payload
        assert "claim_timeline" in payload
        assert "graph" not in payload
        assert payload["current_best_explanation"] is not None
        assert payload["process_evaluation"] is not None
    finally:
        _remove(session_id)


def test_canonical_download_endpoint_is_deterministic_and_downloadable():
    session = _rich_session()
    session_id = _register(session)
    try:
        client = _client()
        first = client.get(f"/api/epistemic/replay/export/{session_id}/canonical")
        second = client.get(f"/api/epistemic/replay/export/{session_id}/canonical")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.text == second.text
        assert first.text == canonical_replay_json(session)
        assert first.headers["x-ced-replay-version"] == "v7"
        assert "attachment" in first.headers["content-disposition"]
        assert f"ced-replay-{session_id}.json" in first.headers["content-disposition"]
        assert first.headers["content-type"].startswith("application/json")
    finally:
        _remove(session_id)


def test_missing_session_returns_404():
    response = _client().get("/api/epistemic/replay/export/not-a-real-session")
    assert response.status_code == 404
    assert "not-a-real-session" in response.json()["detail"]


def test_empty_session_exports_safely_through_endpoint():
    session = _session("Empty topic")
    session_id = _register(session)
    try:
        response = _client().get(f"/api/epistemic/replay/export/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["metadata"]["claim_count"] == 0
        assert payload["graph"]["nodes"] == []
        assert payload["claim_timeline"] == []
        assert payload["current_best_explanation"] is None
        assert payload["process_evaluation"] is None
        assert payload["audit_checks"]["cbe_invents_no_new_claims"] is True
    finally:
        _remove(session_id)


def test_replay_export_endpoint_is_read_only_and_stable():
    session = _rich_session()
    session_id = _register(session)
    try:
        before = canonical_replay_json(session)
        client = _client()
        a = client.get(f"/api/epistemic/replay/export/{session_id}").json()
        b = client.get(f"/api/epistemic/replay/export/{session_id}").json()
        after = canonical_replay_json(session)
        assert a == b
        assert before == after
        assert len(session.epistemic_graph.claims) == a["metadata"]["claim_count"]
    finally:
        _remove(session_id)

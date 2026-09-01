"""HTTP/SSE and static-boundary tests for the local-only Socrates V0.2 app."""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from backend.local_ced_app import create_local_ced_app


SECRET = "sk-or-v1-THIS-MUST-NEVER-REACH-BROWSER"
VALIDATION_ERROR = {"detail": "Invalid council request."}


def _wait_for_terminal(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        response = client.get(f"/api/council/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "blocked", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("local offline council did not reach a terminal state")


def test_health_and_frozen_ui_are_served_same_origin():
    with TestClient(create_local_ced_app()) as client:
        health = client.get("/api/council/health")
        assert health.status_code == 200
        assert health.json() == {
            "status": "available",
            "ced": "real",
            "providers": "offline_mock",
        }
        page = client.get("/")
        assert page.status_code == 200
        assert "DEMO MODE" in page.text
        assert "LOCAL CED" in page.text


def test_question_contract_rejects_blank_overlong_and_browser_authority_fields():
    with TestClient(create_local_ced_app()) as client:
        invalid_payloads = (
            {"question": "   "},
            {"question": SECRET + "x" * 8001},
            {"question": "Valid?", "phase": SECRET, "ratified": True},
            {},
            {"question": None},
            {"question": ["not", SECRET]},
            {"question": {"text": SECRET}},
            {"question": "valid", "provider_id": SECRET},
            {"question": "valid", "run_id": SECRET},
            {"question": f"bad\x00{SECRET}"},
        )
        for payload in invalid_payloads:
            response = client.post("/api/council", json=payload)
            assert response.status_code == 422
            assert response.json() == VALIDATION_ERROR
            assert SECRET not in response.text


def test_post_status_and_sse_are_public_safe_and_replayable():
    app = create_local_ced_app()
    with TestClient(app) as client:
        created = client.post(
            "/api/council",
            json={"question": "Should a city use an AI scheduling assistant?"},
            headers={"Authorization": f"Bearer {SECRET}"},
        )
        assert created.status_code == 202
        body = created.json()
        assert set(body) == {"run_id", "status"}
        run_id = body["run_id"]
        terminal = _wait_for_terminal(client, run_id)
        assert terminal["status"] in {"completed", "blocked"}

        with client.stream("GET", f"/api/council/{run_id}/events") as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            all_lines = list(stream.iter_lines())
            lines = [line for line in all_lines if line.startswith("data: ")]

        events = [json.loads(line[6:]) for line in lines]
        assert events[0]["type"] == "run.started"
        assert events[-1]["type"] == "run.completed"
        assert [event["sequence"] for event in events] == list(range(len(events)))
        assert [line for line in all_lines if line.startswith("id: ")] == [
            f"id: {event['sequence']}" for event in events
        ]

        cursor = events[-2]["sequence"]
        with client.stream(
            "GET",
            f"/api/council/{run_id}/events",
            headers={"Last-Event-ID": str(cursor)},
        ) as replay:
            replay_lines = [line for line in replay.iter_lines() if line.startswith("data: ")]
        replay_events = [json.loads(line[6:]) for line in replay_lines]
        assert [event["sequence"] for event in replay_events] == [cursor + 1]

        serialized = json.dumps(
            {"created": body, "status": terminal, "events": events},
            ensure_ascii=False,
        ).lower()
        for forbidden in (
            SECRET.lower(),
            "authorization",
            "bearer",
            "raw_text",
            "error_message",
            "provider_id",
            "model_id",
            "task_log",
            "score_breakdown",
            "leaderboard",
            "traceback",
            ".env",
        ):
            assert forbidden not in serialized


def test_unknown_run_and_static_traversal_fail_safely():
    with TestClient(create_local_ced_app()) as client:
        missing = client.get("/api/council/not-a-run")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Council run not found."}
        traversal = client.get("/%2e%2e/.env")
        assert traversal.status_code == 404
        assert SECRET not in traversal.text


def test_dedicated_app_has_no_cross_origin_or_private_debug_surface():
    with TestClient(create_local_ced_app()) as client:
        hostile = client.get(
            "/api/council/health",
            headers={"Origin": "https://hostile.invalid"},
        )
        assert hostile.status_code == 200
        assert "access-control-allow-origin" not in hostile.headers
        assert "access-control-allow-credentials" not in hostile.headers
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/api/dialog").status_code == 404

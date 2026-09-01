"""HTTP/SSE and static-boundary tests for the local-only Socrates V0.2 app."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.local_ced_app import create_local_ced_app
from backend.dialogues.normal_live import NormalLiveCouncilManager
from socrates.source_authorization import (
    NormalLiveSourceAuthorizationError,
    VerifiedNormalLiveSourceAuthorizationV1,
)


SECRET = "sk-or-v1-THIS-MUST-NEVER-REACH-BROWSER"
SECRET_QUESTION = (
    SECRET
    + "\nAuthorization: Bearer THIS-MUST-NOT-LEAK"
    + "\nC:\\private\\secret\\path"
)
VALIDATION_ERROR = {"detail": "Invalid council request."}


def _source_receipt() -> VerifiedNormalLiveSourceAuthorizationV1:
    return VerifiedNormalLiveSourceAuthorizationV1(
        authorization_id="normallivesourceauthv1_" + "a" * 64,
        source_set_digest="a" * 64,
        authorized_implementation_commit_sha="a" * 40,
        authorized_implementation_tree_sha="a" * 40,
        runtime_identity="normal-socrates-browser-runtime/v1",
    )


def _authorized_normal_manager(tmp_path, *, transport=None) -> NormalLiveCouncilManager:
    return NormalLiveCouncilManager(
        source_verifier=_source_receipt,
        transport=transport,
        run_root=tmp_path / "runs",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def _wait_for_terminal(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        response = client.get(f"/api/council/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "blocked", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("local offline council did not reach a terminal state")


def test_private_preflight_request_models_redact_capability_repr() -> None:
    from backend.api.routes_council import (
        NormalLiveCancelRequest,
        NormalLiveExecuteRequest,
    )

    raw_id = "nlpf_" + "a" * 36
    execute = NormalLiveExecuteRequest(preflight_id=raw_id, confirmed=True)
    cancel = NormalLiveCancelRequest(preflight_id=raw_id)
    assert raw_id not in repr(execute)
    assert raw_id not in repr(cancel)
    assert execute.model_dump() == {"preflight_id": raw_id, "confirmed": True}
    assert cancel.model_dump() == {"preflight_id": raw_id}


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


def test_normal_live_preflight_fail_closed_response_is_public_safe(tmp_path):
    def unavailable_source():
        raise NormalLiveSourceAuthorizationError("test-only source refusal")

    manager = NormalLiveCouncilManager(
        source_verifier=unavailable_source,
        run_root=tmp_path / "runs",
    )
    with TestClient(create_local_ced_app(normal_live_manager=manager)) as client:
        response = client.post(
            "/api/council/live/preflight",
            json={"question": "Is this build explicitly authorized?"},
        )
        assert response.status_code == 503
        assert response.json() == {
            "detail": "Normal Live is not yet authorized for this build."
        }
        serialized = response.text.lower()
        for forbidden in (
            "manifest",
            "authorization_id",
            "source_set",
            "commit",
            "tree",
            "path",
            "traceback",
        ):
            assert forbidden not in serialized


def test_normal_live_preflight_cancel_and_strict_request_contracts(tmp_path):
    normal_manager = _authorized_normal_manager(tmp_path)
    with TestClient(
        create_local_ced_app(normal_live_manager=normal_manager)
    ) as client:
        for payload in (
            {},
            {"question": "   "},
            {"question": "Valid?", "provider_count": 3},
            {"question": "Valid?", "maximum_calls": 1},
            {"question": "Valid?", "authorization_id": SECRET},
        ):
            response = client.post("/api/council/live/preflight", json=payload)
            assert response.status_code == 422
            assert response.json() == VALIDATION_ERROR
            assert SECRET not in response.text

        preflight = client.post(
            "/api/council/live/preflight",
            json={"question": SECRET_QUESTION},
        )
        assert preflight.status_code == 200
        body = preflight.json()
        assert set(body) == {
            "preflight_id",
            "approval_reference",
            "question_sha256",
            "question",
            "run_mode",
            "seats",
            "provider_count",
            "base_calls",
            "retry_calls",
            "maximum_calls",
            "maximum_cost_usd",
            "confirmation_required",
            "source_authorization_status",
            "validity_seconds",
            "expires_at_utc",
        }
        assert body["provider_count"] == len(body["seats"]) == 3
        assert body["maximum_calls"] == body["base_calls"] + body["retry_calls"]
        assert body["maximum_cost_usd"] == str(body["maximum_cost_usd"])
        assert re.fullmatch(
            r"normalapprovalv1_[0-9a-f]{64}", body["approval_reference"]
        )
        assert re.fullmatch(r"[0-9a-f]{64}", body["question_sha256"])
        assert body["validity_seconds"] == 900
        assert body["expires_at_utc"] == "2026-09-01T00:15:00Z"
        assert preflight.headers["cache-control"] == "no-store"
        assert preflight.headers["pragma"] == "no-cache"
        assert preflight.headers["referrer-policy"] == "no-referrer"
        assert preflight.headers["x-content-type-options"] == "nosniff"
        raw_id = body["preflight_id"]
        safe_body = {key: value for key, value in body.items() if key != "preflight_id"}
        assert raw_id not in json.dumps(
            {"headers": dict(preflight.headers), "body": safe_body}
        )
        serialized_preflight = json.dumps(
            {"headers": dict(preflight.headers), "body": body}
        ).lower()
        for forbidden in (
            SECRET.lower(),
            "authorization: bearer this-must-not-leak",
            r"c:\private\secret\path",
        ):
            assert forbidden not in serialized_preflight

        preflight_id = body["preflight_id"]
        approval_reference = body["approval_reference"]
        for invalid in (
            {},
            {"confirmed": False, "preflight_id": preflight_id},
            {"confirmed": True},
            {"confirmed": True, "preflight_id": approval_reference},
            {
                "confirmed": True,
                "preflight_id": preflight_id,
                "approval_reference": approval_reference,
            },
            {"confirmed": True, "preflight_id": preflight_id, "run_id": SECRET},
        ):
            response = client.post("/api/council/live/execute", json=invalid)
            assert response.status_code == 422
            assert response.json() == VALIDATION_ERROR
            assert preflight_id not in response.text
            assert approval_reference not in response.text

        guessed = client.post(
            "/api/council/live/execute",
            json={"preflight_id": "nlpf_" + "f" * 36, "confirmed": True},
        )
        assert guessed.status_code == 404
        assert preflight_id not in guessed.text
        assert approval_reference not in guessed.text

        bad_cancel = client.post(
            "/api/council/live/cancel",
            json={"preflight_id": preflight_id, "reason": SECRET},
        )
        assert bad_cancel.status_code == 422
        assert bad_cancel.json() == VALIDATION_ERROR
        reference_cancel = client.post(
            "/api/council/live/cancel",
            json={"preflight_id": approval_reference},
        )
        assert reference_cancel.status_code == 422
        assert reference_cancel.json() == VALIDATION_ERROR
        cancelled = client.post(
            "/api/council/live/cancel", json={"preflight_id": preflight_id}
        )
        assert cancelled.status_code == 204
        assert cancelled.content == b""
        replay = client.post(
            "/api/council/live/execute",
            json={"preflight_id": preflight_id, "confirmed": True},
        )
        assert replay.status_code == 409
        assert replay.json() == {
            "detail": "Normal Live preflight is no longer usable."
        }
        assert normal_manager.runs == {}
        assert not (tmp_path / "runs").exists()


def test_expired_private_preflight_cannot_execute(tmp_path):
    now = [100.0]
    manager = NormalLiveCouncilManager(
        source_verifier=_source_receipt,
        transport=lambda **_kwargs: pytest.fail("transport must remain unreachable"),
        run_root=tmp_path / "runs",
        monotonic_clock=lambda: now[0],
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
        preflight_ttl_seconds=1,
    )
    with TestClient(create_local_ced_app(normal_live_manager=manager)) as client:
        preflight = client.post(
            "/api/council/live/preflight",
            json={"question": "Expire this private capability."},
        ).json()
        now[0] = 101.0
        expired = client.post(
            "/api/council/live/execute",
            json={"preflight_id": preflight["preflight_id"], "confirmed": True},
        )
        assert expired.status_code == 410
        assert expired.json() == {
            "detail": "Normal Live preflight has expired."
        }
        assert preflight["preflight_id"] not in expired.text
        assert preflight["approval_reference"] not in expired.text
        assert manager.runs == {}
        assert not (tmp_path / "runs").exists()


def test_authorized_normal_execute_status_sse_and_replay_are_public_safe(tmp_path):
    from tests_dialogues.test_normal_live_lifecycle import (
        SECRET_CANARIES,
        SECRET_QUESTION,
        _DeterministicWireTransport,
    )

    transport = _DeterministicWireTransport()
    normal_manager = _authorized_normal_manager(tmp_path, transport=transport)
    with TestClient(
        create_local_ced_app(normal_live_manager=normal_manager)
    ) as client:
        preflight = client.post(
            "/api/council/live/preflight",
            json={"question": SECRET_QUESTION},
            headers={"Authorization": f"Bearer {SECRET}"},
        )
        assert preflight.status_code == 200
        preflight_body = preflight.json()
        preflight_id = preflight_body["preflight_id"]
        approval_reference = preflight_body["approval_reference"]
        started = client.post(
            "/api/council/live/execute",
            json={"preflight_id": preflight_id, "confirmed": True},
        )
        assert started.status_code == 202
        assert set(started.json()) == {"run_id", "status"}
        run_id = started.json()["run_id"]
        assert started.json()["status"] != "queued"
        started_run = normal_manager.get_run(run_id)
        assert started_run is not None
        assert started_run.events[0]["type"] == "run.started"
        terminal = _wait_for_terminal(client, run_id)
        assert terminal["status"] in {"completed", "blocked"}

        with client.stream("GET", f"/api/council/{run_id}/events") as stream:
            assert stream.status_code == 200
            lines = [line for line in stream.iter_lines() if line.startswith("data: ")]
        events = [json.loads(line[6:]) for line in lines]
        assert events[0]["type"] == "run.started"
        assert events[-1]["type"] == "run.completed"
        assert "phase.started" in {event["type"] for event in events}
        assert "move.accepted" in {event["type"] for event in events}

        cursor = events[-2]["sequence"]
        with client.stream(
            "GET",
            f"/api/council/{run_id}/events",
            headers={"Last-Event-ID": str(cursor)},
        ) as replay:
            replay_events = [
                json.loads(line[6:])
                for line in replay.iter_lines()
                if line.startswith("data: ")
            ]
        assert [event["sequence"] for event in replay_events] == [cursor + 1]

        consumed = client.post(
            "/api/council/live/execute",
            json={"preflight_id": preflight_id, "confirmed": True},
        )
        assert consumed.status_code == 409
        assert preflight_id not in consumed.text
        assert approval_reference not in consumed.text
        assert preflight_id not in json.dumps(started.json())
        assert preflight_id not in json.dumps(terminal)
        assert preflight_id not in json.dumps(events)
        for artifact in (tmp_path / "runs").rglob("*"):
            if artifact.is_file():
                assert preflight_id.encode("utf-8") not in artifact.read_bytes()
        serialized = json.dumps(
            {
                "preflight_headers": dict(preflight.headers),
                "preflight": {
                    key: value
                    for key, value in preflight_body.items()
                    if key != "preflight_id"
                },
                "started_headers": dict(started.headers),
                "started": started.json(),
                "status": terminal,
                "events": events,
            },
            ensure_ascii=False,
        ).lower()
        for canary in SECRET_CANARIES:
            assert canary.lower() not in serialized
        assert transport.calls > 0
